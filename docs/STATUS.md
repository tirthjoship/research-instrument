# STATUS — multi-modal-stock-recommender

**As of:** 2026-06-12
**Branch:** feat/dashboard-v2 (v2 IMPLEMENTED + verified; PR open, NOT yet merged)
**Phase:** Dashboard v2 — built, review-gated; awaiting merge → wrap to maintenance

## Current State

Dashboard v2 fully implemented on `feat/dashboard-v2` (T1–T8). Suite **1628 passing**,
code pre-commit hooks green, 6-tab app launches clean (HTTP 200 / health ok).
Final 3-way independent Opus review: no fabrication, no live vocab violation, no
regressions; flagged items all fixed (dangling "Falsification Lab"→"Trust" refs,
scoped home-hero vocab guard, dead `_GRADE_TONE` removed, generated screens gitignored).

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

1. Merge: confirm CI green on the open PR → develop, merge, then develop → main
   release PR, merge (keep both branches in sync — standing user instruction).
2. After merge: `git rev-list --count origin/main..origin/develop` should be 0.
3. Then close to maintenance (v2 was the sanctioned final UX scope).

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
