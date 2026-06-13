# Research Instrument — approved Home spike (visual reference)

> Throwaway prototype, validated with Tirth on 2026-06-12 (white/petrol direction, bold semantic
> color, clickable yfinance tickers, comprehensive hover tooltips). **Salvage the CSS/components**
> into the existing component library; do NOT ship this monolith as-is. CSS source-of-truth
> alongside the plan (`2026-06-13-research-instrument-redesign.md`) and ADR-055.

```python
"""THROWAWAY decision spike v3 — white 'Research Instrument' Home, pure Streamlit.

Adds: hover-tooltip ("cloud") system on every term, clickable yfinance tickers,
bolder semantic color, balanced spacing. One tooltip forced-open for the screenshot.
Run: streamlit run /tmp/dossier_home_spike.py --server.port 8540
"""
from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Stock Intelligence", layout="wide",
                   initial_sidebar_state="collapsed")

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700;9..144,900&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap');
:root{
  --app:#F4F6F8; --card:#FFFFFF; --ink:#14181F; --ink2:#3a4250; --muted:#717885;
  --line:#E3E7EC; --hair:#EDF0F3; --teal:#0F6E80;
  --crimson:#CE2F26; --amber:#C9810E; --green:#1F9254;}
#MainMenu,header[data-testid="stHeader"],footer,[data-testid="stToolbar"],[data-testid="stDecoration"]{display:none!important;}
html,body,[data-testid="stApp"],.stApp{background:radial-gradient(1100px 520px at 12% -8%, #FFFFFF 0%, rgba(255,255,255,0) 55%), var(--app)!important;}
[data-testid="stMainBlockContainer"],.block-container{max-width:1180px!important;padding:2.2rem 2.4rem 3rem!important;font-family:'IBM Plex Sans',sans-serif;color:var(--ink);}
.stApp::before{content:"";position:fixed;inset:0;pointer-events:none;z-index:0;opacity:.025;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/%3E%3CfeColorMatrix type='saturate' values='0'/%3E%3C/filter%3E%3Crect width='120' height='120' filter='url(%23n)'/%3E%3C/svg%3E");}
.wrap{position:relative;z-index:1;}
.toprule{height:3px;width:64px;background:var(--teal);border-radius:3px;margin-bottom:1.1rem;}
.kicker{font-family:'IBM Plex Mono',monospace;font-size:.70rem;letter-spacing:.22em;text-transform:uppercase;color:var(--teal);font-weight:600;}
h1.title{font-family:'Fraunces',serif;font-weight:600;font-size:2.75rem;line-height:1.03;letter-spacing:-.015em;margin:.2rem 0 .12rem;color:var(--ink);}
.subtitle{font-family:'Fraunces',serif;font-style:italic;font-weight:400;font-size:1.16rem;color:var(--ink2);margin:0 0 1.15rem;}

/* hover tooltip cloud */
.ttip{position:relative;cursor:help;}
.ttip.u{border-bottom:1px dotted var(--muted);}
.ttip .tip{position:absolute;bottom:142%;left:50%;transform:translateX(-50%) translateY(5px);
  background:#1b2733;color:#eef3f6;font-family:'IBM Plex Sans',sans-serif;font-size:.76rem;font-weight:400;
  letter-spacing:0;text-transform:none;line-height:1.45;padding:.65rem .8rem;border-radius:10px;
  width:240px;box-shadow:0 10px 30px rgba(15,30,45,.22);opacity:0;visibility:hidden;transition:.15s;z-index:60;text-align:left;}
.ttip .tip::after{content:"";position:absolute;top:100%;left:50%;transform:translateX(-50%);border:6px solid transparent;border-top-color:#1b2733;}
.ttip:hover .tip,.ttip.show .tip{opacity:1;visibility:visible;transform:translateX(-50%) translateY(0);}
.tip b{color:#5fd0bf;font-weight:600;}

.ledger{display:flex;align-items:center;flex-wrap:wrap;border-top:1.5px solid var(--ink);border-bottom:1px solid var(--hair);font-family:'IBM Plex Mono',monospace;font-size:.78rem;letter-spacing:.04em;color:var(--ink2);margin:.2rem 0 2rem;padding:.6rem 0;}
.ledger .seg{padding:0 1.1rem;border-right:1px solid var(--hair);white-space:nowrap;}
.ledger .seg:first-child{padding-left:0;}
.ledger b{color:var(--ink);font-weight:600;}
.dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--amber);margin-right:.5rem;box-shadow:0 0 0 3px rgba(201,129,14,.18);vertical-align:middle;}

.tiles{display:grid;grid-template-columns:repeat(3,1fr);gap:1.2rem;margin-bottom:2.2rem;}
.tile{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:1.5rem 1.5rem 1.35rem;position:relative;overflow:visible;box-shadow:0 1px 2px rgba(20,40,60,.05),0 12px 28px rgba(20,40,60,.06);}
.tile::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;border-radius:16px 0 0 16px;}
.tile.t-crimson::before{background:var(--crimson);} .tile.t-amber::before{background:var(--amber);} .tile.t-muted::before{background:var(--muted);}
.tile .lab{font-family:'IBM Plex Mono',monospace;font-size:.68rem;letter-spacing:.16em;text-transform:uppercase;color:var(--muted);display:inline-block;}
.tile .num{font-family:'Fraunces',serif;font-weight:600;font-size:3.05rem;line-height:1;margin:.5rem 0 .35rem;color:var(--ink);font-variant-numeric:tabular-nums;}
.tile .sub{font-size:.85rem;color:var(--ink2);line-height:1.45;}
.stamp{position:absolute;top:1.15rem;right:1.1rem;font-family:'IBM Plex Mono',monospace;font-size:.62rem;font-weight:700;letter-spacing:.13em;text-transform:uppercase;padding:.22rem .5rem;border:2px solid currentColor;border-radius:5px;transform:rotate(3deg);}
.s-crimson{color:var(--crimson);} .s-amber{color:var(--amber);} .s-muted{color:var(--muted);border-style:dashed;}

.sec{font-family:'IBM Plex Mono',monospace;font-size:.72rem;letter-spacing:.2em;text-transform:uppercase;color:var(--muted);margin:.4rem 0 1rem;display:flex;align-items:center;gap:.8rem;}
.sec::after{content:"";flex:1;height:1px;background:var(--hair);}
.cols{display:grid;grid-template-columns:300px 1fr;gap:1.6rem;align-items:start;}
.health{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:1.6rem;box-shadow:0 1px 2px rgba(20,40,60,.05),0 12px 28px rgba(20,40,60,.06);text-align:center;}
.ring-num{font-family:'Fraunces',serif;font-weight:600;font-size:2.5rem;fill:var(--ink);}
.ring-cap{font-family:'IBM Plex Mono',monospace;font-size:.62rem;letter-spacing:.18em;fill:var(--muted);}
.verdict-chip{display:inline-block;font-family:'IBM Plex Mono',monospace;font-size:.66rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;padding:.34rem .62rem;border-radius:6px;margin-top:.5rem;}
.vc-amber{background:rgba(201,129,14,.14);color:var(--amber);}
.health p{font-size:.82rem;color:var(--ink2);margin:.95rem 0 0;text-align:left;line-height:1.5;}
.vcards{display:flex;flex-direction:column;gap:.9rem;}
.vcard{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:1.05rem 1.25rem;display:flex;align-items:center;gap:1.1rem;box-shadow:0 1px 2px rgba(20,40,60,.05);transition:transform .15s,box-shadow .15s;border-left:4px solid var(--line);}
.vcard:hover{transform:translateY(-1px);box-shadow:0 8px 22px rgba(20,40,60,.10);}
.vcard.crimson{border-left-color:var(--crimson);background:linear-gradient(90deg,rgba(206,47,38,.04),var(--card) 22%);}
.vcard.green{border-left-color:var(--green);} .vcard.amber{border-left-color:var(--amber);}
a.tk{font-family:'IBM Plex Mono',monospace;font-weight:600;font-size:1.02rem;width:84px;color:var(--ink);text-decoration:none;display:inline-block;}
a.tk:hover{color:var(--teal);text-decoration:underline;}
a.tk .ar{color:var(--muted);font-size:.8rem;}
.vbody{flex:1;}
.vhead{font-family:'IBM Plex Mono',monospace;font-size:.7rem;font-weight:700;letter-spacing:.09em;text-transform:uppercase;display:inline-block;}
.vhead.crimson{color:var(--crimson);} .vhead.green{color:var(--green);} .vhead.amber{color:var(--amber);}
.vtext{font-size:.86rem;color:var(--ink2);margin-top:.2rem;line-height:1.45;}
.dots{font-family:monospace;letter-spacing:2px;font-size:.98rem;white-space:nowrap;}
.dots.green{color:var(--green);} .dots.crimson{color:var(--crimson);} .dots.amber{color:var(--amber);}
.dots .off{color:#d2d8df;}
.flags{display:flex;gap:.8rem;margin-top:1.8rem;flex-wrap:wrap;}
.flag{font-family:'IBM Plex Mono',monospace;font-size:.74rem;letter-spacing:.05em;border:1px solid var(--line);border-radius:999px;padding:.46rem .95rem;background:var(--card);color:var(--ink2);}
.flag b{color:var(--ink);font-weight:700;}
.foot{margin-top:2.5rem;padding-top:1rem;border-top:1px solid var(--hair);font-family:'IBM Plex Mono',monospace;font-size:.68rem;letter-spacing:.08em;color:var(--muted);text-align:center;}
</style>
"""

def ring(v: float) -> str:
    r = 52; c = 2 * 3.14159 * r; off = c * (1 - v / 100)
    return f"""<svg width="150" height="150" viewBox="0 0 150 150">
      <circle cx="75" cy="75" r="{r}" fill="none" stroke="#E7ECF0" stroke-width="11"/>
      <circle cx="75" cy="75" r="{r}" fill="none" stroke="#0F6E80" stroke-width="11" stroke-linecap="round" stroke-dasharray="{c:.1f}" stroke-dashoffset="{off:.1f}" transform="rotate(-90 75 75)"/>
      <text x="75" y="72" text-anchor="middle" class="ring-num">{v:.1f}</text>
      <text x="75" y="92" text-anchor="middle" class="ring-cap">BOOK HEALTH</text></svg>"""

def tip(label, text, cls="", show=False):
    sc = " show" if show else ""
    return f'<span class="ttip u {cls}{sc}">{label}<span class="tip">{text}</span></span>'

def yf(t): return f"https://finance.yahoo.com/quote/{t}"

HTML = f"""
<div class="wrap">
  <div class="toprule"></div>
  <div class="kicker">Multi-Modal Stock Recommender</div>
  <h1 class="title">A stock engine that learned <em style="font-weight:500;">when not to predict.</em></h1>
  <div class="subtitle">Evidence over forecasts. It abstains on purpose — and tells you why.</div>

  <div class="ledger">
    <span class="seg">{tip('<span class="dot"></span><b>ABSTAINING</b>', "<b>System state.</b> No name cleared the evidence bar this week, so the engine recommends nothing. Honest non-action.")}</span>
    <span class="seg">{tip("UNIVERSE&nbsp;&nbsp;<b>512</b>", "<b>Universe.</b> Names scanned this week (S&amp;P 500 + NASDAQ-100, after liquidity filters).")}</span>
    <span class="seg">{tip("CLEARED&nbsp;&nbsp;<b>0</b>", "<b>Cleared the bar.</b> How many names passed the pre-registered evidence threshold. Zero = abstain.")}</span>
    <span class="seg">{tip("NET&nbsp;β&nbsp;&nbsp;<b>+1.37</b>", "<b>Net market beta.</b> Your book moves ~1.37&times; the S&amp;P. Above 1 = more volatile than the market; most of your risk is one market-wide bet.", show=True)}</span>
    <span class="seg">{tip("BOOK&nbsp;&nbsp;<b>$14,512</b>", "<b>Book value.</b> Current marked value of your tracked holdings.")}</span>
    <span class="seg">AS OF&nbsp;&nbsp;<b>2026-06-11</b></span>
  </div>

  <div class="tiles">
    <div class="tile t-crimson"><span class="stamp s-crimson">Falsified</span>
      <div>{tip("Divergence rank-IC", "<b>Rank information coefficient.</b> Does the signal rank winners above losers? 0.004 &asymp; 0 = no predictive power. Pre-registered &rarr; tested &rarr; killed.", show=True)}</div>
      <div class="num">0.004</div><div class="sub">Pre-registered, tested 2006–2024. CI spans zero — it's noise. We killed it.</div></div>
    <div class="tile t-muted"><span class="stamp s-muted">= EMH</span>
      <div>{tip("Directional accuracy", "<b>Hit rate of up/down calls</b> on mega-caps. ~50% = a coin flip — exactly what the Efficient Market Hypothesis predicts. We don't hide it.")}</div>
      <div class="num">49.8<span style="font-size:1.6rem">%</span></div><div class="sub">On mega-caps, exactly what the Efficient Market Hypothesis predicts. We say so.</div></div>
    <div class="tile t-amber"><span class="stamp s-amber">Abstained</span>
      <div>{tip("This week's screen", "<b>Evidence screen.</b> 512 names checked against valuation, quality &amp; health bars. 0 cleared &rarr; the engine surfaces nothing rather than force a pick.")}</div>
      <div class="num">512&nbsp;→&nbsp;0</div><div class="sub">No name cleared the evidence bar. That is the discipline working, not failing.</div></div>
  </div>

  <div class="sec">What the book actually says</div>
  <div class="cols">
    <div class="health">{ring(63.8)}
      <div>{tip('<span class="verdict-chip vc-amber">Concentrated</span>', "<b>Risk concentration.</b> One factor dominates your book's swings. Adding similar names won't diversify — only a different asset class or hedge will.")}</div>
      <p>Solid quality, but one market-wide bet dominates. Your risk is structural, not stock-picking — read the Risk tab before adding.</p></div>
    <div class="vcards">
      <div class="vcard green"><a class="tk" href="{yf('NVDA')}" target="_blank" rel="noopener">NVDA <span class="ar">↗</span></a><div class="vbody">
        <div>{tip('<span class="vhead green">Trend intact</span>', "<b>Above the 200-day average.</b> The long-term trend is up. Process rule: let winners run — don't sell strength early.")}</div>
        <div class="vtext">Above SMA-200. Process says let the winner run — don't sell strength early.</div></div>
        <div class="dots green">●●●●●<span class="off">●</span></div></div>
      <div class="vcard crimson"><a class="tk" href="{yf('LULU')}" target="_blank" rel="noopener">LULU <span class="ar">↗</span></a><div class="vbody">
        <div>{tip('<span class="vhead crimson">Trend broken</span>', "<b>Below the 200-day average.</b> The trend filter says step aside. This is the kind of loser investors tend to hold too long.")}</div>
        <div class="vtext">Closed below SMA-200. The trend filter says step aside — this is the loser you tend to hold.</div></div>
        <div class="dots crimson">●●<span class="off">●●●●</span></div></div>
      <div class="vcard amber"><a class="tk" href="{yf('SPY')}" target="_blank" rel="noopener">BOOK <span class="ar">↗</span></a><div class="vbody">
        <div>{tip('<span class="vhead amber">Risk concentrated · 64%</span>', "<b>Systematic share.</b> 64% of your book's variance comes from market-wide moves, not stock-specific edges.")}</div>
        <div class="vtext">64% of your swings come from one market-wide bet. Another single name will not diversify this.</div></div>
        <div class="dots amber">●●●<span class="off">●●●</span></div></div>
    </div>
  </div>

  <div class="flags">
    <span class="flag">{tip("REDUCE&nbsp;<b>19</b>", "<b>Reduce.</b> 19 holdings whose evidence weakened (trend, risk or valuation). A prompt to review — never an auto sell order.")}</span>
    <span class="flag">{tip("TRIM&nbsp;<b>20</b>", "<b>Trim.</b> 20 names slightly over target weight or risk — consider lightening, not exiting.")}</span>
    <span class="flag">{tip("HOLD&nbsp;<b>11</b>", "<b>Hold.</b> 11 names where evidence is unchanged — no action indicated.")}</span>
    <span class="flag">{tip("ADD-ON&nbsp;<b>14</b>", "<b>Add-on candidate.</b> 14 names with intact trend &amp; room vs risk caps — eligible to scale, if you choose.")}</span>
    <span class="flag" style="border-style:dashed;">no buy/sell calls — evidence only</span>
  </div>
  <div class="foot">RESEARCH ONLY · NOT INVESTMENT ADVICE · HEXAGONAL ARCHITECTURE · BUILT BY TIRTH JOSHI</div>
</div>
"""

st.markdown(CSS, unsafe_allow_html=True)
st.markdown(HTML, unsafe_allow_html=True)
```
