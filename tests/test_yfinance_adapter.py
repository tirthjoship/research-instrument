"""Tests for yfinance adapter and caching."""
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from adapters.data.cache_mixin import CachingMixin
from adapters.data.yfinance_adapter import YFinanceAdapter
from domain.models import Signal


# ── CachingMixin tests ──────────────────────────────────────────────


class ConcreteCache(CachingMixin):
    def __init__(self, cache_dir: Path) -> None:
        super().__init__(cache_dir)


def test_cache_save_and_load(tmp_path: Path) -> None:
    cache = ConcreteCache(tmp_path)
    cache.save_to_cache("AAPL", {"price": 150.0, "volume": 1000000})
    loaded = cache.load_from_cache("AAPL")
    assert loaded is not None
    assert loaded["price"] == 150.0


def test_cache_load_nonexistent_returns_none(tmp_path: Path) -> None:
    cache = ConcreteCache(tmp_path)
    assert cache.load_from_cache("MISSING") is None


def test_cache_append_only(tmp_path: Path) -> None:
    cache = ConcreteCache(tmp_path)
    cache.save_to_cache("AAPL", {"price": 150.0})
    cache.save_to_cache("AAPL", {"price": 155.0})
    loaded = cache.load_from_cache("AAPL")
    assert loaded is not None
    assert loaded["price"] == 155.0


def test_cache_creates_symbol_directory(tmp_path: Path) -> None:
    cache = ConcreteCache(tmp_path)
    cache.save_to_cache("GOOG", {"price": 2800.0})
    assert (tmp_path / "GOOG").is_dir()


# ── YFinanceAdapter tests (mocked) ─────────────────────────────────


@pytest.fixture
def adapter(tmp_path: Path) -> YFinanceAdapter:
    return YFinanceAdapter(cache_dir=tmp_path, use_cache=False)


@pytest.fixture
def mock_ticker() -> MagicMock:
    ticker = MagicMock()
    dates = pd.date_range("2026-01-01", periods=30, freq="B")
    np.random.seed(42)
    prices = 150.0 + np.cumsum(np.random.randn(30) * 2)
    df = pd.DataFrame(
        {
            "Open": prices - 1,
            "High": prices + 2,
            "Low": prices - 2,
            "Close": prices,
            "Volume": np.random.randint(1_000_000, 10_000_000, 30),
        },
        index=dates,
    )
    ticker.history.return_value = df
    ticker.info = {
        "marketCap": 2_500_000_000_000,
        "trailingPE": 28.5,
        "revenueGrowth": 0.08,
        "heldPercentInstitutions": 0.72,
        "shortRatio": 1.5,
        "shortPercentOfFloat": 0.012,
        "sector": "Technology",
    }
    return ticker


@patch("adapters.data.yfinance_adapter.yf.Ticker")
def test_get_signals_returns_signals(
    mock_yf: MagicMock,
    mock_ticker: MagicMock,
    adapter: YFinanceAdapter,
) -> None:
    mock_yf.return_value = mock_ticker
    signals = adapter.get_signals(
        "AAPL", datetime(2026, 2, 15), start_date=datetime(2026, 1, 1)
    )
    assert len(signals) > 0
    assert all(isinstance(s, Signal) for s in signals)
    assert all(s.timestamp <= datetime(2026, 2, 15) for s in signals)


@patch("adapters.data.yfinance_adapter.yf.Ticker")
def test_get_ticker_info(
    mock_yf: MagicMock,
    mock_ticker: MagicMock,
    adapter: YFinanceAdapter,
) -> None:
    mock_yf.return_value = mock_ticker
    info = adapter.get_ticker_info("AAPL")
    assert "market_cap" in info
    assert info["market_cap"] == 2_500_000_000_000


@patch("adapters.data.yfinance_adapter.yf.Ticker")
def test_compute_indicators(
    mock_yf: MagicMock,
    mock_ticker: MagicMock,
    adapter: YFinanceAdapter,
) -> None:
    mock_yf.return_value = mock_ticker
    signals = adapter.get_signals(
        "AAPL", datetime(2026, 2, 15), start_date=datetime(2026, 1, 1)
    )
    indicators = adapter.compute_indicators(signals)
    assert "rsi_14" in indicators
    assert 0.0 <= indicators["rsi_14"] <= 100.0
    assert "macd" in indicators
