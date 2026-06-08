"""Pure discipline/risk grading primitives (stdlib only). The deterministic core
computes verdicts; the LLM narrator only explains them, never produces them."""

from __future__ import annotations

from enum import Enum


def conditional_vol_signal(
    recent_vol: float, baseline_vol: float, trend_health: float | None
) -> float:
    """De-risk weight in [0,1]. NON-ZERO ONLY when volatility is elevated AND the
    trend is deteriorating (trend_health < 0). High vol alone never de-risks —
    this is the conditional form that is safe on TSX/non-US markets (conventional
    vol-targeting backfires there; see spec)."""
    if trend_health is None or trend_health >= 0:
        return 0.0
    if baseline_vol <= 0 or recent_vol <= baseline_vol:
        return 0.0
    return min(1.0, recent_vol / baseline_vol - 1.0)


def risk_asymmetry(
    price: float, trailing_stop: float | None, recent_high: float
) -> dict[str, float]:
    """Factual asymmetry framing (not a forecast):
    downside_to_stop = fraction at risk before the trailing stop fires;
    upside_to_recover = fraction needed to revisit the recent high."""
    downside = (
        (price - trailing_stop) / price
        if (trailing_stop is not None and price > 0)
        else 0.0
    )
    upside = (recent_high - price) / price if price > 0 else 0.0
    return {"downside_to_stop": downside, "upside_to_recover": upside}


class Verdict(str, Enum):
    REDUCE = "REDUCE"
    TRIM = "TRIM"
    REVIEW = "REVIEW"
    HOLD = "HOLD"
    ADD_OK = "ADD_OK"


# below this many ATRs under the trend line a position is "clearly broken"
_BROKEN_TREND_ATR = 2.0
# above this many ATRs over the trend line it is "clearly strong"
_STRONG_TREND_ATR = 1.5


def is_disposition_risk(trend_health: float | None, unrealized_pct: float) -> bool:
    """The classic hold-a-loser pattern: trend broken AND position held at a loss."""
    return trend_health is not None and trend_health < 0 and unrealized_pct < 0


def is_winner_past_stop(
    trend_health: float | None, price: float, trailing_stop: float | None
) -> bool:
    """In an uptrend but price has breached the trailing stop — trim/tighten."""
    return (
        trend_health is not None
        and trend_health > 0
        and trailing_stop is not None
        and price <= trailing_stop
    )


def grade_position(
    trend_health: float | None,
    vol_signal: float,
    relative_strength: float | None,
    disposition: bool,
    winner_past_stop: bool,
    market_trend_health: float | None,
) -> tuple[Verdict, float, bool]:
    """Combine sub-scores into a graded verdict + confidence in [0,1] + abstained flag.
    ABSTAINS to REVIEW when signals conflict (notably: the name is weak but the whole
    market is weak too, so weakness can't be attributed to the name)."""
    if trend_health is None:
        return Verdict.REVIEW, 0.2, True

    market_broken = market_trend_health is not None and market_trend_health < 0

    if trend_health < 0 and market_broken:
        return Verdict.REVIEW, 0.3, True

    if winner_past_stop:
        conf = min(1.0, 0.5 + abs(trend_health) / 10.0)
        return Verdict.TRIM, conf, False

    if trend_health <= -_BROKEN_TREND_ATR and (disposition or vol_signal > 0.0):
        depth = min(1.0, abs(trend_health) / 4.0)
        conf = min(1.0, 0.5 + 0.5 * depth)
        return Verdict.REDUCE, conf, False

    if trend_health >= _STRONG_TREND_ATR and (relative_strength or 0.0) > 0.0:
        conf = min(1.0, 0.5 + trend_health / 6.0)
        return Verdict.ADD_OK, conf, False

    if trend_health < 0:
        return Verdict.HOLD, 0.4, False
    return Verdict.HOLD, 0.6, False
