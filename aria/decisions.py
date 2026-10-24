"""决策日志：把 Agent 的每一个"经济决策"落成结构化事件。

这是行为研究的核心数据源——工具因为贵被拒绝、技能因为不用而遗忘、
任务因为没赏金被放弃，全部可查询、可绘图、可复现。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from .storage import Database


class EventLog:
    def __init__(self, db: Database):
        self.db = db

    def log(self, type: str, session_id: str = "", ref: str = "", payload: dict | None = None) -> None:
        self.db.execute(
            "INSERT INTO events(ts, type, session_id, ref, payload) VALUES(?,?,?,?,?)",
            (
                datetime.now(timezone.utc).isoformat(),
                type, session_id, ref, json.dumps(payload or {}),
            ),
        )

    def recent(self, limit: int = 50, type: str | None = None) -> list[dict]:
        sql = "SELECT ts, type, session_id, ref, payload FROM events"
        params: tuple = ()
        if type:
            sql += " WHERE type=?"
            params = (type,)
        sql += " ORDER BY id DESC LIMIT ?"
        params += (limit,)
        return [
            {
                "ts": r["ts"], "type": r["type"], "session_id": r["session_id"],
                "ref": r["ref"], "payload": json.loads(r["payload"]),
            }
            for r in self.db.query(sql, params)
        ]

    def count(self, type: str) -> int:
        row = self.db.query_one("SELECT COUNT(*) AS c FROM events WHERE type=?", (type,))
        return int(row["c"])
