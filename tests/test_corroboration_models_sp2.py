from datetime import date

from domain.corroboration_models import (
    CandidateSnapshot,
    ConvergenceTier,
    DiscoveredEntry,
)


def test_candidate_snapshot_fields() -> None:
    snap = CandidateSnapshot(
        ticker="NVDA",
        convergence=ConvergenceTier.STRONG,
        verification="ALL_VERIFIED",
        mean_convergence=0.85,
    )
    assert snap.ticker == "NVDA"
    assert snap.convergence == ConvergenceTier.STRONG
    assert snap.verification == "ALL_VERIFIED"
    assert snap.mean_convergence == 0.85


def test_discovered_entry_fields() -> None:
    entry = DiscoveredEntry(
        ticker="NVDA",
        company_name="NVIDIA Corporation",
        sector="Technology",
        first_seen=date(2026, 6, 22),
        last_seen=date(2026, 6, 22),
        convergence=ConvergenceTier.STRONG,
    )
    assert entry.ticker == "NVDA"
    assert entry.sector == "Technology"
    assert entry.convergence == ConvergenceTier.STRONG
