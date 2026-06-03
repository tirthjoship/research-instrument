"""Progress-tracked wrappers for running use cases from the dashboard.

Each function wraps a use case with stage-based progress reporting.
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from domain.models import SellSignal


def run_monitor_holdings(
    db_path: str = "data/recommendations.db",
    market: str = "us",
    progress_callback: Callable[[float, str], None] | None = None,
) -> list[SellSignal]:
    """Check all holdings for sell signals with progress tracking.

    Stages: Load holdings (30%) → Check prices (60%) → Analyze (100%).
    """
    _update = progress_callback or (lambda p, m: None)

    from adapters.data.sqlite_store import SQLiteStore

    _update(0.1, "Loading holdings...")
    store = SQLiteStore(db_path)
    holdings = store.get_holdings()

    if not holdings:
        _update(1.0, "No holdings to check.")
        return []

    _update(0.3, f"Checking {len(holdings)} holdings...")

    from application.monitor_holdings import MonitorHoldingsUseCase

    def get_price_stub(symbol: str) -> float:
        """Stub price getter — returns purchase price (no live API in dashboard)."""
        for h in holdings:
            if h.symbol == symbol:
                return h.purchase_price
        return 0.0

    from config.loader import load_market_config

    config = load_market_config(market)
    risk_config = config.get("risk", {})
    stop_loss = risk_config.get("stop_loss_threshold", -0.08)

    _update(0.6, "Analyzing sell signals...")
    use_case = MonitorHoldingsUseCase(
        holdings=store,
        get_current_price=get_price_stub,
        stop_loss_threshold=stop_loss,
    )

    signals = use_case.execute(datetime.now())
    _update(1.0, f"Done — {len(signals)} signal(s) found.")
    return signals


def run_add_holding(
    symbol: str,
    quantity: float,
    price: float,
    notes: str = "",
    db_path: str = "data/recommendations.db",
) -> None:
    """Add a holding to the portfolio via SQLite."""
    from adapters.data.sqlite_store import SQLiteStore
    from domain.models import Holding

    store = SQLiteStore(db_path)
    holding = Holding(
        symbol=symbol.upper(),
        quantity=quantity,
        purchase_price=price,
        purchase_date=datetime.now().strftime("%Y-%m-%d"),
        notes=notes,
    )
    store.add_holding(holding)


def run_add_watchlist(
    symbol: str,
    notes: str = "",
    db_path: str = "data/recommendations.db",
) -> None:
    """Add a symbol to the watchlist."""
    from adapters.data.sqlite_store import SQLiteStore

    store = SQLiteStore(db_path)
    store.add_watchlist(symbol.upper(), notes=notes)
