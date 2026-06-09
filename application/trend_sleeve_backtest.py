"""Pre-registered trend-following sleeve falsification backtest (spec 2026-06-08).

Blends an 80% SPY core with a 20% 12-month time-series-momentum sleeve (long/flat,
inverse-vol, 7 liquid ETFs) and gates on Sharpe-diff CI or >=25% drawdown cut,
net of cost. LOCKED gate — do not retune. Backtest only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import pstdev
from typing import Callable

from application.evaluation import DrawdownTracker
from application.precision_metrics import sharpe_difference_bootstrap

# Imported at module top so the CLI test has a single patch point
# (application.trend_sleeve_backtest.load_price_series). The use case itself
# takes an injected price_series_fn and never calls this directly.
from application.price_returns import load_price_series  # noqa: F401
from domain.backtest_metrics import cagr, sharpe
from domain.trend_following import (
    blend_returns,
    equity_curve,
    inverse_vol_weights,
    time_series_momentum,
    turnover,
)

UNIVERSE = ["SPY", "EFA", "EEM", "TLT", "IEF", "GLD", "DBC"]
_CORE = "SPY"
_CORE_WEIGHT = 0.80
_VOL_WINDOW = 60  # trading days
_COST_PER_TRADE = 0.001  # 10 bps one-way

PriceSeriesFn = Callable[[str], list[tuple[datetime, float]]]


def _monthly_closes_asof(
    series: list[tuple[datetime, float]], as_of: datetime
) -> list[float]:
    """Last close of each calendar month with month-end <= as_of, ascending.

    Point-in-time: only uses observations with date <= as_of. (Local helper —
    the project has no shared screen_ic_panels module on this branch.)
    """
    by_month: dict[tuple[int, int], float] = {}
    for d, c in series:
        if d <= as_of:
            by_month[(d.year, d.month)] = c  # ascending input -> last wins
    return [by_month[k] for k in sorted(by_month)]


def _daily_vol_asof(series: list[tuple[datetime, float]], as_of: datetime) -> float:
    """Trailing 60-trading-day return volatility from closes with date <= as_of.

    Returns 0.0 when there are too few points (excludes the ETF from sizing).
    """
    closes = [c for d, c in series if d <= as_of]
    window = closes[-(_VOL_WINDOW + 1) :]
    if len(window) < 2:
        return 0.0
    rets = [window[i] / window[i - 1] - 1.0 for i in range(1, len(window))]
    return pstdev(rets) if len(rets) >= 2 else 0.0


def _close_asof(series: list[tuple[datetime, float]], as_of: datetime) -> float | None:
    prior = [c for d, c in series if d <= as_of]
    return prior[-1] if prior else None


@dataclass(frozen=True)
class SleeveVerdict:
    decision: str  # PASS | INCONCLUSIVE | KILL
    n_months: int
    sharpe_spy: float
    sharpe_sleeve: float
    sharpe_blended: float
    maxdd_spy: float
    maxdd_sleeve: float
    maxdd_blended: float
    cagr_spy: float
    cagr_sleeve: float
    cagr_blended: float
    sharpe_diff_point: float | None
    sharpe_diff_ci_low: float | None
    sharpe_diff_ci_high: float | None
    dd_reduction: float
    sharpe_blended_6040: float | None = None
    maxdd_blended_6040: float | None = None


class TrendSleeveBacktestUseCase:
    def __init__(self, price_series_fn: PriceSeriesFn) -> None:
        self._prices = price_series_fn
        self._cache: dict[str, list[tuple[datetime, float]]] = {}

    def _series(self, ticker: str) -> list[tuple[datetime, float]]:
        if ticker not in self._cache:
            self._cache[ticker] = self._prices(ticker)
        return self._cache[ticker]

    def build_series(
        self, month_ends: list[datetime], core_weight: float = _CORE_WEIGHT
    ) -> tuple[list[float], list[float], list[float]]:
        """Return (spy_returns, sleeve_net_returns, blended_returns), one entry per
        month-end transition t->t+1 (so len = len(month_ends) - 1).
        """
        spy_rets: list[float] = []
        sleeve_rets: list[float] = []
        prev_w: dict[str, float] = {}

        for i in range(len(month_ends) - 1):
            t = month_ends[i]
            t1 = month_ends[i + 1]

            # --- signal + sizing at t (point-in-time) ---
            vols: dict[str, float] = {}
            mom: dict[str, float] = {}
            for tk in UNIVERSE:
                s = self._series(tk)
                closes_m = _monthly_closes_asof(s, t)
                m = time_series_momentum(closes_m)
                if m is not None:
                    mom[tk] = m
                vols[tk] = _daily_vol_asof(s, t)

            raw = inverse_vol_weights(vols)  # across all 7
            # Zero trend-negative / unknown-momentum ETFs; keep raw weight otherwise.
            new_w = {tk: w for tk, w in raw.items() if mom.get(tk, -1.0) > 0}

            # --- realized t->t+1 returns ---
            def _ret(tk: str, _t: datetime = t, _t1: datetime = t1) -> float:
                s = self._series(tk)
                c0 = _close_asof(s, _t)
                c1 = _close_asof(s, _t1)
                if c0 is None or c1 is None or c0 <= 0:
                    return 0.0
                return c1 / c0 - 1.0

            sleeve_gross = sum(w * _ret(tk) for tk, w in new_w.items())
            cost = _COST_PER_TRADE * turnover(prev_w, new_w)
            sleeve_rets.append(sleeve_gross - cost)
            spy_rets.append(_ret(_CORE))
            prev_w = new_w

        blended = blend_returns(spy_rets, sleeve_rets, core_weight)
        return spy_rets, sleeve_rets, blended

    def execute(self, month_ends: list[datetime]) -> SleeveVerdict:
        spy, sleeve, blended = self.build_series(month_ends)
        _, _, blended_6040 = self.build_series(month_ends, core_weight=0.60)

        dd = DrawdownTracker()

        def _maxdd(returns: list[float]) -> float:
            v = dd.compute(returns)["max_drawdown"]
            return float(v) if isinstance(v, (int, float)) else 0.0

        maxdd_spy = _maxdd(spy)
        maxdd_sleeve = _maxdd(sleeve)
        maxdd_blended = _maxdd(blended)

        sd = sharpe_difference_bootstrap(blended, spy, periods_per_year=12)
        ci_low_raw = sd.get("ci_low")
        ci_high_raw = sd.get("ci_high")
        point_raw = sd.get("point")
        ci_low = float(ci_low_raw) if isinstance(ci_low_raw, (int, float)) else None
        ci_high = float(ci_high_raw) if isinstance(ci_high_raw, (int, float)) else None
        point = float(point_raw) if isinstance(point_raw, (int, float)) else None

        # Drawdown-reduction ratio: 1 - |blended|/|spy| (both negative -> positive ratio).
        dd_reduction = 1.0 - (maxdd_blended / maxdd_spy) if maxdd_spy < 0 else 0.0

        s_spy = sharpe(spy, 12)
        s_sleeve = sharpe(sleeve, 12)
        s_blended = sharpe(blended, 12)

        # --- LOCKED gate (spec section 5) ---
        primary = ci_low is not None and ci_low > 0.0
        secondary = dd_reduction >= 0.25
        strictly_worse = s_blended < s_spy and maxdd_blended < maxdd_spy

        if primary or secondary:
            decision = "PASS"
        elif strictly_worse:
            decision = "KILL"
        else:
            decision = "INCONCLUSIVE"

        return SleeveVerdict(
            decision=decision,
            n_months=len(blended),
            sharpe_spy=round(s_spy, 4),
            sharpe_sleeve=round(s_sleeve, 4),
            sharpe_blended=round(s_blended, 4),
            maxdd_spy=round(maxdd_spy, 4),
            maxdd_sleeve=round(maxdd_sleeve, 4),
            maxdd_blended=round(maxdd_blended, 4),
            cagr_spy=round(cagr(equity_curve(spy), 12), 4),
            cagr_sleeve=round(cagr(equity_curve(sleeve), 12), 4),
            cagr_blended=round(cagr(equity_curve(blended), 12), 4),
            sharpe_diff_point=round(point, 6) if point is not None else None,
            sharpe_diff_ci_low=round(ci_low, 6) if ci_low is not None else None,
            sharpe_diff_ci_high=round(ci_high, 6) if ci_high is not None else None,
            dd_reduction=round(dd_reduction, 4),
            sharpe_blended_6040=round(sharpe(blended_6040, 12), 4),
            maxdd_blended_6040=round(_maxdd(blended_6040), 4),
        )
