"""Pydantic models — contract between server, scorer, and frontend."""

from __future__ import annotations

import enum
import time
from typing import Any

from pydantic import BaseModel, Field


def _now_ms() -> int:
    return int(time.time() * 1000)


# ── Core v1 models ───────────────────────────────────────────────────


class Agent(BaseModel):
    id: str
    name: str
    parent: str | None = None
    status: str = "active"  # active | done
    subagent_type: str | None = None
    description: str = ""
    prompt: str | None = None
    first_seen_ms: int = Field(default_factory=_now_ms)
    last_seen_ms: int = Field(default_factory=_now_ms)
    tool_count: int = 0
    error_count: int = 0
    children: list[str] = Field(default_factory=list)
    result: str | None = None
    score: AgentScore | None = None


class ToolCall(BaseModel):
    id: str
    tool: str
    input: dict[str, Any] = Field(default_factory=dict)
    input_preview: str = ""
    timestamp_ms: int = Field(default_factory=_now_ms)
    status: str = "running"  # running | done | error
    output_preview: str | None = None
    response: str | None = None
    duration_ms: int | None = None


class Edge(BaseModel):
    from_agent: str = Field(alias="from")
    to_agent: str = Field(alias="to")
    label: str = ""
    prompt_preview: str = ""
    timestamp_ms: int = Field(default_factory=_now_ms)

    model_config = {"populate_by_name": True}


class Event(BaseModel):
    id: str
    hook: str
    tool_name: str = ""
    agent_context: str = ""
    agent_name: str = ""
    timestamp: str = ""
    timestamp_ms: int = Field(default_factory=_now_ms)
    session_id: str = ""
    input_preview: str = ""
    output_preview: str = ""


# ── v2 scoring models ───────────────────────────────────────────────


class HealthLevel(str, enum.Enum):
    green = "green"
    yellow = "yellow"
    red = "red"


class AgentScore(BaseModel):
    value: float = 0.0
    health: HealthLevel = HealthLevel.green
    confidence: str = "new"  # new | calibrating | confident
    baseline_n: int = 0
    tool_z: float = 0.0
    duration_z: float = 0.0


class AgentBaseline(BaseModel):
    subagent_type: str
    sample_count: int = 0
    tool_count_mean: float = 0.0
    tool_count_stddev: float = 0.0
    duration_mean_ms: float = 0.0
    duration_stddev_ms: float = 0.0
    error_rate_mean: float = 0.0
    completion_rate: float = 1.0
    tool_sequence_common: str = "[]"  # JSON
    updated_at_ms: int = Field(default_factory=_now_ms)


class Session(BaseModel):
    id: str
    start_time_ms: int = Field(default_factory=_now_ms)
    end_time_ms: int | None = None
    project_path: str = ""
    agent_count: int = 0
    status: str = "active"  # active | complete


# ── API response ─────────────────────────────────────────────────────


class StateSummary(BaseModel):
    total_agents: int = 0
    active_agents: int = 0
    total_events: int = 0
    total_tool_calls: int = 0


# Forward ref update
Agent.model_rebuild()
