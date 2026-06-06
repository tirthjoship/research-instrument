"""Domain exceptions for multi-modal stock recommender.

All domain-level errors inherit from DomainError.
"""

from __future__ import annotations

from datetime import datetime


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
        offending_timestamp: datetime | None = None,
        prediction_time: datetime | None = None,
    ) -> None:
        super().__init__(message)
        self.offending_timestamp = offending_timestamp
        self.prediction_time = prediction_time


class SourceThrottledError(Exception):
    """Raised by a data adapter when a source rate-limits us.

    Distinct from returning [] (genuinely no data). Callers MUST treat a
    throttle as "no observation" — never write a 0/empty value to the store
    on a throttle, or the divergence base window gets poisoned.
    """


class InsufficientDataError(DomainError):
    """Raised when too few qualified tickers or data points for pipeline."""

    pass


class StaleDataError(DomainError):
    """Raised when data exceeds maximum staleness threshold.

    Attributes:
        staleness_days: How stale the data actually is.
        max_staleness_days: Maximum allowed staleness.
    """

    def __init__(
        self,
        message: str = "",
        *,
        staleness_days: int | None = None,
        max_staleness_days: int | None = None,
    ) -> None:
        super().__init__(message)
        self.staleness_days = staleness_days
        self.max_staleness_days = max_staleness_days
