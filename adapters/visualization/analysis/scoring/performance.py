"""Performance scoring for stock analysis."""

from __future__ import annotations

from typing import Any, Literal

from adapters.visualization.analysis.models import SectionScore


def score_performance(info: dict[str, Any]) -> SectionScore:
    """6 performance checks: ROE, ROE vs industry, gross margin, op margin, profit margin, earnings growth."""
    verdicts: list[tuple[Literal["pass", "warn", "fail"], str]] = []
    score = 0

    # 1. ROE > 15%
    roe = info.get("returnOnEquity")
    if roe is not None:
        pct = roe * 100
        if roe > 0.15:
            score += 1
            verdicts.append(("pass", f"ROE {pct:.1f}% exceeds 15% quality threshold"))
        else:
            verdicts.append(("warn", f"ROE {pct:.1f}% below 15% threshold"))
    else:
        verdicts.append(("warn", "Return on Equity data not available"))

    # 2. ROE vs industry (proxy: > 20%)
    if roe is not None:
        if roe > 0.20:
            score += 1
            verdicts.append(
                ("pass", f"ROE {roe * 100:.1f}% above industry average (20%)")
            )
        else:
            verdicts.append(("warn", "ROE below industry-beating threshold of 20%"))
    else:
        verdicts.append(("warn", "Cannot benchmark ROE vs industry"))

    # 3. Gross margin > 40%
    gross_margin = info.get("grossMargins")
    if gross_margin is not None:
        pct = gross_margin * 100
        if gross_margin > 0.40:
            score += 1
            verdicts.append(
                ("pass", f"Gross margin {pct:.1f}% indicates pricing power")
            )
        else:
            verdicts.append(("warn", f"Gross margin {pct:.1f}% is below 40%"))
    else:
        verdicts.append(("warn", "Gross margin data not available"))

    # 4. Operating margin > 15%
    op_margin = info.get("operatingMargins")
    if op_margin is not None:
        pct = op_margin * 100
        if op_margin > 0.15:
            score += 1
            verdicts.append(
                ("pass", f"Operating margin {pct:.1f}% shows operational efficiency")
            )
        else:
            verdicts.append(("warn", f"Operating margin {pct:.1f}% is thin"))
    else:
        verdicts.append(("warn", "Operating margin data not available"))

    # 5. Net profit margin > 10%
    net_margin = info.get("profitMargins")
    if net_margin is not None:
        pct = net_margin * 100
        if net_margin > 0.10:
            score += 1
            verdicts.append(("pass", f"Net profit margin {pct:.1f}% healthy (>10%)"))
        else:
            verdicts.append(("warn", f"Net profit margin {pct:.1f}% is thin"))
    else:
        verdicts.append(("warn", "Net profit margin data not available"))

    # 6. Earnings growth > 10%
    eps_growth = info.get("earningsGrowth")
    if eps_growth is not None:
        if eps_growth > 0.10:
            score += 1
            verdicts.append(
                (
                    "pass",
                    f"Earnings growing {eps_growth * 100:.1f}% — above 10% threshold",
                )
            )
        else:
            verdicts.append(
                ("warn", f"Earnings growth {eps_growth * 100:.1f}% below 10%")
            )
    else:
        verdicts.append(("warn", "Earnings growth data not available"))

    pct_score = score / 6
    if pct_score >= 0.67:
        summary = "Strong return metrics and margins signal high-quality profitability."
    elif pct_score >= 0.33:
        summary = "Mixed performance — some margin or return metrics are sub-threshold."
    else:
        summary = "Performance is below par — margins and returns need improvement."

    return SectionScore("Performance", score, 6, summary, verdicts)
