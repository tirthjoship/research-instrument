# Phase 5.5 — Investment Intelligence UX Overhaul

**Date:** 2026-06-04
**Status:** Approved (brainstorming complete)
**ADR:** 037
**Branch:** `feat/phase-5.5-ux-overhaul`
**Predecessor:** Phase 5.4 (SWST-grade redesign, 996 tests, signal radar, conviction engine fix)

---

## Problem Statement

Phase 5.4 built the infrastructure — 15+ chart builders, conviction engine with real sub-scores, Stock Analysis tab, live price cache. But visual QA revealed the dashboard still doesn't answer the fundamental question: **"What should I do right now?"**

**Issues from Round 1 visual QA (2026-06-04 3:05 PM):**

1. **No action orientation** — every tab shows data but doesn't recommend actions. Watchlist shows P/E but not "entry window opening." Portfolio shows P&L but not "sell TSLA, approaching stop-loss."
2. **Stock Analysis doesn't render** — Run Analysis button fails silently (fixed in hotfix but needs proper error handling + full section rendering verification).
3. **Sub-score bars showed nonsensical %** — normalization was wrong (fixed in hotfix).
4. **Watchlist is passive** — user types notes instead of system generating insights. Should be a "smart watchlist" with speculation horizon.
5. **Portfolio has too many sections** — 5 sections of recordkeeping clutter. Should be a table with recommendations.
6. **Tab 5 (How It Works) is empty** — no trades = nothing to show. Empty states look abandoned.
7. **Tab 6 (Market Context) has no actionable info** — leaders/followers with no "so what?"
8. **Font sizes too small** — text hard to read across all tabs.
9. **Buttons have no explanation** — "Scan Now" and "Run Full Cycle" mean nothing to a new user.
10. **No portfolio-level intelligence** — no health score, no diversification analysis, no benchmark comparison, no action queue.

**Root cause:** Phase 5.4 spec focused on building components but not on the UX flow. Subagents implemented what was described but didn't synthesize across tabs to create a coherent decision-making experience.

---

## Vision

Transform from "here's your data" to **"here's what you should do."** Every element on every tab has an action-oriented sentence. The system tells the user what's happening, what to do about it, and when.

**Design principle:** Every visible element answers "What should I do with this?"

**Competitive benchmark:** Portfolio Genius (AI insights + risk analysis), SimplyWallSt (Snowflake + verdicts), PortfolioPilot (action queue + smart alerts), Wealthsimple (clean portfolio view + benchmark).

---

## Tab Architecture (5 tabs, restructured)

```
Dashboard | Opportunities | My Portfolio | Stock Analysis | System Intelligence
```

### Rationale for restructure

| Old Tab | New Home | Why |
|---------|----------|-----|
| Today's Opportunities | Dashboard (action queue) + Opportunities (cards) | Split: actions on landing, details on Opportunities |
| Watchlist | Merged into Opportunities | Watchlist IS a subset of opportunities — tickers being monitored |
| My Portfolio | My Portfolio (simplified) | Keep, but redesign as table + recommendations |
| Stock Analysis | Stock Analysis | Keep, fix rendering, add Gemini AI |
| How It Works | System Intelligence | Rename, merge with Market Context |
| Market Context | System Intelligence | Supply chain, data pipeline, model baseline all = "system internals" |

---

## Global Design Rules

### Font Sizes (increased from Phase 5.4)

```css
html, body, [class*="css"] { font-size: 16px; }  /* base — was 15px */
h1 { font-size: 32px !important; }                /* was 28px */
h2 { font-size: 24px !important; }                /* was 20px */
h3 { font-size: 18px !important; }                /* was 16px */
h4 { font-size: 16px !important; }
.ws-card { font-size: 15px; }                      /* card body text */
.metric-value { font-size: 28px; }                 /* big numbers — was 24px in metric_kpi */
```

### Button Rules

Every button must have:
1. **Clear label** — verb + noun ("Run Analysis", "Scan for Opportunities")
2. **Subtitle or tooltip** explaining what it does
3. **Loading state** — progress bar with step messages for anything >2 seconds

Button subtitle pattern:
```html
<div>
  <button>Scan for Opportunities</button>
  <div style="font-size:12px;color:#64748B;margin-top:2px;">
    Checks SEC filings, sentiment, and fundamentals across 350 tickers
  </div>
</div>
```

### Action Sentence Rule

Every card, every table row, every section must include ONE action-oriented sentence:
- **Green** = positive action ("Hold — all signals bullish")
- **Amber** = watch/caution ("Monitor — approaching overbought")
- **Red** = urgent action ("Consider selling — stop-loss approaching")

---

## Tab 1: Dashboard

**Purpose:** "What should I do today?" — The landing page.

### Layout

```
┌─ Market Ticker Bar ─────────────────────────────────────────────┐
│ S&P 500 $545.23 ▲0.56%  NASDAQ $487 ▲0.8%  DOW $42,100 ▲0.3% │
└─────────────────────────────────────────────────────────────────┘

┌─ Portfolio Health Score ────────────────────────────────────────┐
│                                                                 │
│  Portfolio: $21,340 (+6.2%)    Health: 7/10 ●●●●●●●○○○         │
│  vs S&P 500: +12.1%           ⚠️ Underperforming benchmark     │
│                                                                 │
│  [Portfolio value vs SPY line chart — 30 days, two lines]       │
│                                                                 │
│  Diversification: 80% Tech ⚠️  │  4 positions  │  1 at risk   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─ Action Queue ──────────────────────────────────────────────────┐
│ TODAY'S ACTIONS (prioritized)                                   │
│                                                                 │
│  🔴 1. TSLA: Consider reducing — down 2.2%, approaching        │
│        stop-loss (-8%). No bullish catalysts detected.          │
│        [Analyze] [Record Sell]                                  │
│                                                                 │
│  🟡 2. AMD (watchlist): Entry window opening — upstream         │
│        leader NVDA moved +3.2%. Historical lag: 1-3 days.      │
│        [Analyze] [Add to Portfolio]                             │
│                                                                 │
│  🟢 3. NVDA: Hold — all horizons bullish, conviction 8.2/10.   │
│        Review in 5-10 days.                                     │
│        [Analyze]                                                │
│                                                                 │
│  ℹ️ 4. Portfolio is 80% technology. Consider adding healthcare  │
│        or energy for diversification.                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─ Market Summary ────────────────────────────────────────────────┐
│  Sector Performance Today                                       │
│  Technology ▲1.2%  Healthcare ▼0.3%  Energy ▲0.8%  ...         │
│  [Sector bars — green/red horizontal]                           │
│                                                                 │
│  [Scan for Opportunities]                                       │
│  Checks SEC filings, sentiment, and fundamentals across 350     │
│  tickers. Takes ~30 seconds.                                    │
└─────────────────────────────────────────────────────────────────┘
```

### Portfolio Health Score

Computed from:
- **Performance** (2 pts): total P&L > 0 = 1pt, vs SPY positive = 1pt
- **Diversification** (3 pts): no single sector > 50% = 1pt, >= 3 positions = 1pt, no single position > 40% = 1pt
- **Risk** (2 pts): no positions near stop-loss = 1pt, no sell signals active = 1pt
- **Signals** (3 pts): majority holdings bullish = 1pt, portfolio conviction avg > 5 = 1pt, sentiment positive = 1pt

Total: N/10 with green/gray dots.

### Action Queue

Priority logic:
1. **Red — Urgent sells:** Holdings approaching stop-loss, active sell signals (from `MonitorHoldingsUseCase`)
2. **Amber — Watchlist catalysts:** Watchlist tickers with new signals (upstream leader moved, insider buying, sentiment spike)
3. **Green — Hold confirmations:** Holdings performing well with bullish signals
4. **Blue — Portfolio advice:** Diversification warnings, rebalancing suggestions

Each action item has: color indicator + ticker + plain English sentence + action buttons.

### Action Queue Data Sources

```python
def generate_action_queue(holdings, watchlist, prices, recommendations, buzz_signals, supply_chain) -> list[ActionItem]:
    """Generate prioritized action items from all available data."""
    actions = []

    # 1. Check holdings for sell signals
    for h in holdings:
        current = prices.get(h.symbol, {}).get("price", h.purchase_price)
        pnl_pct = (current - h.purchase_price) / h.purchase_price * 100
        if pnl_pct <= -5:  # approaching stop-loss
            actions.append(ActionItem(
                priority="urgent",
                ticker=h.symbol,
                message=f"Consider reducing — down {pnl_pct:.1f}%, approaching stop-loss (-8%). {_get_catalyst_text(h.symbol, buzz_signals)}",
                buttons=["Analyze", "Record Sell"],
            ))

    # 2. Check watchlist for entry signals
    for w in watchlist:
        ticker = w["symbol"]
        insight = generate_watchlist_insight(ticker, prices, buzz_signals, supply_chain, recommendations)
        if insight["signal"]:
            actions.append(ActionItem(
                priority="watch",
                ticker=ticker,
                message=insight["signal"] + " " + insight["action"],
                buttons=["Analyze", "Add to Portfolio"],
            ))

    # 3. Confirm holds
    for h in holdings:
        rec = recommendations.get(h.symbol)
        if rec and rec.grade in ("strong_buy", "buy"):
            actions.append(ActionItem(
                priority="hold",
                ticker=h.symbol,
                message=f"Hold — {_horizon_summary(rec)}. Review in {_hold_duration(rec)}.",
                buttons=["Analyze"],
            ))

    # 4. Portfolio-level advice
    sector_pcts = _compute_sector_allocation(holdings, prices)
    max_sector = max(sector_pcts, key=sector_pcts.get) if sector_pcts else None
    if max_sector and sector_pcts[max_sector] > 50:
        actions.append(ActionItem(
            priority="info",
            ticker=None,
            message=f"Portfolio is {sector_pcts[max_sector]:.0f}% {max_sector}. Consider adding other sectors for diversification.",
            buttons=[],
        ))

    return sorted(actions, key=lambda a: {"urgent": 0, "watch": 1, "hold": 2, "info": 3}[a.priority])
```

### Portfolio vs SPY Benchmark Chart

Two-line Plotly chart:
- Blue line: portfolio value over 30 days (computed from holdings × daily closing prices)
- Gray dashed line: SPY performance over same period (normalized to same starting value)
- Difference highlighted: green area if portfolio outperforms, red if underperforms

Data: `yf.download(tickers + ["SPY"], period="1mo")`, cached 5min.

---

## Tab 2: Opportunities

**Purpose:** "What should I buy?" — Conviction-ranked opportunities + smart watchlist.

### Layout

```
┌─ Header ────────────────────────────────────────────────────────┐
│  Opportunities                    [Scan for Opportunities]      │
│  Conviction-ranked picks +        Scans 350 tickers across     │
│  your watchlist with live          SEC, sentiment, fundamentals. │
│  monitoring.                       Last scan: 12 min ago.       │
└─────────────────────────────────────────────────────────────────┘

┌─ Filter Bar ────────────────────────────────────────────────────┐
│  Show: [All] [Top Picks] [Watchlist Only]   Sort: [Conviction] │
└─────────────────────────────────────────────────────────────────┘

┌─ Opportunity Card (repeated) ───────────────────────────────────┐
│                                                                  │
│  NVDA  $214.75 +1.8%    Strong Buy    Conviction: 8.2/10       │
│  NVIDIA Corporation · Semiconductors · $5.3T                    │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━        │
│                                                                  │
│  SIGNAL: All horizons bullish. Upstream leaders +2.1%.          │
│  ACTION: Position hold 5-10 days. Consider adding on dips.     │
│  RISK: RSI 68 — near-term pullback possible.                   │
│                                                                  │
│  [1Y price chart sparkline ──────────────────╱──────]           │
│                                                                  │
│  P/E: 33.7x  PEG: 0.66  ROE: 114%  │  Undervalued             │
│  📊 Signal Radar [mini]  │  ✅ 5/6 layers agree                 │
│                                                                  │
│  [Show Evidence ▼]  [Analyze →]  [+ Portfolio]  [♡ Watch]      │
│                                                                  │
│  ┌─ Evidence (expanded) ────────────────────────────────────┐   │
│  │ ✅ P/E 33.7x below sector avg 68.4x                     │   │
│  │ ✅ PEG 0.66 — strong growth-adjusted value               │   │
│  │ ✅ 48/58 analysts rate Buy or higher                      │   │
│  │ ✅ Upstream semiconductor leaders showing momentum        │   │
│  │ ⚠️ Insider selling: 3 transactions in 90 days             │   │
│  │ ❌ P/B at 34.0x — elevated but typical for asset-light   │   │
│  │                                                           │   │
│  │ Sub-scores: Smart Money 4.2 | Signal Agreement 8.5 |     │   │
│  │ Sentiment 7.8 | Fundamentals 9.1 | Freshness 6.0 |       │   │
│  │ ML Direction 7.0                                          │   │
│  └───────────────────────────────────────────────────────────┘   │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

┌─ Watchlist Section ─────────────────────────────────────────────┐
│  YOUR WATCHLIST (4 tickers)              [+ Add Ticker]         │
│                                                                  │
│  Ticker │ Price    │ Change │ Signal              │ Action      │
│  AMD    │ $178.34  │ +2.1%  │ Entry in 1-3 days   │ [Analyze]  │
│  GOOG   │ $178.50  │ +0.4%  │ Monitoring           │ [Analyze]  │
│  META   │ $512.30  │ +1.1%  │ Sentiment improving  │ [Analyze]  │
│  AMZN   │ $198.20  │ +0.8%  │ AWS growth catalyst  │ [Analyze]  │
│                                                     [Remove ✕]  │
└─────────────────────────────────────────────────────────────────┘
```

### Smart Watchlist Insight Generator

```python
def generate_watchlist_insight(ticker, prices, buzz_signals, supply_chain, recommendations) -> dict:
    """Generate action-oriented insight for a watchlist ticker.

    Returns: {"signal": str, "action": str, "risk": str, "timeline": str}

    Rules (checked in priority order):
    1. Upstream leader moved >2% → "Entry window opening. [Leader] moved +X%."
    2. Insider buying cluster → "Insider buying detected. N buys in 30 days."
    3. Sentiment improving → "Sentiment improving from N sources."
    4. Buzz spike → "Mention volume spiked Xx above average."
    5. Price near support → "Price near 52-week low support."
    6. None → "Monitoring. No new catalysts."
    """
```

### Opportunity Card Components

Each card contains:
- **Header row:** Ticker + price + change + grade badge + conviction bar
- **Company line:** Full name + sector + market cap
- **SIGNAL/ACTION/RISK:** Three action-oriented sentences (from `generate_card_insight()`)
- **1-year sparkline:** `yf.download(ticker, period="1y")` → `mini_sparkline()` (wider version, 200px)
- **Key metrics row:** P/E, PEG, ROE + undervalued/overvalued badge from `valuation_z_score`
- **Signal radar mini:** Small 100px signal radar + "N/6 layers agree"
- **Expandable evidence:** Verdict bullets + sub-score breakdown
- **Action buttons:** Show Evidence, Analyze (→ Stock Analysis tab), + Portfolio, Watch/Unwatch

### Valuation Badge

Derived from existing `valuation_z_score` in `FundamentalFeatureEngineer`:
```python
def valuation_badge(peg, pe_vs_sector, fcf_yield) -> tuple[str, str]:
    """Returns (label, color)."""
    z = 0
    if peg and peg < 1: z += 2
    elif peg and peg < 2: z += 1
    if pe_vs_sector and pe_vs_sector < 0: z += 1  # below sector avg
    if fcf_yield and fcf_yield > 0.03: z += 1

    if z >= 3: return ("Undervalued", "#16A34A")
    if z >= 2: return ("Fair Value", "#F59E0B")
    return ("Overvalued", "#DC2626")
```

---

## Tab 3: My Portfolio

**Purpose:** "How are my holdings doing and what should I change?"

### Layout

```
┌─ Summary Row ───────────────────────────────────────────────────┐
│  Total Value        Today's P&L       Total P&L     Positions   │
│  $21,340            +$690 (+3.3%)     +$1,240       4           │
│                                        (+6.2%)                   │
└─────────────────────────────────────────────────────────────────┘

┌─ Portfolio vs Benchmark ────────────────────────────────────────┐
│  [Two-line chart: Your Portfolio (blue) vs S&P 500 (gray)]      │
│  Period: [1W] [1M] [3M] [1Y]                                    │
│  Your Portfolio: +6.2%   S&P 500: +12.1%   Diff: -5.9%         │
└─────────────────────────────────────────────────────────────────┘

┌─ Sector Allocation ────────────────────────────────────────────┐
│  [Pie chart: Technology 80%, Consumer Disc. 10%, Other 10%]     │
│  ⚠️ Heavy tech concentration. Consider diversifying into        │
│     healthcare or energy to reduce sector risk.                  │
└─────────────────────────────────────────────────────────────────┘

┌─ Positions Table ───────────────────────────────────────────────┐
│ Ticker│Shares│Avg Cost│Current │P&L      │Today  │Signal │     │
│ NVDA  │10    │$950    │$1,340  │+$3,900  │+$120  │✅ HOLD│ ⋮   │
│       │      │        │        │(+41.1%) │(+1.8%)│       │     │
│ AAPL  │20    │$190    │$195    │+$100    │+$20   │✅ HOLD│ ⋮   │
│       │      │        │        │(+2.6%)  │(+1.0%)│       │     │
│ MSFT  │15    │$430    │$445    │+$225    │+$30   │✅ HOLD│ ⋮   │
│       │      │        │        │(+3.5%)  │(+0.7%)│       │     │
│ TSLA  │5     │$180    │$176    │-$20     │-$5    │⚠️WATCH│ ⋮   │
│       │      │        │        │(-2.2%)  │(-0.6%)│       │     │
└─────────────────────────────────────────────────────────────────┘

⋮ menu per row: [Analyze] [Record Sell] [Remove]

┌─ Position Alerts ──────────────────────────────────────────────┐
│                                                                 │
│  TSLA — ATTENTION NEEDED                                        │
│  ⚠️ Down 2.2% from entry. Approaching stop-loss threshold.    │
│     Sentiment: neutral. No bullish catalysts in pipeline.       │
│     Recommendation: Monitor daily. Reduce if reaches -5%.      │
│                                                                 │
│  NVDA — PERFORMING WELL                                        │
│  ✅ All 3 horizons bullish. Conviction 8.2/10.                  │
│     Upstream semiconductor leaders showing continued momentum.  │
│     Hold duration: 5-10 more days. Next catalyst: earnings.    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─ AI Portfolio Summary (Gemini free tier) ──────────────────────┐
│  "Your portfolio is up 6.2% with NVDA as the clear winner at   │
│   +41%. All positions except TSLA show bullish signals. TSLA    │
│   is your only risk — approaching stop-loss with neutral        │
│   sentiment. The portfolio is heavily concentrated in tech      │
│   (80%) which amplifies both upside and downside. Consider      │
│   adding a healthcare or energy position for balance."          │
│                                                                 │
│  Generated Jun 4, 2026 · Powered by Google Gemini              │
│  Not financial advice.                                          │
└─────────────────────────────────────────────────────────────────┘

[+ Record Trade]                              [Trade History ▼]
Records a buy or sell to track performance.   Expandable.
```

### Position Signal Column

Derived from recommendation horizon_signals + MonitorHoldingsUseCase:

```python
def position_signal(ticker, recommendation, prices, holding) -> tuple[str, str]:
    """Returns (signal_text, color)."""
    # Check for sell signals first
    current = prices.get(ticker, {}).get("price", holding.purchase_price)
    pnl_pct = (current - holding.purchase_price) / holding.purchase_price * 100

    if pnl_pct <= -8: return ("SELL", "#DC2626")
    if pnl_pct <= -5: return ("WATCH", "#F59E0B")

    if recommendation:
        if recommendation.grade in ("strong_buy", "buy"): return ("HOLD", "#16A34A")
        if recommendation.grade == "hold": return ("HOLD", "#64748B")
        if recommendation.grade in ("may_sell", "immediate_sell"): return ("SELL", "#DC2626")

    return ("HOLD", "#64748B")
```

### AI Portfolio Summary

Gemini free tier call with structured prompt:

```python
PORTFOLIO_SUMMARY_PROMPT = """
Given this portfolio data, write a 3-4 sentence plain English summary.
Focus on: overall performance, best/worst positions, key risks, one actionable suggestion.

Portfolio:
{portfolio_data}

Market context:
{market_data}

Rules:
- Be specific with numbers
- End with one concrete suggestion
- Do NOT say "I recommend" — say "Consider..."
- Max 80 words
"""
```

Called via existing `GeminiEventClassifier` adapter pattern (Gemini free tier, no cost).

---

## Tab 4: Stock Analysis

**Purpose:** "Tell me everything about this ticker."

### Changes from Phase 5.4

1. **Fix rendering** — ensure `analyze_ticker()` works end-to-end with proper error display
2. **Add Gemini AI Deep Analysis button**
3. **Add 1-year price chart** at the top of Section 0
4. **Add undervalued/overvalued badge** to Section 0
5. **Add hold duration** prominently in verdict
6. **Ensure all 7 sections render with charts** — verify each Plotly chart actually displays

### Gemini AI Deep Analysis

Button below Section 0 verdict:

```
[AI Deep Analysis]
Powered by Google Gemini. Generates a plain-English investment
thesis based on all available signals. Free, no API key required.
```

Prompt to Gemini:

```python
AI_ANALYSIS_PROMPT = """
Write a concise investment analysis for {ticker} ({company_name}).

Current data:
- Price: ${price:.2f} ({change_pct:+.2f}% today)
- P/E: {pe:.1f}x (sector avg: {sector_pe:.1f}x)
- PEG: {peg:.2f}
- ROE: {roe:.1f}%
- Revenue growth: {rev_growth:.1f}%
- Earnings growth: {earn_growth:.1f}%
- Debt/Equity: {de:.1f}%
- FCF Yield: {fcf_yield:.1f}%
- Analyst consensus: {analyst_rec} ({analyst_count} analysts, target ${target:.0f})
- Insider activity: {insider_summary}
- Sentiment: {sentiment_summary}
- Supply chain: {supply_chain_summary}
- Our ML signal: {grade} (conviction {conviction:.1f}/10, hold {hold_duration})

Write 4-5 sentences covering:
1. Valuation assessment (cheap/fair/expensive relative to growth)
2. Key bullish catalyst
3. Key risk factor
4. Concrete suggestion (entry/hold/exit with timeframe)

Rules:
- Use specific numbers from the data above
- Say "Consider..." not "I recommend..."
- End with "Primary risk: ..."
- Max 100 words
- Do NOT add disclaimers — the UI adds those
"""
```

Output rendered in a styled card:

```html
<div class="ws-card" style="border-left:4px solid #7C3AED;padding:20px;">
  <div style="font-family:'DM Sans';font-weight:600;font-size:16px;margin-bottom:8px;">
    AI Deep Analysis — NVDA
  </div>
  <div style="font-size:15px;line-height:1.6;color:#374151;">
    {gemini_output}
  </div>
  <div style="font-size:12px;color:#94A3B8;margin-top:12px;">
    Generated {timestamp} · Powered by Google Gemini · AI-generated, not financial advice.
  </div>
</div>
```

### 1-Year Price Chart

At the top of Section 0, before the signal radar:

```python
# Fetch 1 year of daily prices
history = yf.download(ticker, period="1y")
fig = go.Figure(go.Scatter(
    x=history.index, y=history["Close"],
    mode="lines", fill="tozeroy",
    line=dict(color="#2563EB", width=2),
    fillcolor="rgba(37,99,235,0.06)",
))
fig.update_layout(
    height=250,
    yaxis=dict(title="Price ($)"),
    xaxis=dict(title=""),
    margin=dict(l=50, r=20, t=10, b=30),
)
```

---

## Tab 5: System Intelligence

**Purpose:** "How does this system work and how trustworthy is it?"

### Merges former Tab 5 (How It Works) + Tab 6 (Market Context)

### Layout

```
┌─ System Overview ───────────────────────────────────────────────┐
│  System Health 7/10 ●●●●●●●○○○                                  │
│  "5 signal layers active. Model baseline ~50% on mega-caps.     │
│   Conviction engine uses 6 dimensions. 1 trade tracked."        │
└─────────────────────────────────────────────────────────────────┘

┌─ Data Pipeline ─────────────────────────────────────────────────┐
│  Source         │ Status │ Last Run     │ Coverage              │
│  yfinance       │ ✅ Live │ Real-time    │ S&P 500 + NASDAQ-100 │
│  RSS Feeds      │ ✅ Live │ 2h ago       │ 15 feeds configured  │
│  Google Trends  │ ✅ Live │ 1d ago       │ 350 tickers          │
│  StockTwits     │ ✅ Live │ 2h ago       │ Live sentiment       │
│  SEC EDGAR      │ ✅ Live │ 4h ago       │ 13D + Form 4 filings │
│  GDELT          │ 🔴 Off  │ —            │ Future phase          │
│  Gemini AI      │ ✅ Free │ On-demand    │ Event classification  │
└─────────────────────────────────────────────────────────────────┘

┌─ Supply Chain Intelligence ─────────────────────────────────────┐
│  Group selector: [Semiconductors ▼]                              │
│                                                                  │
│  🏭 Semiconductors — Leaders drove +2.1% today                  │
│  "When equipment makers move >3%, chip makers follow in 1-3 days"│
│                                                                  │
│  Leaders          │ Today  │  Followers        │ Today           │
│  AMAT $198 +2.1%  │ ▲      │  AMD $178 +0.4%   │ ▲ (lagging)    │
│  LRCX $98 +1.8%   │ ▲      │  NVDA $214 +1.8%  │ ▲              │
│  KLAC $710 +1.2%  │ ▲      │  INTC $32 -0.3%   │ ▼ (diverging)  │
│                                                                  │
│  Insight: "Leaders are up +1.7% avg. INTC diverging from group. │
│            AMD may follow leaders upward within 1-3 trading days."│
│                                                                  │
│  [Cluster Bubble Chart — all groups selectable]                  │
│  Size: Day volume change  Color: Day price change               │
└─────────────────────────────────────────────────────────────────┘

┌─ Signal Performance (expander — expanded if data exists) ───────┐
│  [If outcomes exist: signal win rates + grade donut]             │
│  [If no outcomes: guided empty state with explanation]           │
│  "Track your first trade on the Portfolio tab to start building  │
│   signal intelligence. The system learns which signals actually  │
│   predict profitable trades."                                    │
└─────────────────────────────────────────────────────────────────┘

┌─ Adaptive Learning (expander) ──────────────────────────────────┐
│  [Weight history + learned rules + Run Learning Cycle]           │
│  [If empty: explain what happens when enough data accumulates]   │
└─────────────────────────────────────────────────────────────────┘

┌─ Model Baseline (expander) ─────────────────────────────────────┐
│  [Accuracy chart + ablation + SHAP + known limitations]          │
│  All existing content, but with criteria cards and better        │
│  empty state guidance.                                           │
└─────────────────────────────────────────────────────────────────┘
```

### Supply Chain Intelligence Improvements

1. **Group selector dropdown** — user picks which supply chain to view (not just semiconductors)
2. **Actionable insight sentence** — "AMD may follow leaders upward within 1-3 days"
3. **Table format** with live prices + today's change + direction arrows
4. **Cluster bubble chart** — selectable by group, sized by day volume change (not market cap), colored by price change
5. **Icons** per sector: 🏭 Semiconductors, 💻 Big Tech, ⚡ Energy, 💊 Pharma, 🚀 Space/Defense, 🛒 Retail, 🤖 AI, ☁️ Cloud, 🏦 Financials, 🏠 Housing

### Empty State Pattern

Every section with no data shows a **guided empty state** instead of blank space:

```html
<div class="ws-card" style="text-align:center;padding:2rem;background:#F8FAFC;">
  <div style="font-size:16px;font-weight:600;color:#1A202C;margin-bottom:8px;">
    No signal performance data yet
  </div>
  <div style="font-size:14px;color:#64748B;max-width:400px;margin:0 auto;">
    Record trades on the Portfolio tab to start building signal intelligence.
    After 10+ closed trades, the system shows which signals actually predict
    profitable outcomes.
  </div>
  <div style="margin-top:16px;">
    <a href="#" style="color:#2563EB;font-weight:500;">Go to Portfolio →</a>
  </div>
</div>
```

---

## New Domain Function: generate_card_insight()

File: `domain/insight_service.py` (NEW — pure domain function, no I/O)

```python
"""Insight generator — synthesizes multiple signals into action-oriented sentences.

Pure functions only. No external imports beyond stdlib.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class CardInsight:
    signal: str     # What's happening
    action: str     # What to do
    risk: str       # What could go wrong
    timeline: str   # When to act


def generate_card_insight(
    ticker: str,
    grade: str,
    conviction: float,
    horizon_signals: dict[str, str],
    peg: float | None,
    pe_vs_sector: float | None,
    sentiment_avg: float | None,
    upstream_leader_change: float | None,
    insider_net_buys: int | None,
    rsi: float | None,
) -> CardInsight:
    """Generate SIGNAL/ACTION/RISK/TIMELINE from available data."""

    # Signal — what's happening (pick highest-priority signal)
    signal_parts = []
    if all(s == "bullish" for s in horizon_signals.values()):
        signal_parts.append("All horizons bullish")
    elif any(s == "bullish" for s in horizon_signals.values()):
        bullish = [h for h, s in horizon_signals.items() if s == "bullish"]
        signal_parts.append(f"{', '.join(bullish)} horizon{'s' if len(bullish) > 1 else ''} bullish")

    if upstream_leader_change and upstream_leader_change > 2:
        signal_parts.append(f"Upstream leaders moved +{upstream_leader_change:.1f}%")
    if insider_net_buys and insider_net_buys > 0:
        signal_parts.append(f"{insider_net_buys} insider buys in 30 days")
    if sentiment_avg and sentiment_avg > 0.3:
        signal_parts.append("Strong positive sentiment")

    signal = ". ".join(signal_parts) if signal_parts else "Monitoring. No strong signals."

    # Action — what to do
    if grade in ("strong_buy", "buy") and conviction >= 7:
        action = f"Consider entry or adding. Conviction {conviction:.1f}/10."
    elif grade in ("strong_buy", "buy"):
        action = f"Watchlist candidate. Conviction {conviction:.1f}/10 — wait for stronger signal."
    elif grade == "hold":
        action = "Hold current position. No new catalysts."
    elif grade in ("may_sell", "immediate_sell"):
        action = "Review position. Bearish signals detected."
    else:
        action = "Monitor for developments."

    # Risk — what could go wrong
    risks = []
    if rsi and rsi > 70:
        risks.append(f"RSI {rsi:.0f} — overbought territory")
    elif rsi and rsi < 30:
        risks.append(f"RSI {rsi:.0f} — oversold, potential value trap")
    if peg and peg > 3:
        risks.append(f"PEG {peg:.1f} — expensive relative to growth")
    if sentiment_avg and sentiment_avg < -0.3:
        risks.append("Negative sentiment trend")
    if not risks:
        risks.append("General market risk")
    risk = ". ".join(risks) + "."

    # Timeline
    bullish_horizons = [h for h, s in horizon_signals.items() if s == "bullish"]
    if "2d" in bullish_horizons and "10d" not in bullish_horizons:
        timeline = "Short-term (2-3 days)"
    elif "10d" in bullish_horizons and "2d" not in bullish_horizons:
        timeline = "Medium-term (5-10 days)"
    elif len(bullish_horizons) == 3:
        timeline = "Hold until signal flip (10+ days)"
    else:
        timeline = "Monitor daily"

    return CardInsight(signal=signal, action=action, risk=risk, timeline=timeline)
```

This function lives in `domain/` because it's pure business logic — no I/O, no external imports. Fully testable with unit tests.

---

## New Domain Function: portfolio_health_score()

File: `domain/portfolio_service.py` (NEW — pure domain function)

```python
"""Portfolio-level intelligence — health scoring and diversification analysis.

Pure functions. No I/O. Computes aggregate portfolio metrics from position data.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class PortfolioHealth:
    score: int            # 0-10
    max_score: int        # 10
    summary: str          # Plain English
    diversification_warning: str | None
    benchmark_diff: float  # portfolio return - SPY return
    sector_allocation: dict[str, float]  # sector -> percentage


def compute_portfolio_health(
    positions: list[dict],   # [{"ticker", "value", "pnl_pct", "sector", "signal"}]
    spy_return: float,       # SPY return over same period
    portfolio_return: float, # Portfolio return over same period
) -> PortfolioHealth:
    """Compute portfolio health score (0-10) with diversification analysis."""
    score = 0

    # Performance (2 pts)
    if portfolio_return > 0: score += 1
    if portfolio_return > spy_return: score += 1

    # Diversification (3 pts)
    sectors = {}
    total_value = sum(p["value"] for p in positions) or 1
    for p in positions:
        s = p.get("sector", "Unknown")
        sectors[s] = sectors.get(s, 0) + p["value"] / total_value * 100

    max_sector_pct = max(sectors.values()) if sectors else 0
    if max_sector_pct <= 50: score += 1
    if len(positions) >= 3: score += 1
    max_position_pct = max((p["value"] / total_value * 100 for p in positions), default=0)
    if max_position_pct <= 40: score += 1

    # Risk (2 pts)
    at_risk = sum(1 for p in positions if p.get("pnl_pct", 0) <= -5)
    if at_risk == 0: score += 1
    sell_signals = sum(1 for p in positions if p.get("signal") in ("SELL", "WATCH"))
    if sell_signals == 0: score += 1

    # Signals (3 pts)
    bullish = sum(1 for p in positions if p.get("signal") == "HOLD")
    if bullish > len(positions) / 2: score += 1
    avg_conviction = sum(p.get("conviction", 5) for p in positions) / max(len(positions), 1)
    if avg_conviction > 5: score += 1
    if portfolio_return > 0 and at_risk == 0: score += 1  # positive and stable

    # Summary
    if score >= 8: summary = "Portfolio performing well with good diversification."
    elif score >= 5: summary = "Portfolio is stable but has areas for improvement."
    else: summary = "Portfolio needs attention — review positions and diversification."

    # Diversification warning
    div_warning = None
    if max_sector_pct > 50:
        top_sector = max(sectors, key=sectors.get)
        div_warning = f"Portfolio is {max_sector_pct:.0f}% {top_sector}. Consider diversifying into other sectors."

    return PortfolioHealth(
        score=score,
        max_score=10,
        summary=summary,
        diversification_warning=div_warning,
        benchmark_diff=portfolio_return - spy_return,
        sector_allocation=sectors,
    )
```

---

## Gemini Integration for Portfolio + Stock Analysis

File: `adapters/ml/gemini_insight.py` (NEW)

Reuses the existing Gemini free tier pattern from `gemini_event_classifier.py`.

```python
"""Gemini-powered insight generation — free tier, no API key cost.

Uses google.generativeai (same dependency as gemini_event_classifier.py).
Rate limit: 15 RPM on free tier.
"""
from __future__ import annotations
from loguru import logger


def generate_stock_insight(data: dict) -> str:
    """Generate AI analysis paragraph for a single ticker."""
    prompt = _build_stock_prompt(data)
    return _call_gemini(prompt)


def generate_portfolio_insight(data: dict) -> str:
    """Generate AI portfolio summary paragraph."""
    prompt = _build_portfolio_prompt(data)
    return _call_gemini(prompt)


def _call_gemini(prompt: str) -> str:
    """Call Gemini free tier. Returns generated text or fallback message."""
    try:
        import google.generativeai as genai
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        return response.text.strip()
    except ImportError:
        return "Gemini SDK not installed. Run: pip install google-generativeai"
    except Exception as exc:
        logger.warning(f"Gemini insight generation failed: {exc}")
        return f"AI insight unavailable: {exc}"


def _build_stock_prompt(data: dict) -> str:
    # ... structured prompt as described in Stock Analysis section above
    pass


def _build_portfolio_prompt(data: dict) -> str:
    # ... structured prompt as described in Portfolio section above
    pass
```

---

## Files Changed / Created

### New Files
| File | Purpose |
|------|---------|
| `domain/insight_service.py` | Pure functions: `generate_card_insight()`, `CardInsight` |
| `domain/portfolio_service.py` | Pure functions: `compute_portfolio_health()`, `PortfolioHealth` |
| `adapters/ml/gemini_insight.py` | Gemini free tier insight generation |
| `adapters/visualization/tabs/dashboard_tab.py` | Tab 1: Dashboard (new landing page) |
| `adapters/visualization/tabs/opportunities.py` | Tab 2: Opportunities (merged watchlist + conviction) |
| `adapters/visualization/tabs/system_intelligence.py` | Tab 5: System Intelligence (merged How It Works + Market Context) |
| `tests/test_insight_service.py` | Tests for insight generation |
| `tests/test_portfolio_service.py` | Tests for portfolio health |
| `tests/test_gemini_insight.py` | Tests for Gemini integration |
| `docs/adr/037-phase-55-ux-overhaul.md` | ADR |

### Modified Files
| File | Changes |
|------|---------|
| `adapters/visualization/dashboard.py` | 5 tabs (restructured) |
| `adapters/visualization/components/styles.py` | Font size increases, button subtitle CSS |
| `adapters/visualization/components/cards.py` | Add `action_item_card()`, `valuation_badge()` |
| `adapters/visualization/components/charts.py` | Add `portfolio_vs_benchmark()`, `sector_allocation_pie()` |
| `adapters/visualization/tabs/positions.py` | Full rewrite — table layout, alerts, AI summary |
| `adapters/visualization/tabs/stock_analysis.py` | Fix rendering, add Gemini AI, add 1Y chart, add valuation badge |
| `adapters/visualization/stock_analyzer.py` | Add `generate_gemini_insight()` integration |
| `adapters/visualization/action_runner.py` | Add `run_generate_actions()` for action queue |
| `adapters/visualization/data_loader.py` | Add loaders for action queue data |

### Deleted Files
| File | Reason |
|------|--------|
| `adapters/visualization/tabs/command_center.py` | Replaced by `dashboard_tab.py` |
| `adapters/visualization/tabs/watchlist.py` | Merged into `opportunities.py` |
| `adapters/visualization/tabs/model_confidence.py` | Merged into `system_intelligence.py` |
| `adapters/visualization/tabs/market_pulse.py` | Merged into `system_intelligence.py` |

---

## Implementation Phases

### Phase A: Domain Layer (pure functions, fully testable)
1. Create `domain/insight_service.py` + tests
2. Create `domain/portfolio_service.py` + tests
3. Create `adapters/ml/gemini_insight.py` + tests

### Phase B: Dashboard Tab (Tab 1 — landing page)
4. Create `dashboard_tab.py` with action queue + portfolio health + benchmark chart
5. Wire `generate_action_queue()` logic
6. Add `portfolio_vs_benchmark()` chart builder
7. Add `sector_allocation_pie()` chart builder

### Phase C: Opportunities Tab (Tab 2 — merged watchlist + conviction)
8. Create `opportunities.py` with rich cards + smart watchlist
9. Implement `generate_watchlist_insight()`
10. Add 1-year sparklines to cards
11. Add valuation badges
12. Add filter bar (All / Top Picks / Watchlist Only)

### Phase D: Portfolio Tab (Tab 3 — redesigned)
13. Rewrite `positions.py` — table layout + position alerts + AI summary
14. Wire Gemini portfolio summary
15. Add portfolio vs SPY benchmark chart
16. Add sector allocation pie

### Phase E: Stock Analysis Fixes (Tab 4)
17. Fix Stock Analysis rendering end-to-end (verify all 7 sections display)
18. Add 1-year price chart to Section 0
19. Add Gemini AI Deep Analysis button
20. Add valuation badge to Section 0

### Phase F: System Intelligence Tab (Tab 5 — merged)
21. Create `system_intelligence.py` merging How It Works + Market Context
22. Add supply chain group selector dropdown
23. Add actionable insight sentences to supply chain groups
24. Fix cluster bubble to be selectable by group + use volume instead of market cap
25. Add guided empty states with navigation links
26. Add sector icons

### Phase G: Polish + Router + Cleanup
27. Update `dashboard.py` to 5-tab router
28. Delete old tab files (command_center, watchlist, model_confidence, market_pulse)
29. Font size increases in styles.py
30. Button subtitles across all tabs
31. Update tests for new tab structure
32. Update CLAUDE.md, README, CONTEXT.md

---

## Success Criteria

1. **Dashboard tab:** Opens with Action Queue showing prioritized items from holdings + watchlist + portfolio advice
2. **Every card/row:** Has an action-oriented sentence (green/amber/red)
3. **Portfolio Health Score:** Single 0-10 number with dots, visible on Dashboard
4. **Portfolio vs SPY:** Two-line benchmark chart on Portfolio tab
5. **Sector allocation:** Pie chart with diversification warning if >50% one sector
6. **Stock Analysis:** "Run Analysis" works for any S&P 500 ticker, renders all 7 sections with charts
7. **AI Deep Analysis:** Gemini generates paragraph on Stock Analysis tab (free tier)
8. **AI Portfolio Summary:** Gemini generates portfolio paragraph (free tier)
9. **Smart Watchlist:** Each watchlist ticker shows system-generated insight, not user notes
10. **Supply Chain:** Group selector, actionable sentences, leader/follower table with prices
11. **Font sizes:** Readable across all tabs (16px base, 32px h1, 24px h2)
12. **Every button:** Has subtitle or tooltip explaining what it does
13. **Loading states:** Progress bar with step messages on every action >2 seconds
14. **Empty states:** Guided with explanation + navigation link (not blank)
15. **5 tabs:** Dashboard, Opportunities, My Portfolio, Stock Analysis, System Intelligence
16. **Tests:** 1000+ (996 existing + new domain + integration tests)
