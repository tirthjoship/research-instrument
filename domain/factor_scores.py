"""Pure factor scoring (stdlib only — no numpy in domain/)."""

from statistics import mean, pstdev


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
