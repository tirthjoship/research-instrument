"""Tests for live headline buzz enrichment."""

from __future__ import annotations

from adapters.visualization.analysis.buzz_enrichment import (
    resolve_sentiment_signals,
    score_headlines_as_buzz_signals,
)
from domain.models import BuzzSignal


def test_score_headlines_produces_nonzero_tone() -> None:
    rows = score_headlines_as_buzz_signals(
        "NVDA",
        [
            {
                "title": "NVIDIA surges on record earnings beat and strong growth",
                "source": "Reuters",
                "date": "2026-07-07",
            }
        ],
    )
    assert len(rows) == 1
    assert rows[0].scorer == "keyword_live"
    assert rows[0].sentiment_raw > 0.05
    assert rows[0].source == "Reuters"
    assert rows[0].publisher == "Reuters"


def test_headline_bearish_terms_boost_negative_score() -> None:
    rows = score_headlines_as_buzz_signals(
        "NVDA",
        [
            {
                "title": "Why chip stocks plummeting today as sector dips",
                "source": "Motley Fool",
                "date": "2026-07-07",
            }
        ],
    )
    assert rows[0].sentiment_raw < -0.05


def test_resolve_sentiment_keeps_harvest_separate() -> None:
    harvest = [
        BuzzSignal(
            ticker="NVDA",
            source="yahoo_finance",
            mention_count=17,
            sentiment_raw=0.0,
            scorer="keyword",
            fetched_at=__import__("datetime").datetime(2026, 6, 4),
            article_hash="old",
        )
    ]
    headlines = [
        {
            "title": "NVIDIA stock rally on upgrade and positive outlook",
            "source": "Barrons",
            "date": "2026-07-07",
        }
    ]
    sentiment, from_live, stale = resolve_sentiment_signals(
        harvest, True, "NVDA", headlines
    )
    assert from_live is True
    assert stale is False
    assert sentiment[0].scorer == "keyword_live"
    assert harvest[0].mention_count == 17


def test_resolve_sentiment_skipped_when_harvest_has_tone() -> None:
    toned = [
        BuzzSignal(
            ticker="NVDA",
            source="yahoo_finance",
            mention_count=1,
            sentiment_raw=0.6,
            scorer="keyword",
            fetched_at=__import__("datetime").datetime(2026, 7, 7),
            article_hash="kw1",
        )
    ]
    sentiment, from_live, stale = resolve_sentiment_signals(
        toned,
        False,
        "NVDA",
        [{"title": "crash plunge sell-off", "source": "X", "date": "2026-07-07"}],
    )
    assert sentiment is toned
    assert from_live is False
    assert stale is False


def test_resolve_sentiment_prefers_live_when_harvest_has_no_tone() -> None:
    flat = [
        BuzzSignal(
            ticker="NVDA",
            source="google_news",
            mention_count=1,
            sentiment_raw=0.0,
            scorer="keyword",
            fetched_at=__import__("datetime").datetime(2026, 7, 7),
            article_hash="kw1",
        ),
    ]
    headlines = [
        {"title": "NVIDIA rally on upgrade", "source": "Reuters", "date": "2026-07-07"},
    ]
    sentiment, from_live, stale = resolve_sentiment_signals(
        flat, False, "NVDA", headlines
    )
    assert from_live is True
    assert sentiment[0].scorer == "keyword_live"
