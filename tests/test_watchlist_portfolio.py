"""Tests for watchlist and portfolio tab rewrites (Phase 5.4 Tasks 32-39)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

# ── Task 32/33: Watchlist folded into positions tab ──────────────────────────


def test_watchlist_section_importable() -> None:
    from adapters.visualization.tabs.positions import _render_watchlist_section

    assert callable(_render_watchlist_section)


def test_watchlist_add_form_importable() -> None:
    from adapters.visualization.tabs.positions import _render_watchlist_add_form

    assert callable(_render_watchlist_add_form)


def test_watchlist_card_importable() -> None:
    from adapters.visualization.tabs.positions import _render_watchlist_card

    assert callable(_render_watchlist_card)


# ── Task 35/36: Positions tab importable ─────────────────────────────────────


def test_positions_render_importable() -> None:
    from adapters.visualization.tabs.positions import render

    assert callable(render)


@pytest.mark.skip(
    reason="Task 12: _render_portfolio_summary removed — replaced by build_hero_html"
)
def test_positions_portfolio_summary_importable() -> None:
    from adapters.visualization.tabs.positions import _render_portfolio_summary

    assert callable(_render_portfolio_summary)


def test_positions_pnl_chart_importable() -> None:
    from adapters.visualization.tabs.positions import _render_pnl_chart

    assert callable(_render_pnl_chart)


# ── Task 37: Portfolio P&L computation logic ──────────────────────────────────


@dataclass
class _FakeHolding:
    symbol: str
    quantity: int
    purchase_price: float
    purchase_date: str = "2026-01-01"
    notes: str = ""


def _compute_portfolio_pnl(
    holdings: list[_FakeHolding],
    prices: dict[str, dict[str, float]],
) -> tuple[float, float, float]:
    """Mirror the P&L logic from _render_portfolio_summary."""
    total_value = 0.0
    total_cost = 0.0
    for h in holdings:
        p = prices.get(h.symbol, {})
        current = p.get("price", h.purchase_price)
        total_value += h.quantity * current
        total_cost += h.quantity * h.purchase_price
    total_pnl = total_value - total_cost
    pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0.0
    return total_value, total_pnl, pnl_pct


def test_portfolio_summary_gain() -> None:
    """Holdings at current price above cost → positive P&L."""
    holdings = [
        _FakeHolding(symbol="NVDA", quantity=10, purchase_price=100.0),
    ]
    prices = {"NVDA": {"price": 150.0, "change_pct": 1.5}}
    total_value, total_pnl, pnl_pct = _compute_portfolio_pnl(holdings, prices)
    assert total_value == 1500.0
    assert total_pnl == 500.0
    assert abs(pnl_pct - 50.0) < 0.01


def test_portfolio_summary_loss() -> None:
    """Holdings at current price below cost → negative P&L."""
    holdings = [
        _FakeHolding(symbol="META", quantity=5, purchase_price=200.0),
    ]
    prices = {"META": {"price": 160.0, "change_pct": -2.0}}
    total_value, total_pnl, pnl_pct = _compute_portfolio_pnl(holdings, prices)
    assert total_value == 800.0
    assert total_pnl == -200.0
    assert abs(pnl_pct - (-20.0)) < 0.01


def test_portfolio_summary_no_price_falls_back_to_cost() -> None:
    """Missing live price → falls back to purchase_price (zero P&L)."""
    holdings = [
        _FakeHolding(symbol="TSLA", quantity=3, purchase_price=250.0),
    ]
    prices: dict[str, Any] = {}  # no live price
    total_value, total_pnl, pnl_pct = _compute_portfolio_pnl(holdings, prices)
    assert total_value == 750.0
    assert total_pnl == 0.0
    assert pnl_pct == 0.0


def test_portfolio_summary_empty_holdings() -> None:
    """No holdings → all zeros."""
    total_value, total_pnl, pnl_pct = _compute_portfolio_pnl([], {})
    assert total_value == 0.0
    assert total_pnl == 0.0
    assert pnl_pct == 0.0


def test_portfolio_summary_multi_position() -> None:
    """Multi-position aggregation is correct."""
    holdings = [
        _FakeHolding(symbol="AAPL", quantity=10, purchase_price=150.0),
        _FakeHolding(symbol="MSFT", quantity=5, purchase_price=300.0),
    ]
    prices = {
        "AAPL": {"price": 180.0, "change_pct": 0.5},
        "MSFT": {"price": 350.0, "change_pct": 0.8},
    }
    total_value, total_pnl, pnl_pct = _compute_portfolio_pnl(holdings, prices)
    # AAPL: 10 * 180 = 1800, cost = 1500 → +300
    # MSFT: 5 * 350 = 1750, cost = 1500 → +250
    assert abs(total_value - 3550.0) < 0.01
    assert abs(total_pnl - 550.0) < 0.01
    assert abs(pnl_pct - (550.0 / 3000.0 * 100)) < 0.01


# ── Task 38: Watchlist card formatting ───────────────────────────────────────


def test_mcap_format_billions() -> None:
    """Market cap >1B renders as $XB."""
    mcap = 2_500_000_000
    mcap_str = f"${mcap / 1e9:.0f}B" if mcap > 1e9 else "—"
    assert mcap_str == "$2B"


def test_mcap_format_millions() -> None:
    """Market cap between 1M and 1B renders as $XM."""
    mcap = 450_000_000
    if mcap > 1e9:
        mcap_str = f"${mcap / 1e9:.0f}B"
    elif mcap > 1e6:
        mcap_str = f"${mcap / 1e6:.0f}M"
    else:
        mcap_str = "—"
    assert mcap_str == "$450M"


def test_mcap_format_small_is_dash() -> None:
    """Market cap 0 or tiny → '—'."""
    mcap = 0
    if mcap > 1e9:
        mcap_str = f"${mcap / 1e9:.0f}B"
    elif mcap > 1e6:
        mcap_str = f"${mcap / 1e6:.0f}M"
    else:
        mcap_str = "—"
    assert mcap_str == "—"


def test_price_change_color_positive() -> None:
    change = 1.5
    color = "#16A34A" if change >= 0 else "#DC2626"
    assert color == "#16A34A"


def test_price_change_color_negative() -> None:
    change = -2.3
    color = "#16A34A" if change >= 0 else "#DC2626"
    assert color == "#DC2626"
