from dataclasses import FrozenInstanceError
from datetime import date

import pytest

from domain.corroboration_models import (
    CandidateSnapshot,
    ConvergenceTier,
    DiscoveredEntry,
)
from domain.ports import TickerResolverPort


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
        first_seen=date(2026, 6, 15),
        last_seen=date(2026, 6, 22),
        convergence=ConvergenceTier.STRONG,
    )
    assert entry.ticker == "NVDA"
    assert entry.sector == "Technology"
    assert entry.convergence == ConvergenceTier.STRONG
    assert entry.first_seen == date(2026, 6, 15)
    assert entry.last_seen == date(2026, 6, 22)


def test_candidate_snapshot_is_frozen() -> None:
    snap = CandidateSnapshot(
        ticker="NVDA",
        convergence=ConvergenceTier.STRONG,
        verification="ALL_VERIFIED",
        mean_convergence=0.85,
    )
    with pytest.raises(FrozenInstanceError):
        snap.ticker = "MSFT"  # type: ignore[misc]


def test_discovered_entry_is_frozen() -> None:
    entry = DiscoveredEntry(
        ticker="NVDA",
        company_name="NVIDIA Corporation",
        sector="Technology",
        first_seen=date(2026, 6, 15),
        last_seen=date(2026, 6, 22),
        convergence=ConvergenceTier.STRONG,
    )
    with pytest.raises(FrozenInstanceError):
        entry.ticker = "MSFT"  # type: ignore[misc]


def test_ticker_resolver_port_has_resolve_method() -> None:
    assert hasattr(TickerResolverPort, "resolve")


class _FakeResolver:
    def resolve(self, ticker: str) -> tuple[str, str]:
        return ("Fake Corp", "Technology")


def test_fake_resolver_satisfies_port() -> None:
    resolver: TickerResolverPort = _FakeResolver()  # type: ignore[assignment]
    name, sector = resolver.resolve("NVDA")
    assert name == "Fake Corp"
    assert sector == "Technology"
