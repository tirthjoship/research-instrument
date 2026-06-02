# ADR-031: Decision Dashboard Architecture — Command Center + 6 Tabs + Plotly

**Status:** Accepted (2026-06-02)

**Context:** Phase 5 builds a Streamlit dashboard to visualize the 101-feature ML system. This ADR records the architectural decisions from the Phase 5 brainstorming session.

## Decisions

### 1. Audience: Local Demo Artifact (Option A)

Local Streamlit app, launched with `streamlit run dashboard.py`. Zero hosting cost, no API keys for viewing. Deployment to Streamlit Cloud deferred.

### 2. Dashboard Philosophy: Decision Tool, Not Data Viewer

Reframed from "show charts" to "what should I do today." Command Center tab synthesizes all 5 signal layers into actionable items (sell signals, buy opportunities, active events, signal freshness).

### 3. Tab Structure: 6 Decision-Oriented Tabs

| Tab | Purpose |
|-----|---------|
| Command Center | Today's actions, alerts, signal freshness |
| Model Confidence | Backtest results, evidence for trust |
| Signal Breakdown | Per-ticker multi-layer signal convergence/divergence |
| My Positions | Holdings P&L, sell signals, risk concentration |
| Opportunities | Ranked picks with reasoning, watchlist |
| Market Pulse | Active events, sector momentum, supply chain cascades |

### 4. Charting: Plotly (Option B)

Interactive charts with hover tooltips. Professional look. Native `st.plotly_chart()` support. Consistent palette: green=#00C853, red=#FF1744, blue=#2979FF.

### 5. Styling: Minimal (Option A)

Streamlit defaults + `st.metric()` cards + Plotly interactivity. 95% of visual impact with 10% effort. Custom CSS deferred.

### 6. Watchlist Feature

New `watchlist` SQLite table + 3 CLI commands (add-watchlist, list-watchlist, remove-watchlist). Lightweight tracking of tickers not yet held.

## Consequences

**Positive:**
- Actionable dashboard, not passive data viewer
- Works with existing data (no new APIs needed for viewing)
- Graceful degradation — empty tabs show helpful CLI instructions
- Plotly interactivity differentiates from static matplotlib

**Negative:**
- 6 tabs is substantial implementation scope
- Signal Breakdown tab depends on stored per-ticker features (may need tournament run first)
- Streamlit adds ~200MB dependency
