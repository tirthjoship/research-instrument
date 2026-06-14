"""Tab 4: My Portfolio — live P&L, position health cards, trade form."""

from __future__ import annotations

import datetime
from typing import Any

import streamlit as st

from adapters.visualization.action_runner import run_record_buy, run_record_sell
from adapters.visualization.components.tooltip import tooltip
from adapters.visualization.components.verdicts import outcome_tracker_verdict
from adapters.visualization.data_loader import (
    load_brief_summary,
    load_holdings,
    load_outcomes,
    load_trades,
    load_watchlist,
)
from adapters.visualization.price_cache import batch_fetch_prices, fetch_ticker_info

DB_PATH = "data/recommendations.db"

# ── Verdict pill design tokens ─────────────────────────────────────────────
_VERDICT_COLORS: dict[str, tuple[str, str]] = {
    # (background, text-color)
    "REDUCE": ("#FEE2E2", "#991B1B"),
    "TRIM": ("#FEF3C7", "#92400E"),
    "REVIEW": ("#DBEAFE", "#1E40AF"),
    "HOLD": ("#F0FDF4", "#166534"),
}
_VERDICT_DEFAULT_COLORS: tuple[str, str] = ("#F1F5F9", "#475569")

# Verdicts that are review prompts (not forecasts / buy-sell instructions).
# Copy used in tooltips and aria text must frame these as discipline reviews.
_VERDICT_REVIEW_LABELS: dict[str, str] = {
    "REDUCE": "Review: consider reducing position size",
    "TRIM": "Review: consider trimming position",
    "REVIEW": "Review: mixed signals — no clear action yet",
    "HOLD": "Review: current size looks appropriate",
}


def _verdict_pill_html(verdict: str) -> str:
    """Return an HTML span styled as a verdict pill.

    Verdicts are DISCIPLINE REVIEW PROMPTS — not forecasts or trade instructions.
    The pill renders the verdict label only; no buy/sell language is included.
    """
    bg, fg = _VERDICT_COLORS.get(verdict, _VERDICT_DEFAULT_COLORS)
    label = _VERDICT_REVIEW_LABELS.get(verdict, f"Review: {verdict}")
    return (
        f'<span title="{label}" '
        f'style="display:inline-block;padding:2px 10px;border-radius:12px;'
        f"background:{bg};color:{fg};font-size:.78rem;font-weight:700;"
        f'letter-spacing:.04em;white-space:nowrap;">'
        f"{verdict}"
        f"</span>"
    )


def render(db_path: str = DB_PATH) -> None:
    """Render the My Portfolio tab."""
    st.markdown(
        '<div class="ri-h1" style="font-size:1.9rem;margin-bottom:.25rem;">My Portfolio</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="ri-sub" style="margin-bottom:1.2rem;">'
        "Tracked positions, recorded trades, and watchlist."
        "</div>",
        unsafe_allow_html=True,
    )

    trades = load_trades(db_path)
    outcomes = load_outcomes(db_path)
    holdings = load_holdings(db_path)

    if not holdings and not trades:
        _render_empty_state()
        st.divider()
        with st.expander("Record a Trade", expanded=False):
            _render_trade_form(db_path)
        return

    # Batch fetch live prices for open holdings
    if holdings:
        holding_tickers = tuple(h.symbol for h in holdings)
        try:
            prices = batch_fetch_prices(holding_tickers)
        except Exception:
            prices = {}
    else:
        prices = {}

    # Load brief summary for verdict / why cross-reference (DATA-GAP if absent)
    brief_summary = load_brief_summary()
    brief_holdings_by_ticker: dict[str, dict[str, Any]] = {}
    if brief_summary:
        for bh in brief_summary.get("holdings", []):
            t = bh.get("ticker", "")
            if t:
                brief_holdings_by_ticker[t] = bh

    # ── Portfolio hero (big-number metrics) ────────────────────────────────────
    st.markdown('<div class="ri-sec">Portfolio snapshot</div>', unsafe_allow_html=True)
    _render_portfolio_hero(holdings, prices, outcomes)

    # ── Open positions (primary view) ──────────────────────────────────────────
    if holdings:
        st.markdown('<div class="ri-sec">Open positions</div>', unsafe_allow_html=True)
        for h in holdings:
            _render_position_card(
                h,
                prices,
                db_path,
                brief_holding=brief_holdings_by_ticker.get(h.symbol),
            )

    # ── Closed positions (secondary — collapsed) ───────────────────────────────
    if outcomes:
        with st.expander("Closed positions", expanded=False):
            st.markdown(
                '<div class="ri-sec">Closed position returns</div>',
                unsafe_allow_html=True,
            )
            _render_pnl_chart(outcomes)
            _render_closed_positions_table(outcomes)

    # ── Trade history + outcome tracker (collapsed) ────────────────────────────
    if trades:
        with st.expander("Trade history & outcome tracker", expanded=False):
            _render_trade_history(trades, outcomes)

    # ── Record a Trade (collapsed) ────────────────────────────────────────────
    with st.expander("Record a Trade", expanded=False):
        _render_trade_form(db_path)

    # ── Watchlist (collapsed) ─────────────────────────────────────────────────
    with st.expander("Watchlist", expanded=False):
        _render_watchlist_section(db_path)


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


def _render_portfolio_hero(
    holdings: list[Any],
    prices: dict[str, dict[str, float]],
    outcomes: list[Any],
) -> None:
    """Big-number hero row: book value, total P&L, position count."""
    total_value = 0.0
    total_cost = 0.0
    for h in holdings:
        p = prices.get(h.symbol, {})
        current = p.get("price", h.purchase_price)
        total_value += h.quantity * current
        total_cost += h.quantity * h.purchase_price

    total_pnl = total_value - total_cost
    pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0.0
    pnl_color = "var(--ri-green)" if total_pnl >= 0 else "var(--ri-crimson)"

    wins = sum(1 for o in outcomes if o.return_pct > 0)
    n_outcomes = len(outcomes)
    win_context = (
        f"{wins}/{n_outcomes} closed wins" if n_outcomes > 0 else "no closed positions"
    )

    sign = "+" if total_pnl >= 0 else ""

    book_health_tip = tooltip("Book health", "Book health")
    concentrated_risk_tip = tooltip("Concentrated risk", "Concentrated risk")

    hero_html = (
        '<div class="ri-metric-row">'
        # Book value
        "<div>"
        f'<div class="ri-metric-lab">{book_health_tip} — Book value</div>'
        f'<div class="ri-metric-num">${total_value:,.0f}</div>'
        "</div>"
        # Total P&L
        "<div>"
        '<div class="ri-metric-lab">Total P&amp;L</div>'
        f'<div class="ri-metric-num" style="color:{pnl_color};">'
        f"{sign}${total_pnl:,.0f}"
        f'<span style="font-size:1.1rem;margin-left:.5rem;color:{pnl_color};">'
        f"({sign}{pnl_pct:.1f}%)</span>"
        "</div>"
        "</div>"
        # Position count
        "<div>"
        f'<div class="ri-metric-lab">{concentrated_risk_tip} — Positions</div>'
        f'<div class="ri-metric-num">{len(holdings)}</div>'
        f'<div style="font-size:.82rem;color:var(--ri-muted);margin-top:.15rem;">{win_context}</div>'
        "</div>"
        "</div>"
    )
    st.markdown(hero_html, unsafe_allow_html=True)


def _render_portfolio_summary(
    holdings: list[Any],
    prices: dict[str, dict[str, float]],
    outcomes: list[Any],
) -> None:
    """Legacy helper kept for import compatibility — delegates to hero."""
    _render_portfolio_hero(holdings, prices, outcomes)


def _render_position_card(
    holding: Any,
    prices: dict[str, dict[str, float]],
    db_path: str,
    brief_holding: dict[str, Any] | None = None,
) -> None:
    """Render a decision-card row for a single open holding.

    Summary line (always visible):
      ticker · company hint · verdict pill · one-line why · unrealized %

    Expander (collapsed by default):
      Existing evidence — live price, P&L details, Yahoo Finance link, Analyze button.

    HONESTY rules:
    - Verdict is a DISCIPLINE REVIEW PROMPT, not a forecast or buy/sell instruction.
    - RAG signal dots: the Holding domain model carries NO 5-signal RAG array.
      brief_summary.json holdings only carry ticker, verdict, unrealized_pct,
      trend_state, why — also no RAG array.
      → We render DATA-GAP for RAG signals rather than fabricate dots.
    - If brief_holding is None (not in latest brief), we show DATA-GAP for
      verdict and why.
    """
    p = prices.get(holding.symbol, {})
    current = p.get("price", holding.purchase_price)
    cost = holding.purchase_price
    pnl = (current - cost) * holding.quantity
    pnl_pct = (current - cost) / cost * 100 if cost > 0 else 0.0
    pnl_color = "#16A34A" if pnl >= 0 else "#DC2626"
    sign = "+" if pnl >= 0 else ""

    symbol = holding.symbol
    yahoo_url = f"https://finance.yahoo.com/quote/{symbol}"

    # ── Verdict + why from brief (DATA-GAP if not in latest brief) ────────────
    if brief_holding is not None:
        verdict = str(brief_holding.get("verdict") or "")
        why_text = str(brief_holding.get("why") or "")
        trend_state = str(brief_holding.get("trend_state") or "unknown")
    else:
        verdict = ""
        why_text = ""
        trend_state = "unknown"

    pill_html = (
        _verdict_pill_html(verdict)
        if verdict
        else (
            '<span style="font-size:.78rem;color:var(--ri-muted);font-style:italic;">'
            "DATA-GAP: run weekly-brief to get verdict"
            "</span>"
        )
    )

    why_display = (
        why_text
        if why_text
        else (
            '<span style="color:var(--ri-muted);font-style:italic;">'
            "DATA-GAP: no discipline context available"
            "</span>"
        )
    )

    # ── RAG signals: DATA-GAP (no 5-signal array on Holding or brief_holding) ─
    # The domain model and brief_summary.json do not carry a structured RAG
    # signal array. Rendering fabricated dots would be dishonest. Show context.
    rag_html = (
        '<span style="font-size:.75rem;color:var(--ri-muted);font-style:italic;">'
        "Signals: DATA-GAP (run screen for RAG breakdown)"
        "</span>"
    )
    # If trend_state is available, show it as the one available signal
    if trend_state and trend_state != "unknown":
        trend_color = "#16A34A" if trend_state == "uptrend" else "#DC2626"
        rag_html = (
            f'<span style="font-size:.75rem;color:var(--ri-muted);">Trend: </span>'
            f'<span style="font-size:.75rem;font-weight:600;color:{trend_color};">'
            f"{trend_state}"
            f"</span>"
            f'<span style="font-size:.75rem;color:var(--ri-muted);font-style:italic;margin-left:.5rem;">'
            f"· other signals: DATA-GAP"
            f"</span>"
        )

    # ── Decision-card summary row ──────────────────────────────────────────────
    summary_html = (
        f'<div class="ri-tile t-{"green" if pnl >= 0 else "crimson"}" '
        f'style="padding:.9rem 1.4rem;margin-bottom:.1rem;">'
        # Row 1: ticker · pill · unrealized %
        f'<div style="display:flex;align-items:center;gap:.7rem;flex-wrap:wrap;">'
        f"<span style=\"font-family:'Fraunces',serif;font-weight:700;font-size:1.25rem;\">"
        f"{symbol}</span>"
        f'<span style="color:var(--ri-muted);font-size:.8rem;">'
        f"{holding.quantity} sh @ ${cost:,.2f}</span>"
        # verdict pill (review prompt, not forecast)
        f"{pill_html}"
        # unrealized %
        f"<span style=\"margin-left:auto;font-family:'IBM Plex Mono',monospace;"
        f'font-size:.9rem;font-weight:700;color:{pnl_color};">'
        f"{sign}{pnl_pct:.1f}%"
        f"</span>"
        f"</div>"
        # Row 2: one-line why meaning
        f'<div style="margin-top:.35rem;font-size:.82rem;color:var(--ri-ink);">'
        f"{why_display}"
        f"</div>"
        # Row 3: RAG signals (honest DATA-GAP if unavailable)
        f'<div style="margin-top:.25rem;">'
        f"{rag_html}"
        f"</div>"
        f"</div>"
    )
    st.markdown(summary_html, unsafe_allow_html=True)

    # ── Expander: existing evidence (live price, P&L, links, button) ──────────
    with st.expander(f"{symbol} — full position details", expanded=False):
        detail_html = (
            f'<div style="display:flex;justify-content:space-between;'
            f'align-items:flex-start;padding:.5rem 0;">'
            # Left: links
            f"<div>"
            f'<div style="font-size:.8rem;color:var(--ri-muted);margin-bottom:.3rem;">'
            f'<a href="{yahoo_url}" target="_blank" '
            f'style="color:var(--ri-teal);text-decoration:none;margin-right:.8rem;">'
            f"&#8599; Yahoo Finance</a>"
            f'<span style="color:var(--ri-muted);">&#8594; pre-filled in Stock Analysis</span>'
            f"</div>"
            f"</div>"
            # Right: live price + full P&L
            f'<div style="text-align:right;">'
            f"<div style=\"font-family:'IBM Plex Mono',monospace;font-size:1rem;"
            f'color:var(--ri-ink);">${current:,.2f} live</div>'
            f'<div style="color:{pnl_color};font-size:.88rem;font-weight:600;'
            f'margin-top:.1rem;">'
            f"{sign}${pnl:,.0f} ({sign}{pnl_pct:.1f}%)</div>"
            f"</div>"
            f"</div>"
        )
        st.markdown(detail_html, unsafe_allow_html=True)

        # Verdict is a review prompt, not a trade instruction
        st.caption(
            "Discipline verdict = a REVIEW PROMPT based on factual signals, "
            "not a forecast or trade instruction."
        )

        btn_col, _ = st.columns([2, 10])
        with btn_col:
            if st.button(f"Analyze {symbol}", key=f"pos_analyze_{symbol}"):
                st.session_state["analyze_ticker"] = symbol
                st.info(f"{symbol} pre-filled — open the Stock Analysis tab to run it.")


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
