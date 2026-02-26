"""Port interfaces (protocols) for multi-modal stock recommender.

Adapters implement these ports; domain and application depend only
on these abstractions. Ports support point-in-time access and leakage pruning.
"""

from datetime import datetime
from typing import Protocol

from .models import BacktestResult, Sentiment, Signal


class MarketDataPort(Protocol):
    """Port: load market data with point-in-time and leakage prevention.

    Implementations must ensure only data with timestamp <= prediction_time
    is exposed. Raise LookAheadBiasError if future-dated data is detected.
    """

    def get_signals(
        self,
        symbol: str,
        prediction_time: datetime,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[Signal]:
        """Return market signals for symbol up to prediction_time only.

        Args:
            symbol: Ticker symbol.
            prediction_time: No data after this time may be included.
            start_date: Optional start filter.
            end_date: Optional end filter (must be <= prediction_time).

        Returns:
            List of Signal objects with timestamps <= prediction_time.

        Raises:
            LookAheadBiasError: If any signal has timestamp > prediction_time.
            InvalidMarketDataError: If data fails validation.
        """
        ...

    def validate_point_in_time(self, prediction_time: datetime) -> None:
        """Validate that no future-dated data is exposed for this prediction time.

        Raises:
            LookAheadBiasError: If future leakage is detected.
        """
        ...


class SentimentPort(Protocol):
    """Port: extract sentiment signals with temporal alignment.

    Implementations must ensure sentiment timestamps align with market data
    and never exceed prediction time.
    """

    def get_sentiment(
        self,
        symbol: str,
        prediction_time: datetime,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[Sentiment]:
        """Return sentiment signals for symbol up to prediction_time only.

        Raises:
            LookAheadBiasError: If any sentiment has timestamp > prediction_time.
        """
        ...


class StockPredictorPort(Protocol):
    """Port: ML model that predicts stock performance.

    Must use only point-in-time features (signals and sentiment up to prediction time).
    """

    def predict(self, symbol: str, signals: list[Signal], sentiments: list[Sentiment]) -> float:
        """Predict return or score for symbol given point-in-time features.

        Args:
            symbol: Ticker symbol.
            signals: Market signals with timestamps <= prediction time.
            sentiments: Sentiment signals with timestamps <= prediction time.

        Returns:
            Predicted return or score.
        """
        ...


class BacktestResultPort(Protocol):
    """Port: persist and retrieve backtest results for recursive learning."""

    def save_result(self, result: BacktestResult) -> None:
        """Persist a backtest result."""
        ...

    def get_results(
        self,
        symbol: str | None = None,
        model_version: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[BacktestResult]:
        """Retrieve backtest results matching filters."""
        ...
