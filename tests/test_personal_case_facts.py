"""TDD tests for application/personal_case_facts.py — shared real-signal
helpers (news + verdict/why + buzz) reused by Home/Portfolio's live
get_case_on_expand() path and the weekly-brief CLI's --cite-cases prefetch,
so a cache hit and a live fallback never disagree on facts.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from adapters.data.sqlite_store import SQLiteStore
from application.news_context import NewsItem
from domain.models import BuzzSignal


def _save_buzz(
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


# ---------------------------------------------------------------------------
# personal_case_news
# ---------------------------------------------------------------------------


def test_personal_case_news_converts_dicts_to_news_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from application import personal_case_facts as pcf

    raw = [
        {"source": "Reuters", "title": "Headline A", "date": "2026-07-10", "url": ""},
        {"source": "AP", "title": "Headline B", "date": "2026-07-11", "url": "x"},
    ]
    monkeypatch.setattr(pcf, "_fetch_recent_news_impl", lambda ticker, **kw: raw)

    items = pcf.personal_case_news("YUMC")

    assert items == [
        NewsItem(source="Reuters", title="Headline A", date="2026-07-10", url=""),
        NewsItem(source="AP", title="Headline B", date="2026-07-11", url="x"),
    ]


def test_personal_case_news_empty_on_fetch_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from application import personal_case_facts as pcf

    monkeypatch.setattr(pcf, "_fetch_recent_news_impl", lambda ticker, **kw: [])

    assert pcf.personal_case_news("YUMC") == []


# ---------------------------------------------------------------------------
# personal_case_extra_facts
# ---------------------------------------------------------------------------


def test_extra_facts_always_includes_verdict_and_why() -> None:
    from application.personal_case_facts import personal_case_extra_facts

    facts = personal_case_extra_facts(
        "ZZZZ", verdict="HOLD", why="steady trend", db_path="/nonexistent.db"
    )

    assert facts == ("Verdict: HOLD. steady trend",)


def test_extra_facts_appends_real_buzz_fact_when_present(tmp_path: object) -> None:
    from application.personal_case_facts import personal_case_extra_facts

    db = str(tmp_path / "buzz.db")  # type: ignore[operator]
    store = SQLiteStore(db)
    _save_buzz(store, "NVDA", 0.6, 5, "a")
    _save_buzz(store, "NVDA", 0.4, 7, "b")

    facts = personal_case_extra_facts(
        "NVDA", verdict="ADD_OK", why="strong momentum", db_path=db
    )

    assert facts[0] == "Verdict: ADD_OK. strong momentum"
    assert len(facts) == 2
    assert "positive" in facts[1].lower()


def test_extra_facts_omits_buzz_fact_when_no_signals(tmp_path: object) -> None:
    from application.personal_case_facts import personal_case_extra_facts

    db = str(tmp_path / "buzz.db")  # type: ignore[operator]
    SQLiteStore(db)  # empty db, schema only

    facts = personal_case_extra_facts(
        "ZZZZ", verdict="HOLD", why="steady trend", db_path=db
    )

    assert facts == ("Verdict: HOLD. steady trend",)
