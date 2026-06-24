# SP7: Weekly Job Reliability — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two broken weekly-job paths (holdings_risk crash + tournament silent 0-picks) and add `ddgs` as a declared runtime dep so the corroboration CLI works in a fresh install.

**Architecture:** Three independent bug-fixes and one dependency declaration. No new abstractions. All fixes stay within the existing hexagonal layout: domain stays pure (no changes), fix lives in application/adapters layer. TDD throughout — each fix starts with a failing test that reproduces the exact failure mode.

**Tech Stack:** Python 3.12, statistics stdlib, numpy, click, pytest, uv (dep management)

**Working directory:** `/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/corroboration-sp7` (worktree on `feat/corroboration-engine`)

**Run commands with:** `PATH=.venv/bin:$PATH pytest ...` (uv-managed venv, no system pip)

---

## File Map

| File | Action | What changes |
|------|--------|-------------|
| `application/holdings_risk.py:59-61` | Modify | `_vol()` coerces returns to `float` before `statistics.pstdev` |
| `application/discipline_backtest.py:40-42` | Modify | Same `_vol()` fix (identical pattern, module-level function) |
| `application/cli/ml_commands.py:87-89` | Modify | `run-tournament` exits non-zero + loud message when 0 picks |
| `pyproject.toml:28` | Modify | Add `ddgs>=6.0` to runtime `dependencies` |
| `tests/test_holdings_risk.py` | Modify | Add numpy-float regression test |
| `tests/test_discipline_backtest.py` | Modify | Add numpy-float regression test |
| `tests/test_weekly_tournament.py` | Modify | Add 0-picks fail-loud test |

---

## Task 1: Fix `holdings_risk._vol()` — numpy float crash

**Root cause:** `application/holdings_risk.py:59-61` — `statistics.pstdev(tail)` receives a list of numpy scalar floats (from `domain/backtest_metrics.daily_returns` which operates on yfinance closes). Python 3.12 `statistics` module calls `.numerator` on elements; numpy scalars lack this attribute → `AttributeError`.

**Files:**
- Modify: `application/holdings_risk.py:59-61`
- Modify: `tests/test_holdings_risk.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_holdings_risk.py`:

```python
def test_vol_numpy_floats_do_not_crash():
    """Regression: statistics.pstdev raises AttributeError on numpy scalars
    in Python 3.12. _vol() must coerce before calling pstdev."""
    import numpy as np

    from application.holdings_risk import HoldingsRiskAssessmentUseCase
    from application.narrator import FakeNarrator

    # Build a price series with enough history using numpy floats
    # (as yfinance returns via daily_returns)
    numpy_prices = [np.float64(100.0 + i * 0.5) for i in range(260)]
    from datetime import datetime, timedelta, timezone

    start = datetime(2023, 1, 1, tzinfo=timezone.utc)
    series = {
        "AAPL": [(start + timedelta(days=i), v) for i, v in enumerate(numpy_prices)],
        "SPY": [(start + timedelta(days=i), 100.0 + i * 0.3) for i in range(260)],
    }

    from application.holdings_reader import Holding

    uc = HoldingsRiskAssessmentUseCase(
        price_provider=lambda t: series.get(t, []), narrator=FakeNarrator("why")
    )
    # Must not raise AttributeError: 'float' object has no attribute 'numerator'
    result = uc.execute(
        [Holding(ticker="AAPL", shares=10.0, cost_basis=2000.0, account_type="TFSA")],
        start,
        start + timedelta(days=259),
    )
    assert result["portfolio"].n_positions == 1
```

- [ ] **Step 2: Run to verify it fails**

```bash
PATH=.venv/bin:$PATH pytest tests/test_holdings_risk.py::test_vol_numpy_floats_do_not_crash -v
```

Expected: FAIL — `AttributeError: 'numpy.float64' object has no attribute 'numerator'` (or similar pstdev error)

- [ ] **Step 3: Apply the fix**

Edit `application/holdings_risk.py`, method `_vol` (lines 59-61):

```python
def _vol(self, returns: list[float], window: int) -> float:
    tail = returns[-window:]
    return statistics.pstdev([float(x) for x in tail]) if len(tail) >= 2 else 0.0
```

- [ ] **Step 4: Run to verify it passes**

```bash
PATH=.venv/bin:$PATH pytest tests/test_holdings_risk.py -v
```

Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/corroboration-sp7"
git add application/holdings_risk.py tests/test_holdings_risk.py
git commit -m "fix(holdings-risk): coerce numpy floats before statistics.pstdev (Python 3.12)"
```

---

## Task 2: Fix `discipline_backtest._vol()` — same class of failure

**Root cause:** `application/discipline_backtest.py:40-42` — identical `_vol()` function (module-level, not method), same `statistics.pstdev(tail)` vulnerability. SP7 spec says "fix the class of volatility failures, not only the one observed crash."

**Files:**
- Modify: `application/discipline_backtest.py:40-42`
- Modify: `tests/test_discipline_backtest.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_discipline_backtest.py`:

```python
def test_backtest_numpy_float_prices_do_not_crash():
    """Regression: discipline_backtest._vol() uses statistics.pstdev which
    raises AttributeError on numpy scalars in Python 3.12."""
    import numpy as np
    from datetime import datetime, timedelta, timezone

    from application.discipline_backtest import backtest_discipline_calibration

    start = datetime(2023, 1, 1, tzinfo=timezone.utc)
    # 300 price points using numpy floats (as returned by live price providers)
    n = 300
    numpy_up = [np.float64(100.0 + i * 0.5) for i in range(n)]
    series = {
        "NP": [(start + timedelta(days=i), v) for i, v in enumerate(numpy_up)],
        "SPY": [(start + timedelta(days=i), 100.0 + i * 0.3) for i in range(n)],
    }

    # Must not raise AttributeError
    out = backtest_discipline_calibration(
        ["NP"],
        lambda t: series.get(t, []),
        start,
        start + timedelta(days=n - 1),
        step_days=21,
        horizon_days=21,
    )
    assert out["total_verdicts"] >= 0  # any result, no crash
```

- [ ] **Step 2: Run to verify it fails**

```bash
PATH=.venv/bin:$PATH pytest tests/test_discipline_backtest.py::test_backtest_numpy_float_prices_do_not_crash -v
```

Expected: FAIL — same `AttributeError` as Task 1

- [ ] **Step 3: Apply the fix**

Edit `application/discipline_backtest.py`, function `_vol` (lines 40-42):

```python
def _vol(returns: list[float], window: int) -> float:
    tail = returns[-window:]
    return statistics.pstdev([float(x) for x in tail]) if len(tail) >= 2 else 0.0
```

- [ ] **Step 4: Run to verify it passes**

```bash
PATH=.venv/bin:$PATH pytest tests/test_discipline_backtest.py -v
```

Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add application/discipline_backtest.py tests/test_discipline_backtest.py
git commit -m "fix(discipline-backtest): coerce numpy floats before statistics.pstdev (Python 3.12)"
```

---

## Task 3: `run-tournament` fail-loud on 0 picks

**Root cause:** `application/use_cases.py:373` — per-ticker `except Exception` swallows `NotFittedError` silently. When no predictor is trained, all tickers fail silently and `candidates` is empty. The tournament logs "0 picks" and exits 0, appearing successful.

**Fix approach:** In `application/cli/ml_commands.py`, after `use_case.execute()`, check `report.recommendations`. If empty, print a clear error to stderr and exit non-zero. This keeps domain and use-case layer untouched (they don't know about process exit codes — that's CLI concern).

**Files:**
- Modify: `application/cli/ml_commands.py:86-89`
- Modify: `tests/test_weekly_tournament.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_weekly_tournament.py`:

```python
def test_run_tournament_cli_exits_nonzero_on_zero_picks():
    """run-tournament must exit non-zero when predictors are untrained.
    A clean exit with 0 picks is a silent lie — the command is a no-op."""
    from click.testing import CliRunner

    from application.cli._cli_group import cli

    runner = CliRunner()
    # No pretrain → predictors are unfitted → 0 picks → must exit 1
    result = runner.invoke(cli, ["run-tournament", "--market", "us"])
    assert result.exit_code == 1, (
        f"Expected exit code 1 (untrained), got {result.exit_code}. "
        f"Output: {result.output}"
    )
    assert "no picks" in result.output.lower() or "not trained" in result.output.lower() or result.exit_code == 1
```

- [ ] **Step 2: Run to verify it fails (currently exits 0)**

```bash
PATH=.venv/bin:$PATH pytest tests/test_weekly_tournament.py::test_run_tournament_cli_exits_nonzero_on_zero_picks -v
```

Expected: FAIL — `AssertionError: Expected exit code 1, got 0`

- [ ] **Step 3: Apply the fix**

Edit `application/cli/ml_commands.py`. Replace the `run_tournament` command body after `report = use_case.execute(...)`:

```python
@cli.command("run-tournament")
@click.option("--market", default="us")
@click.option("--date", default=None, help="Prediction date (YYYY-MM-DD)")
def run_tournament(market: str, date: str | None) -> None:
    """Run weekly tournament and generate top 15 picks."""
    deps = _build_dependencies(market)
    config = deps["config"]
    tickers = _get_ticker_universe(config)

    prediction_date = datetime.strptime(date, "%Y-%m-%d") if date else datetime.now()

    use_case = WeeklyTournamentUseCase(
        market_data=deps["market_data"],
        technical_analysis=deps["technical_analysis"],
        feature_engineer=deps["feature_engineer"],
        predictors=deps["predictors"],
        store=deps["store"],
        tickers=tickers,
        macro_symbols=deps["macro_symbols"],
        market=market,
        fundamental_engineer=deps["fundamental_engineer"],
        cross_asset_engineer=deps["cross_asset_engineer"],
        event_causal_engineer=deps["event_causal_engineer"],
    )

    report = use_case.execute(prediction_date=prediction_date)

    if not report.recommendations:
        click.echo(
            "run-tournament: 0 picks generated — predictors are not trained. "
            "Run 'pretrain' first. This run is a no-op.",
            err=True,
        )
        raise SystemExit(1)

    _print_report(report)
```

- [ ] **Step 4: Run to verify it passes**

```bash
PATH=.venv/bin:$PATH pytest tests/test_weekly_tournament.py -v
```

Expected: ALL PASS (including the new test)

- [ ] **Step 5: Commit**

```bash
git add application/cli/ml_commands.py tests/test_weekly_tournament.py
git commit -m "fix(cli): run-tournament exits non-zero with loud message when predictors not trained"
```

---

## Task 4: Declare `ddgs` runtime dependency

**Root cause:** `application/cli/corroboration_commands.py` imports `ddgs` at call time (lines 61-83). `pyproject.toml` mypy config knows about the module (lines 112, 175) but it is NOT in `[project.dependencies]` — a fresh `uv sync` won't install it, breaking the live corroborate path.

**Files:**
- Modify: `pyproject.toml` (add `ddgs` to `[project.dependencies]`)

No test needed — `ddgs` is a live-network dependency and the existing corroboration tests use fakes. The fix is a one-line addition; verify by checking `uv sync` doesn't error and the import resolves.

- [ ] **Step 1: Add `ddgs` to runtime dependencies**

Edit `pyproject.toml`. In the `[project]` `dependencies` list (line 29, after `scipy>=1.11`), add:

```toml
dependencies = [
    "pandas>=2.0.0",
    "scikit-learn>=1.3.0",
    "xgboost>=2.0.0",
    "lightgbm>=4.0.0",
    "shap>=0.50.0",
    "yfinance>=0.2.0",
    "pytrends>=4.9.2",
    "praw>=7.7.1",
    "feedparser>=6.0.0",
    "google-api-python-client>=2.0.0",
    "click>=8.0.0",
    "pyyaml>=6.0.0",
    "loguru>=0.7.0",
    "requests>=2.30.0",
    "networkx>=3.0",
    "statsmodels>=0.14.0",
    "scipy>=1.11",
    "ddgs>=6.0",
]
```

- [ ] **Step 2: Sync and verify import resolves**

```bash
PATH=.venv/bin:$PATH uv sync
PATH=.venv/bin:$PATH python -c "from duckduckgo_search import DDGS; print('ddgs ok')"
```

Expected output: `ddgs ok`

- [ ] **Step 3: Run corroboration tests to confirm no regressions**

```bash
PATH=.venv/bin:$PATH pytest tests/test_citation_verifier.py tests/test_corroboration_service.py tests/test_corroboration_models.py tests/test_search_harvester.py -v
```

Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore(deps): declare ddgs>=6.0 as runtime dependency (used by corroborate CLI)"
```

---

## Task 5: Full gate + STATUS.md update

- [ ] **Step 1: Run the targeted test set for all SP7 changes**

```bash
PATH=.venv/bin:$PATH pytest tests/test_holdings_risk.py tests/test_discipline_backtest.py tests/test_weekly_tournament.py tests/test_corroboration_service.py -v
```

Expected: ALL PASS

- [ ] **Step 2: Run mypy strict**

```bash
PATH=.venv/bin:$PATH mypy domain/ adapters/ application/ --strict
```

Expected: `Success: no issues found in N source files`

- [ ] **Step 3: Run ruff**

```bash
PATH=.venv/bin:$PATH ruff check application/holdings_risk.py application/discipline_backtest.py application/cli/ml_commands.py pyproject.toml
```

Expected: no output (no errors)

- [ ] **Step 4: Update STATUS.md**

Overwrite `docs/STATUS.md` with:

```markdown
# STATUS — multi-modal-stock-recommender

**As of:** 2026-06-21
**Branch:** `feat/corroboration-engine` (worktree: corroboration-sp7)
**Phase:** SP7 DONE — weekly job reliability fixed; next = SP2 candidate surfacing

## NEXT ACTION (fresh session — start here)

**Brainstorm + full spec SP2 candidate surfacing.**
Brief: `docs/superpowers/specs/2026-06-20-sp2-candidate-surfacing-brief.md`
Skill order: brainstorming → writing-plans → subagent-driven-development.

Documented build order: SP2 → SP3 → SP4 → SP5 → SP6.
PR #73 (SP1 corroboration core) still OPEN → develop, deferred by user.

## SP7 — DONE (3 fixes, 4 commits)

| Fix | File | Status |
|-----|------|--------|
| holdings_risk numpy-float crash | `application/holdings_risk.py:60` | ✅ |
| discipline_backtest same class | `application/discipline_backtest.py:41` | ✅ |
| run-tournament fail-loud exit(1) | `application/cli/ml_commands.py` | ✅ |
| ddgs runtime dep declared | `pyproject.toml` | ✅ |

## Worktree / branch layout

- Main tree: `fix/test-hang-timeout` (CI gate fix, not yet merged)
- This worktree: `feat/corroboration-engine` (SP1 + SP7, PR #73 open)
- Other active worktrees: portfolio-tab-redesign, risk-tab-redesign

## Gotchas

- Use `.venv` (uv-managed): prefix commands with `PATH=.venv/bin:$PATH`
- Full `make check` coverage suite HANGS (open flag: `fix/test-hang-timeout`)
  → verify via targeted pytest + mypy --strict only
- google.generativeai prints FutureWarning (project-wide, non-blocking)
- factor_percentile is None unless `screen_<date>.json` exists (run `screen-candidates` first)
```

- [ ] **Step 5: Commit STATUS.md**

```bash
git add docs/STATUS.md
git commit -m "docs: STATUS — SP7 complete, next=SP2 candidate surfacing"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|-----------------|------|
| Fix `holdings_risk.py:61` numpy-float crash | Task 1 ✅ |
| Sweep + fix `discipline_backtest.py` same pattern | Task 2 ✅ |
| `run-tournament` fail-loud, non-zero exit | Task 3 ✅ |
| `ddgs` declared in pyproject.toml | Task 4 ✅ (grounding-surfaced bonus fix) |
| Wire `corroborate` into weekly cadence slot (LOW, SP1 already done) | deferred — `corroborate` CLI exists; launchd scheduling is SP5 scope per spec |
| mypy strict stays green | Task 5 ✅ |

**Placeholder scan:** none found — all steps have exact code and exact commands.

**Type consistency:** `statistics.pstdev([float(x) for x in tail])` returns `float` in both Task 1 and Task 2. `SystemExit(1)` in Task 3 is a click-compatible exit. All method signatures unchanged.
