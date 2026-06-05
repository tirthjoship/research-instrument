"""Tab 4: My Portfolio — live P&L, position health cards, trade form."""

from __future__ import annotations

import datetime
from typing import Any

import streamlit as st

from adapters.visualization.action_runner import run_record_buy, run_record_sell
from adapters.visualization.components.cards import metric_kpi
from adapters.visualization.components.verdicts import outcome_tracker_verdict
from adapters.visualization.data_loader import load_holdings, load_outcomes, load_trades
from adapters.visualization.price_cache import batch_fetch_prices

DB_PATH = "data/recommendations.db"


def render(db_path: str = DB_PATH) -> None:
    """Render the My Portfolio tab."""
    st.markdown("### My Portfolio")

    trades = load_trades(db_path)
    outcomes = load_outcomes(db_path)
    holdings = load_holdings(db_path)

    if not holdings and not trades:
        _render_empty_state()
        st.divider()
        with st.expander("Record a Trade"):
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

    # Portfolio summary with live P&L
    _render_portfolio_summary(holdings, prices, outcomes)

    # Position cards with live P&L
    if holdings:
        st.divider()
        st.markdown("#### Positions")
        for h in holdings:
            _render_position_card(h, prices, db_path)

    # P&L bar chart for closed positions
    if outcomes:
        st.divider()
        _render_pnl_chart(outcomes)

    # Trade recording (collapsed)
    st.divider()
    with st.expander("Record a Trade"):
        _render_trade_form(db_path)

    # Trade history
    if trades:
        st.divider()
        _render_trade_history(trades, outcomes)


def _render_empty_state() -> None:
    st.markdown(
        '<div class="ws-card" style="text-align:center;padding:2rem;">'
        '<div style="font-size:15px;font-weight:500;color:#1A202C;">No trades recorded yet</div>'
        '<div style="font-size:13px;color:#64748B;margin-top:6px;">'
        "Log a buy to start tracking your portfolio. The system learns from every trade you make."
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )


def _render_portfolio_summary(
    holdings: list[Any],
    prices: dict[str, dict[str, float]],
    outcomes: list[Any],
) -> None:
    total_value = 0.0
    total_cost = 0.0
    for h in holdings:
        p = prices.get(h.symbol, {})
        current = p.get("price", h.purchase_price)
        total_value += h.quantity * current
        total_cost += h.quantity * h.purchase_price

    total_pnl = total_value - total_cost
    pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0.0
    pnl_color = "#16A34A" if total_pnl >= 0 else "#DC2626"

    wins = sum(1 for o in outcomes if o.return_pct > 0)
    n_outcomes = len(outcomes)
    win_context = f"{wins}/{n_outcomes} wins" if n_outcomes > 0 else ""

    sign = "+" if total_pnl >= 0 else ""
    cols = st.columns(3)
    with cols[0]:
        st.markdown(
            metric_kpi("Total Value", f"${total_value:,.0f}"),
            unsafe_allow_html=True,
        )
    with cols[1]:
        st.markdown(
            metric_kpi(
                "Total P&L",
                f"{sign}${total_pnl:,.0f}",
                f"{sign}{pnl_pct:.1f}%",
                color=pnl_color,
            ),
            unsafe_allow_html=True,
        )
    with cols[2]:
        st.markdown(
            metric_kpi("Positions", str(len(holdings)), win_context),
            unsafe_allow_html=True,
        )


def _render_position_card(
    holding: Any, prices: dict[str, dict[str, float]], db_path: str
) -> None:
    p = prices.get(holding.symbol, {})
    current = p.get("price", holding.purchase_price)
    cost = holding.purchase_price
    pnl = (current - cost) * holding.quantity
    pnl_pct = (current - cost) / cost * 100 if cost > 0 else 0.0
    pnl_color = "#16A34A" if pnl >= 0 else "#DC2626"
    sign = "+" if pnl >= 0 else ""

    card_html = (
        f'<div class="ws-card" style="padding:16px;margin-bottom:12px;">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f"<div>"
        f"<span style=\"font-family:'DM Sans',sans-serif;font-weight:700;font-size:18px;\">{holding.symbol}</span>"
        f'<span style="color:#64748B;font-size:13px;margin-left:8px;">'
        f"{holding.quantity} shares @ ${cost:,.2f}</span>"
        f"</div>"
        f'<div style="text-align:right;">'
        f"<div style=\"font-family:'JetBrains Mono',monospace;font-size:16px;\">${current:,.2f}</div>"
        f'<div style="color:{pnl_color};font-size:14px;font-weight:600;">'
        f"{sign}${pnl:,.0f} ({sign}{pnl_pct:.1f}%)</div>"
        f"</div>"
        f"</div>"
        f"</div>"
    )
    st.markdown(card_html, unsafe_allow_html=True)


def _render_pnl_chart(outcomes: list[Any]) -> None:
    st.markdown("#### Closed Position Returns")
    try:
        from adapters.visualization.components.charts import comparison_bars

        items = [{"name": o.ticker, "value": o.return_pct} for o in outcomes]
        if items:
            fig = comparison_bars(items, value_suffix="%")
            st.plotly_chart(fig, use_container_width=True)
    except Exception:
        pass


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

    # Closed positions table
    if outcomes:
        st.markdown("#### Closed Positions")

        def _pct_cell(val: float) -> str:
            color = "#16A34A" if val > 0 else ("#DC2626" if val < 0 else "#374151")
            sign = "+" if val >= 0 else ""
            return (
                f'<span style="color:{color};font-weight:600;">{sign}{val:.1f}%</span>'
            )

        def _dollar_cell(val: float) -> str:
            color = "#16A34A" if val > 0 else ("#DC2626" if val < 0 else "#374151")
            sign = "+" if val >= 0 else ""
            return (
                f'<span style="color:{color};font-weight:600;">{sign}${val:,.2f}</span>'
            )

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
        st.divider()

    # Open positions
    closed_buy_dates = {(o.ticker, o.buy_date) for o in outcomes}
    open_trades = [
        t
        for t in trades
        if t.action.value.upper() == "BUY"
        and (t.ticker, t.trade_date) not in closed_buy_dates
    ]
    if open_trades:
        st.markdown("#### Open Positions")
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
        st.divider()

    # All trades
    st.markdown("#### All Recorded Trades")
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
