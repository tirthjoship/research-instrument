"""Google News per-ticker RSS adapter — keyless live mid-cap news volume.

Queries Google News RSS by company alias so mid-caps (not just mega-caps)
surface. Emits one aggregated BuzzSignal per ticker. Implements the
scan_sources half of BuzzDiscoveryPort.
"""

from __future__ import annotations

import hashlib
import time
from datetime import datetime
from typing import Any

from loguru import logger

from adapters.data.feed_fetch import fetch_feed
from domain.models import BuzzSignal

_RSS = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
_MAX_HEADLINES_PER_TICKER = 8


class GoogleNewsAdapter:
    def __init__(
        self, alias_map: dict[str, str] | None = None, throttle_s: float = 0.5
    ) -> None:
        self._alias_map = alias_map or {}
        self._throttle_s = throttle_s

    def _throttle(self) -> None:
        time.sleep(self._throttle_s)

    def _make_hash(self, ticker: str, scan_time: datetime, suffix: str = "") -> str:
        payload = f"google_news:{ticker}:{scan_time.date().isoformat()}:{suffix}"
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def _fetch_entries(self, ticker: str) -> list[Any]:
        query = self._alias_map.get(ticker, ticker).replace(" ", "+")
        feed = fetch_feed(_RSS.format(query=query))
        return list(getattr(feed, "entries", []))

    def scan_sources(
        self, scan_time: datetime, tickers: list[str] | None = None
    ) -> list[BuzzSignal]:
        if not tickers:
            return []
        out: list[BuzzSignal] = []
        for ticker in tickers:
            try:
                self._throttle()
                entries = self._fetch_entries(ticker)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Google News failed for {}: {}", ticker, exc)
                continue
            count = len(entries)
            if count == 0:
                continue
            out.append(
                BuzzSignal(
                    ticker=ticker,
                    source="google_news",
                    mention_count=count,
                    sentiment_raw=0.0,
                    scorer="google_news",
                    fetched_at=scan_time,
                    article_hash=self._make_hash(ticker, scan_time),
                )
            )
        return out

    def scan_headline_sources(
        self, scan_time: datetime, tickers: list[str] | None = None
    ) -> list[BuzzSignal]:
        """One BuzzSignal per Google News headline (for keyword sentiment scoring)."""
        if not tickers:
            return []
        out: list[BuzzSignal] = []
        for ticker in tickers:
            try:
                self._throttle()
                entries = self._fetch_entries(ticker)[:_MAX_HEADLINES_PER_TICKER]
            except Exception as exc:  # noqa: BLE001
                logger.warning("Google News headlines failed for {}: {}", ticker, exc)
                continue
            for entry in entries:
                title = (getattr(entry, "title", "") or "").strip()
                if not title:
                    continue
                link = getattr(entry, "link", "") or ""
                out.append(
                    BuzzSignal(
                        ticker=ticker,
                        source="google_news",
                        mention_count=1,
                        sentiment_raw=0.0,
                        scorer="google_news_raw",
                        fetched_at=scan_time,
                        article_hash=self._make_hash(ticker, scan_time, link + title),
                        article_text=title[:2000],
                    )
                )
        return out
