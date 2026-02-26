"""Domain services: pure business logic for stock recommendation.

No external dependencies. Point-in-time validation only.
"""

from datetime import datetime

from .exceptions import LookAheadBiasError
from .models import Sentiment, Signal


def validate_point_in_time_access(
    prediction_time: datetime,
    signals: list[Signal],
    sentiments: list[Sentiment],
) -> None:
    """Verify all data timestamps are <= prediction_time.

    Raises:
        LookAheadBiasError: If any signal or sentiment is after prediction_time.
    """
    for s in signals:
        if s.timestamp > prediction_time:
            raise LookAheadBiasError(
                f"Signal timestamp {s.timestamp} > prediction_time {prediction_time}"
            )
    for s in sentiments:
        if s.timestamp > prediction_time:
            raise LookAheadBiasError(
                f"Sentiment timestamp {s.timestamp} > prediction_time {prediction_time}"
            )
