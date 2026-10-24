"""工具系统测试：购买、使用、磨损、损坏、修复、租赁、赠送。"""
from __future__ import annotations

from aria.models import Account


def test_buy_tool_charges_wallet(agent):
    agent.grant(100)
    out = agent.tools.buy("calculator")
    assert "Bought" in out
    assert agent.tools.is_owned("calculator")
    assert agent.wallet.balance() == 100 - 10  # 目录价 10


def test_buy_insufficient_funds_logs_decline(agent):
    out = agent.tools.buy("bash")  # 25，余额 0
    assert "Insufficient" in out
    assert not agent.tools.is_owned("bash")
    assert agent.events.count("tool_declined_price") == 1


def test_use_charges_usage_fee_and_wears(agent):
    agent.grant(100)
    agent.tools.buy("calculator")
    before = agent.wallet.balance()
    life_before = agent.tools._state("calculator").life
    w = agent.tools.wrap("calculator")
    result = w("1+1")
    assert result == "2"
    assert agent.wallet.balance() < before            # 扣了使用费
    assert agent.tools._state("calculator").life < life_before  # 磨损
    assert agent.tools._state("calculator").calls == 1
    assert agent.events.count("tool_used") == 1


def test_use_unavailable_tool_returns_message(agent):
    w = agent.tools.wrap("calculator")
    out = w("1+1")
    assert "not available" in out


def test_repair_restores_life(agent):
    agent.grant(100)
    agent.tools.buy("calculator")
    st = agent.tools._state("calculator")
    st.life = 20.0
    agent.tools._save_state(st)
    out = agent.tools.repair("calculator")
    assert "Repaired" in out
    st = agent.tools._state("calculator")
    assert st.life == 60.0  # 20 + 40
    assert st.repairs_left == 4  # 5 - 1


def test_rental_expires(agent):
    agent.grant(100)
    agent.tools.rent("calculator", sessions=2)
    assert agent.tools.is_available("calculator")
    # 推进会话计数到过期之后
    agent.db.kv_set("session_counter", str(agent.tools.current_session() + 3))
    assert not agent.tools.is_available("calculator")


def test_give_away_removes_tool(agent):
    import random

    agent.grant(100)
    agent.tools.buy("calculator")
    out = agent.tools.give_away("calculator", random.Random(7))
    assert "Gave away" in out
    assert not agent.tools.is_owned("calculator")


def test_broken_tool_blocks_usage(agent):
    agent.grant(100)
    agent.tools.buy("calculator")
    st = agent.tools._state("calculator")
    st.life = 0
    agent.tools._save_state(st)
    w = agent.tools.wrap("calculator")
    assert "broken" in w("1+1")
    assert agent.events.count("tool_broken") == 1


def test_calculator_rejects_unsafe(agent):
    agent.grant(100)
    agent.tools.buy("calculator")
    w = agent.tools.wrap("calculator")
    out = w("__import__('os')")
    assert "Unsafe" in out or "not allowed" in out
