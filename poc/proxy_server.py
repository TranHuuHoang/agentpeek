"""
AgentPeek Proxy PoC — Intercepts all LLM traffic, tracks agent hierarchy.
Serves a live HTML dashboard at http://localhost:8099/_agentpeek/
"""

import asyncio
import json
import os
import random
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import StreamingResponse, JSONResponse, Response, HTMLResponse
from starlette.routing import Route

MOCK_MODE = os.environ.get("AGENTPEEK_MOCK", "auto")

# ── State ─────────────────────────────────────────────────────────────
events: list[dict] = []
agents: dict[str, dict] = {}  # agent_name -> {parent, model, status, first_seen, last_seen, calls, tokens_in, tokens_out}
edges: list[dict] = []  # {from_agent, to_agent, content_preview, timestamp_ms}

TARGET_HOSTS = {
    "anthropic": "https://api.anthropic.com",
    "openai": "https://api.openai.com",
}


def register_agent(name: str, parent: str | None, model: str) -> None:
    if name not in agents:
        agents[name] = {
            "name": name,
            "parent": parent,
            "model": model,
            "status": "active",
            "first_seen_ms": int(time.time() * 1000),
            "last_seen_ms": int(time.time() * 1000),
            "calls": 0,
            "tokens_in": 0,
            "tokens_out": 0,
        }
    agents[name]["last_seen_ms"] = int(time.time() * 1000)
    agents[name]["status"] = "active"


def register_edge(from_agent: str, to_agent: str, content: str) -> None:
    edges.append({
        "from": from_agent,
        "to": to_agent,
        "content_preview": content[:300],
        "timestamp_ms": int(time.time() * 1000),
    })


def make_mock_response(agent_name: str, model: str, messages: list) -> dict:
    # Import mock data
    from mock_data import get_mock_response
    text = get_mock_response(agent_name)
    input_text = json.dumps(messages)
    return {
        "id": f"msg_{uuid.uuid4().hex[:16]}",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [{"type": "text", "text": text}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {
            "input_tokens": len(input_text) // 4,
            "output_tokens": len(text) // 4,
        },
    }


async def proxy_handler(request: Request) -> Response:
    path = request.url.path
    headers = dict(request.headers)
    body = await request.body()

    agent_name = headers.get("x-agent-name", "unknown")
    agent_parent = headers.get("x-agent-parent")
    agent_session = headers.get("x-agent-session", "default")

    try:
        body_json = json.loads(body) if body else {}
    except json.JSONDecodeError:
        body_json = {}

    model = body_json.get("model", "unknown")
    messages = body_json.get("messages", [])
    is_streaming = body_json.get("stream", False)

    # Register agent + hierarchy
    register_agent(agent_name, agent_parent, model)
    if agent_parent and agent_parent in agents:
        # Edge: parent delegated to this agent
        last_msg = messages[-1]["content"] if messages else ""
        if isinstance(last_msg, list):
            last_msg = str(last_msg)
        register_edge(agent_parent, agent_name, last_msg[:200])

    # Capture request
    request_event = {
        "id": uuid.uuid4().hex[:8],
        "direction": "request",
        "timestamp": datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3],
        "timestamp_ms": int(time.time() * 1000),
        "agent_name": agent_name,
        "agent_parent": agent_parent,
        "session": agent_session,
        "model": model,
        "path": path,
        "input_tokens": len(json.dumps(messages)) // 4,
        "messages_preview": [
            {"role": m.get("role"), "content": (m.get("content", "") if isinstance(m.get("content", ""), str) else str(m.get("content", "")))[:300]}
            for m in messages[-3:]
        ],
    }
    events.append(request_event)
    agents[agent_name]["calls"] += 1

    ts = request_event["timestamp"]
    print(f"  \033[32m>>>\033[0m [{ts}] {agent_name} -> LLM ({model})")

    # Mock or forward
    has_real_key = bool(headers.get("x-api-key", "").startswith("sk-ant-"))
    use_mock = (MOCK_MODE == "always") or (MOCK_MODE == "auto" and not has_real_key)

    start_time = time.time()

    if use_mock:
        latency = random.uniform(0.3, 1.5)
        await asyncio.sleep(latency)
        elapsed = int((time.time() - start_time) * 1000)

        mock_resp = make_mock_response(agent_name, model, messages)
        usage = mock_resp["usage"]
        resp_text = mock_resp["content"][0]["text"]

        response_event = {
            "id": uuid.uuid4().hex[:8],
            "direction": "response",
            "timestamp": datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3],
            "timestamp_ms": int(time.time() * 1000),
            "agent_name": agent_name,
            "agent_parent": agent_parent,
            "session": agent_session,
            "model": model,
            "status": 200,
            "latency_ms": elapsed,
            "input_tokens": usage["input_tokens"],
            "output_tokens": usage["output_tokens"],
            "response_preview": resp_text[:500],
        }
        events.append(response_event)
        agents[agent_name]["tokens_in"] += usage["input_tokens"]
        agents[agent_name]["tokens_out"] += usage["output_tokens"]
        agents[agent_name]["status"] = "done"

        print(f"  \033[34m<<<\033[0m [{response_event['timestamp']}] {agent_name} <- LLM ({elapsed}ms, {usage['output_tokens']} tokens)")

        return Response(
            content=json.dumps(mock_resp).encode(),
            status_code=200,
            headers={"content-type": "application/json"},
        )

    # Real forward (same as before)
    forward_headers = {
        k: v for k, v in headers.items()
        if k.lower() not in ("host", "content-length", "transfer-encoding", "x-agent-name", "x-agent-parent", "x-agent-session")
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.request(request.method, f"{TARGET_HOSTS.get('anthropic', '')}{path}", headers=forward_headers, content=body)
        elapsed = int((time.time() - start_time) * 1000)

        try:
            resp_json = resp.json()
            usage = resp_json.get("usage", {})
            in_t = usage.get("input_tokens", 0)
            out_t = usage.get("output_tokens", 0)
            content_blocks = resp_json.get("content", [])
            resp_text = content_blocks[0].get("text", "")[:500] if content_blocks else resp.text[:500]
        except Exception:
            in_t, out_t, resp_text = 0, 0, resp.text[:500]

        response_event = {
            "id": uuid.uuid4().hex[:8],
            "direction": "response",
            "timestamp": datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3],
            "timestamp_ms": int(time.time() * 1000),
            "agent_name": agent_name,
            "model": model,
            "status": resp.status_code,
            "latency_ms": elapsed,
            "input_tokens": in_t,
            "output_tokens": out_t,
            "response_preview": resp_text,
        }
        events.append(response_event)
        agents[agent_name]["tokens_in"] += in_t
        agents[agent_name]["tokens_out"] += out_t
        agents[agent_name]["status"] = "done"

        return Response(content=resp.content, status_code=resp.status_code, headers=dict(resp.headers))


# ── API endpoints ─────────────────────────────────────────────────────

async def api_state(request: Request) -> JSONResponse:
    return JSONResponse({
        "agents": agents,
        "edges": edges,
        "events": events[-100:],
        "summary": {
            "total_agents": len(agents),
            "total_calls": sum(a["calls"] for a in agents.values()),
            "total_tokens_in": sum(a["tokens_in"] for a in agents.values()),
            "total_tokens_out": sum(a["tokens_out"] for a in agents.values()),
        },
    })


async def api_reset(request: Request) -> JSONResponse:
    events.clear()
    agents.clear()
    edges.clear()
    return JSONResponse({"status": "reset"})


async def serve_dashboard(request: Request) -> HTMLResponse:
    html_path = Path(__file__).parent / "dashboard.html"
    return HTMLResponse(html_path.read_text())


async def catch_all(request: Request) -> Response:
    if request.url.path.startswith("/_agentpeek"):
        if "state" in request.url.path:
            return await api_state(request)
        if "reset" in request.url.path:
            return await api_reset(request)
        return await serve_dashboard(request)
    return await proxy_handler(request)


app = Starlette(routes=[
    Route("/_agentpeek", serve_dashboard, methods=["GET"]),
    Route("/_agentpeek/", serve_dashboard, methods=["GET"]),
    Route("/_agentpeek/state", api_state, methods=["GET"]),
    Route("/_agentpeek/reset", api_reset, methods=["POST", "GET"]),
    Route("/{path:path}", catch_all, methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]),
])

if __name__ == "__main__":
    print("""
\033[1m╔══════════════════════════════════════════════════════════════╗
║  AgentPeek Proxy                                             ║
║  Dashboard:  http://localhost:8099/_agentpeek                ║
║  API State:  http://localhost:8099/_agentpeek/state           ║
╚══════════════════════════════════════════════════════════════╝\033[0m
""")
    uvicorn.run(app, host="0.0.0.0", port=8099, log_level="warning")
