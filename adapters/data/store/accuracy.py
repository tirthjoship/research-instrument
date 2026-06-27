"""Accuracy records mixin for SQLiteStore."""

from __future__ import annotations

import sqlite3
from typing import Any

from adapters.data.store._base import connect_and_init
from domain.models import AccuracyRecord


class AccuracyMixin:
    _db_path: str

    def _conn(self) -> sqlite3.Connection:
        return connect_and_init(self._db_path)

    def save_accuracy_record(self, record: AccuracyRecord) -> None:
        conn = self._conn()
        conn.execute(
            """INSERT OR REPLACE INTO accuracy_records
            (symbol, week_start, predicted_grade,
             predicted_return_2d, predicted_return_5d, predicted_return_10d,
             actual_return_2d, actual_return_5d, actual_return_10d,
             direction_correct_2d, direction_correct_5d, direction_correct_10d)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.symbol,
                record.week_start,
                record.predicted_grade,
                record.predicted_return_2d,
                record.predicted_return_5d,
                record.predicted_return_10d,
                record.actual_return_2d,
                record.actual_return_5d,
                record.actual_return_10d,
                int(record.direction_correct_2d),
                int(record.direction_correct_5d),
                int(record.direction_correct_10d),
            ),
        )
        conn.commit()

    def get_accuracy_records(
        self,
        week_start: str | None = None,
        symbol: str | None = None,
    ) -> list[AccuracyRecord]:
        query = "SELECT * FROM accuracy_records WHERE 1=1"
        params: list[Any] = []
        if week_start is not None:
            query += " AND week_start = ?"
            params.append(week_start)
        if symbol is not None:
            query += " AND symbol = ?"
            params.append(symbol)

        conn = self._conn()
        rows = conn.execute(query, params).fetchall()
        return [
            AccuracyRecord(
                symbol=r["symbol"],
                week_start=r["week_start"],
                predicted_grade=r["predicted_grade"],
                predicted_return_2d=r["predicted_return_2d"],
                predicted_return_5d=r["predicted_return_5d"],
                predicted_return_10d=r["predicted_return_10d"],
                actual_return_2d=r["actual_return_2d"],
                actual_return_5d=r["actual_return_5d"],
                actual_return_10d=r["actual_return_10d"],
                direction_correct_2d=bool(r["direction_correct_2d"]),
                direction_correct_5d=bool(r["direction_correct_5d"]),
                direction_correct_10d=bool(r["direction_correct_10d"]),
            )
            for r in rows
        ]
