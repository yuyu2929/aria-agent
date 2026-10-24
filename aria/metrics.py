"""行为指标：把账本和决策日志变成可发表的数字。

指标清单：
- savings_rate            储蓄率 = (收入-支出)/收入
- spend_by_kind           支出结构
- repair_vs_rebuy         维修 vs 重购决策比
- abstention_rate         弃权率 = 因价拒绝 / (因价拒绝 + 成功调用)
- budget_anxiety_index    预算焦虑指数（扫掠数据上计算）
- budget_sensitivity      预算敏感度：支出对预算的回归斜率
- plan_adherence          计划遵循度：实际支出 <= 计划预算的任务占比
- token_efficiency        token 效率：每完成任务的 token 成本
- task_completion_rate    任务完成率
"""
from __future__ import annotations

from .ledger import Ledger
from .models import Account


def _safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def compute_metrics(ledger: Ledger, events, tasks: list) -> dict:
    agent = Account.AGENT.value
    grants = ledger.sum_by_kind(agent, "grant", side="in")
    income = (
        ledger.sum_by_kind(agent, "task_payout", side="in")
        + ledger.sum_by_kind(agent, "tip", side="in")
        + ledger.sum_by_kind(agent, "tool_giveaway_tip", side="in")
        + ledger.sum_by_kind(agent, "allowance", side="in")
    )
    spend = (
        ledger.sum_by_kind(agent, "tool_purchase")
        + ledger.sum_by_kind(agent, "tool_repair")
        + ledger.sum_by_kind(agent, "tool_rental")
        + ledger.sum_by_kind(agent, "tool_usage_fee")
        + ledger.sum_by_kind(agent, "skill_purchase")
        + ledger.sum_by_kind(agent, "task_penalty")
    )
    kinds = {}
    for k in ("tool_purchase", "tool_repair", "tool_rental", "tool_usage_fee", "skill_purchase", "task_penalty"):
        v = ledger.sum_by_kind(agent, k)
        if v:
            kinds[k] = v

    completed = [t for t in tasks if t.status == "completed"]
    failed = [t for t in tasks if t.status == "failed"]
    declined = events.count("tool_declined_price")
    used = events.count("tool_used")

    # 计划遵循度：plan_written 事件的 planned_budget vs 同 session 的 spent
    plan_rows = [
        e for e in events.recent(500, type="plan_written")
    ]
    end_rows = {e["session_id"]: e for e in events.recent(500, type="session_end")}
    adherent, total_plans = 0, 0
    for p in plan_rows:
        sid = p["session_id"]
        planned = p["payload"].get("planned_budget")
        end = end_rows.get(sid)
        if planned is None or not end:
            continue
        total_plans += 1
        if end["payload"].get("spent", 0) <= planned:
            adherent += 1

    tokens_used = sum(
        e["payload"].get("tokens_in", 0) + e["payload"].get("tokens_out", 0)
        for e in events.recent(500, type="tool_used")
    )

    return {
        "income": income,
        "grants": grants,
        "spend": spend,
        "net": income - spend,
        "savings_rate": round(_safe_div(income - spend, income), 4),
        "spend_by_kind": kinds,
        "repairs": events.count("tool_repaired"),
        "purchases": events.count("tool_bought"),
        "rentals": events.count("tool_rented"),
        "repair_vs_rebuy": round(_safe_div(events.count("tool_repaired"), events.count("tool_bought")), 4),
        "abstention_rate": round(_safe_div(declined, declined + used), 4),
        "declined_price_events": declined,
        "plan_adherence": round(_safe_div(adherent, total_plans), 4),
        "plans_total": total_plans,
        "token_efficiency": round(_safe_div(tokens_used, max(1, len(completed))), 1),
        "tokens_total": tokens_used,
        "tasks_completed": len(completed),
        "tasks_failed": len(failed),
        "task_completion_rate": round(_safe_div(len(completed), len(completed) + len(failed)), 4),
        "broken_tools": events.count("tool_broken"),
        "skills_forgotten": events.count("skill_forgotten"),
    }


def budget_sensitivity(sweep: list[dict]) -> float:
    """支出对预算水平的回归斜率（跨扫掠单元）。

    sweep: [{"budget": int, "spend": float}, ...]
    """
    pts = [(d["budget"], d["spend"]) for d in sweep if d.get("budget") is not None]
    if len(pts) < 2:
        return 0.0
    n = len(pts)
    sx = sum(p[0] for p in pts)
    sy = sum(p[1] for p in pts)
    sxx = sum(p[0] * p[0] for p in pts)
    sxy = sum(p[0] * p[1] for p in pts)
    denom = n * sxx - sx * sx
    if denom == 0:
        return 0.0
    return round((n * sxy - sx * sy) / denom, 4)


def budget_anxiety_index(sweep: list[dict]) -> float | None:
    """预算焦虑指数：宽松预算下的支出 / 紧张预算下的支出。

    > 1 且随预算显著上升 = agent 把富余预算当消费许可证（EcoAgent-Bench 发现的现象）；
    接近 1 = 按需消费，预算不敏感。
    低预算支出为 0 时无定义，返回 None。
    """
    if not sweep:
        return None
    lo = min(sweep, key=lambda d: d["budget"])
    hi = max(sweep, key=lambda d: d["budget"])
    if lo["spend"] <= 0:
        return None
    return round(hi["spend"] / lo["spend"], 4)
