"""Source reliability mixin for SQLiteStore."""

from __future__ import annotations

import sqlite3

from adapters.data.store._base import connect_and_init
from domain.models import SourceReliability


class SourceReliabilityMixin:
    _db_path: str

    def _conn(self) -> sqlite3.Connection:
        return connect_and_init(self._db_path)

    def record_source_outcome(
        self,
        source: str,
        ticker: str,
        predicted_direction: float,
        actual_direction: float,
    ) -> None:
        is_correct = int((predicted_direction >= 0) == (actual_direction >= 0))
        conn = self._conn()
        conn.execute(
            """INSERT INTO source_reliability (source, ticker, correct_calls, total_calls, last_updated)
            VALUES (?, ?, ?, 1, datetime('now'))
            ON CONFLICT(source, ticker) DO UPDATE SET
                correct_calls = correct_calls + excluded.correct_calls,
                total_calls = total_calls + 1,
                last_updated = datetime('now')""",
            (source, ticker, is_correct),
        )
        conn.commit()

    def get_source_reliability(
        self, source: str, ticker: str | None = None
    ) -> SourceReliability:
        conn = self._conn()
        if ticker is not None:
            row = conn.execute(
                "SELECT correct_calls, total_calls FROM source_reliability WHERE source = ? AND ticker = ?",
                (source, ticker),
            ).fetchone()
            if row is None:
                return SourceReliability(
                    source=source, ticker=ticker, correct_calls=0, total_calls=0
                )
            return SourceReliability(
                source=source,
                ticker=ticker,
                correct_calls=row["correct_calls"],
                total_calls=row["total_calls"],
            )
        else:
            row = conn.execute(
                "SELECT SUM(correct_calls) AS correct_calls, SUM(total_calls) AS total_calls FROM source_reliability WHERE source = ?",
                (source,),
            ).fetchone()
            correct = row["correct_calls"] or 0
            total = row["total_calls"] or 0
            return SourceReliability(
                source=source, ticker=None, correct_calls=correct, total_calls=total
            )

    def get_all_source_reliabilities(self) -> list[SourceReliability]:
        conn = self._conn()
        rows = conn.execute("SELECT * FROM source_reliability").fetchall()
        return [
            SourceReliability(
                source=r["source"],
                ticker=r["ticker"],
                correct_calls=r["correct_calls"],
                total_calls=r["total_calls"],
            )
            for r in rows
        ]
