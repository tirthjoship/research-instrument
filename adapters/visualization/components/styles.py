"""Global CSS styles for dashboard — injected once in dashboard.py."""

from __future__ import annotations

GLOBAL_CSS = """
<style>
/* ===== Fonts ===== */
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700&family=Newsreader:opsz,wght@6..72,400;6..72,500;6..72,600&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

/* ===== CSS Variables ===== */
:root {
    --bg-page: #FAFAF8;
    --bg-primary: #FFFFFF;
    --bg-secondary: #F8FAFC;
    --border: #E2E8F0;
    --text-primary: #1A1D27;
    --text-secondary: #5C6370;
    --text-muted: #94A3B8;
    --accent: #1D4ED8;
    --accent-hover: #1E40AF;
    --success: #15803D;
    --warning: #B45309;
    --danger: #B91C1C;
    --purple: #7C3AED;
    --orange: #EA580C;
    --shadow-sm: 0 1px 2px rgba(16,24,40,.06), 0 4px 12px rgba(16,24,40,.04);
    --shadow-md: 0 4px 12px rgba(0,0,0,0.08), 0 2px 4px rgba(0,0,0,0.04);
    --radius-sm: 8px;
    --radius-md: 12px;
    --radius-lg: 12px;
    --radius-xl: 20px;
}

/* ===== Base Typography ===== */
html, body, [class*="css"] {
    font-size: 16px;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    color: var(--text-primary);
    background-color: var(--bg-primary);
    -webkit-font-smoothing: antialiased;
    scroll-behavior: smooth;
}
h1 {
    font-family: 'DM Sans', sans-serif !important;
    font-size: 28px !important;
    font-weight: 700 !important;
    color: var(--text-primary) !important;
    letter-spacing: -0.5px !important;
}

/* ===== App-level title — Fraunces display override (beats h1 DM Sans rule) ===== */
.ri-app-title {
    font-family: 'Fraunces', Georgia, serif !important;
    font-weight: 600 !important;
    font-size: 30px !important;
    letter-spacing: -0.01em !important;
    color: #14181F !important;
    line-height: 1.0 !important;
    margin-bottom: 2px !important;
    margin-top: 0 !important;
    padding-top: 0 !important;
    padding-bottom: 0 !important;
}
/* Streamlit wraps a raw <h1> in a heading container with its own top padding;
   zero it so the title sits at the very top and the subtitle hugs it. */
[data-testid="stHeadingWithActionElements"]:has(.ri-app-title) {
    padding-top: 0 !important;
    margin-top: 0 !important;
}
[data-testid="stHeadingWithActionElements"]:has(.ri-app-title) [data-testid="stHeaderActionElements"] {
    display: none !important;
}
/* App subtitle — Newsreader, tight under the title (matches approved mockup) */
.ri-app-sub {
    font-family: 'Newsreader', Georgia, serif !important;
    font-weight: 400 !important;
    font-size: 14px !important;
    color: #717885 !important;
    line-height: 1.3 !important;
    margin: -12px 0 14px 0 !important;
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

/* ===== Page Background + Tabular Numerals ===== */
.stApp { background: var(--bg-page); }
[data-testid="stMetricValue"], .ws-card, .verdict-card, table {
    font-variant-numeric: tabular-nums;
}

/* ===== Hide Streamlit Chrome ===== */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header [data-testid="stToolbar"] { visibility: hidden; }
[data-testid="stDecoration"] { display: none; }
header[data-testid="stHeader"] { display: none !important; }

/* ===== Tab Styling ===== */
.stTabs [data-baseweb="tab-list"] {
    gap: 26px;
    background: transparent;
    border: none;
    border-bottom: 1px solid var(--border);
    border-radius: 0;
    padding: 0;
}
/* Neutralise baseweb's sliding highlight/border bar so only our flat underline shows */
.stTabs [data-baseweb="tab-highlight"],
.stTabs [data-baseweb="tab-border"] {
    display: none !important;
}
.stTabs [data-baseweb="tab-list"] button {
    font-family: 'Fraunces', Georgia, serif !important;
    font-weight: 500 !important;
    font-size: 15px !important;
    color: #717885 !important;
    border: none !important;
    border-radius: 0 !important;
    background: transparent !important;
    box-shadow: none !important;
    padding: 10px 2px !important;
    transition: color 0.15s ease !important;
}
.stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
    color: #14181F !important;
    font-weight: 600 !important;
    background: transparent !important;
    box-shadow: none !important;
    border-bottom: 2px solid #14181F !important;
}
/* The tab LABEL text lives in a nested <p> (stMarkdownContainer) whose default
   Source Sans wins over the button's font — restyle the <p> itself to Fraunces. */
.stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
    font-family: 'Fraunces', Georgia, serif !important;
    font-weight: 500 !important;
    font-size: 15px !important;
    color: inherit !important;
}
.stTabs [data-baseweb="tab-list"] button[aria-selected="true"] [data-testid="stMarkdownContainer"] p {
    font-weight: 600 !important;
}
.stTabs [data-baseweb="tab-list"] button:hover:not([aria-selected="true"]) {
    color: var(--text-primary) !important;
    background: transparent !important;
}

/* ===== ws-card — Primary Card Component ===== */
.ws-card {
    background: var(--bg-primary);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 1.5rem;
    margin-bottom: 1rem;
    box-shadow: var(--shadow-sm);
    transition: box-shadow .15s ease, border-color .15s ease,
                transform .15s ease;
}
.ws-card:hover {
    box-shadow: 0 2px 4px rgba(16,24,40,.08), 0 8px 24px rgba(16,24,40,.08);
    border-color: rgba(29,78,216,.35);
    transform: translateY(-1px);
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
    padding-top: 1rem !important;
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
.verdict-caution { border-left: 4px solid var(--warning, #CA8A04); }
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

/* ===== Tooltips ===== */
.tooltip-container {
    position: relative;
    display: inline-flex;
    align-items: center;
    cursor: help;
}
.tooltip-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: #E2E8F0;
    color: #64748B;
    font-size: 10px;
    font-weight: 700;
    margin-left: 4px;
    flex-shrink: 0;
}
.tooltip-container:hover .tooltip-text {
    visibility: visible;
    opacity: 1;
}
.tooltip-text {
    visibility: hidden;
    opacity: 0;
    position: absolute;
    bottom: 125%;
    left: 50%;
    transform: translateX(-50%);
    background: #1E293B;
    color: white;
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 12px;
    line-height: 1.4;
    white-space: normal;
    width: max-content;
    max-width: 280px;
    z-index: 1000;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    transition: opacity 0.2s;
}
.tooltip-text::after {
    content: "";
    position: absolute;
    top: 100%;
    left: 50%;
    margin-left: -5px;
    border-width: 5px;
    border-style: solid;
    border-color: #1E293B transparent transparent transparent;
}

/* ===== Section Chips ===== */
.section-chip {
    display: inline-flex; align-items: center; justify-content: center;
    width: 22px; height: 22px; border-radius: 50%;
    background: var(--accent); color: #fff;
    font-size: 12px; font-weight: 700; margin-right: 8px;
}

/* ===== Inline .tip Tooltips ===== */
.tip {
    border-bottom: 1px dotted var(--text-secondary);
    cursor: help; position: relative;
}
.tip:hover::after {
    content: attr(data-tip);
    position: absolute; left: 0; bottom: 125%;
    background: #1A1D27; color: #fff; padding: 8px 12px;
    border-radius: 8px; font-size: 12px; line-height: 1.4;
    width: 260px; z-index: 99; white-space: normal;
}

/* ===== Hero Gradient ===== */
.hero-gradient {
    background: linear-gradient(135deg, #FFFFFF 0%, #EEF2FF 100%);
}

/* ===== Research Instrument Design Tokens ===== */
:root{
  --ri-app:#F4F6F8; --ri-card:#FFFFFF; --ri-ink:#14181F; --ri-ink2:#3A4250; --ri-muted:#717885;
  --ri-line:#E3E7EC; --ri-hair:#EDF0F3; --ri-teal:#0F6E80;
  --ri-crimson:#CE2F26; --ri-amber:#C9810E; --ri-green:#1F9254;
}
#MainMenu,header[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stDecoration"]{display:none!important;}
html,body,[data-testid="stApp"],.stApp{background:radial-gradient(1100px 520px at 12% -8%,#FFF 0%,rgba(255,255,255,0) 55%),var(--ri-app)!important;}
[data-testid="stMainBlockContainer"],.block-container{max-width:1180px!important;margin-left:auto!important;margin-right:auto!important;padding:0.5rem 1.9rem 3rem!important;font-family:'IBM Plex Sans',sans-serif;color:var(--ri-ink);}
.ri-h1{font-family:'Fraunces',serif;font-weight:900;font-size:38px;line-height:1.04;letter-spacing:-.02em;color:var(--ri-ink);}.ri-h1 em{font-style:italic;font-weight:400;}
.ri-sub{font-family:'Fraunces',serif;font-style:italic;font-size:1.12rem;color:var(--ri-ink2);}
.ri-sec{font-family:'IBM Plex Mono',monospace;font-size:.72rem;letter-spacing:.2em;text-transform:uppercase;color:var(--ri-muted);display:flex;align-items:center;gap:.8rem;margin:.4rem 0 1rem;}
.ri-sec::after{content:"";flex:1;height:1px;background:var(--ri-hair);}
.ri-ttip{position:relative;cursor:help;border-bottom:1px dotted var(--ri-muted);}
.ri-tip{position:absolute;bottom:142%;left:50%;transform:translateX(-50%) translateY(5px);background:#1b2733;color:#eef3f6;font-family:'IBM Plex Sans';font-size:.76rem;line-height:1.45;padding:.65rem .8rem;border-radius:10px;width:240px;box-shadow:0 10px 30px rgba(15,30,45,.22);opacity:0;visibility:hidden;transition:.15s;z-index:60;text-align:left;}
.ri-tip::after{content:"";position:absolute;top:100%;left:50%;transform:translateX(-50%);border:6px solid transparent;border-top-color:#1b2733;}
.ri-ttip:hover .ri-tip{opacity:1;visibility:visible;transform:translateX(-50%) translateY(0);}
.ri-lens{transition:transform .15s;display:block;}
.ri-lens:hover{transform:translateY(-2px);}

/* ===== Research Instrument — Evidence Ledger ===== */
.ri-ledger{display:flex;align-items:center;flex-wrap:wrap;border-top:1.5px solid var(--ri-ink);border-bottom:1px solid var(--ri-hair);font-family:'IBM Plex Mono',monospace;font-size:.78rem;letter-spacing:.04em;color:var(--ri-ink2);margin:.2rem 0 2rem;padding:.6rem 0;}
.ri-seg{padding:0 1.1rem;border-right:1px solid var(--ri-hair);white-space:nowrap;}
.ri-seg:first-child{padding-left:0;}
.ri-ledger b{color:var(--ri-ink);font-weight:600;}

/* ===== Research Instrument — Proof Tiles ===== */
.ri-tile{background:var(--ri-card);border:1px solid var(--ri-line);border-radius:16px;padding:1.5rem 1.5rem 1.35rem;position:relative;overflow:visible;box-shadow:0 1px 2px rgba(20,40,60,.05),0 12px 28px rgba(20,40,60,.06);}
.ri-tile::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;border-radius:16px 0 0 16px;}
.ri-tile.t-crimson::before{background:var(--ri-crimson);}
.ri-tile.t-amber::before{background:var(--ri-amber);}
.ri-tile.t-green::before{background:var(--ri-green);}
.ri-tile.t-muted::before{background:var(--ri-muted);}
.ri-lab{font-family:'IBM Plex Mono',monospace;font-size:.68rem;letter-spacing:.16em;text-transform:uppercase;color:var(--ri-muted);display:inline-block;}
.ri-num{font-family:'Fraunces',serif;font-weight:600;font-size:3.05rem;line-height:1;margin:.5rem 0 .35rem;color:var(--ri-ink);font-variant-numeric:tabular-nums;}
.ri-tile .ri-sub{font-size:.85rem;color:var(--ri-ink2);line-height:1.45;}
.ri-stamp{position:absolute;top:1.15rem;right:1.1rem;font-family:'IBM Plex Mono',monospace;font-size:.62rem;font-weight:700;letter-spacing:.13em;text-transform:uppercase;padding:.22rem .5rem;border:2px solid currentColor;border-radius:5px;transform:rotate(3deg);}
.ri-tile.t-crimson .ri-stamp{color:var(--ri-crimson);}
.ri-tile.t-amber .ri-stamp{color:var(--ri-amber);}
.ri-tile.t-green .ri-stamp{color:var(--ri-green);}
.ri-tile.t-muted .ri-stamp{color:var(--ri-muted);border-style:dashed;}

/* ===== Research Instrument — Screener Funnel ===== */
.ri-funnel{display:flex;align-items:center;flex-wrap:wrap;gap:.5rem;padding:1.25rem 1.5rem;background:var(--ri-card);border:1px solid var(--ri-line);border-radius:16px;box-shadow:0 1px 2px rgba(20,40,60,.05),0 8px 20px rgba(20,40,60,.05);margin:.5rem 0 1.5rem;}
.ri-funnel-step{display:flex;flex-direction:column;align-items:center;gap:.25rem;padding:.5rem .9rem;border-radius:10px;background:var(--ri-hair);min-width:90px;}
.ri-funnel-step--amber{background:#FEF3E2;}
.ri-funnel-label{font-family:'IBM Plex Mono',monospace;font-size:.68rem;letter-spacing:.1em;text-transform:uppercase;color:var(--ri-muted);}
.ri-funnel-count{font-family:'Fraunces',serif;font-weight:600;font-size:2rem;line-height:1;color:var(--ri-ink);font-variant-numeric:tabular-nums;}
.ri-funnel-step--amber .ri-funnel-count{color:var(--ri-amber);}
.ri-funnel-step--amber .ri-funnel-label{color:var(--ri-amber);}
.ri-funnel-arrow{font-size:1.2rem;color:var(--ri-muted);line-height:1;padding-top:.5rem;}

/* ===== Research Instrument — Conclusion Band ===== */
.ri-conclusion{display:block;width:100%;background:#FFFFFF;border-left:4px solid var(--ri-teal);border-radius:0 10px 10px 0;padding:1rem 1.4rem;margin:1.2rem 0 1.5rem;font-family:'IBM Plex Sans',sans-serif;font-size:1.05rem;line-height:1.55;color:var(--ri-ink2);box-shadow:0 1px 3px rgba(15,110,128,.08);}

/* ===== Research Instrument — Inline Metric Row ===== */
.ri-metric-row{display:flex;gap:3rem;margin:.3rem 0 1.4rem;flex-wrap:wrap;}
.ri-metric-lab{font-size:.82rem;color:var(--ri-muted);margin-bottom:.15rem;}
.ri-metric-num{font-family:'Fraunces',serif;font-weight:600;font-size:2.1rem;line-height:1;color:var(--ri-ink);font-variant-numeric:tabular-nums;}

/* ===== Trust Tab — Experiment Cards ===== */
.ri-experiment{background:var(--ri-card);border:1px solid var(--ri-line);border-radius:14px;padding:1.1rem 1.4rem;margin-bottom:.85rem;box-shadow:0 1px 2px rgba(20,40,60,.04),0 6px 14px rgba(20,40,60,.05);}
.ri-exp-verdict{font-family:'IBM Plex Mono',monospace;font-size:.68rem;font-weight:700;letter-spacing:.18em;text-transform:uppercase;margin-bottom:.6rem;}
.ri-exp-row{display:flex;gap:.75rem;align-items:baseline;margin-bottom:.3rem;font-size:.88rem;line-height:1.45;}
.ri-exp-field{font-family:'IBM Plex Mono',monospace;font-size:.65rem;letter-spacing:.12em;text-transform:uppercase;color:var(--ri-muted);flex-shrink:0;width:4.5rem;}
.ri-exp-value{color:var(--ri-ink2);}
.ri-exp-result{font-weight:600;}
.ri-exp-decision{font-style:italic;color:var(--ri-muted);}

/* ===== Portfolio Tab — Hero + Position Cards ===== */
.port-hero{background:var(--ri-card);border:1px solid var(--ri-line);border-radius:16px;padding:1.6rem 2rem;margin-bottom:1.2rem;box-shadow:0 1px 2px rgba(20,40,60,.05),0 8px 20px rgba(20,40,60,.05);}
.port-hero .ri-metric-row{margin-bottom:0;}
.port-pos-card{background:var(--ri-card);border:1px solid var(--ri-line);border-radius:14px;padding:1.1rem 1.4rem;margin-bottom:.75rem;box-shadow:0 1px 2px rgba(20,40,60,.04),0 6px 14px rgba(20,40,60,.05);position:relative;overflow:hidden;}
.port-pos-card::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;border-radius:14px 0 0 14px;}
.port-pos-gain::before{background:var(--ri-green);}
.port-pos-loss::before{background:var(--ri-crimson);}
.port-drill{font-size:.78rem;color:var(--ri-muted);margin-top:.35rem;}
.port-drill a{color:var(--ri-teal);text-decoration:none;}
.port-drill a:hover{text-decoration:underline;}

/* ---- decision card (S3) ---- */
.dc-row{display:flex;align-items:center;gap:13px;padding:13px 16px;border-top:1px solid var(--ri-hair);cursor:pointer;}
.dc-row:first-child{border-top:0;}
.dc-tk b{font-size:14.5px;} .dc-tk span{display:block;font-size:10px;color:var(--ri-muted);}
.dc-sq{width:15px;height:15px;border-radius:4px;position:relative;display:inline-block;}
.dc-sq.r{background:var(--ri-crimson);} .dc-sq.a{background:var(--ri-amber);} .dc-sq.g{background:var(--ri-green);}
.dc-sq.gap{background:repeating-linear-gradient(45deg,#e7edee,#e7edee 3px,#fafcfc 3px,#fafcfc 6px);border:1px solid var(--ri-line);}
.dc-sq .dc-tip{visibility:hidden;opacity:0;position:absolute;bottom:150%;left:50%;transform:translateX(-50%);width:172px;background:var(--ri-ink);color:#fff;font-size:10.5px;line-height:1.45;padding:7px 9px;border-radius:7px;z-index:30;box-shadow:0 10px 26px -8px rgba(0,0,0,.4);text-align:left;}
.dc-sq:hover .dc-tip{visibility:visible;opacity:1;}
.dc-spark{width:80px;height:28px;}
.dc-sk{background:linear-gradient(90deg,#eef3f4 8%,#dceaec 22%,#eef3f4 36%);background-size:200% 100%;animation:dc-shimmer 1.25s linear infinite;border-radius:5px;display:inline-block;}
@keyframes dc-shimmer{0%{background-position:160% 0;}100%{background-position:-60% 0;}}
.dc-case{border:1px solid var(--ri-line);border-radius:9px;overflow:hidden;margin-bottom:13px;}
.dc-case-hd{display:flex;justify-content:space-between;align-items:center;background:var(--ri-hair);padding:9px 12px;font-weight:700;font-size:12.5px;}
.dc-case-badge{font-family:'IBM Plex Mono';font-size:9px;font-weight:600;color:var(--ri-muted);background:#e3ebec;padding:2px 8px;border-radius:9px;}
.dc-cols{display:flex;} .dc-cols>div{flex:1;padding:11px 13px;} .dc-cols>div:first-child{border-right:1px solid var(--ri-hair);}
.dc-ch{font-family:'IBM Plex Mono';font-size:10px;font-weight:700;text-transform:uppercase;margin-bottom:6px;}
.dc-learn{border:1.5px solid var(--ri-teal);border-radius:10px;padding:12px;background:#f7fdfe;margin-bottom:13px;}

/* ===== Top-region vertical rhythm ===== */
/* Breathing room between the app title and the tab bar */
h1.ri-app-title, h1[class*="ri-app-title"] {
    margin-bottom: 12px !important;
}
/* Give the tab bar a little breathing room below it before content starts */
.stTabs [data-baseweb="tab-list"] {
    margin-bottom: 4px !important;
}
/* Tab panel top-padding: first content sits 1.2rem below the tab strip */
[role="tabpanel"] > div:first-child {
    padding-top: 1.2rem !important;
}
/* Door banner: 0 top-margin; no bottom margin — .door-actions sits flush below it */
.door {
    margin-top: 0 !important;
    margin-bottom: 0 !important;
}
/* .door-actions panel provides the 1.25rem gap below the whole unit */
.door-actions {
    /* defined in Landing Door block above */
}
/* Onboarding button row: tighten the gap below it */
.ob-row-spacer {
    margin-bottom: 0.5rem;
}

/* ===== Landing Door (S6 onboarding) ===== */
/* Banner: square bottom so it flows directly into the action panel below */
.door{background:linear-gradient(135deg,#0F6E80 0%,#0a4a57 100%);border-radius:18px 18px 0 0;padding:22px 30px 18px;box-shadow:0 4px 24px rgba(15,110,128,.22);}
.door h2{color:#fff;}
/* Action panel: connects directly under the banner — no gap, matching width,
   light petrol tint background so banner+buttons read as one cohesive block */
.door-actions{background:#f0f7f8;border:1px solid #c8dfe3;border-top:none;border-radius:0 0 18px 18px;padding:16px 30px 20px;margin-bottom:1.25rem;box-shadow:0 4px 24px rgba(15,110,128,.12);}
/* .db classes kept for backward compat but dead buttons removed from HTML */
.db{display:inline-flex;align-items:center;justify-content:center;padding:9px 18px;border-radius:10px;font-family:'IBM Plex Sans',sans-serif;font-size:13.5px;font-weight:600;cursor:pointer;border:none;transition:opacity .15s,transform .12s;}
.db.primary{background:#fff;color:#0F6E80;}
.db.primary:hover{opacity:.92;transform:translateY(-1px);}
.db.ghost{background:rgba(255,255,255,.12);color:#fff;border:1.5px solid rgba(255,255,255,.35);}
.db.ghost:hover{background:rgba(255,255,255,.22);transform:translateY(-1px);}

/* ===== Door + action-panel cohesion (AREA 1) ===== */
/* The .door-actions div is injected via st.markdown immediately before and after
   the 3-column button row. Since Streamlit renders widgets as siblings (not children)
   of inline HTML divs, we use a CSS rule to background-color the column group that
   directly follows .door — targeting the stHorizontalBlock sibling. */
.door + div > div[data-testid="stHorizontalBlock"],
.door + div[data-testid="stHorizontalBlock"] {
    background: #f0f7f8 !important;
    border: 1px solid #c8dfe3 !important;
    border-top: none !important;
    border-radius: 0 0 18px 18px !important;
    padding: 14px 18px 18px !important;
    margin-bottom: 1.25rem !important;
    box-shadow: 0 4px 16px rgba(15,110,128,.10) !important;
}

/* ===== Onboarding action widgets — petrol on-brand ===== */
/* All action buttons — full-width, minimum height, IBM Plex Sans */
div.stButton > button {
    width: 100% !important;
    min-height: 46px !important;
    border-radius: 10px !important;
    font-family: 'IBM Plex Sans', sans-serif !important;
    font-weight: 600 !important;
    font-size: 13.5px !important;
    transition: opacity .15s, transform .12s, background .15s !important;
}
/* Primary button — petrol fill, white text */
div.stButton > button[kind="primary"] {
    background-color: #0F6E80 !important;
    border: none !important;
    color: #FFFFFF !important;
    box-shadow: 0 2px 8px rgba(15,110,128,.28) !important;
}
div.stButton > button[kind="primary"]:hover {
    background-color: #0a4a57 !important;
    opacity: .95 !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 14px rgba(15,110,128,.35) !important;
}
/* Secondary button — white bg, petrol border + text */
div.stButton > button[kind="secondary"] {
    background: #FFFFFF !important;
    border: 1.5px solid #0F6E80 !important;
    color: #0F6E80 !important;
}
div.stButton > button[kind="secondary"]:hover {
    background: rgba(15,110,128,.07) !important;
    transform: translateY(-1px) !important;
}
/* File uploader — full-width, dashed petrol border, light tint */
div[data-testid="stFileUploader"] {
    border: 1.5px dashed rgba(15,110,128,.45) !important;
    border-radius: 10px !important;
    padding: 8px 12px !important;
    background: rgba(15,110,128,.04) !important;
    width: 100% !important;
}
section[data-testid="stFileUploaderDropzone"] {
    background: transparent !important;
    border: none !important;
    padding: 6px 0 !important;
}
/* Hide noisy file-size hint; keep the Browse button */
[data-testid="stFileUploaderDropzoneInstructions"] small { display: none !important; }
div[data-testid="stFileUploader"] span {
    font-family: 'IBM Plex Sans', sans-serif !important;
    font-size: 12.5px !important;
    color: #0F6E80 !important;
}

/* ===== Risk Tab — Status-First Design Tokens (Task 10 / ADR-052) ===== */
/* STATUS SPINE: green=within line · grey=neutral character · amber=look-here
   Petrol (--ri-teal) is the ONLY data colour. These tokens mirror risk-v8.html :root */
:root {
    --risk-ok: #15803d;
    --risk-ok-l: #e7f4ec;
    --risk-amber: #b45309;
    --risk-amber-l: #fbf0dc;
    --risk-amber-b: #ecdcb6;
    --risk-g0: #E2E8F0;
    --risk-g1: #94A3B8;
    --risk-g2: #475569;
    /* petrol data hue — reuse existing --ri-teal (#0F6E80) for data bars */
    --risk-petrol: #0F6E80;
    --risk-petrol-d: #0a5260;
    --risk-petrol-l: #e6f1f3;
    --risk-ink: #0f1c1f;
    --risk-mut: #5b7178;
    --risk-faint: #94a8ad;
    --risk-line: #dde7e9;
    --risk-paper: #fbfcfc;
    --risk-card: #ffffff;
    --risk-shadow: 0 1px 2px rgba(15,28,31,.05), 0 8px 24px -12px rgba(15,28,31,.12);
}

/* ── Status banner (green / amber states) ── */
.risk-status {
    display: flex;
    align-items: center;
    gap: 14px;
    border-radius: 14px;
    padding: 15px 18px;
    box-shadow: var(--risk-shadow);
    margin-bottom: 12px;
    border: 1px solid var(--risk-amber-b);
    background: linear-gradient(120deg, var(--risk-amber-l), #fff 75%);
}
.risk-status.ok {
    border-color: #bbddc8;
    background: linear-gradient(120deg, var(--risk-ok-l), #fff 75%);
}
.risk-status .risk-big {
    width: 46px;
    height: 46px;
    border-radius: 12px;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: 'Fraunces', serif;
    font-weight: 900;
    font-size: 22px;
    background: var(--risk-amber);
    color: #fff;
}
.risk-status.ok .risk-big { background: var(--risk-ok); }
.risk-status .risk-sk {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    letter-spacing: .12em;
    text-transform: uppercase;
    color: var(--risk-amber);
    font-weight: 600;
}
.risk-status.ok .risk-sk { color: var(--risk-ok); }
.risk-status .risk-sv {
    font-family: 'Fraunces', serif;
    font-size: 18px;
    font-weight: 700;
    line-height: 1.3;
    margin-top: 2px;
}
.risk-status .risk-ss {
    font-size: 12px;
    color: var(--risk-mut);
    margin-top: 3px;
    line-height: 1.45;
}
.risk-status .risk-meas {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 9px;
    color: var(--risk-faint);
    letter-spacing: .06em;
    text-align: right;
    flex-shrink: 0;
    line-height: 1.6;
}

/* ── Vitals strip ── */
.risk-vitals {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(132px, 1fr));
    gap: 10px;
    margin: 14px 0 0;
}
.risk-vit {
    background: var(--risk-card);
    border: 1px solid var(--risk-line);
    border-radius: 12px;
    padding: 12px 14px;
    box-shadow: var(--risk-shadow);
    border-top: 3px solid var(--risk-petrol);
}
.risk-vit.amber { border-top-color: var(--risk-amber); }
.risk-vit.grey  { border-top-color: var(--risk-g1); }
.risk-vit.ok    { border-top-color: var(--risk-ok); }
.risk-vit .risk-vk {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 9px;
    letter-spacing: .08em;
    text-transform: uppercase;
    color: var(--risk-faint);
    display: flex;
    align-items: center;
}
.risk-vit .risk-vv {
    font-family: 'Fraunces', serif;
    font-weight: 800;
    font-size: 23px;
    margin-top: 5px;
    line-height: 1;
}
.risk-vit .risk-vv small {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    font-weight: 500;
    color: var(--risk-mut);
}
.risk-vit .risk-vs {
    font-size: 10.5px;
    color: var(--risk-mut);
    margin-top: 5px;
    line-height: 1.4;
}

/* ── Gauge dials ── */
.risk-cluster {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 13px;
}
.risk-gauge {
    background: var(--risk-card);
    border: 1px solid var(--risk-line);
    border-radius: 14px;
    padding: 16px 14px 14px;
    box-shadow: var(--risk-shadow);
    text-align: center;
    border-top: 3px solid var(--risk-g1);
}
.risk-gauge.flagged {
    border-top-color: var(--risk-amber);
    background: linear-gradient(180deg, var(--risk-amber-l), #fff 55%);
}
.risk-gauge.clear { border-top-color: var(--risk-ok); }
.risk-glab {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 9.5px;
    letter-spacing: .1em;
    text-transform: uppercase;
    color: var(--risk-faint);
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
}
.risk-gval {
    font-family: 'Fraunces', serif;
    font-weight: 800;
    font-size: 24px;
    line-height: 1;
    margin-top: 5px;
}
.risk-gband {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 9.5px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 8px;
    background: #eef1f4;
    color: var(--risk-g2);
    display: inline-block;
    margin-top: 7px;
}
.risk-gband.warn { background: var(--risk-amber); color: #fff; }
.risk-gband.ok   { background: var(--risk-ok);    color: #fff; }
.risk-gsub {
    font-size: 10.5px;
    color: var(--risk-mut);
    margin-top: 7px;
    line-height: 1.4;
}

/* ── Bootstrap CI band on a track strip ── */
.risk-ciband {
    position: absolute;
    top: 0;
    height: 14px;
    background: rgba(180, 83, 9, .16);
    border-left: 1px dashed rgba(180, 83, 9, .5);
    border-right: 1px dashed rgba(180, 83, 9, .5);
}
.risk-cilabel {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 9px;
    color: var(--risk-amber);
    margin-top: 5px;
    text-align: center;
}

/* ── Factor whiskers (90% CI on factor bars) ── */
.risk-whisk {
    position: absolute;
    top: 6.5px;
    height: 1.5px;
    background: rgba(15, 28, 31, .45);
}
.risk-whisk::before,
.risk-whisk::after {
    content: "";
    position: absolute;
    top: -3px;
    width: 1.5px;
    height: 7px;
    background: rgba(15, 28, 31, .45);
}
.risk-whisk::before { left: 0; }
.risk-whisk::after  { right: 0; }

/* ── ENB (Effective Number of Bets) block ── */
.risk-enb {
    background: var(--risk-card);
    border: 1px solid var(--risk-line);
    border-radius: 14px;
    padding: 18px 20px;
    box-shadow: var(--risk-shadow);
    display: flex;
    gap: 20px;
    align-items: center;
}
.risk-enbnum {
    text-align: center;
    flex-shrink: 0;
}
.risk-enbnum .risk-big-n {
    font-family: 'Fraunces', serif;
    font-weight: 900;
    font-size: 46px;
    line-height: .9;
    color: var(--risk-amber);
}
.risk-enbnum .risk-of {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    color: var(--risk-faint);
    letter-spacing: .06em;
    margin-top: 4px;
}
.risk-enbnum .risk-lab {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 9px;
    letter-spacing: .1em;
    text-transform: uppercase;
    color: var(--risk-faint);
    margin-top: 8px;
}
.risk-enbright { flex: 1; }
.risk-enbright p {
    font-size: 12.5px;
    color: #33474c;
    line-height: 1.55;
    margin: 0 0 12px;
}
.risk-enbright p b { color: var(--risk-ink); }

/* PC variance bars inside ENB block */
.risk-pcrow {
    display: grid;
    grid-template-columns: 64px 1fr 40px;
    align-items: center;
    gap: 9px;
    font-size: 11px;
    margin-bottom: 6px;
}
.risk-pcrow .risk-pn {
    font-family: 'IBM Plex Mono', monospace;
    color: var(--risk-mut);
}
.risk-pcrow .risk-pt {
    height: 9px;
    background: #f4f7f8;
    border-radius: 5px;
    position: relative;
    overflow: hidden;
}
.risk-pcrow .risk-pf {
    position: absolute;
    top: 0; left: 0;
    height: 9px;
    border-radius: 5px;
    background: var(--risk-petrol);
}
.risk-pcrow .risk-pf.one { background: var(--risk-amber); }
.risk-pcrow .risk-pv {
    font-family: 'IBM Plex Mono', monospace;
    text-align: right;
    color: var(--risk-ink);
}

/* ── Sector / weight bars ── */
.risk-wrow {
    display: grid;
    grid-template-columns: 140px 1fr 48px;
    align-items: center;
    gap: 10px;
    font-size: 12px;
    margin-bottom: 8px;
}
.risk-wrow .risk-wn {
    font-family: 'IBM Plex Mono', monospace;
    color: var(--risk-ink);
}
.risk-wrow .risk-wt {
    height: 11px;
    background: #f4f7f8;
    border-radius: 5px;
    position: relative;
    overflow: hidden;
}
.risk-wrow .risk-wf {
    position: absolute;
    top: 0; left: 0;
    height: 11px;
    border-radius: 5px;
    background: var(--risk-petrol);
}
.risk-wrow .risk-wv {
    font-family: 'IBM Plex Mono', monospace;
    text-align: right;
    color: var(--risk-ink);
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
}

/* ── Google AI second-opinion panel ── */
.risk-ai {
    border: 1px solid #dfe3ea;
    border-radius: 14px;
    background: linear-gradient(180deg, #fbfcff, #fff 60%);
    box-shadow: var(--risk-shadow);
    overflow: hidden;
}
.risk-aihd {
    display: flex;
    align-items: center;
    gap: 9px;
    padding: 14px 17px;
    border-bottom: 1px solid #eef1f6;
}
.risk-aihd .risk-at {
    font-family: 'Fraunces', serif;
    font-weight: 700;
    font-size: 15px;
}
.risk-aihd .risk-ab {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 8.5px;
    font-weight: 600;
    letter-spacing: .06em;
    background: #eef1f4;
    color: var(--risk-mut);
    padding: 2px 7px;
    border-radius: 7px;
    margin-left: auto;
}
.risk-aibody { padding: 14px 17px; }
.risk-aiq {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    letter-spacing: .06em;
    color: var(--risk-faint);
    text-transform: uppercase;
    margin-bottom: 10px;
}
.risk-aipt {
    display: flex;
    gap: 10px;
    align-items: flex-start;
    font-size: 12.5px;
    line-height: 1.55;
    color: #33474c;
    margin-bottom: 10px;
}
.risk-aipt .risk-n {
    flex-shrink: 0;
    width: 18px;
    height: 18px;
    border-radius: 5px;
    background: #eef1f6;
    color: var(--risk-mut);
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-top: 1px;
}
.risk-aipt b { color: var(--risk-ink); }
.risk-aifoot {
    font-size: 10.5px;
    color: var(--risk-faint);
    background: #f8f9fc;
    border-top: 1px solid #eef1f6;
    padding: 9px 17px;
    line-height: 1.5;
}
/* Google coloured dots for AI attribution */
.risk-gdot { display: flex; gap: 3px; }
.risk-gdot i { width: 8px; height: 8px; border-radius: 50%; }
.risk-gdot .gb { background: #4285F4; }
.risk-gdot .gr { background: #EA4335; }
.risk-gdot .gy { background: #FBBC05; }
.risk-gdot .gg { background: #34A853; }
/* Re-run instruction label (non-interactive — live calls happen via weekly-brief CLI, not at render) */
.risk-aibtn{display:inline-flex;align-items:center;gap:7px;font-family:'IBM Plex Mono',monospace;font-size:11px;font-weight:600;color:var(--risk-petrol);border:1px solid var(--risk-line);border-radius:9px;padding:8px 13px;background:#fff;margin-top:4px}
/* Section-tag label used in ri-sec headers */
.ri-tg{color:var(--risk-petrol)}

/* ── Drift flag card ── */
.risk-drift {
    display: flex;
    gap: 16px;
    align-items: center;
    background: var(--risk-card);
    border: 1px solid var(--risk-amber-b);
    border-left: 4px solid var(--risk-amber);
    border-radius: 14px;
    padding: 16px 20px;
    box-shadow: var(--risk-shadow);
}
.risk-drift .risk-dk {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    letter-spacing: .1em;
    text-transform: uppercase;
    color: var(--risk-amber);
    display: flex;
    align-items: center;
}
.risk-drift .risk-dt {
    font-size: 13px;
    line-height: 1.55;
    color: #33474c;
    margin-top: 6px;
}
.risk-drift .risk-dt b  { color: var(--risk-ink); }
.risk-drift .risk-dt .risk-up { color: var(--risk-amber); font-weight: 600; }

/* ── Spectrum note (under dials) ── */
.risk-spectrum-note {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 9.5px;
    color: var(--risk-faint);
    text-align: center;
    margin-top: 9px;
    letter-spacing: .04em;
}

/* ── Coverage line ── */
.risk-cov {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    color: var(--risk-faint);
    letter-spacing: .08em;
    margin-top: 10px;
    text-align: right;
    display: flex;
    align-items: center;
    justify-content: flex-end;
}

/* ── Flag cards (active flags list) ── */
.risk-flagcard {
    display: flex;
    gap: 11px;
    align-items: flex-start;
    background: var(--risk-amber-l);
    border: 1px solid var(--risk-amber-b);
    border-left: 4px solid var(--risk-amber);
    border-radius: 11px;
    padding: 13px 15px;
    margin-bottom: 9px;
}
.risk-flagcard .risk-fdot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--risk-amber);
    margin-top: 5px;
    flex-shrink: 0;
}
.risk-flagcard .risk-ft {
    font-size: 13px;
    line-height: 1.5;
    color: #5b4a28;
}
.risk-flagcard .risk-ft b {
    color: #3f3318;
    display: block;
    margin-bottom: 3px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    letter-spacing: .06em;
}

/* ── Teach-me walkthrough (.teach family) — ported from risk-v8.html lines 100-104 ── */
/* .teach border-left-color is NOT !important so R04/ENB can override it with style="border-left-color:var(--risk-amber)" */
.teach{border:1px solid var(--risk-line);border-left:4px solid var(--risk-petrol);border-radius:13px;background:var(--risk-paper);overflow:hidden}
.teach summary{list-style:none;cursor:pointer;padding:14px 17px;font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--risk-petrol);font-weight:600;display:flex;justify-content:space-between;align-items:center}
.teach summary::-webkit-details-marker{display:none}
.teach summary .h{font-family:'Fraunces',serif;font-weight:700;font-size:15px;text-transform:none;color:var(--risk-ink)}
.teach[open] summary{border-bottom:1px solid var(--risk-line)}
.tbody{padding:4px 17px 14px}
.chap{padding:14px 0;border-bottom:1px solid #eef3f4}
.chap:last-child{border-bottom:0}
.cnum{font-family:'IBM Plex Mono',monospace;font-size:10px;font-weight:600;color:var(--risk-petrol);letter-spacing:.1em}
.cq{font-family:'Fraunces',serif;font-weight:700;font-size:16px;margin:3px 0 4px}
.csub{font-size:12px;color:var(--risk-mut);line-height:1.5;margin:0 0 9px}
.ans{font-size:12.5px;line-height:1.55;color:#33474c;margin-top:8px}
.ans b{color:var(--risk-ink)}
/* donut: base is a neutral placeholder; inline style="background:conic-gradient(...)" from _teach() sets the real split */
.donut{width:118px;height:118px;border-radius:50%;background:var(--risk-line);display:flex;align-items:center;justify-content:center;flex-shrink:0}
.donut b{width:74px;height:74px;border-radius:50%;background:#fff;display:flex;flex-direction:column;align-items:center;justify-content:center;font-family:'Fraunces',serif;font-weight:800;font-size:18px}
.donut b span{font-family:'IBM Plex Mono',monospace;font-size:8px;font-weight:600;color:var(--risk-faint);letter-spacing:.05em}
.split{display:flex;gap:16px;align-items:center}
.dleg{font-size:10.5px;color:var(--risk-mut);line-height:1.7}
.sw2{display:inline-block;width:9px;height:9px;border-radius:2px;vertical-align:middle;margin-right:4px}
/* .levers: sub-block inside .tbody; default border-left petrol, R04 overrides to amber inline */
.levers{border-left:3px solid var(--risk-petrol);padding:10px 0 4px 14px;margin-top:8px}
.lvh{font-family:'IBM Plex Mono',monospace;font-size:10px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:var(--risk-mut);margin-bottom:8px}
/* .act / .act .ic: action rows inside .levers (icon badge + body text) */
.act{display:flex;gap:11px;align-items:flex-start;font-size:13px;line-height:1.5;color:#33474c;margin-bottom:9px}
.act:last-child{margin-bottom:0}
.act .ic{flex-shrink:0;width:22px;height:22px;border-radius:6px;background:var(--risk-amber);color:#fff;font-family:'IBM Plex Mono',monospace;font-weight:700;font-size:11px;display:flex;align-items:center;justify-content:center;margin-top:1px}
.act b{color:var(--risk-ink)}

/* ===== Portfolio Tab — Needs-Review Cards (Task 6) ===== */
.pf-review{border:1px solid var(--ri-line);border-radius:10px;padding:12px 15px;margin-bottom:8px;transition:box-shadow .1s;}
.pf-review:hover{box-shadow:0 2px 10px rgba(15,23,42,.08);}
.pf-review.reduce{border-left:4px solid #991B1B;background:#FFFAFA;}
.pf-review.trim{border-left:4px solid #DC2626;background:#FFFBFB;}
.pf-review.review{border-left:4px solid #F59E0B;background:#FFFDF6;}

/* ===== Portfolio Tab — Squarified Treemap (Task 7) ===== */
.pf-stage{position:relative;width:100%;background:#E2E8F0;border-radius:11px;overflow:hidden;}
.pf-sec{position:absolute;border-radius:8px;overflow:hidden;background:#0F172A;}
.pf-sechdr{position:absolute;top:0;left:0;right:0;height:16px;background:rgba(15,23,42,.82);color:#fff;font-size:.58rem;font-weight:700;text-transform:uppercase;letter-spacing:.04em;padding:2px 7px;display:flex;justify-content:space-between;white-space:nowrap;}
.pf-tile{position:absolute;overflow:hidden;text-decoration:none;padding:4px 6px;display:flex;flex-direction:column;justify-content:center;}
.pf-tile:hover{outline:3px solid #0F172A;z-index:8;}
.pf-tile:hover .pf-tip{opacity:1;}
.pf-tip{position:absolute;bottom:calc(100% + 6px);left:50%;transform:translateX(-50%);background:#0F172A;color:#fff;border-radius:9px;padding:8px 10px;width:170px;opacity:0;pointer-events:none;transition:.12s;z-index:50;}
.pf-tip-tt{font-family:'Fraunces',serif;font-weight:700;font-size:.85rem;margin-bottom:3px;}
.pf-tip-row{font-size:.69rem;color:#CBD5E1;display:flex;justify-content:space-between;margin-top:2px;}
.pf-tip-row b{color:#fff;}
</style>
"""


def inject_global_css() -> None:
    """Inject global CSS into the Streamlit page. Call once in dashboard.py."""
    import streamlit as st

    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
