"""Tests for OutcomeTrackingUseCase — TDD with FakeTradeStore."""

from __future__ import annotations

from typing import Any

from domain.outcome import TrackedTrade, TradeAction, TradeOutcome

# ---------------------------------------------------------------------------
# Fake store
# ---------------------------------------------------------------------------


class FakeTradeStore:
    """In-memory double for any real trade persistence adapter."""

    def __init__(self) -> None:
        self._trades: list[TrackedTrade] = []
        self._outcomes: list[TradeOutcome] = []

    # -- trades --
    def save_trade(self, trade: TrackedTrade) -> None:
        self._trades.append(trade)

    def get_trades(self) -> list[TrackedTrade]:
        return list(self._trades)

    # -- outcomes --
    def save_trade_outcome(self, outcome: TradeOutcome) -> None:
        self._outcomes.append(outcome)

    def get_trade_outcomes(self) -> list[TradeOutcome]:
        return list(self._outcomes)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_use_case() -> Any:
    from application.outcome_use_case import OutcomeTrackingUseCase

    return OutcomeTrackingUseCase(store=FakeTradeStore())


# ---------------------------------------------------------------------------
# record_buy
# ---------------------------------------------------------------------------


class TestRecordBuy:
    def test_returns_tracked_trade(self) -> None:
        uc = _make_use_case()
        trade = uc.record_buy(
            ticker="AAPL",
            price=150.0,
            quantity=10,
            trade_date="2024-01-15",
        )
        assert isinstance(trade, TrackedTrade)
        assert trade.ticker == "AAPL"
        assert trade.action == TradeAction.BUY
        assert trade.price == 150.0
        assert trade.quantity == 10
        assert trade.trade_date == "2024-01-15"

    def test_trade_id_is_8_chars(self) -> None:
        uc = _make_use_case()
        trade = uc.record_buy("MSFT", 300.0, 5, "2024-01-15")
        assert len(trade.trade_id) == 8

    def test_conviction_and_signals_stored(self) -> None:
        uc = _make_use_case()
        trade = uc.record_buy(
            ticker="TSLA",
            price=200.0,
            quantity=3,
            trade_date="2024-01-15",
            conviction=0.82,
            signals=["rsi_oversold", "sentiment_spike"],
        )
        assert trade.conviction_at_trade == 0.82
        assert trade.signals_at_trade == ["rsi_oversold", "sentiment_spike"]

    def test_optional_fields_default(self) -> None:
        uc = _make_use_case()
        trade = uc.record_buy("GOOG", 140.0, 2, "2024-01-15")
        assert trade.conviction_at_trade == 0.0
        assert trade.signals_at_trade == []
        assert trade.opportunity_card_id == ""
        assert trade.notes == ""

    def test_trade_persisted_in_store(self) -> None:
        store = FakeTradeStore()
        from application.outcome_use_case import OutcomeTrackingUseCase

        uc = OutcomeTrackingUseCase(store=store)
        uc.record_buy("NVDA", 500.0, 1, "2024-01-15")
        assert len(store.get_trades()) == 1

    def test_each_buy_has_unique_id(self) -> None:
        uc = _make_use_case()
        t1 = uc.record_buy("AAPL", 150.0, 1, "2024-01-15")
        t2 = uc.record_buy("AAPL", 155.0, 1, "2024-01-16")
        assert t1.trade_id != t2.trade_id


# ---------------------------------------------------------------------------
# record_sell
# ---------------------------------------------------------------------------


class TestRecordSell:
    def test_returns_none_when_no_buy(self) -> None:
        uc = _make_use_case()
        result = uc.record_sell("AAPL", 160.0, 5, "2024-01-20")
        assert result is None

    def test_returns_outcome_and_sell_trade(self) -> None:
        uc = _make_use_case()
        uc.record_buy("AAPL", 150.0, 10, "2024-01-15")
        result = uc.record_sell("AAPL", 165.0, 10, "2024-01-25")
        assert result is not None
        outcome, sell_trade = result
        assert isinstance(outcome, TradeOutcome)
        assert isinstance(sell_trade, TrackedTrade)
        assert sell_trade.action == TradeAction.SELL

    def test_return_pct_calculated_correctly(self) -> None:
        uc = _make_use_case()
        uc.record_buy("AAPL", 100.0, 10, "2024-01-15")
        result = uc.record_sell("AAPL", 110.0, 10, "2024-01-25")
        assert result is not None
        outcome, _ = result
        assert abs(outcome.return_pct - 10.0) < 1e-6

    def test_negative_return_pct(self) -> None:
        uc = _make_use_case()
        uc.record_buy("AAPL", 200.0, 5, "2024-01-15")
        result = uc.record_sell("AAPL", 180.0, 5, "2024-01-25")
        assert result is not None
        outcome, _ = result
        assert outcome.return_pct < 0

    def test_outcome_persisted_in_store(self) -> None:
        store = FakeTradeStore()
        from application.outcome_use_case import OutcomeTrackingUseCase

        uc = OutcomeTrackingUseCase(store=store)
        uc.record_buy("TSLA", 200.0, 2, "2024-01-10")
        uc.record_sell("TSLA", 220.0, 2, "2024-01-20")
        assert len(store.get_trade_outcomes()) == 1

    def test_sell_trade_persisted_in_store(self) -> None:
        store = FakeTradeStore()
        from application.outcome_use_case import OutcomeTrackingUseCase

        uc = OutcomeTrackingUseCase(store=store)
        uc.record_buy("MSFT", 300.0, 3, "2024-01-10")
        uc.record_sell("MSFT", 310.0, 3, "2024-01-20")
        assert len(store.get_trades()) == 2  # buy + sell

    def test_sell_uses_most_recent_buy(self) -> None:
        """When two buys exist, sell should pair with the most recent one."""
        uc = _make_use_case()
        uc.record_buy("AAPL", 100.0, 5, "2024-01-01")
        uc.record_buy("AAPL", 120.0, 5, "2024-01-10")
        result = uc.record_sell("AAPL", 130.0, 5, "2024-01-20")
        assert result is not None
        outcome, _ = result
        assert outcome.buy_price == 120.0  # most recent buy

    def test_sell_without_buy_returns_none_different_ticker(self) -> None:
        uc = _make_use_case()
        uc.record_buy("AAPL", 150.0, 1, "2024-01-15")
        result = uc.record_sell("MSFT", 300.0, 1, "2024-01-20")
        assert result is None


# ---------------------------------------------------------------------------
# get_signal_report
# ---------------------------------------------------------------------------


class TestGetSignalReport:
    def test_empty_store_returns_no_data_message(self) -> None:
        uc = _make_use_case()
        report = uc.get_signal_report()
        assert "No signal performance data" in report

    def test_report_contains_signal_names(self) -> None:
        uc = _make_use_case()
        uc.record_buy(
            "AAPL",
            100.0,
            10,
            "2024-01-15",
            signals=["rsi_oversold", "sentiment_spike"],
        )
        uc.record_sell("AAPL", 110.0, 10, "2024-01-25")
        report = uc.get_signal_report()
        assert "rsi_oversold" in report
        assert "sentiment_spike" in report

    def test_report_contains_month_label(self) -> None:
        uc = _make_use_case()
        uc.record_buy("NVDA", 400.0, 2, "2024-03-01", signals=["macd_cross"])
        uc.record_sell("NVDA", 420.0, 2, "2024-03-15")
        report = uc.get_signal_report(month="2024-03")
        assert "2024-03" in report

    def test_report_is_string(self) -> None:
        uc = _make_use_case()
        assert isinstance(uc.get_signal_report(), str)


# ---------------------------------------------------------------------------
# get_outcomes_summary
# ---------------------------------------------------------------------------


class TestGetOutcomesSummary:
    def test_empty_store_returns_zeros(self) -> None:
        uc = _make_use_case()
        summary = uc.get_outcomes_summary()
        assert summary["total_trades"] == 0
        assert summary["total_return"] == 0.0
        assert summary["win_rate"] == 0.0
        assert summary["avg_return_pct"] == 0.0

    def test_summary_keys_present(self) -> None:
        uc = _make_use_case()
        summary = uc.get_outcomes_summary()
        assert set(summary.keys()) == {
            "total_trades",
            "total_return",
            "win_rate",
            "avg_return_pct",
        }

    def test_single_profitable_trade(self) -> None:
        uc = _make_use_case()
        uc.record_buy("AAPL", 100.0, 10, "2024-01-01")
        uc.record_sell("AAPL", 120.0, 10, "2024-01-15")
        summary = uc.get_outcomes_summary()
        assert summary["total_trades"] == 1
        assert abs(summary["avg_return_pct"] - 20.0) < 1e-6
        assert summary["win_rate"] == 100.0

    def test_mixed_trades_win_rate(self) -> None:
        uc = _make_use_case()
        uc.record_buy("AAPL", 100.0, 5, "2024-01-01")
        uc.record_sell("AAPL", 120.0, 5, "2024-01-15")
        uc.record_buy("MSFT", 200.0, 3, "2024-02-01")
        uc.record_sell("MSFT", 180.0, 3, "2024-02-15")
        summary = uc.get_outcomes_summary()
        assert summary["total_trades"] == 2
        assert summary["win_rate"] == 50.0

    def test_total_return_is_sum_of_dollar_returns(self) -> None:
        uc = _make_use_case()
        uc.record_buy("AAPL", 100.0, 10, "2024-01-01")
        uc.record_sell("AAPL", 110.0, 10, "2024-01-15")  # +$100
        uc.record_buy("MSFT", 200.0, 5, "2024-02-01")
        uc.record_sell("MSFT", 210.0, 5, "2024-02-15")  # +$50
        summary = uc.get_outcomes_summary()
        assert abs(summary["total_return"] - 150.0) < 1e-6
