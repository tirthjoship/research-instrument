"""Tab 1: Opportunity Feed — conviction-ranked cards, hero banner, actions."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

from adapters.visualization.action_runner import run_conviction_scan, run_full_cycle
from adapters.visualization.components.formatters import freshness_dot_html
from adapters.visualization.components.metrics import (
    render_hero_banner,
    render_inline_context,
)
from adapters.visualization.components.opportunity_cards import (
    render_opportunity_card_html,
)
from adapters.visualization.components.verdicts import command_center_verdict
from adapters.visualization.data_loader import load_holdings, load_recommendations

DB_PATH = "data/recommendations.db"
REPORTS_DIR = "data/reports"


def render(db_path: str = DB_PATH, reports_dir: str = REPORTS_DIR) -> None:
    """Render the Opportunity Feed tab."""
    holdings = load_holdings(db_path)
    recs = load_recommendations(db_path)

    total_value = (
        sum(h.quantity * h.purchase_price for h in holdings) if holdings else 0
    )
    freshness_hours = _get_freshness_hours(reports_dir)

    # Hero banner
    verdict = command_center_verdict(
        n_holdings=len(holdings),
        n_recommendations=len(recs),
        n_sell_signals=0,
        freshness_hours=freshness_hours,
    )
    render_hero_banner(
        st, verdict, portfolio_value=total_value, n_positions=len(holdings)
    )

    # Two action buttons side by side
    col_scan, col_cycle = st.columns(2)

    with col_scan:
        scan_clicked = st.button(
            "Scan for Opportunities", type="primary", key="scan_opportunities"
        )

    with col_cycle:
        cycle_clicked = st.button("Run Full Cycle", key="run_full_cycle_opp")

    if scan_clicked:
        progress = st.progress(0)
        status_text = st.empty()

        def _scan_update(pct_val: float, msg: str) -> None:
            progress.progress(pct_val)
            status_text.text(msg)

        cards = run_conviction_scan(db_path=db_path, progress_callback=_scan_update)
        st.session_state["opportunity_cards"] = cards
        progress.empty()
        status_text.empty()
        st.success(f"Scan complete — {len(cards)} opportunities ranked.")

    if cycle_clicked:
        progress = st.progress(0)
        status_text = st.empty()

        def _cycle_update(pct_val: float, msg: str) -> None:
            progress.progress(pct_val)
            status_text.text(msg)

        results = run_full_cycle(db_path=db_path, progress_callback=_cycle_update)
        st.success("Full cycle complete")
        for key, val in results.items():
            st.caption(f"{key}: {val}")
        st.rerun()

    st.divider()

    # Opportunity cards
    cards = st.session_state.get("opportunity_cards", [])
    if cards:
        render_inline_context(
            st,
            f"{len(cards)} opportunities ranked by conviction. "
            "Green border = strong signal (7+), amber = developing (4-6), red = weak (<4).",
        )
        for card in cards:
            st.markdown(
                render_opportunity_card_html(card, now=datetime.now()),
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            '<div class="dashboard-card card-info">'
            "<strong>No opportunities scanned yet</strong><br>"
            '<span style="color: #6B7280;">Click "Scan for Opportunities" above to '
            "run conviction scoring across the ticker universe.</span>"
            "</div>",
            unsafe_allow_html=True,
        )

    st.divider()

    # Holdings summary
    _render_holdings_summary(holdings)

    # Signal freshness row
    _render_freshness(reports_dir, db_path)


def _get_freshness_hours(reports_dir: str) -> float | None:
    """Get hours since last backtest report."""
    report_path = Path(reports_dir)
    backtest_files = (
        sorted(report_path.glob("backtest_report_*.json"))
        if report_path.exists()
        else []
    )
    if backtest_files:
        mtime = datetime.fromtimestamp(backtest_files[-1].stat().st_mtime)
        return (datetime.now() - mtime).total_seconds() / 3600
    return None


def _render_holdings_summary(holdings: list[Any]) -> None:
    """Show a brief summary of current holdings."""
    st.markdown("**Holdings Summary**")
    if not holdings:
        st.caption("No holdings tracked. Add positions via the Positions tab.")
        return

    total_value = sum(h.quantity * h.purchase_price for h in holdings)
    st.caption(
        f"{len(holdings)} position(s) tracked · "
        f"Total cost basis: ${total_value:,.0f}"
    )


def _render_freshness(reports_dir: str, db_path: str) -> None:
    """Show signal freshness as a single row with colored dots."""
    st.markdown("**Signal Freshness**")
    render_inline_context(
        st,
        "How recent is your data? Stale data means stale predictions.",
    )

    report_path = Path(reports_dir)
    backtest_files = (
        sorted(report_path.glob("backtest_report_*.json"))
        if report_path.exists()
        else []
    )

    recs = load_recommendations(db_path)
    holdings = load_holdings(db_path)

    backtest_dot = (
        freshness_dot_html(datetime.fromtimestamp(backtest_files[-1].stat().st_mtime))
        if backtest_files
        else freshness_dot_html(None)
    )

    shap_path = Path(reports_dir) / "shap_importance.json"
    shap_dot = (
        freshness_dot_html(datetime.fromtimestamp(shap_path.stat().st_mtime))
        if shap_path.exists()
        else freshness_dot_html(None)
    )

    tournament_html = (
        f'<span class="freshness-dot dot-fresh"></span>{len(recs)} picks'
        if recs
        else freshness_dot_html(None)
    )

    st.markdown(
        f"Backtest {backtest_dot} · "
        f"Tournament {tournament_html} · "
        f"SHAP {shap_dot} · "
        f"Holdings {len(holdings)} tracked",
        unsafe_allow_html=True,
    )
