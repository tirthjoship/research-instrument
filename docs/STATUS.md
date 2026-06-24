# STATUS — multi-modal-stock-recommender

**As of:** 2026-06-24
**Branch:** `feat/sp5-forward-gate` (ready for PR → develop)
**Phase:** SP5 COMPLETE — ready for PR

## NEXT ACTION (fresh session — start here)

Create PR: `feat/sp5-forward-gate` → `develop`
- 8 commits, 2364 tests pass, mypy strict clean, verification SHIP
- Then: cut `feat/sp6-dashboard-tabs` off develop (SP6 is next)

## SP Status Summary

| SP | Name | Status | Branch / PR |
|----|------|--------|-------------|
| SP1 | Corroboration core | PR #73 OPEN | `feat/corroboration-engine` |
| SP2 | Candidate surfacing | ✅ merged to develop | — |
| SP3 | Screener revamp | ✅ merged to develop | — |
| SP4 | Portfolio verdict | ✅ merged to develop | — |
| SP5 | Forward gate | ✅ COMPLETE | `feat/sp5-forward-gate` (PR pending) |
| SP6 | Dashboard tabs | brief only | — |
| SP7 | Weekly job reliability | ✅ merged to develop | — |

## Open PRs

- PR #73 (SP1 corroboration core) — open, develop deferred by user
- PR #76 (efficiency pass) — open

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
- `make test-fast` runs ~21s parallel (2364 tests on SP5 branch)
- SP5 depends on SP1 (CorroborationStore weekly snapshots) — note PR #73 still open
- `corroborate` job must run BEFORE `resolve-corroboration` each week
- `store: Any` in CorroborationResolverUseCase — intentional hexagonal compromise (no store port yet)
