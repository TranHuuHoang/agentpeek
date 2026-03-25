"""
AgentPeek Server — Tails /tmp/agentpeek.jsonl for hook events.

Hooks write JSON lines to a file (zero overhead).
Server tails the file and builds the agent tree.
Dashboard at http://localhost:8099
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, HTMLResponse
from starlette.routing import Route

EVENTS_FILE = "/tmp/agentpeek.jsonl"

# ── State ─────────────────────────────────────────────────────────────
events: list[dict] = []
agents: dict[str, dict] = {}
edges: list[dict] = []

# Pending Agent tool calls: tool_use_id -> {description, prompt, parent_agent, ...}
# Keyed by tool_use_id so parallel spawns don't overwrite each other.
pending_agent_spawns: dict[str, dict] = {}

# Map agent_id -> set of active child agent_ids (for parallel tracking)
active_children: dict[str, set] = {"root": set()}

# Map session_id -> current "leaf" agent (for tool call attribution)
# This is best-effort for parallel agents — tool calls without agent context
# get attributed to the most recently active agent in the session
session_current: dict[str, str] = {}

# Tool calls per agent
tool_calls: dict[str, list[dict]] = {"root": []}


def init_root():
    agents["root"] = {
        "id": "root", "name": "Claude Code", "parent": None,
        "status": "active", "subagent_type": None, "description": "Main session",
        "first_seen_ms": int(time.time() * 1000), "last_seen_ms": int(time.time() * 1000),
        "tool_count": 0, "children": [], "prompt": None, "result": None,
    }

init_root()


def ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]


def current_agent(session_id: str) -> str:
    return session_current.get(session_id, "root")


def ensure_agent(agent_id: str, agent_type: str, now_ms: int) -> None:
    """Auto-discover agents from agent_id on tool events (SubagentStart may not fire)."""
    if agent_id and agent_id not in agents:
        label = agent_type or agent_id[:12]
        agents[agent_id] = {
            "id": agent_id,
            "name": label,
            "parent": "root",
            "status": "active",
            "subagent_type": agent_type,
            "description": label,
            "prompt": None,
            "first_seen_ms": now_ms,
            "last_seen_ms": now_ms,
            "tool_count": 0,
            "children": [],
            "result": None,
        }
        agents["root"]["children"].append(agent_id)
        active_children.setdefault("root", set()).add(agent_id)
        active_children[agent_id] = set()
        tool_calls[agent_id] = []
        edges.append({
            "from": "root", "to": agent_id,
            "label": label, "prompt_preview": "",
            "timestamp_ms": now_ms,
        })
        print(f"  \033[36m⊕ AUTO-DISCOVERED\033[0m [{ts()}] {label} ({agent_id[:12]})")


# ── Event processors ──────────────────────────────────────────────────

def process_event(data: dict) -> None:
    hook = data.get("hook", "")
    now_ms = int(time.time() * 1000)
    session_id = data.get("session_id", "default")

    # Auto-discover agents from agent_id field on any event
    agent_id = data.get("agent_id", "")
    agent_type = data.get("agent_type", "")
    if agent_id:
        ensure_agent(agent_id, agent_type, now_ms)

    if hook == "PreToolUse":
        process_pre_tool(data, now_ms, session_id)
    elif hook == "PostToolUse":
        process_post_tool(data, now_ms, session_id)
    elif hook == "SubagentStart":
        process_subagent_start(data, now_ms, session_id)
    elif hook == "SubagentStop":
        process_subagent_stop(data, now_ms, session_id)


def process_pre_tool(data: dict, now_ms: int, session_id: str) -> None:
    tool_name = data.get("tool_name", "unknown")
    tool_input = data.get("tool_input", {})
    tool_use_id = data.get("tool_use_id", "")

    if tool_name == "Agent":
        # Stash by tool_use_id — parallel spawns get separate entries
        # Parent is whoever is current RIGHT NOW (before the agent starts)
        parent_id = data.get("agent_id") or current_agent(session_id)
        pending_agent_spawns[tool_use_id] = {
            "description": tool_input.get("description", ""),
            "prompt": tool_input.get("prompt", ""),
            "subagent_type": tool_input.get("subagent_type", ""),
            "parent_id": parent_id,
            "tool_use_id": tool_use_id,
            "timestamp_ms": now_ms,
        }
        return

    # Use agent_id from event data if available, fall back to session tracking
    ctx = data.get("agent_id") or current_agent(session_id)
    if ctx in agents:
        agents[ctx]["tool_count"] += 1
        agents[ctx]["last_seen_ms"] = now_ms

    tc = {
        "id": tool_use_id,
        "tool": tool_name,
        "input": tool_input,
        "input_preview": _tool_preview(tool_name, tool_input),
        "timestamp_ms": now_ms,
        "status": "running",
        "output_preview": None,
        "response": None,
    }
    tool_calls.setdefault(ctx, []).append(tc)

    events.append({
        "id": uuid.uuid4().hex[:8],
        "hook": "PreToolUse",
        "tool_name": tool_name,
        "agent_context": ctx,
        "agent_name": agents.get(ctx, {}).get("name", ctx),
        "timestamp": ts(),
        "timestamp_ms": now_ms,
        "session_id": session_id,
        "input_preview": tc["input_preview"],
    })

    name = agents.get(ctx, {}).get("name", ctx)[:25]
    print(f"  \033[33m▸ {tool_name:12s}\033[0m [{ts()}] {name}: {tc['input_preview'][:60]}")


def process_post_tool(data: dict, now_ms: int, session_id: str) -> None:
    tool_name = data.get("tool_name", "unknown")
    tool_input = data.get("tool_input", {})
    tool_response = data.get("tool_response", "")
    tool_use_id = data.get("tool_use_id", "")

    if tool_name == "Agent":
        return

    # Use agent_id from event data if available
    ctx = data.get("agent_id") or current_agent(session_id)
    resp_str = str(tool_response)[:2000] if tool_response else ""

    # Match by tool_use_id first, then by tool name
    calls = tool_calls.get(ctx, [])
    matched = False
    for tc in reversed(calls):
        if tc["id"] == tool_use_id or (tc["tool"] == tool_name and tc["status"] == "running"):
            tc["status"] = "done"
            tc["output_preview"] = resp_str[:300]
            tc["response"] = resp_str
            tc["duration_ms"] = now_ms - tc["timestamp_ms"]
            matched = True
            break

    events.append({
        "id": uuid.uuid4().hex[:8],
        "hook": "PostToolUse",
        "tool_name": tool_name,
        "agent_context": ctx,
        "agent_name": agents.get(ctx, {}).get("name", ctx),
        "timestamp": ts(),
        "timestamp_ms": now_ms,
        "session_id": session_id,
        "output_preview": resp_str[:300],
    })


def process_subagent_start(data: dict, now_ms: int, session_id: str) -> None:
    tool_use_id = data.get("tool_use_id", "")
    agent_id = data.get("agent_id") or tool_use_id or f"agent-{uuid.uuid4().hex[:6]}"
    tool_input = data.get("tool_input", {})

    # Look up stashed info from PreToolUse via tool_use_id (handles parallel)
    pending = pending_agent_spawns.pop(tool_use_id, {})

    # Parent comes from the stash (captured at PreToolUse time, before stack changed)
    parent_id = pending.get("parent_id") or current_agent(session_id)

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
    )

    agents[agent_id] = {
        "id": agent_id,
        "name": description,
        "parent": parent_id,
        "status": "active",
        "subagent_type": subagent_type,
        "description": description,
        "prompt": str(prompt)[:2000],
        "first_seen_ms": now_ms,
        "last_seen_ms": now_ms,
        "tool_count": 0,
        "children": [],
        "result": None,
    }

    if parent_id in agents:
        agents[parent_id]["children"].append(agent_id)
        active_children.setdefault(parent_id, set()).add(agent_id)

    edges.append({
        "from": parent_id, "to": agent_id,
        "label": description, "prompt_preview": str(prompt)[:300],
        "timestamp_ms": now_ms,
    })

    # Track this as the most recently started agent for tool attribution
    session_current[session_id] = agent_id
    active_children[agent_id] = set()
    tool_calls[agent_id] = []

    events.append({
        "id": uuid.uuid4().hex[:8],
        "hook": "SubagentStart",
        "tool_name": "Agent",
        "agent_id": agent_id,
        "agent_context": parent_id,
        "agent_name": description,
        "timestamp": ts(),
        "timestamp_ms": now_ms,
        "session_id": session_id,
        "input_preview": description,
    })

    parent_name = agents.get(parent_id, {}).get("name", parent_id)
    print(f"  \033[35m● SPAWN\033[0m [{ts()}] {parent_name} → \033[1m{description}\033[0m ({subagent_type})")


def process_subagent_stop(data: dict, now_ms: int, session_id: str) -> None:
    agent_id = data.get("agent_id") or data.get("tool_use_id") or current_agent(session_id)

    if agent_id not in agents:
        # Try tool_use_id match
        tool_use_id = data.get("tool_use_id")
        if tool_use_id and tool_use_id in agents:
            agent_id = tool_use_id
        else:
            agent_id = current_agent(session_id)

    if agent_id in agents and agent_id != "root":
        agents[agent_id]["status"] = "done"
        agents[agent_id]["last_seen_ms"] = now_ms
        result = data.get("result") or data.get("output", "")
        agents[agent_id]["result"] = str(result)[:2000] if result else ""

        dur = now_ms - agents[agent_id]["first_seen_ms"]
        name = agents[agent_id]["name"]
        tools = agents[agent_id]["tool_count"]
        print(f"  \033[32m✓ DONE\033[0m  [{ts()}] \033[1m{name}\033[0m ({dur}ms, {tools} tools)")

    # Remove from parent's active children
    parent_id = agents.get(agent_id, {}).get("parent")
    if parent_id and parent_id in active_children:
        active_children[parent_id].discard(agent_id)
        # If all children done, set current back to parent
        if not active_children[parent_id]:
            session_current[session_id] = parent_id

    events.append({
        "id": uuid.uuid4().hex[:8],
        "hook": "SubagentStop",
        "tool_name": "Agent",
        "agent_id": agent_id,
        "agent_context": current_agent(session_id),
        "agent_name": agents.get(agent_id, {}).get("name", ""),
        "timestamp": ts(),
        "timestamp_ms": now_ms,
        "session_id": session_id,
        "output_preview": agents.get(agent_id, {}).get("result", "")[:300],
    })


def _tool_preview(tool_name: str, tool_input: dict) -> str:
    """Compact one-liner preview of a tool call."""
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


# ── File tailer ───────────────────────────────────────────────────────

async def tail_events_file():
    Path(EVENTS_FILE).touch()
    with open(EVENTS_FILE, "r") as f:
        f.seek(0, 2)
        print(f"  Tailing {EVENTS_FILE} ...")
        while True:
            line = f.readline()
            if line:
                line = line.strip()
                if line:
                    try:
                        process_event(json.loads(line))
                    except json.JSONDecodeError as e:
                        print(f"  \033[31mBAD JSON:\033[0m {line[:80]} — {e}")
            else:
                await asyncio.sleep(0.1)


# ── HTTP Endpoints ────────────────────────────────────────────────────

async def api_state(request: Request) -> JSONResponse:
    return JSONResponse({
        "agents": agents,
        "edges": edges,
        "events": events[-200:],
        "tool_calls": {k: v[-30:] for k, v in tool_calls.items()},
        "summary": {
            "total_agents": len(agents),
            "active_agents": sum(1 for a in agents.values() if a["status"] == "active"),
            "total_events": len(events),
            "total_tool_calls": sum(len(v) for v in tool_calls.values()),
        },
    })


async def api_reset(request: Request) -> JSONResponse:
    events.clear(); agents.clear(); edges.clear()
    pending_agent_spawns.clear(); active_children.clear()
    session_current.clear()
    tool_calls.clear(); tool_calls["root"] = []
    active_children["root"] = set()
    init_root()
    open(EVENTS_FILE, "w").close()
    return JSONResponse({"status": "reset"})


async def serve_dashboard(request: Request) -> HTMLResponse:
    return HTMLResponse((Path(__file__).parent / "dashboard.html").read_text())


async def http_hook(request: Request) -> JSONResponse:
    """Fallback HTTP hook endpoint for sessions using old config."""
    try:
        body = await request.body()
        data = json.loads(body) if body else {}
        path = request.url.path
        if "subagent-start" in path:
            data["hook"] = "SubagentStart"
        elif "subagent-stop" in path:
            data["hook"] = "SubagentStop"
        elif "/pre" in path:
            data["hook"] = "PreToolUse"
        elif "/post" in path:
            data["hook"] = "PostToolUse"
        process_event(data)
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


app = Starlette(routes=[
    Route("/", serve_dashboard, methods=["GET"]),
    Route("/hook/subagent-start", http_hook, methods=["POST"]),
    Route("/hook/subagent-stop", http_hook, methods=["POST"]),
    Route("/hook/pre", http_hook, methods=["POST"]),
    Route("/hook/post", http_hook, methods=["POST"]),
    Route("/state", api_state, methods=["GET"]),
    Route("/reset", api_reset, methods=["POST", "GET"]),
])


async def startup():
    asyncio.create_task(tail_events_file())

app.add_event_handler("startup", startup)


if __name__ == "__main__":
    print("""
\033[1m╔══════════════════════════════════════════════════════════════╗
║  AgentPeek — Claude Code Agent Observer                      ║
║                                                              ║
║  Dashboard:  http://localhost:8099                            ║
║  Events:     /tmp/agentpeek.jsonl (file-tailed)              ║
║  State API:  GET http://localhost:8099/state                  ║
╚══════════════════════════════════════════════════════════════╝\033[0m

Waiting for hook events...
""")
    uvicorn.run(app, host="0.0.0.0", port=8099, log_level="warning")
