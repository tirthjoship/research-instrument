"""Pure trend-following math for the sleeve falsification test (stdlib only)."""

from __future__ import annotations

__all__ = [
    "time_series_momentum",
    "inverse_vol_weights",
    "turnover",
    "blend_returns",
    "equity_curve",
]


def time_series_momentum(monthly_closes: list[float]) -> float | None:
    """12-month total return: most-recent close / close 12 months ago - 1.

    Needs >= 13 monthly closes (most recent last). None if too few or the
    12-months-ago close is non-positive.
    """
    if len(monthly_closes) < 13:
        return None
    base = monthly_closes[-13]
    if base <= 0:
        return None
    return monthly_closes[-1] / base - 1.0


def equity_curve(returns: list[float]) -> list[float]:
    """Compound a return series into an equity curve starting at 1.0.

    Returns a list of length len(returns)+1 (the leading 1.0 plus one point
    per period).
    """
    equity = [1.0]
    for r in returns:
        equity.append(equity[-1] * (1.0 + r))
    return equity


def inverse_vol_weights(vols: dict[str, float]) -> dict[str, float]:
    """Raw inverse-volatility weights normalized to sum to 1 across all entries
    with a positive vol. Entries with vol <= 0 are excluded (weight 0). Returns
    {} when no entry has a positive vol.
    """
    inv = {k: 1.0 / v for k, v in vols.items() if v > 0}
    total = sum(inv.values())
    if total <= 0:
        return {}
    return {k: w / total for k, w in inv.items()}


def turnover(prev_w: dict[str, float], new_w: dict[str, float]) -> float:
    """One-way turnover = 0.5 * sum over the union of keys of |new - prev|.

    A weight absent from a dict is treated as 0. Range [0, 1] when both books
    are fully allocated (cash counts as the absent remainder, so a shift into
    cash is captured by the shrinking asset weights).
    """
    keys = set(prev_w) | set(new_w)
    return 0.5 * sum(abs(new_w.get(k, 0.0) - prev_w.get(k, 0.0)) for k in keys)


def blend_returns(
    core: list[float], sleeve: list[float], core_weight: float
) -> list[float]:
    """Element-wise convex combination: core_weight*core + (1-core_weight)*sleeve.

    `core` and `sleeve` must be the same length.
    """
    sw = 1.0 - core_weight
    return [core_weight * c + sw * s for c, s in zip(core, sleeve)]
