"""SP2: Candidate Surfacing — admits corroborated tickers into discovered universe overlay."""

from __future__ import annotations

from datetime import date

from loguru import logger

from adapters.data.corroboration_store import CorroborationStore
from domain.corroboration_models import (
    CandidateSnapshot,
    ConvergenceTier,
    DiscoveredEntry,
)
from domain.ports import TickerResolverPort

_ADMIT_TIERS = {ConvergenceTier.STRONG, ConvergenceTier.MODERATE}
_ADMIT_VERIFICATION = "ALL_VERIFIED"


class SurfacingUseCase:
    """Admit corroboration candidates into the discovered-ticker universe overlay."""

    def __init__(
        self,
        store: CorroborationStore,
        spine_tickers: frozenset[str],
        resolver: TickerResolverPort,
        max_admissions: int = 10,
    ) -> None:
        self._store = store
        self._spine = spine_tickers
        self._resolver = resolver
        self._max = max_admissions

    def run(
        self,
        candidates: list[CandidateSnapshot],
        run_id: int,
        as_of: date,
    ) -> list[DiscoveredEntry]:
        """Apply admission logic and update the discovered_tickers table.

        Returns the full active discovered universe after this run.
        """
        eligible = sorted(
            (
                c
                for c in candidates
                if c.convergence in _ADMIT_TIERS
                and c.verification == _ADMIT_VERIFICATION
            ),
            key=lambda c: c.mean_convergence,
            reverse=True,
        )

        admitted = 0
        for snap in eligible:
            if admitted >= self._max:
                break
            if snap.ticker in self._spine:
                logger.debug(
                    "[surfacing] %s already in spine, skipping corroboration overlay",
                    snap.ticker,
                )
                continue
            try:
                company_name, sector = self._resolver.resolve(snap.ticker)
            except Exception:
                company_name, sector = "", "unknown"

            self._store.upsert_discovered(
                ticker=snap.ticker,
                company_name=company_name,
                sector=sector,
                as_of=as_of,
                convergence=snap.convergence,
                run_id=run_id,
            )
            admitted += 1
            logger.info(
                "[surfacing] admitted %s (%s) convergence=%s",
                snap.ticker,
                company_name,
                snap.convergence.value,
            )

        expired = self._store.expire_discovered(as_of)
        if expired:
            logger.info(
                "[surfacing] expired %d stale ticker(s) from discovered universe",
                expired,
            )

        return self._store.active_discovered(as_of)
