"""Finnhub recommendation-trend adapter — analyst-consensus fallback for
markets yfinance leaves empty (confirmed live for Canada; India 403s
premium-gated as of 2026-07-18, see docs/STATUS.md).
"""

from __future__ import annotations

import os
from time import sleep as _time_sleep

import requests
from loguru import logger

from adapters.data.retry import retry_with_backoff

_FINNHUB_RECOMMENDATION_URL = "https://finnhub.io/api/v1/stock/recommendation"

# Finnhub 403s on yfinance-style suffixed Canadian symbols (confirmed live
# 2026-07-18) — it wants the bare symbol, e.g. "RY" not "RY.TO".
_CANADIAN_SUFFIXES = (".TO", ".V", ".NE")


def _to_finnhub_symbol(ticker: str) -> str:
    for suffix in _CANADIAN_SUFFIXES:
        if ticker.endswith(suffix):
            return ticker[: -len(suffix)]
    return ticker


# Module-level seam so tests can stub retry backoff waits (no real sleeping).
_SLEEP = _time_sleep


def parse_recommendation_trend(payload: list[dict]) -> dict[str, int] | None:  # type: ignore[type-arg]
    """Pure helper: pick the most recent period's counts from a Finnhub
    recommendation-trend payload.

    Args:
        payload: Parsed JSON list from Finnhub's /stock/recommendation endpoint,
            one entry per monthly period.

    Returns:
        Dict with strongBuy/buy/hold/sell/strongSell counts for the most
        recent period, or None if payload is empty.
    """
    if not payload:
        return None
    latest = max(payload, key=lambda item: str(item.get("period", "")))
    return {
        "strongBuy": int(latest.get("strongBuy", 0) or 0),
        "buy": int(latest.get("buy", 0) or 0),
        "hold": int(latest.get("hold", 0) or 0),
        "sell": int(latest.get("sell", 0) or 0),
        "strongSell": int(latest.get("strongSell", 0) or 0),
    }


class FinnhubRecommendationAdapter:
    """Fetches Finnhub's analyst recommendation-trend counts.

    Reads the API key from the ``FINNHUB_API_KEY`` environment variable or an
    explicit constructor argument. On any network, auth, or parse error the
    adapter logs a warning and returns None — it never raises.

    Args:
        api_key: Finnhub API key. Falls back to ``FINNHUB_API_KEY`` env var.
    """

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key: str | None = api_key or os.environ.get("FINNHUB_API_KEY")

    def get_recommendation_trend(self, ticker: str) -> dict[str, int] | None:
        """Return the most recent recommendation-trend counts for *ticker*.

        Args:
            ticker: Stock ticker symbol, already yfinance-suffixed for
                non-US markets (e.g. ``"RY.TO"``).

        Returns:
            Dict with strongBuy/buy/hold/sell/strongSell counts, or None on
            any error, missing key, empty result, or non-list response.
        """
        if not self._api_key:
            logger.warning("Finnhub: FINNHUB_API_KEY not set — returning None")
            return None

        params: dict[str, str] = {
            "symbol": _to_finnhub_symbol(ticker),
            "token": self._api_key,
        }

        def _fetch() -> dict[str, int] | None:
            response = requests.get(
                _FINNHUB_RECOMMENDATION_URL, params=params, timeout=15
            )
            response.raise_for_status()
            payload: object = response.json()
            if not isinstance(payload, list):
                logger.warning("Finnhub: unexpected response type for {}", ticker)
                return None
            return parse_recommendation_trend(payload)

        try:
            return retry_with_backoff(_fetch, attempts=2, sleep=_SLEEP)
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "?"
            logger.warning("Finnhub HTTP {} for ticker {}: {}", status, ticker, exc)
            return None
        except Exception as exc:  # noqa: BLE001
            logger.warning("Finnhub request failed for ticker {}: {}", ticker, exc)
            return None
