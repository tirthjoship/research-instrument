"""Weekly reports mixin for SQLiteStore."""

from __future__ import annotations

import sqlite3

from adapters.data.store._base import connect_and_init
from domain.models import WeeklyReport


class WeeklyReportsMixin:
    _db_path: str

    def _conn(self) -> sqlite3.Connection:
        return connect_and_init(self._db_path)

    def save_weekly_report(self, report: WeeklyReport) -> None:
        conn = self._conn()
        conn.execute(
            """INSERT OR REPLACE INTO weekly_reports
            (report_date, market, accuracy_vs_last_week,
             spy_return_same_period, max_drawdown, sharpe_ratio,
             transaction_costs)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                report.report_date,
                report.market,
                report.accuracy_vs_last_week,
                report.spy_return_same_period,
                report.max_drawdown,
                report.sharpe_ratio,
                report.transaction_costs,
            ),
        )
        conn.commit()
        # Also save each recommendation
        for rec in report.recommendations:
            self.save_recommendation(rec)  # type: ignore[attr-defined]

    def get_weekly_report(self, report_date: str) -> WeeklyReport | None:
        conn = self._conn()
        row = conn.execute(
            "SELECT * FROM weekly_reports WHERE report_date = ?",
            (report_date,),
        ).fetchone()
        if row is None:
            return None
        recs = self.get_recommendations(week_start=report_date)  # type: ignore[attr-defined]
        return WeeklyReport(
            report_date=row["report_date"],
            market=row["market"],
            recommendations=recs,
            accuracy_vs_last_week=row["accuracy_vs_last_week"],
            spy_return_same_period=row["spy_return_same_period"],
            max_drawdown=row["max_drawdown"],
            sharpe_ratio=row["sharpe_ratio"],
            transaction_costs=row["transaction_costs"],
        )
