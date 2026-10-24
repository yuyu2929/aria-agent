"""复式账本测试。"""
from __future__ import annotations

from aria.ledger import Ledger
from aria.models import Account, TxKind
from aria.storage import Database


def test_post_and_balances(tmp_path):
    db = Database(tmp_path / "t.db")
    led = Ledger(db)
    led.post(Account.USER, Account.AGENT, 50, TxKind.WAGE, note="work")
    led.post(Account.AGENT, Account.SYSTEM, 20, TxKind.TOOL_PURCHASE, ref="bash")
    assert led.balance(Account.AGENT) == 30
    assert led.balance(Account.USER) == -50   # 用户付出 50，未收回
    assert led.balance(Account.SYSTEM) == 20  # 市场收入 20
    assert led.check_invariant()
    db.close()


def test_double_entry_invariant(tmp_path):
    db = Database(tmp_path / "t.db")
    led = Ledger(db)
    for i in range(10):
        led.post(Account.USER, Account.AGENT, i + 1, TxKind.WAGE)
        led.post(Account.AGENT, Account.SYSTEM, 1, TxKind.TOOL_USAGE_FEE)
    assert led.check_invariant()
    db.close()


def test_amount_must_be_positive(tmp_path):
    db = Database(tmp_path / "t.db")
    led = Ledger(db)
    try:
        led.post(Account.USER, Account.AGENT, 0, TxKind.WAGE)
        assert False, "should raise"
    except ValueError:
        pass
    db.close()


def test_history_and_sums(tmp_path):
    db = Database(tmp_path / "t.db")
    led = Ledger(db)
    led.post(Account.USER, Account.AGENT, 100, TxKind.TASK_PAYOUT, ref="t1")
    led.post(Account.AGENT, Account.SYSTEM, 30, TxKind.TOOL_PURCHASE, ref="bash")
    led.post(Account.AGENT, Account.SYSTEM, 5, TxKind.TOOL_REPAIR, ref="bash")
    assert len(led.history(10)) == 3
    assert led.sum_by_kind(Account.AGENT, "tool_purchase") == 30
    assert led.sum_by_kind(Account.AGENT, "task_payout", side="in") == 100
    series = led.net_worth_series()
    assert [p["balance"] for p in series] == [100, 70, 65]
    db.close()
