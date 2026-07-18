"""Financial Modeling Prep adapter — stock-peers endpoint.

Confirmed live (2026-07-17) to return real, already-yfinance-suffixed peer
tickers for all 3 markets this project covers (US, Canada, India) — unlike
Finnhub's peers endpoint, which 403s for India. See
docs/superpowers/specs/2026-07-17-fmp-supply-chain-peers-design.md.
"""

from __future__ import annotations

import os
from datetime import datetime
from time import sleep as _time_sleep
from typing import Any

import requests
from loguru import logger

from adapters.data.retry import retry_with_backoff

_FMP_STOCK_PEERS_URL = "https://financialmodelingprep.com/stable/stock-peers"

# Module-level seam so tests can stub retry backoff waits (no real sleeping).
_SLEEP = _time_sleep


class FMPAdapter:
    """Financial Modeling Prep API client.

    Reads the API key from the ``FINANCIAL_MODELING_PREP_API_KEY`` environment
    variable or an explicit constructor argument. On any network, auth, or
    parse error the adapter logs a warning and returns an empty list — it
    never raises.

    Args:
        api_key: FMP API key. Falls back to ``FINANCIAL_MODELING_PREP_API_KEY``
            env var.
    """

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key: str | None = api_key or os.environ.get(
            "FINANCIAL_MODELING_PREP_API_KEY"
        )

    def get_stock_peers(self, ticker: str) -> list[str]:
        """Return peer ticker symbols for *ticker* from FMP's stock-peers endpoint.

        Args:
            ticker: Stock ticker symbol, already yfinance-suffixed for
                non-US markets (e.g. ``"RY.TO"``, ``"FORCEMOT.NS"``).

        Returns:
            List of peer ticker symbols. Empty list on any error, missing
            key, or non-list response — never raises.
        """
        if not self._api_key:
            logger.warning(
                "FMP: FINANCIAL_MODELING_PREP_API_KEY not set — returning []"
            )
            return []

        params = {"symbol": ticker, "apikey": self._api_key}

        def _fetch() -> list[str]:
            response = requests.get(_FMP_STOCK_PEERS_URL, params=params, timeout=15)
            response.raise_for_status()
            payload: object = response.json()
            if not isinstance(payload, list):
                logger.warning("FMP: unexpected response type for {}", ticker)
                return []
            return [str(item["symbol"]) for item in payload if "symbol" in item]

        try:
            return retry_with_backoff(_fetch, attempts=2, sleep=_SLEEP)
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "?"
            logger.warning("FMP HTTP {} for ticker {}: {}", status, ticker, exc)
            return []
        except Exception as exc:  # noqa: BLE001
            logger.warning("FMP request failed for ticker {}: {}", ticker, exc)
            return []


def get_cached_stock_peers(
    store: Any,
    ticker: str,
    now: datetime,
    adapter: FMPAdapter | None = None,
) -> list[str]:
    """Cache-through wrapper: TTL cache hit -> return cached; miss -> fetch
    live via FMPAdapter. Only non-empty results are written to the cache —
    a live-fetch failure and a genuine zero-peers result both look like
    ``[]`` and neither is cache-worthy (mirrors PR #148's precedent of never
    trusting an empty result as a permanent answer).

    Args:
        store: A SQLiteStore instance (or any object exposing
            get_cached_peers/put_cached_peers with matching signatures).
        ticker: Stock ticker symbol.
        now: Current time, used for TTL comparison.
        adapter: Optional FMPAdapter instance (constructed fresh if omitted).

    Returns:
        List of peer ticker symbols. Empty list if FMP has none or the
        fetch failed.
    """
    cached: list[str] | None = store.get_cached_peers(ticker, now, ttl_hours=24.0)
    if cached is not None:
        return cached

    fmp: FMPAdapter = adapter if adapter is not None else FMPAdapter()
    peers: list[str] = fmp.get_stock_peers(ticker)
    if peers:
        store.put_cached_peers(ticker, peers, now)
    return peers
