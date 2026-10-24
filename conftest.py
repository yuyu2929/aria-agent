"""pytest 全局夹具：隔离工作区 + 可用 Agent。"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


@pytest.fixture
def ws(tmp_path):
    """隔离工作区：复制 marketplace 与 config，账本不落真实项目。"""
    shutil.copytree(ROOT / "marketplace", tmp_path / "marketplace")
    (tmp_path / "config").mkdir()
    shutil.copy(ROOT / "config" / "economy.yaml", tmp_path / "config" / "economy.yaml")
    return tmp_path


@pytest.fixture
def agent(ws):
    from aria.agent import Agent
    from aria.llm import EchoClient

    a = Agent(root=ws, client=EchoClient(script=[]))
    yield a
    a.db.close()
