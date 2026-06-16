"""Dashboard entry point — 6-tab honest cockpit."""

from __future__ import annotations

import os as _os
from pathlib import Path as _Path


def _load_dotenv() -> None:
    """Minimal .env loader (no python-dotenv dependency) so keys like
    GEMINI_API_KEY in the project-root .env reach the app. Never overrides a
    var already set in the real environment; fails silent on any error."""
    try:
        env_path = _Path(__file__).resolve().parents[2] / ".env"
        if not env_path.exists():
            return
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in _os.environ:
                _os.environ[key] = val
    except Exception:  # noqa: BLE001 — env loading must never crash the app
        pass


_load_dotenv()

import streamlit as st  # noqa: E402

st.set_page_config(
    page_title="Stock Intelligence",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="collapsed",
)

from adapters.visualization.components.styles import inject_global_css  # noqa: E402

inject_global_css()

# fmt: off
_APP_TITLE_HTML = (
    "<h1 class='ri-app-title' style=\"font-family:'Fraunces',Georgia,serif !important;font-weight:600 !important;font-size:32px !important;letter-spacing:-0.01em !important;color:#14181F !important;margin-bottom:2px !important;\">Multi-Modal Stock Recommender</h1>"  # noqa: E501
    "<p style=\"font-family:'IBM Plex Sans',sans-serif;font-size:13px;color:#717885;margin:0 0 14px 0;letter-spacing:0.01em;\">Evidence-based equity research instrument &mdash; attribution, not forecast</p>"  # noqa: E501
)
# fmt: on
st.markdown(_APP_TITLE_HTML, unsafe_allow_html=True)

TAB_LABELS = [
    "Loading your book",
    "Building this week's research shortlist",
    "Computing portfolio risk",
    "Loading your portfolio",
    "Loading stock analysis",
    "Loading the track record",
]

tabs = st.tabs(
    ["Home", "Screener", "Risk", "My Portfolio", "Stock Analysis", "Trust"],
    on_change="rerun",
    key="main_tabs",
)

from adapters.visualization.components.tab_loading import (  # noqa: E402
    render_tab_loading,
)

render_tab_loading(TAB_LABELS)


def _refresh_button(slot_key: str) -> None:
    """Right-aligned per-tab refresh: clears cached fetches and reruns."""
    _, right = st.columns([6, 1])
    with right:
        if st.button("↻ refresh", key=f"refresh_{slot_key}"):
            st.cache_data.clear()
            st.rerun()


if tabs[0].open:
    with tabs[0]:
        from adapters.visualization.tabs.weekly_brief import render as render_brief

        _refresh_button("home")
        render_brief()
if tabs[1].open:
    with tabs[1]:
        from adapters.visualization.tabs.research_candidates import (
            render as render_candidates,
        )

        _refresh_button("screener")
        render_candidates()
if tabs[2].open:
    with tabs[2]:
        from adapters.visualization.tabs.risk import render as render_risk

        _refresh_button("risk")
        render_risk()
if tabs[3].open:
    with tabs[3]:
        from adapters.visualization.tabs.positions import render as render_portfolio

        _refresh_button("portfolio")
        render_portfolio()
if tabs[4].open:
    with tabs[4]:
        from adapters.visualization.tabs.stock_analysis import render as render_analysis

        _refresh_button("analysis")
        render_analysis()
if tabs[5].open:
    with tabs[5]:
        from adapters.visualization.tabs.trust import render as render_trust

        _refresh_button("trust")
        render_trust()

st.markdown(
    '<div class="ws-footer">Multi-Modal Stock Recommender · Hexagonal Architecture · Built by Tirth Joshi</div>',
    unsafe_allow_html=True,
)
