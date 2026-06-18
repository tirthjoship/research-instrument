# STATUS — multi-modal-stock-recommender

**As of:** 2026-06-17 (session 2)
**Branch:** `feat/efficiency-overhaul` (off `develop`) — Tier 2 complete
**Phase:** Efficiency overhaul (ADR-061) — ready for PR to `develop`

## NEXT ACTION (fresh session — start here)

**Open PR** `feat/efficiency-overhaul` → `develop`:
```bash
make check              # gate: lint + mypy + test-cov ≥90%
make test-smoke         # ~26s, 264 smoke tests
make test-tab tab=risk  # <25s
```

**Then:** user go for `develop` → `main` when ready.

Plan: `docs/superpowers/plans/2026-06-17-efficiency-overhaul.md`
Spec: `docs/superpowers/specs/2026-06-17-efficiency-overhaul-design.md`

## Tier 1 completion status

| Task | Status | Commit |
|------|--------|--------|
| T1: Makefile + xdist + drop -v | ✅ done | `47037ad` + `a83dd58` |
| T2: uv migration + CI workflows | ✅ done | `ece3ed3` |
| T3: pre-push hook | ✅ done | `ef2c978` |
| T4: .gitignore + scripts/ cleanup | ✅ done | `73da34e` |
| T5: CLAUDE.md overhaul | ✅ done | committed |
| T6: CONTEXT.md trim (884→29 lines) | ✅ done | `806b1ec` |

## Tier 2 completion status

| Task | Status | Notes |
|------|--------|-------|
| T7: `cli.py` → `application/cli/` | ✅ done | 38 commands, `python -m application.cli` works |
| T8: `risk.py` → `risk/` package | ✅ done | 29/29 risk tab tests pass; max file 432 LOC |
| T9: smoke suite + tab markers | ✅ done | 264 smoke tests in ~26s; tab targeting works |

## Key wins already landed

- `make test-fast`: 2185 tests in ~35s (was 484s serial+verbose)
- `make test-tab tab=risk`: single-tab targeting in <15s
- `make check`: lint + mypy + test-cov (CI/pre-PR only, not during iteration)
- uv: CI cold install ~4s (was ~45s)
- pre-push hook: eliminates CI auto-fix loop
- CONTEXT.md: 17,800 tokens → ~350 tokens

## Tier 2 plan summary (completed)

**T7:** `application/cli/` package — `_cli_group`, `_deps`, 8 `*_commands.py`, `__main__.py`

**T8:** `adapters/visualization/tabs/risk/` — compose, components, evidence, factor_chart, enb_section, sections, _theme

**T9:** `make test-smoke` + `tab_*` pytest markers on domain + tab test files

## Open items (carry forward)

- `develop` → `main` release still needs explicit user go (not done yet)
- `#57` fix/adherence-tz-naive-aware — unrelated, still open
- Risk readout ~6wks stale (FF publication lag) — documented tradeoff (ADR-060)

## Gotchas

- `data/reports/*.json` regenerates — always unstaged, never commit
- Gemini panel needs `--server.address localhost` + live `GEMINI_API_KEY` in `.env`
- All Tier 1 tasks committed; branch is clean except data/reports/*.json (never commit those)
