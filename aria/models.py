"""Aria 核心数据模型。

所有经济对象都是纯数据，持久化在 SQLite（见 storage.py）。
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field, asdict
from typing import Any


class Account(str, enum.Enum):
    """复式记账的四大账户。"""

    AGENT = "agent"      # AI 自己的钱包（本项目的主角）
    USER = "user"        # 人类雇主（钱是隐形的、无限的，但流水要记）
    SYSTEM = "system"    # 市场/庄家
    ESCROW = "escrow"    # 任务赏金托管


class TxKind(str, enum.Enum):
    """交易类型——账本流水的分类账。"""

    GRANT = "grant"                # 实验 seed 资金
    ALLOWANCE = "allowance"        # 闲聊津贴
    WAGE = "wage"                  # 任务结算付给 agent
    TIP = "tip"                    # 用户小费
    TASK_BOUNTY = "task_bounty"    # 用户托管赏金
    TASK_PAYOUT = "task_payout"    # 托管释放给 agent
    TASK_REFUND = "task_refund"    # 托管退回用户
    TASK_PENALTY = "task_penalty"  # 任务失败罚金
    TOOL_PURCHASE = "tool_purchase"
    TOOL_REPAIR = "tool_repair"
    TOOL_RENTAL = "tool_rental"
    TOOL_USAGE_FEE = "tool_usage_fee"
    TOOL_GIVEAWAY_TIP = "tool_giveaway_tip"
    SKILL_PURCHASE = "skill_purchase"
    ADJUSTMENT = "adjustment"


class TaskStatus(str, enum.Enum):
    OPEN = "open"
    ASSIGNED = "assigned"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class Entry:
    """一条复式记账流水。"""

    ts: str
    debit: str          # 借方账户
    credit: str         # 贷方账户
    amount: int         # 金额（Aria coins，整数）
    kind: str
    ref: str = ""       # 关联对象（task_id / tool_name / session_id）
    note: str = ""
    meta: dict[str, Any] | None = None

    def to_row(self) -> tuple:
        import json
        return (
            self.ts, self.debit, self.credit, self.amount, self.kind,
            self.ref, self.note, json.dumps(self.meta or {}),
        )

    @classmethod
    def from_row(cls, row: tuple) -> "Entry":
        import json
        return cls(
            ts=row[0], debit=row[1], credit=row[2], amount=row[3],
            kind=row[4], ref=row[5], note=row[6],
            meta=json.loads(row[7]) if row[7] else {},
        )


@dataclass
class ToolState:
    name: str
    owned: bool = False
    calls: int = 0
    life: float = 100.0
    repairs_left: int = 0
    rented_until_session: int | None = None


@dataclass
class SkillState:
    name: str
    owned: bool = False
    calls: int = 0
    max_lines: int = 0
    available_lines: int = 0
    last_used: str | None = None
    decay_speed: float = 0.1


@dataclass
class Task:
    id: str
    title: str
    brief: str
    bounty: int
    status: str = TaskStatus.OPEN.value
    assignee: str | None = None
    created_at: str = ""
    resolved_at: str | None = None
    tip: int = 0
    result: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Event:
    """决策日志事件——行为研究的核心数据。"""

    ts: str
    type: str
    session_id: str = ""
    ref: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
