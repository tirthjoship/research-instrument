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
