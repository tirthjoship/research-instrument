# Design — Cross-tab loading overlay + lazy tab rendering

**Date:** 2026-06-16
**Status:** Approved (brainstorm), ready for implementation plan
**Branch (target):** `feat/dashboard-legibility-redesign` (or a dedicated `feat/cross-tab-loading` worktree)
**Related:** ADR-057 (Home / decision-card redesign — introduced the blocking live fetch), `reference-streamlit-screenshot-lazy-tabs` (memory), `reference-streamlit-v2-component-css-scope` (memory)
**ADR to write:** ADR-058 — Lazy-tab rendering + cross-tab loading

---

## 1. Problem

The Streamlit dashboard (`adapters/visualization/dashboard.py`) renders six tabs eagerly. Streamlit
runs **every** `with tabN:` block on every script run (confirmed: Streamlit docs — "all tab content runs
on every rerun, regardless of which tab is active"; the app does not use the new `on_change`/`tab.open`
lazy pattern).

The **Home** tab (`tabs/weekly_brief.py` → `render()` → `_render_needs_review()` → `_fetch_card()`) makes
**synchronous, per-holding live yfinance fetches** (`fetch_ticker_info`, `fetch_prices`,
`fetch_price_history` from `adapters/visualization/price_cache.py`; `fetch_earnings_history` from
`adapters/data/earnings_history_adapter.py`). On a cold cache these run sequentially and slowly. Because
tabs are eager and sequential and Home is tab index 0, **Home blocks the whole script before any later tab
executes** — so Screener, Risk, My Portfolio, Stock Analysis, and Trust render **blank**.

### Evidence (this session, 2026-06-16)
- Execution trace (prints in `dashboard.py`): `M1 after st.tabs` ✓, `M2 entering tab0` ✓, `M2b tab0 done`
  ✗, `M3 entering tab1` ✗ — `render_brief()` enters but never returns within the window.
- All-panels probe: only `panel0` (Home) had content (1367 chars); panels 1–5 were 0 chars.
- 45 s later: Home grew 1367 → 3765 chars (slow, making progress — not a hard hang); panels 1–5 still 0.
- This is almost certainly the real cause behind the older "lazy tabs / screener silently dead" notes,
  which mis-attributed the blank non-default panels to lazy rendering.

The previously shipped single-tab loading overlay (`components/tab_loading.py`) sat on top of an
already-blank Screener panel and timed out at 15 s with no content — surfacing, not causing, the bug.

## 2. Goals

1. **Fix the root cause:** a slow tab must never block other tabs.
2. **Consistent loading affordance on every tab** while it fetches, so a non-expert never assumes the
   dashboard is broken.
3. **Never blank-vanish:** the loading state clears only when content actually lands (success *or*
   DATA-GAP), or escalates its copy — it is never silently removed on a timeout.
4. **Revisiting a tab does not force a visible reload** when data is still cached; an on-screen control
   gives a manual fresh pull.

## 3. Non-goals

- **Do not change `price_cache.py` TTLs** (`_TTL_MARKET_HOURS = 15*60`, `_TTL_AFTER_HOURS = 60*60`,
  `_PRICE_HISTORY_TTL = 60*60`). They are infra-wide (used by multiple tabs) and changing them risks
  staleness across consumers. Freshness-on-demand is delivered by the per-tab refresh button instead.
- **No streaming / partial render** (layout-first, values-later via fragments). Streamlit renders a tab
  atomically; we keep that. Not worth the complexity.
- **Not fixing** the unrelated pre-existing `application/cli.py:2842` mypy error (backtest/IC-gate path).

## 4. Existing infrastructure referenced

| Concern | Where | Reuse / change |
|---|---|---|
| Tab wiring | `adapters/visualization/dashboard.py` (`st.tabs(...)`, six `with tabN:` blocks) | **Change** to lazy |
| Loading overlay (single-tab) | `adapters/visualization/components/tab_loading.py` + `tests/test_tab_loading.py` | **Rewrite** to multi-tab |
| Data caching | `adapters/visualization/price_cache.py` (`@st.cache_data`, market/after-hours TTL) | **Reuse unchanged** |
| Home blocking fetch | `tabs/weekly_brief.py` `_fetch_card()` / `_render_needs_review()` | unblocked by lazy tabs |
| Tab render entry points | `weekly_brief.render(...)`, `research_candidates.render(reports_dir=...)`, `risk.render(path=...)`, `positions.render(db_path=...)`, `stock_analysis.render()`, `trust.render(...)` | called under `tab.open` guard |
| Privacy guard | `application/runtime_guard.is_local_runtime()` | unchanged |
| v2 component + CSS scope | memory `reference-streamlit-v2-component-css-scope` | followed (CSS via `st.markdown`, JS via `st.components.v2.component`) |
| Streamlit version | 1.58 — `st.tabs(on_change=..., key=..., default=...)` and `TabContainer.open` confirmed present | required |
| Fonts (REAL app — authoritative over the mockup) | `components/styles.py` + `dashboard.py` header: title **Fraunces** (32px/600); subtitle "Evidence-based equity research instrument — attribution, not forecast" **IBM Plex Sans** (13px/#717885); tab labels **DM Sans** (14px/500); body/cards **DM Sans**/**Inter**; mono **IBM Plex Mono** | overlay must match these |
| Palette | `--accent:#1D4ED8`, `--hair:#EDF0F3`, `--muted:#717885`, `--ink:#14181F`, warning amber `#B45309` | matched |

## 5. Design

### 5.1 Lazy tab execution
```python
TAB_LABELS = [
    "Loading your book",                       # 0 Home
    "Building this week’s research shortlist",  # 1 Screener
    "Computing portfolio risk",                # 2 Risk
    "Loading your portfolio",                  # 3 My Portfolio
    "Loading stock analysis",                  # 4 Stock Analysis
    "Loading the track record",                # 5 Trust
]
tabs = st.tabs(
    ["Home", "Screener", "Risk", "My Portfolio", "Stock Analysis", "Trust"],
    on_change="rerun",
    key="main_tabs",
)
render_tab_loading(TAB_LABELS)  # inject overlay component once, before the guarded blocks

render_fns = [render_brief, render_candidates, render_risk,
              render_portfolio, render_analysis, render_trust]
for i, render_fn in enumerate(render_fns):
    if tabs[i].open:
        with tabs[i]:
            render_fn()
```
- Default open tab = Home (index 0). Only the active tab's `render_fn` runs → Home's cold fetch can no
  longer starve later tabs.
- `on_change="rerun"` makes a tab click trigger a server rerun (a real round-trip the overlay covers).
- Tab-local imports stay as today (inside each block).

### 5.2 Caching + per-tab refresh
- Underlying fetches keep using `price_cache.py` (`@st.cache_data`, existing TTL). First open of a tab on
  a cold cache → real fetch (overlay shows). Revisit within TTL → cache hit → near-instant, overlay
  flashes <1 frame and clears (no visible reload).
- Each tab gets a small **`↻ refresh`** control, top-right of the tab content (mirrors the Screener
  view-toggle placement: `st.columns([3,1], vertical_alignment="bottom")`, control in the right column).
  On click it clears that tab's cached data and reruns:
  ```python
  if st.button("↻ refresh", key=f"refresh_{tab_key}"):
      st.cache_data.clear()   # fresh pull on next render
      st.rerun()
  ```
  (`st.cache_data.clear()` clears all `@st.cache_data` entries — acceptable for an explicit manual
  refresh; a scoped `fetch_prices.clear()` per-function variant is an allowed refinement.)

### 5.3 Loading overlay component (rewrite of `tab_loading.py`)
Client-side, delivered via `st.components.v2.component` (no iframe) with CSS injected app-wide through
`st.markdown` (per `reference-streamlit-v2-component-css-scope` — v2 `css=` is component-scoped and would
not reach a body-level overlay).

**Rendered outside the React-controlled panel.** The overlay is appended to `document.body` as a
`position:fixed` element, geometry derived from the active `[role="tabpanel"]`'s bounding box at show
time (top below the tab strip; left/width matching the panel). It is **not** inserted into the panel via
`insertAdjacentHTML` (avoids React mount/reconciliation collisions — the panel re-renders on the lazy
rerun).

**Behaviour (JS):**
1. On load, arm a listener on each of the six tab buttons (`.stTabs [data-baseweb="tab-list"] button`).
2. Show the overlay (a) on the default tab at initial load and (b) when any tab button is clicked, using
   that tab index's label from `TAB_LABELS`.
3. Start a wall-clock elapsed timer (`performance.now()`, updated every 100 ms, format `"%.1fs"`).
4. A `MutationObserver` on the active `[role="tabpanel"]` clears the overlay the moment substantive
   content lands (real content OR an error/DATA-GAP card — both count). No removal on a timer.
5. Escalation copy (timer keeps running, overlay stays):
   - `t ≥ 10 s` → hint becomes the reassurance line (accent colour).
   - `t ≥ 90 s` → hint becomes the long-wait line (amber colour).
6. Markup is a fixed literal; insert with `insertAdjacentHTML` (never `innerHTML`).

### 5.4 Atomic render + DATA-GAP
A tab's layout and values arrive together when its `render_fn` completes. There is no half-filled state.
If a value cannot be fetched, the tab renders the existing honest **DATA-GAP / "—"** marker — never a
blank box and never a fabricated number.

### 5.5 Typography & motion (exact — REAL app fonts, not the mockup's)
The brainstorm mockup used `Newsreader` as a placeholder serif. **The real overlay must use the app's
actual fonts** so it reads as native and "remains the same" as the surrounding chrome. The already-shipped
`tab_loading.py` hardcodes `Newsreader` — that is a drift to **fix** in this work.

| Element | Font | Size / colour |
|---|---|---|
| App title "Multi-Modal Stock Recommender" (unchanged) | **Fraunces** 600 | 32px / `#14181F` |
| Subtitle below the title (unchanged) | **IBM Plex Sans** | 13px / `#717885` |
| Tab labels (unchanged) | **DM Sans** 500 | 14px |
| Overlay label ("Loading your book…") + hint lines | **DM Sans** (match tabs/body; inherit app default) | label 14px `#717885`; hint 12.5px |
| Overlay elapsed timer | **IBM Plex Mono** | 13px `#14181F`, pill bg `#EDF0F3` |

**Motion (must be in the overlay, exactly as the approved mockup):**
- **Progress bar — moving left→right (the "phasing" the user called out):** a 3px track (`#EDF0F3`) with a
  38%-wide accent (`#1D4ED8`) segment that slides across, looping. Keyframe `0%{left:-40%} → 100%{left:102%}`,
  `1.05s cubic-bezier(.55,.15,.35,.9) infinite` — segment always travels left to right.
- **Pulsing dot:** `1s ease-in-out infinite`, opacity `.3↔1`.
- **Skeleton shimmer:** diagonal gradient sweep, `1.3s linear infinite`; layout = 4 tiles (78px) + one
  90%-width line + three cards (last 70% width).
- **Timer:** ticks every 100 ms, format `"%.1fs"` (`0.0s`, `2.3s`, `11.0s`).
- Overlay fade-in `.15s ease-in`.

## 6. Exact copy (must match implementation verbatim)

| Element | Text |
|---|---|
| Per-tab label (suffix `…`) | Home: `Loading your book` · Screener: `Building this week’s research shortlist` · Risk: `Computing portfolio risk` · My Portfolio: `Loading your portfolio` · Stock Analysis: `Loading stock analysis` · Trust: `Loading the track record` |
| Initial hint (`< 10 s`) | `Usually under a second; live look-ups take a few seconds.` |
| Reassurance (`≥ 10 s`) | `Still fetching live market data — this can take a moment.` |
| Long-wait cap (`≥ 90 s`) | `Taking unusually long — try reloading the page.` |
| Timer | `"%.1fs"` (e.g. `0.0s`), tick every 100 ms |
| Refresh control | `↻ refresh` |

## 7. Component API

`adapters/visualization/components/tab_loading.py`:
- `build_tab_loading_css() -> str` — the overlay CSS (classes `.scr-load-bar`, `.scr-load-dot`,
  `.scr-load-timer`, `.scr-load-hint`, `.scr-load-hint.warn`, `.scr-load-hint.long`, `.scr-skeleton`,
  `.scr-sk-tile`/`.scr-sk-line`/`.scr-sk-card`; shimmer/slide/pulse keyframes; palette + motion + fonts
  per §5.5). Label/hint use **DM Sans** (not Newsreader); timer uses **IBM Plex Mono**. The `scrSlide`
  keyframe must move the bar segment left→right (`0%{left:-40%} 100%{left:102%}`, 1.05s).
- `build_tab_loading_js(tab_labels: list[str]) -> str` — ES module
  (`export default function({ parentElement }) { ... }`). Constants `WARN_MS = 10000`, `CAP_MS = 90000`,
  the three copy strings, the label array. Uses `parentElement.ownerDocument`, `querySelectorAll`,
  `MutationObserver`, `performance.now`, `setInterval`.
- `render_tab_loading(tab_labels: list[str]) -> None` — `st.markdown(f"<style>{...}</style>",
  unsafe_allow_html=True)` for the CSS, then `st.components.v2.component(name="scr_tab_loading",
  html="<div></div>", js=build_tab_loading_js(tab_labels))` and call it.

## 8. Honesty invariants
- No `FORBIDDEN_WORDS` (note: avoid "predict"/"forecast"; the labels are operational and clear).
- No fake ETA / countdown — only a real elapsed timer (enforced by test: no `remaining`/`estimated`/
  `eta`/`time left`).
- DATA-GAP is never faked; failed fetches render the honest marker.

## 9. Testing

**TDD units** (`tests/test_tab_loading.py`, rewritten):
- `build_tab_loading_js` contains all six labels.
- Contains `WARN_MS`/`10000` and `CAP_MS`/`90000`, plus the exact reassurance and cap strings.
- Contains `MutationObserver`, `performance.now`, `setInterval`, `querySelectorAll`, and targets
  `[role="tabpanel"]` and the tab-list buttons.
- No fake-ETA language.
- `build_tab_loading_css` contains `.scr-load-bar`, `.scr-skeleton`, `shimmer`, `.scr-load-hint.warn`,
  `.scr-load-hint.long`.
- `build_tab_loading_css` uses the app fonts and **not** Newsreader: asserts `IBM Plex Mono` (timer) and
  `DM Sans` (label/hint) are present and `Newsreader` is absent.
- `build_tab_loading_css` keeps the left→right bar motion: asserts the slide keyframe with `left:-40%` and
  `left:102%`.
- `build_tab_loading_js` raises (or is guarded) if `tab_labels` length ≠ 6.

**Gate:** full `make check` (pre-commit + mypy strict + pytest + coverage) must pass. `st.fragment`-style
`# type: ignore[misc]` only where the gate requires it.

**Manual verification (required):** headless Chrome cannot trigger Streamlit's *trusted* tab render
(established this session; see `reference-streamlit-screenshot-lazy-tabs`). Verify in a real browser:
each tab populates on click; the overlay shows then clears on populate; revisit within TTL is instant;
`↻ refresh` re-fetches; slow path shows the 10 s reassurance; nothing blank-vanishes.

## 10. Risks / notes
- **Lazy re-fetch:** when a tab's cache entry has expired (TTL), reopening re-fetches and the overlay
  shows again — expected; the refresh button is the manual lever.
- **price_cache TTL reuse:** we deliberately keep the existing 15 min / 60 min TTL rather than a
  session-only cache; revisits within TTL are instant. If a longer session-persist is wanted later, that
  is a separate explicit decision (do not silently widen the infra TTL).
- **Overlay geometry:** position is computed from the active tabpanel's bounding box; must update if the
  window resizes mid-load (recompute on show; acceptable to not track live resize during a load).
- **Cache-hit flash:** an instant cache hit shows the overlay for <1 frame; acceptable.

## 11. Out of scope
Streaming/partial render; changing `price_cache` TTL; the `cli.py:2842` mypy error; any change to tab
*content* beyond adding the per-tab refresh control.
