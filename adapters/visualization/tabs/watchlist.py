"""Tab 2: Watchlist — Pinned tickers with live prices + add/remove."""

from __future__ import annotations

import streamlit as st

from adapters.visualization.data_loader import load_watchlist
from adapters.visualization.price_cache import batch_fetch_prices, fetch_ticker_info

DB_PATH = "data/recommendations.db"


def render(db_path: str = DB_PATH) -> None:
    watchlist = load_watchlist(db_path)

    st.markdown("### Watchlist")
    st.markdown(
        f'<div style="color:#64748B;font-size:14px;margin-bottom:16px;">'
        f"{len(watchlist)} ticker{'s' if len(watchlist) != 1 else ''} you're watching.</div>",
        unsafe_allow_html=True,
    )

    if not watchlist:
        st.markdown(
            '<div class="ws-card" style="text-align:center;padding:2rem;">'
            '<div style="font-size:15px;font-weight:500;color:#1A202C;">Your watchlist is empty</div>'
            '<div style="font-size:13px;color:#64748B;margin-top:4px;">Pin tickers from Today\'s Opportunities or add manually below.</div>'
            "</div>",
            unsafe_allow_html=True,
        )
        st.divider()
        _render_add_form(db_path)
        return

    # Batch fetch live prices for all watchlist tickers
    tickers = tuple(w["symbol"] for w in watchlist)
    try:
        prices = batch_fetch_prices(tickers)
    except Exception:
        prices = {}

    # Fetch key fundamentals for each ticker (cached)
    infos: dict[str, dict[str, object]] = {}
    for t in tickers:
        try:
            infos[t] = fetch_ticker_info(t)
        except Exception:
            infos[t] = {}

    # Render cards
    for w in watchlist:
        symbol = w["symbol"]
        price_data = prices.get(symbol, {})
        info = infos.get(symbol, {})
        _render_watchlist_card(symbol, w, price_data, info, db_path)

    st.divider()
    _render_add_form(db_path)


def _render_watchlist_card(
    symbol: str,
    w: dict[str, str],
    price_data: dict[str, float],
    info: dict[str, object],
    db_path: str,
) -> None:
    price = price_data.get("price", 0)
    change = price_data.get("change_pct", 0)
    pe_raw = info.get("trailingPE") or info.get("forwardPE")
    peg_raw = info.get("pegRatio")
    mcap_raw = info.get("marketCap", 0) or 0

    pe: float | None = float(pe_raw) if pe_raw is not None else None  # type: ignore[arg-type]
    peg: float | None = float(peg_raw) if peg_raw is not None else None  # type: ignore[arg-type]
    mcap: float = float(mcap_raw)  # type: ignore[arg-type]

    price_str = f"${price:,.2f}" if price else "—"
    change_color = "#16A34A" if change >= 0 else "#DC2626"
    change_str = f"{change:+.2f}%" if price else ""
    pe_str = f"{pe:.1f}x" if pe is not None else "—"
    peg_str = f"{peg:.2f}" if peg is not None else "—"
    mcap_str: str
    if mcap > 1e9:
        mcap_str = f"${mcap / 1e9:.0f}B"
    elif mcap > 1e6:
        mcap_str = f"${mcap / 1e6:.0f}M"
    else:
        mcap_str = "—"

    card_html = (
        f'<div class="ws-card" style="padding:16px;margin-bottom:12px;">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'<div style="display:flex;align-items:center;gap:12px;">'
        f"<span style=\"font-family:'DM Sans',sans-serif;font-weight:700;font-size:18px;\">{symbol}</span>"
        f"<span style=\"font-family:'JetBrains Mono',monospace;font-size:16px;\">{price_str}</span>"
        f'<span style="color:{change_color};font-weight:600;font-size:14px;">{change_str}</span>'
        f"</div>"
        f"</div>"
        f'<div style="margin-top:8px;font-size:13px;color:#475569;">'
        f"P/E: {pe_str} &middot; PEG: {peg_str} &middot; Mkt Cap: {mcap_str}"
        f"</div>"
        f'<div style="margin-top:6px;font-size:13px;color:#64748B;">'
        f"Watching since: {w.get('added_date', '—')} &middot; {w.get('notes', '')}"
        f"</div>"
        f"</div>"
    )
    st.markdown(card_html, unsafe_allow_html=True)

    btn_cols = st.columns([2, 2, 2, 6])
    with btn_cols[0]:
        if st.button("Remove", key=f"rm_{symbol}"):
            try:
                from adapters.data.sqlite_store import SQLiteStore

                SQLiteStore(db_path).remove_watchlist(symbol)
            except Exception:
                pass
            st.rerun()
    with btn_cols[1]:
        if st.button("Analyze", key=f"az_{symbol}"):
            st.session_state["analyze_ticker"] = symbol
            st.info(f"Switch to Stock Analysis tab and enter {symbol}")


def _render_add_form(db_path: str) -> None:
    st.markdown("#### Add to Watchlist")
    with st.form("add_watchlist_form", clear_on_submit=True):
        cols = st.columns([2, 3, 3, 1])
        ticker = cols[0].text_input("Symbol", placeholder="TSLA")
        reason = cols[1].selectbox(
            "Reason",
            [
                "Earnings play",
                "Sector rotation",
                "Upstream signal",
                "Technical setup",
                "Insider activity",
                "Momentum",
                "Custom",
            ],
        )
        notes = cols[2].text_input("Notes (optional)", placeholder="Details...")
        submitted = cols[3].form_submit_button("Add")
        if submitted and ticker:
            full_notes = f"{reason}" + (f" — {notes}" if notes else "")
            try:
                from adapters.visualization.action_runner import run_add_watchlist

                run_add_watchlist(ticker.upper(), full_notes, db_path=db_path)
            except Exception:
                pass
            st.rerun()
