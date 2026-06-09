"""Pure macro-beta math (no IO, stdlib only).

Returns/alignment/book-aggregation/flag-policy for the macro-beta scrubber
(Unit A, ADR-052). The Ridge fit itself lives in the adapter; this module only
does deterministic arithmetic so it is fully unit- and property-testable.
"""

from __future__ import annotations

from datetime import datetime


def daily_returns(
    series: list[tuple[datetime, float]],
) -> list[tuple[datetime, float]]:
    """Simple daily returns between consecutive closes. `series` ascending by date.

    A step is dropped when the previous close is 0 (undefined return). The
    returned date is the *later* date of each consecutive pair.
    """
    out: list[tuple[datetime, float]] = []
    for (_, prev), (d, cur) in zip(series, series[1:]):
        if prev == 0:
            continue
        out.append((d, (cur - prev) / prev))
    return out


def align_returns(
    y_returns: list[tuple[datetime, float]],
    factor_returns: dict[str, list[tuple[datetime, float]]],
) -> tuple[list[float], dict[str, list[float]]]:
    """Inner-join y and all factor return series on common dates (ascending).

    Returns (y_aligned, {factor: aligned}) over dates present in EVERY series.
    """
    common: set[datetime] = {d for d, _ in y_returns}
    for series in factor_returns.values():
        common &= {d for d, _ in series}
    dates = sorted(common)
    y_map = dict(y_returns)
    f_maps = {f: dict(s) for f, s in factor_returns.items()}
    y_out = [y_map[d] for d in dates]
    f_out = {f: [f_maps[f][d] for d in dates] for f in factor_returns}
    return y_out, f_out


def book_return_series(
    holding_returns: dict[str, list[tuple[datetime, float]]],
    weights: dict[str, float],
    dates: list[datetime],
) -> list[tuple[datetime, float]]:
    """Dollar-weighted book return per date over `dates`.

    On each date, weights are renormalized over holdings that have a return that
    day (ragged histories handled honestly — a missing holding does not pin the
    book return to 0). Dates with no holdings present are skipped.
    """
    maps = {t: dict(s) for t, s in holding_returns.items()}
    out: list[tuple[datetime, float]] = []
    for d in dates:
        present = [(t, weights.get(t, 0.0)) for t in maps if d in maps[t]]
        wsum = sum(w for _, w in present)
        if wsum <= 0:
            continue
        r = sum((w / wsum) * maps[t][d] for t, w in present)
        out.append((d, r))
    return out
