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

CACHE STRATEGY (spec §9 — no live per-render Gemini calls)
Cache-first: on every call (when use_cache=True), we check the cited-case
store before calling the summarizer.  A hit returns immediately, zero network
calls.  On a miss we call the summarizer and write the result to the cache so
subsequent renders are served from disk.  data_gap / error results are NOT
cached so a transient failure retries on the next call.  Cache read/write
errors are swallowed — a corrupt or missing cache file degrades gracefully to
"no cache" and proceeds normally.
"""

from __future__ import annotations

import datetime
from typing import Protocol, runtime_checkable

from application.case_cache import CITED_CASES_PATH, load_cached_case, write_case_cache
from domain.case_models import CaseContext, CaseResult

# Risk-specific context token — used as ticker; never rendered as a fact.
_RISK_TICKER = "RISK_READ"

# Prompt instruction prepended for Gemini; must NOT contain FORBIDDEN_WORDS.
# These lines describe the task intent and are injected only for live Gemini
# calls via _RiskSummarizingWrapper — TemplateCaseSummarizer never sees them.
_RISK_INTENT_LINES = (
    "Task: name blind spots in this risk read.",
    "Describe what a cautious reviewer would double-check.",
    "Use only descriptive, evidence-based language.",
    "This is a third-party second opinion, not a recommendation.",
)

# Cache key (used as ticker in cited_cases.json) — distinct from per-stock tickers.
_CACHE_KEY = "risk_second_opinion"

# Module-level path constant — monkeypatchable in tests (mirrors card_fetch pattern).
_CITED_CASES_PATH: str = CITED_CASES_PATH


@runtime_checkable
class _SummarizerLike(Protocol):
    def summarize_case(self, ctx: CaseContext) -> CaseResult: ...


def build_risk_second_opinion(
    macro_facts: list[str],
    summarizer: _SummarizerLike | None,
    *,
    use_cache: bool = True,
) -> CaseResult:
    """Build a CaseResult acting as a second-opinion on the risk read.

    Cache-first (spec §9): checks the cited-case store before calling the
    summarizer.  A hit returns immediately with zero network calls.  On a miss
    the summarizer is called and the result is written to the cache (unless it
    is a data_gap/error result — failures are not cached so they retry).

    Args:
        macro_facts: Plain-English fact lines from the risk dials
                     (e.g. ["net beta 1.18", "systematic share 71%"]).
        summarizer:  An object with .summarize_case(CaseContext) -> CaseResult.
                     Pass None to use select_case_summarizer() (Gemini if key
                     is present, else TemplateCaseSummarizer — CI/offline safe).
        use_cache:   When False, skip cache read/write entirely.  Intended for
                     unit tests that should not touch the real cache file.

    Returns:
        CaseResult with in_favor / to_watch / data_gap.  Never raises.
    """
    # Cache-first lookup (swallow any read error — missing/corrupt = cache miss).
    if use_cache:
        try:
            cached = load_cached_case(_CITED_CASES_PATH, _CACHE_KEY)
            if cached is not None:
                return cached
        except Exception:  # noqa: BLE001
            pass  # treat as cache miss; proceed to summarizer

    try:
        resolved = _resolve_summarizer(summarizer)
        ctx = _build_context(macro_facts)
        # Only inject risk intent lines when Gemini is the live summarizer.
        # TemplateCaseSummarizer echoes every fact line as CasePoint.text, so
        # passing instruction text would echo forbidden-adjacent words.
        effective: _SummarizerLike = (
            _RiskSummarizingWrapper(resolved) if _needs_intent(resolved) else resolved
        )
        result = effective.summarize_case(ctx)
    except Exception:  # noqa: BLE001 — fail-safe: never surface errors
        return CaseResult(in_favor=(), to_watch=(), data_gap=True)

    # Write successful (non-data_gap) results to cache; swallow write errors.
    if use_cache and not result.data_gap:
        try:
            as_of = datetime.date.today().isoformat()
            write_case_cache(_CITED_CASES_PATH, as_of, {_CACHE_KEY: result})
        except Exception:  # noqa: BLE001
            pass  # cache write failure is non-fatal

    return result


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
