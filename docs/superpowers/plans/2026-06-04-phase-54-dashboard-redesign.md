# Phase 5.4 — SimplyWallSt-Grade Intelligence Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the dashboard from a data engineering demo into a SimplyWallSt-grade financial intelligence platform with charts, verdicts, and live data across all 6 tabs.

**Architecture:** Visualization layer only (adapters/visualization/) plus conviction engine wiring (application/conviction_use_case.py). Domain stays pure. New components are reusable HTML/Plotly builders. Batch price cache wraps yfinance with Streamlit TTL caching. Stock Analysis tab is a new tab with data fetching in a separate analyzer module.

**Tech Stack:** Streamlit 1.38+, Plotly 5.x, yfinance 1.4.x, Python 3.12+

**Spec:** `docs/superpowers/specs/2026-06-04-phase-54-dashboard-redesign.md`
**ADR:** `docs/adr/036-phase-54-dashboard-redesign.md`
**Branch:** `feat/phase-5.4-dashboard-redesign`

---

## File Map

### New Files
| File | Responsibility |
|------|---------------|
| `adapters/visualization/price_cache.py` | Batch yfinance price fetching with `st.cache_data` TTL |
| `adapters/visualization/components/cards.py` | Reusable HTML components: criteria_card, verdict_bullet, price_range_bar, metric_kpi, mini_sparkline, loading_stepper |
| `adapters/visualization/tabs/stock_analysis.py` | Tab 4: Stock Analysis rendering |
| `adapters/visualization/stock_analyzer.py` | Data fetching + criteria scoring for Stock Analysis |
| `tests/test_price_cache.py` | Tests for price_cache |
| `tests/test_cards.py` | Tests for card components |
| `tests/test_stock_analyzer.py` | Tests for stock analyzer logic |
| `tests/test_new_charts.py` | Tests for new Plotly chart builders |

### Modified Files
| File | Changes |
|------|---------|
| `adapters/visualization/components/charts.py` | Add: signal_radar, gauge_chart, comparison_bars, ownership_pie, insider_bars, candlestick_chart, financials_line, cluster_bubble |
| `adapters/visualization/components/styles.py` | Add missing CSS classes + new component styles |
| `adapters/visualization/components/progress.py` | Replace with loading_stepper supporting step messages |
| `adapters/visualization/dashboard.py` | 6 tabs (add Stock Analysis) |
| `adapters/visualization/action_runner.py` | Fix conviction scan (all tickers, pass store), fix monitor_holdings |
| `adapters/visualization/data_loader.py` | Add load_recommendations_latest, remove dead loaders |
| `adapters/visualization/tabs/command_center.py` | Two-mode layout, market overview, scrolling ticker bar |
| `adapters/visualization/tabs/watchlist.py` | Card layout, live prices, remove button |
| `adapters/visualization/tabs/positions.py` | Portfolio summary, P&L chart, position health cards |
| `adapters/visualization/tabs/model_confidence.py` | Fix bugs, wire dead charts, criteria cards |
| `adapters/visualization/tabs/market_pulse.py` | Live prices on supply chain, cluster bubble, real timestamps |
| `application/conviction_use_case.py` | Wire real sub-scores, accept store + market_data |
| `domain/conviction_service.py` | Add rank_opportunities fallback when all below min_score |

---

## Phase 1: Foundation (Tasks 1-12)

Critical path — everything else depends on this.

---

### Task 1: Create Price Cache Module

**Files:**
- Create: `adapters/visualization/price_cache.py`
- Test: `tests/test_price_cache.py`

- [ ] **Step 1: Write tests for batch price fetching**

```python
# tests/test_price_cache.py
"""Tests for batch price cache — uses mocked yfinance."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


def test_batch_fetch_prices_returns_dict_with_price_and_change():
    """batch_fetch_prices returns {ticker: {price, change_pct}} for each ticker."""
    from adapters.visualization.price_cache import _batch_fetch_prices_impl

    # Build a 2-day DataFrame mimicking yfinance.download for 2 tickers
    dates = pd.date_range("2026-06-03", periods=2)
    arrays = [["AAPL", "AAPL", "NVDA", "NVDA"], ["Close", "Volume", "Close", "Volume"]]
    tuples = list(zip(*arrays))
    index = pd.MultiIndex.from_tuples(tuples, names=["Ticker", "Price"])
    data = pd.DataFrame(
        [[190.0, 1000, 950.0, 2000], [195.0, 1100, 960.0, 2200]],
        index=dates,
        columns=index,
    )

    with patch("adapters.visualization.price_cache.yf") as mock_yf:
        mock_yf.download.return_value = data
        result = _batch_fetch_prices_impl(("AAPL", "NVDA"))

    assert "AAPL" in result
    assert "NVDA" in result
    assert abs(result["AAPL"]["price"] - 195.0) < 0.01
    assert abs(result["AAPL"]["change_pct"] - 2.6316) < 0.1  # (195-190)/190*100
    assert abs(result["NVDA"]["price"] - 960.0) < 0.01


def test_batch_fetch_prices_empty_tickers_returns_empty():
    from adapters.visualization.price_cache import _batch_fetch_prices_impl

    result = _batch_fetch_prices_impl(())
    assert result == {}


def test_batch_fetch_prices_single_ticker():
    """Single ticker uses different yfinance column format."""
    from adapters.visualization.price_cache import _batch_fetch_prices_impl

    dates = pd.date_range("2026-06-03", periods=2)
    data = pd.DataFrame(
        {"Close": [100.0, 105.0], "Volume": [500, 600]},
        index=dates,
    )
    with patch("adapters.visualization.price_cache.yf") as mock_yf:
        mock_yf.download.return_value = data
        result = _batch_fetch_prices_impl(("AAPL",))

    assert "AAPL" in result
    assert abs(result["AAPL"]["price"] - 105.0) < 0.01
    assert abs(result["AAPL"]["change_pct"] - 5.0) < 0.1


def test_fetch_ticker_info_impl_returns_dict():
    from adapters.visualization.price_cache import _fetch_ticker_info_impl

    mock_ticker = MagicMock()
    mock_ticker.info = {"trailingPE": 33.0, "pegRatio": 0.66}
    with patch("adapters.visualization.price_cache.yf.Ticker", return_value=mock_ticker):
        result = _fetch_ticker_info_impl("NVDA")

    assert result["trailingPE"] == 33.0


def test_fetch_insider_transactions_impl_returns_list():
    from adapters.visualization.price_cache import _fetch_insider_transactions_impl

    mock_ticker = MagicMock()
    mock_ticker.insider_transactions = pd.DataFrame(
        {"Insider": ["John"], "Shares": [100], "Value": [10000], "Transaction": ["Sale"]}
    )
    with patch("adapters.visualization.price_cache.yf.Ticker", return_value=mock_ticker):
        result = _fetch_insider_transactions_impl("NVDA")

    assert len(result) == 1
    assert result[0]["Insider"] == "John"


def test_fetch_insider_transactions_impl_empty():
    from adapters.visualization.price_cache import _fetch_insider_transactions_impl

    mock_ticker = MagicMock()
    mock_ticker.insider_transactions = None
    with patch("adapters.visualization.price_cache.yf.Ticker", return_value=mock_ticker):
        result = _fetch_insider_transactions_impl("NVDA")

    assert result == []
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `pytest tests/test_price_cache.py -v`
Expected: ModuleNotFoundError — `adapters.visualization.price_cache` does not exist yet.

- [ ] **Step 3: Implement price_cache.py**

```python
# adapters/visualization/price_cache.py
"""Batch price cache — yfinance.download() for multiple tickers, cached with TTL.

Uses Streamlit's st.cache_data for TTL-based caching. The _impl functions contain
the actual logic and are called by the cached wrappers. Tests call _impl directly
to bypass Streamlit caching.
"""
from __future__ import annotations

from datetime import time

import pandas as pd
import yfinance as yf
from loguru import logger


def _is_market_hours() -> bool:
    """Check if US markets are currently open."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    now = datetime.now(ZoneInfo("America/New_York"))
    return now.weekday() < 5 and time(9, 30) <= now.time() < time(16, 0)


def _batch_fetch_prices_impl(tickers: tuple[str, ...]) -> dict[str, dict]:
    """Fetch current prices for multiple tickers in one yfinance call.

    Returns dict[ticker, {"price": float, "change_pct": float}].
    Handles both single-ticker and multi-ticker yfinance column formats.
    """
    if not tickers:
        return {}

    try:
        data = yf.download(
            list(tickers), period="2d", group_by="ticker", progress=False
        )
    except Exception as exc:
        logger.warning(f"yfinance batch download failed: {exc}")
        return {}

    if data is None or data.empty:
        return {}

    results: dict[str, dict] = {}
    for ticker in tickers:
        try:
            if len(tickers) == 1:
                df = data
            else:
                df = data[ticker]

            close = df["Close"].dropna()
            if len(close) >= 2:
                current = float(close.iloc[-1])
                prev = float(close.iloc[-2])
                change_pct = (current - prev) / prev * 100 if prev != 0 else 0.0
                results[ticker] = {"price": current, "change_pct": change_pct}
            elif len(close) == 1:
                results[ticker] = {"price": float(close.iloc[-1]), "change_pct": 0.0}
        except Exception as exc:
            logger.debug(f"Price extraction failed for {ticker}: {exc}")

    return results


def _fetch_ticker_info_impl(ticker: str) -> dict:
    """Fetch full ticker info (fundamentals, analyst data)."""
    try:
        return yf.Ticker(ticker).info
    except Exception as exc:
        logger.warning(f"Failed to fetch info for {ticker}: {exc}")
        return {}


def _fetch_quarterly_financials_impl(
    ticker: str,
) -> tuple[pd.DataFrame | None, pd.DataFrame | None, pd.DataFrame | None]:
    """Fetch quarterly financials, balance sheet, and cashflow."""
    try:
        t = yf.Ticker(ticker)
        return t.quarterly_financials, t.quarterly_balance_sheet, t.quarterly_cashflow
    except Exception as exc:
        logger.warning(f"Failed to fetch financials for {ticker}: {exc}")
        return None, None, None


def _fetch_insider_transactions_impl(ticker: str) -> list[dict]:
    """Fetch insider transactions as list of dicts."""
    try:
        t = yf.Ticker(ticker)
        df = t.insider_transactions
        if df is not None and not df.empty:
            return df.to_dict("records")
    except Exception as exc:
        logger.warning(f"Failed to fetch insider transactions for {ticker}: {exc}")
    return []


def _fetch_index_prices_impl() -> dict[str, dict]:
    """Fetch major index prices for scrolling ticker bar."""
    return _batch_fetch_prices_impl(("SPY", "QQQ", "DIA", "IWM"))


# ── Streamlit-cached wrappers ──────────────────────────────────────────────
# These import st at call time so the module can be imported in non-Streamlit
# contexts (tests, CLI).


def batch_fetch_prices(tickers: tuple[str, ...]) -> dict[str, dict]:
    """Cached batch price fetch. TTL: 5min market hours, 60min after."""
    try:
        import streamlit as st

        ttl = 300 if _is_market_hours() else 3600
        return st.cache_data(ttl=ttl)(_batch_fetch_prices_impl)(tickers)
    except Exception:
        return _batch_fetch_prices_impl(tickers)


def fetch_ticker_info(ticker: str) -> dict:
    """Cached ticker info fetch. TTL: 5min."""
    try:
        import streamlit as st

        return st.cache_data(ttl=300)(_fetch_ticker_info_impl)(ticker)
    except Exception:
        return _fetch_ticker_info_impl(ticker)


def fetch_quarterly_financials(
    ticker: str,
) -> tuple[pd.DataFrame | None, pd.DataFrame | None, pd.DataFrame | None]:
    """Cached quarterly financials. TTL: 60min."""
    try:
        import streamlit as st

        return st.cache_data(ttl=3600)(_fetch_quarterly_financials_impl)(ticker)
    except Exception:
        return _fetch_quarterly_financials_impl(ticker)


def fetch_insider_transactions(ticker: str) -> list[dict]:
    """Cached insider transactions. TTL: 60min."""
    try:
        import streamlit as st

        return st.cache_data(ttl=3600)(_fetch_insider_transactions_impl)(ticker)
    except Exception:
        return _fetch_insider_transactions_impl(ticker)


def fetch_index_prices() -> dict[str, dict]:
    """Cached index prices for ticker bar. TTL: 5min."""
    try:
        import streamlit as st

        ttl = 300 if _is_market_hours() else 3600
        return st.cache_data(ttl=ttl)(_fetch_index_prices_impl)()
    except Exception:
        return _fetch_index_prices_impl()
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `pytest tests/test_price_cache.py -v`
Expected: 6 passed

- [ ] **Step 5: Run full test suite — no regressions**

Run: `pytest tests/ -x -q`
Expected: 838+ passed, 0 failed

- [ ] **Step 6: Commit**

```bash
git add adapters/visualization/price_cache.py tests/test_price_cache.py
git commit -m "feat: add batch price cache with yfinance TTL caching"
```

---

### Task 2: Create Card Components Module

**Files:**
- Create: `adapters/visualization/components/cards.py`
- Test: `tests/test_cards.py`

- [ ] **Step 1: Write tests for card components**

```python
# tests/test_cards.py
"""Tests for reusable card HTML components."""
from __future__ import annotations

import pytest


def test_criteria_card_renders_correct_dots():
    from adapters.visualization.components.cards import criteria_card

    html = criteria_card("Valuation", score=4, max_score=6, summary="Good value.")
    assert "Valuation" in html
    assert "4/6" in html
    assert html.count("#16A34A") == 4  # 4 green dots
    assert html.count("#D1D5DB") == 2  # 2 gray dots
    assert "Good value." in html


def test_criteria_card_zero_score():
    from adapters.visualization.components.cards import criteria_card

    html = criteria_card("Test", score=0, max_score=5, summary="Bad.")
    assert "0/5" in html
    assert html.count("#16A34A") == 0
    assert html.count("#D1D5DB") == 5


def test_verdict_bullet_pass():
    from adapters.visualization.components.cards import verdict_bullet

    html = verdict_bullet("pass", "Revenue growing fast")
    assert "#16A34A" in html  # green
    assert "Revenue growing fast" in html


def test_verdict_bullet_fail():
    from adapters.visualization.components.cards import verdict_bullet

    html = verdict_bullet("fail", "High debt")
    assert "#DC2626" in html  # red
    assert "High debt" in html


def test_verdict_bullet_warn():
    from adapters.visualization.components.cards import verdict_bullet

    html = verdict_bullet("warn", "Moderate risk")
    assert "#F59E0B" in html  # amber
    assert "Moderate risk" in html


def test_metric_kpi_renders():
    from adapters.visualization.components.cards import metric_kpi

    html = metric_kpi("Total Value", "$21,340", context="+6.2% total return")
    assert "$21,340" in html
    assert "Total Value" in html
    assert "+6.2% total return" in html


def test_price_range_bar_positions_marker():
    from adapters.visualization.components.cards import price_range_bar

    html = price_range_bar(current=214.0, low=180.0, high=500.0, target=298.0)
    assert "214" in html
    assert "180" in html
    assert "500" in html
    assert "298" in html


def test_mini_sparkline_returns_svg():
    from adapters.visualization.components.cards import mini_sparkline

    svg = mini_sparkline([100, 102, 98, 105, 110])
    assert "<svg" in svg
    assert "polyline" in svg or "path" in svg


def test_mini_sparkline_empty_returns_dash():
    from adapters.visualization.components.cards import mini_sparkline

    result = mini_sparkline([])
    assert "—" in result or result.strip() == ""


def test_loading_stepper_renders_steps():
    from adapters.visualization.components.cards import loading_stepper_html

    html = loading_stepper_html(
        steps=["Loading...", "Processing...", "Done."],
        current=1,
    )
    assert "Loading..." in html
    assert "Processing..." in html
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `pytest tests/test_cards.py -v`
Expected: ModuleNotFoundError — `adapters.visualization.components.cards` does not exist.

- [ ] **Step 3: Implement cards.py**

```python
# adapters/visualization/components/cards.py
"""Reusable HTML card components — SWST-style criteria cards, verdict bullets, KPIs.

All functions return HTML strings. No Streamlit dependency — pure rendering.
"""
from __future__ import annotations

from typing import Literal


def criteria_card(title: str, score: int, max_score: int, summary: str) -> str:
    """Render a SWST-style criteria card with green/gray dots.

    Example: "Valuation Score 4/6 ●●●●○○"
    """
    green_dot = (
        '<span style="display:inline-block;width:12px;height:12px;'
        'border-radius:50%;background:#16A34A;margin:0 2px;"></span>'
    )
    gray_dot = (
        '<span style="display:inline-block;width:12px;height:12px;'
        'border-radius:50%;background:#D1D5DB;margin:0 2px;"></span>'
    )
    dots = green_dot * score + gray_dot * (max_score - score)

    return (
        f'<div class="ws-card" style="padding:16px 20px;margin:12px 0;">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;'
        f'margin-bottom:8px;">'
        f'<span style="font-family:\'DM Sans\',sans-serif;font-weight:600;'
        f'font-size:14px;color:#0F172A;">'
        f'{title} Score {score}/{max_score}</span>'
        f'<span>{dots}</span>'
        f'</div>'
        f'<div style="font-size:14px;color:#475569;line-height:1.5;">{summary}</div>'
        f'</div>'
    )


def verdict_bullet(status: Literal["pass", "warn", "fail"], text: str) -> str:
    """Render a verdict bullet: ✅ pass / ⚠️ warn / ❌ fail with colored icon."""
    color_map = {"pass": "#16A34A", "warn": "#F59E0B", "fail": "#DC2626"}
    icon_map = {"pass": "&#10003;", "warn": "&#9888;", "fail": "&#10007;"}
    color = color_map.get(status, "#64748B")
    icon = icon_map.get(status, "?")

    return (
        f'<div style="display:flex;align-items:flex-start;gap:8px;'
        f'margin:6px 0;font-size:14px;line-height:1.5;">'
        f'<span style="color:{color};font-weight:700;font-size:16px;'
        f'flex-shrink:0;margin-top:1px;">{icon}</span>'
        f'<span style="color:#374151;">{text}</span>'
        f'</div>'
    )


def metric_kpi(
    label: str,
    value: str,
    context: str = "",
    color: str = "#0F172A",
) -> str:
    """Render a big-number KPI with label and optional context."""
    context_html = (
        f'<div style="font-size:12px;color:#64748B;margin-top:2px;">{context}</div>'
        if context
        else ""
    )
    return (
        f'<div style="text-align:center;">'
        f'<div style="font-size:11px;text-transform:uppercase;letter-spacing:0.5px;'
        f'color:#64748B;font-weight:500;">{label}</div>'
        f'<div style="font-family:\'JetBrains Mono\',monospace;font-size:24px;'
        f'font-weight:600;color:{color};margin-top:2px;">{value}</div>'
        f'{context_html}'
        f'</div>'
    )


def price_range_bar(
    current: float, low: float, high: float, target: float | None = None
) -> str:
    """Render a horizontal price range bar with current position marker.

    Shows: low ──── current ──── high, with optional target marker.
    """
    range_total = high - low
    if range_total <= 0:
        return f'<div style="color:#64748B;">Price: ${current:.2f}</div>'

    current_pct = max(0, min(100, (current - low) / range_total * 100))
    target_html = ""
    if target is not None:
        target_pct = max(0, min(100, (target - low) / range_total * 100))
        target_html = (
            f'<div style="position:absolute;left:{target_pct}%;top:-18px;'
            f'transform:translateX(-50%);font-size:11px;color:#7C3AED;font-weight:600;">'
            f'${target:.0f}</div>'
            f'<div style="position:absolute;left:{target_pct}%;top:0;bottom:0;'
            f'width:2px;background:#7C3AED;"></div>'
        )

    return (
        f'<div style="margin:24px 0 12px;">'
        f'<div style="position:relative;height:8px;background:#E2E8F0;'
        f'border-radius:4px;margin:0 40px;">'
        f'<div style="position:absolute;left:0;top:0;height:100%;'
        f'width:{current_pct}%;background:linear-gradient(90deg,#16A34A,#2563EB);'
        f'border-radius:4px;"></div>'
        f'<div style="position:absolute;left:{current_pct}%;top:-6px;'
        f'width:20px;height:20px;border-radius:50%;background:#2563EB;'
        f'border:3px solid white;box-shadow:0 2px 4px rgba(0,0,0,0.2);'
        f'transform:translateX(-50%);"></div>'
        f'<div style="position:absolute;left:{current_pct}%;top:-24px;'
        f'transform:translateX(-50%);font-size:12px;font-weight:600;color:#2563EB;">'
        f'${current:.0f}</div>'
        f'{target_html}'
        f'</div>'
        f'<div style="display:flex;justify-content:space-between;margin-top:6px;'
        f'font-size:11px;color:#94A3B8;padding:0 30px;">'
        f'<span>${low:.0f}</span><span>${high:.0f}</span>'
        f'</div>'
        f'</div>'
    )


def mini_sparkline(
    prices: list[float], width: int = 120, height: int = 30, color: str = "#2563EB"
) -> str:
    """Render an inline SVG sparkline from a list of prices.

    Returns an SVG element — no Plotly overhead.
    """
    if not prices or len(prices) < 2:
        return '<span style="color:#94A3B8;">—</span>'

    min_p = min(prices)
    max_p = max(prices)
    y_range = max_p - min_p if max_p != min_p else 1.0
    padding = 2

    points: list[str] = []
    for i, p in enumerate(prices):
        x = padding + (width - 2 * padding) * i / (len(prices) - 1)
        y = padding + (height - 2 * padding) * (1 - (p - min_p) / y_range)
        points.append(f"{x:.1f},{y:.1f}")

    polyline = " ".join(points)
    trend_color = "#16A34A" if prices[-1] >= prices[0] else "#DC2626"

    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'style="display:inline-block;vertical-align:middle;">'
        f'<polyline points="{polyline}" fill="none" stroke="{trend_color}" '
        f'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>'
        f'</svg>'
    )


def loading_stepper_html(steps: list[str], current: int) -> str:
    """Render loading progress with step messages.

    Args:
        steps: List of step message strings.
        current: 0-based index of current step.
    """
    step_items = ""
    for i, step in enumerate(steps):
        if i < current:
            color = "#16A34A"
            icon = "&#10003;"
        elif i == current:
            color = "#2563EB"
            icon = "&#9679;"
        else:
            color = "#D1D5DB"
            icon = "&#9675;"
        step_items += (
            f'<div style="display:flex;align-items:center;gap:8px;margin:4px 0;'
            f'font-size:13px;color:{color};">'
            f'<span style="font-size:14px;">{icon}</span>'
            f'<span>{step}</span>'
            f'</div>'
        )

    pct = int((current + 1) / len(steps) * 100) if steps else 0
    return (
        f'<div style="margin:16px 0;">'
        f'<div style="height:6px;background:#E2E8F0;border-radius:3px;overflow:hidden;'
        f'margin-bottom:12px;">'
        f'<div style="width:{pct}%;height:100%;background:linear-gradient(90deg,#2563EB,#7C3AED);'
        f'border-radius:3px;transition:width 0.3s;"></div>'
        f'</div>'
        f'{step_items}'
        f'</div>'
    )
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `pytest tests/test_cards.py -v`
Expected: 10 passed

- [ ] **Step 5: Run full suite — no regressions**

Run: `pytest tests/ -x -q`
Expected: 838+ passed

- [ ] **Step 6: Commit**

```bash
git add adapters/visualization/components/cards.py tests/test_cards.py
git commit -m "feat: add reusable SWST-style card components (criteria, verdicts, KPIs, sparklines)"
```

---

### Task 3: Add New Chart Builders to charts.py

**Files:**
- Modify: `adapters/visualization/components/charts.py`
- Test: `tests/test_new_charts.py`

- [ ] **Step 1: Write tests for new chart builders**

```python
# tests/test_new_charts.py
"""Tests for new Plotly chart builders added in Phase 5.4."""
from __future__ import annotations

import plotly.graph_objects as go
import pytest


def test_signal_radar_returns_figure_with_6_axes():
    from adapters.visualization.components.charts import signal_radar

    scores = {
        "Technical": 7.5,
        "Sentiment": 6.0,
        "Fundamental": 8.0,
        "Cross-Asset": 5.0,
        "Event-Causal": 5.0,
        "Smart Money": 3.0,
    }
    fig = signal_radar(scores)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1
    assert fig.data[0].type == "scatterpolar"


def test_signal_radar_clamps_values():
    from adapters.visualization.components.charts import signal_radar

    scores = {"A": 15.0, "B": -5.0}  # out of range
    fig = signal_radar(scores, max_val=10.0)
    r_values = list(fig.data[0].r)
    assert all(0 <= v <= 10 for v in r_values if isinstance(v, (int, float)))


def test_gauge_chart_returns_figure():
    from adapters.visualization.components.charts import gauge_chart

    fig = gauge_chart(value=81.7, min_v=0, max_v=100, label="ROE %")
    assert isinstance(fig, go.Figure)


def test_comparison_bars_highlights_ticker():
    from adapters.visualization.components.charts import comparison_bars

    items = [
        {"name": "NVDA", "value": 33.7},
        {"name": "AMD", "value": 179.0},
        {"name": "AVGO", "value": 90.9},
    ]
    fig = comparison_bars(items, highlight="NVDA")
    assert isinstance(fig, go.Figure)


def test_ownership_pie_sums_to_100():
    from adapters.visualization.components.charts import ownership_pie

    fig = ownership_pie(institutional=70.0, insider=4.0, public=26.0)
    assert isinstance(fig, go.Figure)
    assert fig.data[0].type == "pie"


def test_insider_bars_returns_figure():
    from adapters.visualization.components.charts import insider_bars

    txns = [
        {"quarter": "2026-Q1", "buys": 5, "sells": 12, "buy_value": 500000, "sell_value": 2000000},
        {"quarter": "2025-Q4", "buys": 3, "sells": 8, "buy_value": 300000, "sell_value": 1500000},
    ]
    fig = insider_bars(txns)
    assert isinstance(fig, go.Figure)


def test_financials_line_returns_figure():
    from adapters.visualization.components.charts import financials_line

    import pandas as pd

    dates = pd.date_range("2025-04", periods=5, freq="QS")
    data = pd.DataFrame(
        {"Total Revenue": [50e9, 55e9, 60e9, 65e9, 70e9], "Net Income": [20e9, 22e9, 25e9, 28e9, 32e9]},
        index=dates,
    )
    fig = financials_line(data, metrics=["Total Revenue", "Net Income"])
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 2


def test_cluster_bubble_returns_figure():
    from adapters.visualization.components.charts import cluster_bubble

    tickers = [
        {"ticker": "NVDA", "market_cap": 5.4e12, "change_pct": 1.8, "role": "follower"},
        {"ticker": "AMAT", "market_cap": 184e9, "change_pct": -0.5, "role": "leader"},
    ]
    fig = cluster_bubble(tickers, group_name="Semiconductors", highlight="NVDA")
    assert isinstance(fig, go.Figure)
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `pytest tests/test_new_charts.py -v`
Expected: ImportError — functions don't exist yet.

- [ ] **Step 3: Implement new chart builders**

Append to `adapters/visualization/components/charts.py`:

```python
# ── Phase 5.4 chart builders ────────────────────────────────────────────────


def signal_radar(
    scores: dict[str, float], max_val: float = 10.0
) -> go.Figure:
    """6-axis radar chart for signal layer scores (our Snowflake equivalent).

    Args:
        scores: dict mapping dimension name to score (0 to max_val).
        max_val: Maximum value per axis.
    """
    categories = list(scores.keys())
    values = [max(0, min(max_val, v)) for v in scores.values()]
    # Close the polygon
    categories_closed = categories + [categories[0]]
    values_closed = values + [values[0]]

    fig = go.Figure()
    fig.add_trace(
        go.Scatterpolar(
            r=values_closed,
            theta=categories_closed,
            fill="toself",
            fillcolor="rgba(37,99,235,0.15)",
            line=dict(color="#2563EB", width=2),
            marker=dict(size=6, color="#2563EB"),
            name="Signal Strength",
        )
    )
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, max_val],
                tickfont=dict(size=10, color="#94A3B8"),
                gridcolor="#E2E8F0",
            ),
            angularaxis=dict(
                tickfont=dict(size=12, color="#374151", family="Inter"),
                gridcolor="#E2E8F0",
            ),
            bgcolor="white",
        ),
        showlegend=False,
        margin=dict(l=60, r=60, t=30, b=30),
        height=300,
        paper_bgcolor="white",
        plot_bgcolor="white",
    )
    return fig


def gauge_chart(
    value: float,
    min_v: float,
    max_v: float,
    label: str,
    thresholds: tuple[float, float] | None = None,
) -> go.Figure:
    """Semicircle gauge chart (like SWST ROE/ROA gauges).

    Args:
        thresholds: (low_boundary, high_boundary) for coloring zones.
                    Below low = red, low-high = amber, above high = green.
                    Defaults to (max_v*0.33, max_v*0.66).
    """
    if thresholds is None:
        thresholds = (min_v + (max_v - min_v) * 0.33, min_v + (max_v - min_v) * 0.66)

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            title=dict(text=label, font=dict(size=14, family="Inter", color="#374151")),
            number=dict(
                font=dict(size=28, family="JetBrains Mono", color="#0F172A"),
                suffix="%" if max_v <= 100 else "",
            ),
            gauge=dict(
                axis=dict(range=[min_v, max_v], tickfont=dict(size=10, color="#94A3B8")),
                bar=dict(color="#2563EB", thickness=0.6),
                bgcolor="white",
                borderwidth=0,
                steps=[
                    dict(range=[min_v, thresholds[0]], color="#FEE2E2"),
                    dict(range=[thresholds[0], thresholds[1]], color="#FEF3C7"),
                    dict(range=[thresholds[1], max_v], color="#DCFCE7"),
                ],
            ),
        )
    )
    fig.update_layout(
        height=200,
        margin=dict(l=20, r=20, t=40, b=10),
        paper_bgcolor="white",
    )
    return fig


def comparison_bars(
    items: list[dict],
    highlight: str | None = None,
    value_suffix: str = "",
) -> go.Figure:
    """Horizontal bar chart comparing items, with one highlighted.

    Args:
        items: list of {"name": str, "value": float}.
        highlight: name to highlight in accent blue.
    """
    names = [d["name"] for d in items]
    values = [d["value"] for d in items]
    colors = [
        "#2563EB" if n == highlight else "#94A3B8" for n in names
    ]

    fig = go.Figure(
        go.Bar(
            x=values,
            y=names,
            orientation="h",
            marker_color=colors,
            text=[f"{v:.1f}{value_suffix}" for v in values],
            textposition="inside",
            textfont=dict(color="white", size=12, family="JetBrains Mono"),
        )
    )
    fig.update_layout(
        height=max(150, len(items) * 45),
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(visible=False),
        yaxis=dict(
            autorange="reversed",
            tickfont=dict(size=12, family="Inter", color="#374151"),
        ),
        paper_bgcolor="white",
        plot_bgcolor="white",
    )
    return fig


def ownership_pie(
    institutional: float, insider: float, public: float
) -> go.Figure:
    """Donut chart for ownership breakdown."""
    fig = go.Figure(
        go.Pie(
            labels=["Institutional", "Insider", "Public"],
            values=[institutional, insider, public],
            hole=0.55,
            marker=dict(colors=["#2563EB", "#16A34A", "#94A3B8"]),
            textinfo="label+percent",
            textfont=dict(size=12, family="Inter"),
        )
    )
    fig.update_layout(
        height=280,
        margin=dict(l=20, r=20, t=20, b=20),
        showlegend=False,
        paper_bgcolor="white",
    )
    return fig


def insider_bars(txns: list[dict]) -> go.Figure:
    """Bar chart of insider buys vs sells by quarter.

    Args:
        txns: list of {"quarter": str, "buys": int, "sells": int,
                        "buy_value": float, "sell_value": float}.
    """
    quarters = [t["quarter"] for t in txns]
    buys = [t.get("buy_value", 0) / 1e6 for t in txns]
    sells = [-t.get("sell_value", 0) / 1e6 for t in txns]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=quarters,
            y=buys,
            name="Buys ($M)",
            marker_color="#16A34A",
        )
    )
    fig.add_trace(
        go.Bar(
            x=quarters,
            y=sells,
            name="Sells ($M)",
            marker_color="#DC2626",
        )
    )
    fig.update_layout(
        barmode="relative",
        height=250,
        margin=dict(l=10, r=10, t=10, b=30),
        yaxis=dict(title="Value ($M)", tickfont=dict(size=10)),
        xaxis=dict(tickfont=dict(size=10)),
        legend=dict(orientation="h", yanchor="top", y=1.1),
        paper_bgcolor="white",
        plot_bgcolor="white",
    )
    return fig


def financials_line(
    data: "pd.DataFrame",
    metrics: list[str],
) -> go.Figure:
    """Multi-line chart for quarterly financial metrics.

    Args:
        data: DataFrame with DatetimeIndex and metric columns.
        metrics: Column names to plot.
    """
    colors = ["#2563EB", "#16A34A", "#7C3AED", "#EA580C", "#DC2626"]
    fig = go.Figure()
    for i, metric in enumerate(metrics):
        if metric in data.columns:
            values = data[metric].dropna()
            fig.add_trace(
                go.Scatter(
                    x=values.index,
                    y=values / 1e9,  # Convert to billions
                    name=metric,
                    mode="lines+markers",
                    line=dict(color=colors[i % len(colors)], width=2),
                    marker=dict(size=6),
                )
            )
    fig.update_layout(
        height=300,
        margin=dict(l=10, r=10, t=10, b=30),
        yaxis=dict(title="$ Billions", tickfont=dict(size=10)),
        xaxis=dict(tickfont=dict(size=10)),
        legend=dict(orientation="h", yanchor="top", y=1.12),
        paper_bgcolor="white",
        plot_bgcolor="white",
        hovermode="x unified",
    )
    return fig


def cluster_bubble(
    tickers: list[dict],
    group_name: str,
    highlight: str | None = None,
) -> go.Figure:
    """Bubble chart for supply chain cluster — sized by market cap, colored by performance.

    Args:
        tickers: list of {"ticker": str, "market_cap": float, "change_pct": float, "role": str}.
        group_name: Name of the supply chain group.
        highlight: Ticker to highlight with a border.
    """
    import numpy as np

    names = [t["ticker"] for t in tickers]
    caps = [t["market_cap"] for t in tickers]
    changes = [t["change_pct"] for t in tickers]
    roles = [t.get("role", "unknown") for t in tickers]

    max_cap = max(caps) if caps else 1
    sizes = [max(15, 80 * (c / max_cap) ** 0.5) for c in caps]

    colors = ["#16A34A" if ch >= 0 else "#DC2626" for ch in changes]
    borders = [3 if n == highlight else 0 for n in names]

    fig = go.Figure(
        go.Scatter(
            x=list(range(len(tickers))),
            y=changes,
            mode="markers+text",
            marker=dict(
                size=sizes,
                color=colors,
                opacity=0.7,
                line=dict(width=borders, color="#2563EB"),
            ),
            text=names,
            textposition="middle center",
            textfont=dict(size=10, color="white", family="Inter"),
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Market Cap: $%{customdata[0]:.0f}B<br>"
                "Day Change: %{y:+.2f}%<br>"
                "Role: %{customdata[1]}"
                "<extra></extra>"
            ),
            customdata=list(zip([c / 1e9 for c in caps], roles)),
        )
    )
    fig.update_layout(
        title=dict(text=group_name, font=dict(size=14, family="DM Sans")),
        height=300,
        margin=dict(l=10, r=10, t=40, b=10),
        xaxis=dict(visible=False),
        yaxis=dict(title="Day Change %", tickfont=dict(size=10)),
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=False,
    )
    return fig
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `pytest tests/test_new_charts.py -v`
Expected: 8 passed

- [ ] **Step 5: Run full suite — no regressions**

Run: `pytest tests/ -x -q`
Expected: 838+ passed

- [ ] **Step 6: Commit**

```bash
git add adapters/visualization/components/charts.py tests/test_new_charts.py
git commit -m "feat: add 8 new Plotly chart builders (radar, gauge, comparison, pie, insider, financials, cluster)"
```

---

### Task 4: Fix Missing CSS Classes in styles.py

**Files:**
- Modify: `adapters/visualization/components/styles.py`

- [ ] **Step 1: Add missing CSS class definitions**

Append before the closing `</style>` tag in `GLOBAL_CSS` string (search for the last `}` before `</style>`):

```css
/* ===== Phase 5.4 — Missing CSS fixes ===== */
.hero-label {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-muted);
    font-weight: 500;
}
.hero-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 22px;
    font-weight: 600;
    color: var(--text-primary);
    margin-top: 4px;
}
.hero-sub {
    font-size: 13px;
    color: var(--text-secondary);
    margin-top: 2px;
}
.verdict-card {
    padding: 16px 20px;
    border-radius: var(--radius-md);
    border: 1px solid var(--border);
    margin: 12px 0;
}
.verdict-positive { border-left: 4px solid var(--success); }
.verdict-negative { border-left: 4px solid var(--danger); }
.verdict-neutral { border-left: 4px solid var(--accent); }
.dashboard-card {
    background: var(--bg-primary);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: 16px;
    margin-bottom: 12px;
    box-shadow: var(--shadow-sm);
}

/* ===== Scrolling Ticker Bar ===== */
.ticker-bar {
    display: flex;
    align-items: center;
    gap: 24px;
    padding: 8px 16px;
    background: #0F172A;
    color: white;
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    overflow: hidden;
    white-space: nowrap;
    border-radius: var(--radius-sm);
    margin-bottom: 8px;
}
.ticker-bar-item {
    display: inline-flex;
    align-items: center;
    gap: 6px;
}
.ticker-bar-up { color: #4ADE80; }
.ticker-bar-down { color: #F87171; }

/* ===== Criteria Card (inside ws-card) ===== */
.criteria-dots {
    display: inline-flex;
    gap: 3px;
}
```

- [ ] **Step 2: Verify existing tests still pass**

Run: `pytest tests/ -x -q`
Expected: 838+ passed

- [ ] **Step 3: Commit**

```bash
git add adapters/visualization/components/styles.py
git commit -m "fix: add missing CSS classes (hero-label/value/sub, verdict-card, dashboard-card, ticker-bar)"
```

---

### Task 5: Fix Conviction Engine — Wire Real Sub-Scores

**Files:**
- Modify: `application/conviction_use_case.py`
- Test: `tests/test_conviction_use_case.py` (modify existing)

- [ ] **Step 1: Write test for real sub-scores**

Add to `tests/test_conviction_use_case.py`:

```python
def test_compute_sub_scores_uses_real_data_when_available():
    """Sub-scores should NOT be hardcoded 5.0 when real data is provided."""
    from application.conviction_use_case import ConvictionScoringUseCase
    from datetime import datetime
    from unittest.mock import MagicMock

    use_case = ConvictionScoringUseCase(
        smart_money=MagicMock(),
        tickers=["NVDA"],
        weights=MagicMock(),
    )

    # Simulate real data inputs
    features = {"sm_13d_count": 0, "sm_form4_buy_count": 0,
                "sm_activist_count": 0, "sm_insider_cluster": 0}

    # Create mock buzz signal
    mock_buzz = MagicMock()
    mock_buzz.sentiment_raw = 0.6
    mock_buzz.fetched_at = datetime(2026, 6, 3)

    # Create mock ticker info
    ticker_info = {"pegRatio": 0.66, "freeCashflow": 46e9, "marketCap": 5.3e12, "returnOnEquity": 1.14}

    # Create mock recommendation
    mock_rec = MagicMock()
    mock_rec.grade = "strong_buy"

    sub_scores = use_case._compute_sub_scores(
        features=features,
        ticker_signals=[],
        scan_time=datetime(2026, 6, 4),
        buzz_signals=[mock_buzz],
        ticker_info=ticker_info,
        recommendation=mock_rec,
    )

    # sentiment_momentum should NOT be 5.0 — real buzz data provided
    assert sub_scores["sentiment_momentum"] != 5.0
    # fundamental_basis should NOT be 5.0 — real ticker_info provided
    assert sub_scores["fundamental_basis"] != 5.0
    # ml_direction should NOT be 5.0 — real recommendation provided
    assert sub_scores["ml_direction"] != 5.0
    assert sub_scores["ml_direction"] == 9  # strong_buy maps to 9


def test_compute_sub_scores_falls_back_to_neutral_without_data():
    """Sub-scores should default to 5.0 when no external data provided."""
    from application.conviction_use_case import ConvictionScoringUseCase
    from datetime import datetime
    from unittest.mock import MagicMock

    use_case = ConvictionScoringUseCase(
        smart_money=MagicMock(),
        tickers=["NVDA"],
        weights=MagicMock(),
    )

    features = {"sm_13d_count": 0, "sm_form4_buy_count": 0,
                "sm_activist_count": 0, "sm_insider_cluster": 0}

    sub_scores = use_case._compute_sub_scores(
        features=features,
        ticker_signals=[],
        scan_time=datetime(2026, 6, 4),
    )

    assert sub_scores["sentiment_momentum"] == 5.0
    assert sub_scores["fundamental_basis"] == 5.0
    assert sub_scores["ml_direction"] == 5.0
```

- [ ] **Step 2: Run test — verify it fails**

Run: `pytest tests/test_conviction_use_case.py::test_compute_sub_scores_uses_real_data_when_available -v`
Expected: TypeError — `_compute_sub_scores()` doesn't accept `buzz_signals`, `ticker_info`, `recommendation` params yet.

- [ ] **Step 3: Modify _compute_sub_scores in conviction_use_case.py**

Replace the existing `_compute_sub_scores` static method (lines ~163-205) with:

```python
    @staticmethod
    def _compute_sub_scores(
        features: dict[str, float],
        ticker_signals: list[SmartMoneySignal],
        scan_time: datetime,
        buzz_signals: list | None = None,
        ticker_info: dict | None = None,
        recommendation: object | None = None,
    ) -> dict[str, float]:
        """Compute the six sub-score dimensions using real data when available.

        Falls back to neutral (5.0) for any dimension without data.
        """
        # ── smart_money sub-score (existing logic) ───────────────────────
        sm_raw = (
            features.get("sm_13d_count", 0.0) * 3
            + features.get("sm_insider_cluster", 0.0) * 7
            + features.get("sm_activist_count", 0.0) * 2
        )
        sm_score = min(sm_raw, 10.0)

        # ── signal_agreement: cross-layer check ─────────────────────────
        layers_firing = 0
        if sm_score > 2:
            layers_firing += 1
        if buzz_signals and any(
            getattr(b, "sentiment_raw", 0) > 0 for b in buzz_signals
        ):
            layers_firing += 1
        if ticker_info and ticker_info.get("pegRatio", 99) < 2:
            layers_firing += 1
        if recommendation and getattr(recommendation, "grade", "") in (
            "strong_buy",
            "buy",
        ):
            layers_firing += 1
        signal_agreement = min(layers_firing / 4.0 * 10.0, 10.0)

        # ── sentiment_momentum: from buzz_signals ────────────────────────
        sentiment_momentum = 5.0  # neutral default
        if buzz_signals:
            recent = []
            for b in buzz_signals:
                fetched = getattr(b, "fetched_at", None)
                raw = getattr(b, "sentiment_raw", 0.0)
                if fetched is not None:
                    try:
                        age_days = (scan_time - fetched).total_seconds() / 86400
                        if age_days < 7:
                            recent.append(raw)
                    except (TypeError, AttributeError):
                        recent.append(raw)
                else:
                    recent.append(raw)
            if recent:
                avg = sum(recent) / len(recent)
                sentiment_momentum = max(1.0, min(10.0, 5.0 + avg * 5.0))

        # ── fundamental_basis: from yfinance ticker_info ─────────────────
        fundamental_basis = 5.0  # neutral default
        if ticker_info:
            peg = ticker_info.get("pegRatio") or 99
            mcap = ticker_info.get("marketCap") or 1
            fcf = ticker_info.get("freeCashflow") or 0
            fcf_yield = fcf / max(mcap, 1)
            roe = ticker_info.get("returnOnEquity") or 0

            peg_score = 3 if peg < 1 else (2 if peg < 2 else (1 if peg < 3 else 0))
            fcf_score = (
                3 if fcf_yield > 0.05 else (2 if fcf_yield > 0.02 else (1 if fcf_yield > 0 else 0))
            )
            roe_score = (
                4 if roe > 0.2 else (3 if roe > 0.15 else (2 if roe > 0.1 else 1))
            )
            fundamental_basis = max(1.0, min(10.0, float(peg_score + fcf_score + roe_score)))

        # ── ml_direction: from stored recommendation ─────────────────────
        ml_direction = 5.0  # neutral default
        if recommendation:
            grade = getattr(recommendation, "grade", "hold")
            grade_map = {
                "strong_buy": 9,
                "buy": 7,
                "hold": 5,
                "may_sell": 3,
                "immediate_sell": 1,
            }
            ml_direction = float(grade_map.get(grade, 5))

        # ── temporal_freshness (existing logic) ──────────────────────────
        freshness = 2.0  # default (no signals)
        for sig in ticker_signals:
            try:
                filed_dt = datetime.strptime(sig.filed_date, "%Y-%m-%d")
                fs = compute_freshness_score(filed_dt, scan_time)
                freshness = max(freshness, fs)
            except ValueError:
                pass

        return {
            "smart_money": sm_score,
            "signal_agreement": signal_agreement,
            "temporal_freshness": freshness,
            "sentiment_momentum": sentiment_momentum,
            "fundamental_basis": fundamental_basis,
            "ml_direction": ml_direction,
        }
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `pytest tests/test_conviction_use_case.py -v`
Expected: All existing + 2 new tests pass

- [ ] **Step 5: Run full suite — no regressions**

Run: `pytest tests/ -x -q`
Expected: 838+ passed

- [ ] **Step 6: Commit**

```bash
git add application/conviction_use_case.py tests/test_conviction_use_case.py
git commit -m "feat: wire real sub-scores into conviction engine (sentiment, fundamentals, ML direction)"
```

---

### Task 6: Fix Conviction Engine — Scan All Tickers + Pass Data Sources

**Files:**
- Modify: `adapters/visualization/action_runner.py` (lines 244-318)

- [ ] **Step 1: Remove tickers[:50] truncation and wire store + ticker_info into conviction scan**

Replace `run_conviction_scan` function (lines 244-318 in `action_runner.py`) with:

```python
def run_conviction_scan(
    db_path: str = "data/recommendations.db",
    market: str = "us",
    progress_callback: Callable[[float, str], None] | None = None,
) -> list[OpportunityCard]:
    """Scan for conviction-ranked opportunities using all available data sources.

    Wires: SEC EDGAR (smart money) + SQLite (buzz signals, recommendations) +
    yfinance (fundamentals) into the conviction scoring pipeline.
    """
    _update = progress_callback or (lambda p, m: None)

    # 1. Load market config
    _update(0.10, "Loading market config...")
    from config.loader import load_market_config

    config = load_market_config(market)

    # 2. Load full ticker universe (no truncation)
    _update(0.15, "Loading ticker universe...")
    tickers: list[str] = config.get("tickers", [])
    if not tickers:
        from pathlib import Path

        ticker_path = Path("config/tickers")
        if ticker_path.exists():
            for f in ticker_path.glob("*.txt"):
                tickers.extend(
                    [
                        t.strip()
                        for t in f.read_text().strip().split("\n")
                        if t.strip() and not t.strip().startswith("#")
                    ]
                )
    tickers = sorted(set(tickers))

    # 3. Create adapters
    _update(0.20, f"Initializing data sources for {len(tickers)} tickers...")
    from adapters.data.sec_edgar_adapter import SECEdgarAdapter
    from adapters.data.sqlite_store import SQLiteStore

    edgar = SECEdgarAdapter()
    store = SQLiteStore(db_path)

    # 4. Load watchlist for pinned tickers
    _update(0.25, "Loading watchlist...")
    pinned: set[str] = set()
    try:
        watchlist = store.get_watchlist()
        pinned = {w["symbol"] for w in watchlist}
    except Exception:
        pass

    # 5. Run conviction scoring with all data sources
    _update(0.30, "Scoring conviction across 6 dimensions...")
    from application.conviction_use_case import ConvictionScoringUseCase
    from domain.conviction import ConvictionWeights

    weights = ConvictionWeights()
    use_case = ConvictionScoringUseCase(
        smart_money=edgar,
        tickers=tickers,
        weights=weights,
        store=store,
        pinned=pinned,
        top_n=15,
    )

    def _inner_progress(idx: int, total_: int) -> None:
        frac = 0.30 + 0.65 * (idx / max(total_, 1))
        _update(frac, f"Analyzing {idx}/{total_} tickers...")

    cards = use_case.run(
        scan_time=datetime.now(),
        progress_callback=_inner_progress,
    )
    _update(1.0, f"Scan complete — {len(cards)} opportunities found.")
    return cards
```

- [ ] **Step 2: Update ConvictionScoringUseCase constructor to accept store**

In `application/conviction_use_case.py`, update `__init__`:

```python
    def __init__(
        self,
        smart_money: object,
        tickers: list[str],
        weights: ConvictionWeights,
        store: object | None = None,
        pinned: set[str] | None = None,
        top_n: int = 15,
    ) -> None:
        self._smart_money = smart_money
        self._tickers = tickers
        self._weights = weights
        self._store = store
        self._pinned = pinned or set()
        self._top_n = top_n
        self._engineer = SmartMoneyFeatureEngineer()
```

- [ ] **Step 3: Update _score_ticker to pass real data to _compute_sub_scores**

In `_score_ticker` method, after computing features, add data lookups:

```python
    def _score_ticker(
        self,
        ticker: str,
        signals: list[SmartMoneySignal],
        scan_time: datetime,
    ) -> ConvictionScore:
        """Compute a ConvictionScore for a single ticker."""
        features = self._engineer.compute(
            ticker=ticker, signals=signals, prediction_time=scan_time
        )

        ticker_signals = [s for s in signals if s.ticker == ticker]

        # Fetch additional data from store if available
        buzz_signals = None
        recommendation = None
        ticker_info = None

        if self._store is not None:
            try:
                buzz_signals = self._store.get_buzz_signals(ticker=ticker)
            except Exception:
                pass
            try:
                recs = self._store.get_recommendations()
                ticker_recs = [r for r in recs if r.symbol == ticker]
                recommendation = ticker_recs[0] if ticker_recs else None
            except Exception:
                pass

        # Fetch fundamentals from yfinance (cached)
        try:
            from adapters.visualization.price_cache import _fetch_ticker_info_impl

            ticker_info = _fetch_ticker_info_impl(ticker)
        except Exception:
            pass

        sub_scores = self._compute_sub_scores(
            features=features,
            ticker_signals=ticker_signals,
            scan_time=scan_time,
            buzz_signals=buzz_signals,
            ticker_info=ticker_info,
            recommendation=recommendation,
        )

        conviction = compute_conviction(sub_scores, self._weights)

        filed_dates = [
            datetime.strptime(s.filed_date, "%Y-%m-%d") for s in ticker_signals
        ]
        freshest = max(filed_dates) if filed_dates else scan_time

        explanation = self._build_explanation(ticker, sub_scores, conviction)

        return ConvictionScore(
            ticker=ticker,
            score=conviction,
            sub_scores=sub_scores,
            signals_firing=sum(1 for v in sub_scores.values() if v > 0),
            freshest_signal=freshest,
            explanation=explanation,
        )
```

- [ ] **Step 4: Run full suite — no regressions**

Run: `pytest tests/ -x -q`
Expected: 838+ passed

- [ ] **Step 5: Commit**

```bash
git add adapters/visualization/action_runner.py application/conviction_use_case.py
git commit -m "feat: conviction scan uses all 350 tickers + wires store and yfinance data"
```

---

### Task 7: Fix rank_opportunities Fallback

**Files:**
- Modify: `domain/conviction_service.py`
- Test: `tests/test_conviction_service.py` (add test)

- [ ] **Step 1: Write test for fallback behavior**

Add to `tests/test_conviction_service.py`:

```python
def test_rank_opportunities_returns_top_n_when_all_below_min_score():
    """When all tickers score below min_score, return top N by score instead of empty."""
    from domain.conviction import ConvictionScore
    from domain.conviction_service import rank_opportunities
    from datetime import datetime

    scores = [
        ConvictionScore(
            ticker=f"T{i}",
            score=2.0 + i * 0.1,
            sub_scores={},
            signals_firing=1,
            freshest_signal=datetime(2026, 6, 4),
            explanation="",
        )
        for i in range(20)
    ]

    # All scores are 2.0-3.9, min_score=3.0 would filter most
    result = rank_opportunities(scores, top_n=5, min_score=3.0)

    # Should return at least 5 results (fallback behavior)
    assert len(result) >= 5
```

- [ ] **Step 2: Modify rank_opportunities to add fallback**

In `domain/conviction_service.py`, update `rank_opportunities`:

```python
def rank_opportunities(
    scores: list[ConvictionScore],
    top_n: int = 15,
    pinned: set[str] | None = None,
    min_score: float = 3.0,
) -> list[ConvictionScore]:
    """Rank conviction scores and return the top opportunities.

    Algorithm:
        1. Separate pinned tickers from the rest.
        2. Filter non-pinned by min_score.
        3. Sort remaining descending by score.
        4. Take up to top_n.
        5. Append any pinned tickers that didn't make the cut.
        6. FALLBACK: if fewer than top_n results after filtering,
           fill up from below-threshold tickers sorted by score descending.
    """
    if not scores:
        return []

    pinned = pinned or set()

    pinned_scores: list[ConvictionScore] = []
    eligible: list[ConvictionScore] = []
    below_threshold: list[ConvictionScore] = []

    for cs in scores:
        if cs.ticker in pinned:
            pinned_scores.append(cs)
        elif cs.score >= min_score:
            eligible.append(cs)
        else:
            below_threshold.append(cs)

    eligible.sort(key=lambda c: c.score, reverse=True)
    top = eligible[:top_n]

    # Fallback: if not enough results, fill from below-threshold
    if len(top) < top_n:
        below_threshold.sort(key=lambda c: c.score, reverse=True)
        needed = top_n - len(top)
        top.extend(below_threshold[:needed])

    top_tickers = {c.ticker for c in top}
    missed_pinned = [c for c in pinned_scores if c.ticker not in top_tickers]

    return top + missed_pinned
```

- [ ] **Step 3: Run tests — verify they pass**

Run: `pytest tests/test_conviction_service.py -v`
Expected: All tests pass

- [ ] **Step 4: Run full suite**

Run: `pytest tests/ -x -q`
Expected: 838+ passed

- [ ] **Step 5: Commit**

```bash
git add domain/conviction_service.py tests/test_conviction_service.py
git commit -m "feat: rank_opportunities fallback — returns top N by score when all below threshold"
```

---

### Task 8: Fix monitor_holdings to Use Live Prices

**Files:**
- Modify: `adapters/visualization/action_runner.py` (lines 16-64)

- [ ] **Step 1: Replace get_price_stub with batch price fetch**

Replace the `run_monitor_holdings` function (lines 16-64):

```python
def run_monitor_holdings(
    db_path: str = "data/recommendations.db",
    market: str = "us",
    progress_callback: Callable[[float, str], None] | None = None,
) -> list:
    """Monitor holdings for sell signals using LIVE prices.

    Returns list of SellSignal objects.
    """
    _update = progress_callback or (lambda p, m: None)

    _update(0.10, "Loading holdings...")
    from adapters.data.sqlite_store import SQLiteStore

    store = SQLiteStore(db_path)
    holdings = store.get_holdings()
    if not holdings:
        _update(1.0, "No holdings to monitor.")
        return []

    _update(0.30, "Fetching live prices...")
    from adapters.visualization.price_cache import _batch_fetch_prices_impl

    tickers = tuple(h.symbol for h in holdings)
    prices = _batch_fetch_prices_impl(tickers)

    def get_live_price(symbol: str) -> float:
        """Return live price from batch fetch, fall back to purchase price."""
        if symbol in prices:
            return prices[symbol]["price"]
        # If live price unavailable, return a very high price to avoid false sell signals
        holding = next((h for h in holdings if h.symbol == symbol), None)
        return holding.purchase_price if holding else 0.0

    _update(0.50, "Checking sell signals...")
    from application.monitor_holdings import MonitorHoldingsUseCase
    from config.loader import load_market_config

    config = load_market_config(market)
    use_case = MonitorHoldingsUseCase(
        store=store,
        get_current_price=get_live_price,
        config=config,
    )
    signals = use_case.check_all()
    _update(1.0, f"Found {len(signals)} sell signals.")
    return signals
```

- [ ] **Step 2: Run full suite — no regressions**

Run: `pytest tests/ -x -q`
Expected: 838+ passed

- [ ] **Step 3: Commit**

```bash
git add adapters/visualization/action_runner.py
git commit -m "fix: monitor_holdings uses live yfinance prices instead of purchase price stub"
```

---

### Task 9: Add 6-Tab Router (Stock Analysis tab)

**Files:**
- Modify: `adapters/visualization/dashboard.py`

- [ ] **Step 1: Update dashboard.py to 6 tabs**

Replace entire file:

```python
"""Dashboard entry point — 6-tab router."""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Stock Intelligence",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="collapsed",
)

from adapters.visualization.components.styles import inject_global_css  # noqa: E402

inject_global_css()

st.markdown(
    "<h1 style=\"margin-bottom:2px;font-family:'DM Sans',sans-serif;\">Multi-Modal Stock Recommender</h1>",
    unsafe_allow_html=True,
)

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    [
        "Today's Opportunities",
        "Watchlist",
        "My Portfolio",
        "Stock Analysis",
        "How It Works",
        "Market Context",
    ]
)

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
    from adapters.visualization.tabs.stock_analysis import render as render_analysis

    render_analysis()
with tab5:
    from adapters.visualization.tabs.model_confidence import render as render_hiw

    render_hiw()
with tab6:
    from adapters.visualization.tabs.market_pulse import render as render_market

    render_market()

st.markdown(
    '<div class="ws-footer">Multi-Modal Stock Recommender · Hexagonal Architecture · Built by Tirth Joshi</div>',
    unsafe_allow_html=True,
)
```

- [ ] **Step 2: Create minimal stock_analysis.py stub**

```python
# adapters/visualization/tabs/stock_analysis.py
"""Tab 4: Stock Analysis — SWST-grade deep dive for any ticker."""

from __future__ import annotations

import streamlit as st


def render() -> None:
    """Render the Stock Analysis tab — placeholder for Phase 3 implementation."""
    st.markdown("### Stock Analysis")
    st.markdown(
        '<div style="color:#64748B;font-size:14px;margin-bottom:16px;">'
        "Type any S&P 500 or NASDAQ-100 ticker to get a full multi-signal analysis."
        "</div>",
        unsafe_allow_html=True,
    )

    cols = st.columns([4, 1])
    ticker = cols[0].text_input(
        "Ticker",
        placeholder="NVDA",
        label_visibility="collapsed",
    )
    analyze = cols[1].button("Run Analysis", type="primary")

    if analyze and ticker:
        st.info(
            f"Full analysis for {ticker.upper()} coming in Phase 3 of the redesign. "
            "Foundation components are ready."
        )
    elif not ticker:
        st.markdown(
            '<div class="ws-card" style="text-align:center;padding:2rem;">'
            '<div style="font-size:15px;font-weight:500;color:#1A202C;">'
            "Enter a ticker above to start</div>"
            '<div style="font-size:13px;color:#64748B;margin-top:4px;">'
            "Get valuation, growth, financial health, sentiment, and conviction analysis"
            "</div></div>",
            unsafe_allow_html=True,
        )
```

- [ ] **Step 3: Run full suite — no regressions**

Run: `pytest tests/ -x -q`
Expected: 838+ passed

- [ ] **Step 4: Commit**

```bash
git add adapters/visualization/dashboard.py adapters/visualization/tabs/stock_analysis.py
git commit -m "feat: add Stock Analysis as 6th tab (stub — full implementation in Phase 3)"
```

---

### Task 10: Wire load_recommendations into data_loader + cleanup dead loaders

**Files:**
- Modify: `adapters/visualization/data_loader.py`

- [ ] **Step 1: Add load_recommendations_latest function and remove dead loaders**

Add this function to `data_loader.py`:

```python
def load_recommendations_latest(db_path: str = DB_PATH) -> list:
    """Load most recent week's recommendations sorted by composite_score descending."""
    try:
        store = _get_store(db_path)
        recs = store.get_recommendations()
        if not recs:
            return []
        # Find the latest week_start
        latest_week = max(r.week_start for r in recs)
        latest = [r for r in recs if r.week_start == latest_week]
        latest.sort(key=lambda r: r.composite_score, reverse=True)
        return latest
    except Exception:
        return []
```

Remove these unused functions (verify they're not imported anywhere first):
- `load_event_sector_mapping`
- `load_scan_timestamp`

- [ ] **Step 2: Run full suite — no regressions**

Run: `pytest tests/ -x -q`
Expected: 838+ passed

- [ ] **Step 3: Commit**

```bash
git add adapters/visualization/data_loader.py
git commit -m "feat: add load_recommendations_latest, remove dead loaders"
```

---

### Task 11: Update CONTEXT.md with Phase 5.4 Glossary

**Files:**
- Modify: `CONTEXT.md`

- [ ] **Step 1: Add Phase 5.4 terms to Glossary**

Append to the Glossary section:

```markdown
### Signal Radar
6-axis radar chart visualizing signal strength per dimension: Technical, Sentiment, Fundamental, Cross-Asset, Event-Causal, Smart Money. Our equivalent of SimplyWallSt's Snowflake chart. Each axis scored 0-10. Displayed on Stock Analysis tab and opportunity cards.

### Criteria Card
SWST-inspired component showing a scored checklist (e.g., "Valuation Score 4/6 ●●●●○○") with a plain English summary. Used across all tabs for every analysis section.

### Verdict Bullet
Green check (✅ pass), amber warning (⚠️ warn), or red X (❌ fail) with a plain English finding. Follows every criteria card and chart.

### Hold Duration
Recommendation derived from multi-horizon signals:
- All horizons bullish → "Hold until flip" (10+ days)
- 2d bullish, 5d/10d neutral → "Short hold (2-3 days)"
- 2d neutral, 5d/10d bullish → "Position hold (5-10 days)"
- Mixed signals → "Monitor daily"

### Market Overview Mode
Landing page fallback when conviction scan data is thin (<5 results). Shows the 15 tournament recommendations ranked by composite score, plus a market heatmap treemap. Banner encourages fresh scan.
```

- [ ] **Step 2: Commit**

```bash
git add CONTEXT.md
git commit -m "docs: add Phase 5.4 glossary terms (signal radar, criteria card, hold duration)"
```

---

### Task 12: Foundation Integration Test

**Files:**
- Create: `tests/test_phase54_integration.py`

- [ ] **Step 1: Write integration test verifying foundation components work together**

```python
# tests/test_phase54_integration.py
"""Integration tests for Phase 5.4 foundation components."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_conviction_scan_produces_more_than_2_results():
    """The fixed conviction engine should produce >2 results with real sub-scores."""
    from datetime import datetime

    from application.conviction_use_case import ConvictionScoringUseCase
    from domain.conviction import ConvictionWeights

    mock_smart_money = MagicMock()
    mock_smart_money.get_all_signals.return_value = []

    mock_store = MagicMock()
    mock_store.get_buzz_signals.return_value = []
    mock_store.get_recommendations.return_value = []

    tickers = ["AAPL", "NVDA", "MSFT", "GOOG", "META", "AMD", "TSLA", "AMZN"]

    with patch(
        "application.conviction_use_case._fetch_ticker_info_impl",
        return_value={"pegRatio": 1.5, "freeCashflow": 10e9, "marketCap": 1e12, "returnOnEquity": 0.25},
    ):
        use_case = ConvictionScoringUseCase(
            smart_money=mock_smart_money,
            tickers=tickers,
            weights=ConvictionWeights(),
            store=mock_store,
            top_n=8,
        )
        cards = use_case.run(scan_time=datetime(2026, 6, 4))

    # With fallback, should get up to top_n results even if all below min_score
    assert len(cards) >= 5, f"Expected >=5 cards, got {len(cards)}"


def test_all_card_components_render_html():
    """Verify all card components return valid HTML strings."""
    from adapters.visualization.components.cards import (
        criteria_card,
        loading_stepper_html,
        metric_kpi,
        mini_sparkline,
        price_range_bar,
        verdict_bullet,
    )

    assert "<div" in criteria_card("Test", 3, 5, "Summary")
    assert "<div" in verdict_bullet("pass", "Good")
    assert "<div" in metric_kpi("Value", "$100")
    assert "<div" in price_range_bar(100, 80, 120)
    assert "<svg" in mini_sparkline([1, 2, 3, 4, 5])
    assert "<div" in loading_stepper_html(["Step 1", "Step 2"], 0)


def test_all_new_chart_builders_return_figures():
    """Verify all new chart builders return Plotly Figure objects."""
    import pandas as pd
    import plotly.graph_objects as go

    from adapters.visualization.components.charts import (
        cluster_bubble,
        comparison_bars,
        financials_line,
        gauge_chart,
        insider_bars,
        ownership_pie,
        signal_radar,
    )

    assert isinstance(signal_radar({"A": 5, "B": 7, "C": 3}), go.Figure)
    assert isinstance(gauge_chart(50, 0, 100, "Test"), go.Figure)
    assert isinstance(comparison_bars([{"name": "X", "value": 10}]), go.Figure)
    assert isinstance(ownership_pie(70, 5, 25), go.Figure)
    assert isinstance(insider_bars([{"quarter": "Q1", "buys": 1, "sells": 2, "buy_value": 100, "sell_value": 200}]), go.Figure)

    dates = pd.date_range("2025-01", periods=3, freq="QS")
    df = pd.DataFrame({"Revenue": [1e9, 2e9, 3e9]}, index=dates)
    assert isinstance(financials_line(df, ["Revenue"]), go.Figure)

    tickers_data = [{"ticker": "A", "market_cap": 1e12, "change_pct": 1.0, "role": "leader"}]
    assert isinstance(cluster_bubble(tickers_data, "Test"), go.Figure)
```

- [ ] **Step 2: Run integration tests**

Run: `pytest tests/test_phase54_integration.py -v`
Expected: 3 passed

- [ ] **Step 3: Run full suite**

Run: `pytest tests/ -x -q`
Expected: 840+ passed (838 existing + new tests from this phase)

- [ ] **Step 4: Commit**

```bash
git add tests/test_phase54_integration.py
git commit -m "test: add Phase 5.4 foundation integration tests"
```

---

## Phase 2: Tab 1 Overhaul (Tasks 13-20)

> Detailed implementation in each task. Subagents should read the spec section "Tab 1: Today's Opportunities" and the new components from Phase 1.

### Task 13: Implement scrolling ticker bar component
**Files:** Modify `command_center.py`. Use `fetch_index_prices()` from `price_cache.py`. Render as HTML div with `ticker-bar` CSS class. Show SPY, QQQ, DIA, IWM with price + change %. Green/red coloring.

### Task 14: Improve hero panels with live data
**Files:** Modify `command_center.py` + `hero.py`. Portfolio panel: compute real P&L from `batch_fetch_prices()` for holding tickers. Signal panel: fix "N watchlist alerts" to show actual alert count. Market panel: render SPY sparkline as small Plotly chart using `load_spy_sparkline()` prices/times data.

### Task 15: Implement Mode A — Market Overview (recommendations as cards)
**Files:** Modify `command_center.py`. When `ScanCache` has < 5 results, show `load_recommendations_latest()` as styled cards with grade badge, composite score, predicted 5d return, horizon signal pills, reasoning text, and [Analyze →] button. Include banner: "Market overview shown — run a fresh scan for conviction-scored opportunities."

### Task 16: Implement market heatmap treemap
**Files:** Modify `command_center.py`. Use `cluster_bubble` or `treemap_chart` from new charts. Show all recommendation + holding + watchlist tickers sized by market cap (from `batch_fetch_prices` or `fetch_ticker_info`), colored by day change.

### Task 17: Improve conviction cards (Mode B)
**Files:** Modify `compact_card.py`. Add mini `signal_radar` (small 150px version), hold duration text derived from recommendation horizon_signals, action buttons ([Analyze →] [+ Watchlist] [+ Portfolio]).

### Task 18: Wire recommendation data into landing page
**Files:** Modify `command_center.py` + `data_loader.py`. For each opportunity card, look up matching recommendation from SQLite to get horizon_signals, predicted returns, reasoning. Display these in expanded card view.

### Task 19: Fix watchlist alerts count
**Files:** Modify `command_center.py`. Replace `n_watchlist_alerts = len(watchlist)` with actual alert detection: count watchlist tickers where conviction changed or sell signals detected.

### Task 20: Write tests for Tab 1 changes
**Files:** Add tests to `tests/test_dashboard_integration.py` or new `tests/test_tab1.py`. Smoke test imports + render with mock data.

---

## Phase 3: Stock Analysis Tab (Tasks 21-31)

> The showpiece. Each section is a task. Subagents should read the spec section "Tab 4: Stock Analysis" and reference REFERENCE_NOTES.md.

### Task 21: Create stock_analyzer.py (data fetching + criteria scoring)
**Files:** Create `adapters/visualization/stock_analyzer.py`. Contains `analyze_ticker(ticker: str) -> AnalysisResult` dataclass with all fetched data + computed criteria scores for each section.

### Task 22: Implement stock_analysis.py main structure
**Files:** Rewrite `tabs/stock_analysis.py`. Search bar → Run Analysis button → progressive loading → call stock_analyzer → render sections. Cache results in `st.session_state`.

### Task 23: Section 0 — Verdict + Signal Radar
**Files:** `tabs/stock_analysis.py`. Render signal_radar chart, conviction score, grade badge, hold duration, side-by-side "Our System vs Wall Street" comparison table, action buttons.

### Task 24: Section 1 — Valuation
**Files:** `tabs/stock_analysis.py`. Criteria card (6 checks), P/E vs sector peers `comparison_bars`, analyst price target `price_range_bar`, 6 `verdict_bullet`s.

### Task 25: Section 2 — Growth
**Files:** `tabs/stock_analysis.py`. Criteria card (6 checks), company vs industry vs market `comparison_bars` for revenue + earnings growth, quarterly `financials_line` chart.

### Task 26: Section 3 — Past Performance
**Files:** `tabs/stock_analysis.py`. Criteria card (6 checks), ROE `gauge_chart`, margins `comparison_bars`, revenue/earnings history `financials_line`.

### Task 27: Section 4 — Financial Health
**Files:** `tabs/stock_analysis.py`. Criteria card (6 checks), D/E `gauge_chart`, cash vs debt bar, current ratio context.

### Task 28: Section 5 — Ownership & Smart Money
**Files:** `tabs/stock_analysis.py`. Criteria card (5 checks), `ownership_pie`, `insider_bars` from yfinance insider_transactions, SEC EDGAR 13D if available.

### Task 29: Section 6 — Sentiment & Signals
**Files:** `tabs/stock_analysis.py`. Criteria card (5 checks), buzz volume `timeline_chart`, sentiment trend line, source agreement indicator, divergence indicator.

### Task 30: Section 7 — Supply Chain
**Files:** `tabs/stock_analysis.py`. Criteria card (4 checks), `cluster_bubble` chart, leader/follower text. Find which supply chain group ticker belongs to from YAML config.

### Task 31: Write tests for Stock Analysis
**Files:** Create `tests/test_stock_analyzer.py` + `tests/test_stock_analysis_tab.py`. Test criteria scoring logic, data assembly, smoke test tab render.

---

## Phase 4: Watchlist + Portfolio (Tasks 32-39)

### Task 32: Watchlist — styled cards with live prices + sparklines
### Task 33: Watchlist — remove button + structured add form
### Task 34: Watchlist — conviction score + criteria card per ticker
### Task 35: Portfolio — live P&L computation with batch prices
### Task 36: Portfolio — portfolio value over time line chart
### Task 37: Portfolio — position health cards with criteria + hold duration
### Task 38: Portfolio — P&L bar chart + allocation pie
### Task 39: Tests for Watchlist + Portfolio

---

## Phase 5: How It Works + Market Context (Tasks 40-46)

### Task 40: Fix accuracy chart with real per-fold data from backtest JSON
### Task 41: Wire grade_donut + sector_heatmap (dead charts)
### Task 42: Add criteria cards to expander sections
### Task 43: Market Context — live prices on supply chain ticker tags
### Task 44: Market Context — cluster bubble chart
### Task 45: Market Context — real pipeline timestamps from buzz_signals
### Task 46: Tests for How It Works + Market Context

---

## Phase 6: Polish (Tasks 47-52)

### Task 47: Dead code cleanup (delete unused components, formatters, loaders)
### Task 48: Tooltips / hover explainers on key elements
### Task 49: Responsive layout check across screen sizes
### Task 50: Update Known Limitations section in How It Works
### Task 51: Full visual QA — screenshot every tab, compare to SWST reference
### Task 52: Update README.md, CLAUDE.md, CONTEXT.md with Phase 5.4 status + ADR-036

---

## Verification Checklist (after all phases)

- [ ] `make check` passes (lint + typecheck + tests)
- [ ] 890+ tests (838 existing + ~50-80 new)
- [ ] Tab 1: shows 15+ opportunities (not 2) when scanned
- [ ] Tab 1: market overview mode works when no conviction data
- [ ] Tab 2: each ticker shows live price, sparkline, remove button
- [ ] Tab 3: real P&L per position, portfolio value chart
- [ ] Tab 4: type NVDA → full 7-section analysis with ~15 charts in <15 seconds
- [ ] Tab 5: real per-fold accuracy, no np.linspace interpolation
- [ ] Tab 6: live prices on supply chain tickers, cluster visualization
- [ ] Every section uses criteria card → chart → verdict bullet pattern
- [ ] Progressive loading with step messages on all action buttons
- [ ] No missing CSS classes (hero-label, verdict-card, etc.)
- [ ] No dead code remaining
- [ ] No silent bugs (monitor_holdings uses live prices, portfolio P&L is real)
