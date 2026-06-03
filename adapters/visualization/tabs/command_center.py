"""Tab 1: Command Center — Today's actions, alerts, signal freshness."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import streamlit as st

from adapters.visualization.components.formatters import freshness_status
from adapters.visualization.components.metrics import render_action_card
from adapters.visualization.data_loader import load_holdings, load_recommendations

DB_PATH = "data/recommendations.db"
REPORTS_DIR = "data/reports"


def render(db_path: str = DB_PATH, reports_dir: str = REPORTS_DIR) -> None:
    """Render the Command Center tab."""
    st.header("Command Center")

    # --- System status / freshness ---
    st.subheader("Signal Freshness")
    _render_freshness(reports_dir, db_path)

    st.divider()

    # --- Today's actions ---
    st.subheader("Today's Actions")
    _render_actions(db_path)

    st.divider()

    # --- Active events placeholder ---
    st.subheader("Active Events")
    st.info("Run event classification pipeline to populate active events.")


def _render_freshness(reports_dir: str, db_path: str) -> None:
    """Show freshness indicators for key data sources."""
    cols = st.columns(4)

    # Last backtest report
    report_path = Path(reports_dir)
    backtest_files = (
        sorted(report_path.glob("backtest_report_*.json"))
        if report_path.exists()
        else []
    )
    if backtest_files:
        mtime = datetime.fromtimestamp(backtest_files[-1].stat().st_mtime)
        icon, label = freshness_status(mtime)
        cols[0].metric("Backtest", f"{icon} {label}")
    else:
        cols[0].metric("Backtest", "❌ Never run")

    # Last recommendation
    recs = load_recommendations(db_path)
    if recs:
        cols[1].metric("Tournament", f"✅ {len(recs)} picks")
    else:
        cols[1].metric("Tournament", "❌ No picks")

    # Holdings
    holdings = load_holdings(db_path)
    cols[2].metric("Holdings", str(len(holdings)))

    # SHAP report
    shap_path = Path(reports_dir) / "shap_importance.json"
    if shap_path.exists():
        mtime = datetime.fromtimestamp(shap_path.stat().st_mtime)
        icon, label = freshness_status(mtime)
        cols[3].metric("SHAP", f"{icon} {label}")
    else:
        cols[3].metric("SHAP", "❌ Not run")


def _render_actions(db_path: str) -> None:
    """Show prioritized action items: sell signals first, then buy opportunities."""
    holdings = load_holdings(db_path)
    recs = load_recommendations(db_path)

    held_symbols = {h.symbol for h in holdings}

    if not holdings and not recs:
        st.info(
            "No data yet. Run these commands to populate:\n\n"
            "```\npython -m application.cli run-tournament --market us\n"
            "python -m application.cli add-holding NVDA 10 --price=950\n```"
        )
        return

    if holdings:
        st.markdown("**Portfolio Status**")
        for h in holdings:
            st.markdown(f"- {h.symbol}: {h.quantity} shares @ ${h.purchase_price:.2f}")

    if recs:
        st.markdown("**Latest Tournament Picks**")
        new_recs = [r for r in recs if r.symbol not in held_symbols]
        for rec in new_recs[:5]:
            render_action_card(
                st,
                action_type="BUY" if "Buy" in rec.grade.value else "WATCH",
                symbol=rec.symbol,
                reason=rec.reasoning[:80] if rec.reasoning else "—",
                urgency="this_week",
                confidence=rec.prediction.confidence_5d,
            )
