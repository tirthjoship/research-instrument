"""Tests for domain services."""

from datetime import datetime, timedelta

import pytest

from domain.exceptions import LookAheadBiasError, StaleDataError
from domain.models import MultiHorizonPrediction, RecommendationGrade, Sentiment, Signal
from domain.services import (
    classify_horizon,
    grade_from_horizons,
    validate_data_freshness,
    validate_feature_matrix,
    validate_point_in_time_access,
)

# --- classify_horizon ---


def test_classify_horizon_bullish() -> None:
    assert classify_horizon(0.025, 0.015) == "bullish"


def test_classify_horizon_bearish() -> None:
    assert classify_horizon(-0.025, 0.015) == "bearish"


def test_classify_horizon_neutral_positive() -> None:
    assert classify_horizon(0.010, 0.015) == "neutral"


def test_classify_horizon_neutral_negative() -> None:
    assert classify_horizon(-0.010, 0.015) == "neutral"


def test_classify_horizon_at_threshold_is_neutral() -> None:
    assert classify_horizon(0.015, 0.015) == "neutral"
    assert classify_horizon(-0.015, 0.015) == "neutral"


# --- grade_from_horizons ---


def test_grade_strong_buy() -> None:
    pred = MultiHorizonPrediction(
        predicted_return_2d=0.03,
        predicted_return_5d=0.04,
        predicted_return_10d=0.06,
        confidence_2d=0.8,
        confidence_5d=0.7,
        confidence_10d=0.7,
    )
    grade, signals = grade_from_horizons(pred)
    assert grade == RecommendationGrade.STRONG_BUY
    assert signals["10d"] == "bullish"


def test_grade_buy_one_horizon_bullish() -> None:
    pred = MultiHorizonPrediction(
        predicted_return_2d=0.025,
        predicted_return_5d=0.005,
        predicted_return_10d=0.01,
        confidence_2d=0.7,
        confidence_5d=0.5,
        confidence_10d=0.5,
    )
    grade, signals = grade_from_horizons(pred)
    assert grade == RecommendationGrade.BUY
    assert signals["2d"] == "bullish"
    assert signals["5d"] == "neutral"


def test_grade_buy_two_horizons_low_magnitude() -> None:
    pred = MultiHorizonPrediction(
        predicted_return_2d=0.02,
        predicted_return_5d=0.03,
        predicted_return_10d=0.04,
        confidence_2d=0.7,
        confidence_5d=0.7,
        confidence_10d=0.7,
    )
    grade, _ = grade_from_horizons(pred)
    assert grade == RecommendationGrade.BUY


def test_grade_hold_all_neutral() -> None:
    pred = MultiHorizonPrediction(
        predicted_return_2d=0.005,
        predicted_return_5d=0.01,
        predicted_return_10d=0.02,
        confidence_2d=0.5,
        confidence_5d=0.5,
        confidence_10d=0.5,
    )
    grade, signals = grade_from_horizons(pred)
    assert grade == RecommendationGrade.HOLD
    assert all(s == "neutral" for s in signals.values())


def test_grade_hold_conflicting_signals() -> None:
    pred = MultiHorizonPrediction(
        predicted_return_2d=0.03,
        predicted_return_5d=-0.04,
        predicted_return_10d=0.01,
        confidence_2d=0.7,
        confidence_5d=0.7,
        confidence_10d=0.5,
    )
    grade, signals = grade_from_horizons(pred)
    assert grade == RecommendationGrade.HOLD
    assert signals["2d"] == "bullish"
    assert signals["5d"] == "bearish"


def test_grade_may_sell() -> None:
    pred = MultiHorizonPrediction(
        predicted_return_2d=0.005,
        predicted_return_5d=-0.025,
        predicted_return_10d=0.01,
        confidence_2d=0.5,
        confidence_5d=0.7,
        confidence_10d=0.5,
    )
    grade, _ = grade_from_horizons(pred)
    assert grade == RecommendationGrade.MAY_SELL


def test_grade_immediate_sell() -> None:
    pred = MultiHorizonPrediction(
        predicted_return_2d=-0.025,
        predicted_return_5d=-0.04,
        predicted_return_10d=-0.06,
        confidence_2d=0.8,
        confidence_5d=0.8,
        confidence_10d=0.8,
    )
    grade, signals = grade_from_horizons(pred)
    assert grade == RecommendationGrade.IMMEDIATE_SELL
    assert signals["2d"] == "bearish"
    assert signals["5d"] == "bearish"


def test_grade_returns_horizon_signals_dict() -> None:
    pred = MultiHorizonPrediction(
        predicted_return_2d=0.03,
        predicted_return_5d=0.04,
        predicted_return_10d=0.06,
        confidence_2d=0.8,
        confidence_5d=0.7,
        confidence_10d=0.7,
    )
    _, signals = grade_from_horizons(pred)
    assert set(signals.keys()) == {"2d", "5d", "10d"}
    assert all(s in ("bullish", "bearish", "neutral") for s in signals.values())


# --- validate_feature_matrix ---


def test_validate_feature_matrix_clean() -> None:
    validate_feature_matrix(["rsi_14", "macd", "volume_ratio_20d"])


def test_validate_feature_matrix_detects_next_day_return() -> None:
    with pytest.raises(LookAheadBiasError, match="next_day_return"):
        validate_feature_matrix(["rsi_14", "next_day_return", "macd"])


def test_validate_feature_matrix_detects_multiple_leaks() -> None:
    with pytest.raises(LookAheadBiasError):
        validate_feature_matrix(["next_day_return", "forward_pe_ratio", "rsi_14"])


def test_validate_feature_matrix_all_leakage_columns() -> None:
    for col in [
        "next_day_return",
        "next_week_return",
        "future_earnings_surprise",
        "forward_pe_ratio",
    ]:
        with pytest.raises(LookAheadBiasError):
            validate_feature_matrix([col])


# --- validate_data_freshness ---


def test_validate_data_freshness_pass() -> None:
    ref = datetime(2026, 5, 25, 12, 0)
    data_ts = datetime(2026, 5, 24, 12, 0)
    validate_data_freshness(data_ts, ref, max_staleness_days=3)


def test_validate_data_freshness_exactly_at_limit() -> None:
    ref = datetime(2026, 5, 25, 12, 0)
    data_ts = datetime(2026, 5, 22, 12, 0)
    validate_data_freshness(data_ts, ref, max_staleness_days=3)


def test_validate_data_freshness_stale_raises() -> None:
    ref = datetime(2026, 5, 25, 12, 0)
    data_ts = datetime(2026, 5, 20, 12, 0)
    with pytest.raises(StaleDataError):
        validate_data_freshness(data_ts, ref, max_staleness_days=3)


# --- validate_point_in_time_access (existing tests preserved) ---


def test_validate_point_in_time_pass() -> None:
    pt = datetime.now()
    signals = [
        Signal(
            symbol="AAPL",
            timestamp=pt - timedelta(days=1),
            price=100.0,
            volume=1000.0,
            open_=99.0,
            high=101.0,
            low=98.0,
        )
    ]
    sentiments = [
        Sentiment(
            source="news",
            timestamp=pt - timedelta(hours=1),
            sentiment_score=0.0,
            confidence=1.0,
        )
    ]
    validate_point_in_time_access(pt, signals, sentiments)


def test_validate_point_in_time_future_signal_raises() -> None:
    pt = datetime.now()
    signals = [
        Signal(
            symbol="AAPL",
            timestamp=pt + timedelta(days=1),
            price=100.0,
            volume=1000.0,
            open_=99.0,
            high=101.0,
            low=98.0,
        )
    ]
    with pytest.raises(LookAheadBiasError):
        validate_point_in_time_access(pt, signals, [])
