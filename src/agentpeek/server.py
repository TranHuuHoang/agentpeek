"""Starlette app — serves API, SSE, and static frontend."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, HTMLResponse, Response, StreamingResponse
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles

from agentpeek.db import Database
from agentpeek.processor import EventProcessor
from agentpeek.tailer import tail_jsonl, EVENTS_FILE

# Shared state — initialized in create_app()
processor: EventProcessor
db: Database


async def api_state(request: Request) -> JSONResponse:
    session_filter = request.query_params.get("session", None)
    return JSONResponse(processor.get_state(session_filter))


async def api_reset(request: Request) -> JSONResponse:
    processor.reset()
    open(EVENTS_FILE, "w").close()
    return JSONResponse({"status": "reset"})


async def api_events_stream(request: Request) -> Response:
    """SSE endpoint — pushes state on every event."""
    session_filter = request.query_params.get("session", None)
    queue = processor.subscribe()

    async def event_generator():
        try:
            # Send initial state
            yield f"data: {json.dumps(processor.get_state(session_filter))}\n\n"
            while True:
                try:
                    await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(processor.get_state(session_filter))}\n\n"
                except asyncio.TimeoutError:
                    # Keepalive
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            processor.unsubscribe(queue)

    return StreamingResponse(
        content=event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def api_history(request: Request) -> JSONResponse:
    limit = int(request.query_params.get("limit", "50"))
    offset = int(request.query_params.get("offset", "0"))
    sessions = await db.list_sessions(limit, offset)
    return JSONResponse(sessions)


async def api_baselines(request: Request) -> JSONResponse:
    baselines = await db.get_all_baselines()
    return JSONResponse(baselines)


async def api_trends(request: Request) -> JSONResponse:
    subagent_type = request.path_params["subagent_type"]
    limit = int(request.query_params.get("limit", "20"))
    scores = await db.get_agent_scores_by_type(subagent_type, limit)
    return JSONResponse(scores)


async def api_session_detail(request: Request) -> JSONResponse:
    session_id = request.path_params["session_id"]
    agents = await db.get_session_agents(session_id)
    return JSONResponse({"agents": agents})


async def api_session_replay(request: Request) -> JSONResponse:
    session_id = request.path_params["session_id"]
    events = [e for e in processor.events if e.get("session_id") == session_id]
    events.sort(key=lambda e: e.get("timestamp_ms", 0))
    return JSONResponse({
        "session_id": session_id,
        "events": events,
        "event_count": len(events),
    })


async def fallback(request: Request) -> HTMLResponse:
    """Serve index.html for SPA routing."""
    static_dir = Path(__file__).parent / "static"
    index = static_dir / "index.html"
    if index.exists():
        return HTMLResponse(index.read_text())
    return HTMLResponse(
        "<html><body><h2>AgentPeek</h2>"
        "<p>Frontend not built. Run <code>cd frontend && npm run build</code></p>"
        "<p>API available at <a href='/api/state'>/api/state</a></p>"
        "</body></html>"
    )


def create_app() -> Starlette:
    global processor, db

    db = Database()
    processor = EventProcessor(db=db)

    routes = [
        Route("/api/state", api_state, methods=["GET"]),
        Route("/api/reset", api_reset, methods=["POST", "GET"]),
        Route("/api/events/stream", api_events_stream, methods=["GET"]),
        Route("/api/history", api_history, methods=["GET"]),
        Route("/api/baselines", api_baselines, methods=["GET"]),
        Route("/api/trends/{subagent_type:path}", api_trends, methods=["GET"]),
        Route("/api/session/{session_id}", api_session_detail, methods=["GET"]),
        Route("/api/session/{session_id}/replay", api_session_replay, methods=["GET"]),
    ]

    # Serve built frontend if available
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists() and (static_dir / "index.html").exists():
        routes.append(Mount("/assets", app=StaticFiles(directory=static_dir / "assets"), name="assets"))

    # SPA fallback
    routes.append(Route("/{path:path}", fallback, methods=["GET"]))

    @asynccontextmanager
    async def lifespan(app):
        await db.connect()
        await processor.load_baselines()
        asyncio.create_task(tail_jsonl(processor.process_event))
        print(f"""
\033[1m╔══════════════════════════════════════════════════════════════╗
║  AgentPeek — Agent Observer                                  ║
║                                                              ║
║  Dashboard:  http://localhost:8099                            ║
║  Events:     {EVENTS_FILE:<44s} ║
║  API:        http://localhost:8099/api/state                  ║
╚══════════════════════════════════════════════════════════════╝\033[0m
""")
        yield
        await db.close()

    app = Starlette(routes=routes, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app


app = create_app()
