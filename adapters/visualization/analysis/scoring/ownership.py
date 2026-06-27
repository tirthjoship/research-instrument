"""Ownership scoring for stock analysis."""

from __future__ import annotations

from typing import Any, Literal

from adapters.visualization.analysis.models import SectionScore


def score_ownership(
    info: dict[str, Any], insider_txns: list[dict[str, Any]]
) -> SectionScore:
    """5 ownership checks: institutional %, insider %, net buying 3mo, 13D activity, sell velocity."""
    verdicts: list[tuple[Literal["pass", "warn", "fail"], str]] = []
    score = 0

    # 1. Institutional > 50%
    inst_pct = info.get("heldPercentInstitutions")
    if inst_pct is not None:
        pct = inst_pct * 100
        if inst_pct > 0.50:
            score += 1
            verdicts.append(
                (
                    "pass",
                    f"Institutional ownership {pct:.1f}% — strong smart-money backing",
                )
            )
        else:
            verdicts.append(
                ("warn", f"Institutional ownership {pct:.1f}% — below 50% threshold")
            )
    else:
        verdicts.append(("warn", "Institutional ownership data not available"))

    # 2. Insider > 1%
    insider_pct = info.get("heldPercentInsiders")
    if insider_pct is not None:
        pct = insider_pct * 100
        if insider_pct > 0.01:
            score += 1
            verdicts.append(
                (
                    "pass",
                    f"Insider ownership {pct:.1f}% — management has skin in the game",
                )
            )
        else:
            verdicts.append(
                (
                    "warn",
                    f"Low insider ownership {pct:.2f}% — misaligned incentives risk",
                )
            )
    else:
        verdicts.append(("warn", "Insider ownership data not available"))

    # 3. Net insider buying last 3 months
    if insider_txns:
        buys = sum(
            1
            for t in insider_txns
            if str(t.get("transactionType", t.get("Transaction", ""))).lower()
            in ("buy", "purchase")
        )
        sells = len(insider_txns) - buys
        if buys > sells:
            score += 1
            verdicts.append(
                (
                    "pass",
                    f"Net insider buying: {buys} buys vs {sells} sells in recent period",
                )
            )
        else:
            verdicts.append(
                (
                    "warn",
                    f"Net insider selling: {sells} sells vs {buys} buys in recent period",
                )
            )
    else:
        verdicts.append(("warn", "No insider transaction data available"))

    # 4. Any 13D / activist filing (proxy: large institutional concentration)
    # yfinance doesn't expose 13D directly; use institutional count proxy
    major_holders = info.get("institutionsCount", 0) or 0
    if major_holders > 500:
        score += 1
        verdicts.append(
            (
                "pass",
                f"{major_holders} institutions hold this — broad institutional interest",
            )
        )
    else:
        verdicts.append(
            ("warn", "Limited institutional participation — lower conviction")
        )

    # 5. Low selling velocity (insider selling < 3 in last period)
    if insider_txns:
        recent_sells = sum(
            1
            for t in insider_txns
            if str(t.get("transactionType", t.get("Transaction", ""))).lower()
            in ("sell", "sale")
        )
        if recent_sells < 3:
            score += 1
            verdicts.append(
                ("pass", f"Low insider sell activity ({recent_sells} transactions)")
            )
        else:
            verdicts.append(
                ("warn", f"Elevated insider selling ({recent_sells} sell transactions)")
            )
    else:
        score += 1  # No sells = pass
        verdicts.append(("pass", "No insider selling activity detected"))

    pct_score = score / 5
    if pct_score >= 0.60:
        summary = "Strong ownership alignment — institutions and insiders both engaged."
    elif pct_score >= 0.40:
        summary = "Mixed ownership signals — watch insider activity closely."
    else:
        summary = "Ownership concerns — low insider alignment or selling pressure."

    return SectionScore("Ownership", score, 5, summary, verdicts)
