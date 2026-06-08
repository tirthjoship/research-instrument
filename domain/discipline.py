"""Pure discipline/risk grading primitives (stdlib only). The deterministic core
computes verdicts; the LLM narrator only explains them, never produces them."""

from __future__ import annotations


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
