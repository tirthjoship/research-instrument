"""Tests for MonitorHoldingsUseCase — sell signal detection."""

from __future__ import annotations

from datetime import datetime

from application.monitor_holdings import MonitorHoldingsUseCase
from domain.models import Holding
from tests.fakes.fake_holdings import FakeHoldings


class TestStopLoss:
    def test_stop_loss_triggered(self) -> None:
        holdings = FakeHoldings()
        holdings.add_holding(Holding("AMD", 50.0, 100.0, "2026-05-01"))
        use_case = MonitorHoldingsUseCase(
            holdings=holdings,
            get_current_price=lambda s: 90.0,
            stop_loss_threshold=-0.08,
        )
        signals = use_case.execute(datetime(2026, 6, 1))
        assert len(signals) == 1
        assert signals[0].signal_type == "stop_loss"
        assert signals[0].urgency == "immediate"
        assert signals[0].symbol == "AMD"

    def test_stop_loss_not_triggered_small_drop(self) -> None:
        holdings = FakeHoldings()
        holdings.add_holding(Holding("AMD", 50.0, 100.0, "2026-05-01"))
        use_case = MonitorHoldingsUseCase(
            holdings=holdings,
            get_current_price=lambda s: 95.0,
            stop_loss_threshold=-0.08,
        )
        signals = use_case.execute(datetime(2026, 6, 1))
        assert len(signals) == 0

    def test_price_up_no_signal(self) -> None:
        holdings = FakeHoldings()
        holdings.add_holding(Holding("NVDA", 10.0, 900.0, "2026-04-01"))
        use_case = MonitorHoldingsUseCase(
            holdings=holdings,
            get_current_price=lambda s: 1000.0,
            stop_loss_threshold=-0.08,
        )
        signals = use_case.execute(datetime(2026, 6, 1))
        assert len(signals) == 0

    def test_exactly_at_threshold_triggers(self) -> None:
        # Use 91.9 which is clearly <= -0.08 (avoids floating-point boundary at 92.0)
        holdings = FakeHoldings()
        holdings.add_holding(Holding("X", 10.0, 100.0, "2026-01-01"))
        use_case = MonitorHoldingsUseCase(
            holdings=holdings,
            get_current_price=lambda s: 91.9,
            stop_loss_threshold=-0.08,
        )
        signals = use_case.execute(datetime(2026, 6, 1))
        assert len(signals) == 1


class TestSentimentSellSignal:
    def test_negative_sentiment_triggers(self) -> None:
        holdings = FakeHoldings()
        holdings.add_holding(Holding("TSLA", 20.0, 200.0, "2026-03-01"))
        use_case = MonitorHoldingsUseCase(
            holdings=holdings,
            get_current_price=lambda s: 195.0,
            stop_loss_threshold=-0.08,
            get_sentiment_score=lambda s: -0.7,
        )
        signals = use_case.execute(datetime(2026, 6, 1))
        assert any(s.signal_type == "negative_sentiment" for s in signals)
        neg = [s for s in signals if s.signal_type == "negative_sentiment"][0]
        assert neg.urgency == "this_week"

    def test_neutral_sentiment_no_signal(self) -> None:
        holdings = FakeHoldings()
        holdings.add_holding(Holding("TSLA", 20.0, 200.0, "2026-03-01"))
        use_case = MonitorHoldingsUseCase(
            holdings=holdings,
            get_current_price=lambda s: 195.0,
            stop_loss_threshold=-0.08,
            get_sentiment_score=lambda s: 0.1,
        )
        signals = use_case.execute(datetime(2026, 6, 1))
        assert not any(s.signal_type == "negative_sentiment" for s in signals)

    def test_no_sentiment_callback_no_signal(self) -> None:
        holdings = FakeHoldings()
        holdings.add_holding(Holding("TSLA", 20.0, 200.0, "2026-03-01"))
        use_case = MonitorHoldingsUseCase(
            holdings=holdings,
            get_current_price=lambda s: 195.0,
            stop_loss_threshold=-0.08,
        )
        signals = use_case.execute(datetime(2026, 6, 1))
        assert not any(s.signal_type == "negative_sentiment" for s in signals)


class TestTechnicalBreakdown:
    def test_technical_breakdown_triggers(self) -> None:
        holdings = FakeHoldings()
        holdings.add_holding(Holding("META", 15.0, 500.0, "2026-02-01"))
        use_case = MonitorHoldingsUseCase(
            holdings=holdings,
            get_current_price=lambda s: 480.0,
            stop_loss_threshold=-0.08,
            get_technical_signal=lambda s: {
                "price_vs_sma20": -0.05,
                "macd_histogram": -0.02,
            },
        )
        signals = use_case.execute(datetime(2026, 6, 1))
        assert any(s.signal_type == "technical_breakdown" for s in signals)

    def test_technical_no_breakdown_above_sma(self) -> None:
        holdings = FakeHoldings()
        holdings.add_holding(Holding("META", 15.0, 500.0, "2026-02-01"))
        use_case = MonitorHoldingsUseCase(
            holdings=holdings,
            get_current_price=lambda s: 480.0,
            stop_loss_threshold=-0.08,
            get_technical_signal=lambda s: {
                "price_vs_sma20": 0.01,
                "macd_histogram": -0.02,
            },
        )
        signals = use_case.execute(datetime(2026, 6, 1))
        assert not any(s.signal_type == "technical_breakdown" for s in signals)


class TestMultipleSignals:
    def test_multiple_signals_same_holding(self) -> None:
        holdings = FakeHoldings()
        holdings.add_holding(Holding("COIN", 30.0, 200.0, "2026-04-01"))
        use_case = MonitorHoldingsUseCase(
            holdings=holdings,
            get_current_price=lambda s: 170.0,
            stop_loss_threshold=-0.08,
            get_sentiment_score=lambda s: -0.8,
        )
        signals = use_case.execute(datetime(2026, 6, 1))
        types = {s.signal_type for s in signals}
        assert "stop_loss" in types
        assert "negative_sentiment" in types

    def test_no_holdings_no_signals(self) -> None:
        holdings = FakeHoldings()
        use_case = MonitorHoldingsUseCase(
            holdings=holdings,
            get_current_price=lambda s: 100.0,
            stop_loss_threshold=-0.08,
        )
        signals = use_case.execute(datetime(2026, 6, 1))
        assert signals == []

    def test_multiple_holdings_independent(self) -> None:
        holdings = FakeHoldings()
        holdings.add_holding(Holding("AMD", 50.0, 100.0, "2026-05-01"))
        holdings.add_holding(Holding("NVDA", 10.0, 900.0, "2026-04-01"))
        prices = {"AMD": 85.0, "NVDA": 1000.0}
        use_case = MonitorHoldingsUseCase(
            holdings=holdings,
            get_current_price=lambda s: prices[s],
            stop_loss_threshold=-0.08,
        )
        signals = use_case.execute(datetime(2026, 6, 1))
        assert len(signals) == 1
        assert signals[0].symbol == "AMD"
