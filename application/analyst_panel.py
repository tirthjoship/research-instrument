"""Attributed analyst-estimate panel.

All data in this module is ATTRIBUTED, not adopted. Figures come from
third-party analyst consensus (via yfinance) and must be displayed as
such — the engine makes no claim of its own about price targets or
analyst ratings. See ADR-055/056 for the attributed-not-adopted rule.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnalystPanel:
    """Third-party analyst consensus snapshot — attributed source, not engine output."""

    count: int
    mean_rating: float | None
    target_mean: float | None
    target_high: float | None
    target_low: float | None
    as_of: str
    attribution: str
    data_gap: bool


def build_analyst_panel(info: dict[str, object], as_of: str) -> AnalystPanel:
    """Build an attributed AnalystPanel from a yfinance-style info dict.

    Data is presented as third-party analyst consensus sourced from
    yfinance (The Street aggregates). It is never framed as a
    recommendation or forecast by this engine.

    Args:
        info: yfinance-style ticker.info dict (may be empty).
        as_of: ISO date string for the snapshot date.

    Returns:
        AnalystPanel with fields populated from available data.
        Sets data_gap=True when no analyst coverage is present.
    """

    def _to_int(val: object) -> int:
        if isinstance(val, (int, float)):
            return int(val)
        if isinstance(val, str):
            return int(val)
        return 0

    def _to_float(val: object) -> float | None:
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            return float(val)
        return None

    count: int = _to_int(info.get("analyst_count"))
    mean_rating: float | None = _to_float(info.get("analyst_recommendation_mean"))
    target_mean: float | None = _to_float(info.get("targetMeanPrice"))
    target_high: float | None = _to_float(info.get("targetHighPrice"))
    target_low: float | None = _to_float(info.get("targetLowPrice"))

    attribution = (
        "The Street (per yfinance) currently reads the following analyst consensus — "
        "these are third-party estimates, not this engine's views."
    )

    data_gap: bool = count == 0

    return AnalystPanel(
        count=count,
        mean_rating=mean_rating,
        target_mean=target_mean,
        target_high=target_high,
        target_low=target_low,
        as_of=as_of,
        attribution=attribution,
        data_gap=data_gap,
    )
