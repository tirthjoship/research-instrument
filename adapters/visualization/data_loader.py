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


def load_event_sector_mapping(yaml_path: str) -> dict[str, Any]:
    """Load event-sector mapping YAML. Returns empty dict if missing."""
    path = Path(yaml_path)
    if not path.exists():
        return {}
    try:
        import yaml

        result: dict[str, Any] = yaml.safe_load(path.read_text()) or {}
        return result
    except Exception as e:
        logger.warning("Failed to load event mapping: %s", e)
        return {}
