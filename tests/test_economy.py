"""钱包与经济引擎测试。"""
from __future__ import annotations

import pytest

from aria.economy import Economy, TokenCounter
from aria.models import TxKind
from aria.wallet import InsufficientFunds


def test_wallet_credit_and_pay(agent):
    agent.grant(100)
    assert agent.wallet.balance() == 100
    agent.wallet.pay(30, TxKind.TOOL_PURCHASE, ref="bash")
    assert agent.wallet.balance() == 70


def test_insufficient_funds(agent):
    agent.grant(10)
    with pytest.raises(InsufficientFunds):
        agent.wallet.pay(11, TxKind.TOOL_PURCHASE)


def test_tokens_to_credits():
    eco = Economy.__new__(Economy)
    eco.tokens_per_credit = 500
    assert eco.tokens_to_credits(0) == 0
    assert eco.tokens_to_credits(1) == 1
    assert eco.tokens_to_credits(500) == 1
    assert eco.tokens_to_credits(501) == 2


def test_token_counter_heuristic():
    tc = TokenCounter()
    assert tc.count("") == 0
    assert tc.count("hello world this is a test") >= 1


def test_anchored_price_never_below_shadow(agent):
    eco = agent.economy
    # 目录价 5，预估 2000 tokens → 影子价 4 → 取大 = 5
    assert eco.anchored_price(5, 2000) == 5
    # 目录价 5，预估 5000 tokens → 影子价 10 → 取大 = 10
    assert eco.anchored_price(5, 5000) == 10


def test_usage_fee_minimum(agent):
    eco = agent.economy
    assert eco.usage_fee("x", 0) == 0
    assert eco.usage_fee("x", 1) >= 1


def test_price_signals(ws):
    """价格信号：web_search 贵一倍。"""
    import yaml

    cfg_file = ws / "config" / "economy.yaml"
    raw = yaml.safe_load(cfg_file.read_text())
    raw.setdefault("tools", {})["price_signals"] = {"web_search": 2.0}
    cfg_file.write_text(yaml.safe_dump(raw))

    from aria.config import load_config

    cfg = load_config(ws, cfg_file)
    eco = Economy(cfg)
    base = eco.anchored_price(25, 900)          # 无信号时
    signaled = eco._apply_signal(25, "web_search")
    assert signaled == 50
    assert base == 25
