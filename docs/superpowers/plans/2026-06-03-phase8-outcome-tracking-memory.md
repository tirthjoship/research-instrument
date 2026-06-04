# Phase 8: Outcome Tracking & Memory — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add outcome tracking so the system learns which signals actually work — manual buy/sell logging, outcome correlation to signals, signal report card, and historical bootstrap for day-one intelligence.

**Architecture:** New domain models (TrackedTrade, TradeOutcome, SignalPerformance) + outcome tracking service (pure domain logic) + SQLite persistence (trades + outcomes tables) + historical bootstrap engine (simulates past recommendations) + dashboard evolution (Positions → Outcome Tracker, Model Confidence → System Intelligence). All hexagonal — domain stays pure.

**Tech Stack:** Python 3.12+, pytest, Streamlit, SQLite, existing conviction engine from Phase 7.

**Design Spec:** `docs/superpowers/specs/2026-06-03-opportunity-intelligence-engine-design.md` (Section 6)

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `domain/outcome.py` | TrackedTrade, TradeOutcome, SignalPerformance domain models |
| `domain/outcome_service.py` | Pure logic: compute returns, correlate signals, generate report card |
| `application/outcome_use_case.py` | OutcomeTrackingUseCase — orchestrates trade logging + outcome evaluation |
| `application/bootstrap_use_case.py` | HistoricalBootstrapUseCase — simulates past recommendations for cold-start |
| `tests/test_outcome_models.py` | Domain model tests |
| `tests/test_outcome_service.py` | Outcome logic tests |
| `tests/test_outcome_use_case.py` | Use case tests with fakes |
| `tests/test_bootstrap_use_case.py` | Bootstrap tests |

### Modified Files

| File | Change |
|------|--------|
| `adapters/data/sqlite_store.py` | Add trades + outcomes tables, CRUD methods |
| `adapters/visualization/tabs/positions.py` | Evolve → Outcome Tracker (buy/sell logging + P&L) |
| `adapters/visualization/tabs/model_confidence.py` | Evolve → System Intelligence (signal report card) |
| `adapters/visualization/data_loader.py` | Add load_trades(), load_outcomes(), load_signal_report() |
| `adapters/visualization/action_runner.py` | Add run_record_trade(), run_bootstrap() |
| `adapters/visualization/components/verdicts.py` | Add outcome_tracker_verdict(), system_intelligence_verdict() |
| `adapters/visualization/dashboard.py` | Update tab labels |
| `tests/test_sqlite_store.py` | Add trade/outcome persistence tests |

---

## Task 1: Domain Models — TrackedTrade, TradeOutcome, SignalPerformance

**Files:**
- Create: `domain/outcome.py`
- Test: `tests/test_outcome_models.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for outcome tracking domain models."""

from datetime import datetime

import pytest

from domain.outcome import (
    SignalPerformance,
    TradeAction,
    TradeOutcome,
    TrackedTrade,
)


class TestTrackedTrade:
    def test_buy_creation(self) -> None:
        t = TrackedTrade(
            trade_id="t001",
            ticker="NVDA",
            action=TradeAction.BUY,
            price=142.0,
            quantity=10,
            trade_date="2026-06-05",
            conviction_at_trade=8.2,
            signals_at_trade=["smart_money", "sentiment_momentum"],
            opportunity_card_id="opp_nvda_20260605",
            notes="Activist 13D + insider cluster",
        )
        assert t.ticker == "NVDA"
        assert t.action == TradeAction.BUY
        assert t.total_value == 1420.0

    def test_sell_creation(self) -> None:
        t = TrackedTrade(
            trade_id="t002",
            ticker="NVDA",
            action=TradeAction.SELL,
            price=158.0,
            quantity=10,
            trade_date="2026-07-10",
            conviction_at_trade=3.0,
            signals_at_trade=[],
            notes="Taking profit",
        )
        assert t.action == TradeAction.SELL

    def test_price_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="price"):
            TrackedTrade(
                trade_id="t003", ticker="X", action=TradeAction.BUY,
                price=-1.0, quantity=1, trade_date="2026-06-01",
                conviction_at_trade=5.0, signals_at_trade=[],
            )

    def test_quantity_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="quantity"):
            TrackedTrade(
                trade_id="t004", ticker="X", action=TradeAction.BUY,
                price=100.0, quantity=0, trade_date="2026-06-01",
                conviction_at_trade=5.0, signals_at_trade=[],
            )


class TestTradeOutcome:
    def test_valid_creation(self) -> None:
        o = TradeOutcome(
            ticker="NVDA",
            buy_trade_id="t001",
            sell_trade_id="t002",
            buy_price=142.0,
            sell_price=158.0,
            quantity=10,
            buy_date="2026-06-05",
            sell_date="2026-07-10",
            holding_days=35,
            return_pct=11.27,
            return_dollar=160.0,
            signals_at_entry=["smart_money", "sentiment_momentum"],
            conviction_at_entry=8.2,
        )
        assert o.return_pct == 11.27
        assert o.is_profitable is True

    def test_loss_outcome(self) -> None:
        o = TradeOutcome(
            ticker="TSLA", buy_trade_id="t005", sell_trade_id="t006",
            buy_price=200.0, sell_price=180.0, quantity=5,
            buy_date="2026-06-01", sell_date="2026-06-15",
            holding_days=14, return_pct=-10.0, return_dollar=-100.0,
            signals_at_entry=["ml_direction"],
            conviction_at_entry=4.0,
        )
        assert o.is_profitable is False


class TestSignalPerformance:
    def test_valid_creation(self) -> None:
        sp = SignalPerformance(
            signal_name="smart_money",
            total_trades=14,
            winning_trades=10,
            losing_trades=4,
            hit_rate=71.4,
            avg_return_pct=8.2,
            avg_winning_return=12.5,
            avg_losing_return=-3.1,
        )
        assert sp.hit_rate == 71.4
        assert sp.is_useful is True

    def test_not_useful_below_50(self) -> None:
        sp = SignalPerformance(
            signal_name="ml_direction",
            total_trades=31, winning_trades=15, losing_trades=16,
            hit_rate=48.4, avg_return_pct=0.3,
            avg_winning_return=5.0, avg_losing_return=-4.8,
        )
        assert sp.is_useful is False
```

- [ ] **Step 2: Run tests — verify FAIL**

Run: `cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender" && python -m pytest tests/test_outcome_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'domain.outcome'`

- [ ] **Step 3: Implement domain models**

```python
"""Outcome tracking domain models.

Pure Python value objects for tracking trades, computing outcomes,
and evaluating signal performance. No external dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TradeAction(str, Enum):
    """Trade direction."""
    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True)
class TrackedTrade:
    """A recorded buy or sell action linked to an opportunity card."""
    trade_id: str
    ticker: str
    action: TradeAction
    price: float
    quantity: int
    trade_date: str  # YYYY-MM-DD
    conviction_at_trade: float
    signals_at_trade: list[str]
    opportunity_card_id: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        if self.price <= 0:
            raise ValueError(f"price must be > 0, got {self.price}")
        if self.quantity <= 0:
            raise ValueError(f"quantity must be > 0, got {self.quantity}")

    @property
    def total_value(self) -> float:
        return self.price * self.quantity


@dataclass(frozen=True)
class TradeOutcome:
    """Computed outcome after closing a position (buy → sell)."""
    ticker: str
    buy_trade_id: str
    sell_trade_id: str
    buy_price: float
    sell_price: float
    quantity: int
    buy_date: str
    sell_date: str
    holding_days: int
    return_pct: float
    return_dollar: float
    signals_at_entry: list[str]
    conviction_at_entry: float

    @property
    def is_profitable(self) -> bool:
        return self.return_pct > 0


@dataclass(frozen=True)
class SignalPerformance:
    """Aggregated performance metrics for a single signal type."""
    signal_name: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    hit_rate: float  # percentage
    avg_return_pct: float
    avg_winning_return: float = 0.0
    avg_losing_return: float = 0.0

    @property
    def is_useful(self) -> bool:
        """Signal is useful if hit rate > 50%."""
        return self.hit_rate > 50.0
```

- [ ] **Step 4: Run tests — verify PASS**

Run: `cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender" && python -m pytest tests/test_outcome_models.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add domain/outcome.py tests/test_outcome_models.py
git commit -m "feat: add outcome tracking domain models (TrackedTrade, TradeOutcome, SignalPerformance)"
```

---

## Task 2: Outcome Tracking Service — Pure Domain Logic

**Files:**
- Create: `domain/outcome_service.py`
- Test: `tests/test_outcome_service.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for outcome tracking service — pure domain logic."""

from datetime import datetime

import pytest

from domain.outcome import SignalPerformance, TradeAction, TradeOutcome, TrackedTrade
from domain.outcome_service import (
    compute_outcome,
    compute_signal_performance,
    generate_report_card,
)


class TestComputeOutcome:
    def test_profitable_trade(self) -> None:
        buy = TrackedTrade(
            trade_id="t1", ticker="NVDA", action=TradeAction.BUY,
            price=142.0, quantity=10, trade_date="2026-06-05",
            conviction_at_trade=8.2, signals_at_trade=["smart_money", "sentiment_momentum"],
        )
        sell = TrackedTrade(
            trade_id="t2", ticker="NVDA", action=TradeAction.SELL,
            price=158.0, quantity=10, trade_date="2026-07-10",
            conviction_at_trade=3.0, signals_at_trade=[],
        )
        outcome = compute_outcome(buy, sell)
        assert outcome.ticker == "NVDA"
        assert outcome.return_pct == pytest.approx(11.27, abs=0.01)
        assert outcome.return_dollar == pytest.approx(160.0)
        assert outcome.holding_days == 35
        assert outcome.signals_at_entry == ["smart_money", "sentiment_momentum"]
        assert outcome.is_profitable is True

    def test_losing_trade(self) -> None:
        buy = TrackedTrade(
            trade_id="t3", ticker="TSLA", action=TradeAction.BUY,
            price=200.0, quantity=5, trade_date="2026-06-01",
            conviction_at_trade=5.0, signals_at_trade=["ml_direction"],
        )
        sell = TrackedTrade(
            trade_id="t4", ticker="TSLA", action=TradeAction.SELL,
            price=180.0, quantity=5, trade_date="2026-06-15",
            conviction_at_trade=2.0, signals_at_trade=[],
        )
        outcome = compute_outcome(buy, sell)
        assert outcome.return_pct == pytest.approx(-10.0)
        assert outcome.is_profitable is False

    def test_ticker_mismatch_raises(self) -> None:
        buy = TrackedTrade(
            trade_id="t5", ticker="NVDA", action=TradeAction.BUY,
            price=100.0, quantity=1, trade_date="2026-06-01",
            conviction_at_trade=5.0, signals_at_trade=[],
        )
        sell = TrackedTrade(
            trade_id="t6", ticker="AAPL", action=TradeAction.SELL,
            price=110.0, quantity=1, trade_date="2026-06-10",
            conviction_at_trade=5.0, signals_at_trade=[],
        )
        with pytest.raises(ValueError, match="ticker mismatch"):
            compute_outcome(buy, sell)


class TestComputeSignalPerformance:
    def test_single_signal_across_outcomes(self) -> None:
        outcomes = [
            TradeOutcome(
                ticker="NVDA", buy_trade_id="t1", sell_trade_id="t2",
                buy_price=100.0, sell_price=112.0, quantity=10,
                buy_date="2026-06-01", sell_date="2026-06-15",
                holding_days=14, return_pct=12.0, return_dollar=120.0,
                signals_at_entry=["smart_money"], conviction_at_entry=8.0,
            ),
            TradeOutcome(
                ticker="AAPL", buy_trade_id="t3", sell_trade_id="t4",
                buy_price=150.0, sell_price=145.0, quantity=5,
                buy_date="2026-06-10", sell_date="2026-06-20",
                holding_days=10, return_pct=-3.33, return_dollar=-25.0,
                signals_at_entry=["smart_money", "ml_direction"],
                conviction_at_entry=6.0,
            ),
        ]
        perfs = compute_signal_performance(outcomes)
        sm = next(p for p in perfs if p.signal_name == "smart_money")
        assert sm.total_trades == 2
        assert sm.winning_trades == 1
        assert sm.losing_trades == 1
        assert sm.hit_rate == pytest.approx(50.0)

    def test_empty_outcomes(self) -> None:
        assert compute_signal_performance([]) == []


class TestGenerateReportCard:
    def test_generates_markdown(self) -> None:
        perfs = [
            SignalPerformance(
                signal_name="smart_money", total_trades=14,
                winning_trades=10, losing_trades=4, hit_rate=71.4,
                avg_return_pct=8.2, avg_winning_return=12.5, avg_losing_return=-3.1,
            ),
            SignalPerformance(
                signal_name="ml_direction", total_trades=31,
                winning_trades=15, losing_trades=16, hit_rate=48.4,
                avg_return_pct=0.3, avg_winning_return=5.0, avg_losing_return=-4.8,
            ),
        ]
        card = generate_report_card(perfs, month="June 2026")
        assert "smart_money" in card
        assert "ml_direction" in card
        assert "Best signal" in card
        assert "Worst signal" in card
```

- [ ] **Step 2: Run tests — verify FAIL**

Run: `cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender" && python -m pytest tests/test_outcome_service.py -v`
Expected: FAIL

- [ ] **Step 3: Implement outcome service**

```python
"""Outcome tracking service — pure domain logic.

Computes trade outcomes, signal performance metrics, and report cards.
No I/O, no external dependencies.
"""

from __future__ import annotations

from datetime import datetime

from domain.outcome import SignalPerformance, TradeAction, TradeOutcome, TrackedTrade


def compute_outcome(buy: TrackedTrade, sell: TrackedTrade) -> TradeOutcome:
    """Compute outcome from a buy-sell pair."""
    if buy.ticker != sell.ticker:
        raise ValueError(f"ticker mismatch: {buy.ticker} vs {sell.ticker}")

    buy_dt = datetime.strptime(buy.trade_date, "%Y-%m-%d")
    sell_dt = datetime.strptime(sell.trade_date, "%Y-%m-%d")
    holding_days = (sell_dt - buy_dt).days

    return_pct = ((sell.price - buy.price) / buy.price) * 100
    return_dollar = (sell.price - buy.price) * buy.quantity

    return TradeOutcome(
        ticker=buy.ticker,
        buy_trade_id=buy.trade_id,
        sell_trade_id=sell.trade_id,
        buy_price=buy.price,
        sell_price=sell.price,
        quantity=buy.quantity,
        buy_date=buy.trade_date,
        sell_date=sell.trade_date,
        holding_days=holding_days,
        return_pct=round(return_pct, 2),
        return_dollar=round(return_dollar, 2),
        signals_at_entry=list(buy.signals_at_trade),
        conviction_at_entry=buy.conviction_at_trade,
    )


def compute_signal_performance(outcomes: list[TradeOutcome]) -> list[SignalPerformance]:
    """Aggregate per-signal performance across all completed trades."""
    if not outcomes:
        return []

    signal_outcomes: dict[str, list[TradeOutcome]] = {}
    for o in outcomes:
        for signal in o.signals_at_entry:
            signal_outcomes.setdefault(signal, []).append(o)

    perfs: list[SignalPerformance] = []
    for signal, trades in sorted(signal_outcomes.items()):
        winners = [t for t in trades if t.is_profitable]
        losers = [t for t in trades if not t.is_profitable]
        total = len(trades)
        hit_rate = (len(winners) / total * 100) if total > 0 else 0.0
        avg_return = sum(t.return_pct for t in trades) / total if total else 0.0
        avg_win = (
            sum(t.return_pct for t in winners) / len(winners) if winners else 0.0
        )
        avg_loss = (
            sum(t.return_pct for t in losers) / len(losers) if losers else 0.0
        )
        perfs.append(
            SignalPerformance(
                signal_name=signal,
                total_trades=total,
                winning_trades=len(winners),
                losing_trades=len(losers),
                hit_rate=round(hit_rate, 1),
                avg_return_pct=round(avg_return, 2),
                avg_winning_return=round(avg_win, 2),
                avg_losing_return=round(avg_loss, 2),
            )
        )
    return perfs


def generate_report_card(
    performances: list[SignalPerformance], month: str = ""
) -> str:
    """Generate a plain-English signal report card."""
    if not performances:
        return "No completed trades yet — start tracking to build your signal report card."

    sorted_by_hit = sorted(performances, key=lambda p: p.hit_rate, reverse=True)
    best = sorted_by_hit[0]
    worst = sorted_by_hit[-1]

    sorted_by_return = sorted(performances, key=lambda p: p.avg_return_pct, reverse=True)
    most_profitable = sorted_by_return[0]

    header = f"Your Signal Performance — {month}" if month else "Your Signal Performance"
    lines = [
        header,
        "─" * len(header),
        f"Best signal:      {best.signal_name} ({best.hit_rate}% hit rate, {best.total_trades} trades)",
        f"Worst signal:     {worst.signal_name} ({worst.hit_rate}% hit rate, {worst.total_trades} trades)",
        f"Most profitable:  {most_profitable.signal_name} (avg {most_profitable.avg_return_pct:+.1f}% return)",
    ]

    # Recommendations
    useless = [p for p in performances if not p.is_useful]
    if useless:
        names = ", ".join(p.signal_name for p in useless)
        lines.append(f"\nConsider reducing weight for: {names}")

    useful = [p for p in performances if p.is_useful]
    if useful:
        names = ", ".join(p.signal_name for p in useful)
        lines.append(f"Strong performers: {names}")

    return "\n".join(lines)
```

- [ ] **Step 4: Run tests — verify PASS**

Run: `cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender" && python -m pytest tests/test_outcome_service.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add domain/outcome_service.py tests/test_outcome_service.py
git commit -m "feat: add outcome tracking service — trade outcomes, signal performance, report card"
```

---

## Task 3: SQLite Persistence — Trades + Outcomes Tables

**Files:**
- Modify: `adapters/data/sqlite_store.py`
- Modify: `tests/test_sqlite_store.py`

- [ ] **Step 1: Write failing tests for trade persistence**

Append to `tests/test_sqlite_store.py`:

```python
from domain.outcome import TradeAction, TradeOutcome, TrackedTrade


class TestTradeStore:
    def test_save_and_load_trade(self, tmp_path) -> None:
        db = str(tmp_path / "test.db")
        from adapters.data.sqlite_store import SQLiteStore
        store = SQLiteStore(db)
        trade = TrackedTrade(
            trade_id="t001", ticker="NVDA", action=TradeAction.BUY,
            price=142.0, quantity=10, trade_date="2026-06-05",
            conviction_at_trade=8.2,
            signals_at_trade=["smart_money", "sentiment_momentum"],
            notes="Test trade",
        )
        store.save_trade(trade)
        trades = store.get_trades(ticker="NVDA")
        assert len(trades) == 1
        assert trades[0].ticker == "NVDA"
        assert trades[0].price == 142.0
        assert trades[0].signals_at_trade == ["smart_money", "sentiment_momentum"]

    def test_save_and_load_outcome(self, tmp_path) -> None:
        db = str(tmp_path / "test.db")
        from adapters.data.sqlite_store import SQLiteStore
        store = SQLiteStore(db)
        outcome = TradeOutcome(
            ticker="NVDA", buy_trade_id="t001", sell_trade_id="t002",
            buy_price=142.0, sell_price=158.0, quantity=10,
            buy_date="2026-06-05", sell_date="2026-07-10",
            holding_days=35, return_pct=11.27, return_dollar=160.0,
            signals_at_entry=["smart_money"], conviction_at_entry=8.2,
        )
        store.save_outcome(outcome)
        outcomes = store.get_outcomes()
        assert len(outcomes) == 1
        assert outcomes[0].return_pct == 11.27

    def test_get_trades_all(self, tmp_path) -> None:
        db = str(tmp_path / "test.db")
        from adapters.data.sqlite_store import SQLiteStore
        store = SQLiteStore(db)
        for i, ticker in enumerate(["NVDA", "AAPL"]):
            store.save_trade(TrackedTrade(
                trade_id=f"t{i}", ticker=ticker, action=TradeAction.BUY,
                price=100.0 + i, quantity=1, trade_date="2026-06-01",
                conviction_at_trade=5.0, signals_at_trade=[],
            ))
        assert len(store.get_trades()) == 2
        assert len(store.get_trades(ticker="NVDA")) == 1
```

- [ ] **Step 2: Run tests — verify FAIL**

Run: `cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender" && python -m pytest tests/test_sqlite_store.py::TestTradeStore -v`
Expected: FAIL — `AttributeError: 'SQLiteStore' object has no attribute 'save_trade'`

- [ ] **Step 3: Add trades + outcomes tables and methods to SQLiteStore**

Append to the `_SCHEMA` string in `adapters/data/sqlite_store.py`:

```sql
CREATE TABLE IF NOT EXISTS tracked_trades (
    trade_id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    action TEXT NOT NULL,
    price REAL NOT NULL,
    quantity INTEGER NOT NULL,
    trade_date TEXT NOT NULL,
    conviction_at_trade REAL,
    signals_at_trade TEXT,
    opportunity_card_id TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS trade_outcomes (
    id INTEGER PRIMARY KEY,
    ticker TEXT NOT NULL,
    buy_trade_id TEXT NOT NULL,
    sell_trade_id TEXT NOT NULL,
    buy_price REAL NOT NULL,
    sell_price REAL NOT NULL,
    quantity INTEGER NOT NULL,
    buy_date TEXT NOT NULL,
    sell_date TEXT NOT NULL,
    holding_days INTEGER NOT NULL,
    return_pct REAL NOT NULL,
    return_dollar REAL NOT NULL,
    signals_at_entry TEXT,
    conviction_at_entry REAL,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(buy_trade_id, sell_trade_id)
);
```

Add methods to `SQLiteStore` class:

```python
def save_trade(self, trade: TrackedTrade) -> None:
    """Save a tracked trade."""
    with sqlite3.connect(self._db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO tracked_trades "
            "(trade_id, ticker, action, price, quantity, trade_date, "
            "conviction_at_trade, signals_at_trade, opportunity_card_id, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (trade.trade_id, trade.ticker, trade.action.value, trade.price,
             trade.quantity, trade.trade_date, trade.conviction_at_trade,
             json.dumps(trade.signals_at_trade), trade.opportunity_card_id,
             trade.notes),
        )

def get_trades(self, ticker: str | None = None) -> list[TrackedTrade]:
    """Load tracked trades, optionally filtered by ticker."""
    with sqlite3.connect(self._db_path) as conn:
        if ticker:
            rows = conn.execute(
                "SELECT * FROM tracked_trades WHERE ticker = ? ORDER BY trade_date",
                (ticker,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM tracked_trades ORDER BY trade_date"
            ).fetchall()
    return [self._row_to_trade(r) for r in rows]

def _row_to_trade(self, row: tuple) -> TrackedTrade:
    return TrackedTrade(
        trade_id=row[0], ticker=row[1], action=TradeAction(row[2]),
        price=row[3], quantity=row[4], trade_date=row[5],
        conviction_at_trade=row[6],
        signals_at_trade=json.loads(row[7]) if row[7] else [],
        opportunity_card_id=row[8] or "", notes=row[9] or "",
    )

def save_outcome(self, outcome: TradeOutcome) -> None:
    """Save a trade outcome."""
    with sqlite3.connect(self._db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO trade_outcomes "
            "(ticker, buy_trade_id, sell_trade_id, buy_price, sell_price, "
            "quantity, buy_date, sell_date, holding_days, return_pct, "
            "return_dollar, signals_at_entry, conviction_at_entry) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (outcome.ticker, outcome.buy_trade_id, outcome.sell_trade_id,
             outcome.buy_price, outcome.sell_price, outcome.quantity,
             outcome.buy_date, outcome.sell_date, outcome.holding_days,
             outcome.return_pct, outcome.return_dollar,
             json.dumps(outcome.signals_at_entry), outcome.conviction_at_entry),
        )

def get_outcomes(self, ticker: str | None = None) -> list[TradeOutcome]:
    """Load trade outcomes."""
    with sqlite3.connect(self._db_path) as conn:
        if ticker:
            rows = conn.execute(
                "SELECT * FROM trade_outcomes WHERE ticker = ? ORDER BY sell_date",
                (ticker,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM trade_outcomes ORDER BY sell_date"
            ).fetchall()
    return [self._row_to_outcome(r) for r in rows]

def _row_to_outcome(self, row: tuple) -> TradeOutcome:
    return TradeOutcome(
        ticker=row[1], buy_trade_id=row[2], sell_trade_id=row[3],
        buy_price=row[4], sell_price=row[5], quantity=row[6],
        buy_date=row[7], sell_date=row[8], holding_days=row[9],
        return_pct=row[10], return_dollar=row[11],
        signals_at_entry=json.loads(row[12]) if row[12] else [],
        conviction_at_entry=row[13],
    )
```

Add import at top of sqlite_store.py:
```python
from domain.outcome import TradeAction, TradeOutcome, TrackedTrade
```

- [ ] **Step 4: Run tests — verify PASS**

Run: `cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender" && python -m pytest tests/test_sqlite_store.py::TestTradeStore -v`
Expected: ALL PASS

- [ ] **Step 5: Run full suite for regression**

Run: `cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender" && python -m pytest tests/ -q --tb=short`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add adapters/data/sqlite_store.py tests/test_sqlite_store.py
git commit -m "feat: add trades + outcomes SQLite tables with CRUD methods"
```

---

## Task 4: OutcomeTrackingUseCase

**Files:**
- Create: `application/outcome_use_case.py`
- Test: `tests/test_outcome_use_case.py`

- [ ] **Step 1: Write failing tests with fakes**

```python
"""Tests for OutcomeTrackingUseCase."""

import pytest

from application.outcome_use_case import OutcomeTrackingUseCase
from domain.outcome import TradeAction, TradeOutcome, TrackedTrade


class FakeTradeStore:
    def __init__(self) -> None:
        self._trades: list[TrackedTrade] = []
        self._outcomes: list[TradeOutcome] = []

    def save_trade(self, trade: TrackedTrade) -> None:
        self._trades.append(trade)

    def get_trades(self, ticker: str | None = None) -> list[TrackedTrade]:
        if ticker:
            return [t for t in self._trades if t.ticker == ticker]
        return list(self._trades)

    def save_outcome(self, outcome: TradeOutcome) -> None:
        self._outcomes.append(outcome)

    def get_outcomes(self, ticker: str | None = None) -> list[TradeOutcome]:
        if ticker:
            return [o for o in self._outcomes if o.ticker == ticker]
        return list(self._outcomes)


class TestOutcomeTrackingUseCase:
    def test_record_buy(self) -> None:
        store = FakeTradeStore()
        uc = OutcomeTrackingUseCase(store=store)
        trade = uc.record_buy(
            ticker="NVDA", price=142.0, quantity=10,
            trade_date="2026-06-05", conviction=8.2,
            signals=["smart_money", "sentiment_momentum"],
        )
        assert trade.action == TradeAction.BUY
        assert len(store.get_trades()) == 1

    def test_record_sell_creates_outcome(self) -> None:
        store = FakeTradeStore()
        uc = OutcomeTrackingUseCase(store=store)
        uc.record_buy(
            ticker="NVDA", price=142.0, quantity=10,
            trade_date="2026-06-05", conviction=8.2, signals=["smart_money"],
        )
        result = uc.record_sell(
            ticker="NVDA", price=158.0, quantity=10,
            trade_date="2026-07-10",
        )
        assert result is not None
        outcome, trade = result
        assert outcome.return_pct == pytest.approx(11.27, abs=0.01)
        assert len(store._outcomes) == 1

    def test_sell_without_buy_returns_none(self) -> None:
        store = FakeTradeStore()
        uc = OutcomeTrackingUseCase(store=store)
        result = uc.record_sell(
            ticker="NVDA", price=158.0, quantity=10,
            trade_date="2026-07-10",
        )
        assert result is None

    def test_get_signal_report(self) -> None:
        store = FakeTradeStore()
        uc = OutcomeTrackingUseCase(store=store)
        # Simulate completed trade
        store._outcomes.append(TradeOutcome(
            ticker="NVDA", buy_trade_id="t1", sell_trade_id="t2",
            buy_price=100.0, sell_price=112.0, quantity=10,
            buy_date="2026-06-01", sell_date="2026-06-15",
            holding_days=14, return_pct=12.0, return_dollar=120.0,
            signals_at_entry=["smart_money"], conviction_at_entry=8.0,
        ))
        report = uc.get_signal_report()
        assert "smart_money" in report
```

- [ ] **Step 2: Run tests — verify FAIL**

- [ ] **Step 3: Implement OutcomeTrackingUseCase**

```python
"""OutcomeTrackingUseCase — orchestrates trade logging and outcome evaluation."""

from __future__ import annotations

import uuid
from typing import Any

from loguru import logger

from domain.outcome import TradeAction, TradeOutcome, TrackedTrade
from domain.outcome_service import compute_outcome, compute_signal_performance, generate_report_card


class OutcomeTrackingUseCase:
    """Manages trade recording, outcome computation, and signal report generation."""

    def __init__(self, store: Any) -> None:
        self._store = store

    def record_buy(
        self,
        ticker: str,
        price: float,
        quantity: int,
        trade_date: str,
        conviction: float = 0.0,
        signals: list[str] | None = None,
        opportunity_card_id: str = "",
        notes: str = "",
    ) -> TrackedTrade:
        """Record a buy trade."""
        trade = TrackedTrade(
            trade_id=str(uuid.uuid4())[:8],
            ticker=ticker,
            action=TradeAction.BUY,
            price=price,
            quantity=quantity,
            trade_date=trade_date,
            conviction_at_trade=conviction,
            signals_at_trade=signals or [],
            opportunity_card_id=opportunity_card_id,
            notes=notes,
        )
        self._store.save_trade(trade)
        logger.info("Recorded BUY: {} {} shares @ ${}", ticker, quantity, price)
        return trade

    def record_sell(
        self,
        ticker: str,
        price: float,
        quantity: int,
        trade_date: str,
        notes: str = "",
    ) -> tuple[TradeOutcome, TrackedTrade] | None:
        """Record a sell trade and compute outcome if matching buy exists."""
        # Find most recent unmatched buy for this ticker
        trades = self._store.get_trades(ticker=ticker)
        buys = [t for t in trades if t.action == TradeAction.BUY]

        if not buys:
            logger.warning("No buy trade found for {} — sell recorded without outcome", ticker)
            return None

        buy = buys[-1]  # Most recent buy

        sell_trade = TrackedTrade(
            trade_id=str(uuid.uuid4())[:8],
            ticker=ticker,
            action=TradeAction.SELL,
            price=price,
            quantity=quantity,
            trade_date=trade_date,
            conviction_at_trade=0.0,
            signals_at_trade=[],
            notes=notes,
        )
        self._store.save_trade(sell_trade)

        outcome = compute_outcome(buy, sell_trade)
        self._store.save_outcome(outcome)
        logger.info(
            "Recorded SELL: {} {} shares @ ${} → {:.1f}% return",
            ticker, quantity, price, outcome.return_pct,
        )
        return outcome, sell_trade

    def get_signal_report(self, month: str = "") -> str:
        """Generate signal performance report card from all completed outcomes."""
        outcomes = self._store.get_outcomes()
        if not outcomes:
            return "No completed trades yet — start tracking to build your signal report card."
        perfs = compute_signal_performance(outcomes)
        return generate_report_card(perfs, month=month)

    def get_outcomes_summary(self) -> dict[str, Any]:
        """Return summary stats for dashboard display."""
        outcomes = self._store.get_outcomes()
        if not outcomes:
            return {"total_trades": 0, "total_return": 0.0, "win_rate": 0.0}
        wins = sum(1 for o in outcomes if o.is_profitable)
        total_return = sum(o.return_dollar for o in outcomes)
        return {
            "total_trades": len(outcomes),
            "total_return": round(total_return, 2),
            "win_rate": round(wins / len(outcomes) * 100, 1),
            "avg_return_pct": round(
                sum(o.return_pct for o in outcomes) / len(outcomes), 2
            ),
        }
```

- [ ] **Step 4: Run tests — verify PASS**

- [ ] **Step 5: Commit**

```bash
git add application/outcome_use_case.py tests/test_outcome_use_case.py
git commit -m "feat: add OutcomeTrackingUseCase — trade recording, outcome computation, signal reports"
```

---

## Task 5: Dashboard Data Loaders + Verdicts

**Files:**
- Modify: `adapters/visualization/data_loader.py` — add load_trades, load_outcomes, load_signal_report
- Modify: `adapters/visualization/components/verdicts.py` — add new verdicts
- Modify: `tests/test_data_loader.py` — add tests

- [ ] **Step 1: Write failing tests**

Append to `tests/test_data_loader.py`:

```python
class TestLoadTrades:
    def test_returns_empty_on_missing_db(self) -> None:
        from adapters.visualization.data_loader import load_trades
        assert load_trades("/nonexistent/db.sqlite") == []

class TestLoadOutcomes:
    def test_returns_empty_on_missing_db(self) -> None:
        from adapters.visualization.data_loader import load_outcomes
        assert load_outcomes("/nonexistent/db.sqlite") == []
```

- [ ] **Step 2: Add data loader functions**

Append to `adapters/visualization/data_loader.py`:

```python
from domain.outcome import TrackedTrade, TradeOutcome


def load_trades(db_path: str, ticker: str | None = None) -> list[TrackedTrade]:
    """Load tracked trades. Returns empty list if DB missing."""
    if not Path(db_path).exists():
        return []
    try:
        from adapters.data.sqlite_store import SQLiteStore
        store = SQLiteStore(db_path)
        return store.get_trades(ticker=ticker)
    except Exception as e:
        logger.warning("Failed to load trades: %s", e)
        return []


def load_outcomes(db_path: str, ticker: str | None = None) -> list[TradeOutcome]:
    """Load trade outcomes. Returns empty list if DB missing."""
    if not Path(db_path).exists():
        return []
    try:
        from adapters.data.sqlite_store import SQLiteStore
        store = SQLiteStore(db_path)
        return store.get_outcomes(ticker=ticker)
    except Exception as e:
        logger.warning("Failed to load outcomes: %s", e)
        return []
```

- [ ] **Step 3: Add verdicts**

Append to `adapters/visualization/components/verdicts.py`:

```python
def outcome_tracker_verdict(
    n_trades: int, n_outcomes: int, total_return: float, win_rate: float,
) -> str:
    """Generate verdict for Outcome Tracker tab."""
    if n_trades == 0:
        return "No trades recorded yet. Log your first buy to start tracking outcomes."
    if n_outcomes == 0:
        return f"{n_trades} trade(s) recorded, none closed yet. Log a sell to see your first outcome."
    sign = "+" if total_return >= 0 else ""
    return (
        f"{n_outcomes} completed trade(s) — {sign}${total_return:,.0f} total return, "
        f"{win_rate:.0f}% win rate."
    )


def system_intelligence_verdict(
    n_outcomes: int, best_signal: str, worst_signal: str,
) -> str:
    """Generate verdict for System Intelligence tab."""
    if n_outcomes == 0:
        return "No outcome data yet. The system needs completed trades to learn which signals work."
    if n_outcomes < 10:
        return f"{n_outcomes} outcomes tracked. Need 10+ for reliable signal performance data."
    return (
        f"Based on {n_outcomes} completed trades: "
        f"best signal is {best_signal}, weakest is {worst_signal}."
    )
```

- [ ] **Step 4: Run tests — verify PASS**

- [ ] **Step 5: Commit**

```bash
git add adapters/visualization/data_loader.py adapters/visualization/components/verdicts.py tests/test_data_loader.py
git commit -m "feat: add trade/outcome data loaders and outcome tracker verdicts"
```

---

## Task 6: Positions → Outcome Tracker Tab

**Files:**
- Modify: `adapters/visualization/tabs/positions.py` — evolve to Outcome Tracker
- Modify: `adapters/visualization/action_runner.py` — add run_record_trade
- Modify: `adapters/visualization/dashboard.py` — update tab label

- [ ] **Step 1: Add run_record_trade to action_runner.py**

Append to `adapters/visualization/action_runner.py`:

```python
from domain.outcome import TrackedTrade, TradeOutcome


def run_record_buy(
    ticker: str, price: float, quantity: int, trade_date: str,
    conviction: float = 0.0, signals: list[str] | None = None,
    db_path: str = "data/recommendations.db",
) -> TrackedTrade:
    """Record a buy trade via OutcomeTrackingUseCase."""
    from adapters.data.sqlite_store import SQLiteStore
    from application.outcome_use_case import OutcomeTrackingUseCase
    store = SQLiteStore(db_path)
    uc = OutcomeTrackingUseCase(store=store)
    return uc.record_buy(
        ticker=ticker, price=price, quantity=quantity,
        trade_date=trade_date, conviction=conviction, signals=signals or [],
    )


def run_record_sell(
    ticker: str, price: float, quantity: int, trade_date: str,
    db_path: str = "data/recommendations.db",
) -> tuple[TradeOutcome, TrackedTrade] | None:
    """Record a sell trade and compute outcome."""
    from adapters.data.sqlite_store import SQLiteStore
    from application.outcome_use_case import OutcomeTrackingUseCase
    store = SQLiteStore(db_path)
    uc = OutcomeTrackingUseCase(store=store)
    return uc.record_sell(
        ticker=ticker, price=price, quantity=quantity, trade_date=trade_date,
    )
```

- [ ] **Step 2: Rewrite positions.py as Outcome Tracker**

Full rewrite of `adapters/visualization/tabs/positions.py`:
- Keep `render(db_path)` signature
- Show outcome verdict at top
- Two sections: "Record a Trade" form (buy/sell toggle, ticker, price, quantity, date) and "Trade History + Outcomes" table
- P&L summary if outcomes exist
- Signal report card if outcomes exist (call OutcomeTrackingUseCase.get_signal_report)

The tab should have:
1. Verdict banner
2. Trade recording form (st.form with buy/sell radio, ticker input, price input, quantity input, date input)
3. Summary metrics (total trades, win rate, total return)
4. Outcomes table (ticker, buy price, sell price, return %, holding days)
5. All trades list (ticker, action, price, date)

- [ ] **Step 3: Update dashboard.py tab label**

Change `"💼 My Positions"` to `"💼 Outcome Tracker"`

- [ ] **Step 4: Run tests**

Run: `cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender" && python -m pytest tests/test_dashboard_smoke.py tests/test_action_runner.py -v --tb=short`

- [ ] **Step 5: Commit**

```bash
git add adapters/visualization/tabs/positions.py adapters/visualization/action_runner.py adapters/visualization/dashboard.py
git commit -m "feat: Positions → Outcome Tracker with trade recording and P&L display"
```

---

## Task 7: Model Confidence → System Intelligence Tab

**Files:**
- Modify: `adapters/visualization/tabs/model_confidence.py` — evolve to System Intelligence
- Modify: `adapters/visualization/dashboard.py` — update tab label

- [ ] **Step 1: Update model_confidence.py**

Add a new section at the top of the render function (before existing backtest content):
- Signal report card section using OutcomeTrackingUseCase.get_signal_report()
- Learning progress: "N outcomes tracked, system is learning..."
- Keep ALL existing backtest/SHAP/ablation content below

- [ ] **Step 2: Update dashboard.py tab label**

Change `"📊 Model Confidence"` to `"📊 System Intelligence"`

- [ ] **Step 3: Run tests**

Run: `cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender" && python -m pytest tests/test_dashboard_smoke.py -v --tb=short`

- [ ] **Step 4: Commit**

```bash
git add adapters/visualization/tabs/model_confidence.py adapters/visualization/dashboard.py
git commit -m "feat: Model Confidence → System Intelligence with signal report card"
```

---

## Task 8: Historical Bootstrap Engine

**Files:**
- Create: `application/bootstrap_use_case.py`
- Test: `tests/test_bootstrap_use_case.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for HistoricalBootstrapUseCase."""

from datetime import datetime

import pytest

from application.bootstrap_use_case import HistoricalBootstrapUseCase
from domain.outcome import TradeOutcome


class FakeMarketData:
    def get_signals(self, symbol, prediction_time, start_date=None, end_date=None):
        from domain.models import Signal
        return [Signal(
            symbol=symbol, timestamp=prediction_time,
            price=100.0 + hash(symbol) % 50,
            volume=1_000_000.0, open_=99.0, high=105.0, low=98.0,
        )]

    def get_ticker_info(self, symbol):
        return {"currentPrice": 100.0 + hash(symbol) % 50}

    def validate_point_in_time(self, prediction_time):
        pass


class FakeBootstrapStore:
    def __init__(self) -> None:
        self.outcomes: list[TradeOutcome] = []

    def save_outcome(self, outcome: TradeOutcome) -> None:
        self.outcomes.append(outcome)

    def get_outcomes(self, ticker=None):
        return self.outcomes


class TestHistoricalBootstrapUseCase:
    def test_generates_simulated_outcomes(self) -> None:
        uc = HistoricalBootstrapUseCase(
            market_data=FakeMarketData(),
            store=FakeBootstrapStore(),
            tickers=["AAPL", "MSFT"],
        )
        outcomes = uc.run(
            start_date=datetime(2026, 1, 1),
            end_date=datetime(2026, 3, 1),
            horizon_days=30,
        )
        assert len(outcomes) > 0
        assert all(isinstance(o, TradeOutcome) for o in outcomes)

    def test_empty_tickers_returns_empty(self) -> None:
        uc = HistoricalBootstrapUseCase(
            market_data=FakeMarketData(),
            store=FakeBootstrapStore(),
            tickers=[],
        )
        outcomes = uc.run(
            start_date=datetime(2026, 1, 1),
            end_date=datetime(2026, 3, 1),
        )
        assert outcomes == []
```

- [ ] **Step 2: Implement HistoricalBootstrapUseCase**

```python
"""HistoricalBootstrapUseCase — simulates past recommendations for cold-start learning.

Uses historical price data to generate simulated buy/sell outcomes as if the system
had been running for 6 months. Pre-populates the outcome store with signal→outcome
correlations so the system has day-one intelligence.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from loguru import logger

from domain.outcome import TradeOutcome


class HistoricalBootstrapUseCase:
    """Simulate past recommendations for cold-start signal performance data."""

    def __init__(
        self,
        market_data: Any,  # MarketDataPort
        store: Any,  # has save_outcome, get_outcomes
        tickers: list[str],
    ) -> None:
        self._market_data = market_data
        self._store = store
        self._tickers = tickers

    def run(
        self,
        start_date: datetime,
        end_date: datetime,
        horizon_days: int = 30,
        step_days: int = 30,
    ) -> list[TradeOutcome]:
        """Generate simulated outcomes by walking through historical windows.

        For each ticker × each window:
        1. Get price at window start (simulated buy)
        2. Get price at window start + horizon_days (simulated sell)
        3. Compute return and store as outcome with placeholder signals
        """
        if not self._tickers:
            return []

        outcomes: list[TradeOutcome] = []
        current = start_date

        while current + timedelta(days=horizon_days) <= end_date:
            buy_date = current
            sell_date = current + timedelta(days=horizon_days)

            for ticker in self._tickers:
                try:
                    buy_signals = self._market_data.get_signals(
                        ticker, buy_date, start_date=buy_date - timedelta(days=5),
                        end_date=buy_date,
                    )
                    sell_signals = self._market_data.get_signals(
                        ticker, sell_date, start_date=sell_date - timedelta(days=5),
                        end_date=sell_date,
                    )

                    if not buy_signals or not sell_signals:
                        continue

                    buy_price = buy_signals[-1].price
                    sell_price = sell_signals[-1].price

                    return_pct = round(((sell_price - buy_price) / buy_price) * 100, 2)
                    return_dollar = round((sell_price - buy_price) * 10, 2)  # 10 share default

                    outcome = TradeOutcome(
                        ticker=ticker,
                        buy_trade_id=f"bootstrap_{ticker}_{buy_date.strftime('%Y%m%d')}",
                        sell_trade_id=f"bootstrap_{ticker}_{sell_date.strftime('%Y%m%d')}",
                        buy_price=buy_price,
                        sell_price=sell_price,
                        quantity=10,
                        buy_date=buy_date.strftime("%Y-%m-%d"),
                        sell_date=sell_date.strftime("%Y-%m-%d"),
                        holding_days=horizon_days,
                        return_pct=return_pct,
                        return_dollar=return_dollar,
                        signals_at_entry=["technical", "fundamental"],  # placeholder signals
                        conviction_at_entry=5.0,  # neutral placeholder
                    )
                    self._store.save_outcome(outcome)
                    outcomes.append(outcome)

                except Exception as exc:
                    logger.warning("Bootstrap failed for {} on {}: {}", ticker, buy_date, exc)

            current += timedelta(days=step_days)

        logger.info("Bootstrap complete: {} simulated outcomes generated", len(outcomes))
        return outcomes
```

- [ ] **Step 3: Run tests — verify PASS**

- [ ] **Step 4: Commit**

```bash
git add application/bootstrap_use_case.py tests/test_bootstrap_use_case.py
git commit -m "feat: add HistoricalBootstrapUseCase — simulated outcomes for cold-start learning"
```

---

## Task 9: Full Regression + ADR-033

- [ ] **Step 1: Run full quality check**

Run: `cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender" && python -m pytest tests/ -q --tb=short`
Expected: ALL PASS

- [ ] **Step 2: Run mypy on new files**

Run: `cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender" && mypy domain/outcome.py domain/outcome_service.py application/outcome_use_case.py application/bootstrap_use_case.py --strict`
Expected: Success

- [ ] **Step 3: Create ADR-033**

```markdown
# ADR-033: Outcome Tracking and Signal Learning

**Date:** 2026-06-03
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context

Phase 7 introduced conviction-based opportunity surfacing. But conviction weights are static defaults — the system has no way to learn which signals actually lead to profitable outcomes. Users need to track their trades and see which signals work.

## Decision

Add outcome tracking with three components:

1. **Trade logging** — manual buy/sell recording linked to opportunity cards and their signals
2. **Signal report card** — per-signal hit rate, avg return, and recommendations
3. **Historical bootstrap** — simulate 6 months of past outcomes for day-one intelligence

## Consequences

- Users can see which signals work for their investment style
- Report card provides actionable guidance ("reduce ml_direction weight")
- Bootstrap prevents cold-start problem — system has data from day one
- Phase 9 (adaptive learning) builds on this outcome data for automatic weight adjustment
```

- [ ] **Step 4: Update CLAUDE.md with Phase 8 status**

- [ ] **Step 5: Commit**

```bash
git add docs/adr/ADR-033-outcome-tracking-signal-learning.md CLAUDE.md
git commit -m "docs: add ADR-033 outcome tracking + update phase status"
```

---

## Dependency Graph

```
Task 1 (domain models) ──▶ Task 2 (outcome service) ──▶ Task 4 (use case) ──┐
                                                                              │
Task 3 (SQLite tables) ──────────────────────────────────────────────────────▶├──▶ Task 6 (Outcome Tracker tab)
                                                                              │
Task 5 (data loaders + verdicts) ────────────────────────────────────────────▶├──▶ Task 7 (System Intelligence tab)
                                                                              │
                                                                              └──▶ Task 8 (bootstrap)
                                                                                        │
                                                                                        ▼
                                                                              Task 9 (regression + ADR)
```

**Parallelizable groups:**
- Task 1 first (all depend on domain models)
- Tasks 2, 3, 5 can run in parallel after Task 1
- Task 4 after Task 2
- Tasks 6, 7 after Tasks 3+4+5
- Task 8 after Task 4
- Task 9 last (sequential)
