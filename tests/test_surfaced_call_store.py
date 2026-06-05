# tests/test_surfaced_call_store.py
from datetime import datetime, timezone

from adapters.data.sqlite_store import SQLiteStore
from domain.surfaced_call import (
    CallOutcome,
    EvidenceItem,
    Horizon,
    OpportunityDirection,
    SurfacedCall,
)


def _utc(y, m, d):
    return datetime(y, m, d, tzinfo=timezone.utc)


def _call(ticker="ASTS", at=None):
    at = at or _utc(2026, 5, 1)
    return SurfacedCall(
        call_id=f"{ticker}_{at:%Y%m%d}",
        ticker=ticker,
        surfaced_at=at,
        conviction=7.0,
        divergence_score=8.0,
        direction=OpportunityDirection.BUY,
        evidence=(EvidenceItem("event_signal", 9.0, "halo"),),
        theme="space",
        cap_tier="small",
        spy_at_surface=500.0,
        ndx_at_surface=440.0,
    )


def test_save_and_get_call_roundtrip():
    s = SQLiteStore(":memory:")
    c = _call()
    s.save_call(c)
    assert s.get_call(c.call_id) == c


def test_due_calls_only_after_horizon_matures():
    s = SQLiteStore(":memory:")
    c = _call(at=_utc(2026, 5, 1))
    s.save_call(c)
    due = s.get_due_calls(_utc(2026, 5, 9))  # 8 days → only W1 (7d) due
    assert (c, Horizon.W1) in due
    assert (c, Horizon.M1) not in due


def test_resolved_horizon_not_returned_again():
    s = SQLiteStore(":memory:")
    c = _call(at=_utc(2026, 5, 1))
    s.save_call(c)
    s.save_outcome(
        CallOutcome(
            call_id=c.call_id,
            horizon=Horizon.W1,
            resolved_at=_utc(2026, 5, 9),
            entry_price=10.0,
            exit_price=11.0,
            forward_return=0.1,
            spy_return=0.01,
            ndx_return=0.01,
            beat_spy=True,
            beat_ndx=True,
            beat_both=True,
        )
    )
    due = s.get_due_calls(_utc(2026, 5, 9))
    assert (c, Horizon.W1) not in due
    assert len(s.get_outcomes()) == 1
