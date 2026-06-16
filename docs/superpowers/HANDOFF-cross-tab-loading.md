# HANDOFF — Cross-tab loading overlay + lazy tab rendering

**For:** a fresh Claude Code session that will IMPLEMENT this feature.
**Date prepared:** 2026-06-16
**Branch:** `feat/dashboard-legibility-redesign` (do NOT commit to `develop`/`main`).

## Start here (read in this order, stop when you have enough)
1. `docs/STATUS.md` — current state, run/verify commands, caveats.
2. `docs/superpowers/plans/2026-06-16-cross-tab-loading-and-lazy-tabs.md` — **the plan you execute, task by task.**
3. `docs/superpowers/specs/2026-06-16-cross-tab-loading-and-lazy-tabs-design.md` — the why + exact copy/fonts/motion (read only what a task points at).

## What you are building (one paragraph)
The 6-tab Streamlit dashboard renders tabs eagerly, so the Home tab's synchronous per-holding live
yfinance fetch (`weekly_brief._fetch_card`) blocks the whole script and leaves Screener / Risk / Portfolio
/ Stock Analysis / Trust **blank**. Fix: make tabs **lazy** (`st.tabs(on_change="rerun", key=...)` +
`if tabs[i].open:` guards) so only the active tab runs, and add ONE consistent client-side **loading
overlay** (left→right indeterminate bar + per-tab label + real elapsed timer + shimmer skeleton) that
clears the instant the panel populates. Per-tab `↻ refresh` clears caches and reruns. Reuse `price_cache.py`
(TTL unchanged). Full root-cause evidence is in the spec §1.

## How to execute
- Use **superpowers:subagent-driven-development** — one fresh **Sonnet** subagent per task (per the repo
  model strategy: implementation → Sonnet), review between tasks. Start at **Task 1**.
- TDD is mandatory (write failing test → watch fail → minimal code → pass → commit). Tasks already contain
  the exact tests and code.
- Tasks 1→2→3→4 build it; Task 5 is the gate; Task 6 is manual verification.

## Hard rules / gotchas (do not relearn the hard way)
- **`git checkout data/reports/` before every `make check`** (tracked JSONs lose trailing newlines; ignore that drift).
- Run the **full `make check`** yourself — do not trust a subagent's "green" that only ran pytest (memory: `feedback-verify-full-make-check`).
- **Headless Chrome cannot trigger Streamlit's trusted tab render** — Task 6 visual verification is done by the USER in a real browser. Do not conclude "blank tab = bug" from a headless screenshot (memory: `reference-streamlit-screenshot-lazy-tabs`).
- **v2 component `css=` is component-scoped** — inject the overlay CSS app-wide via `st.markdown`, JS via `st.components.v2.component` (memory: `reference-streamlit-v2-component-css-scope`). Use `insertAdjacentHTML`, never `innerHTML` (security hook blocks it).
- **Fonts:** overlay uses **DM Sans** (label/hint) + **IBM Plex Mono** (timer) — NOT Newsreader. Do NOT change the header: title **Fraunces**, subtitle **IBM Plex Sans**, tabs **DM Sans** stay as-is.
- **Out of scope:** the pre-existing `application/cli.py:2842` mypy error (unrelated, backtest/IC-gate path); changing `price_cache.py` TTLs; streaming/partial render.

## Run / verify
- App: `streamlit run adapters/visualization/dashboard.py --server.port 8560 --server.headless true` → http://localhost:8560
- Tests: `python -m pytest tests/test_tab_loading.py -q` (feature) and full `make check`.
- Approved visual reference (interactive): `.superpowers/brainstorm/cross-tab-loading-mockup.html` (serve via `python3 -m http.server 8570 --directory .superpowers/brainstorm`).

## Definition of done
Spec §2 goals met: no tab blocks another; every tab shows the loading overlay while fetching; it clears on
populate (never blank-vanishes); revisit within TTL is instant; `↻ refresh` works. ADR-058 written. Full
`make check` green (except the known unrelated `cli.py` error). USER confirms in a real browser (Task 6).
```
```
## Ready-to-paste opening prompt for the fresh session
> Implement `docs/superpowers/plans/2026-06-16-cross-tab-loading-and-lazy-tabs.md`. First read
> `docs/STATUS.md`, then the plan, then `docs/superpowers/HANDOFF-cross-tab-loading.md` for the gotchas.
> Use subagent-driven-development with Sonnet subagents, one task at a time starting at Task 1, TDD, commit
> per task. Run the full `make check` yourself (with `git checkout data/reports/` first). Task 6 (visual
> verify) is mine in a real browser — pause and hand it to me. Stay on `feat/dashboard-legibility-redesign`.
