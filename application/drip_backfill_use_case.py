"""Resumable, rate-aware slow-drip backfill aligned to the scan universe.

Per-ticker, per-source isolation. A throttle (SourceThrottledError) writes
NOTHING (never poison the base window) and is counted. A genuine empty
returns []. Resumable: a ticker already fresh today is skipped, so a crash
resumes for free (store is append-only + deduped).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable

from loguru import logger

from domain.exceptions import SourceThrottledError
from domain.models import SourceHealth


class DripBackfillUseCase:
    def __init__(
        self,
        sources: dict[str, Any],  # name -> AttentionSeriesPort
        store: Any,
        sleep: Callable[[float], None],
        throttle_s: float = 45.0,
    ) -> None:
        self._sources = sources
        self._store = store
        self._sleep = sleep
        self._throttle_s = throttle_s

    def _is_fresh_today(self, ticker: str, now: datetime) -> bool:
        for src in self._sources:
            rows = self._store.get_attention_series(
                ticker, now - timedelta(days=1), now
            )
            if rows:
                return True
        return False

    def execute(
        self, tickers: list[str], now: datetime, days: int = 90
    ) -> dict[str, SourceHealth]:
        start = now - timedelta(days=days)
        health = {name: SourceHealth(source=name) for name in self._sources}
        for ticker in tickers:
            if self._is_fresh_today(ticker, now):
                continue
            for name, src in self._sources.items():
                h = health[name]
                attempts = h.attempts + 1
                try:
                    pts = src.get_attention_series(ticker, start, now)
                except SourceThrottledError:
                    logger.warning("{} throttled on {}", name, ticker)
                    health[name] = SourceHealth(
                        source=name,
                        attempts=attempts,
                        ok=h.ok,
                        empty=h.empty,
                        throttled=h.throttled + 1,
                        failed=h.failed,
                    )
                    continue
                except Exception as exc:  # noqa: BLE001
                    logger.warning("{} failed on {}: {}", name, ticker, exc)
                    health[name] = SourceHealth(
                        source=name,
                        attempts=attempts,
                        ok=h.ok,
                        empty=h.empty,
                        throttled=h.throttled,
                        failed=h.failed + 1,
                    )
                    continue
                if pts:
                    self._store.save_attention_points(pts)
                    health[name] = SourceHealth(
                        source=name,
                        attempts=attempts,
                        ok=h.ok + 1,
                        empty=h.empty,
                        throttled=h.throttled,
                        failed=h.failed,
                    )
                else:
                    health[name] = SourceHealth(
                        source=name,
                        attempts=attempts,
                        ok=h.ok,
                        empty=h.empty + 1,
                        throttled=h.throttled,
                        failed=h.failed,
                    )
                self._sleep(self._throttle_s)
        return health
