"""Tests for the screen PricePort adapter wired in application.cli.

Regression guard for a silent field-name bug: the adapter read ``s.close`` but
``domain.models.Signal`` exposes ``s.price``. The resulting ``AttributeError``
was swallowed by a bare ``except``, so ``trend_health`` returned ``0.0`` and
``monthly_closes`` returned ``[]`` for EVERY ticker — making the whole screener
silently dead (nothing ever passed ``eligible()``).

These tests fake only the unavoidable yfinance boundary (``market_data``) and
exercise the real adapter wiring via ``_build_evidence_screen``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from application.cli import _build_evidence_screen
from domain.models import Signal


class _FakeMarketData:
    """Minimal stand-in for the yfinance-backed market_data dependency."""

    def __init__(self, signals: list[Signal]) -> None:
        self._signals = signals

    def get_signals(self, ticker, now, start_date=None):  # noqa: ANN001
        return self._signals

    def get_analyst_data(self, ticker, now):  # noqa: ANN001
        return None

    def get_ticker_info(self, ticker):  # noqa: ANN001
        return {}


def _rising_signals(n: int = 260) -> list[Signal]:
    """n daily signals trending steadily upward (last price well above its SMA)."""
    base = datetime(2024, 6, 1, tzinfo=timezone.utc)
    out: list[Signal] = []
    for i in range(n):
        price = 100.0 + i  # strictly rising
        out.append(
            Signal(
                symbol="X",
                timestamp=base + timedelta(days=i),
                price=price,
                volume=1_000.0,
                open_=price,
                high=price * 1.01,
                low=price * 0.99,
            )
        )
    return out


def _adapter(signals: list[Signal]):  # noqa: ANN001
    deps = {"market_data": _FakeMarketData(signals)}
    return _build_evidence_screen(deps)._price


def test_monthly_closes_returns_prices_not_empty() -> None:
    adapter = _adapter(_rising_signals())
    closes = adapter.monthly_closes("X")
    assert closes, "monthly_closes must read s.price, not silently return []"
    assert closes == sorted(closes), "monthly closes of a rising series should rise"
    assert closes[-1] > closes[0]


def test_trend_health_positive_for_uptrend() -> None:
    adapter = _adapter(_rising_signals())
    th = adapter.trend_health("X")
    assert th > 0.0, "uptrend (last price above SMA) must yield trend_health > 0"


def test_trend_health_zero_when_history_too_short() -> None:
    # Genuine data-absence (fewer than 22 signals) is still handled gracefully.
    adapter = _adapter(_rising_signals(n=10))
    assert adapter.trend_health("X") == 0.0


class _RaisingMarketData(_FakeMarketData):
    def get_signals(self, ticker, now, start_date=None):  # noqa: ANN001
        raise ConnectionError("simulated yfinance outage")


def test_fetch_failure_degrades_gracefully() -> None:
    # The fetch (network) is still tolerated to fail per-ticker; a transform
    # bug, by contrast, now surfaces because it runs outside the try.
    adapter = _build_evidence_screen({"market_data": _RaisingMarketData([])})._price
    assert adapter.monthly_closes("X") == []
    assert adapter.trend_health("X") == 0.0
