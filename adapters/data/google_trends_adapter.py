"""Google Trends adapter — BuzzDiscoveryPort via pytrends."""

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from domain.models import BuzzSignal

# Maximum tickers per pytrends request
_BATCH_SIZE = 5


class GoogleTrendsAdapter:
    """BuzzDiscoveryPort implementation using Google Trends via pytrends."""

    def __init__(self, rate_limit_seconds: float = 2.0) -> None:
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

    def _get_pytrends(self) -> Any:
        """Lazy import pytrends to avoid hard dependency."""
        from pytrends.request import TrendReq  # type: ignore[import-not-found]

        return TrendReq(hl="en-US", tz=360)

    def _interest_to_sentiment(self, interest: float) -> float:
        """Map search interest [0, 100] to sentiment_raw [-1, 1]."""
        raw = (interest - 50.0) / 50.0
        return max(-1.0, min(1.0, raw))

    def _make_hash(self, ticker: str, source_tag: str, timestamp: datetime) -> str:
        key = f"{ticker}:{source_tag}:{timestamp.isoformat()}"
        return hashlib.md5(key.encode()).hexdigest()  # noqa: S324

    def scan_sources(
        self, scan_time: datetime, tickers: list[str] | None = None
    ) -> list[BuzzSignal]:
        """Query Google Trends for current interest.

        Batches up to 5 tickers per request (pytrends limit).
        Returns one BuzzSignal per ticker with latest interest value.
        """
        if not tickers:
            return []

        results: list[BuzzSignal] = []

        for batch_start in range(0, len(tickers), _BATCH_SIZE):
            batch = tickers[batch_start : batch_start + _BATCH_SIZE]
            try:
                self._throttle()
                pytrends = self._get_pytrends()
                pytrends.build_payload(batch, timeframe="now 7-d")
                df = pytrends.interest_over_time()

                if df is None or df.empty:
                    logger.warning(
                        "Google Trends returned empty data for batch {}", batch
                    )
                    continue

                # Use latest row for current snapshot
                latest = df.iloc[-1]

                for ticker in batch:
                    if ticker not in latest.index:
                        logger.warning("Ticker {} not in Trends response", ticker)
                        continue
                    interest = float(latest[ticker])
                    signal = BuzzSignal(
                        ticker=ticker,
                        source="google_trends",
                        mention_count=int(interest),
                        sentiment_raw=self._interest_to_sentiment(interest),
                        scorer="google_trends",
                        fetched_at=scan_time,
                        article_hash=self._make_hash(ticker, "scan", scan_time),
                    )
                    results.append(signal)

            except Exception as exc:  # noqa: BLE001
                logger.warning("Google Trends scan failed for batch {}: {}", batch, exc)

        return results

    def get_historical_interest(
        self, ticker: str, start_date: datetime, end_date: datetime
    ) -> list[BuzzSignal]:
        """Fetch weekly interest for a single ticker over a date range.

        Returns one BuzzSignal per weekly data point.
        """
        results: list[BuzzSignal] = []
        timeframe = f"{start_date.strftime('%Y-%m-%d')} {end_date.strftime('%Y-%m-%d')}"
        try:
            self._throttle()
            pytrends = self._get_pytrends()
            pytrends.build_payload([ticker], timeframe=timeframe)
            df = pytrends.interest_over_time()

            if df is None or df.empty:
                logger.warning(
                    "Google Trends returned empty historical data for {}", ticker
                )
                return []

            for ts, row in df.iterrows():
                if ticker not in row.index:
                    continue
                interest = float(row[ticker])
                # ts is a pandas Timestamp; convert to datetime
                week_dt: datetime
                if hasattr(ts, "to_pydatetime"):
                    week_dt = ts.to_pydatetime()
                    if week_dt.tzinfo is None:
                        week_dt = week_dt.replace(tzinfo=timezone.utc)
                else:
                    week_dt = datetime.fromisoformat(str(ts)).replace(
                        tzinfo=timezone.utc
                    )

                signal = BuzzSignal(
                    ticker=ticker,
                    source="google_trends",
                    mention_count=int(interest),
                    sentiment_raw=self._interest_to_sentiment(interest),
                    scorer="google_trends",
                    fetched_at=week_dt,
                    article_hash=self._make_hash(ticker, "historical", week_dt),
                )
                results.append(signal)

        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Google Trends historical fetch failed for {}: {}", ticker, exc
            )

        return results

    def get_buzz_signals(
        self,
        ticker: str | None = None,
        source: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[BuzzSignal]:
        """Not applicable for trend queries — returns empty list."""
        return []
