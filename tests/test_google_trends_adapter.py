"""Tests for GoogleTrendsAdapter — never hits real Google Trends API."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pandas as pd

from adapters.data.google_trends_adapter import GoogleTrendsAdapter
from domain.models import BuzzSignal

SCAN_TIME = datetime(2026, 6, 1, 9, 0, 0, tzinfo=timezone.utc)
START_DATE = datetime(2026, 1, 1, tzinfo=timezone.utc)
END_DATE = datetime(2026, 3, 1, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_trends_df(tickers: list[str], value: int = 75) -> pd.DataFrame:
    """Build a minimal DataFrame mimicking pytrends interest_over_time output."""
    dates = pd.date_range("2026-05-25", periods=3, freq="D")
    data = {t: [value] * 3 for t in tickers}
    data["isPartial"] = [False] * 3
    return pd.DataFrame(data, index=dates)


def _make_weekly_df(ticker: str) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=4, freq="W")
    return pd.DataFrame(
        {ticker: [20, 50, 80, 60], "isPartial": [False] * 4}, index=dates
    )


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


def test_default_rate_limit() -> None:
    adapter = GoogleTrendsAdapter()
    assert adapter.rate_limit_seconds == 2.0


def test_custom_rate_limit() -> None:
    adapter = GoogleTrendsAdapter(rate_limit_seconds=0.0)
    assert adapter.rate_limit_seconds == 0.0


# ---------------------------------------------------------------------------
# scan_sources
# ---------------------------------------------------------------------------


def test_scan_sources_empty_tickers_returns_empty() -> None:
    adapter = GoogleTrendsAdapter(rate_limit_seconds=0.0)
    result = adapter.scan_sources(SCAN_TIME, tickers=[])
    assert result == []


def test_scan_sources_none_tickers_returns_empty() -> None:
    adapter = GoogleTrendsAdapter(rate_limit_seconds=0.0)
    result = adapter.scan_sources(SCAN_TIME, tickers=None)
    assert result == []


def test_scan_sources_returns_buzz_signals() -> None:
    adapter = GoogleTrendsAdapter(rate_limit_seconds=0.0)
    mock_pytrends = MagicMock()
    mock_pytrends.interest_over_time.return_value = _make_trends_df(
        ["AAPL", "TSLA"], value=75
    )

    with patch.object(adapter, "_get_pytrends", return_value=mock_pytrends):
        results = adapter.scan_sources(SCAN_TIME, tickers=["AAPL", "TSLA"])

    assert len(results) == 2
    symbols = {s.ticker for s in results}
    assert symbols == {"AAPL", "TSLA"}


def test_scan_sources_buzz_signal_fields() -> None:
    adapter = GoogleTrendsAdapter(rate_limit_seconds=0.0)
    mock_pytrends = MagicMock()
    mock_pytrends.interest_over_time.return_value = _make_trends_df(["AAPL"], value=75)

    with patch.object(adapter, "_get_pytrends", return_value=mock_pytrends):
        results = adapter.scan_sources(SCAN_TIME, tickers=["AAPL"])

    assert len(results) == 1
    signal = results[0]
    assert isinstance(signal, BuzzSignal)
    assert signal.ticker == "AAPL"
    assert signal.source == "google_trends"
    assert signal.scorer == "google_trends"
    assert signal.mention_count == 75
    assert signal.fetched_at == SCAN_TIME
    assert len(signal.article_hash) == 32  # md5 hex


def test_scan_sources_sentiment_formula() -> None:
    """interest=75 → (75-50)/50 = 0.5."""
    adapter = GoogleTrendsAdapter(rate_limit_seconds=0.0)
    mock_pytrends = MagicMock()
    mock_pytrends.interest_over_time.return_value = _make_trends_df(["AAPL"], value=75)

    with patch.object(adapter, "_get_pytrends", return_value=mock_pytrends):
        results = adapter.scan_sources(SCAN_TIME, tickers=["AAPL"])

    assert abs(results[0].sentiment_raw - 0.5) < 1e-6


def test_scan_sources_interest_zero_clamps_to_minus_one() -> None:
    adapter = GoogleTrendsAdapter(rate_limit_seconds=0.0)
    mock_pytrends = MagicMock()
    mock_pytrends.interest_over_time.return_value = _make_trends_df(["AAPL"], value=0)

    with patch.object(adapter, "_get_pytrends", return_value=mock_pytrends):
        results = adapter.scan_sources(SCAN_TIME, tickers=["AAPL"])

    assert results[0].sentiment_raw == -1.0


def test_scan_sources_interest_100_clamps_to_one() -> None:
    adapter = GoogleTrendsAdapter(rate_limit_seconds=0.0)
    mock_pytrends = MagicMock()
    mock_pytrends.interest_over_time.return_value = _make_trends_df(["AAPL"], value=100)

    with patch.object(adapter, "_get_pytrends", return_value=mock_pytrends):
        results = adapter.scan_sources(SCAN_TIME, tickers=["AAPL"])

    assert results[0].sentiment_raw == 1.0


def test_scan_sources_batches_over_5() -> None:
    """6 tickers → 2 API calls (batch of 5 + batch of 1)."""
    adapter = GoogleTrendsAdapter(rate_limit_seconds=0.0)
    tickers = ["AAPL", "TSLA", "MSFT", "AMZN", "GOOG", "NVDA"]

    call_count = 0

    def fake_get_pytrends() -> MagicMock:
        nonlocal call_count
        call_count += 1
        mock = MagicMock()
        # Return appropriate columns depending on call
        if call_count == 1:
            mock.interest_over_time.return_value = _make_trends_df(
                ["AAPL", "TSLA", "MSFT", "AMZN", "GOOG"], value=50
            )
        else:
            mock.interest_over_time.return_value = _make_trends_df(["NVDA"], value=50)
        return mock

    with patch.object(adapter, "_get_pytrends", side_effect=fake_get_pytrends):
        results = adapter.scan_sources(SCAN_TIME, tickers=tickers)

    assert call_count == 2
    assert len(results) == 6


def test_scan_sources_api_exception_returns_empty() -> None:
    adapter = GoogleTrendsAdapter(rate_limit_seconds=0.0)
    mock_pytrends = MagicMock()
    mock_pytrends.interest_over_time.side_effect = RuntimeError("quota exceeded")

    with patch.object(adapter, "_get_pytrends", return_value=mock_pytrends):
        results = adapter.scan_sources(SCAN_TIME, tickers=["AAPL"])

    assert results == []


def test_scan_sources_empty_dataframe_skips_batch() -> None:
    adapter = GoogleTrendsAdapter(rate_limit_seconds=0.0)
    mock_pytrends = MagicMock()
    mock_pytrends.interest_over_time.return_value = pd.DataFrame()

    with patch.object(adapter, "_get_pytrends", return_value=mock_pytrends):
        results = adapter.scan_sources(SCAN_TIME, tickers=["AAPL"])

    assert results == []


# ---------------------------------------------------------------------------
# get_historical_interest
# ---------------------------------------------------------------------------


def test_get_historical_interest_returns_weekly_signals() -> None:
    adapter = GoogleTrendsAdapter(rate_limit_seconds=0.0)
    mock_pytrends = MagicMock()
    mock_pytrends.interest_over_time.return_value = _make_weekly_df("AAPL")

    with patch.object(adapter, "_get_pytrends", return_value=mock_pytrends):
        results = adapter.get_historical_interest("AAPL", START_DATE, END_DATE)

    assert len(results) == 4
    for sig in results:
        assert isinstance(sig, BuzzSignal)
        assert sig.ticker == "AAPL"
        assert sig.source == "google_trends"
        assert sig.scorer == "google_trends"


def test_get_historical_interest_sentiment_values() -> None:
    adapter = GoogleTrendsAdapter(rate_limit_seconds=0.0)
    mock_pytrends = MagicMock()
    mock_pytrends.interest_over_time.return_value = _make_weekly_df("TSLA")

    with patch.object(adapter, "_get_pytrends", return_value=mock_pytrends):
        results = adapter.get_historical_interest("TSLA", START_DATE, END_DATE)

    # interest values are [20, 50, 80, 60]
    # → (20-50)/50=-0.6, (50-50)/50=0, (80-50)/50=0.6, (60-50)/50=0.2
    expected = [-0.6, 0.0, 0.6, 0.2]
    for sig, exp in zip(results, expected):
        assert abs(sig.sentiment_raw - exp) < 1e-6


def test_get_historical_interest_unique_hashes() -> None:
    adapter = GoogleTrendsAdapter(rate_limit_seconds=0.0)
    mock_pytrends = MagicMock()
    mock_pytrends.interest_over_time.return_value = _make_weekly_df("AAPL")

    with patch.object(adapter, "_get_pytrends", return_value=mock_pytrends):
        results = adapter.get_historical_interest("AAPL", START_DATE, END_DATE)

    hashes = [s.article_hash for s in results]
    assert len(hashes) == len(set(hashes)), "article_hash must be unique per week"


def test_get_historical_interest_exception_returns_empty() -> None:
    adapter = GoogleTrendsAdapter(rate_limit_seconds=0.0)
    mock_pytrends = MagicMock()
    mock_pytrends.interest_over_time.side_effect = ConnectionError("timeout")

    with patch.object(adapter, "_get_pytrends", return_value=mock_pytrends):
        results = adapter.get_historical_interest("AAPL", START_DATE, END_DATE)

    assert results == []


def test_get_historical_interest_empty_df_returns_empty() -> None:
    adapter = GoogleTrendsAdapter(rate_limit_seconds=0.0)
    mock_pytrends = MagicMock()
    mock_pytrends.interest_over_time.return_value = pd.DataFrame()

    with patch.object(adapter, "_get_pytrends", return_value=mock_pytrends):
        results = adapter.get_historical_interest("AAPL", START_DATE, END_DATE)

    assert results == []


# ---------------------------------------------------------------------------
# get_buzz_signals
# ---------------------------------------------------------------------------


def test_get_buzz_signals_returns_empty() -> None:
    adapter = GoogleTrendsAdapter()
    result = adapter.get_buzz_signals(ticker="AAPL")
    assert result == []


# ---------------------------------------------------------------------------
# Patch at module level (TrendReq import path)
# ---------------------------------------------------------------------------


def test_scan_sources_patches_trendreq_at_module_level() -> None:
    """Verify patching pytrends.request.TrendReq prevents any real HTTP call."""
    adapter = GoogleTrendsAdapter(rate_limit_seconds=0.0)

    with patch(
        "adapters.data.google_trends_adapter.GoogleTrendsAdapter._get_pytrends"
    ) as mock_fn:
        mock_instance = MagicMock()
        mock_instance.interest_over_time.return_value = _make_trends_df(
            ["MSFT"], value=60
        )
        mock_fn.return_value = mock_instance

        results = adapter.scan_sources(SCAN_TIME, tickers=["MSFT"])

    assert len(results) == 1
    assert results[0].ticker == "MSFT"
