"""Supply chain scoring for stock analysis."""

from __future__ import annotations

from typing import Any, Literal

from adapters.visualization.analysis.models import SectionScore


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
