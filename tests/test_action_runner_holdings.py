"""TDD tests — trades must upsert holdings in action_runner.

Five required cases:
1. buy new ticker → appears in holdings with qty+price
2. buy more of existing → qty summed, price weighted-avg
3. sell partial → qty reduced
4. sell all → holding removed
5. sell unknown ticker → holdings unchanged, no raise
"""

from __future__ import annotations

import os
import tempfile

import pytest

from adapters.data.sqlite_store import SQLiteStore
from adapters.visualization.action_runner import run_record_buy, run_record_sell
from domain.models import Holding


@pytest.fixture
def tmp_db() -> str:  # type: ignore[return]
    with tempfile.TemporaryDirectory() as tmp:
        yield os.path.join(tmp, "test.db")


class TestBuyNewTicker:
    """Case 1: buy brand-new ticker → appears in holdings."""

    def test_buy_creates_holding(self, tmp_db: str) -> None:
        run_record_buy(
            ticker="NVDA",
            price=100.0,
            quantity=10,
            trade_date="2026-01-01",
            db_path=tmp_db,
        )
        store = SQLiteStore(tmp_db)
        h = store.get_holding("NVDA")
        assert h is not None
        assert h.symbol == "NVDA"
        assert h.quantity == 10
        assert abs(h.purchase_price - 100.0) < 0.001
        assert h.purchase_date == "2026-01-01"


class TestBuyExistingTicker:
    """Case 2: buy more of existing → qty summed, price weighted-avg."""

    def test_buy_adds_to_existing_holding(self, tmp_db: str) -> None:
        # Pre-seed holding: 10 @ $100
        store = SQLiteStore(tmp_db)
        store.add_holding(
            Holding(
                symbol="NVDA",
                quantity=10.0,
                purchase_price=100.0,
                purchase_date="2026-01-01",
            )
        )

        # Buy 20 more @ $150
        run_record_buy(
            ticker="NVDA",
            price=150.0,
            quantity=20,
            trade_date="2026-02-01",
            db_path=tmp_db,
        )

        h = SQLiteStore(tmp_db).get_holding("NVDA")
        assert h is not None
        assert h.quantity == 30.0  # 10 + 20
        # Weighted avg = (10*100 + 20*150) / 30 = (1000 + 3000) / 30 = 133.333...
        expected_avg = (10 * 100 + 20 * 150) / 30
        assert abs(h.purchase_price - expected_avg) < 0.01


class TestSellPartial:
    """Case 3: sell partial → qty reduced."""

    def test_sell_reduces_quantity(self, tmp_db: str) -> None:
        store = SQLiteStore(tmp_db)
        store.add_holding(
            Holding(
                symbol="AAPL",
                quantity=20.0,
                purchase_price=200.0,
                purchase_date="2026-01-01",
            )
        )

        run_record_sell(
            ticker="AAPL",
            price=220.0,
            quantity=5,
            trade_date="2026-03-01",
            db_path=tmp_db,
        )

        h = SQLiteStore(tmp_db).get_holding("AAPL")
        assert h is not None
        assert h.quantity == 15.0  # 20 - 5


class TestSellAll:
    """Case 4: sell all → holding removed."""

    def test_sell_all_removes_holding(self, tmp_db: str) -> None:
        store = SQLiteStore(tmp_db)
        store.add_holding(
            Holding(
                symbol="TSLA",
                quantity=10.0,
                purchase_price=300.0,
                purchase_date="2026-01-01",
            )
        )

        run_record_sell(
            ticker="TSLA",
            price=350.0,
            quantity=10,
            trade_date="2026-03-01",
            db_path=tmp_db,
        )

        assert SQLiteStore(tmp_db).get_holding("TSLA") is None

    def test_sell_over_full_qty_also_removes_holding(self, tmp_db: str) -> None:
        """Selling more than held should remove the holding, not go negative."""
        store = SQLiteStore(tmp_db)
        store.add_holding(
            Holding(
                symbol="MSFT",
                quantity=5.0,
                purchase_price=400.0,
                purchase_date="2026-01-01",
            )
        )

        run_record_sell(
            ticker="MSFT",
            price=420.0,
            quantity=5,
            trade_date="2026-03-01",
            db_path=tmp_db,
        )

        assert SQLiteStore(tmp_db).get_holding("MSFT") is None


class TestSellUnknownTicker:
    """Case 5: sell ticker not in holdings → no-op, no raise."""

    def test_sell_unknown_leaves_holdings_unchanged(self, tmp_db: str) -> None:
        # Create DB with one holding (not the one being sold)
        store = SQLiteStore(tmp_db)
        store.add_holding(
            Holding(
                symbol="AAPL",
                quantity=10.0,
                purchase_price=200.0,
                purchase_date="2026-01-01",
            )
        )

        # Sell GOOG which does not exist in holdings — should not raise
        run_record_sell(
            ticker="GOOG",
            price=150.0,
            quantity=5,
            trade_date="2026-03-01",
            db_path=tmp_db,
        )

        # AAPL holding unchanged
        h = SQLiteStore(tmp_db).get_holding("AAPL")
        assert h is not None
        assert h.quantity == 10.0

        # GOOG not created
        assert SQLiteStore(tmp_db).get_holding("GOOG") is None

    def test_sell_empty_db_does_not_raise(self, tmp_db: str) -> None:
        # Should not raise even with empty DB
        SQLiteStore(tmp_db)  # init schema
        run_record_sell(
            ticker="GOOG",
            price=150.0,
            quantity=5,
            trade_date="2026-03-01",
            db_path=tmp_db,
        )
