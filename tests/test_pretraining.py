"""Tests for pretraining use case — walk-forward training pipeline."""

from datetime import datetime, timedelta

import pytest

from application.use_cases import PretrainingUseCase
from domain.models import Signal
from tests.fakes import (
    FakeFeatureEngineer,
    FakeMarketData,
    FakePredictor,
    FakeRecommendationStore,
    FakeTechnicalAnalysis,
)


def _make_signal(symbol: str, day_offset: int, price: float) -> Signal:
    return Signal(
        symbol=symbol,
        timestamp=datetime(2025, 1, 2) + timedelta(days=day_offset),
        price=price,
        volume=1_000_000,
        open_=price - 1,
        high=price + 2,
        low=price - 2,
    )


@pytest.fixture
def signals() -> dict[str, list[Signal]]:
    """260 days of signals for 3 tickers + macro symbols."""
    import random

    random.seed(42)
    result: dict[str, list[Signal]] = {}
    for sym in ["AAPL", "GOOG", "MSFT", "^VIX", "^TNX", "DX-Y.NYB", "^IRX", "SPY"]:
        price = 100.0
        sigs = []
        for i in range(260):
            price = max(price + random.gauss(0, 2), 1.0)
            sigs.append(_make_signal(sym, i, price))
        result[sym] = sigs
    return result


@pytest.fixture
def pretraining_use_case(signals: dict[str, list[Signal]]) -> PretrainingUseCase:
    market_data = FakeMarketData(
        signals=signals,
        ticker_info={
            "AAPL": {"market_cap": 3e12},
            "GOOG": {"market_cap": 2e12},
            "MSFT": {"market_cap": 2.5e12},
        },
    )
    return PretrainingUseCase(
        market_data=market_data,
        technical_analysis=FakeTechnicalAnalysis(),
        feature_engineer=FakeFeatureEngineer(),
        predictors={
            "2d": FakePredictor(),
            "5d": FakePredictor(),
            "10d": FakePredictor(),
        },
        store=FakeRecommendationStore(),
        tickers=["AAPL", "GOOG", "MSFT"],
        macro_symbols={
            "^VIX": "^VIX",
            "^TNX": "^TNX",
            "DX-Y.NYB": "DX-Y.NYB",
            "^IRX": "^IRX",
            "SPY": "SPY",
        },
    )


def test_pretraining_runs_without_error(
    pretraining_use_case: PretrainingUseCase,
) -> None:
    pretraining_use_case.execute(
        start_month="2025-06",
        end_month="2025-09",
    )


def test_pretraining_trains_all_horizons(
    pretraining_use_case: PretrainingUseCase,
) -> None:
    pretraining_use_case.execute(start_month="2025-06", end_month="2025-09")
    for horizon in ("2d", "5d", "10d"):
        predictor = pretraining_use_case._predictors[horizon]
        assert len(predictor.fit_calls) > 0


def test_pretraining_stores_evaluation_runs(
    pretraining_use_case: PretrainingUseCase,
) -> None:
    pretraining_use_case.execute(start_month="2025-06", end_month="2025-09")
    runs = pretraining_use_case._store.get_evaluation_runs()
    assert len(runs) > 0
