"""Pure date-diversity / readiness math for the discipline forward-calibration gate.

Strengthens the ADR-048 experimental design (pre-outcome) by measuring the as_of
diversity of the REDUCE forward-log sample. Changes NO locked threshold. Stdlib
only; unit-testable on synthetic logged-row dicts (no network). See ADR-051.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

__all__ = [
    "spread_of_as_ofs",
    "as_of_spread",
    "resolvable_split",
    "freshness",
]

REDUCE = "REDUCE"


def _date_of(as_of: str) -> date:
    return datetime.fromisoformat(as_of).date()


def spread_of_as_ofs(as_ofs: list[str]) -> dict[str, Any]:
    """Distinct as_of DATES + calendar span across a list of ISO timestamp strings."""
    dates = sorted({_date_of(s) for s in as_ofs})
    if not dates:
        return {"distinct_dates": 0, "span_days": 0, "min_date": None, "max_date": None}
    return {
        "distinct_dates": len(dates),
        "span_days": (dates[-1] - dates[0]).days,
        "min_date": dates[0].isoformat(),
        "max_date": dates[-1].isoformat(),
    }


def as_of_spread(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """spread_of_as_ofs over the as_of field of every row that has one."""
    return spread_of_as_ofs([str(r["as_of"]) for r in rows if "as_of" in r])


def resolvable_split(
    rows: list[dict[str, Any]], today: date, horizon_days: int
) -> dict[str, int]:
    """REDUCE flags whose horizon has elapsed by `today` (resolvable) vs not (pending)."""
    resolvable = pending = 0
    for r in rows:
        if r.get("verdict") != REDUCE:
            continue
        if _date_of(str(r["as_of"])) + timedelta(days=horizon_days) <= today:
            resolvable += 1
        else:
            pending += 1
    return {"resolvable": resolvable, "pending": pending}


def freshness(rows: list[dict[str, Any]], today: date) -> int | None:
    """Calendar days since the most recent as_of date. None if no rows."""
    dates = [_date_of(str(r["as_of"])) for r in rows if "as_of" in r]
    if not dates:
        return None
    return (today - max(dates)).days
