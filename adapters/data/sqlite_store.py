"""SQLite implementation of RecommendationStorePort.

Schema matches spec section 14 — 4 tables with multi-horizon support.
"""

import json
import sqlite3
from datetime import datetime
from typing import Any

from domain.models import (
    AccuracyRecord,
    BuzzSignal,
    EvaluationRun,
    Holding,
    MultiHorizonPrediction,
    RecommendationGrade,
    SourceReliability,
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

CREATE TABLE IF NOT EXISTS buzz_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    source TEXT NOT NULL,
    mention_count INTEGER NOT NULL,
    sentiment_raw REAL NOT NULL,
    scorer TEXT NOT NULL,
    fetched_at TIMESTAMP NOT NULL,
    article_hash TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_buzz_ticker ON buzz_signals(ticker);
CREATE INDEX IF NOT EXISTS idx_buzz_fetched ON buzz_signals(fetched_at);

CREATE TABLE IF NOT EXISTS source_reliability (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    ticker TEXT,
    correct_calls INTEGER DEFAULT 0,
    total_calls INTEGER DEFAULT 0,
    last_updated TIMESTAMP,
    UNIQUE(source, ticker)
);

CREATE TABLE IF NOT EXISTS holdings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL UNIQUE,
    quantity REAL NOT NULL,
    purchase_price REAL NOT NULL,
    purchase_date TEXT NOT NULL,
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL UNIQUE,
    added_date TEXT NOT NULL,
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
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

    def save_buzz_signal(self, signal: BuzzSignal) -> None:
        self._conn.execute(
            """INSERT OR IGNORE INTO buzz_signals
            (ticker, source, mention_count, sentiment_raw, scorer, fetched_at, article_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                signal.ticker,
                signal.source,
                signal.mention_count,
                signal.sentiment_raw,
                signal.scorer,
                signal.fetched_at.isoformat(),
                signal.article_hash,
            ),
        )
        self._conn.commit()

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
        rows = self._conn.execute(query, params).fetchall()
        return [
            BuzzSignal(
                ticker=r["ticker"],
                source=r["source"],
                mention_count=r["mention_count"],
                sentiment_raw=r["sentiment_raw"],
                scorer=r["scorer"],
                fetched_at=datetime.fromisoformat(r["fetched_at"]),
                article_hash=r["article_hash"],
            )
            for r in rows
        ]

    def record_source_outcome(
        self,
        source: str,
        ticker: str,
        predicted_direction: float,
        actual_direction: float,
    ) -> None:
        is_correct = int((predicted_direction >= 0) == (actual_direction >= 0))
        self._conn.execute(
            """INSERT INTO source_reliability (source, ticker, correct_calls, total_calls, last_updated)
            VALUES (?, ?, ?, 1, datetime('now'))
            ON CONFLICT(source, ticker) DO UPDATE SET
                correct_calls = correct_calls + excluded.correct_calls,
                total_calls = total_calls + 1,
                last_updated = datetime('now')""",
            (source, ticker, is_correct),
        )
        self._conn.commit()

    def get_source_reliability(
        self, source: str, ticker: str | None = None
    ) -> SourceReliability:
        if ticker is not None:
            row = self._conn.execute(
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
            row = self._conn.execute(
                "SELECT SUM(correct_calls) AS correct_calls, SUM(total_calls) AS total_calls FROM source_reliability WHERE source = ?",
                (source,),
            ).fetchone()
            correct = row["correct_calls"] or 0
            total = row["total_calls"] or 0
            return SourceReliability(
                source=source, ticker=None, correct_calls=correct, total_calls=total
            )

    def get_all_source_reliabilities(self) -> list[SourceReliability]:
        rows = self._conn.execute("SELECT * FROM source_reliability").fetchall()
        return [
            SourceReliability(
                source=r["source"],
                ticker=r["ticker"],
                correct_calls=r["correct_calls"],
                total_calls=r["total_calls"],
            )
            for r in rows
        ]

    def add_holding(self, holding: Holding) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO holdings
               (symbol, quantity, purchase_price, purchase_date, notes)
               VALUES (?, ?, ?, ?, ?)""",
            (
                holding.symbol,
                holding.quantity,
                holding.purchase_price,
                holding.purchase_date,
                holding.notes,
            ),
        )
        self._conn.commit()

    def remove_holding(self, symbol: str) -> None:
        self._conn.execute("DELETE FROM holdings WHERE symbol = ?", (symbol,))
        self._conn.commit()

    def get_holdings(self) -> list[Holding]:
        rows = self._conn.execute(
            "SELECT symbol, quantity, purchase_price, purchase_date, notes FROM holdings"
        ).fetchall()
        return [
            Holding(
                symbol=r[0],
                quantity=r[1],
                purchase_price=r[2],
                purchase_date=r[3],
                notes=r[4] or "",
            )
            for r in rows
        ]

    def get_holding(self, symbol: str) -> Holding | None:
        row = self._conn.execute(
            "SELECT symbol, quantity, purchase_price, purchase_date, notes FROM holdings WHERE symbol = ?",
            (symbol,),
        ).fetchone()
        if row is None:
            return None
        return Holding(
            symbol=row[0],
            quantity=row[1],
            purchase_price=row[2],
            purchase_date=row[3],
            notes=row[4] or "",
        )

    def add_watchlist(self, symbol: str, notes: str = "") -> None:
        """Add or update a symbol on the watchlist."""
        self._conn.execute(
            """INSERT INTO watchlist (symbol, added_date, notes)
               VALUES (?, date('now'), ?)
               ON CONFLICT(symbol) DO UPDATE SET notes = excluded.notes""",
            (symbol.upper(), notes),
        )
        self._conn.commit()

    def remove_watchlist(self, symbol: str) -> None:
        """Remove a symbol from the watchlist."""
        self._conn.execute("DELETE FROM watchlist WHERE symbol = ?", (symbol.upper(),))
        self._conn.commit()

    def get_watchlist(self) -> list[dict[str, str]]:
        """Return all watchlist items as dicts."""
        rows = self._conn.execute(
            "SELECT symbol, added_date, notes FROM watchlist ORDER BY symbol"
        ).fetchall()
        return [
            {
                "symbol": r["symbol"],
                "added_date": r["added_date"],
                "notes": r["notes"] or "",
            }
            for r in rows
        ]

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
