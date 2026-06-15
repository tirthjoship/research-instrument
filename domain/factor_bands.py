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
