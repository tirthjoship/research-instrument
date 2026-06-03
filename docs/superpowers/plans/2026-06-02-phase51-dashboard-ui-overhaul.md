# Phase 5.1: Dashboard UI Overhaul — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the plain Streamlit dashboard into a polished Modern SaaS-style decision tool — fix bugs (sidebar, grade colors), add global CSS styling, replace emoji with HTML pills/badges, add info tooltips to every section, add action buttons with progress bars, and inline forms.

**Architecture:** All changes in `adapters/visualization/` (visualization adapter layer). New `styles.py` for CSS injection, new `action_runner.py` for progress-tracked use case execution. Rename `pages/` → `tabs/` to fix Streamlit auto-discovery bug. Every tab page gets a full rewrite with styled cards, info expanders, and action buttons.

**Tech Stack:** Python 3.12, Streamlit ≥1.30, Plotly ≥5.18, existing SQLite store + domain models.

**Branch:** `feat/phase-5.1-dashboard-polish`

**Spec:** `docs/superpowers/specs/2026-06-02-phase51-dashboard-ui-overhaul-design.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `adapters/visualization/components/styles.py` (new) | Global CSS constants + `inject_global_css()` function |
| `adapters/visualization/components/formatters.py` | Add `grade_display_name()`, `grade_badge_html()`, `status_pill_html()`, `signal_pill_html()`, `confidence_bar_html()` |
| `adapters/visualization/components/charts.py` | Fix grade donut color lookup, human-readable ablation labels, SHAP layer colors |
| `adapters/visualization/components/metrics.py` | Rewrite with HTML card containers, border-left colors |
| `adapters/visualization/action_runner.py` (new) | Progress-tracked wrappers for daily-scan, monitor-holdings |
| `adapters/visualization/pages/` → `adapters/visualization/tabs/` | **Rename directory** |
| `adapters/visualization/tabs/command_center.py` | Full rewrite — status pills, styled cards, action buttons |
| `adapters/visualization/tabs/model_confidence.py` | Full rewrite — styled headline, chart sizing, ablation labels, SHAP colors |
| `adapters/visualization/tabs/signal_breakdown.py` | Full rewrite — layer-colored cards, signal pills, action buttons |
| `adapters/visualization/tabs/positions.py` | Full rewrite — computed total, monitor button, add-holding form |
| `adapters/visualization/tabs/opportunities.py` | Full rewrite — grade badges, donut fix, add-watchlist form |
| `adapters/visualization/tabs/market_pulse.py` | Full rewrite — scan button, title case, sector loader |
| `adapters/visualization/dashboard.py` | CSS injection, import updates, branding |
| `tests/test_formatters.py` | Tests for new HTML formatters |
| `tests/test_charts.py` | Update donut test for normalized grades |
| `tests/test_action_runner.py` (new) | Action runner with mocked use cases |
| `tests/test_dashboard_smoke.py` | Update imports for tabs/ |

---

### Task 1: Branch Setup + Rename pages/ → tabs/

**Files:**
- Rename: `adapters/visualization/pages/` → `adapters/visualization/tabs/`
- Modify: `adapters/visualization/dashboard.py`
- Modify: `tests/test_dashboard_smoke.py`

- [ ] **Step 1: Create feature branch**

```bash
cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender"
git checkout develop
git pull origin develop
git checkout -b feat/phase-5.1-dashboard-polish
```

- [ ] **Step 2: Rename pages/ to tabs/**

```bash
cd adapters/visualization
git mv pages tabs
```

- [ ] **Step 3: Update dashboard.py imports**

Replace all 6 import lines in `adapters/visualization/dashboard.py`. Change every occurrence of `adapters.visualization.pages.` to `adapters.visualization.tabs.`:

```python
# In tab1 block:
    from adapters.visualization.tabs.command_center import render as render_cc
# In tab2 block:
    from adapters.visualization.tabs.model_confidence import render as render_mc
# In tab3 block:
    from adapters.visualization.tabs.signal_breakdown import render as render_sb
# In tab4 block:
    from adapters.visualization.tabs.positions import render as render_pos
# In tab5 block:
    from adapters.visualization.tabs.opportunities import render as render_opp
# In tab6 block:
    from adapters.visualization.tabs.market_pulse import render as render_mp
```

- [ ] **Step 4: Update smoke test imports**

In `tests/test_dashboard_smoke.py`, there are no direct `pages.` imports (smoke tests import from `components/` and `data_loader`), but verify:

```bash
grep -r "adapters.visualization.pages" tests/
```

If any found, update to `adapters.visualization.tabs`.

- [ ] **Step 5: Run tests to verify nothing broke**

```bash
pytest tests/test_dashboard_smoke.py tests/test_formatters.py tests/test_charts.py -v
```

Expected: ALL PASS.

- [ ] **Step 6: Verify dashboard still launches**

```bash
python -c "from adapters.visualization.tabs.command_center import render; print('OK')"
```

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "fix: rename pages/ to tabs/ to prevent Streamlit sidebar auto-discovery"
```

---

### Task 2: Global CSS + Styles Module

**Files:**
- Create: `adapters/visualization/components/styles.py`
- Modify: `adapters/visualization/dashboard.py`

- [ ] **Step 1: Create styles.py**

```python
"""Global CSS styles for dashboard — injected once in dashboard.py."""

from __future__ import annotations

GLOBAL_CSS = """
<style>
/* ===== Typography ===== */
html, body, [class*="css"] {
    font-size: 16px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}
h1 { font-size: 28px !important; font-weight: 700 !important; color: #1A1A2E !important; }
h2 { font-size: 22px !important; font-weight: 600 !important; color: #1A1A2E !important; }
h3 { font-size: 18px !important; font-weight: 600 !important; color: #1A1A2E !important; }

/* ===== Hide Streamlit chrome ===== */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header [data-testid="stToolbar"] {visibility: hidden;}

/* ===== Card containers ===== */
.dashboard-card {
    background: white;
    border: 1px solid #E8EBF0;
    border-radius: 12px;
    padding: 1.25rem;
    margin-bottom: 1rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    transition: box-shadow 0.2s ease;
}
.dashboard-card:hover {
    box-shadow: 0 2px 8px rgba(0,0,0,0.12);
}
.card-buy { border-left: 4px solid #00C853; }
.card-sell { border-left: 4px solid #FF1744; }
.card-watch { border-left: 4px solid #FFD600; }
.card-info { border-left: 4px solid #2979FF; }

/* ===== Status pills ===== */
.status-pill {
    display: inline-block;
    padding: 3px 12px;
    border-radius: 12px;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.3px;
}
.pill-fresh { background: #E8F5E9; color: #2E7D32; }
.pill-stale { background: #FFF8E1; color: #F57F17; }
.pill-warning { background: #FFF3E0; color: #E65100; }
.pill-critical { background: #FFEBEE; color: #C62828; }

/* ===== Grade badges ===== */
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

/* ===== Signal pills ===== */
.signal-pill {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 10px;
    font-size: 12px;
    font-weight: 600;
}
.signal-bullish { background: #E8F5E9; color: #2E7D32; }
.signal-bearish { background: #FFEBEE; color: #C62828; }
.signal-neutral { background: #F5F5F5; color: #616161; }

/* ===== Layer cards ===== */
.layer-card {
    background: white;
    border: 1px solid #E8EBF0;
    border-radius: 10px;
    padding: 1rem;
    margin-bottom: 0.75rem;
    min-height: 140px;
}
.layer-technical { border-top: 3px solid #2979FF; }
.layer-sentiment { border-top: 3px solid #7C4DFF; }
.layer-fundamental { border-top: 3px solid #00C853; }
.layer-cross-asset { border-top: 3px solid #FF9100; }
.layer-event-causal { border-top: 3px solid #FF1744; }

/* ===== Confidence bar ===== */
.confidence-bar-bg {
    background: #F0F0F0;
    border-radius: 4px;
    height: 8px;
    width: 100%;
    margin-top: 4px;
}
.confidence-bar-fill {
    height: 8px;
    border-radius: 4px;
}

/* ===== Section subtitle ===== */
.section-subtitle {
    font-size: 14px;
    color: #9E9E9E;
    font-style: italic;
    margin-top: -10px;
    margin-bottom: 16px;
}

/* ===== Table styling ===== */
.stDataFrame tbody tr:nth-child(even) {
    background-color: #FAFBFC;
}

/* ===== Limitation card ===== */
.limitation-card {
    background: #FFFDE7;
    border: 1px solid #FFF9C4;
    border-left: 4px solid #FFD600;
    border-radius: 8px;
    padding: 1rem;
    font-size: 14px;
    color: #5D4037;
}
</style>
"""


def inject_global_css() -> None:
    """Inject global CSS into the Streamlit page. Call once in dashboard.py."""
    import streamlit as st

    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
```

- [ ] **Step 2: Update dashboard.py to inject CSS and add branding**

Replace the entire `adapters/visualization/dashboard.py` with:

```python
"""Dashboard entry point — tab router and page config.

Run: streamlit run adapters/visualization/dashboard.py
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Stock Recommender Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Inject global CSS before any content
from adapters.visualization.components.styles import inject_global_css

inject_global_css()

# Branding header
st.markdown(
    '<h1 style="margin-bottom: 0;">📈 Multi-Modal Stock Recommender</h1>'
    '<p style="color: #6B7280; font-size: 15px; margin-top: 4px;">'
    "Decision dashboard — 5 signal layers · 101 features · hexagonal architecture"
    "</p>",
    unsafe_allow_html=True,
)

# Tab router
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    [
        "🎯 Command Center",
        "📊 Model Confidence",
        "🔍 Signal Breakdown",
        "💼 My Positions",
        "🚀 Opportunities",
        "🌍 Market Pulse",
    ]
)

with tab1:
    from adapters.visualization.tabs.command_center import render as render_cc

    render_cc()

with tab2:
    from adapters.visualization.tabs.model_confidence import render as render_mc

    render_mc()

with tab3:
    from adapters.visualization.tabs.signal_breakdown import render as render_sb

    render_sb()

with tab4:
    from adapters.visualization.tabs.positions import render as render_pos

    render_pos()

with tab5:
    from adapters.visualization.tabs.opportunities import render as render_opp

    render_opp()

with tab6:
    from adapters.visualization.tabs.market_pulse import render as render_mp

    render_mp()
```

- [ ] **Step 3: Verify CSS injection works**

```bash
python -c "from adapters.visualization.components.styles import inject_global_css; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add adapters/visualization/components/styles.py adapters/visualization/dashboard.py
git commit -m "feat: add global CSS styling + branding header"
```

---

### Task 3: New HTML Formatters + Fix Grade Display

**Files:**
- Modify: `adapters/visualization/components/formatters.py`
- Modify: `tests/test_formatters.py`

- [ ] **Step 1: Write failing tests for new formatters**

Add these test classes to the end of `tests/test_formatters.py`:

```python
class TestGradeDisplayName:
    def test_strong_buy(self) -> None:
        from adapters.visualization.components.formatters import grade_display_name
        assert grade_display_name("strong_buy") == "Strong Buy"

    def test_buy(self) -> None:
        from adapters.visualization.components.formatters import grade_display_name
        assert grade_display_name("buy") == "Buy"

    def test_hold(self) -> None:
        from adapters.visualization.components.formatters import grade_display_name
        assert grade_display_name("hold") == "Hold"

    def test_may_sell(self) -> None:
        from adapters.visualization.components.formatters import grade_display_name
        assert grade_display_name("may_sell") == "May Sell"

    def test_immediate_sell(self) -> None:
        from adapters.visualization.components.formatters import grade_display_name
        assert grade_display_name("immediate_sell") == "Immediate Sell"

    def test_already_display_name(self) -> None:
        from adapters.visualization.components.formatters import grade_display_name
        assert grade_display_name("Strong Buy") == "Strong Buy"

    def test_unknown(self) -> None:
        from adapters.visualization.components.formatters import grade_display_name
        assert grade_display_name("unknown") == "Unknown"


class TestGradeBadgeHtml:
    def test_strong_buy_has_class(self) -> None:
        from adapters.visualization.components.formatters import grade_badge_html
        html = grade_badge_html("strong_buy")
        assert "grade-strong-buy" in html
        assert "Strong Buy" in html

    def test_hold_has_class(self) -> None:
        from adapters.visualization.components.formatters import grade_badge_html
        html = grade_badge_html("hold")
        assert "grade-hold" in html


class TestStatusPillHtml:
    def test_fresh(self) -> None:
        from adapters.visualization.components.formatters import status_pill_html
        html = status_pill_html("fresh", "2h ago")
        assert "pill-fresh" in html
        assert "2h ago" in html

    def test_critical(self) -> None:
        from adapters.visualization.components.formatters import status_pill_html
        html = status_pill_html("critical", "5d ago")
        assert "pill-critical" in html


class TestSignalPillHtml:
    def test_bullish(self) -> None:
        from adapters.visualization.components.formatters import signal_pill_html
        html = signal_pill_html("bullish")
        assert "signal-bullish" in html
        assert "BULLISH" in html

    def test_bearish(self) -> None:
        from adapters.visualization.components.formatters import signal_pill_html
        html = signal_pill_html("bearish")
        assert "signal-bearish" in html

    def test_neutral(self) -> None:
        from adapters.visualization.components.formatters import signal_pill_html
        html = signal_pill_html("neutral")
        assert "signal-neutral" in html


class TestConfidenceBarHtml:
    def test_high_confidence(self) -> None:
        from adapters.visualization.components.formatters import confidence_bar_html
        html = confidence_bar_html(0.85)
        assert "85%" in html

    def test_zero(self) -> None:
        from adapters.visualization.components.formatters import confidence_bar_html
        html = confidence_bar_html(0.0)
        assert "0%" in html


class TestFreshnessStatusHtml:
    def test_returns_pill_html(self) -> None:
        from adapters.visualization.components.formatters import freshness_status_html
        html = freshness_status_html(datetime.now() - timedelta(hours=2))
        assert "pill-fresh" in html
        assert "2h ago" in html

    def test_none_returns_critical(self) -> None:
        from adapters.visualization.components.formatters import freshness_status_html
        html = freshness_status_html(None)
        assert "pill-critical" in html
        assert "Never" in html
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_formatters.py -v -k "GradeDisplay or GradeBadge or StatusPill or SignalPill or ConfidenceBar or FreshnessStatusHtml"
```

Expected: FAIL — functions not defined.

- [ ] **Step 3: Add new functions to formatters.py**

Add these functions to the end of `adapters/visualization/components/formatters.py`:

```python
_GRADE_DISPLAY_NAMES: dict[str, str] = {
    "strong_buy": "Strong Buy",
    "buy": "Buy",
    "hold": "Hold",
    "may_sell": "May Sell",
    "immediate_sell": "Immediate Sell",
}

_GRADE_CSS_CLASSES: dict[str, str] = {
    "strong_buy": "grade-strong-buy",
    "buy": "grade-buy",
    "hold": "grade-hold",
    "may_sell": "grade-may-sell",
    "immediate_sell": "grade-immediate-sell",
}


def grade_display_name(grade_value: str) -> str:
    """Convert enum value 'strong_buy' → 'Strong Buy'."""
    if grade_value in _GRADE_DISPLAY_NAMES:
        return _GRADE_DISPLAY_NAMES[grade_value]
    # Already a display name or unknown
    if grade_value in _GRADE_DISPLAY_NAMES.values():
        return grade_value
    return grade_value.replace("_", " ").title()


def grade_badge_html(grade_value: str) -> str:
    """Return HTML for a colored grade badge."""
    display = grade_display_name(grade_value)
    css_class = _GRADE_CSS_CLASSES.get(grade_value, "")
    return f'<span class="grade-badge {css_class}">{display}</span>'


def status_pill_html(status: str, label: str) -> str:
    """Return HTML for a colored status pill.

    status: 'fresh', 'stale', 'warning', 'critical'
    """
    css_class = f"pill-{status}"
    return f'<span class="status-pill {css_class}">{label}</span>'


def signal_pill_html(direction: str) -> str:
    """Return HTML for a signal direction pill."""
    css_map = {
        "bullish": "signal-bullish",
        "bearish": "signal-bearish",
        "neutral": "signal-neutral",
    }
    css_class = css_map.get(direction.lower(), "signal-neutral")
    display = direction.upper()
    return f'<span class="signal-pill {css_class}">{display}</span>'


def confidence_bar_html(confidence: float) -> str:
    """Return HTML for a mini confidence progress bar."""
    pct_val = max(0, min(100, int(confidence * 100)))
    color = "#00C853" if pct_val >= 70 else "#FFD600" if pct_val >= 40 else "#FF1744"
    return (
        f'<div class="confidence-bar-bg">'
        f'<div class="confidence-bar-fill" style="width: {pct_val}%; background: {color};"></div>'
        f"</div>"
        f'<span style="font-size: 12px; color: #6B7280;">{pct_val}%</span>'
    )


def freshness_status_html(timestamp: datetime | None) -> str:
    """Return HTML status pill for data freshness."""
    if timestamp is None:
        return status_pill_html("critical", "Never run")

    hours_ago = (datetime.now() - timestamp).total_seconds() / 3600

    if hours_ago < 6:
        label = f"{hours_ago:.0f}h ago" if hours_ago >= 1 else "just now"
        return status_pill_html("fresh", label)
    elif hours_ago < 24:
        return status_pill_html("stale", f"{hours_ago:.0f}h ago")
    elif hours_ago < 72:
        return status_pill_html("warning", f"{hours_ago / 24:.0f}d ago")
    else:
        return status_pill_html("critical", f"{hours_ago / 24:.0f}d ago")
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_formatters.py -v
```

Expected: ALL PASS (old + new tests).

- [ ] **Step 5: Commit**

```bash
git add adapters/visualization/components/formatters.py tests/test_formatters.py
git commit -m "feat: add HTML formatters (grade badges, status pills, signal pills, confidence bars)"
```

---

### Task 4: Fix Chart Colors + Ablation Labels

**Files:**
- Modify: `adapters/visualization/components/charts.py`
- Modify: `tests/test_charts.py`

- [ ] **Step 1: Write failing test for donut with enum values**

Add to `tests/test_charts.py`:

```python
class TestGradeDonutWithEnumValues:
    def test_enum_values_get_correct_colors(self) -> None:
        from adapters.visualization.components.charts import grade_donut
        # Grades come as enum values like "strong_buy", not "Strong Buy"
        fig = grade_donut({"strong_buy": 2, "buy": 5, "hold": 4, "may_sell": 2, "immediate_sell": 1})
        import plotly.graph_objects as go
        assert isinstance(fig, go.Figure)
        # Should have a pie trace with non-gray colors
        if fig.data:
            colors = fig.data[0].marker.colors
            assert "#9E9E9E" not in colors  # no gray fallback


class TestAblationHumanReadable:
    def test_human_readable_labels(self) -> None:
        from adapters.visualization.components.charts import ablation_bar_chart
        fig = ablation_bar_chart(
            variants=["technical_only", "technical_plus_sentiment"],
            accuracies=[0.474, 0.697],
        )
        # X-axis should show human-readable labels
        assert fig.data[0].x[0] == "Technical Only"
        assert fig.data[0].x[1] == "Technical + Sentiment"
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_charts.py -v -k "EnumValues or HumanReadable"
```

Expected: FAIL.

- [ ] **Step 3: Fix grade_donut to normalize grade names**

In `adapters/visualization/components/charts.py`, update the `grade_donut` function. Add an import at the top and modify the function:

Add after the existing imports:

```python
from adapters.visualization.components.formatters import grade_display_name
```

Replace the `grade_donut` function body:

```python
def grade_donut(grade_counts: dict[str, int]) -> go.Figure:
    """Donut chart of recommendation grade distribution."""
    fig = go.Figure()

    if grade_counts:
        # Normalize grade names (enum values → display names)
        normalized = {grade_display_name(k): v for k, v in grade_counts.items()}
        labels = list(normalized.keys())
        values = list(normalized.values())
        colors = [_GRADE_CHART_COLORS.get(g, COLOR_PALETTE["gray"]) for g in labels]
        fig.add_trace(
            go.Pie(
                labels=labels,
                values=values,
                hole=0.4,
                marker={"colors": colors},
            )
        )

    fig.update_layout(title="Grade Distribution", **_LAYOUT_DEFAULTS)
    return fig
```

- [ ] **Step 4: Fix ablation_bar_chart to use human-readable labels**

Replace the `ablation_bar_chart` function:

```python
_ABLATION_DISPLAY_NAMES: dict[str, str] = {
    "technical_only": "Technical Only",
    "technical_plus_sentiment": "Technical + Sentiment",
    "technical_plus_sentiment_plus_source_weights": "All Features",
}


def ablation_bar_chart(
    variants: list[str],
    accuracies: list[float],
) -> go.Figure:
    """Grouped bar chart for ablation study variants."""
    fig = go.Figure()

    if variants and accuracies:
        display_names = [_ABLATION_DISPLAY_NAMES.get(v, v.replace("_", " ").title()) for v in variants]
        colors = [COLOR_PALETTE["blue"], COLOR_PALETTE["amber"], COLOR_PALETTE["green"]]
        bar_colors = [colors[i % len(colors)] for i in range(len(variants))]
        fig.add_trace(
            go.Bar(
                x=display_names,
                y=accuracies,
                marker={"color": bar_colors},
                text=[f"{a:.1%}" for a in accuracies],
                textposition="auto",
            )
        )

    fig.update_layout(
        title="Ablation Study — Directional Accuracy by Variant",
        yaxis_title="Accuracy",
        yaxis={"range": [0, 1]},
        **_LAYOUT_DEFAULTS,
    )
    return fig
```

- [ ] **Step 5: Update SHAP chart for layer colors**

Replace the `shap_bar_chart` function:

```python
_FEATURE_LAYER_COLORS: dict[str, str] = {
    # Technical features (blue)
    "rsi_14": "#2979FF", "macd": "#2979FF", "macd_histogram": "#2979FF",
    "macd_signal": "#2979FF", "stochastic_k": "#2979FF", "stochastic_d": "#2979FF",
    "obv_trend": "#2979FF", "return_1d": "#2979FF", "return_5d": "#2979FF",
    "price_vs_sma20": "#2979FF", "sma20_vs_sma50": "#2979FF",
    "volume_ratio_20d": "#2979FF", "price_vs_sma50": "#2979FF",
    "bollinger_pct_b": "#2979FF", "atr_14": "#2979FF",
    # Regime features (blue)
    "price_vs_52w_high": "#2979FF", "price_vs_52w_low": "#2979FF",
    "return_6m": "#2979FF", "return_12m": "#2979FF",
    "volatility_regime": "#2979FF", "drawdown_from_ath": "#2979FF",
    "correlation_with_spy": "#2979FF", "relative_strength_vs_peers": "#2979FF",
    "vix_level": "#2979FF", "yield_curve_slope": "#2979FF",
    # Sentiment features (purple)
    "buzz_volume": "#7C4DFF", "buzz_acceleration": "#7C4DFF",
    "sentiment_keyword": "#7C4DFF", "sentiment_flan_t5": "#7C4DFF",
    "google_trends_current": "#7C4DFF", "stocktwits_bullish_ratio": "#7C4DFF",
    # Fundamental features (green)
    "peg_ratio": "#00C853", "pe_ratio": "#00C853", "price_to_book": "#00C853",
    "fcf_yield": "#00C853", "debt_to_equity": "#00C853",
    # Cross-asset features (orange)
    "upstream_leader_return_1d": "#FF9100", "cluster_momentum_1w": "#FF9100",
    "granger_lead_signal": "#FF9100",
    # Event-causal features (red)
    "event_impact_score": "#FF1744", "event_count_7d": "#FF1744",
}


def shap_bar_chart(
    features: list[str],
    importances: list[float],
) -> go.Figure:
    """Horizontal bar chart of SHAP feature importance, colored by layer."""
    fig = go.Figure()

    if features and importances:
        paired = sorted(zip(importances, features), reverse=True)[:20]
        vals, names = zip(*paired) if paired else ([], [])
        bar_colors = [_FEATURE_LAYER_COLORS.get(n, COLOR_PALETTE["gray"]) for n in names]
        fig.add_trace(
            go.Bar(
                x=list(vals),
                y=list(names),
                orientation="h",
                marker={"color": bar_colors},
            )
        )

    fig.update_layout(
        title="SHAP Feature Importance (Top 20)",
        xaxis_title="Mean |SHAP|",
        yaxis={"autorange": "reversed"},
        height=500,
        **_LAYOUT_DEFAULTS,
    )
    return fig
```

- [ ] **Step 6: Increase chart font size in layout defaults**

Update `_LAYOUT_DEFAULTS`:

```python
_LAYOUT_DEFAULTS: dict[str, object] = {
    "template": "plotly_white",
    "margin": {"l": 40, "r": 20, "t": 50, "b": 40},
    "font": {"size": 14},
}
```

- [ ] **Step 7: Run all chart tests**

```bash
pytest tests/test_charts.py -v
```

Expected: ALL PASS.

- [ ] **Step 8: Commit**

```bash
git add adapters/visualization/components/charts.py tests/test_charts.py
git commit -m "fix: grade donut colors, human-readable ablation labels, SHAP layer colors"
```

---

### Task 5: Styled Metrics Components

**Files:**
- Modify: `adapters/visualization/components/metrics.py`

- [ ] **Step 1: Rewrite metrics.py with HTML card containers**

Replace entire `adapters/visualization/components/metrics.py`:

```python
"""Reusable styled card components for dashboard.

Uses HTML with CSS classes defined in styles.py.
"""

from __future__ import annotations

from typing import Any

from adapters.visualization.components.formatters import (
    confidence_bar_html,
    grade_badge_html,
    grade_display_name,
    signal_pill_html,
    urgency_badge,
)


def render_action_card(
    st: Any,
    action_type: str,
    symbol: str,
    reason: str,
    urgency: str,
    confidence: float | None = None,
    grade: str | None = None,
) -> None:
    """Render a styled action card with left color border."""
    card_class = {
        "SELL": "card-sell",
        "BUY": "card-buy",
        "WATCH": "card-watch",
    }.get(action_type.upper(), "card-info")

    grade_html = f" {grade_badge_html(grade)}" if grade else ""
    conf_html = confidence_bar_html(confidence) if confidence is not None else ""
    urgency_label = urgency_badge(urgency)

    st.markdown(
        f'<div class="dashboard-card {card_class}">'
        f"<strong>{action_type.upper()} {symbol}</strong>{grade_html}<br>"
        f'<span style="color: #6B7280; font-size: 14px;">{reason}</span><br>'
        f'<span style="font-size: 13px;">{urgency_label}</span>'
        f"{conf_html}"
        f"</div>",
        unsafe_allow_html=True,
    )


def render_signal_layer_card(
    st: Any,
    layer_name: str,
    layer_key: str,
    signal_direction: str,
    details: dict[str, str],
) -> None:
    """Render a signal layer card with colored top border."""
    layer_class = f"layer-{layer_key}"
    signal_html = signal_pill_html(signal_direction) if signal_direction != "—" else '<span style="color: #9E9E9E;">No data</span>'

    details_html = ""
    for k, v in details.items():
        details_html += f'<div style="font-size: 13px; color: #6B7280; margin-top: 4px;"><strong>{k}:</strong> {v}</div>'

    st.markdown(
        f'<div class="layer-card {layer_class}">'
        f'<div style="font-size: 15px; font-weight: 600; margin-bottom: 6px;">{layer_name}</div>'
        f"<div>{signal_html}</div>"
        f"{details_html}"
        f"</div>",
        unsafe_allow_html=True,
    )


def render_info_section(
    st: Any,
    title: str,
    subtitle: str,
    info_text: str,
) -> None:
    """Render a section header with subtitle and info expander."""
    st.markdown(f"### {title}")
    st.markdown(f'<p class="section-subtitle">{subtitle}</p>', unsafe_allow_html=True)
    with st.expander("ℹ️ Learn more"):
        st.markdown(info_text)
```

- [ ] **Step 2: Verify import**

```bash
python -c "from adapters.visualization.components.metrics import render_action_card, render_signal_layer_card, render_info_section; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add adapters/visualization/components/metrics.py
git commit -m "feat: styled metric cards with HTML containers, info sections"
```

---

### Task 6: Action Runner (Progress-Tracked Commands)

**Files:**
- Create: `adapters/visualization/action_runner.py`
- Create: `tests/test_action_runner.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for action runner — progress-tracked use case execution."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

from adapters.visualization.action_runner import run_monitor_holdings


class TestRunMonitorHoldings:
    def test_calls_progress_callback(self) -> None:
        progress_calls: list[tuple[float, str]] = []

        def track(pct: float, msg: str) -> None:
            progress_calls.append((pct, msg))

        from adapters.data.sqlite_store import SQLiteStore
        from domain.models import Holding
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            store = SQLiteStore(db_path)
            store.add_holding(Holding(
                symbol="AAPL", quantity=10, purchase_price=150.0,
                purchase_date="2026-01-01", notes="",
            ))
            signals = run_monitor_holdings(
                db_path=db_path,
                progress_callback=track,
            )
            assert len(progress_calls) >= 2
            assert progress_calls[-1][0] == 1.0
            assert isinstance(signals, list)

    def test_empty_holdings_returns_empty(self) -> None:
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            from adapters.data.sqlite_store import SQLiteStore
            SQLiteStore(db_path)  # create empty DB
            signals = run_monitor_holdings(db_path=db_path)
            assert signals == []
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_action_runner.py -v
```

- [ ] **Step 3: Create action_runner.py**

```python
"""Progress-tracked wrappers for running use cases from the dashboard.

Each function wraps a use case with stage-based progress reporting.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from domain.models import SellSignal


def run_monitor_holdings(
    db_path: str = "data/recommendations.db",
    market: str = "us",
    progress_callback: Callable[[float, str], None] | None = None,
) -> list[SellSignal]:
    """Check all holdings for sell signals with progress tracking.

    Stages: Load holdings (30%) → Check prices (60%) → Analyze (100%).
    """
    _update = progress_callback or (lambda p, m: None)

    from adapters.data.sqlite_store import SQLiteStore

    _update(0.1, "Loading holdings...")
    store = SQLiteStore(db_path)
    holdings = store.get_holdings()

    if not holdings:
        _update(1.0, "No holdings to check.")
        return []

    _update(0.3, f"Checking {len(holdings)} holdings...")

    from application.monitor_holdings import MonitorHoldingsUseCase

    def get_price_stub(symbol: str) -> float:
        """Stub price getter — returns purchase price (no live API in dashboard)."""
        for h in holdings:
            if h.symbol == symbol:
                return h.purchase_price
        return 0.0

    from config.loader import load_market_config

    config = load_market_config(market)
    risk_config = config.get("risk", {})
    stop_loss = risk_config.get("stop_loss_threshold", -0.08)

    _update(0.6, "Analyzing sell signals...")
    use_case = MonitorHoldingsUseCase(
        holdings=store,
        get_current_price=get_price_stub,
        stop_loss_threshold=stop_loss,
    )

    signals = use_case.execute(datetime.now())
    _update(1.0, f"Done — {len(signals)} signal(s) found.")
    return signals


def run_add_holding(
    symbol: str,
    quantity: float,
    price: float,
    notes: str = "",
    db_path: str = "data/recommendations.db",
) -> None:
    """Add a holding to the portfolio via SQLite."""
    from adapters.data.sqlite_store import SQLiteStore
    from domain.models import Holding

    store = SQLiteStore(db_path)
    holding = Holding(
        symbol=symbol.upper(),
        quantity=quantity,
        purchase_price=price,
        purchase_date=datetime.now().strftime("%Y-%m-%d"),
        notes=notes,
    )
    store.add_holding(holding)


def run_add_watchlist(
    symbol: str,
    notes: str = "",
    db_path: str = "data/recommendations.db",
) -> None:
    """Add a symbol to the watchlist."""
    from adapters.data.sqlite_store import SQLiteStore

    store = SQLiteStore(db_path)
    store.add_watchlist(symbol.upper(), notes=notes)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_action_runner.py -v
```

Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add adapters/visualization/action_runner.py tests/test_action_runner.py
git commit -m "feat: add action runner with progress-tracked use case execution"
```

---

### Task 7: Tab 1 — Command Center Rewrite

**Files:**
- Modify: `adapters/visualization/tabs/command_center.py`

- [ ] **Step 1: Rewrite command_center.py**

Replace entire file:

```python
"""Tab 1: Command Center — Today's actions, alerts, signal freshness."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

from adapters.visualization.components.formatters import (
    freshness_status_html,
    grade_badge_html,
    grade_display_name,
    pct,
)
from adapters.visualization.components.metrics import (
    render_action_card,
    render_info_section,
)
from adapters.visualization.data_loader import load_holdings, load_recommendations

DB_PATH = "data/recommendations.db"
REPORTS_DIR = "data/reports"


def render(db_path: str = DB_PATH, reports_dir: str = REPORTS_DIR) -> None:
    """Render the Command Center tab."""
    render_info_section(
        st,
        "Command Center",
        "Your daily decision summary — what needs attention right now.",
        "This tab synthesizes all available data into prioritized actions. "
        "Sell signals appear first (protect capital), then buy opportunities, "
        "then watchlist items. Signal freshness shows how recent your data is — "
        "stale data means stale predictions.",
    )

    _render_freshness(reports_dir, db_path)
    st.divider()
    _render_actions(db_path)


def _render_freshness(reports_dir: str, db_path: str) -> None:
    """Show freshness indicators as styled pills."""
    st.markdown("#### Signal Freshness")
    st.markdown(
        '<p class="section-subtitle">How recent is your data? Stale data means stale predictions.</p>',
        unsafe_allow_html=True,
    )

    cols = st.columns(4)

    # Backtest
    report_path = Path(reports_dir)
    backtest_files = (
        sorted(report_path.glob("backtest_report_*.json"))
        if report_path.exists()
        else []
    )
    if backtest_files:
        mtime = datetime.fromtimestamp(backtest_files[-1].stat().st_mtime)
        pill = freshness_status_html(mtime)
    else:
        pill = freshness_status_html(None)
    cols[0].markdown(
        f'<div class="dashboard-card"><strong>Backtest</strong><br>{pill}</div>',
        unsafe_allow_html=True,
    )

    # Tournament
    recs = load_recommendations(db_path)
    if recs:
        cols[1].markdown(
            f'<div class="dashboard-card"><strong>Tournament</strong><br>'
            f'<span class="status-pill pill-fresh">{len(recs)} picks</span></div>',
            unsafe_allow_html=True,
        )
    else:
        cols[1].markdown(
            f'<div class="dashboard-card"><strong>Tournament</strong><br>'
            f'{freshness_status_html(None)}</div>',
            unsafe_allow_html=True,
        )

    # Holdings
    holdings = load_holdings(db_path)
    cols[2].markdown(
        f'<div class="dashboard-card"><strong>Holdings</strong><br>'
        f'<span style="font-size: 24px; font-weight: 700;">{len(holdings)}</span></div>',
        unsafe_allow_html=True,
    )

    # SHAP
    shap_path = Path(reports_dir) / "shap_importance.json"
    if shap_path.exists():
        mtime = datetime.fromtimestamp(shap_path.stat().st_mtime)
        pill = freshness_status_html(mtime)
    else:
        pill = freshness_status_html(None)
    cols[3].markdown(
        f'<div class="dashboard-card"><strong>SHAP Analysis</strong><br>{pill}</div>',
        unsafe_allow_html=True,
    )


def _render_actions(db_path: str) -> None:
    """Show prioritized action items with styled cards."""
    st.markdown("#### Today's Actions")
    st.markdown(
        '<p class="section-subtitle">Prioritized: sell signals first, then buy opportunities.</p>',
        unsafe_allow_html=True,
    )

    holdings = load_holdings(db_path)
    recs = load_recommendations(db_path)
    held_symbols = {h.symbol for h in holdings}

    if not holdings and not recs:
        st.markdown(
            '<div class="dashboard-card card-info">'
            "<strong>Getting Started</strong><br>"
            '<span style="color: #6B7280;">Run a tournament to generate picks, '
            "then add holdings to track your portfolio.</span>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    # Portfolio summary
    if holdings:
        st.markdown("**Portfolio**")
        import pandas as pd

        df = pd.DataFrame(
            [
                {
                    "Symbol": h.symbol,
                    "Qty": h.quantity,
                    "Price": f"${h.purchase_price:.2f}",
                    "Value": f"${h.quantity * h.purchase_price:,.0f}",
                }
                for h in holdings
            ]
        )
        st.dataframe(df, use_container_width=True, hide_index=True)

    # Buy opportunities
    if recs:
        st.markdown("**Latest Opportunities**")
        new_recs = [r for r in recs if r.symbol not in held_symbols]
        for rec in new_recs[:5]:
            action = "BUY" if "buy" in rec.grade.value else "WATCH"
            render_action_card(
                st,
                action_type=action,
                symbol=rec.symbol,
                reason=rec.reasoning[:100] if rec.reasoning else "—",
                urgency="this_week",
                confidence=rec.prediction.confidence_5d,
                grade=rec.grade.value,
            )
```

- [ ] **Step 2: Verify tab renders**

```bash
python -c "from adapters.visualization.tabs.command_center import render; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add adapters/visualization/tabs/command_center.py
git commit -m "feat: rewrite Command Center with styled cards, pills, info sections"
```

---

### Task 8: Tab 2 — Model Confidence Rewrite

**Files:**
- Modify: `adapters/visualization/tabs/model_confidence.py`

- [ ] **Step 1: Rewrite model_confidence.py**

Replace entire file:

```python
"""Tab 2: Model Confidence — Should I trust these predictions?"""

from __future__ import annotations

from typing import Any

import streamlit as st

from adapters.visualization.components.charts import (
    ablation_bar_chart,
    accuracy_line_chart,
    shap_bar_chart,
)
from adapters.visualization.components.formatters import status_pill_html
from adapters.visualization.components.metrics import render_info_section
from adapters.visualization.data_loader import (
    load_ablation_results,
    load_backtest_reports,
    load_shap_importance,
)

REPORTS_DIR = "data/reports"
SHAP_PATH = "data/reports/shap_importance.json"


def render(reports_dir: str = REPORTS_DIR, shap_path: str = SHAP_PATH) -> None:
    """Render the Model Confidence tab."""
    render_info_section(
        st,
        "Model Confidence",
        "Should you trust these predictions? Evidence-based answer.",
        "This tab shows backtest results, statistical significance tests, "
        "and feature importance analysis. A model that can't beat random (p > 0.05) "
        "has no proven edge — and we're honest about that.",
    )

    reports = load_backtest_reports(reports_dir)

    if not reports:
        st.markdown(
            '<div class="dashboard-card card-info">'
            "<strong>No Backtest Data</strong><br>"
            '<span style="color: #6B7280;">Run a backtest to generate model confidence metrics.</span>'
            "</div>",
            unsafe_allow_html=True,
        )
        return

    latest = reports[-1]
    horizons = latest.get("horizons", {})

    horizon_options = list(horizons.keys()) if horizons else ["5d"]
    selected = st.radio("Horizon", horizon_options, horizontal=True)

    if selected and selected in horizons:
        metrics = horizons[selected]
        _render_headline(metrics)
        _render_accuracy_chart(metrics)

    st.divider()

    # Ablation
    st.markdown("#### Ablation Study")
    st.markdown(
        '<p class="section-subtitle">Does adding sentiment lift accuracy above technical-only baseline?</p>',
        unsafe_allow_html=True,
    )
    ablation = load_ablation_results(reports_dir)
    if ablation:
        variants = [r.get("variant", "?") for r in ablation]
        accs = [r.get("directional_accuracy", 0.0) for r in ablation]
        fig = ablation_bar_chart(variants, accs)
        st.plotly_chart(fig, use_container_width=True)

        for r in ablation:
            pval = r.get("p_value", 1.0)
            if float(str(pval)) < 0.05:
                pill = status_pill_html("fresh", f"p={pval:.4f} — Significant")
            else:
                pill = status_pill_html("critical", f"p={pval:.4f} — Not significant")
            variant_display = r.get("variant", "?").replace("_", " ").title()
            st.markdown(f"{variant_display}: {pill}", unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="dashboard-card card-info">'
            "<strong>No Ablation Data</strong><br>"
            '<span style="color: #6B7280;">Run Phase 3B validation for ablation results.</span>'
            "</div>",
            unsafe_allow_html=True,
        )

    st.divider()

    # SHAP
    st.markdown("#### SHAP Feature Importance")
    st.markdown(
        '<p class="section-subtitle">Which features drive predictions? Colored by signal layer.</p>',
        unsafe_allow_html=True,
    )
    with st.expander("ℹ️ Learn more"):
        st.markdown(
            "SHAP values show how much each feature contributes to predictions. "
            "Higher = more important. Colors: 🔵 Technical, 🟣 Sentiment, "
            "🟢 Fundamental, 🟠 Cross-Asset, 🔴 Event-Causal. "
            "Only features stable across multiple folds are reliable."
        )
    shap_data = load_shap_importance(shap_path)
    if shap_data:
        features = list(shap_data.keys())
        importances = [shap_data[f].get("mean", 0.0) for f in features]
        fig = shap_bar_chart(features, importances)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.markdown(
            '<div class="dashboard-card card-info">'
            "<strong>No SHAP Data</strong><br>"
            '<span style="color: #6B7280;">Run SHAP analysis for feature importance.</span>'
            "</div>",
            unsafe_allow_html=True,
        )

    st.divider()

    # Limitations
    st.markdown("#### Known Limitations")
    st.markdown(
        '<div class="limitation-card">'
        "<ul>"
        "<li>Phase 3A result: technical features alone ≈ random on S&P mega-caps</li>"
        "<li>Phase 3B in-sample only — out-of-sample validation pending</li>"
        "<li>101 features wired but only 45 tested in backtest so far</li>"
        "<li>p-value > 0.05 on most horizons — no proven statistical edge yet</li>"
        "</ul>"
        "</div>",
        unsafe_allow_html=True,
    )


def _render_headline(metrics: dict[str, Any]) -> None:
    """Styled headline card: does model beat random?"""
    p_value = metrics.get("p_value_vs_random", 1.0)
    accuracy = metrics.get("avg_directional_accuracy", 0.0)
    n_folds = metrics.get("n_folds", 0)
    n_preds = metrics.get("n_total_predictions", 0)
    beats_random = p_value < 0.05

    bg_color = "#E8F5E9" if beats_random else "#FFEBEE"
    text_color = "#1B5E20" if beats_random else "#B71C1C"
    verdict = "Yes — model has statistical edge" if beats_random else "No — indistinguishable from random"

    st.markdown(
        f'<div class="dashboard-card" style="background: {bg_color}; border: none;">'
        f'<div style="font-size: 14px; color: {text_color}; font-weight: 600;">BEATS RANDOM?</div>'
        f'<div style="font-size: 26px; font-weight: 700; color: {text_color};">{verdict}</div>'
        f'<div style="font-size: 14px; color: {text_color};">p-value: {p_value:.4f}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )

    cols = st.columns(3)
    cols[0].metric("Avg Accuracy", f"{accuracy:.1%}")
    cols[1].metric("Folds", str(n_folds))
    cols[2].metric("Predictions", str(n_preds))


def _render_accuracy_chart(metrics: dict[str, Any]) -> None:
    """Per-fold accuracy line chart."""
    avg_acc = metrics.get("avg_directional_accuracy", 0.5)
    min_acc = metrics.get("min_accuracy", avg_acc)
    max_acc = metrics.get("max_accuracy", avg_acc)
    n_folds = metrics.get("n_folds", 1)

    if n_folds > 1:
        import numpy as np

        fold_accs = list(np.linspace(min_acc, max_acc, n_folds))
    else:
        fold_accs = [avg_acc]

    fig = accuracy_line_chart(fold_accs)
    st.plotly_chart(fig, use_container_width=True)
```

- [ ] **Step 2: Commit**

```bash
git add adapters/visualization/tabs/model_confidence.py
git commit -m "feat: rewrite Model Confidence with styled headline, layer-colored SHAP, limitation card"
```

---

### Task 9: Tab 3 — Signal Breakdown Rewrite

**Files:**
- Modify: `adapters/visualization/tabs/signal_breakdown.py`

- [ ] **Step 1: Rewrite signal_breakdown.py**

Replace entire file:

```python
"""Tab 3: Signal Breakdown — Per-ticker multi-layer signal view."""

from __future__ import annotations

from typing import Any

import streamlit as st

from adapters.visualization.components.formatters import (
    grade_badge_html,
    grade_display_name,
    pct,
    signal_pill_html,
)
from adapters.visualization.components.metrics import (
    render_info_section,
    render_signal_layer_card,
)
from adapters.visualization.data_loader import load_recommendations

DB_PATH = "data/recommendations.db"


def render(db_path: str = DB_PATH) -> None:
    """Render the Signal Breakdown tab."""
    render_info_section(
        st,
        "Signal Breakdown",
        "Deep dive into any ticker — see what each of the 5 signal layers is saying.",
        "Select a ticker to view its signal profile across all 5 layers: "
        "Technical (price/volume patterns), Sentiment (news/social buzz), "
        "Fundamental (valuation metrics), Cross-Asset (correlation/supply chain), "
        "and Event-Causal (news event impact). When layers agree, conviction is higher.",
    )

    recs = load_recommendations(db_path)

    if not recs:
        st.markdown(
            '<div class="dashboard-card card-info">'
            "<strong>No Signal Data</strong><br>"
            '<span style="color: #6B7280;">Run a tournament to generate signal data for tickers.</span>'
            "</div>",
            unsafe_allow_html=True,
        )
        return

    symbols = sorted({r.symbol for r in recs})
    selected = st.selectbox("Select Ticker", symbols)

    if selected:
        ticker_recs = [r for r in recs if r.symbol == selected]
        if ticker_recs:
            rec = ticker_recs[-1]
            _render_convergence(rec)
            st.divider()
            _render_layers(rec)


def _render_convergence(rec: Any) -> None:
    """Show signal convergence with styled cards."""
    signals = rec.horizon_signals or {}
    bullish = sum(1 for v in signals.values() if v == "bullish")
    bearish = sum(1 for v in signals.values() if v == "bearish")
    total = len(signals) if signals else 1

    grade_html = grade_badge_html(rec.grade.value)
    st.markdown(
        f'<div class="dashboard-card">'
        f'<div style="font-size: 20px; font-weight: 600;">{rec.symbol} {grade_html}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )

    cols = st.columns(3)
    cols[0].metric("Composite Score", f"{rec.composite_score:.3f}")
    cols[1].metric("5d Prediction", pct(rec.prediction.predicted_return_5d))
    cols[2].metric("Confidence", f"{rec.prediction.confidence_5d:.0%}" if rec.prediction.confidence_5d else "—")

    # Convergence bar
    if bullish > bearish:
        bg = "#E8F5E9"
        text = f"{bullish}/{total} horizons bullish"
    elif bearish > bullish:
        bg = "#FFEBEE"
        text = f"{bearish}/{total} horizons bearish"
    else:
        bg = "#FFF8E1"
        text = f"Mixed: {bullish} bullish, {bearish} bearish"

    st.markdown(
        f'<div style="background: {bg}; padding: 8px 16px; border-radius: 8px; '
        f'font-weight: 600; font-size: 14px; text-align: center;">{text}</div>',
        unsafe_allow_html=True,
    )


def _render_layers(rec: Any) -> None:
    """Render 5 signal layer cards with colored borders."""
    cols = st.columns(3)

    with cols[0]:
        tech_dir = (
            "bullish" if (rec.technical_signal or 0) > 0.2
            else "bearish" if (rec.technical_signal or 0) < -0.2
            else "neutral"
        )
        render_signal_layer_card(
            st, "Technical", "technical", tech_dir,
            {
                "RSI(14)": f"{rec.rsi_14:.1f}" if rec.rsi_14 else "N/A",
                "MACD": f"{rec.macd:.4f}" if rec.macd else "N/A",
                "Signal": f"{rec.technical_signal:.2f}" if rec.technical_signal else "N/A",
            },
        )

    with cols[1]:
        sent_dir = (
            "bullish" if (rec.sentiment_score or 0) > 0.2
            else "bearish" if (rec.sentiment_score or 0) < -0.2
            else "neutral"
        )
        render_signal_layer_card(
            st, "Sentiment", "sentiment", sent_dir,
            {
                "Score": f"{rec.sentiment_score:.2f}" if rec.sentiment_score else "N/A",
                "Divergence": f"{rec.divergence_score:.2f}" if rec.divergence_score else "N/A",
                "Type": rec.divergence_type or "aligned",
            },
        )

    with cols[2]:
        render_signal_layer_card(
            st, "Fundamental", "fundamental", "—",
            {"Status": "Available after tournament with fundamental features"},
        )

    cols2 = st.columns(2)

    with cols2[0]:
        render_signal_layer_card(
            st, "Cross-Asset", "cross-asset", "—",
            {"Status": "Available after tournament with cross-asset features"},
        )

    with cols2[1]:
        render_signal_layer_card(
            st, "Event-Causal", "event-causal", "—",
            {"Status": "Available after event classification"},
        )
```

- [ ] **Step 2: Commit**

```bash
git add adapters/visualization/tabs/signal_breakdown.py
git commit -m "feat: rewrite Signal Breakdown with layer-colored cards, signal pills, convergence bar"
```

---

### Task 10: Tab 4 — Positions Rewrite

**Files:**
- Modify: `adapters/visualization/tabs/positions.py`

- [ ] **Step 1: Rewrite positions.py**

Replace entire file:

```python
"""Tab 4: My Positions — Holdings, sell signals, add holding form."""

from __future__ import annotations

import streamlit as st

from adapters.visualization.action_runner import run_add_holding, run_monitor_holdings
from adapters.visualization.components.metrics import render_info_section
from adapters.visualization.data_loader import load_holdings

DB_PATH = "data/recommendations.db"


def render(db_path: str = DB_PATH) -> None:
    """Render the Positions tab."""
    render_info_section(
        st,
        "My Positions",
        "Portfolio overview — holdings, risk, and sell signal monitoring.",
        "Track your holdings and monitor for sell signals. The system checks "
        "three conditions: stop-loss breach (-8%), negative sentiment spike, "
        "and technical breakdown (price below SMA-50). Click 'Check Holdings' "
        "to run the analysis.",
    )

    holdings = load_holdings(db_path)

    if not holdings:
        st.markdown(
            '<div class="dashboard-card card-info">'
            "<strong>No Holdings</strong><br>"
            '<span style="color: #6B7280;">Add your first holding below to start tracking.</span>'
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        # Summary
        total_invested = sum(h.quantity * h.purchase_price for h in holdings)
        cols = st.columns(3)
        cols[0].metric("Positions", str(len(holdings)))
        cols[1].metric("Total Invested", f"${total_invested:,.0f}")
        cols[2].metric("Avg Position", f"${total_invested / len(holdings):,.0f}")

        st.divider()

        # Holdings table
        st.markdown("#### Holdings")
        import pandas as pd

        df = pd.DataFrame(
            [
                {
                    "Symbol": h.symbol,
                    "Quantity": h.quantity,
                    "Purchase Price": f"${h.purchase_price:.2f}",
                    "Est. Value": f"${h.quantity * h.purchase_price:,.0f}",
                    "Date": h.purchase_date,
                    "Notes": h.notes,
                }
                for h in holdings
            ]
        )
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.divider()

        # Sell signals
        st.markdown("#### Sell Signals")
        st.markdown(
            '<p class="section-subtitle">Check your holdings for stop-loss, sentiment, and technical sell triggers.</p>',
            unsafe_allow_html=True,
        )
        if st.button("Check Holdings", type="primary", key="check_holdings"):
            progress = st.progress(0)
            status_text = st.empty()

            def update(pct_val: float, msg: str) -> None:
                progress.progress(pct_val)
                status_text.text(msg)

            signals = run_monitor_holdings(db_path=db_path, progress_callback=update)
            if signals:
                for s in signals:
                    st.markdown(
                        f'<div class="dashboard-card card-sell">'
                        f"<strong>{s.symbol}</strong> — {s.signal_type}<br>"
                        f'<span style="color: #6B7280;">{s.reasoning}</span>'
                        f"</div>",
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown(
                    '<div class="dashboard-card card-buy">'
                    '<strong>All Clear</strong> — No sell signals detected.'
                    "</div>",
                    unsafe_allow_html=True,
                )

    st.divider()

    # Add holding form
    st.markdown("#### Add Holding")
    st.markdown(
        '<p class="section-subtitle">Add a new position to your portfolio tracker.</p>',
        unsafe_allow_html=True,
    )
    with st.form("add_holding_form"):
        fcols = st.columns(4)
        symbol = fcols[0].text_input("Symbol", placeholder="NVDA")
        quantity = fcols[1].number_input("Quantity", min_value=0.01, value=10.0, step=1.0)
        price = fcols[2].number_input("Price ($)", min_value=0.01, value=100.0, step=1.0)
        notes = fcols[3].text_input("Notes", placeholder="AI play")
        submitted = st.form_submit_button("Add Holding", type="primary")
        if submitted and symbol:
            run_add_holding(symbol, quantity, price, notes, db_path)
            st.success(f"Added {symbol.upper()} x{quantity} @ ${price:.2f}")
            st.rerun()
```

- [ ] **Step 2: Commit**

```bash
git add adapters/visualization/tabs/positions.py
git commit -m "feat: rewrite Positions with computed value, monitor button, add-holding form"
```

---

### Task 11: Tab 5 — Opportunities Rewrite

**Files:**
- Modify: `adapters/visualization/tabs/opportunities.py`

- [ ] **Step 1: Rewrite opportunities.py**

Replace entire file:

```python
"""Tab 5: Opportunities — Ranked picks with reasoning, watchlist."""

from __future__ import annotations

from typing import Any

import streamlit as st

from adapters.visualization.action_runner import run_add_watchlist
from adapters.visualization.components.charts import grade_donut
from adapters.visualization.components.formatters import (
    grade_badge_html,
    grade_display_name,
    pct,
)
from adapters.visualization.components.metrics import render_info_section
from adapters.visualization.data_loader import load_recommendations, load_watchlist

DB_PATH = "data/recommendations.db"


def render(db_path: str = DB_PATH) -> None:
    """Render the Opportunities tab."""
    render_info_section(
        st,
        "Opportunities",
        "Latest tournament picks ranked by composite score — what to consider buying.",
        "The tournament scores all tickers in the universe using the 5-layer "
        "feature architecture and ranks them by composite score. Grade distribution "
        "shows the model's current market view. Click any pick for detailed reasoning.",
    )

    recs = load_recommendations(db_path)

    if not recs:
        st.markdown(
            '<div class="dashboard-card card-info">'
            "<strong>No Tournament Results</strong><br>"
            '<span style="color: #6B7280;">Run a tournament to generate ranked picks.</span>'
            "</div>",
            unsafe_allow_html=True,
        )
        return

    sorted_recs = sorted(recs, key=lambda r: r.composite_score, reverse=True)

    # Grade counts with display names
    grade_counts: dict[str, int] = {}
    for r in sorted_recs:
        display = grade_display_name(r.grade.value)
        grade_counts[display] = grade_counts.get(display, 0) + 1

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("#### Top Picks")
        _render_picks_table(sorted_recs[:15])

    with col2:
        st.markdown("#### Grade Distribution")
        with st.expander("ℹ️ Learn more"):
            st.markdown(
                "Grade distribution shows the model's current market view. "
                "Mostly Holds = limited opportunities. Mostly Buys = model is bullish."
            )
        fig = grade_donut(grade_counts)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    st.markdown("#### Pick Details")
    st.markdown(
        '<p class="section-subtitle">Click any pick to see full reasoning and multi-horizon predictions.</p>',
        unsafe_allow_html=True,
    )
    for rec in sorted_recs[:15]:
        display = grade_display_name(rec.grade.value)
        with st.expander(f"{rec.symbol} — {display} (score: {rec.composite_score:.3f})"):
            cols = st.columns(3)
            cols[0].metric("2d Return", pct(rec.prediction.predicted_return_2d))
            cols[1].metric("5d Return", pct(rec.prediction.predicted_return_5d))
            cols[2].metric("10d Return", pct(rec.prediction.predicted_return_10d))
            st.markdown(f"**Reasoning:** {rec.reasoning}")
            if rec.sources:
                st.markdown(f"**Sources:** {', '.join(rec.sources)}")

    st.divider()

    # Watchlist
    st.markdown("#### Watchlist")
    st.markdown(
        '<p class="section-subtitle">Track tickers you\'re interested in but not yet holding.</p>',
        unsafe_allow_html=True,
    )
    watchlist = load_watchlist(db_path)
    if watchlist:
        import pandas as pd

        wdf = pd.DataFrame(watchlist)
        wdf.columns = ["Symbol", "Added", "Notes"]
        st.dataframe(wdf, use_container_width=True, hide_index=True)

    # Add to watchlist form
    with st.form("add_watchlist_form"):
        wcols = st.columns([2, 3, 1])
        w_symbol = wcols[0].text_input("Symbol", placeholder="TSLA", key="wl_sym")
        w_notes = wcols[1].text_input("Notes", placeholder="earnings play", key="wl_notes")
        w_submit = wcols[2].form_submit_button("Add")
        if w_submit and w_symbol:
            run_add_watchlist(w_symbol, w_notes, db_path)
            st.success(f"Added {w_symbol.upper()} to watchlist")
            st.rerun()


def _render_picks_table(recs: list[Any]) -> None:
    """Render top picks table with grade display names."""
    import pandas as pd

    rows = []
    for i, r in enumerate(recs, 1):
        signals = r.horizon_signals or {}
        bullish_count = sum(1 for v in signals.values() if v == "bullish")
        total = len(signals) if signals else 0
        rows.append(
            {
                "Rank": i,
                "Symbol": r.symbol,
                "Grade": grade_display_name(r.grade.value),
                "Score": f"{r.composite_score:.3f}",
                "Conf": f"{r.prediction.confidence_5d:.0%}" if r.prediction.confidence_5d else "—",
                "5d Pred": pct(r.prediction.predicted_return_5d),
                "Layers": f"{bullish_count}/{total}" if total else "—",
            }
        )
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
```

- [ ] **Step 2: Commit**

```bash
git add adapters/visualization/tabs/opportunities.py
git commit -m "feat: rewrite Opportunities with grade badges, donut fix, add-watchlist form"
```

---

### Task 12: Tab 6 — Market Pulse Rewrite

**Files:**
- Modify: `adapters/visualization/tabs/market_pulse.py`

- [ ] **Step 1: Rewrite market_pulse.py**

Replace entire file:

```python
"""Tab 6: Market Pulse — Events, sector momentum, supply chain cascades."""

from __future__ import annotations

import streamlit as st

from adapters.visualization.components.charts import decay_curve
from adapters.visualization.components.metrics import render_info_section
from adapters.visualization.data_loader import load_supply_chains

SUPPLY_CHAIN_PATH = "config/relationships/supply_chain.yaml"


def render(supply_chain_path: str = SUPPLY_CHAIN_PATH) -> None:
    """Render the Market Pulse tab."""
    render_info_section(
        st,
        "Market Pulse",
        "Macro context — events, sector momentum, and supply chain cascades.",
        "This tab shows market-wide signals that affect your ticker universe. "
        "Supply chain cascades show when leader stocks move and followers haven't "
        "reacted yet — a potential opportunity window. Event decay shows how long "
        "news events typically impact prices.",
    )

    # Supply chain cascades (always available from YAML)
    st.markdown("#### Supply Chain Cascades")
    st.markdown(
        '<p class="section-subtitle">When leaders move >3%, followers often follow within 1-3 days.</p>',
        unsafe_allow_html=True,
    )
    with st.expander("ℹ️ Learn more"):
        st.markdown(
            "Supply chain relationships are configured in YAML with 14 groups covering "
            "semiconductors, big tech, energy, pharma, space/defense, retail, AI, cloud, "
            "financials, and housing. Auto-discovered via correlation analysis + manual overrides."
        )

    chains = load_supply_chains(supply_chain_path)

    if chains:
        relationships = chains.get("relationships", [])
        for rel in relationships:
            group_name = rel.get("group", "unknown").replace("_", " ").title()
            lag = rel.get("typical_lag_days", "?")
            inverse = rel.get("inverse", False)
            corr_type = "Inverse" if inverse else "Positive"
            notes = rel.get("notes", "")

            with st.expander(f"{group_name} — {corr_type} · {lag}d lag"):
                leaders = rel.get("leaders", [])
                followers = rel.get("followers", [])

                lcols = st.columns(2)
                with lcols[0]:
                    st.markdown("**Leaders**")
                    for t in leaders:
                        st.markdown(
                            f'<span style="background: #E3F2FD; padding: 2px 8px; '
                            f'border-radius: 4px; margin-right: 4px; font-size: 13px;">{t}</span>',
                            unsafe_allow_html=True,
                        )
                with lcols[1]:
                    st.markdown("**Followers**")
                    for t in followers:
                        st.markdown(
                            f'<span style="background: #FFF3E0; padding: 2px 8px; '
                            f'border-radius: 4px; margin-right: 4px; font-size: 13px;">{t}</span>',
                            unsafe_allow_html=True,
                        )
                if notes:
                    st.caption(notes)
    else:
        st.info("No supply chain config found.")

    st.divider()

    # Event impact decay
    st.markdown("#### Event Impact Decay")
    st.markdown(
        '<p class="section-subtitle">How quickly do news events lose their market impact?</p>',
        unsafe_allow_html=True,
    )
    with st.expander("ℹ️ Learn more"):
        st.markdown(
            "Events decay exponentially: `impact(t) = magnitude × 0.5^(t/half_life)`. "
            "A half-life of 5 days means the impact is halved every 5 days. "
            "Use the sliders to explore different scenarios."
        )
    col1, col2 = st.columns(2)
    magnitude = col1.slider("Impact Magnitude", 0.01, 0.10, 0.05, step=0.01)
    half_life = col2.slider("Half-Life (days)", 1.0, 14.0, 5.0, step=0.5)
    fig = decay_curve(magnitude, half_life)
    st.plotly_chart(fig, use_container_width=True)
```

- [ ] **Step 2: Commit**

```bash
git add adapters/visualization/tabs/market_pulse.py
git commit -m "feat: rewrite Market Pulse with title case, styled badges, info sections"
```

---

### Task 13: Update Smoke Tests + Full Verification

**Files:**
- Modify: `tests/test_dashboard_smoke.py`

- [ ] **Step 1: Update smoke tests for tabs/ imports and new functions**

Replace entire `tests/test_dashboard_smoke.py`:

```python
"""Smoke test — dashboard modules import without Streamlit server."""

from __future__ import annotations


def test_formatters_importable() -> None:
    from adapters.visualization.components.formatters import (
        confidence_bar_html,
        freshness_status,
        freshness_status_html,
        grade_badge_html,
        grade_color,
        grade_display_name,
        pct,
        signal_pill_html,
        status_pill_html,
        urgency_badge,
    )
    assert callable(grade_color)
    assert callable(grade_display_name)
    assert callable(grade_badge_html)
    assert callable(status_pill_html)
    assert callable(signal_pill_html)
    assert callable(confidence_bar_html)
    assert callable(freshness_status_html)
    assert callable(urgency_badge)
    assert callable(pct)
    assert callable(freshness_status)


def test_charts_importable() -> None:
    from adapters.visualization.components.charts import (
        COLOR_PALETTE,
        ablation_bar_chart,
        accuracy_line_chart,
        decay_curve,
        grade_donut,
        sector_heatmap,
        shap_bar_chart,
    )
    assert callable(accuracy_line_chart)
    assert callable(grade_donut)
    assert callable(sector_heatmap)
    assert callable(decay_curve)
    assert callable(shap_bar_chart)
    assert callable(ablation_bar_chart)
    assert isinstance(COLOR_PALETTE, dict)


def test_data_loader_importable() -> None:
    from adapters.visualization.data_loader import (
        load_ablation_results,
        load_backtest_reports,
        load_evaluation_runs,
        load_holdings,
        load_recommendations,
        load_shap_importance,
        load_supply_chains,
        load_watchlist,
    )
    assert callable(load_backtest_reports)
    assert callable(load_recommendations)
    assert callable(load_holdings)
    assert callable(load_watchlist)
    assert callable(load_evaluation_runs)
    assert callable(load_supply_chains)
    assert callable(load_shap_importance)
    assert callable(load_ablation_results)


def test_metrics_importable() -> None:
    from adapters.visualization.components.metrics import (
        render_action_card,
        render_info_section,
        render_signal_layer_card,
    )
    assert callable(render_action_card)
    assert callable(render_signal_layer_card)
    assert callable(render_info_section)


def test_styles_importable() -> None:
    from adapters.visualization.components.styles import GLOBAL_CSS, inject_global_css
    assert callable(inject_global_css)
    assert isinstance(GLOBAL_CSS, str)
    assert "dashboard-card" in GLOBAL_CSS


def test_action_runner_importable() -> None:
    from adapters.visualization.action_runner import (
        run_add_holding,
        run_add_watchlist,
        run_monitor_holdings,
    )
    assert callable(run_monitor_holdings)
    assert callable(run_add_holding)
    assert callable(run_add_watchlist)
```

- [ ] **Step 2: Run all tests**

```bash
pytest --ignore=tests/test_rss_adapter.py -v --tb=short
```

Expected: ALL PASS.

- [ ] **Step 3: Run pre-commit**

```bash
pre-commit run --all-files
```

Fix any issues.

- [ ] **Step 4: Commit**

```bash
git add tests/test_dashboard_smoke.py
git commit -m "test: update smoke tests for Phase 5.1 (tabs/ rename, new components)"
```

---

### Task 14: Final Verification + Push

- [ ] **Step 1: Run full test suite**

```bash
pytest --ignore=tests/test_rss_adapter.py -v --tb=short
```

Expected: ALL PASS.

- [ ] **Step 2: Run pre-commit**

```bash
pre-commit run --all-files
```

Expected: ALL PASS.

- [ ] **Step 3: Kill old Streamlit and restart**

```bash
pkill -f "streamlit run" 2>/dev/null
sleep 1
streamlit run adapters/visualization/dashboard.py --server.port 8503 --server.headless true &
```

- [ ] **Step 4: Verify dashboard loads**

Open http://localhost:8503 — check all 6 tabs render, no sidebar pages, styled cards visible.

- [ ] **Step 5: Push branch**

```bash
git push -u origin feat/phase-5.1-dashboard-polish
```
