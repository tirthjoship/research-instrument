"""Tests for expanded yfinance field_map — Phase 4A fundamental fields."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from adapters.data.yfinance_adapter import YFinanceAdapter


def test_get_ticker_info_includes_peg_ratio() -> None:
    """pegRatio mapped to peg_ratio."""
    mock_info = {"pegRatio": 1.5}
    with patch("adapters.data.yfinance_adapter.yf") as mock_yf:
        mock_ticker = MagicMock()
        mock_ticker.info = mock_info
        mock_yf.Ticker.return_value = mock_ticker
        with TemporaryDirectory() as tmpdir:
            adapter = YFinanceAdapter(cache_dir=Path(tmpdir))
            result = adapter.get_ticker_info("AAPL")
    assert result["peg_ratio"] == 1.5


def test_get_ticker_info_includes_free_cashflow() -> None:
    """freeCashflow mapped to free_cashflow."""
    mock_info = {"freeCashflow": 50_000_000_000}
    with patch("adapters.data.yfinance_adapter.yf") as mock_yf:
        mock_ticker = MagicMock()
        mock_ticker.info = mock_info
        mock_yf.Ticker.return_value = mock_ticker
        with TemporaryDirectory() as tmpdir:
            adapter = YFinanceAdapter(cache_dir=Path(tmpdir))
            result = adapter.get_ticker_info("AAPL")
    assert result["free_cashflow"] == 50_000_000_000


def test_get_ticker_info_includes_gross_margins() -> None:
    """grossMargins mapped to gross_margins."""
    mock_info = {"grossMargins": 0.45}
    with patch("adapters.data.yfinance_adapter.yf") as mock_yf:
        mock_ticker = MagicMock()
        mock_ticker.info = mock_info
        mock_yf.Ticker.return_value = mock_ticker
        with TemporaryDirectory() as tmpdir:
            adapter = YFinanceAdapter(cache_dir=Path(tmpdir))
            result = adapter.get_ticker_info("AAPL")
    assert result["gross_margins"] == 0.45


def test_get_ticker_info_includes_operating_margins() -> None:
    """operatingMargins mapped to operating_margins."""
    mock_info = {"operatingMargins": 0.30}
    with patch("adapters.data.yfinance_adapter.yf") as mock_yf:
        mock_ticker = MagicMock()
        mock_ticker.info = mock_info
        mock_yf.Ticker.return_value = mock_ticker
        with TemporaryDirectory() as tmpdir:
            adapter = YFinanceAdapter(cache_dir=Path(tmpdir))
            result = adapter.get_ticker_info("AAPL")
    assert result["operating_margins"] == 0.30


def test_get_ticker_info_all_fundamental_fields_present() -> None:
    """All Phase 4A fields present when yfinance provides them."""
    mock_info = {
        "pegRatio": 1.5,
        "freeCashflow": 50e9,
        "grossMargins": 0.45,
        "operatingMargins": 0.30,
        "marketCap": 3e12,
        "trailingPE": 28.5,
        "priceToBook": 45.0,
        "debtToEquity": 150.0,
        "currentRatio": 1.1,
        "dividendYield": 0.005,
        "revenueGrowth": 0.08,
        "heldPercentInstitutions": 0.60,
    }
    with patch("adapters.data.yfinance_adapter.yf") as mock_yf:
        mock_ticker = MagicMock()
        mock_ticker.info = mock_info
        mock_yf.Ticker.return_value = mock_ticker
        with TemporaryDirectory() as tmpdir:
            adapter = YFinanceAdapter(cache_dir=Path(tmpdir))
            result = adapter.get_ticker_info("AAPL")

    required = [
        "peg_ratio",
        "free_cashflow",
        "gross_margins",
        "operating_margins",
        "market_cap",
        "trailing_pe",
        "price_to_book",
        "debt_to_equity",
        "current_ratio",
        "dividend_yield",
        "revenue_growth",
        "institutional_ownership",
    ]
    for field in required:
        assert field in result, f"Missing: {field}"
