"""Historical (point-in-time) calibration of the discipline verdicts. Replays the
SAME scoring used live across price history and checks whether REDUCE/TRIM flags
were followed by drops. Cost-basis-INDEPENDENT (disposition overlay excluded — it
flags YOUR behavior, not a market move), so it is computable on any history. Day-1
evidence on the flags; NOT proof the rules beat buy-hold (ADR-046) nor the user's
behavior (forward-tracked only)."""

from __future__ import annotations

import statistics
from datetime import datetime
from typing import Any, Callable

from domain.backtest_metrics import daily_returns
from domain.calibration import brier_score
from domain.discipline import (
    Verdict,
    conditional_vol_signal,
    grade_position,
    is_winner_past_stop,
)
from domain.trend_rules import (
    atr,
    chandelier_stop,
    relative_strength,
    sma,
    trend_health,
)

PriceProvider = Callable[[str], list[tuple[datetime, float]]]

_TREND_WINDOW = 200
_ATR_WINDOW = 22
_ATR_MULT = 3.0
_RECENT_VOL = 22
_BASE_VOL = 252
_RS_WINDOW = 126


def _vol(returns: list[float], window: int) -> float:
    tail = returns[-window:]
    return statistics.pstdev(tail) if len(tail) >= 2 else 0.0


def backtest_discipline_calibration(
    tickers: list[str],
    price_provider: PriceProvider,
    start: datetime,
    end: datetime,
    step_days: int = 21,
    horizon_days: int = 21,
    benchmark: str = "SPY",
) -> dict[str, Any]:
    """Walk each ticker point-in-time every ~step_days, compute the verdict using ONLY
    past+current closes, then look horizon_days forward for the realized return.
    Aggregate per-verdict n/down_rate/mean_fwd_return + a directional Brier for
    REDUCE only (the down-call, p=1.0). TRIM is position-sizing, not a down-call,
    so it is reported in by_verdict but excluded from the Brier (ADR-048)."""
    s_naive = start.replace(tzinfo=None)
    e_naive = end.replace(tzinfo=None)
    bench = [(d.replace(tzinfo=None), c) for d, c in price_provider(benchmark)]
    bench_dates = [d for d, _ in bench]
    bench_closes = [c for _, c in bench]

    by_verdict: dict[str, dict[str, Any]] = {}
    probs: list[float] = []
    outcomes: list[int] = []
    total = 0

    for tkr in tickers:
        series = [
            (d.replace(tzinfo=None), c)
            for d, c in price_provider(tkr)
            if s_naive <= d.replace(tzinfo=None) <= e_naive
        ]
        closes = [c for _, c in series]
        dates = [d for d, _ in series]
        n = len(closes)
        if n < _TREND_WINDOW + horizon_days:
            continue
        for i in range(_TREND_WINDOW, n - horizon_days, max(1, step_days)):
            window = closes[: i + 1]
            th = trend_health(
                closes[i],
                sma(window, _TREND_WINDOW),
                atr(window, window, window, _ATR_WINDOW),
            )
            if th is None:
                continue
            atr_v = atr(window, window, window, _ATR_WINDOW)
            highest = max(window[-_TREND_WINDOW:])
            stop = chandelier_stop(highest, atr_v, _ATR_MULT) if atr_v else None
            rets = daily_returns(window)
            vol_sig = conditional_vol_signal(
                _vol(rets, _RECENT_VOL), _vol(rets, _BASE_VOL), th
            )
            bclose_to_i = [
                c for d, c in zip(bench_dates, bench_closes) if d <= dates[i]
            ]
            rs = (
                relative_strength(window, bclose_to_i, _RS_WINDOW)
                if len(bclose_to_i) > _RS_WINDOW
                else None
            )
            market_th = None
            if len(bclose_to_i) >= _TREND_WINDOW:
                market_th = trend_health(
                    bclose_to_i[-1],
                    sma(bclose_to_i, _TREND_WINDOW),
                    atr(bclose_to_i, bclose_to_i, bclose_to_i, _ATR_WINDOW),
                )
            wps = is_winner_past_stop(th, closes[i], stop)
            verdict, _conf, _ab = grade_position(th, vol_sig, rs, False, wps, market_th)
            fwd = closes[i + horizon_days] / closes[i] - 1.0 if closes[i] > 0 else 0.0
            b = by_verdict.setdefault(
                verdict.value, {"n": 0, "down": 0, "sum_fwd": 0.0}
            )
            b["n"] += 1
            b["down"] += 1 if fwd < 0 else 0
            b["sum_fwd"] += fwd
            total += 1
            # ADR-048: only REDUCE is a directional down-call. TRIM is position-sizing
            # (winner past stop) and historically keeps rising — it is shown in
            # by_verdict for transparency but excluded from the directional Brier.
            if verdict == Verdict.REDUCE:
                probs.append(1.0)
                outcomes.append(1 if fwd < 0 else 0)

    for b in by_verdict.values():
        b["down_rate"] = b["down"] / b["n"] if b["n"] else 0.0
        b["mean_fwd_return"] = b["sum_fwd"] / b["n"] if b["n"] else 0.0

    return {
        "total_verdicts": total,
        "by_verdict": by_verdict,
        "brier_reduce": brier_score(probs, outcomes),
        "n_reduce": len(outcomes),
    }
