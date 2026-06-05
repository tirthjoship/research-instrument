"""SQLite implementation of RecommendationStorePort.

Schema matches spec section 14 — 4 tables with multi-horizon support.
"""

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any

from domain.models import (
    AccuracyRecord,
    AttentionPoint,
    BuzzSignal,
    EvaluationRun,
    Holding,
    MultiHorizonPrediction,
    RecommendationGrade,
    SourceReliability,
    StockRecommendation,
    WeeklyReport,
)
from domain.outcome import TrackedTrade, TradeAction, TradeOutcome
from domain.pattern_memory import LearnedRule, WeightAdjustment
from domain.surfaced_call import (
    CallOutcome,
    EvidenceItem,
    Horizon,
    OpportunityDirection,
    SurfacedCall,
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

CREATE TABLE IF NOT EXISTS tracked_trades (
    trade_id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    action TEXT NOT NULL,
    price REAL NOT NULL,
    quantity INTEGER NOT NULL,
    trade_date TEXT NOT NULL,
    conviction_at_trade REAL,
    signals_at_trade TEXT,
    opportunity_card_id TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS trade_outcomes (
    id INTEGER PRIMARY KEY,
    ticker TEXT NOT NULL,
    buy_trade_id TEXT NOT NULL,
    sell_trade_id TEXT NOT NULL,
    buy_price REAL NOT NULL,
    sell_price REAL NOT NULL,
    quantity INTEGER NOT NULL,
    buy_date TEXT NOT NULL,
    sell_date TEXT NOT NULL,
    holding_days INTEGER NOT NULL,
    return_pct REAL NOT NULL,
    return_dollar REAL NOT NULL,
    signals_at_entry TEXT,
    conviction_at_entry REAL,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(buy_trade_id, sell_trade_id)
);

CREATE TABLE IF NOT EXISTS weight_history (
    id INTEGER PRIMARY KEY,
    dimension TEXT NOT NULL,
    old_weight REAL NOT NULL,
    new_weight REAL NOT NULL,
    reason TEXT,
    adjusted_date TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS learned_rules (
    rule_id TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    signal_combination TEXT NOT NULL,
    sector TEXT DEFAULT 'any',
    action TEXT NOT NULL,
    confidence REAL NOT NULL,
    supporting_outcomes INTEGER NOT NULL,
    learned_date TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS surfaced_calls (
    call_id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    surfaced_at TEXT NOT NULL,
    conviction REAL NOT NULL,
    divergence_score REAL NOT NULL,
    direction TEXT NOT NULL,
    evidence TEXT NOT NULL,
    theme TEXT,
    cap_tier TEXT NOT NULL,
    spy_at_surface REAL NOT NULL,
    ndx_at_surface REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS call_outcomes (
    call_id TEXT NOT NULL,
    horizon INTEGER NOT NULL,
    resolved_at TEXT NOT NULL,
    entry_price REAL NOT NULL,
    exit_price REAL NOT NULL,
    forward_return REAL NOT NULL,
    spy_return REAL NOT NULL,
    ndx_return REAL NOT NULL,
    beat_spy INTEGER NOT NULL,
    beat_ndx INTEGER NOT NULL,
    beat_both INTEGER NOT NULL,
    PRIMARY KEY (call_id, horizon)
);

CREATE TABLE IF NOT EXISTS attention_series (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    source TEXT NOT NULL,
    ts TIMESTAMP NOT NULL,
    value REAL NOT NULL,
    UNIQUE(ticker, source, ts)
);
CREATE INDEX IF NOT EXISTS idx_attn_ticker ON attention_series(ticker);
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

    # ------------------------------------------------------------------
    # TrackedTrade + TradeOutcome CRUD
    # ------------------------------------------------------------------

    def save_trade(self, trade: TrackedTrade) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO tracked_trades
            (trade_id, ticker, action, price, quantity, trade_date,
             conviction_at_trade, signals_at_trade, opportunity_card_id, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                trade.trade_id,
                trade.ticker,
                trade.action.value,
                trade.price,
                trade.quantity,
                trade.trade_date,
                trade.conviction_at_trade,
                json.dumps(trade.signals_at_trade),
                trade.opportunity_card_id,
                trade.notes,
            ),
        )
        self._conn.commit()

    def get_trades(self, ticker: str | None = None) -> list[TrackedTrade]:
        query = "SELECT * FROM tracked_trades WHERE 1=1"
        params: list[Any] = []
        if ticker is not None:
            query += " AND ticker = ?"
            params.append(ticker)
        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_trade(r) for r in rows]

    def save_trade_outcome(self, outcome: TradeOutcome) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO trade_outcomes
            (ticker, buy_trade_id, sell_trade_id, buy_price, sell_price,
             quantity, buy_date, sell_date, holding_days, return_pct,
             return_dollar, signals_at_entry, conviction_at_entry)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                outcome.ticker,
                outcome.buy_trade_id,
                outcome.sell_trade_id,
                outcome.buy_price,
                outcome.sell_price,
                outcome.quantity,
                outcome.buy_date,
                outcome.sell_date,
                outcome.holding_days,
                outcome.return_pct,
                outcome.return_dollar,
                json.dumps(outcome.signals_at_entry),
                outcome.conviction_at_entry,
            ),
        )
        self._conn.commit()

    def get_trade_outcomes(self, ticker: str | None = None) -> list[TradeOutcome]:
        query = "SELECT * FROM trade_outcomes WHERE 1=1"
        params: list[Any] = []
        if ticker is not None:
            query += " AND ticker = ?"
            params.append(ticker)
        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_outcome(r) for r in rows]

    # ------------------------------------------------------------------
    # WeightAdjustment + LearnedRule CRUD
    # ------------------------------------------------------------------

    def save_weight_adjustment(self, adj: WeightAdjustment) -> None:
        self._conn.execute(
            """INSERT INTO weight_history
            (dimension, old_weight, new_weight, reason, adjusted_date)
            VALUES (?, ?, ?, ?, ?)""",
            (
                adj.dimension,
                adj.old_weight,
                adj.new_weight,
                adj.reason,
                adj.adjusted_date,
            ),
        )
        self._conn.commit()

    def get_weight_history(
        self, dimension: str | None = None
    ) -> list[WeightAdjustment]:
        query = "SELECT * FROM weight_history WHERE 1=1"
        params: list[Any] = []
        if dimension is not None:
            query += " AND dimension = ?"
            params.append(dimension)
        query += " ORDER BY adjusted_date DESC"
        rows = self._conn.execute(query, params).fetchall()
        return [
            WeightAdjustment(
                dimension=r["dimension"],
                old_weight=r["old_weight"],
                new_weight=r["new_weight"],
                reason=r["reason"] or "",
                adjusted_date=r["adjusted_date"],
            )
            for r in rows
        ]

    def save_learned_rule(self, rule: LearnedRule) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO learned_rules
            (rule_id, description, signal_combination, sector, action,
             confidence, supporting_outcomes, learned_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                rule.rule_id,
                rule.description,
                json.dumps(list(rule.signal_combination)),
                rule.sector,
                rule.action,
                rule.confidence,
                rule.supporting_outcomes,
                rule.learned_date,
            ),
        )
        self._conn.commit()

    def get_learned_rules(self) -> list[LearnedRule]:
        rows = self._conn.execute("SELECT * FROM learned_rules").fetchall()
        return [
            LearnedRule(
                rule_id=r["rule_id"],
                description=r["description"],
                signal_combination=tuple(json.loads(r["signal_combination"])),
                sector=r["sector"],
                action=r["action"],
                confidence=r["confidence"],
                supporting_outcomes=r["supporting_outcomes"],
                learned_date=r["learned_date"],
            )
            for r in rows
        ]

    def _row_to_trade(self, r: sqlite3.Row) -> TrackedTrade:
        return TrackedTrade(
            trade_id=r["trade_id"],
            ticker=r["ticker"],
            action=TradeAction(r["action"]),
            price=r["price"],
            quantity=r["quantity"],
            trade_date=r["trade_date"],
            conviction_at_trade=r["conviction_at_trade"],
            signals_at_trade=json.loads(r["signals_at_trade"] or "[]"),
            opportunity_card_id=r["opportunity_card_id"] or "",
            notes=r["notes"] or "",
        )

    def _row_to_outcome(self, r: sqlite3.Row) -> TradeOutcome:
        return TradeOutcome(
            ticker=r["ticker"],
            buy_trade_id=r["buy_trade_id"],
            sell_trade_id=r["sell_trade_id"],
            buy_price=r["buy_price"],
            sell_price=r["sell_price"],
            quantity=r["quantity"],
            buy_date=r["buy_date"],
            sell_date=r["sell_date"],
            holding_days=r["holding_days"],
            return_pct=r["return_pct"],
            return_dollar=r["return_dollar"],
            signals_at_entry=json.loads(r["signals_at_entry"] or "[]"),
            conviction_at_entry=r["conviction_at_entry"],
        )

    # ------------------------------------------------------------------
    # SurfacedCall + CallOutcome CRUD
    # ------------------------------------------------------------------

    def save_call(self, call: SurfacedCall) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO surfaced_calls
            (call_id, ticker, surfaced_at, conviction, divergence_score, direction,
             evidence, theme, cap_tier, spy_at_surface, ndx_at_surface)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                call.call_id,
                call.ticker,
                call.surfaced_at.isoformat(),
                call.conviction,
                call.divergence_score,
                call.direction.value,
                json.dumps([[e.dimension, e.score, e.note] for e in call.evidence]),
                call.theme,
                call.cap_tier,
                call.spy_at_surface,
                call.ndx_at_surface,
            ),
        )
        self._conn.commit()

    def _row_to_call(self, r: sqlite3.Row) -> SurfacedCall:
        return SurfacedCall(
            call_id=r["call_id"],
            ticker=r["ticker"],
            surfaced_at=datetime.fromisoformat(r["surfaced_at"]),
            conviction=r["conviction"],
            divergence_score=r["divergence_score"],
            direction=OpportunityDirection(r["direction"]),
            evidence=tuple(
                EvidenceItem(d, s, n) for d, s, n in json.loads(r["evidence"])
            ),
            theme=r["theme"],
            cap_tier=r["cap_tier"],
            spy_at_surface=r["spy_at_surface"],
            ndx_at_surface=r["ndx_at_surface"],
        )

    def get_call(self, call_id: str) -> SurfacedCall | None:
        row = self._conn.execute(
            "SELECT * FROM surfaced_calls WHERE call_id = ?", (call_id,)
        ).fetchone()
        return self._row_to_call(row) if row else None

    def get_all_calls(self) -> list[SurfacedCall]:
        rows = self._conn.execute("SELECT * FROM surfaced_calls").fetchall()
        return [self._row_to_call(r) for r in rows]

    def get_due_calls(self, now: datetime) -> list[tuple[SurfacedCall, Horizon]]:
        resolved = {
            (r["call_id"], r["horizon"])
            for r in self._conn.execute(
                "SELECT call_id, horizon FROM call_outcomes"
            ).fetchall()
        }
        due: list[tuple[SurfacedCall, Horizon]] = []
        for call in self.get_all_calls():
            for h in Horizon:
                if (call.call_id, h.value) in resolved:
                    continue
                if now >= call.surfaced_at + timedelta(days=h.value):
                    due.append((call, h))
        return due

    def save_outcome(self, outcome: CallOutcome) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO call_outcomes
            (call_id, horizon, resolved_at, entry_price, exit_price, forward_return,
             spy_return, ndx_return, beat_spy, beat_ndx, beat_both)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                outcome.call_id,
                outcome.horizon.value,
                outcome.resolved_at.isoformat(),
                outcome.entry_price,
                outcome.exit_price,
                outcome.forward_return,
                outcome.spy_return,
                outcome.ndx_return,
                int(outcome.beat_spy),
                int(outcome.beat_ndx),
                int(outcome.beat_both),
            ),
        )
        self._conn.commit()

    def get_outcomes(self) -> list[CallOutcome]:
        rows = self._conn.execute("SELECT * FROM call_outcomes").fetchall()
        return [
            CallOutcome(
                call_id=r["call_id"],
                horizon=Horizon(r["horizon"]),
                resolved_at=datetime.fromisoformat(r["resolved_at"]),
                entry_price=r["entry_price"],
                exit_price=r["exit_price"],
                forward_return=r["forward_return"],
                spy_return=r["spy_return"],
                ndx_return=r["ndx_return"],
                beat_spy=bool(r["beat_spy"]),
                beat_ndx=bool(r["beat_ndx"]),
                beat_both=bool(r["beat_both"]),
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # AttentionPoint (attention_series) CRUD
    # ------------------------------------------------------------------

    def save_attention_points(self, points: list[AttentionPoint]) -> None:
        for p in points:
            self._conn.execute(
                "INSERT OR IGNORE INTO attention_series (ticker, source, ts, value) "
                "VALUES (?, ?, ?, ?)",
                (p.ticker, p.source, p.timestamp.isoformat(), p.value),
            )
        self._conn.commit()

    def get_attention_series(
        self, ticker: str, start: datetime, end: datetime
    ) -> list[AttentionPoint]:
        rows = self._conn.execute(
            "SELECT * FROM attention_series WHERE ticker = ? AND ts >= ? AND ts <= ? "
            "ORDER BY ts",
            (ticker, start.isoformat(), end.isoformat()),
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
