"""Tests for price_cache — batch yfinance price fetching with TTL cache."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from adapters.visualization.price_cache import (
    _batch_fetch_prices_impl,
    _fetch_index_prices_impl,
    _fetch_insider_transactions_impl,
    _fetch_ticker_info_impl,
    _is_market_hours,
)


class TestIsMarketHours:
    def test_returns_bool(self):
        result = _is_market_hours()
        assert isinstance(result, bool)


class TestBatchFetchPrices:
    def test_multi_ticker_fetch(self):
        """Multi-ticker yf.download returns MultiIndex columns."""
        # Build a MultiIndex DataFrame as yfinance does for multiple tickers
        arrays = [["Close", "Close"], ["AAPL", "MSFT"]]
        multi_idx = pd.MultiIndex.from_arrays(arrays, names=["Price", "Ticker"])
        data = pd.DataFrame(
            [[150.0, 300.0], [155.0, 305.0]],
            columns=multi_idx,
            index=pd.date_range("2026-01-01", periods=2),
        )

        with patch("adapters.visualization.price_cache.yf.download", return_value=data):
            result = _batch_fetch_prices_impl(("AAPL", "MSFT"))

        assert "AAPL" in result
        assert "MSFT" in result
        assert result["AAPL"]["price"] == pytest.approx(155.0)
        assert result["MSFT"]["price"] == pytest.approx(305.0)
        # change_pct = (last - prev) / prev * 100
        assert result["AAPL"]["change_pct"] == pytest.approx(
            (155.0 - 150.0) / 150.0 * 100
        )

    def test_single_ticker_fetch(self):
        """Single-ticker yf.download returns flat columns."""
        data = pd.DataFrame(
            {"Close": [200.0, 210.0]},
            index=pd.date_range("2026-01-01", periods=2),
        )

        with patch("adapters.visualization.price_cache.yf.download", return_value=data):
            result = _batch_fetch_prices_impl(("GOOG",))

        assert "GOOG" in result
        assert result["GOOG"]["price"] == pytest.approx(210.0)
        assert result["GOOG"]["change_pct"] == pytest.approx(
            (210.0 - 200.0) / 200.0 * 100
        )

    def test_single_ticker_multiindex_fetch(self):
        """Newer yfinance returns MultiIndex columns even for ONE ticker.

        Regression: float(close.iloc[-1]) crashed with 'not Series' because
        data["Close"] is a one-column DataFrame, not a flat Series.
        """
        arrays = [["Close"], ["NVDA"]]
        multi_idx = pd.MultiIndex.from_arrays(arrays, names=["Price", "Ticker"])
        data = pd.DataFrame(
            [[500.0], [510.0]],
            columns=multi_idx,
            index=pd.date_range("2026-01-01", periods=2),
        )

        with patch("adapters.visualization.price_cache.yf.download", return_value=data):
            result = _batch_fetch_prices_impl(("NVDA",))

        assert "NVDA" in result
        assert result["NVDA"]["price"] == pytest.approx(510.0)
        assert result["NVDA"]["change_pct"] == pytest.approx(
            (510.0 - 500.0) / 500.0 * 100
        )

    def test_empty_tickers_returns_empty_dict(self):
        with patch("adapters.visualization.price_cache.yf.download") as mock_dl:
            result = _batch_fetch_prices_impl(())
        assert result == {}
        mock_dl.assert_not_called()

    def test_download_failure_returns_empty_dict(self):
        with patch(
            "adapters.visualization.price_cache.yf.download",
            side_effect=Exception("network error"),
        ):
            result = _batch_fetch_prices_impl(("AAPL",))
        assert result == {}


class TestFetchTickerInfo:
    def test_returns_info_dict(self):
        mock_ticker = MagicMock()
        mock_ticker.info = {
            "symbol": "AAPL",
            "longName": "Apple Inc.",
            "sector": "Technology",
        }

        with patch(
            "adapters.visualization.price_cache.yf.Ticker", return_value=mock_ticker
        ):
            result = _fetch_ticker_info_impl("AAPL")

        assert result["symbol"] == "AAPL"
        assert result["longName"] == "Apple Inc."

    def test_returns_empty_on_failure(self):
        mock_ticker = MagicMock()
        mock_ticker.info = MagicMock(side_effect=Exception("API error"))

        with patch(
            "adapters.visualization.price_cache.yf.Ticker",
            side_effect=Exception("Ticker error"),
        ):
            result = _fetch_ticker_info_impl("BADINPUT")

        assert result == {}


class TestFetchInsiderTransactions:
    def test_returns_list_of_dicts_when_data_present(self):
        mock_ticker = MagicMock()
        mock_ticker.insider_transactions = pd.DataFrame(
            {
                "Shares": [1000, -500],
                "Value": [150000.0, -75000.0],
                "Transaction": ["Buy", "Sale"],
            }
        )

        with patch(
            "adapters.visualization.price_cache.yf.Ticker", return_value=mock_ticker
        ):
            result = _fetch_insider_transactions_impl("AAPL")

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["Shares"] == 1000

    def test_returns_empty_list_when_no_data(self):
        mock_ticker = MagicMock()
        mock_ticker.insider_transactions = None

        with patch(
            "adapters.visualization.price_cache.yf.Ticker", return_value=mock_ticker
        ):
            result = _fetch_insider_transactions_impl("AAPL")

        assert result == []

    def test_returns_empty_list_on_exception(self):
        with patch(
            "adapters.visualization.price_cache.yf.Ticker",
            side_effect=Exception("API error"),
        ):
            result = _fetch_insider_transactions_impl("AAPL")

        assert result == []


class TestFetchIndexPrices:
    def test_returns_index_prices(self):
        arrays = [["Close", "Close", "Close", "Close"], ["SPY", "QQQ", "DIA", "IWM"]]
        multi_idx = pd.MultiIndex.from_arrays(arrays, names=["Price", "Ticker"])
        data = pd.DataFrame(
            [[400.0, 350.0, 340.0, 200.0], [405.0, 355.0, 345.0, 202.0]],
            columns=multi_idx,
            index=pd.date_range("2026-01-01", periods=2),
        )

        with patch("adapters.visualization.price_cache.yf.download", return_value=data):
            result = _fetch_index_prices_impl()

        assert "SPY" in result
        assert "QQQ" in result
        assert result["SPY"]["price"] == pytest.approx(405.0)
