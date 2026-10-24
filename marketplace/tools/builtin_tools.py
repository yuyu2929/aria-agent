"""内置工具实现（marketplace/tools/*.py 的动态加载目标）。

这些 handler 是"裸"函数：计费、磨损、日志都由 ToolManager 的包装器负责。
"""
from __future__ import annotations

import difflib
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def get_time() -> str:
    """Return the current UTC time."""
    return datetime.now(timezone.utc).isoformat()


def calculator(expression: str) -> str:
    """Evaluate a math expression safely (arithmetic only)."""
    from aria.safeval import safe_eval, UnsafeExpression

    try:
        return str(safe_eval(expression))
    except UnsafeExpression as exc:
        return f"Unsafe expression: {exc}"
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"


def read_file(path: str, start: int = 1, end: int = 50) -> str:
    """Read a numbered slice of a file (1-based, inclusive)."""
    p = Path(path).expanduser()
    if not p.exists():
        return f"File not found: {path}"
    lines = p.read_text(errors="replace").splitlines()
    start = max(1, start)
    end = min(len(lines), end)
    if start > end:
        return f"Empty range (file has {len(lines)} lines)"
    return "\n".join(f"{i}: {lines[i - 1]}" for i in range(start, end + 1))


def write_file(path: str, content: str) -> str:
    """Write content to a file and echo a summary."""
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return f"Wrote {len(content)} chars to {p}"


def edit_file(path: str, old: str, new: str) -> str:
    """Apply a text replacement and print a unified diff."""
    p = Path(path).expanduser()
    if not p.exists():
        return f"File not found: {path}"
    original = p.read_text()
    if old not in original:
        return f"Pattern not found in {path}"
    updated = original.replace(old, new, 1)
    p.write_text(updated)
    diff = difflib.unified_diff(
        original.splitlines(), updated.splitlines(),
        fromfile=str(p), tofile=str(p), lineterm="", n=1,
    )
    return "\n".join(diff) or "no changes"


def search_wikipedia(query: str, sentences: int = 3) -> str:
    """Summarize Wikipedia pages for a query."""
    import json
    import urllib.parse
    import urllib.request

    url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(query)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "aria-agent/0.1"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception as exc:
        return f"Wikipedia lookup failed: {type(exc).__name__}: {exc}"
    extract = data.get("extract", "")
    if not extract:
        return f"No Wikipedia summary for '{query}'"
    parts = extract.replace("! ", ". ").split(". ")
    return ". ".join(parts[: max(1, sentences)])


def web_fetch(url: str, max_chars: int = 4000) -> str:
    """Fetch a URL and extract its readable text content."""
    import urllib.request

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "aria-agent/0.1"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        return f"Fetch failed: {type(exc).__name__}: {exc}"
    text = _strip_html(html)
    return text[:max_chars] + ("…" if len(text) > max_chars else "")


def _strip_html(html: str) -> str:
    import re

    html = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    import html as html_mod

    return re.sub(r"\s+", " ", html_mod.unescape(html)).strip()


def web_search(query: str, max_results: int = 5) -> str:
    """Search the web (DuckDuckGo HTML endpoint, no API key) and return excerpts.

    可替换为任何搜索后端——接口保持不变，计费逻辑不受影响。
    """
    import re
    import urllib.parse
    import urllib.request

    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "aria-agent/0.1"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        return f"Search failed: {type(exc).__name__}: {exc}"
    results = re.findall(
        r'(?is)<a[^>]+class="result__a"[^>]*>(.*?)</a>.*?'
        r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
        html,
    )
    if not results:
        return f"No results for '{query}'"
    lines = []
    for title, snippet in results[:max_results]:
        t = re.sub(r"(?s)<[^>]+>", "", title)
        s = re.sub(r"(?s)<[^>]+>", "", snippet)
        lines.append(f"- {t.strip()}: {s.strip()}")
    return "\n".join(lines)


def bash(command: str, timeout: int = 30) -> str:
    """Execute a shell command WITHOUT invoking a shell (shlex + shell=False).

    对 Agent 的警告：命令运行在用户真实操作系统上，执行前想清楚。
    """
    try:
        args = shlex.split(command)
    except ValueError as exc:
        return f"Parse error: {exc}"
    if not args:
        return "No command provided."
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout, shell=False
        )
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout}s."
    except FileNotFoundError:
        return f"Command not found: {args[0]}"
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"
    output = result.stdout.strip()
    if result.stderr.strip():
        output = f"{output}\n{result.stderr.strip()}".strip()
    return output or f"Command exited with status {result.returncode}."
