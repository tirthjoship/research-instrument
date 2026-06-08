# Holdings Discipline & Risk Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a graded, calibrated, regime-aware risk/discipline assessment for currently-held positions (decision-support, not prediction) that interrupts disposition-effect mistakes, surfaces book-level concentration, narrates the why via a free local LLM, and logs verdicts so its calibration can be forward-tracked.

**Architecture:** Hexagonal. Pure scorers + grading + calibration in `domain/` (stdlib only). Orchestration in `application/` injecting a price provider (live yfinance / fakes in tests) and a `NarratorPort`. A local-LLM narrator adapter with a graceful templated no-op default. Reuses `domain/trend_rules.py`, `domain/backtest_metrics.py`, `application/price_returns.load_price_series`, and the `.TO` symbol mapping already used by `_get_backtest_universe`.

**Tech Stack:** Python 3.12, stdlib (`statistics`, `math`, `json`, `csv`), yfinance (prices), click (CLI), pytest + Hypothesis, mypy strict, optional Ollama over HTTP (urllib).

**Spec:** `docs/superpowers/specs/2026-06-08-holdings-discipline-risk-engine-design.md`

**Conventions:** `domain/` pure (stdlib only — no numpy/pandas); adapters/use-cases may import libs; tests use fakes/fixtures, never live APIs; FROZEN trend params reused from ADR-046 (200-day trend, ATR(22), 3×ATR Chandelier) — do NOT re-tune; holdings + all derived/output files stay under `data/personal/` (gitignored); only ticker symbols ever reach yfinance; commit after each green task; READ a file before modifying and match real signatures.

---

## File Structure

- Modify `domain/trend_rules.py` — add `ma_slope`, `relative_strength`, `trend_health` (pure).
- Create `domain/discipline.py` — `Verdict` enum, `conditional_vol_signal`, `risk_asymmetry`, `is_disposition_risk`, `is_winner_past_stop`, `grade_position` (pure).
- Create `domain/calibration.py` — `base_rate_from_history`, `brier_score`, `calibration_bins` (pure).
- Modify `domain/models.py` — add `PositionRisk`, `PortfolioRisk` frozen dataclasses.
- Modify `domain/ports.py` — add `NarratorPort` protocol.
- Create `application/narrator.py` — `template_narration` default + `FakeNarrator`.
- Create `adapters/ml/ollama_narrator.py` — `OllamaNarratorAdapter` (graceful no-op).
- Create `application/holdings_reader.py` — `Holding` dataclass + `read_holdings`.
- Create `application/holdings_risk.py` — `HoldingsRiskAssessmentUseCase`.
- Create `application/discipline_log.py` — append/read JSONL assessment log + `resolve_flags`.
- Modify `application/cli.py` — `holdings-risk`, `holdings-risk-calibrate`, `resolve-discipline-flags` commands.
- Tests: `tests/test_trend_rules.py` (additions), `tests/test_discipline.py`, `tests/test_calibration.py`, `tests/test_models.py` (additions or new `tests/test_discipline_models.py`), `tests/test_narrator.py`, `tests/test_holdings_reader.py`, `tests/test_holdings_risk.py`, `tests/test_discipline_log.py`, `tests/test_opportunity_cli.py` (additions).

---

## Phase A — Domain scorers (pure)

### Task 1: `trend_rules` — ma_slope, relative_strength, trend_health

**Files:**
- Modify: `domain/trend_rules.py`
- Test: `tests/test_trend_rules.py`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_trend_rules.py`)

```python
def test_trend_health_positive_above_trend():
    from domain.trend_rules import trend_health
    # price 110, sma 100, atr 5 -> (110-100)/5 = 2.0 ATRs above trend
    assert trend_health(110.0, 100.0, 5.0) == 2.0

def test_trend_health_negative_below_trend():
    from domain.trend_rules import trend_health
    assert trend_health(90.0, 100.0, 5.0) == -2.0

def test_trend_health_none_when_inputs_missing():
    from domain.trend_rules import trend_health
    assert trend_health(100.0, None, 5.0) is None
    assert trend_health(100.0, 100.0, None) is None
    assert trend_health(100.0, 100.0, 0.0) is None

def test_ma_slope_rising():
    from domain.trend_rules import ma_slope
    # rising series -> SMA now > SMA `window` bars ago -> positive slope
    vals = [float(i) for i in range(1, 21)]  # 1..20
    assert ma_slope(vals, 5) > 0

def test_ma_slope_none_when_insufficient():
    from domain.trend_rules import ma_slope
    assert ma_slope([1.0, 2.0, 3.0], 5) is None

def test_relative_strength_outperformer_positive():
    from domain.trend_rules import relative_strength
    asset = [100.0, 110.0, 120.0]      # +20% over 2 bars
    bench = [100.0, 100.0, 110.0]      # +10% over 2 bars
    assert abs(relative_strength(asset, bench, 2) - 0.10) < 1e-9

def test_relative_strength_none_when_insufficient():
    from domain.trend_rules import relative_strength
    assert relative_strength([1.0], [1.0], 5) is None
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_trend_rules.py -k "trend_health or ma_slope or relative_strength" -v`
Expected: FAIL (ImportError on the new names)

- [ ] **Step 3: Implement (append to `domain/trend_rules.py`)**

```python
def trend_health(
    price: float, sma_value: float | None, atr_value: float | None
) -> float | None:
    """Signed distance of price from the trend line in ATR units.
    Positive = above trend, negative = below. None if inputs unavailable."""
    if sma_value is None or atr_value is None or atr_value <= 0:
        return None
    return (price - sma_value) / atr_value


def ma_slope(values: list[float], window: int) -> float | None:
    """Normalized change in the SMA from `window` bars ago to now.
    Needs >= 2*window values. None if too few or the older SMA is non-positive."""
    if window <= 0 or len(values) < 2 * window:
        return None
    sma_now = sum(values[-window:]) / window
    sma_then = sum(values[-2 * window : -window]) / window
    if sma_then <= 0:
        return None
    return (sma_now - sma_then) / sma_then


def relative_strength(
    asset_closes: list[float], benchmark_closes: list[float], window: int
) -> float | None:
    """Asset return minus benchmark return over the last `window` bars.
    Needs > window closes in each. None if insufficient or a base price is non-positive."""
    if window <= 0 or len(asset_closes) <= window or len(benchmark_closes) <= window:
        return None
    a0, a1 = asset_closes[-window - 1], asset_closes[-1]
    b0, b1 = benchmark_closes[-window - 1], benchmark_closes[-1]
    if a0 <= 0 or b0 <= 0:
        return None
    return (a1 / a0 - 1.0) - (b1 / b0 - 1.0)
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_trend_rules.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add domain/trend_rules.py tests/test_trend_rules.py
git commit -m "feat: trend_rules trend_health + ma_slope + relative_strength (pure)"
```

---

### Task 2: `domain/discipline.py` — conditional vol signal + risk asymmetry

**Files:**
- Create: `domain/discipline.py`
- Test: `tests/test_discipline.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_conditional_vol_signal_zero_when_trend_healthy():
    from domain.discipline import conditional_vol_signal
    # vol elevated but trend positive -> NO de-risk (the TSX-safe conditional rule)
    assert conditional_vol_signal(recent_vol=0.04, baseline_vol=0.02, trend_health=1.5) == 0.0

def test_conditional_vol_signal_zero_when_vol_not_elevated():
    from domain.discipline import conditional_vol_signal
    assert conditional_vol_signal(recent_vol=0.01, baseline_vol=0.02, trend_health=-1.0) == 0.0

def test_conditional_vol_signal_positive_when_vol_up_and_trend_down():
    from domain.discipline import conditional_vol_signal
    # recent 2x baseline, trend negative -> de-risk, capped at 1.0
    sig = conditional_vol_signal(recent_vol=0.04, baseline_vol=0.02, trend_health=-1.0)
    assert 0.0 < sig <= 1.0

def test_risk_asymmetry_fields():
    from domain.discipline import risk_asymmetry
    out = risk_asymmetry(price=100.0, trailing_stop=90.0, recent_high=130.0)
    assert abs(out["downside_to_stop"] - 0.10) < 1e-9   # (100-90)/100
    assert abs(out["upside_to_recover"] - 0.30) < 1e-9   # (130-100)/100
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_discipline.py -v`
Expected: FAIL `ModuleNotFoundError: domain.discipline`

- [ ] **Step 3: Implement**

```python
"""Pure discipline/risk grading primitives (stdlib only). The deterministic core
computes verdicts; the LLM narrator only explains them, never produces them."""

from __future__ import annotations

from enum import Enum


def conditional_vol_signal(
    recent_vol: float, baseline_vol: float, trend_health: float | None
) -> float:
    """De-risk weight in [0,1]. NON-ZERO ONLY when volatility is elevated AND the
    trend is deteriorating (trend_health < 0). High vol alone never de-risks —
    this is the conditional form that is safe on TSX/non-US markets (conventional
    vol-targeting backfires there; see spec)."""
    if trend_health is None or trend_health >= 0:
        return 0.0
    if baseline_vol <= 0 or recent_vol <= baseline_vol:
        return 0.0
    return min(1.0, recent_vol / baseline_vol - 1.0)


def risk_asymmetry(
    price: float, trailing_stop: float | None, recent_high: float
) -> dict[str, float]:
    """Factual asymmetry framing (not a forecast):
    downside_to_stop = fraction at risk before the trailing stop fires;
    upside_to_recover = fraction needed to revisit the recent high."""
    downside = (
        (price - trailing_stop) / price
        if (trailing_stop is not None and price > 0)
        else 0.0
    )
    upside = (recent_high - price) / price if price > 0 else 0.0
    return {"downside_to_stop": downside, "upside_to_recover": upside}
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_discipline.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add domain/discipline.py tests/test_discipline.py
git commit -m "feat: discipline conditional_vol_signal + risk_asymmetry (pure)"
```

---

### Task 3: `domain/discipline.py` — behavior detectors + graded verdict

**Files:**
- Modify: `domain/discipline.py`
- Test: `tests/test_discipline.py`

- [ ] **Step 1: Write the failing tests** (append)

```python
def test_disposition_risk_broken_trend_at_loss():
    from domain.discipline import is_disposition_risk
    assert is_disposition_risk(trend_health=-2.0, unrealized_pct=-0.30) is True
    assert is_disposition_risk(trend_health=1.0, unrealized_pct=-0.30) is False  # in trend
    assert is_disposition_risk(trend_health=-2.0, unrealized_pct=0.50) is False  # at a gain

def test_winner_past_stop():
    from domain.discipline import is_winner_past_stop
    assert is_winner_past_stop(trend_health=1.5, price=95.0, trailing_stop=96.0) is True
    assert is_winner_past_stop(trend_health=1.5, price=100.0, trailing_stop=96.0) is False
    assert is_winner_past_stop(trend_health=-1.0, price=95.0, trailing_stop=96.0) is False

def test_grade_reduce_when_broken_trend_loss_and_market_ok():
    from domain.discipline import grade_position, Verdict
    v, conf, abstained = grade_position(
        trend_health=-3.0, vol_signal=0.5, relative_strength=-0.2,
        disposition=True, winner_past_stop=False, market_trend_health=1.0,
    )
    assert v == Verdict.REDUCE
    assert abstained is False
    assert 0.0 < conf <= 1.0

def test_grade_abstains_to_review_when_market_also_broken():
    from domain.discipline import grade_position, Verdict
    # name weak BUT whole market weak too -> can't attribute to the name -> REVIEW/abstain
    v, conf, abstained = grade_position(
        trend_health=-3.0, vol_signal=0.5, relative_strength=0.1,
        disposition=True, winner_past_stop=False, market_trend_health=-2.5,
    )
    assert v == Verdict.REVIEW
    assert abstained is True

def test_grade_trim_for_winner_past_stop():
    from domain.discipline import grade_position, Verdict
    v, conf, abstained = grade_position(
        trend_health=1.2, vol_signal=0.0, relative_strength=0.1,
        disposition=False, winner_past_stop=True, market_trend_health=1.0,
    )
    assert v == Verdict.TRIM

def test_grade_hold_when_in_trend():
    from domain.discipline import grade_position, Verdict
    v, conf, abstained = grade_position(
        trend_health=2.5, vol_signal=0.0, relative_strength=0.3,
        disposition=False, winner_past_stop=False, market_trend_health=1.0,
    )
    assert v in (Verdict.HOLD, Verdict.ADD_OK)

def test_grade_review_when_trend_health_none():
    from domain.discipline import grade_position, Verdict
    v, conf, abstained = grade_position(
        trend_health=None, vol_signal=0.0, relative_strength=None,
        disposition=False, winner_past_stop=False, market_trend_health=None,
    )
    assert v == Verdict.REVIEW
    assert abstained is True
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_discipline.py -k "disposition or winner_past or grade" -v`
Expected: FAIL (ImportError)

- [ ] **Step 3: Implement (append to `domain/discipline.py`)**

```python
class Verdict(str, Enum):
    REDUCE = "REDUCE"      # broken trend, discipline says cut
    TRIM = "TRIM"          # in trend but breached trailing stop
    REVIEW = "REVIEW"      # mixed/abstain — human judgement needed
    HOLD = "HOLD"          # trend intact
    ADD_OK = "ADD_OK"      # strong trend + leading the market


# below this many ATRs under the trend line a position is "clearly broken"
_BROKEN_TREND_ATR = 2.0
# above this many ATRs over the trend line it is "clearly strong"
_STRONG_TREND_ATR = 1.5


def is_disposition_risk(trend_health: float | None, unrealized_pct: float) -> bool:
    """The classic hold-a-loser pattern: trend broken AND position held at a loss."""
    return trend_health is not None and trend_health < 0 and unrealized_pct < 0


def is_winner_past_stop(
    trend_health: float | None, price: float, trailing_stop: float | None
) -> bool:
    """In an uptrend but price has breached the trailing stop — trim/tighten."""
    return (
        trend_health is not None
        and trend_health > 0
        and trailing_stop is not None
        and price <= trailing_stop
    )


def grade_position(
    trend_health: float | None,
    vol_signal: float,
    relative_strength: float | None,
    disposition: bool,
    winner_past_stop: bool,
    market_trend_health: float | None,
) -> tuple[Verdict, float, bool]:
    """Combine sub-scores into a graded verdict + confidence in [0,1] + abstained flag.
    ABSTAINS to REVIEW when signals conflict (notably: the name is weak but the whole
    market is weak too, so weakness can't be attributed to the name)."""
    # No trend read at all -> abstain.
    if trend_health is None:
        return Verdict.REVIEW, 0.2, True

    market_broken = market_trend_health is not None and market_trend_health < 0

    # Name weak, but market also weak -> can't attribute to the name -> abstain.
    if trend_health < 0 and market_broken:
        return Verdict.REVIEW, 0.3, True

    # Winner that breached its trailing stop -> trim.
    if winner_past_stop:
        conf = min(1.0, 0.5 + abs(trend_health) / 10.0)
        return Verdict.TRIM, conf, False

    # Clearly broken trend (and market is fine) -> reduce.
    if trend_health <= -_BROKEN_TREND_ATR and (disposition or vol_signal > 0.0):
        depth = min(1.0, abs(trend_health) / 4.0)
        conf = min(1.0, 0.5 + 0.5 * depth)
        return Verdict.REDUCE, conf, False

    # Clearly strong + leading the market -> ok to hold/add.
    if trend_health >= _STRONG_TREND_ATR and (relative_strength or 0.0) > 0.0:
        conf = min(1.0, 0.5 + trend_health / 6.0)
        return Verdict.ADD_OK, conf, False

    # Mild negative without confirmation, or middling -> hold (with low conf if mixed).
    if trend_health < 0:
        return Verdict.HOLD, 0.4, False
    return Verdict.HOLD, 0.6, False
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_discipline.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add domain/discipline.py tests/test_discipline.py
git commit -m "feat: discipline behavior detectors + graded verdict with abstention (pure)"
```

---

### Task 4: `domain/calibration.py` — history base rates + Brier

**Files:**
- Create: `domain/calibration.py`
- Test: `tests/test_calibration.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_brier_score_perfect_is_zero():
    from domain.calibration import brier_score
    assert brier_score([1.0, 0.0, 1.0], [1, 0, 1]) == 0.0

def test_brier_score_worst_is_one():
    from domain.calibration import brier_score
    assert brier_score([0.0, 1.0], [1, 0]) == 1.0

def test_brier_score_empty_is_zero():
    from domain.calibration import brier_score
    assert brier_score([], []) == 0.0

def test_base_rate_from_history_buckets_downtrend_higher_down_rate():
    from domain.calibration import base_rate_from_history
    # Build a monotonically falling series: every point is below its own trailing trend,
    # and forward returns are negative -> the "below" bucket should show a high down_rate.
    closes = [float(100 - i) for i in range(0, 60)]  # 100,99,...,41
    out = base_rate_from_history(closes, trend_window=10, atr_window=10, horizon=5)
    assert "below" in out
    assert out["below"]["n"] > 0
    assert 0.0 <= out["below"]["down_rate"] <= 1.0
    assert out["below"]["down_rate"] > 0.5  # falling series -> mostly down forward
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_calibration.py -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
"""Pure calibration helpers (stdlib only): historical base-rate priors (point-in-time,
no look-ahead) and Brier/reliability scoring of discipline flags."""

from __future__ import annotations

from .trend_rules import atr, sma, trend_health


def brier_score(predicted_probs: list[float], outcomes: list[int]) -> float:
    """Mean squared error between predicted P(event) and realized 0/1 outcomes."""
    n = min(len(predicted_probs), len(outcomes))
    if n == 0:
        return 0.0
    return sum((predicted_probs[i] - outcomes[i]) ** 2 for i in range(n)) / n


def base_rate_from_history(
    closes: list[float], trend_window: int, atr_window: int, horizon: int
) -> dict[str, dict[str, float]]:
    """Walk the series point-in-time. At each day with enough history, bucket the day
    by trend_health sign (`above`/`below`) using ONLY past+current closes, then look
    `horizon` days forward to record the realized return. No look-ahead: the forward
    window is never used to form the bucket. Returns per-bucket n, mean_fwd_return,
    down_rate (fraction of forward returns < 0)."""
    need = max(trend_window, atr_window)
    buckets: dict[str, list[float]] = {"above": [], "below": []}
    for i in range(need, len(closes) - horizon):
        window = closes[: i + 1]  # point-in-time: up to and including day i
        th = trend_health(closes[i], sma(window, trend_window), atr(window, window, window, atr_window))
        if th is None:
            continue
        fwd = closes[i + horizon] / closes[i] - 1.0 if closes[i] > 0 else 0.0
        buckets["above" if th >= 0 else "below"].append(fwd)
    out: dict[str, dict[str, float]] = {}
    for name, rets in buckets.items():
        if not rets:
            continue
        out[name] = {
            "n": float(len(rets)),
            "mean_fwd_return": sum(rets) / len(rets),
            "down_rate": sum(1 for r in rets if r < 0) / len(rets),
        }
    return out
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_calibration.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add domain/calibration.py tests/test_calibration.py
git commit -m "feat: calibration base_rate_from_history + brier_score (pure, point-in-time)"
```

---

## Phase B — Domain models

### Task 5: `models` — PositionRisk + PortfolioRisk

**Files:**
- Modify: `domain/models.py`
- Test: `tests/test_discipline_models.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_position_risk_construction():
    from domain.models import PositionRisk
    from domain.discipline import Verdict
    pr = PositionRisk(
        ticker="MU", price=100.0, verdict=Verdict.REDUCE, confidence=0.8,
        trend_health=-3.0, vol_signal=0.5, relative_strength=-0.2,
        downside_to_stop=0.1, upside_to_recover=0.3, behavior_flags=("disposition_risk",),
        unrealized_pct=-0.31, account_type="TFSA", abstained=False, why="broke trend",
    )
    assert pr.ticker == "MU"
    assert pr.verdict == Verdict.REDUCE

def test_position_risk_rejects_bad_confidence():
    import pytest
    from domain.models import PositionRisk
    from domain.discipline import Verdict
    with pytest.raises(Exception):
        PositionRisk(
            ticker="MU", price=100.0, verdict=Verdict.HOLD, confidence=1.5,
            trend_health=0.0, vol_signal=0.0, relative_strength=0.0,
            downside_to_stop=0.0, upside_to_recover=0.0, behavior_flags=(),
            unrealized_pct=0.0, account_type="TFSA", abstained=False, why="",
        )

def test_portfolio_risk_construction():
    from domain.models import PortfolioRisk
    prisk = PortfolioRisk(
        n_positions=10, broken_trend_share=0.6, top_concentration=0.45,
        verdict_counts={"REDUCE": 3, "HOLD": 7},
    )
    assert prisk.n_positions == 10
    assert prisk.broken_trend_share == 0.6
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_discipline_models.py -v`
Expected: FAIL (ImportError on PositionRisk/PortfolioRisk)

- [ ] **Step 3: Implement (append to `domain/models.py`)**

Add the import at the top of `domain/models.py` (with the existing imports):
```python
from .discipline import Verdict
```
Then append:
```python
@dataclass(frozen=True)
class PositionRisk:
    """Graded risk/discipline assessment for one held position (decision-support,
    not a prediction)."""

    ticker: str
    price: float
    verdict: Verdict
    confidence: float
    trend_health: float | None
    vol_signal: float
    relative_strength: float | None
    downside_to_stop: float
    upside_to_recover: float
    behavior_flags: tuple[str, ...]
    unrealized_pct: float
    account_type: str
    abstained: bool
    why: str

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise InvalidPredictionError(
                f"Confidence must be in [0, 1], got {self.confidence}"
            )


@dataclass(frozen=True)
class PortfolioRisk:
    """Book-level risk summary across all held positions."""

    n_positions: int
    broken_trend_share: float
    top_concentration: float
    verdict_counts: dict[str, int]
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_discipline_models.py -v`
Expected: PASS (3 passed)

Also run `mypy domain/models.py domain/discipline.py` — expect clean (no import cycle: `models` imports `discipline`, `discipline` imports only stdlib + enum; `calibration` imports `trend_rules`; no cycle).

- [ ] **Step 5: Commit**

```bash
git add domain/models.py tests/test_discipline_models.py
git commit -m "feat: PositionRisk + PortfolioRisk domain models"
```

---

## Phase C — Narrator port + reader + use case

### Task 6: `NarratorPort` + default templated narrator + fake

**Files:**
- Modify: `domain/ports.py`
- Create: `application/narrator.py`
- Test: `tests/test_narrator.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_template_narration_mentions_verdict_and_ticker():
    from application.narrator import template_narration
    ctx = {
        "ticker": "MU", "verdict": "REDUCE", "trend_health": -3.0,
        "unrealized_pct": -0.31, "account_type": "TFSA",
        "downside_to_stop": 0.1, "upside_to_recover": 0.3, "behavior_flags": ["disposition_risk"],
    }
    text = template_narration(ctx)
    assert "MU" in text and "REDUCE" in text
    assert "TFSA" in text  # account context surfaced

def test_fake_narrator_cannot_change_verdict():
    from application.narrator import FakeNarrator
    n = FakeNarrator(canned="explained")
    # narrate receives an already-computed context; it returns prose only
    assert n.narrate({"ticker": "X", "verdict": "HOLD"}) == "explained"
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_narrator.py -v`
Expected: FAIL `ModuleNotFoundError: application.narrator`

- [ ] **Step 3: Implement**

Append to `domain/ports.py` (READ the file first; it uses `typing.Protocol` for the other ports — match that style):
```python
class NarratorPort(Protocol):
    """Explains an ALREADY-COMPUTED verdict in plain English. Receives the computed
    context only; it cannot influence the verdict (structural guarantee the LLM
    narrates, never picks)."""

    def narrate(self, context: dict[str, object]) -> str: ...
```
Create `application/narrator.py`:
```python
"""Default templated narrator + a fake for tests. The real local-LLM adapter lives
in adapters/ml/ollama_narrator.py and falls back to template_narration on any error."""

from __future__ import annotations


def template_narration(context: dict[str, object]) -> str:
    """Deterministic plain-English explanation built from the computed context.
    Used as the graceful default when no LLM is available."""
    t = context.get("ticker", "?")
    v = context.get("verdict", "REVIEW")
    th = context.get("trend_health")
    unreal = context.get("unrealized_pct")
    acct = context.get("account_type", "")
    flags = context.get("behavior_flags") or []
    parts: list[str] = [f"{t}: {v}."]
    if isinstance(th, (int, float)):
        where = "above" if th >= 0 else "below"
        parts.append(f"Price is {abs(float(th)):.1f} ATRs {where} its 200-day trend.")
    if isinstance(unreal, (int, float)):
        parts.append(f"Position is {float(unreal) * 100:+.0f}% vs cost.")
    if "disposition_risk" in flags:
        parts.append("This is the hold-a-loser pattern — broken trend held at a loss.")
    if "winner_past_stop" in flags:
        parts.append("Winner that breached its trailing stop — consider trimming.")
    if acct and str(acct).upper() in {"TFSA", "RRSP", "FHSA"}:
        parts.append(f"In a {acct}, there is no capital-gains tax friction on selling.")
    return " ".join(parts)


class FakeNarrator:
    """Test double implementing NarratorPort."""

    def __init__(self, canned: str = "narration") -> None:
        self._canned = canned

    def narrate(self, context: dict[str, object]) -> str:
        return self._canned
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_narrator.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add domain/ports.py application/narrator.py tests/test_narrator.py
git commit -m "feat: NarratorPort + templated default narrator + FakeNarrator"
```

---

### Task 7: `application/holdings_reader.py` — CSV → holdings

**Files:**
- Create: `application/holdings_reader.py`
- Test: `tests/test_holdings_reader.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_read_holdings_maps_tsx_suffix_and_parses(tmp_path):
    from application.holdings_reader import read_holdings
    p = tmp_path / "h.csv"
    p.write_text(
        "Symbol,Quantity,Book Value (CAD),Market Value,Account Type,Exchange\n"
        "RY,10,1000,1200,TFSA,TSX\n"
        "AAPL,5,500,800,RRSP,NASDAQ\n"
        "BRK.B,2,600,700,Non-registered,NYSE\n"
        ",0,0,0,TFSA,?\n"  # blank symbol -> skipped
    )
    hs = read_holdings(str(p))
    by = {h.ticker: h for h in hs}
    assert "RY.TO" in by            # TSX gets .TO
    assert "AAPL" in by             # US bare
    assert "BRK-B" in by            # class share dot -> dash
    assert len(hs) == 3             # blank-symbol row skipped
    assert by["RY.TO"].account_type == "TFSA"
    assert by["RY.TO"].cost_basis == 1000.0

def test_read_holdings_missing_file_returns_empty(tmp_path):
    from application.holdings_reader import read_holdings
    assert read_holdings(str(tmp_path / "nope.csv")) == []
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_holdings_reader.py -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
"""Read a brokerage holdings CSV into domain-friendly Holding rows. Maps broker
symbols to yfinance tickers (TSX -> .TO, class shares dot -> dash). PRIVACY: this
only reads a local gitignored file; nothing is transmitted here."""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Holding:
    ticker: str
    shares: float
    cost_basis: float
    account_type: str


_TSX = {"TSX", "TSE", "XTSE"}
_TSXV = {"TSXV", "XTSX", "CVE"}
_US = {"NASDAQ", "NYSE", "BATS", "AMEX", "ARCA", "XNAS", "XNYS"}


def _get(row: dict[str, str], name: str) -> str:
    for k, v in row.items():
        if k.strip().lower() == name:
            return (v or "").strip()
    return ""


def _to_yf(symbol: str, exchange: str) -> str:
    base = symbol.replace(".", "-")  # class shares: BRK.B -> BRK-B
    ex = exchange.upper()
    if ex in _TSX:
        return f"{base}.TO"
    if ex in _TSXV:
        return f"{base}.V"
    return base


def read_holdings(path: str) -> list[Holding]:
    """Parse the CSV; skip blank-symbol / non-numeric-quantity / zero-share rows."""
    if not os.path.exists(path):
        return []
    out: list[Holding] = []
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            sym = _get(row, "symbol")
            if not sym:
                continue
            try:
                shares = float(_get(row, "quantity").replace(",", ""))
            except ValueError:
                continue
            if shares == 0:
                continue
            try:
                cost = float(_get(row, "book value (cad)").replace(",", "") or 0)
            except ValueError:
                cost = 0.0
            out.append(
                Holding(
                    ticker=_to_yf(sym, _get(row, "exchange")),
                    shares=shares,
                    cost_basis=cost,
                    account_type=_get(row, "account type") or _get(row, "account classification"),
                )
            )
    return out
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_holdings_reader.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add application/holdings_reader.py tests/test_holdings_reader.py
git commit -m "feat: holdings_reader (broker CSV -> yfinance-mapped Holding rows)"
```

---

### Task 8: `HoldingsRiskAssessmentUseCase`

**Files:**
- Create: `application/holdings_risk.py`
- Test: `tests/test_holdings_risk.py`

- [ ] **Step 1: Write the failing test**

```python
from datetime import datetime, timedelta, timezone

def _series(start, vals):
    return [(start + timedelta(days=i), float(v)) for i, v in enumerate(vals)]

def test_assess_flags_broken_trend_loser_as_reduce():
    from application.holdings_risk import HoldingsRiskAssessmentUseCase
    from application.holdings_reader import Holding
    from application.narrator import FakeNarrator
    from domain.discipline import Verdict
    start = datetime(2023, 1, 1, tzinfo=timezone.utc)
    # name rises then falls hard and ends well below its 200d trend; market stays healthy
    name_vals = list(range(100, 360)) + list(range(360, 200, -1))   # up then crash
    spy_vals = list(range(100, 100 + len(name_vals)))               # steady up
    series = {"WEAK": _series(start, name_vals), "SPY": _series(start, spy_vals)}
    def provider(t): return series.get(t, [])
    holdings = [Holding(ticker="WEAK", shares=10.0, cost_basis=3000.0, account_type="TFSA")]
    uc = HoldingsRiskAssessmentUseCase(price_provider=provider, narrator=FakeNarrator("why"))
    report = uc.execute(holdings, start, start + timedelta(days=len(name_vals)))
    pos = report["positions"][0]
    assert pos.ticker == "WEAK"
    assert pos.verdict in (Verdict.REDUCE, Verdict.REVIEW)  # broken trend
    assert report["portfolio"].n_positions == 1
    assert pos.why == "why"  # narrator wired

def test_assess_empty_holdings():
    from application.holdings_risk import HoldingsRiskAssessmentUseCase
    from application.narrator import FakeNarrator
    uc = HoldingsRiskAssessmentUseCase(price_provider=lambda t: [], narrator=FakeNarrator())
    start = datetime(2023, 1, 1, tzinfo=timezone.utc)
    report = uc.execute([], start, start + timedelta(days=10))
    assert report["positions"] == []
    assert report["portfolio"].n_positions == 0
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_holdings_risk.py -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
"""Assess currently-held positions: graded discipline verdict per holding +
book-level risk. Decision-support, not prediction (spec 2026-06-08)."""

from __future__ import annotations

import statistics
from datetime import datetime
from typing import Any, Callable

from application.holdings_reader import Holding
from application.narrator import template_narration
from domain.backtest_metrics import daily_returns
from domain.discipline import (
    Verdict,
    conditional_vol_signal,
    grade_position,
    is_disposition_risk,
    is_winner_past_stop,
    risk_asymmetry,
)
from domain.models import PortfolioRisk, PositionRisk
from domain.trend_rules import atr, chandelier_stop, relative_strength, sma, trend_health

PriceProvider = Callable[[str], list[tuple[datetime, float]]]

_TREND_WINDOW = 200
_ATR_WINDOW = 22
_ATR_MULT = 3.0
_RECENT_VOL = 22
_BASE_VOL = 252
_RS_WINDOW = 126


class _Narrator:
    def narrate(self, context: dict[str, object]) -> str: ...


class HoldingsRiskAssessmentUseCase:
    def __init__(
        self, price_provider: PriceProvider, narrator: _Narrator, benchmark: str = "SPY"
    ) -> None:
        self._prices = price_provider
        self._narrator = narrator
        self._benchmark = benchmark

    def _closes_in(self, ticker: str, start: datetime, end: datetime) -> list[float]:
        return [c for d, c in self._prices(ticker) if start <= d <= end]

    def _vol(self, returns: list[float], window: int) -> float:
        tail = returns[-window:]
        return statistics.pstdev(tail) if len(tail) >= 2 else 0.0

    def execute(
        self, holdings: list[Holding], start: datetime, end: datetime
    ) -> dict[str, Any]:
        bench_closes = self._closes_in(self._benchmark, start, end)
        market_th: float | None = None
        if len(bench_closes) >= _TREND_WINDOW:
            market_th = trend_health(
                bench_closes[-1],
                sma(bench_closes, _TREND_WINDOW),
                atr(bench_closes, bench_closes, bench_closes, _ATR_WINDOW),
            )

        positions: list[PositionRisk] = []
        for h in holdings:
            closes = self._closes_in(h.ticker, start, end)
            if len(closes) < _TREND_WINDOW:
                positions.append(self._insufficient(h))
                continue
            price = closes[-1]
            th = trend_health(
                price, sma(closes, _TREND_WINDOW), atr(closes, closes, closes, _ATR_WINDOW)
            )
            atr_v = atr(closes, closes, closes, _ATR_WINDOW)
            highest = max(closes[-_TREND_WINDOW:])
            stop = chandelier_stop(highest, atr_v, _ATR_MULT) if atr_v else None
            rets = daily_returns(closes)
            vol_sig = conditional_vol_signal(self._vol(rets, _RECENT_VOL), self._vol(rets, _BASE_VOL), th)
            rs = relative_strength(closes, bench_closes, _RS_WINDOW) if bench_closes else None
            unreal = (price * h.shares - h.cost_basis) / h.cost_basis if h.cost_basis > 0 else 0.0
            disp = is_disposition_risk(th, unreal)
            wps = is_winner_past_stop(th, price, stop)
            verdict, conf, abstained = grade_position(th, vol_sig, rs, disp, wps, market_th)
            asym = risk_asymmetry(price, stop, highest)
            flags = tuple(
                f for f, on in (("disposition_risk", disp), ("winner_past_stop", wps)) if on
            )
            ctx: dict[str, object] = {
                "ticker": h.ticker, "verdict": verdict.value, "trend_health": th,
                "unrealized_pct": unreal, "account_type": h.account_type,
                "downside_to_stop": asym["downside_to_stop"],
                "upside_to_recover": asym["upside_to_recover"], "behavior_flags": list(flags),
            }
            why = self._narrator.narrate(ctx) or template_narration(ctx)
            positions.append(
                PositionRisk(
                    ticker=h.ticker, price=price, verdict=verdict, confidence=conf,
                    trend_health=th, vol_signal=vol_sig, relative_strength=rs,
                    downside_to_stop=asym["downside_to_stop"], upside_to_recover=asym["upside_to_recover"],
                    behavior_flags=flags, unrealized_pct=unreal, account_type=h.account_type,
                    abstained=abstained, why=why,
                )
            )
        return {"positions": positions, "portfolio": self._portfolio(positions)}

    def _insufficient(self, h: Holding) -> PositionRisk:
        return PositionRisk(
            ticker=h.ticker, price=0.0, verdict=Verdict.REVIEW, confidence=0.1,
            trend_health=None, vol_signal=0.0, relative_strength=None,
            downside_to_stop=0.0, upside_to_recover=0.0, behavior_flags=(),
            unrealized_pct=0.0, account_type=h.account_type, abstained=True,
            why=f"{h.ticker}: not enough price history to assess.",
        )

    def _portfolio(self, positions: list[PositionRisk]) -> PortfolioRisk:
        n = len(positions)
        if n == 0:
            return PortfolioRisk(0, 0.0, 0.0, {})
        broken = sum(1 for p in positions if p.trend_health is not None and p.trend_health < 0)
        counts: dict[str, int] = {}
        for p in positions:
            counts[p.verdict.value] = counts.get(p.verdict.value, 0) + 1
        # lightweight concentration: largest single position by market value share
        values = [p.price for p in positions if p.price > 0]
        top = (max(values) / sum(values)) if values else 0.0
        return PortfolioRisk(
            n_positions=n, broken_trend_share=broken / n, top_concentration=top, verdict_counts=counts
        )
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_holdings_risk.py -v`
Expected: PASS (2 passed). Then `mypy application/holdings_risk.py` — clean.

- [ ] **Step 5: Commit**

```bash
git add application/holdings_risk.py tests/test_holdings_risk.py
git commit -m "feat: HoldingsRiskAssessmentUseCase (graded verdict + portfolio risk)"
```

---

## Phase D — Local LLM adapter

### Task 9: `OllamaNarratorAdapter` (graceful no-op)

**Files:**
- Create: `adapters/ml/ollama_narrator.py`
- Test: `tests/test_narrator.py` (additions)

- [ ] **Step 1: Write the failing tests** (append to `tests/test_narrator.py`)

```python
def test_ollama_falls_back_to_template_when_unreachable():
    from adapters.ml.ollama_narrator import OllamaNarratorAdapter
    # point at a closed port so the HTTP call fails -> graceful template fallback
    n = OllamaNarratorAdapter(base_url="http://127.0.0.1:9", model="x", timeout=0.2)
    ctx = {"ticker": "MU", "verdict": "REDUCE", "trend_health": -3.0,
           "unrealized_pct": -0.31, "account_type": "TFSA", "behavior_flags": ["disposition_risk"]}
    text = n.narrate(ctx)
    assert "MU" in text and "REDUCE" in text  # came from template_narration

def test_ollama_uses_model_text_when_available(monkeypatch):
    import adapters.ml.ollama_narrator as mod
    def fake_call(self, prompt):
        return "LLM SAYS: trim it"
    monkeypatch.setattr(mod.OllamaNarratorAdapter, "_call", fake_call, raising=True)
    n = mod.OllamaNarratorAdapter()
    assert n.narrate({"ticker": "X", "verdict": "TRIM"}) == "LLM SAYS: trim it"
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_narrator.py -k ollama -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
"""Local Ollama narrator adapter (NarratorPort). On ANY error (Ollama not running,
timeout, bad response) it falls back to the deterministic template — never raises,
never blocks the scheduled run. Zero API cost, on-device: holdings context never
leaves the machine. Narrates an already-computed verdict; cannot influence it."""

from __future__ import annotations

import json
import urllib.request

from application.narrator import template_narration

_SYSTEM = (
    "You explain a stock position's ALREADY-DECIDED risk verdict in 2-3 plain sentences. "
    "You do NOT predict prices or pick stocks. Use only the numbers given."
)


class OllamaNarratorAdapter:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        model: str = "llama3.1:8b",
        timeout: float = 20.0,
    ) -> None:
        self._url = base_url.rstrip("/") + "/api/generate"
        self._model = model
        self._timeout = timeout

    def _call(self, prompt: str) -> str:
        body = json.dumps(
            {"model": self._model, "prompt": prompt, "system": _SYSTEM, "stream": False}
        ).encode()
        req = urllib.request.Request(self._url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            data = json.loads(resp.read().decode())
        return str(data.get("response", "")).strip()

    def narrate(self, context: dict[str, object]) -> str:
        fallback = template_narration(context)
        try:
            prompt = f"Position context (JSON): {json.dumps(context)}\nExplain the verdict."
            text = self._call(prompt)
            return text or fallback
        except Exception:
            from loguru import logger

            logger.warning("Ollama narrator unavailable; using template fallback")
            return fallback
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_narrator.py -v`
Expected: PASS (all). Then `mypy adapters/ml/ollama_narrator.py` — clean.

- [ ] **Step 5: Commit**

```bash
git add adapters/ml/ollama_narrator.py tests/test_narrator.py
git commit -m "feat: OllamaNarratorAdapter (local, graceful template fallback)"
```

---

## Phase E — Persistence + CLI

### Task 10: `application/discipline_log.py` — append/read log + resolve flags

**Files:**
- Create: `application/discipline_log.py`
- Test: `tests/test_discipline_log.py`

- [ ] **Step 1: Write the failing tests**

```python
from datetime import datetime, timezone

def test_append_and_read_roundtrip(tmp_path):
    from application.discipline_log import append_assessments, read_assessments
    log = tmp_path / "log.jsonl"
    rows = [{"ticker": "MU", "verdict": "REDUCE", "price": 100.0,
             "as_of": "2026-06-08T00:00:00+00:00"}]
    append_assessments(str(log), rows)
    back = read_assessments(str(log))
    assert back[0]["ticker"] == "MU" and back[0]["verdict"] == "REDUCE"

def test_resolve_flags_scores_reduce_followed_by_drop(tmp_path):
    from application.discipline_log import resolve_flags
    # one past REDUCE flag; price later fell -> outcome "down" (1) -> good calibration
    logged = [{"ticker": "MU", "verdict": "REDUCE", "price": 100.0,
               "as_of": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat()}]
    # provider returns a falling series after the flag date
    series = {"MU": [(datetime(2026, 1, 1, tzinfo=timezone.utc), 100.0),
                     (datetime(2026, 2, 5, tzinfo=timezone.utc), 80.0)]}
    out = resolve_flags(logged, lambda t: series.get(t, []), horizon_days=21)
    assert out["resolved"] == 1
    assert 0.0 <= out["brier"] <= 1.0
    assert out["down_rate_on_reduce"] == 1.0  # the REDUCE flag was followed by a drop
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_discipline_log.py -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
"""Append-only JSONL log of discipline assessments (gitignored, local) + a resolver
that forward-scores past REDUCE/TRIM flags once enough time has elapsed. This is how
the engine's calibration is validated over time (spec §5). PRIVACY: file lives under
data/personal/ and is never committed."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from typing import Any, Callable

PriceProvider = Callable[[str], list[tuple[datetime, float]]]


def append_assessments(path: str, rows: list[dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a") as fh:
        for r in rows:
            fh.write(json.dumps(r, default=str) + "\n")


def read_assessments(path: str) -> list[dict[str, Any]]:
    if not os.path.exists(path):
        return []
    out: list[dict[str, Any]] = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def _price_on_or_after(series: list[tuple[datetime, float]], target: datetime) -> float | None:
    for d, c in series:
        if d >= target:
            return c
    return None


def resolve_flags(
    logged: list[dict[str, Any]], price_provider: PriceProvider, horizon_days: int = 21
) -> dict[str, Any]:
    """For each logged REDUCE/TRIM flag whose horizon has elapsed, check whether the
    price fell over the horizon. Score with Brier (a REDUCE/TRIM predicts 'down', p=1.0).
    Returns resolved count, brier, and down_rate_on_reduce."""
    probs: list[float] = []
    outcomes: list[int] = []
    down_on_reduce = 0
    reduce_n = 0
    for row in logged:
        if row.get("verdict") not in ("REDUCE", "TRIM"):
            continue
        as_of = datetime.fromisoformat(str(row["as_of"])).replace(tzinfo=None)
        series = [(d.replace(tzinfo=None), c) for d, c in price_provider(str(row["ticker"]))]
        entry = _price_on_or_after(series, as_of)
        later = _price_on_or_after(series, as_of + timedelta(days=horizon_days))
        if entry is None or later is None or entry <= 0:
            continue
        went_down = 1 if (later / entry - 1.0) < 0 else 0
        probs.append(1.0)  # the flag asserted 'down/at-risk'
        outcomes.append(went_down)
        reduce_n += 1
        down_on_reduce += went_down
    from domain.calibration import brier_score

    return {
        "resolved": len(outcomes),
        "brier": brier_score(probs, outcomes),
        "down_rate_on_reduce": (down_on_reduce / reduce_n) if reduce_n else 0.0,
    }
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_discipline_log.py -v`
Expected: PASS (2 passed). Then `mypy application/discipline_log.py` — clean.

- [ ] **Step 5: Commit**

```bash
git add application/discipline_log.py tests/test_discipline_log.py
git commit -m "feat: discipline_log (append/read JSONL + forward flag resolver + Brier)"
```

---

### Task 11: `holdings-risk` CLI (masked output + gitignored detail + log)

**Files:**
- Modify: `application/cli.py`
- Test: `tests/test_opportunity_cli.py`

- [ ] **Step 1: Write the failing test** (append to `tests/test_opportunity_cli.py`)

```python
def test_holdings_risk_cli_masked_summary(monkeypatch, tmp_path):
    from click.testing import CliRunner
    from application.cli import cli
    import application.cli as climod
    from domain.discipline import Verdict
    from domain.models import PositionRisk, PortfolioRisk

    holdings = tmp_path / "h.csv"
    holdings.write_text("Symbol,Quantity,Book Value (CAD),Account Type,Exchange\nMU,10,3000,TFSA,NASDAQ\n")

    class _UC:
        def __init__(self, *a, **k): pass
        def execute(self, hold, start, end):
            pos = PositionRisk(
                ticker="MU", price=100.0, verdict=Verdict.REDUCE, confidence=0.8,
                trend_health=-3.0, vol_signal=0.5, relative_strength=-0.2,
                downside_to_stop=0.1, upside_to_recover=0.3, behavior_flags=("disposition_risk",),
                unrealized_pct=-0.31, account_type="TFSA", abstained=False, why="broke trend",
            )
            return {"positions": [pos],
                    "portfolio": PortfolioRisk(1, 1.0, 1.0, {"REDUCE": 1})}
    monkeypatch.setattr(climod, "HoldingsRiskAssessmentUseCase", _UC, raising=False)

    runner = CliRunner()
    out_file = tmp_path / "detail.txt"
    result = runner.invoke(cli, ["holdings-risk", "--holdings", str(holdings),
                                 "--out", str(out_file)])
    assert result.exit_code == 0, result.output
    # masked stdout: shows the verdict distribution but NOT per-ticker detail
    assert "REDUCE" in result.output
    assert "MU" not in result.output            # ticker only in the file, not stdout
    assert out_file.exists()
    assert "MU" in out_file.read_text()         # full detail written to gitignored file
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_opportunity_cli.py -k holdings_risk -v`
Expected: FAIL (no such command)

- [ ] **Step 3: Implement**

Add module-level imports near the other use-case imports in `application/cli.py` (so monkeypatch works):
```python
from application.holdings_risk import HoldingsRiskAssessmentUseCase
```
Add the command (match the existing `@cli.command(...)` group style):
```python
@cli.command("holdings-risk")
@click.option("--holdings", default="data/personal/holdings-report-2026-06-07.csv",
              show_default=True, help="Local broker CSV — gitignored, never committed")
@click.option("--out", default="data/personal/holdings_risk_detail.txt", show_default=True,
              help="Full per-ticker detail (gitignored). Stdout stays masked.")
@click.option("--log", default="data/personal/discipline_log.jsonl", show_default=True,
              help="Append assessments here for forward calibration (gitignored)")
@click.option("--narrate", is_flag=True, help="Use local Ollama narrator (else template)")
def holdings_risk(holdings, out, log, narrate):
    """Graded risk/discipline assessment of your holdings (decision-support, not prediction).
    Masked stdout (verdict distribution only); full detail to the gitignored --out file."""
    import os
    from datetime import datetime, timezone
    from application.holdings_reader import read_holdings
    from application.price_returns import load_price_series
    from application.narrator import FakeNarrator
    from application.discipline_log import append_assessments

    rows = read_holdings(holdings)
    if not rows:
        click.echo(f"No holdings at {holdings} (ticker/Symbol + Quantity). It is gitignored.")
        return
    start_dt = datetime(2018, 1, 1, tzinfo=timezone.utc)
    end_dt = datetime.now(timezone.utc)

    _cache: dict[str, list] = {}
    def provider(ticker):
        if ticker not in _cache:
            _cache[ticker] = load_price_series(ticker, start_dt, end_dt)
        return _cache[ticker]

    if narrate:
        from adapters.ml.ollama_narrator import OllamaNarratorAdapter
        narrator = OllamaNarratorAdapter()
    else:
        narrator = FakeNarrator("")  # empty -> use case falls back to template_narration

    uc = HoldingsRiskAssessmentUseCase(provider, narrator)
    report = uc.execute(rows, start_dt, end_dt)
    positions = report["positions"]
    pf = report["portfolio"]

    # full detail -> gitignored file
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w") as f:
        f.write(f"{'TICKER':10} {'VERDICT':8} {'TREND':>6} {'UNREAL':>8}  WHY\n")
        for p in positions:
            th = f"{p.trend_health:+.1f}" if p.trend_health is not None else "  -"
            f.write(f"{p.ticker:10} {p.verdict.value:8} {th:>6} {p.unrealized_pct*100:+7.0f}%  {p.why}\n")

    # append to forward-calibration log
    now_iso = end_dt.isoformat()
    append_assessments(log, [
        {"ticker": p.ticker, "verdict": p.verdict.value, "price": p.price,
         "trend_health": p.trend_health, "as_of": now_iso} for p in positions
    ])

    # masked stdout: distribution + book-level risk only (NO tickers)
    click.echo(f"Assessed {pf.n_positions} positions. Verdict distribution: {pf.verdict_counts}")
    click.echo(f"Broken-trend share: {pf.broken_trend_share:.0%}  Top concentration: {pf.top_concentration:.0%}")
    click.echo(f"Full per-ticker detail written to {out} (gitignored).")
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_opportunity_cli.py -k holdings_risk -v`
Expected: PASS. Then full `pytest tests/test_opportunity_cli.py -q` (no regressions) and `mypy application/cli.py` (clean).

- [ ] **Step 5: Commit**

```bash
git add application/cli.py tests/test_opportunity_cli.py
git commit -m "feat: holdings-risk CLI (masked summary + gitignored detail + calibration log)"
```

---

### Task 12: `resolve-discipline-flags` CLI + warm-start calibration CLI

**Files:**
- Modify: `application/cli.py`
- Test: `tests/test_opportunity_cli.py`

- [ ] **Step 1: Write the failing test** (append)

```python
def test_resolve_discipline_flags_cli(monkeypatch, tmp_path):
    from click.testing import CliRunner
    from application.cli import cli
    import application.cli as climod

    log = tmp_path / "log.jsonl"
    log.write_text(
        '{"ticker": "MU", "verdict": "REDUCE", "price": 100.0, "as_of": "2026-01-01T00:00:00+00:00"}\n'
    )
    monkeypatch.setattr(
        climod, "load_price_series",
        lambda t, s, e: [
            (__import__("datetime").datetime(2026, 1, 1), 100.0),
            (__import__("datetime").datetime(2026, 3, 1), 70.0),
        ],
        raising=False,
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["resolve-discipline-flags", "--log", str(log)])
    assert result.exit_code == 0, result.output
    assert "resolved" in result.output.lower()
    assert "brier" in result.output.lower()
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_opportunity_cli.py -k resolve_discipline -v`
Expected: FAIL (no such command)

- [ ] **Step 3: Implement**

Add a module-level import (so the monkeypatch target exists on the module):
```python
from application.price_returns import load_price_series
```
(If `load_price_series` is already imported at module level, skip; otherwise add it.) Then add the commands:
```python
@cli.command("resolve-discipline-flags")
@click.option("--log", default="data/personal/discipline_log.jsonl", show_default=True)
@click.option("--horizon", default=21, type=int, show_default=True)
def resolve_discipline_flags(log, horizon):
    """Forward-score past REDUCE/TRIM flags: were they followed by drops? (calibration)."""
    from datetime import datetime, timezone
    from application.discipline_log import read_assessments, resolve_flags

    logged = read_assessments(log)
    if not logged:
        click.echo(f"No logged assessments at {log}.")
        return
    start_dt = datetime(2018, 1, 1, tzinfo=timezone.utc)
    end_dt = datetime.now(timezone.utc)
    def provider(ticker):
        return load_price_series(ticker, start_dt, end_dt)
    res = resolve_flags(logged, provider, horizon_days=horizon)
    click.echo(
        f"resolved={res['resolved']}  brier={res['brier']:.3f}  "
        f"down_rate_on_reduce={res['down_rate_on_reduce']:.0%}"
    )


@cli.command("holdings-risk-calibrate")
@click.option("--ticker", required=True, help="Symbol to compute history base rates for")
@click.option("--horizon", default=21, type=int, show_default=True)
def holdings_risk_calibrate(ticker, horizon):
    """Warm-start base rates from price history: what followed each trend state."""
    from datetime import datetime, timezone
    from domain.calibration import base_rate_from_history

    start_dt = datetime(2018, 1, 1, tzinfo=timezone.utc)
    end_dt = datetime.now(timezone.utc)
    closes = [c for _, c in load_price_series(ticker, start_dt, end_dt)]
    rates = base_rate_from_history(closes, trend_window=200, atr_window=22, horizon=horizon)
    if not rates:
        click.echo(f"Not enough history for {ticker}.")
        return
    for bucket, stats in rates.items():
        click.echo(
            f"{bucket:6} n={int(stats['n'])} mean_fwd={stats['mean_fwd_return']:+.2%} "
            f"down_rate={stats['down_rate']:.0%}"
        )
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_opportunity_cli.py -k "resolve_discipline or holdings_risk" -v`
Expected: PASS. Then full `pytest tests/test_opportunity_cli.py -q` and `mypy application/cli.py` — clean.

- [ ] **Step 5: Commit**

```bash
git add application/cli.py tests/test_opportunity_cli.py
git commit -m "feat: resolve-discipline-flags + holdings-risk-calibrate CLIs"
```

---

## Phase F — Quality gate + live smoke (after code green)

### Task 13: `make check` + privacy assertion + live smoke

**Files:** none (verification; may touch `.gitignore`)

- [ ] **Step 1:** `make check` — mypy strict + lint + tests (≥90% cov) all green before any live step.
- [ ] **Step 2:** Confirm privacy: `git check-ignore data/personal/holdings_risk_detail.txt data/personal/discipline_log.jsonl` — BOTH must print (ignored). `data/personal/` is already in `.gitignore`; if either is somehow not ignored, STOP and fix `.gitignore` before any live run.
- [ ] **Step 3:** Live smoke on the real holdings (writes only gitignored files):
  `python -m application.cli holdings-risk --holdings data/personal/holdings-report-2026-06-07.csv`
  Confirm masked stdout (distribution + book risk, NO tickers) and that `data/personal/holdings_risk_detail.txt` contains the per-ticker table.
- [ ] **Step 4:** Warm-start sanity: `python -m application.cli holdings-risk-calibrate --ticker SPY` — prints above/below base rates.
- [ ] **Step 5:** Verify NOTHING personal is staged: `git status --porcelain | grep -i personal` returns empty. Commit only code/tests. The forward-calibration loop (`resolve-discipline-flags`) accrues evidence over the coming weeks; the PROCEED/expand-to-Phase-2 decision is gated on that calibration, not on this build.

---

## Self-Review (completed by plan author)

**Spec coverage:** graded per-holding verdict → T1-T3,T8; conditional vol-targeting (TSX-safe) → T2,T8; relative-strength/regime + abstention → T1,T3,T8; behavior flags → T3,T8; portfolio concentration → T8 (lightweight per spec §9.1); cost-basis/account context → T7,T8; LLM narrator port + local adapter + graceful fallback → T6,T9; warm-start calibration from history → T4,T12; forward outcome logging + calibration/Brier → T10,T12; daily/hourly report-only cadence → T11 (run via existing scheduler); privacy (gitignored, masked stdout, tickers-only-to-yfinance) → T7,T11,T13; honest validation (forward-track, KILL clause) → T10,T12,T13. Phase-2 screening explicitly excluded. Tax leg excluded (registered accounts).

**Placeholder scan:** no TBD/TODO; every code step has complete code; the only behavioral test that relies on a generated series (T8) pins a property (broken-trend name → REDUCE/REVIEW) rather than an exact value.

**Type consistency:** `trend_health/ma_slope/relative_strength` (T1) consumed in T8/T4 with matching signatures; `Verdict` enum (T3) used in models (T5) + use case (T8) + CLI test (T11); `grade_position(th, vol_signal, rs, disposition, winner_past_stop, market_trend_health) -> (Verdict, float, bool)` (T3) called identically in T8; `conditional_vol_signal(recent_vol, baseline_vol, trend_health)` (T2) called in T8; `risk_asymmetry(price, trailing_stop, recent_high)` (T2) returns `downside_to_stop`/`upside_to_recover` consumed in T8; `Holding(ticker, shares, cost_basis, account_type)` (T7) consumed in T8; `PositionRisk`/`PortfolioRisk` (T5) produced in T8 and consumed in T11; `NarratorPort.narrate(context)->str` (T6) implemented by `FakeNarrator` (T6) + `OllamaNarratorAdapter` (T9); `append_assessments`/`read_assessments`/`resolve_flags` (T10) used in T11/T12; `base_rate_from_history(closes, trend_window, atr_window, horizon)` (T4) called in T12; `brier_score` (T4) used in T10. FROZEN params (200/22/3.0) identical in T8 and the calibration CLI (T12).
