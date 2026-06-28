"""Pure factor scoring (stdlib only — no numpy in domain/)."""

from statistics import mean, pstdev

from domain.evidence_registry import get_evidence


def zscore(values: list[float]) -> list[float]:
    if not values:
        return []
    mu = mean(values)
    sd = pstdev(values)
    if sd == 0:
        return [0.0 for _ in values]
    return [(v - mu) / sd for v in values]


def winsorize(values: list[float], p: float = 0.05) -> list[float]:
    if not values:
        return []
    s = sorted(values)
    n = len(s)
    lo = s[max(0, int(p * (n - 1)))]
    hi = s[min(n - 1, int((1 - p) * (n - 1)))]
    return [min(max(v, lo), hi) for v in values]


FACTOR_KEYS = ("momentum", "revision", "quality", "value", "lowvol")

# Internal factor key → evidence_registry key. The registry is the single source
# of truth for the user-facing label + honest caveat of each factor. Note that
# the internal key "revision" maps to "factor_analyst_dispersion": the factor
# measures analyst target-price DISPERSION, not estimate revision drift. The
# internal key is left unchanged (it is wired into regime weights, buckets, and
# factor bands) — only the displayed label is honest.
_FACTOR_EVIDENCE_KEYS: dict[str, str] = {
    "momentum": "factor_momentum",
    "revision": "factor_analyst_dispersion",
    "quality": "factor_quality",
    "value": "factor_value",
}


def factor_display_label(factor_key: str) -> str:
    """Return the honest user-facing label for an internal factor key.

    Sourced from ``domain.evidence_registry`` so the UI and the use-case share
    ONE source of truth. Falls back to a title-cased key when unregistered
    (e.g. ``"lowvol"``, which has no registry entry yet).
    """
    evidence_key = _FACTOR_EVIDENCE_KEYS.get(factor_key)
    if evidence_key is not None:
        entry = get_evidence(evidence_key)
        if entry is not None:
            return entry.label
    return factor_key.capitalize()


def factor_caveat(factor_key: str) -> str | None:
    """Return the honest "what this is NOT" caveat for a factor, or None.

    Sourced from ``domain.evidence_registry`` (single source of truth)."""
    evidence_key = _FACTOR_EVIDENCE_KEYS.get(factor_key)
    if evidence_key is not None:
        entry = get_evidence(evidence_key)
        if entry is not None:
            return entry.caveat
    return None


def revision_momentum(estimate_series: list[float] | None) -> float | None:
    """Analyst target-price dispersion: (last - first) / abs(first).

    HONESTY NOTE: this function is fed a target-price snapshot [low, mean, high]
    as sourced by yfinance, NOT a temporal series of EPS estimate revisions.
    It therefore measures analyst price-target SPREAD (dispersion), not temporal
    estimate drift (revision momentum in the academic sense).  True point-in-time
    EPS revision history is not sourceable from yfinance, so we use the target
    spread as a proxy.  Callers and the glossary label this "Analyst spread".
    Higher value = wider analyst disagreement about the target price.
    """
    if estimate_series is None or len(estimate_series) < 2:
        return None
    first, last = estimate_series[0], estimate_series[-1]
    if first == 0:
        return None
    return (last - first) / abs(first)


def composite_score(sub_scores: dict[str, float | None]) -> float:
    """Equal-weight mean over PRESENT (non-None) factor keys.

    Divides by the count of factors that are actually present, so a missing
    factor leaves the composite unchanged (no dilution bias).
    If all factors are None, returns 0.0.
    """
    total = 0.0
    n_present = 0
    for k in FACTOR_KEYS:
        v = sub_scores.get(k)
        if v is not None:
            total += v
            n_present += 1
    if n_present == 0:
        return 0.0
    return total / n_present
