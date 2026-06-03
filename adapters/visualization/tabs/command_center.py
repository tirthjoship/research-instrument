"""Tab 1: Command Center — Hero banner, actions, signal freshness."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

from adapters.visualization.action_runner import run_full_cycle
from adapters.visualization.components.formatters import freshness_dot_html
from adapters.visualization.components.metrics import (
    render_action_card,
    render_hero_banner,
    render_inline_context,
)
from adapters.visualization.components.verdicts import command_center_verdict
from adapters.visualization.data_loader import load_holdings, load_recommendations

DB_PATH = "data/recommendations.db"
REPORTS_DIR = "data/reports"


def render(db_path: str = DB_PATH, reports_dir: str = REPORTS_DIR) -> None:
    """Render the Command Center tab."""
    holdings = load_holdings(db_path)
    recs = load_recommendations(db_path)
    held_symbols = {h.symbol for h in holdings}

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

    # Run Full Cycle button
    if st.button("Run Full Cycle", type="primary", key="run_full_cycle"):
        progress = st.progress(0)
        status_text = st.empty()

        def update(pct_val: float, msg: str) -> None:
            progress.progress(pct_val)
            status_text.text(msg)

        results = run_full_cycle(db_path=db_path, progress_callback=update)
        st.success("Full cycle complete")
        for key, val in results.items():
            st.caption(f"{key}: {val}")
        st.rerun()

    st.divider()

    # Priority-bucketed actions
    _render_actions(recs, held_symbols)

    st.divider()

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


def _render_actions(recs: list[Any], held_symbols: set[str]) -> None:
    """Show priority-bucketed action cards."""
    if not recs:
        st.markdown(
            '<div class="dashboard-card card-info">'
            "<strong>Getting Started</strong><br>"
            '<span style="color: #6B7280;">Click "Run Full Cycle" above to scan markets, '
            "generate picks, and start tracking.</span>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    new_recs = [r for r in recs if r.symbol not in held_symbols]
    buy_recs = [r for r in new_recs if "buy" in r.grade.value]
    watch_recs = [r for r in new_recs if "buy" not in r.grade.value]

    cols = st.columns(3)

    with cols[0]:
        st.markdown("**Urgent**")
        render_inline_context(st, "Sell signals and stop-loss alerts")
        st.markdown(
            '<div class="dashboard-card" style="border-left: 4px solid #059669;">'
            '<span style="color: #059669; font-weight: 600;">No sell signals detected</span>'
            "</div>",
            unsafe_allow_html=True,
        )

    with cols[1]:
        st.markdown("**This Week**")
        render_inline_context(st, "High-conviction buy opportunities")
        for rec in buy_recs[:3]:
            render_action_card(
                st,
                action_type="BUY",
                symbol=rec.symbol,
                reason=rec.reasoning[:80] if rec.reasoning else "—",
                urgency="this_week",
                confidence=rec.prediction.confidence_5d,
                grade=rec.grade.value,
            )
        if not buy_recs:
            st.caption("No buy signals this cycle")

    with cols[2]:
        st.markdown("**Watch**")
        render_inline_context(st, "Emerging signals worth monitoring")
        for rec in watch_recs[:3]:
            render_action_card(
                st,
                action_type="WATCH",
                symbol=rec.symbol,
                reason=rec.reasoning[:80] if rec.reasoning else "—",
                urgency="watch",
                confidence=rec.prediction.confidence_5d,
                grade=rec.grade.value,
            )
        if not watch_recs:
            st.caption("No watch signals this cycle")


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
