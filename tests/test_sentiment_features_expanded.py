"""Tests for Phase 3.5 expanded sentiment features (10 new features)."""

from __future__ import annotations

import math
from datetime import datetime, timezone

import pytest

from adapters.ml.sentiment_feature_engineer import (
    SENTIMENT_FEATURE_NAMES,
    SentimentFeatureEngineer,
)
from domain.models import BuzzSignal, Sentiment, SourceReliability

_NOW = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_buzz(source: str, sentiment: float = 0.5, count: int = 1) -> BuzzSignal:
    return BuzzSignal(
        ticker="AAPL",
        source=source,
        mention_count=count,
        sentiment_raw=sentiment,
        scorer="keyword",
        fetched_at=_NOW,
        article_hash=f"hash_{source}",
    )


def _make_sentiment(source: str = "gdelt_reuters.com", score: float = 0.3) -> Sentiment:
    return Sentiment(
        source=source,
        timestamp=_NOW,
        sentiment_score=score,
        confidence=0.6,
    )


def _default_reliability() -> SourceReliability:
    return SourceReliability(
        source="reuters_rss", ticker="AAPL", correct_calls=9, total_calls=10
    )


def _base_kwargs() -> dict:
    """Minimal required args for compute()."""
    return dict(
        keyword_sentiment=0.5,
        flan_t5_sentiment=0.5,
        sentiments=[_make_sentiment()],
        buzz_signals_current=[_make_buzz("reuters_rss")],
        buzz_signals_prior=[_make_buzz("reuters_rss")],
        sector_buzz_total=10,
        reliability=_default_reliability(),
        price_return_5d=0.02,
    )


@pytest.fixture()
def engineer() -> SentimentFeatureEngineer:
    return SentimentFeatureEngineer()


# --- Feature count ---


def test_feature_names_total_24() -> None:
    assert len(SENTIMENT_FEATURE_NAMES) == 24


# --- Google Trends ---


def test_google_trends_current(engineer: SentimentFeatureEngineer) -> None:
    buzz = _make_buzz("google_trends", sentiment=0.0, count=75)
    result = engineer.compute(**_base_kwargs(), google_trends_signals=[buzz])
    assert result["google_trends_current"] == pytest.approx(75.0)


def test_google_trends_change_1w(engineer: SentimentFeatureEngineer) -> None:
    current = _make_buzz("google_trends", count=100)
    prior = _make_buzz("google_trends", count=80)
    result = engineer.compute(
        **_base_kwargs(),
        google_trends_signals=[current],
        google_trends_prior=[prior],
    )
    # (100 - 80) / 80 = 0.25
    assert result["google_trends_change_1w"] == pytest.approx(0.25)


def test_google_trends_spike_above_threshold(
    engineer: SentimentFeatureEngineer,
) -> None:
    buzz = _make_buzz("google_trends", count=200)
    result = engineer.compute(
        **_base_kwargs(),
        google_trends_signals=[buzz],
        google_trends_52w_mean=100.0,
        google_trends_52w_std=40.0,  # threshold = 180; 200 > 180 → spike
    )
    assert result["google_trends_spike"] == pytest.approx(1.0)


def test_google_trends_spike_below_threshold(
    engineer: SentimentFeatureEngineer,
) -> None:
    buzz = _make_buzz("google_trends", count=150)
    result = engineer.compute(
        **_base_kwargs(),
        google_trends_signals=[buzz],
        google_trends_52w_mean=100.0,
        google_trends_52w_std=40.0,  # threshold = 180; 150 < 180 → no spike
    )
    assert result["google_trends_spike"] == pytest.approx(0.0)


# --- StockTwits ---


def test_stocktwits_volume_24h(engineer: SentimentFeatureEngineer) -> None:
    buzz = _make_buzz("stocktwits", sentiment=0.6, count=500)
    result = engineer.compute(**_base_kwargs(), stocktwits_signals=[buzz])
    assert result["stocktwits_volume_24h"] == pytest.approx(500.0)


def test_stocktwits_bullish_ratio(engineer: SentimentFeatureEngineer) -> None:
    # sentiment_raw=0.6 → (0.6 + 1) / 2 = 0.8
    buzz = _make_buzz("stocktwits", sentiment=0.6, count=100)
    result = engineer.compute(**_base_kwargs(), stocktwits_signals=[buzz])
    assert result["stocktwits_bullish_ratio"] == pytest.approx(0.8)


def test_stocktwits_volume_change(engineer: SentimentFeatureEngineer) -> None:
    current = _make_buzz("stocktwits", count=600)
    prior = _make_buzz("stocktwits", count=400)
    result = engineer.compute(
        **_base_kwargs(),
        stocktwits_signals=[current],
        stocktwits_prior=[prior],
    )
    # (600 - 400) / 400 = 0.5
    assert result["stocktwits_volume_change"] == pytest.approx(0.5)


# --- News headline sentiment ---


def test_news_sentiment_avg_7d(engineer: SentimentFeatureEngineer) -> None:
    news = [_make_sentiment(score=0.4), _make_sentiment(score=0.6)]
    result = engineer.compute(**_base_kwargs(), news_sentiments_7d=news)
    assert result["news_sentiment_avg_7d"] == pytest.approx(0.5)


def test_news_volume_7d(engineer: SentimentFeatureEngineer) -> None:
    news = [_make_sentiment() for _ in range(5)]
    result = engineer.compute(**_base_kwargs(), news_sentiments_7d=news)
    assert result["news_volume_7d"] == pytest.approx(5.0)


def test_news_sentiment_momentum(engineer: SentimentFeatureEngineer) -> None:
    current_news = [_make_sentiment(score=0.6), _make_sentiment(score=0.4)]
    prior_news = [_make_sentiment(score=0.2), _make_sentiment(score=0.2)]
    result = engineer.compute(
        **_base_kwargs(),
        news_sentiments_7d=current_news,
        news_sentiments_prior_7d=prior_news,
    )
    # current_avg=0.5, prior_avg=0.2 → momentum=0.3
    assert result["news_sentiment_momentum"] == pytest.approx(0.3)


def test_news_negative_spike_triggered(engineer: SentimentFeatureEngineer) -> None:
    # baseline mean=2, std=1 → threshold=4; supply 5 negative articles
    negatives = [_make_sentiment(score=-0.5) for _ in range(5)]
    result = engineer.compute(
        **_base_kwargs(),
        news_sentiments_7d=negatives,
        news_negative_baseline_mean=2.0,
        news_negative_baseline_std=1.0,
    )
    assert result["news_negative_spike"] == pytest.approx(1.0)


def test_news_negative_spike_not_triggered(engineer: SentimentFeatureEngineer) -> None:
    # only 1 negative article, threshold=4 → no spike
    news = [
        _make_sentiment(score=-0.5),
        _make_sentiment(score=0.3),
        _make_sentiment(score=0.1),
    ]
    result = engineer.compute(
        **_base_kwargs(),
        news_sentiments_7d=news,
        news_negative_baseline_mean=2.0,
        news_negative_baseline_std=1.0,
    )
    assert result["news_negative_spike"] == pytest.approx(0.0)


# --- Graceful degradation: all Phase 3.5 features NaN when sources absent ---


def test_phase35_features_nan_when_no_sources(
    engineer: SentimentFeatureEngineer,
) -> None:
    result = engineer.compute(**_base_kwargs())
    phase35_features = [
        "google_trends_current",
        "google_trends_change_1w",
        "google_trends_spike",
        "stocktwits_volume_24h",
        "stocktwits_bullish_ratio",
        "stocktwits_volume_change",
        "news_sentiment_avg_7d",
        "news_volume_7d",
        "news_sentiment_momentum",
        "news_negative_spike",
    ]
    for name in phase35_features:
        assert math.isnan(result[name]), f"Expected NaN for {name}, got {result[name]}"
