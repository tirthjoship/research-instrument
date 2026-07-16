"""Tests for SEC EDGAR adapter — 13D activist + Form 4 insider filings."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import requests

from adapters.data.sec_edgar_adapter import SECEdgarAdapter
from domain.conviction import SmartMoneySignal, SmartMoneyType

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_13D_RESPONSE = {
    "hits": {
        "hits": [
            {
                "_id": "000123",
                "_source": {
                    "file_date": "2026-06-01",
                    "display_names": ["ValueAct Capital"],
                    "entity_name": "NVIDIA Corp",
                    "ticker": "NVDA",
                    "form_type": "SC 13D",
                    "file_num": "005-12345",
                },
            }
        ]
    }
}

_FORM4_RESPONSE = {
    "hits": {
        "hits": [
            {
                "_id": "000456",
                "_source": {
                    "file_date": "2026-06-02",
                    "display_names": ["Jensen Huang"],
                    "entity_name": "NVIDIA Corp",
                    "ticker": "NVDA",
                    "form_type": "4",
                    "file_num": "001-99999",
                },
            }
        ]
    }
}

_EMPTY_RESPONSE = {"hits": {"hits": []}}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _mock_response(json_data: dict, status_code: int = 200) -> MagicMock:
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data
    if status_code >= 400:
        http_error = requests.HTTPError(response=mock)
        mock.raise_for_status.side_effect = http_error
    else:
        mock.raise_for_status.return_value = None
    return mock


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSECEdgarAdapter:

    def test_get_13d_filings_parses_response(self) -> None:
        adapter = SECEdgarAdapter(rate_limit_seconds=0.0)
        with patch("requests.get", return_value=_mock_response(_13D_RESPONSE)):
            signals = adapter.get_13d_filings("NVDA", "2026-05-01")

        assert len(signals) == 1
        sig = signals[0]
        assert isinstance(sig, SmartMoneySignal)
        assert sig.ticker == "NVDA"
        assert sig.signal_type == SmartMoneyType.FORM_13D
        assert sig.filer_name == "ValueAct Capital"
        assert sig.filed_date == "2026-06-01"
        assert sig.is_activist is True

    def test_get_form4_filings_parses_response(self) -> None:
        adapter = SECEdgarAdapter(rate_limit_seconds=0.0)
        with patch("requests.get", return_value=_mock_response(_FORM4_RESPONSE)):
            signals = adapter.get_form4_filings("NVDA", "2026-05-01")

        assert len(signals) == 1
        sig = signals[0]
        assert isinstance(sig, SmartMoneySignal)
        assert sig.ticker == "NVDA"
        assert sig.signal_type == SmartMoneyType.FORM_4
        assert sig.filer_name == "Jensen Huang"
        assert sig.filed_date == "2026-06-02"
        assert sig.is_activist is False

    def test_get_all_signals_combines(self) -> None:
        adapter = SECEdgarAdapter(rate_limit_seconds=0.0)
        responses = [
            _mock_response(_13D_RESPONSE),
            _mock_response(_FORM4_RESPONSE),
        ]
        with patch("requests.get", side_effect=responses):
            signals = adapter.get_all_signals("NVDA", "2026-05-01")

        assert len(signals) == 2
        types = {s.signal_type for s in signals}
        assert SmartMoneyType.FORM_13D in types
        assert SmartMoneyType.FORM_4 in types

    def test_handles_http_error_gracefully(self) -> None:
        adapter = SECEdgarAdapter(rate_limit_seconds=0.0)
        with patch("requests.get", return_value=_mock_response({}, status_code=429)):
            signals = adapter.get_13d_filings("NVDA", "2026-05-01")

        assert signals == []

    def test_handles_network_error_gracefully(self) -> None:
        adapter = SECEdgarAdapter(rate_limit_seconds=0.0)
        with patch("requests.get", side_effect=requests.ConnectionError("timeout")):
            signals = adapter.get_form4_filings("NVDA", "2026-05-01")

        assert signals == []

    def test_user_agent_header_set(self) -> None:
        adapter = SECEdgarAdapter(
            rate_limit_seconds=0.0,
            user_agent="TestBot test@example.com",
        )
        with patch(
            "requests.get", return_value=_mock_response(_EMPTY_RESPONSE)
        ) as mock_get:
            adapter.get_13d_filings("NVDA", "2026-05-01")

        call_kwargs = mock_get.call_args
        assert "User-Agent" in call_kwargs.kwargs.get("headers", {})
        assert call_kwargs.kwargs["headers"]["User-Agent"] == "TestBot test@example.com"

    def test_empty_hits_returns_empty_list(self) -> None:
        adapter = SECEdgarAdapter(rate_limit_seconds=0.0)
        with patch("requests.get", return_value=_mock_response(_EMPTY_RESPONSE)):
            signals = adapter.get_13d_filings("AAPL", "2026-01-01")

        assert signals == []

    def test_rate_limit_seconds_stored(self) -> None:
        adapter = SECEdgarAdapter(rate_limit_seconds=2.5)
        assert adapter.rate_limit_seconds == 2.5

    def test_multiple_filers_in_display_names(self) -> None:
        """When display_names has multiple entries, use the first."""
        response = {
            "hits": {
                "hits": [
                    {
                        "_id": "000789",
                        "_source": {
                            "file_date": "2026-06-01",
                            "display_names": ["Filer A", "Filer B"],
                            "entity_name": "AAPL Inc",
                            "ticker": "AAPL",
                            "form_type": "SC 13D",
                            "file_num": "005-00001",
                        },
                    }
                ]
            }
        }
        adapter = SECEdgarAdapter(rate_limit_seconds=0.0)
        with patch("requests.get", return_value=_mock_response(response)):
            signals = adapter.get_13d_filings("AAPL", "2026-01-01")

        assert signals[0].filer_name == "Filer A"

    def test_malformed_json_returns_empty(self) -> None:
        adapter = SECEdgarAdapter(rate_limit_seconds=0.0)
        mock = MagicMock()
        mock.raise_for_status.return_value = None
        mock.json.side_effect = ValueError("bad json")
        with patch("requests.get", return_value=mock):
            signals = adapter.get_13d_filings("NVDA", "2026-05-01")

        assert signals == []

    def test_get_all_signals_empty_hits_for_non_us_ticker_no_crash(self) -> None:
        """SEC EDGAR is US-only; a CA/India ticker should return an empty
        signal list, not raise -- this is what makes the insider-cluster
        signal DATA-GAP gracefully for non-US tickers instead of crashing the
        whole Stock Analysis tab render."""
        adapter = SECEdgarAdapter(rate_limit_seconds=0.0)
        # Fake the EFTS API response as HTTP 200 with zero hits (the realistic
        # response for an unknown/non-US ticker)
        with patch("requests.get", return_value=_mock_response(_EMPTY_RESPONSE)):
            result = adapter.get_all_signals(ticker="RY.TO")

        assert result == []
