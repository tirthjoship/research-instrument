"""Integration test: multi-source sentiment pipeline end-to-end.

Verifies that all three new adapters can be composed with existing
SentimentFeatureEngineer to produce a complete 24-feature vector.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

from adapters.ml.sentiment_feature_engineer import (
    SENTIMENT_FEATURE_NAMES,
    SentimentFeatureEngineer,
)
from domain.models import BuzzSignal, Sentiment, SourceReliability


def _ts() -> datetime:
    return datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc)


def test_full_24_feature_vector_with_all_sources() -> None:
    """All 24 features computed when all sources provide data."""
    engineer = SentimentFeatureEngineer()

    rss_buzz = [
        BuzzSignal("AAPL", "reuters_rss", 3, 0.4, "keyword", _ts(), "h1"),
        BuzzSignal("AAPL", "reddit_wsb", 2, -0.2, "keyword", _ts(), "h2"),
    ]
    gt_buzz = [
        BuzzSignal("AAPL", "google_trends", 80, 0.6, "google_trends", _ts(), "h3")
    ]
    gt_prior = [
        BuzzSignal("AAPL", "google_trends", 50, 0.0, "google_trends", _ts(), "h4")
    ]
    st_buzz = [BuzzSignal("AAPL", "stocktwits", 45, 0.33, "stocktwits", _ts(), "h5")]
    st_prior = [BuzzSignal("AAPL", "stocktwits", 30, 0.2, "stocktwits", _ts(), "h6")]

    news_7d = [
        Sentiment("gdelt_reuters.com", _ts(), 0.3, 0.6),
        Sentiment("gdelt_cnbc.com", _ts(), 0.5, 0.6),
        Sentiment("gdelt_bbc.com", _ts(), -0.1, 0.6),
    ]
    news_prior = [
        Sentiment("gdelt_reuters.com", _ts(), 0.1, 0.6),
        Sentiment("gdelt_cnbc.com", _ts(), 0.2, 0.6),
    ]

    result = engineer.compute(
        keyword_sentiment=0.4,
        flan_t5_sentiment=0.5,
        sentiments=[Sentiment("rss_news", _ts(), 0.3, 0.8)],
        buzz_signals_current=rss_buzz + gt_buzz + st_buzz,
        buzz_signals_prior=rss_buzz,
        sector_buzz_total=20,
        reliability=SourceReliability("reuters_rss", "AAPL", 9, 10),
        price_return_5d=0.03,
        google_trends_signals=gt_buzz,
        google_trends_prior=gt_prior,
        google_trends_52w_mean=55.0,
        google_trends_52w_std=12.0,
        stocktwits_signals=st_buzz,
        stocktwits_prior=st_prior,
        news_sentiments_7d=news_7d,
        news_sentiments_prior_7d=news_prior,
        news_negative_baseline_mean=1.0,
        news_negative_baseline_std=0.5,
    )

    # All 24 features present
    assert set(result.keys()) == set(SENTIMENT_FEATURE_NAMES)
    assert len(result) == 24

    # Spot-check Phase 3.5 features
    # google_trends_spike: 80 > 55 + 2*12 = 79 → spike = 1.0
    assert result["google_trends_spike"] == 1.0
    assert result["google_trends_current"] == 80.0
    # google_trends_change_1w: (80 - 50) / 50 = 0.6
    assert abs(result["google_trends_change_1w"] - 0.6) < 0.01
    assert result["stocktwits_volume_24h"] == 45.0
    # stocktwits_volume_change: (45 - 30) / 30 = 0.5
    assert abs(result["stocktwits_volume_change"] - 0.5) < 0.01
    assert result["news_volume_7d"] == 3.0
    # news_sentiment_avg_7d: (0.3 + 0.5 + -0.1) / 3 ≈ 0.233
    assert abs(result["news_sentiment_avg_7d"] - 0.2333) < 0.01


def test_graceful_nan_when_sources_missing() -> None:
    """Features return NaN when their source data is absent."""
    engineer = SentimentFeatureEngineer()

    result = engineer.compute(
        keyword_sentiment=0.5,
        flan_t5_sentiment=0.5,
        sentiments=[Sentiment("rss_news", _ts(), 0.3, 0.8)],
        buzz_signals_current=[
            BuzzSignal("AAPL", "reuters_rss", 2, 0.3, "keyword", _ts(), "h1")
        ],
        buzz_signals_prior=[
            BuzzSignal("AAPL", "reuters_rss", 1, 0.2, "keyword", _ts(), "h2")
        ],
        sector_buzz_total=10,
        reliability=SourceReliability("reuters_rss", "AAPL", 9, 10),
        price_return_5d=0.02,
        # No Phase 3.5 sources provided
    )

    # Phase 3.5 features should be NaN
    assert math.isnan(result["google_trends_current"])
    assert math.isnan(result["google_trends_change_1w"])
    assert math.isnan(result["google_trends_spike"])
    assert math.isnan(result["stocktwits_volume_24h"])
    assert math.isnan(result["stocktwits_bullish_ratio"])
    assert math.isnan(result["stocktwits_volume_change"])
    assert math.isnan(result["news_sentiment_avg_7d"])
    assert math.isnan(result["news_volume_7d"])
    assert math.isnan(result["news_sentiment_momentum"])
    assert math.isnan(result["news_negative_spike"])

    # Original 14 features should still compute
    assert not math.isnan(result["buzz_volume"])
    assert not math.isnan(result["buzz_acceleration"])
