"""Pure sector-relative percentile math (E1). No external imports."""

from __future__ import annotations


def sector_percentile(value: float | None, peers: list[float | None]) -> float | None:
    clean = [p for p in peers if p is not None]
    if value is None or not clean:
        return None
    beaten = sum(1 for p in clean if value > p)
    return round(100.0 * beaten / len(clean), 1)
