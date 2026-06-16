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
            }
        ),
    }
