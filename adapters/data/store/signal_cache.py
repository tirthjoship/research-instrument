"""Signal cache mixin for SQLiteStore."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from adapters.data.store._base import connect_and_init, to_naive_utc


class SignalCacheMixin:
    _db_path: str

    def _conn(self) -> sqlite3.Connection:
        return connect_and_init(self._db_path)

    def put_cached_signal(
        self, ticker: str, dim: str, value: float, computed_at: datetime
    ) -> None:
        conn = self._conn()
        conn.execute(
            "INSERT OR REPLACE INTO signal_cache (ticker, dim, value, computed_at) "
            "VALUES (?, ?, ?, ?)",
            (ticker, dim, value, to_naive_utc(computed_at).isoformat()),
        )
        conn.commit()

    def get_cached_signal(
        self, ticker: str, dim: str, now: datetime, ttl_hours: float
    ) -> float | None:
        conn = self._conn()
        row = conn.execute(
            "SELECT value, computed_at FROM signal_cache WHERE ticker = ? AND dim = ?",
            (ticker, dim),
        ).fetchone()
        if row is None:
            return None
        now_naive = to_naive_utc(now)
        computed = to_naive_utc(datetime.fromisoformat(row["computed_at"]))
        if (now_naive - computed).total_seconds() > ttl_hours * 3600:
            return None
        return float(row["value"])
