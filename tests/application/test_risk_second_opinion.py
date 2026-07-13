"""TDD tests for application.risk_second_opinion — fail first, then implement."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from domain.case_models import CasePoint, CaseResult


def test_template_fallback_returns_data_gap() -> None:
    """FIX A: template fallback (no API key → TemplateCaseSummarizer) must return
    data_gap=True instead of echoing template points as 'Google AI' output.

    The honesty guard in build_risk_second_opinion detects that the resolved
    summarizer is a TemplateCaseSummarizer (_needs_intent returns False) and
    short-circuits to data_gap rather than calling the template.
    """
    from application.risk_second_opinion import build_risk_second_opinion

    res = build_risk_second_opinion(
        macro_facts=["systematic share 71%"], summarizer=None, use_cache=False
    )
    assert res.data_gap is True, (
        "Template summarizer path must return data_gap=True — "
        "template echoes must never be presented as Google AI output"
    )
    # No points should be populated when data_gap
    assert len(res.in_favor) == 0
    assert len(res.to_watch) == 0


def test_template_summarizer_injected_returns_data_gap() -> None:
    """FIX A: explicitly injecting a TemplateCaseSummarizer also returns data_gap=True.

    Verifies the guard works for the injected-summarizer path (not just the
    select_case_summarizer() auto-resolved path).
    """
    from application.case_builder import TemplateCaseSummarizer
    from application.risk_second_opinion import build_risk_second_opinion

    template = TemplateCaseSummarizer()
    res = build_risk_second_opinion(
        macro_facts=["net beta 1.18"],
        summarizer=template,  # type: ignore[arg-type]
        use_cache=False,
    )
    assert (
        res.data_gap is True
    ), "Injected TemplateCaseSummarizer must yield data_gap=True (FIX A)"


def test_returns_case_result_type() -> None:
    """build_risk_second_opinion always returns a CaseResult."""
    from application.risk_second_opinion import build_risk_second_opinion

    res = build_risk_second_opinion(
        macro_facts=["net beta 1.18"], summarizer=None, use_cache=False
    )
    assert isinstance(res, CaseResult)


def test_empty_facts_returns_data_gap() -> None:
    """Empty facts list with no summarizer must return data_gap=True (no fake content)."""
    from application.risk_second_opinion import build_risk_second_opinion

    res = build_risk_second_opinion(macro_facts=[], summarizer=None, use_cache=False)
    assert res.data_gap is True


def test_error_in_summarizer_returns_data_gap() -> None:
    """Any exception from an injected summarizer yields data_gap=True — never raises."""
    from application.risk_second_opinion import build_risk_second_opinion

    class _BrokenSummarizer:
        def summarize_case(self, ctx: object) -> CaseResult:
            raise RuntimeError("network down")

    res = build_risk_second_opinion(
        macro_facts=["net beta 1.18"],
        summarizer=_BrokenSummarizer(),  # type: ignore[arg-type]
        use_cache=False,
    )
    assert res.data_gap is True


def test_injected_summarizer_result_passed_through() -> None:
    """A well-behaved summarizer's result is returned as-is (no mutation)."""
    from application.risk_second_opinion import build_risk_second_opinion

    expected = CaseResult(
        in_favor=(CasePoint(text="test point", source_tag="test"),),
        to_watch=(),
        data_gap=False,
    )

    class _StubSummarizer:
        def summarize_case(self, ctx: object) -> CaseResult:
            return expected

    res = build_risk_second_opinion(
        macro_facts=["net beta 1.18"],
        summarizer=_StubSummarizer(),  # type: ignore[arg-type]
        use_cache=False,
    )
    assert res is expected


def test_news_threaded_into_context_for_live_summarizer() -> None:
    """Real news (application.news_context.NewsItem) passed via the news kwarg
    must reach the summarizer's CaseContext.news as (source, title) pairs."""
    from application.news_context import NewsItem
    from application.risk_second_opinion import build_risk_second_opinion

    captured: dict[str, object] = {}

    class _SpySummarizer:
        def summarize_case(self, ctx: object) -> CaseResult:
            captured["ctx"] = ctx
            return CaseResult((), (), False)

    build_risk_second_opinion(
        macro_facts=["net beta 1.18"],
        summarizer=_SpySummarizer(),  # type: ignore[arg-type]
        use_cache=False,
        news=[NewsItem(source="Reuters", title="VIX spikes", date="", url="")],
    )

    ctx = captured["ctx"]
    assert ctx.news == (("Reuters", "VIX spikes"),)  # type: ignore[attr-defined]


def test_default_news_is_backward_compatible() -> None:
    """Omitting news must behave identically to today (empty CaseContext.news)."""
    from application.risk_second_opinion import build_risk_second_opinion

    captured: dict[str, object] = {}

    class _SpySummarizer:
        def summarize_case(self, ctx: object) -> CaseResult:
            captured["ctx"] = ctx
            return CaseResult((), (), False)

    build_risk_second_opinion(
        macro_facts=["net beta 1.18"],
        summarizer=_SpySummarizer(),  # type: ignore[arg-type]
        use_cache=False,
    )

    ctx = captured["ctx"]
    assert ctx.news == ()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Cache behaviour tests (spec §9 — no live per-render Gemini calls)
# ---------------------------------------------------------------------------

_GOOD_RESULT = CaseResult(
    in_favor=(CasePoint(text="portfolio beta is elevated", source_tag="risk-model"),),
    to_watch=(CasePoint(text="sector concentration is high", source_tag="risk-model"),),
    data_gap=False,
)


def test_cache_hit_skips_summarizer() -> None:
    """When the cache returns a result the summarizer must NOT be called."""
    from application import risk_second_opinion as mod

    # Summarizer that raises if touched.
    class _MustNotCallSummarizer:
        def summarize_case(self, ctx: object) -> CaseResult:
            raise AssertionError("summarizer must not be called on a cache hit")

    with patch.object(mod, "load_cached_case", return_value=_GOOD_RESULT) as mock_load:
        result = mod.build_risk_second_opinion(
            macro_facts=["net beta 1.18"],
            summarizer=_MustNotCallSummarizer(),  # type: ignore[arg-type]
            use_cache=True,
        )

    assert result is _GOOD_RESULT
    mock_load.assert_called_once_with(mod._CITED_CASES_PATH, mod._CACHE_KEY)


def test_cache_miss_writes_result() -> None:
    """On a cache miss the summarizer is called and the result is written to cache."""
    from application import risk_second_opinion as mod

    class _StubSummarizer:
        def summarize_case(self, ctx: object) -> CaseResult:
            return _GOOD_RESULT

    with (
        patch.object(mod, "load_cached_case", return_value=None) as mock_load,
        patch.object(mod, "write_case_cache") as mock_write,
    ):
        result = mod.build_risk_second_opinion(
            macro_facts=["net beta 1.18"],
            summarizer=_StubSummarizer(),  # type: ignore[arg-type]
            use_cache=True,
        )

    assert result is _GOOD_RESULT
    mock_load.assert_called_once_with(mod._CITED_CASES_PATH, mod._CACHE_KEY)
    # write_case_cache must have been called once with the canonical cache key.
    assert mock_write.call_count == 1
    write_args = mock_write.call_args
    assert write_args[0][0] == mod._CITED_CASES_PATH  # path
    assert mod._CACHE_KEY in write_args[0][2]  # cases dict contains the key
    assert write_args[0][2][mod._CACHE_KEY] is _GOOD_RESULT


def test_data_gap_not_cached() -> None:
    """A data_gap result (failure/transient error) must NOT be written to cache."""
    from application import risk_second_opinion as mod

    _GAP_RESULT = CaseResult(in_favor=(), to_watch=(), data_gap=True)

    class _GapSummarizer:
        def summarize_case(self, ctx: object) -> CaseResult:
            return _GAP_RESULT

    with (
        patch.object(mod, "load_cached_case", return_value=None),
        patch.object(mod, "write_case_cache") as mock_write,
    ):
        result = mod.build_risk_second_opinion(
            macro_facts=["net beta 1.18"],
            summarizer=_GapSummarizer(),  # type: ignore[arg-type]
            use_cache=True,
        )

    assert result.data_gap is True
    mock_write.assert_not_called()


def test_cache_read_error_falls_through_to_summarizer() -> None:
    """A corrupt/unreadable cache must not crash — falls through to summarizer."""
    from application import risk_second_opinion as mod

    class _StubSummarizer:
        def summarize_case(self, ctx: object) -> CaseResult:
            return _GOOD_RESULT

    with (
        patch.object(mod, "load_cached_case", side_effect=OSError("disk error")),
        patch.object(mod, "write_case_cache") as mock_write,
    ):
        result = mod.build_risk_second_opinion(
            macro_facts=["net beta 1.18"],
            summarizer=_StubSummarizer(),  # type: ignore[arg-type]
            use_cache=True,
        )

    assert result is _GOOD_RESULT
    # The successful result is still cached despite the prior read error.
    assert mock_write.call_count == 1


def test_cache_write_error_does_not_raise() -> None:
    """A cache write failure must be swallowed — the result is still returned."""
    from application import risk_second_opinion as mod

    class _StubSummarizer:
        def summarize_case(self, ctx: object) -> CaseResult:
            return _GOOD_RESULT

    with (
        patch.object(mod, "load_cached_case", return_value=None),
        patch.object(mod, "write_case_cache", side_effect=OSError("disk full")),
    ):
        result = mod.build_risk_second_opinion(
            macro_facts=["net beta 1.18"],
            summarizer=_StubSummarizer(),  # type: ignore[arg-type]
            use_cache=True,
        )

    # Result returned successfully despite write error.
    assert result is _GOOD_RESULT


def test_no_real_cache_file_written_by_tests(tmp_path: pytest.TempPathFactory) -> None:
    """All cache-exercising tests above monkeypatch load/write — real file untouched.

    This test is a belt-and-suspenders guard: calling with use_cache=False
    must never touch the filesystem at the real CITED_CASES_PATH.
    """
    import os

    from application import risk_second_opinion as mod

    real_path = mod._CITED_CASES_PATH

    class _StubSummarizer:
        def summarize_case(self, ctx: object) -> CaseResult:
            return _GOOD_RESULT

    existed_before = os.path.exists(real_path)

    mod.build_risk_second_opinion(
        macro_facts=["net beta 1.18"],
        summarizer=_StubSummarizer(),  # type: ignore[arg-type]
        use_cache=False,
    )

    existed_after = os.path.exists(real_path)
    # File must not have been created by this test run.
    assert (
        existed_before == existed_after
    ), "use_cache=False must not touch the real cache file"


# ---------------------------------------------------------------------------
# load_cached_risk_second_opinion tests
# ---------------------------------------------------------------------------


def test_load_cached_risk_second_opinion_hits_cache() -> None:
    """load_cached_risk_second_opinion returns the value from load_cached_case."""
    from application import risk_second_opinion as mod

    with patch.object(mod, "load_cached_case", return_value=_GOOD_RESULT) as mock_load:
        result = mod.load_cached_risk_second_opinion()

    assert result is _GOOD_RESULT
    mock_load.assert_called_once_with(mod._CITED_CASES_PATH, mod._CACHE_KEY)


def test_load_cached_risk_second_opinion_missing_returns_none() -> None:
    """load_cached_risk_second_opinion returns None when cache returns None."""
    from application import risk_second_opinion as mod

    with patch.object(mod, "load_cached_case", return_value=None):
        result = mod.load_cached_risk_second_opinion()

    assert result is None


def test_load_cached_risk_second_opinion_exception_returns_none() -> None:
    """load_cached_risk_second_opinion swallows exceptions and returns None."""
    from application import risk_second_opinion as mod

    with patch.object(mod, "load_cached_case", side_effect=OSError("disk error")):
        result = mod.load_cached_risk_second_opinion()

    assert result is None
