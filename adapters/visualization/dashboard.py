"""Dashboard entry point — 6-tab honest cockpit."""

from __future__ import annotations

# Load project-root .env (GEMINI_API_KEY etc.) before any other import reads env.
from application.dotenv_loader import load_dotenv

load_dotenv()

import streamlit as st  # noqa: E402

st.set_page_config(
    page_title="Market Research Instrument",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="collapsed",
)

import os  # noqa: E402

from application.access_gate import (  # noqa: E402
    check_password,
    is_access_gate_required,
)


def _render_access_gate() -> bool:
    """Whole-app password gate — bounds the public Cloud deploy's quota/rate-
    limit exposure to invited friends, not arbitrary internet visitors.
    Bypassed automatically for local/operator use (is_access_gate_required()
    wraps is_local_runtime()). Returns whether the rest of the app may render.
    """
    if not is_access_gate_required():
        return True
    if st.session_state.get("_access_granted"):
        return True

    entered = st.text_input("Password", type="password", key="_access_gate_password")
    if st.button("Enter", key="_access_gate_submit"):
        if check_password(entered, os.environ.get("APP_PASSWORD")):
            st.session_state["_access_granted"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    return False


if not _render_access_gate():
    st.stop()

from adapters.visualization.components.styles import inject_global_css  # noqa: E402

inject_global_css()

# fmt: off
_APP_TITLE_HTML = (
    "<div style=\"margin:0 0 2px 0;\">"
    "<h1 class='ri-app-title' style=\"font-family:'Fraunces',Georgia,serif !important;font-weight:600 !important;font-size:30px !important;letter-spacing:-0.01em !important;color:#14181F !important;margin:0 0 2px 0 !important;line-height:1.1 !important;\">Market Research Instrument</h1>"  # noqa: E501
    "<p class='ri-app-sub'>Evidence-based equity research instrument &mdash; attribution, not forecast</p>"  # noqa: E501
    "</div>"
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
)

from adapters.visualization.components.tab_loading import (  # noqa: E402
    render_tab_loading,
)

render_tab_loading(TAB_LABELS)

if tabs[0].open:
    with tabs[0]:
        from adapters.visualization.tabs.weekly_brief import render as render_brief

        render_brief()
if tabs[1].open:
    with tabs[1]:
        from adapters.visualization.tabs.research_candidates import (
            render as render_candidates,
        )

        render_candidates()
if tabs[2].open:
    with tabs[2]:
        from adapters.visualization.tabs.risk import render as render_risk

        render_risk()
if tabs[3].open:
    with tabs[3]:
        from adapters.visualization.tabs.positions import render as render_portfolio

        render_portfolio()
if tabs[4].open:
    with tabs[4]:
        from adapters.visualization.tabs.stock_analysis import render as render_analysis

        render_analysis()
if tabs[5].open:
    with tabs[5]:
        from adapters.visualization.tabs.trust import render as render_trust

        render_trust()

st.markdown(
    '<div class="ws-footer">Market Research Instrument · Hexagonal Architecture · Built by Tirth Joshi</div>',
    unsafe_allow_html=True,
)
