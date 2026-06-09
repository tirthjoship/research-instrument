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
    """Forward-score logged flags once their horizon has elapsed.

    REDUCE is the only DIRECTIONAL down-call: it asserts the name will fall (p=1.0),
    so it alone feeds the Brier and the calibration gate (ADR-048). TRIM is a
    position-sizing action (trim a winner that breached its trailing stop), NOT a
    prediction of a drop — historically TRIM names keep rising — so it is tracked
    separately for transparency and excluded from the directional Brier.

    Returns: resolved/brier/down_rate_on_reduce (REDUCE-only, the gate inputs) plus
    informational trim_resolved/down_rate_on_trim."""
    reduce_probs: list[float] = []
    reduce_outcomes: list[int] = []
    reduce_resolved_as_ofs: list[str] = []
    down_on_reduce = 0
    trim_n = 0
    down_on_trim = 0
    for row in logged:
        verdict = row.get("verdict")
        if verdict not in ("REDUCE", "TRIM"):
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
        if verdict == "REDUCE":
            reduce_probs.append(1.0)
            reduce_outcomes.append(went_down)
            down_on_reduce += went_down
            reduce_resolved_as_ofs.append(str(row["as_of"]))
        else:  # TRIM — informational only, never a down-call
            trim_n += 1
            down_on_trim += went_down
    from domain.calibration import brier_score

    return {
        "resolved": len(reduce_outcomes),
        "brier": brier_score(reduce_probs, reduce_outcomes),
        "down_rate_on_reduce": (
            down_on_reduce / len(reduce_outcomes) if reduce_outcomes else 0.0
        ),
        "trim_resolved": trim_n,
        "down_rate_on_trim": (down_on_trim / trim_n) if trim_n else 0.0,
        "reduce_resolved_as_ofs": reduce_resolved_as_ofs,
    }
