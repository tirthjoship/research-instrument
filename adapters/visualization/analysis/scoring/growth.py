"""Growth scoring for stock analysis."""

from __future__ import annotations

from typing import Any, Literal

from adapters.visualization.analysis.models import SectionScore


def score_growth(info: dict[str, Any]) -> SectionScore:
    """6 growth checks: revenue growth, vs industry, earnings growth, vs industry, acceleration, margin."""
    verdicts: list[tuple[Literal["pass", "warn", "fail"], str]] = []
    score = 0

    # 1. Revenue growth > 0
    rev_growth = info.get("revenueGrowth")
    if rev_growth is not None:
        pct = rev_growth * 100
        if rev_growth > 0:
            score += 1
            verdicts.append(("pass", f"Revenue growing at {pct:.1f}% year-over-year"))
        else:
            verdicts.append(
                ("fail", f"Revenue declining at {abs(pct):.1f}% year-over-year")
            )
    else:
        verdicts.append(("warn", "Revenue growth data not available"))

    # 2. Revenue > industry growth (proxy: > 10%)
    if rev_growth is not None:
        if rev_growth > 0.10:
            score += 1
            verdicts.append(
                (
                    "pass",
                    f"Revenue growth {rev_growth * 100:.1f}% exceeds typical industry (10%)",
                )
            )
        else:
            verdicts.append(("warn", "Revenue growth below 10% industry threshold"))
    else:
        verdicts.append(("warn", "Cannot compare to industry — data missing"))

    # 3. Earnings growth > 0
    eps_growth = info.get("earningsGrowth")
    if eps_growth is not None:
        pct = eps_growth * 100
        if eps_growth > 0:
            score += 1
            verdicts.append(("pass", f"Earnings growing at {pct:.1f}%"))
        else:
            verdicts.append(("fail", f"Earnings declining at {abs(pct):.1f}%"))
    else:
        verdicts.append(("warn", "Earnings growth data not available"))

    # 4. Earnings > industry (proxy: > 15%)
    if eps_growth is not None:
        if eps_growth > 0.15:
            score += 1
            verdicts.append(
                (
                    "pass",
                    f"Earnings growth {eps_growth * 100:.1f}% exceeds typical industry (15%)",
                )
            )
        else:
            verdicts.append(("warn", "Earnings growth below 15% industry threshold"))
    else:
        verdicts.append(("warn", "Cannot compare earnings to industry"))

    # 5. Revenue accelerating — use quarterly earnings growth as proxy
    earnings_quarterly = info.get("earningsQuarterlyGrowth")
    if earnings_quarterly is not None and eps_growth is not None:
        if earnings_quarterly > eps_growth:
            score += 1
            verdicts.append(
                ("pass", "Recent quarterly earnings growth is accelerating")
            )
        else:
            verdicts.append(
                ("warn", "Earnings growth not accelerating quarter-over-quarter")
            )
    else:
        verdicts.append(("warn", "Quarterly earnings trend data not available"))

    # 6. Operating margin > 20%
    op_margin = info.get("operatingMargins")
    if op_margin is not None:
        pct = op_margin * 100
        if op_margin > 0.20:
            score += 1
            verdicts.append(
                ("pass", f"Operating margin {pct:.1f}% indicates efficient growth")
            )
        else:
            verdicts.append(
                ("warn", f"Operating margin {pct:.1f}% below 20% threshold")
            )
    else:
        verdicts.append(("warn", "Operating margin data not available"))

    pct_score = score / 6
    if pct_score >= 0.67:
        summary = "Strong growth trajectory with earnings and revenue both expanding."
    elif pct_score >= 0.33:
        summary = "Moderate growth — some metrics positive, others lagging industry."
    else:
        summary = "Growth signals are weak across multiple dimensions."

    return SectionScore("Growth", score, 6, summary, verdicts)
