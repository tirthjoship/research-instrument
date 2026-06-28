"""Tests for the ticker->CIK resolver. No live SEC calls (project rule #5)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

from adapters.data.sec_cik_resolver import SECCikResolver

# Shape of the real SEC company_tickers.json: index -> {cik_str, ticker, title}.
_RAW = {
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    "1": {"cik_str": 1045810, "ticker": "NVDA", "title": "NVIDIA Corp"},
    "2": {"cik_str": 1067983, "ticker": "BRK-B", "title": "Berkshire Hathaway B"},
}


def _mock_response(json_data: object) -> MagicMock:
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = json_data
    mock.raise_for_status.return_value = None
    return mock


def test_resolves_known_ticker_case_insensitively() -> None:
    r = SECCikResolver(rate_limit_seconds=0.0)
    with patch("requests.get", return_value=_mock_response(_RAW)):
        assert r.resolve("AAPL") == 320193
        assert r.resolve("nvda") == 1045810  # case-insensitive, served from memory


def test_unknown_ticker_returns_none() -> None:
    r = SECCikResolver(rate_limit_seconds=0.0)
    with patch("requests.get", return_value=_mock_response(_RAW)):
        assert r.resolve("ZZZZ") is None


def test_class_share_dot_and_dash_both_resolve() -> None:
    r = SECCikResolver(rate_limit_seconds=0.0)
    with patch("requests.get", return_value=_mock_response(_RAW)):
        assert r.resolve("BRK-B") == 1067983
        assert r.resolve("BRK.B") == 1067983  # '.'-normalised alias


def test_map_is_fetched_once_then_served_from_memory() -> None:
    r = SECCikResolver(rate_limit_seconds=0.0)
    with patch("requests.get", return_value=_mock_response(_RAW)) as g:
        r.resolve("AAPL")
        r.resolve("NVDA")
        r.resolve("AAPL")
    assert g.call_count == 1  # single network fetch, lazily cached in memory


def test_fetch_failure_returns_none_not_error() -> None:
    r = SECCikResolver(rate_limit_seconds=0.0)
    with patch("requests.get", side_effect=requests.ConnectionError("boom")):
        assert r.resolve("AAPL") is None


def test_disk_cache_written_then_reused_without_refetch(tmp_path: Path) -> None:
    cache = tmp_path / "sub" / "company_tickers.json"
    # First resolver fetches and writes the cache.
    r1 = SECCikResolver(rate_limit_seconds=0.0, cache_path=cache)
    with patch("requests.get", return_value=_mock_response(_RAW)) as g1:
        assert r1.resolve("AAPL") == 320193
    assert g1.call_count == 1
    assert cache.exists()
    assert json.loads(cache.read_text())["0"]["ticker"] == "AAPL"

    # Second resolver reads the cache and never hits the network.
    r2 = SECCikResolver(rate_limit_seconds=0.0, cache_path=cache)
    with patch("requests.get", side_effect=AssertionError("should not refetch")) as g2:
        assert r2.resolve("NVDA") == 1045810
    assert g2.call_count == 0


def test_corrupt_disk_cache_falls_back_to_refetch(tmp_path: Path) -> None:
    cache = tmp_path / "company_tickers.json"
    cache.write_text("{ not valid json")
    r = SECCikResolver(rate_limit_seconds=0.0, cache_path=cache)
    with patch("requests.get", return_value=_mock_response(_RAW)) as g:
        assert r.resolve("AAPL") == 320193
    assert g.call_count == 1  # corrupt cache → refetched
