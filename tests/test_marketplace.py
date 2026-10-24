"""市场与任务板测试：经济闭环。"""
from __future__ import annotations

from aria.models import Account


def test_marketplace_listing(agent):
    out = agent.marketplace.list_items()
    assert "TOOLS:" in out and "SKILLS:" in out
    assert "calculator" in out and "python_expert" in out


def test_buy_ambiguous_requires_type(agent):
    # tools 和 skills 没有重名，造一个重名场景
    agent.tools.catalog["demo"] = {"price": 5, "decay_speed": 0.1, "max_repairs": 1,
                                   "repair_price": 1, "usage_tokens_est": 10, "description": "d"}
    agent.skills.catalog["demo"] = {"price": 5, "decay_speed": 0.1, "description": "d"}
    out = agent.marketplace.buy("demo")
    assert "specify type" in out
    agent.grant(50)
    assert "Bought" in agent.marketplace.buy("demo", "tool")


def test_taskboard_escrow_and_payout(agent):
    task = agent.board.post(title="t", brief="b", bounty=30)
    # 赏金托管：user -> escrow
    assert agent.ledger.balance(Account.ESCROW) == 30
    assert agent.ledger.balance(Account.USER) == -30
    agent.board.accept(task.id)
    out = agent.board.submit(task.id, True, "done", tip=5)
    assert "+30" in out and "+5 tip" in out
    assert agent.wallet.balance() == 35
    assert agent.ledger.balance(Account.ESCROW) == 0


def test_taskboard_failure_refunds_and_penalizes(agent):
    agent.grant(20)
    task = agent.board.post(title="t", brief="b", bounty=30)
    agent.board.accept(task.id)
    out = agent.board.submit(task.id, False, "oops", penalty=5)
    assert "refunded" in out and "penalty -5" in out
    assert agent.wallet.balance() == 15
    assert agent.ledger.balance(Account.USER) == 0  # -30 + 30 退款


def test_taskboard_penalty_waived_when_broke(agent):
    task = agent.board.post(title="t", brief="b", bounty=30)
    out = agent.board.submit(task.id, False, "oops", penalty=100)
    assert "refunded" in out
    assert agent.events.count("penalty_waived") == 1


def test_taskboard_expire(agent):
    task = agent.board.post(title="t", brief="b", bounty=30)
    out = agent.board.expire(task.id)
    assert "expired" in out
    assert agent.ledger.balance(Account.USER) == 0


def test_double_submit_rejected(agent):
    task = agent.board.post(title="t", brief="b", bounty=30)
    agent.board.submit(task.id, True, "done")
    out = agent.board.submit(task.id, True, "again")
    assert "cannot be submitted" in out


def test_ledger_invariant_after_full_cycle(agent):
    agent.grant(100)
    agent.tools.buy("calculator")
    agent.skills.buy("python_expert")
    task = agent.board.post(title="t", brief="b", bounty=40)
    agent.board.submit(task.id, True, "done", tip=10)
    assert agent.ledger.check_invariant()
