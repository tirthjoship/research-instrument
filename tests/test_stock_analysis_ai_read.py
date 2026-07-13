"""TDD tests for adapters/visualization/tabs/stock_analysis/ai_read.py.

Same in-favor/to-watch shape as Home/Portfolio (render_gemini_read, CaseResult,
GeminiNarratorAdapter -- no new prompt variant), fed real facts + real news +
real buzz sentiment. Cached same-day per ticker, separate cache file from
Home/Portfolio/Risk's weekly cache (see spec Non-goals for why).
"""

from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

# ---------------------------------------------------------------------------
# buzz_fact_from_signals
# ---------------------------------------------------------------------------


def test_buzz_fact_from_signals_empty_returns_none() -> None:
    from adapters.visualization.tabs.stock_analysis.ai_read import (
        buzz_fact_from_signals,
    )

    assert buzz_fact_from_signals([]) is None


def test_buzz_fact_from_signals_positive() -> None:
    from adapters.visualization.tabs.stock_analysis.ai_read import (
        buzz_fact_from_signals,
    )

    signals = [
        SimpleNamespace(sentiment_raw=0.6, mention_count=5),
        SimpleNamespace(sentiment_raw=0.4, mention_count=7),
    ]
    fact = buzz_fact_from_signals(signals)
    assert fact is not None
    assert "positive" in fact.lower()
    assert "12" in fact


def test_buzz_fact_from_signals_no_forbidden_words() -> None:
    from adapters.visualization.tabs.stock_analysis.ai_read import (
        buzz_fact_from_signals,
    )
    from domain.fit import FORBIDDEN_WORDS

    fact = buzz_fact_from_signals(
        [SimpleNamespace(sentiment_raw=0.9, mention_count=20)]
    )
    assert fact is not None
    low = fact.lower()
    for w in FORBIDDEN_WORDS:
        assert w not in low


# ---------------------------------------------------------------------------
# get_or_fetch_google_ai_read
# ---------------------------------------------------------------------------


class _StubSummarizer:
    def __init__(self, result: object) -> None:
        self._result = result
        self.calls: list[object] = []

    def summarize_case(self, ctx: object) -> object:
        self.calls.append(ctx)
        return self._result


def test_off_local_returns_empty_no_call(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from adapters.visualization.tabs.stock_analysis import ai_read as mod
    from domain.case_models import CaseResult

    monkeypatch.setattr(mod, "is_local_runtime", lambda: False)
    stub = _StubSummarizer(CaseResult((), (), True))
    monkeypatch.setattr(mod, "select_case_summarizer", lambda: stub)
    monkeypatch.setattr(
        mod, "CACHE_PATH", str(tmp_path / "stock_analysis_cited_cases.json")
    )

    html = mod.get_or_fetch_google_ai_read("NVDA", {"Growth": "strong"})
    assert html == ""
    assert stub.calls == []


def test_cache_miss_fetches_live_and_writes_cache(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from adapters.visualization.tabs.stock_analysis import ai_read as mod
    from domain.case_models import CasePoint, CaseResult

    cache_path = str(tmp_path / "stock_analysis_cited_cases.json")
    monkeypatch.setattr(mod, "is_local_runtime", lambda: True)
    monkeypatch.setattr(mod, "_fetch_recent_news_impl", lambda *a, **k: [])
    monkeypatch.setattr(mod, "CACHE_PATH", cache_path)

    result = CaseResult(
        in_favor=(CasePoint("demand durable", "Reuters"),), to_watch=(), data_gap=False
    )
    stub = _StubSummarizer(result)
    monkeypatch.setattr(mod, "select_case_summarizer", lambda: stub)

    html = mod.get_or_fetch_google_ai_read("NVDA", {"Growth": "strong"})
    assert "demand durable" in html
    assert len(stub.calls) == 1

    raw = json.loads(open(cache_path).read())
    assert raw["as_of"] == date.today().isoformat()
    assert "NVDA" in raw["cases"]


def test_cache_hit_same_day_skips_live_call(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from adapters.visualization.tabs.stock_analysis import ai_read as mod
    from application.case_cache import write_case_cache
    from domain.case_models import CasePoint, CaseResult

    cache_path = str(tmp_path / "stock_analysis_cited_cases.json")
    write_case_cache(
        cache_path,
        date.today().isoformat(),
        {
            "NVDA": CaseResult(
                in_favor=(CasePoint("cached point", "s"),), to_watch=(), data_gap=False
            )
        },
    )
    monkeypatch.setattr(mod, "is_local_runtime", lambda: True)
    monkeypatch.setattr(mod, "CACHE_PATH", cache_path)
    stub = _StubSummarizer(CaseResult((), (), True))
    monkeypatch.setattr(mod, "select_case_summarizer", lambda: stub)

    html = mod.get_or_fetch_google_ai_read("NVDA", {"Growth": "strong"})
    assert "cached point" in html
    assert stub.calls == []


def test_stale_cache_different_day_refetches(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from adapters.visualization.tabs.stock_analysis import ai_read as mod
    from application.case_cache import write_case_cache
    from domain.case_models import CasePoint, CaseResult

    cache_path = str(tmp_path / "stock_analysis_cited_cases.json")
    write_case_cache(
        cache_path,
        "2020-01-01",
        {
            "NVDA": CaseResult(
                in_favor=(CasePoint("old point", "s"),), to_watch=(), data_gap=False
            )
        },
    )
    monkeypatch.setattr(mod, "is_local_runtime", lambda: True)
    monkeypatch.setattr(mod, "_fetch_recent_news_impl", lambda *a, **k: [])
    monkeypatch.setattr(mod, "CACHE_PATH", cache_path)

    fresh_result = CaseResult(
        in_favor=(CasePoint("fresh point", "s"),), to_watch=(), data_gap=False
    )
    stub = _StubSummarizer(fresh_result)
    monkeypatch.setattr(mod, "select_case_summarizer", lambda: stub)

    html = mod.get_or_fetch_google_ai_read("NVDA", {"Growth": "strong"})
    assert "fresh point" in html
    assert "old point" not in html
    assert len(stub.calls) == 1

    raw = json.loads(open(cache_path).read())
    assert raw["as_of"] == date.today().isoformat()


def test_read_merge_write_preserves_other_tickers_same_day(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Fetching ticker B on the same day an already-cached ticker A exists must
    not drop A from the file (write_case_cache overwrites the whole file)."""
    from adapters.visualization.tabs.stock_analysis import ai_read as mod
    from application.case_cache import write_case_cache
    from domain.case_models import CasePoint, CaseResult

    cache_path = str(tmp_path / "stock_analysis_cited_cases.json")
    write_case_cache(
        cache_path,
        date.today().isoformat(),
        {
            "AAPL": CaseResult(
                in_favor=(CasePoint("aapl point", "s"),), to_watch=(), data_gap=False
            )
        },
    )
    monkeypatch.setattr(mod, "is_local_runtime", lambda: True)
    monkeypatch.setattr(mod, "_fetch_recent_news_impl", lambda *a, **k: [])
    monkeypatch.setattr(mod, "CACHE_PATH", cache_path)

    stub = _StubSummarizer(
        CaseResult(
            in_favor=(CasePoint("nvda point", "s"),), to_watch=(), data_gap=False
        )
    )
    monkeypatch.setattr(mod, "select_case_summarizer", lambda: stub)

    mod.get_or_fetch_google_ai_read("NVDA", {"Growth": "strong"})

    raw = json.loads(open(cache_path).read())
    assert "AAPL" in raw["cases"]
    assert "NVDA" in raw["cases"]


def test_data_gap_result_not_cached(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """A genuine data_gap result renders the honest 'unavailable' note but must
    not be cached, so a transient failure retries on the next call."""
    from adapters.visualization.tabs.stock_analysis import ai_read as mod
    from domain.case_models import CaseResult

    cache_path = str(tmp_path / "stock_analysis_cited_cases.json")
    monkeypatch.setattr(mod, "is_local_runtime", lambda: True)
    monkeypatch.setattr(mod, "_fetch_recent_news_impl", lambda *a, **k: [])
    monkeypatch.setattr(mod, "CACHE_PATH", cache_path)
    stub = _StubSummarizer(CaseResult((), (), True))
    monkeypatch.setattr(mod, "select_case_summarizer", lambda: stub)

    html = mod.get_or_fetch_google_ai_read("NVDA", {"Growth": "strong"})
    assert "unavailable" in html.lower()
    import os

    assert not os.path.exists(cache_path)
