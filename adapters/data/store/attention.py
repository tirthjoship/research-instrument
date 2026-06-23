"""Attention series mixin for SQLiteStore."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from adapters.data.store._base import connect_and_init, to_naive_utc
from domain.models import AttentionPoint


class AttentionMixin:
    _db_path: str

    def _conn(self) -> sqlite3.Connection:
        return connect_and_init(self._db_path)

    def save_attention_points(self, points: list[AttentionPoint]) -> None:
        conn = self._conn()
        for p in points:
            conn.execute(
                "INSERT OR IGNORE INTO attention_series (ticker, source, ts, value) "
                "VALUES (?, ?, ?, ?)",
                (p.ticker, p.source, to_naive_utc(p.timestamp).isoformat(), p.value),
            )
        conn.commit()

    def get_attention_series(
        self, ticker: str, start: datetime, end: datetime
    ) -> list[AttentionPoint]:
        conn = self._conn()
        rows = conn.execute(
            "SELECT * FROM attention_series WHERE ticker = ? AND ts >= ? AND ts <= ? "
            "ORDER BY ts",
            (ticker, to_naive_utc(start).isoformat(), to_naive_utc(end).isoformat()),
        ).fetchall()
        return [
            AttentionPoint(
                r["ticker"],
                datetime.fromisoformat(r["ts"]),
                r["value"],
                r["source"],
            )
            for r in rows
        ]
