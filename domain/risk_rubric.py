"""Pure risk rubric: character-not-quality bands + scale positions (stdlib only)."""

from __future__ import annotations

from enum import Enum


class NetBetaBand(Enum):
    HEDGED = "Hedged"
    DEFENSIVE = "Defensive"
    MARKET_LIKE = "Market-like"
    ELEVATED = "Elevated"
    AGGRESSIVE = "Aggressive"


class ShareBand(Enum):
    STOCK_SPECIFIC = "Stock-specific"
    BALANCED = "Balanced"
    MACRO_LEANING = "Macro-leaning"
    MACRO_DOMINATED = "Macro-dominated"


def classify_net_beta(v: float) -> NetBetaBand:
    if v < 0.0:
        return NetBetaBand.HEDGED
    if v < 0.8:
        return NetBetaBand.DEFENSIVE
    if v < 1.2:
        return NetBetaBand.MARKET_LIKE
    if v < 1.6:
        return NetBetaBand.ELEVATED
    return NetBetaBand.AGGRESSIVE


def classify_systematic_share(v: float, flag: float = 0.60) -> ShareBand:
    if v < 0.40:
        return ShareBand.STOCK_SPECIFIC
    if v < flag:
        return ShareBand.BALANCED
    if v < 0.75:
        return ShareBand.MACRO_LEANING
    return ShareBand.MACRO_DOMINATED


_DOMAIN_LO, _DOMAIN_HI = -0.5, 2.0  # net beta rendered domain


def net_beta_position(v: float) -> float:
    """Linear position 0..100 for the needle; clamps outside the rendered domain."""
    pct = (v - _DOMAIN_LO) / (_DOMAIN_HI - _DOMAIN_LO) * 100.0
    return max(0.0, min(100.0, pct))
