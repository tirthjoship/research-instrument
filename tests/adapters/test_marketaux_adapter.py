"""Tests for MarketauxAdapter.scan_headline_sources()."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
import requests

from adapters.data.marketaux_adapter import MarketauxAdapter


def _mock_response(data: object) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = {
        "data": data,
        "meta": {"found": len(data) if isinstance(data, list) else 0},
    }
    resp.raise_for_status = MagicMock()
    return resp


def test_scan_headline_sources_uses_company_name_alias():
    payload = [
        {
            "uuid": "abc",
            "title": "Reliance Industries beats estimates",
            "description": "Q1 results strong.",
            "published_at": "2026-07-15T04:20:11.000000Z",
            "source": "economictimes.indiatimes.com",
            "url": "https://example.com/1",
        }
    ]
    with patch("requests.get", return_value=_mock_response(payload)) as mock_get:
        adapter = MarketauxAdapter(api_key="test-key")
        sigs = adapter.scan_headline_sources(
            datetime(2026, 7, 18, tzinfo=timezone.utc),
            tickers=["RELIANCE.NS"],
            alias_map={"RELIANCE.NS": "Reliance Industries"},
        )
    assert len(sigs) == 1
    assert sigs[0].ticker == "RELIANCE.NS"
    assert sigs[0].source == "marketaux"
    assert sigs[0].scorer == "marketaux_raw"
    assert "Reliance Industries beats estimates" in sigs[0].article_text
    mock_get.assert_called_once()
    called_params = mock_get.call_args.kwargs["params"]
    assert called_params["search"] == "Reliance Industries"


def test_scan_headline_sources_falls_back_to_ticker_without_alias():
    payload = [
        {
            "uuid": "abc",
            "title": "TCS wins new deal",
            "description": "",
            "published_at": "2026-07-15T04:20:11.000000Z",
            "source": "x",
            "url": "https://example.com/2",
        }
    ]
    with patch("requests.get", return_value=_mock_response(payload)) as mock_get:
        adapter = MarketauxAdapter(api_key="test-key")
        adapter.scan_headline_sources(
            datetime(2026, 7, 18, tzinfo=timezone.utc), tickers=["TCS.NS"]
        )
    called_params = mock_get.call_args.kwargs["params"]
    assert called_params["search"] == "TCS.NS"


def test_scan_headline_sources_skips_empty_titles():
    payload = [
        {
            "title": "",
            "description": "x",
            "published_at": "2026-07-15T00:00:00.000000Z",
            "url": "u",
        }
    ]
    with patch("requests.get", return_value=_mock_response(payload)):
        adapter = MarketauxAdapter(api_key="test-key")
        sigs = adapter.scan_headline_sources(
            datetime(2026, 7, 18, tzinfo=timezone.utc), tickers=["TCS.NS"]
        )
    assert sigs == []


def test_scan_headline_sources_returns_empty_when_key_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MARKETAUX_API_KEY", raising=False)
    adapter = MarketauxAdapter(api_key=None)
    assert adapter.scan_headline_sources(datetime.now(), tickers=["TCS.NS"]) == []


def test_scan_headline_sources_returns_empty_on_no_tickers():
    adapter = MarketauxAdapter(api_key="test-key")
    assert adapter.scan_headline_sources(datetime.now(), tickers=[]) == []


def test_scan_headline_sources_returns_empty_on_http_error():
    adapter = MarketauxAdapter(api_key="test-key")
    mock_response = MagicMock()
    mock_response.status_code = 402
    mock_response.raise_for_status.side_effect = requests.HTTPError(
        response=mock_response
    )
    with patch("requests.get", return_value=mock_response):
        assert adapter.scan_headline_sources(datetime.now(), tickers=["TCS.NS"]) == []


def test_scan_headline_sources_returns_empty_on_non_list_data():
    adapter = MarketauxAdapter(api_key="test-key")
    mock_response = MagicMock()
    mock_response.json.return_value = {"error": "invalid"}
    mock_response.raise_for_status = MagicMock()
    with patch("requests.get", return_value=mock_response):
        assert adapter.scan_headline_sources(datetime.now(), tickers=["TCS.NS"]) == []


def test_scan_headline_sources_continues_on_per_ticker_error():
    adapter = MarketauxAdapter(api_key="test-key")
    with patch("requests.get", side_effect=Exception("boom")):
        sigs = adapter.scan_headline_sources(
            datetime.now(), tickers=["TCS.NS", "INFY.NS"]
        )
    assert sigs == []


def test_scan_headline_sources_caps_headlines_per_ticker():
    payload = [
        {
            "title": f"Headline {i}",
            "description": "",
            "published_at": "2026-07-15T00:00:00.000000Z",
            "url": f"u{i}",
        }
        for i in range(10)
    ]
    with patch("requests.get", return_value=_mock_response(payload)):
        adapter = MarketauxAdapter(api_key="test-key")
        sigs = adapter.scan_headline_sources(
            datetime(2026, 7, 18, tzinfo=timezone.utc), tickers=["TCS.NS"]
        )
    assert len(sigs) <= 8
