"""Orchestrator — runs full analysis for a single ticker."""

from __future__ import annotations

import datetime as _dt

from loguru import logger

from adapters.visualization.analysis.loaders import (
    find_supply_chain_group,
    get_sector_peers,
    load_buzz_signals,
    load_buzz_volume_signals,
    load_recommendation,
)
from adapters.visualization.analysis.models import AnalysisResult
from adapters.visualization.analysis.radar import compute_signal_radar
from adapters.visualization.analysis.scoring.growth import score_growth
from adapters.visualization.analysis.scoring.health import score_health
from adapters.visualization.analysis.scoring.ownership import score_ownership
from adapters.visualization.analysis.scoring.performance import score_performance
from adapters.visualization.analysis.scoring.sentiment import score_sentiment
from adapters.visualization.analysis.scoring.supply_chain import (
    compute_co_movement,
    score_supply_chain,
)
from adapters.visualization.analysis.scoring.valuation import score_valuation


def analyze_ticker(
    ticker: str, db_path: str = "data/recommendations.db"
) -> AnalysisResult:
    """Run full analysis for a single ticker. Returns AnalysisResult."""
    from adapters.visualization.price_cache import (
        _batch_fetch_closes_impl,
        _batch_fetch_prices_impl,
        _fetch_annual_revenue_impl,
        _fetch_insider_transactions_impl,
        _fetch_price_history_impl,
        _fetch_quarterly_financials_impl,
        _fetch_rating_distribution_impl,
        _fetch_revenue_estimate_impl,
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

    # 5. Fetch buzz signals from DB (rolling 30-day harvest window)
    from datetime import datetime, timezone

    from adapters.visualization.analysis.buzz_enrichment import (
        resolve_sentiment_signals,
        score_headlines_as_buzz_signals,
    )
    from adapters.visualization.price_cache import _fetch_recent_news_impl

    buzz, buzz_stale = load_buzz_signals(
        ticker,
        db_path,
        ref=datetime.now(timezone.utc),
    )
    buzz_volume, buzz_volume_extended = load_buzz_volume_signals(
        ticker,
        db_path,
        ref=datetime.now(timezone.utc),
    )
    live_headlines = _fetch_recent_news_impl(ticker, limit=10)
    sentiment_signals, sentiment_live, _sentiment_stale = resolve_sentiment_signals(
        buzz, buzz_stale, ticker, live_headlines
    )
    publisher_rows = (
        score_headlines_as_buzz_signals(ticker, live_headlines)
        if live_headlines and not sentiment_live
        else []
    )

    # 6. Fetch recommendation from DB
    rec = load_recommendation(ticker, db_path)

    # 7. Find supply chain group (+ recent member moves for the panel bars)
    sc_group = find_supply_chain_group(ticker)
    if sc_group is not None:
        members = list(sc_group.get("leaders") or []) + list(
            sc_group.get("followers") or []
        )
        if members:
            mprices = _batch_fetch_prices_impl(tuple(members))
            closes = _batch_fetch_closes_impl((ticker, *members))
            sc_group = {
                **sc_group,
                "member_moves": {
                    t: float(mprices.get(t, {}).get("change_pct", 0.0) or 0.0)
                    for t in members
                },
                "co_movement": compute_co_movement(closes),
            }

    # 8. Fetch peer data for comparison
    peers = get_sector_peers(ticker, info, sc_group)

    # 9. Fetch daily price history (+ SPY for relative strength). Best-effort:
    #    None on failure so the panels degrade to honest DATA-GAP, never crash.
    price_history = _fetch_price_history_impl(ticker)
    if price_history is not None:
        spy = _fetch_price_history_impl("SPY")
        if spy is not None and spy.get("closes"):
            price_history["spy_closes"] = spy["closes"]

    # 10. Analyst rating distribution (latest period; None-safe)
    rating_distribution = _fetch_rating_distribution_impl(ticker)

    # 11. Annual revenue (3y CAGR) + forward revenue estimate (best-effort)
    annual_revenue = _fetch_annual_revenue_impl(ticker)
    forward_revenue_growth = _fetch_revenue_estimate_impl(ticker)

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
        quarterly_cashflow=qcf,
        price_history=price_history,
        rating_distribution=rating_distribution,
        annual_revenue=annual_revenue,
        forward_revenue_growth=forward_revenue_growth,
        insider_transactions=insider_txns,
        buzz_signals=buzz,
        buzz_harvest_stale=buzz_stale,
        buzz_volume_signals=buzz_volume,
        buzz_volume_extended=buzz_volume_extended,
        sentiment_signals=sentiment_signals,
        sentiment_from_live=sentiment_live,
        sentiment_publisher_rows=publisher_rows,
        recommendation_data=rec,
        peer_data=peers,
        supply_chain_group=sc_group,
    )

    # Compute sections
    result.valuation = score_valuation(info, peers)
    result.growth = score_growth(info)
    result.performance = score_performance(info)
    result.health = score_health(info)
    result.ownership = score_ownership(info, insider_txns)
    result.sentiment = score_sentiment(sentiment_signals or buzz)
    result.supply_chain = score_supply_chain(sc_group)

    # Compute signal radar
    result.signal_scores = compute_signal_radar(
        info, sentiment_signals or buzz, rec, sc_group, insider_txns
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
    as_of = _dt.date.today().isoformat()
    try:
        from application.analyst_panel import build_analyst_panel

        panel_info: dict[str, object] = dict(info)
        panel_info["analyst_count"] = info.get("numberOfAnalystOpinions", 0)
        panel_info["analyst_recommendation_mean"] = info.get("recommendationMean")
        result.analyst_panel = build_analyst_panel(panel_info, as_of)
    except Exception as exc:
        logger.warning("Could not build analyst panel for {}: {}", ticker, exc)
        result.analyst_panel = None

    # E3: Attributed news/event context — live yfinance headlines first, buzz fallback
    try:
        from application.news_context import build_news_context

        headlines = live_headlines
        if headlines:
            signal_dicts: list[dict[str, object]] = [
                {
                    "source": h["source"],
                    "title": h["title"],
                    "date": h["date"],
                    "url": h.get("url", ""),
                }
                for h in headlines
            ]
        else:
            signal_dicts = []
            for b in buzz:
                fetched = getattr(b, "fetched_at", None)
                date_str = str(fetched)[:10] if fetched is not None else ""
                source = getattr(b, "source", "unknown")
                mention_count = getattr(b, "mention_count", 0)
                _raw = getattr(b, "sentiment_raw", 0.0)
                sentiment = float(_raw) if _raw is not None else 0.0
                sent_label = (
                    "positive"
                    if sentiment > 0.01
                    else "negative" if sentiment < -0.01 else "neutral"
                )
                title = (
                    f"{source}: {mention_count} mention(s), "
                    f"sentiment {sent_label} ({sentiment:+.2f})"
                )
                signal_dicts.append(
                    {"source": source, "title": title, "date": date_str}
                )
        result.news_context = build_news_context(signal_dicts, 10)
    except Exception as exc:
        logger.warning("Could not build news context for {}: {}", ticker, exc)
        result.news_context = None

    # E1: Industry-relative peer percentiles
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
        else:
            logger.info(
                "No peer data for {} — peer percentiles will be DATA_GAP", ticker
            )
            peer_percentiles = {"P/E": None, "Market Cap": None}
        result.peer_percentiles = peer_percentiles
    except Exception as exc:
        logger.warning("Could not compute peer percentiles for {}: {}", ticker, exc)
        result.peer_percentiles = {}

    return result
