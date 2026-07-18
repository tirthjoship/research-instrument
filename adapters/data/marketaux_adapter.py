"""Marketaux news adapter — keyless-free-tier India buzz source.

Company-name search (``search=`` param) returns real, relevant results for
Indian tickers; raw symbol search does not reliably match — confirmed live
2026-07-17 (see docs/STATUS.md). Callers should pass an ``alias_map`` of
{ticker: company_name}, falling back to the raw ticker when no alias exists.
"""

from __future__ import annotations

import hashlib
import os
import time
from datetime import datetime
from typing import Any

import requests
from loguru import logger

from domain.models import BuzzSignal

_MARKETAUX_URL = "https://api.marketaux.com/v1/news/all"
_MAX_HEADLINES_PER_TICKER = 8


class MarketauxAdapter:
    """Fetches recent news headlines from Marketaux, keyed by company name.

    Reads the API key from the ``MARKETAUX_API_KEY`` environment variable or
    an explicit constructor argument. On any network, auth, or parse error
    for a given ticker, logs a warning and skips that ticker — never raises.

    Args:
        api_key: Marketaux API key. Falls back to ``MARKETAUX_API_KEY`` env var.
        throttle_s: Seconds to sleep between per-ticker requests.
    """

    def __init__(self, api_key: str | None = None, throttle_s: float = 0.5) -> None:
        self._api_key: str | None = api_key or os.environ.get("MARKETAUX_API_KEY")
        self._throttle_s = throttle_s

    def _throttle(self) -> None:
        time.sleep(self._throttle_s)

    def _make_hash(self, ticker: str, url: str, title: str) -> str:
        payload = f"marketaux:{ticker}:{url}:{title}"
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def _fetch(self, query: str) -> list[dict[str, Any]]:
        params: dict[str, str | int] = {
            "api_token": self._api_key or "",
            "search": query,
            "language": "en",
            "limit": _MAX_HEADLINES_PER_TICKER,
        }
        response = requests.get(_MARKETAUX_URL, params=params, timeout=15)
        response.raise_for_status()
        payload: object = response.json()
        if not isinstance(payload, dict):
            return []
        data = payload.get("data")
        if not isinstance(data, list):
            return []
        return data

    def scan_headline_sources(
        self,
        scan_time: datetime,
        tickers: list[str] | None = None,
        alias_map: dict[str, str] | None = None,
    ) -> list[BuzzSignal]:
        """One BuzzSignal per Marketaux headline (for keyword sentiment scoring).

        Args:
            scan_time: Timestamp to tag every emitted signal with (point-in-time
                safe — not the article's own published_at, which the free tier
                can return well in the past).
            tickers: Tickers to scan. Empty/None returns [].
            alias_map: Optional {ticker: company_name} — used as the search
                query when present, since company-name search is far more
                relevant than raw-symbol search for non-US tickers.

        Returns:
            List of BuzzSignal, one per headline (capped per ticker). Empty
            list if the API key is missing or tickers is empty.
        """
        if not self._api_key:
            logger.warning("Marketaux: MARKETAUX_API_KEY not set — returning []")
            return []
        if not tickers:
            return []

        alias_map = alias_map or {}
        out: list[BuzzSignal] = []
        for ticker in tickers:
            query = alias_map.get(ticker, ticker)
            try:
                self._throttle()
                articles = self._fetch(query)
            except requests.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else "?"
                logger.warning(
                    "Marketaux HTTP {} for ticker {}: {}", status, ticker, exc
                )
                continue
            except Exception as exc:  # noqa: BLE001
                logger.warning("Marketaux request failed for {}: {}", ticker, exc)
                continue

            for article in articles[:_MAX_HEADLINES_PER_TICKER]:
                title = str(article.get("title", "")).strip()
                if not title:
                    continue
                description = str(article.get("description", "")).strip()
                url = str(article.get("url", ""))
                text = f"{title} {description}".strip()
                out.append(
                    BuzzSignal(
                        ticker=ticker,
                        source="marketaux",
                        mention_count=1,
                        sentiment_raw=0.0,
                        scorer="marketaux_raw",
                        fetched_at=scan_time,
                        article_hash=self._make_hash(ticker, url, title),
                        article_text=text[:2000],
                    )
                )
        return out
