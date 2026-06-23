"""Tests for AccuracyMixin."""

from __future__ import annotations

import pytest

from adapters.data.sqlite_store import SQLiteStore
from domain.models import AccuracyRecord


@pytest.fixture
def store() -> SQLiteStore:
    return SQLiteStore(":memory:")


def test_save_and_get_accuracy_record(store: SQLiteStore) -> None:
    record = AccuracyRecord(
        symbol="AAPL",
        week_start="2026-05-12",
        predicted_grade="strong_buy",
        predicted_return_2d=0.03,
        predicted_return_5d=0.04,
        predicted_return_10d=0.06,
        actual_return_2d=0.025,
        actual_return_5d=0.035,
        actual_return_10d=0.055,
        direction_correct_2d=True,
        direction_correct_5d=True,
        direction_correct_10d=True,
    )
    store.save_accuracy_record(record)
    results = store.get_accuracy_records(week_start="2026-05-12")
    assert len(results) == 1
    assert results[0].actual_return_5d == 0.035
