"""Tests for GdeltSentimentAdapter — never hits the real GDELT API."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import requests

from adapters.data.gdelt_sentiment_adapter import GdeltSentimentAdapter
from domain.models import BuzzSignal, Sentiment

START = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
END = datetime(2026, 1, 7, 23, 59, 59, tzinfo=timezone.utc)

# Canonical patch target — all calls go through the adapter module's requests reference
_REQUESTS_GET = "adapters.data.gdelt_sentiment_adapter.requests.get"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(csv_text: str, status_code: int = 200) -> MagicMock:
    """Build a mock requests.Response."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.text = csv_text
    if status_code >= 400:
        http_err = requests.HTTPError(response=mock_resp)
        mock_resp.raise_for_status.side_effect = http_err
    else:
        mock_resp.raise_for_status.return_value = None
    return mock_resp


def _build_csv(rows: list[dict]) -> str:
    """Build a tab-separated GDELT ArtList CSV string with a header row."""
    header = "DATE\tSourceCommonName\tDocumentIdentifier\tV2Tone"
    lines = [header]
    for row in rows:
        date = row.get("DATE", "20260101120000")
        source = row.get("SourceCommonName", "reuters.com")
        doc_id = row.get("DocumentIdentifier", "http://example.com/article")
        v2tone = row.get("V2Tone", "2.5,3.1,0.6,3.7")
        lines.append(f"{date}\t{source}\t{doc_id}\t{v2tone}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


def test_default_rate_limit() -> None:
    adapter = GdeltSentimentAdapter()
    assert adapter.rate_limit_seconds == 1.0


def test_custom_rate_limit() -> None:
    adapter = GdeltSentimentAdapter(rate_limit_seconds=0.0)
    assert adapter.rate_limit_seconds == 0.0


# ---------------------------------------------------------------------------
# Parsing — happy path
# ---------------------------------------------------------------------------


def test_single_row_returns_one_sentiment() -> None:
    adapter = GdeltSentimentAdapter(rate_limit_seconds=0.0)
    csv = _build_csv([{"V2Tone": "2.5,3.1,0.6,3.7"}])
    mock_resp = _make_response(csv)

    with patch("requests.get", return_value=mock_resp):
        results = adapter.get_historical_sentiment("AAPL", START, END)

    assert len(results) == 1
    assert isinstance(results[0], Sentiment)


def test_sentiment_score_normalization_positive() -> None:
    """2.5 tone → 2.5 / 10 = 0.25."""
    adapter = GdeltSentimentAdapter(rate_limit_seconds=0.0)
    csv = _build_csv([{"V2Tone": "2.5,3.1,0.6,3.7"}])
    mock_resp = _make_response(csv)

    with patch("requests.get", return_value=mock_resp):
        results = adapter.get_historical_sentiment("AAPL", START, END)

    assert abs(results[0].sentiment_score - 0.25) < 1e-9


def test_sentiment_score_normalization_negative() -> None:
    """-1.3 tone → -1.3 / 10 = -0.13."""
    adapter = GdeltSentimentAdapter(rate_limit_seconds=0.0)
    csv = _build_csv([{"V2Tone": "-1.3,0.5,1.8,2.3"}])
    mock_resp = _make_response(csv)

    with patch("requests.get", return_value=mock_resp):
        results = adapter.get_historical_sentiment("TSLA", START, END)

    assert abs(results[0].sentiment_score - (-0.13)) < 1e-9


def test_tone_clamped_to_plus_one_when_exceeds_10() -> None:
    """Tone of 15.0 → clamp to 1.0."""
    adapter = GdeltSentimentAdapter(rate_limit_seconds=0.0)
    csv = _build_csv([{"V2Tone": "15.0,15.0,0.0,15.0"}])
    mock_resp = _make_response(csv)

    with patch("requests.get", return_value=mock_resp):
        results = adapter.get_historical_sentiment("MSFT", START, END)

    assert results[0].sentiment_score == 1.0


def test_tone_clamped_to_minus_one_when_below_minus_10() -> None:
    """Tone of -12.5 → clamp to -1.0."""
    adapter = GdeltSentimentAdapter(rate_limit_seconds=0.0)
    csv = _build_csv([{"V2Tone": "-12.5,0.0,12.5,12.5"}])
    mock_resp = _make_response(csv)

    with patch("requests.get", return_value=mock_resp):
        results = adapter.get_historical_sentiment("NVDA", START, END)

    assert results[0].sentiment_score == -1.0


def test_multiple_rows_return_multiple_sentiments() -> None:
    adapter = GdeltSentimentAdapter(rate_limit_seconds=0.0)
    csv = _build_csv(
        [
            {"DATE": "20260101120000", "V2Tone": "1.0,1.2,0.2,1.4"},
            {"DATE": "20260102130000", "V2Tone": "-2.0,0.5,2.5,3.0"},
            {"DATE": "20260103140000", "V2Tone": "5.0,5.5,0.5,6.0"},
        ]
    )
    mock_resp = _make_response(csv)

    with patch("requests.get", return_value=mock_resp):
        results = adapter.get_historical_sentiment("GOOG", START, END)

    assert len(results) == 3


# ---------------------------------------------------------------------------
# Sentiment object fields
# ---------------------------------------------------------------------------


def test_confidence_is_0_6() -> None:
    adapter = GdeltSentimentAdapter(rate_limit_seconds=0.0)
    csv = _build_csv([{"V2Tone": "3.0,3.5,0.5,4.0"}])
    mock_resp = _make_response(csv)

    with patch("requests.get", return_value=mock_resp):
        results = adapter.get_historical_sentiment("AMZN", START, END)

    assert results[0].confidence == 0.6


def test_source_field_includes_source_common_name() -> None:
    adapter = GdeltSentimentAdapter(rate_limit_seconds=0.0)
    csv = _build_csv(
        [{"SourceCommonName": "bloomberg.com", "V2Tone": "1.0,1.2,0.2,1.4"}]
    )
    mock_resp = _make_response(csv)

    with patch("requests.get", return_value=mock_resp):
        results = adapter.get_historical_sentiment("AAPL", START, END)

    assert results[0].source == "gdelt_bloomberg.com"


def test_timestamp_parsed_from_date_column() -> None:
    adapter = GdeltSentimentAdapter(rate_limit_seconds=0.0)
    csv = _build_csv([{"DATE": "20260103153045", "V2Tone": "1.0,1.2,0.2,1.4"}])
    mock_resp = _make_response(csv)

    with patch("requests.get", return_value=mock_resp):
        results = adapter.get_historical_sentiment("AAPL", START, END)

    expected = datetime(2026, 1, 3, 15, 30, 45, tzinfo=timezone.utc)
    assert results[0].timestamp == expected


def test_text_snippet_is_none() -> None:
    adapter = GdeltSentimentAdapter(rate_limit_seconds=0.0)
    csv = _build_csv([{"V2Tone": "1.0,1.2,0.2,1.4"}])
    mock_resp = _make_response(csv)

    with patch("requests.get", return_value=mock_resp):
        results = adapter.get_historical_sentiment("AAPL", START, END)

    assert results[0].text_snippet is None


# ---------------------------------------------------------------------------
# Edge cases — empty / malformed responses
# ---------------------------------------------------------------------------


def test_empty_response_returns_empty_list() -> None:
    adapter = GdeltSentimentAdapter(rate_limit_seconds=0.0)
    mock_resp = _make_response("")

    with patch("requests.get", return_value=mock_resp):
        results = adapter.get_historical_sentiment("AAPL", START, END)

    assert results == []


def test_header_only_response_returns_empty_list() -> None:
    adapter = GdeltSentimentAdapter(rate_limit_seconds=0.0)
    csv = "DATE\tSourceCommonName\tDocumentIdentifier\tV2Tone"
    mock_resp = _make_response(csv)

    with patch("requests.get", return_value=mock_resp):
        results = adapter.get_historical_sentiment("AAPL", START, END)

    assert results == []


def test_malformed_row_is_skipped() -> None:
    """A row with a non-numeric V2Tone should be skipped, not crash."""
    adapter = GdeltSentimentAdapter(rate_limit_seconds=0.0)
    good_row = {"DATE": "20260101120000", "V2Tone": "2.5,3.1,0.6,3.7"}
    bad_row_csv = "20260102130000\treuters.com\thttp://example.com\tBAD_TONE"
    csv = _build_csv([good_row]) + "\n" + bad_row_csv
    mock_resp = _make_response(csv)

    with patch("requests.get", return_value=mock_resp):
        results = adapter.get_historical_sentiment("AAPL", START, END)

    # Only the good row returned
    assert len(results) == 1
    assert abs(results[0].sentiment_score - 0.25) < 1e-9


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_http_error_returns_empty_list() -> None:
    adapter = GdeltSentimentAdapter(rate_limit_seconds=0.0)
    mock_resp = _make_response("", status_code=500)

    with patch("requests.get", return_value=mock_resp):
        results = adapter.get_historical_sentiment("AAPL", START, END)

    assert results == []


def test_429_rate_limit_returns_empty_list() -> None:
    adapter = GdeltSentimentAdapter(rate_limit_seconds=0.0)
    mock_resp = _make_response("", status_code=429)

    with patch("requests.get", return_value=mock_resp):
        results = adapter.get_historical_sentiment("TSLA", START, END)

    assert results == []


def test_network_error_returns_empty_list() -> None:
    adapter = GdeltSentimentAdapter(rate_limit_seconds=0.0)

    with patch("requests.get", side_effect=ConnectionError("timeout")):
        results = adapter.get_historical_sentiment("MSFT", START, END)

    assert results == []


def test_timeout_returns_empty_list() -> None:
    adapter = GdeltSentimentAdapter(rate_limit_seconds=0.0)

    with patch("requests.get", side_effect=requests.Timeout("timed out")):
        results = adapter.get_historical_sentiment("GOOG", START, END)

    assert results == []


# ---------------------------------------------------------------------------
# API call parameters
# ---------------------------------------------------------------------------


def test_request_uses_correct_datetime_format() -> None:
    """Verify startdatetime/enddatetime params are YYYYMMDDHHMMSS."""
    adapter = GdeltSentimentAdapter(rate_limit_seconds=0.0)
    csv = _build_csv([{"V2Tone": "1.0,1.2,0.2,1.4"}])
    mock_resp = _make_response(csv)

    with patch("requests.get", return_value=mock_resp) as mock_get:
        adapter.get_historical_sentiment("AAPL", START, END)

    call_kwargs = mock_get.call_args
    params = (
        call_kwargs[1]["params"] if "params" in call_kwargs[1] else call_kwargs[0][1]
    )
    assert params["startdatetime"] == "20260101000000"
    assert params["enddatetime"] == "20260107235959"


def test_request_query_includes_symbol() -> None:
    adapter = GdeltSentimentAdapter(rate_limit_seconds=0.0)
    csv = _build_csv([{"V2Tone": "1.0,1.2,0.2,1.4"}])
    mock_resp = _make_response(csv)

    with patch("requests.get", return_value=mock_resp) as mock_get:
        adapter.get_historical_sentiment("NVDA", START, END)

    call_kwargs = mock_get.call_args
    params = (
        call_kwargs[1]["params"] if "params" in call_kwargs[1] else call_kwargs[0][1]
    )
    assert "NVDA" in params["query"]
    assert params["mode"] == "ArtList"
    assert params["format"] == "csv"


# ---------------------------------------------------------------------------
# Task 9: 429 backoff/retry + get_historical_buzz
# ---------------------------------------------------------------------------


def test_gdelt_retries_on_429_then_succeeds() -> None:
    err = requests.HTTPError(response=MagicMock(status_code=429))
    ok = MagicMock(status_code=200, text="")
    ok.raise_for_status = lambda: None
    bad = MagicMock()
    bad.raise_for_status = MagicMock(side_effect=err)
    with (
        patch(
            "adapters.data.gdelt_sentiment_adapter.requests.get", side_effect=[bad, ok]
        ) as g,
        patch("adapters.data.gdelt_sentiment_adapter.time.sleep"),
    ):
        GdeltSentimentAdapter(max_retries=2, throttle_s=0).get_historical_sentiment(
            "ASTS", datetime(2026, 4, 1), datetime(2026, 6, 1)
        )
    assert g.call_count == 2


def test_gdelt_get_historical_buzz_returns_buzz_signals() -> None:
    csv_text = "DATE\tSourceCommonName\tDocumentIdentifier\n20260501120000\tx\thttp://a\n20260502120000\ty\thttp://b\n"
    ok = MagicMock(status_code=200, text=csv_text)
    ok.raise_for_status = lambda: None
    with (
        patch("adapters.data.gdelt_sentiment_adapter.requests.get", return_value=ok),
        patch("adapters.data.gdelt_sentiment_adapter.time.sleep"),
    ):
        sigs = GdeltSentimentAdapter(throttle_s=0).get_historical_buzz(
            "ASTS", datetime(2026, 4, 1), datetime(2026, 6, 1)
        )
    assert all(isinstance(s, BuzzSignal) for s in sigs)
    assert all(s.source == "gdelt" for s in sigs)


def test_gdelt_regression_get_historical_sentiment_still_parses() -> None:
    """Regression: refactor must not break existing get_historical_sentiment parsing."""
    csv_text = _build_csv(
        [
            {
                "DATE": "20260101120000",
                "SourceCommonName": "reuters.com",
                "V2Tone": "3.0,3.5,0.5,4.0",
            },
            {
                "DATE": "20260102130000",
                "SourceCommonName": "bloomberg.com",
                "V2Tone": "-2.0,0.5,2.5,3.0",
            },
        ]
    )
    ok = MagicMock(status_code=200, text=csv_text)
    ok.raise_for_status = lambda: None
    with (
        patch("adapters.data.gdelt_sentiment_adapter.requests.get", return_value=ok),
        patch("adapters.data.gdelt_sentiment_adapter.time.sleep"),
    ):
        results = GdeltSentimentAdapter(throttle_s=0).get_historical_sentiment(
            "AAPL", datetime(2026, 1, 1), datetime(2026, 1, 7)
        )
    assert len(results) == 2
    assert all(isinstance(r, Sentiment) for r in results)
    assert abs(results[0].sentiment_score - 0.3) < 1e-9
    assert abs(results[1].sentiment_score - (-0.2)) < 1e-9
