"""Tests for SourceReliabilityMixin."""

from __future__ import annotations

import pytest

from adapters.data.sqlite_store import SQLiteStore


def test_save_and_get_source_reliability(tmp_path: pytest.TempPathFactory) -> None:
    store = SQLiteStore(str(tmp_path / "test.db"))  # type: ignore[arg-type]
    store.record_source_outcome("reuters_rss", "AAPL", 0.5, 0.3)  # correct
    store.record_source_outcome("reuters_rss", "AAPL", -0.2, 0.1)  # incorrect
    rel = store.get_source_reliability("reuters_rss", "AAPL")
    assert rel.correct_calls == 1
    assert rel.total_calls == 2


def test_get_source_reliability_missing(tmp_path: pytest.TempPathFactory) -> None:
    store = SQLiteStore(str(tmp_path / "test.db"))  # type: ignore[arg-type]
    rel = store.get_source_reliability("unknown_source", "AAPL")
    assert rel.correct_calls == 0
    assert rel.total_calls == 0


def test_get_source_reliability_aggregate(tmp_path: pytest.TempPathFactory) -> None:
    store = SQLiteStore(str(tmp_path / "test.db"))  # type: ignore[arg-type]
    store.record_source_outcome("reuters_rss", "AAPL", 0.5, 0.3)
    store.record_source_outcome("reuters_rss", "GOOG", -0.2, -0.1)
    rel = store.get_source_reliability("reuters_rss", None)
    assert rel.total_calls == 2
    assert rel.ticker is None


def test_get_all_source_reliabilities(tmp_path: pytest.TempPathFactory) -> None:
    store = SQLiteStore(str(tmp_path / "test.db"))  # type: ignore[arg-type]
    store.record_source_outcome("reuters_rss", "AAPL", 0.5, 0.3)
    store.record_source_outcome("reddit_wsb", "TSLA", -0.2, -0.1)
    all_rels = store.get_all_source_reliabilities()
    assert len(all_rels) == 2
