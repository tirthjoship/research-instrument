# tests/test_surfaced_call.py
from datetime import datetime, timezone

import pytest

from domain.surfaced_call import (
    CallOutcome,
    EvidenceItem,
    Horizon,
    OpportunityDirection,
    SurfacedCall,
    make_call_id,
)


def _utc(y, m, d):
    return datetime(y, m, d, tzinfo=timezone.utc)


def test_make_call_id_is_deterministic():
    t = _utc(2026, 6, 5)
    assert make_call_id("ASTS", t) == "ASTS_20260605"


def test_surfaced_call_valid():
    call = SurfacedCall(
        call_id="ASTS_20260605",
        ticker="ASTS",
        surfaced_at=_utc(2026, 6, 5),
        conviction=7.5,
        divergence_score=8.0,
        direction=OpportunityDirection.BUY,
        evidence=(EvidenceItem("event_signal", 9.0, "SpaceX IPO halo"),),
        theme="space",
        cap_tier="small",
        spy_at_surface=540.0,
        ndx_at_surface=470.0,
    )
    assert call.ticker == "ASTS"
    assert call.direction is OpportunityDirection.BUY


@pytest.mark.parametrize("conv", [-1.0, 11.0])
def test_surfaced_call_rejects_out_of_range_conviction(conv):
    with pytest.raises(ValueError):
        SurfacedCall(
            call_id="X_20260605",
            ticker="X",
            surfaced_at=_utc(2026, 6, 5),
            conviction=conv,
            divergence_score=5.0,
            direction=OpportunityDirection.BUY,
            evidence=(),
            theme=None,
            cap_tier="mid",
            spy_at_surface=1.0,
            ndx_at_surface=1.0,
        )


def test_surfaced_call_requires_tz_aware():
    with pytest.raises(ValueError):
        SurfacedCall(
            call_id="X_20260605",
            ticker="X",
            surfaced_at=datetime(2026, 6, 5),
            conviction=5.0,
            divergence_score=5.0,
            direction=OpportunityDirection.BUY,
            evidence=(),
            theme=None,
            cap_tier="mid",
            spy_at_surface=1.0,
            ndx_at_surface=1.0,
        )


def test_horizon_days():
    assert (Horizon.W1.value, Horizon.M1.value, Horizon.M3.value) == (7, 30, 90)


def test_call_outcome_beats():
    oc = CallOutcome(
        call_id="ASTS_20260605",
        horizon=Horizon.M1,
        resolved_at=_utc(2026, 7, 5),
        entry_price=10.0,
        exit_price=13.0,
        forward_return=0.30,
        spy_return=0.05,
        ndx_return=0.04,
        beat_spy=True,
        beat_ndx=True,
        beat_both=True,
    )
    assert oc.beat_both is True
