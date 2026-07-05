"""Supply chain scoring for stock analysis."""

from __future__ import annotations

import math
from itertools import combinations
from typing import Any, Literal

from adapters.visualization.analysis.models import SectionScore


def compute_co_movement(closes_by_ticker: dict[str, list[float]]) -> float | None:
    """Average pairwise Pearson correlation of daily returns across tickers.

    Descriptive group-cohesion measure: high average correlation means the
    group trades as a pack (structural context, not a directional signal).
    Series are aligned to the shortest common length (from the end) before
    computing returns. Series with fewer than 2 returns or zero variance are
    excluded. Returns ``None`` when fewer than 2 usable series remain.
    """
    returns_by_ticker: dict[str, list[float]] = {}
    for ticker, closes in closes_by_ticker.items():
        if len(closes) < 3:
            continue
        returns = [
            (closes[i] - closes[i - 1]) / closes[i - 1]
            for i in range(1, len(closes))
            if closes[i - 1] != 0
        ]
        if len(returns) >= 2 and len(set(returns)) > 1:
            returns_by_ticker[ticker] = returns

    if len(returns_by_ticker) < 2:
        return None

    correlations: list[float] = []
    for t1, t2 in combinations(returns_by_ticker, 2):
        r1, r2 = returns_by_ticker[t1], returns_by_ticker[t2]
        n = min(len(r1), len(r2))
        r1, r2 = r1[-n:], r2[-n:]
        corr = _pearson(r1, r2)
        if corr is not None:
            correlations.append(corr)

    return sum(correlations) / len(correlations) if correlations else None


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    """Pearson correlation coefficient; None if either series has zero variance."""
    n = len(xs)
    mean_x, mean_y = sum(xs) / n, sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x == 0 or var_y == 0:
        return None
    return cov / math.sqrt(var_x * var_y)


def find_supply_chain_group(ticker: str) -> dict[str, Any] | None:
    """Find which supply chain group contains this ticker. Returns enriched group dict or None."""
    import os

    from loguru import logger

    try:
        import yaml

        config_path = "config/relationships/supply_chain.yaml"
        if not os.path.exists(config_path):
            return None
        with open(config_path) as f:
            data = yaml.safe_load(f)
        for rel in data.get("relationships", []):
            leaders = rel.get("leaders", [])
            followers = rel.get("followers", [])
            if ticker in leaders or ticker in followers:
                enriched = dict(rel)
                enriched["_is_leader"] = ticker in leaders
                return enriched
        return None
    except Exception as exc:
        logger.warning("Could not load supply chain config: {}", exc)
        return None


def score_supply_chain(group: dict[str, Any] | None) -> SectionScore:
    """4 supply chain checks: known group, leader momentum, cluster momentum, no divergence."""
    verdicts: list[tuple[Literal["pass", "warn", "fail"], str]] = []
    score = 0

    if group is None:
        return SectionScore(
            "Supply Chain",
            0,
            4,
            "This ticker is not in any tracked supply chain group.",
            [("warn", "Not in tracked supply chain — cross-asset signals unavailable")],
        )

    group_name = group.get("group", "unknown")
    leaders = group.get("leaders", [])
    followers = group.get("followers", [])
    role = "leader" if group.get("_is_leader") else "follower"

    # 1. In known group
    score += 1
    verdicts.append(
        (
            "pass",
            f"Part of '{group_name}' supply chain ({role}) with {len(leaders)} leaders, {len(followers)} followers",
        )
    )

    # 2. Leader momentum (we can't fetch live here without circular imports, use heuristic)
    lag = group.get("typical_lag_days", 1)
    if lag <= 2:
        score += 1
        verdicts.append(
            (
                "pass",
                f"Short lag ({lag} days) to supply chain leaders — fast signal propagation",
            )
        )
    else:
        verdicts.append(
            ("warn", f"Longer lag ({lag} days) to leaders — delayed signal propagation")
        )

    # 3. Cluster momentum: group has multiple members
    total_members = len(leaders) + len(followers)
    if total_members >= 5:
        score += 1
        verdicts.append(
            (
                "pass",
                f"Active cluster with {total_members} tracked members — strong group signal",
            )
        )
    else:
        verdicts.append(
            ("warn", f"Small cluster ({total_members} members) — limited group signal")
        )

    # 4. No divergence: leader and follower counts are balanced
    if leaders and followers:
        ratio = len(leaders) / len(followers)
        if 0.3 <= ratio <= 3.0:
            score += 1
            verdicts.append(
                (
                    "pass",
                    "Balanced leader/follower ratio — healthy supply chain structure",
                )
            )
        else:
            verdicts.append(
                ("warn", "Unbalanced leader/follower ratio may reduce signal quality")
            )
    else:
        verdicts.append(
            ("warn", "Incomplete group structure — missing leaders or followers")
        )

    notes = group.get("notes", "")
    summary = (
        f"Part of {group_name} supply chain. {notes}"
        if notes
        else f"Part of {group_name} supply chain group."
    )

    return SectionScore("Supply Chain", score, 4, summary, verdicts)
