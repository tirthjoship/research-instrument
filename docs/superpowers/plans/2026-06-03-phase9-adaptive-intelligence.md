# Phase 9: Adaptive Intelligence — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add pattern memory and adaptive weight adjustment so the conviction engine learns from tracked outcomes — automatically strengthening signals that work and weakening those that don't.

**Architecture:** New domain models (PatternMemory, WeightAdjustment) + pattern memory service (pure domain logic) + SQLite persistence (pattern_memory table) + adaptive weight engine + dashboard evolution (System Intelligence tab shows learning progress, weight history). All hexagonal — domain stays pure.

**Tech Stack:** Python 3.12+, pytest, Streamlit, SQLite, existing outcome tracking from Phase 8.

**Design Spec:** `docs/superpowers/specs/2026-06-03-opportunity-intelligence-engine-design.md` (Section 6, Pattern Memory)

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `domain/pattern_memory.py` | PatternEntry, WeightAdjustment, LearnedRule domain models |
| `domain/pattern_service.py` | Pure logic: pattern matching, weight adjustment computation, rule emergence |
| `application/learning_use_case.py` | LearningUseCase — orchestrates pattern storage + weight updates + rule generation |
| `tests/test_pattern_memory.py` | Domain model tests |
| `tests/test_pattern_service.py` | Pattern logic tests |
| `tests/test_learning_use_case.py` | Use case tests |

### Modified Files

| File | Change |
|------|--------|
| `adapters/data/sqlite_store.py` | Add pattern_memory + weight_history tables |
| `adapters/visualization/tabs/model_confidence.py` | Add weight history + learned rules to System Intelligence |
| `adapters/visualization/data_loader.py` | Add load_pattern_memory(), load_weight_history() |
| `adapters/visualization/components/verdicts.py` | Update system_intelligence_verdict with learning stats |
| `tests/test_sqlite_store.py` | Pattern/weight persistence tests |

---

## Task 1: Domain Models — PatternEntry, WeightAdjustment, LearnedRule

**Files:**
- Create: `domain/pattern_memory.py`
- Test: `tests/test_pattern_memory.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for pattern memory domain models."""

import pytest

from domain.pattern_memory import LearnedRule, PatternEntry, WeightAdjustment


class TestPatternEntry:
    def test_valid_creation(self) -> None:
        p = PatternEntry(
            signal_combination=("smart_money", "sentiment_momentum"),
            sector="Technology",
            market_condition="bull",
            outcome_count=14,
            avg_return_pct=8.2,
            hit_rate=72.0,
            avg_holding_days=28,
        )
        assert p.outcome_count == 14
        assert p.is_reliable is True  # >= 10 outcomes

    def test_unreliable_below_threshold(self) -> None:
        p = PatternEntry(
            signal_combination=("ml_direction",),
            sector="any",
            market_condition="any",
            outcome_count=3,
            avg_return_pct=1.0,
            hit_rate=55.0,
            avg_holding_days=14,
        )
        assert p.is_reliable is False

    def test_pattern_key(self) -> None:
        p = PatternEntry(
            signal_combination=("smart_money", "sentiment_momentum"),
            sector="Technology",
            market_condition="bull",
            outcome_count=10,
            avg_return_pct=5.0,
            hit_rate=60.0,
            avg_holding_days=20,
        )
        key = p.pattern_key
        assert "smart_money" in key
        assert "Technology" in key


class TestWeightAdjustment:
    def test_valid_creation(self) -> None:
        w = WeightAdjustment(
            dimension="smart_money",
            old_weight=1.5,
            new_weight=1.8,
            reason="72% hit rate across 14 trades",
            adjusted_date="2026-06-03",
        )
        assert w.change == pytest.approx(0.3)
        assert w.direction == "increased"

    def test_decrease(self) -> None:
        w = WeightAdjustment(
            dimension="ml_direction",
            old_weight=0.3,
            new_weight=0.15,
            reason="48% hit rate — worse than random",
            adjusted_date="2026-06-03",
        )
        assert w.direction == "decreased"

    def test_no_change(self) -> None:
        w = WeightAdjustment(
            dimension="fundamental_basis",
            old_weight=1.0,
            new_weight=1.0,
            reason="Insufficient data",
            adjusted_date="2026-06-03",
        )
        assert w.direction == "unchanged"


class TestLearnedRule:
    def test_valid_creation(self) -> None:
        r = LearnedRule(
            rule_id="rule_001",
            description="Never recommend pure-technical plays on mega-caps",
            signal_combination=("ml_direction",),
            sector="Technology",
            action="suppress",
            confidence=0.85,
            supporting_outcomes=31,
            learned_date="2026-06-03",
        )
        assert r.is_high_confidence is True

    def test_low_confidence(self) -> None:
        r = LearnedRule(
            rule_id="rule_002",
            description="Test rule",
            signal_combination=("smart_money",),
            sector="any",
            action="boost",
            confidence=0.4,
            supporting_outcomes=5,
            learned_date="2026-06-03",
        )
        assert r.is_high_confidence is False
```

- [ ] **Step 2: Run tests — verify FAIL**

- [ ] **Step 3: Implement domain models**

```python
"""Pattern memory domain models.

Stores signal combination → outcome distributions for adaptive learning.
Pure Python, no external dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass

_MIN_RELIABLE_OUTCOMES = 10
_HIGH_CONFIDENCE_THRESHOLD = 0.7


@dataclass(frozen=True)
class PatternEntry:
    """Observed pattern: signal combination → outcome distribution."""
    signal_combination: tuple[str, ...]
    sector: str
    market_condition: str  # bull, bear, flat
    outcome_count: int
    avg_return_pct: float
    hit_rate: float
    avg_holding_days: int

    @property
    def is_reliable(self) -> bool:
        return self.outcome_count >= _MIN_RELIABLE_OUTCOMES

    @property
    def pattern_key(self) -> str:
        signals = "+".join(sorted(self.signal_combination))
        return f"{signals}|{self.sector}|{self.market_condition}"


@dataclass(frozen=True)
class WeightAdjustment:
    """Record of a conviction weight change."""
    dimension: str
    old_weight: float
    new_weight: float
    reason: str
    adjusted_date: str

    @property
    def change(self) -> float:
        return round(self.new_weight - self.old_weight, 4)

    @property
    def direction(self) -> str:
        if self.new_weight > self.old_weight:
            return "increased"
        if self.new_weight < self.old_weight:
            return "decreased"
        return "unchanged"


@dataclass(frozen=True)
class LearnedRule:
    """An emergent rule discovered from pattern analysis."""
    rule_id: str
    description: str
    signal_combination: tuple[str, ...]
    sector: str
    action: str  # "suppress", "boost", "warn"
    confidence: float  # 0-1
    supporting_outcomes: int
    learned_date: str

    @property
    def is_high_confidence(self) -> bool:
        return self.confidence >= _HIGH_CONFIDENCE_THRESHOLD
```

- [ ] **Step 4: Run tests — verify PASS**
- [ ] **Step 5: Commit**

```bash
git add domain/pattern_memory.py tests/test_pattern_memory.py
git commit -m "feat: add pattern memory domain models (PatternEntry, WeightAdjustment, LearnedRule)"
```

---

## Task 2: Pattern Memory Service — Pure Domain Logic

**Files:**
- Create: `domain/pattern_service.py`
- Test: `tests/test_pattern_service.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for pattern memory service."""

import pytest

from domain.outcome import SignalPerformance, TradeOutcome
from domain.pattern_memory import LearnedRule, PatternEntry, WeightAdjustment
from domain.pattern_service import (
    build_patterns_from_outcomes,
    compute_weight_adjustments,
    discover_rules,
)
from domain.conviction import ConvictionWeights


class TestBuildPatternsFromOutcomes:
    def test_groups_by_signal_combination(self) -> None:
        outcomes = [
            TradeOutcome(
                ticker="NVDA", buy_trade_id="t1", sell_trade_id="t2",
                buy_price=100.0, sell_price=112.0, quantity=10,
                buy_date="2026-06-01", sell_date="2026-06-15",
                holding_days=14, return_pct=12.0, return_dollar=120.0,
                signals_at_entry=["smart_money", "sentiment_momentum"],
                conviction_at_entry=8.0,
            ),
            TradeOutcome(
                ticker="AAPL", buy_trade_id="t3", sell_trade_id="t4",
                buy_price=150.0, sell_price=160.0, quantity=5,
                buy_date="2026-06-10", sell_date="2026-06-25",
                holding_days=15, return_pct=6.67, return_dollar=50.0,
                signals_at_entry=["smart_money", "sentiment_momentum"],
                conviction_at_entry=7.0,
            ),
        ]
        patterns = build_patterns_from_outcomes(outcomes)
        assert len(patterns) >= 1
        # Should group the two trades with same signal combo
        sm_sent = [p for p in patterns if "smart_money" in p.signal_combination and "sentiment_momentum" in p.signal_combination]
        assert len(sm_sent) == 1
        assert sm_sent[0].outcome_count == 2
        assert sm_sent[0].hit_rate == 100.0

    def test_empty_outcomes(self) -> None:
        assert build_patterns_from_outcomes([]) == []


class TestComputeWeightAdjustments:
    def test_strong_signal_gets_boosted(self) -> None:
        perfs = [
            SignalPerformance(
                signal_name="smart_money", total_trades=20,
                winning_trades=15, losing_trades=5, hit_rate=75.0,
                avg_return_pct=8.0,
            ),
        ]
        current = ConvictionWeights()
        adjustments = compute_weight_adjustments(perfs, current)
        sm_adj = next((a for a in adjustments if a.dimension == "smart_money"), None)
        assert sm_adj is not None
        assert sm_adj.new_weight > sm_adj.old_weight

    def test_weak_signal_gets_reduced(self) -> None:
        perfs = [
            SignalPerformance(
                signal_name="ml_direction", total_trades=30,
                winning_trades=14, losing_trades=16, hit_rate=46.7,
                avg_return_pct=-0.5,
            ),
        ]
        current = ConvictionWeights()
        adjustments = compute_weight_adjustments(perfs, current)
        ml_adj = next((a for a in adjustments if a.dimension == "ml_direction"), None)
        assert ml_adj is not None
        assert ml_adj.new_weight < ml_adj.old_weight

    def test_insufficient_data_no_change(self) -> None:
        perfs = [
            SignalPerformance(
                signal_name="smart_money", total_trades=3,
                winning_trades=2, losing_trades=1, hit_rate=66.7,
                avg_return_pct=5.0,
            ),
        ]
        current = ConvictionWeights()
        adjustments = compute_weight_adjustments(perfs, current, min_trades=10)
        sm_adj = next((a for a in adjustments if a.dimension == "smart_money"), None)
        assert sm_adj is not None
        assert sm_adj.direction == "unchanged"


class TestDiscoverRules:
    def test_suppression_rule_for_bad_pattern(self) -> None:
        patterns = [
            PatternEntry(
                signal_combination=("ml_direction",),
                sector="Technology",
                market_condition="any",
                outcome_count=31,
                avg_return_pct=0.3,
                hit_rate=48.0,
                avg_holding_days=14,
            ),
        ]
        rules = discover_rules(patterns)
        assert len(rules) >= 1
        assert rules[0].action == "suppress"

    def test_boost_rule_for_strong_pattern(self) -> None:
        patterns = [
            PatternEntry(
                signal_combination=("smart_money", "sentiment_momentum"),
                sector="any",
                market_condition="any",
                outcome_count=14,
                avg_return_pct=8.2,
                hit_rate=72.0,
                avg_holding_days=28,
            ),
        ]
        rules = discover_rules(patterns)
        boost_rules = [r for r in rules if r.action == "boost"]
        assert len(boost_rules) >= 1

    def test_no_rules_from_unreliable_patterns(self) -> None:
        patterns = [
            PatternEntry(
                signal_combination=("smart_money",),
                sector="any", market_condition="any",
                outcome_count=3, avg_return_pct=5.0,
                hit_rate=66.0, avg_holding_days=10,
            ),
        ]
        rules = discover_rules(patterns)
        assert rules == []
```

- [ ] **Step 2: Run tests — verify FAIL**

- [ ] **Step 3: Implement pattern service**

```python
"""Pattern memory service — pure domain logic.

Builds pattern entries from outcomes, computes weight adjustments,
and discovers emergent rules. No I/O.
"""

from __future__ import annotations

import uuid
from dataclasses import fields
from datetime import datetime

from domain.conviction import ConvictionWeights
from domain.outcome import SignalPerformance, TradeOutcome
from domain.pattern_memory import LearnedRule, PatternEntry, WeightAdjustment

_BOOST_THRESHOLD = 65.0    # hit rate above this → boost
_SUPPRESS_THRESHOLD = 50.0  # hit rate below this → suppress
_WEIGHT_STEP = 0.2          # max adjustment per cycle
_MIN_WEIGHT = 0.05          # never go below
_MAX_WEIGHT = 3.0           # never go above


def build_patterns_from_outcomes(outcomes: list[TradeOutcome]) -> list[PatternEntry]:
    """Group outcomes by signal combination and compute aggregate stats."""
    if not outcomes:
        return []

    groups: dict[tuple[str, ...], list[TradeOutcome]] = {}
    for o in outcomes:
        key = tuple(sorted(o.signals_at_entry))
        if not key:
            continue
        groups.setdefault(key, []).append(o)

    patterns: list[PatternEntry] = []
    for combo, trades in groups.items():
        wins = sum(1 for t in trades if t.is_profitable)
        patterns.append(
            PatternEntry(
                signal_combination=combo,
                sector="any",
                market_condition="any",
                outcome_count=len(trades),
                avg_return_pct=round(sum(t.return_pct for t in trades) / len(trades), 2),
                hit_rate=round(wins / len(trades) * 100, 1),
                avg_holding_days=round(sum(t.holding_days for t in trades) / len(trades)),
            )
        )
    return patterns


def compute_weight_adjustments(
    performances: list[SignalPerformance],
    current_weights: ConvictionWeights,
    min_trades: int = 10,
) -> list[WeightAdjustment]:
    """Compute weight adjustments based on signal performance."""
    weight_map = {f.name: getattr(current_weights, f.name) for f in fields(current_weights)}
    today = datetime.now().strftime("%Y-%m-%d")
    adjustments: list[WeightAdjustment] = []

    for perf in performances:
        dim = perf.signal_name
        old_w = weight_map.get(dim)
        if old_w is None:
            continue

        if perf.total_trades < min_trades:
            adjustments.append(WeightAdjustment(
                dimension=dim, old_weight=old_w, new_weight=old_w,
                reason=f"Insufficient data ({perf.total_trades} trades, need {min_trades}+)",
                adjusted_date=today,
            ))
            continue

        if perf.hit_rate >= _BOOST_THRESHOLD:
            delta = min(_WEIGHT_STEP, _MAX_WEIGHT - old_w)
            new_w = round(old_w + delta, 2)
            reason = f"{perf.hit_rate}% hit rate across {perf.total_trades} trades — boosting"
        elif perf.hit_rate < _SUPPRESS_THRESHOLD:
            delta = min(_WEIGHT_STEP, old_w - _MIN_WEIGHT)
            new_w = round(old_w - delta, 2)
            reason = f"{perf.hit_rate}% hit rate — worse than random, reducing"
        else:
            new_w = old_w
            reason = f"{perf.hit_rate}% hit rate — within normal range, no change"

        adjustments.append(WeightAdjustment(
            dimension=dim, old_weight=old_w, new_weight=new_w,
            reason=reason, adjusted_date=today,
        ))

    return adjustments


def discover_rules(patterns: list[PatternEntry]) -> list[LearnedRule]:
    """Discover emergent rules from reliable patterns."""
    rules: list[LearnedRule] = []

    for p in patterns:
        if not p.is_reliable:
            continue

        if p.hit_rate < _SUPPRESS_THRESHOLD:
            signals_desc = " + ".join(p.signal_combination)
            rules.append(LearnedRule(
                rule_id=str(uuid.uuid4())[:8],
                description=f"Avoid {signals_desc} in {p.sector} — {p.hit_rate}% hit rate over {p.outcome_count} trades",
                signal_combination=p.signal_combination,
                sector=p.sector,
                action="suppress",
                confidence=min(p.outcome_count / 30.0, 1.0),
                supporting_outcomes=p.outcome_count,
                learned_date=datetime.now().strftime("%Y-%m-%d"),
            ))
        elif p.hit_rate >= _BOOST_THRESHOLD and p.avg_return_pct > 3.0:
            signals_desc = " + ".join(p.signal_combination)
            rules.append(LearnedRule(
                rule_id=str(uuid.uuid4())[:8],
                description=f"Prioritize {signals_desc} — {p.hit_rate}% hit rate, avg +{p.avg_return_pct}% return",
                signal_combination=p.signal_combination,
                sector=p.sector,
                action="boost",
                confidence=min(p.outcome_count / 20.0, 1.0),
                supporting_outcomes=p.outcome_count,
                learned_date=datetime.now().strftime("%Y-%m-%d"),
            ))

    return rules
```

- [ ] **Step 4: Run tests — verify PASS**
- [ ] **Step 5: Commit**

```bash
git add domain/pattern_service.py tests/test_pattern_service.py
git commit -m "feat: add pattern memory service — pattern building, weight adjustment, rule discovery"
```

---

## Task 3: SQLite Persistence — Pattern Memory + Weight History

**Files:**
- Modify: `adapters/data/sqlite_store.py`
- Modify: `tests/test_sqlite_store.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_sqlite_store.py`:

```python
from domain.pattern_memory import LearnedRule, PatternEntry, WeightAdjustment


class TestPatternStore:
    def test_save_and_load_weight_adjustment(self, tmp_path) -> None:
        db = str(tmp_path / "test.db")
        from adapters.data.sqlite_store import SQLiteStore
        store = SQLiteStore(db)
        adj = WeightAdjustment(
            dimension="smart_money", old_weight=1.5, new_weight=1.8,
            reason="Strong performance", adjusted_date="2026-06-03",
        )
        store.save_weight_adjustment(adj)
        history = store.get_weight_history()
        assert len(history) == 1
        assert history[0].dimension == "smart_money"
        assert history[0].new_weight == 1.8

    def test_save_and_load_learned_rule(self, tmp_path) -> None:
        db = str(tmp_path / "test.db")
        from adapters.data.sqlite_store import SQLiteStore
        store = SQLiteStore(db)
        rule = LearnedRule(
            rule_id="r001", description="Test rule",
            signal_combination=("smart_money",), sector="Technology",
            action="boost", confidence=0.85, supporting_outcomes=20,
            learned_date="2026-06-03",
        )
        store.save_learned_rule(rule)
        rules = store.get_learned_rules()
        assert len(rules) == 1
        assert rules[0].rule_id == "r001"
```

- [ ] **Step 2: Run tests — verify FAIL**

- [ ] **Step 3: Add tables and methods**

Append to `_SCHEMA` in sqlite_store.py:

```sql
CREATE TABLE IF NOT EXISTS weight_history (
    id INTEGER PRIMARY KEY,
    dimension TEXT NOT NULL,
    old_weight REAL NOT NULL,
    new_weight REAL NOT NULL,
    reason TEXT,
    adjusted_date TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS learned_rules (
    rule_id TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    signal_combination TEXT NOT NULL,
    sector TEXT DEFAULT 'any',
    action TEXT NOT NULL,
    confidence REAL NOT NULL,
    supporting_outcomes INTEGER NOT NULL,
    learned_date TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);
```

Add methods:

```python
from domain.pattern_memory import LearnedRule, WeightAdjustment

def save_weight_adjustment(self, adj: WeightAdjustment) -> None:
    with sqlite3.connect(self._db_path) as conn:
        conn.execute(
            "INSERT INTO weight_history (dimension, old_weight, new_weight, reason, adjusted_date) VALUES (?, ?, ?, ?, ?)",
            (adj.dimension, adj.old_weight, adj.new_weight, adj.reason, adj.adjusted_date),
        )

def get_weight_history(self, dimension: str | None = None) -> list[WeightAdjustment]:
    with sqlite3.connect(self._db_path) as conn:
        if dimension:
            rows = conn.execute("SELECT * FROM weight_history WHERE dimension = ? ORDER BY created_at", (dimension,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM weight_history ORDER BY created_at").fetchall()
    return [WeightAdjustment(dimension=r[1], old_weight=r[2], new_weight=r[3], reason=r[4] or "", adjusted_date=r[5]) for r in rows]

def save_learned_rule(self, rule: LearnedRule) -> None:
    with sqlite3.connect(self._db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO learned_rules (rule_id, description, signal_combination, sector, action, confidence, supporting_outcomes, learned_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (rule.rule_id, rule.description, json.dumps(rule.signal_combination), rule.sector, rule.action, rule.confidence, rule.supporting_outcomes, rule.learned_date),
        )

def get_learned_rules(self) -> list[LearnedRule]:
    with sqlite3.connect(self._db_path) as conn:
        rows = conn.execute("SELECT * FROM learned_rules ORDER BY learned_date").fetchall()
    return [LearnedRule(rule_id=r[0], description=r[1], signal_combination=tuple(json.loads(r[2])), sector=r[3], action=r[4], confidence=r[5], supporting_outcomes=r[6], learned_date=r[7]) for r in rows]
```

- [ ] **Step 4: Run tests — verify PASS**
- [ ] **Step 5: Commit**

```bash
git add adapters/data/sqlite_store.py tests/test_sqlite_store.py
git commit -m "feat: add pattern memory + weight history SQLite tables"
```

---

## Task 4: LearningUseCase — Orchestration

**Files:**
- Create: `application/learning_use_case.py`
- Test: `tests/test_learning_use_case.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for LearningUseCase."""

from domain.conviction import ConvictionWeights
from domain.outcome import TradeOutcome
from domain.pattern_memory import LearnedRule, WeightAdjustment


class FakeLearningStore:
    def __init__(self) -> None:
        self._outcomes: list[TradeOutcome] = []
        self._adjustments: list[WeightAdjustment] = []
        self._rules: list[LearnedRule] = []

    def get_outcomes(self, ticker=None):
        return self._outcomes

    def save_weight_adjustment(self, adj):
        self._adjustments.append(adj)

    def get_weight_history(self, dimension=None):
        return self._adjustments

    def save_learned_rule(self, rule):
        self._rules.append(rule)

    def get_learned_rules(self):
        return self._rules


class TestLearningUseCase:
    def test_learn_from_outcomes(self) -> None:
        from application.learning_use_case import LearningUseCase
        store = FakeLearningStore()
        # Add enough outcomes for reliable patterns
        for i in range(15):
            store._outcomes.append(TradeOutcome(
                ticker=f"T{i}", buy_trade_id=f"b{i}", sell_trade_id=f"s{i}",
                buy_price=100.0, sell_price=110.0, quantity=10,
                buy_date="2026-06-01", sell_date="2026-06-15",
                holding_days=14, return_pct=10.0, return_dollar=100.0,
                signals_at_entry=["smart_money"], conviction_at_entry=8.0,
            ))
        uc = LearningUseCase(store=store, current_weights=ConvictionWeights())
        result = uc.learn()
        assert "patterns" in result
        assert "adjustments" in result
        assert "rules" in result

    def test_no_outcomes_returns_empty(self) -> None:
        from application.learning_use_case import LearningUseCase
        store = FakeLearningStore()
        uc = LearningUseCase(store=store, current_weights=ConvictionWeights())
        result = uc.learn()
        assert result["patterns"] == []

    def test_get_current_intelligence(self) -> None:
        from application.learning_use_case import LearningUseCase
        store = FakeLearningStore()
        uc = LearningUseCase(store=store, current_weights=ConvictionWeights())
        intel = uc.get_current_intelligence()
        assert "weight_history" in intel
        assert "rules" in intel
        assert "total_outcomes" in intel
```

- [ ] **Step 2: Implement LearningUseCase**

```python
"""LearningUseCase — orchestrates pattern memory, weight adjustment, and rule discovery."""

from __future__ import annotations

from typing import Any

from loguru import logger

from domain.conviction import ConvictionWeights
from domain.outcome_service import compute_signal_performance
from domain.pattern_service import (
    build_patterns_from_outcomes,
    compute_weight_adjustments,
    discover_rules,
)


class LearningUseCase:
    """Analyze outcomes, adjust weights, discover rules."""

    def __init__(self, store: Any, current_weights: ConvictionWeights) -> None:
        self._store = store
        self._weights = current_weights

    def learn(self) -> dict[str, Any]:
        """Run full learning cycle: patterns → adjustments → rules."""
        outcomes = self._store.get_outcomes()
        if not outcomes:
            return {"patterns": [], "adjustments": [], "rules": []}

        # Build patterns
        patterns = build_patterns_from_outcomes(outcomes)
        logger.info("Built {} patterns from {} outcomes", len(patterns), len(outcomes))

        # Compute weight adjustments
        perfs = compute_signal_performance(outcomes)
        adjustments = compute_weight_adjustments(perfs, self._weights)
        for adj in adjustments:
            if adj.direction != "unchanged":
                self._store.save_weight_adjustment(adj)
                logger.info("Weight {}: {} → {} ({})", adj.dimension, adj.old_weight, adj.new_weight, adj.reason)

        # Discover rules
        rules = discover_rules(patterns)
        for rule in rules:
            self._store.save_learned_rule(rule)
            logger.info("Learned rule: {} (confidence: {:.0%})", rule.description, rule.confidence)

        return {"patterns": patterns, "adjustments": adjustments, "rules": rules}

    def get_current_intelligence(self) -> dict[str, Any]:
        """Return current learning state for dashboard display."""
        outcomes = self._store.get_outcomes()
        weight_history = self._store.get_weight_history()
        rules = self._store.get_learned_rules()
        return {
            "total_outcomes": len(outcomes),
            "weight_history": weight_history,
            "rules": rules,
            "weights_adjusted": len([w for w in weight_history if w.direction != "unchanged"]),
            "rules_discovered": len(rules),
        }
```

- [ ] **Step 3: Run tests — verify PASS**
- [ ] **Step 4: Commit**

```bash
git add application/learning_use_case.py tests/test_learning_use_case.py
git commit -m "feat: add LearningUseCase — pattern analysis, weight adjustment, rule discovery"
```

---

## Task 5: System Intelligence Tab — Weight History + Rules Display

**Files:**
- Modify: `adapters/visualization/tabs/model_confidence.py` — add learning dashboard section
- Modify: `adapters/visualization/data_loader.py` — add load_weight_history, load_learned_rules

- [ ] **Step 1: Add data loaders**

Append to `adapters/visualization/data_loader.py`:

```python
from domain.pattern_memory import LearnedRule, WeightAdjustment

def load_weight_history(db_path: str) -> list[WeightAdjustment]:
    if not Path(db_path).exists():
        return []
    try:
        from adapters.data.sqlite_store import SQLiteStore
        return SQLiteStore(db_path).get_weight_history()
    except Exception as e:
        logger.warning("Failed to load weight history: %s", e)
        return []

def load_learned_rules(db_path: str) -> list[LearnedRule]:
    if not Path(db_path).exists():
        return []
    try:
        from adapters.data.sqlite_store import SQLiteStore
        return SQLiteStore(db_path).get_learned_rules()
    except Exception as e:
        logger.warning("Failed to load learned rules: %s", e)
        return []
```

- [ ] **Step 2: Add weight history + rules section to model_confidence.py**

After the signal report card section (added in Phase 8), add:
- "Weight History" section — table showing dimension, old→new, reason, date
- "Learned Rules" section — list of rules with confidence and description
- "Run Learning Cycle" button that triggers LearningUseCase.learn()

- [ ] **Step 3: Run tests**
- [ ] **Step 4: Commit**

```bash
git add adapters/visualization/tabs/model_confidence.py adapters/visualization/data_loader.py
git commit -m "feat: add weight history and learned rules to System Intelligence tab"
```

---

## Task 6: Full Regression + ADR-034

- [ ] **Step 1: Run full test suite**

Run: `cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender" && python -m pytest tests/ -q --tb=short`

- [ ] **Step 2: Run mypy on new files**

Run: `mypy domain/pattern_memory.py domain/pattern_service.py application/learning_use_case.py --strict`

- [ ] **Step 3: Create ADR-034**

```markdown
# ADR-034: Adaptive Intelligence — Pattern Memory and Weight Evolution

**Date:** 2026-06-03
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context

Phases 7-8 introduced conviction scoring with static weights and outcome tracking. The system records which signals fire and what happens, but doesn't act on this knowledge. Weights remain at defaults regardless of observed performance.

## Decision

Add adaptive intelligence with three mechanisms:

1. **Pattern memory** — groups outcomes by signal combination, computes hit rate and avg return per pattern
2. **Weight adjustment** — automatically boosts weights for signals with >65% hit rate, reduces for <50%, with guardrails (max ±0.2 per cycle, floor 0.05, ceiling 3.0)
3. **Rule discovery** — emerges "suppress" rules for reliably bad patterns and "boost" rules for reliably good ones

## Consequences

- Conviction weights evolve quarterly based on outcome data
- System gets smarter over time without manual tuning
- Weight history provides full audit trail
- Learned rules are surfaced on System Intelligence tab
- Human can override: manual weight adjustment always takes precedence
```

- [ ] **Step 4: Update CLAUDE.md**
- [ ] **Step 5: Commit**

```bash
git add docs/adr/ADR-034-adaptive-intelligence.md CLAUDE.md
git commit -m "docs: add ADR-034 adaptive intelligence + update phase status"
```

---

## Dependency Graph

```
Task 1 (domain models) ──▶ Task 2 (pattern service) ──▶ Task 4 (LearningUseCase)
                                                                    │
Task 3 (SQLite tables) ────────────────────────────────────────────▶├──▶ Task 5 (dashboard)
                                                                    │
                                                                    └──▶ Task 6 (regression + ADR)
```

**Parallelizable:** Tasks 2 + 3 after Task 1. Task 4 after Task 2. Task 5 after Tasks 3+4. Task 6 last.
