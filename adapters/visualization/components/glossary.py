"""Single source of truth for plain-English term definitions.

Feeds (a) the .tip hover tooltips used across tabs, (b) the Trust tab's
reference table. Definitions mirror README.md's glossary — keep in sync.
"""

from __future__ import annotations

import html

GLOSSARY: dict[str, str] = {
    "Confidence interval (CI)": (
        'The range the true average plausibly sits in. "CI low > 0" = even '
        "the pessimistic read is a profit."
    ),
    "Slippage": (
        "The hidden cost of actually buying a thinly-traded stock — you move "
        "the price against yourself."
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
        "Accidentally letting future data leak into a prediction — makes "
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
