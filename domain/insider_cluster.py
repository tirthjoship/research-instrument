"""Non-routine insider-cluster detection (pure domain).

Strict cluster = >=3 distinct insiders making open-market purchases (Form-4
transaction code 'P', acquired flag 'A') within a 30-day window. Signal fires on
the FILING date (point-in-time), never the transaction date. See spec
2026-06-09-insider-cluster-falsification-design.md (pre-registration).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

CLUSTER_MIN_INSIDERS = 3
CLUSTER_WINDOW_DAYS = 30
INCLUDED_TRANS_CODE = "P"
INCLUDED_ACQ_DISP = "A"
EXCLUDED_TRANS_CODES = {"S", "M", "A", "G", "F", "C", "W"}


@dataclass(frozen=True)
class InsiderTransaction:
    ticker: str
    insider_cik: str
    trans_code: str
    acquired_disp: str
    shares: float
    price_per_share: float
    filing_date: date
    trans_date: date
    equity_swap: bool
    aff10b51: bool

    def __post_init__(self) -> None:
        if self.shares < 0:
            raise ValueError(f"shares must be >= 0, got {self.shares}")
        if self.price_per_share < 0:
            raise ValueError(f"price must be >= 0, got {self.price_per_share}")

    def is_qualifying_buy(self) -> bool:
        """A non-routine open-market purchase that counts toward a cluster."""
        return (
            self.trans_code == INCLUDED_TRANS_CODE
            and self.acquired_disp == INCLUDED_ACQ_DISP
            and self.shares > 0
            and not self.equity_swap
            and not self.aff10b51
        )


@dataclass(frozen=True)
class ClusterEvent:
    ticker: str
    fire_date: date  # filing date of the 3rd qualifying insider (point-in-time)
    distinct_insiders: int
    total_buy_value: float
