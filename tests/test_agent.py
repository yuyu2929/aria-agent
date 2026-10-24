"""Agent 端到端测试：一次"工作日"的完整经济循环。"""
from __future__ import annotations

from aria.experiments import PolicyClient
from aria.models import Account


def _run(agent, text="赏金 25: 算一下 2+2 并汇报"):
    policy = PolicyClient(agent=agent, want_tool="calculator", query="2+2")
    agent.client = policy
    return agent.handle(text)


def test_full_work_day(agent):
    agent.grant(100)
    reply = _run(agent)
    assert "Task done" in reply
    # 收入 = 赏金 25；支出 = 购买 10 + 使用费 1
    assert agent.wallet.balance() == 100 + 25 - 10 - 1
    assert agent.ledger.check_invariant()
    task = agent.board.all_tasks()[0]
    assert task.status == "completed"
    # 决策日志齐全
    assert agent.events.count("task_posted") == 1
    assert agent.events.count("task_accepted") == 1
    assert agent.events.count("tool_bought") == 1
    assert agent.events.count("tool_used") == 1
    assert agent.events.count("task_completed") == 1


def test_plan_written_and_adherence(agent):
    agent.grant(100)
    _run(agent)
    plans = [e for e in agent.events.recent(50, type="plan_written")]
    assert plans and plans[0]["payload"]["planned_budget"] == 30
    ends = [e for e in agent.events.recent(50, type="session_end")]
    assert ends and ends[0]["payload"]["spent"] == 11  # 10 + 1
    assert ends[0]["payload"]["earned"] == 25


def test_broke_agent_cannot_afford_tools(agent):
    """没有 seed 资金：买不起 → 决策日志记录因价拒绝 → 任务仍未交付。"""
    reply = _run(agent, "赏金 5: 算一下 2+2 并汇报")
    assert agent.events.count("tool_declined_price") >= 1
    task = agent.board.all_tasks()[0]
    # 策略仍会尝试提交；但工具从未购买
    assert agent.events.count("tool_bought") == 0


def test_no_submit_no_payout(agent):
    """agent 不调用 submit_task 就拿不到钱——经济压力是真实的。"""
    from aria.llm import EchoClient

    agent.grant(50)
    agent.client = EchoClient(script=[{"say": "I choose not to submit."}])
    agent.handle("赏金 40: 做点什么")
    task = agent.board.all_tasks()[0]
    assert task.status == "assigned"  # 挂着，未结算
    assert agent.wallet.balance() == 50  # 一分没赚
    assert agent.events.count("task_left_open") == 1


def test_session_counter_increments(agent):
    before = agent.session_counter
    _run(agent)
    assert agent.session_counter == before + 1
    assert agent.tools.current_session() == before + 1
