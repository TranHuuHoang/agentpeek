# AgentPeek — Session Memory

This file records session status and context for the next Claude session. For full project documentation, see `PROJECT.md`.

## Current Status
- **Phase:** Project dropped as pure visualization tool (2026-03-17). Pivoting to add reliability benchmarking (2026-03-19).
- **Original drop reason:** Multi-agent visualization is a narrow market. Most developers debug agents via logs/output iteration, not live topology. Real-time canvas is a great demo but thin on daily utility.
- **New direction:** Keep all existing AgentPeek observation features, add a transparent LLM proxy mode that benchmarks per-step agent reliability across N runs with real-time converging statistics and SPRT early stopping.
- **Next step:** Build v2.0 — proxy + chain reconstruction + CLI output, starting from `poc/proxy_server.py`

## Key Learnings from AgentPeek
- "Cool demo" ≠ "useful tool" — viral GIFs get stars but don't guarantee retention
- Most LLM apps are single agent + tools, not multi-agent orchestration
- Post-hoc debugging (logs, Langfuse) is "good enough" for 90% of cases
- Developer tools need daily use to survive
- The question to validate: "will someone's workflow change because this exists?"

## Why Benchmarking Changes the Equation
- The CI/CD gate (`agentpeek gate --threshold 0.85`) is the painkiller — blocks bad deploys
- The dashboard is the vitamin — but now shows actionable data (which step breaks, how often), not just topology
- Real-time convergence means you don't wait for all runs — abort early and save cost
- The proxy approach requires zero code changes (just env vars or CLI wrapper)

## Research Summary (50 agents, 5 batches, March 2026)
- **Gap confirmed:** 0/20+ tools do per-step compound error profiling with visualization
- **Tech feasible:** Messages arrays contain full history, tool_use IDs are globally unique, chain reconstruction is near-trivial
- **SPRT not shipped:** AgentAssay paper (78% trial reduction) exists but is not a product
- **Closest competitor:** Braintrust (proxy + eval, no compound error viz), Datadog (APM flamegraphs, no SPRT)
- **Market:** $1-3B observability, quality = #1 production barrier (32%), 89% of orgs already use observability
- **Biggest risk:** "Feature not product" — mitigated by open-source approach

## What We're Building Next
- v2.0: Proxy mode + chain reconstruction + CLI benchmark output
- v2.1: Dashboard additions (funnel, heatmap, correlation views)
- v2.2: `agentpeek profile --runs N` with real-time convergence
- v2.3: SPRT early stopping + `agentpeek gate` for CI/CD
