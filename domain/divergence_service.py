"""Early-signal divergence: buzz accelerating while price has not moved. Pure."""

from __future__ import annotations

from datetime import datetime, timedelta

_RECENT_DAYS = 7
_BASE_DAYS = 30  # the 30 days before the recent window


def _count_between(times: list[datetime], lo: datetime, hi: datetime) -> int:
    return sum(1 for t in times if lo < t <= hi)


def _recent_return(price_series: list[tuple[datetime, float]], now: datetime) -> float:
    if len(price_series) < 2:
        return 0.0
    asc = sorted(price_series, key=lambda p: p[0])
    last = asc[-1][1]
    cutoff = now - timedelta(days=_RECENT_DAYS)
    prior = next((p for d, p in reversed(asc) if d <= cutoff), asc[0][1])
    if prior == 0:
        return 0.0
    return (last - prior) / prior


def _mean_between(
    series: list[tuple[datetime, float]], lo: datetime, hi: datetime
) -> float:
    vals = [v for t, v in series if lo < t <= hi]
    return sum(vals) / len(vals) if vals else 0.0


def intensity_acceleration(
    series: list[tuple[datetime, float]], now: datetime
) -> float:
    """Scale-free acceleration of an intensity series (GT index, pageviews).

    Mirrors event buzz_accel but on levels: recent mean vs base mean.
    Returns ~[-1, 1]; 0.0 when no data or perfectly flat.
    """
    if not series:
        return 0.0
    recent_level = _mean_between(series, now - timedelta(days=_RECENT_DAYS), now)
    base_level = _mean_between(
        series,
        now - timedelta(days=_RECENT_DAYS + _BASE_DAYS),
        now - timedelta(days=_RECENT_DAYS),
    )
    denom = max(recent_level, base_level, 1e-9)
    return (recent_level - base_level) / denom


def divergence_score(
    buzz_times: list[datetime],
    price_series: list[tuple[datetime, float]],
    sentiment: float,
    now: datetime,
) -> float:
    """0-10. High when buzz frequency is rising and price hasn't moved yet.
    Neutral 5.0 with no buzz. Inputs pre-filtered to <= now upstream."""
    if not buzz_times:
        return 5.0
    recent = _count_between(buzz_times, now - timedelta(days=_RECENT_DAYS), now)
    base = _count_between(
        buzz_times,
        now - timedelta(days=_RECENT_DAYS + _BASE_DAYS),
        now - timedelta(days=_RECENT_DAYS),
    )
    base_rate = (base / _BASE_DAYS) * _RECENT_DAYS
    buzz_accel = (recent - base_rate) / max(recent, base_rate, 1.0)
    price_move = max(_recent_return(price_series, now), 0.0)
    raw = buzz_accel - price_move * 2.0
    score = 5.0 + raw * 5.0 + (sentiment - 0.5) * 2.0
    return max(1.0, min(10.0, score))
