"""Tab 4: My Portfolio — live P&L, position health cards, trade form."""

from __future__ import annotations

import datetime
from typing import Any

import streamlit as st

from adapters.visualization.action_runner import run_record_buy, run_record_sell
from adapters.visualization.components.verdicts import outcome_tracker_verdict
from adapters.visualization.data_loader import load_watchlist
from adapters.visualization.price_cache import batch_fetch_prices, fetch_ticker_info

DB_PATH = "data/recommendations.db"

# Small-book threshold: ≤ this many positions → flat treemap layout.
SMALL_BOOK_MAX = 5


def _resolve_book() -> tuple[list[Any], str]:
    """Resolve the portfolio book via the same resolver Home/Risk use.

    Priority: session-uploaded book (flagged non-sample) -> bundled sample
    book. Never falls back to the operator's ``data/personal/holdings.csv`` or
    SQLite in the public UI — see book_context.resolve_ui_book_context().

    Returns ``(holdings, source_label)`` where ``holdings`` are domain Holdings
    aggregated one-row-per-ticker. The label is shown to the user so they always
    know which book they are looking at (legibility over silent magic).
    """
    from adapters.visualization.book_context import resolve_ui_book_context
    from application.holdings_reader import aggregate_to_book

    ctx = resolve_ui_book_context()
    book = aggregate_to_book(ctx.book)
    source = "sample book" if ctx.is_sample else "uploaded book"
    return book, source


def render(db_path: str = DB_PATH) -> None:
    """Render the My Portfolio tab (redesigned: hero / review / treemap / table / spy)."""
    from adapters.visualization.components.portfolio_detail import render_inspect_detail
    from adapters.visualization.components.portfolio_metrics import build_hero_html
    from adapters.visualization.components.portfolio_performance import (
        alpha_vs_spy,
        build_perf_figure,
    )
    from adapters.visualization.components.portfolio_review import (
        build_calm_html,
        build_review_card_html,
    )
    from adapters.visualization.components.portfolio_table import (
        TableState,
        apply_table_state,
        build_table_html,
    )
    from adapters.visualization.components.treemap import LENSES, build_treemap_html
    from adapters.visualization.data_loader import load_brief_summary, load_trades
    from adapters.visualization.portfolio_view import (
        enrich_holdings,
        split_flagged_healthy,
        top5_weight,
    )
    from adapters.visualization.price_cache import batch_fetch_prices, fetch_ticker_info

    st.markdown('<div class="ri-h1">My Portfolio</div>', unsafe_allow_html=True)

    holdings, book_source = _resolve_book()
    trades = load_trades(db_path)

    if not holdings and not trades:
        _render_empty_state()
        with st.expander("Record a Trade", expanded=False):
            _render_trade_form(db_path)
        return

    if holdings:
        st.caption(f"{len(holdings)} holdings · source: {book_source}")

    tickers = tuple(h.symbol for h in holdings)
    try:
        prices = batch_fetch_prices(tickers) if tickers else {}
    except Exception:  # noqa: BLE001
        prices = {}
    infos: dict[str, dict[str, Any]] = {}
    for t in tickers:
        try:
            infos[t] = fetch_ticker_info(t)
        except Exception:  # noqa: BLE001
            infos[t] = {}
    brief = load_brief_summary() or {}
    brief_by_ticker = {
        b.get("ticker", ""): b for b in brief.get("holdings", []) if b.get("ticker")
    }

    rows = enrich_holdings(holdings, prices, infos, brief_by_ticker)
    flagged, healthy = split_flagged_healthy(rows)
    book_value = sum(r.value for r in rows)
    cost = sum(r.cost for r in rows)
    pnl = book_value - cost
    pnl_pct = (pnl / cost * 100.0) if cost > 0 else 0.0

    spy_pct = brief.get("vs_market_1y")
    spy_end = float(spy_pct) if spy_pct is not None else None

    st.markdown('<div class="ri-sec">Portfolio snapshot</div>', unsafe_allow_html=True)
    st.markdown(
        build_hero_html(
            book_value=book_value,
            cost=cost,
            pnl=pnl,
            pnl_pct=pnl_pct,
            spy_pct=spy_end,
            needs_review=len(flagged),
            total_positions=len(rows),
            top5=top5_weight(rows),
        ),
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div class="ri-sec" style="color:#991B1B;border-color:#FECACA;">'
        f"⚠ Needs review — {len(flagged)} of {len(rows)}</div>",
        unsafe_allow_html=True,
    )
    if flagged:
        for r in flagged:
            st.markdown(build_review_card_html(r), unsafe_allow_html=True)
    else:
        st.markdown(build_calm_html(), unsafe_allow_html=True)

    st.markdown(
        '<div class="ri-sec">Your book at a glance</div>', unsafe_allow_html=True
    )
    lens = st.radio(
        "Colour by",
        LENSES,
        horizontal=True,
        format_func=lambda x: {"pnl": "P&L", "today": "Today", "verdict": "Verdict"}[x],
        key="pf_lens",
        label_visibility="collapsed",
    )
    flat = len(rows) <= SMALL_BOOK_MAX
    st.markdown(
        build_treemap_html(rows, lens=lens, width=1000.0, height=360.0, flat=flat),
        unsafe_allow_html=True,
    )

    inspect = st.query_params.get("inspect")
    if inspect:
        match = next((r for r in rows if r.ticker == inspect), None)
        if match:
            render_inspect_detail(match)

    st.markdown(
        f'<div class="ri-sec">Healthy holdings — {len(healthy)} of {len(rows)}</div>',
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns([3, 2, 2])
    query = c1.text_input(
        "Filter ticker",
        key="pf_q",
        label_visibility="collapsed",
        placeholder="🔎 filter ticker",
    )
    filt = c2.radio(
        "Filter",
        ["all", "gain", "loss"],
        horizontal=True,
        key="pf_filter",
        label_visibility="collapsed",
    )
    show_more = c3.toggle("⊕ more columns", key="pf_more")
    sort_raw = st.selectbox(
        "Sort by",
        ["weight", "pnl", "today", "value", "ticker", "sector"],
        key="pf_sort",
    )
    sort = sort_raw or "weight"
    state = TableState(
        sort=sort,
        ascending=False,
        filter=filt,
        query=query or "",
        show_more=show_more,
    )
    view = apply_table_state(healthy, state)
    PAGE = 10
    total_pages = max(1, (len(view) + PAGE - 1) // PAGE)
    page = st.number_input("Page", 1, total_pages, 1, key="pf_page")
    start = (int(page) - 1) * PAGE
    st.markdown(
        build_table_html(view[start : start + PAGE], state), unsafe_allow_html=True
    )
    st.caption(
        f"Showing {start + 1 if view else 0}–{min(start + PAGE, len(view))} of {len(view)}"
    )

    alpha = alpha_vs_spy(pnl_pct, spy_end)
    badge = (
        f"▲ +{alpha:.1f}% vs SPY"
        if alpha is not None and alpha >= 0
        else (f"▼ {alpha:.1f}% vs SPY" if alpha is not None else "SPY: DATA-GAP")
    )
    st.markdown(
        f'<div class="ri-sec">Portfolio vs SPY &nbsp; '
        f'<span style="font-size:.8rem;color:var(--ri-green);">{badge}</span></div>',
        unsafe_allow_html=True,
    )
    win = st.radio(
        "Window",
        ["ytd", "all", "1y"],
        index=1,
        horizontal=True,
        format_func=lambda x: {"ytd": "YTD", "all": "All", "1y": "1Y"}[x],
        key="pf_window",
        label_visibility="collapsed",
    )
    port_series, spy_series, labels = _perf_series(rows, win, spy_end, pnl_pct)
    st.plotly_chart(
        build_perf_figure(port_pct=port_series, spy_pct=spy_series, labels=labels),
        use_container_width=True,
    )

    st.markdown('<div class="ri-sec">Manage</div>', unsafe_allow_html=True)
    with st.expander("Watchlist", expanded=False):
        _render_watchlist_section(db_path)
    with st.expander("Record a Trade", expanded=False):
        _render_trade_form(db_path)


def _perf_series(
    rows: list[Any],
    window: str,
    spy_end: float | None,
    pnl_pct: float,
) -> tuple[list[float], list[float], list[str]]:
    """Simple attributed cumulative-return series per window (v1 linear ramp)."""
    labels_map: dict[str, list[str]] = {
        "ytd": ["Jan", "Mar", "Jun"],
        "all": ["Mar", "Apr", "Jun"],
        "1y": ["Jun '25", "Dec", "Jun '26"],
    }
    labels = labels_map.get(window, ["Mar", "Apr", "Jun"])
    n = len(labels)
    port = [round(pnl_pct * i / (n - 1), 2) for i in range(n)]
    end = spy_end if spy_end is not None else 0.0
    spy = [round(end * i / (n - 1), 2) for i in range(n)]
    return port, spy, labels


def _render_empty_state() -> None:
    st.markdown(
        '<div class="ws-card" style="text-align:center;padding:2rem;">'
        '<div style="font-size:15px;font-weight:500;color:#1A202C;">No trades recorded yet</div>'
        '<div style="font-size:13px;color:#64748B;margin-top:6px;">'
        "Log a trade to start tracking your portfolio."
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )


def _render_pnl_chart(outcomes: list[Any]) -> None:
    try:
        from adapters.visualization.components.charts import comparison_bars

        items = [{"name": o.ticker, "value": o.return_pct} for o in outcomes]
        if items:
            fig = comparison_bars(items, value_suffix="%")
            st.plotly_chart(fig, use_container_width=True)
    except Exception:
        pass


def _render_closed_positions_table(outcomes: list[Any]) -> None:
    """Render the closed positions HTML table (extracted for expander reuse)."""
    import pandas as pd

    def _pct_cell(val: float) -> str:
        color = "#16A34A" if val > 0 else ("#DC2626" if val < 0 else "#374151")
        sign = "+" if val >= 0 else ""
        return f'<span style="color:{color};font-weight:600;">{sign}{val:.1f}%</span>'

    def _dollar_cell(val: float) -> str:
        color = "#16A34A" if val > 0 else ("#DC2626" if val < 0 else "#374151")
        sign = "+" if val >= 0 else ""
        return f'<span style="color:{color};font-weight:600;">{sign}${val:,.2f}</span>'

    outcome_rows = [
        {
            "Ticker": o.ticker,
            "Buy Date (EST)": o.buy_date,
            "Sell Date (EST)": o.sell_date,
            "Buy Price": f"${o.buy_price:.2f}",
            "Sell Price": f"${o.sell_price:.2f}",
            "Return %": _pct_cell(o.return_pct),
            "Return $": _dollar_cell(o.return_dollar),
            "Holding Days": o.holding_days,
        }
        for o in outcomes
    ]
    outcome_df = pd.DataFrame(outcome_rows)
    st.write(outcome_df.to_html(escape=False, index=False), unsafe_allow_html=True)


def _render_trade_form(db_path: str) -> None:
    with st.form("record_trade_form"):
        action = st.radio("Action", ["Buy", "Sell"], horizontal=True)
        fcols = st.columns(4)
        ticker = fcols[0].text_input("Ticker", placeholder="NVDA")
        price = fcols[1].number_input(
            "Price ($)", min_value=0.01, value=100.0, step=1.0
        )
        quantity = fcols[2].number_input("Quantity", min_value=1, value=10, step=1)
        trade_date = fcols[3].date_input(
            "Date (EST)", value=datetime.date.today(), help="Enter date in EST timezone"
        )
        submitted = st.form_submit_button("Record Trade", type="primary")
        if submitted and ticker:
            date_str = trade_date.strftime("%Y-%m-%d")
            if action == "Buy":
                run_record_buy(
                    ticker=ticker.upper(),
                    price=float(price),
                    quantity=int(quantity),
                    trade_date=date_str,
                    db_path=db_path,
                )
                st.success(
                    f"BUY recorded: {ticker.upper()} x{quantity} @ ${price:.2f} on {date_str} EST"
                )
            else:
                run_record_sell(
                    ticker=ticker.upper(),
                    price=float(price),
                    quantity=int(quantity),
                    trade_date=date_str,
                    db_path=db_path,
                )
                st.success(
                    f"SELL recorded: {ticker.upper()} x{quantity} @ ${price:.2f} on {date_str} EST"
                )
            st.rerun()


def _render_trade_history(trades: list[Any], outcomes: list[Any]) -> None:
    import pandas as pd

    # Verdict banner
    total_return = sum(o.return_dollar for o in outcomes)
    win_rate = (
        (sum(1 for o in outcomes if o.return_pct > 0) / len(outcomes) * 100)
        if outcomes
        else 0.0
    )
    verdict = outcome_tracker_verdict(
        n_trades=len(trades),
        n_outcomes=len(outcomes),
        total_return=total_return,
        win_rate=win_rate,
    )
    card_color = (
        "#16A34A"
        if total_return > 0
        else ("#DC2626" if total_return < 0 else "#2563EB")
    )
    st.markdown(
        f'<div class="ws-card" style="border-left:4px solid {card_color};">'
        f"{verdict}"
        f"</div>",
        unsafe_allow_html=True,
    )

    # Open positions from trade log
    closed_buy_dates = {(o.ticker, o.buy_date) for o in outcomes}
    open_trades = [
        t
        for t in trades
        if t.action.value.upper() == "BUY"
        and (t.ticker, t.trade_date) not in closed_buy_dates
    ]
    if open_trades:
        st.markdown(
            '<div class="ri-sec" style="margin-top:.8rem;">Open positions (from trade log)</div>',
            unsafe_allow_html=True,
        )
        open_rows = [
            {
                "Ticker": t.ticker,
                "Buy Date (EST)": t.trade_date,
                "Buy Price": f"${t.price:.2f}",
                "Quantity": t.quantity,
                "Value": f"${t.total_value:,.2f}",
            }
            for t in open_trades
        ]
        st.dataframe(pd.DataFrame(open_rows), use_container_width=True, hide_index=True)

    # All trades
    st.markdown(
        '<div class="ri-sec" style="margin-top:.8rem;">All recorded trades</div>',
        unsafe_allow_html=True,
    )
    trades_df = pd.DataFrame(
        [
            {
                "Date (EST)": t.trade_date,
                "Ticker": t.ticker,
                "Action": t.action.value,
                "Price": f"${t.price:.2f}",
                "Quantity": t.quantity,
                "Value": f"${t.total_value:,.2f}",
                "Conviction": (
                    f"{t.conviction_at_trade:.2f}" if t.conviction_at_trade else "—"
                ),
            }
            for t in trades
        ]
    )
    st.dataframe(trades_df, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Watchlist section (folded in from deleted tabs/watchlist.py)
# ---------------------------------------------------------------------------


def _render_watchlist_section(db_path: str = "data/recommendations.db") -> None:
    """Render the watchlist — pinned tickers with live prices + add/remove."""
    watchlist = load_watchlist(db_path)

    st.markdown(
        f'<div style="color:var(--ri-muted);font-size:.85rem;margin-bottom:1rem;">'
        f"{len(watchlist)} ticker{'s' if len(watchlist) != 1 else ''} watching.</div>",
        unsafe_allow_html=True,
    )

    if not watchlist:
        st.markdown(
            '<div class="ws-card" style="text-align:center;padding:2rem;">'
            '<div style="font-size:15px;font-weight:500;color:#1A202C;">Watchlist empty</div>'
            "</div>",
            unsafe_allow_html=True,
        )
        _render_watchlist_add_form(db_path)
        return

    tickers = tuple(w["symbol"] for w in watchlist)
    try:
        prices = batch_fetch_prices(tickers)
    except Exception:
        prices = {}

    infos: dict[str, dict[str, object]] = {}
    for t in tickers:
        try:
            infos[t] = fetch_ticker_info(t)
        except Exception:
            infos[t] = {}

    for w in watchlist:
        symbol = w["symbol"]
        _render_watchlist_card(
            symbol, w, prices.get(symbol, {}), infos.get(symbol, {}), db_path
        )

    st.divider()
    _render_watchlist_add_form(db_path)


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
    if mcap > 1e9:
        mcap_str = f"${mcap / 1e9:.0f}B"
    elif mcap > 1e6:
        mcap_str = f"${mcap / 1e6:.0f}M"
    else:
        mcap_str = "—"

    yahoo_url = f"https://finance.yahoo.com/quote/{symbol}"

    st.markdown(
        f'<div class="ws-card" style="padding:16px;margin-bottom:12px;">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'<div style="display:flex;align-items:center;gap:12px;">'
        f'<span style="font-weight:700;font-size:18px;">{symbol}</span>'
        f'<span style="font-size:16px;">{price_str}</span>'
        f'<span style="color:{change_color};font-weight:600;font-size:14px;">{change_str}</span>'
        f'<a href="{yahoo_url}" target="_blank" '
        f'style="color:var(--ri-teal);font-size:.82rem;text-decoration:none;">&#8599;</a>'
        f"</div></div>"
        f'<div style="margin-top:8px;font-size:13px;color:#475569;">'
        f"P/E: {pe_str} &middot; PEG: {peg_str} &middot; Mkt Cap: {mcap_str}"
        f"</div>"
        f'<div style="margin-top:6px;font-size:13px;color:#64748B;">'
        f"Since: {w.get('added_date', '—')} &middot; {w.get('notes', '')}"
        f"</div></div>",
        unsafe_allow_html=True,
    )

    btn_cols = st.columns([2, 2, 2, 6])
    with btn_cols[0]:
        if st.button("Remove", key=f"wl_rm_{symbol}"):
            try:
                from adapters.data.sqlite_store import SQLiteStore

                SQLiteStore(db_path).remove_watchlist(symbol)
            except Exception as exc:
                st.warning(f"Watchlist update failed: {exc}")
            st.rerun()
    with btn_cols[1]:
        if st.button("Analyze", key=f"wl_az_{symbol}"):
            st.session_state["analyze_ticker"] = symbol
            st.info(f"{symbol} pre-filled — open the Stock Analysis tab to run it.")


def _render_watchlist_add_form(db_path: str) -> None:
    st.markdown(
        '<div class="ri-sec">Add to watchlist</div>',
        unsafe_allow_html=True,
    )
    with st.form("add_watchlist_form", clear_on_submit=True):
        cols = st.columns([3, 1])
        ticker = cols[0].text_input("Symbol", placeholder="TSLA")
        submitted = cols[1].form_submit_button("Add")
        if submitted and ticker:
            try:
                from adapters.visualization.action_runner import run_add_watchlist

                run_add_watchlist(ticker.upper(), "", db_path=db_path)
            except Exception as exc:
                st.warning(f"Watchlist update failed: {exc}")
            st.rerun()
