# Cross-tab Loading Overlay + Lazy Tab Rendering — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every dashboard tab render independently (no tab can block another) and show a consistent, honest loading overlay while it fetches, clearing the instant content lands.

**Architecture:** Switch `st.tabs` to lazy execution (`on_change="rerun"` + `tab.open` guards) so only the active tab's `render()` runs — fixing Home's live-fetch from starving downstream tabs. Ship one client-side loading overlay (Streamlit v2 component; CSS injected app-wide via `st.markdown`) that watches all six tab buttons, shows a left→right indeterminate bar + per-tab label + real elapsed timer + shimmer skeleton, and clears via `MutationObserver` when the active panel populates. Add a per-tab `↻ refresh` that clears caches and reruns. Reuse existing `price_cache.py` (TTL unchanged).

**Tech Stack:** Streamlit 1.58 (`st.tabs(on_change=, key=)`, `TabContainer.open`, `st.components.v2.component`, `st.cache_data`), Python 3.12 (mypy strict), pytest.

**Spec:** `docs/superpowers/specs/2026-06-16-cross-tab-loading-and-lazy-tabs-design.md` (read first).

**Reference memories:** `reference-streamlit-v2-component-css-scope` (v2 css= is component-scoped → inject CSS via `st.markdown`; JS via `st.components.v2.component`), `reference-streamlit-screenshot-lazy-tabs` (headless cannot trigger Streamlit's trusted tab render → verify in a real browser), `feedback-verify-full-make-check` (run the full `make check` gate yourself).

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `adapters/visualization/components/tab_loading.py` | Build overlay CSS + JS module; `render_tab_loading(tab_labels)` injects them | **Rewrite** (currently single-tab, hardcodes Newsreader) |
| `tests/test_tab_loading.py` | Unit tests for the CSS + JS builders | **Rewrite** |
| `adapters/visualization/dashboard.py` | Lazy tab wiring + `TAB_LABELS` + `render_tab_loading` + per-tab `↻ refresh` | **Modify** |
| `docs/adr/ADR-058-lazy-tab-rendering-and-cross-tab-loading.md` | Architecture decision record | **Create** |

**Unchanged — must NOT be altered (validated against the mockup + real app):** the header keeps its
existing fonts — app title "Multi-Modal Stock Recommender" in **Fraunces** (32px/600), the statement below
it ("Evidence-based equity research instrument — attribution, not forecast") in **IBM Plex Sans**
(13px/#717885), and the tab labels in **DM Sans** (14px/500). This plan touches only the loading overlay,
tab execution, and the refresh control — it must not change `dashboard.py`'s `ri-app-title`/subtitle
markup or the `.stTabs ... button` font in `components/styles.py`. The overlay deliberately uses the same
family as the surrounding chrome: **DM Sans** for the label/hint, **IBM Plex Mono** for the timer.

**Pre-flight:** confirm working tree is on `feat/dashboard-legibility-redesign` and clean of unrelated changes; the prior single-tab overlay edits (uncommitted `tab_loading.py`, `test_tab_loading.py`, `dashboard.py` wiring) are superseded by this plan and will be overwritten by Tasks 1–4. Run `git checkout data/reports/` before any `make check` (tracked-JSON trailing-newline drift; STATUS caveat).

---

## Task 1: Overlay CSS builder (app fonts + left→right motion)

**Files:**
- Modify: `adapters/visualization/components/tab_loading.py`
- Test: `tests/test_tab_loading.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_tab_loading.py  (replace entire file)
"""Tests for the cross-tab loading overlay builders (CSS + JS)."""

from adapters.visualization.components.tab_loading import (
    build_tab_loading_css,
    build_tab_loading_js,
)

TAB_LABELS = [
    "Loading your book",
    "Building this week’s research shortlist",
    "Computing portfolio risk",
    "Loading your portfolio",
    "Loading stock analysis",
    "Loading the track record",
]


def test_css_has_overlay_classes_and_escalation_states():
    css = build_tab_loading_css()
    for cls in (
        ".scr-load-bar",
        ".scr-load-dot",
        ".scr-load-timer",
        ".scr-load-hint",
        ".scr-load-hint.warn",
        ".scr-load-hint.long",
        ".scr-skeleton",
        ".scr-sk-tile",
    ):
        assert cls in css


def test_css_uses_app_fonts_not_newsreader():
    css = build_tab_loading_css()
    assert "IBM Plex Mono" in css      # timer
    assert "DM Sans" in css            # label/hint
    assert "Newsreader" not in css     # mockup placeholder must be gone


def test_css_bar_moves_left_to_right_and_shimmers():
    css = build_tab_loading_css()
    assert "left:-40%" in css
    assert "left:102%" in css          # segment travels left -> right
    assert "shimmer" in css.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_tab_loading.py -q`
Expected: FAIL — `ImportError`/`AssertionError` (builders not yet in new form; old file may still hardcode Newsreader).

- [ ] **Step 3: Write the CSS builder**

Replace the top of `adapters/visualization/components/tab_loading.py` (module docstring + imports + constants + `build_tab_loading_css`):

```python
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
```

- [ ] **Step 4: Run tests to verify CSS tests pass**

Run: `python -m pytest tests/test_tab_loading.py -k css -q`
Expected: PASS (the `build_tab_loading_js` import will still error other tests — fine; address in Task 2). If collection errors on the missing `build_tab_loading_js`, comment its import temporarily is NOT allowed — instead proceed to Task 2 in the same edit cycle so the module exports both. Re-run after Task 2.

- [ ] **Step 5: Commit (after Task 2 lands the JS builder; CSS + JS commit together)**

Deferred to Task 2, Step 5 (module must export both builders to import cleanly).

---

## Task 2: Overlay JS builder (multi-tab, MutationObserver, escalation, body-level)

**Files:**
- Modify: `adapters/visualization/components/tab_loading.py`
- Test: `tests/test_tab_loading.py`

- [ ] **Step 1: Add the failing JS tests**

Append to `tests/test_tab_loading.py`:

```python
def test_js_contains_all_six_labels():
    js = build_tab_loading_js(TAB_LABELS)
    for label in TAB_LABELS:
        assert label in js


def test_js_has_escalation_thresholds_and_exact_copy():
    js = build_tab_loading_js(TAB_LABELS)
    assert "10000" in js and "90000" in js
    assert "Still fetching live market data — this can take a moment." in js
    assert "Taking unusually long — try reloading the page." in js
    assert "Usually under a second; live look-ups take a few seconds." in js


def test_js_clears_on_populate_and_uses_real_timer():
    js = build_tab_loading_js(TAB_LABELS)
    assert "MutationObserver" in js
    assert "performance.now" in js
    assert "setInterval" in js
    assert "querySelectorAll" in js
    assert 'role="tabpanel"' in js or "role=\\\"tabpanel\\\"" in js


def test_js_no_fake_eta_language():
    js = build_tab_loading_js(TAB_LABELS).lower()
    for banned in ("remaining", "estimated", "eta", "time left"):
        assert banned not in js


def test_js_requires_six_labels():
    import pytest

    with pytest.raises(ValueError):
        build_tab_loading_js(["only", "two"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_tab_loading.py -k js -q`
Expected: FAIL — `build_tab_loading_js` not defined.

- [ ] **Step 3: Implement the JS builder + `render_tab_loading`**

Append to `adapters/visualization/components/tab_loading.py`:

```python
def build_tab_loading_js(tab_labels: list[str]) -> str:
    """ES module for st.components.v2.component. Watches all tab buttons, shows a
    body-level overlay for the active/clicked tab, clears on populate."""
    if len(tab_labels) != 6:
        raise ValueError(f"expected 6 tab labels, got {len(tab_labels)}")
    import json

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
    let idx = 0; buttons().forEach((b,i)=>{{ if(b.getAttribute('aria-selected')==='true') idx=i; }}); return idx;
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
    \"\"\"Inject the cross-tab loading overlay (CSS app-wide + JS v2 component).\"\"\"
    st.markdown(f"<style>{build_tab_loading_css()}</style>", unsafe_allow_html=True)
    component = st.components.v2.component(
        name="scr_tab_loading",
        html="<div></div>",
        js=build_tab_loading_js(tab_labels),
    )
    component()
```

- [ ] **Step 4: Run the full test file**

Run: `python -m pytest tests/test_tab_loading.py -q`
Expected: PASS (all CSS + JS tests).

- [ ] **Step 5: Commit**

```bash
git add adapters/visualization/components/tab_loading.py tests/test_tab_loading.py
git commit -m "feat: cross-tab loading overlay component (CSS+JS builders, app fonts, escalation)"
```

---

## Task 3: Lazy-tab restructure of `dashboard.py`

**Files:**
- Modify: `adapters/visualization/dashboard.py:53-89` (the `st.tabs` call + the six `with tabN:` blocks)

- [ ] **Step 1: Replace the tabs block**

Replace the current `st.tabs(...)` call and the six `with tabN:` blocks with lazy execution. New code:

```python
TAB_LABELS = [
    "Loading your book",
    "Building this week’s research shortlist",
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
```

- [ ] **Step 2: Launch the app and confirm it boots**

Run: `git checkout data/reports/ 2>/dev/null; streamlit run adapters/visualization/dashboard.py --server.port 8560 --server.headless true` (background) then `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8560/`
Expected: `200`, and the server log shows no traceback (only known `use_container_width` / google.generativeai deprecation warnings).

- [ ] **Step 3: Commit**

```bash
git add adapters/visualization/dashboard.py
git commit -m "feat: lazy tab rendering (on_change/open) + per-tab refresh + cross-tab loading wiring"
```

---

## Task 4: ADR-058

**Files:**
- Create: `docs/adr/ADR-058-lazy-tab-rendering-and-cross-tab-loading.md`

- [ ] **Step 1: Write the ADR**

```markdown
# ADR-058: Lazy tab rendering + cross-tab loading overlay

**Status:** Accepted
**Date:** 2026-06-16
**Supersedes/relates:** ADR-057 (Home redesign introduced the blocking per-holding live fetch)

## Context
`st.tabs` renders every tab's content on every rerun (Streamlit default). The Home tab
(`weekly_brief.render` -> `_render_needs_review` -> `_fetch_card`) makes synchronous per-holding
yfinance calls. Because tabs are eager and sequential and Home is index 0, a cold Home fetch blocks
the whole script and every later tab (Screener, Risk, Portfolio, Stock Analysis, Trust) renders blank.
Evidence (2026-06-16): only the Home panel had content; panels 1-5 were empty; Home grew over 45s while
others stayed empty. Non-experts read the blank tabs as "dashboard broken."

## Decision
1. **Lazy tabs:** `st.tabs(..., on_change="rerun", key="main_tabs")` + `if tabs[i].open:` guards so only
   the active tab's `render()` runs. A slow tab can no longer starve the others.
2. **Cross-tab loading overlay:** one client-side component (v2; CSS via `st.markdown`) shows a consistent
   left->right indeterminate bar + per-tab label + real elapsed timer + shimmer skeleton on tab click and
   initial load; clears via `MutationObserver` when the panel populates (success or DATA-GAP). Never
   blank-vanishes; copy escalates at 10s and 90s.
3. **Caching:** reuse existing `price_cache.py` TTLs (15min market / 60min after-hours) — unchanged.
   A per-tab `↻ refresh` clears caches and reruns for an on-demand fresh pull.

## Consequences
- Only the active tab fetches; revisits within TTL are instant (cache hit, overlay flashes < 1 frame).
- Tab data can be up to its TTL old; the refresh button is the freshness lever.
- Headless screenshots cannot trigger Streamlit's trusted tab render; verification is manual in a real
  browser (see reference-streamlit-screenshot-lazy-tabs).
- No streaming/partial render; tabs remain atomic.
```

- [ ] **Step 2: Commit**

```bash
git add docs/adr/ADR-058-lazy-tab-rendering-and-cross-tab-loading.md
git commit -m "docs: ADR-058 lazy tab rendering + cross-tab loading overlay"
```

---

## Task 5: Full gate

- [ ] **Step 1: Run the full Makefile gate yourself**

Run: `git checkout data/reports/ 2>/dev/null; make check`
Expected: black/isort/ruff/secrets pass; mypy clean on `tab_loading.py` and `dashboard.py`; pytest green incl. `tests/test_tab_loading.py`.
Note: the pre-existing `application/cli.py:2842` mypy error is out of scope; if it blocks `make check --all-files`, record it as a known unrelated failure (do not fix here) and confirm the rest is green via `python -m pytest -q` + `python -m mypy --strict adapters/visualization/components/tab_loading.py adapters/visualization/dashboard.py`.

- [ ] **Step 2: Fix any failures in this feature's files, re-run until green.**

---

## Task 6: Live verification (real browser — required)

Headless cannot trigger Streamlit's trusted tab render. Verify manually:

- [ ] App running on `http://localhost:8560`.
- [ ] Click each of the 6 tabs: content populates (no permanent blank); the overlay shows then clears on populate.
- [ ] Overlay label matches the tab (e.g. Screener → "Building this week's research shortlist…").
- [ ] Bar segment moves **left→right**; timer ticks in `0.0s` format; fonts match the app (DM Sans text, IBM Plex Mono timer) — not serif.
- [ ] Switch away from a tab and back within the cache TTL → instant, no visible reload.
- [ ] `↻ refresh` on a tab → re-fetches (overlay shows again).
- [ ] Slow path (a cold Risk/Home fetch) shows the 10s reassurance copy; nothing blank-vanishes.
- [ ] Confirm Screener/Risk/Portfolio/Stock Analysis/Trust are NO LONGER blank (the original bug).

---

## Self-review notes (author)
- Spec §5.1 lazy tabs → Task 3. §5.2 caching/refresh → Task 3 (`_refresh_button`) + reuse price_cache. §5.3 overlay → Tasks 1–2. §5.4 atomic/DATA-GAP → inherent (no content change). §5.5 typography/motion → Task 1 (CSS) + tests. §6 copy → Tasks 1–2 (exact strings) + test. §7 API → Tasks 1–2. §8 honesty → Task 2 no-fake-eta test. §9 testing → Tasks 1,2,5,6. §10 ADR → Task 4.
- Type consistency: builder names `build_tab_loading_css` / `build_tab_loading_js(list[str])` / `render_tab_loading(list[str])` used identically across tasks and the dashboard wiring.
