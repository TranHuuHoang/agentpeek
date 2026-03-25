# AgentPeek

Real-time observability for Claude Code agent teams. See what your agents are doing, how much they cost, and whether they're stuck.

```
pip install agentpeek
agentpeek
```

One command. Auto-installs hooks, starts the dashboard on `:8099`, opens your browser.

## What it does

AgentPeek hooks into Claude Code's event system and gives you a live dashboard showing:

- **Topology** — Left-to-right agent graph showing who spawned who, with cost estimates and error badges
- **Timeline** — Gantt chart of agent execution (parallel vs sequential, durations, errors)
- **Insights** — Actionable intelligence: cost breakdown, stuck agent detection, bottleneck analysis
- **Replay** — Chronological event log with full tool inputs/outputs for debugging

## The three questions AgentPeek answers

### "Where did my tokens go?"
Per-agent cost attribution using Sonnet 4 pricing ($3/MTok input, $15/MTok output). Stacked bar shows which agent consumed the most tokens.

### "Is my agent stuck?"
Real-time loop detection scans the last 10 tool calls per agent for:
- **Repeated tool** — same tool+input called 3+ times
- **Failure loop** — 3+ consecutive errors on the same tool

Stuck agents get amber borders in topology and alert cards in insights.

### "What actually happened?"
Session replay with full tool I/O. Click any event to expand the complete input and output. Filter by agent or tool name.

## Architecture

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

No proxy. No API interception. Just hooks writing JSONL, a Python server tailing the file, and a React dashboard.

## Usage

```bash
# Start (installs hooks, opens browser)
agentpeek

# Start without opening browser
agentpeek --no-browser

# Custom port
agentpeek --port 9000

# Remove hooks
agentpeek --uninstall
```

## Dashboard views

### Topology
Left-to-right directed graph. Root agent on the left, spawned agents to the right. Each node shows agent name, type, estimated cost, duration, and error count.

### Timeline
Horizontal bars showing when each agent ran. Indentation shows parent-child hierarchy. Parallel agents overlap visually. Works for sessions from seconds to hours.

### Insights
1. **Is my agent stuck?** — amber alerts for looping agents
2. **Where did my tokens go?** — stacked cost bar + per-agent breakdown
3. **What should I do?** — bottleneck identification, error analysis, parallelism opportunities
4. **Agent Performance** — table with duration, token %, cost, errors
5. **Agent Type Profiles** — cross-session baselines in plain English

### Replay
Chronological event stream. Color-coded by event type. Click to expand full tool input/output. Filter by agent or tool.

## Development

```bash
# Backend
pip install -e .

# Frontend
cd frontend && npm install && npm run dev

# Build for production
cd frontend && npm run build
```

## Tech stack

- **Backend**: Python (Starlette, uvicorn, aiosqlite, Pydantic, Click)
- **Frontend**: React, TypeScript, Tailwind CSS, React Flow, dagre
- **Persistence**: SQLite with WAL mode
- **Communication**: SSE with polling fallback

## License

MIT
