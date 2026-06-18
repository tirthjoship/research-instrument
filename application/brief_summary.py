"""Serialize a WeeklyBrief to the dashboard-facing structured summary.

The dashboard renders artifacts; it never computes domain logic. This module is
the single place the brief's shape is flattened to JSON-safe primitives.
Written next to the markdown brief (data/personal/ — gitignored, holdings detail).
"""

from __future__ import annotations

from typing import Any

from domain.brief import WeeklyBrief


def brief_to_summary_dict(brief: WeeklyBrief) -> dict[str, Any]:
    macro = brief.macro
    return {
        "as_of": brief.as_of,
        "regime": str(getattr(brief.regime, "value", brief.regime)),
        "screen_label": brief.screen_label.value,
        "abstained": brief.abstained,
        "candidates": [
            {
                "ticker": c.ticker,
                "composite": c.composite,
                "factor_summary": c.factor_summary,
                "why": c.why,
                "already_held": c.already_held,
                "label": c.label.value,
            }
            for c in brief.candidates
        ],
        "holdings": [
            {
                "ticker": h.ticker,
                "verdict": h.verdict.name,
                "unrealized_pct": h.unrealized_pct,
                "trend_state": h.trend_state,
                "why": h.why,
            }
            for h in brief.holdings
        ],
        "concentration": [
            {"descriptor": f.descriptor, "soft_warning": f.soft_warning}
            for f in brief.concentration
        ],
        "scorecard": {
            "screen_window": brief.scorecard.screen_window,
            "screen_n": brief.scorecard.screen_n,
            "screen_significant": brief.scorecard.screen_significant,
            "discipline_window": brief.scorecard.discipline_window,
            "discipline_n": brief.scorecard.discipline_n,
            "discipline_gate_status": brief.scorecard.discipline_gate_status,
        },
        "macro": (
            None
            if macro is None
            else {
                "as_of": macro.as_of,
                "factors": list(macro.factors),
                "net_beta_by_factor": dict(macro.net_beta_by_factor),
                "systematic_share": macro.systematic_share,
                "idiosyncratic_share": macro.idiosyncratic_share,
                "dominant_factor": macro.dominant_factor,
                # MacroBetaFlag is a frozen DATACLASS (domain/models.py:470) with
                # fields kind/factor/message/value/threshold — NOT an Enum.
                "flags": [f.kind for f in macro.flags],
                "coverage_holdings": macro.coverage_holdings,
                "total_holdings": macro.total_holdings,
                # v8 risk-stats fields (Task 9) --------------------------------
                # Scalars pass through directly.
                "enb": macro.enb,
                "pc_labels_data_gap": macro.pc_labels_data_gap,
                "systematic_share_adj": macro.systematic_share_adj,
                "downside_beta": macro.downside_beta,
                "sector_hhi": macro.sector_hhi,
                "diversification_ratio": macro.diversification_ratio,
                # Tuples → lists (JSON arrays).
                "pc_variance": list(macro.pc_variance),
                "pc_labels": list(macro.pc_labels),
                "suppressed_factors": list(macro.suppressed_factors),
                "sector_gaps": list(macro.sector_gaps),
                # tuple[tuple[str, float], ...] → list of [date, value] lists.
                "sys_share_history": [[d, v] for d, v in macro.sys_share_history],
                # tuple[dict, ...] → list of dicts (each dict is already JSON-safe).
                "holdings_meta": list(macro.holdings_meta),
                # Dicts pass through; scalars unchanged.
                "risk_contribution": dict(macro.risk_contribution),
                "sector_weights": dict(macro.sector_weights),
                # Scalar-valued CI tuple → list [lo, hi].
                "systematic_share_ci": list(macro.systematic_share_ci),
                # dict[str, tuple[float, float]] → dict[str, [lo, hi]].
                "beta_ci_by_factor": {
                    f: list(ci) for f, ci in macro.beta_ci_by_factor.items()
                },
                # VIF dict: float('inf') → None (JSON-safe sentinel meaning
                # "collinear / data-gap"; UI should show as "—" not a number).
                "vif_by_factor": {
                    f: (None if v != v or v == float("inf") else v)
                    for f, v in macro.vif_by_factor.items()
                },
            }
        ),
    }
