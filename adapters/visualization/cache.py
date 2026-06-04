"""Smart scan cache with TTL: 15 min during market hours, 60 min after hours."""

from __future__ import annotations

from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

_MARKET_OPEN = time(9, 30)
_MARKET_CLOSE = time(16, 0)
_TTL_MARKET_HOURS_MIN = 15
_TTL_AFTER_HOURS_MIN = 60


def _is_market_hours(now: datetime) -> bool:
    """Return True if *now* falls within 09:30–16:00 ET (exclusive of 16:00)."""
    now_et = now.astimezone(ET)
    t = now_et.time()
    return _MARKET_OPEN <= t < _MARKET_CLOSE


class ScanCache:
    """Cache for conviction scan results with smart TTL."""

    def __init__(self) -> None:
        self._results: list[Any] = []
        self._timestamp: datetime | None = None

    def store(self, results: list[Any], timestamp: datetime) -> None:
        """Save results and the time they were produced."""
        self._results = results
        self._timestamp = timestamp

    def get_results(self) -> list[Any]:
        """Return cached results (empty list if never stored)."""
        return self._results

    def is_stale(self, now: datetime | None = None) -> bool:
        """Return True if cache is empty or older than the applicable TTL."""
        if self._timestamp is None:
            return True
        if now is None:
            now = datetime.now(tz=ET)
        elapsed_minutes = (now - self._timestamp).total_seconds() / 60
        ttl = (
            _TTL_MARKET_HOURS_MIN
            if _is_market_hours(self._timestamp)
            else _TTL_AFTER_HOURS_MIN
        )
        return elapsed_minutes >= ttl

    def minutes_ago(self) -> int:
        """Return whole minutes elapsed since last store (0 if never stored)."""
        if self._timestamp is None:
            return 0
        now = datetime.now(tz=ET)
        return int((now - self._timestamp).total_seconds() / 60)

    def last_scan_time(self) -> str | None:
        """Return formatted scan time as 'HH:MM AM/PM EST', or None if empty."""
        if self._timestamp is None:
            return None
        ts_et = self._timestamp.astimezone(ET)
        return ts_et.strftime("%-I:%M %p EST")
