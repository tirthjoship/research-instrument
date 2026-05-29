"""Real-data backtest runner: orchestrates pretrain + evaluation on yfinance data."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from loguru import logger

from application.evaluation import FullEvaluationSuite


def run_backtest_report(
    store_path: str = "data/recommendations.db",
    output_dir: str = "data/reports",
) -> dict[str, object]:
    """Generate comprehensive backtest report from stored evaluation runs.

    This runs AFTER pretrain has populated the store with walk-forward results.
    """
    from adapters.data.sqlite_store import SQLiteStore

    store = SQLiteStore(store_path)
    runs = store.get_evaluation_runs(eval_type="walk_forward")

    if not runs:
        logger.error("No walk-forward results found. Run pretrain first.")
        return {}

    by_horizon: dict[str, dict[str, list[float]]] = {}
    for run in runs:
        h = run.horizon
        if h not in by_horizon:
            by_horizon[h] = {"accuracies": []}
        by_horizon[h]["accuracies"].append(run.metric_value)

    report: dict[str, object] = {"horizons": {}}

    for horizon, data in by_horizon.items():
        accs = data["accuracies"]
        avg_acc = sum(accs) / len(accs) if accs else 0.0
        report["horizons"][horizon] = {  # type: ignore[index]
            "avg_directional_accuracy": avg_acc,
            "n_folds": len(accs),
            "min_accuracy": min(accs) if accs else 0.0,
            "max_accuracy": max(accs) if accs else 0.0,
        }

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / f"backtest_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(json.dumps(report, indent=2, default=str))
    logger.info(f"Report saved to {report_path}")

    return report
