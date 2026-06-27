"""Tests for CorroborationResolverUseCase — SP5 forward gate resolver."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from domain.corroboration_models import ConvergenceTier, Stance
from domain.screened_row import CorroborationSnapshot

# Constants — all dates fixed so tests never touch real time
SNAP_DATE = date(2025, 1, 1)
AS_OF = SNAP_DATE + timedelta(days=30)  # 30d later — resolvable for 21d, not 63d


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class FakePricePort:
    def __init__(self, prices: dict[tuple[str, date], float]) -> None:
        self._prices = prices

    def price_at(self, ticker: str, on: date) -> float:
        if (ticker, on) not in self._prices:
            raise ValueError(f"No price for {ticker} on {on}")
        return self._prices[(ticker, on)]


def _snap(
    ticker: str,
    surfaced_at: date,
    tier: ConvergenceTier = ConvergenceTier.STRONG,
    n_sources: int = 3,
) -> CorroborationSnapshot:
    return CorroborationSnapshot(
        ticker=ticker,
        convergence_tier=tier,
        n_sources=n_sources,
        surfaced_at=surfaced_at,
        net_stance=Stance.BULLISH,
    )


def _make_store(snaps: list[CorroborationSnapshot]) -> MagicMock:
    store = MagicMock()
    store.load_all_snapshots.return_value = snaps
    return store


def _base_prices(ticker: str = "AAPL") -> dict[tuple[str, date], float]:
    """Prices for ticker and SPY at t0 and t21.

    ticker: +2% over 21d, SPY: +0.5% over 21d → excess ≈ +1.5%
    """
    t0 = SNAP_DATE
    t21 = SNAP_DATE + timedelta(days=21)
    return {
        (ticker, t0): 100.0,
        (ticker, t21): 102.0,
        ("SPY", t0): 400.0,
        ("SPY", t21): 402.0,  # +0.5%
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_resolve_returns_sample_for_strong_ticker() -> None:
    from application.corroboration_resolver_use_case import CorroborationResolverUseCase

    store = _make_store([_snap("AAPL", SNAP_DATE)])
    uc = CorroborationResolverUseCase(store, FakePricePort(_base_prices()))
    samples = uc.resolve(AS_OF)

    assert len(samples) == 1
    s = samples[0]
    assert s.ticker == "AAPL"
    assert s.snapshot_date == SNAP_DATE
    # ticker 21d return: (102-100)/100 = 0.02; SPY: (402-400)/400 = 0.005; excess = 0.015
    assert s.excess_21d == pytest.approx(0.02 - 0.005, abs=1e-9)
    assert s.beat_spy_21d is True


def test_resolve_excludes_non_strong_tier() -> None:
    from application.corroboration_resolver_use_case import CorroborationResolverUseCase

    snaps = [
        _snap("AAPL", SNAP_DATE, ConvergenceTier.STRONG),
        _snap("MSFT", SNAP_DATE, ConvergenceTier.MODERATE),
        _snap("TSLA", SNAP_DATE, ConvergenceTier.WEAK),
    ]
    prices = _base_prices("AAPL")
    store = _make_store(snaps)
    uc = CorroborationResolverUseCase(store, FakePricePort(prices))
    samples = uc.resolve(AS_OF)

    assert len(samples) == 1
    assert samples[0].ticker == "AAPL"


def test_resolve_excludes_snapshots_too_recent() -> None:
    from application.corroboration_resolver_use_case import CorroborationResolverUseCase

    # Surfaced only 10 days before AS_OF — not yet resolvable (need ≥21d)
    recent = _snap("AAPL", AS_OF - timedelta(days=10))
    store = _make_store([recent])
    uc = CorroborationResolverUseCase(store, FakePricePort({}))
    samples = uc.resolve(AS_OF)

    assert samples == []


def test_resolve_skips_sample_on_price_fetch_failure() -> None:
    from application.corroboration_resolver_use_case import CorroborationResolverUseCase

    # Empty price dict — all fetches will raise ValueError
    store = _make_store([_snap("AAPL", SNAP_DATE)])
    uc = CorroborationResolverUseCase(store, FakePricePort({}))
    # Must not raise — failure is logged and sample skipped
    samples = uc.resolve(AS_OF)

    assert samples == []


def test_resolve_computes_excess_63d_when_available() -> None:
    from application.corroboration_resolver_use_case import CorroborationResolverUseCase

    t0 = SNAP_DATE
    t21 = t0 + timedelta(days=21)
    t63 = t0 + timedelta(days=63)
    as_of_64 = t0 + timedelta(days=64)  # past t63

    prices: dict[tuple[str, date], float] = {
        ("AAPL", t0): 100.0,
        ("AAPL", t21): 102.0,
        ("AAPL", t63): 108.0,  # +8% at 63d
        ("SPY", t0): 400.0,
        ("SPY", t21): 402.0,
        ("SPY", t63): 404.0,  # +1% at 63d
    }

    store = _make_store([_snap("AAPL", t0)])
    uc = CorroborationResolverUseCase(store, FakePricePort(prices))
    samples = uc.resolve(as_of_64)

    assert len(samples) == 1
    s = samples[0]
    assert s.excess_63d is not None
    # AAPL 63d: (108-100)/100 = 0.08; SPY: (404-400)/400 = 0.01; excess = 0.07
    assert s.excess_63d == pytest.approx(0.08 - 0.01, abs=1e-9)


def test_resolve_excess_63d_none_when_not_yet_available() -> None:
    from application.corroboration_resolver_use_case import CorroborationResolverUseCase

    # AS_OF is only 30d after snap — not yet past 63d window
    store = _make_store([_snap("AAPL", SNAP_DATE)])
    uc = CorroborationResolverUseCase(store, FakePricePort(_base_prices()))
    samples = uc.resolve(AS_OF)

    assert len(samples) == 1
    assert samples[0].excess_63d is None


def test_resolve_beat_spy_false_when_ticker_underperforms() -> None:
    from application.corroboration_resolver_use_case import CorroborationResolverUseCase

    t0 = SNAP_DATE
    t21 = t0 + timedelta(days=21)
    # ticker flat, SPY up → ticker underperforms
    prices: dict[tuple[str, date], float] = {
        ("AAPL", t0): 100.0,
        ("AAPL", t21): 100.0,  # 0% return
        ("SPY", t0): 400.0,
        ("SPY", t21): 410.0,  # +2.5% return
    }

    store = _make_store([_snap("AAPL", t0)])
    uc = CorroborationResolverUseCase(store, FakePricePort(prices))
    samples = uc.resolve(AS_OF)

    assert len(samples) == 1
    s = samples[0]
    assert s.beat_spy_21d is False
    assert s.excess_21d < 0
