"""Tests for weekly tournament use case — end-to-end pipeline."""

from datetime import datetime, timedelta

import pytest

from application.use_cases import WeeklyTournamentUseCase
from domain.models import RecommendationGrade, Signal
from tests.fakes import (
    FakeFeatureEngineer,
    FakeMarketData,
    FakePredictor,
    FakeRecommendationStore,
    FakeTechnicalAnalysis,
)


def _make_signals(n_tickers: int = 20) -> dict[str, list[Signal]]:
    import random

    random.seed(42)
    result: dict[str, list[Signal]] = {}
    tickers = [f"TICK{i:02d}" for i in range(n_tickers)]
    for sym in tickers + ["^VIX", "^TNX", "DX-Y.NYB", "^IRX", "SPY"]:
        price = 50.0 + random.random() * 200
        sigs = []
        for i in range(60):
            price = max(price + random.gauss(0, 2), 1.0)
            sigs.append(
                Signal(
                    symbol=sym,
                    timestamp=datetime(2026, 3, 1) + timedelta(days=i),
                    price=price,
                    volume=1_000_000,
                    open_=price - 1,
                    high=price + 2,
                    low=price - 2,
                )
            )
        result[sym] = sigs
    return result


@pytest.fixture
def tournament() -> WeeklyTournamentUseCase:
    signals = _make_signals(20)
    tickers = [f"TICK{i:02d}" for i in range(20)]
    return WeeklyTournamentUseCase(
        market_data=FakeMarketData(
            signals=signals,
            ticker_info={t: {"market_cap": 10e9} for t in tickers},
        ),
        technical_analysis=FakeTechnicalAnalysis(),
        feature_engineer=FakeFeatureEngineer(),
        predictors={
            "2d": FakePredictor([0.03]),
            "5d": FakePredictor([0.04]),
            "10d": FakePredictor([0.06]),
        },
        store=FakeRecommendationStore(),
        tickers=tickers,
        macro_symbols={
            "^VIX": "^VIX",
            "^TNX": "^TNX",
            "DX-Y.NYB": "DX-Y.NYB",
            "^IRX": "^IRX",
            "SPY": "SPY",
        },
        market="us",
    )


def test_tournament_produces_recommendations(
    tournament: WeeklyTournamentUseCase,
) -> None:
    report = tournament.execute(
        prediction_date=datetime(2026, 5, 1),
    )
    assert len(report.recommendations) > 0
    assert len(report.recommendations) <= 15


def test_tournament_stores_recommendations(
    tournament: WeeklyTournamentUseCase,
) -> None:
    tournament.execute(prediction_date=datetime(2026, 5, 1))
    stored = tournament._store.get_recommendations()
    assert len(stored) > 0


def test_tournament_grades_are_valid(
    tournament: WeeklyTournamentUseCase,
) -> None:
    report = tournament.execute(prediction_date=datetime(2026, 5, 1))
    for rec in report.recommendations:
        assert isinstance(rec.grade, RecommendationGrade)


def test_tournament_report_has_market(
    tournament: WeeklyTournamentUseCase,
) -> None:
    report = tournament.execute(prediction_date=datetime(2026, 5, 1))
    assert report.market == "us"
