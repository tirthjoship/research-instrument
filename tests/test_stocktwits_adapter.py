"""Tests for StockTwitsAdapter — never hits the real StockTwits API."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import requests

from adapters.data.stocktwits_adapter import StockTwitsAdapter
from domain.models import BuzzSignal

SCAN_TIME = datetime(2026, 6, 1, 9, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(messages: list[dict], status_code: int = 200) -> MagicMock:
    """Build a mock requests.Response."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = {"messages": messages}
    if status_code >= 400:
        http_err = requests.HTTPError(response=mock_resp)
        mock_resp.raise_for_status.side_effect = http_err
    else:
        mock_resp.raise_for_status.return_value = None
    return mock_resp


def _bullish_msg() -> dict:
    return {"id": 1, "body": "Going up!", "sentiment": {"basic": "Bullish"}}


def _bearish_msg() -> dict:
    return {"id": 2, "body": "Selling now", "sentiment": {"basic": "Bearish"}}


def _untagged_msg() -> dict:
    return {"id": 3, "body": "Watching closely", "sentiment": None}


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


def test_default_rate_limit() -> None:
    adapter = StockTwitsAdapter()
    assert adapter.rate_limit_seconds == 1.8


def test_custom_rate_limit() -> None:
    adapter = StockTwitsAdapter(rate_limit_seconds=0.0)
    assert adapter.rate_limit_seconds == 0.0


# ---------------------------------------------------------------------------
# scan_sources — basic cases
# ---------------------------------------------------------------------------


def test_empty_tickers_returns_empty() -> None:
    adapter = StockTwitsAdapter(rate_limit_seconds=0.0)
    assert adapter.scan_sources(SCAN_TIME, tickers=[]) == []


def test_none_tickers_returns_empty() -> None:
    adapter = StockTwitsAdapter(rate_limit_seconds=0.0)
    assert adapter.scan_sources(SCAN_TIME, tickers=None) == []


# ---------------------------------------------------------------------------
# scan_sources — bullish/bearish ratio
# ---------------------------------------------------------------------------


def test_bullish_bearish_ratio_two_bullish_one_bearish() -> None:
    """2 bullish + 1 bearish → (2-1)/3 ≈ 0.333."""
    adapter = StockTwitsAdapter(rate_limit_seconds=0.0)
    messages = [_bullish_msg(), _bullish_msg(), _bearish_msg()]
    mock_resp = _make_response(messages)

    with patch("requests.get", return_value=mock_resp):
        results = adapter.scan_sources(SCAN_TIME, tickers=["AAPL"])

    assert len(results) == 1
    signal = results[0]
    assert abs(signal.sentiment_raw - (1 / 3)) < 1e-6


def test_all_bullish_sentiment_is_one() -> None:
    adapter = StockTwitsAdapter(rate_limit_seconds=0.0)
    messages = [_bullish_msg(), _bullish_msg()]
    mock_resp = _make_response(messages)

    with patch("requests.get", return_value=mock_resp):
        results = adapter.scan_sources(SCAN_TIME, tickers=["TSLA"])

    assert results[0].sentiment_raw == 1.0


def test_all_bearish_sentiment_is_minus_one() -> None:
    adapter = StockTwitsAdapter(rate_limit_seconds=0.0)
    messages = [_bearish_msg(), _bearish_msg(), _bearish_msg()]
    mock_resp = _make_response(messages)

    with patch("requests.get", return_value=mock_resp):
        results = adapter.scan_sources(SCAN_TIME, tickers=["MSFT"])

    assert results[0].sentiment_raw == -1.0


def test_no_tagged_messages_sentiment_is_zero() -> None:
    """Messages with no sentiment tag → sentiment_raw = 0.0."""
    adapter = StockTwitsAdapter(rate_limit_seconds=0.0)
    messages = [_untagged_msg(), _untagged_msg()]
    mock_resp = _make_response(messages)

    with patch("requests.get", return_value=mock_resp):
        results = adapter.scan_sources(SCAN_TIME, tickers=["GOOG"])

    assert results[0].sentiment_raw == 0.0


def test_empty_messages_list_sentiment_is_zero() -> None:
    adapter = StockTwitsAdapter(rate_limit_seconds=0.0)
    mock_resp = _make_response([])

    with patch("requests.get", return_value=mock_resp):
        results = adapter.scan_sources(SCAN_TIME, tickers=["NVDA"])

    assert len(results) == 1
    assert results[0].sentiment_raw == 0.0
    assert results[0].mention_count == 0


# ---------------------------------------------------------------------------
# scan_sources — BuzzSignal fields
# ---------------------------------------------------------------------------


def test_buzz_signal_fields_are_correct() -> None:
    adapter = StockTwitsAdapter(rate_limit_seconds=0.0)
    messages = [_bullish_msg(), _untagged_msg()]
    mock_resp = _make_response(messages)

    with patch("requests.get", return_value=mock_resp):
        results = adapter.scan_sources(SCAN_TIME, tickers=["AAPL"])

    assert len(results) == 1
    signal = results[0]
    assert isinstance(signal, BuzzSignal)
    assert signal.ticker == "AAPL"
    assert signal.source == "stocktwits"
    assert signal.scorer == "stocktwits"
    assert signal.mention_count == 2
    assert signal.fetched_at == SCAN_TIME
    assert len(signal.article_hash) == 32  # md5 hex


def test_article_hash_uses_ticker_and_scan_time() -> None:
    import hashlib

    adapter = StockTwitsAdapter(rate_limit_seconds=0.0)
    mock_resp = _make_response([_bullish_msg()])

    with patch("requests.get", return_value=mock_resp):
        results = adapter.scan_sources(SCAN_TIME, tickers=["AAPL"])

    expected = hashlib.md5(
        f"stocktwits_AAPL_{SCAN_TIME.isoformat()}".encode()
    ).hexdigest()
    assert results[0].article_hash == expected


def test_different_tickers_produce_different_hashes() -> None:
    adapter = StockTwitsAdapter(rate_limit_seconds=0.0)
    mock_resp = _make_response([_bullish_msg()])

    with patch("requests.get", return_value=mock_resp):
        results = adapter.scan_sources(SCAN_TIME, tickers=["AAPL", "TSLA"])

    hashes = [s.article_hash for s in results]
    assert len(set(hashes)) == 2


# ---------------------------------------------------------------------------
# scan_sources — error handling
# ---------------------------------------------------------------------------


def test_429_error_skips_ticker_returns_empty() -> None:
    """Rate-limit response from StockTwits → log warning, skip ticker."""
    adapter = StockTwitsAdapter(rate_limit_seconds=0.0)
    mock_resp = _make_response([], status_code=429)

    with patch("requests.get", return_value=mock_resp):
        results = adapter.scan_sources(SCAN_TIME, tickers=["AAPL"])

    assert results == []


def test_500_error_skips_ticker_returns_empty() -> None:
    adapter = StockTwitsAdapter(rate_limit_seconds=0.0)
    mock_resp = _make_response([], status_code=500)

    with patch("requests.get", return_value=mock_resp):
        results = adapter.scan_sources(SCAN_TIME, tickers=["TSLA"])

    assert results == []


def test_connection_error_skips_ticker_returns_empty() -> None:
    adapter = StockTwitsAdapter(rate_limit_seconds=0.0)

    with patch("requests.get", side_effect=ConnectionError("timeout")):
        results = adapter.scan_sources(SCAN_TIME, tickers=["MSFT"])

    assert results == []


def test_error_on_one_ticker_does_not_block_others() -> None:
    """First ticker fails with 429, second succeeds — only second in result."""
    adapter = StockTwitsAdapter(rate_limit_seconds=0.0)
    bad_resp = _make_response([], status_code=429)
    good_resp = _make_response([_bullish_msg()])

    with patch("requests.get", side_effect=[bad_resp, good_resp]):
        results = adapter.scan_sources(SCAN_TIME, tickers=["FAIL", "AAPL"])

    assert len(results) == 1
    assert results[0].ticker == "AAPL"


# ---------------------------------------------------------------------------
# scan_sources — multiple tickers
# ---------------------------------------------------------------------------


def test_multiple_tickers_return_one_signal_each() -> None:
    adapter = StockTwitsAdapter(rate_limit_seconds=0.0)
    mock_resp = _make_response([_bullish_msg()])

    with patch("requests.get", return_value=mock_resp):
        results = adapter.scan_sources(SCAN_TIME, tickers=["AAPL", "TSLA", "MSFT"])

    assert len(results) == 3
    tickers = {s.ticker for s in results}
    assert tickers == {"AAPL", "TSLA", "MSFT"}


# ---------------------------------------------------------------------------
# get_buzz_signals
# ---------------------------------------------------------------------------


def test_get_buzz_signals_returns_empty() -> None:
    adapter = StockTwitsAdapter()
    assert adapter.get_buzz_signals(ticker="AAPL") == []


def test_get_buzz_signals_no_args_returns_empty() -> None:
    adapter = StockTwitsAdapter()
    assert adapter.get_buzz_signals() == []
