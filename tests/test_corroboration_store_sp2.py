"""Tests for CorroborationStore SP2 additions (in-memory SQLite)."""

from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from adapters.data.corroboration_store import CorroborationStore
from domain.corroboration_models import CandidateSnapshot, ConvergenceTier


@pytest.fixture()
def store() -> CorroborationStore:
    conn = sqlite3.connect(":memory:")
    s = CorroborationStore(conn)
    s.init_schema()
    return s


# ---- candidates_snapshot ----


def test_save_and_load_candidates(store: CorroborationStore) -> None:
    run_id = store.save_run(date(2026, 6, 22), [])
    snaps = [
        CandidateSnapshot("NVDA", ConvergenceTier.STRONG, "ALL_VERIFIED", 0.9),
        CandidateSnapshot("PANW", ConvergenceTier.MODERATE, "ALL_VERIFIED", 0.6),
    ]
    store.save_candidates(run_id, snaps)
    loaded = store.load_candidates(run_id)
    assert len(loaded) == 2
    assert loaded[0].ticker == "NVDA"
    assert loaded[0].convergence == ConvergenceTier.STRONG
    assert loaded[1].ticker == "PANW"
    assert loaded[1].mean_convergence == pytest.approx(0.6)


def test_load_candidates_empty_run(store: CorroborationStore) -> None:
    run_id = store.save_run(date(2026, 6, 22), [])
    assert store.load_candidates(run_id) == []


def test_load_candidates_unknown_run(store: CorroborationStore) -> None:
    assert store.load_candidates(9999) == []


# ---- discovered_tickers ----


def test_upsert_and_active_discovered(store: CorroborationStore) -> None:
    as_of = date(2026, 6, 22)
    store.upsert_discovered(
        "NVDA", "NVIDIA", "Technology", as_of, ConvergenceTier.STRONG, run_id=1
    )
    active = store.active_discovered(as_of)
    assert len(active) == 1
    e = active[0]
    assert e.ticker == "NVDA"
    assert e.company_name == "NVIDIA"
    assert e.sector == "Technology"
    assert e.convergence == ConvergenceTier.STRONG
    assert e.first_seen == as_of
    assert e.last_seen == as_of


def test_upsert_updates_last_seen(store: CorroborationStore) -> None:
    store.upsert_discovered(
        "NVDA",
        "NVIDIA",
        "Technology",
        date(2026, 6, 8),
        ConvergenceTier.MODERATE,
        run_id=1,
    )
    store.upsert_discovered(
        "NVDA",
        "NVIDIA",
        "Technology",
        date(2026, 6, 22),
        ConvergenceTier.STRONG,
        run_id=2,
    )
    active = store.active_discovered(date(2026, 6, 22))
    assert len(active) == 1
    assert active[0].first_seen == date(2026, 6, 8)  # preserved
    assert active[0].last_seen == date(2026, 6, 22)  # updated
    assert active[0].convergence == ConvergenceTier.STRONG  # updated


def test_active_discovered_excludes_stale(store: CorroborationStore) -> None:
    store.upsert_discovered(
        "STALE",
        "Stale Corp",
        "Finance",
        date(2026, 6, 1),
        ConvergenceTier.MODERATE,
        run_id=1,
    )
    active = store.active_discovered(date(2026, 6, 22), dry_weeks=2)
    assert not any(e.ticker == "STALE" for e in active)


def test_expire_discovered_removes_stale(store: CorroborationStore) -> None:
    store.upsert_discovered(
        "OLD",
        "Old Corp",
        "Energy",
        date(2026, 6, 1),
        ConvergenceTier.MODERATE,
        run_id=1,
    )
    store.upsert_discovered(
        "NEW", "New Corp", "Tech", date(2026, 6, 22), ConvergenceTier.STRONG, run_id=2
    )
    removed = store.expire_discovered(date(2026, 6, 22), dry_weeks=2)
    assert removed == 1
    active = store.active_discovered(date(2026, 6, 22))
    assert len(active) == 1
    assert active[0].ticker == "NEW"


def test_latest_run_id_returns_none_when_empty(store: CorroborationStore) -> None:
    assert store.latest_run_id() is None


def test_latest_run_id_returns_most_recent(store: CorroborationStore) -> None:
    r1 = store.save_run(date(2026, 6, 15), [])
    r2 = store.save_run(date(2026, 6, 22), [])
    assert store.latest_run_id() == r2
    assert r2 > r1


def test_yfinance_resolver_returns_name_and_sector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from adapters.data.yfinance_resolver import YFinanceResolver

    class _FakeTicker:
        info = {"longName": "NVIDIA Corporation", "sector": "Technology"}

    monkeypatch.setattr("yfinance.Ticker", lambda _: _FakeTicker())
    resolver = YFinanceResolver()
    name, sector = resolver.resolve("NVDA")
    assert name == "NVIDIA Corporation"
    assert sector == "Technology"


def test_yfinance_resolver_returns_empty_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from adapters.data.yfinance_resolver import YFinanceResolver

    def _raise(_: str) -> None:
        raise RuntimeError("rate limit")

    monkeypatch.setattr("yfinance.Ticker", _raise)
    resolver = YFinanceResolver()
    name, sector = resolver.resolve("FAKE")
    assert name == ""
    assert sector == "unknown"
