"""Real-data backtest runner: orchestrates pretrain + evaluation on yfinance data."""

from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path

from loguru import logger


def compute_binomial_pvalue(accuracy: float, n_predictions: int) -> float:
    """Compute one-sided binomial test p-value: P(X >= observed | p=0.5).

    Tests whether observed directional accuracy significantly exceeds random (50%).
    Uses scipy if available, falls back to normal approximation.
    """
    if n_predictions == 0:
        return 1.0

    k = round(accuracy * n_predictions)

    try:
        from scipy.stats import binomtest

        result = binomtest(k, n_predictions, 0.5, alternative="greater")
        return float(result.pvalue)
    except ImportError:
        # Normal approximation fallback
        z = (accuracy - 0.5) / math.sqrt(0.25 / n_predictions)
        p = 0.5 * math.erfc(z / math.sqrt(2))
        return p


def compute_sharpe_vs_spy(
    model_returns: list[float],
    spy_returns: list[float],
    periods_per_year: int = 12,
) -> dict[str, float]:
    """Compute annualized Sharpe ratios for model vs SPY benchmark."""
    if not model_returns or not spy_returns:
        return {"model_sharpe": 0.0, "spy_sharpe": 0.0, "excess_sharpe": 0.0}

    def _sharpe(returns: list[float]) -> float:
        if len(returns) < 2:
            return 0.0
        mean_r = sum(returns) / len(returns)
        var = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
        std = math.sqrt(var) if var > 0 else 1e-10
        return (mean_r / std) * math.sqrt(periods_per_year)

    model_s = _sharpe(model_returns)
    spy_s = _sharpe(spy_returns)

    return {
        "model_sharpe": round(model_s, 4),
        "spy_sharpe": round(spy_s, 4),
        "excess_sharpe": round(model_s - spy_s, 4),
    }


def run_backtest_report(
    store_path: str = "data/recommendations.db",
    output_dir: str = "data/reports",
) -> dict[str, object]:
    """Generate comprehensive backtest report from stored evaluation runs.

    Enhanced: includes permutation p-values and Sharpe vs SPY.
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

    tickers_per_fold = 40

    for horizon, data in by_horizon.items():
        accs = data["accuracies"]
        n_folds = len(accs)
        avg_acc = sum(accs) / n_folds if n_folds > 0 else 0.0
        n_total = n_folds * tickers_per_fold

        p_value = compute_binomial_pvalue(avg_acc, n_total)
        model_returns = [a - 0.5 for a in accs]

        report["horizons"][horizon] = {  # type: ignore[index]
            "avg_directional_accuracy": avg_acc,
            "n_folds": n_folds,
            "n_total_predictions": n_total,
            "min_accuracy": min(accs) if accs else 0.0,
            "max_accuracy": max(accs) if accs else 0.0,
            "p_value_vs_random": round(p_value, 4),
            "model_excess_returns_per_fold": model_returns,
        }

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    report_path = (
        out / f"backtest_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    report_path.write_text(json.dumps(report, indent=2, default=str))
    logger.info(f"Report saved to {report_path}")

    return report
