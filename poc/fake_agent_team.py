"""
Realistic agent team: "Research US stock market over the last 60 days"

Hierarchy:
  orchestrator
  ├── market-data-agent    (parallel)
  ├── sector-analyst       (parallel)
  ├── news-scanner         (parallel)
  └── report-writer        (sequential, after all 3 complete)

The orchestrator fans out 3 research agents in parallel,
waits for all results, then delegates to report-writer.
"""

import os
import time
import threading

import anthropic

PROXY_URL = "http://localhost:8099"
SESSION_ID = f"stock-research-{int(time.time())}"


def make_client(agent_name: str, parent: str | None = None) -> anthropic.Anthropic:
    headers = {
        "x-agent-name": agent_name,
        "x-agent-session": SESSION_ID,
    }
    if parent:
        headers["x-agent-parent"] = parent
    return anthropic.Anthropic(
        base_url=PROXY_URL,
        api_key=os.environ.get("ANTHROPIC_API_KEY", "sk-mock-key"),
        default_headers=headers,
    )


def call_agent(name: str, parent: str | None, system: str, user_msg: str, model: str = "claude-sonnet-4-20250514") -> str:
    """Generic agent call."""
    client = make_client(name, parent)
    response = client.messages.create(
        model=model,
        max_tokens=2000,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )
    return response.content[0].text


def run_team():
    print("""
\033[1m╔══════════════════════════════════════════════════════════════╗
║  User: "Research US stock market over the last 60 days"      ║
║  Spawning agent team...                                      ║
╚══════════════════════════════════════════════════════════════╝\033[0m
""")

    start = time.time()

    # ── Step 1: Orchestrator plans the research ──────────────────────
    print("  [1/3] Orchestrator planning research strategy...")
    plan = call_agent(
        name="orchestrator",
        parent=None,
        system="You are a research orchestrator. Break down research tasks and delegate to specialist agents.",
        user_msg="Research the US stock market performance over the last 60 days. Plan which specialist agents to spawn and what each should focus on.",
        model="claude-sonnet-4-20250514",
    )
    print(f"        Plan ready ({len(plan)} chars)")

    # ── Step 2: Fan-out — 3 research agents in parallel ──────────────
    print("  [2/3] Spawning 3 research agents in parallel...")
    results = {}

    def run_agent(name, system, prompt, key):
        results[key] = call_agent(
            name=name,
            parent="orchestrator",
            system=system,
            user_msg=prompt,
        )
        print(f"        {name} done ({len(results[key])} chars)")

    threads = [
        threading.Thread(target=run_agent, args=(
            "market-data-agent",
            "You are a market data specialist. Provide precise index performance data, technicals, and price action analysis.",
            "Get S&P 500, NASDAQ, and Dow Jones performance data for the last 60 days (Jan 17 - Mar 18, 2026). Include highs, lows, trends, and key technical indicators.",
            "market_data",
        )),
        threading.Thread(target=run_agent, args=(
            "sector-analyst",
            "You are a sector analysis specialist. Analyze sector rotation, relative performance, and identify what's driving sector moves.",
            "Analyze sector performance across all S&P 500 sectors for the last 60 days. Identify top performers, underperformers, and explain the rotation patterns.",
            "sectors",
        )),
        threading.Thread(target=run_agent, args=(
            "news-scanner",
            "You are a financial news analyst. Identify the most market-moving events and their impact on price action.",
            "Scan for the most significant market-moving events, catalysts, and macro developments affecting US equities over the last 60 days.",
            "news",
        )),
    ]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # ── Step 3: Report writer synthesizes everything ─────────────────
    print("  [3/3] Report writer synthesizing findings...")
    combined_research = f"""## Market Data
{results['market_data']}

## Sector Analysis
{results['sectors']}

## Key Events & Catalysts
{results['news']}"""

    report = call_agent(
        name="report-writer",
        parent="orchestrator",
        system="You are a senior financial analyst. Synthesize research from multiple sources into a clear, actionable brief.",
        user_msg=f"Synthesize the following research into a concise stock market brief:\n\n{combined_research}",
        model="claude-sonnet-4-20250514",
    )

    elapsed = time.time() - start

    print(f"""
\033[1m{'='*60}
  DONE in {elapsed:.1f}s — 5 agents, {len(results) + 2} LLM calls

  Dashboard: \033[4mhttp://localhost:8099/_agentpeek\033[0m
{'='*60}\033[0m

{report[:500]}...
""")


if __name__ == "__main__":
    run_team()
