# Hardening Sprint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `make check` green and make the zero-touch Saturday job fail loud (never silently emit garbage) via resilient fetch, a tri-state fetch contract, delisted-ticker pruning, and a collect-then-fail health check.

**Architecture:** Four loosely-coupled units sharing one concept — a tri-state fetch result (`data | no-data | error`). Retry/backoff + a typed `PriceFetchError` live at the fetch boundary; `load_price_series` gains an opt-in `strict` param so the weekly job fails loud while the ~18 existing callers keep `[]`-on-error. Delisted prune + health-tracking are pure helpers wired into the holdings-risk fetch loop.

**Tech Stack:** Python 3.12+ (active venv 3.13), stdlib only for new code, pytest + Hypothesis, mypy strict. No new dependencies.

**Branch:** `feat/hardening-sprint` (stacked on `feat/unit-c-adherence`; spec committed `5f9070f`). After PR #37 merges, rebase onto develop.

**Spec:** `docs/superpowers/specs/2026-06-10-hardening-sprint-design.md`. Constants: retry attempts 3, base_delay 1.0s, delisted threshold 3 consecutive no-data weeks.

**Existing alignment (reuse, don't reinvent):** `domain/exceptions.py` already has `DomainError`, `SourceThrottledError` (documented as "distinct from returning [] — genuinely no data"). `PriceFetchError` joins this family. `application/price_returns.py::load_price_series` does its OWN inline `yf.Ticker(ticker).history` (NOT via YFinanceAdapter) and is the weekly-job fetch path — that is where retry + strict go.

---

### Task 1: Venv reconcile (ops — green baseline)

**Files:** none (environment + verification only).

- [ ] **Step 1: Confirm the missing deps**

Run: `python -c "import feedparser, networkx, plotly, streamlit, praw" 2>&1`
Expected: `ModuleNotFoundError` on the first missing module.

- [ ] **Step 2: Install the project into the shared venv from pyproject**

Run: `pip install -e .`
Expected: resolves and installs feedparser, networkx, plotly, streamlit, praw (and any other declared deps). No version-conflict errors.

- [ ] **Step 3: Verify every declared dep imports**

Run: `python -c "import feedparser, networkx, plotly, streamlit, praw, yfinance; print('all imports OK')"`
Expected: `all imports OK`

- [ ] **Step 4: Run the full suite — collection errors must go to zero**

Run: `python -m pytest tests/ -q 2>&1 | tail -15`
Expected: 0 collection errors; the previously-failing ~55 import tests now pass. If any test fails for a NON-import reason (real bug surfaced by newly-importable code), STOP and report it — do not fix unrelated failures in this task; note them for separate triage.

- [ ] **Step 5: Confirm `make check` runs end-to-end**

Run: `make check 2>&1 | tail -20`
Expected: lint + typecheck + tests all execute (green, or only genuine non-import failures surfaced and reported). Record the result.

- [ ] **Step 6: Commit (lockstep note only — no code change)**

No file changes in this task. If `pip install -e .` created/modified an `*.egg-info` or similar, confirm it is gitignored (it should be). Nothing to commit. Proceed to Task 2.

---

### Task 2: `PriceFetchError` typed exception

**Files:**
- Modify: `domain/exceptions.py`
- Test: `tests/domain/test_price_fetch_error.py`

- [ ] **Step 1: Write the failing test**

```python
"""tests/domain/test_price_fetch_error.py"""
import pytest

from domain.exceptions import DomainError, PriceFetchError


def test_price_fetch_error_is_domain_error() -> None:
    assert issubclass(PriceFetchError, DomainError)


def test_price_fetch_error_carries_ticker_and_cause() -> None:
    cause = ValueError("network down")
    err = PriceFetchError("AC.TO", cause=cause)
    assert err.ticker == "AC.TO"
    assert err.cause is cause
    assert "AC.TO" in str(err)


def test_price_fetch_error_raisable() -> None:
    with pytest.raises(PriceFetchError):
        raise PriceFetchError("XYZ", cause=RuntimeError("boom"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/domain/test_price_fetch_error.py -v`
Expected: FAIL — `ImportError: cannot import name 'PriceFetchError'`

- [ ] **Step 3: Add the exception to `domain/exceptions.py`** (append after `SourceThrottledError`)

```python
class PriceFetchError(DomainError):
    """Raised when a price fetch fails after retries (a real error, NOT
    genuinely-empty data). Empty data returns []; this is the tri-state's
    'error' arm. Pairs with SourceThrottledError (rate-limit, also not []).

    Attributes:
        ticker: the symbol whose fetch failed.
        cause: the underlying exception that caused the failure.
    """

    def __init__(self, ticker: str, *, cause: Exception | None = None) -> None:
        super().__init__(f"price fetch failed for {ticker}: {cause}")
        self.ticker = ticker
        self.cause = cause
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/domain/test_price_fetch_error.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add domain/exceptions.py tests/domain/test_price_fetch_error.py
git commit -m "feat: PriceFetchError typed exception (tri-state fetch error arm)"
```

---

### Task 3: `retry_with_backoff` helper (stdlib, injectable sleep)

**Files:**
- Create: `adapters/data/retry.py`
- Test: `tests/adapters/data/test_retry.py`

- [ ] **Step 1: Write the failing tests**

```python
"""tests/adapters/data/test_retry.py"""
import pytest

from adapters.data.retry import retry_with_backoff


def test_returns_immediately_on_success() -> None:
    calls = []
    delays: list[float] = []
    result = retry_with_backoff(
        lambda: calls.append(1) or "ok", sleep=delays.append
    )
    assert result == "ok"
    assert len(calls) == 1
    assert delays == []  # no retry, no sleep


def test_retries_then_succeeds() -> None:
    attempts = {"n": 0}
    delays: list[float] = []

    def flaky() -> str:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise ValueError("transient")
        return "ok"

    result = retry_with_backoff(
        flaky, attempts=3, base_delay=1.0, sleep=delays.append
    )
    assert result == "ok"
    assert attempts["n"] == 3
    assert delays == [1.0, 2.0]  # exponential backoff between the 3 tries


def test_raises_last_exception_after_attempts_exhausted() -> None:
    delays: list[float] = []

    def always_fail() -> str:
        raise RuntimeError("down")

    with pytest.raises(RuntimeError, match="down"):
        retry_with_backoff(
            always_fail, attempts=3, base_delay=1.0, sleep=delays.append
        )
    assert delays == [1.0, 2.0]  # slept between tries, not after the last


def test_only_retries_listed_exceptions() -> None:
    def raises_key_error() -> str:
        raise KeyError("not retryable here")

    with pytest.raises(KeyError):
        retry_with_backoff(
            raises_key_error, attempts=3, retryable=(ValueError,), sleep=lambda d: None
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/adapters/data/test_retry.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'adapters.data.retry'`

- [ ] **Step 3: Write `adapters/data/retry.py`**

```python
"""Stdlib retry-with-exponential-backoff. Injectable sleep so tests run with a
fake clock (no real waiting). No external dependency (project ethos: no tenacity)."""

from __future__ import annotations

import time
from typing import Callable, TypeVar

T = TypeVar("T")


def retry_with_backoff(
    fn: Callable[[], T],
    *,
    attempts: int = 3,
    base_delay: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
    retryable: tuple[type[BaseException], ...] = (Exception,),
) -> T:
    """Call fn(); on a retryable exception, wait base_delay * 2**i and retry.
    Re-raises the last exception after `attempts` tries. Sleeps BETWEEN tries
    only (never after the final failure). A non-retryable exception propagates
    immediately."""
    last_exc: BaseException | None = None
    for i in range(attempts):
        try:
            return fn()
        except retryable as exc:
            last_exc = exc
            if i < attempts - 1:
                sleep(base_delay * 2**i)
    assert last_exc is not None  # unreachable: attempts >= 1 and we caught
    raise last_exc
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/adapters/data/test_retry.py -v`
Expected: ALL PASS. (If `tests/adapters/data/__init__.py` is missing and import fails, create empty `tests/adapters/__init__.py` and `tests/adapters/data/__init__.py` to match the package test layout — check whether sibling test dirs use `__init__.py` first.)

- [ ] **Step 5: Commit**

```bash
git add adapters/data/retry.py tests/adapters/data/test_retry.py
git commit -m "feat: stdlib retry_with_backoff helper (injectable sleep)"
```

---

### Task 4: `load_price_series` — retry + tri-state `strict` param

**Files:**
- Modify: `application/price_returns.py`
- Test: `tests/application/test_price_returns_strict.py`

- [ ] **Step 1: Write the failing tests**

```python
"""tests/application/test_price_returns_strict.py"""
from datetime import datetime

import pytest

import application.price_returns as pr
from domain.exceptions import PriceFetchError


def _fake_history_factory(behavior):
    """behavior: 'empty' | 'data' | 'always_raise' | a mutable counter dict."""
    ...


def test_empty_df_returns_empty_both_modes(monkeypatch) -> None:
    # A fetch that yields no rows is NO-DATA, never an error.
    monkeypatch.setattr(pr, "_fetch_history", lambda t, s, e: [])
    start, end = datetime(2024, 1, 1), datetime(2024, 2, 1)
    assert pr.load_price_series("NEW.TO", start, end) == []
    assert pr.load_price_series("NEW.TO", start, end, strict=True) == []


def test_error_non_strict_returns_empty(monkeypatch) -> None:
    def boom(t, s, e):
        raise ConnectionError("network")

    monkeypatch.setattr(pr, "_fetch_history", boom)
    monkeypatch.setattr(pr, "_SLEEP", lambda d: None)  # no real backoff wait
    start, end = datetime(2024, 1, 1), datetime(2024, 2, 1)
    assert pr.load_price_series("AC.TO", start, end) == []  # legacy contract


def test_error_strict_raises_price_fetch_error(monkeypatch) -> None:
    def boom(t, s, e):
        raise ConnectionError("network")

    monkeypatch.setattr(pr, "_fetch_history", boom)
    monkeypatch.setattr(pr, "_SLEEP", lambda d: None)
    start, end = datetime(2024, 1, 1), datetime(2024, 2, 1)
    with pytest.raises(PriceFetchError) as ei:
        pr.load_price_series("AC.TO", start, end, strict=True)
    assert ei.value.ticker == "AC.TO"


def test_transient_then_success_retries(monkeypatch) -> None:
    calls = {"n": 0}

    def flaky(t, s, e):
        calls["n"] += 1
        if calls["n"] < 2:
            raise ConnectionError("transient")
        return [(datetime(2024, 1, 2), 10.0)]

    monkeypatch.setattr(pr, "_fetch_history", flaky)
    monkeypatch.setattr(pr, "_SLEEP", lambda d: None)
    start, end = datetime(2024, 1, 1), datetime(2024, 2, 1)
    out = pr.load_price_series("AC.TO", start, end, strict=True)
    assert out == [(datetime(2024, 1, 2), 10.0)]
    assert calls["n"] == 2  # retried once
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/application/test_price_returns_strict.py -v`
Expected: FAIL — `_fetch_history` / `_SLEEP` attributes don't exist yet.

- [ ] **Step 3: Refactor `application/price_returns.py`**

Replace the existing `load_price_series` (which inlines `import yfinance`) with a seam-friendly version: extract the raw fetch into `_fetch_history` (the retry/test seam) and route through `retry_with_backoff`. Keep `compute_forward_return` untouched.

```python
import time as _time

from adapters.data.retry import retry_with_backoff
from domain.exceptions import PriceFetchError

_SLEEP = _time.sleep  # module-level seam so tests can stub backoff waits


def _fetch_history(
    ticker: str, start: datetime, end: datetime
) -> list[tuple[datetime, float]]:
    """Raw yfinance fetch. Returns ascending (date, close); [] if the symbol
    has no rows in range. Raises on a genuine fetch error (network, etc.)."""
    import yfinance as yf

    df = yf.Ticker(ticker).history(
        start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d")
    )
    if df is None or df.empty:
        return []
    out: list[tuple[datetime, float]] = []
    for idx, row in df.iterrows():
        out.append((idx.to_pydatetime().replace(tzinfo=None), float(row["Close"])))
    return out


def load_price_series(
    ticker: str,
    start: datetime,
    end: datetime,
    *,
    strict: bool = False,
) -> list[tuple[datetime, float]]:
    """Load (date, close) ascending from yfinance, with retry/backoff.

    Tri-state:
      - rows in range            -> the series
      - no rows (new/delisted)   -> []  (NOT an error, both modes)
      - fetch error after retries-> strict=False: log + []  (legacy contract,
                                     ~18 callers); strict=True: raise
                                     PriceFetchError(ticker).
    """
    try:
        return retry_with_backoff(
            lambda: _fetch_history(ticker, start, end), sleep=_SLEEP
        )
    except Exception as exc:
        if strict:
            raise PriceFetchError(ticker, cause=exc) from exc
        from loguru import logger

        logger.warning(f"price load failed for {ticker}: {exc}")
        return []
```

- [ ] **Step 4: Run the new tests + the existing price_returns tests**

Run: `pytest tests/application/test_price_returns_strict.py tests/ -k "price_return" -v`
Expected: new tests PASS; any pre-existing price_returns tests still PASS (the default `strict=False` preserves the `[]`-on-error contract).

- [ ] **Step 5: Confirm no caller breakage**

Run: `pytest tests/ -q 2>&1 | tail -5`
Expected: no NEW failures vs the Task 1 baseline (the 18 callers use the default mode).

- [ ] **Step 6: Commit**

```bash
git add application/price_returns.py tests/application/test_price_returns_strict.py
git commit -m "feat: load_price_series retry/backoff + tri-state strict param"
```

---

### Task 5: Delisted prune (pure counter + JSON persistence)

**Files:**
- Create: `application/delisted.py`
- Test: `tests/application/test_delisted.py`

- [ ] **Step 1: Write the failing tests**

```python
"""tests/application/test_delisted.py"""
import json

from hypothesis import given
from hypothesis import strategies as st

from application.delisted import (
    is_delisted,
    load_prune_list,
    record_fetch_outcome,
    save_prune_list,
)


def test_no_data_increments_counter() -> None:
    state = record_fetch_outcome({}, "DEAD.TO", had_data=False)
    assert state["DEAD.TO"] == 1
    state = record_fetch_outcome(state, "DEAD.TO", had_data=False)
    assert state["DEAD.TO"] == 2


def test_data_resets_counter() -> None:
    state = {"FLAKY.TO": 2}
    state = record_fetch_outcome(state, "FLAKY.TO", had_data=True)
    assert state["FLAKY.TO"] == 0


def test_is_delisted_at_threshold() -> None:
    assert not is_delisted({"X.TO": 2}, "X.TO", threshold=3)
    assert is_delisted({"X.TO": 3}, "X.TO", threshold=3)
    assert not is_delisted({}, "UNKNOWN.TO", threshold=3)


def test_round_trip_persistence(tmp_path) -> None:
    path = str(tmp_path / "delisted.json")
    save_prune_list(path, {"A.TO": 3, "B.TO": 1})
    assert load_prune_list(path) == {"A.TO": 3, "B.TO": 1}


def test_load_missing_file_is_empty(tmp_path) -> None:
    assert load_prune_list(str(tmp_path / "nope.json")) == {}


@given(st.integers(min_value=0, max_value=10))
def test_property_data_always_resets(prior: int) -> None:
    state = record_fetch_outcome({"T.TO": prior}, "T.TO", had_data=True)
    assert state["T.TO"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/application/test_delisted.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'application.delisted'`

- [ ] **Step 3: Write `application/delisted.py`**

```python
"""Delisted-ticker prune list. A name returning no data for `threshold`
consecutive weekly runs is treated as delisted: logged loudly, skipped from
assessment, and persisted to a gitignored JSON so it is not re-fetched (yfinance
is throttled). Reversible: delete the ticker's key (or the file) to retry.

PRIVACY: the file lives under data/personal/ and is never committed."""

from __future__ import annotations

import json
import os
from typing import Any


def record_fetch_outcome(
    state: dict[str, int], ticker: str, had_data: bool
) -> dict[str, int]:
    """Return a new state with ticker's consecutive-no-data counter updated:
    incremented on no-data, reset to 0 on data. Pure (copies input)."""
    out = dict(state)
    out[ticker] = 0 if had_data else out.get(ticker, 0) + 1
    return out


def is_delisted(state: dict[str, int], ticker: str, threshold: int = 3) -> bool:
    """True once a ticker has `threshold` consecutive no-data weeks. The
    threshold guards against a one-off yfinance hiccup pruning a live name."""
    return state.get(ticker, 0) >= threshold


def load_prune_list(path: str) -> dict[str, int]:
    if not os.path.exists(path):
        return {}
    with open(path) as fh:
        data: dict[str, Any] = json.load(fh)
    return {str(k): int(v) for k, v in data.items()}


def save_prune_list(path: str, state: dict[str, int]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as fh:
        json.dump(state, fh, indent=2, sort_keys=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/application/test_delisted.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add application/delisted.py tests/application/test_delisted.py
git commit -m "feat: delisted-ticker prune list (consecutive-no-data counter)"
```

---

### Task 6: Fetch-health tracker (pure counters + summary)

**Files:**
- Create: `application/fetch_health.py`
- Test: `tests/application/test_fetch_health.py`

- [ ] **Step 1: Write the failing tests**

```python
"""tests/application/test_fetch_health.py"""
from application.fetch_health import FetchHealth


def test_counts_and_summary() -> None:
    h = FetchHealth()
    h.record_ok("AC.TO")
    h.record_ok("BMO.TO")
    h.record_no_data("NEW.TO")
    h.record_failed("BROKE.TO")
    h.record_pruned("DEAD.TO")
    assert h.summary_line() == (
        "fetched OK=2 no-data=1 FAILED=1 pruned=1"
    )
    assert h.any_failed() is True
    assert h.failed_tickers == ["BROKE.TO"]


def test_clean_run_not_failed() -> None:
    h = FetchHealth()
    h.record_ok("AC.TO")
    h.record_no_data("NEW.TO")
    h.record_pruned("DEAD.TO")
    assert h.any_failed() is False
    assert h.summary_line() == "fetched OK=1 no-data=1 FAILED=0 pruned=1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/application/test_fetch_health.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'application.fetch_health'`

- [ ] **Step 3: Write `application/fetch_health.py`**

```python
"""Per-run fetch health tally for the weekly job. Pure counters; the CLI reads
any_failed() to decide a loud non-zero exit. Collect-then-fail: the fetch loop
records every ticker's outcome and finishes ALL assessable names before the job
exits non-zero — one flaky fetch never aborts a 66-name run mid-loop."""

from __future__ import annotations


class FetchHealth:
    def __init__(self) -> None:
        self.ok = 0
        self.no_data = 0
        self.pruned = 0
        self.failed_tickers: list[str] = []

    def record_ok(self, ticker: str) -> None:
        self.ok += 1

    def record_no_data(self, ticker: str) -> None:
        self.no_data += 1

    def record_failed(self, ticker: str) -> None:
        self.failed_tickers.append(ticker)

    def record_pruned(self, ticker: str) -> None:
        self.pruned += 1

    def any_failed(self) -> bool:
        return len(self.failed_tickers) > 0

    def summary_line(self) -> str:
        return (
            f"fetched OK={self.ok} no-data={self.no_data} "
            f"FAILED={len(self.failed_tickers)} pruned={self.pruned}"
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/application/test_fetch_health.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add application/fetch_health.py tests/application/test_fetch_health.py
git commit -m "feat: FetchHealth per-run tally (collect-then-fail)"
```

---

### Task 7: Wire health + strict + prune into the holdings-risk fetch loop

**Files:**
- Modify: `application/cli.py` (the `holdings_risk` command, provider closure ~lines 2084-2089, and the end-of-command exit)
- Test: `tests/application/test_cli_holdings_health.py`

- [ ] **Step 1: Write the failing test**

```python
"""tests/application/test_cli_holdings_health.py"""
from datetime import datetime, timedelta

from click.testing import CliRunner

from application import cli as cli_mod


def _series(px: float) -> list[tuple[datetime, float]]:
    start = datetime(2024, 1, 1)
    return [(start + timedelta(days=i), px) for i in range(260)]


def test_health_summary_printed_and_failure_exits_nonzero(tmp_path, monkeypatch) -> None:
    # AC.TO fetches fine; BROKE.TO raises (real error) -> FAILED=1, exit nonzero,
    # but AC.TO is still assessed (collect-then-fail).
    from domain.exceptions import PriceFetchError

    def fake_load(ticker, start, end, *, strict=False):
        if ticker == "USDCAD=X":
            return _series(1.35)
        if ticker == "BROKE.TO":
            if strict:
                raise PriceFetchError("BROKE.TO", cause=ConnectionError("x"))
            return []
        return _series(20.0)

    monkeypatch.setattr("application.price_returns.load_price_series", fake_load)

    csv_path = tmp_path / "h.csv"
    csv_path.write_text(
        "Symbol,Exchange,Quantity,Book Value (CAD),Account Type\n"
        "AC,TSX,30,556.2,FHSA\n"
        "BROKE,TSX,10,100.0,FHSA\n"
    )
    res = CliRunner().invoke(
        cli_mod.cli,
        [
            "holdings-risk",
            "--holdings", str(csv_path),
            "--out", str(tmp_path / "o.txt"),
            "--log", str(tmp_path / "l.jsonl"),
            "--prune-list", str(tmp_path / "delisted.json"),
        ],
    )
    assert "fetched OK=" in res.output
    assert "FAILED=1" in res.output
    assert "BROKE.TO" in res.output
    assert res.exit_code != 0  # loud failure
    # AC.TO still assessed despite BROKE.TO failing
    assert "Assessed" in res.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/application/test_cli_holdings_health.py -v`
Expected: FAIL — no `--prune-list` option / no health summary / exit code 0.

- [ ] **Step 3: Modify the `holdings_risk` command in `application/cli.py`**

(a) Add a CLI option (next to the existing `--log` option):

```python
@click.option(
    "--prune-list",
    default="data/personal/delisted.json",
    show_default=True,
    help="Gitignored consecutive-no-data counter; >=3 weeks => skip as delisted",
)
```
and add `prune_list: str` to the function signature.

(b) Replace the provider closure (currently lines ~2084-2089) with a health-aware, prune-aware, strict-fetch version. Imports go at the top of the function body with the others:

```python
    from application.delisted import (
        is_delisted,
        load_prune_list,
        record_fetch_outcome,
        save_prune_list,
    )
    from application.fetch_health import FetchHealth
    from domain.exceptions import PriceFetchError

    health = FetchHealth()
    prune_state = load_prune_list(prune_list)
    _cache: dict[str, list[tuple[datetime, float]]] = {}

    def provider(ticker: str) -> list[tuple[datetime, float]]:
        nonlocal prune_state
        if ticker in _cache:
            return _cache[ticker]
        if is_delisted(prune_state, ticker):
            health.record_pruned(ticker)
            _cache[ticker] = []
            return []
        try:
            series = load_price_series(ticker, start_dt, end_dt, strict=True)
        except PriceFetchError:
            health.record_failed(ticker)
            _cache[ticker] = []
            return []
        if series:
            health.record_ok(ticker)
        else:
            health.record_no_data(ticker)
        prune_state = record_fetch_outcome(prune_state, ticker, had_data=bool(series))
        _cache[ticker] = series
        return series
```

NOTE: `USDCAD=X` (the FX fetch from Unit C) flows through this same provider, so it is health-tracked too — correct (an FX failure should also surface).

(c) After the assessment completes and the existing summary `click.echo`s, add the health line + prune persistence + loud exit. Find the end of the command (after `click.echo(f"Full per-ticker detail ...")`) and append:

```python
    save_prune_list(prune_list, prune_state)
    click.echo(health.summary_line())
    if health.any_failed():
        click.echo(f"  FETCH FAILURES: {', '.join(health.failed_tickers)}")
        raise SystemExit(1)  # loud: cron under `set -euo pipefail` fails the job
```

- [ ] **Step 4: Run the new test + the Unit C holdings tests**

Run: `pytest tests/application/test_cli_holdings_health.py tests/application/test_holdings_risk_cad.py -v`
Expected: ALL PASS. The Unit C log-row test must still pass (provider change preserves the returned series shape).

- [ ] **Step 5: Full suite — no regressions**

Run: `pytest tests/ -q 2>&1 | tail -5`
Expected: green vs Task 1 baseline.

- [ ] **Step 6: Verify the prune-list path is gitignored**

Run: `git check-ignore data/personal/delisted.json && echo IGNORED-OK`
Expected: path printed + `IGNORED-OK`.

- [ ] **Step 7: Commit**

```bash
git add application/cli.py tests/application/test_cli_holdings_health.py
git commit -m "feat: holdings-risk fetch loop — strict fetch, delisted prune, collect-then-fail health exit"
```

---

### Task 8: Docs + STATUS

**Files:**
- Modify: `scripts/discipline_weekly_review.sh` (header comment only — behavior already correct via `set -euo pipefail`)
- Modify: `docs/STATUS.md`

- [ ] **Step 1: Document the fail-loud behavior in the script header**

In `scripts/discipline_weekly_review.sh`, append to the header comment block (after the step-4 line):

```bash
# Fail-loud: holdings-risk fetches with strict=True and exits non-zero if any
# ticker hard-fails (after retries). Under `set -euo pipefail` that aborts the
# Saturday job loudly. Delisted names (>=3 wks no data) are pruned + skipped,
# not failed. Health summary line precedes each step's output.
```

- [ ] **Step 2: Smoke-test script syntax**

Run: `bash -n scripts/discipline_weekly_review.sh`
Expected: no output (OK). Do NOT run the full script (hits yfinance).

- [ ] **Step 3: Overwrite `docs/STATUS.md`** (~40 lines: hardening shipped; next = dashboard plan; preserve caveats + the known unrealized_pct bug + pointers)

- [ ] **Step 4: Commit**

```bash
git add scripts/discipline_weekly_review.sh docs/STATUS.md
git commit -m "docs: hardening sprint fail-loud behavior + STATUS"
```

---

## Plan self-review (done at write time)

- **Spec coverage:** Unit 1 venv → Task 1; PriceFetchError → Task 2; retry/backoff → Task 3; tri-state strict load_price_series → Task 4; delisted prune → Task 5; health tracker → Task 6; collect-then-fail wiring + loud exit → Task 7; cron doc + STATUS → Task 8. All four spec units covered.
- **Placeholder scan:** the test helper `_fake_history_factory` in Task 4 Step 1 is declared with `...` but is UNUSED by the actual tests (they use `monkeypatch.setattr` on `_fetch_history`/`_SLEEP` directly) — the implementer should DELETE that stub; it is illustrative scaffolding, not required. No other placeholders. (Flagged rather than silently removed so the implementer knows it's intentional dead scaffolding.)
- **Type consistency:** `load_price_series(..., *, strict=False)` signature identical in Task 4 def and Task 7 call. `_fetch_history`/`_SLEEP` seam names match between Task 4 impl and its tests. `FetchHealth` method names (`record_ok/record_no_data/record_failed/record_pruned/any_failed/summary_line/failed_tickers`) identical across Task 6 and Task 7. `record_fetch_outcome/is_delisted/load_prune_list/save_prune_list` identical across Task 5 and Task 7.
- **Ordering risk:** Task 1 (venv) must run first — Tasks 3/5/6 tests import freely; the suite-wide regression checks in Tasks 4/5/7 are only meaningful against the green Task-1 baseline.
- **Known caveat:** Task 7 changes the provider for `USDCAD=X` too (Unit C FX) — intended; an FX hard-failure now also fails loud, which is correct.
