"""Tab 1: Today's Opportunities — auto-scan, 3-panel hero, compact conviction cards."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Literal
from zoneinfo import ZoneInfo

import streamlit as st

from adapters.visualization.action_runner import run_conviction_scan, run_full_cycle
from adapters.visualization.cache import ScanCache
from adapters.visualization.components.compact_card import render_compact_card_html
from adapters.visualization.components.hero import render_hero_html
from adapters.visualization.components.onboarding import (
    render_onboarding_html,
    should_show_onboarding,
)
from adapters.visualization.data_loader import (
    load_holdings,
    load_recommendations_latest,
    load_scan_distribution,
    load_spy_sparkline,
    load_watchlist,
)

ET = ZoneInfo("America/New_York")
DB_PATH = "data/recommendations.db"


def render(db_path: str = DB_PATH) -> None:
    """Render the Today's Opportunities tab."""
    holdings = load_holdings(db_path)
    watchlist = load_watchlist(db_path)

    # Initialize cache
    if "scan_cache" not in st.session_state:
        st.session_state.scan_cache = ScanCache()
    cache: ScanCache = st.session_state.scan_cache

    # Onboarding: first run with nothing yet
    if should_show_onboarding(
        has_scan_results=not cache.is_stale(),
        has_trades=len(holdings) > 0,
        has_watchlist=len(watchlist) > 0,
    ):
        st.markdown(render_onboarding_html(), unsafe_allow_html=True)
        if st.button("Scan for Opportunities", type="primary"):
            _run_scan(cache, db_path)
        return

    # Auto-scan if stale
    if cache.is_stale():
        _run_scan(cache, db_path)

    # Task 13: Scrolling ticker bar
    _render_ticker_bar()

    # Hero section
    spy_data = load_spy_sparkline()
    _render_hero(holdings, cache, spy_data, watchlist)

    # Task 14: SPY sparkline inline chart
    _render_spy_sparkline_chart(spy_data)

    # Mode A or Mode B
    cards = cache.get_results()
    scan_was_run = not cache.is_stale()
    if scan_was_run and len(cards) == 0:
        # Honest empty-state: scan ran but nothing cleared the bar
        _render_empty_state(db_path)
    elif cache.is_stale() or len(cards) < 5:
        # Mode A: market overview with recommendation cards
        _render_mode_a(db_path)
    else:
        # Mode B: conviction feed
        _render_mode_b(cards, cache, db_path)

    # Bottom actions
    st.divider()
    cols = st.columns([2, 3, 2])
    with cols[0]:
        if st.button("Scan Now", type="primary"):
            _run_scan(cache, db_path)
            st.rerun()
    with cols[1]:
        scan_time = cache.last_scan_time()
        if scan_time:
            st.markdown(
                f'<div style="color:#94A3B8;font-size:12px;padding-top:8px;">'
                f"Last scanned: {scan_time} &nbsp;·&nbsp; {cache.minutes_ago()} min ago"
                f"</div>",
                unsafe_allow_html=True,
            )
    with cols[2]:
        if st.button("Run Full Cycle"):
            run_full_cycle(db_path=db_path)
            st.rerun()


# ---------------------------------------------------------------------------
# Task 13: Ticker bar
# ---------------------------------------------------------------------------


def _render_ticker_bar() -> None:
    """Render scrolling ticker bar with major index prices."""
    try:
        from adapters.visualization.price_cache import fetch_index_prices

        prices = fetch_index_prices()
    except Exception:
        return

    if not prices:
        return

    display_names = {
        "SPY": "S&P 500",
        "QQQ": "NASDAQ",
        "DIA": "DOW",
        "IWM": "Russell 2K",
    }
    items_html = ""
    for ticker in ["SPY", "QQQ", "DIA", "IWM"]:
        if ticker not in prices:
            continue
        p = prices[ticker]
        price = p["price"]
        change = p["change_pct"]
        color_class = "ticker-bar-up" if change >= 0 else "ticker-bar-down"
        arrow = "&#9650;" if change >= 0 else "&#9660;"
        name = display_names.get(ticker, ticker)
        items_html += (
            f'<span class="ticker-bar-item">'
            f'<span style="color:#94A3B8;">{name}</span>'
            f'<span style="color:white;">${price:,.2f}</span>'
            f'<span class="{color_class}">{arrow} {abs(change):.2f}%</span>'
            f"</span>"
        )

    if items_html:
        st.markdown(
            f'<div class="ticker-bar">{items_html}</div>', unsafe_allow_html=True
        )


# ---------------------------------------------------------------------------
# Task 14: Hero with live P&L + SPY sparkline
# ---------------------------------------------------------------------------


def _render_hero(
    holdings: list[Any],
    cache: ScanCache,
    spy_data: dict[str, Any],
    watchlist: list[Any],
) -> None:
    """Assemble market/portfolio/signal dicts and render 3-panel hero."""
    # Market panel
    now_est = datetime.now(ET)
    time_est = now_est.strftime("%-I:%M %p EST")
    spy_price = spy_data.get("current", 0.0)
    spy_change = spy_data.get("change_pct", 0.0)
    t = now_est.time()
    from datetime import time as _time

    market_open = _time(9, 30) <= t < _time(16, 0)
    if spy_change > 1:
        mood = "Bulls in control"
    elif spy_change < -1:
        mood = "Bears in control"
    else:
        mood = "Choppy session"

    market = {
        "spy_price": spy_price,
        "spy_change": spy_change,
        "market_open": market_open,
        "time_est": time_est,
        "mood": mood,
    }

    # Portfolio panel — live P&L via batch price fetch
    try:
        from adapters.visualization.price_cache import batch_fetch_prices

        holding_tickers = tuple(h.symbol for h in holdings)
        live_prices = batch_fetch_prices(holding_tickers) if holdings else {}
    except Exception:
        live_prices = {}

    total_value = 0.0
    total_cost = 0.0
    for h in holdings:
        price_data = live_prices.get(h.symbol)
        current_price = price_data["price"] if price_data else h.purchase_price
        total_value += h.quantity * current_price
        total_cost += h.quantity * h.purchase_price

    if not holdings:
        total_value = 0.0
        total_cost = 0.0

    total_pnl = total_value - total_cost
    pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0.0
    best_performer = holdings[0].symbol if holdings else "—"

    portfolio = {
        "total_value": total_value,
        "total_pnl": total_pnl,
        "pnl_pct": pnl_pct,
        "n_positions": len(holdings),
        "best_performer": best_performer,
    }

    # Signal panel — Task 19: actual watchlist-in-scan count
    cards = cache.get_results()
    top_card = cards[0] if cards else None
    n_watchlist_alerts = sum(
        1 for w in watchlist if any(c.ticker == w["symbol"] for c in cards)
    )
    signal = {
        "n_new_opps": len(cards),
        "top_ticker": top_card.ticker if top_card else "—",
        "top_conviction": top_card.conviction if top_card else 0.0,
        "n_watchlist_alerts": n_watchlist_alerts,
        "summary": (
            top_card.alert_summary
            if top_card
            else "Run a scan to surface opportunities."
        ),
    }

    st.markdown(render_hero_html(market, portfolio, signal), unsafe_allow_html=True)


def _render_spy_sparkline_chart(spy_data: dict[str, Any]) -> None:
    """Render SPY intraday sparkline as a small Plotly chart (Task 14)."""
    spy_prices = spy_data.get("prices", [])
    spy_times = spy_data.get("times", [])
    if not spy_prices or len(spy_prices) < 2:
        return
    try:
        import plotly.graph_objects as go

        fig = go.Figure(
            go.Scatter(
                x=spy_times,
                y=spy_prices,
                mode="lines",
                line=dict(color="#2563EB", width=1.5),
                fill="tozeroy",
                fillcolor="rgba(37,99,235,0.08)",
            )
        )
        fig.update_layout(
            height=60,
            margin=dict(l=0, r=0, t=0, b=0),
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    except Exception:
        pass  # never crash if plotly fails


# ---------------------------------------------------------------------------
# Honest empty-state: scan ran but nothing cleared the conviction/divergence bar
# ---------------------------------------------------------------------------


def _render_empty_state(db_path: str) -> None:
    """Render honest empty-state: verdict + full candidate distribution + source health."""
    from adapters.data.sqlite_store import SQLiteStore

    # Verdict line
    st.markdown(
        '<div style="color:#64748B;font-size:13px;margin:12px 0 8px;">'
        "No name cleared the bar today — here is everything the engine looked at."
        "</div>",
        unsafe_allow_html=True,
    )

    # Full candidate distribution table — scoped to today's scan only (UTC date,
    # matching the scan_date written by OpportunityScanUseCase: now.date().isoformat())
    today_scan_date = datetime.now(timezone.utc).date().isoformat()
    try:
        store = SQLiteStore(db_path)
        rows = load_scan_distribution(store, scan_date=today_scan_date)
    except Exception:
        rows = []

    if rows:
        # Sort by conviction desc
        rows_sorted = sorted(
            rows, key=lambda r: float(r.get("conviction", 0)), reverse=True
        )
        st.markdown(
            '<div style="color:#374151;font-size:13px;font-weight:600;margin:8px 0 4px;">'
            "Candidate distribution (all scanned)"
            "</div>",
            unsafe_allow_html=True,
        )
        col_headers = [
            "Ticker",
            "Conviction",
            "Divergence",
            "Cap Tier",
            "Theme",
            "Surfaced",
        ]
        header_row = "".join(
            f'<th style="padding:6px 10px;text-align:left;color:#64748B;font-size:12px;'
            f'font-weight:600;border-bottom:1px solid #E2E8F0;">{h}</th>'
            for h in col_headers
        )
        data_rows_html = ""
        for row in rows_sorted:
            surfaced = row.get("surfaced", False)
            surfaced_html = (
                '<span style="color:#16A34A;font-weight:600;">Yes</span>'
                if surfaced
                else '<span style="color:#94A3B8;">No</span>'
            )
            data_rows_html += (
                "<tr>"
                f'<td style="padding:6px 10px;font-size:13px;font-weight:600;">'
                f'{row.get("ticker", "")}</td>'
                f"<td style=\"padding:6px 10px;font-size:13px;font-family:'JetBrains Mono',monospace;\">"
                f'{float(row.get("conviction", 0)):.2f}</td>'
                f"<td style=\"padding:6px 10px;font-size:13px;font-family:'JetBrains Mono',monospace;\">"
                f'{float(row.get("divergence", 0)):.2f}</td>'
                f'<td style="padding:6px 10px;font-size:13px;color:#475569;">'
                f'{row.get("cap_tier", "")}</td>'
                f'<td style="padding:6px 10px;font-size:13px;color:#475569;">'
                f'{row.get("theme", "")}</td>'
                f'<td style="padding:6px 10px;">{surfaced_html}</td>'
                "</tr>"
            )
        table_html = (
            '<div style="overflow-x:auto;margin-bottom:16px;">'
            '<table style="width:100%;border-collapse:collapse;">'
            f"<thead><tr>{header_row}</tr></thead>"
            f"<tbody>{data_rows_html}</tbody>"
            "</table>"
            "</div>"
        )
        st.markdown(table_html, unsafe_allow_html=True)
    else:
        st.markdown(
            '<div style="color:#94A3B8;font-size:13px;margin:8px 0;">'
            "No candidates logged yet — run a scan to populate the distribution."
            "</div>",
            unsafe_allow_html=True,
        )

    # Source health line (from session state if set by the scan runner)
    source_health = st.session_state.get("last_source_health")
    if source_health and isinstance(source_health, dict):
        parts = []
        for name, h in source_health.items():
            parts.append(
                f"{name}: ok={getattr(h, 'ok', '?')} "
                f"throttled={getattr(h, 'throttled', '?')} "
                f"empty={getattr(h, 'empty', '?')}"
            )
        health_text = " &nbsp;·&nbsp; ".join(parts)
        st.markdown(
            f'<div style="color:#94A3B8;font-size:12px;margin-top:4px;">'
            f"Source health: {health_text}"
            f"</div>",
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Task 15: Mode A — market overview with recommendation cards
# ---------------------------------------------------------------------------


def _render_mode_a(db_path: str) -> None:
    """Mode A: show styled recommendation cards + sector summary."""
    # Banner
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown(
            '<div style="color:#64748B;font-size:13px;margin:12px 0 4px;">'
            "Showing market overview. Run a scan for conviction-scored opportunities."
            "</div>",
            unsafe_allow_html=True,
        )
    with col2:
        pass  # Scan Now button is in the bottom bar

    # Recommendation cards from SQLite
    recs = load_recommendations_latest(db_path)
    if recs:
        st.markdown(
            f'<div style="color:#64748B;font-size:13px;margin:8px 0;">'
            f"{len(recs)} top picks from latest analysis"
            f"</div>",
            unsafe_allow_html=True,
        )
        for rec in recs:
            st.markdown(_rec_card_html(rec), unsafe_allow_html=True)
    else:
        st.info("No recommendations yet. Run a full cycle to generate picks.")

    # Task 16: Sector summary (lightweight)
    _render_sector_summary()


def _rec_card_html(rec: Any) -> str:
    """Build HTML card for a StockRecommendation (Mode A)."""
    grade_colors = {
        "strong_buy": "#16A34A",
        "buy": "#059669",
        "hold": "#F59E0B",
        "may_sell": "#EA580C",
        "immediate_sell": "#DC2626",
    }
    grade_color = grade_colors.get(
        str(rec.grade.value) if hasattr(rec.grade, "value") else str(rec.grade),
        "#64748B",
    )
    grade_display = (
        rec.grade.value.replace("_", " ").title()
        if hasattr(rec.grade, "value")
        else str(rec.grade).replace("_", " ").title()
    )

    # Horizon signals
    horizon_signals = rec.horizon_signals
    if isinstance(horizon_signals, str):
        try:
            horizon_signals = json.loads(horizon_signals)
        except Exception:
            horizon_signals = {}
    if not isinstance(horizon_signals, dict):
        horizon_signals = {}

    horizon_pills = ""
    for h, s in horizon_signals.items():
        pill_color = (
            "#16A34A" if s == "bullish" else "#DC2626" if s == "bearish" else "#94A3B8"
        )
        horizon_pills += (
            f'<span style="background:{pill_color}15;color:{pill_color};padding:2px 8px;'
            f'border-radius:4px;font-size:11px;margin-right:4px;">{h}: {s}</span>'
        )

    # Hold duration from horizon pattern
    bullish_count = sum(1 for s in horizon_signals.values() if s == "bullish")
    if bullish_count == 3:
        hold_text = "Hold until flip"
    elif (
        horizon_signals.get("2d") == "bullish"
        and horizon_signals.get("5d") != "bullish"
    ):
        hold_text = "Short hold (2-3d)"
    elif (
        horizon_signals.get("2d") != "bullish"
        and horizon_signals.get("10d") == "bullish"
    ):
        hold_text = "Position hold (5-10d)"
    else:
        hold_text = "Monitor daily"

    # Predicted return + confidence
    predicted_5d = getattr(rec, "predicted_return_5d", 0.0) or 0.0
    confidence_5d = getattr(rec, "confidence_5d", 0.0) or 0.0
    sentiment_score = getattr(rec, "sentiment_score", 0.0) or 0.0
    reasoning = getattr(rec, "reasoning", "") or ""
    composite_score = getattr(rec, "composite_score", 0.0) or 0.0

    return (
        f'<div class="ws-card" style="padding:16px;margin-bottom:12px;">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'<div style="display:flex;align-items:center;gap:12px;">'
        f"<span style=\"font-family:'DM Sans',sans-serif;font-weight:700;font-size:18px;\">"
        f"{rec.symbol}</span>"
        f'<span style="background:{grade_color};color:white;padding:3px 10px;'
        f'border-radius:6px;font-size:12px;font-weight:600;">{grade_display}</span>'
        f"<span style=\"font-family:'JetBrains Mono',monospace;font-size:14px;color:#374151;\">"
        f"{composite_score:.2f}</span>"
        f"</div>"
        f'<span style="color:#64748B;font-size:13px;">{hold_text}</span>'
        f"</div>"
        + (
            f'<div style="margin-top:8px;">{horizon_pills}</div>'
            if horizon_pills
            else ""
        )
        + f'<div style="margin-top:8px;font-size:13px;color:#475569;">'
        "Predicted 5d: "
        f'<span style="color:#16A34A;font-weight:600;">{predicted_5d:+.1%}</span>'
        f" · Confidence: {confidence_5d:.0%}"
        f" · Sentiment: {sentiment_score:.2f}"
        f"</div>"
        + (
            f'<div style="margin-top:6px;font-size:13px;color:#64748B;font-style:italic;">'
            f"{reasoning}</div>"
            if reasoning
            else ""
        )
        + "</div>"
    )


# ---------------------------------------------------------------------------
# Task 16: Sector summary
# ---------------------------------------------------------------------------


def _render_sector_summary() -> None:
    """Render lightweight sector ETF summary (Task 16)."""
    from adapters.visualization.components.cards import verdict_bullet
    from adapters.visualization.price_cache import batch_fetch_prices

    sector_etfs = {
        "XLK": "Technology",
        "XLF": "Financials",
        "XLV": "Healthcare",
        "XLE": "Energy",
        "XLI": "Industrials",
        "XLY": "Consumer Disc.",
    }
    try:
        sector_prices = batch_fetch_prices(tuple(sector_etfs.keys()))
    except Exception:
        sector_prices = {}

    if not sector_prices:
        return

    st.markdown("#### Market Sectors")
    for etf, name in sector_etfs.items():
        if etf in sector_prices:
            change = sector_prices[etf]["change_pct"]
            if change > 0:
                status_lit: Literal["pass", "warn", "fail"] = "pass"
            elif change < -1:
                status_lit = "fail"
            else:
                status_lit = "warn"
            st.markdown(
                verdict_bullet(status_lit, f"{name}: {change:+.2f}%"),
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------------------------
# Task 17/18: Mode B — conviction feed with enriched cards + rec data
# ---------------------------------------------------------------------------


def _render_mode_b(cards: list[Any], cache: ScanCache, db_path: str) -> None:
    """Mode B: conviction feed with recommendation data wired in (Tasks 17, 18)."""
    # Load recommendations for enrichment
    try:
        recs_map = {r.symbol: r for r in load_recommendations_latest(db_path)}
    except Exception:
        recs_map = {}

    st.markdown(
        f'<div style="color:#64748B;font-size:13px;margin:12px 0 8px;">'
        f"{len(cards)} opportunities ranked by conviction"
        f"</div>",
        unsafe_allow_html=True,
    )
    now = datetime.now()
    for card in cards:
        st.markdown(render_compact_card_html(card, now=now), unsafe_allow_html=True)

        # Task 18: Enrich with recommendation data in an expander
        rec = recs_map.get(card.ticker)
        if rec is not None:
            with st.expander(f"Recommendation details for {card.ticker}"):
                horizon_signals = rec.horizon_signals
                if isinstance(horizon_signals, str):
                    try:
                        horizon_signals = json.loads(horizon_signals)
                    except Exception:
                        horizon_signals = {}
                if isinstance(horizon_signals, dict) and horizon_signals:
                    pills = ""
                    for h, s in horizon_signals.items():
                        pill_color = (
                            "#16A34A"
                            if s == "bullish"
                            else "#DC2626" if s == "bearish" else "#94A3B8"
                        )
                        pills += (
                            f'<span style="background:{pill_color}15;color:{pill_color};'
                            f'padding:2px 8px;border-radius:4px;font-size:11px;margin-right:4px;">'
                            f"{h}: {s}</span>"
                        )
                    st.markdown(pills, unsafe_allow_html=True)

                predicted_5d = getattr(rec, "predicted_return_5d", 0.0) or 0.0
                confidence_5d = getattr(rec, "confidence_5d", 0.0) or 0.0
                sentiment_score = getattr(rec, "sentiment_score", 0.0) or 0.0
                reasoning = getattr(rec, "reasoning", "") or ""

                st.markdown(
                    f"**Predicted 5d return:** {predicted_5d:+.1%}  "
                    f"**Confidence:** {confidence_5d:.0%}  "
                    f"**Sentiment:** {sentiment_score:.2f}"
                )
                if reasoning:
                    st.markdown(f"*{reasoning}*")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_scan(cache: ScanCache, db_path: str) -> None:
    """Run conviction scan with progress bar, store results in cache."""
    progress = st.progress(0)
    status_text = st.empty()

    def _update(pct: float, msg: str) -> None:
        progress.progress(pct)
        status_text.text(msg)

    cards = run_conviction_scan(db_path=db_path, progress_callback=_update)
    cache.store(cards, datetime.now(tz=ET))
    progress.empty()
    status_text.empty()
    st.success(f"Scan complete — {len(cards)} opportunities ranked.")
