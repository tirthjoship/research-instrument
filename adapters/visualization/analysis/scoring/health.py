"""Financial health scoring for stock analysis."""

from __future__ import annotations

from typing import Any, Literal

from adapters.visualization.analysis.models import SectionScore


def score_health(info: dict[str, Any]) -> SectionScore:
    """6 financial health checks: D/E, current ratio, cash vs debt, FCF, D/E trend, interest coverage."""
    verdicts: list[tuple[Literal["pass", "warn", "fail"], str]] = []
    score = 0

    # 1. D/E < 100%
    de = info.get("debtToEquity")
    if de is not None:
        if de < 100:
            score += 1
            verdicts.append(
                (
                    "pass",
                    f"Debt-to-equity {de:.1f}% is below 100% — manageable leverage",
                )
            )
        else:
            verdicts.append(("warn", f"Debt-to-equity {de:.1f}% is elevated"))
    else:
        verdicts.append(("warn", "Debt-to-equity data not available"))

    # 2. Current ratio > 1.5
    current_ratio = info.get("currentRatio")
    if current_ratio is not None:
        if current_ratio > 1.5:
            score += 1
            verdicts.append(
                (
                    "pass",
                    f"Current ratio {current_ratio:.2f} — adequate liquidity buffer",
                )
            )
        else:
            verdicts.append(
                (
                    "warn",
                    f"Current ratio {current_ratio:.2f} is below 1.5 — liquidity concern",
                )
            )
    else:
        verdicts.append(("warn", "Current ratio data not available"))

    # 3. Cash > total debt
    cash = info.get("totalCash")
    total_debt = info.get("totalDebt")
    if cash is not None and total_debt is not None:
        if cash > total_debt:
            score += 1
            verdicts.append(
                (
                    "pass",
                    f"Cash (${cash / 1e9:.1f}B) exceeds total debt (${total_debt / 1e9:.1f}B)",
                )
            )
        else:
            verdicts.append(
                (
                    "warn",
                    f"Debt (${total_debt / 1e9:.1f}B) exceeds cash (${cash / 1e9:.1f}B)",
                )
            )
    else:
        verdicts.append(("warn", "Cash or debt data not available for comparison"))

    # 4. FCF positive
    fcf = info.get("freeCashflow")
    if fcf is not None:
        if fcf > 0:
            score += 1
            verdicts.append(("pass", f"Free cash flow positive at ${fcf / 1e9:.1f}B"))
        else:
            verdicts.append(
                (
                    "fail",
                    f"Negative free cash flow (${fcf / 1e9:.1f}B) — cash burn risk",
                )
            )
    else:
        verdicts.append(("warn", "Free cash flow data not available"))

    # 5. D/E improving proxy: D/E < 50 suggests already conservative
    if de is not None:
        if de < 50:
            score += 1
            verdicts.append(
                ("pass", f"Low leverage D/E {de:.1f}% suggests balance sheet strength")
            )
        else:
            verdicts.append(
                ("warn", "High D/E leaves limited room for further leverage")
            )
    else:
        verdicts.append(("warn", "Cannot assess leverage trend without D/E data"))

    # 6. Interest coverage (EBIT / interest expense)
    ebitda = info.get("ebitda")
    interest = info.get("interestExpense") or info.get("totalOtherIncomeExpenseNet")
    if ebitda is not None and interest is not None and interest != 0:
        try:
            coverage = abs(float(ebitda)) / abs(float(interest))
            if coverage > 5:
                score += 1
                verdicts.append(
                    (
                        "pass",
                        f"Interest coverage {coverage:.1f}x — strong debt service capacity",
                    )
                )
            else:
                verdicts.append(
                    (
                        "warn",
                        f"Interest coverage {coverage:.1f}x — tight but manageable",
                    )
                )
        except (TypeError, ZeroDivisionError):
            verdicts.append(("warn", "Cannot compute interest coverage"))
    else:
        verdicts.append(("warn", "Interest coverage data not available"))

    pct_score = score / 6
    if pct_score >= 0.67:
        summary = "Balance sheet is strong with adequate liquidity and manageable debt."
    elif pct_score >= 0.33:
        summary = "Mixed health signals — watch leverage and liquidity ratios."
    else:
        summary = "Financial health shows stress — debt or liquidity concerns present."

    return SectionScore("Financial Health", score, 6, summary, verdicts)
