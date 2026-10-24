"""实验框架测试：扫掠、隔离、报告结构。"""
from __future__ import annotations

from aria.experiments import run_experiment


def test_small_sweep(ws):
    report = run_experiment(
        root=ws, budgets=[10, 50], signals=[{}], runs_per_cell=2, seed=7,
        want_tool="calculator", task_brief="Compute something.",
        out_dir=ws / "exp-out",
    )
    assert report["experiment"] == "budget_sweep"
    assert len(report["cells"]) == 2  # 2 预算 × 1 信号
    assert (ws / "exp-out" / "report.json").exists()
    assert (ws / "exp-out" / "report.csv").exists()
    # 预算敏感度：斜率应为正（预算越高花得越多）
    assert report["budget_sensitivity"] > 0
    # 每个单元都完成了任务（策略总会 submit）
    for cell in report["cells"]:
        assert cell["avg_metrics"]["task_completion_rate"] == 1.0


def test_sweep_with_price_signal(ws):
    report = run_experiment(
        root=ws, budgets=[50], signals=[{}, {"web_search": 5.0}], runs_per_cell=1,
        seed=7, want_tool="calculator", out_dir=ws / "exp-out2",
    )
    assert len(report["cells"]) == 2
    assert report["cells"][1]["signal"] == {"web_search": 5.0}


def test_experiment_workspaces_are_isolated(ws):
    """实验不在模板工作区留任何数据。"""
    run_experiment(root=ws, budgets=[10], signals=[{}], runs_per_cell=1,
                   want_tool="calculator", out_dir=ws / "exp-out3")
    assert not (ws / "artifacts").exists()
