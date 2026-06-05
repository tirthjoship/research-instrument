"""Precision-first evaluation metrics. Pure functions, no I/O."""

from __future__ import annotations

import math
import random
import warnings


def _rank_desc(scores: list[float], wins: list[int]) -> list[int]:
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    return [wins[i] for i in order]


def precision_at_decile(
    scores: list[float], wins: list[int], decile: float = 0.1
) -> float:
    """Fraction of the top `decile` (by score) that won. decile in (0,1]."""
    if not scores:
        return 0.0
    ranked = _rank_desc(scores, wins)
    k = max(1, round(len(ranked) * decile))
    top = ranked[:k]
    return sum(top) / len(top)


def monotonic_precision_curve(
    scores: list[float], wins: list[int], n_bins: int = 10
) -> list[float]:
    """Precision per score-bin, lowest-score bin -> highest. Healthy conviction => non-decreasing."""
    if not scores:
        return [0.0] * n_bins
    order = sorted(range(len(scores)), key=lambda i: scores[i])
    binned = [wins[i] for i in order]
    out: list[float] = []
    size = max(1, len(binned) // n_bins)
    for b in range(n_bins):
        chunk = (
            binned[b * size : (b + 1) * size] if b < n_bins - 1 else binned[b * size :]
        )
        out.append(sum(chunk) / len(chunk) if chunk else 0.0)
    return out


def f_beta(precision: float, recall: float, beta: float = 0.5) -> float:
    """F-beta. beta<1 weights precision over recall."""
    b2 = beta * beta
    denom = b2 * precision + recall
    if denom == 0:
        return 0.0
    return (1 + b2) * precision * recall / denom


def expected_profit_per_signal(
    precision: float, avg_win: float, avg_loss: float, cost: float
) -> float:
    """E[profit] = P(win)*avg_win - P(loss)*avg_loss - cost. The real-money gate."""
    return precision * avg_win - (1 - precision) * avg_loss - cost


def moving_block_bootstrap(
    values: list[float],
    n_resamples: int = 2000,
    block_size: int | None = None,
    seed: int = 12345,
) -> dict[str, object]:
    """Moving-block bootstrap for the mean of an autocorrelated series.

    Resamples contiguous (overlapping) blocks so within-block time-structure and
    fat tails are preserved, giving a CI on the mean that does not assume
    independence. Deterministic given `seed` (reproducible across runs).
    Returns: n, block_size, n_resamples, mean, ci_low (2.5%), ci_high (97.5%),
    p_value_ge_0 (fraction of resampled means <= 0 — small => mean robustly > 0).
    Safe on n < 2: CI/p None, n_resamples 0.
    """
    n = len(values)
    mean_val = round(sum(values) / n, 6) if n > 0 else 0.0

    if n < 2:
        return {
            "n": n,
            "block_size": None,
            "n_resamples": 0,
            "mean": mean_val,
            "ci_low": None,
            "ci_high": None,
            "p_value_ge_0": None,
        }

    # Determine block size: default max(2, round(n^(1/3))), clamped to <= n
    if block_size is None:
        bs = max(2, round(n ** (1 / 3)))
    else:
        bs = block_size
    bs = min(bs, n)

    max_start = n - bs
    rng = random.Random(seed)

    resample_means: list[float] = []
    for _ in range(n_resamples):
        sample: list[float] = []
        while len(sample) < n:
            start = rng.randint(0, max_start)
            sample.extend(values[start : start + bs])
        sample = sample[:n]
        resample_means.append(sum(sample) / n)

    resample_means.sort()
    ci_low = round(resample_means[int(0.025 * n_resamples)], 6)
    ci_high = round(resample_means[int(0.975 * n_resamples)], 6)
    p_value_ge_0 = round(sum(1 for m in resample_means if m <= 0) / n_resamples, 4)

    return {
        "n": n,
        "block_size": bs,
        "n_resamples": n_resamples,
        "mean": mean_val,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "p_value_ge_0": p_value_ge_0,
    }


def date_level_significance(
    model_basket_returns: list[float], spy_returns: list[float]
) -> dict[str, object]:
    """Treat each scan date as the independent unit. excess[i] = model[i] - spy[i].

    One-sided tests that mean excess > 0. Returns t-test, Wilcoxon signed-rank,
    and sign-test p-values plus mean_excess, n_dates, pct_dates_positive, t_stat.
    Safe on tiny/degenerate input (n<2 or all-equal differences): affected
    p-values are None and the function never raises.
    """
    from application.backtest_runner import compute_binomial_pvalue

    excess = [m - s for m, s in zip(model_basket_returns, spy_returns)]
    n_dates = len(excess)
    mean_excess = round(sum(excess) / n_dates, 6) if n_dates > 0 else 0.0
    n_positive = sum(1 for e in excess if e > 0)
    pct_dates_positive = round(n_positive / n_dates, 4) if n_dates > 0 else 0.0

    _degenerate: dict[str, object] = {
        "n_dates": n_dates,
        "mean_excess": mean_excess,
        "pct_dates_positive": pct_dates_positive,
        "t_stat": None,
        "t_pvalue": None,
        "wilcoxon_pvalue": None,
        "sign_test_pvalue": None,
        "per_date_excess": [round(e, 6) for e in excess],
        "top1_date_share": None,
        "top3_date_share": None,
        "bootstrap": moving_block_bootstrap(excess),
    }

    if n_dates < 2:
        return _degenerate

    # --- t-test (one-sample, one-sided, H1: mean > 0) ---
    t_stat: float | None
    t_pvalue: float | None
    try:
        from scipy.stats import ttest_1samp

        t_result = ttest_1samp(excess, 0.0, alternative="greater")
        t_stat = float(t_result.statistic)
        t_pvalue = round(float(t_result.pvalue), 4)
    except ImportError:
        # stdlib fallback
        mean_e = sum(excess) / n_dates
        var_e = sum((e - mean_e) ** 2 for e in excess) / (n_dates - 1)
        std_e = math.sqrt(var_e) if var_e > 0 else 0.0
        if std_e == 0.0:
            t_stat = None
            t_pvalue = None
        else:
            t_stat = mean_e / (std_e / math.sqrt(n_dates))
            t_pvalue = round(0.5 * math.erfc(t_stat / math.sqrt(2)), 4)

    # --- Wilcoxon signed-rank (one-sided, H1: median > 0) ---
    wilcoxon_pvalue: float | None
    try:
        from scipy.stats import wilcoxon

        # Promote RuntimeWarnings (e.g. all-zero differences → NaN division)
        # to exceptions so they fall into the except branch below.
        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            w_result = wilcoxon(excess, alternative="greater")
        wilcoxon_pvalue = round(float(w_result.pvalue), 4)
    except Exception:
        # scipy absent, all-zero differences, or too few nonzero values
        wilcoxon_pvalue = None

    # --- Sign test (binomial against 0.5) ---
    sign_test_pvalue: float | None = round(
        compute_binomial_pvalue(pct_dates_positive, n_dates, null_p=0.5), 4
    )

    # --- F1: concentration diagnostics ---
    srt = sorted(excess, reverse=True)
    pos_sum = sum(e for e in excess if e > 0)
    top1_date_share: float | None
    top3_date_share: float | None
    if pos_sum > 0:
        top1_date_share = round(srt[0] / pos_sum, 4)
        top3_date_share = round(sum(srt[:3]) / pos_sum, 4)
    else:
        top1_date_share = None
        top3_date_share = None

    return {
        "n_dates": n_dates,
        "mean_excess": mean_excess,
        "pct_dates_positive": pct_dates_positive,
        "t_stat": t_stat,
        "t_pvalue": t_pvalue,
        "wilcoxon_pvalue": wilcoxon_pvalue,
        "sign_test_pvalue": sign_test_pvalue,
        "per_date_excess": [round(e, 6) for e in excess],
        "top1_date_share": top1_date_share,
        "top3_date_share": top3_date_share,
        "bootstrap": moving_block_bootstrap(excess),
    }
