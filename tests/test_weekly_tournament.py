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
from tests.fakes.fake_buzz_discovery import FakeBuzzDiscovery
from tests.fakes.fake_sentiment import FakeSentimentScorer


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


def test_tournament_top_picks_have_positive_composite(
    tournament: WeeklyTournamentUseCase,
) -> None:
    """Top picks should be ranked by signed composite, not absolute."""
    report = tournament.execute(prediction_date=datetime(2026, 5, 1))
    for rec in report.recommendations:
        assert rec.composite_score >= 0.0 or len(report.recommendations) <= 5


def test_tournament_with_sentiment_blending() -> None:
    """WeeklyTournamentUseCase with sentiment_scorer runs and produces recommendations."""
    signals = _make_signals(5)
    tickers = [f"TICK{i:02d}" for i in range(5)]

    # Stage 2 predictor that returns a fixed blended score
    stage2 = FakePredictor([0.05])
    sentiment = FakeSentimentScorer(default_score=0.6)
    buzz_store = FakeBuzzDiscovery(signals=[])

    use_case = WeeklyTournamentUseCase(
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
        sentiment_scorer=sentiment,
        stage2_predictor=stage2,
        buzz_store=buzz_store,
    )

    report = use_case.execute(prediction_date=datetime(2026, 5, 1))

    # Should still produce recommendations
    assert len(report.recommendations) > 0
    # Stage 2 predictor was called — composite should be the blended value
    assert stage2.predict_calls, "Stage 2 predictor was never called"
    # All composites should be the stage2 output (0.05)
    for rec in report.recommendations:
        assert rec.composite_score == pytest.approx(0.05, abs=1e-6)


def test_run_tournament_cli_exits_nonzero_on_zero_picks() -> None:
    """run-tournament must exit non-zero when predictors are untrained.
    A clean exit with 0 picks is a silent lie — the command is a no-op."""
    from unittest.mock import MagicMock, patch

    from click.testing import CliRunner

    from application.cli._cli_group import cli

    runner = CliRunner()
    # Patch _build_dependencies to return a use case that produces 0 recommendations
    mock_report = MagicMock()
    mock_report.recommendations = []

    mock_use_case = MagicMock()
    mock_use_case.execute.return_value = mock_report

    with patch(
        "application.cli.ml_commands.WeeklyTournamentUseCase",
        return_value=mock_use_case,
    ):
        with patch("application.cli.ml_commands._build_dependencies") as mock_deps:
            mock_deps.return_value = {
                "config": MagicMock(),
                "market_data": MagicMock(),
                "technical_analysis": MagicMock(),
                "feature_engineer": MagicMock(),
                "predictors": {},
                "store": MagicMock(),
                "macro_symbols": {},
                "fundamental_engineer": None,
                "cross_asset_engineer": None,
                "event_causal_engineer": None,
            }
            with patch(
                "application.cli.ml_commands._get_ticker_universe",
                return_value=["AAPL"],
            ):
                result = runner.invoke(cli, ["run-tournament", "--market", "us"])

    assert result.exit_code == 1, (
        f"Expected exit code 1 (untrained/0 picks), got {result.exit_code}. "
        f"Output: {result.output}"
    )
    assert "no picks" in result.output.lower() or "not trained" in result.output.lower()


def test_tournament_without_sentiment_is_unchanged() -> None:
    """Without sentiment params, composite is purely technical (backward compatible)."""
    signals = _make_signals(5)
    tickers = [f"TICK{i:02d}" for i in range(5)]

    use_case = WeeklyTournamentUseCase(
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
        # No sentiment params — defaults to None
    )

    report = use_case.execute(prediction_date=datetime(2026, 5, 1))

    # Expected composite: 0.03*0.2 + 0.04*0.3 + 0.06*0.5 = 0.006 + 0.012 + 0.030 = 0.048
    expected = 0.03 * 0.2 + 0.04 * 0.3 + 0.06 * 0.5
    for rec in report.recommendations:
        assert rec.composite_score == pytest.approx(expected, abs=1e-6)
