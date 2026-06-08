"""Append-only JSONL log of discipline assessments (gitignored, local) + a resolver
that forward-scores past REDUCE/TRIM flags once enough time has elapsed. This is how
the engine's calibration is validated over time (spec §5). PRIVACY: file lives under
data/personal/ and is never committed."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from typing import Any, Callable

PriceProvider = Callable[[str], list[tuple[datetime, float]]]


def append_assessments(path: str, rows: list[dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a") as fh:
        for r in rows:
            fh.write(json.dumps(r, default=str) + "\n")


def read_assessments(path: str) -> list[dict[str, Any]]:
    if not os.path.exists(path):
        return []
    out: list[dict[str, Any]] = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def _price_on_or_after(
    series: list[tuple[datetime, float]], target: datetime
) -> float | None:
    for d, c in series:
        if d >= target:
            return c
    return None


def resolve_flags(
    logged: list[dict[str, Any]], price_provider: PriceProvider, horizon_days: int = 21
) -> dict[str, Any]:
    """For each logged REDUCE/TRIM flag whose horizon has elapsed, check whether the
    price fell over the horizon. Score with Brier (a REDUCE/TRIM predicts 'down', p=1.0).
    Returns resolved count, brier, and down_rate_on_reduce."""
    probs: list[float] = []
    outcomes: list[int] = []
    down_on_reduce = 0
    reduce_n = 0
    for row in logged:
        if row.get("verdict") not in ("REDUCE", "TRIM"):
            continue
        as_of = datetime.fromisoformat(str(row["as_of"])).replace(tzinfo=None)
        series = [
            (d.replace(tzinfo=None), c) for d, c in price_provider(str(row["ticker"]))
        ]
        entry = _price_on_or_after(series, as_of)
        later = _price_on_or_after(series, as_of + timedelta(days=horizon_days))
        if entry is None or later is None or entry <= 0:
            continue
        went_down = 1 if (later / entry - 1.0) < 0 else 0
        probs.append(1.0)
        outcomes.append(went_down)
        reduce_n += 1
        down_on_reduce += went_down
    from domain.calibration import brier_score

    return {
        "resolved": len(outcomes),
        "brier": brier_score(probs, outcomes),
        "down_rate_on_reduce": (down_on_reduce / reduce_n) if reduce_n else 0.0,
    }
