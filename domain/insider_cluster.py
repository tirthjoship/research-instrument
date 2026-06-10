"""Non-routine insider-cluster detection (pure domain).

Strict cluster = >=3 distinct insiders making open-market purchases (Form-4
transaction code 'P', acquired flag 'A') within a 30-day window. Signal fires on
the FILING date (point-in-time), never the transaction date. See spec
2026-06-09-insider-cluster-falsification-design.md (pre-registration).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from domain.exceptions import LookAheadBiasError

CLUSTER_MIN_INSIDERS = 3
CLUSTER_WINDOW_DAYS = 30
INCLUDED_TRANS_CODE = "P"
INCLUDED_ACQ_DISP = "A"
# Documentation only: the ENFORCED contract is the is_qualifying_buy() allowlist
# (TRANS_CODE == 'P' AND TRANS_ACQUIRED_DISP_CD == 'A'). This blocklist mirrors the
# spec's exclusion list for reference; nothing reads it for filtering. NB the 'A'
# here is the transaction CODE for a grant/award — a DIFFERENT column from
# INCLUDED_ACQ_DISP='A' (the acquired/disposed FLAG). Never conflate them (spec sec.2).
EXCLUDED_TRANS_CODES = {"S", "M", "A", "G", "F", "C", "W"}
# Lock the code-vs-flag distinction: the included purchase code must never be in
# the exclusion list (a future edit pointing the blocklist at the wrong column
# would silently zero the signal).
assert INCLUDED_TRANS_CODE not in EXCLUDED_TRANS_CODES


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


def detect_clusters(
    transactions: list[InsiderTransaction],
) -> list[ClusterEvent]:
    """Detect strict clusters per ticker.

    A cluster fires when >=3 DISTINCT insiders each have a qualifying buy whose
    FILING dates fall within a rolling 30-day window. Fire date = the filing date
    that completes the 3rd distinct insider (point-in-time: the cluster is only
    knowable once that 3rd Form-4 is public). At most one event per ticker per
    completing-window is emitted; subsequent qualifying buys that extend the same
    standing cluster do not re-fire until the window of distinct insiders resets.
    """
    by_ticker: dict[str, list[InsiderTransaction]] = {}
    for t in transactions:
        if t.is_qualifying_buy():
            by_ticker.setdefault(t.ticker, []).append(t)

    events: list[ClusterEvent] = []
    window = timedelta(days=CLUSTER_WINDOW_DAYS)
    for ticker, txns in by_ticker.items():
        txns.sort(key=lambda x: x.filing_date)
        fired_until: date | None = None
        for i, anchor in enumerate(txns):
            seen: dict[str, InsiderTransaction] = {}
            for t in txns[i:]:
                if t.filing_date - anchor.filing_date > window:
                    break
                seen.setdefault(t.insider_cik, t)
                if len(seen) >= CLUSTER_MIN_INSIDERS:
                    fire_date = t.filing_date
                    # Point-in-time guard (spec sec.2 / CLAUDE.md look-ahead rule):
                    # no contributing filing may post-date the fire date. This is
                    # structurally guaranteed (txns sorted ascending; fire = the
                    # completing filing), asserted as defense-in-depth so a future
                    # refactor cannot silently leak a later filing into the signal.
                    if any(s.filing_date > fire_date for s in seen.values()):
                        raise LookAheadBiasError(
                            f"insider cluster {ticker}: a contributing Form-4 filing "
                            f"post-dates the fire date {fire_date}"
                        )
                    if fired_until is None or fire_date > fired_until:
                        events.append(
                            ClusterEvent(
                                ticker=ticker,
                                fire_date=fire_date,
                                distinct_insiders=len(seen),
                                total_buy_value=sum(
                                    s.shares * s.price_per_share for s in seen.values()
                                ),
                            )
                        )
                        fired_until = fire_date + window
                    break
    return events
