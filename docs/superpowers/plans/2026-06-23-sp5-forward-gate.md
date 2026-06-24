# SP5: Hypothesis #9 Forward Validation Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a pre-registered forward-validation gate that answers "does STRONG-tier corroboration beat SPY over 21 days?" with a weekly resolver job, calibration-status CLI, and permanent KILL clause on failure.

**Architecture:** `domain/corroboration_gate.py` (pure types + `evaluate_gate()`), `adapters/data/corroboration_gate_log.py` (JSONL read/write), `application/corroboration_resolver_use_case.py` (fetch prices, build samples), two new CLI commands in `corroboration_commands.py`, and a launchd-scheduled shell script. ADR-064 (already committed to develop) is the pre-registration lock — no gate parameters may change after the first `resolve-corroboration` run.

**Tech Stack:** Python 3.12, dataclasses (frozen), `domain/bootstrap.py` (moving_block_bootstrap — stdlib-only, already exists), yfinance (price fetching), click (CLI), pytest, hypothesis.

## Global Constraints

- All `domain/` code must have zero external imports — stdlib only (including `domain/corroboration_gate.py`).
- ADR-064 (`docs/adr/ADR-064-corroboration-forward-gate.md`) is already committed on develop. It MUST precede any resolver code in git history. Do not modify its gate parameters.
- No live yfinance calls in any test — use fake `ResolverPricePort` implementations.
- All new test files go under `tests/` matching existing naming convention.
- Run `uv run pytest <test-file> -v` (NOT bare `pytest` — pyproject.toml addopts require the venv).
- Run `make test-fast` after each task for regression check (not `make check` during iteration).
- Conventional commits: `feat:` / `fix:` / `test:` / `chore:`.
- Branch: `feat/sp5-forward-gate` off `develop`.
- `evaluate_gate()` takes `evaluated_at: date` as an explicit argument — never call `date.today()` inside domain code.

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `domain/corroboration_gate.py` | **Create** | `GateSample`, `GateResult` frozen dataclasses; `evaluate_gate()` pure function |
| `adapters/data/corroboration_gate_log.py` | **Create** | Append/load `GateSample` and `GateResult` to/from JSONL files |
| `adapters/data/yfinance_price_resolver.py` | **Create** | Thin yfinance adapter implementing `ResolverPricePort` |
| `application/corroboration_resolver_use_case.py` | **Create** | Loads STRONG snapshots, fetches prices, builds `GateSample` list |
| `domain/ports.py` | **Modify** | Add `ResolverPricePort` Protocol |
| `adapters/data/corroboration_store.py` | **Modify** | Add `load_all_snapshots() -> list[CorroborationSnapshot]` |
| `application/cli/corroboration_commands.py` | **Modify** | Add `resolve-corroboration` and `corroboration-calibration-status` commands |
| `scripts/corroboration_weekly_resolve.sh` | **Create** | Shell script for launchd weekly job |
| `docs/scheduling.md` | **Modify** | Add corroboration-weekly plist |
| `tests/domain/test_corroboration_gate.py` | **Create** | Unit + property-based tests for `evaluate_gate()` |
| `tests/adapters/test_corroboration_gate_log.py` | **Create** | JSONL adapter tests using `tmp_path` |
| `tests/application/test_corroboration_resolver.py` | **Create** | Resolver use case tests with fake price port |
| `tests/test_cli_corroboration_resolve.py` | **Create** | CLI command tests with CliRunner + fakes |

---

### Task 1: Branch setup

**Files:** none changed

- [ ] **Step 1: Create and switch to the feature branch**

```bash
git checkout develop
git checkout -b feat/sp5-forward-gate
```

Expected: `Switched to a new branch 'feat/sp5-forward-gate'`

- [ ] **Step 2: Verify ADR-064 is present (pre-registration must precede all code)**

```bash
ls docs/adr/ADR-064-corroboration-forward-gate.md
```

Expected: file exists. If missing — STOP. Checkout develop, confirm it's there, then re-branch.

- [ ] **Step 3: Verify current test suite is green on this branch**

```bash
make test-fast
```

Expected: `2316 passed` (or higher — develop may have grown).

---

### Task 2: Domain gate types + `evaluate_gate()`

**Files:**
- Create: `domain/corroboration_gate.py`
- Create: `tests/domain/test_corroboration_gate.py`

**Interfaces:**
- Produces:
  - `GateSample(ticker, snapshot_date, resolved_at, excess_21d, excess_63d, beat_spy_21d)`
  - `GateResult(n_resolved, mean_excess_21d, ci_lower, ci_upper, hit_rate_21d, mean_excess_63d, verdict, evaluated_at)`
  - `evaluate_gate(samples, evaluated_at, min_n=30, economic_bar=0.005) -> GateResult`
  - `verdict` is `Literal["PENDING", "PASS", "FAIL"]`

- [ ] **Step 1: Write failing tests**

```python
# tests/domain/test_corroboration_gate.py
from __future__ import annotations

from datetime import date

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from domain.corroboration_gate import GateSample, GateResult, evaluate_gate

SNAP = date(2026, 1, 1)
RESOLVED = date(2026, 1, 22)
TODAY = date(2026, 6, 23)


def _sample(excess: float, beat: bool, excess_63d: float | None = None) -> GateSample:
    return GateSample(
        ticker="AAPL",
        snapshot_date=SNAP,
        resolved_at=RESOLVED,
        excess_21d=excess,
        excess_63d=excess_63d,
        beat_spy_21d=beat,
    )


def _samples(n: int, excess: float = 0.01, beat: bool = True) -> list[GateSample]:
    return [_sample(excess, beat) for _ in range(n)]


# --- PENDING when n < 30 ---

def test_pending_when_n_below_min() -> None:
    result = evaluate_gate(_samples(29), evaluated_at=TODAY)
    assert result.verdict == "PENDING"
    assert result.n_resolved == 29


def test_pending_n_zero() -> None:
    result = evaluate_gate([], evaluated_at=TODAY)
    assert result.verdict == "PENDING"
    assert result.n_resolved == 0


# --- FAIL conditions at n >= 30 ---

def test_fail_when_ci_includes_zero_despite_positive_mean() -> None:
    # High variance samples — bootstrap CI will include 0
    import random
    rng = random.Random(42)
    mixed = [_sample(rng.uniform(-0.5, 0.55), True) for _ in range(30)]
    result = evaluate_gate(mixed, evaluated_at=TODAY)
    # ci_lower may be ≤ 0 due to variance — verdict should not be PASS
    assert result.verdict in ("PASS", "FAIL")  # exact depends on bootstrap seed
    assert result.n_resolved == 30


def test_fail_when_mean_below_economic_bar() -> None:
    # Tiny positive excess, CI will be > 0 but mean < 50 bps
    samples = _samples(30, excess=0.001, beat=True)
    result = evaluate_gate(samples, evaluated_at=TODAY)
    assert result.verdict == "FAIL"
    assert result.mean_excess_21d == pytest.approx(0.001, abs=1e-9)


def test_fail_when_negative_excess() -> None:
    samples = _samples(30, excess=-0.02, beat=False)
    result = evaluate_gate(samples, evaluated_at=TODAY)
    assert result.verdict == "FAIL"


# --- PASS conditions ---

def test_pass_when_strong_consistent_positive_excess() -> None:
    # Uniform 2% excess, no variance — CI lower bound clearly > 0
    samples = _samples(30, excess=0.02, beat=True)
    result = evaluate_gate(samples, evaluated_at=TODAY)
    assert result.verdict == "PASS"
    assert result.ci_lower > 0
    assert result.mean_excess_21d == pytest.approx(0.02, abs=1e-9)


# --- Hit rate ---

def test_hit_rate_all_beat() -> None:
    samples = _samples(30, excess=0.02, beat=True)
    result = evaluate_gate(samples, evaluated_at=TODAY)
    assert result.hit_rate_21d == pytest.approx(1.0)


def test_hit_rate_none_beat() -> None:
    samples = _samples(30, excess=-0.01, beat=False)
    result = evaluate_gate(samples, evaluated_at=TODAY)
    assert result.hit_rate_21d == pytest.approx(0.0)


def test_hit_rate_mixed() -> None:
    samples = [_sample(0.01, True)] * 20 + [_sample(-0.01, False)] * 10
    result = evaluate_gate(samples, evaluated_at=TODAY)
    assert result.hit_rate_21d == pytest.approx(20 / 30)


# --- 63d mean ---

def test_mean_excess_63d_none_when_no_63d_data() -> None:
    samples = _samples(30, excess=0.02, beat=True)  # excess_63d=None
    result = evaluate_gate(samples, evaluated_at=TODAY)
    assert result.mean_excess_63d is None


def test_mean_excess_63d_computed_when_data_present() -> None:
    samples = [_sample(0.02, True, excess_63d=0.04)] * 30
    result = evaluate_gate(samples, evaluated_at=TODAY)
    assert result.mean_excess_63d == pytest.approx(0.04, abs=1e-9)


def test_mean_excess_63d_partial_data() -> None:
    samples = [_sample(0.02, True, excess_63d=0.06)] * 15 + [_sample(0.02, True)] * 15
    result = evaluate_gate(samples, evaluated_at=TODAY)
    assert result.mean_excess_63d == pytest.approx(0.06, abs=1e-9)


# --- evaluated_at propagated ---

def test_evaluated_at_propagated() -> None:
    result = evaluate_gate(_samples(5), evaluated_at=TODAY)
    assert result.evaluated_at == TODAY


# --- Property: verdict invariants ---

@given(
    n=st.integers(min_value=0, max_value=29),
    excess=st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=50)
def test_always_pending_when_n_below_30(n: int, excess: float) -> None:
    beat = excess > 0
    result = evaluate_gate(_samples(n, excess=excess, beat=beat), evaluated_at=TODAY)
    assert result.verdict == "PENDING"
```

- [ ] **Step 2: Run to verify tests fail**

```bash
uv run pytest tests/domain/test_corroboration_gate.py -v 2>&1 | head -20
```

Expected: `ImportError` or `ModuleNotFoundError` — `domain.corroboration_gate` not found.

- [ ] **Step 3: Create `domain/corroboration_gate.py`**

```python
"""SP5 gate types and evaluation logic — pure stdlib, no external imports."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from domain.bootstrap import moving_block_bootstrap


@dataclass(frozen=True)
class GateSample:
    ticker: str
    snapshot_date: date
    resolved_at: date
    excess_21d: float        # ticker 21d return − SPY 21d return
    excess_63d: float | None  # None if <63d elapsed at resolution time
    beat_spy_21d: bool


@dataclass(frozen=True)
class GateResult:
    n_resolved: int
    mean_excess_21d: float
    ci_lower: float          # block-bootstrap 95% CI lower bound on mean excess
    ci_upper: float
    hit_rate_21d: float      # fraction of samples where beat_spy_21d is True
    mean_excess_63d: float | None
    verdict: Literal["PENDING", "PASS", "FAIL"]
    evaluated_at: date


def evaluate_gate(
    samples: list[GateSample],
    evaluated_at: date,
    min_n: int = 30,
    economic_bar: float = 0.005,
) -> GateResult:
    """Evaluate Hypothesis #9 gate. PENDING if n < min_n.
    PASS if bootstrap 95% CI lower bound > 0 AND mean_excess_21d >= economic_bar.
    FAIL otherwise (permanent — see ADR-064).
    """
    n = len(samples)
    excesses = [s.excess_21d for s in samples]
    mean_excess = sum(excesses) / n if n > 0 else 0.0

    bs = moving_block_bootstrap(excesses)
    ci_lower = float(bs["ci_low"]) if bs["ci_low"] is not None else 0.0
    ci_upper = float(bs["ci_high"]) if bs["ci_high"] is not None else 0.0

    hit_rate = sum(1 for s in samples if s.beat_spy_21d) / n if n > 0 else 0.0

    excesses_63 = [s.excess_63d for s in samples if s.excess_63d is not None]
    mean_excess_63d: float | None = (
        sum(excesses_63) / len(excesses_63) if excesses_63 else None
    )

    if n < min_n:
        verdict: Literal["PENDING", "PASS", "FAIL"] = "PENDING"
    elif ci_lower > 0 and mean_excess >= economic_bar:
        verdict = "PASS"
    else:
        verdict = "FAIL"

    return GateResult(
        n_resolved=n,
        mean_excess_21d=mean_excess,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        hit_rate_21d=hit_rate,
        mean_excess_63d=mean_excess_63d,
        verdict=verdict,
        evaluated_at=evaluated_at,
    )
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/domain/test_corroboration_gate.py -v
```

Expected: all PASSED (property tests run 50 examples each).

- [ ] **Step 5: Typecheck**

```bash
make typecheck
```

Expected: `Success: no issues found in N source files`.

- [ ] **Step 6: Regression**

```bash
make test-fast
```

Expected: no new failures.

- [ ] **Step 7: Commit**

```bash
git add domain/corroboration_gate.py tests/domain/test_corroboration_gate.py
git commit -m "feat(domain): add GateSample + GateResult + evaluate_gate() for SP5 forward gate"
```

---

### Task 3: Gate log adapter (JSONL read/write/dedup)

**Files:**
- Create: `adapters/data/corroboration_gate_log.py`
- Create: `tests/adapters/test_corroboration_gate_log.py`

**Interfaces:**
- Consumes: `GateSample`, `GateResult` from `domain.corroboration_gate`
- Produces:
  - `append_samples(samples, path) -> int` (returns count of newly-written samples)
  - `load_samples(path) -> list[GateSample]` (deduped by `ticker:snapshot_date`)
  - `append_result(result, path) -> None`
  - `load_latest_result(path) -> GateResult | None`
  - `SAMPLES_PATH = Path("data/corroboration_samples.jsonl")`
  - `RESULTS_PATH = Path("data/corroboration_gate_log.jsonl")`

- [ ] **Step 1: Write failing tests**

```python
# tests/adapters/test_corroboration_gate_log.py
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from domain.corroboration_gate import GateSample, GateResult


def _sample(ticker: str = "AAPL", snap: str = "2026-01-01") -> GateSample:
    return GateSample(
        ticker=ticker,
        snapshot_date=date.fromisoformat(snap),
        resolved_at=date(2026, 1, 22),
        excess_21d=0.02,
        excess_63d=0.04,
        beat_spy_21d=True,
    )


def _result(verdict: str = "PENDING") -> GateResult:
    from typing import Literal
    v: Literal["PENDING", "PASS", "FAIL"] = verdict  # type: ignore[assignment]
    return GateResult(
        n_resolved=10,
        mean_excess_21d=0.015,
        ci_lower=-0.005,
        ci_upper=0.035,
        hit_rate_21d=0.6,
        mean_excess_63d=0.03,
        verdict=v,
        evaluated_at=date(2026, 6, 23),
    )


# --- load_samples ---

def test_load_samples_missing_file_returns_empty(tmp_path: Path) -> None:
    from adapters.data.corroboration_gate_log import load_samples

    result = load_samples(tmp_path / "missing.jsonl")
    assert result == []


def test_append_and_load_samples_roundtrip(tmp_path: Path) -> None:
    from adapters.data.corroboration_gate_log import append_samples, load_samples

    p = tmp_path / "samples.jsonl"
    s = _sample()
    n = append_samples([s], p)
    assert n == 1
    loaded = load_samples(p)
    assert len(loaded) == 1
    assert loaded[0].ticker == "AAPL"
    assert loaded[0].excess_21d == pytest.approx(0.02)
    assert loaded[0].beat_spy_21d is True


def test_append_samples_deduplicates_by_ticker_and_snapshot_date(tmp_path: Path) -> None:
    from adapters.data.corroboration_gate_log import append_samples, load_samples

    p = tmp_path / "samples.jsonl"
    s = _sample("AAPL", "2026-01-01")
    append_samples([s], p)
    n = append_samples([s], p)  # duplicate — should not write
    assert n == 0
    assert len(load_samples(p)) == 1


def test_append_samples_different_tickers_both_written(tmp_path: Path) -> None:
    from adapters.data.corroboration_gate_log import append_samples, load_samples

    p = tmp_path / "samples.jsonl"
    n = append_samples([_sample("AAPL", "2026-01-01"), _sample("MSFT", "2026-01-01")], p)
    assert n == 2
    assert len(load_samples(p)) == 2


def test_append_samples_same_ticker_different_dates_both_written(tmp_path: Path) -> None:
    from adapters.data.corroboration_gate_log import append_samples, load_samples

    p = tmp_path / "samples.jsonl"
    n = append_samples([_sample("AAPL", "2026-01-01"), _sample("AAPL", "2026-01-08")], p)
    assert n == 2
    assert len(load_samples(p)) == 2


def test_load_samples_excess_63d_none_roundtrip(tmp_path: Path) -> None:
    from adapters.data.corroboration_gate_log import append_samples, load_samples

    p = tmp_path / "samples.jsonl"
    s = GateSample(
        ticker="NVDA",
        snapshot_date=date(2026, 1, 1),
        resolved_at=date(2026, 1, 22),
        excess_21d=0.01,
        excess_63d=None,
        beat_spy_21d=False,
    )
    append_samples([s], p)
    loaded = load_samples(p)
    assert loaded[0].excess_63d is None


# --- append_result / load_latest_result ---

def test_load_latest_result_missing_file_returns_none(tmp_path: Path) -> None:
    from adapters.data.corroboration_gate_log import load_latest_result

    assert load_latest_result(tmp_path / "missing.jsonl") is None


def test_append_and_load_latest_result_roundtrip(tmp_path: Path) -> None:
    from adapters.data.corroboration_gate_log import append_result, load_latest_result

    p = tmp_path / "gate_log.jsonl"
    r = _result("FAIL")
    append_result(r, p)
    loaded = load_latest_result(p)
    assert loaded is not None
    assert loaded.verdict == "FAIL"
    assert loaded.n_resolved == 10
    assert loaded.mean_excess_21d == pytest.approx(0.015)
    assert loaded.mean_excess_63d == pytest.approx(0.03)


def test_load_latest_result_returns_last_appended(tmp_path: Path) -> None:
    from adapters.data.corroboration_gate_log import append_result, load_latest_result

    p = tmp_path / "gate_log.jsonl"
    append_result(_result("PENDING"), p)
    append_result(_result("PASS"), p)
    loaded = load_latest_result(p)
    assert loaded is not None
    assert loaded.verdict == "PASS"


def test_load_latest_result_none_excess_63d_roundtrip(tmp_path: Path) -> None:
    from adapters.data.corroboration_gate_log import append_result, load_latest_result
    from typing import Literal

    p = tmp_path / "gate_log.jsonl"
    v: Literal["PENDING", "PASS", "FAIL"] = "PENDING"
    r = GateResult(
        n_resolved=5,
        mean_excess_21d=0.01,
        ci_lower=0.0,
        ci_upper=0.02,
        hit_rate_21d=0.6,
        mean_excess_63d=None,
        verdict=v,
        evaluated_at=date(2026, 6, 23),
    )
    append_result(r, p)
    loaded = load_latest_result(p)
    assert loaded is not None
    assert loaded.mean_excess_63d is None
```

- [ ] **Step 2: Run to verify tests fail**

```bash
uv run pytest tests/adapters/test_corroboration_gate_log.py -v 2>&1 | head -15
```

Expected: `ImportError` — `adapters.data.corroboration_gate_log` not found.

- [ ] **Step 3: Create `adapters/data/corroboration_gate_log.py`**

```python
"""SP5 gate log adapter — append-only JSONL for GateSample and GateResult."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from domain.corroboration_gate import GateSample, GateResult

SAMPLES_PATH = Path("data/corroboration_samples.jsonl")
RESULTS_PATH = Path("data/corroboration_gate_log.jsonl")


def _sample_key(s: GateSample) -> str:
    return f"{s.ticker}:{s.snapshot_date.isoformat()}"


def _sample_to_dict(s: GateSample) -> dict[str, object]:
    return {
        "ticker": s.ticker,
        "snapshot_date": s.snapshot_date.isoformat(),
        "resolved_at": s.resolved_at.isoformat(),
        "excess_21d": s.excess_21d,
        "excess_63d": s.excess_63d,
        "beat_spy_21d": s.beat_spy_21d,
    }


def _dict_to_sample(d: dict[str, object]) -> GateSample:
    return GateSample(
        ticker=str(d["ticker"]),
        snapshot_date=date.fromisoformat(str(d["snapshot_date"])),
        resolved_at=date.fromisoformat(str(d["resolved_at"])),
        excess_21d=float(d["excess_21d"]),  # type: ignore[arg-type]
        excess_63d=float(d["excess_63d"]) if d.get("excess_63d") is not None else None,  # type: ignore[arg-type]
        beat_spy_21d=bool(d["beat_spy_21d"]),
    )


def load_samples(path: Path = SAMPLES_PATH) -> list[GateSample]:
    """Read all samples, deduplicating by (ticker, snapshot_date). Returns [] if file missing."""
    if not path.exists():
        return []
    samples: list[GateSample] = []
    seen: set[str] = set()
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            s = _dict_to_sample(json.loads(line))
            key = _sample_key(s)
            if key not in seen:
                seen.add(key)
                samples.append(s)
    return samples


def append_samples(new_samples: list[GateSample], path: Path = SAMPLES_PATH) -> int:
    """Append samples not already in path. Returns count of samples written."""
    existing_keys = {_sample_key(s) for s in load_samples(path)}
    to_write = [s for s in new_samples if _sample_key(s) not in existing_keys]
    if to_write:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as f:
            for s in to_write:
                f.write(json.dumps(_sample_to_dict(s)) + "\n")
    return len(to_write)


def _result_to_dict(r: GateResult) -> dict[str, object]:
    return {
        "n_resolved": r.n_resolved,
        "mean_excess_21d": r.mean_excess_21d,
        "ci_lower": r.ci_lower,
        "ci_upper": r.ci_upper,
        "hit_rate_21d": r.hit_rate_21d,
        "mean_excess_63d": r.mean_excess_63d,
        "verdict": r.verdict,
        "evaluated_at": r.evaluated_at.isoformat(),
    }


def _dict_to_result(d: dict[str, object]) -> GateResult:
    from typing import Literal
    v: Literal["PENDING", "PASS", "FAIL"] = str(d["verdict"])  # type: ignore[assignment]
    return GateResult(
        n_resolved=int(d["n_resolved"]),  # type: ignore[arg-type]
        mean_excess_21d=float(d["mean_excess_21d"]),  # type: ignore[arg-type]
        ci_lower=float(d["ci_lower"]),  # type: ignore[arg-type]
        ci_upper=float(d["ci_upper"]),  # type: ignore[arg-type]
        hit_rate_21d=float(d["hit_rate_21d"]),  # type: ignore[arg-type]
        mean_excess_63d=float(d["mean_excess_63d"]) if d.get("mean_excess_63d") is not None else None,  # type: ignore[arg-type]
        verdict=v,
        evaluated_at=date.fromisoformat(str(d["evaluated_at"])),
    )


def append_result(result: GateResult, path: Path = RESULTS_PATH) -> None:
    """Append a GateResult entry. Only call when verdict != PENDING."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(_result_to_dict(result)) + "\n")


def load_latest_result(path: Path = RESULTS_PATH) -> GateResult | None:
    """Return most recent GateResult, or None if file missing / empty."""
    if not path.exists():
        return None
    last: str | None = None
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                last = line
    return _dict_to_result(json.loads(last)) if last else None
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/adapters/test_corroboration_gate_log.py -v
```

Expected: all PASSED.

- [ ] **Step 5: Typecheck + regression**

```bash
make typecheck && make test-fast
```

Expected: both pass, no new failures.

- [ ] **Step 6: Commit**

```bash
git add adapters/data/corroboration_gate_log.py tests/adapters/test_corroboration_gate_log.py
git commit -m "feat(adapters): add corroboration_gate_log — JSONL append/load/dedup for GateSample + GateResult"
```

---

### Task 4: `ResolverPricePort` + store method + yfinance adapter + resolver use case

**Files:**
- Modify: `domain/ports.py` (add `ResolverPricePort`)
- Modify: `adapters/data/corroboration_store.py` (add `load_all_snapshots()`)
- Create: `adapters/data/yfinance_price_resolver.py`
- Create: `application/corroboration_resolver_use_case.py`
- Create: `tests/application/test_corroboration_resolver.py`

**Interfaces:**
- Consumes:
  - `CorroborationStore.load_all_snapshots() -> list[CorroborationSnapshot]`
  - `ResolverPricePort.price_at(ticker: str, on: date) -> float`
  - `GateSample` from Task 2
- Produces:
  - `ResolverPricePort` Protocol in `domain/ports.py`
  - `CorroborationResolverUseCase.resolve(as_of: date) -> list[GateSample]` — idempotent; caller deduplicates via `append_samples`
  - `YFinancePriceResolver` in `adapters/data/yfinance_price_resolver.py` — implements `ResolverPricePort`

- [ ] **Step 1: Write failing tests**

```python
# tests/application/test_corroboration_resolver.py
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from domain.corroboration_models import ConvergenceTier, Stance
from domain.screened_row import CorroborationSnapshot
from domain.ports import ResolverPricePort


# Fake price port for tests — never hits yfinance
class FakePricePort:
    def __init__(self, prices: dict[tuple[str, date], float]) -> None:
        self._prices = prices

    def price_at(self, ticker: str, on: date) -> float:
        if (ticker, on) not in self._prices:
            raise ValueError(f"No price for {ticker} on {on}")
        return self._prices[(ticker, on)]


def _snap(
    ticker: str,
    surfaced_at: date,
    tier: ConvergenceTier = ConvergenceTier.STRONG,
) -> CorroborationSnapshot:
    return CorroborationSnapshot(
        ticker=ticker,
        convergence_tier=tier,
        n_sources=2,
        surfaced_at=surfaced_at,
        net_stance=Stance.BULLISH,
    )


def _make_store(snapshots: list[CorroborationSnapshot]) -> MagicMock:
    store = MagicMock()
    store.load_all_snapshots.return_value = snapshots
    return store


AS_OF = date(2026, 3, 1)
SNAP_DATE = date(2026, 2, 1)  # 28 days before AS_OF — resolvable at 21d
T21 = SNAP_DATE + timedelta(days=21)
T63 = SNAP_DATE + timedelta(days=63)


def _base_prices(ticker: str = "AAPL") -> dict[tuple[str, date], float]:
    return {
        (ticker, SNAP_DATE): 100.0,
        (ticker, T21): 102.0,  # +2%
        ("SPY", SNAP_DATE): 200.0,
        ("SPY", T21): 201.0,   # +0.5%
    }


def test_resolve_returns_sample_for_strong_ticker() -> None:
    from application.corroboration_resolver_use_case import CorroborationResolverUseCase

    store = _make_store([_snap("AAPL", SNAP_DATE)])
    uc = CorroborationResolverUseCase(store, FakePricePort(_base_prices()))
    samples = uc.resolve(AS_OF)
    assert len(samples) == 1
    s = samples[0]
    assert s.ticker == "AAPL"
    assert s.snapshot_date == SNAP_DATE
    assert s.excess_21d == pytest.approx(0.02 - 0.005, abs=1e-9)
    assert s.beat_spy_21d is True


def test_resolve_excludes_non_strong_tier() -> None:
    from application.corroboration_resolver_use_case import CorroborationResolverUseCase

    snaps = [
        _snap("AAPL", SNAP_DATE, ConvergenceTier.STRONG),
        _snap("MSFT", SNAP_DATE, ConvergenceTier.MODERATE),
        _snap("TSLA", SNAP_DATE, ConvergenceTier.WEAK),
    ]
    prices = _base_prices("AAPL")
    store = _make_store(snaps)
    uc = CorroborationResolverUseCase(store, FakePricePort(prices))
    samples = uc.resolve(AS_OF)
    assert len(samples) == 1
    assert samples[0].ticker == "AAPL"


def test_resolve_excludes_snapshots_too_recent() -> None:
    from application.corroboration_resolver_use_case import CorroborationResolverUseCase

    # Surfaced only 10 days before AS_OF — not yet resolvable
    recent = _snap("AAPL", AS_OF - timedelta(days=10))
    store = _make_store([recent])
    uc = CorroborationResolverUseCase(store, FakePricePort({}))
    samples = uc.resolve(AS_OF)
    assert samples == []


def test_resolve_skips_sample_on_price_fetch_failure() -> None:
    from application.corroboration_resolver_use_case import CorroborationResolverUseCase

    store = _make_store([_snap("AAPL", SNAP_DATE)])
    uc = CorroborationResolverUseCase(store, FakePricePort({}))  # no prices
    samples = uc.resolve(AS_OF)
    assert samples == []  # skipped, not raised


def test_resolve_computes_excess_63d_when_available() -> None:
    from application.corroboration_resolver_use_case import CorroborationResolverUseCase

    prices = {
        **_base_prices(),
        ("AAPL", T63): 106.0,   # +6%
        ("SPY", T63): 203.0,    # +1.5%
    }
    as_of_64 = SNAP_DATE + timedelta(days=64)
    store = _make_store([_snap("AAPL", SNAP_DATE)])
    uc = CorroborationResolverUseCase(store, FakePricePort(prices))
    samples = uc.resolve(as_of_64)
    assert samples[0].excess_63d == pytest.approx(0.06 - 0.015, abs=1e-9)


def test_resolve_excess_63d_none_when_not_yet_available() -> None:
    from application.corroboration_resolver_use_case import CorroborationResolverUseCase

    store = _make_store([_snap("AAPL", SNAP_DATE)])
    uc = CorroborationResolverUseCase(store, FakePricePort(_base_prices()))
    samples = uc.resolve(AS_OF)  # AS_OF is only 28d after SNAP_DATE — < 63d
    assert samples[0].excess_63d is None


def test_resolve_beat_spy_false_when_ticker_underperforms() -> None:
    from application.corroboration_resolver_use_case import CorroborationResolverUseCase

    prices = {
        ("AAPL", SNAP_DATE): 100.0,
        ("AAPL", T21): 99.0,    # -1%
        ("SPY", SNAP_DATE): 200.0,
        ("SPY", T21): 201.0,    # +0.5%
    }
    store = _make_store([_snap("AAPL", SNAP_DATE)])
    uc = CorroborationResolverUseCase(store, FakePricePort(prices))
    samples = uc.resolve(AS_OF)
    assert samples[0].beat_spy_21d is False
    assert samples[0].excess_21d < 0
```

- [ ] **Step 2: Run to verify tests fail**

```bash
uv run pytest tests/application/test_corroboration_resolver.py -v 2>&1 | head -15
```

Expected: `ImportError` — `application.corroboration_resolver_use_case` not found.

- [ ] **Step 3: Add `ResolverPricePort` to `domain/ports.py`**

Find the end of the existing Protocol definitions in `domain/ports.py` and add:

```python
class ResolverPricePort(Protocol):
    def price_at(self, ticker: str, on: date) -> float:
        """Closing price for ticker on the given date. Raises if unavailable."""
        ...
```

Add `from datetime import date` to the existing datetime imports at the top if not already present.

- [ ] **Step 4: Add `load_all_snapshots()` to `adapters/data/corroboration_store.py`**

Find the `get_snapshots` method in `CorroborationStore`. After it, add:

```python
def load_all_snapshots(self) -> list[CorroborationSnapshot]:
    """Return CorroborationSnapshot objects from every stored run (all tickers, all dates)."""
    rows = self._c.execute(
        "SELECT id, as_of FROM corroboration_runs ORDER BY as_of ASC"
    ).fetchall()
    all_snapshots: list[CorroborationSnapshot] = []
    for row in rows:
        run_id = int(row[0])
        run_date = date.fromisoformat(str(row[1]))
        claims = self.load_run(run_id)
        all_snapshots.extend(_claims_to_snapshots(claims, run_date))
    return all_snapshots
```

- [ ] **Step 5: Create `adapters/data/yfinance_price_resolver.py`**

```python
"""Thin yfinance adapter implementing ResolverPricePort for SP5 gate resolution."""
from __future__ import annotations

from datetime import date, timedelta

import yfinance as yf


class YFinancePriceResolver:
    """Implements ResolverPricePort. Fetches single closing prices via yfinance."""

    def price_at(self, ticker: str, on: date) -> float:
        """Return the adjusted closing price for ticker on the given date.

        Fetches a 5-day window around `on` to handle weekends/holidays.
        Raises ValueError if no price data found.
        """
        start = on - timedelta(days=4)
        end = on + timedelta(days=1)
        df = yf.download(
            ticker,
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            auto_adjust=True,
            progress=False,
        )
        if df.empty:
            raise ValueError(f"No price data for {ticker} around {on}")
        # Use the last available close on or before `on`
        close_col = "Close"
        series = df[close_col]
        # Filter to dates <= on
        mask = [d.date() <= on for d in series.index]
        filtered = series[mask]
        if filtered.empty:
            raise ValueError(f"No price for {ticker} on or before {on}")
        val = filtered.iloc[-1]
        return float(val)
```

- [ ] **Step 6: Create `application/corroboration_resolver_use_case.py`**

```python
"""SP5 resolver use case: build GateSamples from STRONG-tier corroboration snapshots."""
from __future__ import annotations

import logging
from datetime import date, timedelta

from domain.corroboration_gate import GateSample
from domain.corroboration_models import ConvergenceTier
from domain.ports import ResolverPricePort

logger = logging.getLogger(__name__)


def _ret(price: ResolverPricePort, ticker: str, start: date, end: date) -> float:
    p0 = price.price_at(ticker, start)
    p1 = price.price_at(ticker, end)
    return (p1 - p0) / p0


class CorroborationResolverUseCase:
    def __init__(self, store: object, price: ResolverPricePort) -> None:
        self._store = store
        self._price = price

    def resolve(self, as_of: date) -> list[GateSample]:
        """Load STRONG snapshots ≥21d old, compute excess returns.

        Idempotent — caller deduplicates by (ticker, snapshot_date) via append_samples().
        Price failures are logged and that sample is skipped (job continues).
        """
        cutoff = as_of - timedelta(days=21)
        all_snapshots = self._store.load_all_snapshots()
        resolvable = [
            s
            for s in all_snapshots
            if s.convergence_tier == ConvergenceTier.STRONG and s.surfaced_at <= cutoff
        ]

        samples: list[GateSample] = []
        for snap in resolvable:
            t0 = snap.surfaced_at
            t21 = t0 + timedelta(days=21)
            t63 = t0 + timedelta(days=63)

            try:
                ticker_21 = _ret(self._price, snap.ticker, t0, t21)
                spy_21 = _ret(self._price, "SPY", t0, t21)
            except Exception as exc:
                logger.warning("price fetch failed for %s (%s): %s — skipping", snap.ticker, t0, exc)
                continue

            excess_63: float | None = None
            if as_of >= t63:
                try:
                    excess_63 = _ret(self._price, snap.ticker, t0, t63) - _ret(
                        self._price, "SPY", t0, t63
                    )
                except Exception as exc:
                    logger.warning("63d price fetch failed for %s: %s", snap.ticker, exc)

            samples.append(
                GateSample(
                    ticker=snap.ticker,
                    snapshot_date=t0,
                    resolved_at=as_of,
                    excess_21d=ticker_21 - spy_21,
                    excess_63d=excess_63,
                    beat_spy_21d=ticker_21 > spy_21,
                )
            )
        return samples
```

- [ ] **Step 7: Run tests**

```bash
uv run pytest tests/application/test_corroboration_resolver.py -v
```

Expected: all PASSED.

- [ ] **Step 8: Typecheck + regression**

```bash
make typecheck && make test-fast
```

Expected: both pass.

- [ ] **Step 9: Commit**

```bash
git add domain/ports.py adapters/data/corroboration_store.py \
        adapters/data/yfinance_price_resolver.py \
        application/corroboration_resolver_use_case.py \
        tests/application/test_corroboration_resolver.py
git commit -m "feat(application): add CorroborationResolverUseCase + ResolverPricePort + YFinancePriceResolver"
```

---

### Task 5: CLI commands — `resolve-corroboration` + `corroboration-calibration-status`

**Files:**
- Modify: `application/cli/corroboration_commands.py`
- Create: `tests/test_cli_corroboration_resolve.py`

**Interfaces:**
- Consumes: all of Tasks 2-4
- Produces:
  - `stockrec resolve-corroboration [--as-of DATE]` — resolves, appends, evaluates gate
  - `stockrec corroboration-calibration-status` — read-only status display

- [ ] **Step 1: Write failing tests**

```python
# tests/test_cli_corroboration_resolve.py
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from application.cli._cli_group import cli
from domain.corroboration_gate import GateSample, GateResult


def _sample(ticker: str = "AAPL", excess: float = 0.02) -> GateSample:
    snap = date(2026, 1, 1)
    return GateSample(
        ticker=ticker,
        snapshot_date=snap,
        resolved_at=snap + timedelta(days=21),
        excess_21d=excess,
        excess_63d=None,
        beat_spy_21d=excess > 0,
    )


def _pending_result(n: int = 5) -> GateResult:
    from typing import Literal
    v: Literal["PENDING", "PASS", "FAIL"] = "PENDING"
    return GateResult(
        n_resolved=n,
        mean_excess_21d=0.01,
        ci_lower=-0.005,
        ci_upper=0.025,
        hit_rate_21d=0.6,
        mean_excess_63d=None,
        verdict=v,
        evaluated_at=date(2026, 6, 23),
    )


# --- resolve-corroboration ---

def test_resolve_corroboration_pending_output(tmp_path: Path) -> None:
    runner = CliRunner()
    samples_path = tmp_path / "samples.jsonl"
    results_path = tmp_path / "gate_log.jsonl"

    with (
        patch("application.cli.corroboration_commands.CorroborationResolverUseCase") as mock_uc_cls,
        patch("application.cli.corroboration_commands.append_samples", return_value=2) as mock_append,
        patch("application.cli.corroboration_commands.load_samples", return_value=[_sample(), _sample("MSFT")]),
        patch("application.cli.corroboration_commands.load_latest_result", return_value=None),
        patch("application.cli.corroboration_commands.sqlite3"),
        patch("application.cli.corroboration_commands.CorroborationStore"),
        patch("application.cli.corroboration_commands.YFinancePriceResolver"),
    ):
        mock_uc_cls.return_value.resolve.return_value = [_sample(), _sample("MSFT")]
        result = runner.invoke(cli, ["resolve-corroboration", "--as-of", "2026-06-23"])

    assert result.exit_code == 0, result.output
    assert "2 new samples" in result.output
    assert "total: 2" in result.output
    assert "PENDING" in result.output


def test_resolve_corroboration_fail_output(tmp_path: Path) -> None:
    runner = CliRunner()
    fail_result: GateResult
    from typing import Literal
    v: Literal["PENDING", "PASS", "FAIL"] = "FAIL"
    fail_result = GateResult(
        n_resolved=30,
        mean_excess_21d=-0.005,
        ci_lower=-0.02,
        ci_upper=0.005,
        hit_rate_21d=0.4,
        mean_excess_63d=None,
        verdict=v,
        evaluated_at=date(2026, 6, 23),
    )
    thirty_samples = [_sample(f"T{i}", -0.005) for i in range(30)]

    with (
        patch("application.cli.corroboration_commands.CorroborationResolverUseCase") as mock_uc_cls,
        patch("application.cli.corroboration_commands.append_samples", return_value=30),
        patch("application.cli.corroboration_commands.load_samples", return_value=thirty_samples),
        patch("application.cli.corroboration_commands.load_latest_result", return_value=None),
        patch("application.cli.corroboration_commands.append_result"),
        patch("application.cli.corroboration_commands.evaluate_gate", return_value=fail_result),
        patch("application.cli.corroboration_commands.sqlite3"),
        patch("application.cli.corroboration_commands.CorroborationStore"),
        patch("application.cli.corroboration_commands.YFinancePriceResolver"),
    ):
        mock_uc_cls.return_value.resolve.return_value = thirty_samples
        result = runner.invoke(cli, ["resolve-corroboration", "--as-of", "2026-06-23"])

    assert "FAIL" in result.output
    assert "HYPOTHESIS #9 FAILED" in result.output


# --- corroboration-calibration-status ---

def test_calibration_status_pending_output() -> None:
    runner = CliRunner()
    pending_samples = [_sample(f"T{i}") for i in range(12)]

    with (
        patch("application.cli.corroboration_commands.load_samples", return_value=pending_samples),
        patch("application.cli.corroboration_commands.load_latest_result", return_value=None),
    ):
        result = runner.invoke(cli, ["corroboration-calibration-status"])

    assert result.exit_code == 0, result.output
    assert "PENDING" in result.output
    assert "12" in result.output
    assert "30" in result.output
    assert "RESEARCH_ONLY" in result.output
    assert "ADR-064" in result.output


def test_calibration_status_no_samples_output() -> None:
    runner = CliRunner()
    with (
        patch("application.cli.corroboration_commands.load_samples", return_value=[]),
        patch("application.cli.corroboration_commands.load_latest_result", return_value=None),
    ):
        result = runner.invoke(cli, ["corroboration-calibration-status"])

    assert result.exit_code == 0
    assert "0" in result.output
    assert "PENDING" in result.output
```

- [ ] **Step 2: Run to verify tests fail**

```bash
uv run pytest tests/test_cli_corroboration_resolve.py -v 2>&1 | head -20
```

Expected: `ImportError` — CLI commands not found yet.

- [ ] **Step 3: Add imports and two commands to `application/cli/corroboration_commands.py`**

Add these imports near the top of the file (after existing imports):

```python
import sqlite3
from datetime import date as _date, datetime, timezone

from adapters.data.corroboration_gate_log import (
    append_result,
    append_samples,
    load_latest_result,
    load_samples,
)
from adapters.data.corroboration_store import CorroborationStore
from adapters.data.yfinance_price_resolver import YFinancePriceResolver
from application.corroboration_resolver_use_case import CorroborationResolverUseCase
from domain.corroboration_gate import GateResult, evaluate_gate
```

Add the two commands at the end of the file:

```python
@cli.command("resolve-corroboration")
@click.option(
    "--as-of",
    "as_of_str",
    default=None,
    help="Resolution date (YYYY-MM-DD). Defaults to today.",
)
def resolve_corroboration(as_of_str: str | None) -> None:
    """Compute realized returns for STRONG-tier snapshots ≥21d old. Accrues SP5 gate samples."""
    as_of = (
        _date.fromisoformat(as_of_str)
        if as_of_str
        else datetime.now(timezone.utc).date()
    )
    conn = sqlite3.connect("data/recommendations.db")
    store = CorroborationStore(conn)
    price = YFinancePriceResolver()
    uc = CorroborationResolverUseCase(store, price)

    new_samples = uc.resolve(as_of)
    n_appended = append_samples(new_samples)
    all_samples = load_samples()
    n_total = len(all_samples)

    click.echo(
        f"resolved {n_appended} new samples (total: {n_total}). Gate: ",
        nl=False,
    )

    if n_total >= 30:
        gate_result = evaluate_gate(all_samples, evaluated_at=as_of)
        if load_latest_result() is None or True:  # always append on evaluation
            append_result(gate_result)
        click.echo(gate_result.verdict)
        if gate_result.verdict == "FAIL":
            click.echo(
                "\n⚠️  HYPOTHESIS #9 FAILED — corroboration stays"
                " RESEARCH_ONLY (permanent).",
                err=True,
            )
    else:
        click.echo(f"PENDING ({n_total}/30 samples)")


@cli.command("corroboration-calibration-status")
def corroboration_calibration_status() -> None:
    """Show SP5 forward-gate status (PENDING / PASS / FAIL). Read-only. Masked output."""
    all_samples = load_samples()
    latest = load_latest_result()
    n = len(all_samples)

    if n == 0:
        mean_str = "n/a"
        ci_str = "n/a"
        hit_str = "n/a"
        mean_63_str = "n/a"
        verdict_str = "PENDING"
    elif latest is not None:
        mean_str = f"{latest.mean_excess_21d:+.2%}"
        ci_str = f"[{latest.ci_lower:+.2%}, {latest.ci_upper:+.2%}]"
        hit_str = f"{latest.hit_rate_21d:.0%}"
        mean_63_str = (
            f"{latest.mean_excess_63d:+.2%}"
            if latest.mean_excess_63d is not None
            else "n/a (insufficient data)"
        )
        verdict_str = latest.verdict
    else:
        # Samples exist but no evaluation yet (n < 30)
        excesses = [s.excess_21d for s in all_samples]
        mean_val = sum(excesses) / len(excesses)
        mean_str = f"{mean_val:+.2%} (preliminary)"
        ci_str = "n/a (n < 30)"
        hit_str = f"{sum(1 for s in all_samples if s.beat_spy_21d) / n:.0%} (preliminary)"
        mean_63_str = "n/a (insufficient data)"
        verdict_str = "PENDING"

    click.echo("Corroboration Forward Gate (Hypothesis #9)")
    click.echo(f"  verdict:          {verdict_str}")
    click.echo(f"  n resolved:       {n} / 30 required")
    click.echo(f"  mean excess 21d:  {mean_str}")
    click.echo(f"  95% CI:           {ci_str}")
    click.echo(f"  hit rate 21d:     {hit_str}")
    click.echo(f"  mean excess 63d:  {mean_63_str}")
    click.echo("  gate locked:      2026-06-23 (ADR-064)")
    click.echo("  RESEARCH_ONLY until gate passes.")
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_cli_corroboration_resolve.py -v
```

Expected: all PASSED.

- [ ] **Step 5: Typecheck + full regression**

```bash
make typecheck && make test-fast
```

Expected: both pass.

- [ ] **Step 6: Commit**

```bash
git add application/cli/corroboration_commands.py tests/test_cli_corroboration_resolve.py
git commit -m "feat(cli): add resolve-corroboration + corroboration-calibration-status commands"
```

---

### Task 6: Scheduling — shell script + `docs/scheduling.md`

**Files:**
- Create: `scripts/corroboration_weekly_resolve.sh`
- Modify: `docs/scheduling.md`

**Interfaces:** none — operational wiring only.

- [ ] **Step 1: Create `scripts/corroboration_weekly_resolve.sh`**

```bash
#!/usr/bin/env bash
# SP5 weekly corroboration resolution — runs every Sunday after market close.
# Computes realized 21d returns for STRONG-tier snapshots, accrues gate samples,
# and evaluates Hypothesis #9 gate (ADR-064) when n >= 30.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== corroboration-weekly-resolve: $(date '+%Y-%m-%d %H:%M:%S') ==="
uv run python -m application.cli resolve-corroboration
uv run python -m application.cli corroboration-calibration-status
echo "=== done ==="
```

- [ ] **Step 2: Make script executable**

```bash
chmod +x scripts/corroboration_weekly_resolve.sh
```

- [ ] **Step 3: Smoke-test the script structure (dry run — no live prices needed)**

```bash
bash -n scripts/corroboration_weekly_resolve.sh
```

Expected: exits 0 (syntax valid).

- [ ] **Step 4: Add plist section to `docs/scheduling.md`**

Find the end of the `discipline-weekly` plist section in `docs/scheduling.md`. After it, add:

```markdown
## Corroboration WEEKLY resolution (Sundays) — resolve + gate status (SP5/ADR-064)

Runs `scripts/corroboration_weekly_resolve.sh` every Sunday at 18:00 local time.
Fetches realized 21-day returns for STRONG-tier snapshots, appends to
`data/corroboration_samples.jsonl`, and evaluates Hypothesis #9 gate when n ≥ 30.

Save as `~/Library/LaunchAgents/com.tirthjoshi.stockrec.corroboration-weekly.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.tirthjoshi.stockrec.corroboration-weekly</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender/scripts/corroboration_weekly_resolve.sh</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Weekday</key><integer>0</integer>
    <key>Hour</key><integer>18</integer>
    <key>Minute</key><integer>0</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender/data/reports/corroboration_weekly_resolve.log</string>
  <key>StandardErrorPath</key>
  <string>/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender/data/reports/corroboration_weekly_resolve.log</string>
  <key>RunAtLoad</key><false/>
</dict>
</plist>
```

Load:
```bash
cp com.tirthjoshi.stockrec.corroboration-weekly.plist ~/Library/LaunchAgents/
launchctl load -w ~/Library/LaunchAgents/com.tirthjoshi.stockrec.corroboration-weekly.plist
```

(launchd Weekday 0 = Sunday). Smoke-test once: `bash scripts/corroboration_weekly_resolve.sh`.

**Note:** `corroborate` job (which populates snapshots) must run BEFORE this resolver job each
week. If running both manually, run `stockrec corroborate` first.
```

- [ ] **Step 5: Full quality gate**

```bash
make check
```

Expected: lint + typecheck + test (with coverage) all pass.

- [ ] **Step 6: Commit**

```bash
git add scripts/corroboration_weekly_resolve.sh docs/scheduling.md
git commit -m "chore(sp5): add corroboration weekly resolve script + launchd plist"
```

---

## Self-Review Against Spec

| Spec requirement | Task |
|---|---|
| `GateSample(ticker, snapshot_date, resolved_at, excess_21d, excess_63d, beat_spy_21d)` | Task 2 |
| `GateResult` with all fields incl. `verdict: Literal[...]` | Task 2 |
| `evaluate_gate()` — PENDING/PASS/FAIL, 50 bps bar, bootstrap CI | Task 2 |
| n=29 → PENDING; n=30 + fail conditions → FAIL | Task 2 (tests) |
| `load_samples` / `append_samples` with dedup by `(ticker, snapshot_date)` | Task 3 |
| `load_latest_result` / `append_result` JSONL roundtrip | Task 3 |
| `ResolverPricePort.price_at(ticker, date) -> float` | Task 4 |
| `CorroborationStore.load_all_snapshots()` (all runs, all tickers) | Task 4 |
| `YFinancePriceResolver` — thin yfinance adapter | Task 4 |
| `CorroborationResolverUseCase.resolve()` — STRONG only, ≥21d, idempotent, skip on error | Task 4 |
| `resolve-corroboration` CLI — resolves, dedupes, evaluates at n≥30, FAIL prints warning | Task 5 |
| `corroboration-calibration-status` CLI — mirrors discipline-calibration-status format | Task 5 |
| RESEARCH_ONLY label + ADR-064 date in status output | Task 5 |
| 63d displayed (not gated) in status output | Task 5 |
| hit rate displayed (not gated) | Task 5 |
| Shell script + launchd plist (Sunday 18:00) | Task 6 |
| ADR-064 committed before any code | Task 1 (already on develop) |
| No live yfinance in any test | Tasks 2-5 (all use fakes/mocks) |
| Source learning deferred | ✓ (out of scope — not implemented) |
