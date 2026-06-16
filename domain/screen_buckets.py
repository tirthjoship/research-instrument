"""Reason-bucket assignment for the screener — pure, stdlib only."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum

TOP_QUARTILE = 0.75


@dataclass(frozen=True)
class BucketInput:
    ticker: str
    percentiles: Mapping[str, float]
    composite: float


def _top(p: Mapping[str, float], factor: str) -> bool:
    return p.get(factor, 0.0) >= TOP_QUARTILE


def _count_top(p: Mapping[str, float]) -> int:
    return sum(
        _top(p, f) for f in ("quality", "value", "revision", "momentum", "lowvol")
    )


class Bucket(Enum):
    ALL_ROUNDER = ("🌟", "All-rounder")
    MOMENTUM_LEADERS = ("🚀", "Momentum leaders")
    QUALITY_FAIR_PRICE = ("💎", "Quality at a fair price")
    VALUE_CATALYST = ("📈", "Value with a catalyst")
    QUALITY_COMPOUNDERS = ("⭐", "Quality compounders")
    LOWVOL_DEFENSIVES = ("🛡️", "Low-vol defensives")

    @property
    def emoji(self) -> str:
        return self.value[0]

    @property
    def label(self) -> str:
        return self.value[1]


_PREDICATES: dict[Bucket, Callable[[Mapping[str, float]], bool]] = {
    Bucket.ALL_ROUNDER: lambda p: _count_top(p) >= 3,
    Bucket.MOMENTUM_LEADERS: lambda p: _top(p, "momentum") and _top(p, "revision"),
    Bucket.QUALITY_FAIR_PRICE: lambda p: _top(p, "quality") and _top(p, "value"),
    Bucket.VALUE_CATALYST: lambda p: _top(p, "value") and _top(p, "revision"),
    Bucket.QUALITY_COMPOUNDERS: lambda p: _top(p, "quality"),
    Bucket.LOWVOL_DEFENSIVES: lambda p: _top(p, "lowvol"),
}


def qualifies(bucket: Bucket, percentiles: Mapping[str, float]) -> bool:
    return bool(_PREDICATES[bucket](percentiles))


PRIORITY: tuple[Bucket, ...] = (
    Bucket.ALL_ROUNDER,
    Bucket.MOMENTUM_LEADERS,
    Bucket.QUALITY_FAIR_PRICE,
    Bucket.VALUE_CATALYST,
    Bucket.QUALITY_COMPOUNDERS,
    Bucket.LOWVOL_DEFENSIVES,
)


def primary_bucket(percentiles: Mapping[str, float]) -> Bucket | None:
    for bucket in PRIORITY:
        if qualifies(bucket, percentiles):
            return bucket
    return None


MAX_PER_BUCKET = 5


def assign_buckets(
    candidates: list[BucketInput],
) -> dict[Bucket, list[BucketInput]]:
    """Group candidates into every bucket they qualify for (repeats allowed),
    ranked by composite desc (ticker asc tie-break), capped at MAX_PER_BUCKET.
    Every bucket key is always present (empty list if none qualify)."""
    out: dict[Bucket, list[BucketInput]] = {b: [] for b in PRIORITY}
    for bucket in PRIORITY:
        members = [c for c in candidates if qualifies(bucket, c.percentiles)]
        members.sort(key=lambda c: (-c.composite, c.ticker))
        out[bucket] = members[:MAX_PER_BUCKET]
    return out
