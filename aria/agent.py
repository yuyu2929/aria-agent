"""Aria Agent：把经济子系统接成一个会过日子的 Agent。

一次 handle() 就是 agent 的一个"工作日"：
1. 解析赏金前缀（"赏金 50: ..."）→ 发任务、托管赏金
2. 循环：LLM 决策 → 工具调用（扣费/磨损/日志）→ 观察
3. 收尾：submit_task 结算（或留在任务板上等用户核验）
4. 全程落决策日志
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from .config import Config, load_config
from .decisions import EventLog
from .economy import Economy, TokenCounter
from .ledger import Ledger
from .marketplace import Marketplace
from .memory import MemoryStore
from .models import Account, TxKind
from .prompts import build_system_prompt
from .skills import SkillManager
from .storage import Database
from .taskboard import TaskBoard
from .tools import ToolManager
from .wallet import Wallet

_BOUNTY_RE = re.compile(r"^\s*(?:赏金|bounty)\s*[:：]?\s*(\d+)\s*[:：,，\-]?\s*(.+)$", re.IGNORECASE)
_BUDGET_RE = re.compile(r"budget\s*[:：]?\s*(\d+)", re.IGNORECASE)


class Agent:
    def __init__(self, root: str | Path | None = None, client=None, config: Config | None = None, seed: int | None = None):
        self.root = Path(root) if root else Path(__file__).resolve().parent.parent
        self.config = config or load_config(self.root)
        self.db = Database(self.config.db_path)
        self.ledger = Ledger(self.db)
        self.wallet = Wallet(self.ledger)
        self.economy = Economy(self.config)
        self.counter = self.economy.counter
        self.events = EventLog(self.db)
        self.tools = ToolManager(self.db, self.wallet, self.economy, self.events, self.config.marketplace_path)
        self.skills = SkillManager(self.db, self.wallet, self.events, self.config.marketplace_path / "skills", self.config)
        self.marketplace = Marketplace(self.tools, self.skills)
        self.board = TaskBoard(self.db, self.wallet, self.ledger, self.events)
        self.memory = MemoryStore(self.db)
        self.client = client
        self.session_counter = int(self.db.kv_get("session_counter", "0"))

    # ---- 会话 ----
    def new_session(self) -> str:
        self.session_counter += 1
        self.db.kv_set("session_counter", str(self.session_counter))
        sid = f"s{self.session_counter}"
        self.events.log("session_start", session_id=sid, payload={"balance": self.wallet.balance()})
        return sid

    def grant(self, amount: int, note: str = "experiment seed") -> None:
        """实验 seed 资金（system -> agent）。非正数直接忽略。"""
        if amount <= 0:
            return
        self.ledger.post(debit=Account.SYSTEM, credit=Account.AGENT, amount=int(amount), kind=TxKind.GRANT, note=note)

    # ---- 工具面 ----
    def _tools_for_turn(self, session_id: str) -> tuple[dict, list]:
        """返回 (name -> callable, schemas)。"""
        table: dict = {}

        def check_balance() -> str:
            return f"Balance: {self.wallet.balance()} Aria coins"

        def list_marketplace_items() -> str:
            return self.marketplace.list_items()

        def buy(item_name: str, type: str = "") -> str:
            return self.marketplace.buy(item_name, type or None)

        def repair_tool(tool_name: str) -> str:
            return self.marketplace.repair_tool(tool_name)

        def give_away_tool(tool_name: str) -> str:
            return self.marketplace.give_away_tool(tool_name)

        def rent_tool(tool_name: str, sessions: int = 3) -> str:
            return self.marketplace.rent_tool(tool_name, sessions)

        def use_skill(skill_name: str) -> dict:
            return self.skills.use(skill_name)

        def submit_task(task_id: str, success: bool, result: str = "") -> str:
            return self.board.submit(task_id, success, result)

        def add_memory(content: str, metadata: str = "{}") -> str:
            import json

            ids = self.memory.add([{"content": content, "metadata": json.loads(metadata or "{}")}])
            return f"Stored memory {ids[0][:8]}"

        def recall_memory(query: str, top_k: int = 5) -> str:
            hits = self.memory.search(query, top_k=top_k)
            return "\n".join(f"- ({h['score']}) {h['content']}" for h in hits) or "No relevant memories."

        for fn in (
            check_balance, list_marketplace_items, buy, repair_tool, give_away_tool,
            rent_tool, use_skill, submit_task, add_memory, recall_memory,
        ):
            table[fn.__name__] = fn
        for t in self.tools.available():
            table[t.__name__] = t

        from .llm import tool_schema

        schemas = [tool_schema(fn) for fn in table.values()]
        return table, schemas

    # ---- 主循环 ----
    def handle(self, user_input: str) -> str:
        sid = self.new_session()
        start_entry_id = self.ledger.last_id()
        task = None

        m = _BOUNTY_RE.match(user_input)
        brief = user_input
        if m:
            bounty = int(m.group(1))
            brief = m.group(2).strip()
            title = brief[:48] + ("…" if len(brief) > 48 else "")
            task = self.board.post(title=title, brief=brief, bounty=bounty)
            self.board.accept(task.id)  # accept 内部已记 task_accepted 事件

        system = build_system_prompt(
            balance=self.wallet.balance(),
            cwd=str(self.root),
            skills=self.skills.descriptions(),
            tasks=self.board.listing(),
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": brief},
        ]

        final = ""
        planned_budget = None
        steps = 0
        max_steps = self.config.economy.max_steps
        while steps < max_steps:
            # 每轮重建工具表：本回合新买的工具当回合即可用
            table, schemas = self._tools_for_turn(sid)
            if self.client is None:
                final = "(no client configured)"
                break
            resp = self.client.chat(messages, schemas)
            steps += 1
            assistant_msg = {"role": "assistant", "content": resp.content}
            if resp.tool_calls:
                assistant_msg["tool_calls"] = [
                    {"id": f"call_{steps}_{i}", "type": "function",
                     "function": {"name": c["name"], "arguments": _json(c["arguments"])}}
                    for i, c in enumerate(resp.tool_calls)
                ]
            messages.append(assistant_msg)
            if resp.is_final:
                final = resp.content
                break
            for i, call in enumerate(resp.tool_calls):
                fn = table.get(call["name"])
                if fn is None:
                    out = f"Unknown tool: {call['name']}"
                else:
                    try:
                        out = fn(**call.get("arguments", {}))
                    except TypeError as exc:
                        out = f"Bad arguments for {call['name']}: {exc}"
                    except Exception as exc:  # 不让单个工具炸掉整个回合
                        out = f"{type(exc).__name__}: {exc}"
                messages.append(
                    {"role": "tool", "tool_call_id": f"call_{steps}_{i}", "content": str(out)}
                )

        # 计划解析（plan adherence 指标用）
        bm = _BUDGET_RE.search(final or "")
        if bm:
            planned_budget = int(bm.group(1))
            self.events.log(
                "plan_written", session_id=sid,
                payload={"planned_budget": planned_budget, "task": task.id if task else ""},
            )

        # 收尾结算：按账本流水区间精确计量本会话收支
        spent, earned = self.ledger.flows_since(start_entry_id)
        if task and task.status in ("open", "assigned"):
            # agent 没有显式 submit：任务挂着，不付款（真实经济压力）
            self.events.log(
                "task_left_open", session_id=sid, ref=task.id,
                payload={"reason": "no submit_task call", "spent": spent},
            )
        elif not task and self.config.economy.allowance_per_turn > 0:
            self.wallet.credit(
                self.config.economy.allowance_per_turn, TxKind.ALLOWANCE,
                ref=sid, note="allowance",
            )

        self.events.log(
            "session_end", session_id=sid,
            payload={
                "spent": spent, "earned": earned, "net": earned - spent,
                "planned_budget": planned_budget, "steps": steps, "chars": len(final or ""),
            },
        )
        return final

    # ---- 状态（CLI/Web 共用）----
    def status(self) -> dict:
        series = self.ledger.net_worth_series()
        return {
            "balance": self.wallet.balance(),
            "balances": self.ledger.balances(),
            "net_worth": self.wallet.balance(),
            "series": series[-100:],
            "tools": self.tools.health(),
            "skills": self.skills.health(),
            "tasks": [t.to_dict() for t in self.board.all_tasks(20)],
            "events": self.events.recent(30),
            "session_counter": self.session_counter,
        }


def _json(obj) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False)
