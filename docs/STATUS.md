# STATUS — multi-modal-stock-recommender

**As of:** 2026-06-12
**Branch:** develop ≡ main (Dashboard v2 SHIPPED + merged; docs follow-up on docs/v2-wrap)
**Phase:** Maintenance — v2 was the sanctioned final UX scope; no new feature work

## Current State

Dashboard v2 SHIPPED 2026-06-12: PR #46 → develop, release PR #47 develop → main, both
CI-green and merged; `origin/main..origin/develop` = 0. Suite **1628 passing**, code
pre-commit hooks green, 6-tab app launches clean (HTTP 200 / health ok). Final 3-way
independent Opus verification (conformance / honesty-drift / integration): no fabrication,
no live vocab violation, no regressions; all flagged items fixed pre-merge (dangling
"Falsification Lab"→"Trust" refs incl. `domain/fit.py`, fabricated Trust claim reverted,
scoped vocab guards added, dead `_GRADE_TONE` removed, generated screens gitignored).
Docs (README/CONTEXT/PHASE_LOG + this file) updated on `docs/v2-wrap` (follow-up PR).

Delivered:
- **Theme/glossary** (T1): v2 tokens, card hover, `.section-chip`/`.tip`, `glossary.py`.
- **Builders** (T2): `snowflake.py`, `scorecard.py` (vocab-guarded, XSS-escaped).
- **Batch fit** (T3): `application/batch_fit_use_case.py` — ticker/CSV parse (BOM-safe,
  25-cap), per-name engine, DATA_GAP failure rows, `default_fit_fn`.
- **Home** (T4): book-health hero + gauge, attention cards, week strip.
- **Screener** (T5): screen-history strip + check-your-own-list upload scoreboard
  (renders on abstention weeks too).
- **Stock Analysis** (T6): section chips, evidence snowflake (reuses cached fit).
- **Trust** (T7): falsification_lab→trust, methodology absorbed (four rules + glossary),
  6-tab router, trophy grid.

## Next Action

1. Merge the `docs/v2-wrap` follow-up PR (README/CONTEXT/PHASE_LOG/STATUS) → develop →
   main, keeping both in sync (`git rev-list --count origin/main..origin/develop` = 0).
2. No feature work queued. Project is in maintenance.
3. Standing watch: ADR-048/051 discipline forward gate resolves ~mid-July 2026 via the
   weekly Saturday job (`scripts/discipline_weekly_review.sh`); ~Dec 2026 behavior-gap review.

## Caveats

- All current screen artifacts abstain (0 candidates) → live snowflake won't render
  for any real ticker; expected. Factor-axis branch is fixture-tested only.
- `data/reports/screen_20*.json` now gitignored (generated weekly output); curated
  `insider_cluster_falsification_2024.json` + `screen_ic_*` exhibits stay tracked.
- Test runs strip trailing newlines from 2 tracked `data/reports/*.json` —
  `git checkout data/reports/` before any pre-commit/CI verify.
- RESEARCH_ONLY + FORBIDDEN_WORDS invariant holds on every new surface. Trust/
  weekly_brief/glossary legitimately reference buy/sell/predict in falsification/
  educational context — guarded by SCOPED tests, not whole-module scans (by design).
- Wrap timeline: post-v2 → maintenance. Calendar: mid-July gate read; Dec review.
