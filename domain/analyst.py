"""Analyst rating domain models. Pure value objects, no framework imports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class AnalystAction(str, Enum):
    """Direction of an analyst rating change."""

    UPGRADE = "upgrade"
    DOWNGRADE = "downgrade"
    INIT = "init"
    MAINTAIN = "maintain"


@dataclass(frozen=True)
class AnalystRating:
    """A single analyst rating event from a firm.

    published_at is a naive datetime (matches the codebase convention). It is
    the point-in-time anchor: a rating may only be used as a signal at or after
    published_at.
    """

    ticker: str
    firm: str
    rating: str
    prior_rating: str | None
    action: AnalystAction
    price_target: float | None
    published_at: datetime
    source: str

    def __post_init__(self) -> None:
        if self.price_target is not None and self.price_target < 0:
            raise ValueError(
                f"price_target must be >= 0 if provided, got {self.price_target}"
            )
