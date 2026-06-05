# application/opportunity_scan_use_case.py
"""Surface emerging opportunities: conviction x early-divergence, with abstention."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable

from domain.divergence_service import blended_divergence_score
from domain.surfaced_call import (
    EvidenceItem,
    OpportunityDirection,
    SurfacedCall,
    make_call_id,
)

ConvictionProvider = Callable[[str, datetime], tuple[float, dict[str, float]]]


def _match_awareness(ts: datetime, ref: datetime) -> datetime:
    """Coerce ``ts`` to ``ref``'s tz-awareness.

    Stored timestamps (SQLite buzz ``fetched_at``, some price series) are
    tz-naive, while the CLI passes a tz-aware UTC ``now``. Comparing them
    raises TypeError, so normalize inbound timestamps to the reference's
    awareness before any arithmetic or comparison.
    """
    if ref.tzinfo is not None and ts.tzinfo is None:
        return ts.replace(tzinfo=ref.tzinfo)
    if ref.tzinfo is None and ts.tzinfo is not None:
        return ts.replace(tzinfo=None)
    return ts


def _cap_tier(market_cap: float) -> str:
    if market_cap >= 1e10:
        return "large"
    if market_cap >= 2e9:
        return "mid"
    return "small"


class OpportunityScanUseCase:
    def __init__(
        self,
        universe_provider: Any,
        conviction_provider: ConvictionProvider,
        buzz_discovery: Any,
        market_data: Any,
        store: Any,
        attention_provider: Any = None,
        cmin: float = 6.0,
        dmin: float = 6.0,
    ) -> None:
        self._universe = universe_provider
        self._conviction = conviction_provider
        self._buzz = buzz_discovery
        self._md = market_data
        self._store = store
        self._attn = attention_provider
        self._cmin = cmin
        self._dmin = dmin

    def _intensity_series(
        self, ticker: str, now: datetime
    ) -> list[tuple[datetime, float]]:
        if self._attn is None:
            return []
        start = now - timedelta(days=40)
        pts = self._attn.get_attention_series(ticker, start, now)
        return [(_match_awareness(p.timestamp, now), p.value) for p in pts]

    def _price_series(self, ticker: str, now: datetime) -> list[tuple[datetime, float]]:
        start = now - timedelta(days=40)
        sigs = self._md.get_signals(ticker, now, start_date=start, end_date=now)
        return [(_match_awareness(s.timestamp, now), s.price) for s in sigs]

    def _benchmark(self, symbol: str, now: datetime) -> float:
        sigs = self._md.get_signals(symbol, now, end_date=now)
        return float(sigs[-1].price) if sigs else 0.0

    def execute(
        self, now: datetime, *, allow_abstention: bool = True
    ) -> list[SurfacedCall]:
        spy = self._benchmark("SPY", now)
        ndx = self._benchmark("QQQ", now)
        surfaced: list[SurfacedCall] = []
        for entry in self._universe.get_universe(now):
            conviction, sub_scores = self._conviction(entry.ticker, now)
            buzz = self._buzz.get_buzz_signals(ticker=entry.ticker, end_date=now)
            buzz_times = [
                _match_awareness(b.fetched_at, now)
                for b in buzz
                if b.fetched_at is not None
            ]
            raw_sent = (
                sum(getattr(b, "sentiment_raw", 0.0) for b in buzz) / len(buzz)
                if buzz
                else 0.0
            )
            sentiment = max(0.0, min(1.0, 0.5 + raw_sent / 2.0))
            intensity = self._intensity_series(entry.ticker, now)
            divergence = blended_divergence_score(
                buzz_times,
                intensity,
                self._price_series(entry.ticker, now),
                sentiment,
                now,
            )
            info = self._md.get_ticker_info(entry.ticker)
            cap = _cap_tier(float(info.get("marketCap", 0.0)))
            surfaced_flag = conviction >= self._cmin and divergence >= self._dmin
            self._store.save_scan_candidate(
                scan_date=now.date().isoformat(),
                ticker=entry.ticker,
                conviction=conviction,
                divergence=divergence,
                sub_scores=sub_scores,
                surfaced=surfaced_flag,
                theme=entry.theme,
                cap_tier=cap,
            )
            if not surfaced_flag:
                continue
            evidence = tuple(
                EvidenceItem(dim, score, f"{dim} contribution")
                for dim, score in sorted(sub_scores.items(), key=lambda kv: -kv[1])
            ) + (
                EvidenceItem(
                    "divergence", divergence, "buzz accelerating, price lagging"
                ),
            )
            call = SurfacedCall(
                call_id=make_call_id(entry.ticker, now),
                ticker=entry.ticker,
                surfaced_at=now,
                conviction=conviction,
                divergence_score=divergence,
                direction=OpportunityDirection.BUY,
                evidence=evidence,
                theme=entry.theme,
                cap_tier=cap,
                spy_at_surface=spy,
                ndx_at_surface=ndx,
            )
            self._store.save_call(call)
            surfaced.append(call)
        surfaced.sort(key=lambda c: (c.conviction + c.divergence_score), reverse=True)
        if not surfaced and allow_abstention:
            return []
        return surfaced
