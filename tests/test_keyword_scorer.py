"""Tests for KeywordScorer — rule-based sentiment scorer.

TDD: tests written before implementation.
"""

from __future__ import annotations

from datetime import datetime

from adapters.ml.keyword_scorer import KeywordScorer

FIXED_TS = datetime(2024, 1, 15, 12, 0, 0)


def test_bullish_text_yields_positive_score() -> None:
    scorer = KeywordScorer()
    results = scorer.score_text(
        "AAPL",
        "Apple beats earnings, record revenue growth and surge in profits.",
        FIXED_TS,
        source="news",
    )
    assert len(results) == 1
    assert results[0].sentiment_score > 0.0


def test_bearish_text_yields_negative_score() -> None:
    scorer = KeywordScorer()
    results = scorer.score_text(
        "TSLA",
        "Tesla misses earnings, layoffs announced and losses mount amid debt concerns.",
        FIXED_TS,
        source="news",
    )
    assert len(results) == 1
    assert results[0].sentiment_score < 0.0


def test_neutral_text_yields_near_zero_score() -> None:
    scorer = KeywordScorer()
    results = scorer.score_text(
        "GOOG", "Google released a new product today.", FIXED_TS, source="news"
    )
    assert len(results) == 1
    assert abs(results[0].sentiment_score) < 0.2


def test_empty_text_yields_zero_score() -> None:
    scorer = KeywordScorer()
    results = scorer.score_text("MSFT", "", FIXED_TS, source="news")
    assert len(results) == 1
    assert results[0].sentiment_score == 0.0


def test_confidence_bounded_zero_to_one() -> None:
    scorer = KeywordScorer()
    # text with many keyword hits to push confidence high
    heavy_text = " ".join(["beat surge rally growth upgrade outperform"] * 5)
    results = scorer.score_text("NVDA", heavy_text, FIXED_TS)
    assert 0.0 <= results[0].confidence <= 1.0


def test_score_bounded_minus_one_to_one() -> None:
    scorer = KeywordScorer()
    extreme_bullish = " ".join(
        ["beat surge rally growth upgrade outperform strong profit"] * 10
    )
    results = scorer.score_text("AMD", extreme_bullish, FIXED_TS)
    assert -1.0 <= results[0].sentiment_score <= 1.0


def test_get_sentiment_returns_empty_list() -> None:
    scorer = KeywordScorer()
    results = scorer.get_sentiment("AAPL", prediction_time=FIXED_TS)
    assert results == []
