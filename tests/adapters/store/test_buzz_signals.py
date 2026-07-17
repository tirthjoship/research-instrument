"""Tests for BuzzSignalsMixin."""

from __future__ import annotations

from datetime import datetime

import pytest

from adapters.data.sqlite_store import SQLiteStore
from domain.models import BuzzSignal


def test_save_and_get_buzz_signals(tmp_path: pytest.TempPathFactory) -> None:
    store = SQLiteStore(str(tmp_path / "test.db"))  # type: ignore[arg-type]
    bs = BuzzSignal(
        ticker="AAPL",
        source="reuters_rss",
        mention_count=10,
        sentiment_raw=0.6,
        scorer="keyword",
        fetched_at=datetime(2026, 5, 30, 9, 0),
        article_hash="hash1",
    )
    store.save_buzz_signal(bs)
    results = store.get_buzz_signals(ticker="AAPL")
    assert len(results) == 1
    assert results[0].ticker == "AAPL"
    assert results[0].sentiment_raw == 0.6


def test_save_and_get_buzz_signals_with_article_text(
    tmp_path: pytest.TempPathFactory,
) -> None:
    store = SQLiteStore(str(tmp_path / "test.db"))  # type: ignore[arg-type]
    bs = BuzzSignal(
        ticker="AAPL",
        source="reuters_rss",
        mention_count=10,
        sentiment_raw=0.6,
        scorer="keyword",
        fetched_at=datetime(2026, 5, 30, 9, 0),
        article_hash="hash1",
        article_text="Apple beats earnings with strong growth",
    )
    store.save_buzz_signal(bs)
    results = store.get_buzz_signals(ticker="AAPL")
    assert results[0].article_text == "Apple beats earnings with strong growth"


def test_buzz_signal_dedup_by_hash(tmp_path: pytest.TempPathFactory) -> None:
    store = SQLiteStore(str(tmp_path / "test.db"))  # type: ignore[arg-type]
    bs = BuzzSignal(
        ticker="AAPL",
        source="reuters_rss",
        mention_count=10,
        sentiment_raw=0.6,
        scorer="keyword",
        fetched_at=datetime(2026, 5, 30, 9, 0),
        article_hash="hash1",
    )
    store.save_buzz_signal(bs)
    store.save_buzz_signal(bs)  # duplicate
    results = store.get_buzz_signals(ticker="AAPL")
    assert len(results) == 1


def test_get_buzz_signals_date_filter(tmp_path: pytest.TempPathFactory) -> None:
    store = SQLiteStore(str(tmp_path / "test.db"))  # type: ignore[arg-type]
    bs1 = BuzzSignal(
        ticker="AAPL",
        source="reuters_rss",
        mention_count=5,
        sentiment_raw=0.3,
        scorer="keyword",
        fetched_at=datetime(2026, 5, 28, 9, 0),
        article_hash="h1",
    )
    bs2 = BuzzSignal(
        ticker="AAPL",
        source="reuters_rss",
        mention_count=15,
        sentiment_raw=0.8,
        scorer="keyword",
        fetched_at=datetime(2026, 5, 30, 9, 0),
        article_hash="h2",
    )
    store.save_buzz_signal(bs1)
    store.save_buzz_signal(bs2)
    results = store.get_buzz_signals(ticker="AAPL", start_date=datetime(2026, 5, 29))
    assert len(results) == 1
    assert results[0].article_hash == "h2"


def test_prune_buzz_signals_deletes_rows_older_than_cutoff(
    tmp_path: pytest.TempPathFactory,
) -> None:
    store = SQLiteStore(str(tmp_path / "test.db"))  # type: ignore[arg-type]
    old = BuzzSignal(
        ticker="AAPL",
        source="reuters_rss",
        mention_count=5,
        sentiment_raw=0.3,
        scorer="keyword",
        fetched_at=datetime(2026, 1, 1, 9, 0),
        article_hash="old_hash",
    )
    recent = BuzzSignal(
        ticker="AAPL",
        source="reuters_rss",
        mention_count=8,
        sentiment_raw=0.5,
        scorer="keyword",
        fetched_at=datetime(2026, 6, 1, 9, 0),
        article_hash="recent_hash",
    )
    store.save_buzz_signal(old)
    store.save_buzz_signal(recent)

    deleted = store.prune_buzz_signals(datetime(2026, 3, 1))

    assert deleted == 1
    remaining = store.get_buzz_signals(ticker="AAPL")
    assert len(remaining) == 1
    assert remaining[0].article_hash == "recent_hash"


def test_prune_buzz_signals_returns_zero_when_nothing_old(
    tmp_path: pytest.TempPathFactory,
) -> None:
    store = SQLiteStore(str(tmp_path / "test.db"))  # type: ignore[arg-type]
    bs = BuzzSignal(
        ticker="MSFT",
        source="reuters_rss",
        mention_count=3,
        sentiment_raw=0.1,
        scorer="keyword",
        fetched_at=datetime(2026, 6, 1, 9, 0),
        article_hash="h1",
    )
    store.save_buzz_signal(bs)

    deleted = store.prune_buzz_signals(datetime(2026, 1, 1))

    assert deleted == 0
    assert len(store.get_buzz_signals(ticker="MSFT")) == 1
