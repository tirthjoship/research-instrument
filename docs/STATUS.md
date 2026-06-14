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

**OPEN: PR #58** (`fix/screen-trend-health-price-attr` → develop) — fixes a silent bug where the
screener was dead (adapter read `s.close`; `Signal` has `s.price`; `AttributeError` swallowed by a
bare except → `trend_health`=0.0 for all → 0 candidates every week). 1675 green.
⚠️ **BLOCK before main:** the shipped **512→0 ABSTAINED anti-KPI** (Home tile + Screener abstention
funnel) rests on this bug — re-source/remove those honesty claims, else main presents a bug as EMH
evidence. See memory `project-screener-silent-bug`.
**Also pending (separate task):** reconcile the 4 redesign specs on `feat/per-stock-decision-card`
(home/per-stock/risk/screener, 2026-06-13) against the now-shipped Research Instrument.

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
