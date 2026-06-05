# Phase 5.4 — SimplyWallSt-Grade Intelligence Platform Redesign

**Date:** 2026-06-04
**Status:** Approved (brainstorming complete)
**ADR:** 036
**Branch:** `feat/phase-5.4-dashboard-redesign`
**Predecessor:** Phase 5.3 (WealthSimple 5-tab redesign, 838 tests)

---

## Problem Statement

The dashboard has 838 tests, 101 features, 8 adapters, and 5 signal layers — but looks like a data engineering demo, not a financial intelligence platform. An interviewer opening the app sees 2 low-conviction stocks, no charts, raw dataframes, and empty states.

**Root causes identified during 2026-06-04 audit:**

1. **Conviction engine runs on 1 of 6 cylinders.** Three sub-scores (`sentiment_momentum`, `fundamental_basis`, `ml_direction`) are hardcoded `5.0` placeholders. `signal_agreement` checks only EDGAR features, not cross-layer agreement. `get_all_signals()` called with no args returns global EDGAR page, hitting ~2 of 350 tickers. `action_runner.py` truncates to first 50 tickers.

2. **Rich data exists but isn't surfaced.** 15 recommendations with grades/predicted returns/sentiment/reasoning sit unused in SQLite. 193 buzz signals across 35 tickers. 133 evaluation runs. yfinance provides 5 quarters of financials, 150 insider transactions, all fundamental ratios. None displayed.

3. **Almost no charts.** Only 3 of 6 built Plotly charts render. No price charts, no fundamental visualizations, no signal radars, no gauges. Stock recommender without charts is wrong.

4. **Silent bugs.** Monitor holdings uses purchase price as current price (stop-loss never triggers). Portfolio P&L hardcoded $0. Accuracy chart uses `np.linspace` interpolation. Missing CSS classes. Dead code everywhere.

---

## Vision

Match SimplyWallSt's visual quality and information density across ALL tabs while adding our unique ML/sentiment/conviction layer that they don't have.

**Three audiences served via progressive disclosure:**
- **Amateur investor (surface):** Self-explanatory verdicts, green/red checkmarks, plain English
- **Portfolio manager (middle):** Actionable opportunities, live P&L, hold duration, sell signals
- **Interviewer (deep):** 5-layer signal intelligence, honest statistics, adaptive learning, SHAP/ablation

**Design reference:** 28 SimplyWallSt screenshots analyzed (see `docs/design-references/REFERENCE_NOTES.md`).

---

## Design Language (applies to EVERY tab)

### Section Pattern

Every section across the entire app follows this structure:

```
Number + Title
┌─ Criteria Card ─────────────────────────────────────┐
│  Score N/M  ●●●○○  (green = pass, gray = fail)      │
│  Plain English summary sentence.                     │
└──────────────────────────────────────────────────────┘
[Chart — Plotly interactive]
✅ Positive finding in plain English
✅ Another positive
⚠️ Warning or caution
❌ Negative finding
```

### Reusable Components

All components go in `adapters/visualization/components/`. Each is a pure function returning HTML string or Plotly figure.

| Component | File | Signature | Returns |
|-----------|------|-----------|---------|
| `criteria_card` | `cards.py` | `(title: str, score: int, max_score: int, summary: str) -> str` | HTML with green/gray dots |
| `verdict_bullet` | `cards.py` | `(status: Literal["pass","warn","fail"], text: str) -> str` | HTML with ✅/⚠️/❌ |
| `signal_radar` | `charts.py` | `(scores: dict[str, float], max_val: float = 10) -> Figure` | Plotly radar chart, 5-6 axes |
| `gauge_chart` | `charts.py` | `(value: float, min_v: float, max_v: float, label: str, thresholds: tuple) -> Figure` | Plotly semicircle gauge (green/amber/red zones) |
| `comparison_bars` | `charts.py` | `(items: list[dict], highlight: str) -> Figure` | Horizontal bar chart with one bar highlighted |
| `price_range_bar` | `cards.py` | `(current: float, low: float, high: float, target: float) -> str` | HTML range indicator with position marker |
| `metric_kpi` | `cards.py` | `(label: str, value: str, context: str, color: str) -> str` | HTML big number with context |
| `mini_sparkline` | `cards.py` | `(prices: list[float], color: str = "#2563EB") -> str` | SVG inline sparkline (no Plotly overhead) |
| `ownership_pie` | `charts.py` | `(institutional: float, insider: float, public: float) -> Figure` | Plotly donut |
| `treemap_chart` | `charts.py` | `(data: list[dict], color_field: str) -> Figure` | Plotly treemap |
| `timeline_chart` | `charts.py` | `(events: list[dict], value_field: str) -> Figure` | Plotly scatter with markers |
| `loading_stepper` | `progress.py` | `(steps: list[str], current: int) -> str` | HTML progress bar with step messages |
| `insider_bars` | `charts.py` | `(transactions: list[dict]) -> Figure` | Plotly bar: buys green, sells red, by quarter |
| `candlestick_chart` | `charts.py` | `(ohlcv: pd.DataFrame) -> Figure` | Plotly candlestick + volume subplot |
| `financials_line` | `charts.py` | `(quarterly_data: pd.DataFrame, metrics: list[str]) -> Figure` | Multi-line chart for revenue/earnings/etc |

### Color System

```python
COLORS = {
    "pass": "#16A34A",      # green — positive/bullish/pass
    "fail": "#DC2626",      # red — negative/bearish/fail
    "warn": "#F59E0B",      # amber — caution/neutral
    "accent": "#2563EB",    # blue — primary accent
    "muted": "#64748B",     # gray — secondary text
    "bg_card": "#FFFFFF",   # white card background
    "bg_page": "#F8FAFC",   # light gray page background
    "text_primary": "#0F172A",
    "text_secondary": "#475569",
    "purple": "#7C3AED",    # sentiment layer
    "orange": "#EA580C",    # cross-asset layer
    "teal": "#059669",      # fundamental layer
}
```

### Loading States

Every action button (Scan Now, Run Full Cycle, Run Analysis, Run Backtest, Run Learning Cycle) uses progressive loading:

```python
LOADING_STEPS = {
    "conviction_scan": [
        "Scanning SEC EDGAR filings...",
        "Fetching market data...",
        "Analyzing sentiment signals...",
        "Computing fundamentals...",
        "Scoring conviction across 6 dimensions...",
        "Ranking opportunities...",
        "Preparing results...",
    ],
    "stock_analysis": [
        "Fetching price history...",
        "Loading fundamental data...",
        "Computing technical indicators...",
        "Checking sentiment signals...",
        "Querying insider transactions...",
        "Computing conviction score...",
        "Building charts...",
        "Generating verdicts...",
    ],
    "full_cycle": [
        "Scanning RSS feeds...",
        "Querying Google Trends...",
        "Checking StockTwits sentiment...",
        "Running conviction scan...",
        "Tracking recommendation outcomes...",
        "Computing portfolio signals...",
        "Done.",
    ],
}
```

Rendered via `loading_stepper()` component with Streamlit `st.progress()` + `st.empty()`.

---

## Tab Structure (6 tabs)

```
Today's Opportunities | Watchlist | My Portfolio | Stock Analysis | How It Works | Market Context
```

"Stock Analysis" is NEW (replaces nothing — we go from 5 to 6 tabs).

---

## Tab 1: Today's Opportunities

### Two Modes

**Mode A — Market Overview (fallback).** Shown when conviction scan has < 5 results.

**Mode B — Conviction Feed.** Shown when >= 5 conviction-scored results exist.

### Common Elements (both modes)

**Scrolling Ticker Bar** (top of page, above tabs):
- Fetches SPY, QQQ, DIA, IWM, VIX, 10Y yield via yfinance batch
- Shows: `SPY $545.23 ▲0.56%  |  QQQ $487.12 ▲0.81%  |  VIX 14.2 ▼3.1%`
- CSS marquee animation or static row — ticker data batch-cached 5 min
- Green text = up, red = down

**3-Panel Hero** (improved from current):
- **Market Panel:** SPY price + change + SPY intraday sparkline chart (Plotly, small) + market status (OPEN/CLOSED) + mood
- **Portfolio Panel:** Total value + today's P&L (green/red) + total P&L + position count. **Live prices required** — batch-fetch holdings tickers.
- **Signal Panel:** Number of opportunities + top pick ticker + conviction score + watchlist alert count (actual alerts, not item count)

### Mode A — Market Overview

When conviction scan returns < 5 results:

1. **Banner:** "Market overview shown — conviction data is stale. [Scan Now] for ranked opportunities."

2. **Top 15 Picks (from `recommendations` table):**
   - Each pick is a styled card (not a dataframe row):
     - Ticker + company name + grade badge (Strong Buy/Buy/Hold green→amber→red)
     - Composite score + predicted 5d return + confidence
     - Mini signal radar (small, inline)
     - Horizon signals: 2d/5d/10d as bullish/neutral/bearish pills
     - Hold duration derived from horizon pattern
     - Reasoning text from DB
     - [Analyze →] button linking to Stock Analysis tab
   - Cards sorted by composite_score descending

3. **Market Heatmap:**
   - Plotly treemap: all holdings + watchlist + recommendation tickers
   - Sized by market cap (from yfinance batch cache)
   - Colored by day change (green = up, red = down)
   - Click a cell → navigates to Stock Analysis for that ticker

### Mode B — Conviction Feed

When conviction scan returns >= 5 results:

1. **Opportunity Cards** (richer than current compact_card):
   - Ticker + price + day change
   - Conviction score bar + action badge (BUY/WATCH/SELL)
   - **Mini signal radar** showing 6 sub-score dimensions
   - Hold duration recommendation
   - Top 2 evidence bullets + top 1 risk bullet
   - Freshness indicator
   - [Analyze →] [+ Watchlist] [+ Portfolio] buttons
   - Expandable: full evidence list + all risks

2. **Bottom actions:** Scan Now (primary) | Last scanned timestamp | Run Full Cycle

### Data Requirements

- `load_recommendations(db_path)` — already exists but never called from any tab
- `load_spy_sparkline()` — exists, need to render chart instead of just scalars
- Batch price fetch for holdings + watchlist + recommendation tickers
- Conviction scan results from ScanCache

---

## Tab 2: Watchlist

### Layout

**Header row:** "Watchlist (N tickers)" + [+ Add Ticker] button (opens form)

**Per-ticker card** (replaces raw dataframe):

```
┌──────────────────────────────────────────────────────┐
│  AMD  $178.34  +2.1%  ▲                           ✕  │
│  [30-day sparkline ─────────────╱──]                  │
│  P/E: 179x · PEG: 5.2 · Mkt Cap: $289B · RSI: 48   │
│  Conviction: 6.2/10 — WATCH                          │
│  ┌─ Criteria 3/5 ●●●○○ ──────────────────────────┐  │
│  │ Fundamentals strong but momentum weak.          │  │
│  │ Sentiment improving from 3 sources.             │  │
│  └────────────────────────────────────────────────┘  │
│  ✅ P/E below sector avg  ⚠️ High volatility regime  │
│  Watching since: Jun 2 · Reason: upstream signal NVDA │
│  [Analyze →]  [Add to Portfolio]                      │
└──────────────────────────────────────────────────────┘
```

**Remove:** ✕ button on each card. Calls existing `SQLiteStore.remove_watchlist()`.

**Add form** (replaces current inline form):
- Ticker input (validates against sp500.txt + nasdaq100.txt)
- Reason dropdown: Earnings play | Sector rotation | Upstream signal | Technical setup | Insider activity | Momentum | Custom
- Optional notes text field
- [Add to Watchlist] button

### Data Requirements

- `load_watchlist(db_path)` — exists
- Batch price fetch for all watchlist tickers (yfinance download, cached 5min)
- `yfinance.Ticker.info` for P/E, PEG, market cap per ticker
- Conviction score if available from last scan
- RSI from `compute_indicators()` via yfinance adapter

---

## Tab 3: My Portfolio

### Layout

**Portfolio Summary Card:**
```
┌──────────────────────────────────────────────────────┐
│  Total Value        Today's P&L       Total P&L      │
│  $21,340            +$690 (+3.3%)     +$1,240 (+6.2%)│
│  4 positions        Best: NVDA +41%   Worst: TSLA -2%│
│  ┌─ Portfolio Value Over Time ──────────────────────┐│
│  │  [30-day line chart: portfolio value each day]    ││
│  │  [computed from holdings × daily closing prices]  ││
│  └──────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────┘
```

**Position Cards** (one per holding):
```
┌──────────────────────────────────────────────────────┐
│  NVDA  10 shares │ Cost: $950 │ Current: $1,340      │
│  P&L: +$3,900 (+41.1%)  │  Today: +$120 (+1.8%)     │
│  [sparkline]                                          │
│  ┌─ Position Health 4/5 ●●●●○ ────────────────────┐ │
│  │ Strong position. All horizons bullish. Smart      │ │
│  │ money activity detected. Consider holding.        │ │
│  └──────────────────────────────────────────────────┘ │
│  ✅ All 3 horizons bullish (from recommendations)     │
│  ✅ Insider buying cluster detected (SEC EDGAR)       │
│  ⚠️ RSI 68 — approaching overbought territory        │
│  Suggested hold: 5-10 days │ [Record Sell] [Analyze →]│
└──────────────────────────────────────────────────────┘
```

**P&L Bar Chart:**
- Horizontal bars per position
- Green = profit, red = loss
- Sorted by P&L descending

**Closed Positions** (if any trade_outcomes exist):
- Styled table with colored return cells (existing pattern, keep)
- Win rate + total return summary

**Record Trade** (collapsed expander at bottom):
- Buy/Sell radio + Ticker + Price + Qty + Date
- Same as current but in a collapsible section

**Portfolio Allocation Pie:**
- Donut chart showing % of portfolio in each position
- Colored by sector if available

### Data Requirements

- `load_holdings(db_path)` — exists
- `load_trades(db_path)` + `load_outcomes(db_path)` — exists
- Batch price fetch for all holding tickers
- Historical daily prices for portfolio value chart (yfinance download with `period="1mo"`)
- Recommendation data for horizon signals per holding ticker
- Sell signal detection via `MonitorHoldingsUseCase` (with REAL current prices, not purchase price)

---

## Tab 4: Stock Analysis (NEW — the showpiece)

### Entry

Search bar at top: `[Enter ticker: ____]  [Run Analysis]`

When ticker is entered and analysis runs:
1. Progressive loading with `loading_stepper` (8 steps, ~5-10 seconds total)
2. All data fetched in parallel where possible
3. Results cached in `st.session_state` keyed by ticker

### Section 0: Our Verdict

**Signal Radar** — 6-axis Plotly radar chart (each axis 0-10):
- Technical: `composite = (RSI_normalized + MACD_signal + SMA_alignment) / 3 * 10`. RSI < 30 = 2, 30-50 = 5, 50-70 = 7, > 70 = 9. MACD positive = 7, negative = 3. Price > SMA50 > SMA200 = 9, inverted = 2.
- Sentiment: `mean(sentiment_raw) * 5 + 5` from buzz_signals (maps [-1,1] to [0,10]). No data = 5.0.
- Fundamental: same formula as conviction `fundamental_basis` sub-score (PEG + FCF yield + ROE composite).
- Cross-Asset: if in supply chain group and leader momentum positive = 8, negative = 3. Not in group = 5.0.
- Event-Causal: if recent events (7d) with positive sentiment = 7-9, negative = 2-4. No events = 5.0.
- Smart Money: same formula as conviction `smart_money` sub-score (13D count + insider cluster + activist).

**Verdict Card:**
- Grade badge: Strong Buy / Buy / Hold / May Sell / Immediate Sell
- Conviction score: N/10
- Hold duration: "Short hold (2-3 days)" / "Position hold (5-10 days)" / "Long hold (10+ days)"
- Derived from `horizon_signals`:
  - All bullish → "Hold until flip" (10+ days)
  - 2d bullish, 5d/10d neutral → "Short hold (2-3 days)"
  - 2d neutral, 5d/10d bullish → "Position hold (5-10 days)"
  - Mixed → "Monitor daily"

**Side-by-side: Our System vs Wall Street:**

| | Our ML System | Analyst Consensus |
|---|---|---|
| Verdict | Strong Buy 8.2/10 | Strong Buy (58 analysts) |
| Time horizon | Hold 5-10 days | 12-month target |
| Target | +3.2% (5-day) | $298 (+39%) |
| Confidence | High (5/6 layers agree) | Low (wide analyst spread) |

**Action buttons:** [+ Add to Watchlist] [+ Add to Portfolio]

### Section 1: Valuation

**Criteria Card:** Valuation Score N/6. Checks:
1. P/E below sector average? (sector peers batch-fetched)
2. PEG < 2? (growth-adjusted value)
3. P/B reasonable for sector?
4. Analyst consensus ≥ Buy?
5. Price below analyst mean target?
6. FCF yield > 3%?

**Charts:**
- **P/E vs Sector Peers** — horizontal bar chart. Highlight current ticker. Show peer average line. Peers = 4-5 tickers from same supply chain group or sector ETF constituents.
- **Analyst Price Target Range** — `price_range_bar()`: current price marker on low—mean—high range bar.

**Verdict bullets:** ✅/⚠️/❌ for each of the 6 checks with plain English explanation.

### Section 2: Growth

**Criteria Card:** Growth Score N/6. Checks:
1. Revenue growth > 0?
2. Revenue growth > industry average?
3. Earnings growth > 0?
4. Earnings growth > industry average?
5. Revenue growth accelerating? (current > sector)
6. Positive operating margin trend?

**Charts:**
- **Company vs Industry vs Market** — `comparison_bars()` for earnings growth + revenue growth. Three bars each: Company (blue), Industry (teal), Market (gray).
- **Quarterly Revenue & Earnings** — `financials_line()` from `t.quarterly_financials`. Lines: Total Revenue, Net Income, Gross Profit. 5 quarters.

**Verdict bullets** per check.

### Section 3: Past Performance

**Criteria Card:** Performance Score N/6. Checks:
1. ROE > 15%?
2. ROE > industry average?
3. Gross margin > 40%?
4. Operating margin > 20%?
5. Profit margin improving?
6. Earnings growth > 10% YoY?

**Charts:**
- **ROE Gauge** — `gauge_chart()` with zones: 0-10% red, 10-20% amber, 20%+ green. Industry avg marker.
- **Margins Comparison** — `comparison_bars()`: gross margin, operating margin, profit margin. Company vs industry.
- **Revenue & Earnings History** — `financials_line()` from quarterly data.

**Verdict bullets** per check.

### Section 4: Financial Health

**Criteria Card:** Health Score N/6. Checks:
1. D/E < 100%?
2. Current ratio > 1.5?
3. Cash > total debt?
4. Free cash flow positive?
5. D/E improving (decreasing)?
6. Interest coverage adequate? (EBIT/interest expense)

**Charts:**
- **Debt-to-Equity Gauge** — `gauge_chart()` with zones: 0-50% green, 50-100% amber, 100%+ red.
- **Cash vs Debt Bar** — simple horizontal comparison bar.

**Verdict bullets** per check.

### Section 5: Ownership & Smart Money

**Criteria Card:** Ownership Score N/5. Checks:
1. Institutional ownership > 50%?
2. Insider ownership > 1%?
3. Net insider buying in past 3 months?
4. Any 13D activist filings?
5. Low insider selling velocity?

**Charts:**
- **Ownership Pie** — `ownership_pie()`: institutional (from `heldPercentInstitutions`), insider (from `heldPercentInsiders`), public (remainder).
- **Insider Trading Timeline** — `insider_bars()`: from `yf.Ticker.insider_transactions` (150 rows for NVDA). Bars by quarter: green = buys, red = sells. Sized by dollar value.

**Verdict bullets** per check.

### Section 6: Sentiment & Signals

**Criteria Card:** Sentiment Score N/5. Checks:
1. Sentiment positive (avg > 0)?
2. Multiple sources agree?
3. Buzz volume above average?
4. No negative spike in past 7 days?
5. Sentiment-price divergence bullish?

**Charts:**
- **Buzz Volume Timeline** — `timeline_chart()` from `buzz_signals` table: x = date, y = mention_count, colored by source.
- **Sentiment Score Trend** — line chart from `buzz_signals`: x = date, y = sentiment_raw, by scorer.

**Verdict bullets** per check. If no buzz data for this ticker: "No sentiment data available — run a daily scan to collect."

### Section 7: Supply Chain & Cross-Asset

**Criteria Card:** Cluster Score N/4. Checks:
1. Ticker is in a known supply chain group?
2. Leader stocks showing positive momentum?
3. Cluster momentum positive (peers moving up)?
4. No supply chain divergence detected?

**Charts:**
- **Cluster Bubble Chart** — `treemap_chart()` or Plotly scatter: all tickers in the same supply chain group, sized by market cap, colored by day change. Current ticker highlighted.
- Leader/follower relationship text.

**Verdict bullets** per check. If not in any cluster: "This ticker is not in a tracked supply chain group."

### Data Fetching Strategy

All data for one ticker fetched in parallel:
```python
# Parallel fetches (each ~1-2 sec)
info = yf.Ticker(ticker).info                    # fundamentals
history = yf.download(ticker, period="6mo")       # OHLCV
quarterly = yf.Ticker(ticker).quarterly_financials # 5 quarters
balance = yf.Ticker(ticker).quarterly_balance_sheet
insider_txns = yf.Ticker(ticker).insider_transactions
major_holders = yf.Ticker(ticker).major_holders
recommendations = yf.Ticker(ticker).recommendations

# From our DB (instant)
buzz_signals = store.get_buzz_signals(ticker=ticker)
recommendation = store.get_recommendations(week_start=latest_week, ticker=ticker)
edgar_signals = edgar_adapter.get_all_signals(ticker=ticker, since_date=90_days_ago)

# From config (instant)
supply_chain_group = find_cluster_for_ticker(ticker, supply_chain_yaml)
sector_peers = get_sector_peers(ticker, supply_chain_yaml, sp500_tickers)
```

Cached in `st.session_state[f"analysis_{ticker}"]` — rerun analysis button clears cache.

---

## Tab 5: How It Works (enhanced)

### Fixes
- Fix `.verdict-card`, `.dashboard-card` missing CSS
- Fix "Track your first trade" overlapping Signal Performance
- Replace `np.linspace` fake fold data with real per-fold accuracy from backtest JSON
- Wire `grade_donut` chart (dead code) into Signal Performance section
- Wire `sector_heatmap` chart (dead code) into new Sector Breakdown section

### Enhancements
- Each expander section gets a criteria card header
- Signal Performance: add grade_donut + per-signal win rate bar chart
- System Learning: add weight evolution line chart (when data exists)
- Model Baseline: show all 3 horizons simultaneously (not radio button), each with its own accuracy + verdict
- Ablation: keep existing + add explanation of what ablation means for non-technical audience

---

## Tab 6: Market Context (enhanced)

### Data Pipeline
- Replace hardcoded status strings with real timestamps from last scan
- Query `buzz_signals` for latest `fetched_at` per source
- GDELT status: check if adapter is actually configured (mark it correctly)

### Supply Chain Cascades
- **Live prices for all leader/follower tickers** (batch cached)
- Color tags: green if up today, red if down
- Add **day change %** next to each ticker tag
- Each group gets a mini criteria card: "Semiconductors: Leaders ▲, Followers lagging. Potential cascade opportunity."

### Cluster Bubble Chart (NEW)
- Full treemap of all supply chain tickers
- Sized by market cap, colored by day change
- Grouped by supply chain group

### Event Impact Decay
- Keep existing interactive sliders
- Add real event examples if available from buzz_signals or evaluation_runs

### Sector Heatmap (wire dead chart)
- Wire `sector_heatmap` from charts.py
- Show S&P 500 sectors with day performance

---

## Conviction Engine Fixes

### File: `application/conviction_use_case.py`

**Fix 1: Per-ticker EDGAR queries.**
Change line 70 from:
```python
all_signals: list[SmartMoneySignal] = self._smart_money.get_all_signals()
```
To: call `get_all_signals(ticker=ticker)` inside `_score_ticker()` loop, with batch fallback if rate-limited.

**Fix 2: Wire real sub-scores.** Replace `_compute_sub_scores()` (lines 163-205):

```python
def _compute_sub_scores(
    self,
    ticker: str,
    features: dict[str, float],
    ticker_signals: list[SmartMoneySignal],
    scan_time: datetime,
    buzz_signals: list | None = None,
    ticker_info: dict | None = None,
    recommendation: object | None = None,
) -> dict[str, float]:
    # smart_money: from EDGAR features (keep existing logic)
    sm_score = ...  # existing

    # signal_agreement: cross-layer check
    layers_firing = 0
    if sm_score > 2: layers_firing += 1
    if buzz_signals and any(b.sentiment_raw > 0 for b in buzz_signals): layers_firing += 1
    if ticker_info and ticker_info.get("pegRatio", 99) < 2: layers_firing += 1
    if recommendation and recommendation.grade in ("strong_buy", "buy"): layers_firing += 1
    signal_agreement = min(layers_firing / 4.0 * 10.0, 10.0)

    # sentiment_momentum: from buzz_signals
    if buzz_signals:
        recent = [b for b in buzz_signals if (scan_time - b.fetched_at).days < 7]
        avg_sentiment = mean([b.sentiment_raw for b in recent]) if recent else 0
        sentiment_momentum = max(1, min(10, 5 + avg_sentiment * 5))
    else:
        sentiment_momentum = 5.0  # neutral when no data

    # fundamental_basis: from yfinance ticker_info
    if ticker_info:
        peg = ticker_info.get("pegRatio", 3)
        fcf_yield = (ticker_info.get("freeCashflow", 0) / max(ticker_info.get("marketCap", 1), 1))
        roe = ticker_info.get("returnOnEquity", 0)
        fundamental_basis = min(10, max(1,
            (3 if peg < 1 else 2 if peg < 2 else 1 if peg < 3 else 0) +
            (3 if fcf_yield > 0.05 else 2 if fcf_yield > 0.02 else 1 if fcf_yield > 0 else 0) +
            (4 if roe > 0.2 else 3 if roe > 0.15 else 2 if roe > 0.1 else 1)
        ))
    else:
        fundamental_basis = 5.0

    # ml_direction: from stored recommendation
    if recommendation:
        score_map = {"strong_buy": 9, "buy": 7, "hold": 5, "may_sell": 3, "immediate_sell": 1}
        ml_direction = score_map.get(recommendation.grade, 5)
    else:
        ml_direction = 5.0  # neutral when no model data

    # temporal_freshness: keep existing logic

    return {
        "smart_money": sm_score,
        "signal_agreement": signal_agreement,
        "temporal_freshness": freshness,
        "sentiment_momentum": sentiment_momentum,
        "fundamental_basis": fundamental_basis,
        "ml_direction": ml_direction,
    }
```

**Fix 3: Constructor accepts additional data sources.**
```python
class ConvictionScoringUseCase:
    def __init__(
        self,
        smart_money: object,
        tickers: list[str],
        weights: ConvictionWeights,
        store: object | None = None,      # SQLiteStore for buzz_signals + recommendations
        market_data: object | None = None,  # YFinanceAdapter for ticker_info
        pinned: set[str] | None = None,
        top_n: int = 15,
    ) -> None:
```

### File: `adapters/visualization/action_runner.py`

**Fix 4: Scan all tickers, not just 50.**
Remove `tickers[:50]` truncation. Use full universe.

**Fix 5: Pass store + market_data to ConvictionScoringUseCase.**
Wire `SQLiteStore` and `YFinanceAdapter` into the conviction scan pipeline.

**Fix 6: Fix `run_monitor_holdings` to use live prices.**
Replace `get_price_stub` (returns purchase_price) with actual `yf.download()` batch fetch.

### File: `domain/conviction_service.py`

**Fix 7: Lower min_score or add fallback.**
When all tickers score below `min_score=3.0`, return top 15 by score regardless (with a "low conviction" warning flag).

---

## Batch Price Cache

New file: `adapters/visualization/price_cache.py`

```python
"""Batch price cache — yfinance.download() for multiple tickers, cached with TTL."""

import streamlit as st
import yfinance as yf
from datetime import datetime
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

def is_market_hours() -> bool:
    now = datetime.now(ET)
    return now.weekday() < 5 and time(9, 30) <= now.time() < time(16, 0)

@st.cache_data(ttl=300 if is_market_hours() else 3600)
def batch_fetch_prices(tickers: tuple[str, ...]) -> dict[str, dict]:
    """Fetch current prices for multiple tickers in one yfinance call.

    Returns dict[ticker, {"price": float, "change_pct": float, "volume": int}].
    """
    if not tickers:
        return {}
    data = yf.download(list(tickers), period="2d", group_by="ticker", progress=False)
    results = {}
    for ticker in tickers:
        try:
            if len(tickers) == 1:
                df = data
            else:
                df = data[ticker]
            if len(df) >= 2:
                current = float(df["Close"].iloc[-1])
                prev = float(df["Close"].iloc[-2])
                change_pct = (current - prev) / prev * 100
                results[ticker] = {"price": current, "change_pct": change_pct}
            elif len(df) == 1:
                results[ticker] = {"price": float(df["Close"].iloc[-1]), "change_pct": 0.0}
        except Exception:
            pass
    return results

@st.cache_data(ttl=300)
def fetch_ticker_info(ticker: str) -> dict:
    """Fetch full ticker info (fundamentals, analyst data)."""
    return yf.Ticker(ticker).info

@st.cache_data(ttl=3600)
def fetch_quarterly_financials(ticker: str) -> tuple:
    """Fetch quarterly financials + balance sheet."""
    t = yf.Ticker(ticker)
    return t.quarterly_financials, t.quarterly_balance_sheet, t.quarterly_cashflow

@st.cache_data(ttl=3600)
def fetch_insider_transactions(ticker: str) -> list[dict]:
    """Fetch insider transactions."""
    t = yf.Ticker(ticker)
    df = t.insider_transactions
    if df is not None and not df.empty:
        return df.to_dict("records")
    return []

@st.cache_data(ttl=300)
def fetch_index_prices() -> dict[str, dict]:
    """Fetch major index prices for scrolling ticker bar."""
    return batch_fetch_prices(("SPY", "QQQ", "DIA", "IWM", "^VIX", "^TNX"))
```

---

## Bug Fixes (alongside redesign)

| Bug | File | Fix |
|-----|------|-----|
| Portfolio P&L hardcoded $0 | `command_center.py` | Compute from live prices |
| "N watchlist alerts" = item count | `command_center.py` | Count tickers with active sell signals or conviction changes |
| Accuracy chart uses np.linspace | `model_confidence.py` | Parse real per-fold data from backtest JSON |
| Missing CSS: .hero-label, .hero-value, .hero-sub | `styles.py` | Add definitions |
| Missing CSS: .verdict-card, .verdict-positive/negative/neutral | `styles.py` | Add definitions |
| Missing CSS: .dashboard-card | `styles.py` | Add definition or replace usage |
| run_monitor_holdings uses purchase price | `action_runner.py` | Use batch_fetch_prices() |
| Track your first trade overlaps Signal Performance | `model_confidence.py` | Fix spacing/z-index |

---

## Dead Code Cleanup

| Dead code | File | Action |
|-----------|------|--------|
| `opportunity_cards.py` (entire file) | `components/` | Delete — superseded by `compact_card.py` |
| `render_hero_banner()` | `metrics.py` | Delete |
| `render_action_card()` | `metrics.py` | Delete |
| `render_signal_layer_card()` | `metrics.py` | Delete |
| `render_pick_card()` | `metrics.py` | Delete — unless reimplemented for new design |
| `grade_donut()` | `charts.py` | Wire into How It Works tab |
| `sector_heatmap()` | `charts.py` | Wire into Market Context tab |
| `load_event_sector_mapping()` | `data_loader.py` | Delete — never called |
| `load_scan_timestamp()` | `data_loader.py` | Delete — ScanCache handles this |
| `direction_icon()`, `urgency_badge()` | `formatters.py` | Delete — superseded by CSS pills |
| `grade_color()` | `formatters.py` | Keep if used by new charts |
| Legacy helpers in model_confidence.py | `tabs/model_confidence.py` | Delete `_render_signal_report_card` and `_render_learning_dashboard` (lines 362-384) |

---

## New Files

| File | Purpose |
|------|---------|
| `adapters/visualization/price_cache.py` | Batch yfinance price fetching with TTL cache |
| `adapters/visualization/components/cards.py` | Criteria card, verdict bullet, price range bar, metric KPI, mini sparkline |
| `adapters/visualization/tabs/stock_analysis.py` | New Tab 4: full SWST-grade deep analysis |
| `adapters/visualization/stock_analyzer.py` | Data fetching + computation for Stock Analysis (keeps tab file focused on rendering) |
| `docs/adr/036-phase-54-dashboard-redesign.md` | ADR documenting this redesign |

---

## Modified Files

| File | Changes |
|------|---------|
| `adapters/visualization/dashboard.py` | 6 tabs (add Stock Analysis) |
| `adapters/visualization/components/styles.py` | Add missing CSS + new component classes |
| `adapters/visualization/components/charts.py` | Add signal_radar, gauge_chart, comparison_bars, ownership_pie, treemap_chart, timeline_chart, insider_bars, candlestick_chart, financials_line |
| `adapters/visualization/components/progress.py` | Add loading_stepper with step messages |
| `adapters/visualization/components/formatters.py` | Cleanup dead functions |
| `adapters/visualization/components/compact_card.py` | Add mini signal radar + hold duration + action buttons |
| `adapters/visualization/tabs/command_center.py` | Two-mode layout + market overview + scrolling ticker bar |
| `adapters/visualization/tabs/watchlist.py` | Full card layout + live prices + remove button |
| `adapters/visualization/tabs/positions.py` | Portfolio summary + P&L chart + position cards with verdicts |
| `adapters/visualization/tabs/model_confidence.py` | Fix bugs + wire dead charts + criteria cards |
| `adapters/visualization/tabs/market_pulse.py` | Live prices + cluster bubble + sector heatmap + real timestamps |
| `adapters/visualization/action_runner.py` | Fix conviction scan (all tickers, pass store+market_data), fix monitor_holdings |
| `adapters/visualization/data_loader.py` | Remove dead loaders, add new loaders for analysis |
| `application/conviction_use_case.py` | Wire real sub-scores, accept store + market_data |
| `domain/conviction_service.py` | Add fallback when all scores below min_score |
| `config/markets/us.yaml` | Update conviction weights if needed |

---

## Testing Strategy

### New Tests (estimated ~50-80 new tests)

| Category | Tests | What's tested |
|----------|-------|---------------|
| Conviction sub-scores | 12 | Each dimension returns real values, not 5.0 placeholder |
| Price cache | 6 | Batch fetch, TTL, missing ticker handling |
| New chart builders | 15 | signal_radar, gauge, comparison_bars, ownership_pie, treemap, timeline, insider_bars, candlestick, financials_line |
| New card components | 10 | criteria_card, verdict_bullet, price_range_bar, metric_kpi, mini_sparkline |
| Stock analyzer | 8 | Data fetching, section computation, criteria scoring |
| Tab rendering | 6 | Smoke tests for all 6 tabs with mock data |
| Integration | 5 | Full stock analysis flow with mock yfinance |

### Existing Test Protection

All 838 existing tests must continue passing. Conviction engine changes need backward compatibility: if store/market_data are None, fall back to current behavior (placeholder scores).

---

## Implementation Phases

### Phase 1: Foundation (~12 tasks)
1. Create `price_cache.py` with batch fetch + TTL
2. Create `cards.py` with all reusable components (criteria_card, verdict_bullet, etc.)
3. Add new chart builders to `charts.py` (signal_radar, gauge, comparison_bars, etc.)
4. Add loading_stepper to `progress.py`
5. Fix missing CSS in `styles.py`
6. Fix conviction engine: wire real sub-scores
7. Fix conviction engine: per-ticker EDGAR queries
8. Fix conviction engine: scan all 350 tickers
9. Fix conviction engine: fallback when all below min_score
10. Fix action_runner: pass store + market_data to conviction scan
11. Fix action_runner: real prices for monitor_holdings
12. Write tests for all foundation components

### Phase 2: Tab 1 Overhaul (~8 tasks)
13. Implement scrolling ticker bar (fetch_index_prices + CSS)
14. Improve hero panels (SPY sparkline chart, live portfolio P&L)
15. Implement Mode A: market overview (recommendations as styled cards)
16. Implement market heatmap treemap
17. Improve Mode B: richer conviction cards (mini radar, hold duration, action buttons)
18. Wire recommendation data into landing page
19. Fix "watchlist alerts" count
20. Tests for Tab 1

### Phase 3: Stock Analysis Tab (~10 tasks)
21. Create `stock_analyzer.py` (data fetching + computation)
22. Create `tabs/stock_analysis.py` (main tab structure)
23. Implement Section 0: Verdict + Signal Radar + side-by-side comparison
24. Implement Section 1: Valuation (P/E peers bar, analyst targets, criteria)
25. Implement Section 2: Growth (comparison bars, quarterly financials line)
26. Implement Section 3: Past Performance (ROE gauge, margins, history)
27. Implement Section 4: Financial Health (D/E gauge, cash/debt)
28. Implement Section 5: Ownership & Smart Money (pie, insider timeline)
29. Implement Section 6: Sentiment & Signals (buzz timeline, sentiment trend)
30. Implement Section 7: Supply Chain (cluster bubble chart)
31. Tests for Stock Analysis

### Phase 4: Watchlist + Portfolio (~8 tasks)
32. Watchlist: styled cards with live prices + sparklines
33. Watchlist: remove button + structured add form
34. Watchlist: conviction score + criteria card per ticker
35. Portfolio: live P&L computation
36. Portfolio: portfolio value over time chart
37. Portfolio: position cards with health criteria + hold duration
38. Portfolio: P&L bar chart + allocation pie
39. Tests for Watchlist + Portfolio

### Phase 5: How It Works + Market Context (~6 tasks)
40. Fix accuracy chart (real per-fold data)
41. Wire grade_donut + sector_heatmap
42. Add criteria cards to expander sections
43. Market Context: live prices on supply chain tags
44. Market Context: cluster bubble chart
45. Market Context: real pipeline timestamps
46. Tests for How It Works + Market Context

### Phase 6: Polish (~6 tasks)
47. Dead code cleanup
48. Tooltips / hover explainers on key elements
49. Responsive layout check
50. Update Known Limitations section
51. Full visual QA: screenshot every tab, compare to SimplyWallSt reference
52. Update README, CLAUDE.md, CONTEXT.md with Phase 5.4 status

---

## Verification Gates

After EACH phase:
1. `make check` passes (all tests + lint + typecheck)
2. `streamlit run` — visually inspect every tab
3. Screenshot and compare to this spec's wireframes
4. Commit to feature branch

After ALL phases:
1. Full test suite passes (838 existing + ~50-80 new)
2. Every tab screenshotted and reviewed against SimplyWallSt reference quality
3. PR to develop with before/after screenshots
4. ADR-036 committed

---

## Success Criteria

1. **Tab 1:** Shows 15+ opportunities (not 2) with conviction scores, mini radars, and hold durations
2. **Tab 2:** Each watchlist ticker shows live price, sparkline, fundamentals, and remove button
3. **Tab 3:** Portfolio shows real P&L, value chart, and per-position health verdicts
4. **Tab 4:** Any S&P 500/NASDAQ ticker returns a full 7-section analysis with ~15 charts in <15 seconds
5. **Tab 5:** Real per-fold accuracy data, working learning cycle, no spacing bugs
6. **Tab 6:** Live prices on supply chain tickers, cluster visualization, real pipeline timestamps
7. **Design:** Every section uses criteria card → chart → verdict bullet pattern
8. **Loading:** Every action shows progressive loading with step messages
9. **Tests:** 890+ tests (838 existing + 50+ new), all passing
10. **No regressions:** Zero broken existing functionality
