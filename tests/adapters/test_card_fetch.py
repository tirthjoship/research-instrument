from __future__ import annotations

import pytest

from adapters.visualization.card_fetch import get_case_on_expand
from application.evidence_card import EvidenceCard
from domain.case_models import CasePoint, CaseResult
from domain.evidence_rag import DIMENSIONS, RagColor, RagSignal


class _SpySummarizer:
    def __init__(self) -> None:
        self.calls = 0

    def summarize_case(self, ctx: object) -> CaseResult:
        self.calls += 1
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
