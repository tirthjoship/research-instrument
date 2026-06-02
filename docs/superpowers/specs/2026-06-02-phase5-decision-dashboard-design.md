# Phase 5: Decision Dashboard — Design Spec

**Date:** 2026-06-02
**ADRs:** 027 (cross-asset), 029 (cross-asset features), 030 (event-causal)
**Branch:** `feat/phase-5-decision-dashboard`
**Depends on:** All Phase 4 (A/B/C/D) complete

---

## Goal

Streamlit dashboard that turns the 101-feature ML system into an actionable investment decision tool. Not a data viewer — a command center that synthesizes all 5 signal layers into "what should I do today and why."

Runs locally: `streamlit run adapters/visualization/dashboard.py`

## Non-Goals

- Deployed web app (local-only for now, Streamlit Cloud later)
- Real-time streaming data (reads stored data, refreshed via CLI commands)
- Automated trading / order execution
- Custom Streamlit components or heavy CSS

---

## Architecture

```
adapters/visualization/
  dashboard.py              → Entry point, tab router, page config
  pages/
    command_center.py       → Today's actions, alerts, signal freshness
    model_confidence.py     → Backtest results, should I trust predictions?
    signal_breakdown.py     → Per-ticker multi-layer signal view
    positions.py            → Holdings P&L, sell signals, risk concentration
    opportunities.py        → Ranked picks with reasoning, watchlist
    market_pulse.py         → Active events, sector momentum, cascades
  components/
    charts.py               → Shared Plotly chart builders (consistent palette)
    metrics.py              → Reusable metric card components
    formatters.py           → Grade colors, direction icons, number formatting
  data_loader.py            → SQLite + JSON loading with @st.cache_data
```

---

## Tab 1: Command Center

**Purpose:** Open dashboard → instantly see what to do.

### Layout

```
┌─────────────────────────────────────────────────────┐
│  🟢 System Status: All data fresh (last scan: 2h ago)│
├─────────────────────────────────────────────────────┤
│  TODAY'S ACTIONS                                     │
│  ┌─────────────────────────────────────────────┐    │
│  │ 🔴 SELL AMD — stop-loss triggered (-10%)    │    │
│  │    Confidence: 95% | Urgency: IMMEDIATE     │    │
│  │    Layers: technical ❌ sentiment ❌ cross ⚠️│    │
│  ├─────────────────────────────────────────────┤    │
│  │ 🟡 WATCH TSLA — sentiment spike (-0.8)      │    │
│  │    Urgency: THIS WEEK | 2/5 layers bearish  │    │
│  ├─────────────────────────────────────────────┤    │
│  │ 🟢 BUY NVDA — Strong Buy (4/5 layers agree) │    │
│  │    Predicted 5d: +3.2% | Confidence: 82%    │    │
│  └─────────────────────────────────────────────┘    │
│                                                     │
│  ACTIVE EVENTS                                      │
│  ⚡ tariff_trade (2d ago) — Energy+, Tech-          │
│     Half-life: 5d | Remaining impact: 71%           │
│  ⚡ earnings_surprise NVDA (1d ago) — Tech+         │
│     Half-life: 3d | Remaining impact: 79%           │
│                                                     │
│  SIGNAL FRESHNESS                                   │
│  ✅ Daily scan: 2h ago                              │
│  ✅ Backtest: today                                 │
│  ⚠️ SHAP analysis: 3 days ago                       │
│  ❌ Tournament: 5 days ago — run `run-tournament`   │
└─────────────────────────────────────────────────────┘
```

### Data Sources
- **Actions:** MonitorHoldingsUseCase sell signals + latest tournament top picks
- **Active Events:** ClassifiedEvent records from SQLite (if populated) or mock data showing structure
- **Freshness:** File modification times of `data/reports/*.json`, SQLite last-insert timestamps

### Logic
- Actions sorted by urgency: IMMEDIATE > THIS WEEK > WATCH > BUY opportunities
- Sell signals from holdings always surface first
- Buy signals only shown for tickers NOT already held
- Freshness thresholds: <6h = ✅, 6h-24h = 🟡, >24h = ⚠️, >72h = ❌

---

## Tab 2: Model Confidence

**Purpose:** Should I trust these predictions? Show the evidence + honest limitations.

### Layout
- **Headline metric:** "Model beats random? {Yes/No} (p={value})" — big, honest, front and center
- **Horizon selector:** 2d / 5d / 10d radio buttons
- **Walk-forward accuracy chart:** Plotly line chart, per-fold accuracy with 50% baseline dashed line
- **Key stats row:** avg accuracy, min/max fold, n_folds, n_predictions, p-value
- **Sharpe comparison:** Model Sharpe vs SPY Sharpe (bar chart, side by side)
- **Ablation chart:** grouped bar — tech-only vs +sentiment vs +all features
- **Honest limitations box:** `st.warning()` listing known caveats:
  - "Phase 3A result: technical features alone = random on S&P mega-caps"
  - "Phase 3B in-sample only — out-of-sample validation pending"
  - "101 features wired but only 45 tested in backtest so far"

### Data Sources
- Backtest JSON reports from `data/reports/backtest_report_*.json`
- Phase 3B validation JSON
- SQLite evaluation_runs table

---

## Tab 3: Signal Breakdown

**Purpose:** For a specific ticker, what is each of the 5 layers saying? Where do they agree/disagree?

### Layout
- **Ticker search/selector** at top (dropdown of universe tickers)
- **Signal convergence indicator:** "4/5 layers BULLISH" or "CONFLICTING: 2 bull, 2 bear, 1 neutral"
- **Layer-by-layer cards:**

```
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ 📊 Technical     │ │ 💬 Sentiment     │ │ 💰 Fundamental   │
│ Signal: BULLISH  │ │ Signal: BULLISH  │ │ Signal: NEUTRAL  │
│ RSI: 45 (neutral)│ │ Score: +0.65     │ │ PEG: 1.8         │
│ MACD: positive   │ │ Buzz: high       │ │ P/E vs sector: +2│
│ SMA20: above     │ │ Sources: 3 agree │ │ FCF yield: 4.2%  │
└──────────────────┘ └──────────────────┘ └──────────────────┘
┌──────────────────┐ ┌──────────────────┐
│ 🔗 Cross-Asset   │ │ ⚡ Event-Causal   │
│ Signal: BULLISH  │ │ Signal: BULLISH  │
│ Upstream: +2.3%  │ │ Earnings (1d ago)│
│ Cluster: +1.8%   │ │ Impact: 79%      │
│ Lag signal: 0.04 │ │ Half-life: 3d    │
└──────────────────┘ └──────────────────┘
```

- **Convergence history:** mini sparkline showing how many layers agreed over past 10 days

### Data Sources
- Latest feature computation for selected ticker (from SQLite recommendations or computed on-demand)
- This tab may show "Run tournament first" if no recommendation data exists for the ticker

### Note
This tab requires stored per-ticker feature values. If recommendations table has the raw features, use those. If not, show structure with placeholder "run tournament to populate" message.

---

## Tab 4: My Positions

**Purpose:** What do I own, how's it doing, what's at risk?

### Layout
- **Portfolio summary row:** total positions, total value (if prices available), positions at risk count
- **Holdings table:** symbol, quantity, purchase price, current status (healthy/warning/sell), days held
- **Sell signals panel:** active signals with full reasoning
- **Risk concentration:**
  - Sector exposure donut chart (what % of holdings per sector)
  - Correlation heatmap of held positions (are positions diversified or clustered?)
- **Event exposure:** which active events affect your held sectors

### Data Sources
- SQLite holdings table
- MonitorHoldingsUseCase for sell signals
- Sector info from ticker_info (yfinance cached)
- For correlation: cross-asset graph data if available

### Empty State
"No holdings tracked. Add with `python -m application.cli add-holding NVDA 10 --price=950`"

---

## Tab 5: Opportunities

**Purpose:** What should I consider buying? Ranked picks with full reasoning chain.

### Layout
- **Latest tournament date** + "Run new tournament" instruction
- **Top 15 table:**
  | Rank | Symbol | Grade | Score | Conf | 5d Pred | Layers Agree | Key Signal |
  |------|--------|-------|-------|------|---------|-------------|------------|
  | 1 | NVDA | 🟢 Strong Buy | 0.85 | 82% | +3.2% | 4/5 | Earnings catalyst |
  | 2 | AMD | 🟢 Buy | 0.72 | 75% | +2.1% | 3/5 | Upstream leader +4% |

- **Grade distribution donut:** how many Strong Buy vs Buy vs Hold
- **Reasoning expander:** click a ticker → see full reasoning text, all horizon predictions, which layers contributed
- **Watchlist section:** user-flagged tickers to track (stored in SQLite, new simple table)

### Data Sources
- SQLite recommendations table (latest week_start)
- SQLite accuracy_records for historical accuracy per ticker

### Watchlist
New lightweight feature: `watchlist` table in SQLite (symbol, added_date, notes). CLI commands: `add-watchlist`, `list-watchlist`, `remove-watchlist`. Dashboard shows watchlist tickers with latest available signals.

---

## Tab 6: Market Pulse

**Purpose:** What's happening in the market right now that affects my universe?

### Layout
- **Active events timeline:** horizontal timeline showing classified events from past 7 days with decay curves
- **Sector momentum heatmap:** 11 sectors × 1d/5d/10d returns, color-coded green/red
- **Supply chain cascades:** if a leader moved >3%, show which followers haven't reacted yet
  - "AMAT +4.2% yesterday → LRCX, KLAC haven't moved. Historical follow rate: 73%"
- **Correlation cluster status:** which clusters are moving together (normal) vs diverging (unusual)

### Data Sources
- Classified events from SQLite (if event classification pipeline has been run)
- Supply chain YAML for cascade display
- Sector ETF data from config (sector_etfs in us.yaml)
- Cross-asset graph data

### Empty State
Events section shows "Run event classification pipeline to populate" if no events stored. Sector momentum shows static structure with "run daily-scan for live data."

---

## Data Loader

**File:** `adapters/visualization/data_loader.py`

### Responsibilities
- Load backtest JSONs from `data/reports/`
- Query SQLite tables (recommendations, accuracy, evaluation_runs, holdings, buzz_signals)
- Load SHAP JSON
- Load supply chain + event mapping YAMLs
- All functions decorated with `@st.cache_data(ttl=300)` (5 min cache)

### Graceful Degradation
Every loader returns a sensible default (empty list, empty DataFrame, None) on missing data. No tab crashes from missing data — shows empty state message instead.

---

## Shared Components

### charts.py — Plotly Builders
- `COLOR_PALETTE`: green=#00C853, red=#FF1744, blue=#2979FF, amber=#FFD600, gray=#9E9E9E
- `accuracy_line_chart(folds, baseline=0.5)` → Plotly Figure
- `shap_bar_chart(features, importances, layers)` → horizontal bar, colored by layer
- `sector_heatmap(sectors, returns)` → heatmap Figure
- `grade_donut(grade_counts)` → donut Figure
- `decay_curve(magnitude, half_life, days=10)` → line Figure
- All charts: consistent template, hover tooltips, no gridline clutter

### metrics.py — Metric Cards
- `render_metric(label, value, delta=None, color=None)` → calls `st.metric()` with formatting
- `render_action_card(action_type, symbol, reason, urgency)` → styled container

### formatters.py
- `grade_color(grade)` → hex color
- `direction_icon(direction)` → 🟢/🔴/⚪
- `urgency_badge(urgency)` → styled string
- `pct(value)` → "+2.3%" or "-1.5%"
- `freshness_status(timestamp)` → ✅/🟡/⚠️/❌ with label

---

## New SQLite Table: Watchlist

```sql
CREATE TABLE IF NOT EXISTS watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL UNIQUE,
    added_date TEXT NOT NULL,
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

Add to SQLiteStore: `add_watchlist()`, `remove_watchlist()`, `get_watchlist()`.
Add CLI commands: `add-watchlist SYMBOL`, `list-watchlist`, `remove-watchlist SYMBOL`.

---

## Dependencies

```toml
[project.optional-dependencies]
dashboard = [
    "streamlit>=1.30.0",
    "plotly>=5.18.0",
]
```

Install: `pip install -e ".[dashboard]"`
Run: `streamlit run adapters/visualization/dashboard.py`

---

## Testing Strategy

- **data_loader.py:** unit tests with test fixtures (small SQLite + JSON)
- **charts.py:** unit tests verifying returned Plotly Figure objects have correct traces/layout
- **formatters.py:** unit tests for color/icon/badge logic
- **Smoke test:** `import adapters.visualization.dashboard` succeeds without Streamlit server
- **No Streamlit server tests** — test the functions, not the UI rendering

---

## Success Criteria

1. Dashboard launches with `streamlit run adapters/visualization/dashboard.py`
2. All 6 tabs render without error (even with empty data)
3. Command Center shows actionable items when data exists
4. Backtest results display with interactive Plotly charts
5. Signal Breakdown shows per-ticker multi-layer view
6. Portfolio tab shows holdings + sell signals
7. Graceful empty states with helpful CLI commands for populating data
8. All new tests pass, no regressions in existing 410 tests
9. All pre-commit hooks pass
