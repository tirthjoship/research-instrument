"""StockTwits adapter — BuzzDiscoveryPort via StockTwits free API."""

from __future__ import annotations

import hashlib
import time
from datetime import datetime
from typing import Any

import requests
from loguru import logger

from domain.models import BuzzSignal

_BASE_URL = "https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"


class StockTwitsAdapter:
    """BuzzDiscoveryPort implementation using the StockTwits free streaming API."""

    def __init__(self, rate_limit_seconds: float = 1.8) -> None:
        self._rate_limit_seconds = rate_limit_seconds
        self._last_request_time: float = 0.0

    @property
    def rate_limit_seconds(self) -> float:
        return self._rate_limit_seconds

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < self._rate_limit_seconds:
            time.sleep(self._rate_limit_seconds - elapsed)
        self._last_request_time = time.time()

    def _make_hash(self, ticker: str, scan_time: datetime) -> str:
        key = f"stocktwits_{ticker}_{scan_time.isoformat()}"
        return hashlib.md5(key.encode()).hexdigest()  # noqa: S324

    def _fetch_messages(self, ticker: str) -> list[dict[str, Any]]:
        """Fetch raw messages for a ticker from the StockTwits API."""
        url = _BASE_URL.format(ticker=ticker)
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        messages: list[dict[str, Any]] = data.get("messages", [])
        return messages

    def _compute_sentiment(self, messages: list[dict[str, Any]]) -> float:
        """Compute (bullish - bearish) / total_tagged, or 0.0 if none tagged."""
        bullish = 0
        bearish = 0
        for msg in messages:
            sentiment = msg.get("sentiment")
            if not sentiment:
                continue
            basic = sentiment.get("basic", "")
            if basic == "Bullish":
                bullish += 1
            elif basic == "Bearish":
                bearish += 1

        total_tagged = bullish + bearish
        if total_tagged == 0:
            return 0.0
        return (bullish - bearish) / total_tagged

    def scan_sources(
        self, scan_time: datetime, tickers: list[str] | None = None
    ) -> list[BuzzSignal]:
        """Fetch recent StockTwits messages per ticker.

        Returns one BuzzSignal per ticker with:
        - mention_count = number of messages in response
        - sentiment_raw = (bullish - bearish) / total_tagged, or 0.0 if none tagged
        - scorer = "stocktwits"
        - source = "stocktwits"
        """
        if not tickers:
            return []

        results: list[BuzzSignal] = []

        for ticker in tickers:
            try:
                self._throttle()
                messages = self._fetch_messages(ticker)
                signal = BuzzSignal(
                    ticker=ticker,
                    source="stocktwits",
                    mention_count=len(messages),
                    sentiment_raw=self._compute_sentiment(messages),
                    scorer="stocktwits",
                    fetched_at=scan_time,
                    article_hash=self._make_hash(ticker, scan_time),
                )
                results.append(signal)
            except requests.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else "?"
                logger.warning(
                    "StockTwits HTTP {} for ticker {}: {}", status, ticker, exc
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("StockTwits scan failed for ticker {}: {}", ticker, exc)

        return results

    def get_buzz_signals(
        self,
        ticker: str | None = None,
        source: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[BuzzSignal]:
        """Not available on StockTwits free tier — returns empty list."""
        return []
