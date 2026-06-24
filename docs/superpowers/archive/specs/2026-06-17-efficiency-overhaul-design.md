# Efficiency Overhaul Design
**Date:** 2026-06-17
**Status:** Approved — ready for implementation
**ADR reference:** ADR-061 (direction; this spec operationalises it)
**Branch target:** `feat/efficiency-overhaul` off `develop`

---

## Problem Statement

Every development session pays compounding overhead before real work starts:

| Bottleneck | Current cost | Root cause |
|------------|-------------|------------|
| `make check` gate | 484s (8 min) | Serial execution, `-v` verbose, coverage every run |
| CLI file read | ~32,300 tokens | `cli.py` is 3440 LOC — one monolithic file |
| Risk tab file read | ~19,300 tokens | `risk.py` is 1710 LOC — one monolithic file |
| CONTEXT.md if read | ~17,800 tokens | 884-line session-history file, no "don't auto-read" guard |
| CI failures on push | Frequent | Pre-commit auto-fixes files → CI fails first run, passes second |
| CI cold install | ~45s per run | No pip/uv caching; reinstalls all deps every push |
| No targeted test path | n/a | Only `make check` exists; no fast-iteration target |

**Goal:** reduce per-session token overhead ~60%, cut gate from 8 min → <2 min, eliminate the CI auto-fix loop, and give Claude clear navigation so it reads the right 300 LOC not the wrong 3400.

---

## Scope

Two tiers within one spec. Tier 1 delivers ~80% of the value; Tier 2 completes the remaining 20%.

---

## Tier 1 — Quick wins, low risk (~2.5 hours)

### T1-1: Makefile overhaul

Replace the current 6-target Makefile with a tiered test system:

```makefile
.PHONY: test test-fast test-tab test-domain test-adapters test-cov lint typecheck setup check

# Iteration targets (fast — no coverage)
test-fast:
	pytest tests/ -q -n auto --tb=short

test-tab:
	pytest tests/ -q -n auto -m "tab_$(tab)" --tb=short
	# Usage: make test-tab tab=risk

test-domain:
	pytest tests/domain/ -q -n auto --tb=short

test-adapters:
	pytest tests/adapters/ -q -n auto --tb=short

# Full suite (no coverage — for pre-commit iteration)
test:
	pytest tests/ -n auto --tb=short

# Coverage gate (CI + pre-PR only)
test-cov:
	pytest tests/ -n auto --cov=domain --cov=adapters --cov=application \
	    --cov-fail-under=90 --tb=short

# Quality checks
lint:
	pre-commit run --all-files

typecheck:
	mypy domain/ adapters/ application/ --strict

# Full gate — CI and pre-PR only, not during iteration
check: lint typecheck test-cov

setup:
	uv sync
	pre-commit install
```

**Key changes from current:**
- `-v` removed everywhere (verbose output is token-heavy and noise during iteration)
- `-n auto` added (xdist parallelism — conditional on T1-2 audit)
- `test-tab tab=<name>` for targeted tab testing
- `make setup` uses `uv sync` instead of `pip install -e ".[dev]"`

### T1-2: Test isolation audit + pytest-xdist

Before adding `-n auto` to all targets, audit for shared mutable state:

**Check list:**
- SQLite temp files in tests: do multiple tests write to the same path?
- `conftest.py` fixtures: any session-scoped fixtures that write to disk?
- `tests/fakes/`: all stateless (new instance per test)?
- Any `tmp_path` vs hardcoded `data/` paths in tests?

If all clean → add `pytest-xdist` to `[dev]` deps in `pyproject.toml` and ship `-n auto`.
If issues found → fix isolation first (separate task per violation), then add xdist.

**Expected outcome:** 484s → ~85s (8 cores / 6 workers, ~5.7× speedup).

### T1-3: uv migration

Replace pip with uv across all surfaces:

- `pyproject.toml`: no change needed (uv reads it natively)
- `Makefile`: `make setup` → `uv sync` (done in T1-1)
- `.github/workflows/ci.yml`: replace pip install block:
  ```yaml
  - uses: astral-sh/setup-uv@v4
    with:
      version: "latest"
  - name: Install dependencies
    run: uv sync --extra dev --extra dashboard
  ```
- `.github/workflows/lint.yml`: same replacement
- Add `uv.lock` to git (reproducible CI builds)
- Add `uv.lock` update note to `CLAUDE.md` (run `uv lock` after dep changes)

**Expected outcome:** CI cold install 45s → ~4s.

### T1-4: Pre-push hook (eliminate CI auto-fix loop)

Current pain: black/whitespace reformats files locally → first CI push fails → re-push passes.

Add a git pre-push hook that runs pre-commit before every push:

```bash
# .git/hooks/pre-push (created via pre-commit config, not manually)
```

In `.pre-commit-config.yaml`, add a `default_stages: [pre-push]` for the formatting hooks OR document in `CLAUDE.md`: always run `pre-commit run --all-files` before `git push`.

The simpler path: add `make pre-push` target that runs `pre-commit run --all-files && git push "$@"` and document it as the push command in CLAUDE.md.

**Expected outcome:** zero CI failures from formatting auto-fixes.

### T1-5: CLAUDE.md overhaul

Replace the current 117-line CLAUDE.md with an updated version covering:

**New sections to add:**

1. **Model routing table** (project-specific, complements global CLAUDE.md):

| Task | Model |
|------|-------|
| Tab/adapter edits, CLI commands | Sonnet |
| Domain model changes | Sonnet |
| Architecture decisions, ADRs | Fable (main loop) |
| Debugging test failures | Opus |
| File lookup, grep, search | Haiku |
| Full codebase exploration | Sonnet (Explore agent) |
| Code review pre-PR | Opus |

2. **Testing discipline table** (mandatory, not advisory):

| Change type | Run immediately | Before commit | Before PR |
|-------------|-----------------|---------------|-----------|
| Any tab tweak | `make test-tab tab=<name>` | `make test-fast` | `make check` |
| CLI command | `pytest tests/test_<cmd>.py -q` | `make test-fast` | `make check` |
| Domain model | `make test-domain` | `make test-fast` | `make check` |
| Adapter change | `make test-adapters` | `make test-fast` | `make check` |
| Cross-cutting change | `make test-fast` | `make test-fast` | `make check` |

3. **CONTEXT.md guard** — explicit note: `CONTEXT.md` is a historical timeline (17,800 tokens). Do NOT read it at session start or during exploration. Open only if user explicitly asks for project history.

4. **Module map** (placeholder pre-Tier 2; updated post-decomp):
```
# Key files — where to look
application/cli.py              CLI entry point (3440 LOC — Tier 2 decomp target)
adapters/visualization/tabs/    One file per dashboard tab
domain/models.py                Core dataclasses
domain/ports.py                 All port interfaces
tests/fakes/                    Test doubles for all ports
```

### T1-6: CONTEXT.md trim

Current: 884 lines, 17,800 tokens. Loaded if Claude explores root dir.

Action: trim to a 1-page index (~50 lines) pointing to the real docs:
- Phase history → `docs/PHASE_LOG.md`
- Current state → `docs/STATUS.md`
- Architecture decisions → `docs/adr/`
- Skills → `docs/SKILL_ROUTING.md`

**Expected outcome:** if CONTEXT.md is ever read, costs ~500 tokens not 17,800.

### T1-7: Repo cleanup

- `audit_sentiment.py` (root, 76 LOC): move to `scripts/audit_sentiment.py` — keeps it but out of root scan path
- Verify `.gitignore` contains: `.mypy_cache/`, `.pytest_cache/`, `.ruff_cache/`, `.hypothesis/`
- Remove `research/` directory entries that are now stale (if any)

**Gate 1 (must pass before Tier 2):**
- `make check` green (2145 tests, ≥90% coverage, mypy strict, ruff clean)
- `git push --dry-run` triggers pre-push hook cleanly
- CI push green with no auto-fix re-push needed
- `make test-fast` completes in <90s
- `make test-tab tab=risk` completes in <15s

---

## Tier 2 — Structural improvements (~5 hours, adjacent session)

Tier 2 depends on Tier 1 gate passing. Each item is independently gate-guarded.

### T2-1: Module decomposition — cli.py

Split `application/cli.py` (3440 LOC) into `application/cli/` package.

**Target structure:**

```
application/cli/
├── __init__.py          # exports cli group; imports all submodules
├── _deps.py             # _build_dependencies(), shared helpers
├── ml_commands.py       # pretrain, run-tournament, evaluate-last-week, backtest, shap-report
├── scan_commands.py     # daily-scan, validate-3b, scan-opportunities, resolve-calls, opportunity-report
├── brief_commands.py    # weekly-brief, _build_weekly_brief, _prefetch_cited_cases
├── portfolio_commands.py # portfolio-verdict, holdings-risk, holdings-risk-calibrate
├── screen_commands.py   # screen-candidates, backtest-screen
├── validation_commands.py # adherence-report, discipline flags, audit-dimensions, validate-divergence-ic
├── data_commands.py     # wiki, backfill, drip-backfill, backfill-history
└── backtest_commands.py # backtest-trend-sleeve, backtest-insider-clusters, daily-cycle
```

**Rules:**
- Public interface unchanged: `from application.cli import cli` still works
- Shared helpers in `_deps.py` — imported by submodules, not re-exported
- `make check` green after every submodule extracted (not at end)
- Exact command-to-file mapping confirmed at implementation via code analysis

**Expected token reduction:** 32,300 → ~5,000 per targeted edit (~85% reduction).

### T2-2: Module decomposition — risk.py

Split `adapters/visualization/tabs/risk.py` (1710 LOC) into `adapters/visualization/tabs/risk/` package.

**Target structure:**

```
adapters/visualization/tabs/risk/
├── __init__.py     # exports render()
├── components.py   # header, banner, lens-nav, vitals, standing, dials, legend
├── evidence.py     # evidence_bands, grill_drill, flags_footer
├── factor_chart.py # _factor_chart (~240 LOC isolated)
├── enb_section.py  # _enb_section (~220 LOC isolated)
├── sections.py     # sector, who_owns, drift, teach
└── compose.py      # _compose, render (entry point)
```

**Rules:**
- `render()` signature unchanged
- `make check` green after every submodule extracted
- Exact boundaries decided at implementation via code analysis

**Expected token reduction:** 19,300 → ~3,200 per targeted edit (~83% reduction).

### T2-3: Module decomposition — styles.py

Split `adapters/visualization/components/styles.py` (1505 LOC) by concern.

**Approach:** inspect at implementation time. If it's one large CSS string function → split by component group (base, tabs, cards, risk). If it's many small functions → group by component.

**Rules:** same as T2-1 and T2-2.

### T2-4: Smoke suite + pytest markers

Define a fast regression guard that runs in <15s and covers critical cross-cutting paths.

**Marker taxonomy (add to `pyproject.toml`):**
```toml
[tool.pytest.ini_options]
markers = [
    "smoke: critical regression guard — must pass before every commit",
    "tab_risk: risk tab tests",
    "tab_weekly_brief: weekly brief tab tests",
    "tab_research: research candidates tab tests",
    "tab_screener: screener tab tests",
    "tab_positions: positions tab tests",
    "tab_trust: trust tab tests",
]
```

**Smoke suite criteria** (~60 tests tagged `@pytest.mark.smoke`):
- All Hypothesis property tests (domain invariants)
- Port contract tests (one per port interface)
- Critical use-case integration paths: weekly-brief pipeline, conviction use case, risk output
- LookAheadBias enforcement test
- Zero Streamlit/UI rendering tests in smoke

**New Makefile target:**
```makefile
test-smoke:
	pytest tests/ -q -n auto -m smoke --tb=short
	# Target: <15s
```

**Updated CLAUDE.md discipline table** (replaces T1-5 placeholder):

| Change type | Run immediately | Before commit | Before PR |
|-------------|-----------------|---------------|-----------|
| Any tab tweak | `make test-tab tab=<name>` | `make test-smoke` | `make check` |
| CLI command | `pytest tests/test_<cmd>.py -q` | `make test-smoke` | `make check` |
| Domain model | `make test-domain` | `make test-smoke` | `make check` |
| Adapter change | `make test-adapters` | `make test-smoke` | `make check` |
| Cross-cutting | `make test-fast` | `make test-smoke` | `make check` |

**Gate 2 (must pass after Tier 2):**
- `make check` green (all tests, ≥90% coverage)
- `make test-smoke` completes in <15s
- `make test-tab tab=risk` completes in <10s
- No file in `application/cli/` or `adapters/visualization/tabs/risk/` exceeds 600 LOC
- `CLAUDE.md` module map updated to reflect new package structure

---

## Measured impact (baseline 2026-06-17)

| Metric | Before | After Tier 1 | After Tier 2 |
|--------|--------|--------------|--------------|
| `make check` wall-clock | 484s | ~85s | ~85s |
| `make test-fast` | n/a | ~60s | ~60s |
| Targeted tab test | 484s | ~10s | ~10s |
| CI install time | ~45s | ~4s | ~4s |
| Read cli.py | 32,300 tokens | 32,300 tokens | ~5,000 tokens |
| Read risk.py | 19,300 tokens | 19,300 tokens | ~3,200 tokens |
| CONTEXT.md if read | 17,800 tokens | ~500 tokens | ~500 tokens |
| Typical session token overhead | ~60,000+ | ~25,000 | ~15,000 |
| CI push failures (formatting) | frequent | zero | zero |

---

## Non-goals

- No changes to domain logic, business rules, or port interfaces
- No new features
- No test deletions (coverage target stays at 90%)
- No change to hexagonal architecture boundaries
- `make check` remains the authoritative gate — never bypassed

---

## Files touched

**Tier 1:**
- `Makefile`
- `pyproject.toml` (addopts, add xdist dep, add uv, marker definitions placeholder)
- `.github/workflows/ci.yml`
- `.github/workflows/lint.yml`
- `.pre-commit-config.yaml` (pre-push hook documentation)
- `CLAUDE.md`
- `CONTEXT.md` (trimmed)
- `audit_sentiment.py` → `scripts/audit_sentiment.py`
- `.gitignore` (verify cache dirs)
- `uv.lock` (new)

**Tier 2:**
- `application/cli.py` → `application/cli/` package (10 files)
- `adapters/visualization/tabs/risk.py` → `adapters/visualization/tabs/risk/` package (6 files)
- `adapters/visualization/components/styles.py` → split (TBD at implementation)
- `tests/` (add markers to ~60 smoke tests + tab markers)
- `CLAUDE.md` (module map update)
