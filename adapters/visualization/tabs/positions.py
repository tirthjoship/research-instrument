"""Tab 4: Outcome Tracker — trade recording form and P&L display."""

from __future__ import annotations

import datetime

import streamlit as st

from adapters.visualization.action_runner import run_record_buy, run_record_sell
from adapters.visualization.components.metrics import render_inline_context
from adapters.visualization.components.verdicts import outcome_tracker_verdict
from adapters.visualization.data_loader import load_outcomes, load_trades

DB_PATH = "data/recommendations.db"


def render(db_path: str = DB_PATH) -> None:
    """Render the Outcome Tracker tab."""
    st.markdown("### Outcome Tracker")
    render_inline_context(
        st,
        "Record your trades (buys and sells) to track real P&L. "
        "Closing a position by logging a sell triggers automatic round-trip outcome calculation.",
    )

    trades = load_trades(db_path)
    outcomes = load_outcomes(db_path)

    # ── Verdict banner ────────────────────────────────────────────────
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
    card_class = (
        "card-buy"
        if total_return > 0
        else ("card-sell" if total_return < 0 else "card-info")
    )
    st.markdown(
        f'<div class="dashboard-card {card_class}">{verdict}</div>',
        unsafe_allow_html=True,
    )

    st.divider()

    # ── Trade Recording Form ──────────────────────────────────────────
    st.markdown("#### Record a Trade")
    st.markdown(
        '<p class="section-subtitle">Log a buy or sell to start tracking outcomes.</p>',
        unsafe_allow_html=True,
    )
    with st.form("record_trade_form"):
        action = st.radio("Action", ["Buy", "Sell"], horizontal=True)
        fcols = st.columns(4)
        ticker = fcols[0].text_input("Ticker", placeholder="NVDA")
        price = fcols[1].number_input(
            "Price ($)", min_value=0.01, value=100.0, step=1.0
        )
        quantity = fcols[2].number_input("Quantity", min_value=1, value=10, step=1)
        trade_date = fcols[3].date_input("Date", value=datetime.date.today())
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
                    f"BUY recorded: {ticker.upper()} x{quantity} @ ${price:.2f} on {date_str}"
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
                    f"SELL recorded: {ticker.upper()} x{quantity} @ ${price:.2f} on {date_str}"
                )
            st.rerun()

    st.divider()

    # ── Summary metrics ───────────────────────────────────────────────
    st.markdown("#### Summary")
    mcols = st.columns(3)
    mcols[0].metric("Total Trades", str(len(trades)))
    mcols[1].metric(
        "Win Rate",
        f"{win_rate:.0f}%" if outcomes else "—",
    )
    sign = "+" if total_return >= 0 else ""
    mcols[2].metric(
        "Total Return",
        f"{sign}${total_return:,.2f}" if outcomes else "—",
    )

    st.divider()

    # ── Outcomes table ────────────────────────────────────────────────
    if outcomes:
        st.markdown("#### Closed Positions")
        import pandas as pd

        outcome_df = pd.DataFrame(
            [
                {
                    "Ticker": o.ticker,
                    "Buy Price": f"${o.buy_price:.2f}",
                    "Sell Price": f"${o.sell_price:.2f}",
                    "Return %": f"{'+' if o.return_pct >= 0 else ''}{o.return_pct:.1f}%",
                    "Return $": f"{'+' if o.return_dollar >= 0 else ''}${o.return_dollar:,.2f}",
                    "Holding Days": o.holding_days,
                    "Buy Date": o.buy_date,
                    "Sell Date": o.sell_date,
                }
                for o in outcomes
            ]
        )
        st.dataframe(outcome_df, use_container_width=True, hide_index=True)
        st.divider()

    # ── All trades list ───────────────────────────────────────────────
    if trades:
        st.markdown("#### All Recorded Trades")
        import pandas as pd

        trades_df = pd.DataFrame(
            [
                {
                    "Date": t.trade_date,
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
    else:
        st.markdown(
            '<div class="dashboard-card card-info">'
            "<strong>No trades yet</strong><br>"
            '<span style="color: #6B7280;">Use the form above to record your first trade.</span>'
            "</div>",
            unsafe_allow_html=True,
        )
