# AgentPeek — Project Memory

## Tagline
**"Peek into your agents."** Watch your AI agent systems work in real-time.

## What It Is
A real-time visualization tool for multi-agent AI systems. Agents appear as interactive nodes on a canvas, with animated edges showing messages flowing between them. Click any node or edge to see full intermediate results. Works with any agent framework.

**Not** an observability/monitoring platform (that's Langfuse). **Not** a cute screensaver (that's PixelAgent). It's a **live diagnostic tool** — Chrome DevTools for AI agent systems.

## Core Concept
7 visualization layers on one interactive canvas:
1. **Topology** — Who exists, parent-child hierarchy (from `parent_agent_id`)
2. **Communication** — Who talks to who, animated edges with message content
3. **Orchestration patterns** — Auto-detect: sequential, parallel, fan-out, evaluator-optimizer, router
4. **Intermediate state** — Click any edge to see exactly what was passed between agents
5. **Temporal flow** — Timeline/Gantt showing when each agent was active
6. **Health/Cost** — Per-agent token/cost breakdown, retry count, wait time
7. **Cross-session** — Multiple agent sessions on one canvas (3 Claude Code tabs = one unified view)

## Key Differentiators
- **Real-time** (not post-hoc like Langfuse/Arize)
- **Framework-agnostic** (not locked to one ecosystem like LangGraph Studio)
- **Cross-session** (see ALL your agent sessions in one place)
- **Intermediate results** (see WHAT agents passed to each other, not just THAT they communicated)
- **Pattern detection** (auto-labels orchestration patterns)
- **Feedback loop visualization** (retry cycles visible as graph cycles)

## Event Schema (Validated with 47 fake events)
6 event types power all 7 layers:
```
agent_start | agent_end | message | tool_call | tool_result | error
```
Each event has: `session_id`, `agent_id`, `agent_name`, `timestamp_ms`, `type`, `parent_agent_id`, `target_agent_id`, `content`, `metadata` (model, tokens, cost, latency, tool_name).

Fake events file: `/Users/huuhoangtran/Documents/Projects/DeepCrew/simulation_events.json` (47 events, 2 sessions, 8 agents)

## Architecture
```
Agent Sources (Claude Code, LangGraph, CrewAI, OTel, HTTP POST)
    │
    ▼ (emit events)
FastAPI Server (SSE endpoint, in-memory session store)
    │
    ▼ (Server-Sent Events)
React Frontend (React Flow canvas + side panels + stats)
```

- **SSE** (not WebSocket) — simpler, auto-reconnect, sufficient for one-directional observation
- **In-memory** — no database needed. 10-minute agent run = ~2-10 MB. Trivially small.
- **React Flow** — handles dynamic nodes, animated edges, nested groups, dagre layout. 5-20 nodes is nowhere near performance limits.

## Framework Integration (Lines of Code)
| Framework | Integration Effort |
|-----------|-------------------|
| LangGraph | ~15-30 lines (callback handler) |
| CrewAI | ~10-20 lines (OTel instrumentor) |
| OpenAI Agents SDK | ~20-40 lines (RunHooks subclass) |
| Claude Agent SDK | ~20-40 lines (hooks) |
| Generic OTel | 0 lines (point OTLP endpoint at collector) |
| Any language/framework | HTTP POST /events with JSON |

## Auto-Detection Strategy (No API Keys)
Priority order for LLM backend (if needed for any AI features):
1. Ollama (localhost:11434) — free, local
2. Claude Code CLI — user already subscribed
3. Codex CLI — user already subscribed
4. Direct SDK from existing credentials (~/.claude, OPENAI_API_KEY)

## Competitive Landscape
| Tool | Overlap | Key Gap |
|------|:-------:|---------|
| Langfuse (23K stars) | ~50% | Post-hoc, no real-time animated topology |
| LangGraph Studio | ~60% | LangGraph-only, not framework-agnostic |
| AgentOps (5K stars) | ~40% | Waterfall timeline, not graph topology |
| PixelAgent | ~15% | Pure cosmetic, no real data, no intermediate results |
| AgentPrism (288 stars) | ~30% | Post-hoc components only, no live streaming |
| Mission Control (1.8K stars) | ~45% | Kanban/fleet view, not execution graph |
| AgentWatch (CyberArk, 111 stars) | ~15-20% | Basic HTTP audit log with flat graph |

**Nobody combines:** real-time streaming + visual graph + intermediate results + hierarchy + cross-session + framework-agnostic.

## Market Data
- 500K-1M developers actively building multi-agent systems (2026)
- "Debugging multi-agent systems takes 3-5x longer than single-agent" (OneUpTime)
- "Teams spend 40% of sprint time investigating agent failures" (Medium)
- Pixel Agents went viral doing NOTHING useful — proves appetite for agent visualization
- LangGraph: 38M monthly PyPI downloads
- CrewAI: 100K+ certified developers

## Naming
- **Name:** AgentPeek
- **PyPI:** `agentpeek` — AVAILABLE ✅
- **npm:** `agentpeek` — AVAILABLE ✅
- **GitHub:** `TranHuuHoang/agent-peek` (github.com/agentpeek username taken by inactive squatter)
- **Domain:** `agentpeek.dev` — AVAILABLE ✅ (.com is parked)
- **Tagline:** "Peek into your agents."
- **Visual identity:** Minimalist spy-themed character avatars per agent role (spymaster, scout, analyst, forger, inspector)
- **UI style:** Modern indie dev aesthetic — Inter font, rounded corners, glass cards, soft accent colors, dark mode

### Name Research (2026-03-17)
- "AgentPeek" dropped — agentpeek.com taken by insurance software (KRJ Software)
- "SpyAgent" dropped — registered US trademark (#2788955), MITRE ATT&CK classified malware (S1214)
- "agentspy" dropped — PyPI taken (AgentsPy), agent-spy repos exist in same product space
- "agentpeek" selected — clean across PyPI, npm, all app stores, no malware/trademark conflicts
- Minor: Korean fashion brand "Agent Peek" exists (different industry, zero overlap)

## Build Plan (1-2 weeks with Claude Code)
| Day | Deliverable |
|-----|------------|
| 1 | Event schema + FastAPI SSE server + in-memory session store |
| 2 | LangGraph adapter (~30 lines). Real 3-agent example emitting events. |
| 3 | React Flow canvas: agents as nodes, messages as animated edges. Dagre layout. |
| 4 | Click/hover panel for intermediate results. Status colors. Event log sidebar. |
| 5 | Generic OTel adapter. Cross-session grouping. Polish animations. |
| 6 | Health/cost stats panel. Orchestration pattern detection badges. |
| 7 | README + demo GIF + `pip install agentpeek` + landing page. |
| 8 | Launch: Show HN + Twitter + r/LangChain + r/LocalLLaMA |

## What to CUT from v1
- Timeline scrubber/replay (add in v1.1)
- Bedrock/Azure support
- User accounts / auth
- Database / persistence (in-memory only)
- Production monitoring features
- Multi-user collaboration
- Mobile responsive

## Launch Strategy
1. Show HN (Tuesday/Wednesday 9am US Pacific)
2. r/LangChain (87K members) + r/LocalLLaMA (266K members)
3. Twitter/X with demo GIF — tag Anthropic devrel, LangChain community
4. Dev.to "How I Built AgentPeek" article
5. Target: 500 stars in first week

## Tech Stack
- **Backend:** Python, FastAPI, SSE
- **Frontend:** React 19, TypeScript, Vite, Tailwind, shadcn/ui, React Flow
- **Storage:** In-memory (SQLite optional for replay in v2)
- **Layout:** dagre.js for auto-positioning
- **Adapters:** LangGraph callback, OTel collector, HTTP POST endpoint

## Research Origins
This project was selected after evaluating 106 ideas across 40+ research agents over multiple rounds. Key filters that led here:
1. Must be AI/agent related
2. Must be genuinely complex (not a wrapper)
3. Must produce shareable visual output
4. Must NOT be replaceable by Claude Code prompting (needs runtime, live UI, persistent state)
5. Must not already exist as a polished tool (validated against 20+ competitors)
6. Must be buildable in 1-2 weeks

The "live real-time agent visualization" direction survived every filter. The gap between post-hoc tools (Langfuse) and framework-locked tools (LangGraph Studio) is where AgentPeek lives.

## UI Design Direction (2026-03-17)
- **Style:** Modern indie dev — Inter + JetBrains Mono, rounded corners (10px), glass cards (#FFFFFF06), soft accents
- **Palette:** #09090B bg, #4ADE80 green, #60A5FA blue, #A78BFA purple, #FBBF24 amber, #F87171 red
- **Agent avatars:** Minimalist spy characters per role — each with unique accessory (binoculars, glasses, pen, shield, etc.)
- **Flow visualization:** Top-to-bottom with numbered steps, thick gradient arrows, labeled edges showing what was passed
- **Right panel:** Flow summary timeline + intermediate result inspector (color-coded JSON)
- **Design files:** `design/` directory (Pencil .pen files with multiple mockup iterations)
