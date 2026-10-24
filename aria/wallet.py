"""钱包：Agent 账户在账本上的 convenience 层。"""
from __future__ import annotations

from .ledger import Ledger
from .models import Account, TxKind


class InsufficientFunds(Exception):
    """余额不足。"""


class Wallet:
    """Agent 的钱包。所有操作都落到复式账本上。"""

    def __init__(self, ledger: Ledger):
        self.ledger = ledger

    @property
    def account(self) -> str:
        return Account.AGENT.value

    def balance(self) -> int:
        return self.ledger.balance(self.account)

    def can_afford(self, amount: int) -> bool:
        return self.balance() >= amount

    def credit(
        self, amount: int, kind: str | TxKind, ref: str = "", note: str = "", meta: dict | None = None
    ) -> int:
        """别人付给 agent。"""
        self.ledger.post(
            debit=Account.SYSTEM if kind == TxKind.GRANT else Account.USER,
            credit=self.account,
            amount=amount, kind=kind, ref=ref, note=note, meta=meta,
        )
        return self.balance()

    def pay(
        self, amount: int, kind: str | TxKind, ref: str = "", note: str = "", meta: dict | None = None
    ) -> int:
        """agent 付款给市场。余额不足抛 InsufficientFunds。"""
        if amount > self.balance():
            raise InsufficientFunds(f"need {amount}, have {self.balance()}")
        self.ledger.post(
            debit=self.account,
            credit=Account.SYSTEM,
            amount=amount, kind=kind, ref=ref, note=note, meta=meta,
        )
        return self.balance()
