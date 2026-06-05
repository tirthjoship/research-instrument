"""Google News per-ticker RSS adapter — keyless live mid-cap news volume.

Queries Google News RSS by company alias so mid-caps (not just mega-caps)
surface. Emits one aggregated BuzzSignal per ticker. Implements the
scan_sources half of BuzzDiscoveryPort.
"""

from __future__ import annotations

import hashlib
import time
from datetime import datetime

import feedparser
from loguru import logger

from domain.models import BuzzSignal

_RSS = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"


class GoogleNewsAdapter:
    def __init__(
        self, alias_map: dict[str, str] | None = None, throttle_s: float = 0.3
    ) -> None:
        self._alias_map = alias_map or {}
        self._throttle_s = throttle_s

    def _throttle(self) -> None:
        time.sleep(self._throttle_s)

    def _make_hash(self, ticker: str, scan_time: datetime) -> str:
        return hashlib.sha256(
            f"google_news:{ticker}:{scan_time.date().isoformat()}".encode()
        ).hexdigest()

    def scan_sources(
        self, scan_time: datetime, tickers: list[str] | None = None
    ) -> list[BuzzSignal]:
        if not tickers:
            return []
        out: list[BuzzSignal] = []
        for ticker in tickers:
            query = self._alias_map.get(ticker, ticker).replace(" ", "+")
            try:
                self._throttle()
                feed = feedparser.parse(_RSS.format(query=query))
                count = len(getattr(feed, "entries", []))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Google News failed for {}: {}", ticker, exc)
                continue
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
