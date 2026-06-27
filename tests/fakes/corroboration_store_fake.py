"""Fake CorroborationStore for testing — never hits SQLite."""

from __future__ import annotations

from datetime import date

from domain.corroboration_models import (
    CandidateSnapshot,
    ConvergenceTier,
    HarvestedClaim,
    Stance,
)


class FakeCorroborationStore:
    def __init__(
        self,
        run_id: int | None = 1,
        claims: list[HarvestedClaim] | None = None,
        candidates: list[CandidateSnapshot] | None = None,
    ) -> None:
        self._run_id = run_id
        self._claims: list[HarvestedClaim] = claims or []
        self._candidates: list[CandidateSnapshot] = candidates or []

    def latest_run_id(self) -> int | None:
        return self._run_id

    def load_run(self, run_id: int) -> list[HarvestedClaim]:
        return self._claims

    def load_candidates(self, run_id: int) -> list[CandidateSnapshot]:
        return self._candidates


FAKE_CLAIM_BULLISH = HarvestedClaim(
    source_name="Goldman Sachs",
    ticker="AAPL",
    stance=Stance.BULLISH,
    thesis_summary="Strong iPhone cycle and services momentum",
    url="https://example.com/gs-aapl-2026",
    published_at=date(2026, 6, 20),
    verified=True,
    reliability_weight=0.85,
)

FAKE_CLAIM_BEARISH = HarvestedClaim(
    source_name="Barclays",
    ticker="AAPL",
    stance=Stance.BEARISH,
    thesis_summary="China headwinds may weigh on near-term results",
    url="https://example.com/barcl-aapl-2026",
    published_at=date(2026, 6, 19),
    verified=True,
    reliability_weight=0.65,
)

FAKE_CLAIM_WEAK = HarvestedClaim(
    source_name="Reddit r/investing",
    ticker="AAPL",
    stance=Stance.BULLISH,
    thesis_summary="People love the Vision Pro",
    url="https://reddit.com/r/investing/aapl",
    published_at=date(2026, 6, 18),
    verified=False,
    reliability_weight=0.25,
)

FAKE_SNAPSHOT = CandidateSnapshot(
    ticker="AAPL",
    convergence=ConvergenceTier.MODERATE,
    verification="PARTIAL",
    mean_convergence=0.62,
)
