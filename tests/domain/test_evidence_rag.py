# tests/domain/test_evidence_rag.py
from domain.evidence_rag import DIMENSIONS, RagColor, RagSignal


def test_dimensions_fixed_order():
    assert DIMENSIONS == (
        "Technicals",
        "Valuation",
        "Financials",
        "Earnings",
        "Analysts",
    )


def test_rag_signal_is_frozen():
    sig = RagSignal(
        dimension="Technicals", color=RagColor.RED, detail="2.3 ATR below 200-day"
    )
    assert sig.color is RagColor.RED
    assert sig.detail == "2.3 ATR below 200-day"
    import dataclasses

    assert dataclasses.is_dataclass(sig)
    try:
        sig.detail = "x"  # type: ignore[misc]
        raised = False
    except dataclasses.FrozenInstanceError:
        raised = True
    assert raised
