"""Moving-block bootstrap for the mean of an autocorrelated series (pure domain).

Stdlib-only. Lives in the domain layer so domain code (e.g. the insider gate) can
depend on it without importing the application layer. Re-exported from
`application.precision_metrics` for backward compatibility with existing callers.
"""

from __future__ import annotations

import random


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
