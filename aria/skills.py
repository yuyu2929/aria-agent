"""技能系统：SKILL.md 知识包 + 分段递进 + 时间衰退。

相对原型的改动：
- 自研分段器（markdown 标题 + 句子边界正则），不再依赖 MPL-2.0 的 yasbd
- 状态持久化在 SQLite，不再用全局 dict
- 衰退规则延续原型并参数化：保鲜期内使用可恢复，超时不用则按时间衰减
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .ledger import Ledger
from .models import SkillState, TxKind
from .storage import Database
from .wallet import InsufficientFunds, Wallet

_SENTENCE_END = re.compile(r"(?<=[.!?。！？])\s+")


def segment_text(text: str) -> list[str]:
    """把 SKILL.md 切成可递进的段：先按 markdown 结构，再按句子。"""
    blocks = re.split(r"\n\s*\n", text)
    segments: list[str] = []
    for block in blocks:
        lines = [ln for ln in block.splitlines() if ln.strip()]
        # 标题行各自成段
        buf: list[str] = []
        for ln in lines:
            if ln.lstrip().startswith("#"):
                if buf:
                    segments.extend(_split_sentences("\n".join(buf)))
                    buf = []
                segments.append(ln.strip())
            else:
                buf.append(ln)
        if buf:
            segments.extend(_split_sentences("\n".join(buf)))
    return [s for s in (seg.strip() for seg in segments) if s]


def _split_sentences(text: str) -> list[str]:
    return [s for s in (p.strip() for p in _SENTENCE_END.split(text)) if s]


class SkillManager:
    def __init__(
        self,
        db: Database,
        wallet: Wallet,
        events,
        skills_dir: Path,
        config,
    ):
        self.db = db
        self.wallet = wallet
        self.events = events
        self.dir = Path(skills_dir)
        self.config = config
        self.catalog = self._load_catalog()

    def _load_catalog(self) -> dict:
        manifest = self.dir / "manifest.json"
        if not manifest.exists():
            return {}
        return json.loads(manifest.read_text())

    def _content(self, name: str) -> str:
        p = self.dir / name / "SKILL.md"
        if p.exists():
            return p.read_text()
        p = self.dir / f"{name}.md"
        if p.exists():
            return p.read_text()
        return ""

    def listing(self) -> str:
        lines = ["SKILLS:"]
        for name, m in sorted(self.catalog.items()):
            owned = " [OWNED]" if self.is_owned(name) else ""
            lines.append(f"- {name} | price: {m['price']} | {m['description']}{owned}")
        return "\n".join(lines)

    # ---- 状态 ----
    def _state(self, name: str) -> SkillState | None:
        row = self.db.query_one("SELECT * FROM skill_states WHERE name=?", (name,))
        if not row:
            return None
        return SkillState(
            name=row["name"], owned=bool(row["owned"]), calls=row["calls"],
            max_lines=row["max_lines"], available_lines=row["available_lines"],
            last_used=row["last_used"], decay_speed=row["decay_speed"],
        )

    def _save_state(self, st: SkillState) -> None:
        self.db.execute(
            "INSERT INTO skill_states(name, owned, calls, max_lines, available_lines, "
            "last_used, decay_speed) VALUES(?,?,?,?,?,?,?) "
            "ON CONFLICT(name) DO UPDATE SET owned=excluded.owned, calls=excluded.calls, "
            "max_lines=excluded.max_lines, available_lines=excluded.available_lines, "
            "last_used=excluded.last_used, decay_speed=excluded.decay_speed",
            (st.name, int(st.owned), st.calls, st.max_lines, st.available_lines,
             st.last_used, st.decay_speed),
        )

    def is_owned(self, name: str) -> bool:
        st = self._state(name)
        return bool(st and st.owned and st.available_lines > 0)

    def owned_names(self) -> list[str]:
        return [r["name"] for r in self.db.query("SELECT name FROM skill_states WHERE owned=1")]

    def health(self) -> dict:
        out = {}
        for name in self.catalog:
            st = self._state(name)
            out[name] = {
                "owned": bool(st and st.owned),
                "available_lines": st.available_lines if st else 0,
                "max_lines": st.max_lines if st else 0,
                "calls": st.calls if st else 0,
            }
        return out

    # ---- 交易 ----
    def buy(self, name: str) -> str:
        if name not in self.catalog:
            return f"Skill '{name}' not listed"
        if self.is_owned(name):
            return f"You already know '{name}'"
        m = self.catalog[name]
        price = int(m["price"])
        try:
            self.wallet.pay(price, TxKind.SKILL_PURCHASE, ref=name, note=f"learn {name}")
        except InsufficientFunds:
            self.events.log("skill_declined_price", ref=name, payload={"price": price})
            return f"Insufficient coins to learn '{name}' ({price} needed)"
        segments = segment_text(self._content(name))
        st = self._state(name) or SkillState(name=name)
        st.owned = True
        st.max_lines = len(segments)
        st.available_lines = len(segments)
        st.decay_speed = float(m.get("decay_speed", 0.1))
        self._save_state(st)
        self.events.log("skill_bought", ref=name, payload={"price": price, "segments": len(segments)})
        return f"Learned skill '{name}' for {price} coins"

    # ---- 使用（带时间衰退）----
    def use(self, name: str) -> dict:
        st = self._state(name)
        if not st or not st.owned:
            return {"result": f"'{name}' is not an owned skill.", "usage": {}}
        if st.available_lines <= 0:
            self.events.log("skill_forgotten", ref=name, payload={"reason": "fully_decayed"})
            return {"result": f"Skill '{name}' has fully decayed from disuse.", "usage": {}}

        eco = self.config.economy
        now = datetime.now(timezone.utc)
        decayed = 0
        if st.last_used:
            last = datetime.fromisoformat(st.last_used)
            hours = (now - last).total_seconds() / 3600
            if hours < eco.freshness_hours:
                st.available_lines = min(st.max_lines, st.available_lines + eco.skill_regain_lines)
            else:
                decayed = int(st.decay_speed * (hours - eco.freshness_hours) * 5)
                st.available_lines = max(0, st.available_lines - decayed)
                if decayed:
                    self.events.log("skill_decayed", ref=name, payload={"lost_segments": decayed, "idle_hours": round(hours, 1)})

        segments = segment_text(self._content(name))
        context = "\n".join(segments[: st.available_lines])
        st.calls += 1
        st.last_used = now.isoformat()
        self._save_state(st)
        self.events.log(
            "skill_used", ref=name,
            payload={"available_lines": st.available_lines, "decayed": decayed},
        )
        return {
            "result": context,
            "usage": {"calls": st.calls, "available_lines": st.available_lines},
        }

    def descriptions(self) -> str:
        entries = [
            f"- {name}: {self.catalog[name]['description']}"
            for name in self.owned_names()
            if name in self.catalog
        ]
        return "\n".join(entries) if entries else "No owned skills"
