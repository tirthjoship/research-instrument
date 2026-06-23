"""Tests for TradesMixin."""

from __future__ import annotations

import pytest

from adapters.data.sqlite_store import SQLiteStore
from domain.outcome import TrackedTrade, TradeAction, TradeOutcome


def _make_trade(trade_id: str = "t1", ticker: str = "AAPL") -> TrackedTrade:
    return TrackedTrade(
        trade_id=trade_id,
        ticker=ticker,
        action=TradeAction.BUY,
        price=150.0,
        quantity=10,
        trade_date="2026-06-03",
        conviction_at_trade=0.82,
        signals_at_trade=["rsi_oversold", "macd_cross"],
        opportunity_card_id="opp-001",
        notes="Test trade",
    )


def _make_outcome(buy_id: str = "t1", sell_id: str = "t2") -> TradeOutcome:
    return TradeOutcome(
        ticker="AAPL",
        buy_trade_id=buy_id,
        sell_trade_id=sell_id,
        buy_price=150.0,
        sell_price=165.0,
        quantity=10,
        buy_date="2026-06-03",
        sell_date="2026-06-13",
        holding_days=10,
        return_pct=10.0,
        return_dollar=150.0,
        signals_at_entry=["rsi_oversold", "macd_cross"],
        conviction_at_entry=0.82,
    )


def test_save_and_load_trade(tmp_path: pytest.TempPathFactory) -> None:
    store = SQLiteStore(str(tmp_path / "trades.db"))  # type: ignore[arg-type]
    trade = _make_trade()
    store.save_trade(trade)
    results = store.get_trades()
    assert len(results) == 1
    loaded = results[0]
    assert loaded.trade_id == "t1"
    assert loaded.ticker == "AAPL"
    assert loaded.action == TradeAction.BUY
    assert loaded.price == 150.0
    assert loaded.quantity == 10
    assert loaded.signals_at_trade == ["rsi_oversold", "macd_cross"]
    assert loaded.conviction_at_trade == 0.82
    assert loaded.opportunity_card_id == "opp-001"
    assert loaded.notes == "Test trade"


def test_save_and_load_outcome(tmp_path: pytest.TempPathFactory) -> None:
    store = SQLiteStore(str(tmp_path / "outcomes.db"))  # type: ignore[arg-type]
    outcome = _make_outcome()
    store.save_trade_outcome(outcome)
    results = store.get_trade_outcomes()
    assert len(results) == 1
    loaded = results[0]
    assert loaded.ticker == "AAPL"
    assert loaded.return_pct == 10.0
    assert loaded.return_dollar == 150.0
    assert loaded.holding_days == 10
    assert loaded.signals_at_entry == ["rsi_oversold", "macd_cross"]
    assert loaded.conviction_at_entry == 0.82


def test_get_trades_all(tmp_path: pytest.TempPathFactory) -> None:
    store = SQLiteStore(str(tmp_path / "filter.db"))  # type: ignore[arg-type]
    store.save_trade(_make_trade("t1", "AAPL"))
    store.save_trade(_make_trade("t2", "GOOG"))
    all_trades = store.get_trades()
    assert len(all_trades) == 2
    aapl_trades = store.get_trades(ticker="AAPL")
    assert len(aapl_trades) == 1
    assert aapl_trades[0].ticker == "AAPL"
    goog_trades = store.get_trades(ticker="GOOG")
    assert len(goog_trades) == 1
    assert goog_trades[0].ticker == "GOOG"
