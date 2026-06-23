"""Tests for EvaluationMixin."""

from __future__ import annotations

import pytest

from adapters.data.sqlite_store import SQLiteStore
from domain.models import EvaluationRun


@pytest.fixture
def store() -> SQLiteStore:
    return SQLiteStore(":memory:")


def test_save_and_get_evaluation_run(store: SQLiteStore) -> None:
    run = EvaluationRun(
        run_date="2026-05-25",
        eval_type="walk_forward",
        horizon="5d",
        metric_name="directional_accuracy",
        metric_value=0.58,
        p_value=0.03,
    )
    store.save_evaluation_run(run)
    results = store.get_evaluation_runs(run_date="2026-05-25")
    assert len(results) == 1
    assert results[0].p_value == 0.03
