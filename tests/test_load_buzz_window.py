"""Tests for rolling buzz mention window in load_buzz_signals."""

from __future__ import annotations

from datetime import datetime, timezone

from adapters.data.sqlite_store import SQLiteStore
from adapters.visualization.analysis.loaders import (
    BUZZ_MENTION_WINDOW_DAYS,
    load_buzz_signals,
    load_buzz_volume_signals,
)
from domain.models import BuzzSignal


def test_load_buzz_signals_filters_outside_window(tmp_path) -> None:
    db = str(tmp_path / "buzz.db")
    store = SQLiteStore(db)
    store.save_buzz_signal(
        BuzzSignal(
            ticker="NVDA",
            source="yahoo_finance",
            mention_count=3,
            sentiment_raw=0.1,
            scorer="keyword",
            fetched_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            article_hash="old",
        )
    )
    store.save_buzz_signal(
        BuzzSignal(
            ticker="NVDA",
            source="yahoo_finance",
            mention_count=7,
            sentiment_raw=0.2,
            scorer="keyword",
            fetched_at=datetime(2026, 6, 10, tzinfo=timezone.utc),
            article_hash="recent",
        )
    )
    ref = datetime(2026, 7, 7, tzinfo=timezone.utc)
    rows, stale = load_buzz_signals("NVDA", db, ref=ref, window_days=30)
    assert len(rows) == 1
    assert stale is False
    assert rows[0].mention_count == 7


def test_load_buzz_signals_stale_fallback_outside_primary_window(tmp_path) -> None:
    db = str(tmp_path / "buzz.db")
    store = SQLiteStore(db)
    store.save_buzz_signal(
        BuzzSignal(
            ticker="NVDA",
            source="yahoo_finance",
            mention_count=17,
            sentiment_raw=0.1,
            scorer="keyword",
            fetched_at=datetime(2026, 6, 4, tzinfo=timezone.utc),
            article_hash="stale",
        )
    )
    ref = datetime(2026, 7, 7, tzinfo=timezone.utc)
    rows, stale = load_buzz_signals("NVDA", db, ref=ref, window_days=30)
    assert stale is True
    assert len(rows) == 1
    assert rows[0].mention_count == 17


def test_buzz_panel_shows_30d_sublabel_when_fresh() -> None:
    from types import SimpleNamespace

    from adapters.visualization.tabs.stock_analysis import buzz_view

    result = SimpleNamespace(
        buzz_signals=[
            SimpleNamespace(
                source="reddit",
                mention_count=30,
                sentiment_raw=0.3,
                fetched_at="2026-06-27",
            )
        ],
        buzz_harvest_stale=False,
        ticker="NVDA",
        analyst_panel=SimpleNamespace(as_of="2026-06-27"),
        news_context=None,
    )
    v = buzz_view.build_buzz_view(result)
    mentions = next(m for m in v["metrics"] if m.label == "Mentions")
    assert mentions.sub == f"{BUZZ_MENTION_WINDOW_DAYS}d"


def test_buzz_panel_shows_stale_when_flag_set() -> None:
    from types import SimpleNamespace

    from adapters.visualization.tabs.stock_analysis import buzz_view

    result = SimpleNamespace(
        buzz_signals=[
            SimpleNamespace(
                source="yahoo_finance",
                mention_count=17,
                sentiment_raw=0.1,
                fetched_at="2026-06-04",
            )
        ],
        buzz_harvest_stale=True,
        ticker="NVDA",
        analyst_panel=SimpleNamespace(as_of="2026-07-07"),
        news_context=None,
    )
    v = buzz_view.build_buzz_view(result)
    mentions = next(m for m in v["metrics"] if m.label == "Mentions")
    assert mentions.sub == "stale"
    assert mentions.tone == "amber"
    assert "outside" in v["claim"].lower()


def test_load_buzz_signals_prefers_keyword_over_rss_raw(tmp_path) -> None:
    db = str(tmp_path / "buzz.db")
    store = SQLiteStore(db)
    store.save_buzz_signal(
        BuzzSignal(
            ticker="NVDA",
            source="yahoo_finance",
            mention_count=5,
            sentiment_raw=0.0,
            scorer="rss_raw",
            fetched_at=datetime(2026, 7, 7, tzinfo=timezone.utc),
            article_hash="raw1",
            article_text="headline",
        )
    )
    store.save_buzz_signal(
        BuzzSignal(
            ticker="NVDA",
            source="yahoo_finance",
            mention_count=5,
            sentiment_raw=0.8,
            scorer="keyword",
            fetched_at=datetime(2026, 7, 7, tzinfo=timezone.utc),
            article_hash="kw_raw1",
            article_text="headline",
        )
    )
    rows, _ = load_buzz_signals(
        "NVDA", db, ref=datetime(2026, 7, 7, tzinfo=timezone.utc)
    )
    assert len(rows) == 1
    assert rows[0].scorer == "keyword"
    assert rows[0].sentiment_raw == 0.8


def test_load_buzz_volume_signals_extends_sparse_primary(tmp_path) -> None:
    db = str(tmp_path / "buzz.db")
    store = SQLiteStore(db)
    store.save_buzz_signal(
        BuzzSignal(
            ticker="NVDA",
            source="google_news",
            mention_count=1,
            sentiment_raw=0.5,
            scorer="keyword",
            fetched_at=datetime(2026, 7, 7, tzinfo=timezone.utc),
            article_hash="today",
        )
    )
    store.save_buzz_signal(
        BuzzSignal(
            ticker="NVDA",
            source="yahoo_finance",
            mention_count=4,
            sentiment_raw=0.2,
            scorer="keyword",
            fetched_at=datetime(2026, 6, 3, tzinfo=timezone.utc),
            article_hash="june",
        )
    )
    ref = datetime(2026, 7, 7, tzinfo=timezone.utc)
    rows, extended = load_buzz_volume_signals("NVDA", db, ref=ref)
    assert extended is True
    assert len(rows) == 2
