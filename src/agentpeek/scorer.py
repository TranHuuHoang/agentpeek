"""Anomaly scoring engine — computes per-agent health scores from historical baselines."""

from __future__ import annotations

import time
from typing import Any


def _now_ms() -> int:
    return int(time.time() * 1000)


def z_score(value: float, mean: float, stddev: float) -> float:
    """Compute z-score with floored stddev to prevent div-by-zero."""
    safe_std = max(stddev, mean * 0.2, 1.0)
    return (value - mean) / safe_std


def compute_score(
    agent: dict[str, Any],
    baseline: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Score an agent against its baseline.

    Returns AgentScore dict or None if no baseline available.
    """
    if not baseline or baseline.get("sample_count", 0) < 2:
        return None

    # Current metrics
    tool_count = agent.get("tool_count", 0)
    first_seen = agent.get("first_seen_ms", 0)
    last_seen = agent.get("last_seen_ms", 0)
    duration_ms = last_seen - first_seen
    error_count = agent.get("error_count", 0)
    error_rate = error_count / max(tool_count, 1)

    # Baseline stats
    tc_mean = baseline.get("tool_count_mean", 0)
    tc_std = baseline.get("tool_count_stddev", 0)
    dur_mean = baseline.get("duration_mean_ms", 0)
    dur_std = baseline.get("duration_stddev_ms", 0)
    err_mean = baseline.get("error_rate_mean", 0)

    # Z-scores
    tool_z = z_score(tool_count, tc_mean, tc_std)
    duration_z = z_score(duration_ms, dur_mean, dur_std)
    error_deviation = max(0, error_rate - err_mean)

    # Composite score
    raw = abs(tool_z) * 0.3 + abs(duration_z) * 0.3 + error_deviation * 5 * 0.4

    # Completion penalty
    if agent.get("status") != "done" and duration_ms > dur_mean * 2:
        raw += 0.5

    # Health classification
    if raw < 1.0:
        health = "green"
    elif raw < 2.0:
        health = "yellow"
    else:
        health = "red"

    # Confidence level
    n = baseline.get("sample_count", 0)
    if n < 5:
        confidence = "calibrating"
    else:
        confidence = "confident"

    return {
        "value": round(raw, 2),
        "health": health,
        "confidence": confidence,
        "baseline_n": n,
        "tool_z": round(tool_z, 2),
        "duration_z": round(duration_z, 2),
        "baseline_tool_mean": round(tc_mean, 1),
        "baseline_duration_mean_ms": round(dur_mean, 0),
    }
