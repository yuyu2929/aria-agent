"""运行行为实验：python run_experiment.py [--budgets 20,50,100,200] [--runs 3]

扫掠（预算 × 价格信号），输出 artifacts/experiments/report.json 与 report.csv。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from aria.config import load_config
from aria.experiments import run_experiment


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budgets", default="")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--tool", default="web_search")
    args = ap.parse_args()

    cfg = load_config(Path(__file__).parent)
    budgets = [int(x) for x in args.budgets.split(",") if x.strip()] or cfg.experiments.default_budgets
    report = run_experiment(
        root=Path(__file__).parent,
        budgets=budgets,
        signals=cfg.experiments.default_signals,
        runs_per_cell=args.runs,
        seed=cfg.experiments.seed,
        want_tool=args.tool,
    )
    print(json.dumps({
        "budget_sensitivity": report["budget_sensitivity"],
        "budget_anxiety_index": report["budget_anxiety_index"],
        "cells": report["cells"],
    }, indent=2, ensure_ascii=False))
    print("\n报告已写入 artifacts/experiments/report.{json,csv}")


if __name__ == "__main__":
    main()
