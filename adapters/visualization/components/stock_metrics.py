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
        "vs peer percentile",
    ),
    "p_fcf": ("Price divided by free cash flow.", "vs peer percentile"),
    "roic": (
        "Return on invested capital; the cleanest efficiency measure, capital-structure neutral.",
        "vs peer median",
    ),
    "net_debt_ebitda": (
        "Net debt over EBITDA; negative means net cash. Higher multiples mean more years of earnings would be needed to clear net debt.",
        "net debt / EBITDA; lower = less leverage",
    ),
    "interest_coverage": (
        "Operating profit divided by interest expense; how many times interest is covered.",
        "EBIT / interest",
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
