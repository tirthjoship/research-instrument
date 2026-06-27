"""Evaluation runs mixin for SQLiteStore."""

from __future__ import annotations

import sqlite3
from typing import Any

from adapters.data.store._base import connect_and_init
from domain.models import EvaluationRun


class EvaluationMixin:
    _db_path: str

    def _conn(self) -> sqlite3.Connection:
        return connect_and_init(self._db_path)

    def save_evaluation_run(self, run: EvaluationRun) -> None:
        conn = self._conn()
        conn.execute(
            """INSERT INTO evaluation_runs
            (run_date, eval_type, horizon, metric_name, metric_value,
             p_value, regime, details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run.run_date,
                run.eval_type,
                run.horizon,
                run.metric_name,
                run.metric_value,
                run.p_value,
                run.regime,
                run.details,
            ),
        )
        conn.commit()

    def get_evaluation_runs(
        self,
        run_date: str | None = None,
        eval_type: str | None = None,
    ) -> list[EvaluationRun]:
        query = "SELECT * FROM evaluation_runs WHERE 1=1"
        params: list[Any] = []
        if run_date is not None:
            query += " AND run_date = ?"
            params.append(run_date)
        if eval_type is not None:
            query += " AND eval_type = ?"
            params.append(eval_type)

        conn = self._conn()
        rows = conn.execute(query, params).fetchall()
        return [
            EvaluationRun(
                run_date=r["run_date"],
                eval_type=r["eval_type"],
                horizon=r["horizon"],
                metric_name=r["metric_name"],
                metric_value=r["metric_value"],
                p_value=r["p_value"],
                regime=r["regime"],
                details=r["details"],
            )
            for r in rows
        ]
