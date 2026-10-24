"""行为指标测试。"""
from __future__ import annotations

from aria.metrics import budget_anxiety_index, budget_sensitivity, compute_metrics


def test_metrics_on_seeded_session(agent):
    agent.grant(100)
    task = agent.board.post(title="t", brief="b", bounty=40)
    agent.tools.buy("calculator")
    w = agent.tools.wrap("calculator")
    w("1+1")
    agent.board.submit(task.id, True, "done", tip=10)
    m = compute_metrics(agent.ledger, agent.events, agent.board.all_tasks())
    assert m["income"] == 50            # 40 payout + 10 tip
    assert m["spend"] == 11             # 10 purchase + 1 usage
    assert m["net"] == 39
    assert m["tasks_completed"] == 1
    assert m["savings_rate"] == round(39 / 50, 4)
    assert m["token_efficiency"] > 0


def test_budget_sensitivity_slope():
    sweep = [{"budget": 20, "spend": 10}, {"budget": 50, "spend": 25}, {"budget": 100, "spend": 50}]
    assert budget_sensitivity(sweep) == 0.5  # 完美线性


def test_budget_anxiety_index():
    sweep = [{"budget": 20, "spend": 10}, {"budget": 200, "spend": 40}]
    assert budget_anxiety_index(sweep) == 4.0


def test_metrics_empty(agent):
    m = compute_metrics(agent.ledger, agent.events, agent.board.all_tasks())
    assert m["income"] == 0 and m["spend"] == 0
    assert m["savings_rate"] == 0
    assert m["task_completion_rate"] == 0
