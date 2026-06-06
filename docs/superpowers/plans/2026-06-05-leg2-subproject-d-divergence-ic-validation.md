# Leg-2 Sub-Project D — Divergence IC Falsification + Forward Clock Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run a pre-registered cross-sectional IC test that can cheaply *falsify* the intensity-divergence signal on a broad survivor-biased universe; if it survives the locked gate, start the forward-tracking clock.

**Architecture:** Hexagonal, reuse-heavy. Pure signal + IC math in `domain/`/`application/`; the backtest is an application use case that injects point-in-time data and reuses the existing `precision_metrics` significance engine (`date_level_significance`, `moving_block_bootstrap`, `monotonic_precision_curve`). Wikipedia attention backfilled via the existing `DripBackfillUseCase`. No new model dims, no paid sources.

**Tech Stack:** Python 3.12, SQLite, click, pytest + Hypothesis, mypy strict, numpy (present), scipy (present, with stdlib fallback pattern already used in `precision_metrics.py`).

**Pre-registration (LOCKED, spec §4):** primary horizon = **1 month (21 trading days)**; gate = **mean IC bootstrap CI excludes 0, positive, |IC| ≥ 0.02**; universe = **broad ~605 (S&P500 + NASDAQ100)**. Secondary horizons (1w, 3m) exploratory only.

**Branch:** `feat/leg2-subproject-d-divergence-ic-validation`.

**Conventions:** domain pure (stdlib only); adapters/use cases may import libs; tests use fakes/fixtures, never live APIs; stored timestamps via `_to_naive_utc`; commit after each green task; when modifying an existing file READ it first and match real signatures.

---

## Phase 1 — The signal under test + IC math (pure)

### Task 1: `intensity_divergence_raw` — the continuous signal under test

**Files:**
- Modify: `domain/divergence_service.py` (add public fn; reuse `intensity_acceleration` + `_recent_return`)
- Test: `tests/test_divergence_service.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_intensity_divergence_raw_rising_attention_flat_price_positive():
    from datetime import datetime, timedelta, timezone
    from domain.divergence_service import intensity_divergence_raw

    now = datetime(2026, 6, 5, tzinfo=timezone.utc)
    attn = [(now - timedelta(days=d), 10.0) for d in range(8, 30)]
    attn += [(now - timedelta(days=d), 90.0) for d in range(0, 7)]   # attention surging
    price = [(now - timedelta(days=d), 100.0) for d in range(0, 40)]  # price flat
    assert intensity_divergence_raw(attn, price, now) > 0.4


def test_intensity_divergence_raw_rising_price_cancels():
    from datetime import datetime, timedelta, timezone
    from domain.divergence_service import intensity_divergence_raw

    now = datetime(2026, 6, 5, tzinfo=timezone.utc)
    attn = [(now - timedelta(days=d), 10.0) for d in range(8, 30)]
    attn += [(now - timedelta(days=d), 90.0) for d in range(0, 7)]
    # price ALSO surged 20% over the last 7d -> not a divergence
    price = [(now - timedelta(days=d), 100.0) for d in range(8, 40)]
    price += [(now - timedelta(days=d), 120.0) for d in range(0, 8)]
    rising = intensity_divergence_raw(attn, price, now)
    flat_price = [(now - timedelta(days=d), 100.0) for d in range(0, 40)]
    flat = intensity_divergence_raw(attn, flat_price, now)
    assert rising < flat


def test_intensity_divergence_raw_no_attention_is_zero():
    from datetime import datetime, timezone
    from domain.divergence_service import intensity_divergence_raw

    now = datetime(2026, 6, 5, tzinfo=timezone.utc)
    price = [(now, 100.0)]
    assert intensity_divergence_raw([], price, now) == 0.0
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_divergence_service.py -k intensity_divergence_raw -v`
Expected: FAIL with `ImportError: cannot import name 'intensity_divergence_raw'`

- [ ] **Step 3: Implement**

In `domain/divergence_service.py` (reuse existing `intensity_acceleration` and `_recent_return`; this is the *continuous, intensity-only, sentiment-free* divergence — the exact signal the pre-registration tests):
```python
def intensity_divergence_raw(
    intensity_series: list[tuple[datetime, float]],
    price_series: list[tuple[datetime, float]],
    now: datetime,
) -> float:
    """Continuous intensity-divergence signal under test (no [1,10] mapping,
    no sentiment): attention acceleration minus clamped recent up-price-move.

    Positive => attention rising faster than price (the hypothesis's 'lead').
    Returns 0.0 when there is no attention data.
    """
    if not intensity_series:
        return 0.0
    accel = intensity_acceleration(intensity_series, now)
    price_move = max(_recent_return(price_series, now), 0.0)
    return accel - price_move * 2.0
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_divergence_service.py -k intensity_divergence_raw -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add domain/divergence_service.py tests/test_divergence_service.py
git commit -m "feat: intensity_divergence_raw — continuous signal under test for IC"
```

---

### Task 2: `compute_cross_sectional_ic` — Spearman rank-IC across dates

**Files:**
- Create: `application/ic_analysis.py`
- Test: `tests/test_ic_analysis.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_ic_perfect_rank_agreement_is_one():
    from application.ic_analysis import spearman_ic

    signal = [1.0, 2.0, 3.0, 4.0, 5.0]
    fwd = [0.1, 0.2, 0.3, 0.4, 0.5]
    assert abs(spearman_ic(signal, fwd) - 1.0) < 1e-9


def test_ic_perfect_disagreement_is_minus_one():
    from application.ic_analysis import spearman_ic

    signal = [1.0, 2.0, 3.0, 4.0, 5.0]
    fwd = [0.5, 0.4, 0.3, 0.2, 0.1]
    assert abs(spearman_ic(signal, fwd) + 1.0) < 1e-9


def test_ic_too_few_points_is_nan_skipped():
    import math
    from application.ic_analysis import spearman_ic
    assert math.isnan(spearman_ic([1.0], [0.1]))


def test_aggregate_ic_summarizes_per_date_series():
    from application.ic_analysis import aggregate_ic

    # three dates, each a (signal_list, fwd_list)
    per_date = [
        ([1.0, 2.0, 3.0], [0.1, 0.2, 0.3]),   # IC = +1
        ([1.0, 2.0, 3.0], [0.3, 0.2, 0.1]),   # IC = -1
        ([1.0, 2.0, 3.0], [0.1, 0.2, 0.3]),   # IC = +1
    ]
    out = aggregate_ic(per_date, min_names=3)
    assert out["n_dates"] == 3
    assert abs(out["mean_ic"] - (1.0 - 1.0 + 1.0) / 3.0) < 1e-9
    assert out["pct_positive_dates"] == 2 / 3
    assert out["ic_series"] == [1.0, -1.0, 1.0]


def test_aggregate_ic_skips_thin_dates():
    from application.ic_analysis import aggregate_ic
    per_date = [([1.0, 2.0], [0.1, 0.2]), ([1.0, 2.0, 3.0], [0.1, 0.2, 0.3])]
    out = aggregate_ic(per_date, min_names=3)
    assert out["n_dates"] == 1   # the 2-name date is skipped
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_ic_analysis.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`application/ic_analysis.py` (Spearman = Pearson on ranks; scipy-or-fallback mirrors `precision_metrics.py`):
```python
"""Cross-sectional Information Coefficient (rank-IC) analysis.

IC = Spearman rank correlation between a signal and forward returns, computed
ACROSS names on a single date, then aggregated over dates. The standard quant
measure of monotonic predictive power; robust to a few outlier names.
"""

from __future__ import annotations

import math
from typing import Any


def _rank(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0  # average rank for ties (1-based)
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _pearson(a: list[float], b: list[float]) -> float:
    n = len(a)
    ma = sum(a) / n
    mb = sum(b) / n
    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    va = math.sqrt(sum((x - ma) ** 2 for x in a))
    vb = math.sqrt(sum((x - mb) ** 2 for x in b))
    if va == 0.0 or vb == 0.0:
        return float("nan")
    return cov / (va * vb)


def spearman_ic(signal: list[float], forward_return: list[float]) -> float:
    """Spearman rank-IC for one date. NaN if < 2 points or degenerate."""
    if len(signal) != len(forward_return) or len(signal) < 2:
        return float("nan")
    return _pearson(_rank(signal), _rank(forward_return))


def aggregate_ic(
    per_date: list[tuple[list[float], list[float]]], min_names: int = 50
) -> dict[str, Any]:
    """Aggregate per-date (signal, forward_return) pairs into IC summary.

    Skips dates with fewer than min_names valid names. Returns mean IC,
    IC IR (mean/std), % positive dates, and the per-date IC series (for the
    bootstrap / date-level significance step).
    """
    ic_series: list[float] = []
    for signal, fwd in per_date:
        if len(signal) < min_names:
            continue
        ic = spearman_ic(signal, fwd)
        if not math.isnan(ic):
            ic_series.append(ic)
    n = len(ic_series)
    if n == 0:
        return {"n_dates": 0, "mean_ic": 0.0, "ic_ir": 0.0,
                "pct_positive_dates": 0.0, "ic_series": []}
    mean_ic = sum(ic_series) / n
    if n > 1:
        var = sum((x - mean_ic) ** 2 for x in ic_series) / (n - 1)
        std = math.sqrt(var)
    else:
        std = 0.0
    return {
        "n_dates": n,
        "mean_ic": mean_ic,
        "ic_ir": (mean_ic / std) if std > 0 else 0.0,
        "pct_positive_dates": sum(1 for x in ic_series if x > 0) / n,
        "ic_series": ic_series,
    }
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_ic_analysis.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add application/ic_analysis.py tests/test_ic_analysis.py
git commit -m "feat: cross-sectional Spearman IC analysis (spearman_ic + aggregate_ic)"
```

---

## Phase 2 — Backtest use case

### Task 3: `DivergenceICBacktestUseCase` — point-in-time loop + significance

**Files:**
- Create: `application/divergence_ic_backtest.py`
- Test: `tests/test_divergence_ic_backtest.py`

- [ ] **Step 1: Write the failing tests**

```python
from datetime import datetime, timedelta, timezone


def _attn(now, ticker, recent_val, base_val=10.0):
    pts = [(now - timedelta(days=d), base_val) for d in range(8, 35)]
    pts += [(now - timedelta(days=d), recent_val) for d in range(0, 7)]
    return [(t, v) for t, v in pts]


def test_ic_backtest_detects_positive_signal():
    from application.divergence_ic_backtest import DivergenceICBacktestUseCase

    now = datetime(2026, 1, 5, tzinfo=timezone.utc)
    dates = [now + timedelta(days=7 * k) for k in range(8)]
    tickers = [f"T{i}" for i in range(60)]

    # attention provider: half the names get a surge, half flat
    def attn_fn(ticker, t):
        i = int(ticker[1:])
        return _attn(t, ticker, 90.0 if i % 2 == 0 else 10.0)

    # price flat for everyone up to t
    def price_fn(ticker, t):
        return [(t - timedelta(days=d), 100.0) for d in range(0, 40)]

    # forward return: surged names (even i) actually go up later -> signal works
    def fwd_fn(ticker, t):
        i = int(ticker[1:])
        return 0.05 if i % 2 == 0 else -0.01

    uc = DivergenceICBacktestUseCase(
        attention_fn=attn_fn, price_fn=price_fn, forward_return_fn=fwd_fn, min_names=50
    )
    report = uc.execute(dates, tickers, horizon_label="1m")
    assert report["mean_ic"] > 0.2
    assert report["n_dates"] >= 1
    assert "bootstrap" in report and "date_level" in report


def test_ic_backtest_noise_signal_near_zero():
    from application.divergence_ic_backtest import DivergenceICBacktestUseCase

    now = datetime(2026, 1, 5, tzinfo=timezone.utc)
    dates = [now + timedelta(days=7 * k) for k in range(8)]
    tickers = [f"T{i}" for i in range(60)]

    def attn_fn(ticker, t):
        i = int(ticker[1:])
        return _attn(t, ticker, 90.0 if i % 2 == 0 else 10.0)

    def price_fn(ticker, t):
        return [(t - timedelta(days=d), 100.0) for d in range(0, 40)]

    # forward return UNRELATED to the surge -> IC ~ 0
    def fwd_fn(ticker, t):
        i = int(ticker[1:])
        return 0.03 if i % 3 == 0 else -0.01

    uc = DivergenceICBacktestUseCase(
        attention_fn=attn_fn, price_fn=price_fn, forward_return_fn=fwd_fn, min_names=50
    )
    report = uc.execute(dates, tickers, horizon_label="1m")
    assert abs(report["mean_ic"]) < 0.2
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_divergence_ic_backtest.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`application/divergence_ic_backtest.py` (reuse `intensity_divergence_raw`, `aggregate_ic`, and the existing significance functions):
```python
"""Pre-registered cross-sectional IC backtest for intensity-divergence.

Point-in-time loop over (date x universe): compute the continuous
intensity-divergence signal and the forward return for each name, then the
cross-sectional rank-IC per date, then aggregate + significance. Falsification
tool only (see spec D §1): a non-positive IC on a survivor-biased sample kills
the signal; a positive IC merely earns the right to forward-track.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from application.ic_analysis import aggregate_ic
from application.precision_metrics import date_level_significance, moving_block_bootstrap
from domain.divergence_service import intensity_divergence_raw


class DivergenceICBacktestUseCase:
    def __init__(
        self,
        attention_fn: Callable[[str, datetime], list[tuple[datetime, float]]],
        price_fn: Callable[[str, datetime], list[tuple[datetime, float]]],
        forward_return_fn: Callable[[str, datetime], float],
        min_names: int = 50,
    ) -> None:
        self._attn = attention_fn
        self._price = price_fn
        self._fwd = forward_return_fn
        self._min_names = min_names

    def execute(
        self, dates: list[datetime], tickers: list[str], horizon_label: str
    ) -> dict[str, Any]:
        per_date: list[tuple[list[float], list[float]]] = []
        for t in dates:
            signals: list[float] = []
            fwds: list[float] = []
            for ticker in tickers:
                attn = self._attn(ticker, t)
                if not attn:
                    continue
                sig = intensity_divergence_raw(attn, self._price(ticker, t), t)
                fwd = self._fwd(ticker, t)
                signals.append(sig)
                fwds.append(fwd)
            per_date.append((signals, fwds))

        agg = aggregate_ic(per_date, min_names=self._min_names)
        ic_series = agg["ic_series"]
        boot = moving_block_bootstrap(ic_series) if ic_series else {}
        # date-level significance treats each date's IC as one unit vs a 0 benchmark
        date_level = (
            date_level_significance(ic_series, [0.0] * len(ic_series))
            if ic_series
            else {}
        )
        return {
            "horizon": horizon_label,
            "mean_ic": agg["mean_ic"],
            "ic_ir": agg["ic_ir"],
            "pct_positive_dates": agg["pct_positive_dates"],
            "n_dates": agg["n_dates"],
            "bootstrap": boot,
            "date_level": date_level,
        }
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_divergence_ic_backtest.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add application/divergence_ic_backtest.py tests/test_divergence_ic_backtest.py
git commit -m "feat: DivergenceICBacktestUseCase — point-in-time IC + bootstrap/date-level significance"
```

---

## Phase 3 — Data backfill + CLI

### Task 4: Wikipedia-only broad backfill option on `drip-backfill`

**Files:**
- Modify: `application/cli.py` (the `drip-backfill` command from sub-project B; add `--source` filter + reuse broad-universe loader)
- Test: `tests/test_opportunity_cli.py`

- [ ] **Step 1: Write the failing test**

```python
def test_drip_backfill_source_filter(monkeypatch):
    from click.testing import CliRunner
    from application.cli import cli
    import application.cli as climod
    from domain.models import SourceHealth

    captured = {}

    class _UC:
        def __init__(self, sources, store, sleep, throttle_s=45.0):
            captured["sources"] = list(sources.keys())
        def execute(self, tickers, now, days=90):
            return {"wikipedia": SourceHealth("wikipedia", attempts=1, ok=1)}
    monkeypatch.setattr(climod, "DripBackfillUseCase", _UC, raising=False)

    runner = CliRunner()
    result = runner.invoke(cli, ["drip-backfill", "--source", "wikipedia", "--limit", "3"])
    assert result.exit_code == 0
    assert captured["sources"] == ["wikipedia"]   # only wikipedia wired
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_opportunity_cli.py -k source_filter -v`
Expected: FAIL (no `--source` option)

- [ ] **Step 3: Implement**

In `application/cli.py` `drip-backfill` command (READ it first; it currently builds `sources = {"google_trends": ..., "wikipedia": ...}`): add
```python
@click.option("--source", "source_filter", default=None,
              help="Restrict to a single source: wikipedia | google_trends")
```
and after building the full `sources` dict, filter it:
```python
if source_filter:
    sources = {k: v for k, v in sources.items() if k == source_filter}
```
Wikipedia has no rate limit issue, so when `--source wikipedia` is used the 45s throttle is harmless but unnecessary — leave throttle as-is (the drip only sleeps after a successful save; Wikipedia returns the full range in one call, so this is fine). No other behavior change.

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_opportunity_cli.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add application/cli.py tests/test_opportunity_cli.py
git commit -m "feat: drip-backfill --source filter (wikipedia-only broad backfill)"
```

---

### Task 5: `validate-divergence-ic` CLI (pre-registered run)

**Files:**
- Modify: `application/cli.py`
- Test: `tests/test_opportunity_cli.py`

- [ ] **Step 1: Write the failing test**

```python
def test_validate_divergence_ic_runs(monkeypatch):
    from click.testing import CliRunner
    from application.cli import cli
    import application.cli as climod

    class _UC:
        def __init__(self, *a, **k): pass
        def execute(self, dates, tickers, horizon_label):
            return {"horizon": horizon_label, "mean_ic": 0.031, "ic_ir": 0.5,
                    "pct_positive_dates": 0.6, "n_dates": 40,
                    "bootstrap": {"ci_low": 0.01, "ci_high": 0.05, "p_value_ge_0": 0.01},
                    "date_level": {}}
    monkeypatch.setattr(climod, "DivergenceICBacktestUseCase", _UC, raising=False)

    runner = CliRunner()
    result = runner.invoke(cli, ["validate-divergence-ic", "--limit", "5", "--quick"])
    assert result.exit_code == 0
    assert "mean_ic" in result.output.lower() or "IC" in result.output
    assert "PROCEED" in result.output or "KILL" in result.output
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_opportunity_cli.py -k validate_divergence_ic -v`
Expected: FAIL (no such command)

- [ ] **Step 3: Implement**

In `application/cli.py` add (module-level import `DivergenceICBacktestUseCase`; reuse `_build_dependencies`, `_get_ticker_universe`, the store's `get_attention_series`, and `application.price_returns.load_price_series` + `compute_forward_return`):
```python
@cli.command("validate-divergence-ic")
@click.option("--market", default="us")
@click.option("--start", default="2016-01-01", show_default=True)
@click.option("--end", default="2025-12-31", show_default=True)
@click.option("--horizon-days", default=21, show_default=True, type=int)  # 1-month primary
@click.option("--min-names", default=50, show_default=True, type=int)
@click.option("--limit", default=0, type=int, help="Cap universe (0 = all ~605)")
@click.option("--quick", is_flag=True, help="Monthly cadence sample (faster) instead of weekly")
def validate_divergence_ic(market, start, end, horizon_days, min_names, limit, quick):
    """Pre-registered cross-sectional IC test of intensity-divergence (spec D §4)."""
    from datetime import datetime, timedelta, timezone
    import json as _json

    deps = _build_dependencies(market)
    store = deps["store"]
    tickers = _get_ticker_universe(deps["config"])
    if limit:
        tickers = tickers[:limit]

    start_dt = datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
    end_dt = datetime.fromisoformat(end).replace(tzinfo=timezone.utc)
    step = 28 if quick else 7
    dates, d = [], start_dt
    while d <= end_dt - timedelta(days=horizon_days):
        dates.append(d)
        d += timedelta(days=step)

    def attention_fn(ticker, t):
        pts = store.get_attention_series(ticker, t - timedelta(days=40), t)
        return [(p.timestamp, p.value) for p in pts]

    _price_cache: dict[str, list] = {}
    def _prices(ticker):
        if ticker not in _price_cache:
            from application.price_returns import load_price_series
            _price_cache[ticker] = load_price_series(ticker, start_dt - timedelta(days=60), end_dt + timedelta(days=horizon_days + 5))
        return _price_cache[ticker]

    def price_fn(ticker, t):
        return [(ts, px) for ts, px in _prices(ticker) if ts <= t and ts >= t - timedelta(days=40)]

    def forward_return_fn(ticker, t):
        from application.price_returns import compute_forward_return
        return compute_forward_return(_prices(ticker), t, horizon_days)

    uc = DivergenceICBacktestUseCase(attention_fn, price_fn, forward_return_fn, min_names=min_names)
    report = uc.execute(dates, tickers, horizon_label=f"{horizon_days}d")

    # LOCKED gate (spec D §4): |mean_ic| >= 0.02, bootstrap CI excludes 0, positive
    boot = report.get("bootstrap") or {}
    ci_low = boot.get("ci_low")
    mean_ic = report["mean_ic"]
    proceed = (
        mean_ic >= 0.02 and ci_low is not None and ci_low > 0.0
    )
    verdict = "PROCEED" if proceed else "KILL"
    report["verdict"] = verdict
    out_path = f"data/reports/divergence_ic_{horizon_days}d.json"
    with open(out_path, "w") as f:
        _json.dump(report, f, indent=2, default=str)
    click.echo(f"mean_ic={mean_ic:.4f} ic_ir={report['ic_ir']:.3f} "
               f"n_dates={report['n_dates']} CI=[{boot.get('ci_low')},{boot.get('ci_high')}]")
    click.echo(f"VERDICT: {verdict}  (gate: |IC|>=0.02 & bootstrap CI excludes 0, positive)")
    click.echo(f"report -> {out_path}")
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_opportunity_cli.py -k validate_divergence_ic -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add application/cli.py tests/test_opportunity_cli.py
git commit -m "feat: validate-divergence-ic CLI (pre-registered IC gate)"
```

---

## Phase 4 — Run it (live, local) + verdict

### Task 6: Backfill Wikipedia (broad) + run the pre-registered test

**Files:** none (live run; writes `data/reports/`)

- [ ] **Step 1: Quality gate first**

Run: `make check`
Expected: green before any live step.

- [ ] **Step 2: Backfill Wikipedia attention for the broad universe (live, not CI)**

Run:
```bash
python -m application.cli drip-backfill --source wikipedia --days 3650 > data/reports/_wiki_broad_backfill.log 2>&1
```
Expected: Wikipedia is keyless + returns the full date range per article in one call, so ~605 requests, minutes of wall-clock. Source-health summary printed. Re-runnable (idempotent).

- [ ] **Step 3: Run the pre-registered primary test (1-month horizon)**

Run:
```bash
python -m application.cli validate-divergence-ic --horizon-days 21 > data/reports/_ic_1m.log 2>&1
cat data/reports/_ic_1m.log
```
Expected: prints `mean_ic`, IR, n_dates, bootstrap CI, and `VERDICT: PROCEED|KILL`. Writes `data/reports/divergence_ic_21d.json`.

- [ ] **Step 4: Run secondary horizons (exploratory only — do NOT let them change the gate)**

Run:
```bash
python -m application.cli validate-divergence-ic --horizon-days 5  > data/reports/_ic_1w.log 2>&1
python -m application.cli validate-divergence-ic --horizon-days 63 > data/reports/_ic_3m.log 2>&1
```

- [ ] **Step 5: Record the numbers (no commit of code; reports are artifacts)**

Copy the three reports to dated names:
```bash
cp data/reports/divergence_ic_21d.json data/reports/divergence_ic_1m_$(date +%Y%m%d).json
git add data/reports/divergence_ic_1m_*.json
git commit -m "chore: record pre-registered divergence IC results (primary 1m)"
```

---

### Task 7: ADR-044 — verdict + project direction

**Files:**
- Create: `docs/adr/044-divergence-ic-verdict.md`
- Modify: `CLAUDE.md` (status), `CONTEXT.md` (glossary: cross-sectional IC, falsification-vs-validation, forward clock)

- [ ] **Step 1: Write ADR-044**

Confirm 044 is next (`ls docs/adr/`). Record: the locked pre-registration (1m, |IC|≥0.02, broad 605), the observed primary mean IC + CI + n_dates, the exploratory 1w/3m numbers (labeled exploratory), and the **verdict (PROCEED or KILL)**. State plainly what it means: PROCEED → forward clock (Phase 5), real money still gated on forward record + costs; KILL → divergence falsified even on a flattering sample, pivot (research/monitoring tool or different primary signal). Include the survivorship caveat. Status: Accepted. Match ADR-041/042/043 format.

- [ ] **Step 2: Update CLAUDE.md + CONTEXT.md**

CLAUDE.md: add "Done (Leg-2 sub-project D — Divergence IC validation 2026-06-05)" with the verdict + test count. CONTEXT.md: glossary entries for cross-sectional IC, falsification-vs-validation, forward clock.

- [ ] **Step 3: Final gate**

Run: `make check`
Expected: green.

- [ ] **Step 4: Commit**

```bash
git add docs/adr/044-divergence-ic-verdict.md CLAUDE.md CONTEXT.md
git commit -m "docs: ADR-044 divergence IC verdict + status/glossary"
```

---

## Phase 5 — CONDITIONAL (run ONLY if Task 6 verdict == PROCEED)

> If the verdict is KILL, STOP here. Do not build surfacing on a falsified signal. Bring the result back to the user to decide the pivot. The tasks below are gated on PROCEED.

### Task 8 (conditional): Divergence-led surfacing

**Files:**
- Modify: `application/opportunity_scan_use_case.py`, `application/cli.py`
- Test: `tests/test_opportunity_scan.py`

- [ ] **Step 1: Write the failing test**

```python
def test_divergence_led_surfacing_ranks_by_divergence():
    from datetime import datetime, timedelta, timezone
    from application.opportunity_scan_use_case import OpportunityScanUseCase
    from domain.models import AttentionPoint
    from domain.universe import UniverseEntry
    from tests.fakes.fake_buzz_discovery import FakeBuzzDiscovery
    from tests.fakes.fake_market_data import FakeMarketData
    from tests.fakes.fake_surfaced_call_store import FakeSurfacedCallStore
    from tests.fakes.fake_universe_provider import FakeUniverseProvider
    from tests.fakes.fake_attention_series import FakeAttentionSeries

    NOW = datetime(2026, 6, 5, tzinfo=timezone.utc)
    hist = []
    for d in range(0, 30):
        hist.append(AttentionPoint("HOT", NOW - timedelta(days=d), 90.0 if d < 7 else 10.0, "wikipedia"))
        hist.append(AttentionPoint("COLD", NOW - timedelta(days=d), 10.0, "wikipedia"))
    store = FakeSurfacedCallStore()
    uc = OpportunityScanUseCase(
        universe_provider=FakeUniverseProvider([UniverseEntry("HOT", "space"), UniverseEntry("COLD", "space")]),
        conviction_provider=lambda t, now: (5.0, {"smart_money": 5.0}),
        buzz_discovery=FakeBuzzDiscovery([]),
        market_data=FakeMarketData(signals={"HOT": [], "COLD": [], "SPY": [], "QQQ": []},
                                   ticker_info={"HOT": {"market_cap": 3e9}, "COLD": {"market_cap": 3e9}}),
        store=store,
        attention_provider=FakeAttentionSeries(hist),
        cmin=0.0, dmin=6.0, min_history_days=21, surfacing_mode="divergence",
    )
    uc.execute(NOW)
    surfaced = {c["ticker"]: c["surfaced"] for c in store.candidates}
    assert surfaced["HOT"] is True
    assert surfaced["COLD"] is False
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_opportunity_scan.py -k divergence_led -v`
Expected: FAIL (no `surfacing_mode` param)

- [ ] **Step 3: Implement**

In `application/opportunity_scan_use_case.py`: add `surfacing_mode: str = "layered"` to `__init__`. When `surfacing_mode == "divergence"`, the surfaced decision uses divergence as the primary gate and ignores conviction (`surfaced = eligible and divergence >= dmin`); ranking by divergence descending. Keep `"layered"` (current `conviction>=cmin and divergence>=dmin`) as default for backward compatibility. Wire a `--surfacing-mode` option on the `scan-opportunities` CLI (default from config). Keep full-distribution logging + abstention intact.

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_opportunity_scan.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add application/opportunity_scan_use_case.py application/cli.py tests/test_opportunity_scan.py
git commit -m "feat: divergence-led surfacing mode (PROCEED path)"
```

---

### Task 9 (conditional): Start the forward clock + outcome divergence-bucket slicing

**Files:**
- Modify: `application/forward_tracking_use_case.py` (slice outcomes by divergence bucket), `docs/scheduling.md`
- Test: `tests/test_forward_tracking.py`

- [ ] **Step 1: Write the failing test**

```python
def test_track_record_by_divergence_bucket():
    from application.forward_tracking_use_case import bucket_outcomes_by_divergence

    # outcomes carry (divergence_score, beat_spy)
    rows = [
        {"divergence_score": 8.0, "beat_spy": True},
        {"divergence_score": 8.5, "beat_spy": True},
        {"divergence_score": 5.0, "beat_spy": False},
        {"divergence_score": 4.0, "beat_spy": False},
    ]
    out = bucket_outcomes_by_divergence(rows, threshold=6.0)
    assert out["high"]["n"] == 2 and out["high"]["beat_spy_rate"] == 1.0
    assert out["low"]["n"] == 2 and out["low"]["beat_spy_rate"] == 0.0
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_forward_tracking.py -k divergence_bucket -v`
Expected: FAIL (no such function)

- [ ] **Step 3: Implement**

Add `bucket_outcomes_by_divergence(rows, threshold)` to `application/forward_tracking_use_case.py` (pure helper splitting resolved outcomes into high/low divergence buckets and computing beat-SPY rate per bucket — this is the join that tells us whether higher divergence actually predicts beating SPY in the live record).

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_forward_tracking.py -v`
Expected: PASS

- [ ] **Step 5: Schedule the daily loop**

Per `docs/scheduling.md` (caffeinate-wrapped launchd), enable the daily `scan-opportunities --surfacing-mode divergence` → `resolve-calls` cycle. Document the start date in `docs/scheduling.md` (the forward clock's t0). Commit:
```bash
git add application/forward_tracking_use_case.py tests/test_forward_tracking.py docs/scheduling.md
git commit -m "feat: divergence-bucket outcome slicing + start forward clock (PROCEED path)"
```

---

## Self-Review (completed by plan author)

**Spec coverage:**
- §2 signal under test → T1 (`intensity_divergence_raw`, intensity-only, sentiment-free).
- §3 architecture: IC math → T2; backtest use case → T3; broad Wikipedia backfill → T4; CLI → T5; conditional forward clock → T8/T9.
- §4 pre-registration LOCKED → encoded in T5's gate (`|IC|≥0.02 & CI>0`), T5 default `--horizon-days 21`, broad universe via `_get_ticker_universe`; secondary horizons exploratory in T6 Step 4.
- §4 decision rule → T5 verdict + T7 ADR-044.
- §5 risks: survivorship (falsification framing, ADR), look-ahead (point-in-time `attention_fn`/`price_fn` filter ≤ t; `compute_forward_return` strictly after t), min-names thin-date guard (T2 `aggregate_ic`/T3), researcher DoF (locked gate).
- §6 acceptance → T1-T7; conditional → T8-T9.

**Placeholder scan:** new files have full code; existing-file edits cite file + block + "read first."

**Type consistency:** `intensity_divergence_raw(intensity_series, price_series, now)` (T1) used T3. `spearman_ic(signal, fwd)` + `aggregate_ic(per_date, min_names)` returning `{n_dates, mean_ic, ic_ir, pct_positive_dates, ic_series}` (T2) used T3. `DivergenceICBacktestUseCase(attention_fn, price_fn, forward_return_fn, min_names).execute(dates, tickers, horizon_label)` returning `{mean_ic, ic_ir, pct_positive_dates, n_dates, bootstrap, date_level}` (T3) used T5. Gate reads `report["mean_ic"]` + `report["bootstrap"]["ci_low"]` — consistent with `moving_block_bootstrap` keys (`ci_low/ci_high/p_value_ge_0`, confirmed in precision_metrics).

**Note:** Phase 5 is conditional on a PROCEED verdict — explicitly gated; KILL stops at Task 7 and returns to the user for the pivot decision.
