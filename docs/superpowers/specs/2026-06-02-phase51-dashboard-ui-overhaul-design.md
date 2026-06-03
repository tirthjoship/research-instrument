# Phase 5.1: Dashboard UI Overhaul — Design Spec

**Date:** 2026-06-02
**Branch:** `feat/phase-5.1-dashboard-polish`
**Depends on:** Phase 5 complete (PR #15)

---

## Goal

Transform the functional-but-plain Streamlit dashboard into a polished, intuitive, Modern SaaS-style decision tool. Fix bugs (sidebar pages, grade colors), add contextual info to every section, replace emoji with SVG icons, add action buttons with progress bars, and apply professional styling throughout.

## Non-Goals

- Deploying to Streamlit Cloud (still local-only)
- Adding new data sources or ML features
- Changing domain/adapter/application logic (visualization-only changes)
- Custom Streamlit components (CSS + built-in components only)

---

## Bug Fixes

### 1. Sidebar Pages Auto-Discovery

**Problem:** Streamlit auto-discovers any directory named `pages/` and creates broken sidebar navigation entries (command center, market pulse, etc. appear as separate pages that don't work because they lack the dashboard context).

**Fix:** Rename `adapters/visualization/pages/` → `adapters/visualization/tabs/`. Update all imports in `dashboard.py`. Streamlit only auto-discovers directories literally named `pages/`.

### 2. Grade Display Names

**Problem:** `RecommendationGrade.STRONG_BUY.value` returns `"strong_buy"` but color maps and donut charts use `"Strong Buy"`. Donut renders all gray. Tables show raw enum values.

**Fix:** Add `grade_display_name(grade_value: str) -> str` to formatters. Maps `"strong_buy"` → `"Strong Buy"`, etc. Use everywhere grades are displayed. Fix donut chart color lookup to use display names.

### 3. Grade Donut Colors

**Problem:** `_GRADE_CHART_COLORS` keys are `"Strong Buy"` but incoming data uses `"strong_buy"`. All bars render default gray.

**Fix:** Normalize grade values through `grade_display_name()` before color lookup in `grade_donut()`.

---

## Global Styling

### Custom CSS (injected in dashboard.py)

```css
/* Base typography */
html, body, [class*="css"] {
    font-size: 16px;
}

/* Hide Streamlit chrome */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header [data-testid="stToolbar"] {visibility: hidden;}
button[title="Deploy"] {display: none;}

/* Card containers */
.dashboard-card {
    background: white;
    border: 1px solid #E8EBF0;
    border-radius: 12px;
    padding: 1.25rem;
    margin-bottom: 1rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}

/* Cards with colored left border (for action cards) */
.card-buy { border-left: 4px solid #00C853; }
.card-sell { border-left: 4px solid #FF1744; }
.card-watch { border-left: 4px solid #FFD600; }
.card-info { border-left: 4px solid #2979FF; }

/* Status pills (replace emoji checkmarks) */
.status-pill {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 13px;
    font-weight: 600;
}
.pill-fresh { background: #E8F5E9; color: #2E7D32; }
.pill-stale { background: #FFF8E1; color: #F57F17; }
.pill-warning { background: #FFF3E0; color: #E65100; }
.pill-critical { background: #FFEBEE; color: #C62828; }

/* Grade badges */
.grade-badge {
    display: inline-block;
    padding: 3px 12px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.grade-strong-buy { background: #E8F5E9; color: #1B5E20; }
.grade-buy { background: #F1F8E9; color: #33691E; }
.grade-hold { background: #FFFDE7; color: #F57F17; }
.grade-may-sell { background: #FFF3E0; color: #E65100; }
.grade-immediate-sell { background: #FFEBEE; color: #B71C1C; }

/* Signal direction pills */
.signal-bullish { background: #E8F5E9; color: #2E7D32; }
.signal-bearish { background: #FFEBEE; color: #C62828; }
.signal-neutral { background: #F5F5F5; color: #616161; }

/* Section headers */
.section-header {
    font-size: 20px;
    font-weight: 600;
    color: #1A1A2E;
    margin-bottom: 4px;
}
.section-subtitle {
    font-size: 14px;
    color: #9E9E9E;
    font-style: italic;
    margin-bottom: 16px;
}

/* Layer colors for signal breakdown cards */
.layer-technical { border-top: 3px solid #2979FF; }
.layer-sentiment { border-top: 3px solid #7C4DFF; }
.layer-fundamental { border-top: 3px solid #00C853; }
.layer-cross-asset { border-top: 3px solid #FF9100; }
.layer-event-causal { border-top: 3px solid #FF1744; }

/* Table styling */
.stDataFrame tbody tr:nth-child(even) {
    background-color: #FAFBFC;
}
```

### Branding

**App logo:** Simple inline SVG — stylized layered chart icon (5 horizontal layers in the 5 layer colors: blue, purple, green, orange, red). Used as:
- Streamlit `page_icon` (favicon)
- Header logo next to title
- Sidebar header (if sidebar is used)

**Color palette (consistent throughout):**
- Primary: `#2979FF` (blue)
- Success/Buy: `#00C853` (green)
- Warning/Hold: `#FFD600` (amber)
- Danger/Sell: `#FF1744` (red)
- Neutral: `#9E9E9E` (gray)
- Background: `#FAFBFC` (off-white)
- Card background: `#FFFFFF` (white)
- Text primary: `#1A1A2E` (near-black)
- Text secondary: `#6B7280` (gray)

---

## Info System

Every section gets two layers of context:

### 1. Subtitle (always visible)
Gray italic text directly under each section heading. One line. Answers "what does this show?"

Examples:
- Signal Freshness: *"How recent is your data? Stale data means stale predictions."*
- Walk-Forward Accuracy: *"Per-fold directional accuracy across 19 time periods. Blue line should stay above the dashed baseline."*
- Supply Chain Cascades: *"When leaders move >3%, followers often follow within 1-3 days."*

### 2. Info Expander (collapsed by default)
Triggered by ℹ️ icon or `st.expander("Learn more")`. 2-3 sentences explaining:
- What data feeds this section
- How to interpret the numbers
- When this matters for decision-making

---

## Action Runner System

### New file: `adapters/visualization/action_runner.py`

Wraps use case execution with progress tracking for dashboard buttons.

**Interface:**
```python
def run_daily_scan(
    market: str = "us",
    progress_callback: Callable[[float, str], None] | None = None,
) -> dict[str, int]:
    """Run daily scan with progress updates.

    Stages: RSS scan (33%), Google Trends (66%), StockTwits (100%).
    Skips sources scanned < 6h ago (incremental).
    """

def run_monitor_holdings(
    market: str = "us",
    progress_callback: Callable[[float, str], None] | None = None,
) -> list[SellSignal]:
    """Check all holdings for sell signals.

    Stages: Load prices (50%), Analyze signals (100%).
    """

def run_tournament_scoring(
    market: str = "us",
    progress_callback: Callable[[float, str], None] | None = None,
) -> WeeklyReport | None:
    """Score tickers using pretrained models.

    Requires pretrained models to exist.
    Stages: Load models (10%), Fetch data (50%), Score tickers (90%), Save (100%).
    Returns None if models not pretrained.
    """
```

**Dashboard integration pattern:**
```python
if st.button("Scan for Events", type="primary"):
    progress = st.progress(0)
    status = st.status("Starting scan...", expanded=True)

    def update(pct: float, msg: str) -> None:
        progress.progress(pct)
        status.update(label=msg)

    result = run_daily_scan(progress_callback=update)
    status.update(label=f"Done! {result['signals_stored']} signals found.", state="complete")
    st.rerun()  # refresh data
```

**Incremental logic:**
- Check `last_scan_timestamp` from SQLite before each source
- If source scanned < 6h ago → skip, update progress, move to next
- Progress bar still moves smoothly (skipped stages show "Recent data — skipped")

---

## Tab-by-Tab Changes

### Tab 1: Command Center

**Header:** "Command Center" with subtitle *"Your daily decision summary — what needs attention right now."*

**Signal Freshness:**
- Replace emoji ✅/❌ with colored status pills: `<span class="status-pill pill-fresh">Fresh — 2h ago</span>`
- Each metric in a dashboard-card container
- ℹ️ expander: "Data freshness affects prediction reliability. Green = data updated within 6 hours. Red = stale, re-run the relevant pipeline."

**Today's Actions:**
- Sell signals (if any) shown first in red-bordered cards
- Buy opportunities in green-bordered cards with grade badge
- Watch items in amber-bordered cards
- Each card shows: symbol, grade badge, one-line reasoning, confidence bar (not just number)
- ℹ️ expander: "Actions are prioritized: sell signals first (protect capital), then new buy opportunities, then watchlist items."

**Portfolio Status:**
- Compact table instead of bullet list (Symbol, Qty, Avg Price, Est. Value)
- Total portfolio value metric card

**Active Events:**
- "Scan for Events" primary button → progress bar → populates section
- When populated: event cards with decay indicator (bar showing remaining impact %)

### Tab 2: Model Confidence

**Header:** "Model Confidence" with subtitle *"Should you trust these predictions? Evidence-based answer."*

**Headline Card:**
- Large styled card (not st.metric)
- Green background if p < 0.05, red if not
- Shows: "Model beats random: No (p=0.1464)" or "Model beats random: Yes (p=0.003)"
- Key stats row below: Accuracy, Folds, Predictions in smaller metric cards

**Accuracy Chart:**
- Larger chart (height 400px)
- Better axis labels, font size 14px
- Hover tooltips with fold number and accuracy

**Ablation Study:**
- Human-readable variant names: "Technical Only", "Technical + Sentiment", "All Features"
- Significance badges as styled pills (not emoji ✅/❌)

**SHAP Chart:**
- Color bars by feature layer:
  - Blue = technical features (RSI, MACD, SMA, etc.)
  - Purple = sentiment features
  - Green = fundamental features
  - Orange = cross-asset features
  - Red = event-causal features
- ℹ️ expander: "SHAP values show how much each feature contributes to predictions. Higher = more important. Only features stable across multiple folds are reliable."

**Known Limitations:**
- Styled as amber-bordered card (not st.warning yellow box)
- Bullet points with proper typography

### Tab 3: Signal Breakdown

**Header:** "Signal Breakdown" with subtitle *"Deep dive into any ticker — see what each of the 5 signal layers is saying."*

**Ticker Selector:**
- Larger dropdown, show grade badge next to each symbol in the selector label

**Convergence Summary:**
- Styled card showing: grade badge, composite score, 5d prediction
- Visual convergence indicator: 5 colored dots (one per layer), filled = bullish, empty = bearish, half = neutral
- Replace st.success/st.error/st.warning with styled convergence card

**5 Layer Cards:**
- Each in a `dashboard-card` with colored top border matching layer color
- Layer icon (SVG) + layer name + signal direction pill
- Key metrics below in clean key-value layout
- For unpopulated layers: "No data" with styled "Run Analysis" button (not raw CLI command)
- ℹ️ expander per layer explaining what that signal layer measures

### Tab 4: My Positions

**Header:** "My Positions" with subtitle *"Portfolio overview — holdings, risk, and sell signal monitoring."*

**Summary Row:**
- Positions count (metric card)
- Total Investment: computed from sum(quantity × purchase_price)
- Remove "At Risk: 0" — only show when monitor-holdings has data
- Remove "Run monitor-holdings for live data" as metric value

**Holdings Table:**
- Better styled table with alternating rows
- Status column: if recommendation data exists for this symbol, show grade badge

**Sell Signals:**
- "Check Holdings" primary button → runs monitor-holdings with progress bar
- When signals exist: red-bordered cards with urgency, reasoning, confidence
- ℹ️ expander: "Sell signals detect three conditions: stop-loss breach (-8%), negative sentiment spike, and technical breakdown (price below SMA-50)."

**Add Holding Form:**
- Inline form (symbol input, quantity, price, notes) in a collapsible section
- "Add" button saves directly to SQLite, refreshes page

### Tab 5: Opportunities

**Header:** "Opportunities" with subtitle *"Latest tournament picks ranked by composite score — what to consider buying."*

**Top Picks Table:**
- Grade column: display name "Strong Buy" with colored badge (not raw "strong_buy")
- Score column: formatted with color gradient
- Confidence: mini progress bar instead of percentage text

**Grade Donut:**
- Fix colors (normalize grade names before lookup)
- Larger chart
- ℹ️ expander: "Grade distribution shows the model's current market view. Mostly Holds = model sees limited opportunities. Mostly Buys = model is bullish."

**Pick Details:**
- Expander header: "NVDA — Strong Buy (score: 0.920)" with grade badge
- Inside: 3 horizon metrics + reasoning + sources

**Watchlist:**
- Better styled table
- "Add to Watchlist" inline form (symbol + notes)
- ℹ️ expander: "Watchlist tickers are tracked but not actively recommended. Use to monitor stocks you're interested in."

### Tab 6: Market Pulse

**Header:** "Market Pulse" with subtitle *"Macro context — events, sector momentum, and supply chain cascades affecting your universe."*

**Active Events:**
- "Scan for Events" primary button with progress bar (calls daily-scan)
- When populated: timeline-style event cards with decay bar
- ℹ️ expander: "Events are classified into 10 categories (earnings, tariffs, FDA, etc.) with learned impact magnitude and decay half-life."

**Sector Momentum:**
- "Load Sector Data" button → fetches sector ETF returns from us.yaml config → renders heatmap
- ℹ️ expander: "Sector momentum shows which sectors are gaining/losing over 1d, 5d, 10d. Green = positive returns, red = negative."

**Supply Chain Cascades:**
- Better styled expanders with group name in title case ("Semiconductors" not "semiconductors")
- Leaders/Followers shown as inline badges
- Lag and correlation type as subtle metadata

**Event Impact Decay:**
- Keep interactive sliders (good feature)
- Add ℹ️ expander: "Events decay exponentially. Half-life = days until impact is halved. Use to estimate how long a recent event will affect prices."

---

## New Formatter Functions

```python
def grade_display_name(grade_value: str) -> str:
    """Convert 'strong_buy' → 'Strong Buy'."""

def grade_badge_html(grade_value: str) -> str:
    """Return HTML for a colored grade badge."""

def status_pill_html(status: str, label: str) -> str:
    """Return HTML for a colored status pill."""

def signal_pill_html(direction: str) -> str:
    """Return HTML for a signal direction pill (Bullish/Bearish/Neutral)."""

def confidence_bar_html(confidence: float) -> str:
    """Return HTML for a mini progress bar showing confidence level."""

def layer_icon_svg(layer_name: str) -> str:
    """Return inline SVG icon for a signal layer."""
```

---

## File Changes Summary

| File | Change Type |
|------|------------|
| `pages/` → `tabs/` | **Rename directory** |
| `tabs/__init__.py` | Rename from pages |
| `tabs/command_center.py` | Major rewrite — cards, pills, action buttons |
| `tabs/model_confidence.py` | Major rewrite — styled headline, charts, SHAP colors |
| `tabs/signal_breakdown.py` | Major rewrite — layer cards, convergence visual, action buttons |
| `tabs/positions.py` | Major rewrite — computed value, monitor button, add-holding form |
| `tabs/opportunities.py` | Major rewrite — grade badges, donut fix, watchlist form |
| `tabs/market_pulse.py` | Major rewrite — action buttons, title case, sector loader |
| `dashboard.py` | Global CSS, branding, import updates |
| `components/formatters.py` | Add 6 new HTML formatter functions |
| `components/charts.py` | Fix grade donut colors, SHAP layer colors, ablation labels |
| `components/metrics.py` | Styled card containers, confidence bars |
| `action_runner.py` (new) | Progress-tracked use case execution |
| `components/styles.py` (new) | CSS constants and injection function |
| `components/icons.py` (new) | SVG icon definitions for layers, sections, branding |
| `tests/test_formatters.py` | Tests for new formatter functions |
| `tests/test_action_runner.py` | Tests for action runner (mocked use cases) |

---

## Testing Strategy

- **Formatter tests:** Unit tests for all new HTML formatters (grade_display_name, badge, pill, bar)
- **Action runner tests:** Mock use cases, verify progress callbacks fire, verify incremental skip logic
- **Chart tests:** Verify fixed donut colors, SHAP layer colors
- **Smoke test:** Update imports for tabs/ rename
- **No Streamlit server tests** — test functions, not UI rendering

---

## Success Criteria

1. No broken sidebar pages (only main dashboard tab works)
2. Grade donut shows correct colors (green/amber/red, not gray)
3. Every section has subtitle + ℹ️ info expander
4. No emoji checkmarks/crosses anywhere — all styled pills and badges
5. Action buttons with progress bars for daily-scan, monitor-holdings, sector data
6. Incremental refresh skips sources scanned < 6h ago
7. Inline forms for add-holding and add-watchlist
8. Font sizes readable (16px body, 20px headers)
9. Card-based layout with shadows and borders throughout
10. Professional branding (SVG logo, consistent color palette)
11. All existing tests pass, new tests for formatters and action runner
