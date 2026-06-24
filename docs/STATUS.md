# STATUS — multi-modal-stock-recommender

**As of:** 2026-06-23
**Branch:** `develop` (working branch)
**Phase:** SP5 designed — ready for writing-plans → implementation

## NEXT ACTION (fresh session — start here)

SP5: Hypothesis #9 Forward Gate — invoke `superpowers:writing-plans` with:
- Spec: `docs/superpowers/specs/2026-06-23-sp5-hypothesis9-forward-gate-design.md`
- Branch: `feat/sp5-forward-gate` off `develop`
- Task 1 MUST be ADR-064 commit before any resolver code

## SP Status Summary

| SP | Name | Status | Branch / PR |
|----|------|--------|-------------|
| SP1 | Corroboration core | PR #73 OPEN | `feat/corroboration-engine` |
| SP2 | Candidate surfacing | ✅ merged to develop | — |
| SP3 | Screener revamp | ✅ merged to develop | — |
| SP4 | Portfolio verdict | PR #78 OPEN | `feat/sp4-portfolio-verdict` |
| SP5 | Forward gate | ✅ DESIGNED | `feat/sp5-forward-gate` (not started) |
| SP6 | Dashboard tabs | brief only | — |
| SP7 | Weekly job reliability | ✅ merged to develop | — |

## Open PRs

- PR #73 (SP1 corroboration core) — open, develop deferred by user
- PR #76 (efficiency pass) — open
- PR #78 (SP4 portfolio verdict) — open, implementation complete + verified

## SP5 Key Decisions (locked — see ADR-064)

- Unit: per-ticker-snapshot `(ticker, snapshot_date)`
- Gate: STRONG-tier only, mean 21d excess vs SPY ≥ 50 bps AND bootstrap 95% CI lower bound > 0
- n_min: 30 resolved pairs
- KILL: permanent at first evaluation where n≥30 and gate fails
- Storage: `data/corroboration_samples.jsonl` + `data/corroboration_gate_log.jsonl`
- ADR-064 committed as Task 1 before any resolver runs

## Future Enhancement (deferred from SP5)

Source reliability learning loop: update `HarvestedClaim.reliability_weight` per-source based on
proven 21d forward hit-rates. Deferred until SP5 gate resolves — if SP5 KILLs the signal,
the loop was never needed. Track as SP5b when SP5 verdict is known.

## ADRs Written This Session

- ADR-063: SP3 screener blend formula (retroactive — equal-weight 50/50 factor + tier)
- ADR-064: SP5 forward gate parameters (pre-registration lock)

## Gotchas

- `uv run pytest` required (bare pytest fails — pyproject.toml injects --timeout flags)
- `make test-fast` runs ~21s parallel (2316 tests on develop + SP4)
- SP5 depends on SP1 (CorroborationStore weekly snapshots) — implement after PR #73 merges
- `ResolverPricePort.price_at(ticker, date)` is a new port — needs yfinance adapter + fake
