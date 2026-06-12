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


KNOWN_DELISTED = {"SIVB", "PXD", "SPLK", "WBA"}


def test_universe_files_contain_no_known_delisted_or_foreign_suffix() -> None:
    """Guard: known-delisted and foreign-suffix tickers must not appear in production universe files."""
    config_dir = Path(__file__).parent.parent / "config" / "tickers"
    universe = load_ticker_universe(
        [config_dir / "sp500.txt", config_dir / "nasdaq100.txt"]
    )
    stale = KNOWN_DELISTED & set(universe)
    assert not stale, f"delisted tickers still in universe files: {sorted(stale)}"
    foreign = [t for t in universe if t.endswith(".TO") or t.endswith(".V")]
    assert not foreign, f"foreign-suffix artifacts in US universe: {foreign}"
