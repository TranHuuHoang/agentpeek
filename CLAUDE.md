# AgentPeek

See `PROJECT.md` for project vision, scope, and documentation.
See `MEMORY.md` for session status and context for the next Claude session.

## Code Style

- Python: ruff defaults, type hints, Pydantic for data models
- TypeScript: strict mode, functional components, no `any`
- Keep files small and focused

## Architecture

### v1: Hook-Based Observation
- Hooks append JSONL to `/tmp/agentpeek.jsonl` via jq (configured in `~/.claude/settings.json`)
- Python server tails the file, builds agent state, serves dashboard on `:8099`
- Venv at `.venv/` — run server with `.venv/bin/python`

### v2: Proxy-Based Benchmarking (new)
- Transparent proxy intercepts LLM API calls via `ANTHROPIC_BASE_URL` / `OPENAI_BASE_URL` env vars
- Chain reconstruction uses messages array prefix matching — no instrumentation needed
- Tool_use IDs (`toolu_*`, `call_*`) are globally unique — deterministic chain linking
- Per-step reliability tracking across N runs with SPRT early stopping
- SSE streams data to dashboard for real-time convergence visualization

## Critical Build Rules

- **SubagentStart/SubagentStop hooks don't fire** — auto-discover agents from `agent_id` field on PreToolUse/PostToolUse events
- **Don't break existing hooks** in `~/.claude/settings.json` — AgentPeek hooks are actively used during development
- **All hooks must have `"async": true`** — blocking hooks kill Claude Code sessions
- PoC code lives in `poc/` — reference it but don't extend it; build fresh
- **v2 proxy: start from `poc/proxy_server.py`** — the proxy pattern is proven and reusable
- **Anthropic + OpenAI only at launch** — don't boil the ocean with provider support
- **Statistics must be correct** — Wilson CIs, SPRT (Wald), not hand-rolled approximations
