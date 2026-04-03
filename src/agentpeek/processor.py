"""Event processor — builds in-memory state from hook events.

Ported from poc/server.py with additions for SQLite persistence.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from agentpeek.baselines import recompute_baseline
from agentpeek.db import Database
from agentpeek.scorer import compute_score


def _now_ms() -> int:
    return int(time.time() * 1000)


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]


def _tool_preview(tool_name: str, tool_input: dict) -> str:
    if tool_name == "Bash":
        return (tool_input.get("command", "") or "")[:80]
    elif tool_name in ("Read", "Write", "Edit"):
        return (tool_input.get("file_path", "") or "").split("/")[-1]
    elif tool_name in ("Grep", "Glob"):
        return (tool_input.get("pattern", "") or "")[:60]
    elif tool_name == "WebSearch":
        return (tool_input.get("query", "") or tool_input.get("prompt", "") or "")[:80]
    elif tool_name == "WebFetch":
        return (tool_input.get("url", "") or "")[:80]
    elif tool_name == "Agent":
        return (tool_input.get("description", "") or "")[:60]
    else:
        return str(tool_input)[:60]


class EventProcessor:
    """Processes hook events into in-memory state. Optionally persists to SQLite."""

    def __init__(self, db: Database | None = None) -> None:
        self.db = db

        # In-memory state (same structure as PoC)
        self.events: list[dict] = []
        self.agents: dict[str, dict] = {}
        self.edges: list[dict] = []
        self.tool_calls: dict[str, list[dict]] = {}

        # Internal tracking
        self._pending_spawns: dict[str, dict] = {}
        self._active_children: dict[str, set] = {}
        self._session_current: dict[str, str] = {}
        self._known_sessions: set[str] = set()

        # Session metadata: session_id -> {id, start_time_ms, project_path, status}
        self.sessions: dict[str, dict] = {}

        # SSE subscribers
        self._subscribers: list[asyncio.Queue] = []

        # Session inactivity tracking
        self._session_last_event: dict[str, int] = {}
        # Track last agent that made a real tool call (not Agent spawn) per session
        self._last_tool_caller: dict[str, str] = {}
        self._inactivity_timeout_ms = 5 * 60 * 1000  # 5 minutes

        # Agent tool history for loop detection
        self._agent_tool_history: dict[str, list[tuple[str, str]]] = {}

        # Baseline cache: subagent_type -> {baseline_data, fetched_at_ms}
        self._baseline_cache: dict[str, dict] = {}
        self._baseline_cache_ttl_ms = 60_000  # 60s TTL

        # Transcript usage cache: transcript_path -> {file_size, usage}
        self._transcript_cache: dict[str, dict] = {}

        # Per-agent transcript paths: agent_id -> transcript_path
        self._agent_transcript_paths: dict[str, str] = {}

        # Subagents directory scan cache: dir_path -> {scanned_at_ms, mapping}
        self._subagents_dir_cache: dict[str, dict] = {}

    def _root_id(self, session_id: str) -> str:
        return f"root:{session_id}"

    def _ensure_session_root(self, session_id: str, now_ms: int) -> str:
        root_id = self._root_id(session_id)
        if root_id not in self.agents:
            self.agents[root_id] = {
                "id": root_id, "name": "Claude Code", "parent": None,
                "status": "active", "subagent_type": None, "description": "Main session",
                "session_id": session_id,
                "first_seen_ms": now_ms, "last_seen_ms": now_ms,
                "tool_count": 0, "error_count": 0, "children": [],
                "prompt": None, "result": None, "score": None,
                "estimated_input_chars": 0, "estimated_output_chars": 0,
            }
            self._active_children[root_id] = set()
            self.tool_calls[root_id] = []
        return root_id

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q) if hasattr(self._subscribers, 'discard') else None
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass

    def _notify_subscribers(self) -> None:
        for q in self._subscribers:
            try:
                q.put_nowait("update")
            except asyncio.QueueFull:
                pass

    def _compute_files_touched(self, agent_id: str) -> dict:
        """Extract files touched from tool calls: read/wrote/edited/deleted."""
        files: dict[str, list[str]] = {"read": [], "wrote": [], "edited": [], "deleted": []}
        for tc in self.tool_calls.get(agent_id, []):
            tool = tc.get("tool", "")
            inp = tc.get("input", {})
            fp = inp.get("file_path", "")
            if not fp:
                continue
            fname = fp.split("/")[-1]
            if tool == "Read" and fname not in files["read"]:
                files["read"].append(fname)
            elif tool == "Write" and fname not in files["wrote"]:
                files["wrote"].append(fname)
            elif tool == "Edit" and fname not in files["edited"]:
                files["edited"].append(fname)
        # Deduplicate: if wrote, don't also show as edited
        files["edited"] = [f for f in files["edited"] if f not in files["wrote"]]
        # Remove empty lists
        return {k: v for k, v in files.items() if v}

    def _compute_time_share(self, agent: dict, session_filter: str | None) -> float:
        """Compute what % of session time this agent consumed."""
        sid = agent.get("session_id")
        if not sid:
            return 0.0
        session_agents = [a for a in self.agents.values() if a.get("session_id") == sid and not a["id"].startswith("root:")]
        total_duration = sum(a.get("last_seen_ms", 0) - a.get("first_seen_ms", 0) for a in session_agents)
        if total_duration <= 0:
            return 0.0
        agent_duration = agent.get("last_seen_ms", 0) - agent.get("first_seen_ms", 0)
        return round(agent_duration / total_duration * 100, 1)

    def _compute_loop_detection(self, agent_id: str) -> dict | None:
        """Scan last 10 tool calls for stuck patterns."""
        calls = self.tool_calls.get(agent_id, [])[-10:]
        if len(calls) < 3:
            return None

        # Pattern A: Same (tool_name, input_preview) appears 3+ times AND most recent call is still that pattern
        from collections import Counter
        signatures = [(tc.get("tool", ""), tc.get("input_preview", "")) for tc in calls if tc.get("tool") != "Agent"]
        if signatures:
            counts = Counter(signatures)
            most_common, count = counts.most_common(1)[0]
            if count >= 3 and signatures[-1] == most_common:
                return {
                    "is_stuck": True,
                    "pattern": "repeated_tool",
                    "tool_name": most_common[0],
                    "repeat_count": count,
                    "description": f"{most_common[0]} called {count}x with same input in last {len(calls)} calls",
                }

        # Pattern B: 3+ consecutive errors on same tool
        consecutive_errors = 0
        last_error_tool = None
        for tc in reversed(calls):
            if tc.get("status") == "error":
                if last_error_tool is None:
                    last_error_tool = tc.get("tool", "")
                if tc.get("tool", "") == last_error_tool:
                    consecutive_errors += 1
                else:
                    break
            else:
                break

        if consecutive_errors >= 3 and last_error_tool:
            return {
                "is_stuck": True,
                "pattern": "failure_loop",
                "tool_name": last_error_tool,
                "repeat_count": consecutive_errors,
                "description": f"{last_error_tool} failed {consecutive_errors}x consecutively",
            }

        return None

    def _read_transcript_usage(self, transcript_path: str) -> dict:
        """Read real token usage from Claude Code transcript file."""
        if not transcript_path or not os.path.exists(transcript_path):
            return {}

        file_size = os.path.getsize(transcript_path)
        cache_key = transcript_path
        cached = self._transcript_cache.get(cache_key)
        if cached and cached.get("file_size") == file_size:
            return cached.get("usage", {})

        usage = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
        try:
            with open(transcript_path, "r") as f:
                for line in f:
                    try:
                        d = json.loads(line.strip())
                        if d.get("type") == "assistant":
                            msg = d.get("message", {})
                            if isinstance(msg, dict):
                                u = msg.get("usage", {})
                                if u:
                                    usage["input_tokens"] += u.get("input_tokens", 0)
                                    usage["output_tokens"] += u.get("output_tokens", 0)
                                    usage["cache_read_input_tokens"] += u.get("cache_read_input_tokens", 0)
                                    usage["cache_creation_input_tokens"] += u.get("cache_creation_input_tokens", 0)
                    except (json.JSONDecodeError, KeyError):
                        continue
        except OSError:
            return {}

        self._transcript_cache[cache_key] = {"file_size": file_size, "usage": usage}
        return usage

    def _read_agent_transcript_usage(self, transcript_path: str) -> dict:
        """Read real token usage from a single agent's transcript file."""
        if not transcript_path or not os.path.exists(transcript_path):
            return {"input_tokens": 0, "output_tokens": 0}

        file_size = os.path.getsize(transcript_path)
        cache_key = f"agent:{transcript_path}"
        cached = self._transcript_cache.get(cache_key)
        if cached and cached.get("file_size") == file_size:
            return cached.get("usage", {"input_tokens": 0, "output_tokens": 0})

        usage = {"input_tokens": 0, "output_tokens": 0}
        try:
            with open(transcript_path, "r") as f:
                for line in f:
                    try:
                        d = json.loads(line.strip())
                        if d.get("type") == "assistant":
                            msg = d.get("message", {})
                            if isinstance(msg, dict):
                                u = msg.get("usage", {})
                                if u:
                                    usage["input_tokens"] += u.get("input_tokens", 0)
                                    usage["output_tokens"] += u.get("output_tokens", 0)
                    except (json.JSONDecodeError, KeyError):
                        continue
        except OSError:
            return {"input_tokens": 0, "output_tokens": 0}

        self._transcript_cache[cache_key] = {"file_size": file_size, "usage": usage}
        return usage

    def _read_root_agent_usage(self, main_transcript_path: str) -> dict:
        """Read token usage from main transcript for root agent only.

        Sums only assistant entries that do NOT have agentId set
        (or have isSidechain=false and no agentId). These belong to the root agent.
        """
        if not main_transcript_path or not os.path.exists(main_transcript_path):
            return {"input_tokens": 0, "output_tokens": 0}

        file_size = os.path.getsize(main_transcript_path)
        cache_key = f"root:{main_transcript_path}"
        cached = self._transcript_cache.get(cache_key)
        if cached and cached.get("file_size") == file_size:
            return cached.get("usage", {"input_tokens": 0, "output_tokens": 0})

        usage = {"input_tokens": 0, "output_tokens": 0}
        try:
            with open(main_transcript_path, "r") as f:
                for line in f:
                    try:
                        d = json.loads(line.strip())
                        if d.get("type") == "assistant":
                            # Skip entries that belong to subagents
                            if d.get("agentId"):
                                continue
                            if d.get("isSidechain") is True:
                                continue
                            msg = d.get("message", {})
                            if isinstance(msg, dict):
                                u = msg.get("usage", {})
                                if u:
                                    usage["input_tokens"] += u.get("input_tokens", 0)
                                    usage["output_tokens"] += u.get("output_tokens", 0)
                    except (json.JSONDecodeError, KeyError):
                        continue
        except OSError:
            return {"input_tokens": 0, "output_tokens": 0}

        self._transcript_cache[cache_key] = {"file_size": file_size, "usage": usage}
        return usage

    def _scan_subagents_dir(self, main_transcript_path: str) -> dict[str, str]:
        """Scan subagents directory for agent transcript files.

        Returns mapping of agent_id -> transcript_path.
        Cached with ~5 second TTL.
        """
        if not main_transcript_path:
            return {}

        sid_base = os.path.basename(main_transcript_path).replace(".jsonl", "")
        subagents_dir = os.path.join(os.path.dirname(main_transcript_path), sid_base, "subagents")

        now_ms = _now_ms()
        cached = self._subagents_dir_cache.get(subagents_dir)
        if cached and (now_ms - cached.get("scanned_at_ms", 0)) < 5000:
            return cached.get("mapping", {})

        mapping: dict[str, str] = {}
        if os.path.isdir(subagents_dir):
            try:
                for fname in os.listdir(subagents_dir):
                    if fname.startswith("agent-") and fname.endswith(".jsonl"):
                        # agent_id is the filename without .jsonl extension
                        agent_id = fname.replace(".jsonl", "")
                        mapping[agent_id] = os.path.join(subagents_dir, fname)
            except OSError:
                pass

        self._subagents_dir_cache[subagents_dir] = {"scanned_at_ms": now_ms, "mapping": mapping}
        return mapping

    def get_state(self, session_filter: str | None = None) -> dict:
        # Filter by session if requested
        if session_filter:
            agent_ids = {aid for aid, a in self.agents.items() if a.get("session_id") == session_filter}
        else:
            agent_ids = set(self.agents.keys())

        # Augment agents with computed fields
        agents_augmented = {}
        for aid in agent_ids:
            agent = self.agents[aid]
            a = dict(agent)
            # Score from baseline
            st = a.get("subagent_type")
            if st and st in self._baseline_cache:
                cached = self._baseline_cache[st]
                a["score"] = compute_score(a, cached.get("baseline"))
            # Files touched
            a["files_touched"] = self._compute_files_touched(aid)
            # Time share
            a["time_share"] = self._compute_time_share(a, session_filter)
            # Loop detection
            a["loop_detection"] = self._compute_loop_detection(aid)
            # Parent name
            parent_id = a.get("parent")
            if parent_id and parent_id in self.agents:
                a["parent_name"] = self.agents[parent_id].get("name", parent_id)
            else:
                a["parent_name"] = None
            agents_augmented[aid] = a

        # Compute session-wide totals for cost attribution (proportional share from chars)
        total_chars = sum(
            a.get("estimated_input_chars", 0) + a.get("estimated_output_chars", 0)
            for a in agents_augmented.values()
        )
        for aid, a in agents_augmented.items():
            agent_chars = a.get("estimated_input_chars", 0) + a.get("estimated_output_chars", 0)
            a["estimated_total_chars"] = agent_chars
            a["token_share_pct"] = round(agent_chars / total_chars * 100, 1) if total_chars > 0 else 0.0

        # Real token usage from transcript
        session_usage = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
        main_transcript_path = ""
        if session_filter and session_filter in self.sessions:
            main_transcript_path = self.sessions[session_filter].get("transcript_path", "")
            if main_transcript_path:
                session_usage = self._read_transcript_usage(main_transcript_path)

        total_input = session_usage.get("input_tokens", 0)
        total_output = session_usage.get("output_tokens", 0)

        # Scan subagents directory for transcript files
        subagent_transcripts: dict[str, str] = {}
        if main_transcript_path:
            subagent_transcripts = self._scan_subagents_dir(main_transcript_path)

        # Per-agent real token usage from individual transcript files
        for aid, a in agents_augmented.items():
            if aid.startswith("root:"):
                # Root agent: read only non-subagent entries from main transcript
                if main_transcript_path:
                    root_usage = self._read_root_agent_usage(main_transcript_path)
                    a["real_input_tokens"] = root_usage.get("input_tokens", 0)
                    a["real_output_tokens"] = root_usage.get("output_tokens", 0)
                else:
                    a["real_input_tokens"] = 0
                    a["real_output_tokens"] = 0
            else:
                # Subagent: try to find its individual transcript file
                agent_tp = self._agent_transcript_paths.get(aid, "")
                if not agent_tp:
                    # Try filesystem scan mapping
                    agent_tp = subagent_transcripts.get(aid, "")
                if not agent_tp and main_transcript_path:
                    # Try constructing the path directly
                    sid_base = os.path.basename(main_transcript_path).replace(".jsonl", "")
                    subagents_dir = os.path.join(os.path.dirname(main_transcript_path), sid_base, "subagents")
                    candidate = os.path.join(subagents_dir, f"{aid}.jsonl")
                    if os.path.exists(candidate):
                        agent_tp = candidate

                if agent_tp:
                    agent_usage = self._read_agent_transcript_usage(agent_tp)
                    a["real_input_tokens"] = agent_usage.get("input_tokens", 0)
                    a["real_output_tokens"] = agent_usage.get("output_tokens", 0)
                else:
                    a["real_input_tokens"] = 0
                    a["real_output_tokens"] = 0

        # Recompute token_share_pct from real tokens if available
        total_real_tokens = sum(
            a.get("real_input_tokens", 0) + a.get("real_output_tokens", 0)
            for a in agents_augmented.values()
        )
        if total_real_tokens > 0:
            for aid, a in agents_augmented.items():
                agent_tokens = a.get("real_input_tokens", 0) + a.get("real_output_tokens", 0)
                if agent_tokens > 0:
                    a["token_share_pct"] = round(agent_tokens / total_real_tokens * 100, 1)
                # Keep chars-based share as fallback if no real token data for this agent

        # Filter edges and events
        if session_filter:
            edges = [e for e in self.edges if e.get("from") in agent_ids or e.get("to") in agent_ids]
            events = [e for e in self.events if e.get("session_id") == session_filter][-200:]
            tool_calls = {k: v[-30:] for k, v in self.tool_calls.items() if k in agent_ids}
        else:
            edges = self.edges
            events = self.events[-200:]
            tool_calls = {k: v[-30:] for k, v in self.tool_calls.items()}

        # Only count agents with errors that are still active (not recovered)
        error_count = sum(1 for a in agents_augmented.values() if a.get("error_count", 0) > 0 and a.get("status") == "active")

        return {
            "agents": agents_augmented,
            "edges": edges,
            "events": events,
            "tool_calls": tool_calls,
            "sessions": list(self.sessions.values()),
            "summary": {
                "total_agents": len(agents_augmented),
                "active_agents": sum(1 for a in agents_augmented.values() if a["status"] == "active"),
                "error_agents": error_count,
                "total_events": len(events),
                "total_tool_calls": sum(len(v) for v in tool_calls.values()),
                "session_input_tokens": total_input,
                "session_output_tokens": total_output,
            },
        }

    def reset(self) -> None:
        self.events.clear()
        self.agents.clear()
        self.edges.clear()
        self._pending_spawns.clear()
        self._active_children.clear()
        self._session_current.clear()
        self._known_sessions.clear()
        self.sessions.clear()
        self.tool_calls.clear()
        self._agent_transcript_paths.clear()
        self._subagents_dir_cache.clear()
        self._notify_subscribers()

    # ── Main entry point ─────────────────────────────────────────────

    def process_event(self, data: dict) -> None:
        hook = data.get("hook", "")
        now_ms = _now_ms()
        session_id = data.get("session_id", "default")

        # Track session activity
        self._session_last_event[session_id] = now_ms

        # Ensure session is known with its own root agent
        if session_id not in self._known_sessions:
            self._known_sessions.add(session_id)
            project_path = data.get("cwd", "")
            self._ensure_session_root(session_id, now_ms)
            self.sessions[session_id] = {
                "id": session_id,
                "start_time_ms": now_ms,
                "project_path": project_path,
                "status": "active",
                "name": None,  # derived from first agent descriptions
            }
            if self.db:
                asyncio.get_event_loop().create_task(
                    self._init_session_in_db(session_id, now_ms, project_path)
                )

        # Capture transcript_path from events
        transcript_path = data.get("transcript_path", "")
        if transcript_path and session_id in self.sessions:
            self.sessions[session_id].setdefault("transcript_path", transcript_path)

        # Auto-discover agents from agent_id field
        agent_id = data.get("agent_id", "")
        agent_type = data.get("agent_type", "")
        if agent_id:
            self._ensure_agent(agent_id, agent_type, now_ms, session_id)

        if hook == "PreToolUse":
            self._process_pre_tool(data, now_ms, session_id)
        elif hook == "PostToolUse":
            self._process_post_tool(data, now_ms, session_id)
        elif hook == "PostToolUseFailure":
            self._process_post_tool(data, now_ms, session_id, is_error=True)
        elif hook == "SubagentStart":
            self._process_subagent_start(data, now_ms, session_id)
        elif hook == "SubagentStop":
            self._process_subagent_stop(data, now_ms, session_id)
        elif hook == "Stop":
            self._process_stop(data, now_ms, session_id)

        self._notify_subscribers()

    async def _recompute_and_cache_baseline(self, subagent_type: str) -> None:
        """Recompute baseline and cache it."""
        if not self.db:
            return
        baseline = await recompute_baseline(self.db, subagent_type)
        if baseline:
            self._baseline_cache[subagent_type] = {
                "baseline": baseline,
                "fetched_at_ms": _now_ms(),
            }

    async def load_baselines(self) -> None:
        """Load all baselines from DB into cache on startup."""
        if not self.db:
            return
        baselines = await self.db.get_all_baselines()
        for b in baselines:
            st = b.get("subagent_type")
            if st:
                self._baseline_cache[st] = {
                    "baseline": b,
                    "fetched_at_ms": _now_ms(),
                }

    async def _init_session_in_db(self, session_id: str, now_ms: int, project_path: str) -> None:
        """Create session and root agent in SQLite."""
        root_id = self._root_id(session_id)
        await self.db.upsert_session(session_id, now_ms, project_path)
        await self.db.upsert_agent(
            root_id, session_id, None, "Claude Code", None, "active", now_ms, now_ms,
        )

    # ── Agent auto-discovery ─────────────────────────────────────────

    def _ensure_agent(self, agent_id: str, agent_type: str, now_ms: int, session_id: str) -> None:
        """Auto-discover agent from agent_id field. Does NOT create edges — SubagentStart handles that."""
        if agent_id and agent_id not in self.agents:
            root_id = self._root_id(session_id)
            label = agent_type or agent_id[:12]
            self.agents[agent_id] = {
                "id": agent_id, "name": label, "parent": root_id,
                "status": "active", "subagent_type": agent_type or None,
                "description": label, "prompt": None,
                "session_id": session_id,
                "first_seen_ms": now_ms, "last_seen_ms": now_ms,
                "tool_count": 0, "error_count": 0, "children": [],
                "result": None, "score": None,
                "estimated_input_chars": 0, "estimated_output_chars": 0,
            }
            # Tentatively add as child of root — SubagentStart will reparent if needed
            if root_id in self.agents:
                if agent_id not in self.agents[root_id]["children"]:
                    self.agents[root_id]["children"].append(agent_id)
            self._active_children.setdefault(root_id, set()).add(agent_id)
            self._active_children[agent_id] = set()
            self.tool_calls[agent_id] = []
            # NOTE: No edge created here — edges are only created in SubagentStart
            print(f"  \033[36m+ auto-discovered\033[0m [{_ts()}] {label} ({agent_id[:12]})")

            if self.db:
                asyncio.get_event_loop().create_task(
                    self.db.upsert_agent(
                        agent_id, session_id, agent_type or None, label,
                        root_id, "active", now_ms, now_ms,
                    )
                )

    def _derive_session_name(self, session_id: str) -> None:
        """Derive a human-readable session name from spawned agent descriptions."""
        session_agents = [
            a for a in self.agents.values()
            if a.get("session_id") == session_id and not a["id"].startswith("root:")
        ]
        if not session_agents:
            return
        # Use the first agent's description as a base
        first_desc = session_agents[0].get("description", "")
        if len(first_desc) > 40:
            first_desc = first_desc[:37] + "..."
        # If there's a project path, combine: "webapp: Auth Implementation"
        project = self.sessions[session_id].get("project_path", "")
        project_name = project.rstrip("/").split("/")[-1] if project else ""
        if project_name and first_desc:
            name = f"{project_name}: {first_desc}"
        elif first_desc:
            name = first_desc
        elif project_name:
            name = project_name
        else:
            name = session_id[:12]
        self.sessions[session_id]["name"] = name

    def _current_agent(self, session_id: str) -> str:
        return self._session_current.get(session_id, self._root_id(session_id))

    # ── PreToolUse ───────────────────────────────────────────────────

    def _process_pre_tool(self, data: dict, now_ms: int, session_id: str) -> None:
        tool_name = data.get("tool_name", "unknown")
        tool_input = data.get("tool_input", {})
        tool_use_id = data.get("tool_use_id", "")

        if tool_name == "Agent":
            parent_id = data.get("agent_id") or self._current_agent(session_id)
            self._pending_spawns[tool_use_id] = {
                "description": tool_input.get("description", ""),
                "prompt": tool_input.get("prompt", ""),
                "subagent_type": tool_input.get("subagent_type", ""),
                "parent_id": parent_id,
                "tool_use_id": tool_use_id,
                "timestamp_ms": now_ms,
            }
            # Also record spawn in parent's tool_calls for execution trace
            spawn_tc = {
                "id": tool_use_id,
                "tool": "Agent",
                "input": tool_input,
                "input_preview": tool_input.get("description", "spawn agent"),
                "timestamp_ms": now_ms,
                "status": "running",
                "output_preview": None,
                "response": None,
                "duration_ms": None,
            }
            self.tool_calls.setdefault(parent_id, []).append(spawn_tc)
            return

        ctx = data.get("agent_id") or self._current_agent(session_id)
        if ctx in self.agents:
            self.agents[ctx]["tool_count"] += 1
            self.agents[ctx]["last_seen_ms"] = now_ms
        # Track this as the last real tool caller for parent detection
        self._last_tool_caller[session_id] = ctx

        input_chars = len(str(tool_input))
        if ctx in self.agents:
            self.agents[ctx]["estimated_input_chars"] = self.agents[ctx].get("estimated_input_chars", 0) + input_chars

        tc = {
            "id": tool_use_id,
            "tool": tool_name,
            "input": tool_input,
            "input_preview": _tool_preview(tool_name, tool_input),
            "timestamp_ms": now_ms,
            "status": "running",
            "output_preview": None,
            "response": None,
            "duration_ms": None,
            "input_chars": input_chars,
        }
        self.tool_calls.setdefault(ctx, []).append(tc)

        self.events.append({
            "id": uuid.uuid4().hex[:8],
            "hook": "PreToolUse",
            "tool_name": tool_name,
            "agent_context": ctx,
            "agent_name": self.agents.get(ctx, {}).get("name", ctx),
            "timestamp": _ts(),
            "timestamp_ms": now_ms,
            "session_id": session_id,
            "input_preview": tc["input_preview"],
            "output_preview": "",
            "full_input": str(tool_input)[:5000],
        })

        name = self.agents.get(ctx, {}).get("name", ctx)[:25]
        print(f"  \033[33m> {tool_name:12s}\033[0m [{_ts()}] {name}: {tc['input_preview'][:60]}")

        if self.db and tool_use_id:
            asyncio.get_event_loop().create_task(
                self.db.upsert_tool_call(
                    tool_use_id, ctx, session_id, tool_name,
                    status="running", timestamp_ms=now_ms,
                )
            )

    # ── PostToolUse ──────────────────────────────────────────────────

    def _process_post_tool(self, data: dict, now_ms: int, session_id: str, is_error: bool = False) -> None:
        tool_name = data.get("tool_name", "unknown")
        tool_response = data.get("tool_response", "")
        tool_use_id = data.get("tool_use_id", "")

        if tool_name == "Agent":
            return

        ctx = data.get("agent_id") or self._current_agent(session_id)
        resp_str = str(tool_response)[:2000] if tool_response else ""
        status = "error" if is_error else "done"

        output_chars = len(resp_str)
        if ctx in self.agents:
            self.agents[ctx]["estimated_output_chars"] = self.agents[ctx].get("estimated_output_chars", 0) + output_chars

        if is_error and ctx in self.agents:
            self.agents[ctx]["error_count"] = self.agents[ctx].get("error_count", 0) + 1

        calls = self.tool_calls.get(ctx, [])
        for tc in reversed(calls):
            if tc["id"] == tool_use_id or (tc["tool"] == tool_name and tc["status"] == "running"):
                tc["status"] = status
                tc["output_preview"] = resp_str[:300]
                tc["response"] = resp_str
                tc["duration_ms"] = now_ms - tc["timestamp_ms"]
                tc["output_chars"] = output_chars
                break

        self.events.append({
            "id": uuid.uuid4().hex[:8],
            "hook": "PostToolUse" if not is_error else "PostToolUseFailure",
            "tool_name": tool_name,
            "agent_context": ctx,
            "agent_name": self.agents.get(ctx, {}).get("name", ctx),
            "timestamp": _ts(),
            "timestamp_ms": now_ms,
            "session_id": session_id,
            "input_preview": "",
            "output_preview": resp_str[:300],
            "full_output": resp_str[:5000],
        })

        if self.db and tool_use_id:
            # Find matched tool call's duration
            matched_duration = None
            for tc in reversed(calls):
                if tc["id"] == tool_use_id:
                    matched_duration = tc.get("duration_ms")
                    break
            asyncio.get_event_loop().create_task(
                self.db.upsert_tool_call(
                    tool_use_id, ctx, session_id, tool_name,
                    duration_ms=matched_duration, status=status, timestamp_ms=now_ms,
                )
            )

    # ── SubagentStart ────────────────────────────────────────────────

    def _process_subagent_start(self, data: dict, now_ms: int, session_id: str) -> None:
        tool_use_id = data.get("tool_use_id", "")
        agent_id = data.get("agent_id") or tool_use_id or f"agent-{uuid.uuid4().hex[:6]}"
        tool_input = data.get("tool_input", {})

        # Try to match to pending spawn by tool_use_id, or FIFO for name resolution only
        pending = {}
        if tool_use_id and tool_use_id in self._pending_spawns:
            pending = self._pending_spawns.pop(tool_use_id)
        elif self._pending_spawns:
            # No tool_use_id — match oldest pending spawn (FIFO) for name/description only
            oldest_key = min(self._pending_spawns, key=lambda k: self._pending_spawns[k].get("timestamp_ms", 0))
            pending = self._pending_spawns.pop(oldest_key)

        # Parent: use pending's parent_id if it was captured with a real tool_use_id match.
        # Otherwise keep the existing parent from _ensure_agent (defaults to root).
        if tool_use_id and tool_use_id in pending.get("tool_use_id", ""):
            parent_id = pending.get("parent_id") or self._current_agent(session_id)
        elif agent_id in self.agents:
            parent_id = self.agents[agent_id].get("parent") or self._current_agent(session_id)
        else:
            parent_id = pending.get("parent_id") or self._current_agent(session_id)

        # Capture agent transcript path if available from start event
        agent_transcript_path = (
            data.get("agent_transcript_path")
            or tool_input.get("agent_transcript_path")
            or ""
        )
        if agent_transcript_path and agent_id:
            self._agent_transcript_paths[agent_id] = agent_transcript_path

        description = (
            pending.get("description")
            or tool_input.get("description")
            or data.get("agent_type")
            or "subagent"
        )
        prompt = pending.get("prompt") or tool_input.get("prompt", "")
        subagent_type = (
            pending.get("subagent_type")
            or tool_input.get("subagent_type")
            or data.get("agent_type", "")
        ) or None

        # Keep existing parent from auto-discovery (root) unless we have definitive match
        existing = self.agents.get(agent_id, {})
        has_definitive_match = bool(tool_use_id and pending.get("tool_use_id") == tool_use_id)
        if has_definitive_match:
            # We know the exact parent from the tool_use_id match
            real_parent = pending.get("parent_id") or parent_id
            old_parent = existing.get("parent")
            if old_parent and old_parent != real_parent and old_parent in self.agents:
                children = self.agents[old_parent]["children"]
                if agent_id in children:
                    children.remove(agent_id)
                self._active_children.get(old_parent, set()).discard(agent_id)
            parent_id = real_parent
        else:
            # No definitive match — keep existing parent (from auto-discovery = root)
            parent_id = existing.get("parent") or parent_id

        self.agents[agent_id] = {
            "id": agent_id, "name": description, "parent": parent_id,
            "status": "active", "subagent_type": subagent_type,
            "description": description, "prompt": str(prompt)[:2000],
            "session_id": session_id,
            "first_seen_ms": existing.get("first_seen_ms", now_ms), "last_seen_ms": now_ms,
            "tool_count": existing.get("tool_count", 0),
            "error_count": existing.get("error_count", 0),
            "children": existing.get("children", []),
            "result": None, "score": None,
            "estimated_input_chars": existing.get("estimated_input_chars", 0),
            "estimated_output_chars": existing.get("estimated_output_chars", 0),
        }

        if parent_id in self.agents:
            if agent_id not in self.agents[parent_id]["children"]:
                self.agents[parent_id]["children"].append(agent_id)
            self._active_children.setdefault(parent_id, set()).add(agent_id)

        # Only add edge if not already present
        edge_exists = any(e["from"] == parent_id and e["to"] == agent_id for e in self.edges)
        if not edge_exists:
            self.edges.append({
                "from": parent_id, "to": agent_id,
                "label": description, "prompt_preview": str(prompt)[:300],
                "timestamp_ms": now_ms,
            })

        # Don't change session_current here — it should only change when tool calls
        # actually come FROM an agent. Changing it on SubagentStart breaks parallel spawns.
        self._active_children.setdefault(agent_id, set())
        if agent_id not in self.tool_calls:
            self.tool_calls[agent_id] = []

        self.events.append({
            "id": uuid.uuid4().hex[:8],
            "hook": "SubagentStart",
            "tool_name": "Agent",
            "agent_context": parent_id,
            "agent_name": description,
            "timestamp": _ts(),
            "timestamp_ms": now_ms,
            "session_id": session_id,
            "input_preview": description,
            "output_preview": "",
            "full_input": str(prompt)[:5000],
        })

        prompt_hash = hashlib.sha256(str(prompt)[:500].encode()).hexdigest()[:16] if prompt else None
        parent_name = self.agents.get(parent_id, {}).get("name", parent_id)
        print(f"  \033[35m* spawn\033[0m [{_ts()}] {parent_name} -> \033[1m{description}\033[0m ({subagent_type})")

        # Derive session name from first agent descriptions
        if session_id in self.sessions and not self.sessions[session_id].get("name"):
            self._derive_session_name(session_id)

        if self.db:
            asyncio.get_event_loop().create_task(
                self.db.upsert_agent(
                    agent_id, session_id, subagent_type, description,
                    parent_id, "active", now_ms, now_ms, prompt_hash=prompt_hash,
                )
            )

    # ── SubagentStop ─────────────────────────────────────────────────

    def _process_subagent_stop(self, data: dict, now_ms: int, session_id: str) -> None:
        agent_id = data.get("agent_id") or data.get("tool_use_id") or self._current_agent(session_id)

        if agent_id not in self.agents:
            tool_use_id = data.get("tool_use_id")
            if tool_use_id and tool_use_id in self.agents:
                agent_id = tool_use_id
            else:
                agent_id = self._current_agent(session_id)

        # Capture agent transcript path
        agent_transcript_path = data.get("agent_transcript_path", "")
        if agent_transcript_path and agent_id:
            self._agent_transcript_paths[agent_id] = agent_transcript_path

        if agent_id in self.agents and not agent_id.startswith("root:"):
            agent = self.agents[agent_id]
            agent["status"] = "done"
            agent["last_seen_ms"] = now_ms
            result = data.get("result") or data.get("output", "")
            agent["result"] = str(result)[:2000] if result else ""

            dur = now_ms - agent["first_seen_ms"]
            print(f"  \033[32m~ done\033[0m  [{_ts()}] \033[1m{agent['name']}\033[0m ({dur}ms, {agent['tool_count']} tools)")

            # Mark parent's Agent tool call as done
            parent_id = agent.get("parent")
            if parent_id:
                tool_use_id = data.get("tool_use_id", "")
                for tc in reversed(self.tool_calls.get(parent_id, [])):
                    if tc["tool"] == "Agent" and (tc["id"] == tool_use_id or tc["status"] == "running"):
                        tc["status"] = "done"
                        tc["duration_ms"] = dur
                        tc["output_preview"] = str(result)[:300] if result else ""
                        tc["response"] = str(result)[:2000] if result else ""
                        break

            if self.db:
                asyncio.get_event_loop().create_task(
                    self.db.upsert_agent(
                        agent_id, session_id, agent.get("subagent_type"),
                        agent["name"], agent.get("parent"), "done",
                        agent["first_seen_ms"], now_ms,
                        agent["tool_count"], agent.get("error_count", 0),
                    )
                )
                # Recompute baseline for this agent type
                st = agent.get("subagent_type")
                if st:
                    asyncio.get_event_loop().create_task(
                        self._recompute_and_cache_baseline(st)
                    )

        parent_id = self.agents.get(agent_id, {}).get("parent")
        if parent_id and parent_id in self._active_children:
            self._active_children[parent_id].discard(agent_id)
            if not self._active_children[parent_id]:
                self._session_current[session_id] = parent_id

        self.events.append({
            "id": uuid.uuid4().hex[:8],
            "hook": "SubagentStop",
            "tool_name": "Agent",
            "agent_context": self._current_agent(session_id),
            "agent_name": self.agents.get(agent_id, {}).get("name", ""),
            "timestamp": _ts(),
            "timestamp_ms": now_ms,
            "session_id": session_id,
            "input_preview": "",
            "output_preview": self.agents.get(agent_id, {}).get("result", "")[:300],
            "full_output": str(self.agents.get(agent_id, {}).get("result", ""))[:5000],
        })

    # ── Stop (session end) ───────────────────────────────────────────

    def _process_stop(self, data: dict, now_ms: int, session_id: str) -> None:
        # Mark session as complete
        if session_id in self.sessions:
            self.sessions[session_id]["status"] = "complete"
        # Mark session root as done
        root_id = self._root_id(session_id)
        if root_id in self.agents:
            self.agents[root_id]["status"] = "done"
            self.agents[root_id]["last_seen_ms"] = now_ms

        agent_count = sum(
            1 for a in self.agents.values()
            if a.get("session_id") == session_id and not a["id"].startswith("root:")
        )
        if self.db and session_id in self._known_sessions:
            asyncio.get_event_loop().create_task(
                self.db.complete_session(session_id, now_ms)
            )
            asyncio.get_event_loop().create_task(
                self.db.upsert_session(session_id, now_ms, agent_count=agent_count, status="complete", end_time_ms=now_ms)
            )
        print(f"  \033[36m# session end\033[0m [{_ts()}] {session_id[:12]}")
