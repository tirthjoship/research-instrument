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


FACTOR_KEYS = ("momentum", "revision", "quality", "value")


def revision_momentum(estimate_series: list[float] | None) -> float | None:
    """Normalized drift of analyst EPS estimates (oldest..newest)."""
    if estimate_series is None or len(estimate_series) < 2:
        return None
    first, last = estimate_series[0], estimate_series[-1]
    if first == 0:
        return None
    return (last - first) / abs(first)


def composite_score(sub_scores: dict[str, float | None]) -> float:
    """Equal-weight mean over the 4 factor keys. None = flagged-neutral (0.0)."""
    total = 0.0
    for k in FACTOR_KEYS:
        v = sub_scores.get(k)
        total += 0.0 if v is None else v
    return total / len(FACTOR_KEYS)
