"""Tab 1: Today's Opportunities — auto-scan, 3-panel hero, compact conviction cards."""

from __future__ import annotations

from datetime import datetime
from typing import Any
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

    # Hero section
    spy_data = load_spy_sparkline()
    _render_hero(holdings, cache, spy_data, watchlist)

    # Opportunity cards
    cards = cache.get_results()
    if cards:
        st.markdown(
            f'<div style="color:#64748B;font-size:13px;margin:12px 0 8px;">'
            f"{len(cards)} opportunities ranked by conviction"
            f"</div>",
            unsafe_allow_html=True,
        )
        now = datetime.now()
        for card in cards:
            st.markdown(render_compact_card_html(card, now=now), unsafe_allow_html=True)

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

    # Portfolio panel
    total_value = (
        sum(h.quantity * h.purchase_price for h in holdings) if holdings else 0.0
    )
    best_performer = holdings[0].ticker if holdings else "—"
    portfolio = {
        "total_value": total_value,
        "total_pnl": 0.0,
        "pnl_pct": 0.0,
        "n_positions": len(holdings),
        "best_performer": best_performer,
    }

    # Signal panel
    cards = cache.get_results()
    top_card = cards[0] if cards else None
    n_watchlist_alerts = len(watchlist)
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
