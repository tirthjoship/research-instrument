"""Skeleton tests for domain services (point-in-time validation)."""

from datetime import datetime, timedelta

import pytest

from domain.exceptions import LookAheadBiasError
from domain.models import Sentiment, Signal
from domain.services import validate_point_in_time_access


def test_validate_point_in_time_pass() -> None:
    """All timestamps <= prediction_time passes."""
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
        ),
    ]
    sentiments = [
        Sentiment(
            source="news",
            timestamp=pt - timedelta(hours=1),
            sentiment_score=0.0,
            confidence=1.0,
        ),
    ]
    validate_point_in_time_access(pt, signals, sentiments)


def test_validate_point_in_time_future_signal_raises() -> None:
    """Signal with timestamp > prediction_time raises LookAheadBiasError."""
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
        ),
    ]
    with pytest.raises(LookAheadBiasError):
        validate_point_in_time_access(pt, signals, [])
