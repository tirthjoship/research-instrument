# Financial Intelligence Engine v1 — Implementation Spec & Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax. Each phase produces working, tested software on its own. **Phase 1 is the priority — if the weekend runs short, ship Phase 1 fully before anything else.**

**Date:** 2026-06-04
**Status:** Approved (scope locked: "Lock it in" tier, "Validated engine" protected)
**Branch:** `feat/intelligence-engine-v1`
**ADR:** 038 (to be written in Task 0)
**Predecessor:** Phase 5.4 (996 tests). Supersedes the Phase 5.5 UX-only spec.

---

## Why this exists (the reframe)

Six consecutive dashboard redesigns (5.0→5.5) polished the *presentation* of a conviction score that has **never been validated against forward returns**, while the only validated component — the technical ML model — backtests at coin-flip (5d accuracy 0.52, p=0.1464). The "backtest" emits a **fabricated** return metric: `model_excess_returns_per_fold = [a - 0.5 for a in accs]` (`backtest_runner.py:98`) — accuracy-minus-baseline relabeled as returns. `compute_sharpe_vs_spy` exists but is **never called**.

This project stops repainting the frame and builds the painting: a **validated, event-aware, track-record-weighted intelligence engine** with **honest confidence and abstention**. The differentiator vs SimplyWallSt (valuation visualization) is *event-causal reasoning + measured signal quality + honest uncertainty*.

**Hard requirement (owner):** real-money use → **high precision, few false positives.** "I want winners coming out." Accuracy is banned as a headline metric. Everything is evaluated by **precision of the top picks**.

---

## Locked decisions

1. **Validation-first.** No new signal is trusted until the conviction backtest (Phase 1) measures it. Build proceeds in parallel, but the validation harness is the spine and the protected deliverable.
2. **Precision-first evaluation.** Headline metric = **Top-Decile Hit Rate**. Metric suite = Precision@top-decile, monotonic precision–conviction curve, F₀.₅, Expected-Profit-per-signal, real Sharpe vs SPY. (Sources locked in prior research session.)
3. **Reuse the dormant event engine.** Phase 4D (`gemini_event_classifier.py`, `event_impact_analyzer.py`, `event_causal_features.py`, `config/events/sector_mapping.yaml`, `EventCategory` enum) already models `geopolitical` (Iran→Energy↑/Tech↓) and `labor_layoffs`. Gaps: feed it live news, add one category (`government_investment`), wire its output into conviction.
4. **Independent free signals only.** Analyst upgrade/downgrade (Finnhub free + yfinance history) + event/news. No paywalled scraping (Motley Fool/SA/Zacks/TipRanks/Bloomberg = off-limits). Free articles via search→trafilatura→Gemini are **v2**, not this weekend.
5. **Learn the weights.** Replace hand-set `ConvictionWeights` magic numbers with weights fit to historical precision.
6. **Honest UX, not a 6th redesign.** Extend the existing dashboard: Top-Decile Hit Rate headline, per-pick evidence + confidence, **abstention** ("no high-conviction picks today"), signal-feedback panel. No tab restructure this round.

## Non-goals (explicitly v2)

Meta-labeling, conformal prediction layer, full options/short-interest squeeze radar, full-article LLM synthesis at scale, position sizing (Kelly). Each is referenced in the research dossier; none ships this weekend.

---

## Success criteria (Definition of Done)

| # | Criterion | Verified by |
|---|---|---|
| 1 | Conviction backtest runs over ≥2yr walk-forward and emits the full precision suite | `backtest-conviction` CLI report JSON |
| 2 | The fabricated `[a-0.5]` returns are gone; real Sharpe vs SPY is computed and reported | `backtest_runner.py` + report contains real per-fold returns |
| 3 | Top-Decile Hit Rate is the dashboard headline; every conviction number shows its backtested hit rate | Dashboard screenshot |
| 4 | `government_investment` event category exists end-to-end (enum → prompt → YAML → sub-score) | `test_event_*` + a Trump-Intel-stake fixture |
| 5 | A news/event headline measurably moves a ticker's conviction, point-in-time safe | `test_event_conviction` |
| 6 | A fresh analyst upgrade from a historically-accurate firm raises conviction | `test_analyst_service` |
| 7 | Learned weights are fit from history and either beat hand-set on held-out precision **or** the null is reported honestly | `weight_learning` report |
| 8 | Dashboard abstains (shows "no high-conviction picks") when nothing clears the validated precision threshold | `test_abstention` + dashboard |
| 9 | All quality gates pass: `make check` (black, isort, mypy strict, ruff, pytest), pre-commit clean | CI green |
| 10 | Test count ≥ 1050 (996 existing + new) | `pytest` |

---

## File structure map

### New files
| File | Responsibility |
|---|---|
| `application/precision_metrics.py` | Pure functions: `precision_at_decile`, `monotonic_precision_curve`, `f_beta`, `expected_profit_per_signal` |
| `application/conviction_backtest.py` | Walk-forward conviction backtest: score→select→join forward returns→metric suite + real Sharpe |
| `domain/event_service.py` | Pure: `event_conviction_score(events, sector, impacts, now)` → 1–10 |
| `domain/analyst_service.py` | Pure: `score_firm_accuracy`, `analyst_conviction_score` |
| `domain/analyst.py` | `AnalystRating` frozen dataclass + `AnalystAction` enum |
| `adapters/data/alphavantage_news_adapter.py` | `NewsHeadlinePort` impl — free NEWS_SENTIMENT, point-in-time |
| `adapters/data/finnhub_analyst_adapter.py` | `AnalystRatingsPort` impl — free upgrade/downgrade + yfinance history |
| `application/weight_learning.py` | Fit `ConvictionWeights` from historical precision; persist to YAML |
| `config/conviction_weights.yaml` | Learned weights (loaded with fallback to dataclass defaults) |
| `tests/test_precision_metrics.py`, `tests/test_conviction_backtest.py`, `tests/test_event_service.py`, `tests/test_analyst_service.py`, `tests/test_alphavantage_news_adapter.py`, `tests/test_finnhub_analyst_adapter.py`, `tests/test_weight_learning.py`, `tests/fakes/fake_news_source.py`, `tests/fakes/fake_analyst_source.py` | Tests + fakes |
| `docs/adr/038-financial-intelligence-engine.md` | ADR |

### Modified files
| File | Change |
|---|---|
| `application/backtest_runner.py` | Delete fake `[a-0.5]` returns; wire `compute_sharpe_vs_spy` with real returns |
| `domain/models.py:311` | Add `GOVERNMENT_INVESTMENT = "government_investment"` to `EventCategory` |
| `domain/conviction.py:73` | Add `event_signal` and `analyst_signal` weights to `ConvictionWeights` |
| `domain/conviction_service.py:80` | `rank_opportunities` — add `allow_abstention: bool = False` |
| `domain/ports.py` | Add `NewsHeadlinePort`, `AnalystRatingsPort` protocols |
| `application/conviction_use_case.py:196` | `_compute_sub_scores` — add `event_signal` + `analyst_signal` dimensions; load learned weights |
| `adapters/ml/gemini_event_classifier.py:19` | Add `government_investment` to system prompt category list |
| `config/events/sector_mapping.yaml` | Add `government_investment` mapping |
| `adapters/visualization/...` (data_loader, a dashboard tab) | Headline = Top-Decile Hit Rate; per-pick evidence + confidence; abstention; signal-feedback panel |
| `config/markets/us.yaml` | Add `alphavantage` + `finnhub` API key refs (env vars), conviction precision threshold |
| `CLAUDE.md`, `CONTEXT.md`, `README.md` | Status + new commands |

No deletions.

---

## Task 0: Branch + ADR (5 min)

- [ ] Create branch `feat/intelligence-engine-v1` off the current branch.
- [ ] Write `docs/adr/038-financial-intelligence-engine.md` — Context (validation gap + fabricated returns + dormant event engine), Decision (the 6 locked decisions above), Alternatives (6th UX redesign — rejected; meta-label/conformal — deferred to v2), Consequences.
- [ ] Commit: `docs: ADR-038 financial intelligence engine v1`

---

## Phase 1 — Validation Harness (THE PRIORITY)

**Goal:** A real economic backtest of the conviction score with the precision suite. Ships independently. If the weekend collapses, this is what survives.

### Task 1.1: Precision metrics module

**Files:** Create `application/precision_metrics.py`; Test `tests/test_precision_metrics.py`

- [ ] **Step 1 — failing tests.** Each metric is a pure function over `(scores: list[float], forward_returns: list[float])` where a "win" = forward_return > benchmark_return for that row.

```python
# tests/test_precision_metrics.py
from application.precision_metrics import (
    precision_at_decile, monotonic_precision_curve, f_beta, expected_profit_per_signal,
)

def test_precision_at_decile_perfect_ranking():
    # 10 names; top scorers are exactly the winners
    scores  = [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]
    wins    = [1, 1, 1, 1, 1, 0, 0, 0, 0, 0]  # 1 = beat benchmark
    # top decile = top 1 name (10% of 10) → it won → precision 1.0
    assert precision_at_decile(scores, wins, decile=0.1) == 1.0

def test_precision_at_decile_random_is_base_rate():
    scores = list(range(20))
    wins   = [1, 0] * 10                      # 50% base rate, uncorrelated with score
    p = precision_at_decile(scores, wins, decile=0.5)
    assert 0.3 <= p <= 0.7                    # near base rate

def test_monotonic_curve_detects_monotonic():
    scores = list(range(100))
    wins   = [1 if s >= 50 else 0 for s in scores]  # higher score → more wins
    curve = monotonic_precision_curve(scores, wins, n_bins=5)
    assert curve == sorted(curve)            # non-decreasing
    assert len(curve) == 5

def test_f_beta_half_weights_precision():
    # precision 1.0, recall 0.5 → F0.5 should exceed F1
    assert f_beta(precision=1.0, recall=0.5, beta=0.5) > f_beta(1.0, 0.5, 1.0)

def test_expected_profit_positive_when_precision_high():
    ep = expected_profit_per_signal(precision=0.7, avg_win=0.06, avg_loss=0.04, cost=0.001)
    assert ep > 0
    ep2 = expected_profit_per_signal(precision=0.4, avg_win=0.05, avg_loss=0.05, cost=0.002)
    assert ep2 < 0
```

- [ ] **Step 2** — run, verify fail (ImportError).
- [ ] **Step 3 — implement.**

```python
# application/precision_metrics.py
"""Precision-first evaluation metrics. Pure functions, no I/O."""
from __future__ import annotations


def _rank_desc(scores: list[float], wins: list[int]) -> list[int]:
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    return [wins[i] for i in order]


def precision_at_decile(scores: list[float], wins: list[int], decile: float = 0.1) -> float:
    """Fraction of the top `decile` (by score) that won. decile in (0,1]."""
    if not scores:
        return 0.0
    ranked = _rank_desc(scores, wins)
    k = max(1, round(len(ranked) * decile))
    top = ranked[:k]
    return sum(top) / len(top)


def monotonic_precision_curve(scores: list[float], wins: list[int], n_bins: int = 10) -> list[float]:
    """Precision per score-bin, ordered lowest-score bin → highest. A healthy
    conviction score yields a non-decreasing curve."""
    if not scores:
        return [0.0] * n_bins
    order = sorted(range(len(scores)), key=lambda i: scores[i])  # ascending
    binned = [wins[i] for i in order]
    out: list[float] = []
    size = max(1, len(binned) // n_bins)
    for b in range(n_bins):
        chunk = binned[b * size : (b + 1) * size] if b < n_bins - 1 else binned[b * size :]
        out.append(sum(chunk) / len(chunk) if chunk else 0.0)
    return out


def f_beta(precision: float, recall: float, beta: float = 0.5) -> float:
    """F-beta. beta<1 weights precision over recall."""
    b2 = beta * beta
    denom = b2 * precision + recall
    if denom == 0:
        return 0.0
    return (1 + b2) * precision * recall / denom


def expected_profit_per_signal(precision: float, avg_win: float, avg_loss: float, cost: float) -> float:
    """E[profit] = P(win)*avg_win - P(loss)*avg_loss - cost. The real-money gate."""
    return precision * avg_win - (1 - precision) * avg_loss - cost
```

- [ ] **Step 4** — run tests, verify pass.
- [ ] **Step 5** — commit: `feat: precision-first evaluation metrics`

### Task 1.2: Conviction backtest harness

**Files:** Create `application/conviction_backtest.py`; Test `tests/test_conviction_backtest.py`
**Reuse:** `compute_sharpe_vs_spy`, `compute_binomial_pvalue` from `backtest_runner.py`; `precision_metrics`.

**Design:** Input = a list of historical scan dates + a callable `score_fn(date) -> dict[ticker, conviction]` (injected; in tests a fake, in prod a point-in-time `ConvictionScoringUseCase`) + a `forward_return_fn(ticker, date) -> float` and `benchmark_return_fn(date) -> float`. For each date: score all tickers, mark win = forward_return > benchmark, accumulate (score, win, forward_return). Output the precision suite + real Sharpe (model = mean forward return of top-decile basket per date; spy = benchmark per date) + p-value.

- [ ] **Step 1 — failing test** (fake score/return fns; assert the report keys + that a perfectly-correlated fake yields precision@decile==1.0 and positive excess Sharpe).
- [ ] **Step 2** — verify fail.
- [ ] **Step 3 — implement** `run_conviction_backtest(scan_dates, tickers, score_fn, forward_return_fn, benchmark_return_fn, decile=0.1) -> dict`. Build per-date top-decile basket return series and benchmark series; call `compute_sharpe_vs_spy(model_returns, spy_returns)`; call the four precision metrics on the pooled (score, win) arrays; compute avg_win/avg_loss from winning/losing forward returns; `expected_profit_per_signal(precision_at_decile, avg_win, avg_loss, cost=0.001)`. Return dict with: `top_decile_hit_rate`, `precision_curve`, `f_beta_0_5`, `expected_profit_per_signal`, `model_sharpe`, `spy_sharpe`, `excess_sharpe`, `p_value`, `n_signals`, `n_dates`.
- [ ] **Step 4** — verify pass.
- [ ] **Step 5** — commit: `feat: conviction backtest harness with precision suite`

### Task 1.3: Kill the fabricated returns; wire real Sharpe

**Files:** Modify `application/backtest_runner.py`; Test `tests/test_backtest_runner.py`

- [ ] **Step 1 — failing test:** assert `run_backtest_report` output for a horizon does **not** contain `model_excess_returns_per_fold` equal to `[acc-0.5...]`, and **does** contain a `sharpe` block (`model_sharpe`, `spy_sharpe`, `excess_sharpe`). (If real per-fold returns aren't yet persisted, the honest fix is to report Sharpe as `null` with a `returns_source: "unavailable"` note rather than fabricate — assert that explicit honesty.)
- [ ] **Step 2** — verify fail.
- [ ] **Step 3 — implement:** remove line 98 `model_returns = [a - 0.5 for a in accs]`. If stored runs lack real returns, set `"sharpe": None, "returns_source": "directional_accuracy_only"` and drop the fake key. Where real returns exist (conviction backtest), call `compute_sharpe_vs_spy`. Never relabel accuracy as returns.
- [ ] **Step 4** — verify pass.
- [ ] **Step 5** — commit: `fix: remove fabricated excess-returns; report honest Sharpe or null`

### Task 1.4: CLI + report

**Files:** Modify the CLI module (find existing Click/argparse entry; mirror `pretrain`/`run-backtest`); reuse report-writing pattern from `backtest_runner.run_backtest_report`.

- [ ] Add `backtest-conviction --years 2 --decile 0.1` that wires the prod point-in-time scorer (`ConvictionScoringUseCase` over historical scan dates from stored data / reconstructed) into `run_conviction_backtest`, writes `data/reports/conviction_backtest_<ts>.json`, and logs **Top-Decile Hit Rate** as the headline line.
- [ ] Test: smoke test the CLI wiring with a tiny fake universe (2–3 dates).
- [ ] Commit: `feat: backtest-conviction CLI + report`

**Phase 1 success:** `python -m <cli> backtest-conviction --years 2` prints a Top-Decile Hit Rate and writes the full precision suite. This number now governs the dashboard and the abstention threshold.

---

## Phase 2 — Event Intelligence Revival

**Goal:** Feed news into the existing classifier; add the government-investment category; produce an event sub-score for conviction. Point-in-time safe.

### Task 2.1: `government_investment` category, end-to-end

**Files:** Modify `domain/models.py:311`, `adapters/ml/gemini_event_classifier.py:19`, `config/events/sector_mapping.yaml`; Test `tests/test_event_models.py`, `tests/test_gemini_event_classifier.py`

- [ ] Test: `EventCategory("government_investment")` resolves; classifier system prompt string contains `government_investment`; YAML loads a mapping for it.
- [ ] Implement: add `GOVERNMENT_INVESTMENT = "government_investment"` to the enum; add to the classifier's `_SYSTEM_PROMPT` category list with a one-line definition ("government takes an equity stake in / directly funds a company or sector"); add YAML:

```yaml
  government_investment:
    - sector: Technology
      direction: 1
    - sector: Industrials
      direction: 1
    - sector: Semiconductors
      direction: 1
```

- [ ] Verify pass. Commit: `feat: add government_investment event category (Trump-Intel-stake class)`

### Task 2.2: News headline source (Alpha Vantage, free, point-in-time)

**Files:** Add `NewsHeadlinePort` to `domain/ports.py`; create `adapters/data/alphavantage_news_adapter.py`, `tests/fakes/fake_news_source.py`, `tests/test_alphavantage_news_adapter.py`

- [ ] Port:

```python
@runtime_checkable
class NewsHeadlinePort(Protocol):
    """Recent news headlines with publish timestamps, point-in-time safe."""
    def get_recent_headlines(
        self, ticker: str, since: datetime, until: datetime | None = None
    ) -> list[tuple[str, str]]: ...   # [(headline, "YYYY-MM-DD"), ...], publish-time only
```

- [ ] Adapter: call AlphaVantage `NEWS_SENTIMENT` (`apikey` from env `ALPHAVANTAGE_API_KEY`), filter `time_published <= until`, return `(title, date)`. Respect the 25-req/day free limit via the existing cache mixin (cache 6h). Fake source returns canned `[(headline, date)]` for tests — **CI never hits the network** (project rule #5).
- [ ] Tests: fake-driven; assert point-in-time filtering drops future-dated items.
- [ ] Commit: `feat: Alpha Vantage news headline adapter (NewsHeadlinePort)`

### Task 2.3: Event sub-score (pure domain)

**Files:** Create `domain/event_service.py`; Test `tests/test_event_service.py`

- [ ] Test: events with bullish classified direction in a sector with positive learned impact → score > 5; stale events decay toward neutral; no events → 5.0 (neutral).
- [ ] Implement:

```python
# domain/event_service.py
"""Event → conviction sub-score. Pure functions, no I/O."""
from __future__ import annotations
import math
from datetime import datetime
from domain.models import ClassifiedEvent, EventSectorImpact


def event_conviction_score(
    events: list[ClassifiedEvent],
    sector: str,
    impacts: dict[tuple, EventSectorImpact],   # (category, sector) -> impact
    now: datetime,
) -> float:
    """1–10. Aggregates classified events weighted by learned sector magnitude,
    exponential time-decay (half-life from impact), and classifier confidence."""
    if not events:
        return 5.0
    signal = 0.0
    for ev in events:
        impact = impacts.get((ev.category, sector))
        if impact is None:
            continue
        age_days = (now - datetime.strptime(ev.event_date, "%Y-%m-%d")).days
        decay = 0.5 ** (max(age_days, 0) / impact.half_life_days)
        signal += ev.direction * ev.confidence * impact.magnitude * decay
    return max(1.0, min(10.0, 5.0 + signal * 5.0))
```

- [ ] Verify pass. Commit: `feat: event_conviction_score domain function`

### Task 2.4: Wire event sub-score into conviction

**Files:** Modify `domain/conviction.py:73` (add `event_signal: float = 1.0` weight), `application/conviction_use_case.py:196` (`_compute_sub_scores` gains an `event_signal` dimension fed by `event_conviction_score`, sourced from the classifier over `NewsHeadlinePort` headlines + `EventImpactAnalyzer` impacts); Test `tests/test_conviction_use_case.py`

- [ ] Test: a ticker with a fresh bullish `government_investment` event scores higher conviction than the same ticker without it (point-in-time: event dated after scan_time is ignored).
- [ ] Implement the wiring; ensure future-dated events are filtered (mirror `_filter_future_signals`).
- [ ] Verify pass. Commit: `feat: wire event intelligence into conviction score`

**Phase 2 success:** Criterion 4 & 5 met — Trump-Intel-stake-class news moves conviction, point-in-time enforced.

---

## Phase 3 — Analyst Upgrade/Downgrade Signal

**Goal:** Independent, track-record-weighted analyst signal.

### Task 3.1: Models + port

**Files:** Create `domain/analyst.py`; add `AnalystRatingsPort` to `domain/ports.py`; Test `tests/test_analyst_models.py`

- [ ] `AnalystAction(Enum)`: `UPGRADE`, `DOWNGRADE`, `INIT`, `MAINTAIN`. `AnalystRating` frozen dataclass: `ticker, firm, rating, prior_rating: str|None, action: AnalystAction, price_target: float|None, published_at: datetime, source: str`. Validate `published_at` tz-aware.
- [ ] Port:

```python
@runtime_checkable
class AnalystRatingsPort(Protocol):
    def get_rating_events(
        self, ticker: str, since: datetime, until: datetime | None = None
    ) -> list[AnalystRating]: ...
```

- [ ] Commit: `feat: analyst rating models + AnalystRatingsPort`

### Task 3.2: Finnhub adapter (free) + yfinance history

**Files:** Create `adapters/data/finnhub_analyst_adapter.py`, `tests/fakes/fake_analyst_source.py`, `tests/test_finnhub_analyst_adapter.py`

- [ ] Adapter: Finnhub `/stock/upgrade-downgrade` (env `FINNHUB_API_KEY`, 60/min free) mapped to `AnalystRating` (`gradeTime`→`published_at`, `company`→`firm`, `fromGrade/toGrade`, `action`→`AnalystAction`); yfinance `upgrades_downgrades` for multi-year history. Cache via mixin. Point-in-time filter on `published_at`. Fake for CI.
- [ ] Tests: fake-driven; future-dated events dropped; label normalization (Overweight/Outperform/Buy → bullish) via a lookup table.
- [ ] Commit: `feat: Finnhub + yfinance analyst ratings adapter`

### Task 3.3: Track-record scorer (pure domain)

**Files:** Create `domain/analyst_service.py`; Test `tests/test_analyst_service.py`

- [ ] `score_firm_accuracy(events, forward_return_fn) -> dict[firm, float]`: per firm, directional hit rate of their calls vs realized forward returns (min 10 calls else neutral 0.5).
- [ ] `analyst_conviction_score(recent_events, firm_scores, now) -> float` (1–10): recent upgrades by high-accuracy firms push up; downgrades push down; freshness-decayed. No events → 5.0.
- [ ] Tests: fresh upgrade by 0.7-accuracy firm > same by unknown firm > stale upgrade.
- [ ] Commit: `feat: analyst track-record scorer + conviction sub-score`

### Task 3.4: Wire analyst sub-score into conviction

**Files:** Modify `domain/conviction.py` (add `analyst_signal: float = 1.0`), `application/conviction_use_case.py:196`; Test `tests/test_conviction_use_case.py`

- [ ] Test: fresh upgrade from accurate firm raises conviction; point-in-time safe.
- [ ] Implement wiring (sub-score from `analyst_conviction_score`). The two weak ML-linked dimensions stay but are downweighted by Phase 4 learning.
- [ ] Commit: `feat: wire analyst signal into conviction score`

**Phase 3 success:** Criterion 6 met.

---

## Phase 4 — Learned Conviction Weights

**Goal:** Replace hand-set magic-number weights with weights fit to historical precision.

### Task 4.1: Weight learning

**Files:** Create `application/weight_learning.py`, `config/conviction_weights.yaml`; Test `tests/test_weight_learning.py`

- [ ] `fit_weights(history: list[tuple[dict_subscores, win: int]]) -> ConvictionWeights`: constrained non-negative logistic fit (or coordinate grid search if sklearn unavailable) maximizing precision@decile on a temporal holdout; persist to YAML; clamp weights ≥ 0.
- [ ] Tests: on synthetic data where one sub-score perfectly predicts wins, that sub-score's learned weight is the largest.
- [ ] Commit: `feat: learn conviction weights from historical precision`

### Task 4.2 + 4.3: Load + compare

**Files:** Modify `application/conviction_use_case.py` (load `config/conviction_weights.yaml`, fallback to `ConvictionWeights()` defaults); rerun Phase 1 backtest with learned weights.

- [ ] Test: loader falls back cleanly when YAML absent.
- [ ] Run `backtest-conviction` with hand-set vs learned; record both Top-Decile Hit Rates in the ADR.
- [ ] **Honesty gate:** if learned ≤ hand-set on held-out precision, report the null in the ADR — do not cherry-pick.
- [ ] Commit: `feat: load learned conviction weights with safe fallback`

**Phase 4 success:** Criterion 7 met (improvement or honest null).

---

## Phase 5 — Honest-Confidence UX

**Goal:** Surface the validated engine honestly. Extends the existing dashboard; no tab restructure.

### Task 5.1: Top-Decile Hit Rate headline + per-number hit rate

**Files:** Modify dashboard data_loader + the landing tab; Test `tests/test_*` for the loader.

- [ ] Loader reads the latest `conviction_backtest_*.json`; dashboard headline shows **Top-Decile Hit Rate: XX%** with a tooltip ("of our highest-conviction picks, the share that beat SPY over the horizon, walk-forward N dates"). Every conviction number renders with `· hit rate XX%` from the backtest.
- [ ] Commit: `feat: Top-Decile Hit Rate headline + per-pick backtested hit rate`

### Task 5.2: Per-pick evidence + confidence

**Files:** Modify the opportunity/pick card renderer.

- [ ] Each pick shows: confidence (from conviction + backtested hit rate), the **event/news evidence** ("Intel ▲ — government stake; policy tailwind, Technology +"), analyst evidence ("2 upgrades in 14d from firms with 68% hit rate"), and a one-line "why."
- [ ] Commit: `feat: per-pick evidence (event + analyst) and confidence`

### Task 5.3: Abstention

**Files:** Modify `domain/conviction_service.py:80` (`rank_opportunities(..., allow_abstention=False)`); dashboard uses `allow_abstention=True` with the Phase 1 precision threshold; Test `tests/test_conviction_service.py`

- [ ] Test: with `allow_abstention=True` and all scores below threshold, returns `[]` (no fabricated fill).
- [ ] Implement: when `allow_abstention`, skip the below-threshold fill (lines 117-121) and return only qualifying picks. Dashboard renders "No high-conviction picks today — the engine is sitting out. (Sitting out is a position.)"
- [ ] Commit: `feat: honest abstention — no fabricated picks below precision threshold`

### Task 5.4: Signal-feedback panel

**Files:** Modify a dashboard panel.

- [ ] Show which signals fired today (event/analyst/smart-money/fundamental/sentiment) + each signal's historical hit rate (per-signal precision from the Phase 1 backtest). This is the "insightful feedback" loop.
- [ ] Commit: `feat: signal-feedback panel with per-signal historical hit rates`

**Phase 5 success:** Criteria 3 & 8 met.

---

## Cross-cutting rules (every task)

- TDD: failing test → run-fail → minimal impl → run-pass → commit. Small fixtures, fakes only — **no network in CI** (rule #5).
- `domain/` imports only stdlib/typing/dataclasses/datetime/enum (rule #1). `event_service.py`, `analyst_service.py`, `precision_metrics.py` (the last lives in `application/`, may import domain) obey this.
- Point-in-time everywhere: every new signal filters to `published_at/event_date <= prediction_time` (rule #2).
- `make check` green before each commit; never `--no-verify`. Conventional commits. Feature branch only (rule #4).

## Self-review checklist (run before handoff)
- [ ] Every success criterion (1–10) maps to a task. ✅ (1,2→P1; 4,5→P2; 6→P3; 7→P4; 3,8→P5; 9,10→cross-cutting)
- [ ] No placeholders / TBDs in any step.
- [ ] Type names consistent: `ConvictionWeights.event_signal`/`analyst_signal`, `AnalystAction`, `NewsHeadlinePort`, `AnalystRatingsPort`, `event_conviction_score`, `analyst_conviction_score`, `precision_at_decile`.
- [ ] Phase 1 is independently shippable and first.
