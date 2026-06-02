"""Tests for watchlist SQLite CRUD."""

from __future__ import annotations

import pathlib

import pytest

from adapters.data.sqlite_store import SQLiteStore


class TestWatchlistCRUD:
    @pytest.fixture()
    def store(self, tmp_path: pathlib.Path) -> SQLiteStore:
        db_path = str(tmp_path / "test.db")
        return SQLiteStore(db_path)

    def test_add_watchlist_item(self, store: SQLiteStore) -> None:
        store.add_watchlist("NVDA", notes="earnings play")
        items = store.get_watchlist()
        assert len(items) == 1
        assert items[0]["symbol"] == "NVDA"
        assert items[0]["notes"] == "earnings play"

    def test_add_duplicate_updates(self, store: SQLiteStore) -> None:
        store.add_watchlist("NVDA", notes="first")
        store.add_watchlist("NVDA", notes="updated")
        items = store.get_watchlist()
        assert len(items) == 1
        assert items[0]["notes"] == "updated"

    def test_remove_watchlist_item(self, store: SQLiteStore) -> None:
        store.add_watchlist("NVDA")
        store.add_watchlist("AMD")
        store.remove_watchlist("NVDA")
        items = store.get_watchlist()
        assert len(items) == 1
        assert items[0]["symbol"] == "AMD"

    def test_remove_nonexistent_no_error(self, store: SQLiteStore) -> None:
        store.remove_watchlist("FAKE")  # should not raise

    def test_get_empty_watchlist(self, store: SQLiteStore) -> None:
        items = store.get_watchlist()
        assert items == []

    def test_get_watchlist_returns_dicts(self, store: SQLiteStore) -> None:
        store.add_watchlist("TSLA", notes="")
        items = store.get_watchlist()
        assert "symbol" in items[0]
        assert "added_date" in items[0]
        assert "notes" in items[0]
