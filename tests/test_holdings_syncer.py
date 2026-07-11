"""Unit tests for holdings_syncer.py."""

from __future__ import annotations

import json

import pytest

from adapters.data.sqlite_store import SQLiteStore
from adapters.visualization import holdings_syncer


@pytest.fixture
def temp_env(tmp_path, monkeypatch):
    # Set up temp paths
    db_file = tmp_path / "test_recs.db"
    personal_dir = tmp_path / "personal"
    holdings_csv = personal_dir / "holdings.csv"
    history_json = personal_dir / "upload_history.json"
    brief_history = personal_dir / "brief_history"

    monkeypatch.setattr(holdings_syncer, "DB_PATH", str(db_file))
    monkeypatch.setattr(holdings_syncer, "PERSONAL_DIR", str(personal_dir))
    monkeypatch.setattr(holdings_syncer, "HOLDINGS_CSV_PATH", str(holdings_csv))
    monkeypatch.setattr(holdings_syncer, "UPLOAD_HISTORY_PATH", str(history_json))
    monkeypatch.setattr(holdings_syncer, "BRIEF_HISTORY_DIR", str(brief_history))

    # Eagerly initialize SQLite schema
    store = SQLiteStore(str(db_file))

    return {
        "db": db_file,
        "personal_dir": personal_dir,
        "holdings_csv": holdings_csv,
        "history_json": history_json,
        "brief_history": brief_history,
        "store": store,
    }


def test_save_and_sync_holdings(temp_env):
    csv_content = (
        "symbol,quantity,book value (cad),exchange,account type\n"
        "AAPL,10,1500.0,NASDAQ,TFSA\n"
        "RIVN,50,750.0,NASDAQ,Margin\n"
    )

    holdings_syncer.save_and_sync_holdings(csv_content, "user_portfolio.csv")

    # 1. Check CSV files are written
    assert temp_env["holdings_csv"].exists()
    assert temp_env["holdings_csv"].read_text() == csv_content

    # Check timestamped backup CSV exists
    backups = list(temp_env["brief_history"].glob("holdings_*.csv"))
    assert len(backups) == 1
    assert backups[0].read_text() == csv_content

    # 2. Check DB sync
    store = temp_env["store"]
    db_holdings = store.get_holdings()
    assert len(db_holdings) == 2

    aapl = store.get_holding("AAPL")
    assert aapl is not None
    assert aapl.quantity == 10.0
    assert aapl.purchase_price == 150.0  # 1500 / 10
    assert aapl.notes == "TFSA"

    rivn = store.get_holding("RIVN")
    assert rivn is not None
    assert rivn.quantity == 50.0
    assert rivn.purchase_price == 15.0  # 750 / 50
    assert rivn.notes == "Margin"

    # 3. Check upload history
    assert temp_env["history_json"].exists()
    history = json.loads(temp_env["history_json"].read_text())
    assert len(history) == 1
    assert history[0]["filename"] == "user_portfolio.csv"
    assert history[0]["positions_count"] == 2
    assert history[0]["total_cost_basis"] == 2250.0
    assert "timestamp" in history[0]


def test_rebuild_weekly_brief_cached_invokes_cli(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(cmd, check):  # type: ignore[no-untyped-def]
        calls.append(cmd)

    monkeypatch.setattr(holdings_syncer.subprocess, "run", fake_run)

    holdings_syncer.rebuild_weekly_brief_cached()

    assert len(calls) == 1
    assert "--use-cache" in calls[0]
    assert "weekly-brief" in calls[0]


def test_save_and_sync_holdings_overwrites_existing(temp_env):
    store = temp_env["store"]
    from domain.models import Holding as DomainHolding

    store.add_holding(DomainHolding("MSFT", 5.0, 300.0, "2026-01-01"))

    assert len(store.get_holdings()) == 1

    csv_content = (
        "symbol,quantity,book value (cad),exchange,account type\n"
        "AAPL,10,1500.0,NASDAQ,TFSA\n"
    )
    holdings_syncer.save_and_sync_holdings(csv_content, "new.csv")

    db_holdings = store.get_holdings()
    assert len(db_holdings) == 1
    assert db_holdings[0].symbol == "AAPL"


def test_rebuild_weekly_brief_cached_accepts_session_paths(monkeypatch, tmp_path):
    """A session/temp holdings CSV + out path must override the personal
    defaults — the public upload path rebuilds outside data/personal/."""
    calls: list[list[str]] = []

    def fake_run(cmd, check):  # type: ignore[no-untyped-def]
        calls.append(cmd)

    monkeypatch.setattr(holdings_syncer.subprocess, "run", fake_run)

    session_csv = tmp_path / "holdings.csv"
    session_out = tmp_path / "weekly_brief.md"

    holdings_syncer.rebuild_weekly_brief_cached(
        holdings_csv=str(session_csv), out_path=str(session_out)
    )

    assert len(calls) == 1
    cmd = calls[0]
    assert str(session_csv) in cmd
    assert str(session_out) in cmd
    assert "data/personal/holdings.csv" not in cmd
    assert "data/personal/weekly_brief.md" not in cmd
