"""Pure data-readiness state for a card row. PENDING≠GAP (shimmer vs hatched)."""

from __future__ import annotations

from enum import Enum

from application.evidence_card import EvidenceCard
from domain.evidence_rag import RagColor


class RowState(Enum):
    PENDING = "pending"  # loading — render shimmer
    READY = "ready"  # has real signals
    GAP = "gap"  # genuine data gap — render hatched, never shimmer forever


def card_state(card: EvidenceCard) -> RowState:
    if not card.signals:
        return RowState.PENDING
    if all(s.color is RagColor.GAP for s in card.signals):
        return RowState.GAP
    return RowState.READY


def select_case_summarizer() -> object:
    """Gemini if a key is present, else the deterministic template (CI/no-key safe)."""
    import os

    from application.case_builder import TemplateCaseSummarizer

    if os.environ.get("GEMINI_API_KEY"):
        from adapters.ml.gemini_narrator import GeminiNarratorAdapter

        return GeminiNarratorAdapter()
    return TemplateCaseSummarizer()
