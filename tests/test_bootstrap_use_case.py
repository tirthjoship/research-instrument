"""Tests for HistoricalBootstrapUseCase — TDD phase."""

from __future__ import annotations

from datetime import datetime

from application.bootstrap_use_case import HistoricalBootstrapUseCase
from domain.models import Signal
from domain.outcome import TradeOutcome


class FakeMarketData:
    def get_signals(self, symbol, prediction_time, start_date=None, end_date=None):
        return [
            Signal(
                symbol=symbol,
                timestamp=prediction_time,
                price=100.0 + hash(symbol) % 50,
                volume=1_000_000.0,
                open_=99.0,
                high=105.0,
                low=98.0,
            )
        ]


class FakeBootstrapStore:
    def __init__(self):
        self.outcomes: list[TradeOutcome] = []

    def save_trade_outcome(self, outcome: TradeOutcome) -> None:
        self.outcomes.append(outcome)

    def get_trade_outcomes(self, ticker=None):
        return self.outcomes


class FakeEmptyMarketData:
    """Returns no signals for any ticker."""

    def get_signals(self, symbol, prediction_time, start_date=None, end_date=None):
        return []


def test_generates_simulated_outcomes():
    """2 tickers × 2 months should produce outcomes."""
    tickers = ["AAPL", "MSFT"]
    store = FakeBootstrapStore()
    uc = HistoricalBootstrapUseCase(FakeMarketData(), store, tickers)

    start = datetime(2024, 1, 1)
    end = datetime(2024, 3, 1)
    outcomes = uc.run(start, end, horizon_days=30, step_days=30)

    # At least 1 outcome per ticker per window
    assert len(outcomes) > 0
    assert all(isinstance(o, TradeOutcome) for o in outcomes)
    # Outcomes should be persisted in store
    assert len(store.outcomes) == len(outcomes)


def test_outcome_fields_are_correct():
    """TradeOutcome fields should be populated correctly."""
    store = FakeBootstrapStore()
    uc = HistoricalBootstrapUseCase(FakeMarketData(), store, ["AAPL"])

    start = datetime(2024, 1, 1)
    end = datetime(2024, 2, 15)
    outcomes = uc.run(start, end, horizon_days=30, step_days=30)

    assert len(outcomes) >= 1
    o = outcomes[0]
    assert o.ticker == "AAPL"
    assert o.buy_price > 0
    assert o.sell_price > 0
    assert o.quantity == 1
    assert o.holding_days == 30
    assert o.signals_at_entry == ["technical", "fundamental"]
    # return_pct = (sell - buy) / buy * 100
    expected_pct = (o.sell_price - o.buy_price) / o.buy_price * 100
    assert abs(o.return_pct - expected_pct) < 1e-6
    assert abs(o.return_dollar - (o.sell_price - o.buy_price)) < 1e-6


def test_empty_tickers_returns_empty():
    """No tickers → empty list, no crash."""
    store = FakeBootstrapStore()
    uc = HistoricalBootstrapUseCase(FakeMarketData(), store, [])

    outcomes = uc.run(datetime(2024, 1, 1), datetime(2024, 3, 1))
    assert outcomes == []


def test_missing_data_skipped_gracefully():
    """Tickers with no signals should be silently skipped."""
    store = FakeBootstrapStore()
    uc = HistoricalBootstrapUseCase(FakeEmptyMarketData(), store, ["AAPL", "MSFT"])

    outcomes = uc.run(datetime(2024, 1, 1), datetime(2024, 3, 1))
    assert outcomes == []
    assert store.outcomes == []


def test_single_step_single_ticker():
    """One window, one ticker → exactly one outcome."""
    store = FakeBootstrapStore()
    uc = HistoricalBootstrapUseCase(FakeMarketData(), store, ["TSLA"])

    # window: Jan 1 → Feb 1 (step=31 days > range=31 → exactly one window)
    start = datetime(2024, 1, 1)
    end = datetime(2024, 1, 31)
    outcomes = uc.run(start, end, horizon_days=30, step_days=30)

    assert len(outcomes) == 1
    assert outcomes[0].ticker == "TSLA"
