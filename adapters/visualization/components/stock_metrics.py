"""Central copy for stock-analysis metric tooltips: meaning + measurement basis."""

from __future__ import annotations

from adapters.visualization.components.info_tip import render_info

# key -> (plain meaning, measurement basis / source line)
STOCK_METRICS: dict[str, tuple[str, str]] = {
    "pe_ttm": (
        "Price divided by trailing earnings; higher = pricier per dollar of profit.",
        "trailing P/E vs peers",
    ),
    "pe_fwd": (
        "Price divided by analyst forward earnings; a third-party estimate, not our forecast.",
        "attributed / analyst consensus",
    ),
    "peg": (
        "PEG = P/E divided by growth; below 1.0 means not expensive relative to its own growth.",
        "P/E relative to growth; <1.0 = P/E below the growth rate",
    ),
    "ev_ebitda": (
        "Enterprise value over EBITDA; capital-structure-neutral valuation multiple.",
        "yfinance info.enterpriseToEbitda (trailing, no peer comparison shown)",
    ),
    "ps": (
        "Price divided by trailing sales; useful for low-margin or pre-profit businesses without stable earnings.",
        "yfinance info.priceToSalesTrailing12Months (trailing, no peer comparison shown)",
    ),
    "p_fcf": (
        "Price divided by free cash flow.",
        "price / info.freeCashflow (trailing, no peer comparison shown)",
    ),
    "roic": (
        "Return on invested capital; efficiency measure independent of how the company is financed.",
        "EBIT*(1-tax) / (equity+debt-cash) (no peer comparison shown)",
    ),
    "net_debt_ebitda": (
        "Net debt over EBITDA; negative means net cash. Higher multiples mean more years of earnings would be needed to clear net debt.",
        "net debt / EBITDA; lower = less leverage",
    ),
    "interest_coverage": (
        "EBITDA divided by interest expense; how many times interest is covered "
        "(uses EBITDA, not EBIT, so it reads more forgiving than the stricter EBIT-based ratio).",
        "yfinance info.ebitda / info.interestExpense; green when > 5×",
    ),
    "relative_strength": (
        "Price relative to the S&P, indexed to 100; rising = pulling ahead.",
        "NVDA / SPY normalized",
    ),
    "co_movement": (
        "Average correlation of the supply-chain group; high = they trade as a pack.",
        "pairwise correlation",
    ),
}


def metric_info(key: str) -> str:
    meaning, basis = STOCK_METRICS[key]  # KeyError if unknown — by design
    return render_info(meaning, basis)
