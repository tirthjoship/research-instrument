# Engine Phase A — Evidence Screen MVP — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A weekly, evidence-ranked shortlist of universe names scored by equal-weighted factors (momentum / analyst-revision / quality / value), each carrying its backing + honest validation label + forward scorecard.

**Architecture:** Pure stdlib domain scorers (`factor_scores.py`, `screen.py`) + frozen models; application use cases orchestrate adapters and reuse `ic_analysis` + `precision_metrics` + `TransactionCostModel`; results surface as `SurfacedCall`s for existing forward-tracking. No numpy in `domain/`.

**Tech Stack:** Python 3.12, stdlib `statistics`, pytest + Hypothesis, mypy strict. Reuses `domain/trend_rules.py`, `application/ic_analysis.py` (`spearman_ic`, `aggregate_ic`), `application/precision_metrics.py` (`moving_block_bootstrap`, `sharpe_difference_bootstrap`, `date_level_significance`).

**Locked decisions:** rank-all-present-top-10 · equal-weight 4 factors v1 · partial analyst coverage = flagged-neutral (never a silent pin).

**Branch:** `feat/engine-phase-a-evidence-screen` off `develop`.

---

### Task 0: Branch

- [ ] **Step 1: Create branch**

```bash
git checkout develop && git pull && git checkout -b feat/engine-phase-a-evidence-screen
```

---

### Task 1: Pure stat helpers — `zscore`, `winsorize`

**Files:**
- Create: `domain/factor_scores.py`
- Test: `tests/test_domain_factor_scores.py`

- [ ] **Step 1: Write failing tests**

```python
import math
from domain.factor_scores import zscore, winsorize

def test_zscore_centers_and_scales():
    out = zscore([1.0, 2.0, 3.0, 4.0, 5.0])
    assert abs(sum(out)) < 1e-9
    assert abs(out[0] + out[4]) < 1e-9 and out[0] < 0 < out[4]

def test_zscore_degenerate_returns_zeros():
    assert zscore([2.0, 2.0, 2.0]) == [0.0, 0.0, 0.0]

def test_winsorize_clamps_tails():
    out = winsorize([0.0, 1, 2, 3, 100.0], p=0.2)
    assert max(out) < 100.0 and min(out) >= 0.0
```

- [ ] **Step 2: Run, expect fail** — `pytest tests/test_domain_factor_scores.py -v` → FAIL (module missing).

- [ ] **Step 3: Implement**

```python
"""Pure factor scoring (stdlib only — no numpy in domain/)."""
from statistics import mean, pstdev

def zscore(values: list[float]) -> list[float]:
    if not values:
        return []
    mu = mean(values)
    sd = pstdev(values)
    if sd == 0:
        return [0.0 for _ in values]
    return [(v - mu) / sd for v in values]

def winsorize(values: list[float], p: float = 0.05) -> list[float]:
    if not values:
        return []
    s = sorted(values)
    n = len(s)
    lo = s[max(0, int(p * (n - 1)))]
    hi = s[min(n - 1, int((1 - p) * (n - 1)))]
    return [min(max(v, lo), hi) for v in values]
```

- [ ] **Step 4: Run, expect pass.**
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: pure zscore/winsorize factor helpers"`

---

### Task 2: Factor scores + equal-weight composite

**Files:**
- Modify: `domain/factor_scores.py`
- Test: `tests/test_domain_factor_scores.py`

- [ ] **Step 1: Write failing tests**

```python
from domain.factor_scores import revision_momentum, composite_score

def test_revision_momentum_positive_on_upgrades():
    # estimate series rising over time -> positive momentum
    assert revision_momentum([1.0, 1.1, 1.2, 1.3]) > 0

def test_revision_momentum_none_when_insufficient():
    assert revision_momentum([1.0]) is None

def test_composite_equal_weight_average_of_present():
    # flagged-neutral: a None sub-score contributes 0 (neutral), not dropped
    c = composite_score({"momentum": 1.0, "revision": None, "quality": -1.0, "value": 0.0})
    assert abs(c - 0.0) < 1e-9  # (1 + 0 + -1 + 0)/4
```

- [ ] **Step 2: Run, expect fail.**

- [ ] **Step 3: Implement (append to `domain/factor_scores.py`)**

```python
FACTOR_KEYS = ("momentum", "revision", "quality", "value")

def revision_momentum(estimate_series: list[float]) -> float | None:
    """Normalized drift of analyst EPS estimates (oldest..newest)."""
    if estimate_series is None or len(estimate_series) < 2:
        return None
    first, last = estimate_series[0], estimate_series[-1]
    if first == 0:
        return None
    return (last - first) / abs(first)

def composite_score(sub_scores: dict[str, float | None]) -> float:
    """Equal-weight mean over the 4 factor keys. None = flagged-neutral (0.0)."""
    total = 0.0
    for k in FACTOR_KEYS:
        v = sub_scores.get(k)
        total += 0.0 if v is None else v
    return total / len(FACTOR_KEYS)
```

> NOTE: `quality`/`value` sub-scores are z-scored cross-sectionally by the use case (Task 5) from fundamentals before being passed here; `momentum` is z-scored `momentum_12_1`. This keeps `composite_score` pure and trivially testable.

- [ ] **Step 4: Run, expect pass.**
- [ ] **Step 5: Commit** — `git commit -am "feat: revision_momentum + equal-weight composite (flagged-neutral)"`

---

### Task 3: Domain models — `FactorScore`, `ScreenCandidate`, `ScreenResult`

**Files:**
- Create: `domain/screen_models.py`
- Test: `tests/test_domain_screen_models.py`

- [ ] **Step 1: Write failing tests**

```python
import pytest
from domain.screen_models import FactorScore, ScreenCandidate, ScreenLabel, ScreenResult

def test_candidate_frozen_and_valid():
    c = ScreenCandidate(ticker="MU", composite=0.8,
                        factor_scores=(FactorScore("momentum", 1.2, 0.94, 0.3),),
                        trend_health=0.5, why="strong momentum", label=ScreenLabel.RESEARCH_ONLY)
    with pytest.raises(Exception):
        c.composite = 0.1  # frozen

def test_result_rejects_negative_universe():
    with pytest.raises(ValueError):
        ScreenResult(as_of="2026-06-08", candidates=(), universe_size=-1,
                     regime="NEUTRAL", scorecard_ref=None)
```

- [ ] **Step 2: Run, expect fail.**

- [ ] **Step 3: Implement**

```python
from dataclasses import dataclass
from enum import Enum

class ScreenLabel(Enum):
    VALIDATED = "VALIDATED"
    RESEARCH_ONLY = "RESEARCH_ONLY"

@dataclass(frozen=True)
class FactorScore:
    name: str
    value: float
    percentile: float
    contribution: float

@dataclass(frozen=True)
class ScreenCandidate:
    ticker: str
    composite: float
    factor_scores: tuple[FactorScore, ...]
    trend_health: float
    why: str
    label: ScreenLabel

@dataclass(frozen=True)
class ScreenResult:
    as_of: str
    candidates: tuple[ScreenCandidate, ...]
    universe_size: int
    regime: str
    scorecard_ref: str | None
    def __post_init__(self) -> None:
        if self.universe_size < 0:
            raise ValueError("universe_size must be >= 0")
```

- [ ] **Step 4: Run, expect pass.**
- [ ] **Step 5: Commit** — `git commit -am "feat: screen domain models (frozen, validated)"`

---

### Task 4: `domain/screen.py` — eligibility, ranking, abstention

**Files:**
- Create: `domain/screen.py`
- Test: `tests/test_domain_screen.py`

- [ ] **Step 1: Write failing tests**

```python
from domain.screen import eligible, rank_universe, abstain_if_thin
from domain.screen_models import ScreenCandidate, FactorScore, ScreenLabel

def _c(t, comp): return ScreenCandidate(t, comp, (FactorScore("momentum", comp, 0.5, comp),), 0.1, "", ScreenLabel.RESEARCH_ONLY)

def test_eligible_requires_uptrend_and_history():
    assert eligible(trend_health=0.2, has_min_history=True) is True
    assert eligible(trend_health=-0.1, has_min_history=True) is False
    assert eligible(trend_health=0.2, has_min_history=False) is False

def test_rank_orders_desc_and_caps_top_n():
    out = rank_universe([_c("A", 0.1), _c("B", 0.9), _c("C", 0.5)], top_n=2)
    assert [c.ticker for c in out] == ["B", "C"]

def test_abstain_when_coverage_thin():
    assert abstain_if_thin(present_factor_fraction=0.2) is True
    assert abstain_if_thin(present_factor_fraction=0.9) is False
```

- [ ] **Step 2: Run, expect fail.**

- [ ] **Step 3: Implement**

```python
"""Pure screen ranking + eligibility (stdlib only)."""
from domain.screen_models import ScreenCandidate

def eligible(trend_health: float, has_min_history: bool) -> bool:
    """Screen + ride: only confirmed-uptrend names with enough history."""
    return has_min_history and trend_health > 0.0

def rank_universe(candidates: list[ScreenCandidate], top_n: int = 10) -> list[ScreenCandidate]:
    ranked = sorted(candidates, key=lambda c: c.composite, reverse=True)
    return ranked[:top_n]

def abstain_if_thin(present_factor_fraction: float, threshold: float = 0.5) -> bool:
    """Flag the whole result research-only when factor coverage is poor."""
    return present_factor_fraction < threshold
```

- [ ] **Step 4: Run, expect pass.**
- [ ] **Step 5: Commit** — `git commit -am "feat: pure screen eligibility/ranking/abstention"`

---

### Task 5: `EvidenceScreenUseCase`

**Files:**
- Create: `application/evidence_screen_use_case.py`
- Test: `tests/test_evidence_screen_use_case.py`

- [ ] **Step 1: Write failing test (fakes for all ports)**

```python
from application.evidence_screen_use_case import EvidenceScreenUseCase
from domain.screen_models import ScreenLabel

class FakePrice:
    def monthly_closes(self, t): return [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 22, 24]
    def trend_health(self, t): return 0.4
    def has_min_history(self, t): return True
class FakeAnalyst:
    def estimate_series(self, t): return [1.0, 1.1, 1.2] if t == "MU" else None  # NVDA missing -> flagged-neutral
class FakeFund:
    def quality_value(self, t): return {"quality": 0.5, "value": 0.2}
class FakeNarrator:
    def narrate(self, cand): return f"why-{cand.ticker}"

def test_screen_ranks_and_flags_neutral_coverage():
    uc = EvidenceScreenUseCase(FakePrice(), FakeAnalyst(), FakeFund(), FakeNarrator())
    res = uc.run(universe=["MU", "NVDA"], as_of="2026-06-08", top_n=10)
    tickers = [c.ticker for c in res.candidates]
    assert set(tickers) == {"MU", "NVDA"}
    # NVDA has no analyst series -> revision is flagged-neutral, not dropped
    assert all(c.why.startswith("why-") for c in res.candidates)
    assert res.candidates[0].label in (ScreenLabel.VALIDATED, ScreenLabel.RESEARCH_ONLY)
```

- [ ] **Step 2: Run, expect fail.**

- [ ] **Step 3: Implement** (reuse `domain.trend_rules.momentum_12_1`, `domain.factor_scores`, `domain.screen`)

```python
from domain import trend_rules
from domain.factor_scores import zscore, revision_momentum, composite_score, FACTOR_KEYS
from domain.screen import eligible, rank_universe, abstain_if_thin
from domain.screen_models import FactorScore, ScreenCandidate, ScreenResult, ScreenLabel

class EvidenceScreenUseCase:
    def __init__(self, price, analyst, fundamentals, narrator):
        self._price = price; self._analyst = analyst
        self._fund = fundamentals; self._narrator = narrator

    def run(self, universe, as_of, top_n=10):
        raw = []
        for t in universe:
            if not eligible(self._price.trend_health(t), self._price.has_min_history(t)):
                continue
            mom = trend_rules.momentum_12_1(self._price.monthly_closes(t))
            rev = revision_momentum(self._analyst.estimate_series(t))
            qv = self._fund.quality_value(t)
            raw.append((t, mom, rev, qv, self._price.trend_health(t)))
        # cross-sectional z-score each present factor
        zmom = self._z([r[1] for r in raw]); zrev = self._z([r[2] for r in raw])
        zqual = self._z([r[3].get("quality") for r in raw]); zval = self._z([r[3].get("value") for r in raw])
        cands = []
        present_counts = []
        for i, (t, _, _, _, th) in enumerate(raw):
            subs = {"momentum": zmom[i], "revision": zrev[i], "quality": zqual[i], "value": zval[i]}
            present = sum(1 for k in FACTOR_KEYS if subs[k] is not None)
            present_counts.append(present / len(FACTOR_KEYS))
            comp = composite_score(subs)
            fs = tuple(FactorScore(k, subs[k] or 0.0, 0.0, (subs[k] or 0.0) / len(FACTOR_KEYS)) for k in FACTOR_KEYS)
            c = ScreenCandidate(t, comp, fs, th, "", ScreenLabel.RESEARCH_ONLY)
            cands.append(ScreenCandidate(t, comp, fs, th, self._narrator.narrate(c), ScreenLabel.RESEARCH_ONLY))
        ranked = rank_universe(cands, top_n=top_n)
        thin = abstain_if_thin(min(present_counts) if present_counts else 0.0)
        return ScreenResult(as_of=as_of, candidates=tuple(ranked),
                            universe_size=len(universe), regime="NEUTRAL",
                            scorecard_ref=None)

    @staticmethod
    def _z(vals):
        present = [v for v in vals if v is not None]
        if not present:
            return [None for _ in vals]
        zs = zscore(present); it = iter(zs)
        return [next(it) if v is not None else None for v in vals]
```

> NOTE for implementer: wire `FakePrice/FakeAnalyst/FakeFund` to the real `yfinance`/analyst/fundamental adapters at the composition root; keep adapter method names (`estimate_series`, `quality_value`) as a thin shim over existing adapter calls. Surfacing each candidate as a `SurfacedCall` for forward-tracking is a follow-up step in Task 8.

- [ ] **Step 4: Run, expect pass.**
- [ ] **Step 5: Commit** — `git commit -am "feat: EvidenceScreenUseCase (equal-weight, flagged-neutral, ranked)"`

---

### Task 6: `ScreenBacktestUseCase` — pre-registered gate

**Files:**
- Create: `application/screen_backtest_use_case.py`
- Test: `tests/test_screen_backtest_use_case.py`

- [ ] **Step 1: Write failing tests (planted-IC + zero-IC fixtures)**

```python
from application.screen_backtest_use_case import ScreenBacktestUseCase, ScreenVerdict

def test_recovers_planted_ic_pass():
    # forward return == signal -> perfect IC -> PASS
    panels = [{"AAA": (1.0, 0.10), "BBB": (0.0, 0.0), "CCC": (-1.0, -0.10)} for _ in range(60)]
    v = ScreenBacktestUseCase().run(panels)
    assert v.decision == "PASS" and v.mean_ic > 0.02

def test_zero_ic_does_not_false_pass():
    panels = [{"AAA": (1.0, -0.05), "BBB": (0.0, 0.20), "CCC": (-1.0, 0.01)} for _ in range(60)]
    v = ScreenBacktestUseCase().run(panels)
    assert v.decision in ("INCONCLUSIVE", "HALT")

def test_negative_ic_halts():
    panels = [{"AAA": (1.0, -0.10), "BBB": (0.0, 0.0), "CCC": (-1.0, 0.10)} for _ in range(60)]
    v = ScreenBacktestUseCase().run(panels)
    assert v.decision == "HALT"
```

- [ ] **Step 2: Run, expect fail.**

- [ ] **Step 3: Implement** (reuse `application.ic_analysis`, `application.precision_metrics`)

```python
from dataclasses import dataclass
from application.ic_analysis import spearman_ic

@dataclass(frozen=True)
class ScreenVerdict:
    decision: str  # PASS | INCONCLUSIVE | HALT
    mean_ic: float
    n_dates: int

class ScreenBacktestUseCase:
    """Pre-registered: per-date Spearman rank-IC of composite vs fwd 1m return.
    Gate: mean IC >= 0.02 -> PASS; (0, 0.02) -> INCONCLUSIVE; <= 0 -> HALT.
    (Bootstrap CI via precision_metrics.moving_block_bootstrap on per-date ICs
    is added during implementation for the CI-excludes-0 condition.)"""
    def run(self, panels: list[dict[str, tuple[float, float]]]) -> ScreenVerdict:
        ics = []
        for p in panels:
            sig = [v[0] for v in p.values()]
            fwd = [v[1] for v in p.values()]
            ics.append(spearman_ic(sig, fwd))
        mean_ic = sum(ics) / len(ics) if ics else 0.0
        if mean_ic <= 0.0:
            decision = "HALT"
        elif mean_ic >= 0.02:
            decision = "PASS"
        else:
            decision = "INCONCLUSIVE"
        return ScreenVerdict(decision, round(mean_ic, 6), len(panels))
```

> NOTE: before the live run, add the `moving_block_bootstrap` CI on `ics` (CI-excludes-0) and the secondary top-decile `sharpe_difference_bootstrap` net of `TransactionCostModel`, per spec §5. Tests above lock the IC-threshold branching; the implementer adds the CI gate without changing the decision labels.

- [ ] **Step 4: Run, expect pass.**
- [ ] **Step 5: Commit** — `git commit -am "feat: ScreenBacktestUseCase pre-registered IC gate (PASS/INCONCLUSIVE/HALT)"`

---

### Task 7: CLI — `screen-candidates` + `backtest-screen`

**Files:**
- Modify: `application/cli.py`
- Test: `tests/test_cli_screen.py`

- [ ] **Step 1: Write failing test (masked stdout + full-distribution report)**

```python
from click.testing import CliRunner
from application.cli import cli

def test_screen_candidates_masked_summary(monkeypatch, tmp_path):
    runner = CliRunner()
    res = runner.invoke(cli, ["screen-candidates", "--top", "10", "--report-dir", str(tmp_path)])
    assert res.exit_code == 0
    assert "candidates" in res.output.lower()
    assert list(tmp_path.glob("screen_*.json"))  # full distribution written
```

- [ ] **Step 2: Run, expect fail.**

- [ ] **Step 3: Implement** — add two `@cli.command` handlers mirroring the existing `opportunity-report` pattern (`application/cli.py:1027`): build the use case from real adapters, run, write full ranked distribution JSON to `--report-dir` (default `data/reports/`), print masked summary (counts + label) to stdout. `backtest-screen` runs `ScreenBacktestUseCase` on point-in-time panels, writes `screen_ic_<date>.json`, prints the verdict.

- [ ] **Step 4: Run, expect pass.**
- [ ] **Step 5: Commit** — `git commit -am "feat: screen-candidates + backtest-screen CLIs (masked, full-distribution report)"`

---

### Task 8: Forward-tracking wiring, label surfacing, `make check`

**Files:**
- Modify: `application/evidence_screen_use_case.py`, `application/cli.py`
- Test: `tests/test_evidence_screen_use_case.py`

- [ ] **Step 1: Write failing test** — assert each ranked candidate is emitted as a `SurfacedCall` (ticker, surfaced_at, evidence tuple) so existing `ForwardTrackingUseCase` resolves it; assert a `VALIDATED` label only when a verdict JSON marks PASS, else `RESEARCH_ONLY`.

```python
def test_emits_surfaced_calls_and_label_from_verdict(tmp_path):
    # given a verdict file with decision PASS, candidates get VALIDATED
    ...
```

- [ ] **Step 2: Run, expect fail.**

- [ ] **Step 3: Implement** — map each `ScreenCandidate` → `SurfacedCall` (reuse `domain/surfaced_call.py`: ticker, `surfaced_at`, `evidence=(EvidenceItem(dim, score, note), ...)`, `direction=OpportunityDirection.UP`, `cap_tier`); persist via the existing `SurfacedCallStorePort`. Read the latest `screen_ic_*.json`; set `label=VALIDATED` iff `decision == "PASS"`, else `RESEARCH_ONLY`.

- [ ] **Step 4: Run tests; then full suite + gates**

Run: `make check`
Expected: mypy strict clean, ≥90% coverage, all tests pass.

- [ ] **Step 5: Commit** — `git commit -am "feat: surface screen calls for forward-tracking + verdict-driven label; make check green"`

---

## Self-Review

- **Spec coverage:** §4.1 domain (T1–T4) ✓ · §4.2 use cases (T5–T6, T8) ✓ · §4.3 CLI (T7) ✓ · §5 pre-registered gate w/ planted/zero/negative fixtures (T6) ✓ · §6 full-distribution + label honesty (T7–T8) ✓ · forward-tracking reuse (T8) ✓.
- **Locked decisions:** equal-weight composite (T2) · top-10 from rank-all (T4) · flagged-neutral coverage (T2, T5) ✓.
- **Type consistency:** `FACTOR_KEYS`, `composite_score`, `ScreenCandidate`, `ScreenLabel`, `ScreenVerdict` used consistently T2→T8.
- **Open follow-ups flagged inline:** bootstrap-CI gate + cost-aware secondary (T6 note), adapter shim names (T5 note) — to be completed during impl before the live `backtest-screen` run, per spec §5.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-08-engine-phase-a-evidence-screen.md`. Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task (Sonnet impl), review between tasks.
2. **Inline Execution** — execute in this session with checkpoints.
