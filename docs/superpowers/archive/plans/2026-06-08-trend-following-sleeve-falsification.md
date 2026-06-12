# Trend-Following Sleeve Falsification Test — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a pre-registered backtest that tests whether an 80% SPY core + 20% cross-asset 12-month time-series-momentum trend sleeve (long/flat, inverse-vol, liquid ETFs) improves the blended portfolio's Sharpe or cuts its max drawdown ≥25% net of cost over 2008–2026 — and emit a frozen PASS/INCONCLUSIVE/KILL verdict.

**Architecture:** Pure-domain `trend_following.py` (signal/weights/turnover/blend math, stdlib only) + an application `TrendSleeveBacktestUseCase` (point-in-time monthly loop reusing the protected falsification harness — `price_returns`, `precision_metrics.sharpe_difference_bootstrap`, `evaluation.TransactionCostModel`/`DrawdownTracker`, `backtest_metrics`) + a `backtest-trend-sleeve` CLI writing a full-distribution JSON report. Backtest only; no product.

**Tech Stack:** Python 3.12, stdlib-only domain, yfinance via the existing loader, pytest + Hypothesis, mypy strict, black/isort/ruff pre-commit.

---

## Context the implementer needs

This is a **falsification test**, same machinery as the divergence-IC (ADR-044) and momentum-exit (ADR-046) tests. The gate is **LOCKED before the run** — do not retune anything to manufacture a PASS. Spec: `docs/superpowers/specs/2026-06-08-trend-following-sleeve-falsification-design.md`.

**Verbatim signatures of the reused components (use exactly these):**
- `application.price_returns.load_price_series(ticker: str, start: datetime, end: datetime) -> list[tuple[datetime, float]]` — ascending (date, adjusted-close); `[]` on error.
- `application.screen_ic_panels.monthly_closes_asof(series: list[tuple[datetime, float]], as_of: datetime) -> list[float]` — last close of each calendar month with month-end ≤ as_of, ascending; point-in-time.
- `domain.backtest_metrics.sharpe(returns: list[float], periods_per_year: int = 252, rf: float = 0.0) -> float`
- `domain.backtest_metrics.cagr(equity: list[float], periods_per_year: int = 252) -> float` — takes an EQUITY curve (starts at 1.0), not returns.
- `application.evaluation.TransactionCostModel(cost_per_trade=0.001)` with `.cost_for_turnover(turnover: float) -> float` (= `cost_per_trade * turnover`, one-way).
- `application.evaluation.DrawdownTracker().compute(returns: list[float]) -> dict[str, float | int | None]` — `["max_drawdown"]` is a **negative** float (0.0 if no decline).
- `application.precision_metrics.sharpe_difference_bootstrap(strategy_returns, buy_hold_returns, periods_per_year=252, n_resamples=2000, block_size=None, seed=12345) -> dict` — keys `point, ci_low, ci_high, p_value_le_0, n` (`ci_*` None if n<2).

**Frozen params (spec §4):** universe `["SPY","EFA","EEM","TLT","IEF","GLD","DBC"]`; momentum lookback 12 months; vol window 60 trading days; blend `core_weight=0.80`; cost 10 bps (`TransactionCostModel(cost_per_trade=0.001)` → `cost_for_turnover` with 10bps means `cost_per_trade=0.001`); window 2008-01→2026-01 monthly; cash earns 0%.

**Look-ahead rule (non-negotiable):** at month-end `t`, signals/vols use only daily closes with date ≤ `t`; the realized return uses `t → t+1`. Never pass post-`t` data into a signal.

---

## File Structure

- **Create** `domain/trend_following.py` — pure: `time_series_momentum`, `inverse_vol_weights`, `turnover`, `blend_returns`, `equity_curve`.
- **Create** `application/trend_sleeve_backtest.py` — `SleeveVerdict` (frozen) + `TrendSleeveBacktestUseCase`.
- **Modify** `application/cli.py` — `backtest-trend-sleeve` command.
- **Create** tests: `tests/test_trend_following.py`, `tests/test_trend_sleeve_backtest.py`, `tests/test_cli_trend_sleeve.py`.

---

## Task 1: Momentum signal + equity curve (`domain/trend_following.py`)

**Files:**
- Create: `domain/trend_following.py`
- Test: `tests/test_trend_following.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_trend_following.py
from domain.trend_following import time_series_momentum, equity_curve


def test_momentum_positive_for_uptrend() -> None:
    closes = [float(100 + 5 * i) for i in range(13)]  # 13 monthly closes, rising
    assert time_series_momentum(closes) > 0


def test_momentum_negative_for_downtrend() -> None:
    closes = [float(200 - 5 * i) for i in range(13)]
    assert time_series_momentum(closes) < 0


def test_momentum_is_12m_total_return() -> None:
    closes = [10.0] * 12 + [11.0]  # 13 values; 12 months ago = 10, now = 11
    assert abs(time_series_momentum(closes) - 0.10) < 1e-9


def test_momentum_none_when_too_short() -> None:
    assert time_series_momentum([1.0] * 12) is None  # need >= 13


def test_momentum_none_when_base_nonpositive() -> None:
    closes = [0.0] + [1.0] * 12
    assert time_series_momentum(closes) is None


def test_equity_curve_compounds() -> None:
    assert equity_curve([0.1, -0.1]) == [1.0, 1.1, 1.1 * 0.9]
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_trend_following.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'domain.trend_following'`.

- [ ] **Step 3: Implement**

```python
# domain/trend_following.py
"""Pure trend-following math for the sleeve falsification test (stdlib only)."""

from __future__ import annotations

from statistics import pstdev

__all__ = [
    "time_series_momentum",
    "inverse_vol_weights",
    "turnover",
    "blend_returns",
    "equity_curve",
]


def time_series_momentum(monthly_closes: list[float]) -> float | None:
    """12-month total return: most-recent close / close 12 months ago - 1.

    Needs >= 13 monthly closes (most recent last). None if too few or the
    12-months-ago close is non-positive.
    """
    if len(monthly_closes) < 13:
        return None
    base = monthly_closes[-13]
    if base <= 0:
        return None
    return monthly_closes[-1] / base - 1.0


def equity_curve(returns: list[float]) -> list[float]:
    """Compound a return series into an equity curve starting at 1.0.

    Returns a list of length len(returns)+1 (the leading 1.0 plus one point
    per period).
    """
    equity = [1.0]
    for r in returns:
        equity.append(equity[-1] * (1.0 + r))
    return equity
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_trend_following.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add domain/trend_following.py tests/test_trend_following.py
git commit -m "feat(trend): 12-month time-series momentum + equity curve"
```

---

## Task 2: Inverse-vol weights (`domain/trend_following.py`)

**Files:**
- Modify: `domain/trend_following.py`
- Test: `tests/test_trend_following.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_trend_following.py  (append; keep imports at top)
from domain.trend_following import inverse_vol_weights


def test_inverse_vol_weights_sum_to_one() -> None:
    w = inverse_vol_weights({"A": 0.1, "B": 0.2, "C": 0.4})
    assert abs(sum(w.values()) - 1.0) < 1e-9


def test_inverse_vol_down_weights_high_vol() -> None:
    w = inverse_vol_weights({"LOW": 0.1, "HIGH": 0.4})
    assert w["LOW"] > w["HIGH"]  # lower vol gets more weight


def test_inverse_vol_zero_or_missing_vol_excluded() -> None:
    w = inverse_vol_weights({"A": 0.2, "BAD": 0.0})
    assert "BAD" not in w or w["BAD"] == 0.0
    assert abs(sum(w.values()) - 1.0) < 1e-9


def test_inverse_vol_all_zero_returns_empty() -> None:
    assert inverse_vol_weights({"A": 0.0, "B": 0.0}) == {}
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_trend_following.py -k inverse_vol -v`
Expected: FAIL with `ImportError: cannot import name 'inverse_vol_weights'`.

- [ ] **Step 3: Implement (append)**

```python
# domain/trend_following.py  (append)
def inverse_vol_weights(vols: dict[str, float]) -> dict[str, float]:
    """Raw inverse-volatility weights normalized to sum to 1 across all entries
    with a positive vol. Entries with vol <= 0 are excluded (weight 0). Returns
    {} when no entry has a positive vol.
    """
    inv = {k: 1.0 / v for k, v in vols.items() if v > 0}
    total = sum(inv.values())
    if total <= 0:
        return {}
    return {k: w / total for k, w in inv.items()}
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_trend_following.py -k inverse_vol -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add domain/trend_following.py tests/test_trend_following.py
git commit -m "feat(trend): inverse-vol weights"
```

---

## Task 3: Turnover + blend (`domain/trend_following.py`)

**Files:**
- Modify: `domain/trend_following.py`
- Test: `tests/test_trend_following.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_trend_following.py  (append)
from domain.trend_following import turnover, blend_returns


def test_turnover_zero_for_unchanged_book() -> None:
    w = {"A": 0.5, "B": 0.5}
    assert turnover(w, w) == 0.0


def test_turnover_one_way_half_sum_abs_delta() -> None:
    prev = {"A": 1.0}
    new = {"B": 1.0}  # fully rotate A->B: |0-1|+|1-0| = 2, one-way = 1.0
    assert turnover(prev, new) == 1.0


def test_turnover_handles_cash_shrink() -> None:
    prev = {"A": 1.0}
    new = {"A": 0.5}  # half to cash: |0.5-1.0| = 0.5, one-way = 0.25
    assert turnover(prev, new) == 0.25


def test_blend_is_convex_combination() -> None:
    core = [0.10, -0.20]
    sleeve = [0.00, 0.10]
    out = blend_returns(core, sleeve, core_weight=0.8)
    assert abs(out[0] - (0.8 * 0.10 + 0.2 * 0.00)) < 1e-12
    assert abs(out[1] - (0.8 * -0.20 + 0.2 * 0.10)) < 1e-12
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_trend_following.py -k "turnover or blend" -v`
Expected: FAIL with `ImportError: cannot import name 'turnover'`.

- [ ] **Step 3: Implement (append)**

```python
# domain/trend_following.py  (append)
def turnover(prev_w: dict[str, float], new_w: dict[str, float]) -> float:
    """One-way turnover = 0.5 * sum over the union of keys of |new - prev|.

    A weight absent from a dict is treated as 0. Range [0, 1] when both books
    are fully allocated (cash counts as the absent remainder, so a shift into
    cash is captured by the shrinking asset weights).
    """
    keys = set(prev_w) | set(new_w)
    return 0.5 * sum(abs(new_w.get(k, 0.0) - prev_w.get(k, 0.0)) for k in keys)


def blend_returns(
    core: list[float], sleeve: list[float], core_weight: float
) -> list[float]:
    """Element-wise convex combination: core_weight*core + (1-core_weight)*sleeve.

    `core` and `sleeve` must be the same length.
    """
    sw = 1.0 - core_weight
    return [core_weight * c + sw * s for c, s in zip(core, sleeve)]
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_trend_following.py -v`
Expected: PASS (all trend_following tests).

- [ ] **Step 5: Commit**

```bash
git add domain/trend_following.py tests/test_trend_following.py
git commit -m "feat(trend): one-way turnover + portfolio blend"
```

---

## Task 4: `SleeveVerdict` + backtest construction (`application/trend_sleeve_backtest.py`)

**Files:**
- Create: `application/trend_sleeve_backtest.py`
- Test: `tests/test_trend_sleeve_backtest.py`

This task builds the point-in-time construction loop and the per-arm return series, injecting a `price_series_fn` so tests use synthetic data (no network). The gate logic comes in Task 5.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_trend_sleeve_backtest.py
from datetime import datetime, timedelta

from application.trend_sleeve_backtest import TrendSleeveBacktestUseCase


def _daily(start_price: float, slope: float, days: int) -> list[tuple[datetime, float]]:
    base = datetime(2006, 1, 2)
    return [(base + timedelta(days=i), start_price + slope * i) for i in range(days)]


def test_construction_builds_three_aligned_series() -> None:
    # 7-ETF universe; give SPY a steady uptrend, everything else flat-ish.
    days = 900  # ~3y of daily points
    series = {
        "SPY": _daily(100.0, 0.05, days),
        "EFA": _daily(50.0, 0.0, days),
        "EEM": _daily(50.0, 0.0, days),
        "TLT": _daily(100.0, 0.0, days),
        "IEF": _daily(100.0, 0.0, days),
        "GLD": _daily(100.0, 0.0, days),
        "DBC": _daily(20.0, 0.0, days),
    }
    uc = TrendSleeveBacktestUseCase(price_series_fn=lambda t: series[t])
    dates = [datetime(2007, m, 28) for m in range(1, 13)] + [datetime(2008, 1, 28)]
    spy, sleeve, blended = uc.build_series(dates)
    assert len(spy) == len(sleeve) == len(blended)
    assert len(spy) >= 1
    # Blended must equal 0.8*spy + 0.2*sleeve elementwise.
    for i in range(len(spy)):
        assert abs(blended[i] - (0.8 * spy[i] + 0.2 * sleeve[i])) < 1e-9
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_trend_sleeve_backtest.py::test_construction_builds_three_aligned_series -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the construction**

```python
# application/trend_sleeve_backtest.py
"""Pre-registered trend-following sleeve falsification backtest (spec 2026-06-08).

Blends an 80% SPY core with a 20% 12-month time-series-momentum sleeve (long/flat,
inverse-vol, 7 liquid ETFs) and gates on Sharpe-diff CI or >=25% drawdown cut,
net of cost. LOCKED gate — do not retune. Backtest only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import pstdev
from typing import Callable

from application.screen_ic_panels import monthly_closes_asof
from domain.trend_following import (
    blend_returns,
    inverse_vol_weights,
    time_series_momentum,
    turnover,
)

UNIVERSE = ["SPY", "EFA", "EEM", "TLT", "IEF", "GLD", "DBC"]
_CORE = "SPY"
_CORE_WEIGHT = 0.80
_VOL_WINDOW = 60  # trading days
_COST_PER_TRADE = 0.001  # 10 bps one-way

PriceSeriesFn = Callable[[str], list[tuple[datetime, float]]]


def _daily_vol_asof(series: list[tuple[datetime, float]], as_of: datetime) -> float:
    """Trailing 60-trading-day return volatility from closes with date <= as_of.

    Returns 0.0 when there are too few points (excludes the ETF from sizing).
    """
    closes = [c for d, c in series if d <= as_of]
    window = closes[-(_VOL_WINDOW + 1) :]
    if len(window) < 2:
        return 0.0
    rets = [window[i] / window[i - 1] - 1.0 for i in range(1, len(window))]
    return pstdev(rets) if len(rets) >= 2 else 0.0


def _close_asof(series: list[tuple[datetime, float]], as_of: datetime) -> float | None:
    prior = [c for d, c in series if d <= as_of]
    return prior[-1] if prior else None


@dataclass(frozen=True)
class SleeveVerdict:
    decision: str  # PASS | INCONCLUSIVE | KILL
    n_months: int
    sharpe_spy: float
    sharpe_sleeve: float
    sharpe_blended: float
    maxdd_spy: float
    maxdd_sleeve: float
    maxdd_blended: float
    cagr_spy: float
    cagr_sleeve: float
    cagr_blended: float
    sharpe_diff_point: float | None
    sharpe_diff_ci_low: float | None
    sharpe_diff_ci_high: float | None
    dd_reduction: float
    sharpe_blended_6040: float | None = None
    maxdd_blended_6040: float | None = None


class TrendSleeveBacktestUseCase:
    def __init__(self, price_series_fn: PriceSeriesFn) -> None:
        self._prices = price_series_fn
        self._cache: dict[str, list[tuple[datetime, float]]] = {}

    def _series(self, ticker: str) -> list[tuple[datetime, float]]:
        if ticker not in self._cache:
            self._cache[ticker] = self._prices(ticker)
        return self._cache[ticker]

    def build_series(
        self, month_ends: list[datetime], core_weight: float = _CORE_WEIGHT
    ) -> tuple[list[float], list[float], list[float]]:
        """Return (spy_returns, sleeve_net_returns, blended_returns), one entry per
        month-end transition t->t+1 (so len = len(month_ends) - 1).
        """
        spy_rets: list[float] = []
        sleeve_rets: list[float] = []
        prev_w: dict[str, float] = {}

        for i in range(len(month_ends) - 1):
            t = month_ends[i]
            t1 = month_ends[i + 1]

            # --- signal + sizing at t (point-in-time) ---
            vols: dict[str, float] = {}
            mom: dict[str, float] = {}
            for tk in UNIVERSE:
                s = self._series(tk)
                closes_m = monthly_closes_asof(s, t)
                m = time_series_momentum(closes_m)
                if m is not None:
                    mom[tk] = m
                vols[tk] = _daily_vol_asof(s, t)

            raw = inverse_vol_weights(vols)  # across all 7
            # Zero trend-negative / unknown-momentum ETFs; keep raw weight otherwise.
            new_w = {tk: w for tk, w in raw.items() if mom.get(tk, -1.0) > 0}

            # --- realized t->t+1 returns ---
            def _ret(tk: str) -> float:
                s = self._series(tk)
                c0 = _close_asof(s, t)
                c1 = _close_asof(s, t1)
                if c0 is None or c1 is None or c0 <= 0:
                    return 0.0
                return c1 / c0 - 1.0

            sleeve_gross = sum(w * _ret(tk) for tk, w in new_w.items())
            cost = _COST_PER_TRADE * turnover(prev_w, new_w)
            sleeve_rets.append(sleeve_gross - cost)
            spy_rets.append(_ret(_CORE))
            prev_w = new_w

        blended = blend_returns(spy_rets, sleeve_rets, core_weight)
        return spy_rets, sleeve_rets, blended
```

> Note: `monthly_closes_asof` lives in `application/screen_ic_panels.py` (built for the Phase-A IC backtest); reuse it, don't reimplement. `pstdev` is imported from `statistics`.

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_trend_sleeve_backtest.py::test_construction_builds_three_aligned_series -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add application/trend_sleeve_backtest.py tests/test_trend_sleeve_backtest.py
git commit -m "feat(trend): point-in-time sleeve construction (signal->weights->blended series)"
```

---

## Task 5: Gate logic — `execute()` → `SleeveVerdict` (`application/trend_sleeve_backtest.py`)

**Files:**
- Modify: `application/trend_sleeve_backtest.py`
- Test: `tests/test_trend_sleeve_backtest.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_trend_sleeve_backtest.py  (append)
def _crash_series(days: int) -> dict[str, list[tuple[datetime, float]]]:
    # SPY rises for 2y then crashes hard; a safe-haven (TLT) trends up through the crash.
    base = datetime(2006, 1, 2)
    spy: list[tuple[datetime, float]] = []
    tlt: list[tuple[datetime, float]] = []
    for i in range(days):
        d = base + timedelta(days=i)
        if i < days * 2 // 3:
            spy.append((d, 100.0 + 0.06 * i))
            tlt.append((d, 100.0 + 0.01 * i))
        else:
            # crash phase: SPY -0.4/day drift down, TLT keeps rising (flight to safety)
            spy.append((d, spy[-1][1] - 0.4))
            tlt.append((d, tlt[-1][1] + 0.05))
    flat = [(base + timedelta(days=i), 50.0) for i in range(days)]
    return {"SPY": spy, "EFA": flat, "EEM": flat, "TLT": tlt,
            "IEF": flat, "GLD": flat, "DBC": flat}


def test_planted_crash_protection_cuts_drawdown() -> None:
    series = _crash_series(1100)
    uc = TrendSleeveBacktestUseCase(price_series_fn=lambda t: series[t])
    months: list[datetime] = []
    for yr in (2007, 2008):
        for m in range(1, 13):
            months.append(datetime(yr, m, 28))
    v = uc.execute(months)
    # The blended portfolio must have a shallower (less negative) max drawdown
    # than SPY-core, and the gate should not be KILL.
    assert v.maxdd_blended > v.maxdd_spy  # less negative
    assert v.decision in ("PASS", "INCONCLUSIVE")


def test_flat_noise_does_not_false_pass() -> None:
    # No asset trends; sleeve sits mostly in cash, blended ~= 0.8*SPY (flat).
    base = datetime(2006, 1, 2)
    flat = [(base + timedelta(days=i), 50.0) for i in range(1100)]
    series = {tk: flat for tk in
              ["SPY", "EFA", "EEM", "TLT", "IEF", "GLD", "DBC"]}
    uc = TrendSleeveBacktestUseCase(price_series_fn=lambda t: series[t])
    months = [datetime(yr, m, 28) for yr in (2007, 2008) for m in range(1, 13)]
    v = uc.execute(months)
    assert v.decision in ("INCONCLUSIVE", "KILL")  # never a false PASS on no signal


def test_verdict_is_frozen() -> None:
    base = datetime(2006, 1, 2)
    flat = [(base + timedelta(days=i), 50.0) for i in range(500)]
    uc = TrendSleeveBacktestUseCase(price_series_fn=lambda t: flat)
    months = [datetime(2007, m, 28) for m in range(1, 13)]
    v = uc.execute(months)
    try:
        v.decision = "X"  # type: ignore[misc]
        assert False, "should be frozen"
    except Exception:
        pass
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_trend_sleeve_backtest.py -k "planted or flat_noise or frozen" -v`
Expected: FAIL with `AttributeError: 'TrendSleeveBacktestUseCase' object has no attribute 'execute'`.

- [ ] **Step 3: Implement `execute` (append to the class; add imports at top)**

Add these imports at the top of `application/trend_sleeve_backtest.py`:

```python
from application.evaluation import DrawdownTracker
from application.precision_metrics import sharpe_difference_bootstrap
from domain.backtest_metrics import cagr, sharpe
from domain.trend_following import equity_curve
```

Add the method to `TrendSleeveBacktestUseCase`:

```python
    def execute(self, month_ends: list[datetime]) -> SleeveVerdict:
        spy, sleeve, blended = self.build_series(month_ends)
        _, _, blended_6040 = self.build_series(month_ends, core_weight=0.60)

        dd = DrawdownTracker()
        maxdd_spy = float(dd.compute(spy)["max_drawdown"])
        maxdd_sleeve = float(dd.compute(sleeve)["max_drawdown"])
        maxdd_blended = float(dd.compute(blended)["max_drawdown"])

        sd = sharpe_difference_bootstrap(blended, spy, periods_per_year=12)
        ci_low = sd.get("ci_low")
        ci_high = sd.get("ci_high")
        point = sd.get("point")

        # Drawdown-reduction ratio: 1 - |blended|/|spy| (both negative -> positive ratio).
        dd_reduction = (
            1.0 - (maxdd_blended / maxdd_spy) if maxdd_spy < 0 else 0.0
        )

        s_spy = sharpe(spy, 12)
        s_sleeve = sharpe(sleeve, 12)
        s_blended = sharpe(blended, 12)

        # --- LOCKED gate (spec section 5) ---
        primary = ci_low is not None and ci_low > 0.0
        secondary = dd_reduction >= 0.25
        strictly_worse = s_blended < s_spy and maxdd_blended < maxdd_spy

        if primary or secondary:
            decision = "PASS"
        elif strictly_worse:
            decision = "KILL"
        else:
            decision = "INCONCLUSIVE"

        return SleeveVerdict(
            decision=decision,
            n_months=len(blended),
            sharpe_spy=round(s_spy, 4),
            sharpe_sleeve=round(s_sleeve, 4),
            sharpe_blended=round(s_blended, 4),
            maxdd_spy=round(maxdd_spy, 4),
            maxdd_sleeve=round(maxdd_sleeve, 4),
            maxdd_blended=round(maxdd_blended, 4),
            cagr_spy=round(cagr(equity_curve(spy), 12), 4),
            cagr_sleeve=round(cagr(equity_curve(sleeve), 12), 4),
            cagr_blended=round(cagr(equity_curve(blended), 12), 4),
            sharpe_diff_point=point,
            sharpe_diff_ci_low=ci_low,
            sharpe_diff_ci_high=ci_high,
            dd_reduction=round(dd_reduction, 4),
            sharpe_blended_6040=round(sharpe(blended_6040, 12), 4),
            maxdd_blended_6040=round(float(dd.compute(blended_6040)["max_drawdown"]), 4),
        )
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_trend_sleeve_backtest.py -v`
Expected: PASS (all construction + gate tests).

- [ ] **Step 5: Commit**

```bash
git add application/trend_sleeve_backtest.py tests/test_trend_sleeve_backtest.py
git commit -m "feat(trend): LOCKED gate (Sharpe-diff CI or >=25% drawdown cut) -> SleeveVerdict"
```

---

## Task 6: `backtest-trend-sleeve` CLI (`application/cli.py`)

**Files:**
- Modify: `application/cli.py`
- Test: `tests/test_cli_trend_sleeve.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_trend_sleeve.py
import json
from datetime import datetime, timedelta
from pathlib import Path

from click.testing import CliRunner

from application import cli as cli_mod


def test_backtest_trend_sleeve_writes_report_and_prints_verdict(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    base = datetime(2006, 1, 2)
    flat = [(base + timedelta(days=i), 50.0) for i in range(1200)]

    # Avoid network: every ticker returns the same synthetic flat series.
    monkeypatch.setattr(
        "application.trend_sleeve_backtest.load_price_series",
        lambda ticker, start, end: flat,
        raising=False,
    )

    runner = CliRunner()
    result = runner.invoke(
        cli_mod.cli,
        ["backtest-trend-sleeve", "--start", "2007-01-01", "--end", "2008-12-01",
         "--report-dir", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    assert "VERDICT" in result.output
    assert "drawdown" in result.output.lower()
    reports = list(Path(tmp_path).glob("trend_sleeve_*.json"))
    assert len(reports) == 1
    data = json.loads(reports[0].read_text())
    assert data["decision"] in ("PASS", "INCONCLUSIVE", "KILL")
    assert "sharpe_diff_ci_low" in data and "dd_reduction" in data
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_cli_trend_sleeve.py -v`
Expected: FAIL (no `backtest-trend-sleeve` command).

- [ ] **Step 3: Implement the command in `application/cli.py`**

First ensure the use case can be monkeypatched at the module's `load_price_series` name. Add this default price function inside the command (the use case takes an injected `price_series_fn`). Add near the other `@cli.command` definitions:

```python
@cli.command("backtest-trend-sleeve")
@click.option("--start", default="2008-01-01", show_default=True)
@click.option("--end", default="2026-01-01", show_default=True)
@click.option("--report-dir", default="data/reports/", show_default=True)
def backtest_trend_sleeve(start: str, end: str, report_dir: str) -> None:
    """Pre-registered trend-following sleeve falsification test (spec 2026-06-08).

    80% SPY + 20% 12-mo time-series-momentum sleeve (7 liquid ETFs, long/flat,
    inverse-vol). LOCKED gate: PASS if blended Sharpe-diff CI excludes 0 OR max
    drawdown cut >=25% net of cost; KILL if strictly worse; else INCONCLUSIVE.
    Backtest only — no product. Honest non-claim: diversifier sleeve, not alpha.
    """
    import json
    from datetime import date, datetime, timedelta

    from application.trend_sleeve_backtest import (
        UNIVERSE,
        TrendSleeveBacktestUseCase,
    )
    from application.trend_sleeve_backtest import load_price_series  # patchable name

    start_dt = datetime.fromisoformat(start)
    end_dt = datetime.fromisoformat(end)

    # Month-end dates (28th as a stable in-month sentinel), monthly cadence.
    months: list[datetime] = []
    d = start_dt
    while d <= end_dt:
        months.append(datetime(d.year, d.month, 28))
        d = datetime(d.year + (d.month // 12), (d.month % 12) + 1, 1)

    price_start = start_dt - timedelta(days=420)  # 12-mo lookback + buffer
    cache: dict[str, list[tuple[datetime, float]]] = {}

    def _prices(ticker: str) -> list[tuple[datetime, float]]:
        if ticker not in cache:
            cache[ticker] = load_price_series(ticker, price_start, end_dt)
        return cache[ticker]

    click.echo(f"Loading {len(UNIVERSE)} ETFs ({', '.join(UNIVERSE)})...")
    uc = TrendSleeveBacktestUseCase(price_series_fn=_prices)
    v = uc.execute(months)

    as_of = date.today().isoformat()
    out_dir = Path(report_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"trend_sleeve_{as_of}.json"
    report = {
        "as_of": as_of, "start": start, "end": end, "n_months": v.n_months,
        "decision": v.decision,
        "sharpe_spy": v.sharpe_spy, "sharpe_sleeve": v.sharpe_sleeve,
        "sharpe_blended": v.sharpe_blended,
        "maxdd_spy": v.maxdd_spy, "maxdd_sleeve": v.maxdd_sleeve,
        "maxdd_blended": v.maxdd_blended,
        "cagr_spy": v.cagr_spy, "cagr_sleeve": v.cagr_sleeve,
        "cagr_blended": v.cagr_blended,
        "sharpe_diff_point": v.sharpe_diff_point,
        "sharpe_diff_ci_low": v.sharpe_diff_ci_low,
        "sharpe_diff_ci_high": v.sharpe_diff_ci_high,
        "dd_reduction": v.dd_reduction,
        "sharpe_blended_6040": v.sharpe_blended_6040,
        "maxdd_blended_6040": v.maxdd_blended_6040,
        "claim": "diversifier sleeve (risk control), NOT alpha — see spec 2026-06-08",
    }
    out_file.write_text(json.dumps(report, indent=2))

    click.echo(f"\nTrend-Following Sleeve Backtest ({as_of})  n_months={v.n_months}")
    click.echo(f"  SPY-core   : Sharpe {v.sharpe_spy:+.3f}  maxDD {v.maxdd_spy:+.1%}  CAGR {v.cagr_spy:+.1%}")
    click.echo(f"  sleeve     : Sharpe {v.sharpe_sleeve:+.3f}  maxDD {v.maxdd_sleeve:+.1%}  CAGR {v.cagr_sleeve:+.1%}")
    click.echo(f"  blended80/20: Sharpe {v.sharpe_blended:+.3f}  maxDD {v.maxdd_blended:+.1%}  CAGR {v.cagr_blended:+.1%}")
    sd_ci = (
        f"[{v.sharpe_diff_ci_low}, {v.sharpe_diff_ci_high}]"
        if v.sharpe_diff_ci_low is not None else "n/a"
    )
    click.echo(f"  Sharpe-diff (blended-SPY): {v.sharpe_diff_point}  CI={sd_ci}")
    click.echo(f"  drawdown reduction: {v.dd_reduction:+.1%}  (gate >= 25%)")
    click.echo(f"  [sensitivity 60/40, not gated] Sharpe {v.sharpe_blended_6040}  maxDD {v.maxdd_blended_6040}")
    click.echo(f"  VERDICT: {v.decision}")
    click.echo("  (diversifier sleeve = risk control, NOT alpha)")
    click.echo(f"Report -> {out_file}")
```

Then add a module-level import so `load_price_series` is patchable from `application.trend_sleeve_backtest`. At the top of `application/trend_sleeve_backtest.py`, add:

```python
from application.price_returns import load_price_series
```

(The use case itself takes an injected `price_series_fn` and does NOT call `load_price_series` directly — the CLI wires the real loader through `_prices`. Importing it here gives the CLI test a single patch point: `application.trend_sleeve_backtest.load_price_series`.)

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_cli_trend_sleeve.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add application/cli.py application/trend_sleeve_backtest.py tests/test_cli_trend_sleeve.py
git commit -m "feat(trend): backtest-trend-sleeve CLI (full report + honest non-claim)"
```

---

## Task 7: Verify, run live, record verdict

**Files:**
- Create (output): `data/reports/trend_sleeve_<date>.json`

- [ ] **Step 1: Full quality gate**

Run: `make check`
Expected: green — mypy strict, ≥90% coverage, all tests pass. If new-module coverage < 90%, add a focused test (do NOT lower the threshold).

- [ ] **Step 2: Run the live pre-registered backtest**

Run: `python -m application.cli backtest-trend-sleeve --start 2008-01-01 --end 2026-01-01`
Expected: loads 7 ETFs from yfinance, prints the per-arm table + Sharpe-diff CI + drawdown reduction + VERDICT, writes `data/reports/trend_sleeve_<today>.json`. Record the verdict and all printed numbers.

- [ ] **Step 3: Do NOT retune on the result.** Whatever the gate returns is the result. If PASS → the diversifier sleeve is validated (risk control, not alpha). If INCONCLUSIVE/KILL → record honestly.

- [ ] **Step 4: Commit the report**

```bash
git add data/reports/trend_sleeve_*.json
git commit -m "test(trend): live trend-sleeve backtest verdict (2008-2026)"
```

> The verdict interpretation (CI width, regime read, is the drawdown-cut cost-robust, PASS/INCONCLUSIVE/KILL label, ADR write-up, and the Phase-2 decision) is an Opus `verification-before-completion` step the controller does AFTER this plan — not part of the mechanical implementation.

---

## Self-Review (completed by planner)

**Spec coverage:**
- §2 claim (80/20 blend beats SPY on Sharpe-diff OR ≥25% DD cut net cost) → Task 5 gate.
- §3 universe/window/data (7 ETFs, 2008–2026, `load_price_series`, 0% cash) → Task 4 (`UNIVERSE`, `_ret` 0% cash), Task 6 (window/dates).
- §4 signal/sizing (12-mo momentum, inverse-vol-across-7→zero-negatives→cash, 10bps turnover cost, 80/20) → Tasks 1–5 (`time_series_momentum`, `inverse_vol_weights` + zeroing in `build_series`, `turnover`, `blend_returns`).
- §5 gate (Sharpe-diff CI **or** ≥25% DD cut; KILL if strictly worse; full printout; 60/40 sensitivity) → Task 5 (`execute`) + Task 6 (printout + sensitivity).
- §6 architecture (pure domain + application use case + CLI) → Tasks 1–6 match the file map.
- §7 testing (planted-crash recovers protection, flat-noise no false-PASS, drawdown math, cost charged) → Tasks 4–5 tests.
- §8 scope (backtest only, no product) → no product task; Task 7 records verdict only.

**Placeholder scan:** none. Every code step is complete. The one `# type: ignore[no-untyped-def]` is on a test signature only (project convention).

**Type consistency:** `SleeveVerdict` fields used in Task 5 match the dataclass defined in Task 4. `build_series` returns `(spy, sleeve, blended)` consistently in Tasks 4 and 5. `monthly_closes_asof`, `sharpe_difference_bootstrap`, `DrawdownTracker.compute`, `cagr`, `sharpe`, `cost`-via-`turnover` all match the verbatim signatures gathered. `load_price_series` is imported at module top in `trend_sleeve_backtest.py` (patch point) and the use case stays injection-based.

**One known subtlety flagged for the implementer:** the `dd_reduction = 1 - maxdd_blended/maxdd_spy` formula assumes `maxdd_spy < 0` (guarded). When SPY has no drawdown in a synthetic test (maxDD 0.0), `dd_reduction` is 0.0 and the gate falls to the Sharpe-diff branch — correct behavior, covered by the flat-noise test.
