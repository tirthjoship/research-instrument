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
        "+1.00 = exactly with the market. Above 1.0 means it typically moves "
        "more than the market (SPY = 1.0)."
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
    # ── Risk tab redesign terms (Task 10) ─────────────────────────────────────
    "Effective bets": (
        "How many truly independent bets your book behaves like, after "
        "accounting for holdings that move together (Meucci ENB). Lower = "
        "fewer genuinely separate risks — a concentration signal."
    ),
    "Adjusted R²": (
        "The share of your book's moves explained by the market factors, "
        "adjusted down for the number of factors used so the fit isn't "
        "flattered by simply counting more factors."
    ),
    "Bootstrap band": (
        "A range showing how much an estimate would wobble if the sample "
        "days were resampled. A wider band means less statistical certainty "
        "— the true value could land anywhere inside it."
    ),
    "Downside beta": (
        "Beta measured only on market-DOWN days (semi-beta, Ang-Chen-Xing). "
        "It describes how the book tends to move when the market falls — "
        "which can differ from its behaviour on up days."
    ),
    "Risk contribution": (
        "Each holding's share of the book's total variance (Euler "
        "decomposition), summing to 100%. Can differ a great deal from its "
        "dollar weight — a small volatile name can own more risk than a "
        "large calm one."
    ),
    "VIF": (
        "Variance Inflation Factor. Measures how much two factors overlap. "
        "VIF > 5 means those factors move so together they act as one shared "
        "influence — their individual net-beta figures cannot be read as "
        "fully independent."
    ),
    "Diversification ratio": (
        "Weighted-average holding volatility divided by the book's volatility "
        "(Choueifaty). Higher = more offsetting movement among holdings; "
        "1.0 = no diversification benefit at all."
    ),
    "HHI": (
        "Herfindahl-Hirschman Index — a standard concentration score applied "
        "here to sector weights. Higher = more of the book clustered in "
        "fewer sectors."
    ),
    "GICS sector": (
        "The Global Industry Classification Standard used to group holdings "
        "by the part of the economy they operate in. Used here to show where "
        "the book clusters by industry."
    ),
    "Drift": (
        "How much a factor exposure has shifted over recent weeks versus its "
        "longer-run level. A rising line crossing a defined threshold is a "
        "prompt to confirm the change was intentional."
    ),
    "Risk line": (
        "A pre-set threshold you defined; crossing it surfaces an amber flag "
        "as a prompt to look here and confirm the reading is intentional. "
        "A descriptive dial, not a validated edge."
    ),
    "Coverage": (
        "The share of the book (by holding count) that had enough price "
        "history to measure. Holdings outside coverage are honestly excluded, "
        "not assumed to have zero exposure."
    ),
    "Concentration": (
        "How much of the book's risk sits in a few holdings, sectors, or "
        "factors rather than spread across many. Measured here as systematic "
        "share and HHI — a description of structure, not a verdict."
    ),
    # ── S3 Screener redesign terms ─────────────────────────────────────────────
    "Evidence score": (
        "Equal-weight average of the factor z-scores. Higher = more factors look "
        "strong now. A ranking aid, not a return forecast."
    ),
    "Percentile": (
        "Where a name ranks among this week's trend-eligible cohort. p95 = stronger "
        "than 95% of them — not vs its sector, not vs the full universe."
    ),
    "Low-vol factor": (
        "How little the price swings (trailing volatility). Higher score = steadier, "
        "smaller drawdowns historically. Descriptive, not a forecast."
    ),
    "Analyst spread": (
        "Width of today's analyst price-target range (high vs low). A dispersion "
        "signal, not estimate-revision over time."
    ),
    "Trend gate": (
        "A loose filter that keeps only names above their 200-day average. Most "
        "survivors aren't special — the ranking is the selective part."
    ),
    "Reason bucket": (
        "A plain-English grouping (e.g. cheap & high-quality) derived from a name's "
        "strongest factors, so you see the kind of opportunity before the name."
    ),
    "Showing": (
        "The top names from this week's screen — a research shortlist to start "
        "digging into, not trade signals."
    ),
    "As of": (
        "The screen's run date. Everything shown is current evidence as of this "
        "date — never a projection of next week."
    ),
    "Factors": (
        "How many evidence factors are scored per name this week (momentum, "
        "analyst spread, quality, value, and — once live — low-volatility)."
    ),
    "Trust the signal": (
        "Verdict from our pre-registered IC backtest gate. INCONCLUSIVE = no proven "
        "forward edge yet, so the ranking stays descriptive evidence, not a forecast."
    ),
    # ── Portfolio tab redesign terms (Task 0) ─────────────────────────────────
    "Concentration (top 5)": (
        "The combined weight of your five largest positions. Higher means more "
        "of your book rides on a few names — more single-name risk."
    ),
    "Needs review": (
        "Holdings where the discipline rule fired (REDUCE, TRIM, or REVIEW). "
        "This list grows with problems, not with how many stocks you own."
    ),
    "Treemap colour": (
        "Tile size is the position's weight in your book. Tile colour is the "
        "lens you pick: realised profit/loss, today's move, or the verdict. "
        "Colour is actual history, not a projection."
    ),
    "Dividend yield": (
        "Trailing dividend income as a percent of price, from the data provider. "
        "Shown as a dash when the provider reports none."
    ),
    "Excess return vs SPY": (
        "Your portfolio's return minus the S&P 500's over the same window. "
        "Positive means you beat the benchmark; actual, not projected."
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
