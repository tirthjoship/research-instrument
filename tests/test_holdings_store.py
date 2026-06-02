"""Tests for SQLite holdings storage."""

from __future__ import annotations

import tempfile

import pytest

from adapters.data.sqlite_store import SQLiteStore
from domain.models import Holding


@pytest.fixture
def store() -> SQLiteStore:
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    return SQLiteStore(tmp.name)


class TestHoldingsStore:
    def test_add_and_get_holding(self, store: SQLiteStore) -> None:
        h = Holding("AMD", 50.0, 165.0, "2026-05-15")
        store.add_holding(h)
        result = store.get_holding("AMD")
        assert result is not None
        assert result.symbol == "AMD"
        assert result.quantity == 50.0
        assert result.purchase_price == 165.0

    def test_get_all_holdings(self, store: SQLiteStore) -> None:
        store.add_holding(Holding("AMD", 50.0, 165.0, "2026-05-15"))
        store.add_holding(Holding("NVDA", 10.0, 950.0, "2026-04-01"))
        holdings = store.get_holdings()
        assert len(holdings) == 2

    def test_remove_holding(self, store: SQLiteStore) -> None:
        store.add_holding(Holding("AMD", 50.0, 165.0, "2026-05-15"))
        store.remove_holding("AMD")
        assert store.get_holding("AMD") is None

    def test_get_nonexistent_returns_none(self, store: SQLiteStore) -> None:
        assert store.get_holding("XYZ") is None

    def test_add_duplicate_updates(self, store: SQLiteStore) -> None:
        store.add_holding(Holding("AMD", 50.0, 165.0, "2026-05-15"))
        store.add_holding(Holding("AMD", 100.0, 170.0, "2026-06-01"))
        result = store.get_holding("AMD")
        assert result is not None
        assert result.quantity == 100.0
        assert result.purchase_price == 170.0

    def test_holding_with_notes(self, store: SQLiteStore) -> None:
        store.add_holding(
            Holding("TSLA", 5.0, 200.0, "2026-01-01", notes="Speculative")
        )
        result = store.get_holding("TSLA")
        assert result is not None
        assert result.notes == "Speculative"

    def test_remove_nonexistent_no_error(self, store: SQLiteStore) -> None:
        store.remove_holding("DOESNOTEXIST")  # should not raise
