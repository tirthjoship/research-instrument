"""Orchestrate harvest → verify → corroborate → persist (spec §4). RESEARCH_ONLY."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from typing import Callable

from domain.corroboration_models import (
    CorroboratedCandidate,
    HarvestedClaim,
    OurReadout,
)
from domain.corroboration_service import CorroborationService
from domain.ports import CitationVerifierPort, RecommendationHarvestPort


@dataclass(frozen=True)
class CorroborationResult:
    run_id: int
    candidates: list[CorroboratedCandidate]


class CorroborationUseCase:
    def __init__(
        self,
        harvester: RecommendationHarvestPort,
        verifier: CitationVerifierPort,
        readout_fn: Callable[[str, date], OurReadout],
        held_tickers: set[str],
        store: object,
        service: CorroborationService | None = None,
    ) -> None:
        self._harvester = harvester
        self._verifier = verifier
        self._readout_fn = readout_fn
        self._held = held_tickers
        self._store = store
        self._svc = service or CorroborationService()

    def execute(self, as_of: date) -> CorroborationResult:
        # Point-in-time guard (spec §9): drop any claim published after as_of.
        claims: list[HarvestedClaim] = [
            c for c in self._harvester.harvest(as_of) if c.published_at <= as_of
        ]
        verified: list[HarvestedClaim] = [
            replace(c, verified=self._verifier.verify(c.url, c.ticker)) for c in claims
        ]
        run_id: int = self._store.save_run(as_of, verified)  # type: ignore[attr-defined]
        by_ticker: dict[str, list[HarvestedClaim]] = {}
        for c in verified:
            by_ticker.setdefault(c.ticker, []).append(c)
        cands: list[CorroboratedCandidate] = [
            self._svc.corroborate(
                t,
                as_of,
                cs,
                self._readout_fn(t, as_of),
                held=(t in self._held),
            )
            for t, cs in by_ticker.items()
        ]
        return CorroborationResult(run_id=run_id, candidates=cands)
