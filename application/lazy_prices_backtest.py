"""Pre-registered falsification of the SEC filing text-change signal ("Lazy Prices").

Mirrors ``DivergenceICBacktestUseCase``: a point-in-time loop over (filing-cohort ×
universe) computes the text-change similarity signal and a forward EXCESS return per
name, then the cross-sectional rank-IC per cohort, then a locked verdict.

The gate thresholds below are LOCKED PRE-REGISTRATION (ADR-057). They must not be tuned
after looking at results — doing so forfeits the falsification. Design is shaped by the
recurring kill-modes of ADRs 039/044/046/049/050/053:

  * CI-spans-zero killed 6/7 priors  -> primary gate is a bootstrap CI that must EXCLUDE 0,
    and we maximise cohort count by testing QUARTERLY (10-Q+10-K), not annually.
  * Costs killed real gross signals   -> secondary gate is a long-short basket NET of 50bps;
    the signal is naturally low-turnover (quarterly), which is its main edge.
  * Coverage/structural absence       -> liquid large-cap universe only; THIN_COVERAGE guard.
  * Regime-lock / survivorship        -> >=8yr OOS window (post-2014, after the paper sample).
  * Horizon mismatch                  -> 63-day (one quarter) PRIMARY horizon, since Lazy
    Prices returns accrue over months, not the project's usual 21 days (justified in ADR-057).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from application.ic_analysis import aggregate_ic
from application.precision_metrics import (
    date_level_significance,
    moving_block_bootstrap,
)

# ---------------------------------------------------------------------------
# LOCKED pre-registration constants (ADR-057). DO NOT tune post-hoc.
# ---------------------------------------------------------------------------
IC_BAR = 0.02  # economic-relevance floor; below this is noise (ADR-044 lesson)
COVERAGE_FLOOR = 0.80  # >=80% of universe must have a usable signal (ADR-053 lesson)
MIN_COHORTS = 20  # need many cohorts for a tight CI (ADR-044 lesson)
MIN_EVENTS = 1000  # total (cohort x name) observations
SLIPPAGE_BPS = 50  # per side, liquid large-cap; low turnover keeps this survivable
PRIMARY_HORIZON_DAYS = 63  # one quarter (ADR-057 horizon justification)


@dataclass(frozen=True)
class LazyPricesVerdict:
    """Locked decision-tree output. ``decision`` is one of:

    PASS | CONDITIONAL_PASS_PRIMARY_ONLY | INCONCLUSIVE |
    HALT_NEGATIVE | INCONCLUSIVE_THIN_COVERAGE | INCONCLUSIVE_THIN_N
    """

    decision: str
    mean_ic: float
    ic_ci_low: float | None
    ic_ci_high: float | None
    ls_net_ci_low: float | None  # long-short basket, net of cost
    n_cohorts: int
    n_events: int
    coverage: float


def classify_lazy_prices(
    *,
    mean_ic: float,
    ic_ci_low: float | None,
    ic_ci_high: float | None,
    ls_net_ci_low: float | None,
    n_cohorts: int,
    n_events: int,
    coverage: float,
) -> str:
    """The LOCKED verdict decision tree. Guards fire first, then HALT, then PASS logic."""
    # Guards (data-validity) override everything — pre-committed before any data.
    if coverage < COVERAGE_FLOOR:
        return "INCONCLUSIVE_THIN_COVERAGE"
    if n_cohorts < MIN_COHORTS or n_events < MIN_EVENTS:
        return "INCONCLUSIVE_THIN_N"
    # Significant-negative => the hypothesis is actively wrong-signed.
    if ic_ci_high is not None and ic_ci_high < 0:
        return "HALT_NEGATIVE"
    primary_pass = ic_ci_low is not None and ic_ci_low > 0.0 and mean_ic >= IC_BAR
    secondary_pass = ls_net_ci_low is not None and ls_net_ci_low > 0.0
    if primary_pass and secondary_pass:
        return "PASS"
    if primary_pass:
        # Real cross-sectional IC but the tradeable net-of-cost basket did not confirm.
        return "CONDITIONAL_PASS_PRIMARY_ONLY"
    return "INCONCLUSIVE"


def _tercile_long_short_net(
    signals: list[float], fwds: list[float], slippage_bps: int
) -> float | None:
    """Mean(top-tercile fwd) - mean(bottom-tercile fwd), net of 2x slippage (long+short).

    Returns None when a cohort is too small to form terciles.
    """
    n = len(signals)
    if n < 6:
        return None
    order = sorted(range(n), key=lambda i: signals[i])
    k = n // 3
    bottom = order[:k]
    top = order[-k:]
    long_ret = sum(fwds[i] for i in top) / len(top)
    short_ret = sum(fwds[i] for i in bottom) / len(bottom)
    gross = long_ret - short_ret
    cost = 2 * slippage_bps / 10_000.0  # both legs
    return gross - cost


class LazyPricesBacktestUseCase:
    """Cross-sectional rank-IC + net-of-cost long-short falsification of text-change.

    Dependency-injected callables keep the domain pure (ports & adapters):
      similarity_fn(ticker, cohort_date) -> float | None   (None = MISSING, dropped)
      forward_return_fn(ticker, cohort_date) -> float       (EXCESS over benchmark, horizon-fwd)
      universe_fn(cohort_date) -> list[str]                 (point-in-time constituents)
    """

    def __init__(
        self,
        similarity_fn: Callable[[str, datetime], float | None],
        forward_return_fn: Callable[[str, datetime], float],
        universe_fn: Callable[[datetime], list[str]],
        min_names: int = 50,
        slippage_bps: int = SLIPPAGE_BPS,
    ) -> None:
        self._sim = similarity_fn
        self._fwd = forward_return_fn
        self._universe = universe_fn
        self._min_names = min_names
        self._slippage_bps = slippage_bps

    def execute(
        self, cohort_dates: list[datetime], horizon_label: str
    ) -> dict[str, Any]:
        per_date: list[tuple[list[float], list[float]]] = []
        ls_series: list[float] = []
        n_events = 0
        n_attempted = 0  # universe-name slots, for coverage accounting

        for t in cohort_dates:
            tickers = self._universe(t)
            n_attempted += len(tickers)
            signals: list[float] = []
            fwds: list[float] = []
            for ticker in tickers:
                sig = self._sim(ticker, t)
                if sig is None:  # MISSING — never imputed (no-look-ahead discipline)
                    continue
                signals.append(sig)
                fwds.append(self._fwd(ticker, t))
            n_events += len(signals)
            per_date.append((signals, fwds))
            ls = _tercile_long_short_net(signals, fwds, self._slippage_bps)
            if ls is not None:
                ls_series.append(ls)

        agg = aggregate_ic(per_date, min_names=self._min_names)
        ic_series = agg["ic_series"]
        boot: dict[str, Any] = moving_block_bootstrap(ic_series) if ic_series else {}
        ls_boot: dict[str, Any] = moving_block_bootstrap(ls_series) if ls_series else {}
        date_level: dict[str, Any] = (
            date_level_significance(ic_series, [0.0] * len(ic_series))
            if ic_series
            else {}
        )

        coverage = (n_events / n_attempted) if n_attempted else 0.0
        decision = classify_lazy_prices(
            mean_ic=agg["mean_ic"],
            ic_ci_low=boot.get("ci_low"),
            ic_ci_high=boot.get("ci_high"),
            ls_net_ci_low=ls_boot.get("ci_low"),
            n_cohorts=agg["n_dates"],
            n_events=n_events,
            coverage=coverage,
        )

        return {
            "horizon": horizon_label,
            "verdict": decision,
            "mean_ic": agg["mean_ic"],
            "ic_ir": agg["ic_ir"],
            "pct_positive_dates": agg["pct_positive_dates"],
            "n_cohorts": agg["n_dates"],
            "n_events": n_events,
            "coverage": round(coverage, 4),
            "ic_bootstrap": boot,
            "long_short_net_bootstrap": ls_boot,
            "date_level": date_level,
            "locked_gates": {
                "ic_bar": IC_BAR,
                "coverage_floor": COVERAGE_FLOOR,
                "min_cohorts": MIN_COHORTS,
                "min_events": MIN_EVENTS,
                "slippage_bps": self._slippage_bps,
            },
        }
