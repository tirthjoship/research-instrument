"""Valuation scoring for stock analysis."""

from __future__ import annotations

from typing import Any, Literal

from adapters.visualization.analysis.models import SectionScore
from adapters.visualization.components.currency import (
    currency_for_ticker,
    currency_symbol,
)


def sector_pe_avg(sector: str) -> float:
    """Return approximate sector-average P/E reference."""
    _SECTOR_PE: dict[str, float] = {
        "Technology": 30,
        "Healthcare": 25,
        "Financial Services": 18,
        "Consumer Cyclical": 22,
        "Consumer Defensive": 20,
        "Industrials": 22,
        "Energy": 15,
        "Basic Materials": 18,
        "Utilities": 20,
        "Real Estate": 35,
        "Communication Services": 22,
    }
    return _SECTOR_PE.get(sector, 22)


def score_valuation(
    info: dict[str, Any], peers: list[dict[str, Any]], ticker: str = ""
) -> SectionScore:
    """6 valuation checks: P/E, PEG, P/B, analyst consensus, price vs target, FCF yield."""
    sym = currency_symbol(currency_for_ticker(ticker))
    verdicts: list[tuple[Literal["pass", "warn", "fail"], str]] = []
    score = 0

    # 1. P/E vs sector avg
    pe = info.get("trailingPE")
    sector_pe = sector_pe_avg(info.get("sector", ""))
    if pe is not None:
        if pe < sector_pe:
            score += 1
            verdicts.append(
                ("pass", f"P/E {pe:.1f}x below sector avg ({sector_pe:.0f}x)")
            )
        else:
            verdicts.append(
                ("warn", f"P/E {pe:.1f}x above sector avg ({sector_pe:.0f}x)")
            )
    else:
        verdicts.append(("warn", "P/E ratio not available"))

    # 2. PEG < 2
    peg = info.get("pegRatio")
    if peg is not None:
        if peg < 2:
            score += 1
            verdicts.append(
                (
                    "pass",
                    f"PEG ratio {peg:.2f} indicates reasonable growth-adjusted value",
                )
            )
        else:
            verdicts.append(
                ("fail", f"PEG ratio {peg:.2f} suggests overvalued relative to growth")
            )
    else:
        verdicts.append(("warn", "PEG ratio not available"))

    # 3. P/B < 5
    pb = info.get("priceToBook")
    if pb is not None:
        if pb < 5:
            score += 1
            verdicts.append(
                ("pass", f"Price-to-book {pb:.2f}x is within acceptable range")
            )
        else:
            verdicts.append(("warn", f"Price-to-book {pb:.2f}x is elevated"))
    else:
        verdicts.append(("warn", "Price-to-book not available"))

    # 4. Analyst consensus >= Buy
    rec_mean = info.get("recommendationMean", 3) or 3
    if rec_mean <= 2.5:
        score += 1
        verdicts.append(
            ("pass", f"Analyst consensus is Buy (mean score {rec_mean:.1f})")
        )
    elif rec_mean <= 3.5:
        verdicts.append(
            ("warn", f"Analyst consensus is Hold (mean score {rec_mean:.1f})")
        )
    else:
        verdicts.append(
            ("fail", f"Analyst consensus is Sell (mean score {rec_mean:.1f})")
        )

    # 5. Price < target
    current = info.get("currentPrice") or info.get("regularMarketPrice", 0)
    target = info.get("targetMeanPrice")
    if current and target and current > 0:
        upside = (target - current) / current * 100
        if upside > 0:
            score += 1
            verdicts.append(
                (
                    "pass",
                    f"Analyst target {sym}{target:.2f} implies {upside:.1f}% upside",
                )
            )
        else:
            verdicts.append(
                (
                    "fail",
                    f"Analyst target {sym}{target:.2f} implies {abs(upside):.1f}% downside",
                )
            )
    else:
        verdicts.append(("warn", "Analyst price target not available"))

    # 6. FCF yield > 3%
    fcf = info.get("freeCashflow")
    mc = info.get("marketCap")
    if fcf and mc and mc > 0:
        fcf_yield = fcf / mc * 100
        if fcf_yield > 3:
            score += 1
            verdicts.append(
                ("pass", f"FCF yield {fcf_yield:.1f}% exceeds 3% threshold")
            )
        else:
            verdicts.append(("warn", f"FCF yield {fcf_yield:.1f}% below 3% threshold"))
    else:
        verdicts.append(("warn", "Free cash flow data not available"))

    pct = score / 6
    if pct >= 0.67:
        summary = (
            "Trading at a reasonable or discounted valuation with analyst support."
        )
    elif pct >= 0.33:
        summary = "Mixed valuation signals — some metrics elevated, some reasonable."
    else:
        summary = "Valuation appears stretched across multiple measures."

    return SectionScore("Valuation", score, 6, summary, verdicts)
