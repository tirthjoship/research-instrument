from __future__ import annotations

import pytest

from adapters.visualization.card_fetch import get_case_on_expand
from application.evidence_card import EvidenceCard
from domain.case_models import CasePoint, CaseResult
from domain.evidence_rag import DIMENSIONS, RagColor, RagSignal


class _SpySummarizer:
    def __init__(self) -> None:
        self.calls = 0
        self.last_ctx: object = None

    def summarize_case(self, ctx: object) -> CaseResult:
        self.calls += 1
        self.last_ctx = ctx
        return CaseResult((), (), True)


def _card() -> EvidenceCard:
    sigs = tuple(RagSignal(d, RagColor.GREEN, "x") for d in DIMENSIONS)
    return EvidenceCard("YUMC", sigs, ())


def _cached_result() -> CaseResult:
    return CaseResult(
        in_favor=(CasePoint("cached signal", "reported"),),
        to_watch=(),
        data_gap=False,
    )


def test_case_not_fetched_unless_expanded() -> None:
    spy = _SpySummarizer()
    assert (
        get_case_on_expand("YUMC", _card(), news=[], expanded=False, summarizer=spy)
        is None
    )
    assert spy.calls == 0  # NOT called when collapsed


def test_case_fetched_on_expand() -> None:
    spy = _SpySummarizer()
    res = get_case_on_expand("YUMC", _card(), news=[], expanded=True, summarizer=spy)
    assert res is not None and spy.calls == 1


# ---------------------------------------------------------------------------
# extra_facts — appended onto the built CaseContext before summarize_case
# ---------------------------------------------------------------------------


def test_extra_facts_default_is_backward_compatible() -> None:
    """Omitting extra_facts must behave identically to today (no ctx.facts change)."""
    spy = _SpySummarizer()
    get_case_on_expand("YUMC", _card(), news=[], expanded=True, summarizer=spy)
    assert "Verdict:" not in " ".join(spy.last_ctx.facts)  # type: ignore[attr-defined]


def test_extra_facts_appended_onto_context_facts() -> None:
    spy = _SpySummarizer()
    get_case_on_expand(
        "YUMC",
        _card(),
        news=[],
        expanded=True,
        summarizer=spy,
        extra_facts=("Verdict: HOLD. steady trend", "Recent buzz: mildly positive"),
    )
    assert spy.last_ctx is not None
    facts = spy.last_ctx.facts  # type: ignore[attr-defined]
    assert "Verdict: HOLD. steady trend" in facts
    assert "Recent buzz: mildly positive" in facts


def test_extra_facts_not_applied_on_cache_hit(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cache hit short-circuits before extra_facts is ever used (no live call)."""
    import os

    assert isinstance(tmp_path, os.PathLike)
    cache_path = str(tmp_path / "cited_cases.json")

    from application.case_cache import write_case_cache

    result = _cached_result()
    write_case_cache(cache_path, "2026-06-14", {"YUMC": result})

    import adapters.visualization.card_fetch as cf_mod

    monkeypatch.setattr(cf_mod, "_CITED_CASES_PATH", cache_path)

    spy = _SpySummarizer()
    fetched = get_case_on_expand(
        "YUMC",
        _card(),
        news=[],
        expanded=True,
        summarizer=spy,
        extra_facts=("Verdict: HOLD. steady trend",),
    )

    assert spy.calls == 0
    assert fetched == result


# ---------------------------------------------------------------------------
# D2 — cache-first tests
# ---------------------------------------------------------------------------


def test_cache_hit_skips_summarizer(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When a cached result exists, the summarizer must NOT be called (0 pings)."""
    import os

    assert isinstance(tmp_path, os.PathLike)
    cache_path = str(tmp_path / "cited_cases.json")

    # Pre-populate cache
    from application.case_cache import write_case_cache

    result = _cached_result()
    write_case_cache(cache_path, "2026-06-14", {"YUMC": result})

    # Redirect card_fetch to use this temp cache path
    import adapters.visualization.card_fetch as cf_mod

    monkeypatch.setattr(cf_mod, "_CITED_CASES_PATH", cache_path)

    spy = _SpySummarizer()
    fetched = get_case_on_expand(
        "YUMC", _card(), news=[], expanded=True, summarizer=spy
    )

    assert spy.calls == 0, "summarizer must NOT be called on cache hit"
    assert fetched == result


def test_cache_miss_calls_summarizer_once(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """On a cache miss (ticker absent), the summarizer is called once (live ping)."""
    import os

    assert isinstance(tmp_path, os.PathLike)
    cache_path = str(tmp_path / "cited_cases.json")

    # Cache exists but has a different ticker
    from application.case_cache import write_case_cache

    write_case_cache(cache_path, "2026-06-14", {"OTHER": _cached_result()})

    import adapters.visualization.card_fetch as cf_mod

    monkeypatch.setattr(cf_mod, "_CITED_CASES_PATH", cache_path)

    spy = _SpySummarizer()
    fetched = get_case_on_expand(
        "YUMC", _card(), news=[], expanded=True, summarizer=spy
    )

    assert spy.calls == 1, "summarizer must be called exactly once on cache miss"
    assert fetched is not None


def test_explicit_cache_path_overrides_module_default(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An explicit cache_path kwarg is used over the module-level _CITED_CASES_PATH.

    This is what lets Home/Portfolio pass a {reports_dir}-scoped cache file
    instead of the hardcoded, gitignored data/personal/cited_cases.json (which
    never exists on a fresh Cloud clone).
    """
    import os

    assert isinstance(tmp_path, os.PathLike)
    explicit_path = str(tmp_path / "home_cited_cases.json")
    unused_default_path = str(tmp_path / "should_not_be_read.json")

    from application.case_cache import write_case_cache

    result = _cached_result()
    write_case_cache(explicit_path, "2026-06-14", {"YUMC": result})

    import adapters.visualization.card_fetch as cf_mod

    monkeypatch.setattr(cf_mod, "_CITED_CASES_PATH", unused_default_path)

    spy = _SpySummarizer()
    fetched = get_case_on_expand(
        "YUMC",
        _card(),
        news=[],
        expanded=True,
        summarizer=spy,
        cache_path=explicit_path,
    )

    assert spy.calls == 0, "explicit cache_path hit must skip the summarizer"
    assert fetched == result


def test_no_cache_file_calls_summarizer(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When cache file is absent, the summarizer is called (live fallback)."""
    import os

    assert isinstance(tmp_path, os.PathLike)
    missing_path = str(tmp_path / "nonexistent.json")

    import adapters.visualization.card_fetch as cf_mod

    monkeypatch.setattr(cf_mod, "_CITED_CASES_PATH", missing_path)

    spy = _SpySummarizer()
    fetched = get_case_on_expand(
        "YUMC", _card(), news=[], expanded=True, summarizer=spy
    )

    assert spy.calls == 1
    assert fetched is not None
