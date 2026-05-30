---
name: domain-check
description: Validate hexagonal architecture compliance — verify domain/ has zero external imports, all adapters implement port Protocols, and no business logic leaks into adapters.
---

Validate hexagonal architecture compliance for the multi-modal-stock-recommender project.

## What is hexagonal compliance?

The core rule: **dependencies point inward only.**

```
adapters/     →  domain/  ←  application/
(external)       (pure)      (orchestration)
```

- `domain/` imports ONLY: `typing`, `dataclasses`, `datetime`, `enum`, `collections.abc`, `__future__`
- `adapters/` imports from `domain/` to implement port Protocols
- `application/` imports from both `domain/` and `adapters/` to orchestrate
- `config/` contains YAML configuration only — no Python imports

## Audit steps

### 1. Domain purity check (NON-NEGOTIABLE)

```bash
grep -rn "^import\|^from" domain/*.py
```

Filter out allowed modules. Any remaining import = **critical violation**.

Allowed imports in domain/:
- `from __future__ import annotations`
- `from typing import ...`
- `from dataclasses import ...`
- `from datetime import ...`
- `from enum import ...`
- `from collections.abc import ...`
- `from domain. ...` (internal cross-references)

Forbidden imports (non-exhaustive):
- `pandas`, `numpy`, `sklearn`, `xgboost`, `lightgbm`
- `yfinance`, `praw`, `feedparser`, `requests`
- `sqlite3`, `sqlalchemy`
- `from adapters`, `from application`

### 2. Port interface coverage

Read `domain/ports.py`. For each Protocol defined:
- Search `adapters/` for classes implementing it
- Verify method signatures match (name, parameters, return type)
- Flag any Protocol with zero implementations (acceptable during Phase 3 build, but note it)

Expected ports and implementations:
- `MarketDataPort` → `yfinance_adapter.py`
- `SentimentPort` → (existing, check implementation)
- `StockPredictorPort` → `xgboost_predictor.py`, `lightgbm_predictor.py`, `ensemble_predictor.py`
- `BacktestResultPort` → (check implementation)
- `NewsDiscoveryPort` → `rss_adapter.py`, `google_search_adapter.py`
- `BuzzScorerPort` → `reddit_adapter.py`, `stocktwits_adapter.py`
- `SentimentScorerPort` → `keyword_scorer.py`, `flan_t5_scorer.py`
- `RecommendationStorePort` → `sqlite_store.py`
- `TechnicalAnalysisPort` → `yfinance_adapter.py`

### 3. Adapter → domain dependency direction

```bash
grep -rn "from application" adapters/
```

Adapters must NOT import from application/. If found = dependency inversion violation.

### 4. Application composition check

```bash
grep -rn "^import\|^from" application/*.py
```

Application layer SHOULD import from both domain/ and adapters/. Verify it wires them together (composition root pattern).

### 5. Frozen dataclass check

```bash
grep -n "dataclass" domain/models.py
```

All domain entities must use `@dataclass(frozen=True)` for immutability: Signal, Sentiment, BacktestResult, TechnicalIndicators, DivergenceSignal, StockRecommendation, WeeklyReport, AccuracyRecord.

### 6. No business logic in adapters

Review each adapter file. Business rules belong in `domain/services.py`:
- Divergence computation → `domain/services.py`
- Grade assignment → `domain/services.py`
- Point-in-time validation → `domain/services.py`
- Filtering thresholds → `config/markets/*.yaml`

Adapters should only:
- Parse/transform external data into domain entities
- Delegate to domain services for logic
- Format domain results for external output

## Output format

```
## Domain Check — <date>

### Domain Purity
✅ Zero external imports / ❌ <file>:<line> — imports <module>

### Port Coverage
- MarketDataPort → implemented by: <adapter> ✅ / ❌ no implementation
- NewsDiscoveryPort → implemented by: <adapters> ✅
- BuzzScorerPort → implemented by: <adapters> ✅
- SentimentScorerPort → implemented by: <adapters> ✅
- RecommendationStorePort → implemented by: <adapter> ✅
- TechnicalAnalysisPort → implemented by: <adapter> ✅
- StockPredictorPort → implemented by: <adapters> ✅

### Dependency Direction
✅ No reverse dependencies / ❌ <file> imports from wrong layer

### Frozen Dataclasses
✅ All domain entities frozen / ⚠️ <class> should be frozen

### Business Logic Placement
✅ All logic in domain/services.py / ❌ <adapter>:<line> contains business rule

### Verdict
✅ Hexagonal architecture compliant / ❌ <N> violations found
```
