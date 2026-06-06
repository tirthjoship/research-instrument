"""Pre-registered cross-sectional IC backtest for intensity-divergence.

Point-in-time loop over (date x universe): compute the continuous
intensity-divergence signal and the forward return for each name, then the
cross-sectional rank-IC per date, then aggregate + significance. Falsification
tool only (see spec D §1): a non-positive IC on a survivor-biased sample kills
the signal; a positive IC merely earns the right to forward-track.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from application.ic_analysis import aggregate_ic
from application.precision_metrics import (
    date_level_significance,
    moving_block_bootstrap,
)
from domain.divergence_service import intensity_divergence_raw


class DivergenceICBacktestUseCase:
    def __init__(
        self,
        attention_fn: Callable[[str, datetime], list[tuple[datetime, float]]],
        price_fn: Callable[[str, datetime], list[tuple[datetime, float]]],
        forward_return_fn: Callable[[str, datetime], float],
        min_names: int = 50,
    ) -> None:
        self._attn = attention_fn
        self._price = price_fn
        self._fwd = forward_return_fn
        self._min_names = min_names

    def execute(
        self, dates: list[datetime], tickers: list[str], horizon_label: str
    ) -> dict[str, Any]:
        per_date: list[tuple[list[float], list[float]]] = []
        for t in dates:
            signals: list[float] = []
            fwds: list[float] = []
            for ticker in tickers:
                attn = self._attn(ticker, t)
                if not attn:
                    continue
                sig = intensity_divergence_raw(attn, self._price(ticker, t), t)
                fwd = self._fwd(ticker, t)
                signals.append(sig)
                fwds.append(fwd)
            per_date.append((signals, fwds))

        agg = aggregate_ic(per_date, min_names=self._min_names)
        ic_series = agg["ic_series"]

        # moving_block_bootstrap(values) — single list, all args optional
        boot: dict[str, Any] = moving_block_bootstrap(ic_series) if ic_series else {}

        # date_level_significance(model_basket_returns, spy_returns) — two lists.
        # We test mean IC > 0 by passing ic_series as "model" and zeros as "spy"
        # so excess[i] = ic[i] - 0 = ic[i], one-sided H1: mean IC > 0.
        date_level: dict[str, Any]
        try:
            date_level = (
                date_level_significance(ic_series, [0.0] * len(ic_series))
                if ic_series
                else {}
            )
        except Exception:
            # Graceful degradation on tiny/degenerate series (e.g. n < 2)
            date_level = {}

        return {
            "horizon": horizon_label,
            "mean_ic": agg["mean_ic"],
            "ic_ir": agg["ic_ir"],
            "pct_positive_dates": agg["pct_positive_dates"],
            "n_dates": agg["n_dates"],
            "bootstrap": boot,
            "date_level": date_level,
        }
