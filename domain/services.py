"""Domain services: pure business logic for stock recommendation.

No external dependencies. Point-in-time validation, grading,
feature matrix validation, and data freshness checks.
"""

from datetime import datetime, timedelta

from .conviction import SmartMoneySignal
from .exceptions import LookAheadBiasError, StaleDataError
from .models import MultiHorizonPrediction, RecommendationGrade, Sentiment, Signal

NOISE_THRESHOLDS: dict[str, float] = {
    "2d": 0.015,
    "5d": 0.020,
    "10d": 0.030,
}

FUTURE_LEAKAGE_COLUMNS: frozenset[str] = frozenset(
    {
        "next_day_return",
        "next_week_return",
        "future_earnings_surprise",
        "forward_pe_ratio",
    }
)


def validate_point_in_time_access(
    prediction_time: datetime,
    signals: list[Signal],
    sentiments: list[Sentiment],
) -> None:
    """Verify all data timestamps are <= prediction_time."""
    for s in signals:
        if s.timestamp > prediction_time:
            raise LookAheadBiasError(
                f"Signal timestamp {s.timestamp} > prediction_time {prediction_time}"
            )
    for sent in sentiments:
        if sent.timestamp > prediction_time:
            raise LookAheadBiasError(
                f"Sentiment timestamp {sent.timestamp} > prediction_time {prediction_time}"
            )


def classify_horizon(predicted_return: float, threshold: float) -> str:
    """Classify a single horizon prediction as bullish/neutral/bearish."""
    if predicted_return > threshold:
        return "bullish"
    if predicted_return < -threshold:
        return "bearish"
    return "neutral"


def grade_from_horizons(
    prediction: MultiHorizonPrediction,
) -> tuple[RecommendationGrade, dict[str, str]]:
    """Grade a multi-horizon prediction into a RecommendationGrade.

    Grading logic:
        Strong Buy: Bullish on 2+ horizons AND magnitude > 5% on longest bullish
        Buy: Bullish on 1+ horizon (no bearish)
        Hold: All neutral OR conflicting bullish+bearish signals
        May Sell: Bearish on 1 horizon only (no bullish)
        Immediate Sell: Bearish on 2+ horizons AND magnitude < -3%
    """
    signals = {
        "2d": classify_horizon(prediction.predicted_return_2d, NOISE_THRESHOLDS["2d"]),
        "5d": classify_horizon(prediction.predicted_return_5d, NOISE_THRESHOLDS["5d"]),
        "10d": classify_horizon(
            prediction.predicted_return_10d, NOISE_THRESHOLDS["10d"]
        ),
    }

    bullish_count = sum(1 for s in signals.values() if s == "bullish")
    bearish_count = sum(1 for s in signals.values() if s == "bearish")

    # Find max magnitude on longest bullish horizon
    max_bullish_magnitude = 0.0
    for horizon in ("10d", "5d", "2d"):
        if signals[horizon] == "bullish":
            max_bullish_magnitude = getattr(prediction, f"predicted_return_{horizon}")
            break

    max_bearish_magnitude = 0.0
    for horizon in ("10d", "5d", "2d"):
        if signals[horizon] == "bearish":
            max_bearish_magnitude = getattr(prediction, f"predicted_return_{horizon}")
            break

    # Conflicting signals → Hold
    if bullish_count > 0 and bearish_count > 0:
        return RecommendationGrade.HOLD, signals

    if bullish_count >= 2 and max_bullish_magnitude > 0.05:
        return RecommendationGrade.STRONG_BUY, signals
    if bullish_count >= 1:
        return RecommendationGrade.BUY, signals
    if bearish_count >= 2 and max_bearish_magnitude < -0.03:
        return RecommendationGrade.IMMEDIATE_SELL, signals
    if bearish_count >= 1:
        return RecommendationGrade.MAY_SELL, signals

    return RecommendationGrade.HOLD, signals


def validate_feature_matrix(feature_names: list[str]) -> None:
    """Verify no future-leakage columns appear in feature set."""
    leaked = set(feature_names) & FUTURE_LEAKAGE_COLUMNS
    if leaked:
        raise LookAheadBiasError(f"Future leakage columns detected: {sorted(leaked)}")


def validate_smart_money_signals(
    prediction_time: datetime,
    signals: list[SmartMoneySignal],
) -> None:
    """Verify all filing dates are <= prediction_time."""
    for signal in signals:
        filed_dt = datetime.strptime(signal.filed_date, "%Y-%m-%d")
        if filed_dt > prediction_time:
            raise LookAheadBiasError(
                f"SmartMoneySignal filed_date {signal.filed_date} > prediction_time {prediction_time}"
            )


def validate_data_freshness(
    data_timestamp: datetime,
    reference_time: datetime,
    max_staleness_days: int = 3,
) -> None:
    """Verify data is not stale relative to reference time."""
    staleness = reference_time - data_timestamp
    if staleness > timedelta(days=max_staleness_days):
        raise StaleDataError(
            f"Data is {staleness.days} days stale (max: {max_staleness_days})",
            staleness_days=staleness.days,
            max_staleness_days=max_staleness_days,
        )
