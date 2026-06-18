# Efficiency Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cut `make check` from 8 min → <2 min, eliminate CI auto-fix failures, reduce per-session token overhead ~60%, and give Claude surgical test targets for every file type.

**Architecture:** Two tiers. Tier 1 (Tasks 1–6) delivers ~80% value through config/tooling changes only — zero structural risk. Tier 2 (Tasks 7–9) decomposes the three largest modules and adds a smoke suite. Each task is gate-guarded; `make check` must be green before moving to the next task.

**Tech Stack:** Python 3.12, pytest + pytest-xdist, uv, pre-commit, click, GitHub Actions, mypy strict.

**Spec:** `docs/superpowers/specs/2026-06-17-efficiency-overhaul-design.md`

---

## TIER 1 — Quick wins (~2.5 hours)

---

### Task 1: Makefile overhaul + pytest-xdist + drop `-v`

**Why first:** Zero-risk config change. Delivers the biggest single win (8 min → ~85s gate, fast iteration targets). Tests confirmed xdist-safe (all use `tmp_path`, no shared state).

**Files:**
- Modify: `Makefile`
- Modify: `pyproject.toml` (addopts + add xdist dep)

- [ ] **Step 1: Add pytest-xdist to dev deps in pyproject.toml**

In `pyproject.toml`, find `[project.optional-dependencies]` → `dev` array. Add `"pytest-xdist>=3.0.0"`:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
    "pytest-xdist>=3.0.0",
    "hypothesis>=6.0.0",
    "black>=24.0.0",
    "isort>=5.13.0",
    "mypy>=1.8.0",
    "ruff>=0.1.0",
    "pre-commit>=3.0.0",
    "scipy>=1.11",
]
```

- [ ] **Step 2: Remove `-v` from addopts in pyproject.toml**

Find `[tool.pytest.ini_options]` and change:
```toml
# Before
addopts = "-v -p no:playwright"

# After
addopts = "-p no:playwright"
```

- [ ] **Step 3: Replace Makefile entirely**

```makefile
.PHONY: test test-fast test-tab test-domain test-adapters test-cov lint typecheck setup check

# ── Iteration targets (fast, no coverage) ────────────────────────────────────

test-fast:
	pytest tests/ -q -n auto --tb=short

# Usage: make test-tab tab=risk  |  make test-tab tab=weekly_brief
test-tab:
	pytest tests/ -q -n auto -m "tab_$(tab)" --tb=short

test-domain:
	pytest tests/domain/ -q -n auto --tb=short

test-adapters:
	pytest tests/adapters/ -q -n auto --tb=short

# ── Full suite, no coverage ───────────────────────────────────────────────────

test:
	pytest tests/ -n auto --tb=short

# ── Coverage gate (CI + pre-PR only) ─────────────────────────────────────────

test-cov:
	pytest tests/ -n auto \
	    --cov=domain --cov=adapters --cov=application \
	    --cov-fail-under=90 --tb=short

# ── Quality checks ────────────────────────────────────────────────────────────

lint:
	pre-commit run --all-files

typecheck:
	mypy domain/ adapters/ application/ --strict

# ── Full gate — CI and pre-PR only, NOT during iteration ─────────────────────

check: lint typecheck test-cov

# ── Environment setup ─────────────────────────────────────────────────────────

setup:
	uv sync
	pre-commit install
```

- [ ] **Step 4: Install xdist and run test-fast to verify**

```bash
pip install pytest-xdist  # temporary until uv migration in Task 2
make test-fast
```

Expected: all 2145 tests pass, runtime ~60–90s (no verbose output, parallel workers active).

- [ ] **Step 5: Run full gate to confirm nothing broken**

```bash
make check
```

Expected: lint pass, mypy pass, 2145 passed, ≥90% coverage.

- [ ] **Step 6: Commit**

```bash
git add Makefile pyproject.toml
git commit -m "chore: add xdist, drop -v, add targeted test targets"
```

---

### Task 2: uv migration

**Why:** CI cold-install drops from ~45s → ~4s. `make setup` becomes reproducible via lockfile.

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `.github/workflows/lint.yml`
- New: `uv.lock` (generated, committed)

- [ ] **Step 1: Install uv locally**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# or: brew install uv
uv --version  # verify
```

Expected: uv 0.4.x or later printed.

- [ ] **Step 2: Generate lockfile**

```bash
cd /path/to/multi-modal-stock-recommender
uv lock
```

Expected: `uv.lock` created in project root.

- [ ] **Step 3: Verify uv sync works**

```bash
uv sync --extra dev --extra dashboard
```

Expected: all deps installed, no errors.

- [ ] **Step 4: Update ci.yml**

Replace the entire `Install dependencies` block in `.github/workflows/ci.yml`:

```yaml
# Before:
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev,dashboard]"
          pip install pytest pytest-cov hypothesis
      - name: Run tests with coverage
        run: pytest tests/ -v --tb=short --cov=domain --cov=adapters --cov=application --cov-fail-under=90
```

```yaml
# After:
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"
      - name: Install dependencies
        run: uv sync --extra dev --extra dashboard
      - name: Run tests with coverage
        run: uv run pytest tests/ -n auto --tb=short --cov=domain --cov=adapters --cov=application --cov-fail-under=90
```

- [ ] **Step 5: Update lint.yml**

In `.github/workflows/lint.yml`, replace pip install lines in both jobs (lint + typecheck) with:

```yaml
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"
      - name: Install dependencies
        run: uv sync --extra dev
```

- [ ] **Step 6: Run make check locally to confirm uv env is equivalent**

```bash
make check
```

Expected: 2145 passed, ≥90% coverage, mypy strict, ruff clean.

- [ ] **Step 7: Commit**

```bash
git add uv.lock .github/workflows/ci.yml .github/workflows/lint.yml pyproject.toml
git commit -m "chore: migrate to uv, update CI workflows"
```

---

### Task 3: Pre-push hook — eliminate CI auto-fix loop

**Why:** The current pain point: black/whitespace reformats files on commit → first CI push fails → re-push passes. A pre-push hook stops this at source.

**Files:**
- Modify: `.pre-commit-config.yaml`

- [ ] **Step 1: Add pre-push stage to formatting hooks in .pre-commit-config.yaml**

Add `stages: [pre-commit, pre-push]` to the hooks that auto-fix files (trailing-whitespace, end-of-file-fixer, black, isort):

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
        stages: [pre-commit, pre-push]
      - id: end-of-file-fixer
        stages: [pre-commit, pre-push]
      - id: check-yaml
      - id: check-added-large-files
        args: [--maxkb=500]
      - id: detect-private-key

  - repo: https://github.com/psf/black
    rev: 24.10.0
    hooks:
      - id: black
        language_version: python3.12
        stages: [pre-commit, pre-push]

  - repo: https://github.com/pycqa/isort
    rev: 5.13.2
    hooks:
      - id: isort
        args: ["--profile", "black"]
        stages: [pre-commit, pre-push]

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        args: ["--strict"]
        exclude: "^(tests/|audit_sentiment\\.py)"
        additional_dependencies:
          - types-PyYAML
          - types-click
          - types-requests
          - pandas-stubs
          - loguru

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.15
    hooks:
      - id: ruff

  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.4
    hooks:
      - id: gitleaks
```

- [ ] **Step 2: Install the pre-push hook**

```bash
pre-commit install --hook-type pre-push
```

Expected: `pre-push` hook installed in `.git/hooks/pre-push`.

- [ ] **Step 3: Verify pre-push hook fires**

```bash
git stash  # ensure clean state
git push --dry-run 2>&1 | head -5
```

Expected: pre-commit runs formatting checks before the push attempt.

- [ ] **Step 4: Commit**

```bash
git add .pre-commit-config.yaml
git commit -m "chore: add pre-push hook to prevent CI auto-fix failures"
```

---

### Task 4: Fix .gitignore + repo cleanup

**Why:** `.pytest_cache/` is NOT in `.gitignore` (confirmed). `audit_sentiment.py` lives at root, polluting Claude's initial file scan.

**Files:**
- Modify: `.gitignore`
- Move: `audit_sentiment.py` → `scripts/audit_sentiment.py`

- [ ] **Step 1: Add .pytest_cache to .gitignore**

Open `.gitignore` and add after `.hypothesis/`:

```
.pytest_cache/
```

- [ ] **Step 2: Verify .mypy_cache already ignored**

```bash
grep -E "mypy_cache|pytest_cache|ruff_cache|hypothesis" .gitignore
```

Expected output (all four lines present):
```
.hypothesis/
.mypy_cache/
.ruff_cache/
.pytest_cache/
```

- [ ] **Step 3: Move audit_sentiment.py to scripts/**

```bash
mv audit_sentiment.py scripts/audit_sentiment.py
```

Update `pyproject.toml` mypy exclude to match new path:
```toml
# Before
exclude = ["tests/", "audit_sentiment\\.py"]

# After
exclude = ["tests/", "scripts/audit_sentiment\\.py"]
```

Also update `.pre-commit-config.yaml` mypy hook exclude:
```yaml
        exclude: "^(tests/|scripts/audit_sentiment\\.py)"
```

- [ ] **Step 4: Verify make check still passes**

```bash
make check
```

Expected: 2145 passed, mypy strict, ruff clean.

- [ ] **Step 5: Commit**

```bash
git add .gitignore pyproject.toml .pre-commit-config.yaml scripts/audit_sentiment.py
git rm audit_sentiment.py
git commit -m "chore: fix .gitignore, move audit_sentiment.py to scripts/"
```

---

### Task 5: CLAUDE.md overhaul

**Why:** Current CLAUDE.md missing model routing, testing discipline table, CONTEXT.md guard, and module map. Every Claude session starts without this guidance.

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Read current CLAUDE.md to preserve existing valid content**

Read `CLAUDE.md` fully before editing. Preserve: Project Context, Commands section, Architecture section, Critical Domain Knowledge, Non-Negotiable Rules, External Documentation section, Phase Status.

- [ ] **Step 2: Add Model Routing section after the Commands section**

Insert after the `## Commands` section:

```markdown
## Model Routing (this project)

Use the right model for each task. Never burn Opus on work Sonnet handles.

| Task | Model |
|------|-------|
| Tab/adapter edits, CLI commands, tests | Sonnet |
| Domain model changes | Sonnet |
| Architecture decisions, ADRs | Fable (main loop) |
| Debugging test failures | Opus |
| File lookup, grep, targeted search | Haiku |
| Full codebase exploration | Sonnet (Explore agent) |
| Code review pre-PR | Opus |
```

- [ ] **Step 3: Add Testing Discipline section after Commands**

Insert after Model Routing:

```markdown
## Testing Discipline (mandatory — not advisory)

Run the narrowest target that covers your change. `make check` is for PRs only.

| Change type | Run immediately | Before commit | Before PR |
|-------------|-----------------|---------------|-----------|
| Any dashboard tab | `make test-tab tab=<name>` | `make test-fast` | `make check` |
| CLI command | `pytest tests/test_<name>.py -q` | `make test-fast` | `make check` |
| Domain model | `make test-domain` | `make test-fast` | `make check` |
| Adapter change | `make test-adapters` | `make test-fast` | `make check` |
| Cross-cutting | `make test-fast` | `make test-fast` | `make check` |

Tab names for `make test-tab`: `risk`, `weekly_brief`, `research`, `screener`, `positions`, `trust`

**Never run `make check` after every edit during a session — only at checkpoints and pre-PR.**
```

- [ ] **Step 4: Add CONTEXT.md guard and Module Map section**

Insert before the Phase Status section:

```markdown
## Key Files — Where to Look

```
domain/models.py                   Core dataclasses (Signal, Conviction, Brief, etc.)
domain/ports.py                    All port interfaces — source of truth for contracts
domain/services.py                 Business logic (LookAheadBias enforcement here)
application/cli.py                 CLI entry point — Tier 2 decomp target (3440 LOC)
adapters/visualization/tabs/       One file per dashboard tab
adapters/visualization/components/ Shared UI components (styles.py, charts.py, cards.py)
adapters/data/sqlite_store.py      Persistence layer (1093 LOC)
tests/fakes/                       Test doubles for all ports — use these, don't mock
tests/conftest.py                  Strips live API keys — one autouse fixture only
```

## CONTEXT.md — Do NOT auto-read

`CONTEXT.md` is a historical session timeline (17,800 tokens). **Do not read it** at session start
or during exploration. Open only when the user explicitly asks about project history.
Current state lives in `docs/STATUS.md` (read this first — it is short and authoritative).
```

- [ ] **Step 5: Run make check to confirm CLAUDE.md has no syntax issues and nothing else broke**

```bash
make check
```

Expected: 2145 passed, all gates green.

- [ ] **Step 6: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: overhaul CLAUDE.md — model routing, test discipline, module map"
```

---

### Task 6: Trim CONTEXT.md

**Why:** 884 lines, 17,800 tokens. If Claude ever reads it during repo exploration, it burns 17k tokens before a single line of code is touched. Trim to a 1-page index.

**Files:**
- Modify: `CONTEXT.md`

- [ ] **Step 1: Read CONTEXT.md to understand its current structure**

Read `CONTEXT.md` and identify: section headers, what is historical vs still-relevant.

- [ ] **Step 2: Replace CONTEXT.md with a concise index**

Overwrite `CONTEXT.md` with an index that points to the real docs (preserve the filename — other tools may reference it):

```markdown
# Project Context Index

> This file is a navigation index only. All detail lives in the docs below.
> Full history trimmed 2026-06-17 — see git log for prior content.

## Current state
→ `docs/STATUS.md` — phase, branch, next action, open items (read this first)

## Architecture decisions
→ `docs/adr/` — ADR-036 through ADR-061+; each decision and its rationale

## Phase history
→ `docs/PHASE_LOG.md` — full session-by-session history

## Skill routing
→ `docs/SKILL_ROUTING.md` — which skill/agent to invoke per phase

## Project brief (what we built and why)
→ `README.md` — feature overview, data sources, setup

## Design specs
→ `docs/superpowers/specs/` — approved design documents per feature

## Domain context
- **Core hypothesis:** sentiment leads price 1–48h; cross-modal divergence predicts 5-day returns
- **Architecture:** hexagonal (ports & adapters); domain/ is stdlib-only
- **Phase:** maintenance / RESEARCH_ONLY — no new prediction signals without explicit ADR
- **Critical constraint:** look-ahead bias is non-negotiable; `LookAheadBiasError` halts pipeline
```

- [ ] **Step 3: Verify file size reduced**

```bash
wc -c CONTEXT.md  # should be <2000 bytes
```

Expected: ~900–1500 bytes.

- [ ] **Step 4: Commit**

```bash
git add CONTEXT.md
git commit -m "docs: trim CONTEXT.md to navigation index (was 17,800 tokens)"
```

---

### Task 6.5: Gate 1 verification

Before moving to Tier 2, verify all Tier 1 changes work together.

- [ ] **Step 1: Run full make check**

```bash
make check
```

Expected: lint pass, mypy pass, 2145 passed, ≥90% coverage.

- [ ] **Step 2: Verify targeted test targets work**

```bash
make test-tab tab=risk        # should run only risk tab tests
make test-domain              # should run only domain tests
make test-adapters            # should run only adapter tests
make test-fast                # full suite, fast, no coverage
```

All expected to pass. `test-tab tab=risk` should complete in <15s.

- [ ] **Step 3: Verify pre-push hook fires**

```bash
echo "test" >> README.md && git add README.md
git stash  # clean up test change
```

Confirm that `pre-commit install --hook-type pre-push` installed correctly:
```bash
ls .git/hooks/pre-push
```

Expected: file exists.

- [ ] **Step 4: Time the gate**

```bash
time make check
```

Expected: <120s total (lint ~5s, mypy ~10s, test-cov ~90s).

---

## TIER 2 — Structural improvements (~5 hours, next session)

> Start Tier 2 only after Gate 1 passes. Each task below is independently gate-guarded.

---

### Task 7: Decompose cli.py → application/cli/ package

**Why:** `cli.py` at 3440 LOC (~32,300 tokens) makes every CLI-related edit token-heavy. After split, each targeted edit touches ~5,000 tokens.

**Files:**
- New: `application/cli/__init__.py`
- New: `application/cli/_cli_group.py`
- New: `application/cli/_deps.py`
- New: `application/cli/ml_commands.py`
- New: `application/cli/scan_commands.py`
- New: `application/cli/brief_commands.py`
- New: `application/cli/portfolio_commands.py`
- New: `application/cli/screen_commands.py`
- New: `application/cli/validation_commands.py`
- New: `application/cli/data_commands.py`
- New: `application/cli/backtest_commands.py`
- Delete: `application/cli.py`

**Pattern — how to avoid circular imports with Click groups:**

```
_cli_group.py   → defines @click.group() cli
_deps.py        → defines _build_dependencies() and shared helpers
*_commands.py   → imports cli from ._cli_group; imports helpers from ._deps
__init__.py     → imports cli from ._cli_group (re-export); imports all *_commands modules
```

This pattern is the standard Click application splitting approach. `_cli_group.py` is imported first by `__init__.py`; then submodules import `cli` from `._cli_group` — no circular import possible.

- [ ] **Step 1: Create application/cli/ package skeleton**

```bash
mkdir application/cli
```

Create `application/cli/_cli_group.py`:
```python
"""Click group definition — imported by all command submodules."""
import click
from application.dotenv_loader import load_dotenv

load_dotenv()


@click.group()
def cli() -> None:
    """Multi-modal stock recommender CLI."""
```

(Copy the actual `@click.group()` definition and any setup code from `cli.py` lines 95–105 — the dotenv call lives inside the group function body in the original.)

- [ ] **Step 2: Create application/cli/_deps.py**

Copy `_build_dependencies()` and all shared private helpers into `_deps.py`:
- `_build_dependencies()` (lines 46–93)
- `_load_wiki_map()`, `_load_wiki_map_merged()`, `_get_company_name()`, `_load_spine_tickers()`
- `_get_ticker_universe()`, `_get_backtest_universe()`
- `_cfg_cmin()`, `_cfg_dmin()`, `_is_backfill_due()`
- `_print_report()`, `_risk_macro_facts()`

These are shared across multiple command groups.

- [ ] **Step 3: Extract ml_commands.py**

Commands: `pretrain`, `run-tournament`, `evaluate-last-week`, `show-report`, `backtest`, `shap-report`.

Template for every submodule:
```python
"""ML training and evaluation commands."""
from __future__ import annotations

import click
from application.cli._cli_group import cli
from application.cli._deps import _build_dependencies
# ... other imports specific to these commands

@cli.command("pretrain")
@click.option("--market", default="us")
@click.option("--start", default="2024-01")
@click.option("--end", default="2026-05")
def pretrain(market: str, start: str, end: str) -> None:
    # ... exact implementation from cli.py
```

- [ ] **Step 4: Run make check after ml_commands.py extracted**

```bash
make check
```

Expected: 2145 passed. Fix any import errors before continuing.

- [ ] **Step 5: Extract remaining command groups one at a time**

For each group below, extract → `make check` → fix → proceed:

**scan_commands.py** — `daily-scan`, `validate-3b`, `scan-opportunities`, `resolve-calls`, `opportunity-report`

**brief_commands.py** — `weekly-brief`, `_build_weekly_brief()`, `_prefetch_cited_cases()`

**portfolio_commands.py** — `portfolio-verdict`, `holdings-risk`, `holdings-risk-calibrate`

**screen_commands.py** — `screen-candidates`, `backtest-screen`

**validation_commands.py** — `adherence-report`, `resolve-discipline-flags`, `discipline-calibration-status`, `audit-dimensions`, `validate-divergence-ic`, `validate-momentum-discipline`, `backtest-discipline-flags`

**data_commands.py** — `resolve-wiki-articles`, `drip-backfill`, `backfill-history`, `add-watchlist`, `list-watchlist`, `remove-watchlist`, `monitor-holdings`

**backtest_commands.py** — `backtest-trend-sleeve`, `backtest-insider-clusters`, `daily-cycle`

Run `make check` after EACH group. Do not batch multiple groups before testing.

- [ ] **Step 6: Create application/cli/__init__.py**

```python
"""CLI package — imports all submodules to register commands."""
from application.cli._cli_group import cli  # noqa: F401
from application.cli import (  # noqa: F401
    ml_commands,
    scan_commands,
    brief_commands,
    portfolio_commands,
    screen_commands,
    validation_commands,
    data_commands,
    backtest_commands,
)

__all__ = ["cli"]
```

- [ ] **Step 7: Delete application/cli.py and verify**

```bash
git rm application/cli.py
make check
```

Expected: 2145 passed. `from application.cli import cli` still works (now resolves to package).

- [ ] **Step 8: Verify CLI still works end-to-end**

```bash
python -m application.cli --help
```

Expected: all command groups listed.

- [ ] **Step 9: Update CLAUDE.md module map**

Replace the `application/cli.py` entry in the Key Files section:
```
application/cli/                   CLI package (decomposed from 3440-LOC monolith)
  _cli_group.py                    Click group definition
  _deps.py                         _build_dependencies() + shared helpers
  *_commands.py                    One file per command domain (~300-500 LOC each)
```

- [ ] **Step 10: Commit**

```bash
git add application/cli/ CLAUDE.md
git rm application/cli.py
git commit -m "refactor: decompose cli.py into application/cli/ package"
```

---

### Task 8: Decompose risk.py → adapters/visualization/tabs/risk/ package

**Why:** `risk.py` at 1710 LOC (~19,300 tokens). After split, targeted edits touch ~3,200 tokens.

**Files:**
- New: `adapters/visualization/tabs/risk/__init__.py`
- New: `adapters/visualization/tabs/risk/components.py`
- New: `adapters/visualization/tabs/risk/evidence.py`
- New: `adapters/visualization/tabs/risk/factor_chart.py`
- New: `adapters/visualization/tabs/risk/enb_section.py`
- New: `adapters/visualization/tabs/risk/sections.py`
- New: `adapters/visualization/tabs/risk/compose.py`
- Delete: `adapters/visualization/tabs/risk.py`

**Split plan (verify exact line ranges at implementation):**

| File | Functions | Approx LOC |
|------|-----------|-----------|
| `components.py` | `_header`, `_status_banner`, `_flag_short`, `_contract_legend`, `_vitals`, `_lens_nav`, `_standing`, `_dials` | ~400 |
| `evidence.py` | `_evidence_bands`, `_grill_drill`, `_flags_footer` | ~300 |
| `factor_chart.py` | `_factor_chart` | ~240 |
| `enb_section.py` | `_enb_section` | ~220 |
| `sections.py` | `_sector_section`, `_who_owns`, `_drift`, `_teach` | ~400 |
| `compose.py` | `_compose`, `render` | ~100 |

- [ ] **Step 1: Create package skeleton**

```bash
mkdir adapters/visualization/tabs/risk
```

- [ ] **Step 2: Extract compose.py first (entry point — defines render())**

`adapters/visualization/tabs/risk/compose.py`:
```python
"""Tab composition — _compose() and render() entry point."""
from __future__ import annotations
from typing import Any

# Imports from sibling modules (filled in as each module is created)
from .components import _header, _status_banner, ...
from .evidence import _evidence_bands, _grill_drill, _flags_footer
from .factor_chart import _factor_chart
from .enb_section import _enb_section
from .sections import _sector_section, _who_owns, _drift, _teach

def _compose(macro: dict[str, Any] | None, ai_html: str = "") -> str:
    # exact implementation from risk.py _compose()
    ...

def render(path: str = "data/personal/brief_summary.json") -> None:
    # exact implementation from risk.py render()
    ...
```

`adapters/visualization/tabs/risk/__init__.py`:
```python
"""Risk tab package — exports render()."""
from .compose import render  # noqa: F401

__all__ = ["render"]
```

- [ ] **Step 3: Extract each submodule — run make check after each**

Order: `components.py` → `evidence.py` → `factor_chart.py` → `enb_section.py` → `sections.py`

For each: copy the functions, add necessary imports, run `make check`.

- [ ] **Step 4: Delete adapters/visualization/tabs/risk.py and verify**

```bash
git rm adapters/visualization/tabs/risk.py
make check
```

Expected: all tests pass. Verify `render()` import works:
```bash
python -c "from adapters.visualization.tabs.risk import render; print('ok')"
```

- [ ] **Step 5: Update CLAUDE.md module map**

```
adapters/visualization/tabs/risk/   Risk tab package (decomposed from 1710-LOC monolith)
  compose.py                        _compose() + render() entry point
  components.py                     Header, banner, nav, vitals, dials (~400 LOC)
  evidence.py                       Evidence bands, grill drill, flags footer
  factor_chart.py                   Fama-French factor chart (~240 LOC isolated)
  enb_section.py                    ENB drill section (~220 LOC isolated)
  sections.py                       Sector, who_owns, drift, teach sections
```

- [ ] **Step 6: Commit**

```bash
git add adapters/visualization/tabs/risk/ CLAUDE.md
git rm adapters/visualization/tabs/risk.py
git commit -m "refactor: decompose risk.py into adapters/visualization/tabs/risk/ package"
```

---

### Task 9: Smoke suite + pytest markers

**Why:** One tab tweak should run 10 targeted tests, not 2145. Smoke suite catches cross-cutting regressions in <15s.

**Files:**
- Modify: `pyproject.toml` (register markers)
- Modify: `Makefile` (add test-smoke target)
- Modify: `tests/domain/` files (add @pytest.mark.smoke)
- Modify: `tests/` tab test files (add tab markers)
- Modify: `CLAUDE.md` (update testing discipline table to use test-smoke as commit gate)

- [ ] **Step 1: Register markers in pyproject.toml**

Add to `[tool.pytest.ini_options]`:
```toml
markers = [
    "smoke: critical regression guard — run before every commit",
    "tab_risk: risk tab tests",
    "tab_weekly_brief: weekly brief tab tests",
    "tab_research: research candidates tab tests",
    "tab_screener: screener tab tests",
    "tab_positions: positions tab tests",
    "tab_trust: trust tab tests",
]
```

- [ ] **Step 2: Add test-smoke target to Makefile**

Add after `test-adapters`:
```makefile
test-smoke:
	pytest tests/ -q -n auto -m smoke --tb=short
```

- [ ] **Step 3: Tag smoke tests — domain invariants (all Hypothesis tests)**

In each file in `tests/domain/`, add `@pytest.mark.smoke` to all Hypothesis-based property tests. These are the most critical — they test domain invariants that must hold everywhere.

Example pattern:
```python
import pytest
from hypothesis import given, strategies as st

@pytest.mark.smoke
@given(...)
def test_signal_invariant(...):
    ...
```

- [ ] **Step 4: Tag smoke tests — port contract tests**

In `tests/` files that test port interfaces (not implementation), add `@pytest.mark.smoke`. These catch if an adapter breaks the contract.

Criterion: any test that instantiates a fake and verifies the port protocol is a smoke candidate.

- [ ] **Step 5: Tag smoke tests — critical integration paths**

Tag one test per critical use-case path:
- `test_conviction_use_case.py` — tag the happy-path integration test
- `test_weekly_brief_tab.py` — tag the end-to-end render test
- `test_risk_tab.py` — tag the `render()` integration test
- Any test for `LookAheadBiasError` enforcement

Goal: ~60 tests total tagged `@pytest.mark.smoke`.

- [ ] **Step 6: Tag tab markers**

In each tab test file, add the corresponding marker to all tests:

```python
# tests/test_risk_tab.py — add to each test function or use pytestmark
import pytest
pytestmark = pytest.mark.tab_risk

# tests/test_weekly_brief_tab.py
pytestmark = pytest.mark.tab_weekly_brief

# tests/test_research_candidates_tab.py
pytestmark = pytest.mark.tab_research
```

For screener, positions, trust tabs: same pattern.

- [ ] **Step 7: Verify smoke suite speed**

```bash
time make test-smoke
```

Expected: <15s, all smoke tests pass.

- [ ] **Step 8: Verify tab targeting works**

```bash
make test-tab tab=risk
make test-tab tab=weekly_brief
```

Expected: only the tagged tests run, <15s each.

- [ ] **Step 9: Update CLAUDE.md testing discipline table**

Replace the Tier 1 placeholder table with the smoke-gated version:

```markdown
| Change type | Run immediately | Before commit | Before PR |
|-------------|-----------------|---------------|-----------|
| Any dashboard tab | `make test-tab tab=<name>` | `make test-smoke` | `make check` |
| CLI command | `pytest tests/test_<name>.py -q` | `make test-smoke` | `make check` |
| Domain model | `make test-domain` | `make test-smoke` | `make check` |
| Adapter change | `make test-adapters` | `make test-smoke` | `make check` |
| Cross-cutting | `make test-fast` | `make test-smoke` | `make check` |
```

- [ ] **Step 10: Final gate — run make check**

```bash
make check
```

Expected: 2145 passed, ≥90% coverage, mypy strict, ruff clean.

- [ ] **Step 11: Commit**

```bash
git add pyproject.toml Makefile tests/ CLAUDE.md
git commit -m "test: add smoke suite and tab markers for targeted testing"
```

---

## Final verification (end of Tier 2)

- [ ] `make check` green: 2145+ passed, ≥90% coverage
- [ ] `make test-smoke` completes in <15s
- [ ] `make test-tab tab=risk` completes in <10s
- [ ] `make test-fast` completes in <90s
- [ ] `python -m application.cli --help` lists all commands
- [ ] No file in `application/cli/` exceeds 600 LOC
- [ ] No file in `adapters/visualization/tabs/risk/` exceeds 450 LOC
- [ ] `git push` triggers pre-push hook

---

## PR checklist

After all tasks complete, open PR from `feat/efficiency-overhaul` → `develop`:
- Title: `chore: efficiency overhaul — xdist, uv, targeted tests, module decomp`
- Body: reference ADR-061, list Tier 1 and Tier 2 changes, include gate timing before/after
