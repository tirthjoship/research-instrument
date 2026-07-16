"""Real regime + market-news signal for the Risk tab's second-opinion.

Risk's live-generation path is CLI-only (weekly-brief's --cite-cases-
independent prefetch, application/cli/brief_commands.py) — the dashboard
risk tab only ever reads the cache. So these helpers have exactly one
caller; no live-vs-cache fact reconciliation needed (unlike Home+Portfolio).

Honesty rule: no real signal -> omit, never fabricate.
"""

from __future__ import annotations

from adapters.visualization.price_cache import _fetch_recent_news_impl
from application.news_context import NewsItem
from domain.regime import Regime

# GICS sector name (the taxonomy adapters/data/sector_provider.py normalizes
# to) -> standard SPDR Select Sector ETF ticker.
_SECTOR_ETF: dict[str, str] = {
    "Information Technology": "XLK",
    "Financials": "XLF",
    "Health Care": "XLV",
    "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP",
    "Materials": "XLB",
    "Industrials": "XLI",
    "Energy": "XLE",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Communication Services": "XLC",
}


def risk_regime_fact(regime: Regime) -> str:
    """Already-computed regime label as a plain fact — zero extra fetch."""
    return f"Regime: {regime.value}"


def dominant_sector(sector_weights: dict[str, float]) -> str | None:
    """The GICS sector with the largest book weight. None on no data."""
    if not sector_weights:
        return None
    return max(sector_weights, key=lambda k: sector_weights[k])


def risk_market_news(
    dominant_sector: str | None, *, benchmark_ticker: str = "SPY"
) -> list[NewsItem]:
    """Real headlines for the benchmark (SPY by default) + ^VIX (always), plus
    the dominant sector's ETF proxy when it maps to a known ticker. Omits
    sector news (never fabricates) when dominant_sector is None or unrecognized.
    """
    tickers = [benchmark_ticker, "^VIX"]
    etf = _SECTOR_ETF.get(dominant_sector) if dominant_sector else None
    if etf is not None:
        tickers.append(etf)

    items: list[NewsItem] = []
    for ticker in tickers:
        raw = _fetch_recent_news_impl(ticker)
        items.extend(NewsItem(**item) for item in raw)
    return items
