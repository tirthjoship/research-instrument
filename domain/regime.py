"""Pure regime classification — conditions the brief's presentation/tilt only.

Does NOT predict the macro (the trend is non-stationary, ADR-049). Inputs:
spy_trend_health is SIGNED ATR-distance of SPY from its trend (positive = above
trend, ~-3..+3); vix_level is the raw VIX index level.
"""

from __future__ import annotations

from enum import Enum

from domain.factor_scores import FACTOR_KEYS

# Frozen thresholds (ATR units / VIX points) — set before use, not tuned.
_RISK_ON_TREND = 0.5
_RISK_ON_VIX = 18.0
_RISK_OFF_TREND = -0.5
_RISK_OFF_VIX = 28.0


class Regime(Enum):
    RISK_ON = "RISK_ON"
    NEUTRAL = "NEUTRAL"
    RISK_OFF = "RISK_OFF"


def classify_regime(spy_trend_health: float, vix_level: float) -> Regime:
    """Classify regime from SPY trend-health (signed ATR-distance) and VIX level.

    RISK_OFF dominates (capital-preservation bias): a broken trend OR an elevated
    VIX forces RISK_OFF. RISK_ON requires BOTH a clearly-above-trend tape AND a
    calm VIX. Everything else is NEUTRAL. Monotone: higher trend never increases
    risk-off; higher VIX never increases risk-on.
    """
    if spy_trend_health <= _RISK_OFF_TREND or vix_level >= _RISK_OFF_VIX:
        return Regime.RISK_OFF
    if spy_trend_health >= _RISK_ON_TREND and vix_level < _RISK_ON_VIX:
        return Regime.RISK_ON
    return Regime.NEUTRAL


_TILTS: dict[Regime, dict[str, float]] = {
    Regime.RISK_ON: {
        "momentum": 0.40,
        "revision": 0.30,
        "quality": 0.15,
        "value": 0.15,
    },
    Regime.NEUTRAL: {
        "momentum": 0.25,
        "revision": 0.25,
        "quality": 0.25,
        "value": 0.25,
    },
    Regime.RISK_OFF: {
        "momentum": 0.15,
        "revision": 0.15,
        "quality": 0.40,
        "value": 0.30,
    },
}


def screen_tilt(regime: Regime) -> dict[str, float]:
    """Display-only factor-weight tilt for the brief (weights sum to 1).

    v1 does NOT re-rank candidates with these weights — the tilt is shown as
    context ('regime favors quality/low-vol'). Re-ranking is a soft predictive
    act and is deferred (keeps Phase B's no-new-claim invariant).
    """
    return dict(_TILTS[regime])


__all__ = ["Regime", "classify_regime", "screen_tilt", "FACTOR_KEYS"]
