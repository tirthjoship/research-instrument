"""Dashboard entry point — tab router and page config.

Run: streamlit run adapters/visualization/dashboard.py
"""

from __future__ import annotations

import datetime

import streamlit as st

st.set_page_config(
    page_title="Stock Recommender Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from adapters.visualization.components.styles import inject_global_css  # noqa: E402
from adapters.visualization.data_loader import (  # noqa: E402
    load_scan_timestamp,
    load_spy_sparkline,
)

inject_global_css()

# ── Freshness header bar ──────────────────────────────────────────────────────
_now = datetime.datetime.now()
_market_open = _now.hour > 9 or (_now.hour == 9 and _now.minute >= 30)
_market_closed = _now.hour >= 16
_market_status = "OPEN" if (_market_open and not _market_closed) else "CLOSED"
_market_color = "#16A34A" if _market_status == "OPEN" else "#DC2626"

_scan_ts = load_scan_timestamp("data/reports")
_scan_label = f"Last scan: {_scan_ts}" if _scan_ts else "Last scan: No reports yet"

_spy = load_spy_sparkline()
if _spy:
    _spy_price = f"${_spy['current']:.2f}"
    _spy_change = _spy["change_pct"]
    _spy_sign = "+" if _spy_change >= 0 else ""
    _spy_color = "#16A34A" if _spy_change >= 0 else "#DC2626"
    _spy_label = (
        f'<span style="color:{_spy_color};">'
        f"S&amp;P 500: {_spy_price} {_spy_sign}{_spy_change:.2f}%"
        f"</span>"
    )
else:
    _spy_label = '<span style="color:#6B7280;">S&amp;P 500: unavailable</span>'

st.markdown(
    '<h1 style="margin-bottom: 0;">Multi-Modal Stock Recommender</h1>'
    f'<p style="color: #6B7280; font-size: 14px; margin-top: 4px;">'
    f"{_scan_label} &nbsp;&middot;&nbsp; "
    f'Market: <span style="color:{_market_color}; font-weight:600;">{_market_status}</span>'
    f" &nbsp;&middot;&nbsp; {_spy_label}"
    f"</p>",
    unsafe_allow_html=True,
)

# Tab router
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    [
        "🎯 Opportunity Feed",
        "📊 System Intelligence",
        "🔍 Signal Breakdown",
        "💼 Outcome Tracker",
        "🚀 Opportunities",
        "🌍 Market Pulse",
    ]
)

with tab1:
    from adapters.visualization.tabs.command_center import render as render_cc

    render_cc()

with tab2:
    from adapters.visualization.tabs.model_confidence import render as render_mc

    render_mc()

with tab3:
    from adapters.visualization.tabs.signal_breakdown import render as render_sb

    render_sb()

with tab4:
    from adapters.visualization.tabs.positions import render as render_pos

    render_pos()

with tab5:
    from adapters.visualization.tabs.opportunities import render as render_opp

    render_opp()

with tab6:
    from adapters.visualization.tabs.market_pulse import render as render_mp

    render_mp()

# Footer
st.markdown(
    '<div class="dashboard-footer">'
    "Multi-Modal Stock Recommender · Hexagonal Architecture · Built by Tirth Joshi"
    "</div>",
    unsafe_allow_html=True,
)
