"""Walk-forward conviction backtest with precision-first metrics.

Pure orchestration. All data access is injected via callables, so this is
fully testable with fakes and never touches the network.
"""

from __future__ import annotations

from typing import Callable

from application.backtest_runner import compute_binomial_pvalue, compute_sharpe_vs_spy
from application.precision_metrics import (
    date_level_significance,
    expected_profit_per_signal,
    f_beta,
    monotonic_precision_curve,
)


def run_conviction_backtest(
    scan_dates: list[str],
    tickers: list[str],
    score_fn: Callable[[str], dict[str, float]],
    forward_return_fn: Callable[[str, str], float],
    benchmark_return_fn: Callable[[str], float],
    decile: float = 0.1,
    cost: float = 0.001,
) -> dict[str, object]:
    """Backtest the conviction score with precision-first metrics.

    For each date: score all tickers, select the top `decile` by conviction,
    mark a pick a "win" if its forward return beats the benchmark, and build a
    top-decile basket return series for Sharpe. Returns the precision suite.
    """
    pooled_scores: list[float] = []
    pooled_wins: list[int] = []
    selected_wins: list[int] = []
    selected_returns: list[float] = []
    model_basket_returns: list[float] = []
    spy_returns: list[float] = []
    total_universe_wins = 0
    n_dates = 0

    for date in scan_dates:
        scores_map = score_fn(date)
        rows = list(scores_map.items())
        if not rows:
            continue
        n_dates += 1
        bench = benchmark_return_fn(date)

        for ticker, conv in rows:
            fwd = forward_return_fn(ticker, date)
            win = 1 if fwd > bench else 0
            pooled_scores.append(conv)
            pooled_wins.append(win)
            total_universe_wins += win

        rows_sorted = sorted(rows, key=lambda r: r[1], reverse=True)
        k = max(1, round(len(rows_sorted) * decile))
        top = rows_sorted[:k]
        basket = 0.0
        for ticker, _conv in top:
            fwd = forward_return_fn(ticker, date)
            win = 1 if fwd > bench else 0
            selected_wins.append(win)
            selected_returns.append(fwd)
            basket += fwd
        model_basket_returns.append(basket / k)
        spy_returns.append(bench)

    n_selected = len(selected_wins)
    precision = sum(selected_wins) / n_selected if n_selected else 0.0
    recall = (sum(selected_wins) / total_universe_wins) if total_universe_wins else 0.0
    wins_ret = [r for r, w in zip(selected_returns, selected_wins) if w == 1]
    loss_ret = [r for r, w in zip(selected_returns, selected_wins) if w == 0]
    avg_win = sum(wins_ret) / len(wins_ret) if wins_ret else 0.0
    avg_loss = -(sum(loss_ret) / len(loss_ret)) if loss_ret else 0.0
    sharpe = compute_sharpe_vs_spy(model_basket_returns, spy_returns)

    # Empirical base rate: fraction of the whole scored universe that beat the benchmark
    base_rate = sum(pooled_wins) / len(pooled_wins) if pooled_wins else 0.0

    return {
        "top_decile_hit_rate": round(precision, 4),
        "precision_curve": monotonic_precision_curve(
            pooled_scores, pooled_wins, n_bins=10
        ),
        "f_beta_0_5": round(f_beta(precision, recall, beta=0.5), 4),
        "expected_profit_per_signal": round(
            expected_profit_per_signal(precision, avg_win, avg_loss, cost), 6
        ),
        "model_sharpe": sharpe["model_sharpe"],
        "spy_sharpe": sharpe["spy_sharpe"],
        "excess_sharpe": sharpe["excess_sharpe"],
        # Honest null: test against empirical base rate, not hardcoded 0.5
        "p_value": round(
            compute_binomial_pvalue(precision, n_selected, null_p=base_rate), 4
        ),
        # Additive keys for transparency
        "base_rate": round(base_rate, 4),
        "edge_over_base": round(precision - base_rate, 4),
        "p_value_vs_50": round(
            compute_binomial_pvalue(precision, n_selected, null_p=0.5), 4
        ),
        "date_level": date_level_significance(model_basket_returns, spy_returns),
        "n_signals": n_selected,
        "n_dates": n_dates,
        "avg_win": round(avg_win, 4),
        "avg_loss": round(avg_loss, 4),
    }
