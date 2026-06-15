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


_STRONG = {Band.EXCEPTIONAL, Band.STRONG}


def plain_read(bands: dict[str, "Band"]) -> str:
    """One-sentence, forecast-free read of a name's band profile. Deterministic."""
    q = bands.get("quality", Band.FLAT)
    v = bands.get("value", Band.FLAT)
    m = bands.get("momentum", Band.FLAT)
    r = bands.get("revision", Band.FLAT)

    strengths = [
        name
        for name, b in (("quality", q), ("value", v), ("revision", r))
        if b in _STRONG
    ]
    head = "Strong on " + " and ".join(strengths) if strengths else "No standout factor"

    # momentum caveat
    mom = (
        "momentum flat"
        if m == Band.FLAT
        else ("momentum weak" if m == Band.WEAK else "momentum strong")
    )

    # value framing
    if v == Band.WEAK:
        tail = "but not cheap — decide if the premium is justified"
    elif v in _STRONG and q in _STRONG:
        tail = "a value setup worth a look, not urgent"
    else:
        tail = "a reason to investigate, not a return forecast"

    return f"{head}; {mom} — {tail}."
