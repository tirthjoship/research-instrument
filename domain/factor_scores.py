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
