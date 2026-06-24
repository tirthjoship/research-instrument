# STATUS — multi-modal-stock-recommender

**As of:** 2026-06-24
**Branch:** `feat/sp6-dashboard-tabs` (= develop HEAD — SP6 brainstorm in progress)
**Phase:** SP6 — Dashboard tabs (brainstorm → spec → plan → implement)

## NEXT ACTION (fresh session — start here)

Continue SP6 brainstorm. Spec brief at:
`docs/superpowers/specs/2026-06-20-sp6-stock-analysis-tabs-brief.md`

Decisions locked so far:
- Q1: Graceful empty state when corroboration store empty (no SP1 dependency block)
- Q2: Decompose `stock_analysis.py` monolith → package + add corroboration sections (Option C)
- Q3: Convergence tier badge on Verdict section + full evidence chain as dedicated "Corroboration" section after Sentiment (Option C)

## SP Status Summary

| SP | Name | Status | Branch / PR |
|----|------|--------|-------------|
| SP1 | Corroboration core | ✅ merged to develop | PR #73 MERGED |
| SP2 | Candidate surfacing | ✅ merged to develop | — |
| SP3 | Screener revamp | ✅ merged to develop | — |
| SP4 | Portfolio verdict | ✅ merged to develop | — |
| SP5 | Forward gate | ✅ merged to develop | PR #79 MERGED |
| SP6 | Dashboard tabs | brainstorm in progress | `feat/sp6-dashboard-tabs` |
| SP7 | Weekly job reliability | ✅ merged to develop | — |

## Open PRs

- PR #76 (efficiency pass) — develop → main, open (release promotion, not a develop concern)
- PR #72 (CI dedup) — fix/ci-dedup-triggers → develop, open
- PR #71 (Questrade holdings) — feat/questrade-holdings → develop, open
- PR #57 (tz-naive fix) — fix/adherence-tz-naive-aware → develop, open

## SP5 Key Decisions (locked — ADR-064)

- Unit: per-ticker-snapshot `(ticker, snapshot_date)`
- Gate: STRONG-tier only, mean 21d excess vs SPY ≥ 50 bps AND bootstrap 95% CI lower bound > 0
- n_min: 30 resolved pairs
- KILL: permanent at first evaluation where n≥30 and gate fails
- Storage: `data/corroboration_samples.jsonl` + `data/corroboration_gate_log.jsonl` (gitignored)
- Weekly job: `scripts/corroboration_weekly_resolve.sh` (Sunday 18:00, launchd)

## Future Enhancement (deferred from SP5)

Source reliability learning loop: update `HarvestedClaim.reliability_weight` per-source based on
proven 21d forward hit-rates. Track as SP5b when SP5 gate verdict is known.

## Gotchas

- `uv run pytest` required (bare pytest fails — pyproject.toml injects --timeout flags)
- `make test-fast` runs ~21s parallel (~2364 tests)
- `corroborate` job must run BEFORE `resolve-corroboration` each week
- `store: Any` in CorroborationResolverUseCase — intentional hexagonal compromise (no store port yet)
