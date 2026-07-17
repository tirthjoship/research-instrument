"""Tests for FMPAdapter.get_stock_peers()."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
import requests

from adapters.data.fmp_adapter import FMPAdapter, get_cached_stock_peers
from adapters.data.sqlite_store import SQLiteStore


def test_get_stock_peers_returns_symbols_on_success() -> None:
    adapter = FMPAdapter(api_key="test-key")
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {
            "symbol": "GOOGL",
            "companyName": "Alphabet Inc.",
            "price": 346.77,
            "mktCap": 4.1e12,
        },
        {
            "symbol": "META",
            "companyName": "Meta Platforms, Inc.",
            "price": 646.01,
            "mktCap": 1.6e12,
        },
    ]
    mock_response.raise_for_status = MagicMock()
    with patch("requests.get", return_value=mock_response) as mock_get:
        result = adapter.get_stock_peers("AAPL")
    assert result == ["GOOGL", "META"]
    mock_get.assert_called_once_with(
        "https://financialmodelingprep.com/stable/stock-peers",
        params={"symbol": "AAPL", "apikey": "test-key"},
        timeout=15,
    )


def test_get_stock_peers_returns_empty_list_when_key_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FINANCIAL_MODELING_PREP_API_KEY", raising=False)
    adapter = FMPAdapter(api_key=None)
    assert adapter.get_stock_peers("AAPL") == []


def test_get_stock_peers_returns_empty_list_on_http_error() -> None:
    adapter = FMPAdapter(api_key="test-key")
    mock_response = MagicMock()
    mock_response.status_code = 402
    mock_response.raise_for_status.side_effect = requests.HTTPError(
        response=mock_response
    )
    with patch("requests.get", return_value=mock_response):
        assert adapter.get_stock_peers("FORCEMOT.NS") == []


def test_get_stock_peers_returns_empty_list_on_non_list_payload() -> None:
    adapter = FMPAdapter(api_key="test-key")
    mock_response = MagicMock()
    mock_response.json.return_value = {"error": "Invalid symbol"}
    mock_response.raise_for_status = MagicMock()
    with patch("requests.get", return_value=mock_response):
        assert adapter.get_stock_peers("ZZZZ") == []


def test_get_stock_peers_retries_on_transient_failure() -> None:
    adapter = FMPAdapter(api_key="test-key")
    success_response = MagicMock()
    success_response.json.return_value = [
        {"symbol": "BMO.TO", "companyName": "x", "price": 1.0, "mktCap": 1.0}
    ]
    success_response.raise_for_status = MagicMock()
    with (
        patch(
            "requests.get",
            side_effect=[requests.ConnectionError("transient"), success_response],
        ) as mock_get,
        patch("adapters.data.fmp_adapter._SLEEP") as mock_sleep,
    ):
        result = adapter.get_stock_peers("RY.TO")
    assert result == ["BMO.TO"]
    assert mock_get.call_count == 2
    mock_sleep.assert_called_once()


def test_get_stock_peers_returns_empty_list_after_retries_exhausted() -> None:
    adapter = FMPAdapter(api_key="test-key")
    with (
        patch("requests.get", side_effect=requests.ConnectionError("down")),
        patch("adapters.data.fmp_adapter._SLEEP"),
    ):
        assert adapter.get_stock_peers("AAPL") == []


def test_get_cached_stock_peers_fetches_live_on_cache_miss(
    tmp_path: pytest.TempPathFactory,
) -> None:
    store = SQLiteStore(str(tmp_path / "t.db"))  # type: ignore[arg-type]
    now = datetime(2026, 7, 17, 8, 0, 0)
    mock_adapter = MagicMock(spec=FMPAdapter)
    mock_adapter.get_stock_peers.return_value = ["BMO.TO", "BNS.TO"]

    result = get_cached_stock_peers(store, "RY.TO", now, adapter=mock_adapter)

    assert result == ["BMO.TO", "BNS.TO"]
    mock_adapter.get_stock_peers.assert_called_once_with("RY.TO")


def test_get_cached_stock_peers_writes_to_cache_and_hits_next_call(
    tmp_path: pytest.TempPathFactory,
) -> None:
    store = SQLiteStore(str(tmp_path / "t.db"))  # type: ignore[arg-type]
    now = datetime(2026, 7, 17, 8, 0, 0)
    mock_adapter = MagicMock(spec=FMPAdapter)
    mock_adapter.get_stock_peers.return_value = ["ASAHIINDIA.NS"]

    get_cached_stock_peers(store, "FORCEMOT.NS", now, adapter=mock_adapter)
    result = get_cached_stock_peers(
        store, "FORCEMOT.NS", now + timedelta(hours=1), adapter=mock_adapter
    )

    assert result == ["ASAHIINDIA.NS"]
    mock_adapter.get_stock_peers.assert_called_once()  # second call was a cache hit


def test_get_cached_stock_peers_does_not_cache_empty_result(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """A live-fetch failure and a genuine zero-peers result both look like []
    — neither is persisted, so the next call retries live (see plan's Global
    Constraints: never persist an empty peers result)."""
    store = SQLiteStore(str(tmp_path / "t.db"))  # type: ignore[arg-type]
    now = datetime(2026, 7, 17, 8, 0, 0)
    mock_adapter = MagicMock(spec=FMPAdapter)
    mock_adapter.get_stock_peers.return_value = []

    get_cached_stock_peers(store, "ZZZZ", now, adapter=mock_adapter)
    get_cached_stock_peers(
        store, "ZZZZ", now + timedelta(minutes=1), adapter=mock_adapter
    )

    assert mock_adapter.get_stock_peers.call_count == 2  # no cache write happened
