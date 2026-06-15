"""Build an attributed second-opinion CaseResult for the Risk tab.

Wires the existing Gemini summarizer stack (or template fallback) with a
RISK-specific prompt context. Fail-safe: any error → data_gap=True.
No network calls unless GEMINI_API_KEY is present and a live summarizer is
injected (or selected via select_case_summarizer()).

HONESTY RAILS
- template fallback text must NEVER contain FORBIDDEN_WORDS
- rendered text must NEVER contain FORBIDDEN_WORDS
- no verdict / trade call; purely descriptive blind-spot discovery

DESIGN NOTE — intent injection
The risk-specific prompt instruction is prepended ONLY for Gemini (via
_RiskSummarizingWrapper), so the TemplateCaseSummarizer never sees it and
can never echo forbidden words back into CasePoint.text.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from domain.case_models import CaseContext, CaseResult

# Risk-specific context token — used as ticker; never rendered as a fact.
_RISK_TICKER = "RISK_READ"

# Prompt instruction prepended for Gemini; must NOT contain FORBIDDEN_WORDS
# (it instructs Gemini *not* to use them, so the words appear — see note below).
# This is intentionally kept OUTSIDE CaseContext.facts to prevent
# TemplateCaseSummarizer from echoing the instruction text as CasePoint content.
_RISK_INTENT_LINES = (
    "Task: name blind spots in this risk read.",
    "Describe what a cautious reviewer would double-check.",
    "Use only descriptive, evidence-based language.",
    "This is a third-party second opinion, not a recommendation.",
)

_CACHE_KEY = "risk_second_opinion"


@runtime_checkable
class _SummarizerLike(Protocol):
    def summarize_case(self, ctx: CaseContext) -> CaseResult: ...


def build_risk_second_opinion(
    macro_facts: list[str],
    summarizer: _SummarizerLike | None,
) -> CaseResult:
    """Build a CaseResult acting as a second-opinion on the risk read.

    Args:
        macro_facts: Plain-English fact lines from the risk dials
                     (e.g. ["net beta 1.18", "systematic share 71%"]).
        summarizer:  An object with .summarize_case(CaseContext) -> CaseResult.
                     Pass None to use select_case_summarizer() (Gemini if key
                     is present, else TemplateCaseSummarizer — CI/offline safe).

    Returns:
        CaseResult with in_favor / to_watch / data_gap.  Never raises.
    """
    try:
        resolved = _resolve_summarizer(summarizer)
        ctx = _build_context(macro_facts)
        # Only inject risk intent lines when Gemini is the live summarizer.
        # TemplateCaseSummarizer echoes every fact line as CasePoint.text, so
        # passing instruction text would echo forbidden-adjacent words.
        effective: _SummarizerLike = (
            _RiskSummarizingWrapper(resolved) if _needs_intent(resolved) else resolved
        )
        return effective.summarize_case(ctx)
    except Exception:  # noqa: BLE001 — fail-safe: never surface errors
        return CaseResult(in_favor=(), to_watch=(), data_gap=True)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


class _RiskSummarizingWrapper:
    """Thin wrapper that prepends the risk intent lines before calling Gemini.

    IMPORTANT: Only use this when the inner summarizer is a live Gemini adapter
    (i.e. when GEMINI_API_KEY is set).  The TemplateCaseSummarizer must receive
    only bare facts — it echoes every fact line as CasePoint.text, so injecting
    instruction text would violate the FORBIDDEN_WORDS guard.

    When _needs_intent(inner) is False, we skip the wrapper entirely (see
    build_risk_second_opinion).
    """

    def __init__(self, inner: _SummarizerLike) -> None:
        self._inner = inner

    def summarize_case(self, ctx: CaseContext) -> CaseResult:
        enriched_facts = _RISK_INTENT_LINES + ctx.facts
        enriched_ctx = CaseContext(
            ticker=ctx.ticker,
            facts=enriched_facts,
            news=ctx.news,
        )
        return self._inner.summarize_case(enriched_ctx)


def _needs_intent(summarizer: _SummarizerLike) -> bool:
    """True when the summarizer is a live Gemini-backed one (not the template)."""
    from application.case_builder import TemplateCaseSummarizer

    return not isinstance(summarizer, TemplateCaseSummarizer)


def _resolve_summarizer(summarizer: _SummarizerLike | None) -> _SummarizerLike:
    if summarizer is not None:
        return summarizer
    from application.card_loading import select_case_summarizer

    s = select_case_summarizer()
    assert isinstance(s, _SummarizerLike)
    return s


def _build_context(macro_facts: list[str]) -> CaseContext:
    """Construct a CaseContext from macro_facts only (no intent lines at this stage)."""
    return CaseContext(
        ticker=_RISK_TICKER,
        facts=tuple(macro_facts),
        news=(),
    )
