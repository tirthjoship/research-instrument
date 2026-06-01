"""Tests for SentimentFeatureEngineer — 14 sentiment/buzz/divergence features.

TDD: tests written before implementation.
"""

from __future__ import annotations

import math
from datetime import datetime

from adapters.ml.sentiment_feature_engineer import (
    SENTIMENT_FEATURE_NAMES,
    SentimentFeatureEngineer,
)
from domain.models import BuzzSignal, Sentiment, SourceReliability

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_NOW = datetime(2024, 1, 15, 12, 0, 0)


def _make_buzz(source: str = "reuters_rss", sentiment: float = 0.5) -> BuzzSignal:
    return BuzzSignal(
        ticker="AAPL",
        source=source,
        mention_count=1,
        sentiment_raw=sentiment,
        scorer="keyword",
        fetched_at=_NOW,
        article_hash="abc123",
    )


def _make_sentiment(source: str = "rss_news", score: float = 0.5) -> Sentiment:
    return Sentiment(
        source=source,
        timestamp=_NOW,
        sentiment_score=score,
        confidence=0.8,
    )


def _make_reliability(correct: int = 9, total: int = 10) -> SourceReliability:
    return SourceReliability(
        source="reuters_rss",
        ticker="AAPL",
        correct_calls=correct,
        total_calls=total,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_feature_count() -> None:
    """SENTIMENT_FEATURE_NAMES must contain exactly 24 features (14 original + 10 Phase 3.5)."""
    assert len(SENTIMENT_FEATURE_NAMES) == 24


def test_compute_returns_all_features() -> None:
    """compute() must return a dict containing all 14 feature names."""
    engineer = SentimentFeatureEngineer()
    buzz = [_make_buzz()]
    sentiments = [_make_sentiment()]
    reliability = _make_reliability()

    result = engineer.compute(
        keyword_sentiment=0.5,
        flan_t5_sentiment=0.4,
        sentiments=sentiments,
        buzz_signals_current=buzz,
        buzz_signals_prior=buzz,
        sector_buzz_total=10,
        reliability=reliability,
        price_return_5d=0.02,
    )

    for name in SENTIMENT_FEATURE_NAMES:
        assert name in result, f"Missing feature: {name}"


def test_buzz_acceleration_positive_when_growing() -> None:
    """10 current vs 3 prior signals → buzz_acceleration > 0."""
    engineer = SentimentFeatureEngineer()
    current = [_make_buzz() for _ in range(10)]
    prior = [_make_buzz() for _ in range(3)]

    result = engineer.compute(
        keyword_sentiment=0.0,
        flan_t5_sentiment=0.0,
        sentiments=[],
        buzz_signals_current=current,
        buzz_signals_prior=prior,
        sector_buzz_total=20,
        reliability=_make_reliability(),
        price_return_5d=0.0,
    )

    assert result["buzz_acceleration"] > 0.0


def test_sentiment_price_divergence_flag() -> None:
    """Positive sentiment + negative price return → divergence flag = 1.0."""
    engineer = SentimentFeatureEngineer()
    sentiments = [_make_sentiment(score=0.8)]

    result = engineer.compute(
        keyword_sentiment=0.8,
        flan_t5_sentiment=0.8,
        sentiments=sentiments,
        buzz_signals_current=[_make_buzz(sentiment=0.8)],
        buzz_signals_prior=[_make_buzz()],
        sector_buzz_total=10,
        reliability=_make_reliability(),
        price_return_5d=-0.05,
    )

    assert result["sentiment_price_divergence_flag"] == 1.0


def test_sentiment_price_divergence_magnitude() -> None:
    """Diverging sentiment and price → magnitude > 0."""
    engineer = SentimentFeatureEngineer()
    sentiments = [_make_sentiment(score=0.8)]

    result = engineer.compute(
        keyword_sentiment=0.8,
        flan_t5_sentiment=0.8,
        sentiments=sentiments,
        buzz_signals_current=[_make_buzz(sentiment=0.8)],
        buzz_signals_prior=[_make_buzz()],
        sector_buzz_total=10,
        reliability=_make_reliability(),
        price_return_5d=-0.05,
    )

    assert result["sentiment_price_divergence_magnitude"] > 0.0


def test_no_divergence_when_aligned() -> None:
    """Both positive → divergence flag = 0.0, magnitude = 0.0."""
    engineer = SentimentFeatureEngineer()
    sentiments = [_make_sentiment(score=0.8)]

    result = engineer.compute(
        keyword_sentiment=0.8,
        flan_t5_sentiment=0.8,
        sentiments=sentiments,
        buzz_signals_current=[_make_buzz(sentiment=0.8)],
        buzz_signals_prior=[_make_buzz()],
        sector_buzz_total=10,
        reliability=_make_reliability(),
        price_return_5d=0.05,
    )

    assert result["sentiment_price_divergence_flag"] == 0.0
    assert result["sentiment_price_divergence_magnitude"] == 0.0


def test_source_weighted_sentiment() -> None:
    """avg((0.6 + 0.8) / 2) * accuracy(9/10 = 0.9) = 0.63."""
    engineer = SentimentFeatureEngineer()
    sentiments = [
        _make_sentiment(score=0.6),
        _make_sentiment(score=0.8),
    ]
    reliability = _make_reliability(correct=9, total=10)

    result = engineer.compute(
        keyword_sentiment=0.7,
        flan_t5_sentiment=0.7,
        sentiments=sentiments,
        buzz_signals_current=[_make_buzz()],
        buzz_signals_prior=[_make_buzz()],
        sector_buzz_total=10,
        reliability=reliability,
        price_return_5d=0.02,
    )

    assert abs(result["source_weighted_sentiment"] - 0.63) < 1e-9


def test_nan_when_no_data() -> None:
    """Empty sentiments + NaN inputs → NaN for sentiment-dependent features."""
    engineer = SentimentFeatureEngineer()

    result = engineer.compute(
        keyword_sentiment=float("nan"),
        flan_t5_sentiment=float("nan"),
        sentiments=[],
        buzz_signals_current=[],
        buzz_signals_prior=[],
        sector_buzz_total=0,
        reliability=_make_reliability(correct=0, total=0),
        price_return_5d=float("nan"),
    )

    assert math.isnan(result["sentiment_agreement"])
    assert math.isnan(result["source_weighted_sentiment"])
    assert math.isnan(result["sector_buzz_ratio"])
    assert math.isnan(result["sentiment_price_divergence_flag"])
