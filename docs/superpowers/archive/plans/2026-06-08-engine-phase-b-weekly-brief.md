# Engine Phase B — Unified Weekly Brief Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one decision-oriented weekly brief that composes the Phase-A evidence screen (buy side), the shipped Holdings Discipline engine (sell/hold side), a regime tilt, a concentration warning, and the forward scorecard into a single artifact — CLI + dashboard tab — with every claim carrying its honest label.

**Architecture:** Pure-domain `regime.py` (classify + factor tilt) and `brief.py` (frozen models + assembly + markdown/masked formatters), a thin `RegimeReadUseCase`, and a composing `WeeklyBriefUseCase` that drives the four existing sub-use-cases point-in-time, masks holdings per ADR-047, and writes a gitignored full markdown brief + a masked stdout summary. A new Streamlit tab renders it; a `weekly-brief` CLI generates it.

**Tech Stack:** Python 3.12, stdlib-only domain (no numpy/pandas in `domain/`), Click CLI, Streamlit dashboard, pytest + Hypothesis, mypy strict, black/isort/ruff via pre-commit.

---

## Context the implementer needs

**Phase B adds NO predictive claim.** The Phase-A screen validated INCONCLUSIVE (momentum-leg IC 0.0107, CI spans 0 — ADR-049 Phase-A Validation Outcome) and ships `RESEARCH_ONLY`. The brief therefore must never render "buy" language while the label is `RESEARCH_ONLY`; it presents A and the discipline engine honestly. Phase B's gate is **integrity** (determinism, no look-ahead, privacy, scorecard fidelity, label fidelity), not edge.

**Decisions locked from the spec's open questions (§7):**
1. Concentration → **soft flag** (surface + warn; the user decides). No hard block.
2. Regime inputs → **SPY-trend (ATR-distance) + VIX only**. No breadth (does not exist in the codebase).
3. Cadence → **weekly brief**; the daily holdings delta is the *already-shipped* discipline run (`holdings-risk` / `resolve-discipline-flags`) — no new daily build in this plan.
4. **Regime tilt is DISPLAY-ONLY in v1.** It annotates the brief ("regime favors quality/low-vol") and reports per-factor tilt weights, but it does **not** re-rank the candidate list (re-ranking would be a soft predictive act; deferred). The primary candidate order stays the screen's equal-weight order. This keeps "no new predictive claim" true.
5. **Research-links section is a Phase-C stub in v1** — rendered as "research-only, Phase C pending" with an empty link tuple. Do NOT build Phase C here.

**Verbatim signatures of composed components** (confirmed against the codebase — use exactly these):

- `EvidenceScreenUseCase(price, analyst, fundamentals, narrator).run(universe: list[str], as_of: str, top_n: int = 10) -> ScreenResult` (note: `run` ignores `top_n` internally and returns ALL eligible candidates ranked; the caller slices).
- `label_from_verdict_file(report_dir: str) -> ScreenLabel` (VALIDATED iff latest `screen_ic_*.json` has `decision == "PASS"`, else RESEARCH_ONLY).
- `ScreenResult(as_of: str, candidates: tuple[ScreenCandidate, ...], universe_size: int, regime: str, scorecard_ref: str | None, abstained: bool = False)`.
- `ScreenCandidate(ticker: str, composite: float, factor_scores: tuple[FactorScore, ...], trend_health: float, why: str, label: ScreenLabel)`.
- `FactorScore(name: str, value: float, percentile: float, contribution: float)`.
- `ScreenLabel.VALIDATED | ScreenLabel.RESEARCH_ONLY` (`domain/screen_models.py`).
- `HoldingsRiskAssessmentUseCase(price_provider, narrator, benchmark="SPY").execute(holdings: list[Holding], start: datetime, end: datetime) -> dict[str, Any]` returning `{"positions": list[PositionRisk], "portfolio": PortfolioRisk}`.
- `Holding(ticker: str, shares: float, cost_basis: float, account_type: str)` (`application/holdings_reader.py`); `read_holdings(path: str) -> list[Holding]`.
- `PositionRisk(ticker, price, verdict: Verdict, confidence, trend_health: float | None, vol_signal, relative_strength: float | None, downside_to_stop, upside_to_recover, behavior_flags: tuple[str, ...], unrealized_pct, account_type, abstained, why)` (`domain/models.py`).
- `PortfolioRisk(n_positions: int, broken_trend_share: float, top_concentration: float, verdict_counts: dict[str, int])`.
- `Verdict(str, Enum)` = REDUCE | TRIM | REVIEW | HOLD | ADD_OK (`domain/discipline.py`).
- `ForwardTrackingUseCase(store, market_data).get_track_record() -> list[SignalPerformance]` (from `domain.outcome_service.compute_signal_performance`).
- `resolve_flags(logged: list[dict], price_provider, horizon_days=21) -> {"resolved": int, "brier": float, "down_rate_on_reduce": float, "trim_resolved": int, "down_rate_on_trim": float}` (`application/discipline_log.py`); read the log with `read_assessments(log_path)`.
- `CorrelationAnalyzer(supply_chain_path=...).get_cluster_peers(ticker: str) -> list[str]` (same Ward-linkage cluster; `[]` if unclustered; requires `build_graph(signals_by_ticker, window_days)` first).
- `validate_point_in_time_access(prediction_time: datetime, signals: list[Signal], sentiments: list[Sentiment]) -> None` raises `LookAheadBiasError`.
- `trend_health(price, sma_value, atr_value) -> float | None` = **signed ATR-distance** (positive above trend, ~-3..+3, 0 = on trend) — NOT a 0..1 score. Regime thresholds below use this scale.
- Dashboard tab convention: each module in `adapters/visualization/tabs/` exports `def render(...) -> None`, lazy-imported and registered in `adapters/visualization/dashboard.py`'s `st.tabs([...])` block. Data loaders live in `adapters/visualization/data_loader.py` as `load_*` functions returning empty defaults on missing data.
- CLI masking is architectural: sensitive per-holding detail goes ONLY to a `data/personal/` file (gitignored by the `data/personal/` glob); `click.echo` prints aggregates only. `_build_dependencies(market) -> dict` provides `"store"`, `"market_data"`, `"config"`, etc.

**ADR-048 discipline forward gate (for the scorecard status string):** PROCEED needs `down_rate_on_reduce >= 0.55 AND brier <= 0.45 AND resolved >= 30`; otherwise `PENDING` (or `n<30`).

---

## File Structure

- **Create** `domain/regime.py` — pure: `Regime` enum, `classify_regime(...)`, `screen_tilt(...)`.
- **Create** `domain/brief.py` — pure: frozen models (`BuyCandidateLine`, `HoldingVerdictLine`, `ConcentrationFlag`, `ResearchLink`, `ScorecardSnapshot`, `WeeklyBrief`), `assemble_brief(...)`, `to_markdown(...)`, `to_stdout_masked(...)`.
- **Create** `application/weekly_brief_use_case.py` — `RegimeReadUseCase` (thin) + `WeeklyBriefUseCase` (composition).
- **Modify** `application/cli.py` — add `weekly-brief` command.
- **Create** `adapters/visualization/tabs/weekly_brief.py` — `render(...)`.
- **Modify** `adapters/visualization/dashboard.py` — register the new tab.
- **Modify** `adapters/visualization/data_loader.py` — add `load_weekly_brief(...)`.
- **Create** tests alongside: `tests/test_regime.py`, `tests/test_brief.py`, `tests/test_weekly_brief_use_case.py`, `tests/test_cli_weekly_brief.py`, `tests/test_weekly_brief_tab.py`.
- **Modify** `docs/adr/049-decision-support-engine-architecture.md` — Phase-B-built note (final task).

---

## Task 1: Regime classification (`domain/regime.py`)

**Files:**
- Create: `domain/regime.py`
- Test: `tests/test_regime.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_regime.py
from hypothesis import given, strategies as st

from domain.regime import Regime, classify_regime


def test_clear_uptrend_low_vix_is_risk_on() -> None:
    assert classify_regime(spy_trend_health=1.2, vix_level=14.0) == Regime.RISK_ON


def test_broken_trend_is_risk_off() -> None:
    assert classify_regime(spy_trend_health=-0.8, vix_level=15.0) == Regime.RISK_OFF


def test_high_vix_is_risk_off_even_if_trend_ok() -> None:
    assert classify_regime(spy_trend_health=0.7, vix_level=30.0) == Regime.RISK_OFF


def test_middle_is_neutral() -> None:
    assert classify_regime(spy_trend_health=0.2, vix_level=20.0) == Regime.NEUTRAL


@given(
    t1=st.floats(-3, 3),
    t2=st.floats(-3, 3),
    vix=st.floats(8, 40),
)
def test_monotone_in_trend(t1: float, t2: float, vix: float) -> None:
    # Higher trend health never makes the regime MORE risk-off.
    order = {Regime.RISK_OFF: 0, Regime.NEUTRAL: 1, Regime.RISK_ON: 2}
    lo, hi = (t1, t2) if t1 <= t2 else (t2, t1)
    assert order[classify_regime(lo, vix)] <= order[classify_regime(hi, vix)]


@given(
    trend=st.floats(-3, 3),
    v1=st.floats(8, 40),
    v2=st.floats(8, 40),
)
def test_monotone_in_vix(trend: float, v1: float, v2: float) -> None:
    # Higher VIX never makes the regime MORE risk-on.
    order = {Regime.RISK_OFF: 0, Regime.NEUTRAL: 1, Regime.RISK_ON: 2}
    lo, hi = (v1, v2) if v1 <= v2 else (v2, v1)
    assert order[classify_regime(trend, hi)] <= order[classify_regime(trend, lo)]
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_regime.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'domain.regime'`.

- [ ] **Step 3: Implement `classify_regime`**

```python
# domain/regime.py
"""Pure regime classification — conditions the brief's presentation/tilt only.

Does NOT predict the macro (the trend is non-stationary, ADR-049). Inputs:
spy_trend_health is SIGNED ATR-distance of SPY from its trend (positive = above
trend, ~-3..+3); vix_level is the raw VIX index level.
"""

from __future__ import annotations

from enum import Enum

# Frozen thresholds (ATR units / VIX points) — set before use, not tuned.
_RISK_ON_TREND = 0.5
_RISK_ON_VIX = 18.0
_RISK_OFF_TREND = -0.5
_RISK_OFF_VIX = 28.0


class Regime(Enum):
    RISK_ON = "RISK_ON"
    NEUTRAL = "NEUTRAL"
    RISK_OFF = "RISK_OFF"


def classify_regime(spy_trend_health: float, vix_level: float) -> Regime:
    """Classify regime from SPY trend-health (signed ATR-distance) and VIX level.

    RISK_OFF dominates (capital-preservation bias): a broken trend OR an elevated
    VIX forces RISK_OFF. RISK_ON requires BOTH a clearly-above-trend tape AND a
    calm VIX. Everything else is NEUTRAL. Monotone: higher trend never increases
    risk-off; higher VIX never increases risk-on.
    """
    if spy_trend_health <= _RISK_OFF_TREND or vix_level >= _RISK_OFF_VIX:
        return Regime.RISK_OFF
    if spy_trend_health >= _RISK_ON_TREND and vix_level < _RISK_ON_VIX:
        return Regime.RISK_ON
    return Regime.NEUTRAL
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_regime.py -v`
Expected: PASS (5 tests, including the two Hypothesis monotonicity tests).

- [ ] **Step 5: Commit**

```bash
git add domain/regime.py tests/test_regime.py
git commit -m "feat(brief): regime classification (SPY-trend + VIX, presentation-only)"
```

---

## Task 2: Factor tilt (`domain/regime.py`)

**Files:**
- Modify: `domain/regime.py`
- Test: `tests/test_regime.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_regime.py  (append)
from domain.regime import screen_tilt
from domain.factor_scores import FACTOR_KEYS


def test_tilt_weights_sum_to_one_each_regime() -> None:
    for regime in Regime:
        w = screen_tilt(regime)
        assert set(w.keys()) == set(FACTOR_KEYS)
        assert abs(sum(w.values()) - 1.0) < 1e-9


def test_risk_off_favors_quality_over_momentum() -> None:
    w = screen_tilt(Regime.RISK_OFF)
    assert w["quality"] > w["momentum"]


def test_risk_on_favors_momentum_over_quality() -> None:
    w = screen_tilt(Regime.RISK_ON)
    assert w["momentum"] > w["quality"]


def test_neutral_is_equal_weight() -> None:
    w = screen_tilt(Regime.NEUTRAL)
    assert all(abs(v - 0.25) < 1e-9 for v in w.values())
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_regime.py -k tilt -v`
Expected: FAIL with `ImportError: cannot import name 'screen_tilt'`.

- [ ] **Step 3: Implement `screen_tilt`**

```python
# domain/regime.py  (append; add this import at top)
from domain.factor_scores import FACTOR_KEYS

_TILTS: dict[Regime, dict[str, float]] = {
    Regime.RISK_ON: {"momentum": 0.40, "revision": 0.30, "quality": 0.15, "value": 0.15},
    Regime.NEUTRAL: {"momentum": 0.25, "revision": 0.25, "quality": 0.25, "value": 0.25},
    Regime.RISK_OFF: {"momentum": 0.15, "revision": 0.15, "quality": 0.40, "value": 0.30},
}


def screen_tilt(regime: Regime) -> dict[str, float]:
    """Display-only factor-weight tilt for the brief (weights sum to 1).

    v1 does NOT re-rank candidates with these weights — the tilt is shown as
    context ('regime favors quality/low-vol'). Re-ranking is a soft predictive
    act and is deferred (keeps Phase B's no-new-claim invariant).
    """
    return dict(_TILTS[regime])
```

> Note: `FACTOR_KEYS` is `("momentum", "revision", "quality", "value")` in `domain/factor_scores.py`. Keep the keys in sync with it.

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_regime.py -v`
Expected: PASS (all regime tests).

- [ ] **Step 5: Commit**

```bash
git add domain/regime.py tests/test_regime.py
git commit -m "feat(brief): display-only factor tilt per regime (weights sum to 1)"
```

---

## Task 3: Brief models (`domain/brief.py`)

**Files:**
- Create: `domain/brief.py`
- Test: `tests/test_brief.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_brief.py
from domain.brief import (
    BuyCandidateLine,
    HoldingVerdictLine,
    ConcentrationFlag,
    ResearchLink,
    ScorecardSnapshot,
    WeeklyBrief,
)
from domain.regime import Regime
from domain.screen_models import ScreenLabel
from domain.discipline import Verdict


def test_models_construct_and_are_frozen() -> None:
    cand = BuyCandidateLine(
        ticker="AAPL",
        composite=0.42,
        factor_summary="mom p82 · rev n/a · qual n/a · val n/a · trend ok",
        why="strong 12-1 momentum",
        already_held=True,
        label=ScreenLabel.RESEARCH_ONLY,
    )
    hold = HoldingVerdictLine(
        ticker="MSFT", unrealized_pct=0.12, trend_state="uptrend",
        verdict=Verdict.HOLD, why="trend intact",
    )
    conc = ConcentrationFlag(descriptor="Tech 32% of book", soft_warning=True)
    link = ResearchLink(source="WMT", linked="MCK", relationship="customer→supplier")
    card = ScorecardSnapshot(
        screen_window="since 2026-06-08", screen_top_ret=None, screen_spy_ret=None,
        screen_n=0, screen_significant=False,
        discipline_window="21d", discipline_reduce_down_rate=0.58,
        discipline_n=5462, discipline_gate_status="PENDING",
    )
    brief = WeeklyBrief(
        as_of="2026-06-08", regime=Regime.NEUTRAL,
        tilt={"momentum": 0.25, "revision": 0.25, "quality": 0.25, "value": 0.25},
        candidates=(cand,), holdings=(hold,), research_links=(link,),
        concentration=(conc,), scorecard=card, screen_label=ScreenLabel.RESEARCH_ONLY,
    )
    assert brief.as_of == "2026-06-08"
    try:
        brief.as_of = "x"  # type: ignore[misc]
        assert False, "should be frozen"
    except Exception:
        pass
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_brief.py::test_models_construct_and_are_frozen -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'domain.brief'`.

- [ ] **Step 3: Implement the models**

```python
# domain/brief.py
"""Pure assembly + formatting for the unified weekly brief (no IO).

Phase B adds NO predictive claim — it composes the Phase-A screen and the
discipline engine honestly. RESEARCH_ONLY screens never render 'buy' language.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.discipline import Verdict
from domain.regime import Regime
from domain.screen_models import ScreenLabel


@dataclass(frozen=True)
class BuyCandidateLine:
    ticker: str
    composite: float
    factor_summary: str
    why: str
    already_held: bool
    label: ScreenLabel


@dataclass(frozen=True)
class HoldingVerdictLine:
    ticker: str
    unrealized_pct: float
    trend_state: str  # "uptrend" | "broken" | "unknown"
    verdict: Verdict
    why: str


@dataclass(frozen=True)
class ConcentrationFlag:
    descriptor: str
    soft_warning: bool


@dataclass(frozen=True)
class ResearchLink:
    source: str
    linked: str
    relationship: str


@dataclass(frozen=True)
class ScorecardSnapshot:
    screen_window: str
    screen_top_ret: float | None
    screen_spy_ret: float | None
    screen_n: int
    screen_significant: bool
    discipline_window: str
    discipline_reduce_down_rate: float | None
    discipline_n: int
    discipline_gate_status: str


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
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_brief.py::test_models_construct_and_are_frozen -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add domain/brief.py tests/test_brief.py
git commit -m "feat(brief): frozen weekly-brief domain models"
```

---

## Task 4: `assemble_brief` (`domain/brief.py`)

**Files:**
- Modify: `domain/brief.py`
- Test: `tests/test_brief.py`

`assemble_brief` is the pure composition step. It receives already-fetched raw pieces (so it stays IO-free and fully fakeable) and produces a `WeeklyBrief`. The use case (Task 8) fetches the pieces and calls this.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_brief.py  (append)
from domain.brief import assemble_brief
from domain.screen_models import ScreenResult, ScreenCandidate, FactorScore
from domain.models import PositionRisk, PortfolioRisk


def _screen_result(label: ScreenLabel) -> ScreenResult:
    fs = (
        FactorScore("momentum", 1.1, 0.82, 0.27),
        FactorScore("revision", 0.0, 0.0, 0.0),
        FactorScore("quality", 0.0, 0.0, 0.0),
        FactorScore("value", 0.0, 0.0, 0.0),
    )
    cands = (
        ScreenCandidate("AAPL", 0.42, fs, 1.3, "strong 12-1 momentum", label),
        ScreenCandidate("NEW1", 0.30, fs, 0.9, "momentum", label),
    )
    return ScreenResult("2026-06-08", cands, 500, "NEUTRAL", None, abstained=False)


def _positions() -> list[PositionRisk]:
    return [
        PositionRisk("AAPL", 200.0, Verdict.HOLD, 0.6, 1.4, 0.0, 0.1, 0.2, 0.3,
                     (), 0.15, "TFSA", False, "trend intact"),
        PositionRisk("RIVN", 10.0, Verdict.REDUCE, 0.7, -1.2, 0.0, -0.1, 0.4, 0.1,
                     ("broken_trend",), -0.45, "Margin", False, "broken trend"),
    ]


def _portfolio() -> PortfolioRisk:
    return PortfolioRisk(2, 0.5, 0.22, {"HOLD": 1, "REDUCE": 1})


def _scorecard() -> ScorecardSnapshot:
    return ScorecardSnapshot("since 2026-06-08", None, None, 0, False,
                             "21d", 0.58, 5462, "PENDING")


def test_assemble_marks_already_held_candidate() -> None:
    brief = assemble_brief(
        as_of="2026-06-08",
        regime=Regime.NEUTRAL,
        tilt={"momentum": 0.25, "revision": 0.25, "quality": 0.25, "value": 0.25},
        screen_result=_screen_result(ScreenLabel.RESEARCH_ONLY),
        screen_label=ScreenLabel.RESEARCH_ONLY,
        top_n=10,
        positions=_positions(),
        portfolio=_portfolio(),
        held_tickers={"AAPL", "RIVN"},
        cluster_overlaps={"AAPL": ["MSFT"], "NEW1": []},
        scorecard=_scorecard(),
        concentration_threshold=0.20,
    )
    aapl = next(c for c in brief.candidates if c.ticker == "AAPL")
    new1 = next(c for c in brief.candidates if c.ticker == "NEW1")
    assert aapl.already_held is True
    assert new1.already_held is False


def test_assemble_orders_holdings_reduce_first() -> None:
    brief = assemble_brief(
        as_of="2026-06-08", regime=Regime.NEUTRAL,
        tilt={"momentum": 0.25, "revision": 0.25, "quality": 0.25, "value": 0.25},
        screen_result=_screen_result(ScreenLabel.RESEARCH_ONLY),
        screen_label=ScreenLabel.RESEARCH_ONLY, top_n=10,
        positions=_positions(), portfolio=_portfolio(),
        held_tickers={"AAPL", "RIVN"}, cluster_overlaps={},
        scorecard=_scorecard(), concentration_threshold=0.20,
    )
    # REDUCE is the most urgent verdict — must sort before HOLD.
    assert brief.holdings[0].verdict == Verdict.REDUCE


def test_assemble_flags_concentration_when_over_threshold() -> None:
    brief = assemble_brief(
        as_of="2026-06-08", regime=Regime.NEUTRAL,
        tilt={"momentum": 0.25, "revision": 0.25, "quality": 0.25, "value": 0.25},
        screen_result=_screen_result(ScreenLabel.RESEARCH_ONLY),
        screen_label=ScreenLabel.RESEARCH_ONLY, top_n=10,
        positions=_positions(), portfolio=_portfolio(),
        held_tickers={"AAPL", "RIVN"}, cluster_overlaps={},
        scorecard=_scorecard(), concentration_threshold=0.20,
    )
    # top_concentration 0.22 > 0.20 → one soft flag.
    assert any(f.soft_warning for f in brief.concentration)


def test_assemble_top_n_limits_candidates() -> None:
    brief = assemble_brief(
        as_of="2026-06-08", regime=Regime.NEUTRAL,
        tilt={"momentum": 0.25, "revision": 0.25, "quality": 0.25, "value": 0.25},
        screen_result=_screen_result(ScreenLabel.RESEARCH_ONLY),
        screen_label=ScreenLabel.RESEARCH_ONLY, top_n=1,
        positions=_positions(), portfolio=_portfolio(),
        held_tickers=set(), cluster_overlaps={},
        scorecard=_scorecard(), concentration_threshold=0.20,
    )
    assert len(brief.candidates) == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_brief.py -k assemble -v`
Expected: FAIL with `ImportError: cannot import name 'assemble_brief'`.

- [ ] **Step 3: Implement `assemble_brief`**

```python
# domain/brief.py  (append; add imports at top)
from domain.models import PortfolioRisk, PositionRisk
from domain.screen_models import ScreenCandidate, ScreenResult

# Verdict urgency for ordering holdings (most urgent first).
_VERDICT_ORDER: dict[Verdict, int] = {
    Verdict.REDUCE: 0,
    Verdict.TRIM: 1,
    Verdict.REVIEW: 2,
    Verdict.HOLD: 3,
    Verdict.ADD_OK: 4,
}


def _factor_summary(cand: ScreenCandidate) -> str:
    parts: list[str] = []
    for fs in cand.factor_scores:
        # A flagged-neutral factor has value==0 and percentile==0 (no coverage).
        if fs.value == 0.0 and fs.percentile == 0.0:
            parts.append(f"{fs.name[:3]} n/a")
        else:
            parts.append(f"{fs.name[:3]} p{int(round(fs.percentile * 100))}")
    trend = "trend ok" if cand.trend_health >= 0 else "trend weak"
    return " · ".join(parts) + " · " + trend


def _trend_state(th: float | None) -> str:
    if th is None:
        return "unknown"
    return "uptrend" if th >= 0 else "broken"


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
) -> WeeklyBrief:
    """Compose a WeeklyBrief from already-fetched pieces (pure, IO-free).

    held_tickers: set of tickers the user holds (for already-held marking).
    cluster_overlaps: candidate ticker -> held tickers in its correlation cluster.
    """
    candidates = tuple(
        BuyCandidateLine(
            ticker=c.ticker,
            composite=c.composite,
            factor_summary=_factor_summary(c),
            why=c.why,
            already_held=c.ticker in held_tickers,
            label=screen_label,
        )
        for c in screen_result.candidates[:top_n]
    )

    holdings = tuple(
        sorted(
            (
                HoldingVerdictLine(
                    ticker=p.ticker,
                    unrealized_pct=p.unrealized_pct,
                    trend_state=_trend_state(p.trend_health),
                    verdict=p.verdict,
                    why=p.why,
                )
                for p in positions
            ),
            key=lambda h: _VERDICT_ORDER.get(h.verdict, 99),
        )
    )

    flags: list[ConcentrationFlag] = []
    if portfolio.top_concentration > concentration_threshold:
        flags.append(
            ConcentrationFlag(
                descriptor=(
                    f"Top concentration {portfolio.top_concentration:.0%} of book "
                    f"(> {concentration_threshold:.0%}) — correlated leverage on one bet, "
                    f"not diversification"
                ),
                soft_warning=True,
            )
        )
    for cand_ticker, overlaps in cluster_overlaps.items():
        if overlaps:
            flags.append(
                ConcentrationFlag(
                    descriptor=(
                        f"{cand_ticker} is in the same correlation cluster as "
                        f"{', '.join(overlaps)} you already hold — adds to an existing bet"
                    ),
                    soft_warning=True,
                )
            )

    return WeeklyBrief(
        as_of=as_of,
        regime=regime,
        tilt=dict(tilt),
        candidates=candidates,
        holdings=holdings,
        research_links=(),  # Phase C stub — populated only when Phase C ships.
        concentration=tuple(flags),
        scorecard=scorecard,
        screen_label=screen_label,
    )
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_brief.py -v`
Expected: PASS (all assemble tests + the model test).

- [ ] **Step 5: Commit**

```bash
git add domain/brief.py tests/test_brief.py
git commit -m "feat(brief): pure assemble_brief composition (already-held, ordering, concentration)"
```

---

## Task 5: Markdown formatter (`domain/brief.py`)

**Files:**
- Modify: `domain/brief.py`
- Test: `tests/test_brief.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_brief.py  (append)
from domain.brief import to_markdown


def _full_brief(label: ScreenLabel) -> WeeklyBrief:
    return assemble_brief(
        as_of="2026-06-08", regime=Regime.RISK_OFF,
        tilt={"momentum": 0.15, "revision": 0.15, "quality": 0.40, "value": 0.30},
        screen_result=_screen_result(label), screen_label=label, top_n=10,
        positions=_positions(), portfolio=_portfolio(),
        held_tickers={"AAPL", "RIVN"}, cluster_overlaps={},
        scorecard=_scorecard(), concentration_threshold=0.20,
    )


def test_markdown_has_all_sections() -> None:
    md = to_markdown(_full_brief(ScreenLabel.RESEARCH_ONLY))
    assert "WEEKLY BRIEF" in md
    assert "REGIME" in md
    assert "HOLDINGS VERDICTS" in md
    assert "CONCENTRATION" in md
    assert "SCORECARD" in md
    assert "RIVN" in md  # full markdown DOES include holding tickers (gitignored file)


def test_markdown_research_only_has_no_buy_language() -> None:
    md = to_markdown(_full_brief(ScreenLabel.RESEARCH_ONLY)).lower()
    assert "buy candidates" not in md
    assert "evidence-ranked" in md  # honest header instead


def test_markdown_validated_uses_buy_header() -> None:
    md = to_markdown(_full_brief(ScreenLabel.VALIDATED))
    assert "BUY CANDIDATES" in md
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_brief.py -k markdown -v`
Expected: FAIL with `ImportError: cannot import name 'to_markdown'`.

- [ ] **Step 3: Implement `to_markdown`**

```python
# domain/brief.py  (append)
def _candidates_header(label: ScreenLabel) -> str:
    if label == ScreenLabel.VALIDATED:
        return "BUY CANDIDATES (validated)"
    return "EVIDENCE-RANKED CANDIDATES (research-only, not validated)"


def to_markdown(brief: WeeklyBrief) -> str:
    """Full brief as markdown — written to a gitignored file / rendered in the
    dashboard. Includes holding tickers + P&L (the file lives under data/personal/).
    """
    tilt = brief.tilt
    tilt_str = " · ".join(f"{k} {tilt[k]:.0%}" for k in ("momentum", "revision", "quality", "value"))
    lines: list[str] = []
    lines.append(f"# WEEKLY BRIEF — {brief.as_of}")
    lines.append("")
    lines.append(f"**REGIME:** {brief.regime.value}  →  screen tilt: {tilt_str}")
    lines.append("")
    lines.append(f"## {_candidates_header(brief.screen_label)}")
    if not brief.candidates:
        lines.append("_(screen abstained — no eligible candidates)_")
    for c in brief.candidates:
        held = "  ⚠ already held" if c.already_held else ""
        lines.append(f"- **{c.ticker}**  {c.factor_summary}  — {c.why}{held}")
    lines.append("")
    lines.append("## HOLDINGS VERDICTS")
    for h in brief.holdings:
        lines.append(
            f"- **{h.ticker}**  {h.unrealized_pct:+.0%}  {h.trend_state}  "
            f"**{h.verdict.value}** — {h.why}"
        )
    lines.append("")
    lines.append("## RESEARCH LINKS (research-only, Phase C pending)")
    if not brief.research_links:
        lines.append("_(economic-link research ships in Phase C — not a signal)_")
    for link in brief.research_links:
        lines.append(f"- {link.source} → {link.linked} ({link.relationship}) → go research")
    lines.append("")
    lines.append("## CONCENTRATION")
    if not brief.concentration:
        lines.append("_(no concentration flags)_")
    for f in brief.concentration:
        lines.append(f"- {f.descriptor}")
    lines.append("")
    lines.append("## SCORECARD")
    sc = brief.scorecard
    if sc.screen_n == 0:
        lines.append(f"- screen ({sc.screen_window}): n=0 — abstaining, no track record yet")
    else:
        sig = "significant" if sc.screen_significant else "not significant"
        lines.append(
            f"- screen ({sc.screen_window}): top-10 {sc.screen_top_ret:+.2%} vs "
            f"SPY {sc.screen_spy_ret:+.2%} (n={sc.screen_n}, {sig})"
        )
    dr = "n/a" if sc.discipline_reduce_down_rate is None else f"{sc.discipline_reduce_down_rate:.0%}"
    lines.append(
        f"- discipline ({sc.discipline_window}): REDUCE down-rate {dr} "
        f"(n={sc.discipline_n}) — forward gate {sc.discipline_gate_status}"
    )
    return "\n".join(lines)
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_brief.py -k markdown -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add domain/brief.py tests/test_brief.py
git commit -m "feat(brief): markdown formatter with RESEARCH_ONLY buy-language suppression"
```

---

## Task 6: Masked stdout formatter (`domain/brief.py`)

**Files:**
- Modify: `domain/brief.py`
- Test: `tests/test_brief.py`

The masked formatter is what the CLI prints to the terminal. Per ADR-047 it must NOT reveal holding tickers or per-position P&L — only aggregate verdict counts. Public buy candidates (drawn from the public universe) are fine to show.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_brief.py  (append)
from hypothesis import given, strategies as st
from domain.brief import to_stdout_masked


def test_masked_stdout_hides_holding_tickers_and_pnl() -> None:
    out = to_stdout_masked(_full_brief(ScreenLabel.RESEARCH_ONLY))
    assert "RIVN" not in out          # holding ticker masked
    assert "-45%" not in out and "-0.45" not in out  # holding P&L masked
    assert "HOLDINGS (masked)" in out  # aggregate counts shown
    assert "AAPL" in out               # public candidate IS shown


def test_masked_stdout_shows_verdict_counts() -> None:
    out = to_stdout_masked(_full_brief(ScreenLabel.RESEARCH_ONLY))
    assert "REDUCE" in out  # counts, not names


@given(label=st.sampled_from([ScreenLabel.RESEARCH_ONLY, ScreenLabel.VALIDATED]))
def test_masked_research_only_no_buy_language(label: ScreenLabel) -> None:
    out = to_stdout_masked(_full_brief(label)).lower()
    if label == ScreenLabel.RESEARCH_ONLY:
        assert "buy candidates" not in out
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_brief.py -k masked -v`
Expected: FAIL with `ImportError: cannot import name 'to_stdout_masked'`.

- [ ] **Step 3: Implement `to_stdout_masked`**

```python
# domain/brief.py  (append; add Counter import at top: from collections import Counter)
def to_stdout_masked(brief: WeeklyBrief) -> str:
    """Terminal summary — masks all holding-level detail (ADR-047).

    Shows: regime, public buy/evidence candidates (universe is public), aggregate
    holding verdict counts (NOT tickers or P&L), concentration as aggregate text,
    and the scorecard. Full detail goes only to the gitignored markdown file.
    """
    lines: list[str] = []
    lines.append(f"WEEKLY BRIEF — {brief.as_of}   REGIME: {brief.regime.value}")
    lines.append(_candidates_header(brief.screen_label))
    for c in brief.candidates:
        held = "  [already held]" if c.already_held else ""
        lines.append(f"  {c.ticker}  {c.factor_summary}{held}")
    counts = Counter(h.verdict.value for h in brief.holdings)
    lines.append("HOLDINGS (masked): " + ", ".join(f"{v} {counts[v]}" for v in sorted(counts)))
    if brief.concentration:
        lines.append(f"CONCENTRATION: {len(brief.concentration)} flag(s) — see full brief")
    sc = brief.scorecard
    dr = "n/a" if sc.discipline_reduce_down_rate is None else f"{sc.discipline_reduce_down_rate:.0%}"
    screen_line = "n=0 (abstaining)" if sc.screen_n == 0 else f"n={sc.screen_n}"
    lines.append(
        f"SCORECARD: screen {screen_line}; discipline REDUCE down-rate {dr} "
        f"(n={sc.discipline_n}, gate {sc.discipline_gate_status})"
    )
    return "\n".join(lines)
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_brief.py -v`
Expected: PASS (all brief tests).

- [ ] **Step 5: Commit**

```bash
git add domain/brief.py tests/test_brief.py
git commit -m "feat(brief): masked stdout formatter (holdings detail never printed)"
```

---

## Task 7: `RegimeReadUseCase` (`application/weekly_brief_use_case.py`)

**Files:**
- Create: `application/weekly_brief_use_case.py`
- Test: `tests/test_weekly_brief_use_case.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_weekly_brief_use_case.py
from application.weekly_brief_use_case import RegimeReadUseCase
from domain.regime import Regime


def test_regime_read_uses_providers() -> None:
    uc = RegimeReadUseCase(
        vix_provider=lambda: 14.0,
        spy_trend_provider=lambda: 1.1,
    )
    assert uc.read() == Regime.RISK_ON


def test_regime_read_risk_off_on_high_vix() -> None:
    uc = RegimeReadUseCase(
        vix_provider=lambda: 32.0,
        spy_trend_provider=lambda: 0.6,
    )
    assert uc.read() == Regime.RISK_OFF
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_weekly_brief_use_case.py::test_regime_read_uses_providers -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `RegimeReadUseCase`**

```python
# application/weekly_brief_use_case.py
"""Compose the unified weekly brief from the four validated sub-use-cases."""

from __future__ import annotations

from typing import Callable

from domain.regime import Regime, classify_regime

VixProvider = Callable[[], float]
SpyTrendProvider = Callable[[], float]


class RegimeReadUseCase:
    """Thin: read live VIX + SPY trend-health, classify the regime."""

    def __init__(self, vix_provider: VixProvider, spy_trend_provider: SpyTrendProvider) -> None:
        self._vix = vix_provider
        self._spy_trend = spy_trend_provider

    def read(self) -> Regime:
        return classify_regime(self._spy_trend(), self._vix())
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_weekly_brief_use_case.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add application/weekly_brief_use_case.py tests/test_weekly_brief_use_case.py
git commit -m "feat(brief): thin RegimeReadUseCase (VIX + SPY trend)"
```

---

## Task 8: `WeeklyBriefUseCase` orchestration (`application/weekly_brief_use_case.py`)

**Files:**
- Modify: `application/weekly_brief_use_case.py`
- Test: `tests/test_weekly_brief_use_case.py`

The use case drives the sub-use-cases and the pure assembly. Heavy collaborators are injected so tests use fakes (no network). It computes the scorecard, the held-ticker set, and the cluster overlaps, then calls `assemble_brief`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_weekly_brief_use_case.py  (append)
from datetime import datetime

from application.weekly_brief_use_case import WeeklyBriefUseCase
from domain.screen_models import (
    ScreenResult, ScreenCandidate, FactorScore, ScreenLabel,
)
from domain.models import PositionRisk, PortfolioRisk
from domain.discipline import Verdict
from domain.brief import WeeklyBrief
from application.holdings_reader import Holding


def _fs() -> tuple[FactorScore, ...]:
    return (
        FactorScore("momentum", 1.1, 0.82, 0.27),
        FactorScore("revision", 0.0, 0.0, 0.0),
        FactorScore("quality", 0.0, 0.0, 0.0),
        FactorScore("value", 0.0, 0.0, 0.0),
    )


class _FakeScreen:
    def run(self, universe: list[str], as_of: str, top_n: int = 10) -> ScreenResult:
        cands = (
            ScreenCandidate("AAPL", 0.42, _fs(), 1.3, "momentum", ScreenLabel.RESEARCH_ONLY),
            ScreenCandidate("NEW1", 0.30, _fs(), 0.9, "momentum", ScreenLabel.RESEARCH_ONLY),
        )
        return ScreenResult(as_of, cands, 500, "NEUTRAL", None, False)


class _FakeHoldingsRisk:
    def execute(self, holdings, start, end):  # type: ignore[no-untyped-def]
        positions = [
            PositionRisk("AAPL", 200.0, Verdict.HOLD, 0.6, 1.4, 0.0, 0.1, 0.2, 0.3,
                         (), 0.15, "TFSA", False, "trend intact"),
            PositionRisk("RIVN", 10.0, Verdict.REDUCE, 0.7, -1.2, 0.0, -0.1, 0.4, 0.1,
                         ("broken_trend",), -0.45, "Margin", False, "broken trend"),
        ]
        return {"positions": positions, "portfolio": PortfolioRisk(2, 0.5, 0.22, {"HOLD": 1, "REDUCE": 1})}


def _make_uc() -> WeeklyBriefUseCase:
    return WeeklyBriefUseCase(
        screen=_FakeScreen(),
        holdings_risk=_FakeHoldingsRisk(),
        regime_reader=RegimeReadUseCase(vix_provider=lambda: 20.0, spy_trend_provider=lambda: 0.1),
        screen_label_fn=lambda report_dir: ScreenLabel.RESEARCH_ONLY,
        cluster_peers_fn=lambda ticker: ["AAPL"] if ticker == "NEW1" else [],
        screen_scorecard_fn=lambda: (None, None, 0, False),  # (top_ret, spy_ret, n, significant)
        discipline_scorecard_fn=lambda: (0.58, 5462, "PENDING"),  # (down_rate, n, gate_status)
    )


def test_execute_returns_weekly_brief() -> None:
    uc = _make_uc()
    holdings = [Holding("AAPL", 10, 1000, "TFSA"), Holding("RIVN", 5, 500, "Margin")]
    brief = uc.execute(
        universe=["AAPL", "NEW1", "MSFT"],
        holdings=holdings,
        as_of=datetime(2026, 6, 8),
        report_dir="data/reports/",
        top_n=10,
    )
    assert isinstance(brief, WeeklyBrief)
    assert brief.screen_label == ScreenLabel.RESEARCH_ONLY
    # AAPL is held → already_held; NEW1 not held.
    assert any(c.ticker == "AAPL" and c.already_held for c in brief.candidates)
    # NEW1 clusters with held AAPL → a concentration overlap flag exists.
    assert any("NEW1" in f.descriptor for f in brief.concentration)
    # discipline scorecard wired through.
    assert brief.scorecard.discipline_reduce_down_rate == 0.58


def test_execute_is_deterministic() -> None:
    uc = _make_uc()
    holdings = [Holding("AAPL", 10, 1000, "TFSA"), Holding("RIVN", 5, 500, "Margin")]
    kwargs = dict(universe=["AAPL", "NEW1"], holdings=holdings,
                  as_of=datetime(2026, 6, 8), report_dir="data/reports/", top_n=10)
    b1 = uc.execute(**kwargs)  # type: ignore[arg-type]
    b2 = uc.execute(**kwargs)  # type: ignore[arg-type]
    from domain.brief import to_markdown
    assert to_markdown(b1) == to_markdown(b2)
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_weekly_brief_use_case.py -k execute -v`
Expected: FAIL with `ImportError: cannot import name 'WeeklyBriefUseCase'`.

- [ ] **Step 3: Implement `WeeklyBriefUseCase`**

```python
# application/weekly_brief_use_case.py  (append; extend imports)
from datetime import datetime, timedelta
from typing import Any

from domain.brief import ScorecardSnapshot, WeeklyBrief, assemble_brief
from domain.regime import screen_tilt
from domain.screen_models import ScreenLabel

# Callables injected so tests stay network-free.
ScreenLabelFn = Callable[[str], ScreenLabel]
ClusterPeersFn = Callable[[str], list[str]]
# screen scorecard -> (top_ret, spy_ret, n, significant)
ScreenScorecardFn = Callable[[], "tuple[float | None, float | None, int, bool]"]
# discipline scorecard -> (reduce_down_rate, n, gate_status)
DisciplineScorecardFn = Callable[[], "tuple[float | None, int, str]"]

_HISTORY_DAYS = 400  # lookback for holdings-risk price windows


class WeeklyBriefUseCase:
    def __init__(
        self,
        screen: Any,                      # EvidenceScreenUseCase
        holdings_risk: Any,               # HoldingsRiskAssessmentUseCase
        regime_reader: RegimeReadUseCase,
        screen_label_fn: ScreenLabelFn,
        cluster_peers_fn: ClusterPeersFn,
        screen_scorecard_fn: ScreenScorecardFn,
        discipline_scorecard_fn: DisciplineScorecardFn,
    ) -> None:
        self._screen = screen
        self._holdings = holdings_risk
        self._regime = regime_reader
        self._label_fn = screen_label_fn
        self._cluster = cluster_peers_fn
        self._screen_card = screen_scorecard_fn
        self._disc_card = discipline_scorecard_fn

    def execute(
        self,
        universe: list[str],
        holdings: list[Any],   # list[Holding]
        as_of: datetime,
        report_dir: str,
        top_n: int = 10,
        concentration_threshold: float = 0.20,
    ) -> WeeklyBrief:
        as_of_iso = as_of.date().isoformat()

        screen_result = self._screen.run(universe, as_of_iso, top_n)
        label = self._label_fn(report_dir)
        regime = self._regime.read()

        start = as_of - timedelta(days=_HISTORY_DAYS)
        risk = self._holdings.execute(holdings, start, as_of)
        positions = risk["positions"]
        portfolio = risk["portfolio"]

        held_tickers = {h.ticker for h in holdings}

        # Cluster overlaps: for each candidate, which held tickers share its cluster.
        cluster_overlaps: dict[str, list[str]] = {}
        for c in screen_result.candidates[:top_n]:
            peers = set(self._cluster(c.ticker))
            overlaps = sorted(peers & held_tickers)
            cluster_overlaps[c.ticker] = overlaps

        top_ret, spy_ret, n, significant = self._screen_card()
        down_rate, disc_n, gate_status = self._disc_card()
        scorecard = ScorecardSnapshot(
            screen_window=f"since {as_of_iso}",
            screen_top_ret=top_ret,
            screen_spy_ret=spy_ret,
            screen_n=n,
            screen_significant=significant,
            discipline_window="21d",
            discipline_reduce_down_rate=down_rate,
            discipline_n=disc_n,
            discipline_gate_status=gate_status,
        )

        return assemble_brief(
            as_of=as_of_iso,
            regime=regime,
            tilt=screen_tilt(regime),
            screen_result=screen_result,
            screen_label=label,
            top_n=top_n,
            positions=positions,
            portfolio=portfolio,
            held_tickers=held_tickers,
            cluster_overlaps=cluster_overlaps,
            scorecard=scorecard,
            concentration_threshold=concentration_threshold,
        )
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_weekly_brief_use_case.py -v`
Expected: PASS (regime + execute + determinism tests).

- [ ] **Step 5: Commit**

```bash
git add application/weekly_brief_use_case.py tests/test_weekly_brief_use_case.py
git commit -m "feat(brief): WeeklyBriefUseCase composition (screen + discipline + regime + concentration + scorecard)"
```

---

## Task 9: `weekly-brief` CLI command (`application/cli.py`)

**Files:**
- Modify: `application/cli.py`
- Test: `tests/test_cli_weekly_brief.py`

The command wires real adapters, generates the brief, prints the masked summary, and writes the full markdown to a gitignored `data/personal/` path. It reads VIX + SPY trend from the market-data adapter and builds the CorrelationAnalyzer graph over the holdings + candidates.

- [ ] **Step 1: Write the failing test (CliRunner with a monkeypatched builder)**

```python
# tests/test_cli_weekly_brief.py
from pathlib import Path

from click.testing import CliRunner

from application import cli as cli_mod
from application.weekly_brief_use_case import WeeklyBriefUseCase, RegimeReadUseCase
from domain.screen_models import ScreenResult, ScreenCandidate, FactorScore, ScreenLabel
from domain.models import PositionRisk, PortfolioRisk
from domain.discipline import Verdict
from application.holdings_reader import Holding


def _fs():
    return (
        FactorScore("momentum", 1.1, 0.82, 0.27),
        FactorScore("revision", 0.0, 0.0, 0.0),
        FactorScore("quality", 0.0, 0.0, 0.0),
        FactorScore("value", 0.0, 0.0, 0.0),
    )


class _FakeScreen:
    def run(self, universe, as_of, top_n=10):  # type: ignore[no-untyped-def]
        return ScreenResult(
            as_of,
            (ScreenCandidate("AAPL", 0.42, _fs(), 1.3, "momentum", ScreenLabel.RESEARCH_ONLY),),
            500, "NEUTRAL", None, False,
        )


class _FakeHoldingsRisk:
    def execute(self, holdings, start, end):  # type: ignore[no-untyped-def]
        return {
            "positions": [
                PositionRisk("RIVN", 10.0, Verdict.REDUCE, 0.7, -1.2, 0.0, -0.1, 0.4, 0.1,
                             ("broken_trend",), -0.45, "Margin", False, "broken trend"),
            ],
            "portfolio": PortfolioRisk(1, 1.0, 0.10, {"REDUCE": 1}),
        }


def test_weekly_brief_cli_masks_stdout_and_writes_gitignored_file(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    out_file = tmp_path / "weekly_brief.md"
    holdings_csv = tmp_path / "holdings.csv"
    holdings_csv.write_text("symbol,quantity,book value (cad),exchange,account type\nRIVN,10,500,NASDAQ,Margin\n")

    def _fake_build(market, holdings, report_dir):  # noqa: ANN001
        uc = WeeklyBriefUseCase(
            screen=_FakeScreen(),
            holdings_risk=_FakeHoldingsRisk(),
            regime_reader=RegimeReadUseCase(vix_provider=lambda: 20.0, spy_trend_provider=lambda: 0.1),
            screen_label_fn=lambda rd: ScreenLabel.RESEARCH_ONLY,
            cluster_peers_fn=lambda t: [],
            screen_scorecard_fn=lambda: (None, None, 0, False),
            discipline_scorecard_fn=lambda: (0.58, 5462, "PENDING"),
        )
        return uc, ["AAPL", "RIVN"]

    monkeypatch.setattr(cli_mod, "_build_weekly_brief", _fake_build)

    runner = CliRunner()
    result = runner.invoke(
        cli_mod.cli,
        ["weekly-brief", "--holdings", str(holdings_csv), "--out", str(out_file)],
    )
    assert result.exit_code == 0, result.output
    # stdout is masked: no holding ticker, no P&L.
    assert "RIVN" not in result.output
    assert "HOLDINGS (masked)" in result.output
    # full markdown written, and it DOES contain the holding ticker.
    assert out_file.exists()
    assert "RIVN" in out_file.read_text()


def test_weekly_brief_default_out_is_gitignored_personal_dir():  # type: ignore[no-untyped-def]
    # The default --out must live under data/personal/ (gitignored).
    params = {p.name: p for p in cli_mod.weekly_brief.params}
    assert params["out"].default.startswith("data/personal/")
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_cli_weekly_brief.py -v`
Expected: FAIL with `AttributeError: module 'application.cli' has no attribute '_build_weekly_brief'` (and `weekly_brief`).

- [ ] **Step 3: Implement the command + builder helper**

Add near the other `_build_*` helpers in `application/cli.py`:

```python
def _build_weekly_brief(
    market: str, holdings: list[Any], report_dir: str
) -> "tuple[Any, list[str]]":
    """Wire real adapters into a WeeklyBriefUseCase. Returns (use_case, universe)."""
    from datetime import datetime as _dt

    from adapters.ml.correlation_analyzer import CorrelationAnalyzer
    from application.evidence_screen_use_case import (
        EvidenceScreenUseCase,
        label_from_verdict_file,
    )
    from application.discipline_log import read_assessments, resolve_flags
    from application.holdings_risk import HoldingsRiskAssessmentUseCase
    from application.forward_tracking_use_case import ForwardTrackingUseCase
    from application.price_returns import load_price_series
    from application.weekly_brief_use_case import RegimeReadUseCase, WeeklyBriefUseCase
    from domain.trend_rules import trend_health as _trend_health

    deps = _build_dependencies(market)
    store = deps["store"]
    market_data = deps["market_data"]
    universe = _get_backtest_universe(market)

    # Screen ports: reuse the same adapters Phase-A's screen-candidates CLI wires.
    screen = _build_evidence_screen(deps)  # existing helper used by screen-candidates

    def _price_provider(ticker: str) -> list[tuple[Any, float]]:
        end = _dt.now()
        start = end - timedelta(days=420)
        return load_price_series(ticker, start, end)

    holdings_risk = HoldingsRiskAssessmentUseCase(price_provider=_price_provider, narrator=None)

    def _vix() -> float:
        series = load_price_series("^VIX", _dt.now() - timedelta(days=10), _dt.now())
        return series[-1][1] if series else 20.0

    def _spy_trend() -> float:
        series = load_price_series("SPY", _dt.now() - timedelta(days=420), _dt.now())
        closes = [c for _, c in series]
        if len(closes) < 200:
            return 0.0
        sma = sum(closes[-200:]) / 200
        # ATR proxy: stdev of daily abs change over last 20 closes.
        diffs = [abs(closes[i] - closes[i - 1]) for i in range(-20, 0)]
        atr = sum(diffs) / len(diffs) if diffs else None
        th = _trend_health(closes[-1], sma, atr)
        return th if th is not None else 0.0

    regime_reader = RegimeReadUseCase(vix_provider=_vix, spy_trend_provider=_spy_trend)

    # Concentration: build a CorrelationAnalyzer graph over holdings + universe head.
    analyzer = CorrelationAnalyzer()
    held = [h.ticker for h in holdings]
    graph_tickers = list(dict.fromkeys(held + universe[:100]))
    signals_by_ticker = {
        t: market_data.get_signals(t, datetime.now())  # MarketDataPort
        for t in graph_tickers
    }
    try:
        analyzer.build_graph(signals_by_ticker)
    except Exception:
        pass  # concentration overlaps degrade to empty if the graph can't build

    def _cluster_peers(ticker: str) -> list[str]:
        try:
            return analyzer.get_cluster_peers(ticker)
        except Exception:
            return []

    forward = ForwardTrackingUseCase(store, market_data)

    def _screen_scorecard() -> tuple[float | None, float | None, int, bool]:
        records = forward.get_track_record()
        # No live forward window yet → abstain honestly.
        return (None, None, len(records), False)

    def _discipline_scorecard() -> tuple[float | None, int, str]:
        log_path = "data/personal/discipline_log.jsonl"
        try:
            logged = read_assessments(log_path)
        except Exception:
            return (None, 0, "NO-LOG")
        res = resolve_flags(logged, _price_provider, horizon_days=21)
        n = int(res.get("resolved", 0))
        dr = res.get("down_rate_on_reduce")
        brier = res.get("brier", 1.0)
        gate = "PROCEED" if (dr is not None and dr >= 0.55 and brier <= 0.45 and n >= 30) else "PENDING"
        return (dr, n, gate)

    uc = WeeklyBriefUseCase(
        screen=screen,
        holdings_risk=holdings_risk,
        regime_reader=regime_reader,
        screen_label_fn=label_from_verdict_file,
        cluster_peers_fn=_cluster_peers,
        screen_scorecard_fn=_screen_scorecard,
        discipline_scorecard_fn=_discipline_scorecard,
    )
    return uc, universe


@cli.command("weekly-brief")
@click.option("--market", default="us", show_default=True, help="Market config")
@click.option(
    "--holdings",
    default="data/personal/holdings-report-2026-06-07.csv",
    show_default=True,
    help="Holdings CSV (gitignored).",
)
@click.option(
    "--out",
    default="data/personal/weekly_brief.md",
    show_default=True,
    help="Full markdown brief (gitignored — contains holdings detail).",
)
@click.option("--report-dir", default="data/reports/", show_default=True)
@click.option("--top-n", default=10, type=int, show_default=True)
def weekly_brief(market: str, holdings: str, out: str, report_dir: str, top_n: int) -> None:
    """Generate the unified weekly brief (masked stdout + gitignored full markdown).

    Composes the Phase-A evidence screen, the discipline engine, a regime tilt,
    a concentration warning, and the forward scorecard. Phase B adds no predictive
    claim; a RESEARCH_ONLY screen renders no 'buy' language.
    """
    from pathlib import Path

    from application.holdings_reader import read_holdings
    from domain.brief import to_markdown, to_stdout_masked

    held = read_holdings(holdings)
    uc, universe = _build_weekly_brief(market, held, report_dir)
    brief = uc.execute(
        universe=universe,
        holdings=held,
        as_of=datetime.now(),
        report_dir=report_dir,
        top_n=top_n,
    )

    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(to_markdown(brief))

    click.echo(to_stdout_masked(brief))
    click.echo(f"\nFull brief (gitignored) written to: {out_path}")
```

> Implementation notes for the engineer:
> - `_build_evidence_screen(deps)` — if no such helper exists yet, factor the screen-port wiring out of the existing `screen-candidates` command body (search `application/cli.py` for `EvidenceScreenUseCase(`) into a small `_build_evidence_screen(deps) -> EvidenceScreenUseCase` helper and call it from both places (DRY). Add a one-line test that it returns an `EvidenceScreenUseCase`.
> - `HoldingsRiskAssessmentUseCase(..., narrator=None)`: confirm the constructor tolerates a `None` narrator (the live `holdings-risk` command passes a template-fallback narrator). If it requires a non-None narrator, reuse exactly the narrator construction from the `holdings-risk` command body instead of `None`.
> - `market_data.get_signals(...)`: confirm the MarketDataPort method name used elsewhere in `cli.py` (grep `get_signals(`); if the project uses a different method to fetch `list[Signal]`, use that one.

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_cli_weekly_brief.py -v`
Expected: PASS (both tests; the network paths are monkeypatched out).

- [ ] **Step 5: Commit**

```bash
git add application/cli.py tests/test_cli_weekly_brief.py
git commit -m "feat(brief): weekly-brief CLI (masked stdout, gitignored markdown)"
```

---

## Task 10: Dashboard tab (`adapters/visualization/`)

**Files:**
- Create: `adapters/visualization/tabs/weekly_brief.py`
- Modify: `adapters/visualization/dashboard.py`
- Modify: `adapters/visualization/data_loader.py`
- Test: `tests/test_weekly_brief_tab.py`

The tab reads the most recent generated brief markdown (gitignored file) and renders it. It does NOT regenerate the brief (that's the CLI / scheduled job's job) — the dashboard is a viewer, keeping holdings detail off any server round-trip beyond the local file.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_weekly_brief_tab.py
from adapters.visualization.data_loader import load_weekly_brief


def test_load_weekly_brief_missing_returns_none(tmp_path) -> None:  # type: ignore[no-untyped-def]
    assert load_weekly_brief(str(tmp_path / "nope.md")) is None


def test_load_weekly_brief_reads_markdown(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / "weekly_brief.md"
    p.write_text("# WEEKLY BRIEF — 2026-06-08\n")
    assert load_weekly_brief(str(p)) == "# WEEKLY BRIEF — 2026-06-08\n"


def test_tab_module_exposes_render() -> None:
    from adapters.visualization.tabs import weekly_brief as tab
    assert callable(tab.render)
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_weekly_brief_tab.py -v`
Expected: FAIL with `ImportError: cannot import name 'load_weekly_brief'`.

- [ ] **Step 3a: Add the loader**

```python
# adapters/visualization/data_loader.py  (append)
def load_weekly_brief(path: str = "data/personal/weekly_brief.md") -> str | None:
    """Read the generated weekly-brief markdown; None if not yet generated."""
    from pathlib import Path

    p = Path(path)
    if not p.exists():
        return None
    return p.read_text()
```

- [ ] **Step 3b: Add the tab module**

```python
# adapters/visualization/tabs/weekly_brief.py
"""Weekly Brief tab — renders the most recent generated brief markdown."""

from __future__ import annotations

import streamlit as st

from adapters.visualization.data_loader import load_weekly_brief

_BRIEF_PATH = "data/personal/weekly_brief.md"


def render(path: str = _BRIEF_PATH) -> None:
    """Render the unified weekly brief (read-only viewer)."""
    st.subheader("Weekly Brief")
    md = load_weekly_brief(path)
    if md is None:
        st.info(
            "No brief generated yet. Run `python -m application.cli weekly-brief` "
            "to generate it (stays on your machine)."
        )
        return
    st.markdown(md)
    st.caption(
        "Evidence-ranked, not validated where the screen label is RESEARCH_ONLY. "
        "Phase B adds no predictive claim."
    )
```

- [ ] **Step 3c: Register the tab in `dashboard.py`**

Modify the `st.tabs([...])` block in `adapters/visualization/dashboard.py` to add a 7th tab as the FIRST tab (the brief is the headline artifact):

```python
# adapters/visualization/dashboard.py
tab0, tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    [
        "Weekly Brief",
        "Today's Opportunities",
        "Watchlist",
        "My Portfolio",
        "Stock Analysis",
        "How It Works",
        "Market Context",
    ]
)

with tab0:
    from adapters.visualization.tabs.weekly_brief import render as render_brief
    render_brief()
# ... (leave the existing tab1–tab6 `with` blocks unchanged)
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_weekly_brief_tab.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add adapters/visualization/tabs/weekly_brief.py adapters/visualization/dashboard.py adapters/visualization/data_loader.py tests/test_weekly_brief_tab.py
git commit -m "feat(brief): Weekly Brief dashboard tab (read-only viewer)"
```

---

## Task 11: Phase Exit Gate — verify, document, finalize

**Files:**
- Modify: `docs/adr/049-decision-support-engine-architecture.md`

- [ ] **Step 1: Full quality gate**

Run: `make check`
Expected: `make check` green — mypy strict passes, coverage ≥ 90%, all tests pass (existing 1347 + the new regime/brief/use-case/cli/tab tests).
If coverage on any new module < 90%, add a focused test (do NOT lower the threshold).

- [ ] **Step 2: Manual smoke of the CLI against real holdings (point-in-time + privacy)**

Run: `python -m application.cli weekly-brief --holdings data/personal/holdings-report-2026-06-07.csv`
Expected:
- Masked summary prints (regime, candidates, `HOLDINGS (masked)` counts, scorecard). NO holding tickers or P&L in stdout.
- `data/personal/weekly_brief.md` written and contains full holdings detail.
- `git status` shows the brief file is NOT tracked (covered by `data/personal/`).

Record the observed regime, candidate count, holdings verdict distribution, and scorecard line for the Phase-C entry note.

- [ ] **Step 3: Confirm the Phase Exit Gate checklist (spec §8)**

Verify and note each:
- [ ] Brief renders end-to-end (CLI + dashboard) on real holdings + the Phase-A screen, deterministically and point-in-time-safe.
- [ ] Privacy asserts pass (masked stdout, gitignored detail, only tickers to yfinance).
- [ ] Scorecard matches source records; the screen's honest label carries through with no "buy" language when `RESEARCH_ONLY`.
- [ ] `make check` green.

- [ ] **Step 4: Add the Phase-B outcome note to ADR-049**

Append a `## Phase-B Outcome (<date>)` section recording: built composition (regime + brief + WeeklyBriefUseCase + CLI + tab), the v1 scoping decisions (display-only tilt, soft concentration, research-links stub, SPY+VIX regime), the screen carried through as `RESEARCH_ONLY` with no buy language, the test count + coverage, and the **intercept note** from spec §8: capture the user's reaction to the first real brief — that reaction decides whether Phase C/D are worth building. Note which sections the user reads/acts on (discovery checkpoint).

- [ ] **Step 5: Commit**

```bash
git add docs/adr/049-decision-support-engine-architecture.md
git commit -m "docs(adr-049): Phase-B weekly brief built — outcome + Phase-C intercept note"
```

---

## Self-Review (completed by planner)

**Spec coverage:**
- §2 brief shape → Tasks 4–6 (assemble + markdown + masked) cover every section (regime/tilt, candidates, holdings verdicts, research links stub, concentration, scorecard).
- §3 architecture → `domain/regime.py` (Task 1–2), `domain/brief.py` (Task 3–6), `WeeklyBriefUseCase`/`RegimeReadUseCase` (Task 7–8), dashboard tab + CLI (Task 9–10). `RegimeReadUseCase` thin ✓; regime conditions presentation only (display-only tilt) ✓.
- §4 concentration reuse `CorrelationAnalyzer.get_cluster_peers`, framed as warning, soft flag ✓ (Task 4 + Task 9 wiring).
- §5 validation gates → determinism test (Task 8), point-in-time (holdings-risk + screen both point-in-time; brief is composition), privacy/masking (Task 6 + Task 9), scorecard fidelity (discipline numbers come straight from `resolve_flags`), label fidelity (Tasks 5/6 buy-language suppression) ✓.
- §6 testing → unit + Hypothesis for regime/brief; fakes for the use case; masked-output + gitignore-safety in CLI test; tab render test; `make check` (Task 11) ✓.
- §7 open questions → all resolved in "Context" with the spec's lean defaults ✓.
- §8 phase exit gate → Task 11 ✓.

**Placeholder scan:** No "TBD/handle edge cases/similar to Task N". The three grep-confirm notes in Task 9 (`_build_evidence_screen`, `narrator=None`, `get_signals`) are explicit verification steps with the exact fallback action, not placeholders — they exist because the screen-port wiring and the MarketDataPort method name must be read from the live `cli.py` rather than guessed.

**Type consistency:** `assemble_brief` keyword args match between Task 4 definition and Task 8 call site. `ScorecardSnapshot` fields match between Task 3, Task 5, Task 8. `screen_scorecard_fn` returns `(top_ret, spy_ret, n, significant)` and `discipline_scorecard_fn` returns `(down_rate, n, gate_status)` consistently in Tasks 8 and 9. `Verdict`/`ScreenLabel`/`PositionRisk`/`PortfolioRisk` use the verbatim signatures from the component report.
