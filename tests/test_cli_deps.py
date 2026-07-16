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
    # tsx60.txt has 52 real, dated tickers stored bare on disk -- .TO is
    # applied here (_apply_yf_market_suffix) so the LIVE screen-candidates
    # path resolves the same real yfinance symbols as the offline backtest
    # path (_get_backtest_universe) does. A bare "RY" would previously
    # silently mis-resolve or fail against yfinance (RY.TO is Royal Bank
    # of Canada; bare RY happens to also exist as an NYSE cross-listing for
    # a few names, which is exactly what made this bug easy to miss).
    assert "RY.TO" in tickers
    assert "RY" not in tickers
    assert len(tickers) == 52


def test_in_market_config_loads_and_uses_nifty50():
    from config.loader import load_market_config

    config = load_market_config("in")
    assert config["market"] == "in"

    tickers = _get_ticker_universe(config)
    # nifty50.txt has 50 real, dated (2025-12-08) tickers stored bare on
    # disk -- .NS is applied here so these resolve against yfinance at all
    # (a bare "RELIANCE" is not a valid yfinance symbol and fails outright).
    assert "RELIANCE.NS" in tickers
    assert "TCS.NS" in tickers
    assert "RELIANCE" not in tickers
    assert len(tickers) == 50


def test_get_backtest_universe_us_excludes_tsx60_and_nifty():
    from application.cli._deps import _get_backtest_universe

    us_tickers = _get_backtest_universe("us")
    # RY (Royal Bank of Canada) and RELIANCE.NS are real entries in the
    # other markets' files and NOT US sp500/nasdaq100 constituents —
    # today's bug includes CA in "us" anyway (India wasn't even wired yet).
    assert "RY.TO" not in us_tickers
    assert "RELIANCE.NS" not in us_tickers


def test_get_backtest_universe_ca_returns_tsx60_with_to_suffix():
    from application.cli._deps import _get_backtest_universe

    ca_tickers = _get_backtest_universe("ca")
    assert "RY.TO" in ca_tickers
    assert len(ca_tickers) == 52
    # Must NOT silently include the full US universe too.
    assert "AAPL" not in ca_tickers


def test_get_backtest_universe_in_returns_nifty50_with_ns_suffix():
    from application.cli._deps import _get_backtest_universe

    in_tickers = _get_backtest_universe("in")
    assert "RELIANCE.NS" in in_tickers
    assert "TCS.NS" in in_tickers
    assert len(in_tickers) == 50
    assert "AAPL" not in in_tickers


def test_ca_class_shares_use_dash_before_to_suffix():
    """tsx60.txt stores class shares with dotted notation (GIB.A) -- yfinance
    wants dash + suffix (GIB-A.TO), mirroring holdings_reader._to_yf. Must
    hold for BOTH universe-loading paths, not just the offline backtest one."""
    from application.cli._deps import _get_backtest_universe

    ca_tickers = _get_backtest_universe("ca")
    assert "GIB-A.TO" in ca_tickers
    assert "GIB.A" not in ca_tickers
    assert "GIB.A.TO" not in ca_tickers


def test_live_and_backtest_universes_match_for_ca_and_in():
    """The live screen-candidates path (_get_ticker_universe) and the offline
    backtest path (_get_backtest_universe) must resolve to the EXACT same
    yfinance-suffixed ticker set for a given market -- this is the invariant
    that broke silently before (_get_ticker_universe returned bare tickers
    while _get_backtest_universe correctly suffixed them), producing wrong/
    missing live-scan data for CA and India while backtests looked fine."""
    from application.cli._deps import _get_backtest_universe
    from config.loader import load_market_config

    for market in ("ca", "in"):
        config = load_market_config(market)
        live = sorted(_get_ticker_universe(config))
        backtest = sorted(_get_backtest_universe(market))
        assert live == backtest, f"{market}: live/backtest universe mismatch"
