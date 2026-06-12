"""Tests for ticker universe loader."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from application.ticker_universe import load_ticker_universe


def test_load_deduplicates_across_files() -> None:
    """Tickers appearing in both files are deduplicated."""
    with TemporaryDirectory() as tmpdir:
        sp500 = Path(tmpdir) / "sp500.txt"
        nasdaq = Path(tmpdir) / "nasdaq100.txt"
        sp500.write_text("AAPL\nMSFT\nGOOG\n")
        nasdaq.write_text("AAPL\nTSLA\nNVDA\n")

        result = load_ticker_universe([sp500, nasdaq])

        assert len(result) == 5
        assert set(result) == {"AAPL", "MSFT", "GOOG", "TSLA", "NVDA"}


def test_load_strips_whitespace_and_skips_comments() -> None:
    """Lines with # prefix or empty lines are skipped."""
    with TemporaryDirectory() as tmpdir:
        f = Path(tmpdir) / "tickers.txt"
        f.write_text("# S&P 500 tickers\nAAPL\n  MSFT  \n\n# end\n")

        result = load_ticker_universe([f])

        assert result == ["AAPL", "MSFT"]


def test_load_returns_sorted() -> None:
    """Universe is alphabetically sorted for deterministic ordering."""
    with TemporaryDirectory() as tmpdir:
        f = Path(tmpdir) / "tickers.txt"
        f.write_text("TSLA\nAAPL\nMSFT\n")

        result = load_ticker_universe([f])

        assert result == ["AAPL", "MSFT", "TSLA"]
