"""Diversification lens: rank candidates by lowest |corr| of daily returns to the
book's dominant macro factor. Pure composition over caller-supplied price series —
point-in-time safety is the caller's responsibility (series end at as_of)."""

from __future__ import annotations

MIN_POINTS = 5  # need >= MIN_POINTS closes -> MIN_POINTS-1 returns


def _returns(closes: list[float]) -> list[float]:
    return [
        (b - a) / a for a, b in zip(closes[:-1], closes[1:], strict=False) if a != 0.0
    ]


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = min(len(xs), len(ys))
    if n < MIN_POINTS - 1:
        return None
    xs, ys = xs[-n:], ys[-n:]
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx == 0.0 or vy == 0.0:
        return None
    raw: float = cov / (vx**0.5 * vy**0.5)
    return max(-1.0, min(1.0, raw))


def rank_by_diversification(
    *,
    factor_series: list[float],
    candidate_series: dict[str, list[float]],
) -> list[tuple[str, float]]:
    """Return (ticker, corr) sorted by |corr| ascending — most diversifying first."""
    fr = _returns(factor_series)
    out: list[tuple[str, float]] = []
    for ticker, closes in candidate_series.items():
        corr = _pearson(fr, _returns(closes))
        if corr is not None:
            out.append((ticker, corr))
    return sorted(out, key=lambda r: abs(r[1]))
