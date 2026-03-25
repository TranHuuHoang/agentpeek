# AgentPeek

Real-time observability for Claude Code agent teams. See what your agents are doing, how much they cost, and whether they're stuck.

## Prerequisites

- **Claude Code** installed and running
- **Python 3.10+**
- **jq** — the hooks use it to write events (`brew install jq` on macOS, `apt install jq` on Linux)
- **Node.js 18+** (only needed for frontend development)

## Quick start

```bash
# Clone and install
git clone https://github.com/TranHuuHoang/agentpeek.git
cd agentpeek
pip install -e .

# Start (installs hooks into ~/.claude/settings.json, starts dashboard, opens browser)
agentpeek
```

That's it. Open Claude Code in another terminal and start working — agents will appear in the dashboard at `http://localhost:8099`.

## How it works

AgentPeek installs async hooks into `~/.claude/settings.json`. When Claude Code runs tools or spawns sub-agents, the hooks append JSON events to `/tmp/agentpeek.jsonl` via `jq`. The AgentPeek server tails this file, builds agent state in memory, persists to SQLite for cross-session baselines, and serves a React dashboard.

```
Claude Code hooks → jq → /tmp/agentpeek.jsonl
                              ↓
                      AgentPeek server (tail file)
                              ↓
              ┌───────────────┼───────────────┐
              │                               │
       In-memory state                  SQLite persistence
       (live topology)                  (~/.agentpeek/history.db)
              │                               │
              └───────→ Scorer ←──────────────┘
                            ↓
                     Dashboard at :8099
```

No proxy. No API interception. All hooks are async (non-blocking) — they won't slow down Claude Code.

## CLI options

```bash
agentpeek                  # Start server + install hooks + open browser
agentpeek --no-browser     # Start without opening browser
agentpeek --port 9000      # Custom port
agentpeek --install-hooks  # Just install hooks and exit
agentpeek --uninstall      # Remove hooks from settings.json
```

## The three questions AgentPeek answers

### "Where did my tokens go?"
Per-agent cost attribution using Sonnet 4 pricing ($3/MTok input, $15/MTok output). Estimates tokens from tool payload sizes (chars / 4). Each agent shows its estimated cost and percentage of session total.

### "Is my agent stuck?"
Real-time loop detection scans the last 10 tool calls per agent for:
- **Repeated tool** — same tool + input called 3+ times (e.g., reading a non-existent file in a loop)
- **Failure loop** — 3+ consecutive errors on the same tool

Stuck agents get amber borders in topology and alert cards at the top of insights.

### "What actually happened?"
Session replay tab shows every event chronologically. Click any event to expand the full tool input and output. Filter by agent name or tool.

## Dashboard views

### Topology
Left-to-right directed graph. Root agent on the left, spawned agents to the right. Arrows show spawn direction. Each node shows agent name, type, estimated cost, duration, and error count.

### Timeline
Horizontal Gantt bars showing when each agent ran. Indentation shows parent-child hierarchy. Parallel agents overlap visually. Works for sessions from seconds to hours (auto-scales time axis).

### Insights
1. **Is my agent stuck?** — amber alert cards for looping agents (only when detected)
2. **Where did my tokens go?** — stacked cost breakdown bar + per-agent legend
3. **What should I do?** — bottleneck identification, error analysis, parallelism opportunities
4. **Agent Performance** — table with duration, token %, estimated cost, errors
5. **Agent Type Profiles** — cross-session baselines in plain English ("Usually makes 3-5 tool calls, takes 2-4s")

### Replay
Chronological event stream for a session. Color-coded by event type (spawn/call/result/error). Click to expand full tool I/O. Filter by agent or tool name.

## Session management

- **Session tabs** auto-named from the first agent's description (e.g., "webapp: Explore component structure")
- **Dismiss** tabs by hovering and clicking X
- **Restore** dismissed sessions from the clock icon history popover (top-right)
- **Auto-selects** the most recent active session on page load

## Development

```bash
# Install backend in dev mode
pip install -e .

# Install frontend dependencies
cd frontend && npm install

# Run backend
agentpeek --no-browser

# Run frontend dev server (hot reload, proxies API to :8099)
cd frontend && npm run dev

# Build frontend for production (outputs to src/agentpeek/static/)
cd frontend && npm run build
```

## Tech stack

- **Backend**: Python — Starlette, uvicorn, aiosqlite, Pydantic, Click
- **Frontend**: React, TypeScript, Tailwind CSS v4, React Flow, dagre
- **Persistence**: SQLite (WAL mode) at `~/.agentpeek/history.db`
- **Communication**: SSE (Server-Sent Events) with polling fallback

## Cost estimation note

Token costs are estimates based on tool payload character counts (chars / 4 ≈ tokens), priced at Claude Sonnet 4 rates. These represent only the tool I/O portion — actual API costs include conversation context, system prompts, and model reasoning which hooks cannot capture. Use the estimates for relative comparison between agents, not as billing predictions.

## License

MIT
