"""Single source of truth for plain-English term definitions.

Feeds (a) the .tip hover tooltips used across tabs, (b) the Trust tab's
reference table. Definitions mirror README.md's glossary — keep in sync.
"""

from __future__ import annotations

import html

GLOSSARY: dict[str, str] = {
    # ── Original 12 terms ──────────────────────────────────────────────────────
    "Confidence interval (CI)": (
        'The range the true average plausibly sits in. "CI low > 0" = even '
        "the pessimistic read is a profit."
    ),
    "Slippage": (
        "The hidden cost of trading a thinly-traded stock — your own order "
        "moves the price against you."
    ),
    "Tercile": (
        'Split into thirds. "Bottom liquidity tercile" = the third of stocks '
        "that are hardest to trade."
    ),
    "Abnormal return": (
        "A stock's return minus what a comparable index did over the same "
        'days — the part the stock did "on its own."'
    ),
    "IC (information coefficient)": (
        "Correlation between a signal's ranking and what actually happened "
        "next. Zero = the signal knows nothing."
    ),
    "Sharpe ratio": (
        "Return earned per unit of risk taken. Higher is better — it rewards "
        "steady gains, not lucky volatile ones."
    ),
    "Bootstrap": (
        "Re-running a test on thousands of resampled versions of the data to "
        "see how much of the result is just luck. A confidence interval that "
        '"spans zero" means the edge could easily be nothing.'
    ),
    "Pre-registration": (
        "Locking the test rules before seeing results, so you can't move the "
        "goalposts."
    ),
    "Look-ahead bias": (
        "Accidentally letting future data leak into a model — makes "
        "backtests look great and live trading fail."
    ),
    "Systematic share": (
        "How much of your book's movement is explained by broad market "
        "forces rather than your individual stock picks."
    ),
    "Beta": (
        "How much a stock (or your whole book) moves when the market moves. "
        "+1.00 = exactly with the market."
    ),
    "Evidence grade": (
        "Where a stock ranks on present-day facts (valuation, quality, "
        "health) versus the screened universe. A description, not a forecast."
    ),
    # ── New terms (Stage 0 expansion) ─────────────────────────────────────────
    "Net beta": (
        "Your whole book's net sensitivity to the market after long and short "
        "positions offset each other. Zero = market-neutral."
    ),
    "Universe": (
        "The defined set of stocks the screen runs over. A stock not in the "
        "universe receives no evidence grade."
    ),
    "Cleared the bar": (
        "A stock passed every pre-registered gate (liquidity, data quality, "
        "minimum history) and entered the evidence screen."
    ),
    "Abstention": (
        "The screen declined to rank a stock — either because it failed a "
        "gate or because the evidence was too thin to be meaningful."
    ),
    "Directional accuracy": (
        "How often the up/down call matched what happened next. ~50% = no "
        "edge over a coin flip."
    ),
    "Rank-IC": (
        "Correlation between a signal's RANKING of stocks and the order of "
        "what happened next. Zero = the ranking knows nothing."
    ),
    "Evidence screen": (
        "The systematic pass over the universe that scores each stock on "
        "present-day factual data. It describes; it does not forecast."
    ),
    "Trend filter": (
        "A rule that checks whether a stock's price is above or below a "
        "long-run moving average, used to flag macro momentum context."
    ),
    "Concentrated risk": (
        "When a single position or a correlated cluster dominates the book's "
        "risk, so one bad outcome disproportionately hurts the whole."
    ),
    "Reduce flag": (
        "A signal to take some risk off a position — trim its size without "
        "exiting fully."
    ),
    "Trim flag": (
        "A signal to reduce the size of an existing holding, not to exit " "fully."
    ),
    "Hold flag": (
        "A signal that the current position size is appropriate — no action "
        "warranted."
    ),
    "Add-on flag": (
        "A signal that adding to an existing holding fits the book's current "
        "risk capacity."
    ),
    "Book health": (
        "A summary of whether the portfolio's diversification, liquidity, "
        "and factor exposures are within acceptable ranges."
    ),
    "Momentum factor": (
        "A stock characteristic based on its recent relative performance — "
        "stocks that have risen more than peers over a look-back window."
    ),
    "Revision factor": (
        "A stock characteristic based on how much third-party analyst "
        "earnings estimates have moved up or down recently."
    ),
    "Quality factor": (
        "A stock characteristic capturing profitability, earnings stability, "
        "and balance-sheet strength relative to peers."
    ),
    "Value factor": (
        "A stock characteristic based on how cheap a stock is relative to "
        "its fundamentals — e.g. low price-to-earnings or price-to-book."
    ),
    "Industry percentile": (
        "Where a stock ranks within its industry on a given metric, "
        "removing sector-level effects from the comparison."
    ),
    "Analyst consensus": (
        "The central tendency of third-party analyst estimates or ratings for "
        "a stock. Displayed as-sourced; this project does not adopt it."
    ),
    "Dispersion": (
        "The spread among third-party analyst estimates — wide dispersion "
        "signals high uncertainty about the stock's near-term path."
    ),
    "Snowflake": (
        "A radar-chart visual showing a stock's scores across multiple "
        "factor dimensions at once."
    ),
    "Portfolio fit": (
        "An assessment of how well a stock complements the existing book — "
        "factoring in beta overlap, concentration, and liquidity."
    ),
    "EMH": (
        "Efficient-Market Hypothesis: public information is already in the "
        "price, so a public signal rarely beats the market on its own."
    ),
    "SMA-200": (
        "The 200-day simple moving average of a stock's closing price — a "
        "widely watched long-run trend reference level."
    ),
    "Falsified": (
        "A hypothesis that was pre-registered and then failed its gate when "
        "tested on real data. Honest accounting of what did not work."
    ),
    "Snowflake chart": (
        "Synonym for Snowflake — a radar chart summarising multiple factor "
        "scores in a single view."
    ),
    # ── Triage strip (Task 8 / home hybrid) ──────────────────────────────────
    "Need review": (
        "Holdings whose discipline verdict is REDUCE or TRIM — signals that "
        "a position size may need adjusting. These are review prompts, not "
        "trade instructions."
    ),
    "vs Market (1y)": (
        "How the book's total return compared to SPY over the trailing year. "
        "Not pre-computed in the weekly brief — re-run the macro-beta report "
        "for a live figure."
    ),
    "Regime": (
        "The current broad market regime (e.g. RISK_ON / RISK_OFF / NEUTRAL) "
        "as classified by the macro overlay. It provides context for discipline "
        "decisions but does not alter the evidence grades."
    ),
    # ── Home Front-Desk strip (S4) ────────────────────────────────────────────
    "Screen": (
        "The systematic weekly pass over the universe that scores each stock "
        "on present-day evidence. Shows how many names cleared every gate."
    ),
    # ── Screen diagnostics funnel (Task 5 / ADR-05x) ─────────────────────────
    "Had history": (
        "Of the universe scanned, these names had enough price history (at "
        "least the minimum required trading days) to be scored. Names missing "
        "sufficient history are excluded before scoring begins."
    ),
    "Above trend": (
        "Of those with sufficient history, these names were trading above the "
        "long-run trend filter (SMA-200). Below-trend names are excluded from "
        "the scored pool — they pass the data gate but not the trend gate."
    ),
}


def tip(term: str) -> str:
    """Wrap *term* in a hover-tooltip span if a definition exists."""
    definition = GLOSSARY.get(term)
    if definition is None:
        return term
    return (
        f'<span class="tip" data-tip="{html.escape(definition, quote=True)}">'
        f"{html.escape(term)}</span>"
    )
