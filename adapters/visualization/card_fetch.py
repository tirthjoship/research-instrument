"""Streamlit-cached card fetches + the lazy-case gate.

Cache-first strategy (D2):
  1. If collapsed → return None immediately (no work).
  2. If expanded → check weekly cited-case cache (data/personal/cited_cases.json).
     Cache hit → return cached CaseResult, zero live pings.
     Cache miss → call summarizer.summarize_case (live Gemini ping, throttled).
"""

from __future__ import annotations

from application.case_builder import build_case_context
from application.case_cache import CITED_CASES_PATH, load_cached_case
from application.evidence_card import EvidenceCard
from domain.case_models import CaseResult
from domain.evidence_rag import RagColor

# Module-level path constant — monkeypatchable in tests.
_CITED_CASES_PATH: str = CITED_CASES_PATH


def get_case_on_expand(
    ticker: str,
    card: EvidenceCard,
    news: list[object],
    *,
    expanded: bool,
    summarizer: object,
) -> CaseResult | None:
    """Fetch the cited case ONLY when the card is expanded. Returns None when collapsed.

    Cache-first: checks the weekly cited-case cache before making a live Gemini
    ping.  A cache hit returns immediately with zero network calls.  Only on a
    miss is summarizer.summarize_case(...) invoked (the throttled live path).
    """
    if not expanded:
        return None

    # Cache-first: weekly prefetch wins over live ping.
    cached = load_cached_case(_CITED_CASES_PATH, ticker)
    if cached is not None:
        return cached

    # Cache miss — live ping (rate-limited by the summarizer itself).
    sigs = tuple(s for s in card.signals if s.color is not RagColor.GAP)
    ctx = build_case_context(ticker, sigs, news)  # type: ignore[arg-type]
    result: CaseResult = summarizer.summarize_case(ctx)  # type: ignore[attr-defined]
    return result
