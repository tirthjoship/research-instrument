"""Shared SQLite helpers for all store sub-modules."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

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
    article_text TEXT,
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

CREATE TABLE IF NOT EXISTS scan_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_date TEXT NOT NULL,
    ticker TEXT NOT NULL,
    conviction REAL NOT NULL,
    divergence REAL NOT NULL,
    sub_scores_json TEXT NOT NULL,
    surfaced INTEGER NOT NULL,
    theme TEXT,
    cap_tier TEXT
);
CREATE INDEX IF NOT EXISTS idx_cand_date ON scan_candidates(scan_date);

CREATE TABLE IF NOT EXISTS signal_cache (
    ticker TEXT NOT NULL,
    dim TEXT NOT NULL,
    value REAL NOT NULL,
    computed_at TIMESTAMP NOT NULL,
    PRIMARY KEY (ticker, dim)
);
"""


def to_naive_utc(dt: datetime) -> datetime:
    """Normalize to naive UTC so stored timestamps compare consistently.

    Existing rows are tz-naive; an aware datetime is converted to UTC then
    stripped of tzinfo. A naive datetime is assumed already UTC and returned
    unchanged. Prevents naive/aware comparison crashes and isoformat-string
    ordering bugs in range/TTL queries.
    """
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def connect_and_init(db_path: str) -> sqlite3.Connection:
    """Connect to SQLite and initialise schema."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    _migrate_buzz_signals(conn)
    return conn


def _migrate_buzz_signals(conn: sqlite3.Connection) -> None:
    """Add article_text column for headline scoring (ADR-022 follow-up)."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(buzz_signals)")}
    if "article_text" not in cols:
        conn.execute("ALTER TABLE buzz_signals ADD COLUMN article_text TEXT")
        conn.commit()
