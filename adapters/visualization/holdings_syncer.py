"""Holdings syncer utility for visualization.

Manages CSV upload synchronization with the database and triggers cached brief rebuilds.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from adapters.data.sqlite_store import SQLiteStore
from application.holdings_reader import read_holdings
from domain.models import Holding as DomainHolding

# Expose constants at module level for easy test patching
DB_PATH = "data/recommendations.db"
PERSONAL_DIR = "data/personal"
HOLDINGS_CSV_PATH = "data/personal/holdings.csv"
UPLOAD_HISTORY_PATH = "data/personal/upload_history.json"
BRIEF_HISTORY_DIR = "data/personal/brief_history"


def save_and_sync_holdings(content: str, filename: str) -> None:
    """Save the CSV holdings content and synchronize it to the database."""
    Path(PERSONAL_DIR).mkdir(parents=True, exist_ok=True)
    holdings_csv = Path(HOLDINGS_CSV_PATH)
    holdings_csv.write_text(content, encoding="utf-8")

    # Save a timestamped copy
    Path(BRIEF_HISTORY_DIR).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    history_csv = Path(BRIEF_HISTORY_DIR) / f"holdings_{timestamp}.csv"
    history_csv.write_text(content, encoding="utf-8")

    # Read holdings using holdings_reader
    holdings = read_holdings(str(holdings_csv))

    # Empty SQLite DB holdings table
    store = SQLiteStore(DB_PATH)
    conn = store._conn()
    conn.execute("DELETE FROM holdings")
    conn.commit()

    total_cost_basis = 0.0
    for h in holdings:
        shares = max(0.0, h.shares)
        if shares > 0:
            price = max(0.01, h.cost_basis / shares)
        else:
            price = 0.01

        domain_holding = DomainHolding(
            symbol=h.ticker,
            quantity=h.shares,
            purchase_price=price,
            purchase_date=datetime.now().strftime("%Y-%m-%d"),
            notes=h.account_type or "",
        )
        store.add_holding(domain_holding)
        total_cost_basis += h.cost_basis

    # Update upload_history.json
    history_json = Path(UPLOAD_HISTORY_PATH)
    history = []
    if history_json.exists():
        try:
            history = json.loads(history_json.read_text(encoding="utf-8"))
        except Exception:
            history = []

    history_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "filename": filename,
        "positions_count": len(holdings),
        "total_cost_basis": round(total_cost_basis, 2),
    }
    history.insert(0, history_entry)
    history = history[:20]
    history_json.write_text(json.dumps(history, indent=2), encoding="utf-8")


def rebuild_weekly_brief_cached() -> None:
    """Run yfinance-cached weekly brief build via CLI command."""
    cmd = [
        sys.executable,
        "-m",
        "application.cli",
        "weekly-brief",
        "--holdings",
        str(HOLDINGS_CSV_PATH),
        "--out",
        "data/personal/weekly_brief.md",
        "--use-cache",
    ]
    subprocess.run(cmd, check=True)
