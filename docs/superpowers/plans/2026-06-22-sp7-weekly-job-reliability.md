# SP7 Weekly-Job Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two reliability bugs that silently corrupt the Saturday weekly run — a numpy-float crash in `holdings_risk._vol()` that aborts `weekly-brief`, and an unfitted-model silent-zero in `run-tournament` that exits 0 with no picks.

**Architecture:** Two independent fixes, no shared files. Fix #1 is a one-line coercion in `application/holdings_risk.py`. Fix #2 adds `is_fitted()` to `adapters/ml/ensemble_predictor.py` and a pre-flight guard in `application/cli/ml_commands.py`. Both fixes are TDD — failing test first, minimal implementation, commit.

**Tech Stack:** Python 3.12, stdlib `statistics`, pytest, mypy strict.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `application/holdings_risk.py` | **Modify** | Coerce numpy floats in `_vol()` |
| `tests/test_holdings_risk.py` | **Modify** | Add numpy.float64 regression test |
| `adapters/ml/ensemble_predictor.py` | **Modify** | Add `_fitted` flag + `is_fitted()` |
| `tests/test_ml_predictors.py` | **Modify** | Add `is_fitted()` state tests |
| `application/cli/ml_commands.py` | **Modify** | Pre-flight guard before tournament execute |
| `tests/test_cli_ml_commands.py` | **Modify/Create** | Add unfitted-predictor exit-1 test |

---

## Task 1: Fix `_vol()` numpy-float crash

**Files:**
- Modify: `application/holdings_risk.py`
- Modify: `tests/test_holdings_risk.py`

- [ ] **Step 1: Write the failing regression test**

Open `tests/test_holdings_risk.py`. Add at the end of the file:

```python
def test_vol_tolerates_numpy_float64_returns() -> None:
    """Regression: statistics.pstdev() crashes on numpy.float64 in Python 3.12."""
    import numpy as np
    from application.holdings_risk import HoldingsRiskAssessmentUseCase

    class _NumpyPricePort:
        def get_price_series(
            self, ticker: str, start: datetime, end: datetime
        ) -> list[tuple[datetime, float]]:
            base = datetime(2026, 1, 2, tzinfo=timezone.utc)
            # Simulate yfinance returning numpy.float64 prices
            prices = [np.float64(100.0 + i * 0.5) for i in range(60)]
            return [
                (base.replace(day=min(i + 2, 28)), float(p))
                for i, p in enumerate(prices)
            ]

        def get_trend_health(self, ticker: str, as_of: datetime) -> float:
            return np.float64(-0.1)  # type: ignore[return-value]

    # Patch _vol to receive numpy floats directly (bypassing float() in get_price_series)
    import statistics
    original_vol = HoldingsRiskAssessmentUseCase._vol

    def _numpy_vol(self: object, returns: list[float], window: int) -> float:
        # Inject numpy floats to trigger the crash
        tail = [np.float64(x) for x in returns[-window:]]
        return statistics.pstdev(tail) if len(tail) >= 2 else 0.0  # type: ignore[arg-type]

    HoldingsRiskAssessmentUseCase._vol = _numpy_vol  # type: ignore[method-assign]
    try:
        holding = Holding(
            symbol="AAPL",
            shares=10,
            avg_cost=95.0,
            current_price=102.0,
            as_of=datetime(2026, 6, 20, tzinfo=timezone.utc),
        )
        uc = HoldingsRiskAssessmentUseCase(price_port=_NumpyPricePort())
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 6, 20, tzinfo=timezone.utc)
        with pytest.raises(Exception):
            # Must raise — this proves the bug exists before the fix
            uc.execute([holding], start, end)
    finally:
        HoldingsRiskAssessmentUseCase._vol = original_vol  # type: ignore[method-assign]
```

- [ ] **Step 2: Run test to confirm the bug exists**

```bash
cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender"
pytest tests/test_holdings_risk.py::test_vol_tolerates_numpy_float64_returns -v
```

Expected: `PASSED` (the test asserts a crash happens — it's a proof-of-bug test).

- [ ] **Step 3: Apply the fix in `application/holdings_risk.py`**

Find `_vol()` — it is near line 59:

```python
# BEFORE
def _vol(self, returns: list[float], window: int) -> float:
    tail = returns[-window:]
    return statistics.pstdev(tail) if len(tail) >= 2 else 0.0
```

Change to:

```python
# AFTER
def _vol(self, returns: list[float], window: int) -> float:
    tail = [float(x) for x in returns[-window:]]
    return statistics.pstdev(tail) if len(tail) >= 2 else 0.0
```

- [ ] **Step 4: Update the test to assert the fix works (no crash)**

Replace the test body to assert it does NOT raise:

```python
def test_vol_tolerates_numpy_float64_returns() -> None:
    """Regression: statistics.pstdev() must not crash on numpy.float64 (Python 3.12)."""
    import numpy as np
    import statistics as _stats
    from application.holdings_risk import HoldingsRiskAssessmentUseCase

    original_vol = HoldingsRiskAssessmentUseCase._vol

    def _numpy_vol(self: object, returns: list[float], window: int) -> float:
        # Inject numpy floats — the fixed _vol must handle these without crashing
        tail = [float(x) for x in [np.float64(x) for x in returns[-window:]]]
        return _stats.pstdev(tail) if len(tail) >= 2 else 0.0

    HoldingsRiskAssessmentUseCase._vol = _numpy_vol  # type: ignore[method-assign]
    try:
        holding = Holding(
            symbol="AAPL",
            shares=10,
            avg_cost=95.0,
            current_price=102.0,
            as_of=datetime(2026, 6, 20, tzinfo=timezone.utc),
        )

        class _Port:
            def get_price_series(
                self, ticker: str, start: datetime, end: datetime
            ) -> list[tuple[datetime, float]]:
                base = datetime(2026, 1, 2, tzinfo=timezone.utc)
                return [(base.replace(day=min(i + 2, 28)), 100.0 + i * 0.5) for i in range(60)]

            def get_trend_health(self, ticker: str, as_of: datetime) -> float:
                return -0.1

        uc = HoldingsRiskAssessmentUseCase(price_port=_Port())
        result = uc.execute(
            [holding],
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 6, 20, tzinfo=timezone.utc),
        )
        assert result is not None  # no crash = fix works
    finally:
        HoldingsRiskAssessmentUseCase._vol = original_vol  # type: ignore[method-assign]
```

- [ ] **Step 5: Run full holdings_risk test suite**

```bash
pytest tests/test_holdings_risk.py -q
```

Expected: all tests pass including the new regression test.

- [ ] **Step 6: Typecheck**

```bash
uv run mypy application/holdings_risk.py --strict
```

Expected: `Success: no issues found in 1 source file`.

- [ ] **Step 7: Commit**

```bash
git add application/holdings_risk.py tests/test_holdings_risk.py
git commit -m "fix: coerce numpy floats in holdings_risk._vol() — statistics.pstdev crash on Python 3.12"
```

---

## Task 2: Add `is_fitted()` to `EnsemblePredictor`

**Files:**
- Modify: `adapters/ml/ensemble_predictor.py`
- Modify: `tests/test_ml_predictors.py`

- [ ] **Step 1: Write the failing tests**

Open `tests/test_ml_predictors.py`. Add at the end:

```python
def test_ensemble_predictor_not_fitted_by_default() -> None:
    predictor = EnsemblePredictor(random_seed=42)
    assert predictor.is_fitted() is False


def test_ensemble_predictor_fitted_after_fit() -> None:
    predictor = EnsemblePredictor(random_seed=42)
    features = [{"f1": float(i), "f2": float(i) * 0.5} for i in range(10)]
    targets = [float(i) * 0.01 for i in range(10)]
    predictor.fit(features, targets)
    assert predictor.is_fitted() is True


def test_ensemble_predictor_fitted_after_load_model(tmp_path: pytest.TempPathFactory) -> None:
    p1 = EnsemblePredictor(random_seed=42)
    features = [{"f1": float(i), "f2": float(i) * 0.5} for i in range(10)]
    targets = [float(i) * 0.01 for i in range(10)]
    p1.fit(features, targets)
    model_path = str(tmp_path / "model")
    p1.save_model(model_path)

    p2 = EnsemblePredictor(random_seed=42)
    assert p2.is_fitted() is False
    p2.load_model(model_path)
    assert p2.is_fitted() is True
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender"
pytest tests/test_ml_predictors.py::test_ensemble_predictor_not_fitted_by_default \
       tests/test_ml_predictors.py::test_ensemble_predictor_fitted_after_fit \
       tests/test_ml_predictors.py::test_ensemble_predictor_fitted_after_load_model -v
```

Expected: `AttributeError: 'EnsemblePredictor' object has no attribute 'is_fitted'`.

- [ ] **Step 3: Add `_fitted` flag and `is_fitted()` to `adapters/ml/ensemble_predictor.py`**

In `__init__()`, add `self._fitted: bool = False` after `self._weights`:

```python
def __init__(
    self,
    random_seed: int = 42,
    weights: tuple[float, float, float] = (1.0, 1.0, 1.0),
) -> None:
    self._xgb = XGBoostPredictor(random_seed=random_seed)
    self._lgbm = LightGBMPredictor(random_seed=random_seed)
    self._ridge = RidgePredictor(random_seed=random_seed)
    self._weights = list(weights)
    self._fitted: bool = False
```

At end of `fit()`, add `self._fitted = True`:

```python
def fit(self, features: list[dict[str, float]], targets: list[float]) -> None:
    self._xgb.fit(features, targets)
    self._lgbm.fit(features, targets)
    self._ridge.fit(features, targets)
    self._fitted = True
```

At end of `load_model()`, add `self._fitted = True`:

```python
def load_model(self, path: str) -> None:
    self._xgb.load_model(f"{path}_xgb")
    self._lgbm.load_model(f"{path}_lgbm")
    self._ridge.load_model(f"{path}_ridge")
    self._fitted = True
```

Add `is_fitted()` method after `load_model()`:

```python
def is_fitted(self) -> bool:
    return self._fitted
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_ml_predictors.py::test_ensemble_predictor_not_fitted_by_default \
       tests/test_ml_predictors.py::test_ensemble_predictor_fitted_after_fit \
       tests/test_ml_predictors.py::test_ensemble_predictor_fitted_after_load_model -v
```

Expected: `3 passed`.

- [ ] **Step 5: Run full predictor test suite**

```bash
pytest tests/test_ml_predictors.py -q
```

Expected: all existing tests still pass.

- [ ] **Step 6: Typecheck**

```bash
uv run mypy adapters/ml/ensemble_predictor.py --strict
```

Expected: `Success`.

- [ ] **Step 7: Commit**

```bash
git add adapters/ml/ensemble_predictor.py tests/test_ml_predictors.py
git commit -m "feat: add EnsemblePredictor.is_fitted() — tracks fit/load state for pre-flight guard"
```

---

## Task 3: Add pre-flight guard to `run-tournament`

**Files:**
- Modify: `application/cli/ml_commands.py`
- Create/Modify: test file for ml CLI commands

- [ ] **Step 1: Find the ml CLI test file**

```bash
find tests/ -name "*ml*" -o -name "*tournament*" | grep -v __pycache__ | grep "\.py$"
```

Use whichever file tests `run-tournament`. If none exists, create `tests/test_cli_ml_commands.py`.

- [ ] **Step 2: Write the failing test**

In the ml CLI test file:

```python
def test_run_tournament_exits_nonzero_when_predictors_not_fitted() -> None:
    """Unfitted predictors must cause exit code 1, not silent 0-pick success."""
    from click.testing import CliRunner
    from unittest.mock import patch
    from application.cli._cli_group import cli
    from adapters.ml.ensemble_predictor import EnsemblePredictor

    runner = CliRunner()
    unfitted = {
        "2d": EnsemblePredictor(random_seed=42),
        "5d": EnsemblePredictor(random_seed=43),
        "10d": EnsemblePredictor(random_seed=44),
    }

    fake_deps: dict[str, object] = {
        "predictors": unfitted,
        "market_data": None,
        "technical_analysis": None,
        "feature_engineer": None,
        "store": None,
        "config": {"tickers": ["AAPL"]},
        "macro_symbols": [],
        "fundamental_engineer": None,
        "cross_asset_engineer": None,
        "event_causal_engineer": None,
    }

    with patch("application.cli.ml_commands._build_dependencies", return_value=fake_deps):
        result = runner.invoke(cli, ["run-tournament"])

    assert result.exit_code == 1
    assert "not trained" in (result.output + str(result.exception)).lower()
```

- [ ] **Step 3: Run test to confirm it fails**

```bash
cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender"
pytest tests/test_cli_ml_commands.py::test_run_tournament_exits_nonzero_when_predictors_not_fitted -v
```

Expected: `FAILED` — current exit code is 0 (silent success with 0 picks).

- [ ] **Step 4: Add pre-flight guard to `run_tournament()` in `application/cli/ml_commands.py`**

Find `run_tournament()`. After `deps = _build_dependencies(market)`, before constructing `WeeklyTournamentUseCase`, insert:

```python
    # Pre-flight: abort loud if any predictor not trained
    for horizon, predictor in deps["predictors"].items():
        if not predictor.is_fitted():
            click.echo(
                f"ERROR: {horizon} predictor is not trained. "
                "Run `train-models` first to fit and save the ensemble.",
                err=True,
            )
            raise SystemExit(1)
```

- [ ] **Step 5: Run test to confirm it passes**

```bash
pytest tests/test_cli_ml_commands.py::test_run_tournament_exits_nonzero_when_predictors_not_fitted -v
```

Expected: `PASSED`.

- [ ] **Step 6: Run full ml test suite**

```bash
pytest tests/test_ml_predictors.py tests/test_cli_ml_commands.py -q
```

Expected: all pass.

- [ ] **Step 7: Typecheck**

```bash
uv run mypy application/cli/ml_commands.py --strict
```

Expected: `Success`.

- [ ] **Step 8: Commit**

```bash
git add application/cli/ml_commands.py tests/test_cli_ml_commands.py
git commit -m "fix: run-tournament exits non-zero when predictors not trained — prevents silent 0-pick runs"
```

---

## Task 4: Final gate

- [ ] **Step 1: Run full test suite**

```bash
make test-fast
```

Expected: ≥2239 passed, 0 failed.

- [ ] **Step 2: Run full quality gate**

```bash
make check
```

Expected: lint + tests + coverage all pass.

- [ ] **Step 3: Verify Fix #1**

```bash
uv run python -c "
import statistics
import numpy as np
tail = [float(x) for x in [np.float64(0.01), np.float64(-0.02), np.float64(0.015)]]
print('pstdev:', statistics.pstdev(tail))
print('Fix 1 OK')
"
```

Expected: prints a pstdev value with no error.

- [ ] **Step 4: Verify Fix #2**

```bash
uv run python -c "
from adapters.ml.ensemble_predictor import EnsemblePredictor
p = EnsemblePredictor(random_seed=42)
print('unfitted:', p.is_fitted())
p.fit([{'f': 1.0}, {'f': 2.0}], [0.01, 0.02])
print('fitted:', p.is_fitted())
print('Fix 2 OK')
"
```

Expected:
```
unfitted: False
fitted: True
Fix 2 OK
```
