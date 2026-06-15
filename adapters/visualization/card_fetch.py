"""Streamlit-cached card fetches + the lazy-case gate."""

from __future__ import annotations

from application.case_builder import build_case_context
from application.evidence_card import EvidenceCard
from domain.case_models import CaseResult
from domain.evidence_rag import RagColor


def get_case_on_expand(
    ticker: str,
    card: EvidenceCard,
    news: list[object],
    *,
    expanded: bool,
    summarizer: object,
) -> CaseResult | None:
    """Fetch the cited case ONLY when the card is expanded. Returns None when collapsed."""
    if not expanded:
        return None
    sigs = tuple(s for s in card.signals if s.color is not RagColor.GAP)
    ctx = build_case_context(ticker, sigs, news)  # type: ignore[arg-type]
    result: CaseResult = summarizer.summarize_case(ctx)  # type: ignore[attr-defined]
    return result
