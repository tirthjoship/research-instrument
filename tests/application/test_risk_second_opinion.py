"""TDD tests for application.risk_second_opinion — fail first, then implement."""

from __future__ import annotations

from domain.case_models import CaseResult
from domain.fit import FORBIDDEN_WORDS


def test_template_fallback_no_forbidden_words() -> None:
    """Template fallback (no summarizer, no API key) must emit zero forbidden words."""
    from application.risk_second_opinion import build_risk_second_opinion

    res = build_risk_second_opinion(
        macro_facts=["systematic share 71%"], summarizer=None
    )
    text = " ".join(p.text for p in res.in_favor + res.to_watch).lower()
    assert not any(w in text for w in FORBIDDEN_WORDS)


def test_returns_case_result_type() -> None:
    """build_risk_second_opinion always returns a CaseResult."""
    from application.risk_second_opinion import build_risk_second_opinion

    res = build_risk_second_opinion(macro_facts=["net beta 1.18"], summarizer=None)
    assert isinstance(res, CaseResult)


def test_empty_facts_returns_data_gap() -> None:
    """Empty facts list with no summarizer must return data_gap=True (no fake content)."""
    from application.risk_second_opinion import build_risk_second_opinion

    res = build_risk_second_opinion(macro_facts=[], summarizer=None)
    assert res.data_gap is True


def test_error_in_summarizer_returns_data_gap() -> None:
    """Any exception from an injected summarizer yields data_gap=True — never raises."""
    from application.risk_second_opinion import build_risk_second_opinion

    class _BrokenSummarizer:
        def summarize_case(self, ctx: object) -> CaseResult:
            raise RuntimeError("network down")

    res = build_risk_second_opinion(
        macro_facts=["net beta 1.18"], summarizer=_BrokenSummarizer()  # type: ignore[arg-type]
    )
    assert res.data_gap is True


def test_injected_summarizer_result_passed_through() -> None:
    """A well-behaved summarizer's result is returned as-is (no mutation)."""
    from application.risk_second_opinion import build_risk_second_opinion
    from domain.case_models import CasePoint

    expected = CaseResult(
        in_favor=(CasePoint(text="test point", source_tag="test"),),
        to_watch=(),
        data_gap=False,
    )

    class _StubSummarizer:
        def summarize_case(self, ctx: object) -> CaseResult:
            return expected

    res = build_risk_second_opinion(
        macro_facts=["net beta 1.18"], summarizer=_StubSummarizer()  # type: ignore[arg-type]
    )
    assert res is expected
