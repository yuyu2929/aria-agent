"""语义记忆测试。"""
from __future__ import annotations


def test_add_search_delete(agent):
    ids = agent.memory.add([
        {"content": "The Moon has no atmosphere", "metadata": {"category": "space"}},
        {"content": "Python lists are mutable", "metadata": {"category": "programming"}},
    ])
    assert len(ids) == 2
    hits = agent.memory.search("Moon atmosphere", top_k=2)
    assert hits and "Moon" in hits[0]["content"]
    agent.memory.delete([ids[0]])
    hits = agent.memory.search("Moon atmosphere", top_k=5)
    assert all("Moon" not in h["content"] for h in hits)


def test_filters(agent):
    agent.memory.add([
        {"content": "cheap fact", "metadata": {"importance": 1, "category": "x"}},
        {"content": "important fact", "metadata": {"importance": 9, "category": "x"}},
    ])
    hits = agent.memory.search("fact", top_k=5, filters=["importance >= 5"])
    assert len(hits) == 1 and "important" in hits[0]["content"]


def test_bad_filter_rejects_all(agent):
    agent.memory.add([{"content": "a", "metadata": {"k": 1}}])
    hits = agent.memory.search("a", top_k=5, filters=["k >"])
    assert hits == []


def test_update_same_id(agent):
    mid = agent.memory.add([{"content": "v1"}])[0]
    agent.memory.add([{"id": mid, "content": "v2"}])
    hits = agent.memory.search("v2", top_k=5)
    assert hits and hits[0]["content"] == "v2"
