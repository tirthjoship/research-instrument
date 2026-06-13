"""Global CSS styles for dashboard — injected once in dashboard.py."""

from __future__ import annotations

GLOBAL_CSS = """
<style>
/* ===== Fonts ===== */
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

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
[data-testid="stMainBlockContainer"],.block-container{max-width:1180px!important;padding:2.2rem 2.4rem 3rem!important;font-family:'IBM Plex Sans',sans-serif;color:var(--ri-ink);}
.ri-h1{font-family:'Fraunces',serif;font-weight:600;font-size:2.6rem;line-height:1.03;letter-spacing:-.015em;color:var(--ri-ink);}
.ri-sub{font-family:'Fraunces',serif;font-style:italic;font-size:1.12rem;color:var(--ri-ink2);}
.ri-sec{font-family:'IBM Plex Mono',monospace;font-size:.72rem;letter-spacing:.2em;text-transform:uppercase;color:var(--ri-muted);display:flex;align-items:center;gap:.8rem;margin:.4rem 0 1rem;}
.ri-sec::after{content:"";flex:1;height:1px;background:var(--ri-hair);}
.ri-ttip{position:relative;cursor:help;border-bottom:1px dotted var(--ri-muted);}
.ri-tip{position:absolute;bottom:142%;left:50%;transform:translateX(-50%) translateY(5px);background:#1b2733;color:#eef3f6;font-family:'IBM Plex Sans';font-size:.76rem;line-height:1.45;padding:.65rem .8rem;border-radius:10px;width:240px;box-shadow:0 10px 30px rgba(15,30,45,.22);opacity:0;visibility:hidden;transition:.15s;z-index:60;text-align:left;}
.ri-tip::after{content:"";position:absolute;top:100%;left:50%;transform:translateX(-50%);border:6px solid transparent;border-top-color:#1b2733;}
.ri-ttip:hover .ri-tip{opacity:1;visibility:visible;transform:translateX(-50%) translateY(0);}

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
</style>
"""


def inject_global_css() -> None:
    """Inject global CSS into the Streamlit page. Call once in dashboard.py."""
    import streamlit as st

    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
