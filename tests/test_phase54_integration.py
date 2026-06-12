"""Integration tests for Phase 5.4 foundation components."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import plotly.graph_objects as go


def test_conviction_engine_produces_results_with_fallback():
    """Fixed conviction engine should produce results via fallback even without EDGAR data."""
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
        "adapters.visualization.price_cache._fetch_ticker_info_impl",
        return_value={
            "pegRatio": 1.5,
            "freeCashflow": 10e9,
            "marketCap": 1e12,
            "returnOnEquity": 0.25,
        },
    ):
        use_case = ConvictionScoringUseCase(
            smart_money=mock_smart_money,
            tickers=tickers,
            weights=ConvictionWeights(),
            store=mock_store,
            top_n=8,
        )
        cards = use_case.run(scan_time=datetime(2026, 6, 4))

    assert len(cards) >= 5, f"Expected >=5 cards, got {len(cards)}"


def test_all_card_components_render_html():
    """All card components return valid HTML strings."""
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
    """All new chart builders return Plotly Figure objects."""
    import pandas as pd

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
    assert isinstance(
        insider_bars(
            [
                {
                    "quarter": "Q1",
                    "buys": 1,
                    "sells": 2,
                    "buy_value": 100,
                    "sell_value": 200,
                }
            ]
        ),
        go.Figure,
    )

    dates = pd.date_range("2025-01", periods=3, freq="QS")
    df = pd.DataFrame({"Revenue": [1e9, 2e9, 3e9]}, index=dates)
    assert isinstance(financials_line(df, ["Revenue"]), go.Figure)

    tickers_data = [
        {
            "ticker": "A",
            "market_cap": 1e12,
            "change_pct": 1.0,
            "role": "leader",
        }
    ]
    assert isinstance(cluster_bubble(tickers_data, "Test"), go.Figure)


def test_price_cache_functions_exist():
    """Price cache module exports all expected functions."""
    from adapters.visualization.price_cache import (
        _batch_fetch_prices_impl,
        _fetch_ticker_info_impl,
        fetch_ticker_info,
    )

    # All functions should be importable and callable
    assert callable(_batch_fetch_prices_impl)
    assert callable(_fetch_ticker_info_impl)
    assert callable(fetch_ticker_info)


def test_load_recommendations_latest_returns_list():
    """data_loader.load_recommendations_latest returns a list (even if empty)."""
    from adapters.visualization.data_loader import load_recommendations_latest

    result = load_recommendations_latest("nonexistent.db")
    assert isinstance(result, list)
