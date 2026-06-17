# STATUS — multi-modal-stock-recommender

**As of:** 2026-06-17
**Branch:** `feat/efficiency-overhaul` (off `develop`) — Tier 1 in progress
**Phase:** Efficiency overhaul (ADR-061) — Tier 1 tasks executing

## NEXT ACTION (fresh session — start here)

**Run Gate 1 verification:**
```bash
make check              # must pass: 2185 tests, ≥90% coverage
time make test-fast     # should be ~35s
make test-tab tab=risk  # should be <15s
ls .git/hooks/pre-push  # must exist
```

**Then start Tier 2** — create sub-tasks and dispatch subagent-driven-development for:
- T7: Decompose `application/cli.py` (3440 LOC) → `application/cli/` package
- T8: Decompose `adapters/visualization/tabs/risk.py` (1710 LOC) → `risk/` package
- T9: Add smoke suite + pytest markers (tab_risk, tab_weekly_brief, etc.)

Plan: `docs/superpowers/plans/2026-06-17-efficiency-overhaul.md`
Spec: `docs/superpowers/specs/2026-06-17-efficiency-overhaul-design.md`

## Tier 1 completion status (as of session end)

| Task | Status | Commit |
|------|--------|--------|
| T1: Makefile + xdist + drop -v | ✅ done | `47037ad` + `a83dd58` |
| T2: uv migration + CI workflows | ✅ done | `ece3ed3` |
| T3: pre-push hook | ✅ done | `ef2c978` |
| T4: .gitignore + scripts/ cleanup | ✅ done | `73da34e` |
| T5: CLAUDE.md overhaul | ✅ done | committed |
| T6: CONTEXT.md trim (884→29 lines) | ✅ done | `806b1ec` |

## Key wins already landed

- `make test-fast`: 2185 tests in ~35s (was 484s serial+verbose)
- `make test-tab tab=risk`: single-tab targeting in <15s
- `make check`: lint + mypy + test-cov (CI/pre-PR only, not during iteration)
- uv: CI cold install ~4s (was ~45s)
- pre-push hook: eliminates CI auto-fix loop
- CONTEXT.md: 17,800 tokens → ~350 tokens

## Tier 2 plan summary (for next session)

**T7 (cli.py decomp):** Split `application/cli.py` into `application/cli/` package.
Pattern: `_cli_group.py` defines `@click.group()`, `_deps.py` has `_build_dependencies()`,
8 `*_commands.py` files each import `cli` from `._cli_group`. `make check` after each submodule.
Token reduction: 32,300 → ~5,000 per edit.

**T8 (risk.py decomp):** Split `adapters/visualization/tabs/risk.py` into `risk/` package:
`compose.py` (entry), `components.py`, `evidence.py`, `factor_chart.py`, `enb_section.py`, `sections.py`.
Token reduction: 19,300 → ~3,200 per edit.

**T9 (smoke suite):** Tag ~60 smoke tests (all Hypothesis + port contracts + critical integration),
add `pytestmark = pytest.mark.tab_risk` etc to tab test files. `make test-smoke` target <15s.

## Open items (carry forward)

- `develop` → `main` release still needs explicit user go (not done yet)
- `#57` fix/adherence-tz-naive-aware — unrelated, still open
- Risk readout ~6wks stale (FF publication lag) — documented tradeoff (ADR-060)

## Gotchas

- `data/reports/*.json` regenerates — always unstaged, never commit
- Gemini panel needs `--server.address localhost` + live `GEMINI_API_KEY` in `.env`
- All Tier 1 tasks committed; branch is clean except data/reports/*.json (never commit those)
