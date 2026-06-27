"""SP5 gate log adapter — append-only JSONL for GateSample and GateResult."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Literal

from domain.corroboration_gate import GateResult, GateSample

SAMPLES_PATH: Path = Path("data/corroboration_samples.jsonl")
RESULTS_PATH: Path = Path("data/corroboration_gate_log.jsonl")


# ---------------------------------------------------------------------------
# Internal helpers — samples
# ---------------------------------------------------------------------------


def _sample_key(s: GateSample) -> str:
    return f"{s.ticker}:{s.snapshot_date.isoformat()}"


def _sample_to_dict(s: GateSample) -> dict[str, object]:
    return {
        "ticker": s.ticker,
        "snapshot_date": s.snapshot_date.isoformat(),
        "resolved_at": s.resolved_at.isoformat(),
        "excess_21d": s.excess_21d,
        "excess_63d": s.excess_63d,  # None serialises as JSON null
        "beat_spy_21d": s.beat_spy_21d,
    }


def _dict_to_sample(d: dict[str, object]) -> GateSample:
    raw_63d = d.get("excess_63d")
    return GateSample(
        ticker=str(d["ticker"]),
        snapshot_date=date.fromisoformat(str(d["snapshot_date"])),
        resolved_at=date.fromisoformat(str(d["resolved_at"])),
        excess_21d=float(d["excess_21d"]),  # type: ignore[arg-type]
        excess_63d=float(raw_63d) if raw_63d is not None else None,  # type: ignore[arg-type]
        beat_spy_21d=bool(d["beat_spy_21d"]),
    )


# ---------------------------------------------------------------------------
# Internal helpers — results
# ---------------------------------------------------------------------------


def _result_to_dict(r: GateResult) -> dict[str, object]:
    return {
        "n_resolved": r.n_resolved,
        "mean_excess_21d": r.mean_excess_21d,
        "ci_lower": r.ci_lower,
        "ci_upper": r.ci_upper,
        "hit_rate_21d": r.hit_rate_21d,
        "mean_excess_63d": r.mean_excess_63d,  # None serialises as JSON null
        "verdict": r.verdict,
        "evaluated_at": r.evaluated_at.isoformat(),
    }


def _dict_to_result(d: dict[str, object]) -> GateResult:
    raw_63d = d.get("mean_excess_63d")
    v: Literal["PENDING", "PASS", "FAIL"] = str(d["verdict"])  # type: ignore[assignment]
    return GateResult(
        n_resolved=int(str(d["n_resolved"])),
        mean_excess_21d=float(str(d["mean_excess_21d"])),
        ci_lower=float(str(d["ci_lower"])),
        ci_upper=float(str(d["ci_upper"])),
        hit_rate_21d=float(str(d["hit_rate_21d"])),
        mean_excess_63d=float(str(raw_63d)) if raw_63d is not None else None,
        verdict=v,
        evaluated_at=date.fromisoformat(str(d["evaluated_at"])),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_samples(path: Path = SAMPLES_PATH) -> list[GateSample]:
    """Return all GateSamples from *path*, deduplicated by ticker:snapshot_date.

    The last occurrence of a duplicate key wins (append-wins semantics).
    """
    if not path.exists():
        return []
    seen: dict[str, GateSample] = {}
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                s = _dict_to_sample(json.loads(line))
                seen[_sample_key(s)] = s
    return list(seen.values())


def append_samples(
    new_samples: list[GateSample],
    path: Path = SAMPLES_PATH,
) -> int:
    """Append *new_samples* to *path*, skipping duplicates already on disk.

    Returns the count of lines actually written (newly unique samples only).
    Dedup key: ``ticker:snapshot_date``.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    # Build the set of keys already stored on disk
    existing_keys: set[str] = {_sample_key(s) for s in load_samples(path)}

    written = 0
    with path.open("a") as f:
        for s in new_samples:
            key = _sample_key(s)
            if key not in existing_keys:
                f.write(json.dumps(_sample_to_dict(s)) + "\n")
                existing_keys.add(key)  # guard against duplicates within the batch
                written += 1
    return written


def append_result(result: GateResult, path: Path = RESULTS_PATH) -> None:
    """Append one GateResult entry to *path* (append-only log)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(_result_to_dict(result)) + "\n")


def load_latest_result(path: Path = RESULTS_PATH) -> GateResult | None:
    """Return the most recently appended GateResult, or None if file missing/empty."""
    if not path.exists():
        return None
    last: str | None = None
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                last = line
    if last is None:
        return None
    return _dict_to_result(json.loads(last))
