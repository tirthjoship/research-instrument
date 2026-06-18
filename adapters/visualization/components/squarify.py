"""Pure squarified-treemap rectangle packing (no framework imports)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rect:
    """A tile rectangle: index into the input list + pixel geometry."""

    index: int
    x: float
    y: float
    w: float
    h: float


def squarify(values: list[float], x: float, y: float, w: float, h: float) -> list[Rect]:
    """Pack ``values`` (already in desired order) into rect (x,y,w,h).

    Returns one Rect per value; tile area is proportional to value and tiles
    stay as close to square as possible (Bruls et al. squarified treemap).
    """
    if not values:
        return []

    # Drop zero/negative values — degenerate tiles crash the algorithm
    # (division by zero in worst() / lay() when remaining reaches 0).
    # Track original indices so Rect.index maps back to the caller's list.
    filtered = [(idx, v) for idx, v in enumerate(values) if v > 0]
    if not filtered:
        return []
    orig_idx = [idx for idx, _ in filtered]
    values = [v for _, v in filtered]

    out: list[Rect] = []
    rx, ry, rw, rh = x, y, w, h
    remaining = float(sum(values))
    i = 0
    row: list[float] = []
    row_idx: list[int] = []

    def worst(candidate: list[float]) -> float:
        s = sum(candidate)
        if s <= 0:
            return float("inf")
        vertical = rw >= rh
        side = rh if vertical else rw
        thick = (s / remaining) * (rw if vertical else rh)
        if thick <= 0:
            return float("inf")
        bad = 1.0
        for v in candidate:
            long = (v / s) * side
            if long <= 0:
                return float("inf")
            ar = max(long / thick, thick / long)
            bad = max(bad, ar)
        return bad

    def lay(r: list[float], idxs: list[int]) -> None:
        nonlocal rx, ry, rw, rh, remaining
        s = sum(r)
        vertical = rw >= rh
        side = rh if vertical else rw
        thick = (s / remaining) * (rw if vertical else rh)
        off = ry if vertical else rx
        for v, idx in zip(r, idxs):
            long = (v / s) * side
            if vertical:
                out.append(Rect(idx, rx, off, thick, long))
            else:
                out.append(Rect(idx, off, ry, long, thick))
            off += long
        if vertical:
            rx += thick
            rw -= thick
        else:
            ry += thick
            rh -= thick
        remaining -= s

    while i < len(values):
        cand = row + [values[i]]
        if not row or worst(cand) <= worst(row):
            row = cand
            row_idx = row_idx + [orig_idx[i]]
            i += 1
        else:
            lay(row, row_idx)
            row, row_idx = [], []
    if row:
        lay(row, row_idx)
    return out
