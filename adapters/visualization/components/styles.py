"""Global CSS styles for dashboard — injected once in dashboard.py."""

from __future__ import annotations

GLOBAL_CSS = """
<style>
/* ===== Fonts ===== */
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

/* ===== CSS Variables ===== */
:root {
    --bg-primary: #FFFFFF;
    --bg-secondary: #F8FAFC;
    --border: #E2E8F0;
    --text-primary: #1A202C;
    --text-secondary: #64748B;
    --text-muted: #94A3B8;
    --accent: #2563EB;
    --accent-hover: #1D4ED8;
    --success: #16A34A;
    --warning: #D97706;
    --danger: #DC2626;
    --purple: #7C3AED;
    --orange: #EA580C;
    --shadow-sm: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
    --shadow-md: 0 4px 12px rgba(0,0,0,0.08), 0 2px 4px rgba(0,0,0,0.04);
    --radius-sm: 8px;
    --radius-md: 12px;
    --radius-lg: 16px;
    --radius-xl: 20px;
}

/* ===== Base Typography ===== */
html, body, [class*="css"] {
    font-size: 15px;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    color: var(--text-primary);
    background-color: var(--bg-primary);
    -webkit-font-smoothing: antialiased;
}
h1 {
    font-family: 'DM Sans', sans-serif !important;
    font-size: 28px !important;
    font-weight: 700 !important;
    color: var(--text-primary) !important;
    letter-spacing: -0.5px !important;
}
h2 {
    font-family: 'DM Sans', sans-serif !important;
    font-size: 20px !important;
    font-weight: 600 !important;
    color: var(--text-primary) !important;
    letter-spacing: -0.3px !important;
}
h3 {
    font-family: 'DM Sans', sans-serif !important;
    font-size: 16px !important;
    font-weight: 600 !important;
    color: var(--text-primary) !important;
}
h4 {
    font-family: 'DM Sans', sans-serif !important;
    font-size: 14px !important;
    font-weight: 600 !important;
    color: var(--text-secondary) !important;
    text-transform: uppercase !important;
    letter-spacing: 0.5px !important;
}

/* ===== Hide Streamlit Chrome ===== */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header [data-testid="stToolbar"] { visibility: hidden; }
[data-testid="stDecoration"] { display: none; }

/* ===== Tab Styling ===== */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    padding: 4px;
    border: none;
}
.stTabs [data-baseweb="tab-list"] button {
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 500 !important;
    font-size: 14px !important;
    color: var(--text-secondary) !important;
    border-radius: var(--radius-sm) !important;
    border: none !important;
    background: transparent !important;
    padding: 8px 16px !important;
    transition: color 0.15s ease, background 0.15s ease !important;
}
.stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
    color: var(--accent) !important;
    background: var(--bg-primary) !important;
    box-shadow: var(--shadow-sm) !important;
    border-bottom: 2px solid var(--accent) !important;
}
.stTabs [data-baseweb="tab-list"] button:hover:not([aria-selected="true"]) {
    color: var(--text-primary) !important;
    background: rgba(37,99,235,0.05) !important;
}

/* ===== ws-card — Primary Card Component ===== */
.ws-card {
    background: var(--bg-primary);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 1.5rem;
    margin-bottom: 1rem;
    box-shadow: var(--shadow-sm);
    transition: transform 0.18s ease, box-shadow 0.18s ease;
}
.ws-card:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
}

/* ===== Hero Panel ===== */
.hero-panel {
    background: var(--bg-primary);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 2rem;
    margin-bottom: 1.5rem;
    box-shadow: var(--shadow-sm);
    min-height: 180px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    transition: transform 0.18s ease, box-shadow 0.18s ease;
}
.hero-panel:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
}

/* ===== Opportunity Cards ===== */
.opp-card {
    background: var(--bg-primary);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 1.25rem 1.5rem;
    margin-bottom: 0.75rem;
    box-shadow: var(--shadow-sm);
    transition: transform 0.18s ease, box-shadow 0.18s ease;
    border-left: 4px solid var(--border);
}
.opp-card:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
}
.opp-card-high {
    border-left-color: var(--success);
}
.opp-card-mid {
    border-left-color: var(--warning);
}
.opp-card-low {
    border-left-color: var(--text-muted);
}

/* ===== Conviction Bar ===== */
.conviction-bar {
    background: var(--bg-secondary);
    border-radius: 999px;
    height: 6px;
    width: 100%;
    margin-top: 6px;
    overflow: hidden;
}
.conviction-bar-fill {
    height: 6px;
    border-radius: 999px;
    background: linear-gradient(90deg, var(--accent) 0%, #7C3AED 100%);
    transition: width 0.4s ease;
}

/* ===== Learning Progress ===== */
.learning-progress {
    background: var(--bg-secondary);
    border-radius: 999px;
    height: 10px;
    width: 100%;
    overflow: hidden;
}
.learning-progress-fill {
    height: 10px;
    border-radius: 999px;
    background: linear-gradient(90deg, var(--accent) 0%, #7C3AED 100%);
    transition: width 0.5s cubic-bezier(0.4, 0, 0.2, 1);
}

/* ===== Badges ===== */
.badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 600;
    font-family: 'DM Sans', sans-serif;
    letter-spacing: 0.2px;
    line-height: 1.6;
}
.badge-buy {
    background: #DCFCE7;
    color: #166534;
}
.badge-sell {
    background: #FEE2E2;
    color: #991B1B;
}
.badge-watch {
    background: #FEF3C7;
    color: #92400E;
}
.badge-hold {
    background: var(--bg-secondary);
    color: var(--text-secondary);
    border: 1px solid var(--border);
}

/* ===== Freshness Badges ===== */
.badge-fresh {
    background: #DCFCE7;
    color: #166534;
}
.badge-recent {
    background: #FEF3C7;
    color: #92400E;
}
.badge-stale {
    background: #FEE2E2;
    color: #991B1B;
}

/* ===== Onboarding Card ===== */
.onboarding-card {
    background: linear-gradient(135deg, #EFF6FF 0%, #F5F3FF 100%);
    border: 1px solid #C7D2FE;
    border-radius: var(--radius-xl);
    padding: 2.5rem;
    text-align: center;
    max-width: 600px;
    margin: 2rem auto;
}

/* ===== Onboarding Steps ===== */
.onboarding-step {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    margin-bottom: 1rem;
    text-align: left;
}
.onboarding-num {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: var(--accent);
    color: #FFFFFF;
    font-family: 'DM Sans', sans-serif;
    font-size: 13px;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}

/* ===== Status Dots ===== */
.status-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 6px;
    vertical-align: middle;
    flex-shrink: 0;
}
.status-green {
    background: var(--success);
    box-shadow: 0 0 0 2px rgba(22,163,74,0.2);
}
.status-amber {
    background: var(--warning);
    box-shadow: 0 0 0 2px rgba(217,119,6,0.2);
}
.status-red {
    background: var(--danger);
    box-shadow: 0 0 0 2px rgba(220,38,38,0.2);
}

/* ===== Footer ===== */
.ws-footer {
    text-align: center;
    color: var(--text-muted);
    font-size: 12px;
    padding: 2rem 0 1rem 0;
    border-top: 1px solid var(--border);
    margin-top: 3rem;
    font-family: 'Inter', sans-serif;
}

/* ===== Skeleton Shimmer ===== */
@keyframes shimmer {
    0% { background-position: -400px 0; }
    100% { background-position: 400px 0; }
}
.skeleton {
    background: linear-gradient(90deg, var(--bg-secondary) 25%, #EDF2F7 50%, var(--bg-secondary) 75%);
    background-size: 800px 100%;
    animation: shimmer 1.4s infinite linear;
    border-radius: var(--radius-sm);
}

/* ===== Button Overrides ===== */
.stButton > button {
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 600 !important;
    border-radius: 10px !important;
    transition: transform 0.12s ease, box-shadow 0.12s ease, background-color 0.15s ease !important;
}
.stButton > button[kind="primary"] {
    background-color: var(--accent) !important;
    border: none !important;
    color: #FFFFFF !important;
    padding: 10px 22px !important;
    box-shadow: 0 1px 3px rgba(37,99,235,0.3) !important;
}
.stButton > button[kind="primary"]:hover {
    background-color: var(--accent-hover) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 12px rgba(37,99,235,0.35) !important;
}
.stButton > button[kind="secondary"] {
    background-color: var(--bg-primary) !important;
    border: 1px solid var(--border) !important;
    color: var(--text-primary) !important;
    padding: 10px 22px !important;
}
.stButton > button[kind="secondary"]:hover {
    background-color: var(--bg-secondary) !important;
    transform: translateY(-1px) !important;
    box-shadow: var(--shadow-sm) !important;
}

/* ===== Expander Styling ===== */
.streamlit-expanderHeader {
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    color: var(--text-primary) !important;
    border-radius: var(--radius-sm) !important;
}
.streamlit-expanderHeader:hover {
    background-color: var(--bg-secondary) !important;
}

/* ===== Form Inputs ===== */
.stTextInput input, .stNumberInput input, .stSelectbox select {
    border-radius: var(--radius-sm) !important;
    border-color: var(--border) !important;
    color: var(--text-primary) !important;
    font-family: 'Inter', sans-serif !important;
}
.stTextInput input:focus, .stNumberInput input:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px rgba(37,99,235,0.15) !important;
}

/* ===== Numeric Values ===== */
.metric-value {
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-weight: 500;
    font-size: 22px;
    color: var(--text-primary);
    letter-spacing: -0.5px;
}
.metric-label {
    font-family: 'DM Sans', sans-serif;
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.6px;
}

/* ===== Layer Cards ===== */
.layer-card {
    background: var(--bg-primary);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: 1.25rem;
    margin-bottom: 0.75rem;
    min-height: 140px;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.layer-card:hover {
    transform: translateY(-1px);
    box-shadow: var(--shadow-md);
}
.layer-technical  { border-top: 3px solid var(--accent); }
.layer-sentiment  { border-top: 3px solid var(--purple); }
.layer-fundamental { border-top: 3px solid var(--success); }
.layer-cross-asset { border-top: 3px solid var(--orange); }
.layer-event-causal { border-top: 3px solid var(--danger); }

/* ===== Confidence Bar (legacy compat) ===== */
.confidence-bar-bg {
    background: var(--bg-secondary);
    border-radius: 999px;
    height: 8px;
    width: 100%;
    margin-top: 4px;
    overflow: hidden;
}
.confidence-bar-fill {
    height: 8px;
    border-radius: 999px;
}

/* ===== Inline Context ===== */
.inline-context {
    font-size: 14px;
    color: var(--text-secondary);
    margin-top: -8px;
    margin-bottom: 16px;
    line-height: 1.6;
}

/* ===== Table ===== */
.stDataFrame tbody tr:hover {
    background-color: var(--bg-secondary) !important;
}

/* ===== Limitation Card ===== */
.limitation-card {
    background: #FFFBEB;
    border: 1px solid #FDE68A;
    border-left: 4px solid var(--warning);
    border-radius: var(--radius-sm);
    padding: 1rem;
    font-size: 14px;
    color: #92400E;
}

/* ===== Section Spacing ===== */
.block-container {
    padding-left: 1rem !important;
    padding-right: 1rem !important;
}

/* ===== Legacy Grade Badges (backward compat) ===== */
.grade-badge {
    display: inline-block;
    padding: 3px 12px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 700;
    font-family: 'DM Sans', sans-serif;
    text-transform: uppercase;
    letter-spacing: 0.4px;
}
.grade-strong-buy   { background: #DCFCE7; color: #166534; }
.grade-buy          { background: #D1FAE5; color: #065F46; }
.grade-hold         { background: #FEF9C3; color: #854D0E; }
.grade-may-sell     { background: #FFEDD5; color: #9A3412; }
.grade-immediate-sell { background: #FEE2E2; color: #991B1B; }

/* ===== Legacy Status Pills (backward compat) ===== */
.status-pill {
    display: inline-block;
    padding: 3px 12px;
    border-radius: 999px;
    font-size: 13px;
    font-weight: 600;
    font-family: 'DM Sans', sans-serif;
    letter-spacing: 0.2px;
}
.pill-fresh        { background: #DCFCE7; color: #166534; }
.pill-stale        { background: #FEF9C3; color: #854D0E; }
.pill-warning      { background: #FFEDD5; color: #9A3412; }
.pill-critical     { background: #FEE2E2; color: #991B1B; }
.pill-urgent       { background: #FEE2E2; color: #991B1B; }
.pill-this-week    { background: #FEF9C3; color: #854D0E; }
.pill-watch-priority { background: var(--bg-secondary); color: var(--text-secondary); }

/* ===== Legacy Signal Pills (backward compat) ===== */
.signal-pill {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 600;
    font-family: 'DM Sans', sans-serif;
}
.signal-bullish { background: #DCFCE7; color: #166534; }
.signal-bearish { background: #FEE2E2; color: #991B1B; }
.signal-neutral { background: var(--bg-secondary); color: var(--text-secondary); }

/* ===== Legacy Freshness Dots (backward compat) ===== */
.freshness-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 6px;
    vertical-align: middle;
}
.dot-fresh    { background: var(--success); }
.dot-stale    { background: var(--warning); }
.dot-warning  { background: var(--orange); }
.dot-critical { background: var(--danger); }

/* ===== SHAP Legend Dots ===== */
.shap-legend-dot {
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    margin-right: 4px;
    vertical-align: middle;
}

/* ===== Dashboard Footer (legacy compat) ===== */
.dashboard-footer {
    text-align: center;
    color: var(--text-muted);
    font-size: 12px;
    padding: 2rem 0 1rem 0;
    border-top: 1px solid var(--border);
    margin-top: 3rem;
}

/* ===== Phase 5.4 — Missing CSS fixes ===== */
.hero-label {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-muted);
    font-weight: 500;
}
.hero-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 22px;
    font-weight: 600;
    color: var(--text-primary);
    margin-top: 4px;
}
.hero-sub {
    font-size: 13px;
    color: var(--text-secondary);
    margin-top: 2px;
}
.verdict-card {
    padding: 16px 20px;
    border-radius: var(--radius-md);
    border: 1px solid var(--border);
    margin: 12px 0;
}
.verdict-positive { border-left: 4px solid var(--success); }
.verdict-negative { border-left: 4px solid var(--danger); }
.verdict-neutral { border-left: 4px solid var(--accent); }
.dashboard-card {
    background: var(--bg-primary);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: 16px;
    margin-bottom: 12px;
    box-shadow: var(--shadow-sm);
}
.ticker-bar {
    display: flex;
    align-items: center;
    gap: 24px;
    padding: 8px 16px;
    background: #0F172A;
    color: white;
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    overflow: hidden;
    white-space: nowrap;
    border-radius: var(--radius-sm);
    margin-bottom: 8px;
}
.ticker-bar-item { display: inline-flex; align-items: center; gap: 6px; }
.ticker-bar-up { color: #4ADE80; }
.ticker-bar-down { color: #F87171; }
</style>
"""


def inject_global_css() -> None:
    """Inject global CSS into the Streamlit page. Call once in dashboard.py."""
    import streamlit as st

    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
