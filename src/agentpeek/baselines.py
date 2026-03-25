"""Baseline computation from historical agent data by subagent_type."""

from __future__ import annotations

import math
import time

from agentpeek.db import Database


def _now_ms() -> int:
    return int(time.time() * 1000)


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    variance = sum((v - m) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)


async def recompute_baseline(db: Database, subagent_type: str) -> dict | None:
    """Recompute baseline for a subagent_type from all completed historical agents."""
    agents = await db.get_completed_agents_by_type(subagent_type)
    if not agents:
        return None

    tool_counts = [float(a.get("tool_count", 0)) for a in agents]
    durations = [float(a.get("last_seen_ms", 0) - a.get("first_seen_ms", 0)) for a in agents]
    error_rates = [
        float(a.get("error_count", 0)) / max(a.get("tool_count", 1), 1)
        for a in agents
    ]
    completed = sum(1 for a in agents if a.get("status") == "done")

    now = _now_ms()
    await db.upsert_baseline(
        subagent_type=subagent_type,
        sample_count=len(agents),
        tool_count_mean=_mean(tool_counts),
        tool_count_stddev=_stddev(tool_counts),
        duration_mean_ms=_mean(durations),
        duration_stddev_ms=_stddev(durations),
        error_rate_mean=_mean(error_rates),
        completion_rate=completed / len(agents) if agents else 1.0,
        updated_at_ms=now,
    )

    return {
        "subagent_type": subagent_type,
        "sample_count": len(agents),
        "tool_count_mean": _mean(tool_counts),
        "tool_count_stddev": _stddev(tool_counts),
        "duration_mean_ms": _mean(durations),
        "duration_stddev_ms": _stddev(durations),
        "error_rate_mean": _mean(error_rates),
        "completion_rate": completed / len(agents) if agents else 1.0,
    }
