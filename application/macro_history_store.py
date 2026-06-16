"""Append-only weekly systematic-share history (JSONL) for the drift sparkline."""

from __future__ import annotations

import json
from pathlib import Path


def append_systematic_share(path: str, as_of: str, value: float) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as fh:
        fh.write(json.dumps({"as_of": as_of, "systematic_share": value}) + "\n")


def load_systematic_share_history(path: str) -> list[tuple[str, float]]:
    p = Path(path)
    if not p.exists():
        return []
    out: list[tuple[str, float]] = []
    for line in p.read_text().splitlines():
        if not line.strip():
            continue
        try:
            d = json.loads(line)
            out.append((str(d["as_of"]), float(d["systematic_share"])))
        except Exception:
            continue
    return out
