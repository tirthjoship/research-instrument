# Momentum & Exit-Discipline Engine — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the pre-registered momentum + trend-filter + trailing-exit backtest (the validation gate) plus a per-holding verdict layer, producing a PROCEED/KILL verdict on whether disciplined exit rules beat buy-and-hold out of sample.

**Architecture:** Hexagonal, reuse-heavy. Pure rule math + metrics in `domain/` (stdlib only). Backtest + verdict orchestration in `application/`, injecting a price provider (live yfinance in CLI, fakes in tests). Reuses `precision_metrics.moving_block_bootstrap`, `evaluation` (DrawdownTracker/RegimeSplitter/TransactionCostModel), `price_returns.load_price_series`, and `_get_ticker_universe`. Phase 2 (screener/daily feed) is NOT in this plan — it is gated on a PROCEED verdict per the spec.

**Tech Stack:** Python 3.12, numpy (present), yfinance (present, `.TO` for TSX), pytest + Hypothesis, mypy strict, click.

**Spec:** `docs/superpowers/specs/2026-06-07-personal-momentum-exit-discipline-backtest-design.md`

**Conventions:** domain pure (stdlib only — no numpy in `domain/`); adapters/use-cases may import libs; tests use fakes/fixtures, never live APIs; pre-registered parameters (200-day trend, 3×ATR(22) Chandelier, 12-1 momentum, top tercile, 12% vol target) are FROZEN — do not tune; commit after each green task; READ a file before modifying and match real signatures.

---

## File Structure

- Create `domain/trend_rules.py` — pure rule primitives: `sma`, `above_trend`, `true_range`, `atr`, `chandelier_stop`, `momentum_12_1`, `top_fraction_threshold`.
- Create `domain/backtest_metrics.py` — pure metrics on equity curves: `daily_returns`, `cagr`, `sharpe`, `sortino`, `max_drawdown`.
- Create `application/momentum_exit_backtest.py` — `MomentumExitBacktestUseCase` (strategy + baselines + verdict gate).
- Create `application/portfolio_verdict.py` — `PortfolioVerdictUseCase` (apply rules to current holdings).
- Create `config/tickers/tsx60.txt` — TSX 60 constituents.
- Modify `application/cli.py` — add `validate-momentum-discipline` and `portfolio-verdict` commands.
- Tests: `tests/test_trend_rules.py`, `tests/test_backtest_metrics.py`, `tests/test_momentum_exit_backtest.py`, `tests/test_portfolio_verdict.py`, plus additions to `tests/test_opportunity_cli.py`.

---

## Phase 1A — Pure rule primitives

### Task 1: `domain/trend_rules.py` — SMA + trend filter

**Files:**
- Create: `domain/trend_rules.py`
- Test: `tests/test_trend_rules.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_sma_basic():
    from domain.trend_rules import sma
    assert sma([1.0, 2.0, 3.0, 4.0], 2) == 3.5   # mean of last 2

def test_sma_insufficient_returns_none():
    from domain.trend_rules import sma
    assert sma([1.0, 2.0], 5) is None

def test_above_trend_true_when_price_over_sma():
    from domain.trend_rules import above_trend
    assert above_trend(105.0, 100.0) is True

def test_above_trend_false_when_sma_none():
    from domain.trend_rules import above_trend
    assert above_trend(105.0, None) is False
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_trend_rules.py -v`
Expected: FAIL `ModuleNotFoundError: domain.trend_rules`

- [ ] **Step 3: Implement**

```python
"""Pure trend/momentum rule primitives (stdlib only). Pre-registered params
live in the use cases; these are parameter-free building blocks."""

from __future__ import annotations


def sma(values: list[float], window: int) -> float | None:
    """Simple moving average of the last `window` values; None if too few."""
    if window <= 0 or len(values) < window:
        return None
    return sum(values[-window:]) / window


def above_trend(price: float, sma_value: float | None) -> bool:
    """True iff price is strictly above the trend line. None SMA => not in trend."""
    if sma_value is None:
        return False
    return price > sma_value
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_trend_rules.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add domain/trend_rules.py tests/test_trend_rules.py
git commit -m "feat: trend_rules sma + above_trend (pure)"
```

---

### Task 2: `domain/trend_rules.py` — ATR + Chandelier trailing stop

**Files:**
- Modify: `domain/trend_rules.py`
- Test: `tests/test_trend_rules.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_true_range_uses_max_of_three():
    from domain.trend_rules import true_range
    # high-low=5, |high-prevclose|=|105-101|=4, |low-prevclose|=|100-101|=1 -> 5
    assert true_range(105.0, 100.0, 101.0) == 5.0

def test_atr_averages_true_ranges():
    from domain.trend_rules import atr
    highs = [10.0, 11.0, 12.0]
    lows = [9.0, 10.0, 11.0]
    closes = [9.5, 10.5, 11.5]
    # TR1 (no prev close): 10-9=1; TR2: max(11-10, |11-9.5|, |10-9.5|)=1.5; TR3: max(12-11,|12-10.5|,|11-10.5|)=1.5
    assert atr(highs, lows, closes, 3) == (1.0 + 1.5 + 1.5) / 3

def test_atr_insufficient_returns_none():
    from domain.trend_rules import atr
    assert atr([1.0], [1.0], [1.0], 5) is None

def test_chandelier_stop_below_high():
    from domain.trend_rules import chandelier_stop
    # highest_high - mult*atr
    assert chandelier_stop(120.0, 4.0, 3.0) == 108.0
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_trend_rules.py -k "true_range or atr or chandelier" -v`
Expected: FAIL (ImportError on the new names)

- [ ] **Step 3: Implement (append to `domain/trend_rules.py`)**

```python
def true_range(high: float, low: float, prev_close: float | None) -> float:
    """Wilder true range. prev_close None => simple high-low."""
    hl = high - low
    if prev_close is None:
        return hl
    return max(hl, abs(high - prev_close), abs(low - prev_close))


def atr(
    highs: list[float], lows: list[float], closes: list[float], window: int
) -> float | None:
    """Average true range over the last `window` bars (simple mean of TRs)."""
    n = len(closes)
    if n < window or len(highs) != n or len(lows) != n or window <= 0:
        return None
    trs: list[float] = []
    for i in range(n - window, n):
        prev_close = closes[i - 1] if i > 0 else None
        trs.append(true_range(highs[i], lows[i], prev_close))
    return sum(trs) / window


def chandelier_stop(highest_high: float, atr_value: float, mult: float = 3.0) -> float:
    """Trailing stop = highest high since entry minus mult*ATR."""
    return highest_high - mult * atr_value
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_trend_rules.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add domain/trend_rules.py tests/test_trend_rules.py
git commit -m "feat: trend_rules atr + chandelier_stop (pure)"
```

---

### Task 3: `domain/trend_rules.py` — 12-1 momentum + tercile threshold

**Files:**
- Modify: `domain/trend_rules.py`
- Test: `tests/test_trend_rules.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_momentum_12_1_skips_recent_month():
    from domain.trend_rules import momentum_12_1
    # 13 monthly closes; price 12 months ago = closes[-13], price 1 month ago = closes[-2]
    closes = [100.0] + [0.0]*10 + [150.0, 999.0]  # [-13]=100, [-2]=150, [-1]=999 (ignored)
    closes = [100.0, 0,0,0,0,0,0,0,0,0,0, 150.0, 999.0]
    assert abs(momentum_12_1(closes) - 0.5) < 1e-9   # 150/100 - 1

def test_momentum_12_1_insufficient_returns_none():
    from domain.trend_rules import momentum_12_1
    assert momentum_12_1([1.0]*5) is None

def test_top_fraction_threshold_tercile():
    from domain.trend_rules import top_fraction_threshold
    vals = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
    # top 1/3 -> the 2 highest are 0.5,0.6; threshold = min of top tercile = 0.5
    assert top_fraction_threshold(vals, 1/3) == 0.5
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_trend_rules.py -k "momentum or tercile or threshold" -v`
Expected: FAIL (ImportError)

- [ ] **Step 3: Implement (append)**

```python
import math


def momentum_12_1(monthly_closes: list[float]) -> float | None:
    """12-minus-1 month total return: price 1 month ago / price 12 months ago - 1.
    Needs >= 13 monthly closes (most recent last). Skips the most recent month."""
    if len(monthly_closes) < 13:
        return None
    twelve_ago = monthly_closes[-13]
    one_ago = monthly_closes[-2]
    if twelve_ago <= 0:
        return None
    return one_ago / twelve_ago - 1.0


def top_fraction_threshold(values: list[float], fraction: float) -> float | None:
    """Return the cutoff value such that the top `fraction` of values are >= it.
    e.g. fraction=1/3 over 6 values -> the 2 highest qualify; returns min of those 2."""
    clean = [v for v in values if not math.isnan(v)]
    if not clean or fraction <= 0:
        return None
    k = max(1, math.floor(len(clean) * fraction))
    return sorted(clean, reverse=True)[k - 1]
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_trend_rules.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add domain/trend_rules.py tests/test_trend_rules.py
git commit -m "feat: trend_rules momentum_12_1 + top_fraction_threshold (pure)"
```

---

## Phase 1B — Backtest metrics (pure)

### Task 4: `domain/backtest_metrics.py` — returns, CAGR, Sharpe, Sortino

**Files:**
- Create: `domain/backtest_metrics.py`
- Test: `tests/test_backtest_metrics.py`

- [ ] **Step 1: Write the failing tests**

```python
import math

def test_daily_returns():
    from domain.backtest_metrics import daily_returns
    assert daily_returns([100.0, 110.0, 99.0]) == [0.1, -0.1]

def test_cagr_doubling_over_one_year():
    from domain.backtest_metrics import cagr
    eq = [1.0] + [2.0]  # endpoints; 252 trading days assumed via n_periods
    # 1 -> 2 over 252 periods => ~100% annualized
    assert abs(cagr([1.0, 2.0], periods_per_year=1) - 1.0) < 1e-9

def test_sharpe_positive_for_steady_gains():
    from domain.backtest_metrics import sharpe
    rets = [0.001] * 252
    assert sharpe(rets, periods_per_year=252) > 0

def test_sharpe_zero_variance_returns_zero():
    from domain.backtest_metrics import sharpe
    assert sharpe([0.0, 0.0, 0.0]) == 0.0
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_backtest_metrics.py -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
"""Pure performance metrics on equity curves / return series (stdlib only)."""

from __future__ import annotations

import math


def daily_returns(equity: list[float]) -> list[float]:
    out: list[float] = []
    for i in range(1, len(equity)):
        prev = equity[i - 1]
        out.append((equity[i] - prev) / prev if prev != 0 else 0.0)
    return out


def cagr(equity: list[float], periods_per_year: int = 252) -> float:
    if len(equity) < 2 or equity[0] <= 0:
        return 0.0
    n_periods = len(equity) - 1
    total = equity[-1] / equity[0]
    if total <= 0:
        return -1.0
    years = n_periods / periods_per_year
    if years <= 0:
        return 0.0
    return total ** (1.0 / years) - 1.0


def sharpe(returns: list[float], periods_per_year: int = 252, rf: float = 0.0) -> float:
    if len(returns) < 2:
        return 0.0
    excess = [r - rf / periods_per_year for r in returns]
    mean = sum(excess) / len(excess)
    var = sum((r - mean) ** 2 for r in excess) / (len(excess) - 1)
    std = math.sqrt(var)
    if std == 0.0:
        return 0.0
    return (mean / std) * math.sqrt(periods_per_year)


def sortino(returns: list[float], periods_per_year: int = 252, rf: float = 0.0) -> float:
    if len(returns) < 2:
        return 0.0
    excess = [r - rf / periods_per_year for r in returns]
    mean = sum(excess) / len(excess)
    downside = [min(r, 0.0) ** 2 for r in excess]
    dd = math.sqrt(sum(downside) / len(excess))
    if dd == 0.0:
        return 0.0
    return (mean / dd) * math.sqrt(periods_per_year)
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_backtest_metrics.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add domain/backtest_metrics.py tests/test_backtest_metrics.py
git commit -m "feat: backtest_metrics daily_returns/cagr/sharpe/sortino (pure)"
```

---

### Task 5: `domain/backtest_metrics.py` — max drawdown

**Files:**
- Modify: `domain/backtest_metrics.py`
- Test: `tests/test_backtest_metrics.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_max_drawdown_simple():
    from domain.backtest_metrics import max_drawdown
    # peak 100 -> trough 60 => 0.40
    assert abs(max_drawdown([100.0, 120.0, 72.0, 90.0]) - 0.40) < 1e-9  # peak 120 -> 72 = 0.40

def test_max_drawdown_monotonic_up_is_zero():
    from domain.backtest_metrics import max_drawdown
    assert max_drawdown([1.0, 2.0, 3.0]) == 0.0
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_backtest_metrics.py -k drawdown -v`
Expected: FAIL (ImportError)

- [ ] **Step 3: Implement (append)**

```python
def max_drawdown(equity: list[float]) -> float:
    """Largest peak-to-trough decline as a positive fraction (0.40 = -40%)."""
    if not equity:
        return 0.0
    peak = equity[0]
    mdd = 0.0
    for v in equity:
        if v > peak:
            peak = v
        if peak > 0:
            dd = (peak - v) / peak
            if dd > mdd:
                mdd = dd
    return mdd
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_backtest_metrics.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add domain/backtest_metrics.py tests/test_backtest_metrics.py
git commit -m "feat: backtest_metrics max_drawdown (pure)"
```

---

## Phase 1C — Backtest use case

### Task 6: `MomentumExitBacktestUseCase` — strategy simulation

**Files:**
- Create: `application/momentum_exit_backtest.py`
- Test: `tests/test_momentum_exit_backtest.py`

The use case injects a `price_provider(ticker) -> list[tuple[datetime, float]]` (daily closes; in CLI this wraps `load_price_series`, in tests a fake). It simulates a monthly-rebalanced, long-only, equal-weight portfolio: each month, a name is held iff `above_trend(price, sma(closes, 200))` AND its `momentum_12_1` (on monthly closes) is in the top `mom_fraction`. A held name is force-exited intra-month if its close breaches the Chandelier stop (`chandelier_stop(highest_high_since_entry, atr(...,22), 3.0)`). Builds a daily equity curve. Pre-registered params are constructor defaults — FROZEN.

- [ ] **Step 1: Write the failing test**

```python
from datetime import datetime, timedelta, timezone

def _daily(start, vals):
    return [(start + timedelta(days=i), float(v)) for i, v in enumerate(vals)]

def test_strategy_exits_on_trend_break_cuts_drawdown():
    from application.momentum_exit_backtest import MomentumExitBacktestUseCase
    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    # WIN: rises 100->300 over ~400 days then crashes to 150.
    # Strategy with a trailing stop should exit during the crash; buy&hold rides it down.
    up = list(range(100, 300)) + list(range(300, 150, -1))  # up then crash
    prices = {"WIN": _daily(start, up)}
    def provider(t): return prices.get(t, [])
    uc = MomentumExitBacktestUseCase(price_provider=provider)
    report = uc.execute(["WIN"], start, start + timedelta(days=len(up)))
    # strategy max drawdown < buy&hold max drawdown (it exited the crash)
    assert report["strategy"]["max_drawdown"] < report["buy_hold"]["max_drawdown"]
    assert "equity" in report["strategy"]
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_momentum_exit_backtest.py -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Implement**

Create `application/momentum_exit_backtest.py`. Structure (fill the simulation loop to satisfy the test; reuse `domain.trend_rules` + `domain.backtest_metrics`):

```python
"""Pre-registered momentum + trend-filter + Chandelier-exit backtest.
Validation gate per spec 2026-06-07. Long-only, monthly rebalance, equal weight."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from domain.backtest_metrics import cagr, daily_returns, max_drawdown, sharpe, sortino
from domain.trend_rules import (
    above_trend, atr, chandelier_stop, momentum_12_1, sma, top_fraction_threshold,
)

PriceProvider = Callable[[str], list[tuple[datetime, float]]]


class MomentumExitBacktestUseCase:
    def __init__(
        self,
        price_provider: PriceProvider,
        trend_window: int = 200,
        atr_window: int = 22,
        atr_mult: float = 3.0,
        mom_fraction: float = 1.0 / 3.0,
    ) -> None:
        self._prices = price_provider
        self._trend_window = trend_window
        self._atr_window = atr_window
        self._atr_mult = atr_mult
        self._mom_fraction = mom_fraction

    def _metrics(self, equity: list[float]) -> dict[str, Any]:
        rets = daily_returns(equity)
        return {
            "equity": equity,
            "cagr": cagr(equity),
            "sharpe": sharpe(rets),
            "sortino": sortino(rets),
            "max_drawdown": max_drawdown(equity),
        }

    def execute(
        self, universe: list[str], start: datetime, end: datetime
    ) -> dict[str, Any]:
        # 1. Load aligned daily closes per ticker within [start, end].
        # 2. Build a shared trading-day calendar (union of dates, sorted).
        # 3. STRATEGY: walk days; on the 1st trading day of each month recompute
        #    eligibility per name: in-trend (close > sma(closes_so_far, trend_window))
        #    AND momentum_12_1(monthly_closes_so_far) >= top_fraction_threshold(all names' mom, mom_fraction).
        #    Hold eligible names equal-weight; track highest_high since entry; exit a
        #    name intra-month when close < chandelier_stop(highest_high, atr(...22), atr_mult).
        #    Daily portfolio return = mean of held names' daily returns (0 if flat). Build equity (start=1.0).
        # 4. BUY_HOLD: equal-weight buy-hold of all names, daily-rebalanced equity.
        # Return {"strategy": self._metrics(strat_eq), "buy_hold": self._metrics(bh_eq), "universe": universe}.
        ...
```

Implement the loop so the test passes (strategy exits the WIN crash via the trailing stop → lower max_drawdown than buy_hold). Keep it pure-Python + the domain helpers; no look-ahead (only data up to the current day feeds each decision).

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_momentum_exit_backtest.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add application/momentum_exit_backtest.py tests/test_momentum_exit_backtest.py
git commit -m "feat: MomentumExitBacktestUseCase strategy + buy-hold simulation"
```

---

### Task 7: Verdict gate — SPY baseline + bootstrap Sharpe-diff + drawdown-reduction

**Files:**
- Modify: `application/momentum_exit_backtest.py`
- Test: `tests/test_momentum_exit_backtest.py`

- [ ] **Step 1: Write the failing test**

```python
def test_verdict_proceed_when_better_sharpe_and_lower_dd(monkeypatch):
    from application import momentum_exit_backtest as m
    uc = m.MomentumExitBacktestUseCase(price_provider=lambda t: [])
    report = {
        "strategy": {"sharpe": 1.2, "max_drawdown": 0.20,
                     "equity": [1.0, 1.1, 1.2], "cagr": 0.1, "sortino": 1.5},
        "buy_hold": {"sharpe": 0.6, "max_drawdown": 0.50,
                     "equity": [1.0, 0.9, 1.1], "cagr": 0.1, "sortino": 0.7},
    }
    verdict = uc.verdict(report, sharpe_diff_ci_low=0.1)  # CI excludes 0
    assert verdict["decision"] == "PROCEED"
    assert verdict["drawdown_reduction"] >= 0.30

def test_verdict_kill_when_dd_not_reduced_enough():
    from application import momentum_exit_backtest as m
    uc = m.MomentumExitBacktestUseCase(price_provider=lambda t: [])
    report = {
        "strategy": {"sharpe": 1.2, "max_drawdown": 0.45, "equity": [1.0], "cagr": 0, "sortino": 0},
        "buy_hold": {"sharpe": 0.6, "max_drawdown": 0.50, "equity": [1.0], "cagr": 0, "sortino": 0},
    }
    verdict = uc.verdict(report, sharpe_diff_ci_low=0.1)
    assert verdict["decision"] == "KILL"   # only 10% dd reduction < 30%
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_momentum_exit_backtest.py -k verdict -v`
Expected: FAIL (no `verdict` method)

- [ ] **Step 3: Implement (add method + SPY baseline)**

Add a `verdict` method implementing the LOCKED gate (spec §"LOCKED success criterion"):
```python
    def verdict(self, report: dict[str, Any], sharpe_diff_ci_low: float) -> dict[str, Any]:
        strat = report["strategy"]
        bh = report["buy_hold"]
        bh_dd = bh["max_drawdown"]
        dd_reduction = (bh_dd - strat["max_drawdown"]) / bh_dd if bh_dd > 0 else 0.0
        beats_sharpe = sharpe_diff_ci_low > 0.0          # bootstrap CI excludes 0, positive
        cuts_drawdown = dd_reduction >= 0.30
        decision = "PROCEED" if (beats_sharpe and cuts_drawdown) else "KILL"
        return {
            "decision": decision,
            "sharpe_diff_ci_low": sharpe_diff_ci_low,
            "drawdown_reduction": dd_reduction,
            "beats_sharpe": beats_sharpe,
            "cuts_drawdown": cuts_drawdown,
        }
```
Also extend `execute` to compute an SPY buy-hold baseline (call `self._prices("SPY")`) and include it under `report["spy"]` via `self._metrics(...)`. The bootstrap CI on the per-period Sharpe difference is computed in the CLI (Task 9) using `moving_block_bootstrap` on the paired daily-return difference series; `verdict` just consumes `sharpe_diff_ci_low`.

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_momentum_exit_backtest.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add application/momentum_exit_backtest.py tests/test_momentum_exit_backtest.py
git commit -m "feat: verdict gate (Sharpe-diff CI + >=30% drawdown reduction) + SPY baseline"
```

---

## Phase 1D — Universe + CLI

### Task 8: TSX 60 ticker config + universe loader

**Files:**
- Create: `config/tickers/tsx60.txt`
- Modify: `application/cli.py` (extend `_get_ticker_universe` or add a `_get_backtest_universe(market)` helper — READ the existing loader first and match its file-reading pattern)
- Test: `tests/test_opportunity_cli.py`

- [ ] **Step 1: Write the failing test**

```python
def test_backtest_universe_includes_tsx(monkeypatch):
    import application.cli as climod
    uni = climod._get_backtest_universe("us")
    assert "AAPL" in uni
    assert any(t.endswith(".TO") for t in uni)   # TSX names carry .TO suffix
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_opportunity_cli.py -k backtest_universe -v`
Expected: FAIL (no `_get_backtest_universe`)

- [ ] **Step 3: Implement**

Create `config/tickers/tsx60.txt` with TSX 60 symbols WITHOUT suffix (one per line, `#` comments allowed), e.g. `RY`, `TD`, `ENB`, `CNR`, `SU`, `ATD`, `BMO`, `CP`, `SHOP`, `BNS`, `CNQ`, `TRP`, `MFC`, `STN`, `LSPD`, … (use the current TSX 60 list). Then in `application/cli.py` add:
```python
def _get_backtest_universe(market: str) -> list[str]:
    """US S&P+NDX (existing) plus TSX 60 with .TO suffix for the backtest."""
    us = _get_ticker_universe(_build_dependencies(market)["config"])
    tsx_path = Path(__file__).parent.parent / "config" / "tickers" / "tsx60.txt"
    tsx: list[str] = []
    if tsx_path.exists():
        for line in tsx_path.read_text().splitlines():
            s = line.strip()
            if s and not s.startswith("#"):
                tsx.append(f"{s}.TO")
    # de-dup, preserve order
    seen: set[str] = set()
    out: list[str] = []
    for t in [*us, *tsx]:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out
```
(READ `application/cli.py` first to confirm `_get_ticker_universe`, `_build_dependencies`, and the `Path` import exist; reuse them.)

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_opportunity_cli.py -k backtest_universe -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add config/tickers/tsx60.txt application/cli.py tests/test_opportunity_cli.py
git commit -m "feat: TSX60 ticker config + _get_backtest_universe (.TO suffix)"
```

---

### Task 9: `validate-momentum-discipline` CLI

**Files:**
- Modify: `application/cli.py`
- Test: `tests/test_opportunity_cli.py`

- [ ] **Step 1: Write the failing test**

```python
def test_validate_momentum_discipline_runs(monkeypatch):
    from click.testing import CliRunner
    from application.cli import cli
    import application.cli as climod

    class _UC:
        def __init__(self, *a, **k): pass
        def execute(self, universe, start, end):
            return {
                "strategy": {"sharpe": 1.1, "max_drawdown": 0.2, "cagr": 0.12,
                             "sortino": 1.3, "equity": [1.0, 1.05, 1.1]},
                "buy_hold": {"sharpe": 0.6, "max_drawdown": 0.5, "cagr": 0.10,
                             "sortino": 0.7, "equity": [1.0, 0.95, 1.0]},
                "spy": {"sharpe": 0.7, "max_drawdown": 0.34, "cagr": 0.11,
                        "sortino": 0.8, "equity": [1.0, 0.98, 1.05]},
            }
        def verdict(self, report, sharpe_diff_ci_low):
            return {"decision": "PROCEED", "drawdown_reduction": 0.6,
                    "sharpe_diff_ci_low": sharpe_diff_ci_low,
                    "beats_sharpe": True, "cuts_drawdown": True}
    monkeypatch.setattr(climod, "MomentumExitBacktestUseCase", _UC, raising=False)
    monkeypatch.setattr(climod, "_get_backtest_universe", lambda m: ["AAPL", "MSFT"], raising=False)

    runner = CliRunner()
    result = runner.invoke(cli, ["validate-momentum-discipline", "--limit", "2", "--quick"])
    assert result.exit_code == 0, result.output
    assert "PROCEED" in result.output or "KILL" in result.output
    assert "sharpe" in result.output.lower()
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_opportunity_cli.py -k validate_momentum -v`
Expected: FAIL (no such command)

- [ ] **Step 3: Implement**

Add a module-level import `from application.momentum_exit_backtest import MomentumExitBacktestUseCase` (so monkeypatch works), then the command. It wires a live price provider over `load_price_series` (daily closes), computes the bootstrap CI of the paired daily Sharpe-difference via `moving_block_bootstrap`, runs `execute` + `verdict`, prints a metrics table + verdict, writes `data/reports/momentum_discipline_<date>.json` (use `os.makedirs(..., exist_ok=True)`):
```python
@cli.command("validate-momentum-discipline")
@click.option("--market", default="us")
@click.option("--start", default="2018-01-01", show_default=True)
@click.option("--end", default="2026-06-01", show_default=True)
@click.option("--limit", default=0, type=int, help="Cap universe (0 = all)")
@click.option("--quick", is_flag=True, help="Smaller universe sample for a fast dry run")
def validate_momentum_discipline(market, start, end, limit, quick):
    """Pre-registered momentum + trailing-exit backtest (spec 2026-06-07). PROCEED/KILL."""
    from datetime import datetime, timezone
    import json as _json, os
    from application.price_returns import load_price_series
    from application.precision_metrics import moving_block_bootstrap
    from domain.backtest_metrics import daily_returns

    start_dt = datetime.fromisoformat(start)
    end_dt = datetime.fromisoformat(end)
    universe = _get_backtest_universe(market)
    if quick:
        universe = universe[:50]
    if limit:
        universe = universe[:limit]

    _cache: dict[str, list] = {}
    def provider(ticker):
        if ticker not in _cache:
            _cache[ticker] = load_price_series(ticker, start_dt, end_dt)
        return _cache[ticker]

    uc = MomentumExitBacktestUseCase(provider)
    report = uc.execute(universe, start_dt, end_dt)

    # bootstrap CI on the paired daily Sharpe-difference (strategy - buy_hold)
    s_ret = daily_returns(report["strategy"]["equity"])
    b_ret = daily_returns(report["buy_hold"]["equity"])
    n = min(len(s_ret), len(b_ret))
    diff = [s_ret[i] - b_ret[i] for i in range(n)]
    boot = moving_block_bootstrap(diff) if diff else {}
    ci_low = boot.get("ci_low", 0.0)

    v = uc.verdict(report, sharpe_diff_ci_low=ci_low)
    os.makedirs("data/reports", exist_ok=True)
    out = {"report": {k: {m: report[k][m] for m in report[k] if m != "equity"}
                      for k in report}, "verdict": v}
    with open("data/reports/momentum_discipline.json", "w") as f:
        _json.dump(out, f, indent=2, default=str)
    for name in ("strategy", "buy_hold", "spy"):
        if name in report:
            r = report[name]
            click.echo(f"{name:10} sharpe={r['sharpe']:.2f} cagr={r['cagr']:.2%} "
                       f"maxDD={r['max_drawdown']:.2%}")
    click.echo(f"VERDICT: {v['decision']}  (drawdown_reduction={v['drawdown_reduction']:.0%}, "
               f"sharpe_diff_ci_low={v['sharpe_diff_ci_low']:.4f})")
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_opportunity_cli.py -k validate_momentum -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add application/cli.py tests/test_opportunity_cli.py
git commit -m "feat: validate-momentum-discipline CLI (backtest + verdict + report)"
```

---

## Phase 1E — Personal holdings verdict

### Task 10: `PortfolioVerdictUseCase` — per-holding verdict

**Files:**
- Create: `application/portfolio_verdict.py`
- Test: `tests/test_portfolio_verdict.py`

- [ ] **Step 1: Write the failing test**

```python
from datetime import datetime, timedelta, timezone

def _series(start, vals):
    return [(start + timedelta(days=i), float(v)) for i, v in enumerate(vals)]

def test_verdict_exit_for_broken_trend():
    from application.portfolio_verdict import PortfolioVerdictUseCase
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    # 250 days rising to 350 then falling below the 200d MA -> EXIT
    vals = list(range(100, 350)) + list(range(350, 250, -1))
    uc = PortfolioVerdictUseCase(price_provider=lambda t: _series(start, vals))
    row = uc.verdict_for("RIVN")
    assert row["verdict"] in {"EXIT", "TRIM"}
    assert row["trend_intact"] is False

def test_verdict_hold_for_intact_uptrend():
    from application.portfolio_verdict import PortfolioVerdictUseCase
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    vals = list(range(100, 400))  # steady uptrend
    uc = PortfolioVerdictUseCase(price_provider=lambda t: _series(start, vals))
    row = uc.verdict_for("MU")
    assert row["verdict"] == "HOLD"
    assert row["trend_intact"] is True
    assert row["trailing_stop"] is not None
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_portfolio_verdict.py -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
"""Apply the validated trend/exit rules to current holdings (application, not
validation — see spec). Output is decision-support, not a forecast."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from domain.trend_rules import above_trend, atr, chandelier_stop, sma

PriceProvider = Callable[[str], list[tuple[datetime, float]]]


class PortfolioVerdictUseCase:
    def __init__(
        self, price_provider: PriceProvider, trend_window: int = 200,
        atr_window: int = 22, atr_mult: float = 3.0,
    ) -> None:
        self._prices = price_provider
        self._trend_window = trend_window
        self._atr_window = atr_window
        self._atr_mult = atr_mult

    def verdict_for(self, ticker: str) -> dict[str, Any]:
        series = self._prices(ticker)
        closes = [p for _, p in series]
        if len(closes) < self._trend_window:
            return {"ticker": ticker, "verdict": "INSUFFICIENT_DATA",
                    "trend_intact": False, "trailing_stop": None}
        price = closes[-1]
        trend = above_trend(price, sma(closes, self._trend_window))
        # ATR uses closes as a proxy for highs/lows when only closes are available
        atr_v = atr(closes, closes, closes, self._atr_window)
        highest = max(closes[-self._trend_window:])
        stop = chandelier_stop(highest, atr_v, self._atr_mult) if atr_v else None
        if not trend:
            verdict = "EXIT"
        elif stop is not None and price <= stop:
            verdict = "TRIM"
        else:
            verdict = "HOLD"
        return {
            "ticker": ticker, "price": price, "verdict": verdict,
            "trend_intact": trend, "trailing_stop": stop,
            "why": _why(verdict, trend, price, stop),
        }


def _why(verdict: str, trend: bool, price: float, stop: float | None) -> str:
    if verdict == "EXIT":
        return "Below 200-day trend — discipline says exit, don't anchor."
    if verdict == "TRIM":
        return "In trend but breached trailing stop — trim/tighten."
    return f"Trend intact; ride it, trailing stop at {stop:.2f}." if stop else "Trend intact."
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_portfolio_verdict.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add application/portfolio_verdict.py tests/test_portfolio_verdict.py
git commit -m "feat: PortfolioVerdictUseCase — per-holding hold/trim/exit verdict"
```

---

### Task 11: `portfolio-verdict` CLI (reads local gitignored holdings)

**Files:**
- Modify: `application/cli.py`
- Test: `tests/test_opportunity_cli.py`

- [ ] **Step 1: Write the failing test**

```python
def test_portfolio_verdict_cli(monkeypatch, tmp_path):
    from click.testing import CliRunner
    from application.cli import cli
    import application.cli as climod

    holdings = tmp_path / "holdings.csv"
    holdings.write_text("ticker,shares\nMU,25\nRIVN,80\n")

    class _UC:
        def __init__(self, *a, **k): pass
        def verdict_for(self, ticker):
            return {"ticker": ticker, "price": 100.0,
                    "verdict": "HOLD" if ticker == "MU" else "EXIT",
                    "trend_intact": ticker == "MU", "trailing_stop": 90.0,
                    "why": "test"}
    monkeypatch.setattr(climod, "PortfolioVerdictUseCase", _UC, raising=False)

    runner = CliRunner()
    result = runner.invoke(cli, ["portfolio-verdict", "--holdings", str(holdings)])
    assert result.exit_code == 0, result.output
    assert "MU" in result.output and "HOLD" in result.output
    assert "RIVN" in result.output and "EXIT" in result.output
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_opportunity_cli.py -k portfolio_verdict -v`
Expected: FAIL (no such command)

- [ ] **Step 3: Implement**

Module-level import `from application.portfolio_verdict import PortfolioVerdictUseCase`, then:
```python
@cli.command("portfolio-verdict")
@click.option("--holdings", default="data/personal/holdings.csv", show_default=True,
              help="Local CSV (ticker,shares[,entry]) — gitignored, never committed")
@click.option("--market", default="us")
def portfolio_verdict(holdings, market):
    """Apply validated trend/exit rules to your current holdings (decision-support)."""
    import csv, os
    from datetime import datetime, timezone
    from application.price_returns import load_price_series

    if not os.path.exists(holdings):
        click.echo(f"No holdings file at {holdings}. Create it (ticker,shares) — it is gitignored.")
        return
    start_dt = datetime(2018, 1, 1, tzinfo=timezone.utc)
    end_dt = datetime.fromisoformat("2026-06-01")
    def provider(ticker):
        return load_price_series(ticker, start_dt, end_dt)
    uc = PortfolioVerdictUseCase(provider)
    with open(holdings) as f:
        rows = [r for r in csv.DictReader(f) if r.get("ticker")]
    click.echo(f"{'TICKER':8} {'VERDICT':16} {'TREND':6} STOP / WHY")
    for r in rows:
        v = uc.verdict_for(r["ticker"].strip().upper())
        stop = v.get("trailing_stop")
        stop_s = f"{stop:.2f}" if stop else "-"
        click.echo(f"{v['ticker']:8} {v['verdict']:16} "
                   f"{'yes' if v['trend_intact'] else 'no':6} {stop_s}  {v.get('why','')}")
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_opportunity_cli.py -k portfolio_verdict -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add application/cli.py tests/test_opportunity_cli.py
git commit -m "feat: portfolio-verdict CLI (local holdings hold/trim/exit table)"
```

---

## Phase 1F — Run it + verdict (live, after code green)

### Task 12: Quality gate + live backtest run

**Files:** none (live run; writes `data/reports/`)

- [ ] **Step 1:** `make check` — green before any live step.
- [ ] **Step 2:** Quick dry run: `python -m application.cli validate-momentum-discipline --quick` — confirm it runs end-to-end on ~50 names, prints metrics + verdict.
- [ ] **Step 3:** Full run: `python -m application.cli validate-momentum-discipline > data/reports/_momentum_validation.log 2>&1` (caffeinate-wrapped; yfinance price loads for the full US+TSX universe take time). Read the verdict.
- [ ] **Step 4:** Record the dated report: `cp data/reports/momentum_discipline.json data/reports/momentum_discipline_$(date +%Y%m%d).json` and `git add` + commit it.
- [ ] **Step 5:** The PROCEED/KILL verdict is the Phase-1 result. **STOP here and bring it to the user** — Phase 2 (screener/daily feed) is gated on PROCEED and is a separate plan. (This is where the next session's effort flips back to max for interpretation.)

---

## Self-Review (completed by plan author)

**Spec coverage:** pre-registered rules → T1-T3 (trend/atr/chandelier/momentum) + T6 (applied in sim); metrics + locked gate → T4-T5 + T7 (Sharpe-diff CI + ≥30% DD reduction); broad US+TSX universe → T8; backtest CLI + report → T9; personal holdings verdict (application≠validation) → T10-T11; live run + PROCEED/KILL → T12. Phase 2 explicitly excluded (gated on PROCEED). Honesty constraints (frozen params, no tuning, privacy/gitignore) carried in conventions + T11 (local holdings).

**Placeholder scan:** the only non-literal step is T6's simulation loop, given as a precise commented skeleton + a behavioral test that pins the required property (strategy cuts drawdown vs buy-hold) — acceptable because the exact loop is mechanical and review-gated; all other steps have complete code.

**Type consistency:** `sma/atr/chandelier_stop/momentum_12_1/top_fraction_threshold` (T1-3) consumed in T6/T10 with matching signatures; `MomentumExitBacktestUseCase(price_provider).execute(universe,start,end)->{strategy,buy_hold,spy}` + `.verdict(report, sharpe_diff_ci_low)` (T6-7) consumed in T9; `PortfolioVerdictUseCase(price_provider).verdict_for(ticker)` (T10) consumed in T11; `moving_block_bootstrap` returns `ci_low` (confirmed in precision_metrics). Frozen params identical across T6/T10 (200, 22, 3.0, 1/3).
