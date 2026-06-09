"""Dashboard data loader — SQLite + JSON loading with graceful defaults.

All functions return sensible defaults (empty list, empty dict, None) on missing data.
No tab should crash from missing data.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from domain.models import Holding, StockRecommendation

logger = logging.getLogger(__name__)


def load_backtest_reports(reports_dir: str) -> list[dict[str, Any]]:
    """Load all backtest JSON reports from a directory, sorted by name (newest last)."""
    path = Path(reports_dir)
    if not path.exists():
        return []
    files = sorted(path.glob("backtest_report_*.json"))
    results: list[dict[str, Any]] = []
    for f in files:
        try:
            results.append(json.loads(f.read_text()))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load %s: %s", f, e)
    return results


def load_recommendations(
    db_path: str,
    week_start: str | None = None,
) -> list[StockRecommendation]:
    """Load recommendations from SQLite. Returns empty list if DB missing."""
    if not Path(db_path).exists():
        return []
    try:
        from adapters.data.sqlite_store import SQLiteStore

        store = SQLiteStore(db_path)
        return store.get_recommendations(week_start=week_start)
    except Exception as e:
        logger.warning("Failed to load recommendations: %s", e)
        return []


def load_recommendations_latest(db_path: str) -> list[Any]:
    """Load most recent week's recommendations sorted by composite_score desc."""
    try:
        if not Path(db_path).exists():
            return []
        from adapters.data.sqlite_store import SQLiteStore

        store = SQLiteStore(db_path)
        recs = store.get_recommendations()
        if not recs:
            return []
        latest_week = max(r.week_start for r in recs)
        latest = [r for r in recs if r.week_start == latest_week]
        latest.sort(key=lambda r: r.composite_score, reverse=True)
        return latest
    except Exception:
        return []


def load_holdings(db_path: str) -> list[Holding]:
    """Load holdings from SQLite. Returns empty list if DB missing."""
    if not Path(db_path).exists():
        return []
    try:
        from adapters.data.sqlite_store import SQLiteStore

        store = SQLiteStore(db_path)
        return store.get_holdings()
    except Exception as e:
        logger.warning("Failed to load holdings: %s", e)
        return []


def load_watchlist(db_path: str) -> list[dict[str, str]]:
    """Load watchlist from SQLite. Returns empty list if DB missing."""
    if not Path(db_path).exists():
        return []
    try:
        from adapters.data.sqlite_store import SQLiteStore

        store = SQLiteStore(db_path)
        return store.get_watchlist()
    except Exception as e:
        logger.warning("Failed to load watchlist: %s", e)
        return []


def load_evaluation_runs(
    db_path: str,
    eval_type: str | None = None,
) -> list[Any]:
    """Load evaluation runs from SQLite. Returns empty list if DB missing."""
    if not Path(db_path).exists():
        return []
    try:
        from adapters.data.sqlite_store import SQLiteStore

        store = SQLiteStore(db_path)
        return store.get_evaluation_runs(eval_type=eval_type)
    except Exception as e:
        logger.warning("Failed to load evaluation runs: %s", e)
        return []


def load_shap_importance(json_path: str) -> dict[str, dict[str, float]]:
    """Load SHAP importance JSON. Returns {feature: {mean, std, cv, ...}}."""
    path = Path(json_path)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())  # type: ignore[no-any-return]
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load SHAP: %s", e)
        return {}


def load_ablation_results(reports_dir: str) -> list[dict[str, Any]]:
    """Load Phase 3B ablation results from validation JSON."""
    path = Path(reports_dir)
    if not path.exists():
        return []
    files = sorted(path.glob("phase3b_validation_*.json"))
    if not files:
        return []
    try:
        data = json.loads(files[-1].read_text())
        return data.get("ablation_results", [])  # type: ignore[no-any-return]
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load ablation: %s", e)
        return []


def load_supply_chains(yaml_path: str) -> dict[str, Any]:
    """Load supply chain YAML config. Returns empty dict if missing."""
    path = Path(yaml_path)
    if not path.exists():
        return {}
    try:
        import yaml

        result: dict[str, Any] = yaml.safe_load(path.read_text()) or {}
        return result
    except Exception as e:
        logger.warning("Failed to load supply chains: %s", e)
        return {}


def load_spy_sparkline() -> dict[str, Any]:
    """Fetch SPY intraday 1d/5m data for header sparkline.

    Returns dict with keys: prices, times, current, open, change_pct, high, low.
    Returns {} on any failure (network, missing yfinance, market closed).
    """
    try:
        import yfinance as yf

        ticker = yf.Ticker("SPY")
        hist = ticker.history(period="1d", interval="5m")
        if hist.empty:
            return {}
        prices = hist["Close"].tolist()
        times = [str(t) for t in hist.index.tolist()]
        current = float(prices[-1])
        open_price = float(hist["Open"].iloc[0])
        high = float(hist["High"].max())
        low = float(hist["Low"].min())
        change_pct = ((current - open_price) / open_price) * 100 if open_price else 0.0
        return {
            "prices": prices,
            "times": times,
            "current": current,
            "open": open_price,
            "change_pct": change_pct,
            "high": high,
            "low": low,
        }
    except Exception as e:
        logger.warning("Failed to load SPY sparkline: %s", e)
        return {}


def load_trades(db_path: str, ticker: str | None = None) -> list[Any]:
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


def load_outcomes(db_path: str, ticker: str | None = None) -> list[Any]:
    """Load trade outcomes. Returns empty list if DB missing."""
    if not Path(db_path).exists():
        return []
    try:
        from adapters.data.sqlite_store import SQLiteStore

        store = SQLiteStore(db_path)
        return store.get_trade_outcomes(ticker=ticker)
    except Exception as e:
        logger.warning("Failed to load outcomes: %s", e)
        return []


def load_weight_history(db_path: str) -> list[Any]:
    """Load weight adjustment history from SQLite. Returns empty list if DB missing."""
    if not Path(db_path).exists():
        return []
    try:
        from adapters.data.sqlite_store import SQLiteStore

        return SQLiteStore(db_path).get_weight_history()
    except Exception as e:
        logger.warning("Failed to load weight history: %s", e)
        return []


def load_learned_rules(db_path: str) -> list[Any]:
    """Load learned rules from SQLite. Returns empty list if DB missing."""
    if not Path(db_path).exists():
        return []
    try:
        from adapters.data.sqlite_store import SQLiteStore

        return SQLiteStore(db_path).get_learned_rules()
    except Exception as e:
        logger.warning("Failed to load learned rules: %s", e)
        return []


def load_scan_distribution(
    store: Any, scan_date: str | None = None
) -> list[dict[str, Any]]:
    """Return the full candidate distribution for the given scan_date.

    Thin wrapper over store.get_scan_candidates. Returns all rows (surfaced
    and non-surfaced) so the dashboard can render an honest empty-state when
    the surfaced list is empty.
    """
    try:
        return store.get_scan_candidates(scan_date=scan_date)  # type: ignore[no-any-return]
    except Exception as e:
        logger.warning("Failed to load scan distribution: %s", e)
        return []


def load_scan_timestamp(reports_dir: str = "data/reports") -> str | None:
    """Find most recent backtest report and return formatted timestamp string.

    Extracts timestamp from filename: backtest_report_YYYYMMDD_HHMMSS.json
    Returns formatted string like "Jun 03, 2026 at 02:15 PM", or None if no reports.
    """
    import datetime

    path = Path(reports_dir)
    if not path.exists():
        return None
    files = sorted(path.glob("backtest_report_*.json"))
    if not files:
        return None
    latest = files[-1]
    stem = latest.stem  # e.g. "backtest_report_20260603_021500"
    parts = stem.split("_", 2)  # ["backtest", "report", "20260603_021500"]
    if len(parts) < 3:
        return None
    ts_str = parts[2]  # "20260603_021500"
    try:
        dt = datetime.datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
        return dt.strftime("%b %d, %Y at %I:%M %p")
    except ValueError:
        return None


def load_weekly_brief(path: str = "data/personal/weekly_brief.md") -> str | None:
    """Read the generated weekly-brief markdown; None if not yet generated."""
    p = Path(path)
    if not p.exists():
        return None
    return p.read_text()
