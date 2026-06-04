"""Tab 4: My Portfolio — trade recording form and P&L display."""

from __future__ import annotations

import datetime

import streamlit as st

from adapters.visualization.action_runner import run_record_buy, run_record_sell
from adapters.visualization.components.verdicts import outcome_tracker_verdict
from adapters.visualization.data_loader import load_outcomes, load_trades

DB_PATH = "data/recommendations.db"


def render(db_path: str = DB_PATH) -> None:
    """Render the My Portfolio tab."""
    st.markdown("### My Portfolio")
    st.markdown(
        '<div style="color:#64748B;font-size:14px;margin-bottom:16px;">'
        "Record trades and track your performance. The system learns from every trade."
        "</div>",
        unsafe_allow_html=True,
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

    st.divider()

    # ── Trade Recording Form ──────────────────────────────────────────
    st.markdown("#### Record a Trade")
    st.markdown(
        '<p style="color:#64748B;font-size:13px;margin-top:-8px;margin-bottom:12px;">'
        "Log a buy or sell to start tracking your outcomes."
        "</p>",
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
        trade_date = fcols[3].date_input(
            "Date (EST)", value=datetime.date.today(), help="Enter date in EST timezone"
        )
        submitted = st.form_submit_button(
            "Record Trade",
            type="primary",
            use_container_width=False,
        )
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

    st.divider()

    # ── Summary metrics (only shown when there is data) ───────────────
    if trades or outcomes:
        st.markdown("#### Summary")
        st.markdown(
            '<div class="ws-card">',
            unsafe_allow_html=True,
        )
        metric_cols = st.columns(
            3 if (outcomes and trades) else (2 if outcomes or trades else 1)
        )
        col_idx = 0
        if trades:
            metric_cols[col_idx].metric("Total Trades", str(len(trades)))
            col_idx += 1
        if outcomes:
            metric_cols[col_idx].metric("Win Rate", f"{win_rate:.0f}%")
            col_idx += 1
            sign = "+" if total_return >= 0 else ""
            metric_cols[col_idx].metric("Total Return", f"{sign}${total_return:,.2f}")
        st.markdown("</div>", unsafe_allow_html=True)
        st.divider()

    # ── Closed Positions table ────────────────────────────────────────
    if outcomes:
        import pandas as pd

        st.markdown("#### Closed Positions")

        def _pct_cell(val: float) -> str:
            color = "#16A34A" if val > 0 else ("#DC2626" if val < 0 else "#374151")
            sign = "+" if val >= 0 else ""
            return (
                f'<span style="color:{color};font-weight:600;">'
                f"{sign}{val:.1f}%</span>"
            )

        def _dollar_cell(val: float) -> str:
            color = "#16A34A" if val > 0 else ("#DC2626" if val < 0 else "#374151")
            sign = "+" if val >= 0 else ""
            return (
                f'<span style="color:{color};font-weight:600;">'
                f"{sign}${val:,.2f}</span>"
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

    # ── Open Positions (buys without matching sell) ───────────────────
    if trades:
        import pandas as pd

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
                    "Action": "Record Sell when ready",
                }
                for t in open_trades
            ]
            st.dataframe(
                pd.DataFrame(open_rows), use_container_width=True, hide_index=True
            )
            st.divider()

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
    else:
        # ── Empty state ───────────────────────────────────────────────
        st.markdown(
            '<div class="ws-card" style="text-align:center;padding:2rem;">'
            '<div style="font-size:15px;font-weight:500;color:#1A202C;">No trades recorded yet</div>'
            '<div style="font-size:13px;color:#64748B;margin-top:6px;">'
            "When you spot an opportunity, click 'Track Trade' on the card to log it here. "
            "The system learns from every trade you make."
            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )
