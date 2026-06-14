# STATUS — multi-modal-stock-recommender

**As of:** 2026-06-13
**Branch:** **SHIPPED** — merged to `develop` (PR #53) and released to `main` (PR #54), both
CI-green; `origin/main` ≡ `origin/develop`. **1628 → 1671 tests passing, 94% cov.**
**Phase:** Research Instrument Redesign — **SHIPPED. Project back to maintenance.**

## Current State

The flat v2 dashboard is rebuilt into a distinctive "Research Instrument" (white/petrol design
system, Fraunces + IBM Plex) purely by presenting already-computed honest evidence better — **zero
return predictions**. Executed the staged plan via subagent-driven development (Sonnet
implementers, two independent **Opus** verification passes at the end).

Shipped:
- **Design system** — tokens + fonts + base CSS (`components/styles.py`), shared Plotly template
  (`apply_dossier_template`), hover-tooltip glossary (12 → 39 terms, vocab-guarded), signature
  components: Evidence Ledger, anti-KPI proof-tile, abstention funnel.
- **Home** — Fraunces hero, evidence ledger, 3 honest anti-KPI tiles (512→0 ABSTAINED · 47.4%
  =EMH · Rank-IC 0.004 FALSIFIED, sourced from the real 496-date run), book-health gauge.
- **Screener** — abstention funnel (UNIVERSE 512 → CLEARED 0, renders on empty weeks).
- **Risk** — petrol dossier charts + big-number metric row + plain-English conclusion band.
- **My Portfolio** — progressive disclosure (expanders) + drill-down (Yahoo link + Stock-Analysis
  pre-fill).
- **Trust** — anti-KPI hero + 7 Claim→Test→Result→Decision experiment cards.
- **Stock Analysis** — attributed evidence dossier: E1 sector percentiles (pure
  `domain/peer_relative.py`), E2 attributed analyst panel (`application/analyst_panel.py`), E3
  news context (`application/news_context.py`), E5 fit verdict + falsification badge.
- Durable CDP screenshotter (`scripts/screenshot_dashboard.py`); honest-state snapshot tests.

## Next Action

**Legibility redesign BUILT on branch `feat/dashboard-legibility-redesign`** (stacked on the
`s.close→s.price` fix; 16 commits). 5 of 6 tabs done via subagent-driven dev + per-task Opus review:
Screener (verdict funnel + 4-factor cards), Risk (additive distance-ramp bands), Home (triage strip
+ honest screen tile, 512→0 ABSTAINED gone), My Portfolio (decision-card rows), Trust (512→0
citation re-sourced — it WAS citing the bug at trust.py:129). **1718 tests pass, mypy clean, pre-commit green.**
New pure-domain: `domain/screen_diagnostics.py`, `domain/risk_rubric.py`.

**NEXT SESSION (visual review):**
1. **Run the screener live** (`screen-candidates`) so a fresh `screen_*.json` carries `diagnostics`
   + real candidates — the smoke screenshots used STALE cached data (0 candidates, no diagnostics),
   so Screener cards + Home HAS_CANDIDATES tile showed fallback states. Re-screenshot to eyeball rich states.
2. **Stock Analysis (tab 4) decision-card** = the one deferred tab — build next (see plan).
3. **PR/merge ordering:** PR #58 (the fix) merges to develop first; this branch stacks on it.
   ⚠️ Still BLOCK-before-main: confirm no shipped surface presents 512→0 as EMH/discipline (Home
   tile + Trust now fixed on this branch; verify on develop after merge).
4. Known DATA-GAPs surfaced honestly (not bugs): per-holding **5-signal RAG array doesn't exist** in
   data (Portfolio shows trend_state + "other signals: DATA-GAP"); **vs-Market(1y)** not in brief.
   If wanted, add real computations later. Minor: two different "net beta" numbers on Home (ledger
   uses systematic-share %, triage uses SPY coeff) — future copy pass.
5. Plan: `docs/superpowers/plans/2026-06-14-dashboard-legibility-redesign.md`. Decisions: memory
   `project-whole-site-redesign-decisions`. Mockup: `.superpowers/brainstorm/whole-site/...`.

## Caveats

- **Honesty held under pressure:** FORBIDDEN_WORDS guard + RESEARCH_ONLY on every new surface;
  third-party data is **attributed**, never adopted. Two verification slips were caught + fixed
  mid-run (a "predict" in a Home hero / Stock-Analysis banner; a Rank-IC sourced from a degenerate
  empty file). E4/DCF correctly deferred.
- **Stock Analysis populated dossier** verified by `tests/test_dossier_render.py` (15 tests) +
  a live `analyze_ticker` run, NOT a screenshot — Streamlit's controlled-input doesn't sync under
  headless CDP automation. Empty state screenshotted. Run a ticker live to eyeball the populated layout.
- `git checkout data/reports/` before any pre-commit/CI verify (tests strip trailing newlines from
  2 tracked JSONs: `divergence_ic_21d.json`, `momentum_discipline.json`).
- Standing watch (unchanged): ADR-048/051 discipline forward gate resolves ~mid-July 2026 (weekly
  Saturday job); ~Dec 2026 behavior-gap review.
