"""LLM 客户端：两种驱动，同一接口。

- OpenAIClient：任何 OpenAI 兼容端点（Cerebras / OpenAI / vLLM / Ollama…）
- EchoClient：脚本化确定性驱动——无 API key 也能跑测试和实验

接口统一为 chat(messages, tools) -> {"content": str, "tool_calls": [{"name", "arguments"}]}
"""
from __future__ import annotations

import json
import os
import urllib.request


class ChatResponse:
    def __init__(self, content: str = "", tool_calls: list | None = None, tokens_used: int = 0):
        self.content = content
        self.tool_calls = tool_calls or []
        self.tokens_used = tokens_used

    @property
    def is_final(self) -> bool:
        return not self.tool_calls


class OpenAIClient:
    def __init__(self, base_url: str | None = None, api_key: str | None = None, model: str | None = None):
        self.base_url = (base_url or os.getenv("ARIA_BASE_URL", "https://api.cerebras.ai/v1")).rstrip("/")
        self.api_key = api_key or os.getenv("ARIA_API_KEY", "")
        self.model = model or os.getenv("ARIA_MODEL", "gpt-oss-120b")

    def chat(self, messages: list[dict], tools: list[dict]) -> ChatResponse:
        if not self.api_key:
            raise RuntimeError("ARIA_API_KEY not set — use EchoClient or export a key")
        payload = {"model": self.model, "messages": messages, "temperature": 0.7}
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
        choice = data["choices"][0]["message"]
        tool_calls = []
        for tc in choice.get("tool_calls") or []:
            try:
                args = json.loads(tc["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}
            tool_calls.append({"name": tc["function"]["name"], "arguments": args})
        usage = data.get("usage") or {}
        return ChatResponse(
            content=choice.get("content") or "",
            tool_calls=tool_calls,
            tokens_used=int(usage.get("total_tokens") or 0),
        )


class EchoClient:
    """脚本化驱动：按脚本逐步回放工具调用/发言。用于测试与无头实验。"""

    def __init__(self, script: list[dict] | None = None, token_counter=None):
        self.script = list(script or [])
        self.i = 0
        self.token_counter = token_counter

    def chat(self, messages: list[dict], tools: list[dict]) -> ChatResponse:
        step = self.script[self.i] if self.i < len(self.script) else {"say": "(script exhausted)"}
        self.i += 1
        content = step.get("say", "")
        tool_calls = []
        for name, args in (step.get("tool") and [step["tool"]] or []):
            tool_calls.append({"name": name, "arguments": step.get("args", {})})
        tokens = 0
        if self.token_counter:
            tokens = self.token_counter.count(content) + self.token_counter.count(
                json.dumps(tool_calls, default=str)
            )
        return ChatResponse(content=content, tool_calls=tool_calls, tokens_used=tokens)


def tool_schema(func) -> dict:
    """从 Python 函数签名生成 OpenAI tool schema（够用的最小实现）。"""
    import inspect

    sig = inspect.signature(func)
    props, required = {}, []
    for pname, param in sig.parameters.items():
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue
        ann = param.annotation
        jtype = "string"
        if ann in (int, "int"):
            jtype = "integer"
        elif ann in (float, "float"):
            jtype = "number"
        elif ann in (bool, "bool"):
            jtype = "boolean"
        props[pname] = {"type": jtype}
        if param.default is inspect.Parameter.empty:
            required.append(pname)
    doc = (func.__doc__ or "").strip().splitlines()
    return {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": doc[0] if doc else "",
            "parameters": {"type": "object", "properties": props, "required": required},
        },
    }
