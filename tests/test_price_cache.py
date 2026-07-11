"""Tests for price_cache — batch yfinance price fetching with TTL cache."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from adapters.visualization.price_cache import (
    _batch_fetch_closes_impl,
    _batch_fetch_prices_impl,
    _fetch_index_prices_impl,
    _fetch_insider_transactions_impl,
    _fetch_ticker_info_impl,
    _is_market_hours,
    parse_price_history,
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


class TestBatchFetchCloses:
    def test_multi_ticker_returns_full_close_series(self):
        arrays = [["Close", "Close"], ["AAPL", "MSFT"]]
        multi_idx = pd.MultiIndex.from_arrays(arrays, names=["Price", "Ticker"])
        data = pd.DataFrame(
            [[150.0, 300.0], [155.0, 305.0], [160.0, 310.0]],
            columns=multi_idx,
            index=pd.date_range("2026-01-01", periods=3),
        )

        with patch("adapters.visualization.price_cache.yf.download", return_value=data):
            result = _batch_fetch_closes_impl(("AAPL", "MSFT"))

        assert result["AAPL"] == pytest.approx([150.0, 155.0, 160.0])
        assert result["MSFT"] == pytest.approx([300.0, 305.0, 310.0])

    def test_single_ticker_flat_columns(self):
        data = pd.DataFrame(
            {"Close": [200.0, 210.0, 220.0]},
            index=pd.date_range("2026-01-01", periods=3),
        )

        with patch("adapters.visualization.price_cache.yf.download", return_value=data):
            result = _batch_fetch_closes_impl(("GOOG",))

        assert result["GOOG"] == pytest.approx([200.0, 210.0, 220.0])

    def test_single_ticker_multiindex(self):
        arrays = [["Close"], ["NVDA"]]
        multi_idx = pd.MultiIndex.from_arrays(arrays, names=["Price", "Ticker"])
        data = pd.DataFrame(
            [[500.0], [510.0], [520.0]],
            columns=multi_idx,
            index=pd.date_range("2026-01-01", periods=3),
        )

        with patch("adapters.visualization.price_cache.yf.download", return_value=data):
            result = _batch_fetch_closes_impl(("NVDA",))

        assert result["NVDA"] == pytest.approx([500.0, 510.0, 520.0])

    def test_empty_tickers_returns_empty_dict(self):
        with patch("adapters.visualization.price_cache.yf.download") as mock_dl:
            result = _batch_fetch_closes_impl(())
        assert result == {}
        mock_dl.assert_not_called()

    def test_download_failure_returns_empty_dict(self):
        with patch(
            "adapters.visualization.price_cache.yf.download",
            side_effect=Exception("network error"),
        ):
            result = _batch_fetch_closes_impl(("AAPL",))
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


class TestParsePriceHistory:
    """Pure parser tests — no network, no yfinance calls."""

    def _make_df(self, n: int = 252, include_hl: bool = True) -> pd.DataFrame:
        """Build a fake daily OHLC DataFrame with n rows."""
        closes = [100.0 + i * 0.1 for i in range(n)]
        data: dict[str, list[float]] = {"Close": closes}
        if include_hl:
            data["High"] = [c + 2.0 for c in closes]
            data["Low"] = [c - 2.0 for c in closes]
        return pd.DataFrame(
            data, index=pd.date_range("2025-06-01", periods=n, freq="B")
        )

    def test_closes_length_matches_input(self) -> None:
        df = self._make_df(252)
        result = parse_price_history(df)
        assert result is not None
        assert len(result["closes"]) == 252

    def test_ma200_is_mean_of_last_200(self) -> None:
        df = self._make_df(252)
        result = parse_price_history(df)
        assert result is not None
        closes = result["closes"]
        expected_ma200 = sum(closes[-200:]) / 200
        assert result["ma200"] == pytest.approx(expected_ma200, rel=1e-6)

    def test_ma200_uses_all_when_fewer_than_200_rows(self) -> None:
        df = self._make_df(50)
        result = parse_price_history(df)
        assert result is not None
        expected_ma200 = sum(result["closes"]) / 50
        assert result["ma200"] == pytest.approx(expected_ma200, rel=1e-6)

    def test_atr_computed_from_high_low(self) -> None:
        df = self._make_df(252, include_hl=True)
        result = parse_price_history(df)
        assert result is not None
        # High-Low difference is always 4.0 (each row: high=c+2, low=c-2)
        assert result["atr"] == pytest.approx(4.0, rel=1e-6)

    def test_atr_falls_back_to_abs_diff_without_high_low(self) -> None:
        df = self._make_df(252, include_hl=False)
        result = parse_price_history(df)
        assert result is not None
        # closes are 100, 100.1, 100.2 ... → each daily diff = 0.1
        assert result["atr"] == pytest.approx(0.1, rel=1e-3)

    def test_vs_spy_is_none(self) -> None:
        df = self._make_df(30)
        result = parse_price_history(df)
        assert result is not None
        assert result["vs_spy"] is None

    def test_none_df_returns_none(self) -> None:
        assert parse_price_history(None) is None

    def test_empty_df_returns_none(self) -> None:
        assert parse_price_history(pd.DataFrame()) is None

    def test_df_missing_close_returns_none(self) -> None:
        df = pd.DataFrame({"High": [100.0], "Low": [99.0]})
        assert parse_price_history(df) is None


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


class TestYfinanceNews:
    def test_parse_nested_content_shape(self):
        from adapters.visualization.price_cache import _parse_yfinance_news_item

        item = {
            "content": {
                "title": "Chip demand stays hot",
                "pubDate": "2026-06-27T12:00:00Z",
                "provider": {"displayName": "Yahoo Finance"},
                "clickThroughUrl": {
                    "url": "https://finance.yahoo.com/news/chip-demand.html",
                },
            }
        }
        parsed = _parse_yfinance_news_item(item)
        assert parsed == {
            "source": "Yahoo Finance",
            "title": "Chip demand stays hot",
            "date": "2026-06-27T12:00:00Z",
            "url": "https://finance.yahoo.com/news/chip-demand.html",
        }

    def test_parse_flat_legacy_shape(self):
        from adapters.visualization.price_cache import _parse_yfinance_news_item

        item = {
            "title": "Legacy headline",
            "providerPublishTime": 1719504000,
            "publisher": "Reuters",
        }
        parsed = _parse_yfinance_news_item(item)
        assert parsed is not None
        assert parsed["source"] == "Reuters"
        assert parsed["title"] == "Legacy headline"

    def test_fetch_recent_news_impl(self):
        from adapters.visualization.price_cache import _fetch_recent_news_impl

        mock_ticker = MagicMock()
        mock_ticker.news = [
            {
                "content": {
                    "title": "One",
                    "pubDate": "2026-06-27",
                    "provider": {"displayName": "Yahoo Finance"},
                }
            },
            {"content": {"title": "", "pubDate": "2026-06-26"}},
        ]
        with patch(
            "adapters.visualization.price_cache.yf.Ticker", return_value=mock_ticker
        ):
            out = _fetch_recent_news_impl("NVDA", limit=5)
        assert len(out) == 1
        assert out[0]["title"] == "One"
