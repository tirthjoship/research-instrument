from unittest.mock import MagicMock

from application.analyst_panel import (
    build_analyst_panel,
    build_finnhub_consensus_panel,
    get_analyst_panel_with_fallback,
)


def test_panel_attributes_and_shows_dispersion():
    raw = {
        "analyst_recommendation_mean": 2.1,
        "analyst_count": 28,
        "targetMeanPrice": 480.0,
        "targetHighPrice": 600.0,
        "targetLowPrice": 350.0,
    }
    p = build_analyst_panel(raw, as_of="2026-06-12")
    assert p.count == 28 and p.target_high == 600.0 and p.target_low == 350.0
    assert p.as_of == "2026-06-12"
    assert p.attribution.lower().startswith("the street")  # attributed, not adopted


def test_panel_handles_missing_data_gap():
    p = build_analyst_panel({}, as_of="2026-06-12")
    assert p.count == 0 and p.data_gap is True


def test_finnhub_panel_computes_weighted_mean_rating():
    trend = {"strongBuy": 7, "buy": 2, "hold": 1, "sell": 0, "strongSell": 0}
    p = build_finnhub_consensus_panel(trend, as_of="2026-07-18")
    assert p.count == 10
    assert p.mean_rating is not None and round(p.mean_rating, 2) == 1.4
    assert p.target_mean is None and p.target_high is None and p.target_low is None
    assert p.data_gap is False
    assert "finnhub" in p.attribution.lower()


def test_finnhub_panel_none_trend_is_data_gap():
    p = build_finnhub_consensus_panel(None, as_of="2026-07-18")
    assert p.count == 0 and p.data_gap is True


def test_finnhub_panel_zero_counts_is_data_gap():
    trend = {"strongBuy": 0, "buy": 0, "hold": 0, "sell": 0, "strongSell": 0}
    p = build_finnhub_consensus_panel(trend, as_of="2026-07-18")
    assert p.data_gap is True


def test_fallback_returns_yfinance_panel_when_present():
    info = {"analyst_count": 12, "analyst_recommendation_mean": 2.0}
    mock_adapter = MagicMock()
    p = get_analyst_panel_with_fallback(
        "AAPL", info, as_of="2026-07-18", finnhub_adapter=mock_adapter
    )
    assert p.count == 12
    mock_adapter.get_recommendation_trend.assert_not_called()


def test_fallback_skips_finnhub_for_non_canadian_ticker():
    mock_adapter = MagicMock()
    p = get_analyst_panel_with_fallback(
        "FORCEMOT.NS", {}, as_of="2026-07-18", finnhub_adapter=mock_adapter
    )
    assert p.data_gap is True
    mock_adapter.get_recommendation_trend.assert_not_called()


def test_fallback_calls_finnhub_for_canadian_ticker_on_data_gap():
    mock_adapter = MagicMock()
    mock_adapter.get_recommendation_trend.return_value = {
        "strongBuy": 3,
        "buy": 1,
        "hold": 0,
        "sell": 0,
        "strongSell": 0,
    }
    p = get_analyst_panel_with_fallback(
        "RY.TO", {}, as_of="2026-07-18", finnhub_adapter=mock_adapter
    )
    assert p.count == 4
    assert p.data_gap is False
    assert "finnhub" in p.attribution.lower()
    mock_adapter.get_recommendation_trend.assert_called_once_with("RY.TO")
