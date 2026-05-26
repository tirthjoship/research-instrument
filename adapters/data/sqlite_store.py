"""SQLite implementation of RecommendationStorePort.

Schema matches spec section 14 — 4 tables with multi-horizon support.
"""

import json
import sqlite3
from typing import Any

from domain.models import (
    AccuracyRecord,
    EvaluationRun,
    MultiHorizonPrediction,
    RecommendationGrade,
    StockRecommendation,
    WeeklyReport,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS recommendations (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    week_start TEXT NOT NULL,
    grade TEXT NOT NULL,
    composite_score REAL,
    predicted_return_2d REAL,
    predicted_return_5d REAL,
    predicted_return_10d REAL,
    confidence_2d REAL,
    confidence_5d REAL,
    confidence_10d REAL,
    horizon_signals TEXT,
    sentiment_score REAL,
    divergence_score REAL,
    divergence_type TEXT,
    technical_signal REAL,
    rsi_14 REAL,
    macd REAL,
    reasoning TEXT,
    sources TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(symbol, week_start)
);

CREATE TABLE IF NOT EXISTS accuracy_records (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    week_start TEXT NOT NULL,
    predicted_grade TEXT,
    predicted_return_2d REAL,
    predicted_return_5d REAL,
    predicted_return_10d REAL,
    actual_return_2d REAL,
    actual_return_5d REAL,
    actual_return_10d REAL,
    direction_correct_2d INTEGER,
    direction_correct_5d INTEGER,
    direction_correct_10d INTEGER,
    evaluated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(symbol, week_start)
);

CREATE TABLE IF NOT EXISTS evaluation_runs (
    id INTEGER PRIMARY KEY,
    run_date TEXT NOT NULL,
    eval_type TEXT NOT NULL,
    horizon TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value REAL,
    p_value REAL,
    regime TEXT,
    details TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS weekly_reports (
    id INTEGER PRIMARY KEY,
    report_date TEXT NOT NULL UNIQUE,
    market TEXT NOT NULL,
    accuracy_vs_last_week REAL,
    spy_return_same_period REAL,
    max_drawdown REAL,
    sharpe_ratio REAL,
    transaction_costs REAL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_rec_week ON recommendations(week_start);
CREATE INDEX IF NOT EXISTS idx_rec_symbol ON recommendations(symbol);
CREATE INDEX IF NOT EXISTS idx_acc_week ON accuracy_records(week_start);
CREATE INDEX IF NOT EXISTS idx_eval_date ON evaluation_runs(run_date);
"""


class SQLiteStore:
    """RecommendationStorePort backed by SQLite."""

    def __init__(self, db_path: str = "data/recommendations.db") -> None:
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)

    def save_recommendation(self, rec: StockRecommendation) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO recommendations
            (symbol, week_start, grade, composite_score,
             predicted_return_2d, predicted_return_5d, predicted_return_10d,
             confidence_2d, confidence_5d, confidence_10d,
             horizon_signals, sentiment_score, divergence_score,
             divergence_type, technical_signal, rsi_14, macd,
             reasoning, sources)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                rec.symbol,
                rec.week_start,
                rec.grade.value,
                rec.composite_score,
                rec.prediction.predicted_return_2d,
                rec.prediction.predicted_return_5d,
                rec.prediction.predicted_return_10d,
                rec.prediction.confidence_2d,
                rec.prediction.confidence_5d,
                rec.prediction.confidence_10d,
                json.dumps(rec.horizon_signals),
                rec.sentiment_score,
                rec.divergence_score,
                rec.divergence_type,
                rec.technical_signal,
                rec.rsi_14,
                rec.macd,
                rec.reasoning,
                json.dumps(rec.sources),
            ),
        )
        self._conn.commit()

    def get_recommendations(
        self,
        week_start: str | None = None,
        symbol: str | None = None,
    ) -> list[StockRecommendation]:
        query = "SELECT * FROM recommendations WHERE 1=1"
        params: list[Any] = []
        if week_start is not None:
            query += " AND week_start = ?"
            params.append(week_start)
        if symbol is not None:
            query += " AND symbol = ?"
            params.append(symbol)

        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_recommendation(r) for r in rows]

    def save_accuracy_record(self, record: AccuracyRecord) -> None:
        self._conn.execute(
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
        self._conn.commit()

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

        rows = self._conn.execute(query, params).fetchall()
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

    def save_evaluation_run(self, run: EvaluationRun) -> None:
        self._conn.execute(
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
        self._conn.commit()

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

        rows = self._conn.execute(query, params).fetchall()
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

    def save_weekly_report(self, report: WeeklyReport) -> None:
        self._conn.execute(
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
        # Also save each recommendation
        for rec in report.recommendations:
            self.save_recommendation(rec)
        self._conn.commit()

    def get_weekly_report(self, report_date: str) -> WeeklyReport | None:
        row = self._conn.execute(
            "SELECT * FROM weekly_reports WHERE report_date = ?",
            (report_date,),
        ).fetchone()
        if row is None:
            return None
        recs = self.get_recommendations(week_start=report_date)
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

    def _row_to_recommendation(self, r: sqlite3.Row) -> StockRecommendation:
        pred = MultiHorizonPrediction(
            predicted_return_2d=r["predicted_return_2d"],
            predicted_return_5d=r["predicted_return_5d"],
            predicted_return_10d=r["predicted_return_10d"],
            confidence_2d=r["confidence_2d"],
            confidence_5d=r["confidence_5d"],
            confidence_10d=r["confidence_10d"],
        )
        return StockRecommendation(
            symbol=r["symbol"],
            week_start=r["week_start"],
            grade=RecommendationGrade(r["grade"]),
            composite_score=r["composite_score"],
            prediction=pred,
            horizon_signals=json.loads(r["horizon_signals"]),
            reasoning=r["reasoning"],
            sources=json.loads(r["sources"]),
            sentiment_score=r["sentiment_score"],
            divergence_score=r["divergence_score"],
            divergence_type=r["divergence_type"],
            technical_signal=r["technical_signal"],
            rsi_14=r["rsi_14"],
            macd=r["macd"],
        )
