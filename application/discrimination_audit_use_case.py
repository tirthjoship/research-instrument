"""One-shot diagnostic: which conviction dims actually discriminate?

Surfaces per-dim variance + neutral-share so the human can prune dead
dimensions. No automatic pruning — evidence only. Supports the
"prune, don't add" stance (spec section 1).
"""

from __future__ import annotations

from typing import Any


class DiscriminationAuditUseCase:
    def execute(
        self, candidates: list[dict[str, Any]], neutral: float = 5.0
    ) -> dict[str, dict[str, float]]:
        if not candidates:
            return {}
        dims: dict[str, list[float]] = {}
        for c in candidates:
            for dim, val in c.get("sub_scores", {}).items():
                dims.setdefault(dim, []).append(float(val))
        report: dict[str, dict[str, float]] = {}
        for dim, vals in dims.items():
            n = len(vals)
            mean = sum(vals) / n
            variance = sum((v - mean) ** 2 for v in vals) / n
            neutral_share = sum(1 for v in vals if v == neutral) / n
            report[dim] = {
                "n": float(n),
                "mean": mean,
                "variance": variance,
                "neutral_share": neutral_share,
            }
        return report
