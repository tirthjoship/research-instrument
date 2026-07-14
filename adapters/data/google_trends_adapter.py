"""Google Trends adapter — BuzzDiscoveryPort via pytrends."""

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from domain.exceptions import SourceThrottledError
from domain.models import AttentionPoint, BuzzSignal

# Maximum tickers per pytrends request
_BATCH_SIZE = 5
_429_BACKOFF_SECONDS = (30.0, 60.0, 90.0)


class GoogleTrendsAdapter:
    """BuzzDiscoveryPort implementation using Google Trends via pytrends."""

    def __init__(self, rate_limit_seconds: float = 6.0) -> None:
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
        from pytrends.request import TrendReq  # type: ignore

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

        consecutive_429 = 0
        for batch_start in range(0, len(tickers), _BATCH_SIZE):
            batch = tickers[batch_start : batch_start + _BATCH_SIZE]
            batch_signals = self._scan_batch(batch, scan_time)
            if batch_signals is None:
                consecutive_429 += 1
                if consecutive_429 >= 2:
                    logger.warning(
                        "Google Trends still rate-limited after retries — "
                        "skipping remaining {} ticker(s)",
                        len(tickers) - batch_start,
                    )
                    break
                continue
            consecutive_429 = 0
            results.extend(batch_signals)

        return results

    def _scan_batch(
        self, batch: list[str], scan_time: datetime
    ) -> list[BuzzSignal] | None:
        """Fetch one pytrends batch; return None when rate-limited after retries."""
        last_exc: Exception | None = None
        for attempt, backoff in enumerate((0.0, *_429_BACKOFF_SECONDS)):
            if backoff > 0:
                logger.warning(
                    "Google Trends 429 for batch {} — backing off {:.0f}s (retry {})",
                    batch,
                    backoff,
                    attempt,
                )
                time.sleep(backoff)
            try:
                self._throttle()
                pytrends = self._get_pytrends()
                pytrends.build_payload(batch, timeframe="now 7-d")
                df = pytrends.interest_over_time()

                if df is None or df.empty:
                    logger.warning(
                        "Google Trends returned empty data for batch {}", batch
                    )
                    return []

                latest = df.iloc[-1]
                batch_results: list[BuzzSignal] = []
                for ticker in batch:
                    if ticker not in latest.index:
                        logger.warning("Ticker {} not in Trends response", ticker)
                        continue
                    interest = float(latest[ticker])
                    batch_results.append(
                        BuzzSignal(
                            ticker=ticker,
                            source="google_trends",
                            mention_count=int(interest),
                            sentiment_raw=self._interest_to_sentiment(interest),
                            scorer="google_trends",
                            fetched_at=scan_time,
                            article_hash=self._make_hash(ticker, "scan", scan_time),
                        )
                    )
                return batch_results

            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if "429" not in str(exc):
                    logger.warning(
                        "Google Trends scan failed for batch {}: {}", batch, exc
                    )
                    return []
        logger.warning(
            "Google Trends scan failed for batch {} after retries: {}",
            batch,
            last_exc,
        )
        return None

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
            msg = str(exc)
            if "429" in msg or "Too Many Requests" in msg:
                raise SourceThrottledError(
                    f"Google Trends rate-limited (429) for {ticker}: {msg}"
                ) from exc
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

    def get_attention_series(
        self,
        ticker: str,
        start: datetime,
        end: datetime,
    ) -> list[AttentionPoint]:
        """Adapt historical interest to AttentionSeriesPort (intensity points)."""
        signals = self.get_historical_interest(ticker, start, end)
        return [
            AttentionPoint(
                ticker=ticker,
                timestamp=s.fetched_at,
                value=float(s.mention_count),
                source="google_trends",
            )
            for s in signals
        ]
