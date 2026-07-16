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
