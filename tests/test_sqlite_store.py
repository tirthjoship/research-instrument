"""Tests for SQLite recommendation store (in-memory)."""

import pytest

from adapters.data.sqlite_store import SQLiteStore
from domain.models import (
    AccuracyRecord,
    EvaluationRun,
    MultiHorizonPrediction,
    RecommendationGrade,
    StockRecommendation,
    WeeklyReport,
)


@pytest.fixture
def store() -> SQLiteStore:
    return SQLiteStore(":memory:")


@pytest.fixture
def sample_rec() -> StockRecommendation:
    pred = MultiHorizonPrediction(
        predicted_return_2d=0.03,
        predicted_return_5d=0.04,
        predicted_return_10d=0.06,
        confidence_2d=0.8,
        confidence_5d=0.7,
        confidence_10d=0.6,
    )
    return StockRecommendation(
        symbol="AAPL",
        week_start="2026-05-19",
        grade=RecommendationGrade.STRONG_BUY,
        composite_score=0.85,
        prediction=pred,
        horizon_signals={"2d": "bullish", "5d": "bullish", "10d": "bullish"},
        reasoning="Strong momentum",
        sources=["yfinance"],
        rsi_14=65.0,
        macd=1.2,
    )


def test_save_and_get_recommendation(
    store: SQLiteStore, sample_rec: StockRecommendation
) -> None:
    store.save_recommendation(sample_rec)
    results = store.get_recommendations(week_start="2026-05-19")
    assert len(results) == 1
    assert results[0].symbol == "AAPL"
    assert results[0].grade == RecommendationGrade.STRONG_BUY
    assert results[0].prediction.predicted_return_10d == 0.06


def test_get_recommendations_by_symbol(
    store: SQLiteStore, sample_rec: StockRecommendation
) -> None:
    store.save_recommendation(sample_rec)
    assert len(store.get_recommendations(symbol="AAPL")) == 1
    assert len(store.get_recommendations(symbol="GOOG")) == 0


def test_upsert_recommendation(
    store: SQLiteStore, sample_rec: StockRecommendation
) -> None:
    """Same symbol+week_start overwrites."""
    store.save_recommendation(sample_rec)
    store.save_recommendation(sample_rec)
    results = store.get_recommendations(week_start="2026-05-19")
    assert len(results) == 1


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


def test_save_and_get_weekly_report(
    store: SQLiteStore, sample_rec: StockRecommendation
) -> None:
    report = WeeklyReport(
        report_date="2026-05-19",
        market="us",
        recommendations=[sample_rec],
        spy_return_same_period=0.012,
        sharpe_ratio=1.5,
    )
    store.save_weekly_report(report)
    loaded = store.get_weekly_report("2026-05-19")
    assert loaded is not None
    assert loaded.market == "us"
    assert loaded.sharpe_ratio == 1.5


def test_get_missing_weekly_report_returns_none(store: SQLiteStore) -> None:
    assert store.get_weekly_report("2026-01-01") is None
