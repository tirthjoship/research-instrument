# Macro-Beta Scrubber Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the 66-name book's hidden macro factor bets — Ridge-regress each holding's returns on SPY/TLT/UUP/XLE, aggregate to a dollar-weighted book net-beta + systematic-vs-idiosyncratic variance split, surface flags in the weekly brief, and prune the stale screen universe.

**Architecture:** Hexagonal. New `MacroBetaEstimatorPort` (domain) implemented by `RidgeMacroBetaEstimator` (adapter, only sklearn touchpoint). Pure `domain/macro_beta.py` does returns/alignment/aggregation/flag-policy (stdlib only). `MacroBetaUseCase` (application) orchestrates price fetch → returns → estimate → aggregate. Folds into the existing `WeeklyBriefUseCase` via an injected `macro_fn` (mirrors `cluster_peers_fn`), rendered by the existing `to_markdown`/`to_stdout_masked` formatters.

**Tech Stack:** Python 3.12, sklearn `Ridge`, numpy, click CLI, pytest + Hypothesis, mypy strict, black.

**Spec:** `docs/superpowers/specs/2026-06-09-macro-beta-scrubber-design.md`
**Branch:** `feat/macro-beta-scrubber` (already created off develop).

**Non-negotiables (AGENTS.md / CLAUDE.md):** domain/ imports only stdlib (typing/dataclasses/datetime/enum) — NO sklearn/numpy in domain. Tests use small fixtures, never real yfinance. No `--no-verify`. Conventional commits. Pre-commit (black/isort/mypy/ruff/gitleaks) must pass each commit.

**Methodology locks:** regress daily SIMPLE returns (de-meaned), NOT price levels. Fit `sklearn.Ridge` on RAW returns with NO StandardScaler (so `.coef_` IS the raw beta). Factors SPY/TLT/UUP/XLE. Headline window 252 trading days, drift window 63. Thresholds are UN-VALIDATED heuristics (surfacing dials), labeled as such.

---

## File Structure

| File | Create/Modify | Responsibility |
|---|---|---|
| `domain/models.py` | Modify (append) | `MacroFactorBeta`, `HoldingMacroExposure`, `MacroBetaFlag`, `BookMacroExposure` frozen dataclasses |
| `domain/macro_beta.py` | Create | pure: `daily_returns`, `align_returns`, `book_return_series`, `net_beta`, `build_flags`, `aggregate_macro_exposure` |
| `domain/ports.py` | Modify | `MacroBetaEstimatorPort` Protocol |
| `adapters/ml/macro_beta_analyzer.py` | Create | `RidgeMacroBetaEstimator` (Ridge on raw returns, reads `.coef_`, in-sample R²) |
| `application/macro_beta_use_case.py` | Create | `MacroBetaUseCase` — fetch→returns→estimate→aggregate |
| `domain/brief.py` | Modify | add `macro` field to `WeeklyBrief`; param to `assemble_brief`; render in `to_markdown`/`to_stdout_masked` |
| `application/weekly_brief_use_case.py` | Modify | inject `macro_fn`, compute, pass to `assemble_brief` |
| `application/cli.py` | Modify `_build_weekly_brief` (L2763) | wire estimator + use case + `macro_fn` |
| `config/markets/us.yaml` | Modify (append) | `macro_beta:` config block |
| `config/tickers/{sp500,nasdaq100,tsx60}.txt` | Modify | prune delisted tickers |
| `tests/test_macro_beta.py` | Create | pure domain unit + Hypothesis |
| `tests/test_macro_beta_analyzer.py` | Create | adapter synthetic-recovery |
| `tests/test_macro_beta_use_case.py` | Create | use case w/ fake price provider |
| `tests/test_brief.py` | Modify (or `tests/test_weekly_brief*.py`) | macro pillar renders |

---

## Task 1: Domain models

**Files:**
- Modify: `domain/models.py` (append at end)
- Test: `tests/test_macro_beta.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_macro_beta.py
from domain.models import (
    BookMacroExposure,
    HoldingMacroExposure,
    MacroBetaFlag,
    MacroFactorBeta,
)


def test_macro_factor_beta_drift_field():
    b = MacroFactorBeta(factor="TLT", beta_headline=0.4, beta_recent=0.7, drift=0.3)
    assert b.factor == "TLT"
    assert b.drift == 0.3


def test_book_macro_exposure_holds_pieces():
    hb = HoldingMacroExposure(
        ticker="NVDA",
        weight=0.1,
        betas=(MacroFactorBeta("SPY", 1.2, 1.3, 0.1),),
        r_squared=0.55,
    )
    flag = MacroBetaFlag(
        kind="SYSTEMATIC_DOMINANT",
        factor=None,
        message="x",
        value=0.7,
        threshold=0.6,
    )
    book = BookMacroExposure(
        as_of="2026-06-09",
        factors=("SPY", "TLT", "UUP", "XLE"),
        net_beta_by_factor={"SPY": 0.9, "TLT": -0.2, "UUP": 0.1, "XLE": 0.3},
        systematic_share=0.7,
        idiosyncratic_share=0.3,
        dominant_factor="SPY",
        flags=(flag,),
        holdings=(hb,),
        coverage_holdings=1,
        total_holdings=1,
        coverage_value_frac=1.0,
    )
    assert book.dominant_factor == "SPY"
    assert book.holdings[0].ticker == "NVDA"
    assert book.flags[0].kind == "SYSTEMATIC_DOMINANT"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_macro_beta.py -v`
Expected: FAIL — `ImportError: cannot import name 'MacroFactorBeta'`.

- [ ] **Step 3: Append the models to `domain/models.py`**

```python
# --- Macro-beta scrubber (Unit A, ADR-052) -------------------------------


@dataclass(frozen=True)
class MacroFactorBeta:
    """Per-factor sensitivity for one holding or the book.

    beta_headline: 252-day window. beta_recent: 63-day window.
    drift = beta_recent - beta_headline (positive = exposure rising).
    """

    factor: str
    beta_headline: float
    beta_recent: float
    drift: float


@dataclass(frozen=True)
class HoldingMacroExposure:
    """One holding's macro betas plus its systematic share (headline R^2)."""

    ticker: str
    weight: float  # fraction of covered book market value
    betas: tuple[MacroFactorBeta, ...]
    r_squared: float


@dataclass(frozen=True)
class MacroBetaFlag:
    """A surfaced CRO flag. value/threshold are heuristic dials, not edges."""

    kind: str  # "SYSTEMATIC_DOMINANT" | "FACTOR_DOMINANCE" | "DRIFT"
    factor: str | None
    message: str
    value: float
    threshold: float


@dataclass(frozen=True)
class BookMacroExposure:
    """Book-level macro exposure summary for the weekly brief."""

    as_of: str
    factors: tuple[str, ...]
    net_beta_by_factor: dict[str, float]  # dollar-weighted Sum w_i * beta_i
    systematic_share: float  # book-level R^2 (macro-explained variance)
    idiosyncratic_share: float  # 1 - systematic_share
    dominant_factor: str | None
    flags: tuple[MacroBetaFlag, ...]
    holdings: tuple[HoldingMacroExposure, ...]
    coverage_holdings: int
    total_holdings: int
    coverage_value_frac: float
```

Confirm `from dataclasses import dataclass` already imported at top of `domain/models.py` (it is — existing dataclasses present). No new imports needed.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_macro_beta.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add domain/models.py tests/test_macro_beta.py
git commit -m "feat: macro-beta domain models (Unit A, ADR-052)"
```

---

## Task 2: Pure returns + alignment helpers

**Files:**
- Create: `domain/macro_beta.py`
- Test: `tests/test_macro_beta.py` (append)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_macro_beta.py  (append)
from datetime import datetime

from domain.macro_beta import align_returns, book_return_series, daily_returns


def _d(day: int) -> datetime:
    return datetime(2026, 1, day)


def test_daily_returns_simple():
    series = [(_d(1), 100.0), (_d(2), 110.0), (_d(3), 99.0)]
    out = daily_returns(series)
    assert out[0][0] == _d(2)
    assert abs(out[0][1] - 0.10) < 1e-9
    assert abs(out[1][1] - (-0.10)) < 1e-9


def test_daily_returns_skips_zero_prev():
    series = [(_d(1), 0.0), (_d(2), 100.0), (_d(3), 110.0)]
    out = daily_returns(series)
    # the 0->100 step is dropped (undefined return); only 100->110 survives.
    assert len(out) == 1
    assert abs(out[0][1] - 0.10) < 1e-9


def test_align_returns_inner_join():
    y = [(_d(2), 0.01), (_d(3), 0.02), (_d(4), 0.03)]
    factors = {
        "SPY": [(_d(2), 0.005), (_d(3), 0.006)],  # missing _d(4)
        "TLT": [(_d(3), -0.01), (_d(4), -0.02)],  # missing _d(2)
    }
    y_out, f_out = align_returns(y, factors)
    # only _d(3) is common to y, SPY, TLT.
    assert y_out == [0.02]
    assert f_out["SPY"] == [0.006]
    assert f_out["TLT"] == [-0.01]


def test_book_return_series_renormalizes_per_date():
    # date 2: both A,B present -> weighted by 0.5/0.5; date 3: only A present -> A gets 1.0
    holding_returns = {
        "A": [(_d(2), 0.10), (_d(3), 0.20)],
        "B": [(_d(2), 0.30)],
    }
    weights = {"A": 0.5, "B": 0.5}
    out = book_return_series(holding_returns, weights, [_d(2), _d(3)])
    assert abs(out[0][1] - 0.20) < 1e-9  # 0.5*0.10 + 0.5*0.30
    assert abs(out[1][1] - 0.20) < 1e-9  # only A -> renormalized weight 1.0
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_macro_beta.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'domain.macro_beta'`.

- [ ] **Step 3: Create `domain/macro_beta.py` with the helpers**

```python
"""Pure macro-beta math (no IO, stdlib only).

Returns/alignment/book-aggregation/flag-policy for the macro-beta scrubber
(Unit A, ADR-052). The Ridge fit itself lives in the adapter; this module only
does deterministic arithmetic so it is fully unit- and property-testable.
"""

from __future__ import annotations

from datetime import datetime

from domain.models import (
    BookMacroExposure,
    HoldingMacroExposure,
    MacroBetaFlag,
    MacroFactorBeta,
)


def daily_returns(
    series: list[tuple[datetime, float]],
) -> list[tuple[datetime, float]]:
    """Simple daily returns between consecutive closes. `series` ascending by date.

    A step is dropped when the previous close is 0 (undefined return). The
    returned date is the *later* date of each consecutive pair.
    """
    out: list[tuple[datetime, float]] = []
    for (_, prev), (d, cur) in zip(series, series[1:]):
        if prev == 0:
            continue
        out.append((d, (cur - prev) / prev))
    return out


def align_returns(
    y_returns: list[tuple[datetime, float]],
    factor_returns: dict[str, list[tuple[datetime, float]]],
) -> tuple[list[float], dict[str, list[float]]]:
    """Inner-join y and all factor return series on common dates (ascending).

    Returns (y_aligned, {factor: aligned}) over dates present in EVERY series.
    """
    common: set[datetime] = {d for d, _ in y_returns}
    for series in factor_returns.values():
        common &= {d for d, _ in series}
    dates = sorted(common)
    y_map = dict(y_returns)
    f_maps = {f: dict(s) for f, s in factor_returns.items()}
    y_out = [y_map[d] for d in dates]
    f_out = {f: [f_maps[f][d] for d in dates] for f in factor_returns}
    return y_out, f_out


def book_return_series(
    holding_returns: dict[str, list[tuple[datetime, float]]],
    weights: dict[str, float],
    dates: list[datetime],
) -> list[tuple[datetime, float]]:
    """Dollar-weighted book return per date over `dates`.

    On each date, weights are renormalized over holdings that have a return that
    day (ragged histories handled honestly — a missing holding does not pin the
    book return to 0). Dates with no holdings present are skipped.
    """
    maps = {t: dict(s) for t, s in holding_returns.items()}
    out: list[tuple[datetime, float]] = []
    for d in dates:
        present = [(t, weights.get(t, 0.0)) for t in maps if d in maps[t]]
        wsum = sum(w for _, w in present)
        if wsum <= 0:
            continue
        r = sum((w / wsum) * maps[t][d] for t, w in present)
        out.append((d, r))
    return out
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_macro_beta.py -v`
Expected: PASS (all Task 1 + Task 2 tests).

- [ ] **Step 5: Commit**

```bash
git add domain/macro_beta.py tests/test_macro_beta.py
git commit -m "feat: pure returns + alignment helpers for macro-beta"
```

---

## Task 3: Pure net-beta + flag policy + aggregator

**Files:**
- Modify: `domain/macro_beta.py` (append)
- Test: `tests/test_macro_beta.py` (append) — includes Hypothesis invariants

- [ ] **Step 1: Write the failing tests (unit + property)**

```python
# tests/test_macro_beta.py  (append)
from hypothesis import given
from hypothesis import strategies as st

from domain.macro_beta import aggregate_macro_exposure, build_flags, net_beta
from domain.models import HoldingMacroExposure, MacroFactorBeta


def _hme(ticker, weight, betas, r2):
    return HoldingMacroExposure(
        ticker=ticker,
        weight=weight,
        betas=tuple(MacroFactorBeta(f, bh, br, br - bh) for f, bh, br in betas),
        r_squared=r2,
    )


def test_net_beta_dollar_weighted():
    holdings = [
        _hme("A", 0.5, [("SPY", 1.0, 1.0), ("TLT", -0.4, -0.4)], 0.6),
        _hme("B", 0.5, [("SPY", 0.6, 0.6), ("TLT", 0.2, 0.2)], 0.4),
    ]
    nb = net_beta(holdings, ("SPY", "TLT"))
    assert abs(nb["SPY"] - 0.8) < 1e-9  # 0.5*1.0 + 0.5*0.6
    assert abs(nb["TLT"] - (-0.1)) < 1e-9  # 0.5*-0.4 + 0.5*0.2


def test_build_flags_systematic_dominant():
    flags = build_flags(
        net_beta_by_factor={"SPY": 0.2, "TLT": 0.0},
        systematic_share=0.72,
        per_holding=[],
        factor_move_std={"SPY": 0.01, "TLT": 0.01},
        book_drift_by_factor={"SPY": 0.0, "TLT": 0.0},
        beta_headline_by_factor={"SPY": 0.2, "TLT": 0.0},
        systematic_share_threshold=0.60,
        factor_dominance_threshold=0.25,
        drift_threshold=0.50,
    )
    kinds = {f.kind for f in flags}
    assert "SYSTEMATIC_DOMINANT" in kinds


def test_build_flags_factor_dominance_and_drift():
    flags = build_flags(
        net_beta_by_factor={"TLT": 2.0},
        systematic_share=0.30,
        per_holding=[],
        factor_move_std={"TLT": 0.20},  # |2.0 * 0.20| = 0.40 > 0.25
        book_drift_by_factor={"TLT": 0.6},
        beta_headline_by_factor={"TLT": 1.0},  # |0.6/1.0| = 0.6 > 0.50
        systematic_share_threshold=0.60,
        factor_dominance_threshold=0.25,
        drift_threshold=0.50,
    )
    kinds = {f.kind for f in flags}
    assert "FACTOR_DOMINANCE" in kinds
    assert "DRIFT" in kinds


def test_aggregate_empty_abstains():
    book = aggregate_macro_exposure(
        as_of="2026-06-09",
        factors=("SPY", "TLT", "UUP", "XLE"),
        per_holding=[],
        systematic_share=0.0,
        factor_move_std={},
        book_drift_by_factor={},
        beta_headline_by_factor={},
        total_holdings=5,
        coverage_value_frac=0.0,
        thresholds={
            "systematic_share_threshold": 0.60,
            "factor_dominance_threshold": 0.25,
            "drift_threshold": 0.50,
        },
    )
    assert book.coverage_holdings == 0
    assert book.flags == ()
    assert book.dominant_factor is None


@given(
    w=st.floats(min_value=0.01, max_value=0.99),
    b1=st.floats(min_value=-3, max_value=3),
    b2=st.floats(min_value=-3, max_value=3),
)
def test_net_beta_equals_weighted_sum_property(w, b1, b2):
    holdings = [
        _hme("A", w, [("SPY", b1, b1)], 0.5),
        _hme("B", 1 - w, [("SPY", b2, b2)], 0.5),
    ]
    nb = net_beta(holdings, ("SPY",))
    assert abs(nb["SPY"] - (w * b1 + (1 - w) * b2)) < 1e-6


@given(s=st.floats(min_value=0.0, max_value=1.0))
def test_systematic_idiosyncratic_sum_to_one(s):
    book = aggregate_macro_exposure(
        as_of="2026-06-09",
        factors=("SPY",),
        per_holding=[_hme("A", 1.0, [("SPY", 1.0, 1.0)], s)],
        systematic_share=s,
        factor_move_std={"SPY": 0.01},
        book_drift_by_factor={"SPY": 0.0},
        beta_headline_by_factor={"SPY": 1.0},
        total_holdings=1,
        coverage_value_frac=1.0,
        thresholds={
            "systematic_share_threshold": 0.60,
            "factor_dominance_threshold": 0.25,
            "drift_threshold": 0.50,
        },
    )
    assert abs(book.systematic_share + book.idiosyncratic_share - 1.0) < 1e-9
    assert 0.0 <= book.systematic_share <= 1.0
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_macro_beta.py -v`
Expected: FAIL — `ImportError: cannot import name 'aggregate_macro_exposure'`.

- [ ] **Step 3: Append to `domain/macro_beta.py`**

```python
def net_beta(
    per_holding: list[HoldingMacroExposure], factors: tuple[str, ...]
) -> dict[str, float]:
    """Dollar-weighted net beta per factor: Sum_i weight_i * beta_headline_i,k."""
    out: dict[str, float] = {f: 0.0 for f in factors}
    for h in per_holding:
        bmap = {b.factor: b.beta_headline for b in h.betas}
        for f in factors:
            out[f] += h.weight * bmap.get(f, 0.0)
    return out


def build_flags(
    *,
    net_beta_by_factor: dict[str, float],
    systematic_share: float,
    per_holding: list[HoldingMacroExposure],
    factor_move_std: dict[str, float],
    book_drift_by_factor: dict[str, float],
    beta_headline_by_factor: dict[str, float],
    systematic_share_threshold: float,
    factor_dominance_threshold: float,
    drift_threshold: float,
) -> tuple[MacroBetaFlag, ...]:
    """Apply the heuristic surfacing policy. Thresholds are dials, not edges."""
    flags: list[MacroBetaFlag] = []

    if systematic_share > systematic_share_threshold:
        flags.append(
            MacroBetaFlag(
                kind="SYSTEMATIC_DOMINANT",
                factor=None,
                message=(
                    f"{systematic_share:.0%} of book variance is macro-explained — "
                    f"these are a few factor bets, not independent ideas"
                ),
                value=systematic_share,
                threshold=systematic_share_threshold,
            )
        )

    for f, beta in net_beta_by_factor.items():
        implied = abs(beta) * factor_move_std.get(f, 0.0)
        if implied > factor_dominance_threshold:
            flags.append(
                MacroBetaFlag(
                    kind="FACTOR_DOMINANCE",
                    factor=f,
                    message=(
                        f"net {f} exposure dominates: a 1-sigma {f} move shifts the "
                        f"book ~{implied:.0%}"
                    ),
                    value=implied,
                    threshold=factor_dominance_threshold,
                )
            )

    for f, drift in book_drift_by_factor.items():
        headline = beta_headline_by_factor.get(f, 0.0)
        denom = max(abs(headline), 1e-6)
        ratio = abs(drift) / denom
        if ratio > drift_threshold:
            flags.append(
                MacroBetaFlag(
                    kind="DRIFT",
                    factor=f,
                    message=(
                        f"{f} exposure shifting fast — 63-day beta diverges "
                        f"{ratio:.0%} from the 1-year beta"
                    ),
                    value=ratio,
                    threshold=drift_threshold,
                )
            )

    return tuple(flags)


def aggregate_macro_exposure(
    *,
    as_of: str,
    factors: tuple[str, ...],
    per_holding: list[HoldingMacroExposure],
    systematic_share: float,
    factor_move_std: dict[str, float],
    book_drift_by_factor: dict[str, float],
    beta_headline_by_factor: dict[str, float],
    total_holdings: int,
    coverage_value_frac: float,
    thresholds: dict[str, float],
) -> BookMacroExposure:
    """Assemble the book-level exposure summary from pure pieces."""
    nb = net_beta(per_holding, factors)
    share = min(max(systematic_share, 0.0), 1.0)
    dominant = (
        max(nb, key=lambda f: abs(nb[f])) if per_holding and nb else None
    )
    flags = build_flags(
        net_beta_by_factor=nb,
        systematic_share=share,
        per_holding=per_holding,
        factor_move_std=factor_move_std,
        book_drift_by_factor=book_drift_by_factor,
        beta_headline_by_factor=beta_headline_by_factor,
        systematic_share_threshold=thresholds["systematic_share_threshold"],
        factor_dominance_threshold=thresholds["factor_dominance_threshold"],
        drift_threshold=thresholds["drift_threshold"],
    )
    return BookMacroExposure(
        as_of=as_of,
        factors=factors,
        net_beta_by_factor=nb,
        systematic_share=share,
        idiosyncratic_share=1.0 - share,
        dominant_factor=dominant,
        flags=flags,
        holdings=tuple(per_holding),
        coverage_holdings=len(per_holding),
        total_holdings=total_holdings,
        coverage_value_frac=coverage_value_frac,
    )
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_macro_beta.py -v`
Expected: PASS (all unit + Hypothesis property tests).

- [ ] **Step 5: Commit**

```bash
git add domain/macro_beta.py tests/test_macro_beta.py
git commit -m "feat: pure net-beta aggregation + heuristic flag policy"
```

---

## Task 4: MacroBetaEstimatorPort

**Files:**
- Modify: `domain/ports.py`
- Test: covered indirectly (Protocol — no behavior). Add a structural test.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_macro_beta.py  (append)
def test_estimator_port_is_protocol():
    from domain.ports import MacroBetaEstimatorPort

    class _Fake:
        def estimate(self, y_returns, factor_returns, alpha):
            return ({k: 0.0 for k in factor_returns}, 0.0)

    f: MacroBetaEstimatorPort = _Fake()
    betas, r2 = f.estimate([0.1], {"SPY": [0.1]}, 0.2)
    assert r2 == 0.0
    assert betas == {"SPY": 0.0}
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_macro_beta.py::test_estimator_port_is_protocol -v`
Expected: FAIL — `ImportError: cannot import name 'MacroBetaEstimatorPort'`.

- [ ] **Step 3: Add the port to `domain/ports.py`**

Append a new Protocol class (follow the existing `StockPredictorPort` style at L73):

```python
class MacroBetaEstimatorPort(Protocol):
    """Port: estimate factor betas of a return series via shrinkage regression.

    Returns (beta_by_factor, r_squared). Implementations fit on RAW de-meaned
    daily returns (no scaling) so coefficients are raw, dollar-interpretable betas.
    """

    def estimate(
        self,
        y_returns: list[float],
        factor_returns: dict[str, list[float]],
        alpha: float,
    ) -> tuple[dict[str, float], float]: ...
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_macro_beta.py::test_estimator_port_is_protocol -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add domain/ports.py tests/test_macro_beta.py
git commit -m "feat: MacroBetaEstimatorPort protocol"
```

---

## Task 5: RidgeMacroBetaEstimator adapter

**Files:**
- Create: `adapters/ml/macro_beta_analyzer.py`
- Test: `tests/test_macro_beta_analyzer.py` (create)

- [ ] **Step 1: Write the failing tests (synthetic recovery + degenerate)**

```python
# tests/test_macro_beta_analyzer.py
import numpy as np

from adapters.ml.macro_beta_analyzer import RidgeMacroBetaEstimator


def test_recovers_known_betas():
    rng = np.random.default_rng(0)
    n = 400
    spy = rng.normal(0, 0.01, n)
    tlt = rng.normal(0, 0.01, n)
    # holding = 0.8*SPY - 0.3*TLT + small noise
    y = 0.8 * spy - 0.3 * tlt + rng.normal(0, 0.0005, n)
    est = RidgeMacroBetaEstimator(alpha=0.05)
    betas, r2 = est.estimate(
        list(y), {"SPY": list(spy), "TLT": list(tlt)}, alpha=0.05
    )
    assert abs(betas["SPY"] - 0.8) < 0.1
    assert abs(betas["TLT"] - (-0.3)) < 0.1
    assert r2 > 0.8


def test_degenerate_constant_y_no_crash():
    est = RidgeMacroBetaEstimator()
    betas, r2 = est.estimate(
        [0.0] * 50, {"SPY": [0.01] * 50, "TLT": [0.0] * 50}, alpha=0.2
    )
    assert set(betas) == {"SPY", "TLT"}
    assert np.isfinite(r2)


def test_too_few_points_returns_zeros():
    est = RidgeMacroBetaEstimator()
    betas, r2 = est.estimate([0.01], {"SPY": [0.01]}, alpha=0.2)
    assert betas == {"SPY": 0.0}
    assert r2 == 0.0
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_macro_beta_analyzer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'adapters.ml.macro_beta_analyzer'`.

- [ ] **Step 3: Create `adapters/ml/macro_beta_analyzer.py`**

```python
"""Ridge factor-beta estimator (macro-beta scrubber, Unit A, ADR-052).

Fits sklearn Ridge on RAW de-meaned daily returns with NO StandardScaler, so
`.coef_` are raw, dollar-interpretable betas. This is deliberately NOT a reuse
of RidgePredictor (which wraps a StandardScaler and never exposes coefficients).
"""

from __future__ import annotations

import numpy as np
from sklearn.linear_model import Ridge

_MIN_POINTS = 20  # below this, betas are noise — abstain to zeros.


class RidgeMacroBetaEstimator:
    """Implements MacroBetaEstimatorPort."""

    def __init__(self, alpha: float = 0.2) -> None:
        self._alpha = alpha

    def estimate(
        self,
        y_returns: list[float],
        factor_returns: dict[str, list[float]],
        alpha: float | None = None,
    ) -> tuple[dict[str, float], float]:
        factors = list(factor_returns)
        zeros = {f: 0.0 for f in factors}
        n = len(y_returns)
        if n < _MIN_POINTS or not factors:
            return zeros, 0.0
        if any(len(factor_returns[f]) != n for f in factors):
            return zeros, 0.0

        y = np.asarray(y_returns, dtype=float)
        x = np.column_stack([np.asarray(factor_returns[f], dtype=float) for f in factors])
        # De-mean so intercept ~ 0 and betas are pure sensitivities.
        y = y - y.mean()
        x = x - x.mean(axis=0, keepdims=True)

        model = Ridge(alpha=alpha if alpha is not None else self._alpha)
        model.fit(x, y)
        betas = {f: float(c) for f, c in zip(factors, model.coef_)}

        ss_tot = float(np.sum(y**2))
        if ss_tot == 0.0:
            return betas, 0.0
        resid = y - model.predict(x)
        r2 = 1.0 - float(np.sum(resid**2)) / ss_tot
        return betas, max(min(r2, 1.0), 0.0)
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_macro_beta_analyzer.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add adapters/ml/macro_beta_analyzer.py tests/test_macro_beta_analyzer.py
git commit -m "feat: RidgeMacroBetaEstimator adapter (raw-return betas)"
```

---

## Task 6: MacroBetaUseCase

**Files:**
- Create: `application/macro_beta_use_case.py`
- Test: `tests/test_macro_beta_use_case.py` (create)

Note: `Holding` here is `application/holdings_reader.Holding` (`ticker`, `shares`, `cost_basis`, `account_type`). The use case only reads `.ticker` and `.shares`.

- [ ] **Step 1: Write the failing tests (fake price provider)**

```python
# tests/test_macro_beta_use_case.py
from datetime import datetime, timedelta

from adapters.ml.macro_beta_analyzer import RidgeMacroBetaEstimator
from application.macro_beta_use_case import MacroBetaUseCase


class _H:
    def __init__(self, ticker, shares):
        self.ticker = ticker
        self.shares = shares


def _trend(base, slope, n, start):
    # n daily closes, deterministic, ascending dates.
    return [(start + timedelta(days=i), base + slope * i) for i in range(n)]


def _provider_factory(series_by_ticker):
    def provider(ticker, start, end):
        return series_by_ticker.get(ticker, [])

    return provider


def test_use_case_builds_book_exposure():
    start = datetime(2025, 1, 1)
    n = 320
    # Factors + two holdings, all with full history.
    spy = _trend(400, 0.5, n, start)
    tlt = _trend(90, -0.05, n, start)
    uup = _trend(28, 0.0, n, start)
    xle = _trend(85, 0.1, n, start)
    a = _trend(100, 0.4, n, start)  # tracks SPY-ish uptrend
    b = _trend(50, -0.02, n, start)
    series = {"SPY": spy, "TLT": tlt, "UUP": uup, "XLE": xle, "A": a, "B": b}

    uc = MacroBetaUseCase(
        price_provider=_provider_factory(series),
        estimator=RidgeMacroBetaEstimator(alpha=0.2),
        factors=["SPY", "TLT", "UUP", "XLE"],
        alpha=0.2,
        headline_window=252,
        drift_window=63,
        thresholds={
            "systematic_share_threshold": 0.60,
            "factor_dominance_threshold": 0.25,
            "drift_threshold": 0.50,
        },
        history_days=400,
    )
    book = uc.execute([_H("A", 10), _H("B", 20)], datetime(2026, 1, 1))
    assert book is not None
    assert book.total_holdings == 2
    assert book.coverage_holdings == 2
    assert set(book.net_beta_by_factor) == {"SPY", "TLT", "UUP", "XLE"}
    assert 0.0 <= book.systematic_share <= 1.0


def test_use_case_excludes_holding_without_history():
    start = datetime(2025, 1, 1)
    n = 320
    series = {
        "SPY": _trend(400, 0.5, n, start),
        "TLT": _trend(90, -0.05, n, start),
        "UUP": _trend(28, 0.0, n, start),
        "XLE": _trend(85, 0.1, n, start),
        "A": _trend(100, 0.4, n, start),
        # "NEW" has no series -> excluded, coverage gap reported.
    }
    uc = MacroBetaUseCase(
        price_provider=_provider_factory(series),
        estimator=RidgeMacroBetaEstimator(alpha=0.2),
        factors=["SPY", "TLT", "UUP", "XLE"],
        alpha=0.2,
        headline_window=252,
        drift_window=63,
        thresholds={
            "systematic_share_threshold": 0.60,
            "factor_dominance_threshold": 0.25,
            "drift_threshold": 0.50,
        },
        history_days=400,
    )
    book = uc.execute([_H("A", 10), _H("NEW", 5)], datetime(2026, 1, 1))
    assert book is not None
    assert book.total_holdings == 2
    assert book.coverage_holdings == 1


def test_use_case_all_factors_fail_returns_none():
    uc = MacroBetaUseCase(
        price_provider=_provider_factory({}),  # nothing resolves
        estimator=RidgeMacroBetaEstimator(alpha=0.2),
        factors=["SPY", "TLT", "UUP", "XLE"],
        alpha=0.2,
        headline_window=252,
        drift_window=63,
        thresholds={
            "systematic_share_threshold": 0.60,
            "factor_dominance_threshold": 0.25,
            "drift_threshold": 0.50,
        },
        history_days=400,
    )
    book = uc.execute([_H("A", 10)], datetime(2026, 1, 1))
    assert book is None  # no factors -> cannot compute, abstain honestly
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_macro_beta_use_case.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'application.macro_beta_use_case'`.

- [ ] **Step 3: Create `application/macro_beta_use_case.py`**

```python
"""Orchestrate the macro-beta scrubber: prices -> returns -> estimate -> aggregate.

Network-free by injection (price_provider + estimator). Reuses the same
price_provider closure as _build_weekly_brief so the brief and the scrubber see
identical price data.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable

from loguru import logger

from domain.macro_beta import (
    aggregate_macro_exposure,
    align_returns,
    book_return_series,
    daily_returns,
)
from domain.models import (
    BookMacroExposure,
    HoldingMacroExposure,
    MacroFactorBeta,
)

PriceProvider = Callable[[str, datetime, datetime], "list[tuple[datetime, float]]"]


class MacroBetaUseCase:
    def __init__(
        self,
        price_provider: PriceProvider,
        estimator: Any,  # MacroBetaEstimatorPort
        factors: list[str],
        alpha: float,
        headline_window: int,
        drift_window: int,
        thresholds: dict[str, float],
        history_days: int = 400,
    ) -> None:
        self._prices = price_provider
        self._est = estimator
        self._factors = factors
        self._alpha = alpha
        self._headline = headline_window
        self._drift = drift_window
        self._thresholds = thresholds
        self._history_days = history_days

    def execute(
        self, holdings: list[Any], as_of: datetime
    ) -> BookMacroExposure | None:
        start = as_of - timedelta(days=self._history_days)

        # Factor return series (fetched once). A failed factor is dropped loudly.
        factor_rets: dict[str, list[tuple[datetime, float]]] = {}
        for f in self._factors:
            series = self._prices(f, start, as_of)
            rets = daily_returns(series)
            if len(rets) >= self._headline:
                factor_rets[f] = rets
            else:
                logger.warning(f"macro-beta: factor {f} dropped (insufficient history)")
        if not factor_rets:
            logger.warning("macro-beta: no usable factors — abstaining")
            return None
        factors = tuple(factor_rets)

        # Per-holding: returns, latest close (for market value), beta estimates.
        holding_rets: dict[str, list[tuple[datetime, float]]] = {}
        values: dict[str, float] = {}
        per_holding: list[HoldingMacroExposure] = []
        covered_value = 0.0
        total_value = 0.0

        for h in holdings:
            series = self._prices(h.ticker, start, as_of)
            if not series:
                continue
            latest_close = series[-1][1]
            value = h.shares * latest_close
            total_value += value
            rets = daily_returns(series)
            if len(rets) < self._headline:
                continue
            holding_rets[h.ticker] = rets
            values[h.ticker] = value
            covered_value += value

        if not holding_rets:
            return aggregate_macro_exposure(
                as_of=as_of.date().isoformat(),
                factors=factors,
                per_holding=[],
                systematic_share=0.0,
                factor_move_std={},
                book_drift_by_factor={},
                beta_headline_by_factor={},
                total_holdings=len(holdings),
                coverage_value_frac=0.0,
                thresholds=self._thresholds,
            )

        covered_total = sum(values.values())
        weights = {t: v / covered_total for t, v in values.items()}

        for t, rets in holding_rets.items():
            y_h, f_h = align_returns(rets, factor_rets)
            bh = self._fit(y_h, f_h, self._headline)
            br = self._fit(y_h, f_h, self._drift)
            betas = tuple(
                MacroFactorBeta(
                    factor=f,
                    beta_headline=bh[0].get(f, 0.0),
                    beta_recent=br[0].get(f, 0.0),
                    drift=br[0].get(f, 0.0) - bh[0].get(f, 0.0),
                )
                for f in factors
            )
            per_holding.append(
                HoldingMacroExposure(
                    ticker=t, weight=weights[t], betas=betas, r_squared=bh[1]
                )
            )

        # Book-level: regress the dollar-weighted book return on factors (one fit).
        factor_dates = sorted({d for d, _ in next(iter(factor_rets.values()))})
        book_rets = book_return_series(holding_rets, weights, factor_dates)
        yb, fb = align_returns(book_rets, factor_rets)
        book_head = self._fit(yb, fb, self._headline)
        book_drift = self._fit(yb, fb, self._drift)
        book_drift_by_factor = {
            f: book_drift[0].get(f, 0.0) - book_head[0].get(f, 0.0) for f in factors
        }

        factor_move_std = {f: _std(fb[f][-self._headline :]) for f in factors}

        return aggregate_macro_exposure(
            as_of=as_of.date().isoformat(),
            factors=factors,
            per_holding=per_holding,
            systematic_share=book_head[1],
            factor_move_std=factor_move_std,
            book_drift_by_factor=book_drift_by_factor,
            beta_headline_by_factor=book_head[0],
            total_holdings=len(holdings),
            coverage_value_frac=(covered_value / total_value) if total_value else 0.0,
            thresholds=self._thresholds,
        )

    def _fit(
        self,
        y: list[float],
        factors: dict[str, list[float]],
        window: int,
    ) -> tuple[dict[str, float], float]:
        y_w = y[-window:]
        f_w = {k: v[-window:] for k, v in factors.items()}
        return self._est.estimate(y_w, f_w, self._alpha)


def _std(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = sum(xs) / len(xs)
    return (sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_macro_beta_use_case.py -v`
Expected: PASS (3 tests). If the recovery test for `systematic_share` is flaky on the linear-trend fixture, that is fine — the assertion only bounds it to [0,1].

- [ ] **Step 5: Commit**

```bash
git add application/macro_beta_use_case.py tests/test_macro_beta_use_case.py
git commit -m "feat: MacroBetaUseCase orchestrates scrubber pipeline"
```

---

## Task 7: Fold macro into WeeklyBrief + formatters

**Files:**
- Modify: `domain/brief.py` (WeeklyBrief field, assemble_brief param, both formatters, `__all__` unchanged)
- Test: `tests/test_macro_beta.py` (append a brief-render test)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_macro_beta.py  (append)
def test_brief_renders_macro_section():
    from domain.brief import to_markdown, to_stdout_masked
    from domain.models import (
        BookMacroExposure,
        HoldingMacroExposure,
        MacroBetaFlag,
        MacroFactorBeta,
    )
    from domain.regime import Regime
    from domain.brief import ScorecardSnapshot, WeeklyBrief
    from domain.screen_models import ScreenLabel

    macro = BookMacroExposure(
        as_of="2026-06-09",
        factors=("SPY", "TLT", "UUP", "XLE"),
        net_beta_by_factor={"SPY": 0.9, "TLT": -0.6, "UUP": 0.1, "XLE": 0.2},
        systematic_share=0.72,
        idiosyncratic_share=0.28,
        dominant_factor="SPY",
        flags=(
            MacroBetaFlag("SYSTEMATIC_DOMINANT", None, "72% macro", 0.72, 0.60),
        ),
        holdings=(
            HoldingMacroExposure(
                "NVDA", 0.2, (MacroFactorBeta("SPY", 1.4, 1.5, 0.1),), 0.6
            ),
        ),
        coverage_holdings=1,
        total_holdings=1,
        coverage_value_frac=0.95,
    )
    brief = WeeklyBrief(
        as_of="2026-06-09",
        regime=Regime.RISK_ON,
        tilt={"momentum": 0.25, "revision": 0.25, "quality": 0.25, "value": 0.25},
        candidates=(),
        holdings=(),
        research_links=(),
        concentration=(),
        scorecard=ScorecardSnapshot(
            "forward since 2026-06-09", None, None, 0, False, "21d", None, 0, "PENDING"
        ),
        screen_label=ScreenLabel.RESEARCH_ONLY,
        macro=macro,
    )
    md = to_markdown(brief)
    assert "MACRO EXPOSURE" in md
    assert "72%" in md  # systematic share
    assert "NVDA" in md  # per-holding detail allowed in gitignored markdown

    masked = to_stdout_masked(brief)
    assert "MACRO" in masked
    assert "NVDA" not in masked  # masked stdout never leaks holding tickers


def test_brief_macro_none_renders_safely():
    from domain.brief import to_markdown
    from domain.regime import Regime
    from domain.brief import ScorecardSnapshot, WeeklyBrief
    from domain.screen_models import ScreenLabel

    brief = WeeklyBrief(
        as_of="2026-06-09",
        regime=Regime.RISK_ON,
        tilt={"momentum": 0.25, "revision": 0.25, "quality": 0.25, "value": 0.25},
        candidates=(),
        holdings=(),
        research_links=(),
        concentration=(),
        scorecard=ScorecardSnapshot(
            "forward since 2026-06-09", None, None, 0, False, "21d", None, 0, "PENDING"
        ),
        screen_label=ScreenLabel.RESEARCH_ONLY,
        # macro omitted -> defaults to None
    )
    md = to_markdown(brief)
    assert "MACRO EXPOSURE" in md
    assert "not computed" in md
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_macro_beta.py::test_brief_renders_macro_section -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'macro'`.

- [ ] **Step 3a: Add the import + field to `domain/brief.py`**

At the top imports (after L27), add `BookMacroExposure` to the `domain.models` import:

```python
from domain.models import BookMacroExposure, PortfolioRisk, PositionRisk
```

Add `"BookMacroExposure"` is NOT needed in `__all__` (it lives in models). Add the field to `WeeklyBrief` (must be LAST — it has a default):

```python
@dataclass(frozen=True)
class WeeklyBrief:
    as_of: str
    regime: Regime
    tilt: dict[str, float]
    candidates: tuple[BuyCandidateLine, ...]
    holdings: tuple[HoldingVerdictLine, ...]
    research_links: tuple[ResearchLink, ...]
    concentration: tuple[ConcentrationFlag, ...]
    scorecard: ScorecardSnapshot
    screen_label: ScreenLabel
    macro: BookMacroExposure | None = None
```

- [ ] **Step 3b: Add `macro` param to `assemble_brief` and pass it through**

Change the signature (after `concentration_threshold`):

```python
def assemble_brief(
    *,
    as_of: str,
    regime: Regime,
    tilt: dict[str, float],
    screen_result: ScreenResult,
    screen_label: ScreenLabel,
    top_n: int,
    positions: list[PositionRisk],
    portfolio: PortfolioRisk,
    held_tickers: set[str],
    cluster_overlaps: dict[str, list[str]],
    scorecard: ScorecardSnapshot,
    concentration_threshold: float = 0.20,
    macro: BookMacroExposure | None = None,
) -> WeeklyBrief:
```

In the `return WeeklyBrief(...)` block, add `macro=macro,` as the last argument.

- [ ] **Step 3c: Render in `to_markdown` (insert a section before `## SCORECARD`)**

```python
    lines.append("## MACRO EXPOSURE")
    m = brief.macro
    if m is None:
        lines.append("_(macro-beta not computed)_")
    else:
        lines.append(
            f"- systematic share: **{m.systematic_share:.0%}** of book variance is "
            f"macro-explained (idiosyncratic {m.idiosyncratic_share:.0%})"
        )
        if m.dominant_factor is not None:
            lines.append(f"- dominant factor: **{m.dominant_factor}**")
        nb = " · ".join(f"{f} {m.net_beta_by_factor[f]:+.2f}" for f in m.factors)
        lines.append(f"- net book beta: {nb}")
        lines.append(
            f"- coverage: {m.coverage_holdings}/{m.total_holdings} holdings "
            f"= {m.coverage_value_frac:.0%} of book value"
        )
        for fl in m.flags:
            lines.append(f"- ⚠ {fl.message}")
        for h in m.holdings:
            hb = " · ".join(f"{b.factor} {b.beta_headline:+.2f}" for b in h.betas)
            lines.append(f"  - {h.ticker} (w {h.weight:.0%}): {hb}  R²={h.r_squared:.2f}")
        lines.append("_(thresholds are heuristic surfacing dials, not validated edges)_")
    lines.append("")
```

- [ ] **Step 3d: Render an aggregate line in `to_stdout_masked` (before the SCORECARD line)**

```python
    m = brief.macro
    if m is not None:
        flag_n = len(m.flags)
        dom = m.dominant_factor or "n/a"
        lines.append(
            f"MACRO: systematic {m.systematic_share:.0%}, dominant {dom}, "
            f"{flag_n} flag(s), coverage {m.coverage_value_frac:.0%}"
        )
```

(No per-holding tickers in masked stdout — ADR-047.)

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_macro_beta.py -v && pytest tests/ -k brief -v`
Expected: PASS, and existing brief tests still green (the new field is optional/defaulted).

- [ ] **Step 5: Commit**

```bash
git add domain/brief.py tests/test_macro_beta.py
git commit -m "feat: render macro exposure pillar in weekly brief"
```

---

## Task 8: Wire macro into WeeklyBriefUseCase + CLI

**Files:**
- Modify: `application/weekly_brief_use_case.py` (inject `macro_fn`)
- Modify: `application/cli.py` `_build_weekly_brief` (L2763)
- Test: `tests/test_macro_beta_use_case.py` (append a use-case wiring test)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_macro_beta_use_case.py  (append)
def test_weekly_brief_use_case_accepts_macro_fn():
    import inspect

    from application.weekly_brief_use_case import WeeklyBriefUseCase

    sig = inspect.signature(WeeklyBriefUseCase.__init__)
    assert "macro_fn" in sig.parameters
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_macro_beta_use_case.py::test_weekly_brief_use_case_accepts_macro_fn -v`
Expected: FAIL — `AssertionError` (`macro_fn` not a parameter).

- [ ] **Step 3a: Add `macro_fn` to `WeeklyBriefUseCase`**

In `application/weekly_brief_use_case.py`:

Add a type alias near the other callables (after L21):

```python
# macro provider -> BookMacroExposure | None (network-free in tests)
MacroFn = Callable[[list[Any], datetime], "Any"]
```

Add `macro_fn: MacroFn | None = None` as the last `__init__` param and store it:

```python
        discipline_scorecard_fn: DisciplineScorecardFn,
        macro_fn: MacroFn | None = None,
    ) -> None:
        ...
        self._disc_card = discipline_scorecard_fn
        self._macro_fn = macro_fn
```

In `execute`, compute macro before the `assemble_brief` call:

```python
        macro = self._macro_fn(holdings, as_of) if self._macro_fn else None
```

and pass `macro=macro,` as the last argument to `assemble_brief(...)`.

- [ ] **Step 3b: Wire the use case in `cli._build_weekly_brief`**

In `application/cli.py`, inside `_build_weekly_brief` (after the `forward = ForwardTrackingUseCase(...)` block, before the `WeeklyBriefUseCase(...)` construction):

```python
    from adapters.ml.macro_beta_analyzer import RidgeMacroBetaEstimator
    from application.macro_beta_use_case import MacroBetaUseCase

    macro_cfg = deps.get("config", {}).get("macro_beta", {})
    macro_uc = MacroBetaUseCase(
        price_provider=lambda t, s, e: load_price_series(t, s, e),
        estimator=RidgeMacroBetaEstimator(alpha=macro_cfg.get("ridge_alpha", 0.2)),
        factors=macro_cfg.get("factors", ["SPY", "TLT", "UUP", "XLE"]),
        alpha=macro_cfg.get("ridge_alpha", 0.2),
        headline_window=macro_cfg.get("headline_window_days", 252),
        drift_window=macro_cfg.get("drift_window_days", 63),
        thresholds={
            "systematic_share_threshold": macro_cfg.get("systematic_share_threshold", 0.60),
            "factor_dominance_threshold": macro_cfg.get("factor_dominance_threshold", 0.25),
            "drift_threshold": macro_cfg.get("drift_threshold", 0.50),
        },
    )

    def _macro_fn(hlds: "list[Any]", as_of: datetime) -> "Any":
        try:
            return macro_uc.execute(hlds, as_of)
        except Exception:
            logger.warning("macro-beta scrubber failed — brief renders without it")
            return None
```

Then add `macro_fn=_macro_fn,` to the `WeeklyBriefUseCase(...)` constructor call.

> **Verified:** `_build_dependencies` returns `deps["config"]` (the full `load_market_config(market)` dict) — `deps.get("config", {}).get("macro_beta", {})` works as written. `logger` (loguru) is already imported at `cli.py:15`. `load_price_series` already imported at `cli.py:32`. No extra imports needed beyond the two new ones shown above.

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_macro_beta_use_case.py -v && pytest tests/ -k "weekly_brief or brief" -v`
Expected: PASS. Existing weekly-brief tests still green (`macro_fn` defaults to None).

- [ ] **Step 5: Commit**

```bash
git add application/weekly_brief_use_case.py application/cli.py tests/test_macro_beta_use_case.py
git commit -m "feat: wire macro-beta scrubber into weekly-brief pipeline"
```

---

## Task 9: Config block

**Files:**
- Modify: `config/markets/us.yaml`

- [ ] **Step 1: Add the `macro_beta` block** (append near `macro_symbols`/`sector_etfs`; keep it SEPARATE from `macro_symbols`, which holds yield indices unfit for return-regression):

```yaml
# Macro-beta scrubber (Unit A, ADR-052). Independent of macro_symbols above:
# those are yield/index LEVELS; these are tradeable ETFs whose daily RETURNS are
# the factors. Thresholds are heuristic surfacing dials, NOT validated edges.
macro_beta:
  factors: [SPY, TLT, UUP, XLE]   # market / rates / dollar / energy-equity
  headline_window_days: 252       # ~1 year
  drift_window_days: 63           # ~1 quarter
  ridge_alpha: 0.2                # light shrinkage; betas reported shrinkage-adjusted
  systematic_share_threshold: 0.60
  factor_dominance_threshold: 0.25
  drift_threshold: 0.50
```

- [ ] **Step 2: Verify YAML parses**

Run: `python -c "import yaml; print(yaml.safe_load(open('config/markets/us.yaml'))['macro_beta'])"`
Expected: prints the dict with `factors: ['SPY','TLT','UUP','XLE']`.

- [ ] **Step 3: Commit**

```bash
git add config/markets/us.yaml
git commit -m "feat: macro_beta config block (us market)"
```

---

## Task 10: Prune stale screen universe

**Files:**
- Modify: `config/tickers/sp500.txt`, `config/tickers/nasdaq100.txt`, `config/tickers/tsx60.txt`

> **Verify-before-delete:** each ticker below was confirmed delisted/consolidated in the ADR-052 dogfood. Before deleting, re-confirm each is NOT a live name typo (e.g. quick yfinance check or known-delisted list). Do not remove anything not on this list.

Confirmed delisted: SP500/NASDAQ — `SIVB` (SVB, 2023), `PXD` (Pioneer→Exxon, 2024), `SPLK` (Splunk→Cisco, 2024), `WBA` (taken private, 2025), `WRK` (WestRock→Smurfit, 2024). TSX — `GIB.A`, `RCI.B`, `TECK.B` (class-share notation; confirm against current TSX listing — some may be live under a different symbol; only remove if delisted from the data source).

- [ ] **Step 1: Show current presence**

Run:
```bash
grep -nE '^(SIVB|PXD|WBA|WRK)$' config/tickers/sp500.txt
grep -nE '^SPLK$' config/tickers/nasdaq100.txt
grep -nE '^(GIB\.A|RCI\.B|TECK\.B)$' config/tickers/tsx60.txt
```
Expected: line numbers for each present ticker.

- [ ] **Step 2: Remove the confirmed-delisted lines**

Edit each file, deleting only the exact lines for the confirmed tickers. (Use the Edit tool per line; do not sed-delete blindly.) Leave `SPLK` in `sp500.txt` removed too if present (re-grep `^SPLK$` in sp500.txt).

- [ ] **Step 3: Verify removal + universe still loads**

Run:
```bash
grep -cE '^(SIVB|PXD|SPLK|WBA|WRK)$' config/tickers/sp500.txt config/tickers/nasdaq100.txt
python -c "from application.ticker_universe import load_ticker_universe; from pathlib import Path; print(len(load_ticker_universe([Path('config/tickers/sp500.txt'), Path('config/tickers/nasdaq100.txt')])))"
```
Expected: first grep count `0`; second prints a ticker count (universe loads without the stale names).

- [ ] **Step 4: Commit**

```bash
git add config/tickers/
git commit -m "fix: prune delisted tickers from screen universe (ADR-052)"
```

---

## Task 11: Full check + ADR cross-reference

**Files:**
- Modify: `docs/adr/052-cro-direction-alpha-hunt-closed.md` (append a "Unit A — DONE" note)

- [ ] **Step 1: Run the full quality gate**

Run: `make check`
Expected: lint + mypy strict + all tests pass with coverage ≥ 90%. Fix anything red before proceeding (no `--no-verify`).

- [ ] **Step 2: Live dogfood (manual, local machine, gitignored holdings)**

Run: `python -m application.cli weekly-brief --holdings data/personal/holdings-report-2026-06-07.csv`
Expected stdout: includes a `MACRO: systematic NN%, dominant <FACTOR>, K flag(s), coverage NN%` line. Open `data/personal/weekly_brief.md` and confirm the `## MACRO EXPOSURE` section shows per-holding betas + net book beta + coverage + any flags.

> **Sanity check the betas (escalation gate):** SPY beta for an equity book should be roughly 0.7–1.3. If net SPY beta comes back near ~0.1 (implausibly small), shrinkage is too aggressive — lower `ridge_alpha` toward 0.05 in `us.yaml`, or escalate the estimator to orthogonalized OLS per the spec. Record the observed betas either way.

- [ ] **Step 3: Append the ADR note**

In `docs/adr/052-cro-direction-alpha-hunt-closed.md`, append:

```markdown

## Unit A — Macro-Beta Scrubber (DONE 2026-06-09)

Shipped the macro-beta scrubber: per-holding Ridge betas on SPY/TLT/UUP/XLE (raw
de-meaned daily returns, light shrinkage), dollar-weighted book net-beta, book
systematic-vs-idiosyncratic variance split, three heuristic flags
(SYSTEMATIC_DOMINANT / FACTOR_DOMINANCE / DRIFT), folded into `weekly-brief`.
Pruned delisted screen tickers (SIVB/PXD/SPLK/WBA/WRK + stale TSX names).
Thresholds are surfacing dials, not validated edges. Cluster caps deferred
(factor view subsumes them). Next: Unit B (sub-$1B insider-cluster IC).
```

- [ ] **Step 4: Commit**

```bash
git add docs/adr/052-cro-direction-alpha-hunt-closed.md
git commit -m "docs: ADR-052 Unit A macro-beta scrubber complete"
```

---

## Self-Review

**Spec coverage:**
- Macro-beta scrubber (per-holding betas + net book beta + variance split) → Tasks 1-6. ✓
- Returns-not-levels, raw Ridge no scaler → Task 5. ✓
- SPY/TLT/UUP/XLE → Task 9 config, used in Tasks 6/8. ✓
- 252d headline + 63d drift → Tasks 6/9. ✓
- Three flags (systematic/dominance/drift) → Task 3. ✓
- Fold into weekly-brief (markdown + masked) → Tasks 7/8. ✓
- Coverage reporting + no silent failures → Tasks 6/7 (coverage line) + dropped-factor logging. ✓
- Thresholds as un-validated heuristics → Tasks 3/7/9 (labeled). ✓
- Stale universe fix → Task 10. ✓
- Hypothesis invariants → Task 3. ✓

**Placeholder scan:** no TBD/TODO; every code step has complete code. The two `> Check`/`> Verify` callouts (Task 8 config-key, Task 10 ticker-confirm) are deliberate verification steps with explicit fallbacks, not placeholders.

**Type consistency:** `estimate(...) -> tuple[dict[str,float], float]` consistent across port (Task 4), adapter (Task 5), use case `_fit` (Task 6). `BookMacroExposure | None` consistent across use case return (6), WeeklyBrief field (7), macro_fn (8). `MacroFactorBeta(factor, beta_headline, beta_recent, drift)` consistent in models (1), use case (6), tests. `aggregate_macro_exposure` kwargs identical between Task 3 definition and Task 6 call sites.

**Known approximation (documented):** `net_beta` (pure, Σwβ over per-holding shrunk betas) and `systematic_share`/book `beta_headline_by_factor` (from the separate book-return regression) come from two fits; under Ridge shrinkage Σwβ ≠ the book coefficient exactly. Both are honest, sourced where the data lives; the brief reports net beta from the aggregator and systematic share from the book fit. Acceptable for LOW build per spec.
