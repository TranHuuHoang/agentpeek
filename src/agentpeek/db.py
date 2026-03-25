"""SQLite persistence layer for cross-session history and baselines."""

from __future__ import annotations

import json
from pathlib import Path

import aiosqlite

DB_DIR = Path.home() / ".agentpeek"
DB_PATH = DB_DIR / "history.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    start_time_ms INTEGER,
    end_time_ms INTEGER,
    project_path TEXT DEFAULT '',
    agent_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    subagent_type TEXT,
    name TEXT,
    parent_id TEXT,
    status TEXT DEFAULT 'active',
    first_seen_ms INTEGER,
    last_seen_ms INTEGER,
    tool_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    prompt_hash TEXT,
    anomaly_score REAL,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS tool_calls (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    tool_name TEXT,
    duration_ms INTEGER,
    status TEXT DEFAULT 'running',
    timestamp_ms INTEGER,
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);

CREATE TABLE IF NOT EXISTS agent_baselines (
    subagent_type TEXT PRIMARY KEY,
    sample_count INTEGER DEFAULT 0,
    tool_count_mean REAL DEFAULT 0,
    tool_count_stddev REAL DEFAULT 0,
    duration_mean_ms REAL DEFAULT 0,
    duration_stddev_ms REAL DEFAULT 0,
    error_rate_mean REAL DEFAULT 0,
    completion_rate REAL DEFAULT 1.0,
    tool_sequence_common TEXT DEFAULT '[]',
    updated_at_ms INTEGER
);

CREATE INDEX IF NOT EXISTS idx_agents_type ON agents(subagent_type);
CREATE INDEX IF NOT EXISTS idx_agents_session ON agents(session_id);
CREATE INDEX IF NOT EXISTS idx_tool_calls_agent ON tool_calls(agent_id);
"""


class Database:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        self._db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(str(self._db_path))
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        assert self._conn is not None, "Database not connected"
        return self._conn

    # ── Sessions ─────────────────────────────────────────────────────

    async def upsert_session(
        self, session_id: str, start_time_ms: int, project_path: str = "",
        agent_count: int = 0, status: str = "active", end_time_ms: int | None = None,
    ) -> None:
        await self.conn.execute(
            """INSERT INTO sessions (id, start_time_ms, end_time_ms, project_path, agent_count, status)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 end_time_ms=COALESCE(excluded.end_time_ms, end_time_ms),
                 agent_count=excluded.agent_count,
                 status=excluded.status""",
            (session_id, start_time_ms, end_time_ms, project_path, agent_count, status),
        )
        await self.conn.commit()

    async def complete_session(self, session_id: str, end_time_ms: int) -> None:
        await self.conn.execute(
            "UPDATE sessions SET status='complete', end_time_ms=? WHERE id=?",
            (end_time_ms, session_id),
        )
        await self.conn.commit()

    async def list_sessions(self, limit: int = 50, offset: int = 0) -> list[dict]:
        cursor = await self.conn.execute(
            "SELECT * FROM sessions ORDER BY start_time_ms DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, row)) for row in await cursor.fetchall()]

    # ── Agents ───────────────────────────────────────────────────────

    async def upsert_agent(
        self, agent_id: str, session_id: str, subagent_type: str | None = None,
        name: str = "", parent_id: str | None = None, status: str = "active",
        first_seen_ms: int = 0, last_seen_ms: int = 0, tool_count: int = 0,
        error_count: int = 0, prompt_hash: str | None = None, anomaly_score: float | None = None,
    ) -> None:
        await self.conn.execute(
            """INSERT INTO agents (id, session_id, subagent_type, name, parent_id, status,
                 first_seen_ms, last_seen_ms, tool_count, error_count, prompt_hash, anomaly_score)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 status=excluded.status, last_seen_ms=excluded.last_seen_ms,
                 tool_count=excluded.tool_count, error_count=excluded.error_count,
                 anomaly_score=excluded.anomaly_score""",
            (agent_id, session_id, subagent_type, name, parent_id, status,
             first_seen_ms, last_seen_ms, tool_count, error_count, prompt_hash, anomaly_score),
        )
        await self.conn.commit()

    async def get_completed_agents_by_type(self, subagent_type: str) -> list[dict]:
        cursor = await self.conn.execute(
            "SELECT * FROM agents WHERE subagent_type=? AND status='done' ORDER BY first_seen_ms DESC",
            (subagent_type,),
        )
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, row)) for row in await cursor.fetchall()]

    async def get_session_agents(self, session_id: str) -> list[dict]:
        cursor = await self.conn.execute(
            "SELECT * FROM agents WHERE session_id=? ORDER BY first_seen_ms",
            (session_id,),
        )
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, row)) for row in await cursor.fetchall()]

    # ── Tool calls ───────────────────────────────────────────────────

    async def upsert_tool_call(
        self, tc_id: str, agent_id: str, session_id: str,
        tool_name: str = "", duration_ms: int | None = None,
        status: str = "running", timestamp_ms: int = 0,
    ) -> None:
        await self.conn.execute(
            """INSERT INTO tool_calls (id, agent_id, session_id, tool_name, duration_ms, status, timestamp_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 duration_ms=COALESCE(excluded.duration_ms, duration_ms),
                 status=excluded.status""",
            (tc_id, agent_id, session_id, tool_name, duration_ms, status, timestamp_ms),
        )
        await self.conn.commit()

    # ── Baselines ────────────────────────────────────────────────────

    async def get_baseline(self, subagent_type: str) -> dict | None:
        cursor = await self.conn.execute(
            "SELECT * FROM agent_baselines WHERE subagent_type=?",
            (subagent_type,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        cols = [d[0] for d in cursor.description]
        return dict(zip(cols, row))

    async def upsert_baseline(
        self, subagent_type: str, sample_count: int,
        tool_count_mean: float, tool_count_stddev: float,
        duration_mean_ms: float, duration_stddev_ms: float,
        error_rate_mean: float, completion_rate: float,
        tool_sequence_common: str = "[]", updated_at_ms: int = 0,
    ) -> None:
        await self.conn.execute(
            """INSERT INTO agent_baselines
                 (subagent_type, sample_count, tool_count_mean, tool_count_stddev,
                  duration_mean_ms, duration_stddev_ms, error_rate_mean, completion_rate,
                  tool_sequence_common, updated_at_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(subagent_type) DO UPDATE SET
                 sample_count=excluded.sample_count,
                 tool_count_mean=excluded.tool_count_mean,
                 tool_count_stddev=excluded.tool_count_stddev,
                 duration_mean_ms=excluded.duration_mean_ms,
                 duration_stddev_ms=excluded.duration_stddev_ms,
                 error_rate_mean=excluded.error_rate_mean,
                 completion_rate=excluded.completion_rate,
                 tool_sequence_common=excluded.tool_sequence_common,
                 updated_at_ms=excluded.updated_at_ms""",
            (subagent_type, sample_count, tool_count_mean, tool_count_stddev,
             duration_mean_ms, duration_stddev_ms, error_rate_mean, completion_rate,
             tool_sequence_common, updated_at_ms),
        )
        await self.conn.commit()

    async def get_all_baselines(self) -> list[dict]:
        cursor = await self.conn.execute("SELECT * FROM agent_baselines ORDER BY subagent_type")
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, row)) for row in await cursor.fetchall()]

    async def get_agent_scores_by_type(self, subagent_type: str, limit: int = 20) -> list[dict]:
        cursor = await self.conn.execute(
            """SELECT a.id, a.session_id, a.anomaly_score, a.tool_count,
                      (a.last_seen_ms - a.first_seen_ms) as duration_ms, a.first_seen_ms
               FROM agents a
               WHERE a.subagent_type=? AND a.status='done' AND a.anomaly_score IS NOT NULL
               ORDER BY a.first_seen_ms DESC LIMIT ?""",
            (subagent_type, limit),
        )
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, row)) for row in await cursor.fetchall()]
