"""Tests for domain models and exceptions."""

from datetime import datetime

import pytest

from domain.exceptions import (
    DomainError,
    InsufficientDataError,
    InvalidMarketDataError,
    InvalidPredictionError,
    StaleDataError,
)
from domain.models import (
    AccuracyRecord,
    BacktestResult,
    EvaluationRun,
    MultiHorizonPrediction,
    RecommendationGrade,
    Sentiment,
    Signal,
    StockRecommendation,
    WeeklyReport,
)


# --- Existing model tests ---


def test_signal_valid_creation() -> None:
    """Valid Signal is created."""
    s = Signal(
        symbol="AAPL",
        timestamp=datetime.now(),
        price=150.0,
        volume=1_000_000.0,
        open_=149.0,
        high=151.0,
        low=148.0,
    )
    assert s.symbol == "AAPL"
    assert s.price == 150.0


def test_signal_negative_price_raises() -> None:
    """Negative price raises InvalidMarketDataError."""
    with pytest.raises(InvalidMarketDataError):
        Signal(
            symbol="AAPL",
            timestamp=datetime.now(),
            price=-1.0,
            volume=1000.0,
            open_=100.0,
            high=101.0,
            low=99.0,
        )


def test_sentiment_valid_creation() -> None:
    """Valid Sentiment is created."""
    s = Sentiment(
        source="news",
        timestamp=datetime.now(),
        sentiment_score=0.2,
        confidence=0.9,
    )
    assert s.sentiment_score == 0.2
    assert s.confidence == 0.9


def test_sentiment_score_out_of_bounds_raises() -> None:
    """Sentiment score outside [-1, 1] raises InvalidMarketDataError."""
    with pytest.raises(InvalidMarketDataError):
        Sentiment(
            source="news",
            timestamp=datetime.now(),
            sentiment_score=1.5,
            confidence=0.8,
        )


def test_backtest_result_valid_creation() -> None:
    """Valid BacktestResult is created."""
    r = BacktestResult(
        run_id="R001",
        symbol="AAPL",
        prediction_time=datetime.now(),
        actual_return=0.02,
        predicted_return=0.015,
        model_version="v1.0",
    )
    assert r.run_id == "R001"
    assert r.symbol == "AAPL"


# --- Task 1: Exception tests ---


def test_insufficient_data_error_is_domain_error() -> None:
    err = InsufficientDataError("only 3 tickers")
    assert isinstance(err, DomainError)
    assert str(err) == "only 3 tickers"


def test_stale_data_error_is_domain_error() -> None:
    err = StaleDataError("data is 5 days stale")
    assert isinstance(err, DomainError)
    assert str(err) == "data is 5 days stale"


def test_stale_data_error_attributes() -> None:
    err = StaleDataError("stale", staleness_days=5, max_staleness_days=3)
    assert err.staleness_days == 5
    assert err.max_staleness_days == 3


# --- Task 2: RecommendationGrade + MultiHorizonPrediction ---


def test_recommendation_grade_ordering() -> None:
    assert RecommendationGrade.STRONG_BUY.value == "strong_buy"
    assert RecommendationGrade.BUY.value == "buy"
    assert RecommendationGrade.HOLD.value == "hold"
    assert RecommendationGrade.MAY_SELL.value == "may_sell"
    assert RecommendationGrade.IMMEDIATE_SELL.value == "immediate_sell"


def test_recommendation_grade_all_values() -> None:
    assert len(RecommendationGrade) == 5


def test_multi_horizon_prediction_valid() -> None:
    pred = MultiHorizonPrediction(
        predicted_return_2d=0.02,
        predicted_return_5d=0.03,
        predicted_return_10d=0.05,
        confidence_2d=0.8,
        confidence_5d=0.7,
        confidence_10d=0.6,
    )
    assert pred.predicted_return_2d == 0.02
    assert pred.confidence_10d == 0.6


def test_multi_horizon_prediction_confidence_below_zero_raises() -> None:
    with pytest.raises(InvalidPredictionError, match="Confidence must be in"):
        MultiHorizonPrediction(
            predicted_return_2d=0.02,
            predicted_return_5d=0.03,
            predicted_return_10d=0.05,
            confidence_2d=-0.1,
            confidence_5d=0.7,
            confidence_10d=0.6,
        )


def test_multi_horizon_prediction_confidence_above_one_raises() -> None:
    with pytest.raises(InvalidPredictionError, match="Confidence must be in"):
        MultiHorizonPrediction(
            predicted_return_2d=0.02,
            predicted_return_5d=0.03,
            predicted_return_10d=0.05,
            confidence_2d=0.8,
            confidence_5d=1.5,
            confidence_10d=0.6,
        )


def test_multi_horizon_prediction_is_frozen() -> None:
    pred = MultiHorizonPrediction(
        predicted_return_2d=0.02,
        predicted_return_5d=0.03,
        predicted_return_10d=0.05,
        confidence_2d=0.8,
        confidence_5d=0.7,
        confidence_10d=0.6,
    )
    with pytest.raises(AttributeError):
        pred.predicted_return_2d = 0.99  # type: ignore[misc]


def test_multi_horizon_prediction_negative_returns_allowed() -> None:
    pred = MultiHorizonPrediction(
        predicted_return_2d=-0.05,
        predicted_return_5d=-0.08,
        predicted_return_10d=-0.12,
        confidence_2d=0.9,
        confidence_5d=0.8,
        confidence_10d=0.7,
    )
    assert pred.predicted_return_2d == -0.05


# --- Task 3: StockRecommendation + AccuracyRecord + EvaluationRun + WeeklyReport ---


def test_stock_recommendation_valid() -> None:
    pred = MultiHorizonPrediction(
        predicted_return_2d=0.03,
        predicted_return_5d=0.04,
        predicted_return_10d=0.06,
        confidence_2d=0.8,
        confidence_5d=0.7,
        confidence_10d=0.6,
    )
    rec = StockRecommendation(
        symbol="AAPL",
        week_start="2026-05-19",
        grade=RecommendationGrade.STRONG_BUY,
        composite_score=0.85,
        prediction=pred,
        horizon_signals={"2d": "bullish", "5d": "bullish", "10d": "bullish"},
        reasoning="Strong momentum across all horizons",
        sources=["yfinance"],
    )
    assert rec.symbol == "AAPL"
    assert rec.grade == RecommendationGrade.STRONG_BUY
    assert rec.prediction.predicted_return_10d == 0.06
    assert rec.sentiment_score is None


def test_stock_recommendation_is_frozen() -> None:
    pred = MultiHorizonPrediction(
        predicted_return_2d=0.01,
        predicted_return_5d=0.02,
        predicted_return_10d=0.03,
        confidence_2d=0.5,
        confidence_5d=0.5,
        confidence_10d=0.5,
    )
    rec = StockRecommendation(
        symbol="GOOG",
        week_start="2026-05-19",
        grade=RecommendationGrade.HOLD,
        composite_score=0.5,
        prediction=pred,
        horizon_signals={"2d": "neutral", "5d": "neutral", "10d": "neutral"},
        reasoning="Flat",
        sources=["yfinance"],
    )
    with pytest.raises(AttributeError):
        rec.symbol = "MSFT"  # type: ignore[misc]


def test_accuracy_record_valid() -> None:
    record = AccuracyRecord(
        symbol="AAPL",
        week_start="2026-05-19",
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
    assert record.direction_correct_2d is True
    assert record.actual_return_5d == 0.035


def test_evaluation_run_valid() -> None:
    run = EvaluationRun(
        run_date="2026-05-25",
        eval_type="walk_forward",
        horizon="5d",
        metric_name="directional_accuracy",
        metric_value=0.58,
        p_value=0.03,
    )
    assert run.eval_type == "walk_forward"
    assert run.p_value == 0.03
    assert run.regime is None


def test_evaluation_run_with_regime() -> None:
    run = EvaluationRun(
        run_date="2026-05-25",
        eval_type="regime",
        horizon="10d",
        metric_name="directional_accuracy",
        metric_value=0.62,
        regime="bull",
    )
    assert run.regime == "bull"


def test_weekly_report_valid() -> None:
    pred = MultiHorizonPrediction(
        predicted_return_2d=0.02,
        predicted_return_5d=0.03,
        predicted_return_10d=0.04,
        confidence_2d=0.8,
        confidence_5d=0.7,
        confidence_10d=0.6,
    )
    rec = StockRecommendation(
        symbol="AAPL",
        week_start="2026-05-19",
        grade=RecommendationGrade.BUY,
        composite_score=0.7,
        prediction=pred,
        horizon_signals={"2d": "bullish", "5d": "neutral", "10d": "bullish"},
        reasoning="test",
        sources=["yfinance"],
    )
    report = WeeklyReport(
        report_date="2026-05-19",
        market="us",
        recommendations=[rec],
    )
    assert report.market == "us"
    assert len(report.recommendations) == 1
    assert report.spy_return_same_period is None


def test_ports_importable() -> None:
    from domain.ports import (
        BacktestResultPort, FeatureEngineerPort, MarketDataPort,
        RecommendationStorePort, SentimentPort, StockPredictorPort,
        TechnicalAnalysisPort,
    )
    assert TechnicalAnalysisPort is not None
    assert RecommendationStorePort is not None
    assert FeatureEngineerPort is not None


# --- Task 7: Market configuration ---


def test_load_us_market_config() -> None:
    from config.loader import load_market_config
    config = load_market_config("us")
    assert config["market"] == "us"
    assert config["macro_symbols"]["vix"] == "^VIX"
    assert config["horizons"]["5d"]["noise_threshold"] == 0.020


def test_load_missing_market_raises() -> None:
    from config.loader import load_market_config
    with pytest.raises(FileNotFoundError):
        load_market_config("nonexistent")


def test_fakes_implement_protocols() -> None:
    from tests.fakes import (
        FakeFeatureEngineer, FakeMarketData, FakePredictor,
        FakeRecommendationStore, FakeTechnicalAnalysis,
    )
    FakeMarketData()
    FakeTechnicalAnalysis()
    FakeRecommendationStore()
    FakeFeatureEngineer()
    FakePredictor()
