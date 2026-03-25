# AgentPeek

**"Peek into your agents."** Real-time observability dashboard for Claude Code agent sessions.

## What It Is

A live diagnostic tool that visualizes Claude Code's multi-agent activity as it happens — topology graph, timeline, event feed, and detail inspector. Think Chrome DevTools for AI agent systems.

## How It Works

```
Claude Code hooks → jq → /tmp/agentpeek.jsonl
                              ↓
                    AgentPeek server (tail file)
                              ↓
                    React dashboard at :8099
```

1. Hooks on PreToolUse/PostToolUse fire on every tool call, appending JSON lines via jq
2. Server tails the file, auto-discovers agents from `agent_id`, builds state in memory
3. Dashboard polls server and renders live views

All hooks run `async: true` — zero impact on Claude Code performance. File appends handle any number of parallel agents.

## Dashboard Views

1. **Topology** — directed graph: Claude Code → spawned agents, edges show relationships
2. **Gantt** — timeline bars showing when each agent was active, who overlaps
3. **Agent Hierarchy** — tree list with status, tool count, duration
4. **Event Feed** — chronological stream of every tool call with input/output previews
5. **Detail Panel** — click any agent or event for full payload inspection

## Distribution

`pip install agentpeek` — one command:
- Starts server on `:8099`
- Writes hooks to `~/.claude/settings.json`
- Opens dashboard in browser

## Tech Stack

- **Server:** Python, Starlette, uvicorn
- **Frontend:** React, TypeScript, Vite, Tailwind, React Flow (topology + layout)
- **Data:** JSONL file as event bus, in-memory state on server

## UI Design

- **Style:** Modern dark — Inter + JetBrains Mono, rounded corners, glass cards, soft accents
- **Palette:** #09090B bg, #4ADE80 green, #60A5FA blue, #A78BFA purple, #FBBF24 amber, #F87171 red
- **Active nodes pulse green, waiting = blue, errors = red, done = gray**

## v1 Scope

**In:**
- Observe Claude Code sessions (any number of parallel agents)
- Real-time topology, gantt, hierarchy, event feed, detail panel
- Cross-session visibility via global hooks
- One-command install and setup
- Per-agent tool count and duration tracking
- Click-to-inspect full tool inputs/outputs

**Out:**
- Modifying or controlling agent behavior
- Persistent storage / session history (in-memory only)
- Non-Claude-Code agent frameworks
- Authentication / multi-user
- Cost/token tracking (no token data in hook payloads)
- Mobile responsive

## Launch

1. Show HN (Tuesday/Wednesday 9am US Pacific)
2. r/LangChain + r/LocalLLaMA
3. Twitter/X with demo GIF
4. Target: 500 GitHub stars first week

## Naming

- **PyPI:** `agentpeek` — available
- **npm:** `agentpeek` — available
- **GitHub:** `TranHuuHoang/agent-peek`
- **Domain:** `agentpeek.dev` — available

---

## v2: Agent Reliability Benchmarking (StepProbe)

### The Problem

AgentPeek v1 shows you what agents are doing. v2 tells you **how reliably they do it**. The #1 barrier to production agents is compound errors: 95% per-step accuracy across 5 steps = only 77% end-to-end. No existing tool (0/20+ surveyed) profiles this per-step.

### How It Works

In addition to the existing hook-based observation, v2 adds a **transparent LLM proxy** mode that intercepts API calls between agents and LLM providers:

```
Agent → AgentPeek proxy (localhost) → Real LLM API (Anthropic/OpenAI)
                  ↓
        Chain reconstruction (messages array prefix matching)
                  ↓
        Per-step reliability tracking
                  ↓
        Real-time dashboard + CLI output
```

**Key insight:** LLM APIs are stateless — every request contains the full conversation history in the `messages` array, including `tool_use`/`tool_result` blocks with globally unique IDs (`toolu_*`, `call_*`). The proxy reconstructs the execution chain automatically without any code instrumentation.

### Zero-Code Setup (Proxy Mode)

```bash
agentpeek bench python my_agent.py          # CLI wrapper, auto-sets env vars
agentpeek profile --command "python agent.py" --runs 50  # N-run profiling
agentpeek gate --threshold 0.85 --runs 50   # CI/CD quality gate (exit 0/1)
```

Under the hood, sets `ANTHROPIC_BASE_URL` / `OPENAI_BASE_URL` to the local proxy. ~3ms overhead. No CA certs needed.

### Three Benchmark Modes

| Mode | What | Display |
|------|------|---------|
| **Watch** | Observe a single run in real-time (existing AgentPeek behavior + proxy chain view) | Live, as it happens |
| **Profile** | Run agent N times, compute per-step reliability with converging statistics | Real-time — stats update after each run completes |
| **Gate** | Pass/fail against a threshold, with SPRT early stopping to save cost | Real-time — can abort at run 12 of 50 when results are decisive |

### Real-Time Converging Dashboard

```
Run  1/50 → chain structure discovered, first pass/fail
Run  5/50 → per-step reliability numbers appear (noisy, wide CIs)
Run 12/50 → bottleneck clear: step 3 fails 42% of the time
           → SPRT: "Step 3 below 70% with 95% confidence. Stop?"
Run 50/50 → final report with tight confidence intervals
```

Uses Sequential Probability Ratio Test (SPRT) for early stopping + Wilson confidence intervals for per-step pass rates. All displayed in real-time as runs complete.

### Additional Dashboard Views (v2)

Added to the existing 5 views:

6. **Reliability Funnel** — Nivo funnel chart: compound reliability dropping step by step
7. **Failure Heatmap** — Nivo heatmap: steps × runs, color = pass/fail
8. **Correlation Matrix** — which step failures cause downstream failures
9. **Run Comparison** — side-by-side overlay of two profiling sessions

### Proxy Architecture (Reuses `poc/proxy_server.py`)

The existing `poc/proxy_server.py` (269 lines) already implements:
- Catch-all request interception
- Agent metadata extraction from headers
- Forward to real API + capture response
- In-memory state tracking

v2 extends this with:
- Messages array prefix matching for chain reconstruction
- Tool-use ID graph for parallel agent demuxing
- Per-step pass/fail tracking across N runs
- SPRT statistics engine
- SSE streaming to dashboard

### Providers Supported (v2)

| Provider | Env Var | Zero-Code? |
|----------|---------|-----------|
| Anthropic | `ANTHROPIC_BASE_URL` | Yes |
| OpenAI | `OPENAI_BASE_URL` | Yes |
| AWS Bedrock | `AWS_ENDPOINT_URL_BEDROCK_RUNTIME` | Yes (SigV4 complexity) |
| Google Gemini | `GOOGLE_GEMINI_BASE_URL` | Partial |
| Ollama | Via `OPENAI_BASE_URL` (compat mode) | Yes |

Launch with **Anthropic + OpenAI only** (80%+ of market).

### Edge Cases

- **OpenAI Responses API** (stateful, `previous_response_id`): breaks proxy reconstruction. Mitigate by capturing all responses or requiring Chat Completions mode.
- **Anthropic Compaction** (`compact_20260112`): summarizes older messages, losing detail. Mitigate by continuous logging before compaction fires.
- **Streaming SSE**: solved — buffer + forward pattern, no added latency.

### Competitive Gap (March 2026 Research: 50 agents, 5 batches)

No existing tool combines: zero-code proxy + auto chain reconstruction + per-step compound error profiling + real-time convergence + SPRT early stopping. Closest competitors:
- **Braintrust** ($800M): has proxy + CI gates, but no compound error viz or SPRT
- **Datadog LLM** ($44B): strongest compound error viz via APM, but requires SDK, no SPRT
- **agentrial**: Wilson CIs but no SPRT, no real-time dashboard
- **AgentAssay** (paper): SPRT with 78% trial reduction, but not shipped as a product

### v2 Build Plan

| Phase | What | Timeline |
|-------|------|----------|
| v2.0 | Proxy + chain reconstruction + CLI output | 1 week |
| v2.1 | Dashboard: funnel + heatmap + reliability views | 1 week |
| v2.2 | `agentpeek profile --runs N` with real-time convergence | 1 week |
| v2.3 | SPRT early stopping + `agentpeek gate` | 3-4 days |

### Known Risks

- **Feature not product** — incumbents can add this as a tab (mitigated: open-source, not a business)
- **Cost of profiling** — $5-50 per N-run session (mitigated: SPRT early stopping saves 40-78%)
- **Maintenance** — supporting provider API changes (mitigated: Anthropic + OpenAI only at launch)
