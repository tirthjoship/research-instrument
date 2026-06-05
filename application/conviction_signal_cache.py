"""Daily cache for the expensive conviction dims (event_signal, analyst_signal).

Cache hit within TTL -> reuse. Miss -> compute + store. Failure -> honest
neutral 5.0 + a flag (never a silent pin). Flags seed sub-project B's
source-health monitor.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from loguru import logger

_NEUTRAL = 5.0


class ConvictionSignalCache:
    def __init__(self, store: Any, ttl_hours: float = 24.0) -> None:
        self._store = store
        self._ttl = ttl_hours
        self.flags: set[tuple[str, str]] = set()

    def get_or_compute(
        self,
        ticker: str,
        dim: str,
        now: datetime,
        compute: Callable[[str, datetime], float],
    ) -> float:
        cached: float | None = self._store.get_cached_signal(
            ticker, dim, now, self._ttl
        )
        if cached is not None:
            return cached
        try:
            value = compute(ticker, now)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Conviction dim {} failed for {}: {}", dim, ticker, exc)
            self.flags.add((ticker, dim))
            return _NEUTRAL
        self._store.put_cached_signal(ticker, dim, value, now)
        return value
