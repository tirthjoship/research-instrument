# tests/test_forward_tracking.py
from datetime import datetime, timedelta, timezone

from application.forward_tracking_use_case import ForwardTrackingUseCase
from domain.models import Signal
from domain.surfaced_call import (
    EvidenceItem,
    Horizon,
    OpportunityDirection,
    SurfacedCall,
)
from tests.fakes.fake_market_data import FakeMarketData
from tests.fakes.fake_surfaced_call_store import FakeSurfacedCallStore


def _utc(y, m, d):
    return datetime(y, m, d, tzinfo=timezone.utc)


def _price_points(symbol, start, days, fn):
    return [
        Signal(
            symbol=symbol,
            timestamp=start + timedelta(days=i),
            price=fn(i),
            volume=1.0,
            open_=fn(i),
            high=fn(i),
            low=fn(i),
        )
        for i in range(days)
    ]


def _call():
    at = _utc(2026, 5, 1)
    return SurfacedCall(
        call_id="ASTS_20260501",
        ticker="ASTS",
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


def test_resolves_w1_outcome_vs_benchmarks():
    start = _utc(2026, 5, 1)
    md = FakeMarketData(
        signals={
            "ASTS": _price_points("ASTS", start, 20, lambda i: 10.0 + i),
            "SPY": _price_points("SPY", start, 20, lambda i: 500.0),
            "QQQ": _price_points("QQQ", start, 20, lambda i: 440.0),
        }
    )
    store = FakeSurfacedCallStore()
    store.save_call(_call())
    uc = ForwardTrackingUseCase(store=store, market_data=md)
    outcomes = uc.resolve_due_calls(_utc(2026, 5, 9))
    w1 = [o for o in outcomes if o.horizon is Horizon.W1]
    assert len(w1) == 1
    assert w1[0].forward_return > 0
    assert w1[0].beat_spy is True
    assert len(store.get_outcomes()) == 1


def test_track_record_aggregates_by_signal():
    start = _utc(2026, 5, 1)
    md = FakeMarketData(
        signals={
            "ASTS": _price_points("ASTS", start, 40, lambda i: 10.0 + i),
            "SPY": _price_points("SPY", start, 40, lambda i: 500.0),
            "QQQ": _price_points("QQQ", start, 40, lambda i: 440.0),
        }
    )
    store = FakeSurfacedCallStore()
    store.save_call(_call())
    uc = ForwardTrackingUseCase(store=store, market_data=md)
    uc.resolve_due_calls(_utc(2026, 8, 1))
    perfs = uc.get_track_record()
    assert "event_signal" in {p.signal_name for p in perfs}
