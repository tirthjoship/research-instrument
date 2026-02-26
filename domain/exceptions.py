"""Domain exceptions for multi-modal stock recommender.

All domain-level errors inherit from DomainError.
"""

from datetime import datetime
from typing import Optional


class DomainError(Exception):
    """Base exception for all domain-level errors."""

    pass


class InvalidMarketDataError(DomainError):
    """Raised when market/signal data violates business invariants."""

    pass


class InvalidPredictionError(DomainError):
    """Raised when prediction or backtest result data is invalid."""

    pass


class LookAheadBiasError(DomainError):
    """Raised when future-dated data is detected in backtesting or training.

    Ensures point-in-time access; no look-ahead leakage.

    Attributes:
        offending_timestamp: Timestamp that violated point-in-time.
        prediction_time: As-of time for the prediction.
    """

    def __init__(
        self,
        message: str = "",
        *,
        offending_timestamp: Optional[datetime] = None,
        prediction_time: Optional[datetime] = None,
    ) -> None:
        super().__init__(message)
        self.offending_timestamp = offending_timestamp
        self.prediction_time = prediction_time
