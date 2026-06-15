"""Reason-bucket assignment for the screener — pure, stdlib only."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

TOP_QUARTILE = 0.75


@dataclass(frozen=True)
class BucketInput:
    ticker: str
    percentiles: Mapping[str, float]
    composite: float
