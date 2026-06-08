"""Pure trend/momentum rule primitives (stdlib only). Pre-registered params
live in the use cases; these are parameter-free building blocks."""

from __future__ import annotations

import math


def sma(values: list[float], window: int) -> float | None:
    """Simple moving average of the last `window` values; None if too few."""
    if window <= 0 or len(values) < window:
        return None
    return sum(values[-window:]) / window


def above_trend(price: float, sma_value: float | None) -> bool:
    """True iff price is strictly above the trend line. None SMA => not in trend."""
    if sma_value is None:
        return False
    return price > sma_value


def true_range(high: float, low: float, prev_close: float | None) -> float:
    """Wilder true range. prev_close None => simple high-low."""
    hl = high - low
    if prev_close is None:
        return hl
    return max(hl, abs(high - prev_close), abs(low - prev_close))


def atr(
    highs: list[float], lows: list[float], closes: list[float], window: int
) -> float | None:
    """Average true range over the last `window` bars (simple mean of TRs)."""
    n = len(closes)
    if n < window or len(highs) != n or len(lows) != n or window <= 0:
        return None
    trs: list[float] = []
    for i in range(n - window, n):
        prev_close = closes[i - 1] if i > 0 else None
        trs.append(true_range(highs[i], lows[i], prev_close))
    return sum(trs) / window


def chandelier_stop(highest_high: float, atr_value: float, mult: float = 3.0) -> float:
    """Trailing stop = highest high since entry minus mult*ATR."""
    return highest_high - mult * atr_value


def momentum_12_1(monthly_closes: list[float]) -> float | None:
    """12-minus-1 month total return: price 1 month ago / price 12 months ago - 1.
    Needs >= 13 monthly closes (most recent last). Skips the most recent month."""
    if len(monthly_closes) < 13:
        return None
    twelve_ago = monthly_closes[-13]
    one_ago = monthly_closes[-2]
    if twelve_ago <= 0:
        return None
    return one_ago / twelve_ago - 1.0


def trend_health(
    price: float, sma_value: float | None, atr_value: float | None
) -> float | None:
    """Signed distance of price from the trend line in ATR units.
    Positive = above trend, negative = below. None if inputs unavailable."""
    if sma_value is None or atr_value is None or atr_value <= 0:
        return None
    return (price - sma_value) / atr_value


def ma_slope(values: list[float], window: int) -> float | None:
    """Normalized change in the SMA from `window` bars ago to now.
    Needs >= 2*window values. None if too few or the older SMA is non-positive."""
    if window <= 0 or len(values) < 2 * window:
        return None
    sma_now = sum(values[-window:]) / window
    sma_then = sum(values[-2 * window : -window]) / window
    if sma_then <= 0:
        return None
    return (sma_now - sma_then) / sma_then


def relative_strength(
    asset_closes: list[float], benchmark_closes: list[float], window: int
) -> float | None:
    """Asset return minus benchmark return over the last `window` bars.
    Needs > window closes in each. None if insufficient or a base price is non-positive.
    """
    if window <= 0 or len(asset_closes) <= window or len(benchmark_closes) <= window:
        return None
    a0, a1 = asset_closes[-window - 1], asset_closes[-1]
    b0, b1 = benchmark_closes[-window - 1], benchmark_closes[-1]
    if a0 <= 0 or b0 <= 0:
        return None
    return (a1 / a0 - 1.0) - (b1 / b0 - 1.0)


def top_fraction_threshold(values: list[float], fraction: float) -> float | None:
    """Return the cutoff value such that the top `fraction` of values are >= it."""
    clean = [v for v in values if not math.isnan(v)]
    if not clean or fraction <= 0:
        return None
    k = max(1, math.floor(len(clean) * fraction))
    return sorted(clean, reverse=True)[k - 1]
