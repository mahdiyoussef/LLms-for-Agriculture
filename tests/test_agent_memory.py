"""Tests for bounded, isolated agent memory."""

from src.agents.agriculture.memory import AgentMemoryStore


def test_memory_round_trip_is_scoped_and_bounded(tmp_path):
    store = AgentMemoryStore(str(tmp_path / "memory.sqlite3"), max_entries=2)
    store.remember("user-a", "farm-1", "user", "irrigation", "first")
    store.remember("user-a", "farm-1", "assistant", "irrigation", "second")
    store.remember("user-a", "farm-1", "assistant", "irrigation", "third")
    store.remember("user-b", "farm-1", "user", "soil-health", "other user")

    entries = store.recall("user-a", "farm-1")
    assert [entry.content for entry in entries] == ["second", "third"]
    assert store.recall("user-b", "farm-1")[0].content == "other user"
    assert store.recall("user-a", "farm-2") == []


def test_memory_redacts_credentials_and_can_be_forgotten(tmp_path):
    store = AgentMemoryStore(str(tmp_path / "memory.sqlite3"))
    store.remember("user-a", "farm-1", "user", "extension", "api_key=do-not-store")
    assert "[REDACTED]" in store.recall("user-a", "farm-1")[0].content
    store.forget("user-a", "farm-1")
    assert store.recall("user-a", "farm-1") == []
