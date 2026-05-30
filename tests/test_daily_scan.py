"""Tests for DailyScanUseCase — TDD (ADR-022).

Uses fake adapters only — no real RSS, no real scoring.
"""

from __future__ import annotations

from datetime import datetime

from application.daily_scan import DailyScanUseCase
from domain.models import BuzzSignal
from tests.fakes.fake_buzz_discovery import FakeBuzzDiscovery
from tests.fakes.fake_sentiment import FakeSentimentScorer

_NOW = datetime(2026, 1, 15, 9, 0, 0)


def _make_signal(ticker: str, source: str = "reuters_rss") -> BuzzSignal:
    return BuzzSignal(
        ticker=ticker,
        source=source,
        mention_count=3,
        sentiment_raw=0.2,
        scorer="raw",
        fetched_at=_NOW,
        article_hash=f"hash_{ticker}",
    )


def test_scan_stores_signals() -> None:
    """2 raw signals (AAPL, TSLA) → at least 2 stored, tickers_found >= 2."""
    signals = [_make_signal("AAPL"), _make_signal("TSLA")]
    discovery = FakeBuzzDiscovery(signals=signals)
    keyword = FakeSentimentScorer(default_score=0.1)
    flan_t5 = FakeSentimentScorer(default_score=0.3)

    stored: list[BuzzSignal] = []

    use_case = DailyScanUseCase(
        discovery=discovery,
        keyword_scorer=keyword,
        flan_t5_scorer=flan_t5,
        store_signal=stored.append,
    )
    result = use_case.execute(_NOW)

    assert result["tickers_found"] >= 2
    assert len(stored) >= 2


def test_scan_scores_with_both_scorers() -> None:
    """1 raw signal → scored signals for both 'keyword' and 'flan_t5' stored."""
    signals = [_make_signal("MSFT")]
    discovery = FakeBuzzDiscovery(signals=signals)
    keyword = FakeSentimentScorer(scores={"MSFT": 0.4})
    flan_t5 = FakeSentimentScorer(scores={"MSFT": -0.2})

    stored: list[BuzzSignal] = []

    use_case = DailyScanUseCase(
        discovery=discovery,
        keyword_scorer=keyword,
        flan_t5_scorer=flan_t5,
        store_signal=stored.append,
    )
    use_case.execute(_NOW)

    scorers_stored = {s.scorer for s in stored}
    assert "keyword" in scorers_stored, "keyword scorer signals not stored"
    assert "flan_t5" in scorers_stored, "flan_t5 scorer signals not stored"


def test_empty_feed_returns_zero() -> None:
    """Empty discovery → tickers_found=0, signals_stored=0, store never called."""
    discovery = FakeBuzzDiscovery(signals=[])
    keyword = FakeSentimentScorer()
    flan_t5 = FakeSentimentScorer()

    stored: list[BuzzSignal] = []

    use_case = DailyScanUseCase(
        discovery=discovery,
        keyword_scorer=keyword,
        flan_t5_scorer=flan_t5,
        store_signal=stored.append,
    )
    result = use_case.execute(_NOW)

    assert result == {"tickers_found": 0, "signals_stored": 0}
    assert stored == []
