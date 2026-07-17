"""Buzz signals mixin for SQLiteStore."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from adapters.data.store._base import connect_and_init
from domain.models import BuzzSignal


class BuzzSignalsMixin:
    _db_path: str

    def _conn(self) -> sqlite3.Connection:
        return connect_and_init(self._db_path)

    def save_buzz_signal(self, signal: BuzzSignal) -> None:
        conn = self._conn()
        conn.execute(
            """INSERT OR IGNORE INTO buzz_signals
            (ticker, source, mention_count, sentiment_raw, scorer, fetched_at, article_hash, article_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                signal.ticker,
                signal.source,
                signal.mention_count,
                signal.sentiment_raw,
                signal.scorer,
                signal.fetched_at.isoformat(),
                signal.article_hash,
                signal.article_text,
            ),
        )
        conn.commit()

    def prune_buzz_signals(self, before: datetime) -> int:
        """Delete buzz_signals rows older than *before*. Returns rows deleted."""
        conn = self._conn()
        cur = conn.execute(
            "DELETE FROM buzz_signals WHERE fetched_at < ?", (before.isoformat(),)
        )
        conn.commit()
        return cur.rowcount

    def get_buzz_signals(
        self,
        ticker: str | None = None,
        source: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[BuzzSignal]:
        query = "SELECT * FROM buzz_signals WHERE 1=1"
        params: list[Any] = []
        if ticker is not None:
            query += " AND ticker = ?"
            params.append(ticker)
        if source is not None:
            query += " AND source = ?"
            params.append(source)
        if start_date is not None:
            query += " AND fetched_at >= ?"
            params.append(start_date.isoformat())
        if end_date is not None:
            query += " AND fetched_at <= ?"
            params.append(end_date.isoformat())
        query += " ORDER BY fetched_at DESC"
        conn = self._conn()
        rows = conn.execute(query, params).fetchall()
        return [
            BuzzSignal(
                ticker=r["ticker"],
                source=r["source"],
                mention_count=r["mention_count"],
                sentiment_raw=r["sentiment_raw"],
                scorer=r["scorer"],
                fetched_at=datetime.fromisoformat(r["fetched_at"]),
                article_hash=r["article_hash"],
                article_text=r["article_text"] if "article_text" in r.keys() else None,
            )
            for r in rows
        ]
