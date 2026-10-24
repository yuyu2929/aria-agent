"""语义记忆系统。

相对原型的三处硬伤修复：
1. 不再硬编码安卓/Termux 路径——embedder 可插拔
2. 维度一致——HashEmbedder 固定 256 维，向量库里存的就是 256 维
3. 不再用"按空格切词"的玩具 tokenizer——hashing-trick 嵌入 + 可选 OpenAI 兼容端点

零依赖可跑（纯 Python 余弦相似度），也可接真实 embedding 服务。
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import uuid
from datetime import datetime, timezone

from .safeval import safe_eval
from .storage import Database

DIM = 256
_WORD = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")


class HashEmbedder:
    """确定性 hashing-trick 嵌入：零依赖、可复现、维度固定。"""

    dim = DIM

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * DIM
        for tok in _WORD.findall(text.lower()):
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            idx = h % DIM
            sign = 1.0 if (h >> 16) & 1 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


class OpenAIEmbedder:
    """可选：任何 OpenAI 兼容的 /embeddings 端点。"""

    def __init__(self, base_url: str, api_key: str, model: str, dim: int = DIM):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        import urllib.request

        req = urllib.request.Request(
            f"{self.base_url}/embeddings",
            data=json.dumps({"model": self.model, "input": text}).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read())
        return payload["data"][0]["embedding"]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


class MemoryStore:
    """增、删、改、查（top-k + 安全过滤表达式）。"""

    def __init__(self, db: Database, embedder=None):
        self.db = db
        self.embedder = embedder or HashEmbedder()

    def add(self, memories: list[dict]) -> list[str]:
        ids = []
        for mem in memories:
            content = mem.get("content", "")
            if not content:
                raise ValueError("content key is required in each memory")
            mid = mem.get("id") or str(uuid.uuid4())
            metadata = dict(mem.get("metadata") or {})
            metadata["content"] = content
            self.db.execute(
                "INSERT INTO memories(id, content, metadata, embedding, updated_at) "
                "VALUES(?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET content=excluded.content, "
                "metadata=excluded.metadata, embedding=excluded.embedding, "
                "updated_at=excluded.updated_at",
                (
                    mid, content, json.dumps(metadata),
                    json.dumps(self.embedder.embed(content)),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            ids.append(mid)
        return ids

    def delete(self, ids: list[str]) -> None:
        for mid in ids:
            self.db.execute("DELETE FROM memories WHERE id=?", (mid,))

    def _passes(self, entry: dict, filters: list[str]) -> bool:
        for expr in filters:
            try:
                if not safe_eval(expr, entry):
                    return False
            except Exception:
                return False
        return True

    def search(self, query: str, top_k: int = 10, filters: list[str] | None = None) -> list[dict]:
        filters = filters or []
        qv = self.embedder.embed(query)
        scored = []
        for row in self.db.query("SELECT id, content, metadata, embedding FROM memories"):
            meta = json.loads(row["metadata"])
            entry = dict(meta)
            entry.setdefault("content", row["content"])
            if not self._passes(entry, filters):
                continue
            sim = _cosine(qv, json.loads(row["embedding"]))
            scored.append({"id": row["id"], "score": round(sim, 4), **entry})
        scored.sort(key=lambda r: r["score"], reverse=True)
        return scored[:top_k]
