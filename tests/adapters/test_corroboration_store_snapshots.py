# tests/adapters/test_corroboration_store_snapshots.py
from __future__ import annotations

import sqlite3
from datetime import date

from adapters.data.corroboration_store import CorroborationStore
from domain.corroboration_models import ConvergenceTier, HarvestedClaim, Stance


def _make_store() -> CorroborationStore:
    conn = sqlite3.connect(":memory:")
    store = CorroborationStore(conn)
    store.init_schema()
    return store


def _bullish(ticker: str) -> HarvestedClaim:
    return HarvestedClaim(
        source_name="Kiplinger",
        ticker=ticker,
        stance=Stance.BULLISH,
        thesis_summary="Buy signal",
        url="https://example.com",
        published_at=date(2026, 6, 20),
        verified=True,
        reliability_weight=1.0,
    )


def _bearish(ticker: str) -> HarvestedClaim:
    return HarvestedClaim(
        source_name="Barrons",
        ticker=ticker,
        stance=Stance.BEARISH,
        thesis_summary="Sell signal",
        url="https://example.com",
        published_at=date(2026, 6, 20),
        verified=True,
        reliability_weight=1.0,
    )


def test_get_snapshots_returns_correct_tiers() -> None:
    store = _make_store()
    as_of = date(2026, 6, 21)
    claims = [
        _bullish("NVDA"),
        _bullish("NVDA"),
        _bullish("NVDA"),
        _bullish("MSFT"),
        _bullish("MSFT"),
        _bullish("AAPL"),
        _bullish("IBM"),
        _bearish("IBM"),
    ]
    store.save_run(as_of, claims)
    snaps = store.get_snapshots(date(2026, 6, 22), window_days=7)
    by_ticker = {s.ticker: s for s in snaps}
    assert by_ticker["NVDA"].convergence_tier == ConvergenceTier.STRONG
    assert by_ticker["NVDA"].n_sources == 3
    assert by_ticker["MSFT"].convergence_tier == ConvergenceTier.MODERATE
    assert by_ticker["AAPL"].convergence_tier == ConvergenceTier.WEAK
    assert by_ticker["IBM"].convergence_tier == ConvergenceTier.CONFLICTED


def test_get_snapshots_outside_window_excluded() -> None:
    store = _make_store()
    store.save_run(date(2026, 6, 1), [_bullish("NVDA")])
    snaps = store.get_snapshots(date(2026, 6, 22), window_days=7)
    assert snaps == []


def test_get_snapshots_no_runs_returns_empty() -> None:
    store = _make_store()
    snaps = store.get_snapshots(date(2026, 6, 22), window_days=7)
    assert snaps == []


def test_get_snapshots_uses_most_recent_run_in_window() -> None:
    store = _make_store()
    store.save_run(date(2026, 6, 18), [_bullish("NVDA")])
    store.save_run(
        date(2026, 6, 21),
        [_bullish("NVDA"), _bullish("NVDA"), _bullish("NVDA")],
    )
    snaps = store.get_snapshots(date(2026, 6, 22), window_days=7)
    by_ticker = {s.ticker: s for s in snaps}
    assert by_ticker["NVDA"].convergence_tier == ConvergenceTier.STRONG
