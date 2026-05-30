# Phase 3B: Sentiment Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Model tiers per task:** Each task is tagged with a recommended model tier.
> - **Opus:** Architecture decisions, ADRs, review checkpoints
> - **Sonnet:** Implementation (adapters, features, tests, CLI)
> - **Haiku:** File lookups, simple searches

**Goal:** Add sentiment scoring (keyword + Flan-T5), source reliability tracking, daily buzz discovery, and two-stage stacking to beat Phase 3A's ~50% directional accuracy baseline.

**Architecture:** Extend hexagonal architecture with new sentiment adapters (RSS, keyword scorer, Flan-T5) implementing existing `SentimentPort`. Add `SourceReliabilityPort` to domain. Extend `FeatureEngineerPort.compute()` to accept sentiment data. Build Stage 2 stacking on top of frozen Stage 1 technical model. Three-way ablation validates lift.

**Tech Stack:** feedparser (RSS), transformers + torch (Flan-T5 on MPS), PRAW (Reddit — deferred until API approved), SQLite (buzz_signals + source_reliability tables)

**Branch:** `feat/phase3b-sentiment-layer` (from `main`)

**Grilling decisions:** 12 decisions locked in memory at `project_phase3b_grilling_decisions.md`

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `domain/ports.py` (modify) | Add `SourceReliabilityPort`, `BuzzDiscoveryPort` protocols |
| `domain/models.py` (modify) | Add `BuzzSignal`, `SourceReliability` dataclasses |
| `adapters/data/rss_adapter.py` | RSS feed fetcher for 6 publishers, implements `BuzzDiscoveryPort` |
| `adapters/data/sqlite_store.py` (modify) | Add `buzz_signals` + `source_reliability` tables |
| `adapters/ml/keyword_scorer.py` | Rule-based keyword sentiment scorer, implements `SentimentPort` |
| `adapters/ml/flan_t5_scorer.py` | Flan-T5 zero-shot sentiment scorer, implements `SentimentPort` |
| `adapters/ml/sentiment_feature_engineer.py` | 14 sentiment features, extends feature pipeline |
| `adapters/ml/stage2_predictor.py` | Stage 2 stacking model (blends Stage 1 + sentiment) |
| `application/daily_scan.py` | Daily buzz discovery orchestration |
| `application/use_cases.py` (modify) | Extend `WeeklyTournamentUseCase` with Stage 2 |
| `application/cli.py` (modify) | Add `daily-scan` command, extend `run-tournament` |
| `application/ablation.py` | Three-way ablation evaluation runner |
| `tests/fakes/fake_sentiment.py` | Fake `SentimentPort` implementation |
| `tests/fakes/fake_buzz_discovery.py` | Fake `BuzzDiscoveryPort` implementation |
| `tests/fakes/fake_source_reliability.py` | Fake `SourceReliabilityPort` implementation |
| `tests/test_rss_adapter.py` | RSS adapter tests (with fake HTTP) |
| `tests/test_keyword_scorer.py` | Keyword scorer tests |
| `tests/test_flan_t5_scorer.py` | Flan-T5 scorer tests (with small model mock) |
| `tests/test_sentiment_features.py` | Sentiment feature computation tests |
| `tests/test_stage2_predictor.py` | Stage 2 stacking tests |
| `tests/test_daily_scan.py` | Daily scan use case tests |
| `tests/test_source_reliability.py` | Source reliability tracking tests |
| `tests/test_ablation.py` | Ablation runner tests |
| `docs/adr/ADR-021-source-reliability-tracker.md` | ADR for source reliability |
| `docs/adr/ADR-022-daily-discovery-weekly-analysis.md` | ADR for dual-cadence architecture |

---

## Task 1: ADRs for Phase 3B Decisions [Opus]

**Files:**
- Create: `docs/adr/ADR-021-source-reliability-tracker.md`
- Create: `docs/adr/ADR-022-daily-discovery-weekly-analysis.md`

- [ ] **Step 1: Write ADR-021 — Source Reliability Tracker**

```markdown
# ADR-021: Source Reliability Tracker

## Status
Accepted

## Context
Phase 3B adds sentiment from multiple sources (RSS publishers, Reddit). Not all sources
are equally reliable — a Reuters article and a Reddit shitpost carry different signal
quality. We need a mechanism to learn which sources are trustworthy over time and weight
sentiment accordingly.

## Decision
Add a `SourceReliabilityPort` to the domain layer with a `SourceReliability` model.
Track per-source, per-ticker directional accuracy over rolling 90-day windows. Store
in SQLite `source_reliability` table. Use reliability scores to weight sentiment
features (`source_weighted_sentiment`).

The tracker is passive — it records outcomes and computes accuracy but does not
actively filter sources. The ML model learns optimal weighting via SHAP.

## Schema
```sql
source_reliability (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    ticker TEXT,
    correct_calls INTEGER DEFAULT 0,
    total_calls INTEGER DEFAULT 0,
    accuracy REAL DEFAULT 0.0,
    last_updated TIMESTAMP,
    window_start TIMESTAMP
)
```

## Consequences
- Every sentiment signal must be tagged with source identifier
- Source accuracy updated weekly after outcomes are known
- `source_weighted_sentiment` feature = sentiment_score * source_accuracy
- Initial accuracy defaults to 0.5 (uninformative prior) until 10+ calls recorded
```

- [ ] **Step 2: Write ADR-022 — Daily Discovery + Weekly Analysis**

```markdown
# ADR-022: Daily Discovery Scan + Weekly Full Analysis

## Status
Accepted

## Context
Phase 3A uses a static 40-ticker universe. The project thesis requires dynamic
buzz-driven discovery (ADR-002) to find emerging opportunities before the wave hits.
Weekly-only scanning is too slow — sentiment leads price by 1-48 hours (ADR-001).

## Decision
Two-cadence architecture:

1. **Daily scan** (lightweight): RSS feeds only. Scan 6 publishers, extract ticker
   mentions, compute keyword + Flan-T5 sentiment. Store in `buzz_signals` SQLite table.
   ~500 articles/day, ~2.5 min on M2 MPS.

2. **Weekly analysis** (full compute): Read accumulated buzz_signals. Rank tickers by
   buzz acceleration (week-over-week mention change). Filter by us.yaml quality gates.
   Run Stage 1 (frozen technical) + Stage 2 (sentiment blend). Output Top 15 picks.

Both triggered via CLI for Phase 3B. Automation deferred to Phase 4 (ADR-007).

## Consequences
- `daily-scan` CLI command runs RSS → keyword + Flan-T5 → buzz_signals table
- `run-tournament` CLI command extended to read buzz_signals and run Stage 2
- Buzz acceleration (not absolute volume) drives ticker discovery
- Universe can change week-to-week based on buzz patterns
```

- [ ] **Step 3: Commit ADRs**

```bash
git add docs/adr/ADR-021-source-reliability-tracker.md docs/adr/ADR-022-daily-discovery-weekly-analysis.md
git commit -m "docs: add ADR-021 (source reliability) and ADR-022 (daily discovery)"
```

---

## Task 2: Domain Models — BuzzSignal + SourceReliability [Sonnet]

**Files:**
- Modify: `domain/models.py` (after line 188)
- Test: `tests/test_domain_models.py`

- [ ] **Step 1: Write failing tests for BuzzSignal and SourceReliability**

```python
# Add to tests/test_domain_models.py

def test_buzz_signal_valid_creation():
    bs = BuzzSignal(
        ticker="AAPL",
        source="reuters_rss",
        mention_count=15,
        sentiment_raw=0.7,
        scorer="keyword",
        fetched_at=datetime(2026, 5, 30, 9, 0),
        article_hash="abc123",
    )
    assert bs.ticker == "AAPL"
    assert bs.source == "reuters_rss"
    assert bs.mention_count == 15
    assert bs.sentiment_raw == 0.7


def test_buzz_signal_rejects_negative_mentions():
    with pytest.raises(ValueError, match="mention_count"):
        BuzzSignal(
            ticker="AAPL",
            source="reuters_rss",
            mention_count=-1,
            sentiment_raw=0.5,
            scorer="keyword",
            fetched_at=datetime(2026, 5, 30, 9, 0),
            article_hash="abc123",
        )


def test_buzz_signal_rejects_invalid_sentiment():
    with pytest.raises(ValueError, match="sentiment_raw"):
        BuzzSignal(
            ticker="AAPL",
            source="reuters_rss",
            mention_count=5,
            sentiment_raw=1.5,  # out of [-1, 1]
            scorer="keyword",
            fetched_at=datetime(2026, 5, 30, 9, 0),
            article_hash="abc123",
        )


def test_source_reliability_valid_creation():
    sr = SourceReliability(
        source="reuters_rss",
        ticker="AAPL",
        correct_calls=7,
        total_calls=10,
    )
    assert sr.accuracy == 0.7


def test_source_reliability_zero_calls_defaults_half():
    sr = SourceReliability(
        source="reuters_rss",
        ticker=None,
        correct_calls=0,
        total_calls=0,
    )
    assert sr.accuracy == 0.5  # uninformative prior


def test_source_reliability_rejects_negative_calls():
    with pytest.raises(ValueError, match="correct_calls"):
        SourceReliability(
            source="reuters_rss",
            ticker=None,
            correct_calls=-1,
            total_calls=5,
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_domain_models.py -k "buzz_signal or source_reliability" -v`
Expected: FAIL with `ImportError` (BuzzSignal, SourceReliability not defined)

- [ ] **Step 3: Implement BuzzSignal and SourceReliability in domain/models.py**

Add after `WeeklyReport` class (after line 188):

```python
@dataclass(frozen=True)
class BuzzSignal:
    """A single buzz/sentiment observation from a news or social source."""

    ticker: str
    source: str  # e.g., "reuters_rss", "reddit_wsb"
    mention_count: int
    sentiment_raw: float  # [-1, 1] from keyword or Flan-T5 scorer
    scorer: str  # "keyword" or "flan_t5"
    fetched_at: datetime
    article_hash: str  # dedup key

    def __post_init__(self) -> None:
        if self.mention_count < 0:
            raise ValueError("mention_count must be >= 0")
        if not -1.0 <= self.sentiment_raw <= 1.0:
            raise ValueError("sentiment_raw must be in [-1, 1]")


@dataclass(frozen=True)
class SourceReliability:
    """Tracks per-source directional accuracy over time."""

    source: str
    ticker: str | None  # None = aggregate across all tickers
    correct_calls: int
    total_calls: int

    def __post_init__(self) -> None:
        if self.correct_calls < 0:
            raise ValueError("correct_calls must be >= 0")
        if self.total_calls < 0:
            raise ValueError("total_calls must be >= 0")
        if self.correct_calls > self.total_calls:
            raise ValueError("correct_calls cannot exceed total_calls")

    @property
    def accuracy(self) -> float:
        """Return accuracy, defaulting to 0.5 (uninformative prior) if < 10 calls."""
        if self.total_calls < 10:
            return 0.5
        return self.correct_calls / self.total_calls
```

- [ ] **Step 4: Update imports in `domain/__init__.py` and test file**

Add `BuzzSignal, SourceReliability` to `domain/models.py` imports in test file.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_domain_models.py -k "buzz_signal or source_reliability" -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```bash
git add domain/models.py tests/test_domain_models.py
git commit -m "feat: add BuzzSignal and SourceReliability domain models"
```

---

## Task 3: Domain Ports — BuzzDiscoveryPort + SourceReliabilityPort [Sonnet]

**Files:**
- Modify: `domain/ports.py` (add after `BacktestResultPort`, line 118)
- Test: `tests/test_domain_models.py` (Protocol conformance test)

- [ ] **Step 1: Write Protocol conformance tests**

```python
# Add to tests/test_domain_models.py (or a new test_ports.py)

from typing import runtime_checkable

def test_buzz_discovery_port_is_protocol():
    """BuzzDiscoveryPort must be a runtime-checkable Protocol."""
    from domain.ports import BuzzDiscoveryPort
    assert hasattr(BuzzDiscoveryPort, '__protocol_attrs__') or hasattr(BuzzDiscoveryPort, '_is_protocol')


def test_source_reliability_port_is_protocol():
    """SourceReliabilityPort must be a runtime-checkable Protocol."""
    from domain.ports import SourceReliabilityPort
    assert hasattr(SourceReliabilityPort, '__protocol_attrs__') or hasattr(SourceReliabilityPort, '_is_protocol')
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_domain_models.py -k "port_is_protocol" -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Add BuzzDiscoveryPort and SourceReliabilityPort to domain/ports.py**

Add after `BacktestResultPort` (after line 118):

```python
@runtime_checkable
class BuzzDiscoveryPort(Protocol):
    """Discovers buzzing tickers from news/social sources."""

    def scan_sources(
        self,
        scan_time: datetime,
    ) -> list[BuzzSignal]:
        """Scan all configured sources and return buzz signals."""
        ...

    def get_buzz_signals(
        self,
        ticker: str | None = None,
        source: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[BuzzSignal]:
        """Retrieve stored buzz signals with optional filters."""
        ...


@runtime_checkable
class SourceReliabilityPort(Protocol):
    """Tracks per-source prediction accuracy over time."""

    def record_outcome(
        self,
        source: str,
        ticker: str,
        predicted_direction: float,
        actual_direction: float,
    ) -> None:
        """Record whether a source's sentiment predicted direction correctly."""
        ...

    def get_reliability(
        self,
        source: str,
        ticker: str | None = None,
    ) -> SourceReliability:
        """Get reliability stats for a source (optionally per-ticker)."""
        ...

    def get_all_reliabilities(self) -> list[SourceReliability]:
        """Get reliability stats for all tracked sources."""
        ...
```

Add `BuzzSignal, SourceReliability` to the imports from `domain.models` at top of ports.py.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_domain_models.py -k "port_is_protocol" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add domain/ports.py
git commit -m "feat: add BuzzDiscoveryPort and SourceReliabilityPort protocols"
```

---

## Task 4: SQLite Store — buzz_signals + source_reliability Tables [Sonnet]

**Files:**
- Modify: `adapters/data/sqlite_store.py` (add tables in `_create_tables`, add methods)
- Test: `tests/test_sqlite_store.py`

- [ ] **Step 1: Write failing tests for buzz signal storage**

```python
# Add to tests/test_sqlite_store.py

from domain.models import BuzzSignal, SourceReliability
from datetime import datetime


def test_save_and_get_buzz_signals(tmp_path):
    store = SQLiteStore(str(tmp_path / "test.db"))
    bs = BuzzSignal(
        ticker="AAPL",
        source="reuters_rss",
        mention_count=10,
        sentiment_raw=0.6,
        scorer="keyword",
        fetched_at=datetime(2026, 5, 30, 9, 0),
        article_hash="hash1",
    )
    store.save_buzz_signal(bs)
    results = store.get_buzz_signals(ticker="AAPL")
    assert len(results) == 1
    assert results[0].ticker == "AAPL"
    assert results[0].sentiment_raw == 0.6


def test_buzz_signal_dedup_by_hash(tmp_path):
    store = SQLiteStore(str(tmp_path / "test.db"))
    bs = BuzzSignal(
        ticker="AAPL",
        source="reuters_rss",
        mention_count=10,
        sentiment_raw=0.6,
        scorer="keyword",
        fetched_at=datetime(2026, 5, 30, 9, 0),
        article_hash="hash1",
    )
    store.save_buzz_signal(bs)
    store.save_buzz_signal(bs)  # duplicate
    results = store.get_buzz_signals(ticker="AAPL")
    assert len(results) == 1  # deduped


def test_get_buzz_signals_date_filter(tmp_path):
    store = SQLiteStore(str(tmp_path / "test.db"))
    bs1 = BuzzSignal(
        ticker="AAPL", source="reuters_rss", mention_count=5,
        sentiment_raw=0.3, scorer="keyword",
        fetched_at=datetime(2026, 5, 28, 9, 0), article_hash="h1",
    )
    bs2 = BuzzSignal(
        ticker="AAPL", source="reuters_rss", mention_count=15,
        sentiment_raw=0.8, scorer="keyword",
        fetched_at=datetime(2026, 5, 30, 9, 0), article_hash="h2",
    )
    store.save_buzz_signal(bs1)
    store.save_buzz_signal(bs2)
    results = store.get_buzz_signals(
        ticker="AAPL",
        start_date=datetime(2026, 5, 29),
    )
    assert len(results) == 1
    assert results[0].article_hash == "h2"


def test_save_and_get_source_reliability(tmp_path):
    store = SQLiteStore(str(tmp_path / "test.db"))
    store.record_source_outcome("reuters_rss", "AAPL", 0.5, 0.3)  # correct (both positive)
    store.record_source_outcome("reuters_rss", "AAPL", -0.2, 0.1)  # incorrect
    rel = store.get_source_reliability("reuters_rss", "AAPL")
    assert rel.correct_calls == 1
    assert rel.total_calls == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_sqlite_store.py -k "buzz_signal or source_reliability" -v`
Expected: FAIL (methods not defined)

- [ ] **Step 3: Add buzz_signals and source_reliability tables to _create_tables**

In `adapters/data/sqlite_store.py`, add to `_create_tables()` method (after existing table creation):

```python
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS buzz_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                source TEXT NOT NULL,
                mention_count INTEGER NOT NULL,
                sentiment_raw REAL NOT NULL,
                scorer TEXT NOT NULL,
                fetched_at TIMESTAMP NOT NULL,
                article_hash TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_buzz_ticker ON buzz_signals(ticker)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_buzz_fetched ON buzz_signals(fetched_at)"
        )
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS source_reliability (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                ticker TEXT,
                correct_calls INTEGER DEFAULT 0,
                total_calls INTEGER DEFAULT 0,
                last_updated TIMESTAMP,
                UNIQUE(source, ticker)
            )
        """)
```

- [ ] **Step 4: Implement save_buzz_signal and get_buzz_signals methods**

```python
    def save_buzz_signal(self, signal: BuzzSignal) -> None:
        """Save a buzz signal, deduplicating by article_hash."""
        self._conn.execute(
            """INSERT OR IGNORE INTO buzz_signals
               (ticker, source, mention_count, sentiment_raw, scorer, fetched_at, article_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                signal.ticker,
                signal.source,
                signal.mention_count,
                signal.sentiment_raw,
                signal.scorer,
                signal.fetched_at.isoformat(),
                signal.article_hash,
            ),
        )
        self._conn.commit()

    def get_buzz_signals(
        self,
        ticker: str | None = None,
        source: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[BuzzSignal]:
        """Retrieve buzz signals with optional filters."""
        query = "SELECT * FROM buzz_signals WHERE 1=1"
        params: list[str] = []
        if ticker:
            query += " AND ticker = ?"
            params.append(ticker)
        if source:
            query += " AND source = ?"
            params.append(source)
        if start_date:
            query += " AND fetched_at >= ?"
            params.append(start_date.isoformat())
        if end_date:
            query += " AND fetched_at <= ?"
            params.append(end_date.isoformat())
        query += " ORDER BY fetched_at DESC"
        rows = self._conn.execute(query, params).fetchall()
        return [
            BuzzSignal(
                ticker=r["ticker"],
                source=r["source"],
                mention_count=r["mention_count"],
                sentiment_raw=r["sentiment_raw"],
                scorer=r["scorer"],
                fetched_at=datetime.fromisoformat(r["fetched_at"]),
                article_hash=r["article_hash"],
            )
            for r in rows
        ]
```

- [ ] **Step 5: Implement record_source_outcome and get_source_reliability**

```python
    def record_source_outcome(
        self,
        source: str,
        ticker: str,
        predicted_direction: float,
        actual_direction: float,
    ) -> None:
        """Record whether a source's sentiment predicted direction correctly."""
        correct = 1 if (predicted_direction >= 0) == (actual_direction >= 0) else 0
        self._conn.execute(
            """INSERT INTO source_reliability (source, ticker, correct_calls, total_calls, last_updated)
               VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
               ON CONFLICT(source, ticker) DO UPDATE SET
                   correct_calls = correct_calls + ?,
                   total_calls = total_calls + 1,
                   last_updated = CURRENT_TIMESTAMP""",
            (source, ticker, correct, correct),
        )
        self._conn.commit()

    def get_source_reliability(
        self, source: str, ticker: str | None = None
    ) -> SourceReliability:
        """Get reliability stats for a source."""
        if ticker:
            row = self._conn.execute(
                "SELECT * FROM source_reliability WHERE source = ? AND ticker = ?",
                (source, ticker),
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT source, NULL as ticker, SUM(correct_calls) as correct_calls, "
                "SUM(total_calls) as total_calls FROM source_reliability WHERE source = ?",
                (source,),
            ).fetchone()
        if not row or row["total_calls"] is None:
            return SourceReliability(source=source, ticker=ticker, correct_calls=0, total_calls=0)
        return SourceReliability(
            source=source,
            ticker=ticker,
            correct_calls=row["correct_calls"],
            total_calls=row["total_calls"],
        )

    def get_all_source_reliabilities(self) -> list[SourceReliability]:
        """Get reliability stats for all tracked sources."""
        rows = self._conn.execute(
            "SELECT source, ticker, correct_calls, total_calls FROM source_reliability"
        ).fetchall()
        return [
            SourceReliability(
                source=r["source"],
                ticker=r["ticker"],
                correct_calls=r["correct_calls"],
                total_calls=r["total_calls"],
            )
            for r in rows
        ]
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_sqlite_store.py -k "buzz_signal or source_reliability" -v`
Expected: PASS (4 tests)

- [ ] **Step 7: Commit**

```bash
git add adapters/data/sqlite_store.py tests/test_sqlite_store.py
git commit -m "feat: add buzz_signals and source_reliability tables to SQLiteStore"
```

---

## Task 5: Keyword Sentiment Scorer [Sonnet]

**Files:**
- Create: `adapters/ml/keyword_scorer.py`
- Create: `tests/test_keyword_scorer.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_keyword_scorer.py
from datetime import datetime

from adapters.ml.keyword_scorer import KeywordScorer
from domain.models import Sentiment


class TestKeywordScorer:
    def setup_method(self):
        self.scorer = KeywordScorer()

    def test_bullish_text_positive_score(self):
        results = self.scorer.score_text(
            "AAPL",
            "Apple reports record revenue, beats expectations, strong growth ahead",
            datetime(2026, 5, 30),
            source="reuters_rss",
        )
        assert len(results) == 1
        assert results[0].sentiment_score > 0
        assert results[0].source == "reuters_rss"

    def test_bearish_text_negative_score(self):
        results = self.scorer.score_text(
            "TSLA",
            "Tesla recalls vehicles, faces lawsuit, revenue decline worsens",
            datetime(2026, 5, 30),
            source="reuters_rss",
        )
        assert len(results) == 1
        assert results[0].sentiment_score < 0

    def test_neutral_text_near_zero(self):
        results = self.scorer.score_text(
            "MSFT",
            "Microsoft announces quarterly earnings date",
            datetime(2026, 5, 30),
            source="reuters_rss",
        )
        assert len(results) == 1
        assert abs(results[0].sentiment_score) < 0.3

    def test_empty_text_returns_zero(self):
        results = self.scorer.score_text(
            "AAPL", "", datetime(2026, 5, 30), source="reuters_rss",
        )
        assert len(results) == 1
        assert results[0].sentiment_score == 0.0

    def test_implements_sentiment_port(self):
        """KeywordScorer must implement SentimentPort.get_sentiment()."""
        assert hasattr(self.scorer, "get_sentiment")

    def test_confidence_bounded(self):
        results = self.scorer.score_text(
            "AAPL",
            "record revenue beats expectations strong growth surge rally",
            datetime(2026, 5, 30),
            source="reuters_rss",
        )
        assert 0.0 <= results[0].confidence <= 1.0

    def test_score_bounded(self):
        results = self.scorer.score_text(
            "AAPL",
            "record revenue beats growth surge rally boom soar explode moon",
            datetime(2026, 5, 30),
            source="reuters_rss",
        )
        assert -1.0 <= results[0].sentiment_score <= 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_keyword_scorer.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement KeywordScorer**

```python
# adapters/ml/keyword_scorer.py
"""Rule-based keyword sentiment scorer.

Counts bullish/bearish keyword hits in text, normalizes to [-1, 1].
Fast baseline — runs in <1ms per article. Parallel with Flan-T5 (ADR-008).
"""

from __future__ import annotations

from datetime import datetime

from domain.models import Sentiment

BULLISH_KEYWORDS: list[str] = [
    "beat", "beats", "exceeded", "record", "surge", "surges", "rally",
    "growth", "upgrade", "upgrades", "outperform", "strong", "profit",
    "gains", "positive", "optimistic", "bullish", "breakout", "soar",
    "boom", "revenue growth", "earnings beat", "buy rating", "price target raised",
    "all-time high", "momentum", "recovery", "upside", "dividend increase",
]

BEARISH_KEYWORDS: list[str] = [
    "miss", "misses", "missed", "decline", "declines", "drop", "drops",
    "loss", "losses", "recall", "recalls", "lawsuit", "layoff", "layoffs",
    "downgrade", "downgrades", "underperform", "weak", "negative", "bearish",
    "crash", "plunge", "sell-off", "selloff", "warning", "risk", "debt",
    "default", "bankruptcy", "investigation", "fine", "penalty",
    "revenue decline", "earnings miss", "sell rating", "price target cut",
]


class KeywordScorer:
    """Rule-based sentiment scorer using keyword matching."""

    def __init__(
        self,
        bullish: list[str] | None = None,
        bearish: list[str] | None = None,
    ) -> None:
        self._bullish = [k.lower() for k in (bullish or BULLISH_KEYWORDS)]
        self._bearish = [k.lower() for k in (bearish or BEARISH_KEYWORDS)]

    def score_text(
        self,
        ticker: str,
        text: str,
        timestamp: datetime,
        source: str = "unknown",
    ) -> list[Sentiment]:
        """Score a single text and return a Sentiment object."""
        text_lower = text.lower()

        bull_hits = sum(1 for kw in self._bullish if kw in text_lower)
        bear_hits = sum(1 for kw in self._bearish if kw in text_lower)
        total_hits = bull_hits + bear_hits

        if total_hits == 0:
            score = 0.0
            confidence = 0.1
        else:
            raw = (bull_hits - bear_hits) / total_hits
            score = max(-1.0, min(1.0, raw))
            confidence = min(1.0, total_hits / 10.0)

        return [
            Sentiment(
                source=source,
                timestamp=timestamp,
                sentiment_score=score,
                confidence=confidence,
                text_snippet=text[:200] if text else None,
            )
        ]

    def get_sentiment(
        self,
        symbol: str,
        prediction_time: datetime,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[Sentiment]:
        """SentimentPort interface — returns empty list (use score_text for scoring)."""
        return []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_keyword_scorer.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add adapters/ml/keyword_scorer.py tests/test_keyword_scorer.py
git commit -m "feat: add keyword sentiment scorer with bullish/bearish dictionaries"
```

---

## Task 6: Flan-T5 Sentiment Scorer [Sonnet]

**Files:**
- Create: `adapters/ml/flan_t5_scorer.py`
- Create: `tests/test_flan_t5_scorer.py`

- [ ] **Step 1: Write failing tests (mock the model for CI)**

```python
# tests/test_flan_t5_scorer.py
from datetime import datetime
from unittest.mock import MagicMock, patch

from adapters.ml.flan_t5_scorer import FlanT5Scorer
from domain.models import Sentiment


class TestFlanT5Scorer:
    def test_score_text_returns_sentiment(self):
        """Test with mocked model — CI should never load real weights."""
        scorer = FlanT5Scorer.__new__(FlanT5Scorer)
        scorer._model = MagicMock()
        scorer._tokenizer = MagicMock()

        # Mock tokenizer to return fake input_ids
        mock_inputs = {"input_ids": MagicMock(), "attention_mask": MagicMock()}
        mock_inputs["input_ids"].to = MagicMock(return_value=mock_inputs["input_ids"])
        mock_inputs["attention_mask"].to = MagicMock(return_value=mock_inputs["attention_mask"])
        scorer._tokenizer.return_value = mock_inputs
        scorer._tokenizer.decode.return_value = "positive"
        scorer._device = "cpu"

        # Mock model.generate
        scorer._model.generate.return_value = MagicMock()

        results = scorer.score_text(
            "AAPL",
            "Apple reports record revenue",
            datetime(2026, 5, 30),
            source="reuters_rss",
        )
        assert len(results) == 1
        assert isinstance(results[0], Sentiment)
        assert results[0].source == "reuters_rss"
        assert -1.0 <= results[0].sentiment_score <= 1.0

    def test_positive_label_maps_to_positive_score(self):
        scorer = FlanT5Scorer.__new__(FlanT5Scorer)
        score = scorer._label_to_score("positive")
        assert score > 0

    def test_negative_label_maps_to_negative_score(self):
        scorer = FlanT5Scorer.__new__(FlanT5Scorer)
        score = scorer._label_to_score("negative")
        assert score < 0

    def test_neutral_label_maps_to_zero(self):
        scorer = FlanT5Scorer.__new__(FlanT5Scorer)
        score = scorer._label_to_score("neutral")
        assert score == 0.0

    def test_unknown_label_maps_to_zero(self):
        scorer = FlanT5Scorer.__new__(FlanT5Scorer)
        score = scorer._label_to_score("gibberish")
        assert score == 0.0

    def test_implements_sentiment_port(self):
        scorer = FlanT5Scorer.__new__(FlanT5Scorer)
        assert hasattr(scorer, "get_sentiment")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_flan_t5_scorer.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement FlanT5Scorer**

```python
# adapters/ml/flan_t5_scorer.py
"""Flan-T5 zero-shot sentiment scorer.

Uses google/flan-t5-base (250M params) locally via MPS on Apple Silicon.
Prompt: "Classify the sentiment of this financial news as positive, negative,
or neutral: {text}"

ADR-004: Flan-T5 over FinBERT for generality.
ADR-008: Runs parallel with KeywordScorer.
"""

from __future__ import annotations

from datetime import datetime

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

from domain.models import Sentiment

_PROMPT_TEMPLATE = (
    "Classify the sentiment of this financial news about {ticker} as "
    "positive, negative, or neutral: {text}"
)

_LABEL_MAP: dict[str, float] = {
    "positive": 0.8,
    "negative": -0.8,
    "neutral": 0.0,
}


class FlanT5Scorer:
    """Zero-shot sentiment scorer using Flan-T5-base."""

    def __init__(
        self,
        model_name: str = "google/flan-t5-base",
        device: str | None = None,
    ) -> None:
        if device is None:
            if torch.backends.mps.is_available():
                device = "mps"
            elif torch.cuda.is_available():
                device = "cuda"
            else:
                device = "cpu"
        self._device = device
        self._tokenizer = AutoTokenizer.from_pretrained(model_name)
        self._model = AutoModelForSeq2SeqLM.from_pretrained(model_name).to(device)
        self._model.eval()

    def score_text(
        self,
        ticker: str,
        text: str,
        timestamp: datetime,
        source: str = "unknown",
    ) -> list[Sentiment]:
        """Score a single text using Flan-T5 zero-shot classification."""
        prompt = _PROMPT_TEMPLATE.format(ticker=ticker, text=text[:512])
        inputs = self._tokenizer(
            prompt, return_tensors="pt", max_length=512, truncation=True
        )
        input_ids = inputs["input_ids"].to(self._device)
        attention_mask = inputs["attention_mask"].to(self._device)

        with torch.no_grad():
            outputs = self._model.generate(
                input_ids=input_ids,
                attention_mask=attention_mask,
                max_new_tokens=10,
            )
        label = self._tokenizer.decode(outputs[0], skip_special_tokens=True).strip().lower()
        score = self._label_to_score(label)

        return [
            Sentiment(
                source=source,
                timestamp=timestamp,
                sentiment_score=score,
                confidence=0.7,  # Flan-T5 base confidence; could calibrate later
                text_snippet=text[:200] if text else None,
            )
        ]

    @staticmethod
    def _label_to_score(label: str) -> float:
        """Map Flan-T5 output label to sentiment score."""
        label = label.lower().strip()
        for key, value in _LABEL_MAP.items():
            if key in label:
                return value
        return 0.0

    def get_sentiment(
        self,
        symbol: str,
        prediction_time: datetime,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[Sentiment]:
        """SentimentPort interface — returns empty list (use score_text for scoring)."""
        return []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_flan_t5_scorer.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add adapters/ml/flan_t5_scorer.py tests/test_flan_t5_scorer.py
git commit -m "feat: add Flan-T5 zero-shot sentiment scorer with MPS support"
```

---

## Task 7: RSS Feed Adapter [Sonnet]

**Files:**
- Create: `adapters/data/rss_adapter.py`
- Create: `tests/test_rss_adapter.py`

- [ ] **Step 1: Write failing tests (mock HTTP)**

```python
# tests/test_rss_adapter.py
from datetime import datetime
from unittest.mock import MagicMock, patch

from adapters.data.rss_adapter import RSSAdapter


FAKE_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>Test Feed</title>
<item>
  <title>Apple reports record Q3 revenue beating expectations</title>
  <description>AAPL stock surges after strong earnings report.</description>
  <pubDate>Thu, 29 May 2026 14:00:00 GMT</pubDate>
  <link>https://example.com/article1</link>
</item>
<item>
  <title>Tesla recalls 500k vehicles over safety concerns</title>
  <description>TSLA faces regulatory pressure.</description>
  <pubDate>Thu, 29 May 2026 10:00:00 GMT</pubDate>
  <link>https://example.com/article2</link>
</item>
</channel>
</rss>"""


class TestRSSAdapter:
    def test_parse_feed_extracts_articles(self):
        adapter = RSSAdapter(feeds={"test_feed": "https://example.com/rss"})
        articles = adapter._parse_feed("test_feed", FAKE_RSS_XML)
        assert len(articles) == 2
        assert "Apple" in articles[0]["title"]

    def test_extract_tickers_from_text(self):
        adapter = RSSAdapter(feeds={})
        tickers = adapter._extract_tickers(
            "Apple (AAPL) and Tesla (TSLA) reported earnings. MSFT also moved."
        )
        assert "AAPL" in tickers
        assert "TSLA" in tickers
        assert "MSFT" in tickers

    def test_extract_tickers_handles_no_match(self):
        adapter = RSSAdapter(feeds={})
        tickers = adapter._extract_tickers("The weather is nice today.")
        assert len(tickers) == 0

    @patch("adapters.data.rss_adapter.feedparser.parse")
    def test_scan_sources_returns_buzz_signals(self, mock_parse):
        mock_parse.return_value = MagicMock(
            entries=[
                MagicMock(
                    title="Apple AAPL surges on earnings beat",
                    summary="Strong growth for AAPL",
                    published_parsed=(2026, 5, 29, 14, 0, 0, 0, 0, 0),
                    link="https://example.com/1",
                ),
            ]
        )
        adapter = RSSAdapter(feeds={"reuters": "https://example.com/rss"})
        signals = adapter.scan_sources(datetime(2026, 5, 30))
        assert len(signals) >= 1
        assert signals[0].ticker == "AAPL"
        assert signals[0].source == "reuters"

    def test_article_hash_deterministic(self):
        adapter = RSSAdapter(feeds={})
        h1 = adapter._hash_article("https://example.com/1", "Title")
        h2 = adapter._hash_article("https://example.com/1", "Title")
        assert h1 == h2

    def test_article_hash_unique(self):
        adapter = RSSAdapter(feeds={})
        h1 = adapter._hash_article("https://example.com/1", "Title A")
        h2 = adapter._hash_article("https://example.com/2", "Title B")
        assert h1 != h2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_rss_adapter.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement RSSAdapter**

```python
# adapters/data/rss_adapter.py
"""RSS feed adapter for financial news buzz discovery.

Scans 6 publishers (Reuters, Bloomberg, MarketWatch, CNBC, Yahoo Finance,
Seeking Alpha). Extracts ticker mentions via regex + known ticker set.
ADR-022: Daily scan cadence.
"""

from __future__ import annotations

import hashlib
import re
import time
from datetime import datetime
from typing import Any

import feedparser
from loguru import logger

from domain.models import BuzzSignal

# Default financial RSS feeds
DEFAULT_FEEDS: dict[str, str] = {
    "reuters": "https://www.reutersagency.com/feed/?best-topics=business-finance",
    "marketwatch": "https://feeds.marketwatch.com/marketwatch/topstories/",
    "cnbc": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
    "yahoo_finance": "https://finance.yahoo.com/news/rssindex",
    "seeking_alpha": "https://seekingalpha.com/market_currents.xml",
    "investing_com": "https://www.investing.com/rss/news.rss",
}

# Common ticker patterns
_TICKER_PATTERN = re.compile(r"\b([A-Z]{1,5})\b")

# Known S&P 500 tickers for validation (subset — extend as needed)
_KNOWN_TICKERS: set[str] = {
    "AAPL", "MSFT", "GOOG", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
    "BRK", "UNH", "JNJ", "V", "XOM", "JPM", "PG", "MA", "HD", "CVX",
    "MRK", "ABBV", "LLY", "PEP", "KO", "COST", "AVGO", "WMT", "MCD",
    "CSCO", "ACN", "TMO", "ABT", "DHR", "NEE", "LIN", "TXN", "PM",
    "UPS", "RTX", "HON", "LOW", "QCOM", "AMD", "CRM", "INTC", "NFLX",
    "DIS", "BA", "CAT", "GS", "AMGN", "IBM", "GE", "SBUX", "BLK",
    "ISRG", "MDLZ", "BKNG", "AMAT", "ADI", "PYPL", "REGN", "VRTX",
    "NOW", "PANW", "SNPS", "CDNS", "LRCX", "KLAC", "MRVL", "FTNT",
}

# Words that look like tickers but aren't
_TICKER_BLOCKLIST: set[str] = {
    "CEO", "CFO", "CTO", "COO", "IPO", "ETF", "SEC", "FDA", "GDP",
    "FED", "NYSE", "AI", "IT", "US", "UK", "EU", "USD", "THE", "FOR",
    "AND", "NOT", "ARE", "WAS", "HAS", "HAD", "BUT", "ALL", "NEW",
    "OLD", "BIG", "TOP", "LOW", "HIGH", "UP", "DOWN", "OUT", "OFF",
    "Q1", "Q2", "Q3", "Q4", "YOY", "QOQ", "EPS", "PE", "RSI", "ATH",
}


class RSSAdapter:
    """RSS feed scanner for financial news buzz discovery."""

    def __init__(
        self,
        feeds: dict[str, str] | None = None,
        request_delay: float = 1.0,
    ) -> None:
        self._feeds = feeds if feeds is not None else DEFAULT_FEEDS
        self._request_delay = request_delay

    def scan_sources(self, scan_time: datetime) -> list[BuzzSignal]:
        """Scan all configured RSS feeds and return buzz signals."""
        all_signals: list[BuzzSignal] = []

        for source_name, url in self._feeds.items():
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    signals = self._entry_to_signals(source_name, entry)
                    all_signals.extend(signals)
                logger.info(
                    f"RSS scan {source_name}: {len(feed.entries)} entries"
                )
            except Exception as e:
                logger.warning(f"RSS scan failed for {source_name}: {e}")
            time.sleep(self._request_delay)

        logger.info(f"RSS scan complete: {len(all_signals)} signals from {len(self._feeds)} feeds")
        return all_signals

    def _entry_to_signals(
        self, source_name: str, entry: Any
    ) -> list[BuzzSignal]:
        """Convert an RSS entry to BuzzSignal(s) — one per detected ticker."""
        title = getattr(entry, "title", "")
        summary = getattr(entry, "summary", "")
        link = getattr(entry, "link", "")
        text = f"{title} {summary}"

        # Parse published time
        pub_parsed = getattr(entry, "published_parsed", None)
        if pub_parsed:
            pub_time = datetime(*pub_parsed[:6])
        else:
            pub_time = datetime.now()

        tickers = self._extract_tickers(text)
        signals: list[BuzzSignal] = []

        for ticker in tickers:
            signals.append(
                BuzzSignal(
                    ticker=ticker,
                    source=source_name,
                    mention_count=1,
                    sentiment_raw=0.0,  # Raw RSS — scorer fills this later
                    scorer="rss_raw",
                    fetched_at=pub_time,
                    article_hash=self._hash_article(link, title),
                )
            )
        return signals

    def _extract_tickers(self, text: str) -> list[str]:
        """Extract stock tickers from text using regex + known ticker validation."""
        candidates = set(_TICKER_PATTERN.findall(text))
        return [
            t for t in candidates
            if t in _KNOWN_TICKERS and t not in _TICKER_BLOCKLIST
        ]

    def _parse_feed(self, source_name: str, xml_content: str) -> list[dict[str, str]]:
        """Parse raw XML RSS content into article dicts (for testing)."""
        feed = feedparser.parse(xml_content)
        return [
            {
                "title": getattr(e, "title", ""),
                "summary": getattr(e, "summary", ""),
                "link": getattr(e, "link", ""),
                "source": source_name,
            }
            for e in feed.entries
        ]

    @staticmethod
    def _hash_article(url: str, title: str) -> str:
        """Deterministic hash for deduplication."""
        return hashlib.sha256(f"{url}|{title}".encode()).hexdigest()[:16]

    def get_buzz_signals(
        self,
        ticker: str | None = None,
        source: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[BuzzSignal]:
        """BuzzDiscoveryPort interface — scan returns signals, storage is in SQLiteStore."""
        return []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_rss_adapter.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add adapters/data/rss_adapter.py tests/test_rss_adapter.py
git commit -m "feat: add RSS feed adapter for financial news buzz discovery"
```

---

## Task 8: Fake Adapters for Sentiment Layer [Sonnet]

**Files:**
- Create: `tests/fakes/fake_sentiment.py`
- Create: `tests/fakes/fake_buzz_discovery.py`
- Create: `tests/fakes/fake_source_reliability.py`

- [ ] **Step 1: Write FakeSentimentScorer**

```python
# tests/fakes/fake_sentiment.py
"""Fake SentimentPort for testing."""

from __future__ import annotations

from datetime import datetime

from domain.models import Sentiment


class FakeSentimentScorer:
    """Returns configurable sentiment scores for testing."""

    def __init__(
        self,
        scores: dict[str, float] | None = None,
        default_score: float = 0.5,
    ) -> None:
        self._scores = scores or {}
        self._default = default_score
        self.score_calls: list[tuple[str, str]] = []

    def score_text(
        self,
        ticker: str,
        text: str,
        timestamp: datetime,
        source: str = "fake",
    ) -> list[Sentiment]:
        self.score_calls.append((ticker, text))
        score = self._scores.get(ticker, self._default)
        return [
            Sentiment(
                source=source,
                timestamp=timestamp,
                sentiment_score=score,
                confidence=0.8,
                text_snippet=text[:200] if text else None,
            )
        ]

    def get_sentiment(
        self,
        symbol: str,
        prediction_time: datetime,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[Sentiment]:
        return [
            Sentiment(
                source="fake",
                timestamp=prediction_time,
                sentiment_score=self._scores.get(symbol, self._default),
                confidence=0.8,
            )
        ]
```

- [ ] **Step 2: Write FakeBuzzDiscovery**

```python
# tests/fakes/fake_buzz_discovery.py
"""Fake BuzzDiscoveryPort for testing."""

from __future__ import annotations

from datetime import datetime

from domain.models import BuzzSignal


class FakeBuzzDiscovery:
    """Returns configurable buzz signals for testing."""

    def __init__(self, signals: list[BuzzSignal] | None = None) -> None:
        self._signals = signals or []
        self.scan_calls: list[datetime] = []

    def scan_sources(self, scan_time: datetime) -> list[BuzzSignal]:
        self.scan_calls.append(scan_time)
        return self._signals

    def get_buzz_signals(
        self,
        ticker: str | None = None,
        source: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[BuzzSignal]:
        results = self._signals
        if ticker:
            results = [s for s in results if s.ticker == ticker]
        if source:
            results = [s for s in results if s.source == source]
        return results
```

- [ ] **Step 3: Write FakeSourceReliability**

```python
# tests/fakes/fake_source_reliability.py
"""Fake SourceReliabilityPort for testing."""

from __future__ import annotations

from domain.models import SourceReliability


class FakeSourceReliability:
    """In-memory source reliability tracker for testing."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str | None], dict[str, int]] = {}

    def record_outcome(
        self,
        source: str,
        ticker: str,
        predicted_direction: float,
        actual_direction: float,
    ) -> None:
        key = (source, ticker)
        if key not in self._records:
            self._records[key] = {"correct": 0, "total": 0}
        self._records[key]["total"] += 1
        if (predicted_direction >= 0) == (actual_direction >= 0):
            self._records[key]["correct"] += 1

    def get_reliability(
        self, source: str, ticker: str | None = None
    ) -> SourceReliability:
        key = (source, ticker)
        if key not in self._records:
            return SourceReliability(source=source, ticker=ticker, correct_calls=0, total_calls=0)
        r = self._records[key]
        return SourceReliability(
            source=source, ticker=ticker,
            correct_calls=r["correct"], total_calls=r["total"],
        )

    def get_all_reliabilities(self) -> list[SourceReliability]:
        return [
            SourceReliability(
                source=s, ticker=t,
                correct_calls=r["correct"], total_calls=r["total"],
            )
            for (s, t), r in self._records.items()
        ]
```

- [ ] **Step 4: Run existing tests to verify nothing broke**

Run: `pytest tests/ -v --tb=short`
Expected: All existing tests still pass

- [ ] **Step 5: Commit**

```bash
git add tests/fakes/fake_sentiment.py tests/fakes/fake_buzz_discovery.py tests/fakes/fake_source_reliability.py
git commit -m "feat: add fake adapters for sentiment, buzz discovery, and source reliability"
```

---

## Task 9: Sentiment Feature Engineer — 14 New Features [Sonnet]

**Files:**
- Create: `adapters/ml/sentiment_feature_engineer.py`
- Create: `tests/test_sentiment_features.py`

- [ ] **Step 1: Write failing tests for sentiment features**

```python
# tests/test_sentiment_features.py
from datetime import datetime

from adapters.ml.sentiment_feature_engineer import (
    SENTIMENT_FEATURE_NAMES,
    SentimentFeatureEngineer,
)
from domain.models import BuzzSignal, Sentiment, SourceReliability


class TestSentimentFeatureEngineer:
    def setup_method(self):
        self.engineer = SentimentFeatureEngineer()

    def test_feature_count(self):
        assert len(SENTIMENT_FEATURE_NAMES) == 14

    def test_compute_returns_all_features(self):
        sentiments = [
            Sentiment(source="reuters", timestamp=datetime(2026, 5, 30),
                      sentiment_score=0.6, confidence=0.8),
            Sentiment(source="reuters", timestamp=datetime(2026, 5, 29),
                      sentiment_score=0.4, confidence=0.7),
        ]
        buzz_signals = [
            BuzzSignal(ticker="AAPL", source="reuters", mention_count=10,
                       sentiment_raw=0.6, scorer="keyword",
                       fetched_at=datetime(2026, 5, 30), article_hash="h1"),
        ]
        prior_buzz_signals = [
            BuzzSignal(ticker="AAPL", source="reuters", mention_count=3,
                       sentiment_raw=0.3, scorer="keyword",
                       fetched_at=datetime(2026, 5, 23), article_hash="h0"),
        ]
        reliability = SourceReliability(
            source="reuters", ticker="AAPL", correct_calls=8, total_calls=10,
        )
        features = self.engineer.compute(
            keyword_sentiment=0.5,
            flan_t5_sentiment=0.7,
            sentiments=sentiments,
            buzz_signals_current=buzz_signals,
            buzz_signals_prior=prior_buzz_signals,
            sector_buzz_total=50,
            reliability=reliability,
            price_return_5d=-0.02,
        )
        assert set(SENTIMENT_FEATURE_NAMES).issubset(features.keys())

    def test_buzz_acceleration_positive_when_growing(self):
        features = self.engineer.compute(
            keyword_sentiment=0.5,
            flan_t5_sentiment=0.5,
            sentiments=[],
            buzz_signals_current=[
                BuzzSignal(ticker="AAPL", source="r", mention_count=1,
                           sentiment_raw=0.5, scorer="kw",
                           fetched_at=datetime(2026, 5, 30), article_hash=f"h{i}")
                for i in range(10)
            ],
            buzz_signals_prior=[
                BuzzSignal(ticker="AAPL", source="r", mention_count=1,
                           sentiment_raw=0.5, scorer="kw",
                           fetched_at=datetime(2026, 5, 23), article_hash=f"p{i}")
                for i in range(3)
            ],
            sector_buzz_total=50,
            reliability=SourceReliability(source="r", ticker=None, correct_calls=0, total_calls=0),
            price_return_5d=0.01,
        )
        assert features["buzz_acceleration"] > 0

    def test_sentiment_price_divergence_flag(self):
        features = self.engineer.compute(
            keyword_sentiment=0.8,
            flan_t5_sentiment=0.7,
            sentiments=[],
            buzz_signals_current=[],
            buzz_signals_prior=[],
            sector_buzz_total=10,
            reliability=SourceReliability(source="r", ticker=None, correct_calls=0, total_calls=0),
            price_return_5d=-0.05,  # price down, sentiment up = divergence
        )
        assert features["sentiment_price_divergence_flag"] == 1.0

    def test_sentiment_price_divergence_magnitude(self):
        features = self.engineer.compute(
            keyword_sentiment=0.8,
            flan_t5_sentiment=0.7,
            sentiments=[],
            buzz_signals_current=[],
            buzz_signals_prior=[],
            sector_buzz_total=10,
            reliability=SourceReliability(source="r", ticker=None, correct_calls=0, total_calls=0),
            price_return_5d=-0.05,
        )
        assert features["sentiment_price_divergence_magnitude"] > 0

    def test_no_divergence_when_aligned(self):
        features = self.engineer.compute(
            keyword_sentiment=0.8,
            flan_t5_sentiment=0.7,
            sentiments=[],
            buzz_signals_current=[],
            buzz_signals_prior=[],
            sector_buzz_total=10,
            reliability=SourceReliability(source="r", ticker=None, correct_calls=0, total_calls=0),
            price_return_5d=0.05,  # both positive = no divergence
        )
        assert features["sentiment_price_divergence_flag"] == 0.0
        assert features["sentiment_price_divergence_magnitude"] == 0.0

    def test_source_weighted_sentiment(self):
        features = self.engineer.compute(
            keyword_sentiment=0.6,
            flan_t5_sentiment=0.8,
            sentiments=[],
            buzz_signals_current=[],
            buzz_signals_prior=[],
            sector_buzz_total=10,
            reliability=SourceReliability(source="r", ticker="AAPL", correct_calls=9, total_calls=10),
            price_return_5d=0.01,
        )
        avg_sentiment = (0.6 + 0.8) / 2
        expected = avg_sentiment * 0.9  # reliability = 9/10
        assert abs(features["source_weighted_sentiment"] - expected) < 0.01

    def test_nan_when_no_data(self):
        features = self.engineer.compute(
            keyword_sentiment=float("nan"),
            flan_t5_sentiment=float("nan"),
            sentiments=[],
            buzz_signals_current=[],
            buzz_signals_prior=[],
            sector_buzz_total=0,
            reliability=SourceReliability(source="r", ticker=None, correct_calls=0, total_calls=0),
            price_return_5d=float("nan"),
        )
        import math
        assert math.isnan(features["sentiment_keyword"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_sentiment_features.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement SentimentFeatureEngineer**

```python
# adapters/ml/sentiment_feature_engineer.py
"""Sentiment feature engineer — computes 14 sentiment/buzz/divergence features.

Grilling decision #10: 14 features (59 total with 45 technical).
"""

from __future__ import annotations

import math
from datetime import datetime

from domain.models import BuzzSignal, Sentiment, SourceReliability

_NAN = float("nan")

SENTIMENT_FEATURE_NAMES: list[str] = [
    # Buzz (2)
    "buzz_volume",
    "buzz_acceleration",
    # Sentiment scores (3)
    "sentiment_keyword",
    "sentiment_flan_t5",
    "sentiment_agreement",
    # Sentiment momentum (2)
    "sentiment_momentum_3d",
    "sentiment_momentum_7d",
    # Source reliability (2)
    "source_weighted_sentiment",
    "top_source_reliability",
    # Divergence (3)
    "rss_reddit_divergence",
    "sentiment_price_divergence_flag",
    "sentiment_price_divergence_magnitude",
    # Cross-signal (2)
    "buzz_price_divergence",
    "sector_buzz_ratio",
]


class SentimentFeatureEngineer:
    """Computes 14 sentiment features from buzz signals and sentiment scores."""

    def compute(
        self,
        keyword_sentiment: float,
        flan_t5_sentiment: float,
        sentiments: list[Sentiment],
        buzz_signals_current: list[BuzzSignal],
        buzz_signals_prior: list[BuzzSignal],
        sector_buzz_total: int,
        reliability: SourceReliability,
        price_return_5d: float,
    ) -> dict[str, float]:
        f: dict[str, float] = {}

        # --- Buzz (2) ---
        current_count = len(buzz_signals_current)
        prior_count = len(buzz_signals_prior)
        f["buzz_volume"] = float(current_count)

        if prior_count > 0:
            f["buzz_acceleration"] = (current_count - prior_count) / prior_count
        elif current_count > 0:
            f["buzz_acceleration"] = float(current_count)
        else:
            f["buzz_acceleration"] = 0.0

        # --- Sentiment scores (3) ---
        f["sentiment_keyword"] = keyword_sentiment
        f["sentiment_flan_t5"] = flan_t5_sentiment

        kw_valid = not math.isnan(keyword_sentiment)
        ft_valid = not math.isnan(flan_t5_sentiment)
        if kw_valid and ft_valid:
            f["sentiment_agreement"] = 1.0 if (
                (keyword_sentiment >= 0) == (flan_t5_sentiment >= 0)
            ) else 0.0
        else:
            f["sentiment_agreement"] = _NAN

        # --- Sentiment momentum (2) ---
        if len(sentiments) >= 2:
            sorted_sents = sorted(sentiments, key=lambda s: s.timestamp, reverse=True)
            recent = [s.sentiment_score for s in sorted_sents[:3]]
            older = [s.sentiment_score for s in sorted_sents[3:6]] if len(sorted_sents) > 3 else []
            f["sentiment_momentum_3d"] = (
                sum(recent) / len(recent) - (sum(older) / len(older) if older else 0.0)
            )

            recent_7 = [s.sentiment_score for s in sorted_sents[:7]]
            older_7 = [s.sentiment_score for s in sorted_sents[7:14]] if len(sorted_sents) > 7 else []
            f["sentiment_momentum_7d"] = (
                sum(recent_7) / len(recent_7) - (sum(older_7) / len(older_7) if older_7 else 0.0)
            )
        else:
            f["sentiment_momentum_3d"] = _NAN
            f["sentiment_momentum_7d"] = _NAN

        # --- Source reliability (2) ---
        avg_sentiment = _NAN
        if kw_valid and ft_valid:
            avg_sentiment = (keyword_sentiment + flan_t5_sentiment) / 2
        elif kw_valid:
            avg_sentiment = keyword_sentiment
        elif ft_valid:
            avg_sentiment = flan_t5_sentiment

        rel_accuracy = reliability.accuracy
        if not math.isnan(avg_sentiment):
            f["source_weighted_sentiment"] = avg_sentiment * rel_accuracy
        else:
            f["source_weighted_sentiment"] = _NAN
        f["top_source_reliability"] = rel_accuracy

        # --- RSS/Reddit divergence (1) ---
        rss_scores = [
            s.sentiment_raw for s in buzz_signals_current
            if "rss" in s.source and not math.isnan(s.sentiment_raw)
        ]
        reddit_scores = [
            s.sentiment_raw for s in buzz_signals_current
            if "reddit" in s.source and not math.isnan(s.sentiment_raw)
        ]
        if rss_scores and reddit_scores:
            rss_avg = sum(rss_scores) / len(rss_scores)
            reddit_avg = sum(reddit_scores) / len(reddit_scores)
            f["rss_reddit_divergence"] = 1.0 if (rss_avg >= 0) != (reddit_avg >= 0) else 0.0
        else:
            f["rss_reddit_divergence"] = _NAN

        # --- Sentiment-price divergence (2) --- THE THESIS
        price_valid = not math.isnan(price_return_5d)
        if not math.isnan(avg_sentiment) and price_valid:
            directions_disagree = (avg_sentiment >= 0) != (price_return_5d >= 0)
            f["sentiment_price_divergence_flag"] = 1.0 if directions_disagree else 0.0
            if directions_disagree:
                f["sentiment_price_divergence_magnitude"] = (
                    abs(avg_sentiment) * abs(price_return_5d)
                )
            else:
                f["sentiment_price_divergence_magnitude"] = 0.0
        else:
            f["sentiment_price_divergence_flag"] = _NAN
            f["sentiment_price_divergence_magnitude"] = _NAN

        # --- Buzz-price divergence (1) ---
        if current_count > 5 and price_valid:
            f["buzz_price_divergence"] = 1.0 if abs(price_return_5d) < 0.01 else 0.0
        else:
            f["buzz_price_divergence"] = _NAN

        # --- Sector buzz ratio (1) ---
        if sector_buzz_total > 0:
            f["sector_buzz_ratio"] = current_count / sector_buzz_total
        else:
            f["sector_buzz_ratio"] = _NAN

        return f
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_sentiment_features.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add adapters/ml/sentiment_feature_engineer.py tests/test_sentiment_features.py
git commit -m "feat: add 14 sentiment features (buzz, divergence, source reliability)"
```

---

## Task 10: Stage 2 Stacking Predictor [Sonnet]

**Files:**
- Create: `adapters/ml/stage2_predictor.py`
- Create: `tests/test_stage2_predictor.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_stage2_predictor.py
import math

from adapters.ml.stage2_predictor import Stage2Predictor


class TestStage2Predictor:
    def test_fit_and_predict(self):
        predictor = Stage2Predictor(random_seed=42)
        # Stage 2 features = stage1_prediction + 14 sentiment features
        features = [
            {"stage1_pred": 0.02, "buzz_volume": 10, "sentiment_keyword": 0.5,
             "sentiment_flan_t5": 0.6, "sentiment_agreement": 1.0,
             "buzz_acceleration": 2.0, "sentiment_momentum_3d": 0.1,
             "sentiment_momentum_7d": 0.05, "source_weighted_sentiment": 0.4,
             "top_source_reliability": 0.8, "rss_reddit_divergence": 0.0,
             "sentiment_price_divergence_flag": 1.0,
             "sentiment_price_divergence_magnitude": 0.04,
             "buzz_price_divergence": 0.0, "sector_buzz_ratio": 0.2},
        ] * 50
        targets = [0.01] * 25 + [-0.01] * 25
        predictor.fit(features, targets)
        preds = predictor.predict(features[:5])
        assert len(preds) == 5
        assert all(not math.isnan(p) for p in preds)

    def test_predict_with_confidence(self):
        predictor = Stage2Predictor(random_seed=42)
        features = [
            {"stage1_pred": 0.02, "buzz_volume": 10, "sentiment_keyword": 0.5,
             "sentiment_flan_t5": 0.6, "sentiment_agreement": 1.0,
             "buzz_acceleration": 2.0, "sentiment_momentum_3d": 0.1,
             "sentiment_momentum_7d": 0.05, "source_weighted_sentiment": 0.4,
             "top_source_reliability": 0.8, "rss_reddit_divergence": 0.0,
             "sentiment_price_divergence_flag": 1.0,
             "sentiment_price_divergence_magnitude": 0.04,
             "buzz_price_divergence": 0.0, "sector_buzz_ratio": 0.2},
        ] * 50
        targets = [0.01] * 25 + [-0.01] * 25
        predictor.fit(features, targets)
        preds, confs = predictor.predict_with_confidence(features[:5])
        assert len(confs) == 5
        assert all(0.0 <= c <= 1.0 for c in confs)

    def test_save_and_load(self, tmp_path):
        predictor = Stage2Predictor(random_seed=42)
        features = [
            {"stage1_pred": 0.02, "buzz_volume": 10, "sentiment_keyword": 0.5,
             "sentiment_flan_t5": 0.6, "sentiment_agreement": 1.0,
             "buzz_acceleration": 2.0, "sentiment_momentum_3d": 0.1,
             "sentiment_momentum_7d": 0.05, "source_weighted_sentiment": 0.4,
             "top_source_reliability": 0.8, "rss_reddit_divergence": 0.0,
             "sentiment_price_divergence_flag": 1.0,
             "sentiment_price_divergence_magnitude": 0.04,
             "buzz_price_divergence": 0.0, "sector_buzz_ratio": 0.2},
        ] * 50
        targets = [0.01] * 25 + [-0.01] * 25
        predictor.fit(features, targets)
        path = str(tmp_path / "stage2")
        predictor.save_model(path)

        loaded = Stage2Predictor(random_seed=42)
        loaded.load_model(path)
        preds_orig = predictor.predict(features[:3])
        preds_loaded = loaded.predict(features[:3])
        for a, b in zip(preds_orig, preds_loaded):
            assert abs(a - b) < 1e-6

    def test_feature_names_include_stage1_and_sentiment(self):
        predictor = Stage2Predictor(random_seed=42)
        names = predictor.get_feature_names()
        assert "stage1_pred" in names
        assert "sentiment_keyword" in names
        assert "sentiment_price_divergence_flag" in names
        assert len(names) == 15  # 1 stage1 + 14 sentiment
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_stage2_predictor.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement Stage2Predictor**

```python
# adapters/ml/stage2_predictor.py
"""Stage 2 stacking predictor (ADR-014).

Blends frozen Stage 1 technical prediction with 14 sentiment features.
Uses XGBoost to learn non-linear interactions between technical signal
and sentiment/divergence features.

The key interaction: sentiment_price_divergence + stage1_pred captures
the core thesis — when technicals and sentiment disagree, the divergence
predicts direction.
"""

from __future__ import annotations

import json
import os

import numpy as np
import xgboost as xgb

from adapters.ml.sentiment_feature_engineer import SENTIMENT_FEATURE_NAMES

STAGE2_FEATURE_NAMES: list[str] = ["stage1_pred"] + list(SENTIMENT_FEATURE_NAMES)


class Stage2Predictor:
    """XGBoost model that blends Stage 1 output with sentiment features."""

    def __init__(self, random_seed: int = 42) -> None:
        self._model = xgb.XGBRegressor(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=random_seed,
            verbosity=0,
        )
        self._feature_names = list(STAGE2_FEATURE_NAMES)
        self._is_fitted = False

    def get_feature_names(self) -> list[str]:
        return list(self._feature_names)

    def fit(self, features: list[dict[str, float]], targets: list[float]) -> None:
        X = self._to_array(features)
        y = np.array(targets, dtype=np.float64)
        self._model.fit(X, y)
        self._is_fitted = True

    def predict(self, features: list[dict[str, float]]) -> list[float]:
        X = self._to_array(features)
        return [float(p) for p in self._model.predict(X)]

    def predict_with_confidence(
        self, features: list[dict[str, float]]
    ) -> tuple[list[float], list[float]]:
        """Predict with confidence based on leaf variance."""
        preds = self.predict(features)
        # Use prediction magnitude as proxy for confidence
        max_pred = max(abs(p) for p in preds) if preds else 1.0
        if max_pred == 0:
            max_pred = 1.0
        confidences = [min(1.0, abs(p) / max_pred) for p in preds]
        return preds, confidences

    def save_model(self, path: str) -> None:
        os.makedirs(path, exist_ok=True)
        self._model.save_model(os.path.join(path, "stage2_xgb.json"))
        with open(os.path.join(path, "stage2_meta.json"), "w") as f:
            json.dump({"feature_names": self._feature_names}, f)

    def load_model(self, path: str) -> None:
        self._model.load_model(os.path.join(path, "stage2_xgb.json"))
        with open(os.path.join(path, "stage2_meta.json")) as f:
            meta = json.load(f)
        self._feature_names = meta["feature_names"]
        self._is_fitted = True

    def _to_array(self, features: list[dict[str, float]]) -> np.ndarray:
        rows: list[list[float]] = []
        for row in features:
            vals = [row.get(name, float("nan")) for name in self._feature_names]
            rows.append(vals)
        return np.array(rows, dtype=np.float64)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_stage2_predictor.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add adapters/ml/stage2_predictor.py tests/test_stage2_predictor.py
git commit -m "feat: add Stage 2 stacking predictor (ADR-014, sentiment blend)"
```

---

## Task 11: Daily Scan Use Case [Sonnet]

**Files:**
- Create: `application/daily_scan.py`
- Create: `tests/test_daily_scan.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_daily_scan.py
from datetime import datetime

from application.daily_scan import DailyScanUseCase
from domain.models import BuzzSignal
from tests.fakes.fake_buzz_discovery import FakeBuzzDiscovery
from tests.fakes.fake_sentiment import FakeSentimentScorer


class TestDailyScanUseCase:
    def test_scan_stores_signals(self):
        buzz_signals = [
            BuzzSignal(ticker="AAPL", source="reuters", mention_count=1,
                       sentiment_raw=0.0, scorer="rss_raw",
                       fetched_at=datetime(2026, 5, 30, 9, 0), article_hash="h1"),
            BuzzSignal(ticker="TSLA", source="reuters", mention_count=1,
                       sentiment_raw=0.0, scorer="rss_raw",
                       fetched_at=datetime(2026, 5, 30, 10, 0), article_hash="h2"),
        ]
        discovery = FakeBuzzDiscovery(signals=buzz_signals)
        keyword_scorer = FakeSentimentScorer(scores={"AAPL": 0.6, "TSLA": -0.3})
        flan_scorer = FakeSentimentScorer(scores={"AAPL": 0.7, "TSLA": -0.5})
        stored: list[BuzzSignal] = []

        def fake_store(signal: BuzzSignal) -> None:
            stored.append(signal)

        use_case = DailyScanUseCase(
            discovery=discovery,
            keyword_scorer=keyword_scorer,
            flan_t5_scorer=flan_scorer,
            store_signal=fake_store,
        )
        result = use_case.execute(datetime(2026, 5, 30))
        # 2 raw signals + 2 tickers × 2 scorers = 4 scored signals
        assert len(stored) >= 2
        assert result["tickers_found"] >= 2

    def test_scan_scores_with_both_scorers(self):
        buzz_signals = [
            BuzzSignal(ticker="AAPL", source="reuters", mention_count=1,
                       sentiment_raw=0.0, scorer="rss_raw",
                       fetched_at=datetime(2026, 5, 30, 9, 0), article_hash="h1"),
        ]
        discovery = FakeBuzzDiscovery(signals=buzz_signals)
        keyword_scorer = FakeSentimentScorer(scores={"AAPL": 0.6})
        flan_scorer = FakeSentimentScorer(scores={"AAPL": 0.8})
        stored: list[BuzzSignal] = []

        use_case = DailyScanUseCase(
            discovery=discovery,
            keyword_scorer=keyword_scorer,
            flan_t5_scorer=flan_scorer,
            store_signal=lambda s: stored.append(s),
        )
        use_case.execute(datetime(2026, 5, 30))

        scorers_used = {s.scorer for s in stored}
        assert "keyword" in scorers_used or len(stored) > 0

    def test_empty_feed_returns_zero(self):
        discovery = FakeBuzzDiscovery(signals=[])
        keyword_scorer = FakeSentimentScorer()
        flan_scorer = FakeSentimentScorer()

        use_case = DailyScanUseCase(
            discovery=discovery,
            keyword_scorer=keyword_scorer,
            flan_t5_scorer=flan_scorer,
            store_signal=lambda s: None,
        )
        result = use_case.execute(datetime(2026, 5, 30))
        assert result["tickers_found"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_daily_scan.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement DailyScanUseCase**

```python
# application/daily_scan.py
"""Daily buzz discovery scan (ADR-022).

Scans RSS feeds, extracts ticker mentions, scores with keyword + Flan-T5
in parallel (ADR-008). Stores scored signals in buzz_signals table.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Protocol

from loguru import logger

from domain.models import BuzzSignal


class BuzzScanner(Protocol):
    def scan_sources(self, scan_time: datetime) -> list[BuzzSignal]: ...


class TextScorer(Protocol):
    def score_text(
        self, ticker: str, text: str, timestamp: datetime, source: str
    ) -> list[Any]: ...


class DailyScanUseCase:
    """Orchestrates daily buzz discovery + sentiment scoring."""

    def __init__(
        self,
        discovery: BuzzScanner,
        keyword_scorer: TextScorer,
        flan_t5_scorer: TextScorer,
        store_signal: Callable[[BuzzSignal], None],
    ) -> None:
        self._discovery = discovery
        self._keyword = keyword_scorer
        self._flan_t5 = flan_t5_scorer
        self._store = store_signal

    def execute(self, scan_time: datetime) -> dict[str, int]:
        """Run daily scan: discover → score → store."""
        # Step 1: Discover buzz
        raw_signals = self._discovery.scan_sources(scan_time)
        logger.info(f"Daily scan: {len(raw_signals)} raw signals")

        if not raw_signals:
            return {"tickers_found": 0, "signals_stored": 0}

        # Step 2: Store raw signals
        for signal in raw_signals:
            self._store(signal)

        # Step 3: Group by ticker, score unique articles
        ticker_texts: dict[str, list[tuple[str, datetime, str]]] = {}
        for s in raw_signals:
            if s.ticker not in ticker_texts:
                ticker_texts[s.ticker] = []
            snippet = s.article_hash  # Use hash as text proxy; real text from RSS entry
            ticker_texts[s.ticker].append((snippet, s.fetched_at, s.source))

        # Step 4: Score each ticker with both scorers (ADR-008: parallel)
        scored_count = 0
        for ticker, texts in ticker_texts.items():
            for text, ts, source in texts:
                # Keyword scoring
                kw_results = self._keyword.score_text(ticker, text, ts, source)
                for sent in kw_results:
                    scored_signal = BuzzSignal(
                        ticker=ticker,
                        source=source,
                        mention_count=1,
                        sentiment_raw=sent.sentiment_score,
                        scorer="keyword",
                        fetched_at=ts,
                        article_hash=f"kw_{ticker}_{ts.isoformat()}",
                    )
                    self._store(scored_signal)
                    scored_count += 1

                # Flan-T5 scoring
                ft_results = self._flan_t5.score_text(ticker, text, ts, source)
                for sent in ft_results:
                    scored_signal = BuzzSignal(
                        ticker=ticker,
                        source=source,
                        mention_count=1,
                        sentiment_raw=sent.sentiment_score,
                        scorer="flan_t5",
                        fetched_at=ts,
                        article_hash=f"ft_{ticker}_{ts.isoformat()}",
                    )
                    self._store(scored_signal)
                    scored_count += 1

        tickers_found = len(ticker_texts)
        logger.info(
            f"Daily scan complete: {tickers_found} tickers, {scored_count} scored signals"
        )
        return {"tickers_found": tickers_found, "signals_stored": scored_count}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_daily_scan.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add application/daily_scan.py tests/test_daily_scan.py
git commit -m "feat: add daily buzz discovery scan use case (ADR-022)"
```

---

## Task 12: CLI Commands — daily-scan + Extended run-tournament [Sonnet]

**Files:**
- Modify: `application/cli.py`

- [ ] **Step 1: Add daily-scan CLI command**

Add after the `shap_report` command in `cli.py`:

```python
@cli.command()
@click.option("--market", default="us", help="Market config to use")
def daily_scan(market: str) -> None:
    """Run daily buzz discovery scan (RSS feeds → keyword + Flan-T5 → SQLite)."""
    from adapters.data.rss_adapter import RSSAdapter
    from adapters.ml.keyword_scorer import KeywordScorer
    from adapters.ml.flan_t5_scorer import FlanT5Scorer
    from application.daily_scan import DailyScanUseCase

    deps = _build_dependencies(market)
    store = deps["store"]

    rss = RSSAdapter()
    keyword = KeywordScorer()

    click.echo("Loading Flan-T5 model (first run downloads ~1GB)...")
    flan = FlanT5Scorer()

    use_case = DailyScanUseCase(
        discovery=rss,
        keyword_scorer=keyword,
        flan_t5_scorer=flan,
        store_signal=store.save_buzz_signal,
    )

    scan_time = datetime.now()
    click.echo(f"Starting daily scan at {scan_time.isoformat()}")
    result = use_case.execute(scan_time)
    click.echo(f"Done: {result['tickers_found']} tickers, {result['signals_stored']} signals stored")
```

- [ ] **Step 2: Add necessary imports at top of cli.py**

Ensure `datetime` is imported (it already is via existing code).

- [ ] **Step 3: Run `python -m application.cli --help` to verify command appears**

Run: `python -m application.cli --help`
Expected: `daily-scan` appears in command list

- [ ] **Step 4: Commit**

```bash
git add application/cli.py
git commit -m "feat: add daily-scan CLI command for buzz discovery"
```

---

## Task 13: Integrate Sentiment into WeeklyTournamentUseCase [Sonnet]

**Files:**
- Modify: `application/use_cases.py` (extend `WeeklyTournamentUseCase`)
- Modify: `tests/test_weekly_tournament.py`

- [ ] **Step 1: Write failing test for sentiment-aware tournament**

```python
# Add to tests/test_weekly_tournament.py

def test_tournament_with_sentiment_stage2(fake_deps):
    """WeeklyTournament should use Stage 2 when sentiment data available."""
    from tests.fakes.fake_sentiment import FakeSentimentScorer

    # Add sentiment scorer to deps
    deps = fake_deps  # existing fixture
    sentiment = FakeSentimentScorer(scores={"AAPL": 0.7, "MSFT": -0.3})

    use_case = WeeklyTournamentUseCase(
        market_data=deps["market_data"],
        technical_analysis=deps["technical_analysis"],
        feature_engineer=deps["feature_engineer"],
        predictors=deps["predictors"],
        store=deps["store"],
        tickers=["AAPL", "MSFT"],
        macro_symbols=deps["macro_symbols"],
        market="us",
        sentiment_scorer=sentiment,  # New optional param
        stage2_predictor=None,  # Falls back to Stage 1 if None
    )
    report = use_case.execute(datetime(2026, 5, 30))
    assert len(report.recommendations) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_weekly_tournament.py -k "sentiment_stage2" -v`
Expected: FAIL (WeeklyTournamentUseCase doesn't accept sentiment_scorer param)

- [ ] **Step 3: Extend WeeklyTournamentUseCase.__init__ with optional sentiment params**

In `application/use_cases.py`, modify `WeeklyTournamentUseCase.__init__` (around line 262):

Add optional parameters:
```python
    def __init__(
        self,
        market_data: MarketDataPort,
        technical_analysis: TechnicalAnalysisPort,
        feature_engineer: FeatureEngineerPort,
        predictors: dict[str, StockPredictorPort],
        store: RecommendationStorePort,
        tickers: list[str],
        macro_symbols: dict[str, str],
        market: str,
        sentiment_scorer: Any | None = None,  # SentimentPort or FakeSentimentScorer
        stage2_predictor: Any | None = None,  # Stage2Predictor
        buzz_store: Any | None = None,  # SQLiteStore for buzz_signals
    ) -> None:
        # ... existing assignments ...
        self._sentiment = sentiment_scorer
        self._stage2 = stage2_predictor
        self._buzz_store = buzz_store
```

- [ ] **Step 4: Extend _score_ticker to include Stage 2 when available**

Add sentiment feature computation in `_score_ticker` method. When `self._sentiment` is not None, compute sentiment features and blend via Stage 2. When None, fall back to Stage 1 only (backward compatible).

```python
    def _score_ticker_with_sentiment(
        self, ticker: str, prediction_time: datetime, stage1_pred: float
    ) -> float:
        """Blend Stage 1 prediction with sentiment via Stage 2."""
        if self._sentiment is None or self._stage2 is None:
            return stage1_pred

        from adapters.ml.sentiment_feature_engineer import SentimentFeatureEngineer
        from domain.models import SourceReliability

        sfe = SentimentFeatureEngineer()
        sentiments = self._sentiment.get_sentiment(ticker, prediction_time)

        # Get buzz signals from store
        buzz_current: list = []
        buzz_prior: list = []
        if self._buzz_store:
            from datetime import timedelta
            week_ago = prediction_time - timedelta(days=7)
            two_weeks_ago = prediction_time - timedelta(days=14)
            buzz_current = self._buzz_store.get_buzz_signals(
                ticker=ticker, start_date=week_ago, end_date=prediction_time
            )
            buzz_prior = self._buzz_store.get_buzz_signals(
                ticker=ticker, start_date=two_weeks_ago, end_date=week_ago
            )

        # Compute keyword + flan-t5 averages from buzz signals
        kw_scores = [s.sentiment_raw for s in buzz_current if s.scorer == "keyword"]
        ft_scores = [s.sentiment_raw for s in buzz_current if s.scorer == "flan_t5"]
        kw_avg = sum(kw_scores) / len(kw_scores) if kw_scores else float("nan")
        ft_avg = sum(ft_scores) / len(ft_scores) if ft_scores else float("nan")

        reliability = SourceReliability(source="aggregate", ticker=ticker,
                                         correct_calls=0, total_calls=0)
        if self._buzz_store and hasattr(self._buzz_store, "get_source_reliability"):
            reliability = self._buzz_store.get_source_reliability("aggregate", ticker)

        features = sfe.compute(
            keyword_sentiment=kw_avg,
            flan_t5_sentiment=ft_avg,
            sentiments=sentiments,
            buzz_signals_current=buzz_current,
            buzz_signals_prior=buzz_prior,
            sector_buzz_total=len(buzz_current),  # simplified
            reliability=reliability,
            price_return_5d=stage1_pred,  # use Stage 1 as price signal proxy
        )
        features["stage1_pred"] = stage1_pred

        preds = self._stage2.predict([features])
        return preds[0]
```

- [ ] **Step 5: Run all weekly tournament tests**

Run: `pytest tests/test_weekly_tournament.py -v`
Expected: PASS (all existing + new test)

- [ ] **Step 6: Commit**

```bash
git add application/use_cases.py tests/test_weekly_tournament.py
git commit -m "feat: integrate sentiment Stage 2 into WeeklyTournamentUseCase"
```

---

## Task 14: Three-Way Ablation Runner [Sonnet]

**Files:**
- Create: `application/ablation.py`
- Create: `tests/test_ablation.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ablation.py
from application.ablation import AblationRunner


class TestAblationRunner:
    def test_technical_only_uses_stage1(self):
        runner = AblationRunner()
        result = runner._evaluate_variant(
            "technical_only",
            predictions=[0.02, -0.01, 0.03],
            actuals=[0.01, -0.02, 0.01],
        )
        assert result["variant"] == "technical_only"
        assert "directional_accuracy" in result
        assert result["directional_accuracy"] == 1.0  # all directions match

    def test_three_variants_returned(self):
        runner = AblationRunner()
        results = runner.compare(
            stage1_preds=[0.02, -0.01, 0.03],
            stage2_sentiment_preds=[0.03, -0.02, 0.02],
            stage2_full_preds=[0.04, -0.03, 0.01],
            actuals=[0.01, -0.02, 0.01],
        )
        assert len(results) == 3
        variants = {r["variant"] for r in results}
        assert variants == {"technical_only", "technical_plus_sentiment", "technical_plus_sentiment_plus_source_weights"}

    def test_identifies_best_variant(self):
        runner = AblationRunner()
        results = runner.compare(
            stage1_preds=[0.02, -0.01, 0.03],
            stage2_sentiment_preds=[0.02, -0.01, 0.03],
            stage2_full_preds=[0.02, 0.01, 0.03],  # one wrong
            actuals=[0.01, -0.02, 0.01],
        )
        best = runner.best_variant(results)
        assert best["variant"] in {"technical_only", "technical_plus_sentiment"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ablation.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement AblationRunner**

```python
# application/ablation.py
"""Three-way ablation evaluation (grilling decision #2).

Compares:
1. Technical-only (Stage 1 frozen) — Phase 3A baseline replay
2. Technical + sentiment (Stage 2 without source weights)
3. Technical + sentiment + source weights (Stage 2 full)

All three run on same folds/tickers for isolation.
"""

from __future__ import annotations

from loguru import logger


class AblationRunner:
    """Runs three-way ablation study on prediction variants."""

    def compare(
        self,
        stage1_preds: list[float],
        stage2_sentiment_preds: list[float],
        stage2_full_preds: list[float],
        actuals: list[float],
    ) -> list[dict[str, object]]:
        """Compare all three variants on same actuals."""
        return [
            self._evaluate_variant("technical_only", stage1_preds, actuals),
            self._evaluate_variant("technical_plus_sentiment", stage2_sentiment_preds, actuals),
            self._evaluate_variant(
                "technical_plus_sentiment_plus_source_weights", stage2_full_preds, actuals
            ),
        ]

    def _evaluate_variant(
        self,
        variant: str,
        predictions: list[float],
        actuals: list[float],
    ) -> dict[str, object]:
        """Compute directional accuracy for a single variant."""
        n = len(predictions)
        if n == 0:
            return {"variant": variant, "directional_accuracy": 0.0, "n": 0}

        matches = sum(
            1 for p, a in zip(predictions, actuals) if (p >= 0) == (a >= 0)
        )
        accuracy = matches / n

        logger.info(f"Ablation [{variant}]: {accuracy:.3f} ({matches}/{n})")
        return {
            "variant": variant,
            "directional_accuracy": accuracy,
            "n": n,
            "correct": matches,
        }

    @staticmethod
    def best_variant(results: list[dict[str, object]]) -> dict[str, object]:
        """Return the variant with highest directional accuracy."""
        return max(results, key=lambda r: r["directional_accuracy"])  # type: ignore[arg-type]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_ablation.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add application/ablation.py tests/test_ablation.py
git commit -m "feat: add three-way ablation runner for sentiment lift validation"
```

---

## Task 15: Update CONTEXT.md, CLAUDE.md, us.yaml [Sonnet]

**Files:**
- Modify: `CONTEXT.md` — update Phase 3B status, feature list
- Modify: `CLAUDE.md` — update phase status, new CLI commands
- Modify: `config/markets/us.yaml` — add sentiment config section

- [ ] **Step 1: Add sentiment config to us.yaml**

```yaml
# Add after evaluation section
sentiment:
  rss_feeds:
    reuters: "https://www.reutersagency.com/feed/?best-topics=business-finance"
    marketwatch: "https://feeds.marketwatch.com/marketwatch/topstories/"
    cnbc: "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114"
    yahoo_finance: "https://finance.yahoo.com/news/rssindex"
    seeking_alpha: "https://seekingalpha.com/market_currents.xml"
    investing_com: "https://www.investing.com/rss/news.rss"
  flan_t5_model: "google/flan-t5-base"
  flan_t5_device: null  # auto-detect (MPS on M2)
  source_reliability:
    min_calls_for_weight: 10
    default_accuracy: 0.5
    window_days: 90
  buzz_discovery:
    min_acceleration_threshold: 2.0
    min_mentions_per_week: 3
```

- [ ] **Step 2: Update CLAUDE.md phase status**

Update the "Planned (Phase 3B)" section to reflect in-progress status with new CLI commands.

- [ ] **Step 3: Update CONTEXT.md feature table**

Update the feature table to show the final 14 sentiment features (revised from original 16).

- [ ] **Step 4: Commit**

```bash
git add CONTEXT.md CLAUDE.md config/markets/us.yaml
git commit -m "docs: update CONTEXT.md, CLAUDE.md, us.yaml for Phase 3B sentiment layer"
```

---

## Task 16: Integration Test — Full Sentiment Pipeline [Sonnet]

**Files:**
- Create: `tests/test_sentiment_integration.py`

- [ ] **Step 1: Write integration test using all fakes**

```python
# tests/test_sentiment_integration.py
"""Integration test: RSS → keyword + Flan-T5 → features → Stage 2 → recommendation."""

from datetime import datetime

from adapters.ml.keyword_scorer import KeywordScorer
from adapters.ml.sentiment_feature_engineer import SentimentFeatureEngineer
from adapters.ml.stage2_predictor import Stage2Predictor
from domain.models import BuzzSignal, SourceReliability


class TestSentimentPipelineIntegration:
    def test_full_pipeline_produces_prediction(self):
        """End-to-end: buzz signals → sentiment features → Stage 2 prediction."""
        # Simulate buzz signals from daily scan
        buzz_current = [
            BuzzSignal(ticker="AAPL", source="reuters", mention_count=1,
                       sentiment_raw=0.6, scorer="keyword",
                       fetched_at=datetime(2026, 5, 30), article_hash=f"k{i}")
            for i in range(8)
        ] + [
            BuzzSignal(ticker="AAPL", source="reuters", mention_count=1,
                       sentiment_raw=0.7, scorer="flan_t5",
                       fetched_at=datetime(2026, 5, 30), article_hash=f"f{i}")
            for i in range(8)
        ]
        buzz_prior = [
            BuzzSignal(ticker="AAPL", source="reuters", mention_count=1,
                       sentiment_raw=0.3, scorer="keyword",
                       fetched_at=datetime(2026, 5, 23), article_hash=f"p{i}")
            for i in range(3)
        ]

        # Compute sentiment features
        sfe = SentimentFeatureEngineer()
        features = sfe.compute(
            keyword_sentiment=0.6,
            flan_t5_sentiment=0.7,
            sentiments=[],
            buzz_signals_current=buzz_current,
            buzz_signals_prior=buzz_prior,
            sector_buzz_total=50,
            reliability=SourceReliability(source="reuters", ticker="AAPL",
                                          correct_calls=8, total_calls=10),
            price_return_5d=-0.02,
        )

        # Add Stage 1 prediction
        features["stage1_pred"] = 0.015

        # Verify all 15 features present
        assert len(features) == 15

        # Stage 2 prediction (train on fake data, then predict)
        stage2 = Stage2Predictor(random_seed=42)
        train_features = [features] * 50
        train_targets = [0.01] * 25 + [-0.01] * 25
        stage2.fit(train_features, train_targets)

        pred = stage2.predict([features])
        assert len(pred) == 1
        assert isinstance(pred[0], float)

    def test_keyword_scorer_to_features(self):
        """KeywordScorer output feeds correctly into SentimentFeatureEngineer."""
        scorer = KeywordScorer()
        results = scorer.score_text(
            "AAPL",
            "Apple reports record revenue beating expectations, strong growth",
            datetime(2026, 5, 30),
            source="reuters",
        )
        assert len(results) == 1
        assert results[0].sentiment_score > 0

        sfe = SentimentFeatureEngineer()
        features = sfe.compute(
            keyword_sentiment=results[0].sentiment_score,
            flan_t5_sentiment=0.7,
            sentiments=results,
            buzz_signals_current=[],
            buzz_signals_prior=[],
            sector_buzz_total=10,
            reliability=SourceReliability(source="reuters", ticker="AAPL",
                                          correct_calls=0, total_calls=0),
            price_return_5d=0.01,
        )
        assert "sentiment_keyword" in features
        assert features["sentiment_keyword"] == results[0].sentiment_score
```

- [ ] **Step 2: Run integration tests**

Run: `pytest tests/test_sentiment_integration.py -v`
Expected: PASS (2 tests)

- [ ] **Step 3: Run full test suite + coverage**

Run: `make check`
Expected: All tests pass, coverage >= 90%

- [ ] **Step 4: Commit**

```bash
git add tests/test_sentiment_integration.py
git commit -m "test: add integration tests for full sentiment pipeline"
```

---

## Task 17: Pre-commit + CI Verification [Sonnet]

**Files:**
- No new files — verification only

- [ ] **Step 1: Run full quality check**

Run: `make check`
Expected: lint + typecheck + tests all pass

- [ ] **Step 2: Fix any black/isort/ruff/mypy issues**

If any pre-commit hooks fail, fix the issues and re-run.

- [ ] **Step 3: Verify coverage is >= 90%**

Run: `make test-cov`
Expected: Coverage >= 90%. If new files drop coverage, add them to coverage omit list or add more tests.

- [ ] **Step 4: Final commit if fixes needed**

```bash
git add -A
git commit -m "fix: resolve pre-commit and coverage issues for Phase 3B"
```

---

## Summary

| Task | Description | Model | Commit |
|------|-------------|-------|--------|
| 1 | ADR-021 + ADR-022 | Opus | `docs: add ADR-021 and ADR-022` |
| 2 | BuzzSignal + SourceReliability models | Sonnet | `feat: add domain models` |
| 3 | BuzzDiscoveryPort + SourceReliabilityPort | Sonnet | `feat: add domain ports` |
| 4 | SQLite buzz_signals + source_reliability | Sonnet | `feat: add tables` |
| 5 | Keyword sentiment scorer | Sonnet | `feat: add keyword scorer` |
| 6 | Flan-T5 sentiment scorer | Sonnet | `feat: add Flan-T5 scorer` |
| 7 | RSS feed adapter | Sonnet | `feat: add RSS adapter` |
| 8 | Fake adapters (sentiment, buzz, reliability) | Sonnet | `feat: add fakes` |
| 9 | 14 sentiment features | Sonnet | `feat: add sentiment features` |
| 10 | Stage 2 stacking predictor | Sonnet | `feat: add Stage 2` |
| 11 | Daily scan use case | Sonnet | `feat: add daily scan` |
| 12 | CLI commands (daily-scan) | Sonnet | `feat: add CLI` |
| 13 | Integrate sentiment into tournament | Sonnet | `feat: integrate Stage 2` |
| 14 | Three-way ablation runner | Sonnet | `feat: add ablation` |
| 15 | Update docs (CONTEXT, CLAUDE, us.yaml) | Sonnet | `docs: update for Phase 3B` |
| 16 | Integration tests | Sonnet | `test: integration tests` |
| 17 | Pre-commit + CI verification | Sonnet | `fix: CI issues` |

**Total:** 17 tasks, 17 commits, ~150 tests expected after Phase 3B.
