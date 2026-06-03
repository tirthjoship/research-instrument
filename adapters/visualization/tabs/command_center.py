"""Tab 1: Command Center — Today's actions, alerts, signal freshness."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import streamlit as st

from adapters.visualization.components.formatters import freshness_status_html
from adapters.visualization.components.metrics import (
    render_action_card,
    render_info_section,
)
from adapters.visualization.data_loader import load_holdings, load_recommendations

DB_PATH = "data/recommendations.db"
REPORTS_DIR = "data/reports"


def render(db_path: str = DB_PATH, reports_dir: str = REPORTS_DIR) -> None:
    """Render the Command Center tab."""
    render_info_section(
        st,
        "Command Center",
        "Your daily decision summary — what needs attention right now.",
        "This tab synthesizes all available data into prioritized actions. "
        "Sell signals appear first (protect capital), then buy opportunities, "
        "then watchlist items. Signal freshness shows how recent your data is — "
        "stale data means stale predictions.",
    )

    _render_freshness(reports_dir, db_path)
    st.divider()
    _render_actions(db_path)


def _render_freshness(reports_dir: str, db_path: str) -> None:
    """Show freshness indicators as styled pills."""
    st.markdown("#### Signal Freshness")
    st.markdown(
        '<p class="section-subtitle">How recent is your data? Stale data means stale predictions.</p>',
        unsafe_allow_html=True,
    )

    cols = st.columns(4)

    # Backtest
    report_path = Path(reports_dir)
    backtest_files = (
        sorted(report_path.glob("backtest_report_*.json"))
        if report_path.exists()
        else []
    )
    if backtest_files:
        mtime = datetime.fromtimestamp(backtest_files[-1].stat().st_mtime)
        pill = freshness_status_html(mtime)
    else:
        pill = freshness_status_html(None)
    cols[0].markdown(
        f'<div class="dashboard-card"><strong>Backtest</strong><br>{pill}</div>',
        unsafe_allow_html=True,
    )

    # Tournament
    recs = load_recommendations(db_path)
    if recs:
        cols[1].markdown(
            f'<div class="dashboard-card"><strong>Tournament</strong><br>'
            f'<span class="status-pill pill-fresh">{len(recs)} picks</span></div>',
            unsafe_allow_html=True,
        )
    else:
        cols[1].markdown(
            f'<div class="dashboard-card"><strong>Tournament</strong><br>'
            f"{freshness_status_html(None)}</div>",
            unsafe_allow_html=True,
        )

    # Holdings
    holdings = load_holdings(db_path)
    cols[2].markdown(
        f'<div class="dashboard-card"><strong>Holdings</strong><br>'
        f'<span style="font-size: 24px; font-weight: 700;">{len(holdings)}</span></div>',
        unsafe_allow_html=True,
    )

    # SHAP
    shap_path = Path(reports_dir) / "shap_importance.json"
    if shap_path.exists():
        mtime = datetime.fromtimestamp(shap_path.stat().st_mtime)
        pill = freshness_status_html(mtime)
    else:
        pill = freshness_status_html(None)
    cols[3].markdown(
        f'<div class="dashboard-card"><strong>SHAP Analysis</strong><br>{pill}</div>',
        unsafe_allow_html=True,
    )


def _render_actions(db_path: str) -> None:
    """Show prioritized action items with styled cards."""
    st.markdown("#### Today's Actions")
    st.markdown(
        '<p class="section-subtitle">Prioritized: sell signals first, then buy opportunities.</p>',
        unsafe_allow_html=True,
    )

    holdings = load_holdings(db_path)
    recs = load_recommendations(db_path)
    held_symbols = {h.symbol for h in holdings}

    if not holdings and not recs:
        st.markdown(
            '<div class="dashboard-card card-info">'
            "<strong>Getting Started</strong><br>"
            '<span style="color: #6B7280;">Run a tournament to generate picks, '
            "then add holdings to track your portfolio.</span>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    # Portfolio summary
    if holdings:
        st.markdown("**Portfolio**")
        import pandas as pd

        df = pd.DataFrame(
            [
                {
                    "Symbol": h.symbol,
                    "Qty": h.quantity,
                    "Price": f"${h.purchase_price:.2f}",
                    "Value": f"${h.quantity * h.purchase_price:,.0f}",
                }
                for h in holdings
            ]
        )
        st.dataframe(df, use_container_width=True, hide_index=True)

    # Buy opportunities
    if recs:
        st.markdown("**Latest Opportunities**")
        new_recs = [r for r in recs if r.symbol not in held_symbols]
        for rec in new_recs[:5]:
            action = "BUY" if "buy" in rec.grade.value else "WATCH"
            render_action_card(
                st,
                action_type=action,
                symbol=rec.symbol,
                reason=rec.reasoning[:100] if rec.reasoning else "—",
                urgency="this_week",
                confidence=rec.prediction.confidence_5d,
                grade=rec.grade.value,
            )
