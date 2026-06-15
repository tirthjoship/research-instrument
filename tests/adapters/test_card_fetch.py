from __future__ import annotations

from adapters.visualization.card_fetch import get_case_on_expand
from application.evidence_card import EvidenceCard
from domain.case_models import CaseResult
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
