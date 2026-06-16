from __future__ import annotations

from application.card_loading import RowState, card_state
from application.evidence_card import EvidenceCard
from domain.evidence_rag import DIMENSIONS, RagColor, RagSignal


def _card(colors: list[RagColor]) -> EvidenceCard:
    sigs = tuple(RagSignal(d, c, "x") for d, c in zip(DIMENSIONS, colors))
    return EvidenceCard("T", sigs, ())


def test_ready_when_any_real_signal() -> None:
    c = _card([RagColor.GREEN, RagColor.GAP, RagColor.GAP, RagColor.GAP, RagColor.GAP])
    assert card_state(c) is RowState.READY


def test_gap_when_all_gap() -> None:
    c = _card([RagColor.GAP] * 5)
    assert card_state(c) is RowState.GAP


def test_pending_when_no_signals() -> None:
    assert card_state(EvidenceCard("T", (), ())) is RowState.PENDING
