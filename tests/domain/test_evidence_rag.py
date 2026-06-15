# tests/domain/test_evidence_rag.py
import dataclasses

from hypothesis import given
from hypothesis import strategies as st

from domain.evidence_rag import (
    DIMENSIONS,
    RagColor,
    RagSignal,
    classify_analysts,
    classify_earnings,
    classify_financials,
    classify_technicals,
    classify_valuation,
)


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


def test_valuation_cheap_is_green():
    sig = classify_valuation(peg=0.9, pe=19.0, sector_pctile=62.0)
    assert sig.color is RagColor.GREEN
    assert "PEG 0.9" in sig.detail and "62%" in sig.detail


def test_valuation_expensive_is_red():
    assert (
        classify_valuation(peg=3.1, pe=44.0, sector_pctile=15.0).color is RagColor.RED
    )


def test_valuation_mid_is_amber():
    assert (
        classify_valuation(peg=1.8, pe=22.0, sector_pctile=45.0).color is RagColor.AMBER
    )


def test_valuation_missing_is_gap():
    assert (
        classify_valuation(peg=None, pe=None, sector_pctile=None).color is RagColor.GAP
    )


def test_financials_healthy_is_green():
    sig = classify_financials(
        fcf_positive=True, debt_to_equity=45.0, margins_stable=True
    )
    assert sig.color is RagColor.GREEN
    assert "FCF positive" in sig.detail


def test_financials_levered_or_burning_is_red():
    assert (
        classify_financials(
            fcf_positive=False, debt_to_equity=40.0, margins_stable=True
        ).color
        is RagColor.RED
    )
    assert (
        classify_financials(
            fcf_positive=True, debt_to_equity=210.0, margins_stable=True
        ).color
        is RagColor.RED
    )


def test_financials_missing_is_gap():
    assert (
        classify_financials(
            fcf_positive=None, debt_to_equity=None, margins_stable=None
        ).color
        is RagColor.GAP
    )


def test_earnings_mostly_beats_is_green():
    sig = classify_earnings(beats=3, total=4)
    assert sig.color is RagColor.GREEN
    assert "beat 3 of 4" in sig.detail and "revenue surprise" in sig.detail.lower()


def test_earnings_mostly_miss_is_red():
    assert classify_earnings(beats=0, total=4).color is RagColor.RED


def test_earnings_no_data_is_gap():
    assert classify_earnings(beats=None, total=None).color is RagColor.GAP
    assert classify_earnings(beats=0, total=0).color is RagColor.GAP


def test_analysts_wide_spread_is_amber():
    sig = classify_analysts(
        count=43,
        target_mean=47.8,
        target_high=70.0,
        target_low=30.0,
        data_gap=False,
        current_price=44.63,
    )  # spread ~0.84
    assert sig.color is RagColor.AMBER
    assert "43 cover" in sig.detail


def test_analysts_tight_upside_is_green():
    assert (
        classify_analysts(
            count=43,
            target_mean=50.0,
            target_high=52.0,
            target_low=48.0,
            data_gap=False,
            current_price=44.63,
        ).color
        is RagColor.GREEN
    )


def test_analysts_tight_downside_is_red():
    assert (
        classify_analysts(
            count=43,
            target_mean=40.0,
            target_high=42.0,
            target_low=39.0,
            data_gap=False,
            current_price=44.63,
        ).color
        is RagColor.RED
    )


def test_analysts_gap():
    assert (
        classify_analysts(
            count=0,
            target_mean=None,
            target_high=None,
            target_low=None,
            data_gap=True,
            current_price=44.63,
        ).color
        is RagColor.GAP
    )


@given(
    beats=st.integers(min_value=0, max_value=20),
    total=st.integers(min_value=1, max_value=20),
)
def test_earnings_color_total_in_range(beats: int, total: int) -> None:
    sig = classify_earnings(min(beats, total), total)
    assert sig.color in {
        RagColor.RED,
        RagColor.AMBER,
        RagColor.GREEN,
    }  # never GAP when total>0


@given(atr=st.floats(min_value=-10, max_value=10, allow_nan=False))
def test_technicals_monotone_buckets(atr: float) -> None:
    c = classify_technicals(atr, 0.0).color
    if atr >= 0.5:
        assert c is RagColor.GREEN
    elif atr <= -1.5:
        assert c is RagColor.RED
    else:
        assert c is RagColor.AMBER
