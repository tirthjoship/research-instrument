"""Global CSS styles for dashboard — injected once in dashboard.py."""

from __future__ import annotations

GLOBAL_CSS = """
<style>
/* ===== Inter Font ===== */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-size: 15px;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    color: #374151;
}
h1 { font-size: 28px !important; font-weight: 600 !important; color: #111827 !important; }
h2 { font-size: 20px !important; font-weight: 600 !important; color: #111827 !important; }
h3 { font-size: 16px !important; font-weight: 600 !important; color: #374151 !important; }
h4 { font-size: 15px !important; font-weight: 600 !important; color: #374151 !important; }

/* ===== Hide Streamlit chrome ===== */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header [data-testid="stToolbar"] {visibility: hidden;}

/* ===== Tab styling ===== */
.stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
    border-bottom-color: #2563EB !important;
}

/* ===== Card containers ===== */
.dashboard-card {
    background: white;
    border: 1px solid #E5E7EB;
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.dashboard-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
.card-buy { border-left: 4px solid #059669; }
.card-sell { border-left: 4px solid #DC2626; }
.card-watch { border-left: 4px solid #D97706; }
.card-info { border-left: 4px solid #2563EB; }

/* ===== Hero card ===== */
.hero-card {
    background: white;
    border: 1px solid #E5E7EB;
    border-left: 4px solid #2563EB;
    border-radius: 12px;
    padding: 2rem;
    margin-bottom: 1.5rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}

/* ===== Verdict card ===== */
.verdict-card {
    background: white;
    border: 1px solid #E5E7EB;
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
}
.verdict-positive { background: #F0FDF4; border: 1px solid #BBF7D0; }
.verdict-negative { background: #FEF2F2; border: 1px solid #FECACA; }
.verdict-neutral { background: #F9FAFB; border: 1px solid #E5E7EB; }

/* ===== Status pills (no emoji) ===== */
.status-pill {
    display: inline-block;
    padding: 3px 12px;
    border-radius: 12px;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.3px;
}
.pill-fresh { background: #DCFCE7; color: #166534; }
.pill-stale { background: #FEF9C3; color: #854D0E; }
.pill-warning { background: #FFEDD5; color: #9A3412; }
.pill-critical { background: #FEE2E2; color: #991B1B; }
.pill-urgent { background: #FEE2E2; color: #991B1B; }
.pill-this-week { background: #FEF9C3; color: #854D0E; }
.pill-watch-priority { background: #F3F4F6; color: #4B5563; }

/* ===== Grade badges ===== */
.grade-badge {
    display: inline-block;
    padding: 3px 12px;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.grade-strong-buy { background: #DCFCE7; color: #166534; }
.grade-buy { background: #D1FAE5; color: #065F46; }
.grade-hold { background: #FEF9C3; color: #854D0E; }
.grade-may-sell { background: #FFEDD5; color: #9A3412; }
.grade-immediate-sell { background: #FEE2E2; color: #991B1B; }

/* ===== Signal pills ===== */
.signal-pill {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 10px;
    font-size: 12px;
    font-weight: 600;
}
.signal-bullish { background: #DCFCE7; color: #166534; }
.signal-bearish { background: #FEE2E2; color: #991B1B; }
.signal-neutral { background: #F3F4F6; color: #4B5563; }

/* ===== Freshness dots ===== */
.freshness-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 6px;
    vertical-align: middle;
}
.dot-fresh { background: #059669; }
.dot-stale { background: #D97706; }
.dot-warning { background: #EA580C; }
.dot-critical { background: #DC2626; }

/* ===== Layer cards ===== */
.layer-card {
    background: white;
    border: 1px solid #E5E7EB;
    border-radius: 10px;
    padding: 1.25rem;
    margin-bottom: 0.75rem;
    min-height: 140px;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.layer-card:hover {
    transform: translateY(-1px);
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}
.layer-technical { border-top: 3px solid #2563EB; }
.layer-sentiment { border-top: 3px solid #7C3AED; }
.layer-fundamental { border-top: 3px solid #059669; }
.layer-cross-asset { border-top: 3px solid #EA580C; }
.layer-event-causal { border-top: 3px solid #DC2626; }

/* ===== SHAP legend dots ===== */
.shap-legend-dot {
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    margin-right: 4px;
    vertical-align: middle;
}

/* ===== Confidence bar ===== */
.confidence-bar-bg {
    background: #F3F4F6;
    border-radius: 4px;
    height: 8px;
    width: 100%;
    margin-top: 4px;
}
.confidence-bar-fill {
    height: 8px;
    border-radius: 4px;
}

/* ===== Inline context (replaces section-subtitle) ===== */
.inline-context {
    font-size: 14px;
    color: #6B7280;
    margin-top: -8px;
    margin-bottom: 16px;
    line-height: 1.5;
}

/* ===== Table styling ===== */
.stDataFrame tbody tr:hover {
    background-color: #F8FAFC !important;
}

/* ===== Limitation card ===== */
.limitation-card {
    background: #FFFBEB;
    border: 1px solid #FDE68A;
    border-left: 4px solid #D97706;
    border-radius: 8px;
    padding: 1rem;
    font-size: 14px;
    color: #92400E;
}

/* ===== Buttons ===== */
.stButton > button[kind="primary"] {
    background-color: #2563EB !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 12px 24px !important;
    font-weight: 600 !important;
    transition: transform 0.1s ease, background-color 0.15s ease !important;
}
.stButton > button[kind="primary"]:hover {
    background-color: #1D4ED8 !important;
    transform: scale(1.02) !important;
}

/* ===== Form inputs ===== */
.stTextInput input, .stNumberInput input {
    border-radius: 8px !important;
}
.stTextInput input:focus, .stNumberInput input:focus {
    border-color: #2563EB !important;
    box-shadow: 0 0 0 2px rgba(37,99,235,0.2) !important;
}

/* ===== Section spacing ===== */
.block-container {
    padding-left: 1rem !important;
    padding-right: 1rem !important;
}

/* ===== Opportunity cards ===== */
.opportunity-card { transition: transform 0.15s ease, box-shadow 0.15s ease; }
.opportunity-card:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.08); }

/* ===== Footer ===== */
.dashboard-footer {
    text-align: center;
    color: #D1D5DB;
    font-size: 12px;
    padding: 2rem 0 1rem 0;
    border-top: 1px solid #F3F4F6;
    margin-top: 3rem;
}
</style>
"""


def inject_global_css() -> None:
    """Inject global CSS into the Streamlit page. Call once in dashboard.py."""
    import streamlit as st

    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
