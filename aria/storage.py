"""SQLite 存储层：schema 初始化与通用查询助手。"""
from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    debit TEXT NOT NULL,
    credit TEXT NOT NULL,
    amount INTEGER NOT NULL CHECK (amount > 0),
    kind TEXT NOT NULL,
    ref TEXT DEFAULT '',
    note TEXT DEFAULT '',
    meta TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_entries_kind ON entries(kind);
CREATE INDEX IF NOT EXISTS idx_entries_ref ON entries(ref);

CREATE TABLE IF NOT EXISTS tool_states (
    name TEXT PRIMARY KEY,
    owned INTEGER DEFAULT 0,
    calls INTEGER DEFAULT 0,
    life REAL DEFAULT 100.0,
    repairs_left INTEGER DEFAULT 0,
    rented_until_session INTEGER
);

CREATE TABLE IF NOT EXISTS skill_states (
    name TEXT PRIMARY KEY,
    owned INTEGER DEFAULT 0,
    calls INTEGER DEFAULT 0,
    max_lines INTEGER DEFAULT 0,
    available_lines INTEGER DEFAULT 0,
    last_used TEXT,
    decay_speed REAL DEFAULT 0.1
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    title TEXT,
    brief TEXT,
    bounty INTEGER,
    status TEXT DEFAULT 'open',
    assignee TEXT,
    created_at TEXT,
    resolved_at TEXT,
    tip INTEGER DEFAULT 0,
    result TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    metadata TEXT DEFAULT '{}',
    embedding TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    type TEXT NOT NULL,
    session_id TEXT DEFAULT '',
    ref TEXT DEFAULT '',
    payload TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);

CREATE TABLE IF NOT EXISTS kv (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


class Database:
    """薄封装：一个连接、行式返回、显式事务。"""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        cur = self.conn.execute(sql, params)
        self.conn.commit()
        return cur

    def query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, params).fetchall()

    def query_one(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        return self.conn.execute(sql, params).fetchone()

    # ---- kv 小助手（会话计数等）----
    def kv_get(self, key: str, default: str = "0") -> str:
        row = self.query_one("SELECT value FROM kv WHERE key=?", (key,))
        return row["value"] if row else default

    def kv_set(self, key: str, value: str) -> None:
        self.execute(
            "INSERT INTO kv(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )

    def close(self) -> None:
        self.conn.close()
