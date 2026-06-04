"""Tests for outcome tracking domain models (TDD — written before implementation)."""

from __future__ import annotations

import pytest

from domain.outcome import SignalPerformance, TrackedTrade, TradeAction, TradeOutcome

# ---------------------------------------------------------------------------
# TrackedTrade
# ---------------------------------------------------------------------------


class TestTrackedTrade:
    def test_buy_creation_and_total_value(self) -> None:
        trade = TrackedTrade(
            trade_id="T001",
            ticker="AAPL",
            action=TradeAction.BUY,
            price=150.0,
            quantity=10,
            trade_date="2026-01-01",
            conviction_at_trade=8.5,
            signals_at_trade=["rsi_oversold", "sentiment_surge"],
        )
        assert trade.ticker == "AAPL"
        assert trade.action == TradeAction.BUY
        assert trade.total_value == 1500.0

    def test_sell_creation(self) -> None:
        trade = TrackedTrade(
            trade_id="T002",
            ticker="TSLA",
            action=TradeAction.SELL,
            price=200.0,
            quantity=5,
            trade_date="2026-02-01",
            conviction_at_trade=3.0,
            signals_at_trade=["stop_loss"],
            opportunity_card_id="OC-42",
            notes="Triggered stop-loss at -8%",
        )
        assert trade.action == TradeAction.SELL
        assert trade.opportunity_card_id == "OC-42"
        assert trade.total_value == 1000.0

    def test_price_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="price"):
            TrackedTrade(
                trade_id="T003",
                ticker="GOOG",
                action=TradeAction.BUY,
                price=-10.0,
                quantity=1,
                trade_date="2026-01-01",
                conviction_at_trade=5.0,
                signals_at_trade=[],
            )

    def test_quantity_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="quantity"):
            TrackedTrade(
                trade_id="T004",
                ticker="MSFT",
                action=TradeAction.BUY,
                price=300.0,
                quantity=0,
                trade_date="2026-01-01",
                conviction_at_trade=5.0,
                signals_at_trade=[],
            )


# ---------------------------------------------------------------------------
# TradeOutcome
# ---------------------------------------------------------------------------


class TestTradeOutcome:
    def test_profitable_outcome(self) -> None:
        outcome = TradeOutcome(
            ticker="AAPL",
            buy_trade_id="T001",
            sell_trade_id="T002",
            buy_price=150.0,
            sell_price=165.0,
            quantity=10,
            buy_date="2026-01-01",
            sell_date="2026-01-15",
            holding_days=14,
            return_pct=10.0,
            return_dollar=150.0,
            signals_at_entry=["rsi_oversold", "sentiment_surge"],
            conviction_at_entry=8.5,
        )
        assert outcome.is_profitable is True

    def test_loss_outcome(self) -> None:
        outcome = TradeOutcome(
            ticker="TSLA",
            buy_trade_id="T003",
            sell_trade_id="T004",
            buy_price=200.0,
            sell_price=184.0,
            quantity=5,
            buy_date="2026-02-01",
            sell_date="2026-02-09",
            holding_days=8,
            return_pct=-8.0,
            return_dollar=-80.0,
            signals_at_entry=["momentum"],
            conviction_at_entry=6.0,
        )
        assert outcome.is_profitable is False


# ---------------------------------------------------------------------------
# SignalPerformance
# ---------------------------------------------------------------------------


class TestSignalPerformance:
    def test_useful_signal(self) -> None:
        perf = SignalPerformance(
            signal_name="rsi_oversold",
            total_trades=20,
            winning_trades=12,
            losing_trades=8,
            hit_rate=60.0,
            avg_return_pct=5.2,
            avg_winning_return=9.1,
            avg_losing_return=-3.5,
        )
        assert perf.is_useful is True

    def test_not_useful_signal(self) -> None:
        perf = SignalPerformance(
            signal_name="random_signal",
            total_trades=30,
            winning_trades=13,
            losing_trades=17,
            hit_rate=43.3,
            avg_return_pct=-1.0,
        )
        assert perf.is_useful is False
