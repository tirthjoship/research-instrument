"""Global CSS styles for dashboard — injected once in dashboard.py."""

from __future__ import annotations

GLOBAL_CSS = """
<style>
/* ===== Typography ===== */
html, body, [class*="css"] {
    font-size: 16px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}
h1 { font-size: 28px !important; font-weight: 700 !important; color: #1A1A2E !important; }
h2 { font-size: 22px !important; font-weight: 600 !important; color: #1A1A2E !important; }
h3 { font-size: 18px !important; font-weight: 600 !important; color: #1A1A2E !important; }

/* ===== Hide Streamlit chrome ===== */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header [data-testid="stToolbar"] {visibility: hidden;}

/* ===== Card containers ===== */
.dashboard-card {
    background: white;
    border: 1px solid #E8EBF0;
    border-radius: 12px;
    padding: 1.25rem;
    margin-bottom: 1rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    transition: box-shadow 0.2s ease;
}
.dashboard-card:hover {
    box-shadow: 0 2px 8px rgba(0,0,0,0.12);
}
.card-buy { border-left: 4px solid #00C853; }
.card-sell { border-left: 4px solid #FF1744; }
.card-watch { border-left: 4px solid #FFD600; }
.card-info { border-left: 4px solid #2979FF; }

/* ===== Status pills ===== */
.status-pill {
    display: inline-block;
    padding: 3px 12px;
    border-radius: 12px;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.3px;
}
.pill-fresh { background: #E8F5E9; color: #2E7D32; }
.pill-stale { background: #FFF8E1; color: #F57F17; }
.pill-warning { background: #FFF3E0; color: #E65100; }
.pill-critical { background: #FFEBEE; color: #C62828; }

/* ===== Grade badges ===== */
.grade-badge {
    display: inline-block;
    padding: 3px 12px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.grade-strong-buy { background: #E8F5E9; color: #1B5E20; }
.grade-buy { background: #F1F8E9; color: #33691E; }
.grade-hold { background: #FFFDE7; color: #F57F17; }
.grade-may-sell { background: #FFF3E0; color: #E65100; }
.grade-immediate-sell { background: #FFEBEE; color: #B71C1C; }

/* ===== Signal pills ===== */
.signal-pill {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 10px;
    font-size: 12px;
    font-weight: 600;
}
.signal-bullish { background: #E8F5E9; color: #2E7D32; }
.signal-bearish { background: #FFEBEE; color: #C62828; }
.signal-neutral { background: #F5F5F5; color: #616161; }

/* ===== Layer cards ===== */
.layer-card {
    background: white;
    border: 1px solid #E8EBF0;
    border-radius: 10px;
    padding: 1rem;
    margin-bottom: 0.75rem;
    min-height: 140px;
}
.layer-technical { border-top: 3px solid #2979FF; }
.layer-sentiment { border-top: 3px solid #7C4DFF; }
.layer-fundamental { border-top: 3px solid #00C853; }
.layer-cross-asset { border-top: 3px solid #FF9100; }
.layer-event-causal { border-top: 3px solid #FF1744; }

/* ===== Confidence bar ===== */
.confidence-bar-bg {
    background: #F0F0F0;
    border-radius: 4px;
    height: 8px;
    width: 100%;
    margin-top: 4px;
}
.confidence-bar-fill {
    height: 8px;
    border-radius: 4px;
}

/* ===== Section subtitle ===== */
.section-subtitle {
    font-size: 14px;
    color: #9E9E9E;
    font-style: italic;
    margin-top: -10px;
    margin-bottom: 16px;
}

/* ===== Table styling ===== */
.stDataFrame tbody tr:nth-child(even) {
    background-color: #FAFBFC;
}

/* ===== Limitation card ===== */
.limitation-card {
    background: #FFFDE7;
    border: 1px solid #FFF9C4;
    border-left: 4px solid #FFD600;
    border-radius: 8px;
    padding: 1rem;
    font-size: 14px;
    color: #5D4037;
}
</style>
"""


def inject_global_css() -> None:
    """Inject global CSS into the Streamlit page. Call once in dashboard.py."""
    import streamlit as st

    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
