"""Stock analyzer — fetches data and computes criteria scores for a single ticker.

Separated from the tab rendering to keep the tab file focused on layout.
All yfinance calls go through price_cache for TTL caching.
"""

from __future__ import annotations

import os
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from loguru import logger

if TYPE_CHECKING:
    from application.analyst_panel import AnalystPanel
    from application.news_context import NewsContext


@dataclass
class SectionScore:
    """Score for one analysis section (e.g., Valuation 4/6)."""

    title: str
    score: int
    max_score: int
    summary: str
    verdicts: list[tuple[Literal["pass", "warn", "fail"], str]]


@dataclass
class AnalysisResult:
    """Complete analysis result for one ticker."""

    ticker: str
    company_name: str
    current_price: float
    change_pct: float
    market_cap: float
    sector: str

    # Signal radar scores (0-10 per dimension)
    signal_scores: dict[str, float] = field(default_factory=dict)

    # Overall verdict
    grade: str = "hold"
    conviction: float = 5.0
    hold_duration: str = "Monitor daily"

    # Analyst consensus
    analyst_count: int = 0
    analyst_mean_target: float = 0.0
    analyst_recommendation: str = ""

    # Per-section scores
    valuation: SectionScore | None = None
    growth: SectionScore | None = None
    performance: SectionScore | None = None
    health: SectionScore | None = None
    ownership: SectionScore | None = None
    sentiment: SectionScore | None = None
    supply_chain: SectionScore | None = None

    # Raw data for charts
    info: dict[str, Any] = field(default_factory=dict)
    quarterly_financials: Any = None
    quarterly_balance_sheet: Any = None
    insider_transactions: list[dict[str, Any]] = field(default_factory=list)
    buzz_signals: list[Any] = field(default_factory=list)
    recommendation_data: Any = None
    peer_data: list[dict[str, Any]] = field(default_factory=list)
    supply_chain_group: dict[str, Any] | None = None

    # E1: Industry-relative percentiles (metric -> 0-100 or None for DATA_GAP)
    peer_percentiles: dict[str, float | None] = field(default_factory=dict)

    # E2: Attributed third-party analyst panel (None if import fails)
    analyst_panel: "AnalystPanel | None" = None

    # E3: Attributed news/event context (None if no signals)
    news_context: "NewsContext | None" = None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def analyze_ticker(
    ticker: str, db_path: str = "data/recommendations.db"
) -> AnalysisResult:
    """Run full analysis for a single ticker. Returns AnalysisResult."""
    from adapters.visualization.price_cache import (
        _batch_fetch_prices_impl,
        _fetch_insider_transactions_impl,
        _fetch_quarterly_financials_impl,
        _fetch_ticker_info_impl,
    )

    ticker = ticker.upper().strip()

    # 1. Fetch ticker info (fundamentals)
    info = _fetch_ticker_info_impl(ticker)

    # 2. Fetch price
    prices = _batch_fetch_prices_impl((ticker,))
    price_data = prices.get(ticker, {})
    current_price = price_data.get(
        "price", info.get("currentPrice", info.get("regularMarketPrice", 0.0))
    )
    change_pct = price_data.get("change_pct", 0.0)

    # 3. Fetch quarterly financials
    qf, qbs, qcf = _fetch_quarterly_financials_impl(ticker)

    # 4. Fetch insider transactions
    insider_txns = _fetch_insider_transactions_impl(ticker)

    # 5. Fetch buzz signals from DB
    buzz = _load_buzz_signals(ticker, db_path)

    # 6. Fetch recommendation from DB
    rec = _load_recommendation(ticker, db_path)

    # 7. Find supply chain group
    sc_group = _find_supply_chain_group(ticker)

    # 8. Fetch peer data for comparison
    peers = _get_sector_peers(ticker, info, sc_group)

    # Build result
    result = AnalysisResult(
        ticker=ticker,
        company_name=info.get("longName", info.get("shortName", ticker)),
        current_price=float(current_price or 0.0),
        change_pct=float(change_pct or 0.0),
        market_cap=float(info.get("marketCap", 0) or 0),
        sector=info.get("sector", "Unknown") or "Unknown",
        info=info,
        quarterly_financials=qf,
        quarterly_balance_sheet=qbs,
        insider_transactions=insider_txns,
        buzz_signals=buzz,
        recommendation_data=rec,
        peer_data=peers,
        supply_chain_group=sc_group,
    )

    # Compute sections
    result.valuation = _score_valuation(info, peers)
    result.growth = _score_growth(info)
    result.performance = _score_performance(info)
    result.health = _score_health(info)
    result.ownership = _score_ownership(info, insider_txns)
    result.sentiment = _score_sentiment(buzz)
    result.supply_chain = _score_supply_chain(sc_group)

    # Compute signal radar
    result.signal_scores = _compute_signal_radar(
        info, buzz, rec, sc_group, insider_txns
    )

    # Compute overall verdict from DB recommendation
    if rec:
        result.grade = getattr(rec, "grade", "hold")
        result.conviction = getattr(rec, "composite_score", 0.5) * 10

    # Hold duration from horizon signals
    if rec and hasattr(rec, "horizon_signals"):
        signals = rec.horizon_signals if isinstance(rec.horizon_signals, dict) else {}
        bullish = sum(1 for s in signals.values() if s == "bullish")
        if bullish == 3:
            result.hold_duration = "Hold until flip (10+ days)"
        elif signals.get("2d") == "bullish" and signals.get("5d") != "bullish":
            result.hold_duration = "Short hold (2-3 days)"
        elif signals.get("2d") != "bullish" and signals.get("10d") == "bullish":
            result.hold_duration = "Position hold (5-10 days)"
        else:
            result.hold_duration = "Monitor daily"

    # Analyst data
    result.analyst_count = int(info.get("numberOfAnalystOpinions", 0) or 0)
    result.analyst_mean_target = float(info.get("targetMeanPrice", 0) or 0)
    rec_mean = info.get("recommendationMean", 3) or 3
    if rec_mean <= 1.5:
        result.analyst_recommendation = "Strong Buy"
    elif rec_mean <= 2.5:
        result.analyst_recommendation = "Buy"
    elif rec_mean <= 3.5:
        result.analyst_recommendation = "Hold"
    else:
        result.analyst_recommendation = "Sell"

    # E2: Attributed analyst panel — normalise yfinance key names before calling
    import datetime as _dt

    as_of = _dt.date.today().isoformat()
    try:
        from application.analyst_panel import build_analyst_panel

        # build_analyst_panel expects "analyst_count" and "analyst_recommendation_mean"
        # (its own field naming); yfinance uses different key names.
        panel_info: dict[str, object] = dict(info)
        panel_info["analyst_count"] = info.get("numberOfAnalystOpinions", 0)
        panel_info["analyst_recommendation_mean"] = info.get("recommendationMean")
        result.analyst_panel = build_analyst_panel(panel_info, as_of)
    except Exception as exc:
        logger.warning("Could not build analyst panel for {}: {}", ticker, exc)
        result.analyst_panel = None

    # E3: Attributed news/event context — map BuzzSignal objects to dicts
    try:
        from application.news_context import build_news_context

        signal_dicts: list[dict[str, object]] = []
        for b in buzz:
            fetched = getattr(b, "fetched_at", None)
            date_str = str(fetched)[:10] if fetched is not None else ""
            source = getattr(b, "source", "unknown")
            mention_count = getattr(b, "mention_count", 0)
            sentiment = getattr(b, "sentiment_raw", 0.0)
            sent_label = (
                "positive"
                if float(sentiment) > 0
                else "negative" if float(sentiment) < 0 else "neutral"
            )
            title = f"{source}: {mention_count} mention(s), sentiment {sent_label} ({float(sentiment):.2f})"
            signal_dicts.append({"source": source, "title": title, "date": date_str})
        result.news_context = build_news_context(signal_dicts, 10)
    except Exception as exc:
        logger.warning("Could not build news context for {}: {}", ticker, exc)
        result.news_context = None

    # E1: Industry-relative peer percentiles
    # peer_data dicts have: ticker, name, pe, market_cap, change_pct, role
    try:
        from domain.peer_relative import sector_percentile

        peer_percentiles: dict[str, float | None] = {}
        if peers:
            peer_pe_values: list[float | None] = [p.get("pe") for p in peers]
            peer_mc_values: list[float | None] = [p.get("market_cap") for p in peers]
            raw_pe = info.get("trailingPE")
            this_pe: float | None = float(raw_pe) if raw_pe is not None else None
            this_mc: float | None = float(info.get("marketCap", 0) or 0) or None

            peer_percentiles["P/E"] = sector_percentile(this_pe, peer_pe_values)
            peer_percentiles["Market Cap"] = sector_percentile(this_mc, peer_mc_values)
            # Additional comparable metrics available in info and peers if present
            raw_pb = info.get("priceToBook")
            this_pb: float | None = float(raw_pb) if raw_pb is not None else None
            # peer_data doesn't carry P/B — will be None (DATA_GAP) which is correct
            peer_percentiles["P/B"] = sector_percentile(this_pb, [None] * len(peers))
        else:
            # No peers — all DATA_GAP; log limitation
            logger.info(
                "No peer data for {} — peer percentiles will be DATA_GAP", ticker
            )
            peer_percentiles = {"P/E": None, "Market Cap": None, "P/B": None}
        result.peer_percentiles = peer_percentiles
    except Exception as exc:
        logger.warning("Could not compute peer percentiles for {}: {}", ticker, exc)
        result.peer_percentiles = {}

    return result


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------


def _score_valuation(info: dict[str, Any], peers: list[dict[str, Any]]) -> SectionScore:
    """6 valuation checks: P/E, PEG, P/B, analyst consensus, price vs target, FCF yield."""
    verdicts: list[tuple[Literal["pass", "warn", "fail"], str]] = []
    score = 0

    # 1. P/E vs sector avg
    pe = info.get("trailingPE")
    sector_pe = _sector_pe_avg(info.get("sector", ""))
    if pe is not None:
        if pe < sector_pe:
            score += 1
            verdicts.append(
                ("pass", f"P/E {pe:.1f}x is below sector avg ({sector_pe:.0f}x)")
            )
        else:
            verdicts.append(
                ("warn", f"P/E {pe:.1f}x is above sector avg ({sector_pe:.0f}x)")
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
                ("pass", f"Analyst target ${target:.2f} implies {upside:.1f}% upside")
            )
        else:
            verdicts.append(
                (
                    "fail",
                    f"Analyst target ${target:.2f} implies {abs(upside):.1f}% downside",
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
            verdicts.append(
                ("warn", f"FCF yield {fcf_yield:.1f}% is below 3% threshold")
            )
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


def _sector_pe_avg(sector: str) -> float:
    """Return approximate sector-average P/E for reference."""
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


def _score_growth(info: dict[str, Any]) -> SectionScore:
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


def _score_performance(info: dict[str, Any]) -> SectionScore:
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
            verdicts.append(("warn", f"ROE {pct:.1f}% is below 15% threshold"))
    else:
        verdicts.append(("warn", "Return on Equity data not available"))

    # 2. ROE > industry (proxy: > 20%)
    if roe is not None:
        if roe > 0.20:
            score += 1
            verdicts.append(
                ("pass", f"ROE {roe * 100:.1f}% is above industry average (20%)")
            )
        else:
            verdicts.append(("warn", "ROE below industry-beating threshold of 20%"))
    else:
        verdicts.append(("warn", "Cannot benchmark ROE to industry"))

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
            verdicts.append(("warn", f"Gross margin {pct:.1f}% below 40% benchmark"))
    else:
        verdicts.append(("warn", "Gross margin data not available"))

    # 4. Operating margin > 20%
    op_margin = info.get("operatingMargins")
    if op_margin is not None:
        pct = op_margin * 100
        if op_margin > 0.20:
            score += 1
            verdicts.append(
                ("pass", f"Operating margin {pct:.1f}% reflects operational efficiency")
            )
        else:
            verdicts.append(("warn", f"Operating margin {pct:.1f}% is modest"))
    else:
        verdicts.append(("warn", "Operating margin data not available"))

    # 5. Profit margin improving (proxy: net margin > 10%)
    net_margin = info.get("profitMargins")
    if net_margin is not None:
        pct = net_margin * 100
        if net_margin > 0.10:
            score += 1
            verdicts.append(("pass", f"Net profit margin {pct:.1f}% is healthy (>10%)"))
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


def _score_health(info: dict[str, Any]) -> SectionScore:
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


def _score_ownership(
    info: dict[str, Any], insider_txns: list[dict[str, Any]]
) -> SectionScore:
    """5 ownership checks: institutional %, insider %, net buying 3mo, 13D activity, sell velocity."""
    verdicts: list[tuple[Literal["pass", "warn", "fail"], str]] = []
    score = 0

    # 1. Institutional > 50%
    inst_pct = info.get("heldPercentInstitutions")
    if inst_pct is not None:
        pct = inst_pct * 100
        if inst_pct > 0.50:
            score += 1
            verdicts.append(
                (
                    "pass",
                    f"Institutional ownership {pct:.1f}% — strong smart-money backing",
                )
            )
        else:
            verdicts.append(
                ("warn", f"Institutional ownership {pct:.1f}% — below 50% threshold")
            )
    else:
        verdicts.append(("warn", "Institutional ownership data not available"))

    # 2. Insider > 1%
    insider_pct = info.get("heldPercentInsiders")
    if insider_pct is not None:
        pct = insider_pct * 100
        if insider_pct > 0.01:
            score += 1
            verdicts.append(
                (
                    "pass",
                    f"Insider ownership {pct:.1f}% — management has skin in the game",
                )
            )
        else:
            verdicts.append(
                (
                    "warn",
                    f"Low insider ownership {pct:.2f}% — misaligned incentives risk",
                )
            )
    else:
        verdicts.append(("warn", "Insider ownership data not available"))

    # 3. Net insider buying last 3 months
    if insider_txns:
        buys = sum(
            1
            for t in insider_txns
            if str(t.get("transactionType", t.get("Transaction", ""))).lower()
            in ("buy", "purchase")
        )
        sells = len(insider_txns) - buys
        if buys > sells:
            score += 1
            verdicts.append(
                (
                    "pass",
                    f"Net insider buying: {buys} buys vs {sells} sells in recent period",
                )
            )
        else:
            verdicts.append(
                (
                    "warn",
                    f"Net insider selling: {sells} sells vs {buys} buys in recent period",
                )
            )
    else:
        verdicts.append(("warn", "No insider transaction data available"))

    # 4. Any 13D / activist filing (proxy: large institutional concentration)
    # yfinance doesn't expose 13D directly; use institutional count proxy
    major_holders = info.get("institutionsCount", 0) or 0
    if major_holders > 500:
        score += 1
        verdicts.append(
            (
                "pass",
                f"{major_holders} institutions hold this — broad institutional interest",
            )
        )
    else:
        verdicts.append(
            ("warn", "Limited institutional participation — lower conviction")
        )

    # 5. Low selling velocity (insider selling < 3 in last period)
    if insider_txns:
        recent_sells = sum(
            1
            for t in insider_txns
            if str(t.get("transactionType", t.get("Transaction", ""))).lower()
            in ("sell", "sale")
        )
        if recent_sells < 3:
            score += 1
            verdicts.append(
                ("pass", f"Low insider sell activity ({recent_sells} transactions)")
            )
        else:
            verdicts.append(
                ("warn", f"Elevated insider selling ({recent_sells} sell transactions)")
            )
    else:
        score += 1  # No sells = pass
        verdicts.append(("pass", "No insider selling activity detected"))

    pct_score = score / 5
    if pct_score >= 0.60:
        summary = "Strong ownership alignment — institutions and insiders both engaged."
    elif pct_score >= 0.40:
        summary = "Mixed ownership signals — watch insider activity closely."
    else:
        summary = "Ownership concerns — low insider alignment or selling pressure."

    return SectionScore("Ownership", score, 5, summary, verdicts)


def _score_sentiment(buzz: list[Any]) -> SectionScore:
    """5 sentiment checks: avg positive, multiple sources, above-average buzz, no negative spike, bullish divergence."""
    verdicts: list[tuple[Literal["pass", "warn", "fail"], str]] = []
    score = 0

    if not buzz:
        return SectionScore(
            "Sentiment",
            0,
            5,
            "No sentiment signals collected yet for this ticker.",
            [("warn", "No buzz signals in database — run daily scan to populate")],
        )

    # Compute stats
    sentiments = [float(b.sentiment_raw) for b in buzz if hasattr(b, "sentiment_raw")]
    sources = set(getattr(b, "source", "unknown") for b in buzz)

    # 1. Avg sentiment > 0
    if sentiments:
        avg_sent = sum(sentiments) / len(sentiments)
        if avg_sent > 0:
            score += 1
            verdicts.append(("pass", f"Average sentiment is positive ({avg_sent:.2f})"))
        else:
            verdicts.append(("fail", f"Average sentiment is negative ({avg_sent:.2f})"))
    else:
        verdicts.append(("warn", "Sentiment scores not available"))

    # 2. Multiple sources agree
    if len(sources) >= 2:
        score += 1
        verdicts.append(
            ("pass", f"{len(sources)} sources active: {', '.join(sorted(sources))}")
        )
    else:
        verdicts.append(
            ("warn", f"Only {len(sources)} source active — limited signal diversity")
        )

    # 3. Buzz above average (mention count heuristic)
    mention_counts = [getattr(b, "mention_count", 0) for b in buzz]
    if mention_counts:
        avg_mentions = sum(mention_counts) / len(mention_counts)
        if avg_mentions >= 3:
            score += 1
            verdicts.append(
                (
                    "pass",
                    f"Average buzz volume {avg_mentions:.1f} mentions/signal — above average",
                )
            )
        else:
            verdicts.append(
                ("warn", f"Low buzz volume ({avg_mentions:.1f} mentions/signal)")
            )
    else:
        verdicts.append(("warn", "Mention count data not available"))

    # 4. No negative sentiment spike (no single signal < -0.5)
    if sentiments:
        min_sent = min(sentiments)
        if min_sent >= -0.5:
            score += 1
            verdicts.append(
                ("pass", "No major negative sentiment spike detected in recent signals")
            )
        else:
            verdicts.append(
                ("fail", f"Negative sentiment spike detected (min: {min_sent:.2f})")
            )
    else:
        verdicts.append(("warn", "Cannot check for spikes — no sentiment data"))

    # 5. Bullish divergence: most recent signals are positive
    recent = buzz[:5] if len(buzz) >= 5 else buzz
    recent_sentiments = [float(getattr(b, "sentiment_raw", 0)) for b in recent]
    if recent_sentiments:
        recent_avg = sum(recent_sentiments) / len(recent_sentiments)
        if recent_avg > 0:
            score += 1
            verdicts.append(
                ("pass", f"Most recent signals are bullish (avg {recent_avg:.2f})")
            )
        else:
            verdicts.append(
                ("warn", f"Recent signals lean bearish (avg {recent_avg:.2f})")
            )
    else:
        verdicts.append(("warn", "Cannot evaluate recent signal trend"))

    pct_score = score / 5
    if pct_score >= 0.60:
        summary = (
            "Sentiment signals are predominantly positive across multiple sources."
        )
    elif pct_score >= 0.40:
        summary = "Mixed sentiment — positive bias with some noise signals."
    else:
        summary = "Sentiment is weak or bearish — caution warranted."

    return SectionScore("Sentiment", score, 5, summary, verdicts)


def _score_supply_chain(group: dict[str, Any] | None) -> SectionScore:
    """4 supply chain checks: known group, leader momentum, cluster momentum, no divergence."""
    verdicts: list[tuple[Literal["pass", "warn", "fail"], str]] = []
    score = 0

    if group is None:
        return SectionScore(
            "Supply Chain",
            0,
            4,
            "This ticker is not in any tracked supply chain group.",
            [("warn", "Not in tracked supply chain — cross-asset signals unavailable")],
        )

    group_name = group.get("group", "unknown")
    leaders = group.get("leaders", [])
    followers = group.get("followers", [])
    role = "leader" if group.get("_is_leader") else "follower"

    # 1. In known group
    score += 1
    verdicts.append(
        (
            "pass",
            f"Part of '{group_name}' supply chain ({role}) with {len(leaders)} leaders, {len(followers)} followers",
        )
    )

    # 2. Leader momentum (we can't fetch live here without circular imports, use heuristic)
    lag = group.get("typical_lag_days", 1)
    if lag <= 2:
        score += 1
        verdicts.append(
            (
                "pass",
                f"Short lag ({lag} days) to supply chain leaders — fast signal propagation",
            )
        )
    else:
        verdicts.append(
            ("warn", f"Longer lag ({lag} days) to leaders — delayed signal propagation")
        )

    # 3. Cluster momentum: group has multiple members
    total_members = len(leaders) + len(followers)
    if total_members >= 5:
        score += 1
        verdicts.append(
            (
                "pass",
                f"Active cluster with {total_members} tracked members — strong group signal",
            )
        )
    else:
        verdicts.append(
            ("warn", f"Small cluster ({total_members} members) — limited group signal")
        )

    # 4. No divergence: leader and follower counts are balanced
    if leaders and followers:
        ratio = len(leaders) / len(followers)
        if 0.3 <= ratio <= 3.0:
            score += 1
            verdicts.append(
                (
                    "pass",
                    "Balanced leader/follower ratio — healthy supply chain structure",
                )
            )
        else:
            verdicts.append(
                ("warn", "Unbalanced leader/follower ratio may reduce signal quality")
            )
    else:
        verdicts.append(
            ("warn", "Incomplete group structure — missing leaders or followers")
        )

    notes = group.get("notes", "")
    summary = (
        f"Part of {group_name} supply chain. {notes}"
        if notes
        else f"Part of {group_name} supply chain group."
    )

    return SectionScore("Supply Chain", score, 4, summary, verdicts)


def _compute_signal_radar(
    info: dict[str, Any],
    buzz: list[Any],
    rec: Any,
    sc_group: dict[str, Any] | None,
    insider_txns: list[dict[str, Any]],
) -> dict[str, float]:
    """Compute 0-10 scores for the 6 signal radar dimensions."""
    scores: dict[str, float] = {}

    # Technical (0-10): based on RSI/momentum proxies from info
    tech_score = 5.0
    pe = info.get("trailingPE")
    roe = info.get("returnOnEquity")
    rev_growth = info.get("revenueGrowth")
    beta = info.get("beta", 1.0) or 1.0
    if pe and pe < 25:
        tech_score += 1
    if roe and roe > 0.15:
        tech_score += 1
    if rev_growth and rev_growth > 0:
        tech_score += 1
    if beta < 1.5:
        tech_score += 0.5
    if pe and pe > 40:
        tech_score -= 1
    scores["Technical"] = min(10.0, max(0.0, tech_score))

    # Sentiment (0-10)
    if buzz:
        sentiments = [float(getattr(b, "sentiment_raw", 0)) for b in buzz]
        avg_sent = sum(sentiments) / len(sentiments) if sentiments else 0
        # Map [-1, 1] → [0, 10]
        sent_score = (avg_sent + 1) / 2 * 10
        sent_score = min(10.0, max(0.0, sent_score))
    else:
        sent_score = 5.0
    scores["Sentiment"] = sent_score

    # Fundamental (0-10): from scoring function
    fundamental_score = 5.0
    if info.get("freeCashflow") and (info.get("freeCashflow") or 0) > 0:
        fundamental_score += 1
    if info.get("profitMargins") and (info.get("profitMargins") or 0) > 0.10:
        fundamental_score += 1
    if info.get("returnOnEquity") and (info.get("returnOnEquity") or 0) > 0.15:
        fundamental_score += 1
    if info.get("debtToEquity") and (info.get("debtToEquity") or 999) < 100:
        fundamental_score += 1
    if info.get("pegRatio") and (info.get("pegRatio") or 99) < 2:
        fundamental_score += 1
    scores["Fundamental"] = min(10.0, max(0.0, fundamental_score))

    # Cross-Asset (0-10): from supply chain group membership
    if sc_group:
        total = len(sc_group.get("leaders", [])) + len(sc_group.get("followers", []))
        cross_score = min(10.0, 5.0 + total * 0.3)
    else:
        cross_score = 3.0
    scores["Cross-Asset"] = cross_score

    # Event-Causal (0-10): from recommendation data
    if rec and hasattr(rec, "composite_score"):
        event_score = float(getattr(rec, "composite_score", 0.5)) * 10
    else:
        event_score = 5.0
    scores["Event-Causal"] = min(10.0, max(0.0, event_score))

    # Smart Money (0-10): from insider transactions
    if insider_txns:
        buys = sum(
            1
            for t in insider_txns
            if str(t.get("transactionType", t.get("Transaction", ""))).lower()
            in ("buy", "purchase")
        )
        total = len(insider_txns)
        buy_ratio = buys / total if total > 0 else 0.5
        smart_score = buy_ratio * 10
    else:
        smart_score = 5.0
    inst_pct = info.get("heldPercentInstitutions", 0.5) or 0.5
    smart_score = (smart_score + inst_pct * 10) / 2
    scores["Smart Money"] = min(10.0, max(0.0, smart_score))

    return scores


# ---------------------------------------------------------------------------
# DB / config loaders
# ---------------------------------------------------------------------------


def _load_buzz_signals(ticker: str, db_path: str) -> list[Any]:
    """Load buzz signals from SQLite. Returns [] on any error."""
    try:
        if not os.path.exists(db_path):
            return []
        from adapters.data.sqlite_store import SQLiteStore

        store = SQLiteStore(db_path)
        return store.get_buzz_signals(ticker=ticker)
    except Exception as exc:
        logger.warning("Could not load buzz signals for {}: {}", ticker, exc)
        return []


def _load_recommendation(ticker: str, db_path: str) -> Any:
    """Load the most recent recommendation for ticker. Returns None on error."""
    try:
        if not os.path.exists(db_path):
            return None
        from adapters.data.sqlite_store import SQLiteStore

        store = SQLiteStore(db_path)
        recs = store.get_recommendations(symbol=ticker)
        if recs:
            return recs[0]  # Most recent
        return None
    except Exception as exc:
        logger.warning("Could not load recommendation for {}: {}", ticker, exc)
        return None


def _find_supply_chain_group(ticker: str) -> dict[str, Any] | None:
    """Find which supply chain group contains this ticker. Returns enriched group dict or None."""
    try:
        import yaml

        config_path = "config/relationships/supply_chain.yaml"
        if not os.path.exists(config_path):
            return None
        with open(config_path) as f:
            data = yaml.safe_load(f)
        for rel in data.get("relationships", []):
            leaders = rel.get("leaders", [])
            followers = rel.get("followers", [])
            if ticker in leaders or ticker in followers:
                enriched = dict(rel)
                enriched["_is_leader"] = ticker in leaders
                return enriched
        return None
    except Exception as exc:
        logger.warning("Could not load supply chain config: {}", exc)
        return None


def _get_sector_peers(
    ticker: str, info: dict[str, Any], sc_group: dict[str, Any] | None
) -> list[dict[str, Any]]:
    """Return 4-5 peer dicts with {ticker, name, pe, market_cap, change_pct, role}."""
    # Determine peer tickers
    peer_tickers: list[str] = []

    if sc_group:
        leaders = sc_group.get("leaders", [])
        followers = sc_group.get("followers", [])
        candidates = leaders + followers
        peer_tickers = [t for t in candidates if t != ticker][:4]
    else:
        # Sector-based hardcoded fallback
        sector = info.get("sector", "")
        _SECTOR_PEERS: dict[str, list[str]] = {
            "Technology": ["MSFT", "AAPL", "GOOGL", "META"],
            "Healthcare": ["JNJ", "PFE", "ABBV", "MRK"],
            "Financial Services": ["JPM", "BAC", "GS", "MS"],
            "Consumer Cyclical": ["AMZN", "TSLA", "HD", "NKE"],
            "Energy": ["XOM", "CVX", "COP", "SLB"],
            "Industrials": ["CAT", "DE", "HON", "GE"],
        }
        peer_tickers = [
            t for t in _SECTOR_PEERS.get(sector, ["SPY", "QQQ"]) if t != ticker
        ][:4]

    # Fetch info for peers
    from adapters.visualization.price_cache import _fetch_ticker_info_impl

    peers: list[dict[str, Any]] = []
    for pt in peer_tickers:
        try:
            pi = _fetch_ticker_info_impl(pt)
            peers.append(
                {
                    "ticker": pt,
                    "name": pi.get("shortName", pt),
                    "pe": pi.get("trailingPE"),
                    "market_cap": float(pi.get("marketCap", 0) or 0),
                    "change_pct": 0.0,  # Would need separate price fetch
                    "role": (
                        "leader"
                        if pt in (sc_group or {}).get("leaders", [])
                        else "peer"
                    ),
                }
            )
        except Exception as exc:
            logger.warning("Could not fetch peer data for {}: {}", pt, exc)

    return peers


# ---------------------------------------------------------------------------
# Insider transaction aggregation helper
# ---------------------------------------------------------------------------


def aggregate_insider_by_quarter(
    insider_txns: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Aggregate insider transactions by quarter for insider_bars chart.

    Returns list of {quarter, buys, sells, buy_value, sell_value}.
    """
    quarters: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"buys": 0, "sells": 0, "buy_value": 0.0, "sell_value": 0.0}
    )
    for txn in insider_txns:
        try:
            # Try to parse date from 'Date' or 'startDate' field
            date_val = (
                txn.get("Date") or txn.get("startDate") or txn.get("dateReported")
            )
            if date_val is None:
                continue
            # Handle both string and datetime-like
            if hasattr(date_val, "year"):
                year = date_val.year
                month = date_val.month
            else:
                from datetime import datetime

                dt = datetime.fromisoformat(str(date_val)[:10])
                year = dt.year
                month = dt.month
            quarter = f"Q{(month - 1) // 3 + 1} {year}"

            txn_type = str(
                txn.get("transactionType", txn.get("Transaction", ""))
            ).lower()
            value = abs(float(txn.get("Value", txn.get("value", 0)) or 0))
            if "buy" in txn_type or "purchase" in txn_type:
                quarters[quarter]["buys"] += 1
                quarters[quarter]["buy_value"] += value
            else:
                quarters[quarter]["sells"] += 1
                quarters[quarter]["sell_value"] += value
        except Exception:
            continue

    # Sort by quarter label
    result = [{"quarter": k, **v} for k, v in sorted(quarters.items())]
    return result[-8:]  # Last 8 quarters
