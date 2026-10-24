"""Aria Web UI：FastAPI + WebSocket + 无依赖单页仪表盘。

与 CLI 共用同一个 SQLite 账本——agent 在哪个进程跑，仪表盘就读同一份数据。
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from aria.agent import Agent
from aria.config import load_config
from aria.llm import EchoClient, OpenAIClient

STATIC = Path(__file__).parent / "static"


class ChatIn(BaseModel):
    message: str


class TaskIn(BaseModel):
    title: str
    brief: str
    bounty: int


class ExperimentIn(BaseModel):
    budgets: list[int] = [20, 50, 100, 200]
    runs_per_cell: int = 2


def create_app(root: str | Path | None = None) -> FastAPI:
    app = FastAPI(title="Aria Dashboard")
    cfg = load_config(root)
    agent = Agent(root=root, config=cfg, client=EchoClient(script=[]))

    # 有 key 就接真实模型，否则用确定性策略驱动（开箱即用的演示）
    real = OpenAIClient()
    if real.api_key:
        agent.client = real
    else:
        from aria.experiments import PolicyClient

        policy = PolicyClient(agent=agent, want_tool="calculator", query="1+1")
        agent.client = policy

    @app.get("/api/status")
    def status():
        return agent.status()

    @app.get("/api/license")
    def license_status():
        from aria import enterprise

        return enterprise.status()

    @app.get("/api/metrics")
    def metrics():
        from aria.metrics import compute_metrics

        return compute_metrics(agent.ledger, agent.events, agent.board.all_tasks())

    @app.get("/api/ledger")
    def ledger(limit: int = 100):
        return [e.__dict__ for e in agent.ledger.history(limit)]

    @app.post("/api/chat")
    def chat(body: ChatIn):
        try:
            reply = agent.handle(body.message)
            return {"reply": reply, "status": agent.status()}
        except Exception as exc:
            return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=500)

    @app.post("/api/task")
    def post_task(body: TaskIn):
        t = agent.board.post(title=body.title, brief=body.brief, bounty=body.bounty)
        return {"task": t.to_dict()}

    @app.post("/api/experiment")
    def experiment(body: ExperimentIn):
        from aria.experiments import run_experiment

        report = run_experiment(
            root=cfg.root, budgets=body.budgets, runs_per_cell=body.runs_per_cell,
            signals=cfg.experiments.default_signals,
        )
        return report

    @app.websocket("/ws")
    async def ws(websocket: WebSocket):
        await websocket.accept()
        try:
            while True:
                await websocket.send_json(agent.status())
                import asyncio

                await asyncio.sleep(2)
        except Exception:
            pass

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
