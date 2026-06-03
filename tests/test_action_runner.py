"""Tests for action runner — progress-tracked use case execution."""

from __future__ import annotations

import os
import tempfile

from adapters.visualization.action_runner import run_monitor_holdings


class TestRunMonitorHoldings:
    def test_calls_progress_callback(self) -> None:
        progress_calls: list[tuple[float, str]] = []

        def track(pct: float, msg: str) -> None:
            progress_calls.append((pct, msg))

        from adapters.data.sqlite_store import SQLiteStore
        from domain.models import Holding

        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            store = SQLiteStore(db_path)
            store.add_holding(
                Holding(
                    symbol="AAPL",
                    quantity=10,
                    purchase_price=150.0,
                    purchase_date="2026-01-01",
                    notes="",
                )
            )
            signals = run_monitor_holdings(
                db_path=db_path,
                progress_callback=track,
            )
            assert len(progress_calls) >= 2
            assert progress_calls[-1][0] == 1.0
            assert isinstance(signals, list)

    def test_empty_holdings_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            from adapters.data.sqlite_store import SQLiteStore

            SQLiteStore(db_path)  # create empty DB
            signals = run_monitor_holdings(db_path=db_path)
            assert signals == []


class TestRunFullCycle:
    def test_importable_and_callable(self) -> None:
        from adapters.visualization.action_runner import run_full_cycle

        assert callable(run_full_cycle)

    def test_signature_accepts_progress_callback(self) -> None:
        import inspect

        from adapters.visualization.action_runner import run_full_cycle

        sig = inspect.signature(run_full_cycle)
        assert "progress_callback" in sig.parameters
        assert "db_path" in sig.parameters
        assert "market" in sig.parameters


class TestRunTournament:
    def test_importable_and_callable(self) -> None:
        from adapters.visualization.action_runner import run_tournament

        assert callable(run_tournament)


class TestRunBacktest:
    def test_importable_and_callable(self) -> None:
        from adapters.visualization.action_runner import run_backtest

        assert callable(run_backtest)
