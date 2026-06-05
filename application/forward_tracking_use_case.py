"""Resolve surfaced calls at 1w/1m/3m vs SPY+NDX; feed Phase 8 signal performance."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from domain.outcome import TradeOutcome
from domain.outcome_service import compute_signal_performance
from domain.surfaced_call import CallOutcome

_EVIDENCE_SIGNAL_MIN = 6.0


def _price_on_or_after(
    md: Any, ticker: str, target: datetime, now: datetime
) -> float | None:
    sigs = md.get_signals(ticker, now, start_date=target, end_date=now)
    asc = sorted(sigs, key=lambda s: s.timestamp)
    return asc[0].price if asc else None


def _price_on_or_before(md: Any, ticker: str, target: datetime) -> float | None:
    sigs = md.get_signals(ticker, target)
    asc = sorted(sigs, key=lambda s: s.timestamp)
    return asc[-1].price if asc else None


class ForwardTrackingUseCase:
    def __init__(self, store: Any, market_data: Any) -> None:
        self._store = store
        self._md = market_data

    def resolve_due_calls(self, now: datetime) -> list[CallOutcome]:
        resolved: list[CallOutcome] = []
        for call, horizon in self._store.get_due_calls(now):
            exit_target = call.surfaced_at + timedelta(days=horizon.value)
            entry = _price_on_or_before(self._md, call.ticker, call.surfaced_at)
            exit_p = _price_on_or_after(self._md, call.ticker, exit_target, now)
            spy_e = _price_on_or_before(self._md, "SPY", call.surfaced_at)
            spy_x = _price_on_or_after(self._md, "SPY", exit_target, now)
            ndx_e = _price_on_or_before(self._md, "QQQ", call.surfaced_at)
            ndx_x = _price_on_or_after(self._md, "QQQ", exit_target, now)
            if None in (entry, exit_p, spy_e, spy_x, ndx_e, ndx_x):
                continue
            assert entry is not None
            assert exit_p is not None
            assert spy_e is not None
            assert spy_x is not None
            assert ndx_e is not None
            assert ndx_x is not None
            if entry == 0:
                continue
            fwd = (exit_p - entry) / entry
            spy_r = (spy_x - spy_e) / spy_e if spy_e else 0.0
            ndx_r = (ndx_x - ndx_e) / ndx_e if ndx_e else 0.0
            outcome = CallOutcome(
                call_id=call.call_id,
                horizon=horizon,
                resolved_at=now,
                entry_price=entry,
                exit_price=exit_p,
                forward_return=fwd,
                spy_return=spy_r,
                ndx_return=ndx_r,
                beat_spy=fwd > spy_r,
                beat_ndx=fwd > ndx_r,
                beat_both=fwd > spy_r and fwd > ndx_r,
            )
            self._store.save_outcome(outcome)
            resolved.append(outcome)
        return resolved

    def get_track_record(self) -> list[Any]:
        by_id = {c.call_id: c for c in self._store.get_all_calls()}
        trade_outcomes: list[TradeOutcome] = []
        for oc in self._store.get_outcomes():
            call = by_id.get(oc.call_id)
            if call is None:
                continue
            signals = [
                e.dimension for e in call.evidence if e.score >= _EVIDENCE_SIGNAL_MIN
            ]
            trade_outcomes.append(
                TradeOutcome(
                    ticker=call.ticker,
                    buy_trade_id=f"{oc.call_id}:{oc.horizon.value}",
                    sell_trade_id=f"{oc.call_id}:{oc.horizon.value}:x",
                    buy_price=oc.entry_price,
                    sell_price=oc.exit_price,
                    quantity=1,
                    buy_date=call.surfaced_at.strftime("%Y-%m-%d"),
                    sell_date=oc.resolved_at.strftime("%Y-%m-%d"),
                    holding_days=oc.horizon.value,
                    return_pct=oc.forward_return * 100.0,
                    return_dollar=oc.exit_price - oc.entry_price,
                    signals_at_entry=signals,
                    conviction_at_entry=call.conviction,
                )
            )
        return compute_signal_performance(trade_outcomes)
