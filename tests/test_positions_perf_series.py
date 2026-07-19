"""Tests for positions.py::_perf_series — real constant-weight backtest.

Replaces the old fabricated "v1 linear ramp" (a straight line from 0% to the
final pnl_pct with hardcoded month labels). The new version must use real
per-ticker historical closes weighted by TODAY's portfolio weight, vs real
SPY closes over the same real dates.
"""

from __future__ import annotations

import pytest


def test_perf_series_uses_real_weighted_closes_not_linear_ramp(monkeypatch):
    """The new _perf_series must be built from real per-ticker closes weighted by
    each row's current portfolio weight, not a fabricated straight-line ramp from
    0 to the final pnl_pct."""
    from adapters.visualization.portfolio_view import PortfolioRow
    from adapters.visualization.tabs import positions as pos_tab

    rows = [
        PortfolioRow(
            ticker="AAA",
            sector="Tech",
            weight=60.0,
            value=6000.0,
            cost=5000.0,
            pnl=20.0,
            today=0.5,
            verdict="HOLD",
            why="",
            dividend_yield=None,
            beta=None,
            quantity=10.0,
        ),
        PortfolioRow(
            ticker="BBB",
            sector="Tech",
            weight=40.0,
            value=4000.0,
            cost=4200.0,
            pnl=-4.8,
            today=-0.2,
            verdict="HOLD",
            why="",
            dividend_yield=None,
            beta=None,
            quantity=5.0,
        ),
    ]

    def _fake_fetch_price_history(ticker):
        histories = {
            "AAA": {
                "closes": [100.0, 105.0, 110.0],
                "dates": ["2026-01-01", "2026-01-02", "2026-01-03"],
            },
            "BBB": {
                "closes": [50.0, 49.0, 48.0],
                "dates": ["2026-01-01", "2026-01-02", "2026-01-03"],
            },
            "SPY": {
                "closes": [400.0, 402.0, 404.0],
                "dates": ["2026-01-01", "2026-01-02", "2026-01-03"],
            },
        }
        return histories.get(ticker)

    monkeypatch.setattr(pos_tab, "fetch_price_history", _fake_fetch_price_history)

    port, spy, labels = pos_tab._perf_series(rows, "all")

    # AAA +10% by day 3, weighted 60%; BBB -4% by day 3, weighted 40%
    # weighted final ~= 0.6*10 + 0.4*(-4) = 6 - 1.6 = 4.4
    assert port[-1] == pytest.approx(4.4, abs=0.1)
    assert port[0] == pytest.approx(0.0, abs=0.01)  # normalized to start at 0%
    assert spy[-1] == pytest.approx(1.0, abs=0.1)  # (404-400)/400 = 1%
    assert labels == ["2026-01-01", "2026-01-02", "2026-01-03"]


def test_perf_series_degrades_honestly_when_no_ticker_has_history(monkeypatch):
    from adapters.visualization.portfolio_view import PortfolioRow
    from adapters.visualization.tabs import positions as pos_tab

    rows = [
        PortfolioRow(
            ticker="ZZZ",
            sector="Tech",
            weight=100.0,
            value=1000.0,
            cost=900.0,
            pnl=11.0,
            today=0.0,
            verdict="HOLD",
            why="",
            dividend_yield=None,
            beta=None,
            quantity=1.0,
        )
    ]
    monkeypatch.setattr(pos_tab, "fetch_price_history", lambda ticker: None)

    port, spy, labels = pos_tab._perf_series(rows, "all")
    assert port == []
    assert spy == []
    assert labels == []
