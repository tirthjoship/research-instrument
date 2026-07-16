"""Tests for application/cli/_deps.py universe-selection helpers."""

from __future__ import annotations

from application.cli._deps import _get_ticker_universe


def test_get_ticker_universe_reads_files_from_config(tmp_path, monkeypatch):
    # Two tiny ticker files standing in for real sp500/nasdaq100 files.
    f1 = tmp_path / "a.txt"
    f1.write_text("AAA\nBBB\n")
    f2 = tmp_path / "b.txt"
    f2.write_text("BBB\nCCC\n")  # BBB duplicated on purpose — must dedupe

    config = {"universe": {"ticker_files": [str(f1), str(f2)]}}
    result = _get_ticker_universe(config)

    assert result == ["AAA", "BBB", "CCC"]


def test_get_ticker_universe_missing_universe_key_falls_back_to_us_files():
    """A config dict with no 'universe' key (shouldn't happen with a real
    market yaml, but defends against a malformed one) falls back to the
    existing hardcoded US sp500+nasdaq100 file paths."""
    result = _get_ticker_universe({})
    assert "AAPL" in result or len(result) > 100  # real sp500+nasdaq100 files exist


def test_ca_market_config_loads_and_uses_tsx60():
    from config.loader import load_market_config

    config = load_market_config("ca")
    assert config["market"] == "ca"

    tickers = _get_ticker_universe(config)
    # tsx60.txt has 52 real, dated tickers (no .TO suffix stored on disk —
    # the .TO suffix is added at runtime by _get_backtest_universe, not here).
    assert "RY" in tickers  # Royal Bank of Canada, first real entry in the file
    assert len(tickers) == 52


def test_in_market_config_loads_and_uses_nifty50():
    from config.loader import load_market_config

    config = load_market_config("in")
    assert config["market"] == "in"

    tickers = _get_ticker_universe(config)
    # nifty50.txt has 50 real, dated (2025-12-08) tickers — see the file's
    # own header for sourcing and open caveats before trusting it further.
    assert "RELIANCE" in tickers
    assert "TCS" in tickers
    assert len(tickers) == 50
