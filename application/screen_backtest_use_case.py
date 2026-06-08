"""Pre-registered IC gate: per-date Spearman rank-IC of composite vs fwd 1m return."""

from __future__ import annotations

from dataclasses import dataclass

from application.ic_analysis import spearman_ic


@dataclass(frozen=True)
class ScreenVerdict:
    decision: str  # PASS | INCONCLUSIVE | HALT
    mean_ic: float
    n_dates: int


class ScreenBacktestUseCase:
    """Pre-registered: per-date Spearman rank-IC of composite vs fwd 1m return.

    Gate: mean IC >= 0.02 -> PASS; (0, 0.02) -> INCONCLUSIVE; <= 0 -> HALT.

    NOTE: Bootstrap-CI gate (via precision_metrics.moving_block_bootstrap) and
    cost-aware top-decile secondary validation are deliberately deferred to be
    added immediately before the live run; see spec section 5.
    """

    def run(self, panels: list[dict[str, tuple[float, float]]]) -> ScreenVerdict:
        """Compute per-date IC and return a gate verdict.

        Args:
            panels: One dict per date. Keys are ticker symbols; values are
                    (composite_signal, forward_1m_return) pairs.

        Returns:
            ScreenVerdict with decision, mean_ic, and n_dates.
        """
        ics: list[float] = []
        for p in panels:
            sig: list[float] = [v[0] for v in p.values()]
            fwd: list[float] = [v[1] for v in p.values()]
            ics.append(spearman_ic(sig, fwd))

        mean_ic: float = sum(ics) / len(ics) if ics else 0.0

        if mean_ic <= 0.0:
            decision = "HALT"
        elif mean_ic >= 0.02:
            decision = "PASS"
        else:
            decision = "INCONCLUSIVE"

        return ScreenVerdict(decision, round(mean_ic, 6), len(panels))
