"""Realistic mock LLM responses for the stock market research agent team."""

RESPONSES = {
    "orchestrator": """I'll break this into parallel research tracks:

1. **market-data-agent**: Fetch S&P 500, NASDAQ, Dow Jones performance over the last 60 days
2. **sector-analyst**: Analyze which sectors outperformed/underperformed
3. **news-scanner**: Find the key catalysts and macro events driving market moves

Once all three report back, I'll send their findings to the **report-writer** to synthesize a final brief.""",

    "market-data-agent": """## US Market Performance (Jan 17 - Mar 18, 2026)

**S&P 500**: 5,842 → 6,127 (+4.9%)
- 60-day high: 6,203 (Mar 7)
- 60-day low: 5,714 (Feb 3)
- Current trend: Upward, consolidating near highs

**NASDAQ Composite**: 18,491 → 19,834 (+7.3%)
- Led by AI/semiconductor rally
- 8 consecutive green weeks ending Mar 14

**Dow Jones**: 42,107 → 43,285 (+2.8%)
- Underperforming vs growth-heavy indices
- Weighed down by healthcare (-3.2%) and energy (-1.8%)

**Key Technicals**:
- VIX: 14.2 (low volatility regime)
- 10Y Treasury: 4.18% (down from 4.52%)
- Put/Call ratio: 0.72 (bullish)
- S&P above 50-day and 200-day MA""",

    "sector-analyst": """## Sector Performance Breakdown (60-day)

**Top Performers:**
1. **Technology** +9.4% — AI infrastructure spending acceleration; NVDA +18%, MSFT +7%, GOOGL +11%
2. **Communication Services** +7.1% — META +14% on AI agent platform launch
3. **Consumer Discretionary** +5.8% — AMZN +9% on AWS AI revenue beat
4. **Financials** +4.2% — Rate cut expectations boosting bank margins

**Underperformers:**
1. **Energy** -1.8% — Oil dropped to $68/bbl on demand concerns
2. **Healthcare** -3.2% — GLP-1 pricing pressure, regulatory uncertainty
3. **Utilities** -0.4% — Rotation out of defensives into growth
4. **Real Estate** +0.9% — Flat, waiting for rate clarity

**Notable Rotation:** Clear risk-on rotation from defensives (utilities, healthcare, staples) into growth (tech, comms). Magnitude suggests institutional rebalancing, not retail-driven.""",

    "news-scanner": """## Key Market Catalysts (Last 60 Days)

**Bullish Events:**
- **Feb 12**: Fed Chair signals potential rate cut in Q2 2026 → S&P +2.1% same day
- **Feb 19**: NVIDIA earnings blow out — $38B revenue, +22% QoQ → semiconductor rally
- **Feb 26**: US-China trade tensions ease; tariff reduction on tech components announced
- **Mar 5**: Jobs report: 187K added, unemployment steady at 3.9% — Goldilocks
- **Mar 11**: Meta launches "Agent Platform" — multi-agent AI marketplace → AI stocks surge

**Bearish Events:**
- **Jan 24**: Surprise CPI print 3.1% vs 2.9% expected → 2-day selloff (-1.8%)
- **Feb 3**: Regional bank stress resurfaces (First Republic successor wobbles) → financials dip
- **Mar 14**: EU announces AI Act enforcement timeline — regulatory overhang on EU-exposed tech

**Macro Context:**
- GDP growth tracking 2.3% annualized (solid)
- Consumer confidence at 104.2 (above average)
- Earnings season Q4 2025: 78% of S&P beat estimates (above historical 74%)
- AI capex from hyperscalers: $220B announced for 2026 (record)""",

    "report-writer": """# US Stock Market Research Brief — Last 60 Days
*Generated Mar 18, 2026*

## Executive Summary
The US stock market posted strong gains over the past 60 days, with the S&P 500 rising 4.9% and the NASDAQ surging 7.3%. The rally was driven by three converging catalysts: dovish Fed signaling, blockbuster AI earnings (particularly NVIDIA), and easing US-China trade tensions.

## Key Findings

**1. AI Remains the Dominant Theme**
Technology led all sectors at +9.4%, powered by AI infrastructure spending. NVIDIA's $38B quarterly revenue and Meta's Agent Platform launch created sustained momentum. Hyperscaler AI capex commitments of $220B for 2026 signal this is structural, not speculative.

**2. Goldilocks Economic Data**
The macro backdrop is supportive: GDP tracking 2.3%, unemployment at 3.9%, and 78% of S&P companies beating Q4 earnings. The Feb jobs report threaded the needle — strong enough to avoid recession fears, soft enough to keep rate cuts on the table.

**3. Clear Risk-On Rotation**
Institutional money is rotating from defensives (healthcare -3.2%, energy -1.8%) into growth (tech +9.4%, comms +7.1%). This isn't retail FOMO — the magnitude and consistency suggest systematic rebalancing.

**4. Low Volatility, High Complacency?**
VIX at 14.2 and a put/call ratio of 0.72 indicate extreme complacency. Historically, sustained low-vol regimes precede sharp corrections, though timing is unpredictable.

## Risks to Monitor
- CPI re-acceleration (Jan surprise print was a warning shot)
- EU AI Act enforcement creating regulatory drag
- Regional banking stress (not resolved, just quiet)
- Concentration risk: top 7 stocks driving >60% of S&P gains

## Outlook
Bias remains bullish near-term with Fed rate cut catalyst ahead. However, the low-volatility regime and narrow market breadth warrant caution. A 3-5% pullback would be healthy and likely bought aggressively.""",

    "default": "Analysis complete. Data processed and ready for synthesis.",
}


def get_mock_response(agent_name: str) -> str:
    return RESPONSES.get(agent_name, RESPONSES["default"])
