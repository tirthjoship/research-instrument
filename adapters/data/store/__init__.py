"""SQLite store package — re-exports SQLiteStore for backward compatibility."""

from __future__ import annotations

import sqlite3

from adapters.data.store._base import _SCHEMA, _migrate_buzz_signals, to_naive_utc
from adapters.data.store.accuracy import AccuracyMixin
from adapters.data.store.attention import AttentionMixin
from adapters.data.store.buzz_signals import BuzzSignalsMixin
from adapters.data.store.calls import CallsMixin
from adapters.data.store.candidates import CandidatesMixin
from adapters.data.store.evaluation import EvaluationMixin
from adapters.data.store.holdings import HoldingsMixin
from adapters.data.store.recommendations import RecommendationsMixin
from adapters.data.store.signal_cache import SignalCacheMixin
from adapters.data.store.source_reliability import SourceReliabilityMixin
from adapters.data.store.trades import TradesMixin
from adapters.data.store.weekly_reports import WeeklyReportsMixin
from adapters.data.store.weights import WeightsMixin

__all__ = ["SQLiteStore"]

# Re-export to_naive_utc for callers that import it from this package
__all__ += ["to_naive_utc"]


class SQLiteStore(
    RecommendationsMixin,
    AccuracyMixin,
    EvaluationMixin,
    WeeklyReportsMixin,
    BuzzSignalsMixin,
    SourceReliabilityMixin,
    HoldingsMixin,
    TradesMixin,
    WeightsMixin,
    CallsMixin,
    AttentionMixin,
    CandidatesMixin,
    SignalCacheMixin,
):
    """RecommendationStorePort backed by SQLite.

    Each mixin's _conn() method opens a new connection; for :memory: databases
    (used in tests) we override _conn() to return a single shared connection so
    all operations share the same in-memory state.
    """

    def __init__(self, db_path: str = "data/recommendations.db") -> None:
        self._db_path = db_path
        # Eagerly create and cache the connection so that ":memory:" databases
        # work correctly — every _conn() call returns the same connection.
        self.__shared_conn: sqlite3.Connection = sqlite3.connect(db_path)
        self.__shared_conn.row_factory = sqlite3.Row
        self.__shared_conn.executescript(_SCHEMA)
        _migrate_buzz_signals(self.__shared_conn)

    def _conn(self) -> sqlite3.Connection:
        """Return the shared connection (works for both file-based and :memory:)."""
        return self.__shared_conn
