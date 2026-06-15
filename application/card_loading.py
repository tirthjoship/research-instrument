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


_GEMINI_DEFAULT_INTERVAL_S: float = (
    5.0  # matches config/markets/us.yaml gemini.min_interval_seconds
)


def select_case_summarizer() -> object:
    """Gemini (rate-limited) if a key is present, else the deterministic template (CI/no-key safe).

    Buffer is read from GEMINI_MIN_INTERVAL_S env var if set, else defaults to
    _GEMINI_DEFAULT_INTERVAL_S (5.0 s — safe margin below Gemini free-tier ~14 rpm limit).
    The TemplateCaseSummarizer path is unthrottled (local/instant).
    """
    import os

    from application.case_builder import TemplateCaseSummarizer

    if os.environ.get("GEMINI_API_KEY"):
        from adapters.ml.gemini_narrator import GeminiNarratorAdapter
        from application.rate_limited_summarizer import RateLimitedCaseSummarizer

        raw = os.environ.get("GEMINI_MIN_INTERVAL_S")
        min_interval = float(raw) if raw is not None else _GEMINI_DEFAULT_INTERVAL_S
        return RateLimitedCaseSummarizer(
            GeminiNarratorAdapter(), min_interval_s=min_interval
        )
    return TemplateCaseSummarizer()
