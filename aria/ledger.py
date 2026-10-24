"""复式记账账本（double-entry ledger）。

每一笔钱都有来路和去处：一条 entry = 一个借方 + 一个贷方 + 相同金额。
余额永远由流水推导，不存快照——这就是"审计追踪"的含义。
"""
from __future__ import annotations

from datetime import datetime, timezone

from .models import Account, Entry, TxKind
from .storage import Database


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class Ledger:
    def __init__(self, db: Database):
        self.db = db

    def post(
        self,
        debit: str | Account,
        credit: str | Account,
        amount: int,
        kind: str | TxKind,
        ref: str = "",
        note: str = "",
        meta: dict | None = None,
    ) -> int:
        """记一笔账。返回 entry id。"""
        if amount <= 0:
            raise ValueError(f"amount must be positive, got {amount}")
        entry = Entry(
            ts=utcnow(),
            debit=str(getattr(debit, "value", debit)),
            credit=str(getattr(credit, "value", credit)),
            amount=int(amount),
            kind=str(getattr(kind, "value", kind)),
            ref=ref,
            note=note,
            meta=meta,
        )
        cur = self.db.execute(
            "INSERT INTO entries(ts, debit, credit, amount, kind, ref, note, meta) "
            "VALUES(?,?,?,?,?,?,?,?)",
            entry.to_row(),
        )
        return cur.lastrowid

    def balance(self, account: str | Account) -> int:
        """某账户余额 = 贷方流入 - 借方流出。"""
        acct = str(getattr(account, "value", account))
        row = self.db.query_one(
            "SELECT "
            "COALESCE(SUM(CASE WHEN credit=? THEN amount ELSE 0 END), 0) - "
            "COALESCE(SUM(CASE WHEN debit=? THEN amount ELSE 0 END), 0) AS bal "
            "FROM entries",
            (acct, acct),
        )
        return int(row["bal"])

    def balances(self) -> dict[str, int]:
        return {a.value: self.balance(a) for a in Account}

    def history(
        self,
        limit: int = 100,
        kind: str | None = None,
        account: str | None = None,
        ref: str | None = None,
    ) -> list[Entry]:
        sql = "SELECT ts, debit, credit, amount, kind, ref, note, meta FROM entries"
        conds, params = [], []
        if kind:
            conds.append("kind=?"); params.append(kind)
        if account:
            conds.append("(debit=? OR credit=?)"); params += [account, account]
        if ref:
            conds.append("ref=?"); params.append(ref)
        if conds:
            sql += " WHERE " + " AND ".join(conds)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        return [Entry.from_row(tuple(r)) for r in self.db.query(sql, tuple(params))]

    def sum_by_kind(self, account: str | Account, kind: str, side: str = "out") -> int:
        """统计某账户在某类交易上的流出/流入总额。"""
        acct = str(getattr(account, "value", account))
        col = "debit" if side == "out" else "credit"
        row = self.db.query_one(
            f"SELECT COALESCE(SUM(amount), 0) AS s FROM entries WHERE {col}=? AND kind=?",
            (acct, kind),
        )
        return int(row["s"])

    def net_worth_series(self, account: str | Account = Account.AGENT) -> list[dict]:
        """按时间顺序的净资产曲线（仪表盘画图用）。"""
        acct = str(getattr(account, "value", account))
        rows = self.db.query(
            "SELECT ts, debit, credit, amount, kind, note FROM entries ORDER BY id"
        )
        bal, series = 0, []
        for r in rows:
            if r["credit"] == acct:
                bal += r["amount"]
            if r["debit"] == acct:
                bal -= r["amount"]
            series.append(
                {"ts": r["ts"], "balance": bal, "kind": r["kind"], "note": r["note"]}
            )
        return series

    def check_invariant(self) -> bool:
        """复式记账铁律：所有账户余额之和为 0（有借必有贷）。"""
        return sum(self.balances().values()) == 0

    def last_id(self) -> int:
        row = self.db.query_one("SELECT COALESCE(MAX(id), 0) AS m FROM entries")
        return int(row["m"])

    def flows_since(self, last_id: int, account: str | Account = Account.AGENT) -> tuple[int, int]:
        """某账户在 last_id 之后的 (支出, 收入)。用于按会话精确计量。"""
        acct = str(getattr(account, "value", account))
        spend = self.db.query_one(
            "SELECT COALESCE(SUM(amount), 0) AS s FROM entries WHERE id > ? AND debit=?",
            (last_id, acct),
        )
        earn = self.db.query_one(
            "SELECT COALESCE(SUM(amount), 0) AS s FROM entries WHERE id > ? AND credit=?",
            (last_id, acct),
        )
        return int(spend["s"]), int(earn["s"])
