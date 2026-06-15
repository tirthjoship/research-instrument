"""Plain-language bands for factor percentiles — pure, stdlib only."""

from __future__ import annotations

from enum import Enum


class Band(Enum):
    EXCEPTIONAL = "Exceptional"
    STRONG = "Strong"
    FLAT = "Flat"
    WEAK = "Weak"


def band_for_percentile(percentile: float) -> Band:
    """Map a 0–1 percentile to a plain-language band. Cutoffs are inclusive lower edges."""
    if percentile >= 0.90:
        return Band.EXCEPTIONAL
    if percentile >= 0.75:
        return Band.STRONG
    if percentile >= 0.40:
        return Band.FLAT
    return Band.WEAK
    # No clamping needed: the >= ladder is total — any float resolves to exactly one band.


_TONE = {
    Band.EXCEPTIONAL: "success",
    Band.STRONG: "accent",
    Band.FLAT: "muted",
    Band.WEAK: "danger",
}


def band_tone_key(band: Band) -> str:
    """Semantic colour key (UI maps to a styles.py var; domain holds no hex)."""
    return _TONE[band]
