"""Tests for FinnhubRecommendationAdapter.get_recommendation_trend()."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from adapters.data.finnhub_recommendation_adapter import (
    FinnhubRecommendationAdapter,
    parse_recommendation_trend,
)


def test_parse_picks_most_recent_period() -> None:
    payload = [
        {
            "symbol": "RY.TO",
            "period": "2026-06-01",
            "strongBuy": 5,
            "buy": 3,
            "hold": 1,
            "sell": 0,
            "strongSell": 0,
        },
        {
            "symbol": "RY.TO",
            "period": "2026-07-01",
            "strongBuy": 7,
            "buy": 2,
            "hold": 1,
            "sell": 0,
            "strongSell": 0,
        },
    ]
    trend = parse_recommendation_trend(payload)
    assert trend == {
        "strongBuy": 7,
        "buy": 2,
        "hold": 1,
        "sell": 0,
        "strongSell": 0,
    }


def test_parse_empty_payload_returns_none() -> None:
    assert parse_recommendation_trend([]) is None


def test_get_recommendation_trend_returns_trend_on_success() -> None:
    adapter = FinnhubRecommendationAdapter(api_key="test-key")
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {
            "symbol": "AAPL",
            "period": "2026-07-01",
            "strongBuy": 7,
            "buy": 2,
            "hold": 1,
            "sell": 0,
            "strongSell": 0,
        }
    ]
    mock_response.raise_for_status = MagicMock()
    with patch("requests.get", return_value=mock_response) as mock_get:
        result = adapter.get_recommendation_trend("AAPL")
    assert result == {
        "strongBuy": 7,
        "buy": 2,
        "hold": 1,
        "sell": 0,
        "strongSell": 0,
    }
    mock_get.assert_called_once_with(
        "https://finnhub.io/api/v1/stock/recommendation",
        params={"symbol": "AAPL", "token": "test-key"},
        timeout=15,
    )


def test_get_recommendation_trend_strips_canadian_suffix() -> None:
    """Finnhub 403s on .TO-suffixed symbols — confirmed live 2026-07-18. It
    wants the bare symbol (e.g. "RY" not "RY.TO")."""
    adapter = FinnhubRecommendationAdapter(api_key="test-key")
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {
            "symbol": "RY",
            "period": "2026-07-01",
            "strongBuy": 6,
            "buy": 13,
            "hold": 5,
            "sell": 0,
            "strongSell": 0,
        }
    ]
    mock_response.raise_for_status = MagicMock()
    with patch("requests.get", return_value=mock_response) as mock_get:
        result = adapter.get_recommendation_trend("RY.TO")
    assert result is not None and result["strongBuy"] == 6
    mock_get.assert_called_once_with(
        "https://finnhub.io/api/v1/stock/recommendation",
        params={"symbol": "RY", "token": "test-key"},
        timeout=15,
    )


def test_get_recommendation_trend_returns_none_when_key_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    adapter = FinnhubRecommendationAdapter(api_key=None)
    assert adapter.get_recommendation_trend("RY.TO") is None


def test_get_recommendation_trend_returns_none_on_http_error() -> None:
    adapter = FinnhubRecommendationAdapter(api_key="test-key")
    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.raise_for_status.side_effect = requests.HTTPError(
        response=mock_response
    )
    with patch("requests.get", return_value=mock_response):
        assert adapter.get_recommendation_trend("FORCEMOT.NS") is None


def test_get_recommendation_trend_returns_none_on_non_list_payload() -> None:
    adapter = FinnhubRecommendationAdapter(api_key="test-key")
    mock_response = MagicMock()
    mock_response.json.return_value = {"error": "no data"}
    mock_response.raise_for_status = MagicMock()
    with patch("requests.get", return_value=mock_response):
        assert adapter.get_recommendation_trend("ZZZZ") is None


def test_get_recommendation_trend_retries_on_transient_failure() -> None:
    adapter = FinnhubRecommendationAdapter(api_key="test-key")
    success_response = MagicMock()
    success_response.json.return_value = [
        {
            "symbol": "TD.TO",
            "period": "2026-07-01",
            "strongBuy": 4,
            "buy": 3,
            "hold": 2,
            "sell": 0,
            "strongSell": 0,
        }
    ]
    success_response.raise_for_status = MagicMock()
    with (
        patch(
            "requests.get",
            side_effect=[requests.ConnectionError("transient"), success_response],
        ) as mock_get,
        patch("adapters.data.finnhub_recommendation_adapter._SLEEP") as mock_sleep,
    ):
        result = adapter.get_recommendation_trend("TD.TO")
    assert result is not None
    assert result["strongBuy"] == 4
    assert mock_get.call_count == 2
    mock_sleep.assert_called_once()
