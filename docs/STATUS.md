# STATUS — multi-modal-stock-recommender

**As of:** 2026-06-16
**Branch:** `feat/dashboard-legibility-redesign` (NOT merged to develop/main).
**Phase:** **Cross-tab loading overlay + lazy tab rendering — spec + plan + handoff written and committed; implementation NOT started.**

## NEXT ACTION (start here)
Execute `docs/superpowers/plans/2026-06-16-cross-tab-loading-and-lazy-tabs.md`, Task 1 first, via
subagent-driven-development (Sonnet subagents), TDD, commit per task. Read
`docs/superpowers/HANDOFF-cross-tab-loading.md` first — it has the start order, gotchas, and the
ready-to-paste opening prompt. Spec: `docs/superpowers/specs/2026-06-16-cross-tab-loading-and-lazy-tabs-design.md`.

## Why (root cause found 2026-06-16)
`st.tabs` renders eagerly; the Home tab's synchronous per-holding live yfinance fetch
(`weekly_brief._fetch_card`) blocks the whole script, so Screener/Risk/Portfolio/Stock Analysis/Trust
render **blank**. Proven via execution trace + all-panels probe (only Home had content). Fix = lazy tabs
(`on_change="rerun"` + `tab.open`) + a consistent cross-tab loading overlay + per-tab refresh; reuse
`price_cache.py` (TTL unchanged). This is also the real cause behind the old "lazy tabs / screener
silently dead" notes.

## How to run / verify
- App: `streamlit run adapters/visualization/dashboard.py --server.port 8560 --server.headless true` → http://localhost:8560
- Tests: `python -m pytest tests/ -q`. Full gate: `make check` — **`git checkout data/reports/` first** (tracked JSON trailing-newline drift; ignore). Run the FULL gate yourself (memory `feedback-verify-full-make-check`).
- Approved visual ref (interactive): `.superpowers/brainstorm/cross-tab-loading-mockup.html` (`python3 -m http.server 8570 --directory .superpowers/brainstorm`).
- **Headless can't trigger Streamlit's trusted tab render** — verify tabs in a REAL browser (memory `reference-streamlit-screenshot-lazy-tabs`).

## Gotchas (carry into implementation)
- v2 component `css=` is component-scoped → inject overlay CSS via `st.markdown`, JS via `st.components.v2.component`; use `insertAdjacentHTML` not `innerHTML` (memory `reference-streamlit-v2-component-css-scope`).
- Overlay fonts: DM Sans (label/hint) + IBM Plex Mono (timer), NOT Newsreader. Header fonts unchanged: title Fraunces, subtitle IBM Plex Sans, tabs DM Sans.
- Out of scope: pre-existing `application/cli.py:2842` mypy error (backtest/IC-gate, unrelated); changing `price_cache.py` TTLs; streaming render.

## Parallel / open (other sessions — do not disturb)
- Risk tab v8 — PR #61 to develop, live eyeball still open (memory `project-risk-tab-redesign-built`).
- Screener redesign shipped; Home + v9 card shipped (ADR-057). Open: verdict-logic-extension decision (memory `project-verdict-logic-extension-question`).

## Recent commits (this session)
`f013ad3` spec · `ad5b852` plan · `a410297` plan font-lock · (HANDOFF + STATUS next).
