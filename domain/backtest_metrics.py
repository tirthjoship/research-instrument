"""Pure performance metrics on equity curves / return series (stdlib only)."""

from __future__ import annotations

import math


def daily_returns(equity: list[float]) -> list[float]:
    out: list[float] = []
    for i in range(1, len(equity)):
        prev = equity[i - 1]
        out.append((equity[i] - prev) / prev if prev != 0 else 0.0)
    return out


def cagr(equity: list[float], periods_per_year: int = 252) -> float:
    if len(equity) < 2 or equity[0] <= 0:
        return 0.0
    n_periods = len(equity) - 1
    total = equity[-1] / equity[0]
    if total <= 0:
        return -1.0
    years = n_periods / periods_per_year
    if years <= 0:
        return 0.0
    result: float = total ** (1.0 / years) - 1.0
    return result


def sharpe(returns: list[float], periods_per_year: int = 252, rf: float = 0.0) -> float:
    if len(returns) < 2:
        return 0.0
    excess = [r - rf / periods_per_year for r in returns]
    mean = sum(excess) / len(excess)
    var = sum((r - mean) ** 2 for r in excess) / (len(excess) - 1)
    std = math.sqrt(var)
    if std == 0.0:
        return 0.0 if mean == 0.0 else float(math.copysign(math.inf, mean))
    return (mean / std) * math.sqrt(periods_per_year)


def sortino(
    returns: list[float], periods_per_year: int = 252, rf: float = 0.0
) -> float:
    if len(returns) < 2:
        return 0.0
    excess = [r - rf / periods_per_year for r in returns]
    mean = sum(excess) / len(excess)
    downside = [min(r, 0.0) ** 2 for r in excess]
    dd = math.sqrt(sum(downside) / len(excess))
    if dd == 0.0:
        return 0.0
    return (mean / dd) * math.sqrt(periods_per_year)


def max_drawdown(equity: list[float]) -> float:
    """Largest peak-to-trough decline as a positive fraction (0.40 = -40%)."""
    if not equity:
        return 0.0
    peak = equity[0]
    mdd = 0.0
    for v in equity:
        if v > peak:
            peak = v
        if peak > 0:
            dd = (peak - v) / peak
            if dd > mdd:
                mdd = dd
    return mdd
