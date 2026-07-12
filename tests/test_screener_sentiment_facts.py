"""TDD tests for application/screener_sentiment_facts.py::buzz_sentiment_fact().

Honesty rule: an empty/missing buzz signal returns None (an omission), never a
fabricated "no buzz" claim baked into the fact text.
"""

from __future__ import annotations

from datetime import datetime, timezone

from adapters.data.sqlite_store import SQLiteStore
from domain.models import BuzzSignal


def _save(
    store: SQLiteStore, ticker: str, sentiment: float, mentions: int, hash_: str
) -> None:
    store.save_buzz_signal(
        BuzzSignal(
            ticker=ticker,
            source="yahoo_finance",
            mention_count=mentions,
            sentiment_raw=sentiment,
            scorer="keyword",
            fetched_at=datetime.now(timezone.utc),
            article_hash=hash_,
        )
    )


def test_buzz_sentiment_fact_positive(tmp_path) -> None:
    from application.screener_sentiment_facts import buzz_sentiment_fact

    db = str(tmp_path / "buzz.db")
    store = SQLiteStore(db)
    _save(store, "NVDA", 0.6, 5, "a")
    _save(store, "NVDA", 0.4, 7, "b")

    fact = buzz_sentiment_fact("NVDA", db)
    assert fact is not None
    assert "positive" in fact.lower()
    assert "12" in fact  # total mentions


def test_buzz_sentiment_fact_negative(tmp_path) -> None:
    from application.screener_sentiment_facts import buzz_sentiment_fact

    db = str(tmp_path / "buzz.db")
    store = SQLiteStore(db)
    _save(store, "XOM", -0.3, 4, "a")

    fact = buzz_sentiment_fact("XOM", db)
    assert fact is not None
    assert "negative" in fact.lower()


def test_buzz_sentiment_fact_neutral(tmp_path) -> None:
    from application.screener_sentiment_facts import buzz_sentiment_fact

    db = str(tmp_path / "buzz.db")
    store = SQLiteStore(db)
    _save(store, "KO", 0.05, 2, "a")

    fact = buzz_sentiment_fact("KO", db)
    assert fact is not None
    assert "neutral" in fact.lower()


def test_buzz_sentiment_fact_none_when_no_signals(tmp_path) -> None:
    from application.screener_sentiment_facts import buzz_sentiment_fact

    db = str(tmp_path / "buzz.db")
    SQLiteStore(db)  # create empty db, schema only

    assert buzz_sentiment_fact("ZZZZ", db) is None


def test_buzz_sentiment_fact_none_when_db_missing(tmp_path) -> None:
    from application.screener_sentiment_facts import buzz_sentiment_fact

    missing_db = str(tmp_path / "does-not-exist.db")
    assert buzz_sentiment_fact("NVDA", missing_db) is None


def test_buzz_sentiment_fact_no_forbidden_words(tmp_path) -> None:
    from application.screener_sentiment_facts import buzz_sentiment_fact
    from domain.fit import FORBIDDEN_WORDS

    db = str(tmp_path / "buzz.db")
    store = SQLiteStore(db)
    _save(store, "NVDA", 0.9, 20, "a")

    fact = buzz_sentiment_fact("NVDA", db)
    assert fact is not None
    low = fact.lower()
    for w in FORBIDDEN_WORDS:
        assert w not in low
