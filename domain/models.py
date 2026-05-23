"""Domain models for multi-modal stock recommender.

Pure Python value objects. No pandas, numpy, or external ML/data imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

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
