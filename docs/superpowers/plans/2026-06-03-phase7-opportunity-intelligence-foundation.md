# Phase 7: Opportunity Intelligence Foundation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the stock recommender from a direction predictor into an opportunity surfacing engine with conviction scoring, SEC EDGAR smart money signals, and a polished opportunity feed dashboard.

**Architecture:** New domain models (ConvictionScore, OpportunityCard, SmartMoneySignal) + new ports (SmartMoneyPort) + conviction scoring service + two SEC EDGAR adapters (13D filings, Form 4 insider trades) + smart money feature engineer + dashboard evolution (Command Center → Opportunity Feed, freshness header with S&P sparkline). All follow existing hexagonal patterns — domain stays pure, adapters implement ports.

**Tech Stack:** Python 3.12+, pytest, Streamlit, Plotly, requests (SEC EDGAR API), yfinance (S&P sparkline), existing SQLite store pattern.

**Design Spec:** `docs/superpowers/specs/2026-06-03-opportunity-intelligence-engine-design.md`

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `domain/conviction.py` | ConvictionScore, ConvictionWeights, OpportunityCard, SmartMoneySignal domain models |
| `domain/conviction_service.py` | Pure conviction scoring logic — compute sub-scores, weighted aggregation, ranking |
| `adapters/data/sec_edgar_adapter.py` | SEC EDGAR 13D + Form 4 fetching, implements SmartMoneyPort |
| `adapters/ml/smart_money_engineer.py` | Feature extraction from smart money signals (insider clusters, stake %) |
| `application/conviction_use_case.py` | ConvictionScoringUseCase — orchestrates signal gathering → scoring → card generation |
| `adapters/visualization/components/opportunity_cards.py` | HTML card rendering for opportunity feed |
| `tests/test_conviction_models.py` | Domain model tests |
| `tests/test_conviction_service.py` | Scoring logic tests |
| `tests/test_sec_edgar_adapter.py` | SEC EDGAR adapter tests |
| `tests/test_smart_money_engineer.py` | Feature engineer tests |
| `tests/test_conviction_use_case.py` | Use case integration tests |
| `tests/test_opportunity_cards.py` | Card rendering tests |

### Modified Files

| File | Change |
|------|--------|
| `domain/ports.py` | Add SmartMoneyPort protocol |
| `domain/services.py` | Add validate_smart_money_signals() |
| `adapters/visualization/dashboard.py` | Add freshness header bar + S&P sparkline, update tab names |
| `adapters/visualization/tabs/command_center.py` | Rewrite → Opportunity Feed with conviction-ranked cards |
| `adapters/visualization/tabs/market_pulse.py` | Add S&P intraday sparkline section |
| `adapters/visualization/components/styles.py` | Add conviction/freshness/opportunity CSS classes |
| `adapters/visualization/components/formatters.py` | Add conviction_badge_html, freshness_indicator_html, action_badge_html |
| `adapters/visualization/data_loader.py` | Add load_conviction_scores(), load_smart_money_signals() |
| `adapters/visualization/action_runner.py` | Add run_conviction_scan() with progress tracking |
| `config/markets/us.yaml` | Add conviction_weights and scan_schedule sections |

---

## Task 1: Domain Models — ConvictionScore, OpportunityCard, SmartMoneySignal

**Files:**
- Create: `domain/conviction.py`
- Test: `tests/test_conviction_models.py`

- [ ] **Step 1: Write failing tests for domain models**

```python
"""Tests for conviction domain models."""

from datetime import datetime

import pytest

from domain.conviction import (
    ActionType,
    ConvictionScore,
    ConvictionWeights,
    FreshnessLevel,
    OpportunityCard,
    SmartMoneySignal,
    SmartMoneyType,
)


class TestSmartMoneySignal:
    def test_valid_creation(self) -> None:
        s = SmartMoneySignal(
            ticker="NVDA",
            signal_type=SmartMoneyType.FORM_13D,
            filer_name="ValueAct Capital",
            stake_pct=5.2,
            transaction_value=450_000_000.0,
            filed_date="2026-06-01",
            is_activist=True,
            source_url="https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany",
        )
        assert s.ticker == "NVDA"
        assert s.is_activist is True

    def test_form4_creation(self) -> None:
        s = SmartMoneySignal(
            ticker="AAPL",
            signal_type=SmartMoneyType.FORM_4,
            filer_name="Tim Cook",
            stake_pct=None,
            transaction_value=2_300_000.0,
            filed_date="2026-06-02",
            is_activist=False,
            insider_role="CEO",
            transaction_type="buy",
        )
        assert s.insider_role == "CEO"
        assert s.transaction_type == "buy"

    def test_stake_pct_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="stake_pct"):
            SmartMoneySignal(
                ticker="NVDA",
                signal_type=SmartMoneyType.FORM_13D,
                filer_name="X",
                stake_pct=-1.0,
                transaction_value=100.0,
                filed_date="2026-06-01",
                is_activist=False,
            )


class TestConvictionWeights:
    def test_default_weights(self) -> None:
        w = ConvictionWeights()
        assert w.signal_agreement == 1.0
        assert w.smart_money == 1.5
        assert w.ml_direction == 0.3

    def test_custom_weights(self) -> None:
        w = ConvictionWeights(smart_money=2.0, ml_direction=0.1)
        assert w.smart_money == 2.0
        assert w.ml_direction == 0.1


class TestConvictionScore:
    def test_valid_creation(self) -> None:
        cs = ConvictionScore(
            ticker="NVDA",
            score=8.2,
            sub_scores={
                "signal_agreement": 9.0,
                "smart_money": 8.5,
                "sentiment_momentum": 7.0,
                "fundamental_basis": 6.5,
                "temporal_freshness": 9.0,
                "ml_direction": 5.0,
            },
            signals_firing=4,
            freshest_signal=datetime(2026, 6, 3, 14, 15),
            explanation="4 of 6 layers aligned — activist 13D + insider buying + sentiment shift",
        )
        assert cs.score == 8.2
        assert cs.signals_firing == 4

    def test_score_clamped_1_to_10(self) -> None:
        with pytest.raises(ValueError, match="score must be between"):
            ConvictionScore(
                ticker="X", score=11.0, sub_scores={},
                signals_firing=0, freshest_signal=datetime.now(),
                explanation="",
            )

    def test_freshness_level(self) -> None:
        now = datetime(2026, 6, 3, 14, 0)
        cs = ConvictionScore(
            ticker="X", score=5.0, sub_scores={},
            signals_firing=1,
            freshest_signal=datetime(2026, 6, 3, 12, 0),
            explanation="",
        )
        assert cs.freshness_level(now) == FreshnessLevel.FRESH

    def test_freshness_stale(self) -> None:
        now = datetime(2026, 6, 3, 14, 0)
        cs = ConvictionScore(
            ticker="X", score=5.0, sub_scores={},
            signals_firing=1,
            freshest_signal=datetime(2026, 6, 1, 10, 0),
            explanation="",
        )
        assert cs.freshness_level(now) == FreshnessLevel.STALE


class TestOpportunityCard:
    def test_valid_creation(self) -> None:
        card = OpportunityCard(
            ticker="NVDA",
            conviction=8.2,
            action=ActionType.BUY,
            alert_summary="4 of 6 layers aligned — activist 13D + insider cluster",
            evidence=[
                "An activist investor (ValueAct Capital) just filed a 13D — they bought 5.2% of the company.",
                "Social media chatter turned sharply positive over the last 3 days.",
            ],
            suggestion="Multiple independent signals converging. Only invest money you're comfortable losing.",
            risks=[
                "The 13D filing could be passive (no activist intent)",
                "Broad market downturn could drag this stock down regardless",
            ],
            generated_at=datetime(2026, 6, 3, 14, 15),
            conviction_score=ConvictionScore(
                ticker="NVDA", score=8.2, sub_scores={},
                signals_firing=4, freshest_signal=datetime(2026, 6, 3, 14, 0),
                explanation="",
            ),
        )
        assert card.action == ActionType.BUY
        assert len(card.evidence) == 2
        assert len(card.risks) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender" && python -m pytest tests/test_conviction_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'domain.conviction'`

- [ ] **Step 3: Implement domain models**

```python
"""Conviction scoring domain models — opportunity surfacing engine.

Pure domain types for conviction-based opportunity scoring.
No external dependencies — only stdlib.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum


class SmartMoneyType(str, Enum):
    """Type of smart money signal."""
    FORM_13D = "13D"
    FORM_4 = "Form4"


class ActionType(str, Enum):
    """Suggested action for an opportunity."""
    BUY = "BUY"
    WATCH = "WATCH"
    HOLD = "HOLD"
    SELL = "SELL"


class FreshnessLevel(str, Enum):
    """Signal freshness classification."""
    FRESH = "fresh"       # < 4 hours
    RECENT = "recent"     # 4-24 hours
    STALE = "stale"       # > 24 hours


@dataclass(frozen=True)
class SmartMoneySignal:
    """SEC filing signal — 13D activist stake or Form 4 insider trade."""
    ticker: str
    signal_type: SmartMoneyType
    filer_name: str
    stake_pct: float | None  # 13D only — percentage of company
    transaction_value: float
    filed_date: str  # YYYY-MM-DD
    is_activist: bool
    source_url: str = ""
    insider_role: str = ""  # Form 4 only — CEO, CFO, Director, etc.
    transaction_type: str = ""  # Form 4 only — buy/sell

    def __post_init__(self) -> None:
        if self.stake_pct is not None and self.stake_pct < 0:
            msg = "stake_pct must be >= 0"
            raise ValueError(msg)


@dataclass(frozen=True)
class ConvictionWeights:
    """Tunable weights for conviction scoring dimensions."""
    signal_agreement: float = 1.0
    smart_money: float = 1.5
    sentiment_momentum: float = 1.0
    fundamental_basis: float = 1.0
    temporal_freshness: float = 1.2
    ml_direction: float = 0.3


@dataclass(frozen=True)
class ConvictionScore:
    """Conviction score for a single ticker — weighted multi-signal aggregation."""
    ticker: str
    score: float  # 1.0 - 10.0
    sub_scores: dict[str, float]
    signals_firing: int
    freshest_signal: datetime
    explanation: str

    def __post_init__(self) -> None:
        if not (1.0 <= self.score <= 10.0):
            msg = f"score must be between 1.0 and 10.0, got {self.score}"
            raise ValueError(msg)

    def freshness_level(self, now: datetime) -> FreshnessLevel:
        """Classify freshness based on age of newest signal."""
        age = now - self.freshest_signal
        if age < timedelta(hours=4):
            return FreshnessLevel.FRESH
        if age < timedelta(hours=24):
            return FreshnessLevel.RECENT
        return FreshnessLevel.STALE


@dataclass(frozen=True)
class OpportunityCard:
    """4-part opportunity output: Alert, Evidence, Suggestion, Risk."""
    ticker: str
    conviction: float
    action: ActionType
    alert_summary: str
    evidence: list[str]
    suggestion: str
    risks: list[str]
    generated_at: datetime
    conviction_score: ConvictionScore
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender" && python -m pytest tests/test_conviction_models.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add domain/conviction.py tests/test_conviction_models.py
git commit -m "feat: add conviction scoring domain models (ConvictionScore, OpportunityCard, SmartMoneySignal)"
```

---

## Task 2: Domain Port — SmartMoneyPort + Validation

**Files:**
- Modify: `domain/ports.py`
- Modify: `domain/services.py`
- Test: `tests/test_domain_services.py` (append)

- [ ] **Step 1: Write failing tests for smart money validation**

Append to `tests/test_domain_services.py`:

```python
from domain.conviction import SmartMoneySignal, SmartMoneyType


class TestValidateSmartMoneySignals:
    def test_valid_signals_pass(self) -> None:
        from domain.services import validate_smart_money_signals

        signals = [
            SmartMoneySignal(
                ticker="NVDA", signal_type=SmartMoneyType.FORM_4,
                filer_name="CEO", stake_pct=None, transaction_value=1_000_000.0,
                filed_date="2026-06-01", is_activist=False,
            ),
        ]
        validate_smart_money_signals(
            prediction_time=datetime(2026, 6, 3),
            signals=signals,
        )

    def test_future_filing_raises(self) -> None:
        from domain.services import validate_smart_money_signals

        signals = [
            SmartMoneySignal(
                ticker="NVDA", signal_type=SmartMoneyType.FORM_4,
                filer_name="CEO", stake_pct=None, transaction_value=1_000_000.0,
                filed_date="2026-06-10", is_activist=False,
            ),
        ]
        with pytest.raises(LookAheadBiasError):
            validate_smart_money_signals(
                prediction_time=datetime(2026, 6, 3),
                signals=signals,
            )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender" && python -m pytest tests/test_domain_services.py::TestValidateSmartMoneySignals -v`
Expected: FAIL — `cannot import name 'validate_smart_money_signals'`

- [ ] **Step 3: Add SmartMoneyPort to domain/ports.py**

Append to `domain/ports.py`:

```python
from domain.conviction import SmartMoneySignal


class SmartMoneyPort(Protocol):
    """Port for fetching SEC filing signals (13D, Form 4)."""

    def get_13d_filings(
        self,
        ticker: str | None = None,
        since_date: str | None = None,
    ) -> list[SmartMoneySignal]:
        """Fetch 13D activist filings. If ticker=None, scan all tracked tickers."""
        ...

    def get_form4_filings(
        self,
        ticker: str | None = None,
        since_date: str | None = None,
    ) -> list[SmartMoneySignal]:
        """Fetch Form 4 insider trades. If ticker=None, scan all tracked tickers."""
        ...

    def get_all_signals(
        self,
        ticker: str | None = None,
        since_date: str | None = None,
    ) -> list[SmartMoneySignal]:
        """Combined 13D + Form 4 signals."""
        ...
```

- [ ] **Step 4: Add validate_smart_money_signals to domain/services.py**

Append to `domain/services.py`:

```python
from domain.conviction import SmartMoneySignal


def validate_smart_money_signals(
    prediction_time: datetime,
    signals: list[SmartMoneySignal],
) -> None:
    """Verify all smart money filing dates are <= prediction_time."""
    for s in signals:
        filed = datetime.strptime(s.filed_date, "%Y-%m-%d")
        if filed > prediction_time:
            raise LookAheadBiasError(
                f"SmartMoney filing date {s.filed_date} > prediction_time {prediction_time}"
            )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender" && python -m pytest tests/test_domain_services.py::TestValidateSmartMoneySignals -v`
Expected: ALL PASS

- [ ] **Step 6: Run full test suite for regression**

Run: `cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender" && python -m pytest tests/ -v --tb=short -q`
Expected: ALL existing tests still pass

- [ ] **Step 7: Commit**

```bash
git add domain/ports.py domain/services.py tests/test_domain_services.py
git commit -m "feat: add SmartMoneyPort protocol and validate_smart_money_signals"
```

---

## Task 3: Conviction Scoring Service

**Files:**
- Create: `domain/conviction_service.py`
- Test: `tests/test_conviction_service.py`

- [ ] **Step 1: Write failing tests for conviction scoring**

```python
"""Tests for conviction scoring service — pure domain logic."""

from datetime import datetime, timedelta

import pytest

from domain.conviction import (
    ActionType,
    ConvictionScore,
    ConvictionWeights,
    SmartMoneySignal,
    SmartMoneyType,
)
from domain.conviction_service import (
    compute_conviction,
    compute_freshness_score,
    determine_action,
    rank_opportunities,
)


class TestFreshnessScore:
    def test_very_fresh(self) -> None:
        now = datetime(2026, 6, 3, 14, 0)
        ts = datetime(2026, 6, 3, 13, 0)  # 1 hour ago
        assert compute_freshness_score(ts, now) == 10.0

    def test_medium_fresh(self) -> None:
        now = datetime(2026, 6, 3, 14, 0)
        ts = datetime(2026, 6, 3, 4, 0)  # 10 hours ago
        assert compute_freshness_score(ts, now) == 8.0

    def test_one_to_three_days(self) -> None:
        now = datetime(2026, 6, 3, 14, 0)
        ts = datetime(2026, 6, 1, 14, 0)  # 2 days ago
        assert compute_freshness_score(ts, now) == 6.0

    def test_three_to_seven_days(self) -> None:
        now = datetime(2026, 6, 3, 14, 0)
        ts = datetime(2026, 5, 29, 14, 0)  # 5 days ago
        assert compute_freshness_score(ts, now) == 4.0

    def test_over_seven_days(self) -> None:
        now = datetime(2026, 6, 3, 14, 0)
        ts = datetime(2026, 5, 20, 14, 0)  # 14 days ago
        assert compute_freshness_score(ts, now) == 2.0


class TestDetermineAction:
    def test_high_conviction_buy(self) -> None:
        assert determine_action(8.5, is_bullish=True) == ActionType.BUY

    def test_medium_conviction_watch(self) -> None:
        assert determine_action(5.5, is_bullish=True) == ActionType.WATCH

    def test_high_conviction_bearish_sell(self) -> None:
        assert determine_action(8.0, is_bullish=False) == ActionType.SELL

    def test_low_conviction_watch(self) -> None:
        assert determine_action(3.0, is_bullish=True) == ActionType.WATCH


class TestComputeConviction:
    def test_all_signals_aligned(self) -> None:
        sub_scores = {
            "signal_agreement": 9.0,
            "smart_money": 8.0,
            "sentiment_momentum": 7.0,
            "fundamental_basis": 6.0,
            "temporal_freshness": 9.0,
            "ml_direction": 5.0,
        }
        weights = ConvictionWeights()
        score = compute_conviction(sub_scores, weights)
        assert 1.0 <= score <= 10.0
        # Smart money weighted 1.5x should pull score up
        assert score > 6.0

    def test_only_technical_signals(self) -> None:
        sub_scores = {
            "signal_agreement": 3.0,
            "smart_money": 0.0,
            "sentiment_momentum": 0.0,
            "fundamental_basis": 0.0,
            "temporal_freshness": 5.0,
            "ml_direction": 6.0,
        }
        weights = ConvictionWeights()
        score = compute_conviction(sub_scores, weights)
        # Low conviction — only ML + weak agreement
        assert score < 4.0

    def test_custom_weights(self) -> None:
        sub_scores = {
            "signal_agreement": 5.0,
            "smart_money": 10.0,
            "sentiment_momentum": 5.0,
            "fundamental_basis": 5.0,
            "temporal_freshness": 5.0,
            "ml_direction": 5.0,
        }
        heavy_smart = ConvictionWeights(smart_money=3.0)
        light_smart = ConvictionWeights(smart_money=0.5)
        assert compute_conviction(sub_scores, heavy_smart) > compute_conviction(sub_scores, light_smart)


class TestRankOpportunities:
    def test_ranks_by_score_descending(self) -> None:
        now = datetime(2026, 6, 3, 14, 0)
        scores = [
            ConvictionScore(ticker="A", score=5.0, sub_scores={}, signals_firing=2,
                          freshest_signal=now, explanation=""),
            ConvictionScore(ticker="B", score=9.0, sub_scores={}, signals_firing=5,
                          freshest_signal=now, explanation=""),
            ConvictionScore(ticker="C", score=3.0, sub_scores={}, signals_firing=1,
                          freshest_signal=now, explanation=""),
        ]
        ranked = rank_opportunities(scores, top_n=15, pinned=set())
        assert [r.ticker for r in ranked] == ["B", "A", "C"]

    def test_pinned_always_included(self) -> None:
        now = datetime(2026, 6, 3, 14, 0)
        scores = [
            ConvictionScore(ticker="A", score=9.0, sub_scores={}, signals_firing=5,
                          freshest_signal=now, explanation=""),
            ConvictionScore(ticker="B", score=8.0, sub_scores={}, signals_firing=4,
                          freshest_signal=now, explanation=""),
            ConvictionScore(ticker="PINNED", score=2.0, sub_scores={}, signals_firing=1,
                          freshest_signal=now, explanation=""),
        ]
        ranked = rank_opportunities(scores, top_n=2, pinned={"PINNED"})
        tickers = [r.ticker for r in ranked]
        assert "PINNED" in tickers
        assert "A" in tickers

    def test_minimum_threshold_filters(self) -> None:
        now = datetime(2026, 6, 3, 14, 0)
        scores = [
            ConvictionScore(ticker="A", score=8.0, sub_scores={}, signals_firing=4,
                          freshest_signal=now, explanation=""),
            ConvictionScore(ticker="LOW", score=1.5, sub_scores={}, signals_firing=1,
                          freshest_signal=now, explanation=""),
        ]
        ranked = rank_opportunities(scores, top_n=15, pinned=set(), min_score=3.0)
        assert len(ranked) == 1
        assert ranked[0].ticker == "A"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender" && python -m pytest tests/test_conviction_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'domain.conviction_service'`

- [ ] **Step 3: Implement conviction scoring service**

```python
"""Conviction scoring service — pure domain logic.

Computes weighted multi-signal conviction scores and ranks opportunities.
No I/O, no external dependencies.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from domain.conviction import (
    ActionType,
    ConvictionScore,
    ConvictionWeights,
)


def compute_freshness_score(signal_time: datetime, now: datetime) -> float:
    """Score signal freshness on a 0-10 scale based on age."""
    age = now - signal_time
    if age < timedelta(hours=4):
        return 10.0
    if age < timedelta(hours=24):
        return 8.0
    if age < timedelta(days=3):
        return 6.0
    if age < timedelta(days=7):
        return 4.0
    return 2.0


def determine_action(score: float, is_bullish: bool) -> ActionType:
    """Map conviction score + direction to an action."""
    if score >= 7.0:
        return ActionType.BUY if is_bullish else ActionType.SELL
    return ActionType.WATCH


def compute_conviction(
    sub_scores: dict[str, float],
    weights: ConvictionWeights,
) -> float:
    """Compute weighted average conviction score, clamped to [1.0, 10.0]."""
    weight_map = {
        "signal_agreement": weights.signal_agreement,
        "smart_money": weights.smart_money,
        "sentiment_momentum": weights.sentiment_momentum,
        "fundamental_basis": weights.fundamental_basis,
        "temporal_freshness": weights.temporal_freshness,
        "ml_direction": weights.ml_direction,
    }
    total_weight = 0.0
    weighted_sum = 0.0
    for dim, w in weight_map.items():
        val = sub_scores.get(dim, 0.0)
        weighted_sum += val * w
        total_weight += w

    if total_weight == 0:
        return 1.0

    raw = weighted_sum / total_weight
    return max(1.0, min(10.0, raw))


def rank_opportunities(
    scores: list[ConvictionScore],
    top_n: int = 15,
    pinned: set[str] | None = None,
    min_score: float = 3.0,
) -> list[ConvictionScore]:
    """Rank conviction scores descending. Always include pinned tickers."""
    pinned = pinned or set()

    # Filter by minimum score (except pinned)
    filtered = [s for s in scores if s.score >= min_score or s.ticker in pinned]

    # Sort descending by score
    filtered.sort(key=lambda s: s.score, reverse=True)

    # Take top_n, ensuring pinned are included
    top = filtered[:top_n]
    top_tickers = {s.ticker for s in top}

    # Add any pinned tickers that didn't make the cut
    for s in filtered:
        if s.ticker in pinned and s.ticker not in top_tickers:
            top.append(s)

    return top
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender" && python -m pytest tests/test_conviction_service.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add domain/conviction_service.py tests/test_conviction_service.py
git commit -m "feat: add conviction scoring service — weighted multi-signal aggregation + ranking"
```

---

## Task 4: SEC EDGAR Adapter — 13D + Form 4

**Files:**
- Create: `adapters/data/sec_edgar_adapter.py`
- Test: `tests/test_sec_edgar_adapter.py`

- [ ] **Step 1: Write failing tests with fake HTTP responses**

```python
"""Tests for SEC EDGAR adapter — 13D filings + Form 4 insider trades.

Uses requests_mock or monkeypatch to avoid hitting real SEC API in tests.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from adapters.data.sec_edgar_adapter import SECEdgarAdapter
from domain.conviction import SmartMoneySignal, SmartMoneyType

# Sample SEC EDGAR XBRL JSON response for full-text search
SAMPLE_EDGAR_SEARCH_RESPONSE = {
    "hits": {
        "hits": [
            {
                "_source": {
                    "file_date": "2026-06-01",
                    "display_names": ["ValueAct Capital"],
                    "entity_name": "NVIDIA Corp",
                    "ticker": "NVDA",
                    "form_type": "SC 13D",
                    "file_num": "005-12345",
                    "file_description": "Schedule 13D",
                },
                "_id": "0001234567-26-000001",
            }
        ]
    }
}

SAMPLE_FORM4_RESPONSE = {
    "hits": {
        "hits": [
            {
                "_source": {
                    "file_date": "2026-06-02",
                    "display_names": ["Tim Cook"],
                    "entity_name": "Apple Inc",
                    "ticker": "AAPL",
                    "form_type": "4",
                    "file_description": "Statement of changes in beneficial ownership",
                },
                "_id": "0001234567-26-000002",
            }
        ]
    }
}


class TestSECEdgarAdapter:
    def test_get_13d_filings_parses_response(self) -> None:
        adapter = SECEdgarAdapter(rate_limit_seconds=0.0)
        with patch("adapters.data.sec_edgar_adapter.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = SAMPLE_EDGAR_SEARCH_RESPONSE
            mock_get.return_value = mock_resp

            signals = adapter.get_13d_filings(ticker="NVDA")

        assert len(signals) == 1
        assert signals[0].ticker == "NVDA"
        assert signals[0].signal_type == SmartMoneyType.FORM_13D
        assert signals[0].filer_name == "ValueAct Capital"

    def test_get_form4_filings_parses_response(self) -> None:
        adapter = SECEdgarAdapter(rate_limit_seconds=0.0)
        with patch("adapters.data.sec_edgar_adapter.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = SAMPLE_FORM4_RESPONSE
            mock_get.return_value = mock_resp

            signals = adapter.get_form4_filings(ticker="AAPL")

        assert len(signals) == 1
        assert signals[0].ticker == "AAPL"
        assert signals[0].signal_type == SmartMoneyType.FORM_4

    def test_get_all_signals_combines(self) -> None:
        adapter = SECEdgarAdapter(rate_limit_seconds=0.0)
        with patch("adapters.data.sec_edgar_adapter.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            # Return different results for 13D vs Form 4 calls
            mock_resp.json.side_effect = [
                SAMPLE_EDGAR_SEARCH_RESPONSE,
                SAMPLE_FORM4_RESPONSE,
            ]
            mock_get.return_value = mock_resp

            signals = adapter.get_all_signals()

        assert len(signals) == 2

    def test_handles_http_error_gracefully(self) -> None:
        adapter = SECEdgarAdapter(rate_limit_seconds=0.0)
        with patch("adapters.data.sec_edgar_adapter.requests.get") as mock_get:
            mock_get.side_effect = Exception("Connection refused")
            signals = adapter.get_13d_filings(ticker="NVDA")
        assert signals == []

    def test_respects_rate_limit(self) -> None:
        adapter = SECEdgarAdapter(rate_limit_seconds=0.0)
        assert adapter.rate_limit_seconds == 0.0

    def test_user_agent_header_set(self) -> None:
        adapter = SECEdgarAdapter(
            rate_limit_seconds=0.0,
            user_agent="TestApp test@example.com",
        )
        assert "TestApp" in adapter._user_agent
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender" && python -m pytest tests/test_sec_edgar_adapter.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'adapters.data.sec_edgar_adapter'`

- [ ] **Step 3: Implement SEC EDGAR adapter**

```python
"""SEC EDGAR adapter — SmartMoneyPort implementation.

Fetches 13D (activist stakes) and Form 4 (insider trades) via EDGAR EFTS API.
SEC requires a User-Agent header with contact info.
"""

from __future__ import annotations

import time

import requests
from loguru import logger

from domain.conviction import SmartMoneySignal, SmartMoneyType

_EDGAR_EFTS_URL = "https://efts.sec.gov/LATEST/search-index"
_EDGAR_FULL_TEXT_URL = "https://efts.sec.gov/LATEST/search-index"
_EDGAR_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"


class SECEdgarAdapter:
    """SmartMoneyPort implementation using SEC EDGAR EFTS full-text search.

    Queries EDGAR for SC 13D and Form 4 filings. Rate-limited per SEC policy
    (max 10 requests/second, recommended 1/second for courtesy).
    """

    def __init__(
        self,
        rate_limit_seconds: float = 1.0,
        user_agent: str = "StockRecommender research@example.com",
    ) -> None:
        self._rate_limit_seconds = rate_limit_seconds
        self._user_agent = user_agent
        self._last_request_time: float = 0.0

    @property
    def rate_limit_seconds(self) -> float:
        return self._rate_limit_seconds

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < self._rate_limit_seconds:
            time.sleep(self._rate_limit_seconds - elapsed)
        self._last_request_time = time.time()

    def _search(
        self,
        form_type: str,
        ticker: str | None = None,
        since_date: str | None = None,
    ) -> list[dict]:
        """Query EDGAR EFTS full-text search API."""
        params: dict[str, str] = {
            "q": ticker or "",
            "forms": form_type,
            "dateRange": "custom",
        }
        if since_date:
            params["startdt"] = since_date
        headers = {"User-Agent": self._user_agent}

        try:
            self._throttle()
            resp = requests.get(
                "https://efts.sec.gov/LATEST/search-index",
                params=params,
                headers=headers,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("hits", {}).get("hits", [])
        except Exception as exc:
            logger.warning("EDGAR search failed for {}: {}", form_type, exc)
            return []

    def get_13d_filings(
        self,
        ticker: str | None = None,
        since_date: str | None = None,
    ) -> list[SmartMoneySignal]:
        """Fetch SC 13D activist filings."""
        hits = self._search("SC 13D", ticker, since_date)
        signals: list[SmartMoneySignal] = []
        for hit in hits:
            src = hit.get("_source", {})
            filers = src.get("display_names", [])
            signals.append(
                SmartMoneySignal(
                    ticker=src.get("ticker", ticker or "UNKNOWN"),
                    signal_type=SmartMoneyType.FORM_13D,
                    filer_name=filers[0] if filers else "Unknown Filer",
                    stake_pct=None,  # Not in search results — need filing detail
                    transaction_value=0.0,
                    filed_date=src.get("file_date", ""),
                    is_activist="13D" in src.get("form_type", ""),
                    source_url=f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&filenum={src.get('file_num', '')}",
                )
            )
        return signals

    def get_form4_filings(
        self,
        ticker: str | None = None,
        since_date: str | None = None,
    ) -> list[SmartMoneySignal]:
        """Fetch Form 4 insider trade filings."""
        hits = self._search("4", ticker, since_date)
        signals: list[SmartMoneySignal] = []
        for hit in hits:
            src = hit.get("_source", {})
            filers = src.get("display_names", [])
            signals.append(
                SmartMoneySignal(
                    ticker=src.get("ticker", ticker or "UNKNOWN"),
                    signal_type=SmartMoneyType.FORM_4,
                    filer_name=filers[0] if filers else "Unknown Insider",
                    stake_pct=None,
                    transaction_value=0.0,
                    filed_date=src.get("file_date", ""),
                    is_activist=False,
                    insider_role="",  # Not in search results
                    transaction_type="",  # Need filing XML for details
                )
            )
        return signals

    def get_all_signals(
        self,
        ticker: str | None = None,
        since_date: str | None = None,
    ) -> list[SmartMoneySignal]:
        """Combined 13D + Form 4 signals."""
        filings_13d = self.get_13d_filings(ticker, since_date)
        form4s = self.get_form4_filings(ticker, since_date)
        return filings_13d + form4s
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender" && python -m pytest tests/test_sec_edgar_adapter.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add adapters/data/sec_edgar_adapter.py tests/test_sec_edgar_adapter.py
git commit -m "feat: add SEC EDGAR adapter — 13D activist filings + Form 4 insider trades"
```

---

## Task 5: Smart Money Feature Engineer

**Files:**
- Create: `adapters/ml/smart_money_engineer.py`
- Test: `tests/test_smart_money_engineer.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for smart money feature extraction."""

from datetime import datetime

import pytest

from adapters.ml.smart_money_engineer import SmartMoneyFeatureEngineer
from domain.conviction import SmartMoneySignal, SmartMoneyType


class TestSmartMoneyFeatureEngineer:
    def setup_method(self) -> None:
        self.engineer = SmartMoneyFeatureEngineer()

    def test_no_signals_returns_zeros(self) -> None:
        features = self.engineer.compute("AAPL", [], datetime(2026, 6, 3))
        assert features["sm_13d_count"] == 0
        assert features["sm_form4_buy_count"] == 0
        assert features["sm_insider_cluster"] == 0.0

    def test_13d_filing_features(self) -> None:
        signals = [
            SmartMoneySignal(
                ticker="NVDA", signal_type=SmartMoneyType.FORM_13D,
                filer_name="ValueAct", stake_pct=5.2,
                transaction_value=450_000_000.0,
                filed_date="2026-06-01", is_activist=True,
            ),
        ]
        features = self.engineer.compute("NVDA", signals, datetime(2026, 6, 3))
        assert features["sm_13d_count"] == 1
        assert features["sm_activist_count"] == 1
        assert features["sm_max_stake_pct"] == 5.2

    def test_insider_cluster_detection(self) -> None:
        """Multiple insider buys within 7 days = cluster."""
        signals = [
            SmartMoneySignal(
                ticker="AAPL", signal_type=SmartMoneyType.FORM_4,
                filer_name=f"Insider{i}", stake_pct=None,
                transaction_value=500_000.0,
                filed_date=f"2026-06-0{i}", is_activist=False,
                transaction_type="buy",
            )
            for i in range(1, 5)
        ]
        features = self.engineer.compute("AAPL", signals, datetime(2026, 6, 5))
        assert features["sm_form4_buy_count"] == 4
        assert features["sm_insider_cluster"] >= 0.8  # High cluster score

    def test_sell_signals_tracked(self) -> None:
        signals = [
            SmartMoneySignal(
                ticker="TSLA", signal_type=SmartMoneyType.FORM_4,
                filer_name="Elon Musk", stake_pct=None,
                transaction_value=10_000_000.0,
                filed_date="2026-06-01", is_activist=False,
                transaction_type="sell",
            ),
        ]
        features = self.engineer.compute("TSLA", signals, datetime(2026, 6, 3))
        assert features["sm_form4_sell_count"] == 1
        assert features["sm_form4_buy_count"] == 0

    def test_feature_names(self) -> None:
        names = self.engineer.get_feature_names()
        assert "sm_13d_count" in names
        assert "sm_form4_buy_count" in names
        assert "sm_insider_cluster" in names
        assert len(names) == 8
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender" && python -m pytest tests/test_smart_money_engineer.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement smart money feature engineer**

```python
"""Smart money feature engineer — extract features from SEC filing signals.

8 features extracted from 13D and Form 4 filings:
- sm_13d_count: number of 13D filings in window
- sm_activist_count: number of activist 13D filings
- sm_max_stake_pct: largest reported stake percentage
- sm_form4_buy_count: insider buy transactions
- sm_form4_sell_count: insider sell transactions
- sm_total_buy_value: aggregate insider buy dollar value
- sm_total_sell_value: aggregate insider sell dollar value
- sm_insider_cluster: cluster score (0-1) based on buy count in 7-day window
"""

from __future__ import annotations

from datetime import datetime

from domain.conviction import SmartMoneySignal, SmartMoneyType

_FEATURE_NAMES = [
    "sm_13d_count",
    "sm_activist_count",
    "sm_max_stake_pct",
    "sm_form4_buy_count",
    "sm_form4_sell_count",
    "sm_total_buy_value",
    "sm_total_sell_value",
    "sm_insider_cluster",
]

_CLUSTER_THRESHOLD = 5  # 5+ insider buys in window = max cluster score


class SmartMoneyFeatureEngineer:
    """Extract features from smart money signals for conviction scoring."""

    def compute(
        self,
        ticker: str,
        signals: list[SmartMoneySignal],
        prediction_time: datetime,
    ) -> dict[str, float]:
        """Compute 8 smart money features for a single ticker."""
        ticker_signals = [s for s in signals if s.ticker == ticker]

        filings_13d = [s for s in ticker_signals if s.signal_type == SmartMoneyType.FORM_13D]
        form4s = [s for s in ticker_signals if s.signal_type == SmartMoneyType.FORM_4]
        buys = [s for s in form4s if s.transaction_type == "buy"]
        sells = [s for s in form4s if s.transaction_type == "sell"]

        stakes = [s.stake_pct for s in filings_13d if s.stake_pct is not None]

        # Insider cluster: normalized count of buys (0-1 scale)
        cluster_score = min(len(buys) / _CLUSTER_THRESHOLD, 1.0) if buys else 0.0

        return {
            "sm_13d_count": float(len(filings_13d)),
            "sm_activist_count": float(sum(1 for s in filings_13d if s.is_activist)),
            "sm_max_stake_pct": max(stakes) if stakes else 0.0,
            "sm_form4_buy_count": float(len(buys)),
            "sm_form4_sell_count": float(len(sells)),
            "sm_total_buy_value": sum(s.transaction_value for s in buys),
            "sm_total_sell_value": sum(s.transaction_value for s in sells),
            "sm_insider_cluster": cluster_score,
        }

    def get_feature_names(self) -> list[str]:
        """Return ordered list of feature names."""
        return list(_FEATURE_NAMES)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender" && python -m pytest tests/test_smart_money_engineer.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add adapters/ml/smart_money_engineer.py tests/test_smart_money_engineer.py
git commit -m "feat: add smart money feature engineer — 8 features from 13D + Form 4 signals"
```

---

## Task 6: ConvictionScoringUseCase — Orchestration

**Files:**
- Create: `application/conviction_use_case.py`
- Test: `tests/test_conviction_use_case.py`

- [ ] **Step 1: Write failing tests with fakes**

```python
"""Tests for ConvictionScoringUseCase — orchestrates signal gathering → scoring → cards."""

from datetime import datetime

import pytest

from application.conviction_use_case import ConvictionScoringUseCase
from domain.conviction import (
    ActionType,
    ConvictionWeights,
    OpportunityCard,
    SmartMoneySignal,
    SmartMoneyType,
)


class FakeSmartMoneyAdapter:
    """Fake SmartMoneyPort for testing."""

    def __init__(self, signals: list[SmartMoneySignal] | None = None) -> None:
        self._signals = signals or []

    def get_13d_filings(self, ticker=None, since_date=None):
        return [s for s in self._signals if s.signal_type == SmartMoneyType.FORM_13D]

    def get_form4_filings(self, ticker=None, since_date=None):
        return [s for s in self._signals if s.signal_type == SmartMoneyType.FORM_4]

    def get_all_signals(self, ticker=None, since_date=None):
        return list(self._signals)


class TestConvictionScoringUseCase:
    def test_empty_universe_returns_empty(self) -> None:
        uc = ConvictionScoringUseCase(
            smart_money=FakeSmartMoneyAdapter(),
            tickers=[],
            weights=ConvictionWeights(),
        )
        cards = uc.run(scan_time=datetime(2026, 6, 3, 14, 0))
        assert cards == []

    def test_produces_opportunity_cards(self) -> None:
        signals = [
            SmartMoneySignal(
                ticker="NVDA", signal_type=SmartMoneyType.FORM_13D,
                filer_name="ValueAct", stake_pct=5.2,
                transaction_value=450_000_000.0,
                filed_date="2026-06-01", is_activist=True,
            ),
            SmartMoneySignal(
                ticker="NVDA", signal_type=SmartMoneyType.FORM_4,
                filer_name="CEO", stake_pct=None,
                transaction_value=2_000_000.0,
                filed_date="2026-06-02", is_activist=False,
                transaction_type="buy",
            ),
        ]
        uc = ConvictionScoringUseCase(
            smart_money=FakeSmartMoneyAdapter(signals),
            tickers=["NVDA"],
            weights=ConvictionWeights(),
        )
        cards = uc.run(scan_time=datetime(2026, 6, 3, 14, 0))
        assert len(cards) >= 1
        assert all(isinstance(c, OpportunityCard) for c in cards)
        nvda_card = next(c for c in cards if c.ticker == "NVDA")
        assert nvda_card.conviction >= 1.0
        assert len(nvda_card.evidence) > 0
        assert len(nvda_card.risks) > 0

    def test_pinned_tickers_always_included(self) -> None:
        uc = ConvictionScoringUseCase(
            smart_money=FakeSmartMoneyAdapter(),
            tickers=["AAPL", "MSFT", "NVDA"],
            weights=ConvictionWeights(),
            pinned={"AAPL"},
        )
        cards = uc.run(scan_time=datetime(2026, 6, 3, 14, 0))
        tickers = [c.ticker for c in cards]
        assert "AAPL" in tickers

    def test_ranked_by_conviction_descending(self) -> None:
        signals = [
            SmartMoneySignal(
                ticker="NVDA", signal_type=SmartMoneyType.FORM_13D,
                filer_name="Activist", stake_pct=8.0,
                transaction_value=1_000_000_000.0,
                filed_date="2026-06-02", is_activist=True,
            ),
        ]
        uc = ConvictionScoringUseCase(
            smart_money=FakeSmartMoneyAdapter(signals),
            tickers=["AAPL", "NVDA"],
            weights=ConvictionWeights(),
        )
        cards = uc.run(scan_time=datetime(2026, 6, 3, 14, 0))
        if len(cards) >= 2:
            assert cards[0].conviction >= cards[1].conviction
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender" && python -m pytest tests/test_conviction_use_case.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement ConvictionScoringUseCase**

```python
"""ConvictionScoringUseCase — orchestrates signal gathering, scoring, and card generation.

Depends only on port interfaces. Gathers smart money signals, computes features,
scores conviction, generates opportunity cards.
"""

from __future__ import annotations

from datetime import datetime

from loguru import logger

from adapters.ml.smart_money_engineer import SmartMoneyFeatureEngineer
from domain.conviction import (
    ActionType,
    ConvictionScore,
    ConvictionWeights,
    OpportunityCard,
    SmartMoneySignal,
    SmartMoneyType,
)
from domain.conviction_service import (
    compute_conviction,
    compute_freshness_score,
    determine_action,
    rank_opportunities,
)
from domain.services import validate_smart_money_signals


class ConvictionScoringUseCase:
    """Orchestrate: gather signals → compute features → score conviction → generate cards."""

    def __init__(
        self,
        smart_money: object,  # SmartMoneyPort
        tickers: list[str],
        weights: ConvictionWeights,
        pinned: set[str] | None = None,
        top_n: int = 15,
    ) -> None:
        self._smart_money = smart_money
        self._tickers = tickers
        self._weights = weights
        self._pinned = pinned or set()
        self._top_n = top_n
        self._feature_engineer = SmartMoneyFeatureEngineer()

    def run(
        self,
        scan_time: datetime,
        progress_callback: object | None = None,
    ) -> list[OpportunityCard]:
        """Run full conviction scan and return ranked opportunity cards."""
        if not self._tickers:
            return []

        _update = progress_callback or (lambda p, m: None)

        # 1. Gather smart money signals
        logger.info("Gathering smart money signals for {} tickers", len(self._tickers))
        all_signals: list[SmartMoneySignal] = self._smart_money.get_all_signals()

        # Validate temporal boundary
        try:
            validate_smart_money_signals(scan_time, all_signals)
        except Exception as exc:
            logger.warning("Temporal validation warning: {}", exc)
            # Filter out future signals instead of failing
            all_signals = [
                s for s in all_signals
                if datetime.strptime(s.filed_date, "%Y-%m-%d") <= scan_time
            ]

        # 2. Score each ticker
        scores: list[ConvictionScore] = []
        for ticker in self._tickers:
            ticker_signals = [s for s in all_signals if s.ticker == ticker]
            features = self._feature_engineer.compute(ticker, ticker_signals, scan_time)

            # Build sub-scores from features
            sub_scores = self._compute_sub_scores(features, ticker_signals, scan_time)
            score = compute_conviction(sub_scores, self._weights)

            # Determine freshest signal
            freshest = scan_time
            for s in ticker_signals:
                try:
                    filed = datetime.strptime(s.filed_date, "%Y-%m-%d")
                    if filed > freshest or freshest == scan_time:
                        freshest = filed
                except ValueError:
                    pass
            if not ticker_signals:
                freshest = scan_time

            explanation = self._build_explanation(ticker, sub_scores, ticker_signals)

            scores.append(
                ConvictionScore(
                    ticker=ticker,
                    score=max(1.0, min(10.0, score)),
                    sub_scores=sub_scores,
                    signals_firing=sum(1 for v in sub_scores.values() if v > 2.0),
                    freshest_signal=freshest,
                    explanation=explanation,
                )
            )

        # 3. Rank
        ranked = rank_opportunities(scores, self._top_n, self._pinned)

        # 4. Generate cards
        cards: list[OpportunityCard] = []
        for cs in ranked:
            is_bullish = cs.sub_scores.get("smart_money", 0) > 3.0
            action = determine_action(cs.score, is_bullish)
            cards.append(
                OpportunityCard(
                    ticker=cs.ticker,
                    conviction=cs.score,
                    action=action,
                    alert_summary=cs.explanation,
                    evidence=self._build_evidence(cs.ticker, all_signals),
                    suggestion=self._build_suggestion(action, cs.score),
                    risks=self._build_risks(cs.ticker, all_signals),
                    generated_at=scan_time,
                    conviction_score=cs,
                )
            )

        return cards

    def _compute_sub_scores(
        self,
        features: dict[str, float],
        signals: list[SmartMoneySignal],
        scan_time: datetime,
    ) -> dict[str, float]:
        """Map raw features to 0-10 sub-scores per dimension."""
        # Smart money: scale based on 13D count + insider cluster
        sm_raw = (
            features.get("sm_13d_count", 0) * 3.0
            + features.get("sm_insider_cluster", 0) * 7.0
            + features.get("sm_activist_count", 0) * 2.0
        )
        smart_money_score = min(sm_raw, 10.0)

        # Signal agreement: count of non-zero feature dimensions
        active_features = sum(1 for v in features.values() if v > 0)
        agreement_score = min(active_features / 4.0 * 10.0, 10.0)

        # Freshness: based on most recent filing
        freshness_score = 2.0  # Default: no signals = stale
        for s in signals:
            try:
                filed = datetime.strptime(s.filed_date, "%Y-%m-%d")
                fs = compute_freshness_score(filed, scan_time)
                freshness_score = max(freshness_score, fs)
            except ValueError:
                pass

        return {
            "signal_agreement": agreement_score,
            "smart_money": smart_money_score,
            "sentiment_momentum": 5.0,  # Placeholder — wired in later phases
            "fundamental_basis": 5.0,  # Placeholder — uses existing features
            "temporal_freshness": freshness_score,
            "ml_direction": 5.0,  # Placeholder — wired to existing model output
        }

    def _build_explanation(
        self, ticker: str, sub_scores: dict[str, float], signals: list[SmartMoneySignal],
    ) -> str:
        firing = [k for k, v in sub_scores.items() if v > 3.0]
        parts = []
        if sub_scores.get("smart_money", 0) > 3.0:
            n13d = sum(1 for s in signals if s.signal_type == SmartMoneyType.FORM_13D)
            nf4 = sum(1 for s in signals if s.signal_type == SmartMoneyType.FORM_4)
            if n13d:
                parts.append(f"{n13d} activist filing(s)")
            if nf4:
                parts.append(f"{nf4} insider trade(s)")
        return f"{len(firing)} of 6 layers active — " + ", ".join(parts) if parts else f"{len(firing)} of 6 layers active"

    def _build_evidence(self, ticker: str, signals: list[SmartMoneySignal]) -> list[str]:
        evidence: list[str] = []
        for s in signals:
            if s.ticker != ticker:
                continue
            if s.signal_type == SmartMoneyType.FORM_13D:
                activist_text = "an activist" if s.is_activist else "a"
                stake_text = f" — they acquired {s.stake_pct}% of the company" if s.stake_pct else ""
                evidence.append(
                    f"{s.filer_name} filed a 13D as {activist_text} investor{stake_text}. "
                    f"Filed {s.filed_date}."
                )
            elif s.signal_type == SmartMoneyType.FORM_4:
                action_word = s.transaction_type or "traded"
                value_text = f" (${s.transaction_value:,.0f})" if s.transaction_value else ""
                evidence.append(
                    f"{s.filer_name} ({s.insider_role or 'insider'}) {action_word}{value_text}. "
                    f"Filed {s.filed_date}."
                )
        if not evidence:
            evidence.append("No specific smart money signals detected for this ticker.")
        return evidence

    def _build_suggestion(self, action: ActionType, score: float) -> str:
        suggestions = {
            ActionType.BUY: "Multiple independent signals converging. Only invest money you are comfortable losing.",
            ActionType.SELL: "Signals suggest downside risk. Review your position and consider reducing exposure.",
            ActionType.WATCH: "Something interesting brewing. Keep an eye on this — not enough conviction to act yet.",
            ActionType.HOLD: "No strong signals either way. Stay the course if you already own this.",
        }
        return suggestions.get(action, "Review the evidence and make your own decision.")

    def _build_risks(self, ticker: str, signals: list[SmartMoneySignal]) -> list[str]:
        risks = ["Broad market downturn could drag this stock down regardless of signals."]
        ticker_signals = [s for s in signals if s.ticker == ticker]
        has_13d = any(s.signal_type == SmartMoneyType.FORM_13D for s in ticker_signals)
        if has_13d:
            risks.append("The 13D filing could be passive (no activist intent to change the company).")
        has_form4 = any(s.signal_type == SmartMoneyType.FORM_4 for s in ticker_signals)
        if has_form4:
            risks.append("Insider trades can be for personal reasons unrelated to company outlook.")
        if not ticker_signals:
            risks.append("Limited signal data — conviction is based on fewer data points than ideal.")
        return risks
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender" && python -m pytest tests/test_conviction_use_case.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run full test suite for regression**

Run: `cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender" && python -m pytest tests/ -q --tb=short`
Expected: ALL PASS (518+ tests)

- [ ] **Step 6: Commit**

```bash
git add application/conviction_use_case.py tests/test_conviction_use_case.py
git commit -m "feat: add ConvictionScoringUseCase — signal gathering, scoring, card generation"
```

---

## Task 7: Dashboard Formatters + Opportunity Card Components

**Files:**
- Modify: `adapters/visualization/components/formatters.py`
- Create: `adapters/visualization/components/opportunity_cards.py`
- Modify: `adapters/visualization/components/styles.py`
- Test: `tests/test_opportunity_cards.py`
- Modify: `tests/test_formatters.py`

- [ ] **Step 1: Write failing tests for new formatters and card rendering**

```python
"""Tests for opportunity card rendering components."""

from datetime import datetime

import pytest

from adapters.visualization.components.formatters import (
    action_badge_html,
    conviction_badge_html,
    freshness_indicator_html,
)
from adapters.visualization.components.opportunity_cards import (
    render_evidence_html,
    render_opportunity_card_html,
    render_risk_html,
)
from domain.conviction import (
    ActionType,
    ConvictionScore,
    FreshnessLevel,
    OpportunityCard,
)


class TestConvictionBadge:
    def test_high_conviction_green(self) -> None:
        html = conviction_badge_html(8.5)
        assert "8.5" in html
        assert "#00C853" in html or "conviction-high" in html

    def test_medium_conviction_amber(self) -> None:
        html = conviction_badge_html(5.5)
        assert "5.5" in html

    def test_low_conviction_red(self) -> None:
        html = conviction_badge_html(2.5)
        assert "2.5" in html


class TestActionBadge:
    def test_buy_badge(self) -> None:
        html = action_badge_html(ActionType.BUY)
        assert "BUY" in html

    def test_sell_badge(self) -> None:
        html = action_badge_html(ActionType.SELL)
        assert "SELL" in html

    def test_watch_badge(self) -> None:
        html = action_badge_html(ActionType.WATCH)
        assert "WATCH" in html


class TestFreshnessIndicator:
    def test_fresh_green(self) -> None:
        html = freshness_indicator_html(FreshnessLevel.FRESH)
        assert "fresh" in html.lower() or "#00C853" in html

    def test_stale_red(self) -> None:
        html = freshness_indicator_html(FreshnessLevel.STALE)
        assert "stale" in html.lower() or "#FF1744" in html


class TestOpportunityCardHTML:
    def test_renders_full_card(self) -> None:
        card = OpportunityCard(
            ticker="NVDA",
            conviction=8.2,
            action=ActionType.BUY,
            alert_summary="4 of 6 layers aligned",
            evidence=["Activist investor filed 13D."],
            suggestion="Multiple signals converging.",
            risks=["Market downturn risk."],
            generated_at=datetime(2026, 6, 3, 14, 15),
            conviction_score=ConvictionScore(
                ticker="NVDA", score=8.2, sub_scores={},
                signals_firing=4, freshest_signal=datetime(2026, 6, 3, 14, 0),
                explanation="",
            ),
        )
        html = render_opportunity_card_html(card, now=datetime(2026, 6, 3, 14, 15))
        assert "NVDA" in html
        assert "8.2" in html
        assert "BUY" in html
        assert "Activist investor filed 13D" in html
        assert "Market downturn risk" in html

    def test_evidence_list_renders(self) -> None:
        html = render_evidence_html(["Point A.", "Point B."])
        assert "Point A" in html
        assert "Point B" in html

    def test_risk_list_renders(self) -> None:
        html = render_risk_html(["Risk 1.", "Risk 2."])
        assert "Risk 1" in html
        assert "Risk 2" in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender" && python -m pytest tests/test_opportunity_cards.py -v`
Expected: FAIL

- [ ] **Step 3: Add new formatters to formatters.py**

Append to `adapters/visualization/components/formatters.py`:

```python
from domain.conviction import ActionType, FreshnessLevel

_CONVICTION_COLORS: dict[str, str] = {
    "high": "#00C853",    # 7-10
    "medium": "#FFD600",  # 4-6.9
    "low": "#FF1744",     # 1-3.9
}

_ACTION_COLORS: dict[str, str] = {
    "BUY": "#00C853",
    "WATCH": "#FFD600",
    "HOLD": "#9E9E9E",
    "SELL": "#FF1744",
}

_FRESHNESS_COLORS: dict[str, str] = {
    "fresh": "#00C853",
    "recent": "#FFD600",
    "stale": "#FF1744",
}


def conviction_badge_html(score: float) -> str:
    """Render conviction score as a colored badge."""
    if score >= 7.0:
        color = _CONVICTION_COLORS["high"]
    elif score >= 4.0:
        color = _CONVICTION_COLORS["medium"]
    else:
        color = _CONVICTION_COLORS["low"]
    return (
        f'<span class="conviction-badge" style="background: {color}; color: white; '
        f'padding: 4px 10px; border-radius: 12px; font-weight: 600; font-size: 14px;">'
        f'{score:.1f}/10</span>'
    )


def action_badge_html(action: ActionType) -> str:
    """Render action type as a colored badge."""
    color = _ACTION_COLORS.get(action.value, "#9E9E9E")
    return (
        f'<span class="action-badge" style="background: {color}; color: white; '
        f'padding: 3px 8px; border-radius: 8px; font-weight: 600; font-size: 12px;">'
        f'{action.value}</span>'
    )


def freshness_indicator_html(level: FreshnessLevel) -> str:
    """Render freshness level as a colored dot with label."""
    color = _FRESHNESS_COLORS.get(level.value, "#9E9E9E")
    label = level.value.capitalize()
    return (
        f'<span style="color: {color}; font-size: 12px;">'
        f'● {label}</span>'
    )
```

- [ ] **Step 4: Create opportunity_cards.py component**

```python
"""Opportunity card HTML rendering for dashboard.

Renders the 4-part opportunity card: Alert, Evidence, Suggestion, Risk.
"""

from __future__ import annotations

from datetime import datetime

from adapters.visualization.components.formatters import (
    action_badge_html,
    conviction_badge_html,
    freshness_indicator_html,
)
from domain.conviction import OpportunityCard


def render_evidence_html(evidence: list[str]) -> str:
    """Render evidence list as styled HTML."""
    items = "".join(
        f'<li style="margin-bottom: 6px; color: #374151; font-size: 14px;">{e}</li>'
        for e in evidence
    )
    return f'<ul style="padding-left: 20px; margin: 8px 0;">{items}</ul>'


def render_risk_html(risks: list[str]) -> str:
    """Render risk list as styled HTML."""
    items = "".join(
        f'<li style="margin-bottom: 4px; color: #6B7280; font-size: 13px;">{r}</li>'
        for r in risks
    )
    return (
        f'<div style="background: #FFF3E0; border-radius: 8px; padding: 12px; margin-top: 8px;">'
        f'<div style="font-weight: 600; font-size: 13px; color: #E65100; margin-bottom: 6px;">'
        f'What could go wrong</div>'
        f'<ul style="padding-left: 20px; margin: 0;">{items}</ul>'
        f'</div>'
    )


def render_opportunity_card_html(card: OpportunityCard, now: datetime) -> str:
    """Render a full 4-part opportunity card as HTML."""
    freshness = card.conviction_score.freshness_level(now)

    conviction_html = conviction_badge_html(card.conviction)
    action_html = action_badge_html(card.action)
    freshness_html = freshness_indicator_html(freshness)
    evidence_html = render_evidence_html(card.evidence)
    risk_html = render_risk_html(card.risks)

    return f"""
    <div class="dashboard-card opportunity-card" style="border-left: 4px solid {'#00C853' if card.conviction >= 7 else '#FFD600' if card.conviction >= 4 else '#FF1744'};">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <div>
                <span style="font-size: 20px; font-weight: 700; color: #111827;">{card.ticker}</span>
                {conviction_html}
                {action_html}
            </div>
            <div>{freshness_html}</div>
        </div>
        <div style="font-size: 14px; color: #374151; margin-bottom: 8px;">
            {card.alert_summary}
        </div>
        <div style="margin-bottom: 8px;">
            <div style="font-weight: 600; font-size: 13px; color: #111827; margin-bottom: 4px;">Evidence</div>
            {evidence_html}
        </div>
        <div style="background: #F0F9FF; border-radius: 8px; padding: 12px; margin-bottom: 8px;">
            <div style="font-weight: 500; font-size: 14px; color: #1E40AF;">
                {card.suggestion}
            </div>
        </div>
        {risk_html}
    </div>
    """
```

- [ ] **Step 5: Add conviction CSS classes to styles.py**

Append to the `GLOBAL_CSS` string in `adapters/visualization/components/styles.py`:

```css
/* ===== Opportunity Cards ===== */
.opportunity-card {
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.opportunity-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
}
.conviction-badge {
    display: inline-block;
    margin-left: 8px;
}
.action-badge {
    display: inline-block;
    margin-left: 6px;
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender" && python -m pytest tests/test_opportunity_cards.py tests/test_formatters.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add adapters/visualization/components/formatters.py adapters/visualization/components/opportunity_cards.py adapters/visualization/components/styles.py tests/test_opportunity_cards.py
git commit -m "feat: add opportunity card HTML components — conviction badges, evidence, risk sections"
```

---

## Task 8: Dashboard Header — Freshness Bar + S&P Sparkline

**Files:**
- Modify: `adapters/visualization/dashboard.py`
- Modify: `adapters/visualization/data_loader.py`
- Test: `tests/test_dashboard_smoke.py` (append)

- [ ] **Step 1: Write failing test for S&P data loader**

Append to `tests/test_data_loader.py`:

```python
class TestLoadSPYSparkline:
    def test_returns_dict_on_missing_data(self) -> None:
        from adapters.visualization.data_loader import load_spy_sparkline
        result = load_spy_sparkline()
        assert isinstance(result, dict)
        assert "prices" in result or result == {}
```

- [ ] **Step 2: Add load_spy_sparkline to data_loader.py**

Append to `adapters/visualization/data_loader.py`:

```python
def load_spy_sparkline() -> dict[str, Any]:
    """Load intraday S&P 500 (SPY) data for sparkline. Returns empty dict on failure."""
    try:
        import yfinance as yf
        spy = yf.Ticker("SPY")
        hist = spy.history(period="1d", interval="5m")
        if hist.empty:
            return {}
        return {
            "prices": hist["Close"].tolist(),
            "times": [t.strftime("%H:%M") for t in hist.index],
            "current": float(hist["Close"].iloc[-1]),
            "open": float(hist["Open"].iloc[0]),
            "change_pct": float((hist["Close"].iloc[-1] - hist["Open"].iloc[0]) / hist["Open"].iloc[0] * 100),
            "high": float(hist["High"].max()),
            "low": float(hist["Low"].min()),
        }
    except Exception as e:
        logger.warning("Failed to load SPY sparkline: %s", e)
        return {}


def load_scan_timestamp(reports_dir: str = "data/reports") -> str | None:
    """Return timestamp of most recent scan from report files. None if no reports."""
    path = Path(reports_dir)
    if not path.exists():
        return None
    files = sorted(path.glob("backtest_report_*.json"), reverse=True)
    if not files:
        return None
    # Extract timestamp from filename: backtest_report_YYYYMMDD_HHMMSS.json
    name = files[0].stem
    parts = name.replace("backtest_report_", "")
    try:
        dt = datetime.strptime(parts, "%Y%m%d_%H%M%S")
        return dt.strftime("%b %d, %Y at %I:%M %p")
    except ValueError:
        return None
```

- [ ] **Step 3: Update dashboard.py header with freshness bar + sparkline**

Replace the branding header section in `adapters/visualization/dashboard.py` with:

```python
from adapters.visualization.data_loader import load_spy_sparkline, load_scan_timestamp

inject_global_css()

# ---- Freshness header bar ----
scan_ts = load_scan_timestamp()
spy_data = load_spy_sparkline()

_header_left = f'<h1 style="margin-bottom: 0;">Multi-Modal Stock Recommender</h1>'
_scan_line = f'Last scan: {scan_ts}' if scan_ts else 'No scan data yet'

# Market status (simple heuristic: NYSE hours 9:30-16:00 ET)
from datetime import datetime
_now = datetime.now()
_market_open = 9 * 60 + 30 <= _now.hour * 60 + _now.minute <= 16 * 60
_market_status = "OPEN" if _market_open else "CLOSED"
_market_color = "#00C853" if _market_open else "#FF1744"

_spy_html = ""
if spy_data:
    _change = spy_data.get("change_pct", 0)
    _change_color = "#00C853" if _change >= 0 else "#FF1744"
    _change_sign = "+" if _change >= 0 else ""
    _spy_html = (
        f'<span style="margin-left: 16px; font-size: 13px;">'
        f'S&P 500: ${spy_data.get("current", 0):,.2f} '
        f'<span style="color: {_change_color}; font-weight: 600;">'
        f'{_change_sign}{_change:.2f}%</span></span>'
    )

st.markdown(
    f'{_header_left}'
    f'<div style="display: flex; align-items: center; gap: 12px; color: #6B7280; font-size: 13px; margin-top: 4px;">'
    f'<span>{_scan_line}</span>'
    f'<span style="color: {_market_color}; font-weight: 600;">Market: {_market_status}</span>'
    f'{_spy_html}'
    f'</div>',
    unsafe_allow_html=True,
)
```

- [ ] **Step 4: Run smoke tests**

Run: `cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender" && python -m pytest tests/test_data_loader.py tests/test_dashboard_smoke.py -v --tb=short`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add adapters/visualization/dashboard.py adapters/visualization/data_loader.py tests/test_data_loader.py
git commit -m "feat: add freshness header bar with S&P 500 sparkline and market status"
```

---

## Task 9: Command Center → Opportunity Feed Tab

**Files:**
- Modify: `adapters/visualization/tabs/command_center.py`
- Modify: `adapters/visualization/action_runner.py`
- Modify: `adapters/visualization/dashboard.py` (tab label)
- Test: `tests/test_dashboard_smoke.py` (update)

- [ ] **Step 1: Add run_conviction_scan to action_runner.py**

Append to `adapters/visualization/action_runner.py`:

```python
from domain.conviction import ConvictionWeights, OpportunityCard


def run_conviction_scan(
    db_path: str = "data/recommendations.db",
    market: str = "us",
    progress_callback: Callable[[float, str], None] | None = None,
) -> list[OpportunityCard]:
    """Run conviction scan with progress tracking.

    Stages: Load config (20%) → Fetch signals (50%) → Score (80%) → Generate cards (100%).
    """
    _update = progress_callback or (lambda p, m: None)

    _update(0.1, "Loading configuration...")
    from config.loader import load_market_config
    config = load_market_config(market)

    _update(0.2, "Loading ticker universe...")
    from adapters.data.sec_edgar_adapter import SECEdgarAdapter

    tickers_config = config.get("universe", {}).get("ticker_files", [])
    tickers: list[str] = []
    for tf in tickers_config:
        try:
            with open(tf) as f:
                tickers.extend(line.strip() for line in f if line.strip())
        except FileNotFoundError:
            pass
    if not tickers:
        tickers = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN"]

    _update(0.4, f"Fetching SEC filings for {len(tickers)} tickers...")
    smart_money = SECEdgarAdapter()

    _update(0.6, "Computing conviction scores...")
    from application.conviction_use_case import ConvictionScoringUseCase

    # Load pinned from watchlist
    from adapters.visualization.data_loader import load_watchlist
    watchlist = load_watchlist(db_path)
    pinned = {w.symbol for w in watchlist} if watchlist else set()

    weights = ConvictionWeights()
    uc = ConvictionScoringUseCase(
        smart_money=smart_money,
        tickers=tickers[:50],  # Limit for performance in initial version
        weights=weights,
        pinned=pinned,
    )

    cards = uc.run(scan_time=datetime.now())
    _update(1.0, f"Done — {len(cards)} opportunities found.")
    return cards
```

- [ ] **Step 2: Rewrite command_center.py as Opportunity Feed**

Replace the entire `adapters/visualization/tabs/command_center.py` with:

```python
"""Tab 1: Opportunity Feed — Conviction-ranked opportunity cards."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

from adapters.visualization.action_runner import run_conviction_scan, run_full_cycle
from adapters.visualization.components.formatters import freshness_dot_html
from adapters.visualization.components.metrics import (
    render_action_card,
    render_hero_banner,
    render_inline_context,
)
from adapters.visualization.components.opportunity_cards import (
    render_opportunity_card_html,
)
from adapters.visualization.components.verdicts import command_center_verdict
from adapters.visualization.data_loader import load_holdings, load_recommendations

DB_PATH = "data/recommendations.db"
REPORTS_DIR = "data/reports"


def render(db_path: str = DB_PATH, reports_dir: str = REPORTS_DIR) -> None:
    """Render the Opportunity Feed tab."""
    holdings = load_holdings(db_path)
    recs = load_recommendations(db_path)
    held_symbols = {h.symbol for h in holdings}

    total_value = (
        sum(h.quantity * h.purchase_price for h in holdings) if holdings else 0
    )

    # Hero banner
    n_holdings = len(holdings)
    n_recs = len(recs)
    verdict = command_center_verdict(
        n_holdings=n_holdings,
        n_recommendations=n_recs,
        n_sell_signals=0,
        freshness_hours=_get_freshness_hours(reports_dir),
    )
    render_hero_banner(
        st, verdict, portfolio_value=total_value, n_positions=n_holdings
    )

    # Scan button
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Scan for Opportunities", type="primary", key="run_conviction_scan"):
            progress = st.progress(0)
            status_text = st.empty()

            def update_progress(pct: float, msg: str) -> None:
                progress.progress(pct)
                status_text.text(msg)

            cards = run_conviction_scan(
                db_path=db_path,
                progress_callback=update_progress,
            )
            st.session_state["opportunity_cards"] = cards
            progress.empty()
            status_text.empty()

    with col2:
        if st.button("Run Full Cycle", key="run_full_cycle"):
            progress = st.progress(0)
            status_text = st.empty()
            run_full_cycle(db_path=db_path, progress_callback=lambda p, m: (progress.progress(p), status_text.text(m)))
            progress.empty()
            status_text.empty()

    # Render opportunity cards
    cards = st.session_state.get("opportunity_cards", [])
    if cards:
        st.markdown(f"### Top {len(cards)} Opportunities")
        render_inline_context(
            st,
            "Ranked by conviction score — how many independent signals agree. "
            "Higher conviction = more evidence from different sources.",
        )
        now = datetime.now()
        for card in cards:
            st.markdown(
                render_opportunity_card_html(card, now=now),
                unsafe_allow_html=True,
            )
    else:
        render_inline_context(
            st,
            "No opportunities scanned yet. Click 'Scan for Opportunities' to run "
            "the conviction engine across the full ticker universe.",
        )

    # Keep existing: holdings summary + recommendations
    if holdings:
        st.divider()
        st.markdown("### Current Holdings")
        for h in holdings:
            st.markdown(
                f"**{h.symbol}** — {h.quantity} shares @ ${h.purchase_price:.2f} "
                f"({h.purchase_date})",
            )


def _get_freshness_hours(reports_dir: str) -> float | None:
    """Get hours since last report."""
    path = Path(reports_dir)
    if not path.exists():
        return None
    files = sorted(path.glob("backtest_report_*.json"), reverse=True)
    if not files:
        return None
    name = files[0].stem
    parts = name.replace("backtest_report_", "")
    try:
        dt = datetime.strptime(parts, "%Y%m%d_%H%M%S")
        delta = datetime.now() - dt
        return delta.total_seconds() / 3600
    except ValueError:
        return None
```

- [ ] **Step 3: Update tab label in dashboard.py**

In `adapters/visualization/dashboard.py`, change the tab label:

```python
# Change this:
"🎯 Command Center",
# To this:
"🎯 Opportunity Feed",
```

- [ ] **Step 4: Run smoke tests + full suite**

Run: `cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender" && python -m pytest tests/test_dashboard_smoke.py tests/test_action_runner.py -v --tb=short`
Expected: PASS (may need minor adjustments for new imports)

- [ ] **Step 5: Run full test suite**

Run: `cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender" && python -m pytest tests/ -q --tb=short`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add adapters/visualization/tabs/command_center.py adapters/visualization/action_runner.py adapters/visualization/dashboard.py
git commit -m "feat: Command Center → Opportunity Feed with conviction-ranked cards"
```

---

## Task 10: Config Update + Conviction Weights in us.yaml

**Files:**
- Modify: `config/markets/us.yaml`
- Modify: `config/loader.py` (if needed for new section)

- [ ] **Step 1: Add conviction config section to us.yaml**

Append to `config/markets/us.yaml`:

```yaml
# Conviction scoring weights — tunable per market
conviction:
  weights:
    signal_agreement: 1.0
    smart_money: 1.5
    sentiment_momentum: 1.0
    fundamental_basis: 1.0
    temporal_freshness: 1.2
    ml_direction: 0.3
  top_n: 15
  min_score: 3.0
  scan_schedule:
    full_scan: "06:00"        # Pre-market
    filing_check: "12:00"     # Midday
    post_market: "18:00"      # After close

# SEC EDGAR configuration
sec_edgar:
  user_agent: "StockRecommender research@example.com"
  rate_limit_seconds: 1.0
```

- [ ] **Step 2: Run existing config tests**

Run: `cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender" && python -m pytest tests/ -k "config or loader" -v --tb=short`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add config/markets/us.yaml
git commit -m "feat: add conviction scoring weights + SEC EDGAR config to us.yaml"
```

---

## Task 11: Full Regression + Lint + Typecheck

- [ ] **Step 1: Run full quality check**

Run: `cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender" && make check`
Expected: lint PASS, typecheck PASS, tests PASS (coverage ≥ 90%)

- [ ] **Step 2: Fix any lint/type issues**

Address any mypy strict violations in new files (type annotations, return types).

- [ ] **Step 3: Fix any failing tests**

Investigate and fix root cause — do not skip tests.

- [ ] **Step 4: Commit fixes if any**

```bash
git add -A
git commit -m "fix: resolve lint and typecheck issues in Phase 7 conviction engine"
```

---

## Task 12: ADR-032 + Documentation

**Files:**
- Create: `docs/adr/ADR-032-opportunity-intelligence-engine.md`
- Modify: `CLAUDE.md` (update phase status)

- [ ] **Step 1: Write ADR-032**

```markdown
# ADR-032: Opportunity Intelligence Engine

**Date:** 2026-06-03
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context

The existing ML-based direction predictor achieved 46-49% accuracy on a full S&P 500 + NASDAQ backtest — no statistical edge. Technical indicators on mega-cap stocks are well-arbitraged. The system needs a fundamentally different approach.

## Decision

Reframe from direction prediction to **opportunity surfacing with conviction scoring**:

1. **Multi-signal conviction engine** — weighted scoring across 6 dimensions (signal agreement, smart money, sentiment, fundamentals, freshness, ML direction)
2. **SEC EDGAR integration** — 13D activist filings and Form 4 insider trades as "smart money" signals
3. **4-part opportunity cards** — Alert, Evidence, Suggestion, Risk in beginner-friendly language
4. **Hybrid universe** — scan 350+ tickers, surface top 15, pin watchlist favorites
5. **Existing ML kept** — low-weight (0.3) input to conviction scoring, value determined by future outcome tracking

## Consequences

- Direction prediction becomes one input signal, not the system's purpose
- Dashboard evolves: Command Center → Opportunity Feed, Model Confidence → System Intelligence (Phase 8)
- Future phases add outcome tracking (Phase 8) and adaptive learning (Phase 9)
- The "honest data scientist" narrative strengthens — acknowledging limitations and reframing around genuine value
```

- [ ] **Step 2: Update CLAUDE.md phase status**

Add Phase 7 status section to CLAUDE.md.

- [ ] **Step 3: Commit**

```bash
git add docs/adr/ADR-032-opportunity-intelligence-engine.md CLAUDE.md
git commit -m "docs: add ADR-032 opportunity intelligence engine + update phase status"
```

---

## Dependency Graph

```
Task 1 (domain models) ──┬──▶ Task 2 (ports + validation) ──▶ Task 3 (scoring service)
                         │                                            │
                         │                                            ▼
                         ├──▶ Task 4 (SEC EDGAR adapter) ──▶ Task 5 (feature engineer)
                         │                                            │
                         │                                            ▼
                         │                                    Task 6 (use case) ──▶ Task 9 (tab rewrite)
                         │                                                               │
                         └──▶ Task 7 (formatters + cards) ──────────────────────────────▶│
                                                                                         │
                              Task 8 (header + sparkline) ──────────────────────────────▶│
                                                                                         ▼
                              Task 10 (config) ──▶ Task 11 (regression) ──▶ Task 12 (ADR + docs)
```

**Parallelizable groups:**
- Tasks 1 must be first (all others depend on domain models)
- Tasks 2, 4, 7, 8 can run in parallel after Task 1
- Tasks 3, 5 after their dependencies
- Task 6 after Tasks 3 + 5
- Task 9 after Tasks 6 + 7 + 8
- Tasks 10, 11, 12 are sequential finalization
