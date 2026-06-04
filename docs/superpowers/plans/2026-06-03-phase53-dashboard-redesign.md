# Phase 5.3: Dashboard Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the dashboard from a data dump into a WealthSimple-inspired personal investment tool with 5 tabs, compact opportunity cards, auto-scan, smart caching, guided onboarding, and conversational voice.

**Architecture:** Complete CSS theme rewrite + 5 tab rewrites + new components (hero panels, compact cards, onboarding, progress bars) + auto-scan with cache + signal breakdown merged into cards. All within Streamlit using CSS injection + st.html().

**Tech Stack:** Python 3.12+, Streamlit, Plotly, CSS3, existing conviction/outcome/learning engines.

**Design Spec:** `docs/superpowers/specs/2026-06-03-phase53-dashboard-redesign.md`

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `adapters/visualization/components/hero.py` | 3-panel hero section (Market, Portfolio, Signal) |
| `adapters/visualization/components/onboarding.py` | First-run onboarding card |
| `adapters/visualization/components/compact_card.py` | Compact opportunity card with expandable signal breakdown |
| `adapters/visualization/components/progress.py` | Learning progress bar component |
| `adapters/visualization/tabs/watchlist.py` | Tab 2: Watchlist + historical recommendations |
| `adapters/visualization/cache.py` | Smart scan cache (15min market / 60min after hours) |
| `tests/test_cache.py` | Cache logic tests |
| `tests/test_hero.py` | Hero component tests |
| `tests/test_compact_card.py` | Compact card tests |

### Modified Files

| File | Change |
|------|--------|
| `adapters/visualization/components/styles.py` | Complete CSS theme rewrite — DM Sans, new palette, rounded cards |
| `adapters/visualization/dashboard.py` | 5 tabs, no emoji labels, minimal header |
| `adapters/visualization/tabs/command_center.py` | Full rewrite → Today's Opportunities with auto-scan + hero + compact cards |
| `adapters/visualization/tabs/positions.py` | Rewrite → My Portfolio with inline CRUD + signal report |
| `adapters/visualization/tabs/model_confidence.py` | Rewrite → How It Works with collapsible sections + progress bar |
| `adapters/visualization/tabs/market_pulse.py` | Polish — data pipeline grid, consistent card styling |
| `adapters/visualization/data_loader.py` | Add load helpers for cache, watchlist conviction |
| `adapters/visualization/action_runner.py` | Update scan to work with cache |

### Deleted Files

| File | Reason |
|------|--------|
| `adapters/visualization/tabs/signal_breakdown.py` | Merged into compact card expand |
| `adapters/visualization/tabs/opportunities.py` | Tournament tab killed, replaced by watchlist.py |

---

## Task 1: CSS Theme Rewrite

**Files:**
- Modify: `adapters/visualization/components/styles.py`

- [ ] **Step 1: Replace GLOBAL_CSS with new WealthSimple-inspired theme**

Complete rewrite of the CSS. New theme:

```python
GLOBAL_CSS = """
<style>
/* ===== Fonts ===== */
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

/* ===== Base ===== */
:root {
    --bg-primary: #FFFFFF;
    --bg-secondary: #F8FAFC;
    --bg-card: #FFFFFF;
    --border: #E2E8F0;
    --text-primary: #1A202C;
    --text-secondary: #64748B;
    --text-muted: #94A3B8;
    --accent: #2563EB;
    --success: #16A34A;
    --warning: #D97706;
    --danger: #DC2626;
}

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    color: var(--text-primary);
    background: var(--bg-secondary);
}

h1, h2, h3, h4 {
    font-family: 'DM Sans', sans-serif;
    color: var(--text-primary);
}
h1 { font-size: 24px !important; font-weight: 700 !important; }
h2 { font-size: 18px !important; font-weight: 600 !important; }
h3 { font-size: 15px !important; font-weight: 600 !important; }

/* ===== Hide Streamlit chrome ===== */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header [data-testid="stToolbar"] {visibility: hidden;}

/* ===== Tabs ===== */
.stTabs [data-baseweb="tab-list"] {
    gap: 0;
    border-bottom: 1px solid var(--border);
}
.stTabs [data-baseweb="tab-list"] button {
    font-family: 'DM Sans', sans-serif;
    font-weight: 500;
    font-size: 14px;
    padding: 12px 20px;
    color: var(--text-secondary);
    border-bottom: 2px solid transparent;
}
.stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
    color: var(--accent) !important;
    border-bottom-color: var(--accent) !important;
    font-weight: 600;
}

/* ===== Cards ===== */
.ws-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 1.25rem;
    margin-bottom: 0.75rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    transition: all 0.2s ease;
}
.ws-card:hover {
    box-shadow: 0 4px 16px rgba(0,0,0,0.08);
    transform: translateY(-1px);
}

/* ===== Hero panels ===== */
.hero-panel {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 1.25rem;
    height: 100%;
}
.hero-panel .hero-label {
    font-family: 'DM Sans', sans-serif;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
    margin-bottom: 8px;
}
.hero-panel .hero-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 22px;
    font-weight: 700;
    color: var(--text-primary);
}
.hero-panel .hero-sub {
    font-size: 13px;
    color: var(--text-secondary);
    margin-top: 4px;
}

/* ===== Opportunity cards ===== */
.opp-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 1rem 1.25rem;
    margin-bottom: 0.5rem;
    transition: all 0.2s ease;
}
.opp-card:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.06);
}
.opp-card-high { border-left: 4px solid var(--success); }
.opp-card-mid { border-left: 4px solid var(--warning); }
.opp-card-low { border-left: 4px solid var(--danger); }

/* ===== Conviction bar ===== */
.conviction-bar {
    height: 6px;
    border-radius: 3px;
    background: var(--border);
    width: 120px;
    display: inline-block;
    vertical-align: middle;
    margin: 0 8px;
}
.conviction-bar-fill {
    height: 100%;
    border-radius: 3px;
    transition: width 0.5s ease;
}

/* ===== Progress bar ===== */
.learning-progress {
    height: 10px;
    border-radius: 5px;
    background: var(--border);
    margin: 12px 0;
}
.learning-progress-fill {
    height: 100%;
    border-radius: 5px;
    background: linear-gradient(90deg, var(--accent), #7C3AED);
    transition: width 0.8s ease;
}

/* ===== Badges ===== */
.badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 600;
    font-family: 'DM Sans', sans-serif;
    letter-spacing: 0.02em;
}
.badge-buy { background: #DCFCE7; color: #166534; }
.badge-sell { background: #FEE2E2; color: #991B1B; }
.badge-watch { background: #FEF3C7; color: #92400E; }
.badge-hold { background: #F1F5F9; color: #475569; }
.badge-fresh { color: var(--success); }
.badge-recent { color: var(--warning); }
.badge-stale { color: var(--danger); }

/* ===== Onboarding ===== */
.onboarding-card {
    background: linear-gradient(135deg, #EEF2FF, #F8FAFC);
    border: 1px solid #C7D2FE;
    border-radius: 20px;
    padding: 2rem;
    text-align: center;
    max-width: 600px;
    margin: 2rem auto;
}
.onboarding-step {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    text-align: left;
    margin: 16px 0;
    padding: 12px;
    background: white;
    border-radius: 12px;
    border: 1px solid var(--border);
}
.onboarding-num {
    background: var(--accent);
    color: white;
    width: 28px;
    height: 28px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 13px;
    flex-shrink: 0;
}

/* ===== Status dots ===== */
.status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    display: inline-block;
    margin-right: 6px;
}
.status-green { background: var(--success); }
.status-amber { background: var(--warning); }
.status-red { background: var(--danger); }

/* ===== Data grid ===== */
.data-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 12px;
    margin: 12px 0;
}

/* ===== Skeleton loading ===== */
@keyframes shimmer {
    0% { background-position: -200px 0; }
    100% { background-position: 200px 0; }
}
.skeleton {
    background: linear-gradient(90deg, #F1F5F9 25%, #E2E8F0 50%, #F1F5F9 75%);
    background-size: 400px 100%;
    animation: shimmer 1.5s infinite;
    border-radius: 8px;
    height: 20px;
    margin: 8px 0;
}

/* ===== Footer ===== */
.ws-footer {
    text-align: center;
    color: var(--text-muted);
    font-size: 12px;
    padding: 2rem 0 1rem;
    border-top: 1px solid var(--border);
    margin-top: 2rem;
}

/* ===== Buttons ===== */
.stButton > button[kind="primary"] {
    background: var(--accent);
    border: none;
    border-radius: 10px;
    font-family: 'DM Sans', sans-serif;
    font-weight: 600;
    padding: 8px 20px;
}
.stButton > button[kind="secondary"] {
    background: transparent;
    border: 1px solid var(--border);
    border-radius: 10px;
    font-family: 'DM Sans', sans-serif;
    color: var(--text-secondary);
}

/* ===== Expander ===== */
.streamlit-expanderHeader {
    font-family: 'DM Sans', sans-serif;
    font-weight: 600;
    font-size: 15px;
    color: var(--text-primary);
}
</style>
"""
```

Keep `inject_global_css()` function unchanged.

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/test_formatters.py tests/test_dashboard_smoke.py -v --tb=short`

- [ ] **Step 3: Commit**

```bash
git add adapters/visualization/components/styles.py
git commit -m "feat: complete CSS theme rewrite — DM Sans, WealthSimple palette, rounded cards, badges"
```

---

## Task 2: Smart Scan Cache

**Files:**
- Create: `adapters/visualization/cache.py`
- Test: `tests/test_cache.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for smart scan cache."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from adapters.visualization.cache import ScanCache

ET = ZoneInfo("America/New_York")


class TestScanCache:
    def test_empty_cache_is_stale(self) -> None:
        cache = ScanCache()
        assert cache.is_stale() is True

    def test_fresh_cache_not_stale_after_hours(self) -> None:
        cache = ScanCache()
        cache.store([], datetime.now(ET))
        assert cache.is_stale() is False

    def test_stale_after_timeout(self) -> None:
        cache = ScanCache()
        old_time = datetime.now(ET) - timedelta(minutes=61)
        cache.store([], old_time)
        assert cache.is_stale() is True

    def test_market_hours_shorter_cache(self) -> None:
        cache = ScanCache()
        # 16 minutes ago during "market hours"
        market_time = datetime(2026, 6, 3, 10, 0, tzinfo=ET)
        cache.store([], market_time)
        now = datetime(2026, 6, 3, 10, 16, tzinfo=ET)
        assert cache.is_stale(now=now) is True

    def test_after_hours_longer_cache(self) -> None:
        cache = ScanCache()
        # 30 minutes ago after hours
        after_time = datetime(2026, 6, 3, 18, 0, tzinfo=ET)
        cache.store([], after_time)
        now = datetime(2026, 6, 3, 18, 30, tzinfo=ET)
        assert cache.is_stale(now=now) is False

    def test_get_results(self) -> None:
        cache = ScanCache()
        cards = [{"ticker": "NVDA"}]
        cache.store(cards, datetime.now(ET))
        assert cache.get_results() == [{"ticker": "NVDA"}]

    def test_minutes_ago(self) -> None:
        cache = ScanCache()
        cache.store([], datetime.now(ET) - timedelta(minutes=5))
        assert 4 <= cache.minutes_ago() <= 6
```

- [ ] **Step 2: Implement cache**

```python
"""Smart scan cache — 15min during market hours, 60min after hours."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

_MARKET_OPEN = (9, 30)
_MARKET_CLOSE = (16, 0)
_CACHE_MARKET_MINUTES = 15
_CACHE_AFTER_MINUTES = 60


def _is_market_hours(now: datetime) -> bool:
    t = now.astimezone(ET)
    minutes = t.hour * 60 + t.minute
    return _MARKET_OPEN[0] * 60 + _MARKET_OPEN[1] <= minutes <= _MARKET_CLOSE[0] * 60 + _MARKET_CLOSE[1]


class ScanCache:
    """Cache for conviction scan results with smart TTL."""

    def __init__(self) -> None:
        self._results: list[Any] = []
        self._timestamp: datetime | None = None

    def store(self, results: list[Any], timestamp: datetime) -> None:
        self._results = results
        self._timestamp = timestamp

    def get_results(self) -> list[Any]:
        return list(self._results)

    def is_stale(self, now: datetime | None = None) -> bool:
        if self._timestamp is None:
            return True
        now = now or datetime.now(ET)
        ttl = _CACHE_MARKET_MINUTES if _is_market_hours(now) else _CACHE_AFTER_MINUTES
        return (now - self._timestamp) > timedelta(minutes=ttl)

    def minutes_ago(self) -> int:
        if self._timestamp is None:
            return 999
        delta = datetime.now(ET) - self._timestamp
        return int(delta.total_seconds() / 60)

    def last_scan_time(self) -> str | None:
        if self._timestamp is None:
            return None
        return self._timestamp.strftime("%I:%M %p EST")
```

- [ ] **Step 3: Run tests, commit**

```bash
git add adapters/visualization/cache.py tests/test_cache.py
git commit -m "feat: add smart scan cache — 15min market hours, 60min after hours"
```

---

## Task 3: Hero + Onboarding + Compact Card + Progress Components

**Files:**
- Create: `adapters/visualization/components/hero.py`
- Create: `adapters/visualization/components/onboarding.py`
- Create: `adapters/visualization/components/compact_card.py`
- Create: `adapters/visualization/components/progress.py`
- Test: `tests/test_hero.py`
- Test: `tests/test_compact_card.py`

- [ ] **Step 1: Write failing tests for hero**

```python
"""Tests for hero panel component."""

from adapters.visualization.components.hero import (
    render_hero_html,
    render_market_panel,
    render_portfolio_panel,
    render_signal_panel,
)


class TestHeroPanel:
    def test_market_panel_open(self) -> None:
        html = render_market_panel(
            spy_price=754.19, spy_change=-0.52,
            market_open=True, time_est="2:15 PM EST",
            mood="Mixed signals today",
        )
        assert "754.19" in html
        assert "OPEN" in html
        assert "2:15 PM EST" in html

    def test_market_panel_closed(self) -> None:
        html = render_market_panel(
            spy_price=754.19, spy_change=-0.52,
            market_open=False, time_est="10:24 PM EST",
            mood="Market closed",
        )
        assert "CLOSED" in html

    def test_portfolio_panel(self) -> None:
        html = render_portfolio_panel(
            total_value=20650.0, total_pnl=420.0,
            pnl_pct=2.1, n_positions=4,
            best_performer="NVDA +3.2%",
        )
        assert "20,650" in html
        assert "+$420" in html or "420" in html

    def test_signal_panel(self) -> None:
        html = render_signal_panel(
            n_new_opps=3, top_ticker="AMD",
            top_conviction=7.2, n_watchlist_alerts=2,
            summary="Smart money moving on AMD",
        )
        assert "AMD" in html
        assert "7.2" in html

    def test_full_hero_renders(self) -> None:
        html = render_hero_html(
            market={"spy_price": 754.0, "spy_change": 0.5, "market_open": True, "time_est": "2:00 PM EST", "mood": "Bull day"},
            portfolio={"total_value": 10000, "total_pnl": 200, "pnl_pct": 2.0, "n_positions": 2, "best_performer": "NVDA"},
            signal={"n_new_opps": 5, "top_ticker": "AMD", "top_conviction": 8.0, "n_watchlist_alerts": 1, "summary": "test"},
        )
        assert "MARKET STATUS" in html or "Market" in html
```

- [ ] **Step 2: Write failing tests for compact card**

```python
"""Tests for compact opportunity card."""

from datetime import datetime

from adapters.visualization.components.compact_card import render_compact_card_html
from domain.conviction import ActionType, ConvictionScore, OpportunityCard


class TestCompactCard:
    def test_renders_ticker_and_conviction(self) -> None:
        card = OpportunityCard(
            ticker="NVDA", conviction=8.2, action=ActionType.BUY,
            alert_summary="Activist 13D + insider cluster",
            evidence=["Evidence 1"], suggestion="Buy signal",
            risks=["Market risk"], generated_at=datetime(2026, 6, 3),
            conviction_score=ConvictionScore(
                ticker="NVDA", score=8.2, sub_scores={},
                signals_firing=4, freshest_signal=datetime(2026, 6, 3),
                explanation="",
            ),
        )
        html = render_compact_card_html(card, now=datetime(2026, 6, 3))
        assert "NVDA" in html
        assert "8.2" in html
        assert "BUY" in html

    def test_high_conviction_green_border(self) -> None:
        card = OpportunityCard(
            ticker="X", conviction=8.0, action=ActionType.BUY,
            alert_summary="test", evidence=[], suggestion="",
            risks=[], generated_at=datetime(2026, 6, 3),
            conviction_score=ConvictionScore(
                ticker="X", score=8.0, sub_scores={},
                signals_firing=4, freshest_signal=datetime(2026, 6, 3),
                explanation="",
            ),
        )
        html = render_compact_card_html(card, now=datetime(2026, 6, 3))
        assert "opp-card-high" in html

    def test_low_conviction_red_border(self) -> None:
        card = OpportunityCard(
            ticker="X", conviction=2.5, action=ActionType.WATCH,
            alert_summary="test", evidence=[], suggestion="",
            risks=[], generated_at=datetime(2026, 6, 3),
            conviction_score=ConvictionScore(
                ticker="X", score=2.5, sub_scores={},
                signals_firing=1, freshest_signal=datetime(2026, 6, 3),
                explanation="",
            ),
        )
        html = render_compact_card_html(card, now=datetime(2026, 6, 3))
        assert "opp-card-low" in html
```

- [ ] **Step 3: Implement hero.py**

```python
"""3-panel hero section — Market Status, Your Portfolio, Today's Signal."""

from __future__ import annotations
from typing import Any


def render_market_panel(
    spy_price: float, spy_change: float,
    market_open: bool, time_est: str, mood: str,
) -> str:
    status = "OPEN" if market_open else "CLOSED"
    status_color = "#16A34A" if market_open else "#DC2626"
    change_color = "#16A34A" if spy_change >= 0 else "#DC2626"
    change_sign = "+" if spy_change >= 0 else ""
    return f"""
    <div class="hero-panel">
        <div class="hero-label">Market Status</div>
        <div class="hero-value">S&P 500 ${spy_price:,.2f}</div>
        <div style="font-family:'JetBrains Mono',monospace;font-size:14px;color:{change_color};font-weight:600;margin-top:2px;">{change_sign}{spy_change:.2f}%</div>
        <div class="hero-sub"><span style="color:{status_color};font-weight:600;">{status}</span> · {time_est}</div>
        <div class="hero-sub">{mood}</div>
    </div>"""


def render_portfolio_panel(
    total_value: float, total_pnl: float,
    pnl_pct: float, n_positions: int,
    best_performer: str,
) -> str:
    pnl_color = "#16A34A" if total_pnl >= 0 else "#DC2626"
    pnl_sign = "+" if total_pnl >= 0 else ""
    return f"""
    <div class="hero-panel">
        <div class="hero-label">Your Portfolio</div>
        <div class="hero-value">${total_value:,.0f}</div>
        <div style="font-family:'JetBrains Mono',monospace;font-size:14px;color:{pnl_color};font-weight:600;margin-top:2px;">{pnl_sign}${total_pnl:,.0f} ({pnl_sign}{pnl_pct:.1f}%)</div>
        <div class="hero-sub">{n_positions} position{'s' if n_positions != 1 else ''}</div>
        <div class="hero-sub">{best_performer}</div>
    </div>"""


def render_signal_panel(
    n_new_opps: int, top_ticker: str,
    top_conviction: float, n_watchlist_alerts: int,
    summary: str,
) -> str:
    return f"""
    <div class="hero-panel">
        <div class="hero-label">Today's Signal</div>
        <div class="hero-value">{n_new_opps} opportunit{'ies' if n_new_opps != 1 else 'y'}</div>
        <div class="hero-sub">Top: {top_ticker} — {top_conviction:.1f}/10</div>
        <div class="hero-sub">{n_watchlist_alerts} watchlist alert{'s' if n_watchlist_alerts != 1 else ''}</div>
        <div style="font-size:13px;color:#1A202C;margin-top:6px;font-style:italic;">"{summary}"</div>
    </div>"""


def render_hero_html(
    market: dict[str, Any], portfolio: dict[str, Any], signal: dict[str, Any],
) -> str:
    m = render_market_panel(**market)
    p = render_portfolio_panel(**portfolio)
    s = render_signal_panel(**signal)
    return f'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;margin-bottom:20px;">{m}{p}{s}</div>'
```

- [ ] **Step 4: Implement onboarding.py**

```python
"""First-run onboarding card."""

from __future__ import annotations


def render_onboarding_html() -> str:
    return """
    <div class="onboarding-card">
        <h2 style="font-family:'DM Sans',sans-serif;margin-bottom:4px;">Welcome to your Investment Intelligence System</h2>
        <p style="color:#64748B;font-size:14px;">Get started in 3 steps</p>
        <div class="onboarding-step">
            <div class="onboarding-num">1</div>
            <div>
                <strong>Scan for Opportunities</strong>
                <div style="color:#64748B;font-size:13px;">System scans 350+ tickers for smart money activity, sentiment shifts, and fundamental signals.</div>
            </div>
        </div>
        <div class="onboarding-step">
            <div class="onboarding-num">2</div>
            <div>
                <strong>Add to Watchlist</strong>
                <div style="color:#64748B;font-size:13px;">Pin tickers you want to monitor daily. Get alerted when signals change.</div>
            </div>
        </div>
        <div class="onboarding-step">
            <div class="onboarding-num">3</div>
            <div>
                <strong>Record a Trade</strong>
                <div style="color:#64748B;font-size:13px;">Log your first buy so the system can learn which signals work for your investment style.</div>
            </div>
        </div>
        <p style="color:#64748B;font-size:13px;margin-top:16px;">The system gets smarter with every trade you track.</p>
    </div>"""


def should_show_onboarding(
    has_scan_results: bool, has_trades: bool, has_watchlist: bool,
) -> bool:
    return not has_scan_results and not has_trades and not has_watchlist
```

- [ ] **Step 5: Implement compact_card.py**

```python
"""Compact opportunity card with expandable signal breakdown."""

from __future__ import annotations

from datetime import datetime

from domain.conviction import ActionType, FreshnessLevel, OpportunityCard

_ACTION_BADGE = {
    ActionType.BUY: "badge-buy",
    ActionType.SELL: "badge-sell",
    ActionType.WATCH: "badge-watch",
    ActionType.HOLD: "badge-hold",
}

_CARD_BORDER = {
    "high": "opp-card-high",
    "mid": "opp-card-mid",
    "low": "opp-card-low",
}


def _conviction_level(score: float) -> str:
    if score >= 7.0:
        return "high"
    if score >= 4.0:
        return "mid"
    return "low"


def _bar_color(level: str) -> str:
    return {"high": "#16A34A", "mid": "#D97706", "low": "#DC2626"}[level]


def _freshness_badge(level: FreshnessLevel) -> str:
    cls = {"fresh": "badge-fresh", "recent": "badge-recent", "stale": "badge-stale"}
    dot = {"fresh": "status-green", "recent": "status-amber", "stale": "status-red"}
    return f'<span class="{cls.get(level.value, "")}"><span class="status-dot {dot.get(level.value, "")}"></span>{level.value.capitalize()}</span>'


def render_compact_card_html(card: OpportunityCard, now: datetime) -> str:
    level = _conviction_level(card.conviction)
    border_cls = _CARD_BORDER[level]
    badge_cls = _ACTION_BADGE.get(card.action, "badge-hold")
    bar_pct = min(card.conviction / 10.0 * 100, 100)
    bar_color = _bar_color(level)
    freshness = card.conviction_score.freshness_level(now)
    freshness_html = _freshness_badge(freshness)

    risk_text = " · ".join(card.risks[:2]) if card.risks else ""

    return f"""
    <div class="opp-card {border_cls}">
        <div style="display:flex;justify-content:space-between;align-items:center;">
            <div style="display:flex;align-items:center;gap:12px;">
                <span style="font-family:'DM Sans',sans-serif;font-size:18px;font-weight:700;">{card.ticker}</span>
                <div class="conviction-bar"><div class="conviction-bar-fill" style="width:{bar_pct}%;background:{bar_color};"></div></div>
                <span style="font-family:'JetBrains Mono',monospace;font-size:14px;font-weight:600;color:{bar_color};">{card.conviction:.1f}/10</span>
                <span class="badge {badge_cls}">{card.action.value}</span>
            </div>
            <div>{freshness_html}</div>
        </div>
        <div style="margin-top:6px;font-size:13px;color:#1A202C;">{card.alert_summary}</div>
        <div style="margin-top:4px;font-size:12px;color:#94A3B8;">{risk_text}</div>
    </div>"""
```

- [ ] **Step 6: Implement progress.py**

```python
"""Learning progress bar component."""

from __future__ import annotations

_MILESTONES = [
    (10, "First insights"),
    (50, "Reliable patterns"),
    (200, "Mature intelligence"),
]


def render_learning_progress_html(n_outcomes: int) -> str:
    target = 50
    pct = min(n_outcomes / target * 100, 100)

    if n_outcomes == 0:
        msg = "Track your first trade to start the learning loop."
    elif n_outcomes < 10:
        msg = f"{n_outcomes} trades tracked. {10 - n_outcomes} more for first signal insights."
    elif n_outcomes < 50:
        msg = f"{n_outcomes} trades tracked. Signal patterns emerging — {50 - n_outcomes} more for reliable intelligence."
    else:
        msg = f"{n_outcomes} trades tracked. System has reliable intelligence and is continuously improving."

    return f"""
    <div class="ws-card" style="text-align:center;">
        <div style="font-family:'DM Sans',sans-serif;font-size:15px;font-weight:600;color:#1A202C;margin-bottom:4px;">System Intelligence</div>
        <div style="font-size:13px;color:#64748B;margin-bottom:12px;">{msg}</div>
        <div class="learning-progress"><div class="learning-progress-fill" style="width:{pct}%;"></div></div>
        <div style="font-size:11px;color:#94A3B8;">{n_outcomes}/{target} trades toward reliable intelligence</div>
    </div>"""
```

- [ ] **Step 7: Run all tests**

Run: `python -m pytest tests/test_hero.py tests/test_compact_card.py tests/test_cache.py -v --tb=short`

- [ ] **Step 8: Commit**

```bash
git add adapters/visualization/components/hero.py adapters/visualization/components/onboarding.py adapters/visualization/components/compact_card.py adapters/visualization/components/progress.py tests/test_hero.py tests/test_compact_card.py
git commit -m "feat: add hero panels, onboarding card, compact opportunity cards, progress bar"
```

---

## Task 4: Dashboard Router — 5 Tabs, No Emoji

**Files:**
- Modify: `adapters/visualization/dashboard.py`

- [ ] **Step 1: Rewrite dashboard.py**

Replace the tab router with 5 tabs, plain text labels, minimal header:

```python
"""Dashboard entry point — 5-tab router.

Run: streamlit run adapters/visualization/dashboard.py
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Stock Intelligence",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="collapsed",
)

from adapters.visualization.components.styles import inject_global_css

inject_global_css()

# Minimal header
st.markdown(
    '<h1 style="margin-bottom:2px;">Multi-Modal Stock Recommender</h1>',
    unsafe_allow_html=True,
)

# 5-tab router — no emoji
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Today's Opportunities",
    "Watchlist",
    "My Portfolio",
    "How It Works",
    "Market Context",
])

with tab1:
    from adapters.visualization.tabs.command_center import render as render_opps
    render_opps()

with tab2:
    from adapters.visualization.tabs.watchlist import render as render_watch
    render_watch()

with tab3:
    from adapters.visualization.tabs.positions import render as render_portfolio
    render_portfolio()

with tab4:
    from adapters.visualization.tabs.model_confidence import render as render_hiw
    render_hiw()

with tab5:
    from adapters.visualization.tabs.market_pulse import render as render_market
    render_market()

# Footer
st.markdown(
    '<div class="ws-footer">Multi-Modal Stock Recommender · Built by Tirth Joshi</div>',
    unsafe_allow_html=True,
)
```

- [ ] **Step 2: Create empty watchlist.py tab**

```python
"""Tab 2: Watchlist — Pinned tickers + historical recommendations."""

from __future__ import annotations

import streamlit as st

from adapters.visualization.data_loader import load_watchlist

DB_PATH = "data/recommendations.db"


def render(db_path: str = DB_PATH) -> None:
    """Render the Watchlist tab."""
    st.markdown("### Watchlist")
    st.markdown(
        '<div style="color:#64748B;font-size:14px;margin-bottom:16px;">'
        "Tickers you're watching. Pin from Today's Opportunities or add manually below.</div>",
        unsafe_allow_html=True,
    )

    watchlist = load_watchlist(db_path)

    if not watchlist:
        st.markdown(
            '<div class="ws-card" style="text-align:center;padding:2rem;">'
            '<div style="font-size:15px;font-weight:500;color:#1A202C;">Your watchlist is empty</div>'
            '<div style="font-size:13px;color:#64748B;margin-top:4px;">'
            "Pin tickers from Today's Opportunities to track them here.</div></div>",
            unsafe_allow_html=True,
        )
    else:
        import pandas as pd
        df = pd.DataFrame(watchlist)
        st.dataframe(df, use_container_width=True, hide_index=True)

    # Add form
    st.divider()
    with st.form("add_watchlist_form", clear_on_submit=True):
        cols = st.columns([3, 5, 2])
        ticker = cols[0].text_input("Symbol", placeholder="TSLA")
        notes = cols[1].text_input("Notes", placeholder="Earnings play")
        submitted = cols[2].form_submit_button("Add")
        if submitted and ticker:
            from adapters.visualization.action_runner import run_add_watchlist
            run_add_watchlist(ticker.upper(), notes, db_path=db_path)
            st.rerun()
```

- [ ] **Step 3: Delete old tabs**

Delete `adapters/visualization/tabs/signal_breakdown.py` and `adapters/visualization/tabs/opportunities.py`.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_dashboard_smoke.py -v --tb=short`
Fix any import errors from deleted tabs.

- [ ] **Step 5: Commit**

```bash
git add adapters/visualization/dashboard.py adapters/visualization/tabs/watchlist.py
git rm adapters/visualization/tabs/signal_breakdown.py adapters/visualization/tabs/opportunities.py
git commit -m "feat: 5-tab dashboard router — no emoji, kill tournament + signal breakdown tabs"
```

---

## Task 5: Today's Opportunities Tab — Auto-Scan + Hero + Compact Cards

**Files:**
- Modify: `adapters/visualization/tabs/command_center.py` — full rewrite

- [ ] **Step 1: Full rewrite of command_center.py**

New implementation:
1. Check scan cache — if stale, auto-scan with loading skeleton
2. Show 3-panel hero (Market, Portfolio, Signal)
3. Show compact opportunity cards below
4. "Scan Now" + "Last scanned X min ago" at bottom
5. If no data at all → show onboarding

Key logic:
- Use `st.session_state` for ScanCache instance
- Auto-scan on first render if cache stale
- EST timestamps via `zoneinfo.ZoneInfo("America/New_York")`
- Hero data assembled from scan results + holdings + spy data

- [ ] **Step 2: Run tests**
- [ ] **Step 3: Commit**

```bash
git add adapters/visualization/tabs/command_center.py
git commit -m "feat: Today's Opportunities — auto-scan, 3-panel hero, compact conviction cards"
```

---

## Task 6: My Portfolio Tab — Redesign with CRUD + Signal Report

**Files:**
- Modify: `adapters/visualization/tabs/positions.py` — polish for new theme

- [ ] **Step 1: Update positions.py**

Changes:
- Use ws-card CSS class for all sections
- Portfolio summary only shows metrics with data (hide empty ones)
- Trade table rows colored green/red by action
- Open positions section with [Record Sell] button per row
- Signal report card section (existing) styled with new theme
- All timestamps in EST

- [ ] **Step 2: Commit**

```bash
git add adapters/visualization/tabs/positions.py
git commit -m "feat: My Portfolio tab polish — ws-card theme, colored rows, EST timestamps"
```

---

## Task 7: How It Works Tab — Collapsible + Progress

**Files:**
- Modify: `adapters/visualization/tabs/model_confidence.py` — restructure

- [ ] **Step 1: Restructure model_confidence.py**

New layout:
1. Learning progress bar at top (always visible)
2. Three st.expander sections:
   - "Signal Performance" — signal report card content
   - "System Learning" — weight history, rules, Run Learning Cycle button
   - "Model Baseline" — walk-forward, ablation, SHAP, limitations
3. All existing chart/backtest content moves into "Model Baseline" expander

- [ ] **Step 2: Commit**

```bash
git add adapters/visualization/tabs/model_confidence.py
git commit -m "feat: How It Works — collapsible sections, learning progress bar"
```

---

## Task 8: Market Context Tab — Polish

**Files:**
- Modify: `adapters/visualization/tabs/market_pulse.py`

- [ ] **Step 1: Polish market_pulse.py**

Changes:
- Data pipeline: replace bullet list with grid of ws-card items (8 sources)
- Add SEC EDGAR to data sources
- Supply chain cards: consistent ws-card styling
- Consistent border radius, hover effects

- [ ] **Step 2: Commit**

```bash
git add adapters/visualization/tabs/market_pulse.py
git commit -m "feat: Market Context polish — data pipeline grid, consistent ws-card styling"
```

---

## Task 9: Update Tests + Fix Smoke Tests

**Files:**
- Modify: `tests/test_dashboard_smoke.py` — update for new tab structure
- Modify: `tests/test_dashboard_integration.py` — update imports

- [ ] **Step 1: Fix smoke tests for 5-tab layout**

Update imports: remove signal_breakdown and opportunities tab imports, add watchlist.

- [ ] **Step 2: Run full suite**

Run: `python -m pytest tests/ -q --tb=short`

- [ ] **Step 3: Commit**

```bash
git add tests/
git commit -m "test: update smoke + integration tests for 5-tab dashboard layout"
```

---

## Task 10: Full Regression + ADR-035

- [ ] **Step 1: Run full quality check**

Run: `python -m pytest tests/ -q --tb=short`

- [ ] **Step 2: Create ADR-035**

```markdown
# ADR-035: Dashboard Redesign — WealthSimple-Inspired 5-Tab Layout

**Date:** 2026-06-03
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context

The dashboard grew from 6 tabs across Phases 5-9 without unified design. Two recommendation systems (conviction + tournament) confused users. Layout was data-dense but not informative. Looked like a Streamlit prototype, not an investment tool.

## Decision

Complete redesign with WealthSimple-inspired aesthetic:

1. **5 tabs in 3 modes:** Act (Opportunities, Watchlist), Track (My Portfolio), Understand (How It Works, Market Context)
2. **Killed tournament tab** — conviction engine is the sole recommendation source
3. **Signal Breakdown merged** into opportunity card expansion (not separate tab)
4. **Auto-scan with smart cache** — 15min market hours, 60min after hours
5. **3-panel hero** — Market Status, Portfolio, Today's Signal at a glance
6. **Compact opportunity cards** — scannable, expandable for detail
7. **Guided onboarding** — first-run 3-step card
8. **DM Sans + Inter + JetBrains Mono** — distinctive typography
9. **Collapsible sections** in How It Works with learning progress gamification
10. **Light theme, friendly voice** — conversational verdicts, plain English

## Consequences

- Simpler mental model (5 tabs vs 6, one recommendation system vs two)
- Auto-scan removes friction (no button click every visit)
- Onboarding helps new users understand the system
- Signal Breakdown content preserved but accessed in context (per-card) not standalone
```

- [ ] **Step 3: Update CLAUDE.md**
- [ ] **Step 4: Commit**

```bash
git add docs/adr/ADR-035-dashboard-redesign.md CLAUDE.md
git commit -m "docs: add ADR-035 dashboard redesign + update phase status"
```

---

## Dependency Graph

```
Task 1 (CSS theme) ──────────────────────────────────────┐
Task 2 (scan cache) ─────────────────────────────────────┤
Task 3 (hero + onboarding + compact card + progress) ────┤
                                                          ▼
Task 4 (dashboard router + watchlist tab + delete old) ──▶ Task 5 (Today's Opportunities)
                                                          ├──▶ Task 6 (My Portfolio)
                                                          ├──▶ Task 7 (How It Works)
                                                          └──▶ Task 8 (Market Context)
                                                                      │
Task 9 (fix tests) ◀─────────────────────────────────────────────────┘
Task 10 (regression + ADR) ◀── Task 9
```

**Parallelizable:** Tasks 1, 2, 3 are independent — run in parallel. Task 4 after all three. Tasks 5-8 after Task 4 (but 6, 7, 8 can parallel). Task 9 after 5-8. Task 10 last.
