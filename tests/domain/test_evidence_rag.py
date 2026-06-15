# tests/domain/test_evidence_rag.py
import dataclasses

from domain.evidence_rag import DIMENSIONS, RagColor, RagSignal, classify_technicals


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
    assert dataclasses.is_dataclass(sig)
    try:
        sig.detail = "x"  # type: ignore[misc]
        raised = False
    except dataclasses.FrozenInstanceError:
        raised = True
    assert raised


def test_technicals_below_trend_is_red():
    sig = classify_technicals(atr_vs_200d=-2.3, vs_spy_pct=-9.0)
    assert sig.color is RagColor.RED
    assert "200-day" in sig.detail and "SPY" in sig.detail


def test_technicals_above_trend_is_green():
    assert classify_technicals(atr_vs_200d=1.2, vs_spy_pct=4.0).color is RagColor.GREEN


def test_technicals_mid_is_amber():
    assert classify_technicals(atr_vs_200d=-0.4, vs_spy_pct=1.0).color is RagColor.AMBER


def test_technicals_missing_is_gap():
    sig = classify_technicals(atr_vs_200d=None, vs_spy_pct=None)
    assert sig.color is RagColor.GAP
    assert "DATA-GAP" in sig.detail
