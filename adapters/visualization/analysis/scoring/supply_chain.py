"""Supply chain scoring for stock analysis."""

from __future__ import annotations

import math
from itertools import combinations
from typing import Any, Literal

from adapters.visualization.analysis.models import SectionScore


def _returns_by_ticker(
    closes_by_ticker: dict[str, list[float]]
) -> dict[str, list[float]]:
    """Convert close series to daily returns, dropping unusable series.

    Series with fewer than 2 returns or zero variance are excluded.
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
    return returns_by_ticker


def compute_co_movement(closes_by_ticker: dict[str, list[float]]) -> float | None:
    """Average pairwise Pearson correlation of daily returns across tickers.

    Descriptive group-cohesion measure: high average correlation means the
    group trades as a pack (structural context, not a directional signal).
    Series are aligned to the shortest common length (from the end) before
    computing returns. Series with fewer than 2 returns or zero variance are
    excluded. Returns ``None`` when fewer than 2 usable series remain.
    """
    returns_by_ticker = _returns_by_ticker(closes_by_ticker)

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


def avg_pairwise_correlation(
    closes_by_ticker: dict[str, list[float]]
) -> dict[str, float]:
    """Per-ticker mean Pearson correlation to every other ticker in the group.

    Used to rank centrality (which ticker moves most "with the pack") when no
    market-cap data is available to determine a supply-chain leader. Tickers
    with unusable series (per :func:`_returns_by_ticker`) are omitted.
    """
    returns_by_ticker = _returns_by_ticker(closes_by_ticker)
    tickers = list(returns_by_ticker)
    if len(tickers) < 2:
        return {}

    sums: dict[str, float] = {t: 0.0 for t in tickers}
    counts: dict[str, int] = {t: 0 for t in tickers}
    for t1, t2 in combinations(tickers, 2):
        r1, r2 = returns_by_ticker[t1], returns_by_ticker[t2]
        n = min(len(r1), len(r2))
        corr = _pearson(r1[-n:], r2[-n:])
        if corr is None:
            continue
        sums[t1] += corr
        sums[t2] += corr
        counts[t1] += 1
        counts[t2] += 1

    return {t: sums[t] / counts[t] for t in tickers if counts[t] > 0}


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


def one_week_return_pct(closes: list[float]) -> float | None:
    """Percent return from 5 trading days ago to the latest close.

    ``None`` when fewer than 6 points are available or the reference close is 0.
    """
    if len(closes) < 6:
        return None
    start, end = closes[-6], closes[-1]
    if start == 0:
        return None
    return (end - start) / start * 100.0


def compute_group_week_moves(
    closes_by_ticker: dict[str, list[float]], ticker: str
) -> tuple[float | None, float | None]:
    """(group_1w_avg_pct, ticker_vs_group_pct) for the supply-chain panel's
    "Group 1w" / "{ticker} vs grp" tiles.

    ``group_1w_avg_pct`` is the average 1-week return across every *other*
    ticker in ``closes_by_ticker`` with enough history; ``ticker_vs_group_pct``
    is ``ticker``'s own 1-week return minus that average. Either (or both) is
    ``None`` when there isn't enough price history to compute it — an honest
    data gap, never a guessed number.
    """
    ticker_ret = one_week_return_pct(closes_by_ticker.get(ticker, []))
    peer_returns = [
        r
        for t, closes in closes_by_ticker.items()
        if t != ticker
        for r in [one_week_return_pct(closes)]
        if r is not None
    ]
    if not peer_returns:
        return None, None
    group_avg = sum(peer_returns) / len(peer_returns)
    vs_group = (ticker_ret - group_avg) if ticker_ret is not None else None
    return round(group_avg, 2), (round(vs_group, 2) if vs_group is not None else None)


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
    lag_raw = group.get("typical_lag_days", 1)
    lag: int | None
    try:
        lag = int(lag_raw) if lag_raw is not None else None
    except (TypeError, ValueError):
        lag = None

    if lag is None:
        verdicts.append(
            ("warn", "Typical lag not available — dynamic cluster has no curated lag")
        )
    elif lag <= 2:
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
