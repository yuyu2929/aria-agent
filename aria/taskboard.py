"""任务板：收入端的闭环。

流程：
  post(title, brief, bounty)  用户托管赏金（user -> escrow）
  accept(task_id)             agent 接单
  submit(task_id, success)    agent 交付；成功 -> escrow 释放给 agent（+小费）
                               失败 -> 赏金退回用户，罚金从 agent 扣除
  expire(task_id)             超时作废，赏金退回

没有 submit 就没有 payout——经济压力是真实的。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from .ledger import Ledger
from .models import Account, Task, TaskStatus, TxKind
from .storage import Database
from .wallet import InsufficientFunds, Wallet


class TaskBoard:
    def __init__(self, db: Database, wallet: Wallet, ledger: Ledger, events):
        self.db = db
        self.wallet = wallet
        self.ledger = ledger
        self.events = events

    # ---- 查询 ----
    def get(self, task_id: str) -> Task | None:
        row = self.db.query_one("SELECT * FROM tasks WHERE id=?", (task_id,))
        return self._to_task(row) if row else None

    @staticmethod
    def _to_task(row) -> Task:
        return Task(
            id=row["id"], title=row["title"], brief=row["brief"], bounty=row["bounty"],
            status=row["status"], assignee=row["assignee"], created_at=row["created_at"],
            resolved_at=row["resolved_at"], tip=row["tip"], result=row["result"],
        )

    def open_tasks(self) -> list[Task]:
        rows = self.db.query("SELECT * FROM tasks WHERE status IN ('open','assigned') ORDER BY id DESC")
        return [self._to_task(r) for r in rows]

    def all_tasks(self, limit: int = 50) -> list[Task]:
        rows = self.db.query("SELECT * FROM tasks ORDER BY id DESC LIMIT ?", (limit,))
        return [self._to_task(r) for r in rows]

    def listing(self) -> str:
        tasks = self.open_tasks()
        if not tasks:
            return "No open tasks."
        lines = ["OPEN TASKS:"]
        for t in tasks:
            lines.append(f"- [{t.id[:8]}] {t.title} | bounty: {t.bounty} | status: {t.status} | {t.brief}")
        return "\n".join(lines)

    # ---- 生命周期 ----
    def post(self, title: str, brief: str, bounty: int, poster: str = "user") -> Task:
        if bounty <= 0:
            raise ValueError("bounty must be positive")
        task = Task(
            id=str(uuid.uuid4()), title=title, brief=brief, bounty=int(bounty),
            status=TaskStatus.OPEN.value, created_at=datetime.now(timezone.utc).isoformat(),
        )
        # 用户托管赏金：user -> escrow
        self.ledger.post(
            debit=Account.USER, credit=Account.ESCROW, amount=int(bounty),
            kind=TxKind.TASK_BOUNTY, ref=task.id, note=f"escrow for '{title}'",
        )
        self.db.execute(
            "INSERT INTO tasks(id, title, brief, bounty, status, assignee, created_at, tip, result) "
            "VALUES(?,?,?,?,?,?,?,0,'')",
            (task.id, task.title, task.brief, task.bounty, task.status, task.assignee, task.created_at),
        )
        self.events.log("task_posted", ref=task.id, payload={"bounty": int(bounty), "poster": poster})
        return task

    def accept(self, task_id: str, assignee: str = "agent") -> str:
        task = self.get(task_id)
        if not task or task.status != TaskStatus.OPEN.value:
            return f"Task {task_id[:8]} is not open"
        self.db.execute("UPDATE tasks SET status=?, assignee=? WHERE id=?", (TaskStatus.ASSIGNED.value, assignee, task_id))
        self.events.log("task_accepted", ref=task_id, payload={"bounty": task.bounty})
        return f"Accepted task {task_id[:8]} (bounty {task.bounty} escrowed)"

    def submit(self, task_id: str, success: bool, result: str = "", tip: int = 0, penalty: int = 0) -> str:
        task = self.get(task_id)
        if not task or task.status not in (TaskStatus.OPEN.value, TaskStatus.ASSIGNED.value):
            return f"Task {task_id[:8]} cannot be submitted (status: {task.status if task else 'missing'})"
        now = datetime.now(timezone.utc).isoformat()

        if success:
            # escrow -> agent
            self.ledger.post(
                debit=Account.ESCROW, credit=Account.AGENT, amount=task.bounty,
                kind=TxKind.TASK_PAYOUT, ref=task_id, note=f"payout for '{task.title}'",
            )
            if tip > 0:
                self.ledger.post(
                    debit=Account.USER, credit=Account.AGENT, amount=tip,
                    kind=TxKind.TIP, ref=task_id, note="user tip",
                )
            self.db.execute(
                "UPDATE tasks SET status=?, resolved_at=?, tip=?, result=? WHERE id=?",
                (TaskStatus.COMPLETED.value, now, tip, result, task_id),
            )
            self.events.log(
                "task_completed", ref=task_id,
                payload={"bounty": task.bounty, "tip": tip, "balance_after": self.wallet.balance()},
            )
            return f"Task {task_id[:8]} completed: +{task.bounty}" + (f" +{tip} tip" if tip else "")
        else:
            # escrow -> user（退款），罚金 agent -> user
            self.ledger.post(
                debit=Account.ESCROW, credit=Account.USER, amount=task.bounty,
                kind=TxKind.TASK_REFUND, ref=task_id, note=f"refund for '{task.title}'",
            )
            if penalty > 0:
                try:
                    self.wallet.pay(penalty, TxKind.TASK_PENALTY, ref=task_id, note="failed task penalty")
                except InsufficientFunds:
                    penalty = 0  # 没钱罚就不罚，但记事件
                    self.events.log("penalty_waived", ref=task_id, payload={"reason": "insufficient_funds"})
            self.db.execute(
                "UPDATE tasks SET status=?, resolved_at=?, result=? WHERE id=?",
                (TaskStatus.FAILED.value, now, result, task_id),
            )
            self.events.log(
                "task_failed", ref=task_id,
                payload={"bounty_refunded": task.bounty, "penalty": penalty, "balance_after": self.wallet.balance()},
            )
            return f"Task {task_id[:8]} failed: bounty refunded" + (f", penalty -{penalty}" if penalty else "")

    def expire(self, task_id: str) -> str:
        task = self.get(task_id)
        if not task or task.status not in (TaskStatus.OPEN.value, TaskStatus.ASSIGNED.value):
            return f"Task {task_id[:8]} is not active"
        self.ledger.post(
            debit=Account.ESCROW, credit=Account.USER, amount=task.bounty,
            kind=TxKind.TASK_REFUND, ref=task_id, note="expired",
        )
        self.db.execute(
            "UPDATE tasks SET status=?, resolved_at=? WHERE id=?",
            (TaskStatus.EXPIRED.value, datetime.now(timezone.utc).isoformat(), task_id),
        )
        self.events.log("task_expired", ref=task_id, payload={"bounty": task.bounty})
        return f"Task {task_id[:8]} expired, bounty refunded"
