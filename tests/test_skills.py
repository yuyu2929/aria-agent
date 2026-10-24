"""技能系统测试：购买、分段递进、时间衰退。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


def test_buy_skill_segments_content(agent):
    agent.grant(100)
    out = agent.skills.buy("python_expert")
    assert "Learned" in out
    st = agent.skills._state("python_expert")
    assert st.owned
    assert st.max_lines > 5  # SKILL.md 被切成多段


def test_use_skill_returns_chunk(agent):
    agent.grant(100)
    agent.skills.buy("python_expert")
    out = agent.skills.use("python_expert")
    assert "Python" in out["result"]
    assert out["usage"]["available_lines"] > 0


def test_use_unowned_skill(agent):
    out = agent.skills.use("python_expert")
    assert "not an owned skill" in out["result"]


def test_skill_decays_after_idle(agent):
    agent.grant(100)
    agent.skills.buy("python_expert")
    agent.skills.use("python_expert")
    st = agent.skills._state("python_expert")
    before = st.available_lines
    # 把最后使用时间推到 10 小时前（超过 4h 保鲜期）
    st.last_used = (datetime.now(timezone.utc) - timedelta(hours=10)).isoformat()
    agent.skills._save_state(st)
    agent.skills.use("python_expert")
    st = agent.skills._state("python_expert")
    assert st.available_lines < before
    assert agent.events.count("skill_decayed") == 1


def test_skill_regains_within_freshness(agent):
    agent.grant(100)
    agent.skills.buy("python_expert")
    agent.skills.use("python_expert")
    st = agent.skills._state("python_expert")
    st.available_lines = max(0, st.max_lines - 10)
    st.last_used = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    agent.skills._save_state(st)
    agent.skills.use("python_expert")
    st = agent.skills._state("python_expert")
    assert st.available_lines == min(st.max_lines, st.max_lines - 10 + 5)


def test_segment_text_basic():
    from aria.skills import segment_text

    segs = segment_text("# Title\n\nFirst sentence. Second sentence!\n\n## Sub\n\nMore text here.")
    assert any(s.startswith("# Title") for s in segs)
    assert "First sentence." in segs
    assert "Second sentence!" in segs
