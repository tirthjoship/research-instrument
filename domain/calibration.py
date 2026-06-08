"""Pure calibration helpers (stdlib only): historical base-rate priors (point-in-time,
no look-ahead) and Brier/reliability scoring of discipline flags."""

from __future__ import annotations

from .trend_rules import atr, sma, trend_health


def brier_score(predicted_probs: list[float], outcomes: list[int]) -> float:
    """Mean squared error between predicted P(event) and realized 0/1 outcomes."""
    n = min(len(predicted_probs), len(outcomes))
    if n == 0:
        return 0.0
    return sum((predicted_probs[i] - outcomes[i]) ** 2 for i in range(n)) / n


def base_rate_from_history(
    closes: list[float], trend_window: int, atr_window: int, horizon: int
) -> dict[str, dict[str, float]]:
    """Walk the series point-in-time. At each day with enough history, bucket the day
    by trend_health sign (`above`/`below`) using ONLY past+current closes, then look
    `horizon` days forward to record the realized return. No look-ahead: the forward
    window is never used to form the bucket. Returns per-bucket n, mean_fwd_return,
    down_rate (fraction of forward returns < 0)."""
    need = max(trend_window, atr_window)
    buckets: dict[str, list[float]] = {"above": [], "below": []}
    for i in range(need, len(closes) - horizon):
        window = closes[: i + 1]  # point-in-time: up to and including day i
        sma_val = sma(window, trend_window)
        # Convention: close-only series passes closes for all three OHLC lists
        atr_val = atr(window, window, window, atr_window)
        th = trend_health(closes[i], sma_val, atr_val)
        if th is None:
            continue
        fwd = closes[i + horizon] / closes[i] - 1.0 if closes[i] > 0 else 0.0
        buckets["above" if th >= 0 else "below"].append(fwd)
    out: dict[str, dict[str, float]] = {}
    for name, rets in buckets.items():
        if not rets:
            continue
        out[name] = {
            "n": float(len(rets)),
            "mean_fwd_return": sum(rets) / len(rets),
            "down_rate": sum(1 for r in rets if r < 0) / len(rets),
        }
    return out
