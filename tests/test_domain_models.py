"""Skeleton tests for domain models (Signal, Sentiment, BacktestResult)."""

from datetime import datetime

import pytest

from domain.exceptions import InvalidMarketDataError, InvalidPredictionError
from domain.models import Signal, Sentiment, BacktestResult


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
