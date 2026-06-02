"""Integration test — data loader reads real SQLite fixtures and returns correct types."""

from __future__ import annotations

import json
import pathlib

import pytest

from adapters.data.sqlite_store import SQLiteStore
from adapters.visualization.data_loader import (
    load_backtest_reports,
    load_holdings,
    load_recommendations,
    load_watchlist,
)
from domain.models import (
    Holding,
    MultiHorizonPrediction,
    RecommendationGrade,
    StockRecommendation,
)


@pytest.fixture()
def populated_db(tmp_path: pathlib.Path) -> str:
    """Create a populated test database."""
    db_path = str(tmp_path / "test.db")
    store = SQLiteStore(db_path)

    rec = StockRecommendation(
        symbol="NVDA",
        week_start="2026-06-01",
        grade=RecommendationGrade.STRONG_BUY,
        composite_score=0.85,
        prediction=MultiHorizonPrediction(
            predicted_return_2d=0.01,
            predicted_return_5d=0.032,
            predicted_return_10d=0.05,
            confidence_2d=0.7,
            confidence_5d=0.82,
            confidence_10d=0.75,
        ),
        horizon_signals={"2d": "bullish", "5d": "bullish", "10d": "bullish"},
        reasoning="Strong earnings + upstream leader signal",
        sources=["yfinance", "rss"],
        sentiment_score=0.65,
        divergence_score=0.3,
        divergence_type="bullish_divergence",
        technical_signal=0.5,
        rsi_14=45.0,
        macd=0.5,
    )
    store.save_recommendation(rec)

    store.add_holding(
        Holding(
            symbol="AAPL",
            quantity=10,
            purchase_price=150.0,
            purchase_date="2026-01-15",
            notes="core position",
        )
    )

    store.add_watchlist("TSLA", notes="momentum play")

    return db_path


@pytest.fixture()
def reports_dir(tmp_path: pathlib.Path) -> str:
    """Create test backtest reports."""
    report = {
        "horizons": {
            "5d": {
                "avg_directional_accuracy": 0.52,
                "n_folds": 19,
                "n_total_predictions": 760,
                "min_accuracy": 0.40,
                "max_accuracy": 0.65,
                "p_value_vs_random": 0.15,
            }
        }
    }
    (tmp_path / "backtest_report_20260601.json").write_text(json.dumps(report))
    return str(tmp_path)


def test_full_data_pipeline(populated_db: str, reports_dir: str) -> None:
    """End-to-end: data loader reads all types from fixtures."""
    recs = load_recommendations(populated_db)
    assert len(recs) == 1
    assert recs[0].symbol == "NVDA"
    assert recs[0].grade == RecommendationGrade.STRONG_BUY

    holdings = load_holdings(populated_db)
    assert len(holdings) == 1
    assert holdings[0].symbol == "AAPL"

    watchlist = load_watchlist(populated_db)
    assert len(watchlist) == 1
    assert watchlist[0]["symbol"] == "TSLA"

    reports = load_backtest_reports(reports_dir)
    assert len(reports) == 1
    assert reports[0]["horizons"]["5d"]["avg_directional_accuracy"] == 0.52
