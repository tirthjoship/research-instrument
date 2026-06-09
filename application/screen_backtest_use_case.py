"""Pre-registered IC gate: per-date Spearman rank-IC of composite vs fwd 1m return."""

from __future__ import annotations

import math
from dataclasses import dataclass

from application.evaluation import TransactionCostModel
from application.ic_analysis import spearman_ic
from application.precision_metrics import (
    moving_block_bootstrap,
    sharpe_difference_bootstrap,
)


@dataclass(frozen=True)
class ScreenVerdict:
    decision: str  # PASS | INCONCLUSIVE | HALT
    mean_ic: float
    n_dates: int
    ic_ci_low: float | None = None
    ic_ci_high: float | None = None
    sharpe_diff_point: float | None = None
    sharpe_diff_ci_low: float | None = None
    sharpe_diff_ci_high: float | None = None
    primary_pass: bool = False
    secondary_pass: bool = False


class ScreenBacktestUseCase:
    """Pre-registered: per-date Spearman rank-IC of composite vs fwd 1m return.

    Gate logic (LOCKED — see spec §5 and ADR-049):
      Primary: block-bootstrap CI of per-date ICs EXCLUDES 0 (positive)
               AND mean IC >= 0.02.
      Secondary: top-decile-minus-market Sharpe-diff CI excludes 0 (positive),
                 net of costs, periods_per_year=12 (monthly panels).
      HALT:  ic_ci_high < 0 (CI entirely negative — significant negative IC).
      PASS:  primary_pass OR secondary_pass.
      INCONCLUSIVE: neither fires (or n<2 dates for CI).
    """

    def run(
        self,
        panels: list[dict[str, tuple[float, float]]],
        market_returns: list[float] | None = None,
    ) -> ScreenVerdict:
        """Compute per-date IC and return a gate verdict.

        Args:
            panels: One dict per date. Keys are ticker symbols; values are
                    (composite_signal, forward_1m_return) pairs.
            market_returns: Optional per-date market (SPY) forward return, same
                    length/order as panels. If None, falls back to per-date
                    equal-weight mean of ALL tickers (cross-sectional proxy).

        Returns:
            ScreenVerdict with decision, mean_ic, n_dates, and CI fields.
        """
        # ------------------------------------------------------------------
        # Step 1: per-date IC
        # ------------------------------------------------------------------
        ics: list[float] = []
        strat_gross: list[float] = []
        mkt_returns_computed: list[float] = []

        for idx, p in enumerate(panels):
            items = list(p.items())
            if not items:
                continue

            sig: list[float] = [v[0] for _, v in items]
            fwd: list[float] = [v[1] for _, v in items]

            ics.append(spearman_ic(sig, fwd))

            # Market return for this date
            if market_returns is not None and idx < len(market_returns):
                mkt_ret = market_returns[idx]
            else:
                mkt_ret = sum(fwd) / len(fwd) if fwd else 0.0
            mkt_returns_computed.append(mkt_ret)

            # Top-decile basket return
            n_top = max(1, math.ceil(len(items) / 10))
            sorted_items = sorted(items, key=lambda kv: kv[1][0], reverse=True)
            top_fwds = [kv[1][1] for kv in sorted_items[:n_top]]
            strat_gross.append(sum(top_fwds) / len(top_fwds))

        mean_ic: float = round(sum(ics) / len(ics), 6) if ics else 0.0

        # ------------------------------------------------------------------
        # Step 2: PRIMARY gate — bootstrap CI on IC series
        # ------------------------------------------------------------------
        boot = moving_block_bootstrap(ics)
        ic_ci_low: float | None = boot.get("ci_low")  # type: ignore[assignment]
        ic_ci_high: float | None = boot.get("ci_high")  # type: ignore[assignment]

        primary_pass = ic_ci_low is not None and ic_ci_low > 0.0 and mean_ic >= 0.02

        # ------------------------------------------------------------------
        # Step 3: SECONDARY gate — top-decile Sharpe diff net of costs
        # ------------------------------------------------------------------
        cost_model = TransactionCostModel()
        strat_net = cost_model.apply_costs(strat_gross, n_trades_per_period=2)

        # Align lengths
        n_align = min(len(strat_net), len(mkt_returns_computed))
        strat_net = strat_net[:n_align]
        mkt_aligned = mkt_returns_computed[:n_align]

        sd = sharpe_difference_bootstrap(
            strat_net,
            mkt_aligned,
            periods_per_year=12,
        )
        sharpe_diff_point: float | None = sd.get("point")  # type: ignore[assignment]
        sharpe_diff_ci_low: float | None = sd.get("ci_low")  # type: ignore[assignment]
        sharpe_diff_ci_high: float | None = sd.get("ci_high")  # type: ignore[assignment]

        secondary_pass = sharpe_diff_ci_low is not None and sharpe_diff_ci_low > 0.0

        # ------------------------------------------------------------------
        # Step 4: DECISION (order matters)
        # ------------------------------------------------------------------
        if ic_ci_high is not None and ic_ci_high < 0.0:
            decision = "HALT"
        elif primary_pass or secondary_pass:
            decision = "PASS"
        else:
            decision = "INCONCLUSIVE"

        return ScreenVerdict(
            decision=decision,
            mean_ic=mean_ic,
            n_dates=len(panels),
            ic_ci_low=ic_ci_low,
            ic_ci_high=ic_ci_high,
            sharpe_diff_point=sharpe_diff_point,
            sharpe_diff_ci_low=sharpe_diff_ci_low,
            sharpe_diff_ci_high=sharpe_diff_ci_high,
            primary_pass=primary_pass,
            secondary_pass=secondary_pass,
        )
