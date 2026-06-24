"""SP5 resolver use case: build GateSamples from STRONG-tier corroboration snapshots."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from domain.corroboration_gate import GateSample
from domain.corroboration_models import ConvergenceTier
from domain.ports import ResolverPricePort

logger = logging.getLogger(__name__)


def _ret(price: ResolverPricePort, ticker: str, start: date, end: date) -> float:
    """Compute simple return between two dates using the price port."""
    p0 = price.price_at(ticker, start)
    p1 = price.price_at(ticker, end)
    return (p1 - p0) / p0


class CorroborationResolverUseCase:
    """Load STRONG-tier snapshots ≥21d old and compute excess returns vs SPY.

    Caller is responsible for deduplicating (ticker, snapshot_date) pairs via
    ``append_samples()`` before persisting — this use case is idempotent on
    re-runs.  Price fetch failures are logged and that sample is skipped; the
    overall job continues.
    """

    def __init__(self, store: Any, price: ResolverPricePort) -> None:
        self._store = store
        self._price = price

    def resolve(self, as_of: date) -> list[GateSample]:
        """Return GateSamples for all STRONG snapshots that are ≥21d old as of *as_of*."""
        cutoff = as_of - timedelta(days=21)
        all_snapshots = self._store.load_all_snapshots()
        resolvable = [
            s
            for s in all_snapshots
            if s.convergence_tier == ConvergenceTier.STRONG and s.surfaced_at <= cutoff
        ]

        samples: list[GateSample] = []
        for snap in resolvable:
            t0 = snap.surfaced_at
            t21 = t0 + timedelta(days=21)
            t63 = t0 + timedelta(days=63)

            try:
                ticker_21 = _ret(self._price, snap.ticker, t0, t21)
                spy_21 = _ret(self._price, "SPY", t0, t21)
            except Exception as exc:
                logger.warning(
                    "price fetch failed for %s (%s): %s — skipping",
                    snap.ticker,
                    t0,
                    exc,
                )
                continue

            excess_63: float | None = None
            if as_of >= t63:
                try:
                    excess_63 = _ret(self._price, snap.ticker, t0, t63) - _ret(
                        self._price, "SPY", t0, t63
                    )
                except Exception as exc:
                    logger.warning(
                        "63d price fetch failed for %s (%s): %s",
                        snap.ticker,
                        t0,
                        exc,
                    )

            samples.append(
                GateSample(
                    ticker=snap.ticker,
                    snapshot_date=t0,
                    resolved_at=as_of,
                    excess_21d=ticker_21 - spy_21,
                    excess_63d=excess_63,
                    beat_spy_21d=ticker_21 > spy_21,
                )
            )

        return samples
