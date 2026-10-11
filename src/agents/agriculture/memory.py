"""Bounded, farm-scoped persistent memory for agriculture agents.

SQLite is used deliberately: it is available in the container, survives
restarts through a mounted volume, and keeps memory ownership explicit. The
store saves normalized user questions and agent summaries, never raw secrets or
full model prompts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import sqlite3
from pathlib import Path
import re
from threading import Lock


_SECRET_PATTERN = re.compile(r"(?i)\b(?:api[_ -]?key|token|password|secret)\s*[:=]\s*\S+")


@dataclass(frozen=True)
class MemoryEntry:
    role: str
    agent_name: str
    content: str
    created_at: str


class AgentMemoryStore:
    """Persistent bounded memory isolated by user and farm identifiers."""

    def __init__(self, path: str, max_entries: int = 20, retention_days: int = 90):
        if max_entries < 1 or retention_days < 1:
            raise ValueError("memory limits must be positive")
        self.path = path
        self.max_entries = max_entries
        self.retention_days = retention_days
        self._lock = Lock()
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_key TEXT NOT NULL,
                    farm_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    agent_name TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_agent_memory_scope "
                "ON agent_memory(owner_key, farm_id, created_at)"
            )

    @staticmethod
    def _owner_key(user_id: str) -> str:
        return hashlib.sha256(user_id.encode("utf-8")).hexdigest()

    def _purge(self, connection: sqlite3.Connection) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.retention_days)
        connection.execute("DELETE FROM agent_memory WHERE created_at < ?", (cutoff.isoformat(),))

    def remember(self, user_id: str, farm_id: str, role: str, agent_name: str, content: str) -> None:
        safe_content = _SECRET_PATTERN.sub("[REDACTED]", " ".join(content.split()))[:2000]
        if not safe_content:
            return
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as connection:
            self._purge(connection)
            owner_key = self._owner_key(user_id)
            connection.execute(
                "INSERT INTO agent_memory(owner_key, farm_id, role, agent_name, content, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (owner_key, farm_id, role, agent_name, safe_content, now),
            )
            connection.execute(
                """
                DELETE FROM agent_memory
                WHERE owner_key = ? AND farm_id = ? AND id NOT IN (
                    SELECT id FROM agent_memory
                    WHERE owner_key = ? AND farm_id = ?
                    ORDER BY id DESC LIMIT ?
                )
                """,
                (owner_key, farm_id, owner_key, farm_id, self.max_entries),
            )

    def recall(self, user_id: str, farm_id: str, limit: int | None = None) -> list[MemoryEntry]:
        requested = min(limit or self.max_entries, self.max_entries)
        with self._lock, self._connect() as connection:
            self._purge(connection)
            rows = connection.execute(
                """
                SELECT role, agent_name, content, created_at
                FROM agent_memory
                WHERE owner_key = ? AND farm_id = ?
                ORDER BY id DESC LIMIT ?
                """,
                (self._owner_key(user_id), farm_id, requested),
            ).fetchall()
        return [MemoryEntry(row["role"], row["agent_name"], row["content"], row["created_at"]) for row in reversed(rows)]

    def forget(self, user_id: str, farm_id: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "DELETE FROM agent_memory WHERE owner_key = ? AND farm_id = ?",
                (self._owner_key(user_id), farm_id),
            )
