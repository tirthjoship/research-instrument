"""Tests for domain/outcome_service.py — TDD: write tests first, then implement."""

from __future__ import annotations

import pytest

from domain.outcome import SignalPerformance, TrackedTrade, TradeAction, TradeOutcome
from domain.outcome_service import (
    compute_outcome,
    compute_signal_performance,
    generate_report_card,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _buy(
    ticker: str = "AAPL", price: float = 150.0, quantity: int = 10
) -> TrackedTrade:
    return TrackedTrade(
        trade_id="buy-001",
        ticker=ticker,
        action=TradeAction.BUY,
        price=price,
        quantity=quantity,
        trade_date="2024-01-01",
        conviction_at_trade=0.75,
        signals_at_trade=["rsi_oversold", "macd_cross"],
    )


def _sell(
    ticker: str = "AAPL", price: float = 166.90, quantity: int = 10
) -> TrackedTrade:
    return TrackedTrade(
        trade_id="sell-001",
        ticker=ticker,
        action=TradeAction.SELL,
        price=price,
        quantity=quantity,
        trade_date="2024-02-05",
        conviction_at_trade=0.60,
        signals_at_trade=["rsi_overbought"],
    )


# ---------------------------------------------------------------------------
# compute_outcome
# ---------------------------------------------------------------------------


class TestComputeOutcome:
    def test_profitable_trade_return_pct(self) -> None:
        """Buy 150 → sell 166.90 over 35 days should yield ~11.27%."""
        outcome = compute_outcome(_buy(), _sell())
        assert round(outcome.return_pct, 2) == 11.27

    def test_profitable_trade_holding_days(self) -> None:
        outcome = compute_outcome(_buy(), _sell())
        assert outcome.holding_days == 35

    def test_profitable_trade_return_dollar(self) -> None:
        """(166.90 - 150.0) * 10 = 169.0"""
        outcome = compute_outcome(_buy(), _sell())
        assert round(outcome.return_dollar, 2) == 169.0

    def test_profitable_trade_ticker(self) -> None:
        outcome = compute_outcome(_buy(), _sell())
        assert outcome.ticker == "AAPL"

    def test_profitable_trade_is_profitable(self) -> None:
        outcome = compute_outcome(_buy(), _sell())
        assert outcome.is_profitable is True

    def test_profitable_trade_signals_at_entry(self) -> None:
        outcome = compute_outcome(_buy(), _sell())
        assert outcome.signals_at_entry == ["rsi_oversold", "macd_cross"]

    def test_losing_trade_return_pct(self) -> None:
        """Buy 150 → sell 130 → negative return."""
        buy = _buy(price=150.0, quantity=5)
        sell = _sell(ticker="AAPL", price=130.0, quantity=5)
        outcome = compute_outcome(buy, sell)
        assert outcome.return_pct < 0
        assert round(outcome.return_pct, 4) == round(((130.0 - 150.0) / 150.0) * 100, 4)

    def test_losing_trade_return_dollar(self) -> None:
        buy = _buy(price=150.0, quantity=5)
        sell = _sell(ticker="AAPL", price=130.0, quantity=5)
        outcome = compute_outcome(buy, sell)
        assert outcome.return_dollar == (130.0 - 150.0) * 5

    def test_losing_trade_is_not_profitable(self) -> None:
        buy = _buy(price=150.0, quantity=5)
        sell = _sell(ticker="AAPL", price=130.0, quantity=5)
        outcome = compute_outcome(buy, sell)
        assert outcome.is_profitable is False

    def test_ticker_mismatch_raises(self) -> None:
        buy = _buy(ticker="AAPL")
        sell = _sell(ticker="TSLA")
        with pytest.raises(ValueError, match="ticker mismatch"):
            compute_outcome(buy, sell)

    def test_outcome_ids_carried(self) -> None:
        outcome = compute_outcome(_buy(), _sell())
        assert outcome.buy_trade_id == "buy-001"
        assert outcome.sell_trade_id == "sell-001"

    def test_outcome_prices_carried(self) -> None:
        outcome = compute_outcome(_buy(), _sell())
        assert outcome.buy_price == 150.0
        assert outcome.sell_price == 166.90

    def test_outcome_conviction_carried(self) -> None:
        outcome = compute_outcome(_buy(), _sell())
        assert outcome.conviction_at_entry == 0.75


# ---------------------------------------------------------------------------
# compute_signal_performance
# ---------------------------------------------------------------------------


def _make_outcome(signals: list[str], return_pct: float) -> TradeOutcome:
    return TradeOutcome(
        ticker="AAPL",
        buy_trade_id="b1",
        sell_trade_id="s1",
        buy_price=100.0,
        sell_price=100.0 + return_pct,
        quantity=1,
        buy_date="2024-01-01",
        sell_date="2024-01-10",
        holding_days=9,
        return_pct=return_pct,
        return_dollar=return_pct,
        signals_at_entry=signals,
        conviction_at_entry=0.7,
    )


class TestComputeSignalPerformance:
    def test_empty_outcomes_returns_empty_list(self) -> None:
        result = compute_signal_performance([])
        assert result == []

    def test_single_signal_two_outcomes(self) -> None:
        outcomes = [
            _make_outcome(["rsi_oversold"], 5.0),
            _make_outcome(["rsi_oversold"], -3.0),
        ]
        result = compute_signal_performance(outcomes)
        assert len(result) == 1
        perf = result[0]
        assert perf.signal_name == "rsi_oversold"
        assert perf.total_trades == 2
        assert perf.winning_trades == 1
        assert perf.losing_trades == 1
        assert perf.hit_rate == 50.0

    def test_single_signal_avg_return(self) -> None:
        outcomes = [
            _make_outcome(["rsi_oversold"], 4.0),
            _make_outcome(["rsi_oversold"], -2.0),
        ]
        result = compute_signal_performance(outcomes)
        assert result[0].avg_return_pct == pytest.approx(1.0)

    def test_single_signal_avg_winning_return(self) -> None:
        outcomes = [
            _make_outcome(["rsi_oversold"], 4.0),
            _make_outcome(["rsi_oversold"], -2.0),
        ]
        result = compute_signal_performance(outcomes)
        assert result[0].avg_winning_return == pytest.approx(4.0)

    def test_single_signal_avg_losing_return(self) -> None:
        outcomes = [
            _make_outcome(["rsi_oversold"], 4.0),
            _make_outcome(["rsi_oversold"], -2.0),
        ]
        result = compute_signal_performance(outcomes)
        assert result[0].avg_losing_return == pytest.approx(-2.0)

    def test_multi_signal_per_outcome(self) -> None:
        """Outcome with two signals contributes to both signal buckets."""
        outcomes = [
            _make_outcome(["sig_a", "sig_b"], 5.0),
            _make_outcome(["sig_a"], -1.0),
        ]
        result = compute_signal_performance(outcomes)
        names = {p.signal_name for p in result}
        assert "sig_a" in names
        assert "sig_b" in names

    def test_sig_a_totals(self) -> None:
        outcomes = [
            _make_outcome(["sig_a", "sig_b"], 5.0),
            _make_outcome(["sig_a"], -1.0),
        ]
        result = compute_signal_performance(outcomes)
        sig_a = next(p for p in result if p.signal_name == "sig_a")
        assert sig_a.total_trades == 2

    def test_all_winning_hit_rate(self) -> None:
        outcomes = [
            _make_outcome(["sig_x"], 3.0),
            _make_outcome(["sig_x"], 7.0),
        ]
        result = compute_signal_performance(outcomes)
        assert result[0].hit_rate == 100.0
        assert result[0].is_useful is True

    def test_all_losing_hit_rate(self) -> None:
        outcomes = [
            _make_outcome(["sig_y"], -3.0),
            _make_outcome(["sig_y"], -1.0),
        ]
        result = compute_signal_performance(outcomes)
        assert result[0].hit_rate == 0.0
        assert result[0].is_useful is False


# ---------------------------------------------------------------------------
# generate_report_card
# ---------------------------------------------------------------------------


def _make_perf(name: str, hit_rate: float, avg_return: float) -> SignalPerformance:
    winning = int(hit_rate)
    losing = 100 - winning
    return SignalPerformance(
        signal_name=name,
        total_trades=100,
        winning_trades=winning,
        losing_trades=losing,
        hit_rate=hit_rate,
        avg_return_pct=avg_return,
        avg_winning_return=max(avg_return, 0.0),
        avg_losing_return=min(avg_return, 0.0),
    )


class TestGenerateReportCard:
    def test_contains_best_signal(self) -> None:
        performances = [
            _make_perf("rsi_oversold", 70.0, 4.0),
            _make_perf("macd_cross", 40.0, -1.0),
        ]
        report = generate_report_card(performances)
        assert "Best signal" in report

    def test_contains_worst_signal(self) -> None:
        performances = [
            _make_perf("rsi_oversold", 70.0, 4.0),
            _make_perf("macd_cross", 40.0, -1.0),
        ]
        report = generate_report_card(performances)
        assert "Worst signal" in report

    def test_strong_performers_label(self) -> None:
        performances = [_make_perf("rsi_oversold", 70.0, 4.0)]
        report = generate_report_card(performances)
        assert "Strong performers" in report

    def test_consider_reducing_weight_label(self) -> None:
        performances = [_make_perf("bad_signal", 40.0, -2.0)]
        report = generate_report_card(performances)
        assert "Consider reducing weight for" in report

    def test_best_signal_name_appears(self) -> None:
        performances = [
            _make_perf("rsi_oversold", 70.0, 4.0),
            _make_perf("macd_cross", 40.0, -1.0),
        ]
        report = generate_report_card(performances)
        assert "rsi_oversold" in report

    def test_worst_signal_name_appears(self) -> None:
        performances = [
            _make_perf("rsi_oversold", 70.0, 4.0),
            _make_perf("macd_cross", 40.0, -1.0),
        ]
        report = generate_report_card(performances)
        assert "macd_cross" in report

    def test_month_appears_in_report(self) -> None:
        performances = [_make_perf("rsi_oversold", 70.0, 4.0)]
        report = generate_report_card(performances, month="2024-01")
        assert "2024-01" in report

    def test_most_profitable_label(self) -> None:
        performances = [
            _make_perf("rsi_oversold", 70.0, 4.0),
            _make_perf("macd_cross", 40.0, -1.0),
        ]
        report = generate_report_card(performances)
        assert "Most profitable" in report

    def test_empty_performances_returns_string(self) -> None:
        report = generate_report_card([])
        assert isinstance(report, str)
        assert len(report) > 0

    def test_hit_rate_at_exactly_50_triggers_reduce_weight(self) -> None:
        """Boundary: hit_rate <= 50 → Consider reducing weight."""
        performances = [_make_perf("border_signal", 50.0, 0.0)]
        report = generate_report_card(performances)
        assert "Consider reducing weight for" in report
