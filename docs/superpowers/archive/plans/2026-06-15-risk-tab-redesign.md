# Risk Tab Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the Streamlit Risk tab into the legible "Where your book stands" surface (mockup v8) and harden the macro-beta statistics with ENB, uncertainty bands, risk-contribution, downside beta, VIF, sector concentration, and an attributed Google-AI second opinion.

**Architecture:** Hexagonal. New *pure* math in `domain/risk_stats.py`; numpy/sklearn-heavy math in `adapters/ml/risk_stats_analyzer.py`; sector lookup in `adapters/data/sector_provider.py`; weekly history in an append-only store; all orchestrated by the existing `MacroBetaUseCase`, serialized into `brief_summary.json`, and rendered by a rewritten `adapters/visualization/tabs/risk.py`. Reuses `tooltip()`, `apply_dossier_template`, the Gemini cited-case stack, `is_local_runtime()`, and `FORBIDDEN_WORDS`.

**Tech Stack:** Python 3.12, numpy, scikit-learn (Ridge already in use), Streamlit, Plotly, pytest + Hypothesis, yfinance (sector lookup).

**Spec:** `docs/superpowers/specs/2026-06-15-risk-tab-redesign-design.md`
**Reuse map:** `research/2026-06-15-risk-tab-existing-infra.md`
**Mockup of record (source of truth for HTML/CSS):** `.superpowers/brainstorm/65055-1781542394/content/risk-v7.html` (eyebrow "v8 — full methodology"). Copy this into the worktree under `docs/superpowers/mockups/risk-v8.html` in Task 0 so it survives.

**Honesty rails (apply to EVERY UI task):** dials are heuristic-not-edge (ADR-052); risk character never graded good/bad; sector gaps descriptive only (`NOT A BUY CALL`); Google AI is attributed, RESEARCH_ONLY, gated by `is_local_runtime()`; no FORBIDDEN_WORDS (`buy/sell/winner/conviction/predict/alpha/outperform`) in any rendered string.

---

## File Structure

**Create:**
- `domain/risk_stats.py` — pure stats arithmetic (adjusted R², ENB-from-eigenvalues, diversification ratio, risk contribution, VIF formula, downside-day filter).
- `adapters/ml/risk_stats_analyzer.py` — numpy covariance/PCA/bootstrap/OLS-SE/downside-refit.
- `adapters/data/sector_provider.py` — GICS sector lookup + JSON cache.
- `application/macro_history_store.py` — append-only weekly `systematic_share` history.
- `application/risk_second_opinion.py` — risk-specific Gemini call (reuses adapter + rate limiter + cache).
- `adapters/visualization/components/risk_second_opinion.py` — render the attributed AI panel.
- `docs/superpowers/mockups/risk-v8.html` — frozen copy of the approved mockup.

**Modify:**
- `domain/models.py` — extend `BookMacroExposure` with new fields.
- `application/macro_beta_use_case.py` — compute + attach the new stats.
- `application/brief_summary.py` — serialize the new fields.
- `application/cli.py` — write history + (optional) prefetch risk second opinion in `weekly-brief`.
- `adapters/visualization/components/styles.py` — add status-first CSS tokens + classes.
- `adapters/visualization/components/glossary.py` — add ~15 terms.
- `adapters/visualization/tabs/risk.py` — full render rewrite to v8.
- `config/markets/us.yaml` — add `risk_stats` block (bootstrap iters, seed).

**Test:** one test file per new module under `tests/` mirroring existing layout.

---

## Task 0: Worktree + scaffolding

**Files:** none (env setup)

- [ ] **Step 1: Create isolated worktree off the committed legibility HEAD**

```bash
cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender"
git worktree add -b feat/risk-tab-redesign ../risk-tab-redesign feat/dashboard-legibility-redesign
cd ../risk-tab-redesign
```
Expected: new worktree on branch `feat/risk-tab-redesign`, clean tree (does NOT carry the other sessions' uncommitted Home/Screener edits).

- [ ] **Step 2: Freeze the mockup + docs into the worktree**

```bash
mkdir -p docs/superpowers/mockups
cp "../multi-modal-stock-recommender/.superpowers/brainstorm/65055-1781542394/content/risk-v7.html" docs/superpowers/mockups/risk-v8.html
# bring the spec/research/plan if not already on this branch:
cp "../multi-modal-stock-recommender/docs/superpowers/specs/2026-06-15-risk-tab-redesign-design.md" docs/superpowers/specs/ 2>/dev/null || true
cp "../multi-modal-stock-recommender/research/2026-06-15-risk-tab-existing-infra.md" research/ 2>/dev/null || true
grep -q "^\.superpowers/" .gitignore || echo ".superpowers/" >> .gitignore
```

- [ ] **Step 3: Verify baseline green**

Run: `make check`
Expected: PASS (ruff clean, mypy --strict clean, pytest ≥90%). If `data/reports/` tracked JSONs cause churn, `git checkout data/reports/` first.

- [ ] **Step 4: Commit scaffolding**

```bash
git add docs/ research/ .gitignore
git commit -m "chore: scaffold risk-tab redesign (spec, plan, frozen mockup)"
```

---

## Task 1: Pure stats — adjusted R²

**Files:**
- Create: `domain/risk_stats.py`
- Test: `tests/domain/test_risk_stats.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/domain/test_risk_stats.py
import math
import pytest
from domain.risk_stats import adjusted_r2


def test_adjusted_r2_penalizes_parameters():
    # raw R²=0.71, n=252 obs, p=9 factors
    adj = adjusted_r2(0.71, n=252, p=9)
    assert adj < 0.71
    assert adj == pytest.approx(1 - (1 - 0.71) * (252 - 1) / (252 - 9 - 1), rel=1e-9)


def test_adjusted_r2_degenerate_guards():
    # n - p - 1 <= 0 → return raw (cannot adjust)
    assert adjusted_r2(0.5, n=5, p=9) == 0.5
    assert adjusted_r2(0.0, n=100, p=3) == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/domain/test_risk_stats.py -v`
Expected: FAIL with "cannot import name 'adjusted_r2'".

- [ ] **Step 3: Write minimal implementation**

```python
# domain/risk_stats.py
"""Pure descriptive-risk statistics (stdlib + math only). NO numpy, NO prediction.

Every function is deterministic arithmetic so it is fully unit/property-testable.
Heavy linear algebra (covariance, PCA, bootstrap) lives in the adapter
adapters/ml/risk_stats_analyzer.py; this module takes its scalar/vector outputs.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def adjusted_r2(r2: float, n: int, p: int) -> float:
    """Adjusted R²: penalizes the p factors. Returns raw r2 if not adjustable."""
    denom = n - p - 1
    if denom <= 0:
        return r2
    return 1.0 - (1.0 - r2) * (n - 1) / denom
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/domain/test_risk_stats.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add domain/risk_stats.py tests/domain/test_risk_stats.py
git commit -m "feat: adjusted R² (descriptive risk stat)"
```

---

## Task 2: Pure stats — Effective Number of Bets (ENB)

**Files:**
- Modify: `domain/risk_stats.py`
- Test: `tests/domain/test_risk_stats.py`

- [ ] **Step 1: Write the failing test**

```python
from domain.risk_stats import effective_number_of_bets


def test_enb_equal_uncorrelated_equals_n():
    # n equal eigenvalues → ENB = n
    assert effective_number_of_bets([1.0, 1.0, 1.0, 1.0]) == pytest.approx(4.0)


def test_enb_one_dominant_equals_one():
    # all variance in one direction → ENB = 1
    assert effective_number_of_bets([1.0, 0.0, 0.0]) == pytest.approx(1.0)


def test_enb_between_one_and_n():
    enb = effective_number_of_bets([0.64, 0.14, 0.09, 0.05, 0.04, 0.04])
    assert 1.0 < enb < 6.0


def test_enb_empty_or_zero_is_zero():
    assert effective_number_of_bets([]) == 0.0
    assert effective_number_of_bets([0.0, 0.0]) == 0.0
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/domain/test_risk_stats.py -k enb -v`
Expected: FAIL "cannot import name 'effective_number_of_bets'".

- [ ] **Step 3: Implement**

```python
def effective_number_of_bets(eigenvalues: Sequence[float]) -> float:
    """Meucci ENB = exp(-Σ pᵢ ln pᵢ) over variance fractions pᵢ (eigenvalues
    of the holdings covariance, i.e. variance of the principal portfolios)."""
    vals = [max(v, 0.0) for v in eigenvalues]
    total = sum(vals)
    if total <= 0.0:
        return 0.0
    entropy = 0.0
    for v in vals:
        p = v / total
        if p > 0.0:
            entropy -= p * math.log(p)
    return math.exp(entropy)
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/domain/test_risk_stats.py -k enb -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add domain/risk_stats.py tests/domain/test_risk_stats.py
git commit -m "feat: effective number of bets (Meucci ENB)"
```

---

## Task 3: Pure stats — diversification ratio, risk contribution, VIF

**Files:**
- Modify: `domain/risk_stats.py`
- Test: `tests/domain/test_risk_stats.py`

- [ ] **Step 1: Write the failing tests**

```python
from domain.risk_stats import diversification_ratio, risk_contributions, vif_from_r2


def test_diversification_ratio_uncorrelated_gt_one():
    # two equal-weight, equal-vol, uncorrelated assets → DR = sqrt(2)
    dr = diversification_ratio(weighted_avg_vol=1.0, portfolio_vol=1.0 / math.sqrt(2))
    assert dr == pytest.approx(math.sqrt(2), rel=1e-9)


def test_diversification_ratio_zero_portfolio_vol_is_one():
    assert diversification_ratio(1.0, 0.0) == 1.0


def test_risk_contributions_sum_to_one():
    # contributions = w_i * (Σw)_i / (wᵀΣw); pass precomputed marginal terms
    rc = risk_contributions(weights=[0.5, 0.5], marginal=[0.5, 0.5], portfolio_var=0.5)
    assert sum(rc.values()) if isinstance(rc, dict) else sum(rc) == pytest.approx(1.0)


def test_vif_from_r2():
    assert vif_from_r2(0.8) == pytest.approx(1 / (1 - 0.8))
    assert vif_from_r2(1.0) == float("inf")
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/domain/test_risk_stats.py -k "diversification or risk_contrib or vif" -v`
Expected: FAIL (imports missing).

- [ ] **Step 3: Implement**

```python
def diversification_ratio(weighted_avg_vol: float, portfolio_vol: float) -> float:
    """(Σ wᵢσᵢ) / σ_portfolio. 1.0 = no diversification benefit. Guards div-by-0."""
    if portfolio_vol <= 0.0:
        return 1.0
    return weighted_avg_vol / portfolio_vol


def risk_contributions(
    weights: Sequence[float], marginal: Sequence[float], portfolio_var: float
) -> list[float]:
    """Euler decomposition: RCᵢ = wᵢ·(Σw)ᵢ / (wᵀΣw). `marginal` = (Σw) per asset.
    Returns fractions summing to 1.0 (empty/zero-var → empty list)."""
    if portfolio_var <= 0.0 or not weights:
        return [0.0 for _ in weights]
    return [w * m / portfolio_var for w, m in zip(weights, marginal)]


def vif_from_r2(r2: float) -> float:
    """Variance inflation factor for a factor whose regression-on-others gave r2."""
    if r2 >= 1.0:
        return float("inf")
    return 1.0 / (1.0 - r2)
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/domain/test_risk_stats.py -k "diversification or risk_contrib or vif" -v`
Expected: PASS.

- [ ] **Step 5: Property test — ENB bounds + RC sum (Hypothesis)**

```python
from hypothesis import given, strategies as st

@given(st.lists(st.floats(min_value=0.0, max_value=10.0), min_size=1, max_size=12))
def test_enb_within_one_and_n(eigs):
    total = sum(eigs)
    enb = effective_number_of_bets(eigs)
    if total > 0:
        assert 0.999 <= enb <= len([e for e in eigs if e > 0]) + 1e-6
```

- [ ] **Step 6: Run + commit**

Run: `pytest tests/domain/test_risk_stats.py -v` → PASS
```bash
git add domain/risk_stats.py tests/domain/test_risk_stats.py
git commit -m "feat: diversification ratio, risk contribution, VIF (descriptive stats)"
```

---

## Task 4: Adapter — covariance, eigenvalues, bootstrap & OLS SE, downside refit

**Files:**
- Create: `adapters/ml/risk_stats_analyzer.py`
- Test: `tests/adapters/test_risk_stats_analyzer.py`

Use context7 for numpy `linalg.eigvalsh` / `cov` if unsure of current API before coding.

- [ ] **Step 1: Write failing tests**

```python
# tests/adapters/test_risk_stats_analyzer.py
import numpy as np
import pytest
from adapters.ml.risk_stats_analyzer import RiskStatsAnalyzer


def _series(rng, n, k):
    return rng.normal(size=(n, k))


def test_eigenvalues_descending_and_positive():
    rng = np.random.default_rng(0)
    X = _series(rng, 250, 5)
    a = RiskStatsAnalyzer(seed=0)
    eigs = a.covariance_eigenvalues(X)
    assert list(eigs) == sorted(eigs, reverse=True)
    assert all(e >= -1e-9 for e in eigs)


def test_bootstrap_ci_brackets_point_estimate():
    rng = np.random.default_rng(1)
    y = rng.normal(size=250)
    F = {"SPY": rng.normal(size=250)}
    a = RiskStatsAnalyzer(seed=1, bootstrap_iters=200)
    lo, hi = a.bootstrap_r2_ci(y, F, alpha=0.2)
    assert 0.0 <= lo <= hi <= 1.0


def test_downside_beta_uses_only_down_days():
    rng = np.random.default_rng(2)
    spy = rng.normal(size=300)
    y = 1.3 * spy + 0.0 * rng.normal(size=300)
    a = RiskStatsAnalyzer(seed=2)
    db = a.downside_beta(y.tolist(), spy.tolist())
    assert db == pytest.approx(1.3, abs=0.15)


def test_beta_ci_straddle_zero_flagged():
    rng = np.random.default_rng(3)
    spy = rng.normal(size=300)
    noise = rng.normal(size=300)        # factor unrelated to y
    y = 1.0 * spy
    a = RiskStatsAnalyzer(seed=3, bootstrap_iters=200)
    cis = a.beta_cis(y.tolist(), {"SPY": spy.tolist(), "NOISE": noise.tolist()}, alpha=0.2)
    lo, hi = cis["NOISE"]
    assert lo < 0 < hi          # straddles zero → caller suppresses
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/adapters/test_risk_stats_analyzer.py -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement**

```python
# adapters/ml/risk_stats_analyzer.py
"""Numpy-backed risk statistics: covariance eigenvalues (for ENB), bootstrap R²
and beta CIs, downside beta. Returns plain Python so domain/use-case stay numpy-free."""

from __future__ import annotations

import numpy as np
from sklearn.linear_model import Ridge


class RiskStatsAnalyzer:
    def __init__(self, seed: int = 0, bootstrap_iters: int = 500) -> None:
        self._seed = seed
        self._iters = bootstrap_iters

    def covariance_eigenvalues(self, returns_matrix: np.ndarray) -> list[float]:
        """Eigenvalues (variance of principal portfolios), descending. Rows=days, cols=holdings."""
        if returns_matrix.ndim != 2 or returns_matrix.shape[1] == 0:
            return []
        cov = np.cov(returns_matrix, rowvar=False)
        cov = np.atleast_2d(cov)
        eigs = np.linalg.eigvalsh(cov)          # ascending, real (symmetric)
        return [float(e) for e in sorted((max(e, 0.0) for e in eigs), reverse=True)]

    def _fit_ridge(self, y: np.ndarray, X: np.ndarray, alpha: float) -> np.ndarray:
        y = y - y.mean()
        X = X - X.mean(axis=0, keepdims=True)
        eff = alpha * max(float(np.mean(np.var(X, axis=0))), 1e-12)
        model = Ridge(alpha=eff)
        model.fit(X, y)
        return model.coef_

    def _r2(self, y: np.ndarray, X: np.ndarray, alpha: float) -> float:
        y0 = y - y.mean()
        ss_tot = float(np.sum(y0**2))
        if ss_tot == 0.0:
            return 0.0
        coef = self._fit_ridge(y, X, alpha)
        pred = (X - X.mean(axis=0, keepdims=True)) @ coef
        resid = y0 - pred
        return max(min(1.0 - float(np.sum(resid**2)) / ss_tot, 1.0), 0.0)

    def bootstrap_r2_ci(self, y, factor_returns, alpha, ci=0.90) -> tuple[float, float]:
        rng = np.random.default_rng(self._seed)
        y = np.asarray(y, float)
        X = np.column_stack([np.asarray(factor_returns[f], float) for f in factor_returns])
        n = len(y)
        if n < 20:
            return (0.0, 0.0)
        vals = []
        for _ in range(self._iters):
            idx = rng.integers(0, n, n)
            vals.append(self._r2(y[idx], X[idx], alpha))
        lo_q, hi_q = (1 - ci) / 2, 1 - (1 - ci) / 2
        return (float(np.quantile(vals, lo_q)), float(np.quantile(vals, hi_q)))

    def beta_cis(self, y, factor_returns, alpha, ci=0.90) -> dict[str, tuple[float, float]]:
        rng = np.random.default_rng(self._seed + 1)
        factors = list(factor_returns)
        y = np.asarray(y, float)
        X = np.column_stack([np.asarray(factor_returns[f], float) for f in factors])
        n = len(y)
        if n < 20:
            return {f: (0.0, 0.0) for f in factors}
        draws = np.empty((self._iters, len(factors)))
        for b in range(self._iters):
            idx = rng.integers(0, n, n)
            draws[b] = self._fit_ridge(y[idx], X[idx], alpha)
        lo_q, hi_q = (1 - ci) / 2, 1 - (1 - ci) / 2
        return {
            f: (float(np.quantile(draws[:, j], lo_q)), float(np.quantile(draws[:, j], hi_q)))
            for j, f in enumerate(factors)
        }

    def downside_beta(self, y, spy, eps: float = 1e-9) -> float:
        y = np.asarray(y, float)
        spy = np.asarray(spy, float)
        mask = spy < 0.0
        if mask.sum() < 10:
            return 0.0
        yd, sd = y[mask], spy[mask]
        var = float(np.var(sd))
        if var <= eps:
            return 0.0
        return float(np.cov(yd, sd, bias=True)[0, 1] / var)

    def principal_loadings(self, returns_matrix: np.ndarray, tickers: list[str], k: int = 3) -> list[list[str]]:
        """For the top-k principal components, the tickers with the largest |loading|.
        Used to label the ENB 'bets'. Returns [] if matrix degenerate."""
        if returns_matrix.ndim != 2 or returns_matrix.shape[1] == 0:
            return []
        cov = np.atleast_2d(np.cov(returns_matrix, rowvar=False))
        vals, vecs = np.linalg.eigh(cov)             # ascending
        order = list(reversed(range(len(vals))))[:k]
        out: list[list[str]] = []
        for i in order:
            loadings = np.abs(vecs[:, i])
            top = [tickers[j] for j in np.argsort(loadings)[::-1][:3] if j < len(tickers)]
            out.append(top)
        return out
```

- [ ] **Step 3b: Add the loadings test**

```python
def test_principal_loadings_returns_top_tickers():
    rng = np.random.default_rng(4)
    base = rng.normal(size=(250, 1))
    X = np.hstack([base + 0.01 * rng.normal(size=(250, 1)) for _ in range(3)])  # 3 co-moving
    a = RiskStatsAnalyzer(seed=4)
    loads = a.principal_loadings(X, ["A", "B", "C"], k=2)
    assert loads and set(loads[0]).issubset({"A", "B", "C"})
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/adapters/test_risk_stats_analyzer.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add adapters/ml/risk_stats_analyzer.py tests/adapters/test_risk_stats_analyzer.py
git commit -m "feat: numpy risk-stats analyzer (eigenvalues, bootstrap CIs, downside beta)"
```

---

## Task 5: Sector provider + cache

**Files:**
- Create: `adapters/data/sector_provider.py`
- Test: `tests/adapters/test_sector_provider.py`

Verify the yfinance `.info` sector field name via context7 before coding.

- [ ] **Step 1: Write failing tests** (inject a fake fetcher — no network in tests)

```python
# tests/adapters/test_sector_provider.py
from adapters.data.sector_provider import SectorProvider


def test_uses_cache_then_fetcher(tmp_path):
    cache = tmp_path / "sector_map.json"
    calls = []
    def fake_fetch(t):
        calls.append(t); return {"NVDA": "Information Technology"}.get(t)
    p = SectorProvider(cache_path=str(cache), fetcher=fake_fetch)
    assert p.sector("NVDA") == "Information Technology"
    # second call hits cache, not fetcher
    assert p.sector("NVDA") == "Information Technology"
    assert calls == ["NVDA"]


def test_unknown_is_data_gap(tmp_path):
    p = SectorProvider(cache_path=str(tmp_path / "m.json"), fetcher=lambda t: None)
    assert p.sector("ZZZZ") == "Unknown"
```

- [ ] **Step 2: Run → FAIL.** `pytest tests/adapters/test_sector_provider.py -v`

- [ ] **Step 3: Implement**

```python
# adapters/data/sector_provider.py
"""GICS sector lookup with a JSON cache. Offline-safe: unknown → "Unknown" (DATA-GAP)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path


def _yf_fetch(ticker: str) -> str | None:
    try:
        import yfinance as yf
        return yf.Ticker(ticker).info.get("sector")  # confirm field via context7
    except Exception:
        return None


class SectorProvider:
    def __init__(self, cache_path: str = "data/personal/sector_map.json",
                 fetcher: Callable[[str], str | None] = _yf_fetch) -> None:
        self._path = Path(cache_path)
        self._fetch = fetcher
        self._cache: dict[str, str] = {}
        if self._path.exists():
            try:
                self._cache = json.loads(self._path.read_text())
            except Exception:
                self._cache = {}

    def sector(self, ticker: str) -> str:
        if ticker in self._cache:
            return self._cache[ticker]
        got = self._fetch(ticker) or "Unknown"
        self._cache[ticker] = got
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._cache, indent=2))
        return got
```

- [ ] **Step 4: Run → PASS.** `pytest tests/adapters/test_sector_provider.py -v`

- [ ] **Step 5: Commit**
```bash
git add adapters/data/sector_provider.py tests/adapters/test_sector_provider.py
git commit -m "feat: sector provider with offline-safe cache"
```

---

## Task 6: Weekly macro-history store

**Files:**
- Create: `application/macro_history_store.py`
- Test: `tests/application/test_macro_history_store.py`

- [ ] **Step 1: Failing test**

```python
from application.macro_history_store import append_systematic_share, load_systematic_share_history

def test_append_and_load(tmp_path):
    p = tmp_path / "macro_history.jsonl"
    append_systematic_share(str(p), "2026-06-01", 0.64)
    append_systematic_share(str(p), "2026-06-08", 0.71)
    hist = load_systematic_share_history(str(p))
    assert hist == [("2026-06-01", 0.64), ("2026-06-08", 0.71)]

def test_load_missing_is_empty(tmp_path):
    assert load_systematic_share_history(str(tmp_path / "none.jsonl")) == []
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement**

```python
# application/macro_history_store.py
"""Append-only weekly systematic-share history (JSONL) for the drift sparkline."""

from __future__ import annotations

import json
from pathlib import Path


def append_systematic_share(path: str, as_of: str, value: float) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as fh:
        fh.write(json.dumps({"as_of": as_of, "systematic_share": value}) + "\n")


def load_systematic_share_history(path: str) -> list[tuple[str, float]]:
    p = Path(path)
    if not p.exists():
        return []
    out: list[tuple[str, float]] = []
    for line in p.read_text().splitlines():
        if not line.strip():
            continue
        try:
            d = json.loads(line)
            out.append((d["as_of"], float(d["systematic_share"])))
        except Exception:
            continue
    return out
```

- [ ] **Step 4: Run → PASS. Step 5: Commit**
```bash
git add application/macro_history_store.py tests/application/test_macro_history_store.py
git commit -m "feat: weekly macro-history store for drift sparkline"
```

---

## Task 7: Extend BookMacroExposure with new fields

**Files:**
- Modify: `domain/models.py:483-498` (the `BookMacroExposure` dataclass)
- Test: `tests/test_macro_beta.py`

- [ ] **Step 1: Failing test**

```python
def test_book_macro_exposure_carries_new_fields():
    from domain.models import BookMacroExposure
    b = BookMacroExposure(
        as_of="2026-06-15", factors=("SPY",), net_beta_by_factor={"SPY": 1.18},
        systematic_share=0.71, idiosyncratic_share=0.29, dominant_factor="SPY",
        flags=(), holdings=(), coverage_holdings=58, total_holdings=66,
        coverage_value_frac=0.9,
        enb=3.2, pc_variance=(0.64, 0.14, 0.09), pc_labels=("PC1", "PC2", "PC3"),
        systematic_share_adj=0.66, systematic_share_ci=(0.66, 0.76),
        beta_ci_by_factor={"SPY": (1.09, 1.27)}, suppressed_factors=(),
        downside_beta=1.31, risk_contribution={"NVDA": 0.14},
        holdings_meta=({"ticker": "NVDA", "name": "Nvidia", "sector": "Information Technology", "weight": 0.09},),
        sector_weights={"Information Technology": 0.52}, sector_hhi=0.34, sector_gaps=("Health Care",),
        vif_by_factor={"SPY": 1.0}, diversification_ratio=1.4,
        sys_share_history=(("2026-06-08", 0.64), ("2026-06-15", 0.71)),
    )
    assert b.enb == 3.2 and b.downside_beta == 1.31
```

- [ ] **Step 2: Run → FAIL** (unexpected keyword args).

- [ ] **Step 3: Implement** — add fields to the dataclass with safe defaults so older construction still works:

```python
# in domain/models.py, BookMacroExposure (append fields, all defaulted):
    enb: float = 0.0
    pc_variance: tuple[float, ...] = ()
    pc_labels: tuple[str, ...] = ()
    pc_labels_data_gap: bool = False
    systematic_share_adj: float = 0.0
    systematic_share_ci: tuple[float, float] = (0.0, 0.0)
    beta_ci_by_factor: dict[str, tuple[float, float]] = field(default_factory=dict)
    suppressed_factors: tuple[str, ...] = ()
    downside_beta: float = 0.0
    risk_contribution: dict[str, float] = field(default_factory=dict)
    holdings_meta: tuple[dict[str, object], ...] = ()
    sector_weights: dict[str, float] = field(default_factory=dict)
    sector_hhi: float = 0.0
    sector_gaps: tuple[str, ...] = ()
    vif_by_factor: dict[str, float] = field(default_factory=dict)
    diversification_ratio: float = 1.0
    sys_share_history: tuple[tuple[str, float], ...] = ()
```
(Ensure `from dataclasses import field` is imported.)

- [ ] **Step 4: Run → PASS.** `pytest tests/test_macro_beta.py -v`
- [ ] **Step 5: Commit**
```bash
git add domain/models.py tests/test_macro_beta.py
git commit -m "feat: extend BookMacroExposure with v8 risk stats fields"
```

---

## Task 8: Compute new stats in the use case

**Files:**
- Modify: `application/macro_beta_use_case.py` (constructor + `execute` tail)
- Test: `tests/test_macro_beta_use_case.py`

- [ ] **Step 1: Failing test** — inject fakes for analyzer + sector provider; assert populated fields.

```python
def test_execute_populates_enb_and_sector(monkeypatch):
    # Build a use case with a 2-holding book, fake price provider + estimator +
    # a RiskStatsAnalyzer(seed=0, bootstrap_iters=50) and a SectorProvider(fetcher=lambda t: "Information Technology").
    # ... (reuse existing test scaffolding in this file) ...
    result = use_case.execute(holdings, as_of)
    assert result is not None
    assert result.enb >= 1.0
    assert result.sector_weights  # non-empty
    assert abs(sum(result.risk_contribution.values()) - 1.0) < 1e-6 or result.risk_contribution == {}
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement** — extend the constructor to accept `risk_analyzer`, `sector_provider`, `history` (all injected), and after building `per_holding`/`book_head`, assemble the stats:
  - Build the aligned **holdings return matrix** from `holding_rets` (intersection dates) → `risk_analyzer.covariance_eigenvalues(matrix)` → `effective_number_of_bets(eigs)`, `pc_variance = top-3 eigenvalues / Σeigenvalues`.
  - `pc_labels`: add `risk_analyzer.principal_loadings(matrix, k=3)` → for each of the top-3 eigenvectors, the ticker(s) with the largest absolute loading; map each to a human label via the **dominant sector** of its top loaders (e.g. top loaders all "Information Technology" → "Big-tech market beta"). If a PC has no clear dominant sector (loadings spread / <60% one sector), emit the generic label `"Bet N"` and set a `pc_labels_data_gap=True` flag so `_enb_section` shows the DATA-GAP fallback instead of an invented name. This keeps the named-bets honest (no fabricated story when the math is inconclusive).
  - The ENB drill "how to raise it" needs no new field — `_enb_section` reuses `sector_gaps` (computed below) for the "axes you're empty on" list.
  - `systematic_share_adj = adjusted_r2(book_head[1], n=window, p=len(factors))`; `systematic_share_ci = risk_analyzer.bootstrap_r2_ci(yb, fb, alpha)`.
  - `beta_ci_by_factor = risk_analyzer.beta_cis(yb, fb, alpha)`; `suppressed = {f for f,(lo,hi) in cis.items() if lo < 0 < hi}`.
  - `downside_beta = risk_analyzer.downside_beta(yb, fb["SPY"])` (guard if SPY absent).
  - `risk_contribution`: from holdings covariance + weights via numpy in the analyzer (`marginal = Σw`), then `risk_contributions(...)` (domain) → map to tickers.
  - `vif_by_factor`: per factor regress-on-others R² (analyzer helper) → `vif_from_r2`.
  - `diversification_ratio`: weighted-avg holding vol / book vol (analyzer).
  - `sector_weights/sector_hhi/sector_gaps`: from `sector_provider.sector(t)` over weights; HHI = Σ w_s²; gaps = standard GICS list minus present sectors.
  - `holdings_meta`: ticker, name, sector, weight per holding.
  - `sys_share_history`: `history.load(...)` (passed in) appended with current point.
  - Pass all into `aggregate_macro_exposure` (extend its signature to accept + forward them, defaulting to current behavior when absent).

- [ ] **Step 4: Run → PASS.** `pytest tests/test_macro_beta_use_case.py -v`
- [ ] **Step 5: Commit**
```bash
git add application/macro_beta_use_case.py domain/macro_beta.py tests/test_macro_beta_use_case.py
git commit -m "feat: compute ENB/CIs/risk-contribution/sector stats in macro use case"
```

---

## Task 9: Serialize new fields + write history

**Files:**
- Modify: `application/brief_summary.py:55-71`, `application/cli.py` (weekly-brief)
- Test: `tests/test_brief_summary.py` (create if absent)

- [ ] **Step 1: Failing test**

```python
def test_macro_block_serializes_new_fields():
    from application.brief_summary import brief_to_summary_dict
    # build a WeeklyBrief whose macro is a populated BookMacroExposure (reuse a factory)
    d = brief_to_summary_dict(brief)["macro"]
    for key in ("enb", "pc_variance", "pc_labels", "pc_labels_data_gap", "systematic_share_adj", "systematic_share_ci",
                "beta_ci_by_factor", "suppressed_factors", "downside_beta",
                "risk_contribution", "holdings_meta", "sector_weights", "sector_hhi",
                "sector_gaps", "vif_by_factor", "diversification_ratio", "sys_share_history"):
        assert key in d
```

- [ ] **Step 2: Run → FAIL. Step 3:** add the keys to the `macro` dict in `brief_to_summary_dict` (mirror existing pattern; convert tuples→lists, dict CI tuples→lists). In `cli.py weekly-brief`, after computing macro, call `append_systematic_share(MACRO_HISTORY_PATH, macro.as_of, macro.systematic_share)`.

- [ ] **Step 4: Run → PASS. Step 5: Commit**
```bash
git add application/brief_summary.py application/cli.py tests/test_brief_summary.py
git commit -m "feat: serialize v8 macro stats + persist weekly history"
```

---

## Task 10: Glossary terms + status-first CSS tokens

**Files:**
- Modify: `adapters/visualization/components/glossary.py`, `adapters/visualization/components/styles.py`
- Test: `tests/test_glossary_complete.py`

- [ ] **Step 1: Failing test** — assert each new term resolves via `tooltip()`:

```python
def test_new_risk_terms_present():
    from adapters.visualization.components.glossary import GLOSSARY
    for term in ["Effective bets", "Adjusted R²", "Bootstrap band", "Downside beta",
                 "Risk contribution", "VIF", "Diversification ratio", "HHI", "GICS sector",
                 "Drift", "Risk line", "Coverage", "Systematic share", "Net beta", "Concentration"]:
        assert term in GLOSSARY and GLOSSARY[term]
```

- [ ] **Step 2: Run → FAIL. Step 3:** add the 15 definitions (plain-English, no FORBIDDEN_WORDS), copying the tooltip copy already written in the mockup. Add status-first CSS to `styles.py`: vars `--risk-ok:#15803d; --risk-amber:#b45309; --risk-g0:#E2E8F0; --risk-g1:#94A3B8; --risk-g2:#475569;` and classes for status banner, vitals strip, dials, band CI band, factor whiskers, ENB block, sector bars, AI panel — porting the `<style>` rules from `docs/superpowers/mockups/risk-v8.html`.

- [ ] **Step 4: Run → PASS. Step 5: Commit**
```bash
git add adapters/visualization/components/glossary.py adapters/visualization/components/styles.py tests/test_glossary_complete.py
git commit -m "feat: risk glossary terms + status-first CSS tokens"
```

---

## Task 11: Risk Google-AI second opinion (attributed, fail-safe)

**Files:**
- Create: `application/risk_second_opinion.py`, `adapters/visualization/components/risk_second_opinion.py`
- Test: `tests/application/test_risk_second_opinion.py`, `tests/components/test_risk_second_opinion_render.py`

- [ ] **Step 1: Failing tests**

```python
def test_template_fallback_no_forbidden_words():
    from application.risk_second_opinion import build_risk_second_opinion
    from domain.fit import FORBIDDEN_WORDS
    res = build_risk_second_opinion(macro_facts=["systematic share 71%"], summarizer=None)
    text = " ".join(p.text for p in res.in_favor + res.to_watch).lower()
    assert not any(w in text for w in FORBIDDEN_WORDS)

def test_render_hidden_when_not_local(monkeypatch):
    from adapters.visualization.components.risk_second_opinion import render_risk_second_opinion
    monkeypatch.setattr("adapters.visualization.components.risk_second_opinion.is_local_runtime", lambda: False)
    assert render_risk_second_opinion(result=None) == ""   # nothing rendered off-local
```

- [ ] **Step 2: Run → FAIL. Step 3:** implement reusing `select_case_summarizer()` + `CaseContext`/`CaseResult` with a risk prompt ("name blind spots in this risk read; do NOT use buy/sell/predict/…"); cache key `risk_second_opinion` via `case_cache`; render mirrors `render_gemini_read` but titled "Second opinion · Google AI" with `ATTRIBUTED · RESEARCH ONLY` badge + the fail-safe footer. Gate the render on `is_local_runtime()`.

- [ ] **Step 4: Run → PASS. Step 5: Commit**
```bash
git add application/risk_second_opinion.py adapters/visualization/components/risk_second_opinion.py tests/application/test_risk_second_opinion.py tests/components/test_risk_second_opinion_render.py
git commit -m "feat: attributed risk second-opinion (Gemini reuse, fail-safe, local-only)"
```

---

## Task 12: Rewrite the Risk tab render (v8 layout)

**Files:**
- Modify: `adapters/visualization/tabs/risk.py` (full render rewrite)
- Test: `tests/test_risk_tab.py`

Port each section's HTML from `docs/superpowers/mockups/risk-v8.html` into Python render helpers. Keep one private helper per page section, **composed in this exact order to match the mockup** (verified against the approved screenshot 2026-06-15):

`_header` → `_status_banner` → `_contract_legend` → `_vitals` → `_lens_nav` → `_standing` → `_dials` → `_grill_drill` → `_evidence_bands` → **`_factor_chart` → `_enb_section`** (factor chart comes BEFORE ENB, as in the mockup) → `_sector_section` → `_who_owns` → `_drift` → `render_risk_second_opinion(...)` → `_teach` → `_flags_footer`.

Each takes typed args from the loaded `macro` dict and returns an HTML string; `render()` composes them in that order. Reuse `tooltip()` for every jargon term; call `render_risk_second_opinion(...)` for the AI panel.

**`_status_banner` two states:** amber "N of your risk lines are crossed" when `flags` non-empty; **green "All clear — nothing crossing a line"** when `flags` empty (N = len(flags)). Always show the "MEASURED VS · the market (β=1.0) · your risk lines · last week" sub-text.

**`_enb_section` actionable drill-down** (the part the user specifically asked to be reactable): render the big `enb`, the `pc_variance` bars labeled with `pc_labels`, and an expandable that (a) names each of the top-3 bets from `pc_labels` with its variance share, and (b) a "how to raise it" block that lists the **axes the book is empty on** — reuse `macro["sector_gaps"]` (descriptive, `NOT A BUY CALL`) — plus the fixed copy "trading within Bet 1 (tech-for-tech) leaves ENB flat." If `pc_labels` are generic (only "PC1/PC2/PC3" because loadings were inconclusive), fall back to "Bet 1 / Bet 2 / Bet 3" with the variance shares and a DATA-GAP note instead of inventing names.

**`_who_owns`** shows BOTH the risk share (`risk_contribution[ticker]`) and the dollar weight (`holdings_meta[].weight`) so the "RISK ≠ $" contrast (e.g. "14% of risk on ~9% of dollars") is real, not asserted.

- [ ] **Step 1: Failing tests** (extend existing additivity tests)

```python
def test_risk_tab_renders_full_macro_v8(monkeypatch):
    # stub load_brief_summary to return a fully-populated v8 macro dict
    from adapters.visualization.tabs import risk
    html = risk._compose(macro)             # pure string composer (testable without Streamlit)
    for needle in ["Effective bets", "Systematic share", "Who owns the bet",
                   "DESCRIPTIVE", "heuristic surfacing dial"]:
        assert needle in html

def test_risk_tab_no_forbidden_words():
    from domain.fit import FORBIDDEN_WORDS
    html = risk._compose(macro).lower()
    assert not any(w in html for w in FORBIDDEN_WORDS)

def test_risk_tab_thin_macro_back_compat():
    # macro missing the new keys → no crash, sections that need them show DATA-GAP
    html = risk._compose(thin_macro)
    assert "DATA-GAP" in html or "building history" in html

def test_risk_tab_none_macro_safe():
    html = risk._compose(None)
    assert "weekly-brief" in html        # the existing safe-fallback warning text
```

- [ ] **Step 2: Run → FAIL. Step 3:** implement `_compose(macro) -> str` + the section helpers (porting mockup HTML), and `render()` that calls `load_brief_summary`, then `st.markdown(_compose(macro), unsafe_allow_html=True)` and the AI panel. Each new-stat section guards on presence → DATA-GAP / "building history" when absent (esp. `sys_share_history` < 3 points). Keep the ADR-052 heuristic line + honesty footer verbatim.

- [ ] **Step 4: Run → PASS.** `pytest tests/test_risk_tab.py -v`
- [ ] **Step 5: Commit**
```bash
git add adapters/visualization/tabs/risk.py tests/test_risk_tab.py
git commit -m "feat: rewrite Risk tab to v8 status-first layout"
```

---

## Task 13: Config + wiring + privacy tripwire

**Files:**
- Modify: `config/markets/us.yaml`, `application/cli.py` (wire analyzer/sector/history into the use case), `tests/application/test_runtime_guard.py`

- [ ] **Step 1:** add to `us.yaml`:
```yaml
risk_stats:
  bootstrap_iters: 500
  seed: 7
```
- [ ] **Step 2: Failing privacy test** — extend tripwire: risk second-opinion render is empty when `is_local_runtime()` False (already covered in Task 11; add an integration assertion that the tab `_compose` never embeds AI HTML when the panel returns "").
- [ ] **Step 3:** wire `RiskStatsAnalyzer(seed, bootstrap_iters)`, `SectorProvider()`, history path into the `_build_weekly_brief` construction of `MacroBetaUseCase` in `cli.py`. Read `risk_stats` from config.
- [ ] **Step 4: Run** `pytest tests/application/ -v` → PASS.
- [ ] **Step 5: Commit**
```bash
git add config/markets/us.yaml application/cli.py tests/application/test_runtime_guard.py
git commit -m "feat: wire risk-stats deps + config + privacy tripwire"
```

---

## Task 14: Full verification + live eyeball

**Files:** none (verification)

- [ ] **Step 1: Full quality gate**

Run: `make check`
Expected: ruff clean, mypy --strict clean, pytest coverage ≥90% PASS. `git checkout data/reports/` if tracked JSONs churn.

- [ ] **Step 2: Regenerate data + run the app**

```bash
python -m application.cli weekly-brief
STOCKREC_LOCAL_ONLY=1 streamlit run adapters/visualization/dashboard.py
```
Open the **Risk** tab. Confirm against `docs/superpowers/mockups/risk-v8.html`: status banner, vitals (ENB/downside/CI), dials, bootstrap band, factor whiskers + `≈0` suppression, ENB drill-down naming the ~3 bets, sector gaps tagged `NOT A BUY CALL`, who-owns = risk contribution, drift sparkline (or "building history"), Google-AI panel (only if `GEMINI_API_KEY` + local), tooltips on every term.

- [ ] **Step 3: Honesty audit**

Run: `grep -rinE "\b(buy|sell|winner|conviction|predict|alpha|outperform)\b" adapters/visualization/tabs/risk.py adapters/visualization/components/risk_second_opinion.py`
Expected: no matches in rendered strings (the FORBIDDEN_WORDS in `domain/fit.py` definition itself is fine).

- [ ] **Step 4: requesting-code-review** (Opus) per project standard, then finishing-a-development-branch (PR to `develop`, stacking on PR #58 per ADR memory). Before main: confirm no surface presents risk character as a good/bad grade.

---

## Self-Review (completed by author)

- **Spec coverage:** every §2 page section → Task 12 helper; every §3 stat → Tasks 1–4, 8; data contract §4 → Tasks 7, 9; reuse §5 honored (no rebuild of Gemini/tooltip/styles); new build §6 → Tasks 4–6, 10, 11; rails §1/§8 → Tasks 11, 12, 13 + honesty tests; dependencies §11: sector (Task 5, offline fallback), bootstrap cost (config iters, seeded), history bootstrap ("building history" guard Task 12), factor-count (renders config factors, no hardcoded 9 — Task 12 iterates `net_beta_by_factor`).
- **Placeholder scan:** Tasks 8/12 describe section assembly at helper granularity rather than full inline HTML — by design, the exact HTML/CSS lives in the committed `docs/superpowers/mockups/risk-v8.html` (port, don't reinvent); all *math* tasks (1–6) carry complete code.
- **Type consistency:** `BookMacroExposure` field names (Task 7) match serializer keys (Task 9), analyzer method names (`covariance_eigenvalues`, `bootstrap_r2_ci`, `beta_cis`, `downside_beta`) match their callers (Task 8), domain fns (`adjusted_r2`, `effective_number_of_bets`, `risk_contributions`, `vif_from_r2`, `diversification_ratio`) match Task 8 usage.
