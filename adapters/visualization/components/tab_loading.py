"""Cross-tab loading overlay for the Streamlit dashboard.

Streamlit runs no Python on a tab click, and lazy tab renders return the frame
only once content is ready — so a Python ``st.spinner`` cannot fill the gap a
user sees between clicking a tab and its panel painting. This component injects
a client-side overlay that watches every tab button, shows an indeterminate
left->right bar + per-tab label + real elapsed timer + shimmer skeleton, and
clears the instant the active panel populates (success or DATA-GAP). It never
auto-removes on a timeout; long waits escalate the copy instead.

Delivered as a Streamlit v2 custom component (no iframe). CSS is injected
app-wide via ``st.markdown`` because v2 ``css=`` is component-scoped and would
not reach a body-level overlay (memory: reference-streamlit-v2-component-css-scope).
Markup is a fixed literal, inserted with ``insertAdjacentHTML`` (never innerHTML).
"""

from __future__ import annotations

import json

import streamlit as st

# Elapsed-time thresholds for escalating the hint copy (ms).
_WARN_MS = 10000
_CAP_MS = 90000
# Panel innerText length above which we treat it as "populated" and clear.
_CONTENT_TEXT_THRESHOLD = 40

_HINT_INIT = "Usually under a second; live look-ups take a few seconds."
_HINT_WARN = "Still fetching live market data — this can take a moment."
_HINT_CAP = "Taking unusually long — try reloading the page."


def build_tab_loading_css() -> str:
    """Overlay CSS. Uses the app's real fonts (DM Sans label/hint, IBM Plex Mono
    timer) and the approved left->right bar motion."""
    return """
.scr-load-overlay{font-family:'DM Sans',sans-serif;animation:scrFade .15s ease-in;}
@keyframes scrFade{from{opacity:0}to{opacity:1}}
.scr-load-bar{height:3px;background:#EDF0F3;overflow:hidden;position:relative;border-radius:2px;margin-bottom:16px;}
.scr-load-bar>span{position:absolute;height:100%;width:38%;background:#1D4ED8;border-radius:2px;animation:scrSlide 1.05s cubic-bezier(.55,.15,.35,.9) infinite;}
@keyframes scrSlide{0%{left:-40%}100%{left:102%}}
.scr-load-row{display:flex;align-items:center;gap:10px;font-size:14px;color:#717885;margin-bottom:2px;}
.scr-load-dot{width:7px;height:7px;border-radius:50%;background:#1D4ED8;animation:scrPulse 1s ease-in-out infinite;}
@keyframes scrPulse{0%,100%{opacity:.3}50%{opacity:1}}
.scr-load-timer{font-family:'IBM Plex Mono',monospace;font-size:13px;color:#14181F;background:#EDF0F3;padding:2px 8px;border-radius:6px;margin-left:auto;}
.scr-load-hint{font-size:12.5px;color:#717885;margin:2px 0 16px;transition:color .2s;}
.scr-load-hint.warn{color:#1D4ED8;}
.scr-load-hint.long{color:#B45309;}
.scr-load-tiles{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:14px;}
.scr-skeleton{background:linear-gradient(100deg,#EDF0F3 30%,#F6F8FA 50%,#EDF0F3 70%);background-size:200% 100%;animation:scrShimmer 1.3s linear infinite;border-radius:8px;}
@keyframes scrShimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}
.scr-sk-tile{height:78px;}
.scr-sk-line{height:14px;margin:10px 0;}
.scr-sk-card{height:64px;margin-top:12px;}
"""


def build_tab_loading_js(tab_labels: list[str]) -> str:
    """ES module for st.components.v2.component. Watches all tab buttons, shows a
    body-level overlay for the active/clicked tab, clears on populate."""
    if len(tab_labels) != 6:
        raise ValueError(f"expected 6 tab labels, got {len(tab_labels)}")

    labels_js = json.dumps(tab_labels, ensure_ascii=False)
    return f"""
export default function({{ parentElement }}) {{
  const LABELS = {labels_js};
  const WARN_MS = {_WARN_MS}, CAP_MS = {_CAP_MS}, THRESH = {_CONTENT_TEXT_THRESHOLD};
  const INIT = {_HINT_INIT!r}, WARN = {_HINT_WARN!r}, CAP = {_HINT_CAP!r};
  const OV = 'scr-load-overlay';
  const doc = parentElement.ownerDocument;
  const buttons = () => doc.querySelectorAll('.stTabs [data-baseweb="tab-list"] button');
  const panels  = () => doc.querySelectorAll('[role="tabpanel"]');
  const activeIndex = () => {{
    let idx = 0; buttons().forEach((b,i)=>{{ if(b.ariaSelected==='true') idx=i; }}); return idx;
  }};

  function markup(label) {{
    let sk = '<div class="scr-load-tiles">' +
      '<div class="scr-skeleton scr-sk-tile"></div>'.repeat(4) + '</div>' +
      '<div class="scr-skeleton scr-sk-line" style="width:90%"></div>' +
      '<div class="scr-skeleton scr-sk-card"></div><div class="scr-skeleton scr-sk-card"></div>' +
      '<div class="scr-skeleton scr-sk-card" style="width:70%"></div>';
    return '<div class="scr-load-overlay" id="' + OV + '">' +
      '<div class="scr-load-bar" role="progressbar" aria-label="Loading"><span></span></div>' +
      '<div class="scr-load-row"><span class="scr-load-dot"></span>' +
        '<span class="scr-load-lbl">' + label + '\\u2026</span>' +
        '<span class="scr-load-timer" id="scr-load-timer">0.0s</span></div>' +
      '<div class="scr-load-hint" id="scr-load-hint">' + INIT + '</div>' + sk + '</div>';
  }}

  let timer=null, poll=null, obs=null;
  function clear() {{
    if(timer){{clearInterval(timer);timer=null;}}
    if(poll){{clearInterval(poll);poll=null;}}
    if(obs){{obs.disconnect();obs=null;}}
    const o=doc.getElementById(OV); if(o) o.remove();
    delete doc.body.dataset.scrPending;
  }}

  function show(idx) {{
    clear();
    const panel = panels()[idx]; if(!panel) return;
    doc.body.insertAdjacentHTML('beforeend', markup(LABELS[idx] || 'Loading'));
    const o = doc.getElementById(OV);
    const r = panel.getBoundingClientRect();
    o.style.position='fixed'; o.style.top=r.top+'px'; o.style.left=r.left+'px';
    o.style.width=r.width+'px'; o.style.zIndex='5';
    o.style.background=getComputedStyle(doc.body).backgroundColor||'#F4F6F8';
    const t0=performance.now();
    timer=setInterval(()=>{{
      const el=doc.getElementById('scr-load-timer'); if(!el){{clear();return;}}
      const s=(performance.now()-t0)/1000; el.textContent=s.toFixed(1)+'s';
      const h=doc.getElementById('scr-load-hint'); if(!h) return;
      if(s>=90){{h.textContent=CAP;h.className='scr-load-hint long';}}
      else if(s>=10){{h.textContent=WARN;h.className='scr-load-hint warn';}}
    }},100);
    const done=()=>{{ if((panel.innerText||'').trim().length>THRESH) clear(); }};
    obs=new MutationObserver(done); obs.observe(panel,{{childList:true,subtree:true}});
    poll=setInterval(done,120);   // backstop; NO timeout-based removal
  }}

  function wire() {{
    const bs=buttons();
    bs.forEach((b,i)=>{{
      if(b.dataset.scrWired) return; b.dataset.scrWired='1';
      b.addEventListener('click',()=>{{ doc.body.dataset.scrPending=String(i); setTimeout(()=>show(i),0); }});
    }});
    return bs.length;
  }}

  let tries=0;
  const arm=setInterval(()=>{{
    const n=wire();
    if(n>=1){{
      const pend=doc.body.dataset.scrPending;
      if(pend!==undefined){{ const i=parseInt(pend,10);
        if(panels()[i] && (panels()[i].innerText||'').trim().length<=THRESH) show(i); else clear(); }}
      else if(!doc.body.dataset.scrInit){{ doc.body.dataset.scrInit='1'; show(activeIndex()); }}
    }}
    if(n>=6 || ++tries>40) clearInterval(arm);
  }},150);
}}
"""


def render_tab_loading(tab_labels: list[str]) -> None:
    """Inject the cross-tab loading overlay (CSS app-wide + JS v2 component)."""
    st.markdown(f"<style>{build_tab_loading_css()}</style>", unsafe_allow_html=True)
    component = st.components.v2.component(
        name="scr_tab_loading",
        html="<div></div>",
        js=build_tab_loading_js(tab_labels),
    )
    component()
