"""Domain models for multi-modal stock recommender.

Pure Python value objects. No pandas, numpy, or external ML/data imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .exceptions import InvalidMarketDataError, InvalidPredictionError


@dataclass(frozen=True)
class Signal:
    """Immutable value object representing a market signal at a point in time.

    Attributes:
        symbol: Ticker symbol.
        timestamp: As-of time for the signal (no future data).
        price: Price at timestamp.
        volume: Volume at timestamp.
        open_: Open price (field name avoids 'open' builtin).
        high: High price.
        low: Low price.
    """

    symbol: str
    timestamp: datetime
    price: float
    volume: float
    open_: float
    high: float
    low: float

    def __post_init__(self) -> None:
        if self.price < 0 or self.volume < 0:
            raise InvalidMarketDataError("Price and volume must be non-negative")


@dataclass(frozen=True)
class Sentiment:
    """Immutable value object representing a sentiment signal.

    Attributes:
        source: Source identifier (e.g. 'news', 'twitter', 'reddit').
        timestamp: As-of time (must be <= prediction time).
        sentiment_score: Score in [-1.0, 1.0].
        confidence: Confidence in [0.0, 1.0].
        text_snippet: Optional snippet for audit.
    """

    source: str
    timestamp: datetime
    sentiment_score: float
    confidence: float
    text_snippet: str | None = None

    def __post_init__(self) -> None:
        if not -1.0 <= self.sentiment_score <= 1.0:
            raise InvalidMarketDataError(
                f"Sentiment score must be in [-1, 1], got {self.sentiment_score}"
            )
        if not 0.0 <= self.confidence <= 1.0:
            raise InvalidPredictionError(
                f"Confidence must be in [0, 1], got {self.confidence}"
            )


@dataclass(frozen=True)
class BacktestResult:
    """Immutable value object representing a single backtest run result.

    Attributes:
        run_id: Unique identifier for the run.
        symbol: Ticker symbol.
        prediction_time: Time at which prediction was made (point-in-time).
        actual_return: Realized return over the evaluation window.
        predicted_return: Model-predicted return.
        model_version: Version of the model used.
    """

    run_id: str
    symbol: str
    prediction_time: datetime
    actual_return: float
    predicted_return: float
    model_version: str

    def __post_init__(self) -> None:
        pass  # Optional: add bounds on returns if desired


class RecommendationGrade(Enum):
    """5-tier grading system for stock recommendations."""

    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    MAY_SELL = "may_sell"
    IMMEDIATE_SELL = "immediate_sell"


@dataclass(frozen=True)
class MultiHorizonPrediction:
    """Predicted returns at 2-day, 5-day, and 10-day horizons."""

    predicted_return_2d: float
    predicted_return_5d: float
    predicted_return_10d: float
    confidence_2d: float
    confidence_5d: float
    confidence_10d: float

    def __post_init__(self) -> None:
        for field_name in ("confidence_2d", "confidence_5d", "confidence_10d"):
            value = getattr(self, field_name)
            if not 0.0 <= value <= 1.0:
                raise InvalidPredictionError(
                    f"Confidence must be in [0, 1], got {value}"
                )


@dataclass(frozen=True)
class StockRecommendation:
    """A graded stock recommendation for a given week."""

    symbol: str
    week_start: str
    grade: RecommendationGrade
    composite_score: float
    prediction: MultiHorizonPrediction
    horizon_signals: dict[str, str]
    reasoning: str
    sources: list[str]
    sentiment_score: float | None = None
    divergence_score: float | None = None
    divergence_type: str | None = None
    technical_signal: float | None = None
    rsi_14: float | None = None
    macd: float | None = None


@dataclass(frozen=True)
class AccuracyRecord:
    """Historical record comparing predicted vs actual returns."""

    symbol: str
    week_start: str
    predicted_grade: str
    predicted_return_2d: float
    predicted_return_5d: float
    predicted_return_10d: float
    actual_return_2d: float
    actual_return_5d: float
    actual_return_10d: float
    direction_correct_2d: bool
    direction_correct_5d: bool
    direction_correct_10d: bool


@dataclass(frozen=True)
class EvaluationRun:
    """Record of a single evaluation metric from a validation run."""

    run_date: str
    eval_type: str
    horizon: str
    metric_name: str
    metric_value: float
    p_value: float | None = None
    regime: str | None = None
    details: str | None = None


@dataclass(frozen=True)
class WeeklyReport:
    """Aggregated weekly report with recommendations and performance."""

    report_date: str
    market: str
    recommendations: list[StockRecommendation]
    accuracy_vs_last_week: float | None = None
    spy_return_same_period: float | None = None
    max_drawdown: float | None = None
    sharpe_ratio: float | None = None
    transaction_costs: float | None = None


@dataclass(frozen=True)
class BuzzSignal:
    """A single buzz/sentiment observation from a news or social source."""

    ticker: str
    source: str  # e.g., "reuters_rss", "reddit_wsb"
    mention_count: int
    sentiment_raw: float  # [-1, 1] from keyword or Flan-T5 scorer
    scorer: str  # "keyword" or "flan_t5"
    fetched_at: datetime
    article_hash: str  # dedup key

    def __post_init__(self) -> None:
        if self.mention_count < 0:
            raise ValueError("mention_count must be >= 0")
        if not -1.0 <= self.sentiment_raw <= 1.0:
            raise ValueError("sentiment_raw must be in [-1, 1]")


@dataclass(frozen=True)
class SourceReliability:
    """Tracks per-source directional accuracy over time."""

    source: str
    ticker: str | None  # None = aggregate across all tickers
    correct_calls: int
    total_calls: int

    def __post_init__(self) -> None:
        if self.correct_calls < 0:
            raise ValueError("correct_calls must be >= 0")
        if self.total_calls < 0:
            raise ValueError("total_calls must be >= 0")
        if self.correct_calls > self.total_calls:
            raise ValueError("correct_calls cannot exceed total_calls")

    @property
    def accuracy(self) -> float:
        if self.total_calls < 10:
            return 0.5
        return self.correct_calls / self.total_calls


_VALID_SIGNAL_TYPES = frozenset(
    {"crash_risk", "negative_sentiment", "technical_breakdown", "stop_loss"}
)
_VALID_URGENCIES = frozenset({"immediate", "this_week", "watch"})


@dataclass(frozen=True)
class Holding:
    """A portfolio holding."""

    symbol: str
    quantity: float
    purchase_price: float
    purchase_date: str  # YYYY-MM-DD
    notes: str = ""

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
        if self.purchase_price <= 0:
            raise ValueError("purchase_price must be positive")


@dataclass(frozen=True)
class SellSignal:
    """A sell signal for a held stock."""

    symbol: str
    signal_date: str
    signal_type: str
    urgency: str
    reasoning: str
    confidence: float

    def __post_init__(self) -> None:
        if self.signal_type not in _VALID_SIGNAL_TYPES:
            raise ValueError(
                f"signal_type must be one of {_VALID_SIGNAL_TYPES}, got '{self.signal_type}'"
            )
        if self.urgency not in _VALID_URGENCIES:
            raise ValueError(
                f"urgency must be one of {_VALID_URGENCIES}, got '{self.urgency}'"
            )
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
