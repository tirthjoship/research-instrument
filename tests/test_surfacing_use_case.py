"""Tests for SurfacingUseCase — in-memory SQLite, FakeTickerResolver, no yfinance."""

from __future__ import annotations

import logging
import sqlite3
from datetime import date

import pytest

from adapters.data.corroboration_store import CorroborationStore
from application.surfacing_use_case import SurfacingUseCase
from domain.corroboration_models import (
    CandidateSnapshot,
    ConvergenceTier,
    DiscoveredEntry,
)


class FakeTickerResolver:
    def __init__(self, mapping: dict[str, tuple[str, str]] | None = None) -> None:
        self._mapping = mapping or {}

    def resolve(self, ticker: str) -> tuple[str, str]:
        return self._mapping.get(ticker, (f"{ticker} Corp", "Unknown"))


@pytest.fixture()
def store() -> CorroborationStore:
    conn = sqlite3.connect(":memory:")
    s = CorroborationStore(conn)
    s.init_schema()
    return s


@pytest.fixture()
def resolver() -> FakeTickerResolver:
    return FakeTickerResolver(
        {"NVDA": ("NVIDIA", "Technology"), "PANW": ("Palo Alto", "Technology")}
    )


def _run(
    store: CorroborationStore,
    resolver: FakeTickerResolver,
    candidates: list[CandidateSnapshot],
    spine: frozenset[str] | None = None,
    max_admissions: int = 10,
    as_of: date | None = None,
) -> list[DiscoveredEntry]:
    uc = SurfacingUseCase(
        store=store,
        spine_tickers=spine or frozenset(),
        resolver=resolver,
        max_admissions=max_admissions,
    )
    return uc.run(candidates=candidates, run_id=1, as_of=as_of or date(2026, 6, 22))


def test_admits_strong_all_verified(
    store: CorroborationStore, resolver: FakeTickerResolver
) -> None:
    candidates = [
        CandidateSnapshot("NVDA", ConvergenceTier.STRONG, "ALL_VERIFIED", 0.9)
    ]
    result = _run(store, resolver, candidates)
    assert len(result) == 1
    assert result[0].ticker == "NVDA"


def test_admits_moderate_all_verified(
    store: CorroborationStore, resolver: FakeTickerResolver
) -> None:
    candidates = [
        CandidateSnapshot("PANW", ConvergenceTier.MODERATE, "ALL_VERIFIED", 0.6)
    ]
    result = _run(store, resolver, candidates)
    assert len(result) == 1
    assert result[0].ticker == "PANW"


def test_rejects_weak(store: CorroborationStore, resolver: FakeTickerResolver) -> None:
    candidates = [CandidateSnapshot("WEAK", ConvergenceTier.WEAK, "ALL_VERIFIED", 0.2)]
    result = _run(store, resolver, candidates)
    assert result == []


def test_rejects_partial_verification(
    store: CorroborationStore, resolver: FakeTickerResolver
) -> None:
    candidates = [CandidateSnapshot("NVDA", ConvergenceTier.STRONG, "PARTIAL", 0.9)]
    result = _run(store, resolver, candidates)
    assert result == []


def test_dedup_spine(
    store: CorroborationStore,
    resolver: FakeTickerResolver,
    caplog: pytest.LogCaptureFixture,
    caplog_loguru: None,
) -> None:
    candidates = [
        CandidateSnapshot("NVDA", ConvergenceTier.STRONG, "ALL_VERIFIED", 0.9)
    ]
    with caplog.at_level(logging.DEBUG):
        result = _run(store, resolver, candidates, spine=frozenset({"NVDA"}))
    assert result == []
    assert any("spine" in r.message.lower() for r in caplog.records)


def test_cap_at_max_admissions(store: CorroborationStore) -> None:
    resolver = FakeTickerResolver()
    candidates = [
        CandidateSnapshot(
            f"T{i:02d}", ConvergenceTier.STRONG, "ALL_VERIFIED", 0.9 - i * 0.01
        )
        for i in range(15)
    ]
    result = _run(store, resolver, candidates, max_admissions=10)
    assert len(result) == 10
    assert result[0].ticker == "T00"


def test_ttl_expire(store: CorroborationStore, resolver: FakeTickerResolver) -> None:
    store.upsert_discovered(
        "OLD",
        "Old Corp",
        "Finance",
        date(2026, 6, 7),
        ConvergenceTier.MODERATE,
        run_id=0,
    )
    _run(store, resolver, [], as_of=date(2026, 6, 22))
    active = store.active_discovered(date(2026, 6, 22))
    assert not any(e.ticker == "OLD" for e in active)


def test_ttl_refresh(store: CorroborationStore, resolver: FakeTickerResolver) -> None:
    store.upsert_discovered(
        "NVDA",
        "NVIDIA",
        "Technology",
        date(2026, 6, 12),
        ConvergenceTier.MODERATE,
        run_id=0,
    )
    candidates = [
        CandidateSnapshot("NVDA", ConvergenceTier.STRONG, "ALL_VERIFIED", 0.9)
    ]
    _run(store, resolver, candidates, as_of=date(2026, 6, 22))
    active = store.active_discovered(date(2026, 6, 22))
    nvda = next(e for e in active if e.ticker == "NVDA")
    assert nvda.last_seen == date(2026, 6, 22)
    assert nvda.first_seen == date(2026, 6, 12)


def test_resolver_failure_still_admits(store: CorroborationStore) -> None:
    class _FailingResolver:
        def resolve(self, ticker: str) -> tuple[str, str]:
            raise RuntimeError("yfinance down")

    uc = SurfacingUseCase(
        store=store,
        spine_tickers=frozenset(),
        resolver=_FailingResolver(),  # type: ignore[arg-type]
        max_admissions=10,
    )
    candidates = [
        CandidateSnapshot("NVDA", ConvergenceTier.STRONG, "ALL_VERIFIED", 0.9)
    ]
    result = uc.run(candidates=candidates, run_id=1, as_of=date(2026, 6, 22))
    assert len(result) == 1
    assert result[0].ticker == "NVDA"
    assert result[0].company_name == ""
    assert result[0].sector == "unknown"
