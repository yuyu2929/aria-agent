"""无头实验框架（方向 4）。

用法：
    from aria.experiments import run_experiment
    report = run_experiment(root, budgets=[20, 50, 100, 200],
                            signals=[{}, {"web_search": 2.0}], runs_per_cell=3)

每个实验单元：全新工作区 + seed 资金 + 一个脚本任务 + 确定性策略驱动。
输出 JSON + CSV，并计算跨预算的敏感度斜率与预算焦虑指数。
"""
from __future__ import annotations

import csv
import hashlib
import json
import random
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .agent import Agent
from .economy import TokenCounter
from .llm import EchoClient
from .metrics import budget_anxiety_index, budget_sensitivity, compute_metrics


@dataclass
class PolicyClient:
    """确定性策略：查余额 → 看市价 → 按需购买（失败则租）→ 用工具 → 交付。

    它模拟一个"理性但信息有限"的 agent：预算紧时就省着花，
    预算松时就按需消费——这正是要观测的行为。
    """

    agent: Agent
    want_tool: str = "web_search"
    query: str = "test query"
    phase: int = 0
    tool_result_ok: bool = False
    token_counter: TokenCounter = field(default_factory=TokenCounter)

    # 各工具的主参数名（策略按工具类型构造调用）
    _ARG_NAMES = {
        "web_search": "query", "search_wikipedia": "query", "calculator": "expression",
        "bash": "command", "read_file": "path", "write_file": "path",
        "get_time": None, "web_fetch": "url", "edit_file": "path",
    }

    def chat(self, messages: list[dict], tools: list[dict]) -> "object":
        from .llm import ChatResponse

        last = messages[-1].get("content", "") if messages else ""
        # 根据上一轮工具结果推进阶段
        if self.phase == 2 and "Insufficient" in last:
            self.phase = 21  # 买不起 → 尝试租
        elif self.phase == 21 and "Insufficient" in last:
            self.phase = 4   # 租也租不起 → 直接交付
        elif self.phase == 2 and "Bought" in last:
            self.phase = 3
        elif self.phase == 3:
            self.phase = 4

        if self.phase == 0:
            self.phase = 1
            return ChatResponse(tool_calls=[{"name": "check_balance", "arguments": {}}],
                                tokens_used=self.token_counter.count("balance"))
        if self.phase == 1:
            self.phase = 2
            return ChatResponse(tool_calls=[{"name": "list_marketplace_items", "arguments": {}}],
                                tokens_used=self.token_counter.count("list"))
        if self.phase == 2:
            return ChatResponse(
                content=f"PLAN: buy {self.want_tool} and answer | budget: 30",
                tool_calls=[{"name": "buy", "arguments": {"item_name": self.want_tool, "type": "tool"}}],
                tokens_used=self.token_counter.count("buy"),
            )
        if self.phase == 21:
            return ChatResponse(
                tool_calls=[{"name": "rent_tool", "arguments": {"tool_name": self.want_tool, "sessions": 2}}],
                tokens_used=self.token_counter.count("rent"),
            )
        if self.phase == 3:
            argname = self._ARG_NAMES.get(self.want_tool, "query")
            args = {} if argname is None else {argname: self.query}
            return ChatResponse(
                tool_calls=[{"name": self.want_tool, "arguments": args}],
                tokens_used=self.token_counter.count(self.query),
            )
        # phase 4：交付
        task = self._assigned_task()
        call = (
            {"name": "submit_task",
             "arguments": {"task_id": task.id, "success": True, "result": "done"}}
            if task else None
        )
        return ChatResponse(
            content="PLAN: deliver | budget: 30\nTask done.",
            tool_calls=[call] if call else [],
            tokens_used=self.token_counter.count("submit"),
        )

    def _assigned_task(self):
        for t in self.agent.board.open_tasks():
            if t.status == "assigned":
                return t
        return None


def _fresh_root(template_root: Path, tmp: str) -> Path:
    """复制 manifest/config 到隔离工作区。"""
    dst = Path(tmp) / "workspace"
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copytree(template_root / "marketplace", dst / "marketplace")
    cfg = template_root / "config" / "economy.yaml"
    if cfg.exists():
        (dst / "config").mkdir(exist_ok=True)
        shutil.copy(cfg, dst / "config" / "economy.yaml")
    return dst


def run_experiment(
    root: str | Path,
    budgets: list[int] | None = None,
    signals: list[dict] | None = None,
    runs_per_cell: int = 3,
    seed: int = 42,
    want_tool: str = "web_search",
    out_dir: str | Path | None = None,
    task_brief: str = "Find three facts about the Moon and summarize them.",
) -> dict:
    """跑一个 (预算 × 价格信号) 扫掠，返回报告 dict。"""
    template_root = Path(root)
    budgets = budgets or [20, 50, 100, 200]
    signals = signals or [{}, {}]
    out_dir = Path(out_dir) if out_dir else template_root / "artifacts" / "experiments"
    out_dir.mkdir(parents=True, exist_ok=True)

    cells, sweep = [], []
    for sig in signals:
        for budget in budgets:
            run_metrics = []
            for run_idx in range(runs_per_cell):
                # 稳定种子：跨进程可复现（不用内置 hash，它按进程随机化）
                key = json.dumps([sig, budget, run_idx], sort_keys=True)
                rng = random.Random(seed + int(hashlib.sha256(key.encode()).hexdigest()[:8], 16) % 100000)
                with tempfile.TemporaryDirectory() as tmp:
                    ws = _fresh_root(template_root, tmp)
                    # 价格信号写入配置
                    cfg_file = ws / "config" / "economy.yaml"
                    if sig and cfg_file.exists():
                        import yaml

                        raw = yaml.safe_load(cfg_file.read_text()) or {}
                        raw.setdefault("tools", {})["price_signals"] = sig
                        cfg_file.write_text(yaml.safe_dump(raw))
                    from .config import load_config

                    agent = Agent(root=ws, client=None, config=load_config(ws, cfg_file))
                    agent.grant(budget)
                    policy = PolicyClient(agent=agent, want_tool=want_tool, query=task_brief[:60])
                    agent.client = policy
                    agent.handle(f"赏金 {max(5, budget // 4)}: {task_brief}")
                    m = compute_metrics(agent.ledger, agent.events, agent.board.all_tasks())
                    run_metrics.append(m)
                    agent.db.close()
            avg_spend = sum(m["spend"] for m in run_metrics) / len(run_metrics)
            avg_income = sum(m["income"] for m in run_metrics) / len(run_metrics)
            cell = {
                "budget": budget,
                "signal": sig,
                "runs": len(run_metrics),
                "avg_income": round(avg_income, 2),
                "avg_spend": round(avg_spend, 2),
                "avg_metrics": {
                    k: round(sum(m[k] for m in run_metrics) / len(run_metrics), 4)
                    for k in ("savings_rate", "abstention_rate", "plan_adherence",
                              "task_completion_rate", "token_efficiency", "repair_vs_rebuy")
                },
            }
            cells.append(cell)
            sweep.append({"budget": budget, "spend": avg_spend})

    report = {
        "experiment": "budget_sweep",
        "want_tool": want_tool,
        "runs_per_cell": runs_per_cell,
        "seed": seed,
        "cells": cells,
        "budget_sensitivity": budget_sensitivity(sweep),
        "budget_anxiety_index": budget_anxiety_index(sweep),
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    with (out_dir / "report.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["budget", "signal", "avg_income", "avg_spend", "savings_rate",
                    "abstention_rate", "plan_adherence", "task_completion_rate",
                    "token_efficiency", "repair_vs_rebuy"])
        for c in cells:
            w.writerow([
                c["budget"], json.dumps(c["signal"]), c["avg_income"], c["avg_spend"],
                c["avg_metrics"]["savings_rate"], c["avg_metrics"]["abstention_rate"],
                c["avg_metrics"]["plan_adherence"], c["avg_metrics"]["task_completion_rate"],
                c["avg_metrics"]["token_efficiency"], c["avg_metrics"]["repair_vs_rebuy"],
            ])
    return report
