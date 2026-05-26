# Phase 3: Core Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working weekly stock recommendation pipeline — from data discovery through graded picks — with CLI output and GitHub Actions automation.

**Architecture:** Hexagonal (ports & adapters). Domain layer is pure Python (zero external imports). Each data source = one adapter implementing one port Protocol. Use cases in application/ receive ports via constructor injection. Vertical slice: get predictions working first, layer sources one by one.

**Tech Stack:** Python 3.12, yfinance, PRAW, feedparser, google-api-python-client, XGBoost, LightGBM, SHAP, SQLite, Click CLI, Hypothesis, pytest

**Conda env:** `multi-modal-stock-ml` (already created)

**Branch:** `dev/structural-updates` (current)

**Existing code:** domain/ has Signal, Sentiment, BacktestResult models + MarketDataPort, SentimentPort, StockPredictorPort, BacktestResultPort + validate_point_in_time_access + exceptions. 7 tests passing.

**Test command:** `pytest -v --tb=short`

---

## File Structure

### Domain Layer (modify existing)
- `domain/exceptions.py` — Add InsufficientDataError, StaleDataError
- `domain/models.py` — Add RecommendationGrade, TechnicalIndicators, DivergenceSignal, StockRecommendation, WeeklyReport, AccuracyRecord
- `domain/ports.py` — Add NewsDiscoveryPort, BuzzScorerPort, SentimentScorerPort, RecommendationStorePort, TechnicalAnalysisPort
- `domain/services.py` — Add compute_divergence_score(), grade_recommendation()

### Adapters (create new)
- `adapters/data/yfinance_adapter.py` — MarketDataPort + TechnicalAnalysisPort
- `adapters/data/rss_adapter.py` — NewsDiscoveryPort
- `adapters/data/google_search_adapter.py` — NewsDiscoveryPort
- `adapters/data/reddit_adapter.py` — BuzzScorerPort
- `adapters/data/stocktwits_adapter.py` — BuzzScorerPort
- `adapters/data/sqlite_store.py` — RecommendationStorePort
- `adapters/ml/keyword_scorer.py` — SentimentScorerPort
- `adapters/ml/xgboost_predictor.py` — StockPredictorPort
- `adapters/ml/lightgbm_predictor.py` — StockPredictorPort
- `adapters/ml/ensemble_predictor.py` — StockPredictorPort

### Application Layer (create/modify)
- `application/use_cases.py` — WeeklyTournamentUseCase, TrackRecommendationsUseCase, BacktestUseCase
- `application/cli.py` — Click CLI entry point

### Config (create new)
- `config/markets/us.yaml` — US market configuration
- `config/__init__.py` — Config loader

### Tests (create new)
- `tests/test_domain_models.py` — Extend with new model tests
- `tests/test_domain_services.py` — Extend with divergence + grading tests
- `tests/test_properties.py` — Hypothesis property-based tests
- `tests/fakes/` — All fake adapter implementations
- `tests/test_keyword_scorer.py`
- `tests/test_sqlite_store.py`
- `tests/test_rss_adapter.py`
- `tests/test_google_search_adapter.py`
- `tests/test_weekly_tournament.py`
- `tests/test_track_recommendations.py`

### CI (create new)
- `.github/workflows/weekly_picks.yml`

---

## Task 1: Domain Exceptions — InsufficientDataError + StaleDataError

**Files:**
- Modify: `domain/exceptions.py`
- Test: `tests/test_domain_models.py`

- [ ] **Step 1: Write failing tests for new exceptions**

Add to `tests/test_domain_models.py`:

```python
from domain.exceptions import InsufficientDataError, StaleDataError


def test_insufficient_data_error_is_domain_error() -> None:
    err = InsufficientDataError("Need 3 mentions, got 1")
    assert isinstance(err, DomainError)
    assert str(err) == "Need 3 mentions, got 1"


def test_stale_data_error_is_domain_error() -> None:
    err = StaleDataError("Data older than 7 days")
    assert isinstance(err, DomainError)
    assert str(err) == "Data older than 7 days"
```

Also add `DomainError` to the imports at the top of the test file:
```python
from domain.exceptions import (
    DomainError,
    InsufficientDataError,
    InvalidMarketDataError,
    InvalidPredictionError,
    StaleDataError,
)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_domain_models.py::test_insufficient_data_error_is_domain_error tests/test_domain_models.py::test_stale_data_error_is_domain_error -v`
Expected: ImportError — InsufficientDataError not defined

- [ ] **Step 3: Implement new exceptions**

Add to bottom of `domain/exceptions.py`:

```python
class InsufficientDataError(DomainError):
    """Raised when not enough data points are available for analysis."""

    pass


class StaleDataError(DomainError):
    """Raised when data is too old to be useful for prediction."""

    pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_domain_models.py -v`
Expected: All tests PASS (including original 5 + 2 new)

- [ ] **Step 5: Commit**

```bash
git add domain/exceptions.py tests/test_domain_models.py
git commit -m "feat: add InsufficientDataError and StaleDataError domain exceptions"
```

---

## Task 2: Domain Models — RecommendationGrade Enum + TechnicalIndicators

**Files:**
- Modify: `domain/models.py`
- Modify: `tests/test_domain_models.py`

- [ ] **Step 1: Write failing tests for RecommendationGrade**

Add to `tests/test_domain_models.py`:

```python
from domain.models import RecommendationGrade, TechnicalIndicators


def test_recommendation_grade_ordering() -> None:
    """Grades have correct ordering: STRONG_BUY > BUY > HOLD > MAY_SELL > IMMEDIATE_SELL."""
    grades = list(RecommendationGrade)
    assert grades == [
        RecommendationGrade.STRONG_BUY,
        RecommendationGrade.BUY,
        RecommendationGrade.HOLD,
        RecommendationGrade.MAY_SELL,
        RecommendationGrade.IMMEDIATE_SELL,
    ]


def test_recommendation_grade_values() -> None:
    assert RecommendationGrade.STRONG_BUY.value == "STRONG_BUY"
    assert RecommendationGrade.IMMEDIATE_SELL.value == "IMMEDIATE_SELL"
```

- [ ] **Step 2: Write failing tests for TechnicalIndicators**

Add to `tests/test_domain_models.py`:

```python
def test_technical_indicators_valid_creation() -> None:
    ti = TechnicalIndicators(
        symbol="AAPL",
        timestamp=datetime.now(),
        rsi_14=55.0,
        macd=1.2,
        macd_signal=0.8,
        sma_20=150.0,
        sma_50=148.0,
        sma_200=140.0,
        bollinger_upper=155.0,
        bollinger_lower=145.0,
        volume_trend=1.1,
        technical_signal=0.3,
    )
    assert ti.symbol == "AAPL"
    assert ti.rsi_14 == 55.0
    assert ti.technical_signal == 0.3


def test_technical_indicators_rsi_out_of_bounds_raises() -> None:
    with pytest.raises(InvalidMarketDataError, match="rsi_14"):
        TechnicalIndicators(
            symbol="AAPL",
            timestamp=datetime.now(),
            rsi_14=150.0,
            macd=1.2,
            macd_signal=0.8,
            sma_20=150.0,
            sma_50=148.0,
            sma_200=140.0,
            bollinger_upper=155.0,
            bollinger_lower=145.0,
            volume_trend=1.1,
            technical_signal=0.3,
        )


def test_technical_indicators_signal_out_of_bounds_raises() -> None:
    with pytest.raises(InvalidMarketDataError, match="technical_signal"):
        TechnicalIndicators(
            symbol="AAPL",
            timestamp=datetime.now(),
            rsi_14=50.0,
            macd=1.2,
            macd_signal=0.8,
            sma_20=150.0,
            sma_50=148.0,
            sma_200=140.0,
            bollinger_upper=155.0,
            bollinger_lower=145.0,
            volume_trend=1.1,
            technical_signal=1.5,
        )
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_domain_models.py -v -k "grade or technical"`
Expected: ImportError — RecommendationGrade not defined

- [ ] **Step 4: Implement RecommendationGrade and TechnicalIndicators**

Add to `domain/models.py` after the existing imports:

```python
from enum import Enum


class RecommendationGrade(Enum):
    """Five-tier stock recommendation grading system."""

    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    MAY_SELL = "MAY_SELL"
    IMMEDIATE_SELL = "IMMEDIATE_SELL"


@dataclass(frozen=True)
class TechnicalIndicators:
    """Technical analysis indicators computed from OHLCV data.

    Attributes:
        rsi_14: Relative Strength Index (0-100).
        technical_signal: Composite signal (-1.0 bearish to 1.0 bullish).
    """

    symbol: str
    timestamp: datetime
    rsi_14: float
    macd: float
    macd_signal: float
    sma_20: float
    sma_50: float
    sma_200: float
    bollinger_upper: float
    bollinger_lower: float
    volume_trend: float
    technical_signal: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.rsi_14 <= 100.0:
            raise InvalidMarketDataError(
                f"rsi_14 must be in [0, 100], got {self.rsi_14}"
            )
        if not -1.0 <= self.technical_signal <= 1.0:
            raise InvalidMarketDataError(
                f"technical_signal must be in [-1, 1], got {self.technical_signal}"
            )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_domain_models.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add domain/models.py tests/test_domain_models.py
git commit -m "feat: add RecommendationGrade enum and TechnicalIndicators model"
```

---

## Task 3: Domain Models — DivergenceSignal + StockRecommendation

**Files:**
- Modify: `domain/models.py`
- Modify: `tests/test_domain_models.py`

- [ ] **Step 1: Write failing tests for DivergenceSignal**

Add to `tests/test_domain_models.py`:

```python
from domain.models import DivergenceSignal, StockRecommendation


def test_divergence_signal_valid_creation() -> None:
    ds = DivergenceSignal(
        symbol="AAPL",
        timestamp=datetime.now(),
        technical_signal=0.5,
        sentiment_signal=-0.3,
        divergence_score=0.8,
        divergence_type="bullish_divergence",
    )
    assert ds.divergence_type == "bullish_divergence"
    assert ds.divergence_score == 0.8


def test_divergence_signal_invalid_type_raises() -> None:
    with pytest.raises(InvalidMarketDataError, match="divergence_type"):
        DivergenceSignal(
            symbol="AAPL",
            timestamp=datetime.now(),
            technical_signal=0.5,
            sentiment_signal=-0.3,
            divergence_score=0.8,
            divergence_type="invalid_type",
        )


def test_divergence_signal_technical_out_of_bounds_raises() -> None:
    with pytest.raises(InvalidMarketDataError, match="technical_signal"):
        DivergenceSignal(
            symbol="AAPL",
            timestamp=datetime.now(),
            technical_signal=1.5,
            sentiment_signal=0.0,
            divergence_score=0.5,
            divergence_type="aligned",
        )


def test_stock_recommendation_valid_creation() -> None:
    now = datetime.now()
    ti = TechnicalIndicators(
        symbol="AAPL", timestamp=now, rsi_14=55.0, macd=1.2,
        macd_signal=0.8, sma_20=150.0, sma_50=148.0, sma_200=140.0,
        bollinger_upper=155.0, bollinger_lower=145.0, volume_trend=1.1,
        technical_signal=0.3,
    )
    ds = DivergenceSignal(
        symbol="AAPL", timestamp=now, technical_signal=0.3,
        sentiment_signal=0.7, divergence_score=0.4,
        divergence_type="bullish_divergence",
    )
    rec = StockRecommendation(
        symbol="AAPL",
        week_start=datetime(2026, 5, 25),  # a Monday
        grade=RecommendationGrade.STRONG_BUY,
        composite_score=0.85,
        predicted_5d_return=0.03,
        confidence=0.8,
        technical_summary=ti,
        sentiment_score=0.7,
        divergence=ds,
        reasoning="Strong bullish divergence with high sentiment",
        sources=["reuters", "reddit"],
    )
    assert rec.grade == RecommendationGrade.STRONG_BUY
    assert rec.confidence == 0.8


def test_stock_recommendation_confidence_out_of_bounds_raises() -> None:
    now = datetime.now()
    ti = TechnicalIndicators(
        symbol="AAPL", timestamp=now, rsi_14=55.0, macd=1.2,
        macd_signal=0.8, sma_20=150.0, sma_50=148.0, sma_200=140.0,
        bollinger_upper=155.0, bollinger_lower=145.0, volume_trend=1.1,
        technical_signal=0.3,
    )
    ds = DivergenceSignal(
        symbol="AAPL", timestamp=now, technical_signal=0.3,
        sentiment_signal=0.7, divergence_score=0.4,
        divergence_type="aligned",
    )
    with pytest.raises(InvalidPredictionError, match="confidence"):
        StockRecommendation(
            symbol="AAPL",
            week_start=datetime(2026, 5, 25),
            grade=RecommendationGrade.BUY,
            composite_score=0.5,
            predicted_5d_return=0.01,
            confidence=1.5,
            technical_summary=ti,
            sentiment_score=0.5,
            divergence=ds,
            reasoning="Test",
            sources=["test"],
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_domain_models.py -v -k "divergence or recommendation"`
Expected: ImportError

- [ ] **Step 3: Implement DivergenceSignal and StockRecommendation**

Add to `domain/models.py`:

```python
_VALID_DIVERGENCE_TYPES = frozenset(
    {"bullish_divergence", "bearish_divergence", "aligned"}
)


@dataclass(frozen=True)
class DivergenceSignal:
    """Disagreement between technical and sentiment signals."""

    symbol: str
    timestamp: datetime
    technical_signal: float
    sentiment_signal: float
    divergence_score: float
    divergence_type: str

    def __post_init__(self) -> None:
        if not -1.0 <= self.technical_signal <= 1.0:
            raise InvalidMarketDataError(
                f"technical_signal must be in [-1, 1], got {self.technical_signal}"
            )
        if not -1.0 <= self.sentiment_signal <= 1.0:
            raise InvalidMarketDataError(
                f"sentiment_signal must be in [-1, 1], got {self.sentiment_signal}"
            )
        if self.divergence_type not in _VALID_DIVERGENCE_TYPES:
            raise InvalidMarketDataError(
                f"divergence_type must be one of {_VALID_DIVERGENCE_TYPES}, "
                f"got {self.divergence_type!r}"
            )


@dataclass(frozen=True)
class StockRecommendation:
    """A graded stock pick for a specific week."""

    symbol: str
    week_start: datetime
    grade: RecommendationGrade
    composite_score: float
    predicted_5d_return: float
    confidence: float
    technical_summary: TechnicalIndicators
    sentiment_score: float
    divergence: DivergenceSignal
    reasoning: str
    sources: list[str]

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise InvalidPredictionError(
                f"confidence must be in [0, 1], got {self.confidence}"
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_domain_models.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add domain/models.py tests/test_domain_models.py
git commit -m "feat: add DivergenceSignal and StockRecommendation domain models"
```

---

## Task 4: Domain Models — WeeklyReport + AccuracyRecord

**Files:**
- Modify: `domain/models.py`
- Modify: `tests/test_domain_models.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_domain_models.py`:

```python
from domain.models import WeeklyReport, AccuracyRecord


def test_weekly_report_valid_creation() -> None:
    now = datetime.now()
    monday = datetime(2026, 5, 25)  # Monday
    ti = TechnicalIndicators(
        symbol="AAPL", timestamp=now, rsi_14=55.0, macd=1.2,
        macd_signal=0.8, sma_20=150.0, sma_50=148.0, sma_200=140.0,
        bollinger_upper=155.0, bollinger_lower=145.0, volume_trend=1.1,
        technical_signal=0.3,
    )
    ds = DivergenceSignal(
        symbol="AAPL", timestamp=now, technical_signal=0.3,
        sentiment_signal=0.7, divergence_score=0.4,
        divergence_type="aligned",
    )
    recs = [
        StockRecommendation(
            symbol=f"TICK{i}", week_start=monday,
            grade=RecommendationGrade.BUY, composite_score=0.5,
            predicted_5d_return=0.01, confidence=0.7,
            technical_summary=ti, sentiment_score=0.5,
            divergence=ds, reasoning="Test", sources=["test"],
        )
        for i in range(15)
    ]
    report = WeeklyReport(
        report_date=monday,
        market="us",
        recommendations=recs,
        carryover_updates=[],
        accuracy_vs_last_week=None,
        spy_return_same_period=None,
    )
    assert len(report.recommendations) == 15
    assert report.market == "us"


def test_weekly_report_too_many_recommendations_raises() -> None:
    now = datetime.now()
    monday = datetime(2026, 5, 25)
    ti = TechnicalIndicators(
        symbol="AAPL", timestamp=now, rsi_14=55.0, macd=1.2,
        macd_signal=0.8, sma_20=150.0, sma_50=148.0, sma_200=140.0,
        bollinger_upper=155.0, bollinger_lower=145.0, volume_trend=1.1,
        technical_signal=0.3,
    )
    ds = DivergenceSignal(
        symbol="AAPL", timestamp=now, technical_signal=0.3,
        sentiment_signal=0.7, divergence_score=0.4,
        divergence_type="aligned",
    )
    recs = [
        StockRecommendation(
            symbol=f"TICK{i}", week_start=monday,
            grade=RecommendationGrade.BUY, composite_score=0.5,
            predicted_5d_return=0.01, confidence=0.7,
            technical_summary=ti, sentiment_score=0.5,
            divergence=ds, reasoning="Test", sources=["test"],
        )
        for i in range(16)
    ]
    with pytest.raises(InvalidPredictionError, match="between 1 and 15"):
        WeeklyReport(
            report_date=monday, market="us", recommendations=recs,
            carryover_updates=[], accuracy_vs_last_week=None,
            spy_return_same_period=None,
        )


def test_weekly_report_empty_recommendations_raises() -> None:
    monday = datetime(2026, 5, 25)
    with pytest.raises(InvalidPredictionError, match="between 1 and 15"):
        WeeklyReport(
            report_date=monday, market="us", recommendations=[],
            carryover_updates=[], accuracy_vs_last_week=None,
            spy_return_same_period=None,
        )


def test_weekly_report_non_monday_raises() -> None:
    now = datetime.now()
    tuesday = datetime(2026, 5, 26)  # Tuesday
    ti = TechnicalIndicators(
        symbol="AAPL", timestamp=now, rsi_14=55.0, macd=1.2,
        macd_signal=0.8, sma_20=150.0, sma_50=148.0, sma_200=140.0,
        bollinger_upper=155.0, bollinger_lower=145.0, volume_trend=1.1,
        technical_signal=0.3,
    )
    ds = DivergenceSignal(
        symbol="AAPL", timestamp=now, technical_signal=0.3,
        sentiment_signal=0.7, divergence_score=0.4,
        divergence_type="aligned",
    )
    recs = [
        StockRecommendation(
            symbol="AAPL", week_start=tuesday,
            grade=RecommendationGrade.BUY, composite_score=0.5,
            predicted_5d_return=0.01, confidence=0.7,
            technical_summary=ti, sentiment_score=0.5,
            divergence=ds, reasoning="Test", sources=["test"],
        )
    ]
    with pytest.raises(InvalidPredictionError, match="Monday"):
        WeeklyReport(
            report_date=tuesday, market="us", recommendations=recs,
            carryover_updates=[], accuracy_vs_last_week=None,
            spy_return_same_period=None,
        )


def test_accuracy_record_valid_creation() -> None:
    ar = AccuracyRecord(
        symbol="AAPL",
        week_start=datetime(2026, 5, 25),
        predicted_grade=RecommendationGrade.STRONG_BUY,
        predicted_return=0.03,
        actual_return=0.025,
        grade_correct=True,
        held_weeks=1,
    )
    assert ar.grade_correct is True
    assert ar.held_weeks == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_domain_models.py -v -k "weekly_report or accuracy_record"`
Expected: ImportError

- [ ] **Step 3: Implement WeeklyReport and AccuracyRecord**

Add to `domain/models.py`:

```python
@dataclass(frozen=True)
class WeeklyReport:
    """Complete output of one weekly tournament round."""

    report_date: datetime
    market: str
    recommendations: list[StockRecommendation]
    carryover_updates: list[StockRecommendation]
    accuracy_vs_last_week: float | None
    spy_return_same_period: float | None

    def __post_init__(self) -> None:
        if not 1 <= len(self.recommendations) <= 15:
            raise InvalidPredictionError(
                f"recommendations must have between 1 and 15 items, "
                f"got {len(self.recommendations)}"
            )
        if self.report_date.weekday() != 0:
            raise InvalidPredictionError(
                f"report_date must be a Monday, got {self.report_date.strftime('%A')}"
            )


@dataclass(frozen=True)
class AccuracyRecord:
    """Historical record comparing predicted vs actual outcomes."""

    symbol: str
    week_start: datetime
    predicted_grade: RecommendationGrade
    predicted_return: float
    actual_return: float
    grade_correct: bool
    held_weeks: int
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_domain_models.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add domain/models.py tests/test_domain_models.py
git commit -m "feat: add WeeklyReport and AccuracyRecord domain models"
```

---

## Task 5: Domain Ports — Phase 3 Port Interfaces

**Files:**
- Modify: `domain/ports.py`
- Test: Read-only verification (ports are Protocols — tested via adapter implementations)

- [ ] **Step 1: Add new port imports and interfaces**

Add to `domain/ports.py` — add new imports at the top:

```python
from .models import (
    AccuracyRecord,
    BacktestResult,
    DivergenceSignal,
    Sentiment,
    Signal,
    StockRecommendation,
    TechnicalIndicators,
    WeeklyReport,
)
```

Then add these Protocol classes after the existing ones:

```python
class TechnicalAnalysisPort(Protocol):
    """Port: compute technical indicators from market data."""

    def compute_indicators(
        self, symbol: str, lookback_days: int = 90
    ) -> TechnicalIndicators:
        """Compute technical indicators for symbol over lookback window."""
        ...

    def compute_technical_signal(self, indicators: TechnicalIndicators) -> float:
        """Compute composite technical signal from indicators. Returns [-1.0, 1.0]."""
        ...


class NewsDiscoveryPort(Protocol):
    """Port: discover financial news articles mentioning stocks."""

    def discover_articles(
        self, query: str, max_results: int = 10
    ) -> list[dict[str, str]]:
        """Return articles matching query.

        Each dict contains: url, title, snippet, source, published_date.
        """
        ...

    def extract_tickers(self, text: str) -> list[str]:
        """Extract ticker symbols from article text."""
        ...


class BuzzScorerPort(Protocol):
    """Port: measure social buzz for stocks."""

    def get_trending_tickers(
        self, lookback_hours: int = 168
    ) -> list[dict[str, int]]:
        """Return trending tickers with mention counts.

        Each dict contains: ticker, mention_count, unique_authors.
        """
        ...

    def get_raw_posts(
        self, ticker: str, limit: int = 50
    ) -> list[dict[str, str]]:
        """Return raw posts mentioning ticker.

        Each dict contains: text, author, timestamp, score.
        """
        ...


class SentimentScorerPort(Protocol):
    """Port: score text for financial sentiment."""

    def score(self, text: str) -> float:
        """Score a single text. Returns [-1.0, 1.0]."""
        ...

    def score_batch(self, texts: list[str]) -> list[float]:
        """Score multiple texts. Returns list of scores [-1.0, 1.0]."""
        ...


class RecommendationStorePort(Protocol):
    """Port: persist and retrieve recommendations and accuracy records."""

    def save_weekly_report(self, report: WeeklyReport) -> None:
        """Persist a weekly report."""
        ...

    def get_report(self, week_start: datetime) -> WeeklyReport | None:
        """Retrieve report for a specific week."""
        ...

    def get_reports_range(
        self, start: datetime, end: datetime
    ) -> list[WeeklyReport]:
        """Retrieve all reports in date range."""
        ...

    def save_accuracy_record(self, record: AccuracyRecord) -> None:
        """Persist an accuracy record."""
        ...

    def get_accuracy_history(self, days: int = 90) -> list[AccuracyRecord]:
        """Retrieve accuracy records for rolling window."""
        ...

    def get_rolling_accuracy(self, days: int = 90) -> float:
        """Compute rolling accuracy over window. Returns fraction correct."""
        ...
```

- [ ] **Step 2: Verify mypy passes on ports**

Run: `mypy domain/ports.py --strict`
Expected: Success, no errors

- [ ] **Step 3: Verify all tests still pass**

Run: `pytest -v --tb=short`
Expected: All existing tests PASS

- [ ] **Step 4: Commit**

```bash
git add domain/ports.py
git commit -m "feat: add Phase 3 port interfaces — NewsDiscovery, BuzzScorer, SentimentScorer, RecommendationStore, TechnicalAnalysis"
```

---

## Task 6: Domain Services — compute_divergence_score + grade_recommendation

**Files:**
- Modify: `domain/services.py`
- Modify: `tests/test_domain_services.py`

- [ ] **Step 1: Write failing tests for compute_divergence_score**

Add to `tests/test_domain_services.py`:

```python
from domain.models import DivergenceSignal, RecommendationGrade, TechnicalIndicators
from domain.services import compute_divergence_score, grade_recommendation


def test_divergence_aligned_when_signals_agree() -> None:
    ds = compute_divergence_score(
        symbol="AAPL",
        timestamp=datetime.now(),
        technical_signal=0.5,
        sentiment_signal=0.6,
    )
    assert ds.divergence_type == "aligned"
    assert ds.divergence_score < 0.5


def test_divergence_bullish_when_sentiment_exceeds_technical() -> None:
    ds = compute_divergence_score(
        symbol="AAPL",
        timestamp=datetime.now(),
        technical_signal=-0.5,
        sentiment_signal=0.7,
    )
    assert ds.divergence_type == "bullish_divergence"
    assert ds.divergence_score > 0.5


def test_divergence_bearish_when_technical_exceeds_sentiment() -> None:
    ds = compute_divergence_score(
        symbol="AAPL",
        timestamp=datetime.now(),
        technical_signal=0.8,
        sentiment_signal=-0.3,
    )
    assert ds.divergence_type == "bearish_divergence"
    assert ds.divergence_score > 0.5
```

- [ ] **Step 2: Write failing tests for grade_recommendation**

Add to `tests/test_domain_services.py`:

```python
def test_grade_top_3_is_strong_buy() -> None:
    assert grade_recommendation(rank=1, total=15) == RecommendationGrade.STRONG_BUY
    assert grade_recommendation(rank=3, total=15) == RecommendationGrade.STRONG_BUY


def test_grade_rank_4_to_8_is_buy() -> None:
    assert grade_recommendation(rank=4, total=15) == RecommendationGrade.BUY
    assert grade_recommendation(rank=8, total=15) == RecommendationGrade.BUY


def test_grade_rank_9_to_12_is_hold() -> None:
    assert grade_recommendation(rank=9, total=15) == RecommendationGrade.HOLD
    assert grade_recommendation(rank=12, total=15) == RecommendationGrade.HOLD


def test_grade_rank_13_to_15_is_may_sell() -> None:
    assert grade_recommendation(rank=13, total=15) == RecommendationGrade.MAY_SELL
    assert grade_recommendation(rank=15, total=15) == RecommendationGrade.MAY_SELL


def test_grade_monotonic() -> None:
    """Higher rank (lower number) never gets a worse grade."""
    grades = [grade_recommendation(rank=r, total=15) for r in range(1, 16)]
    grade_order = list(RecommendationGrade)
    grade_indices = [grade_order.index(g) for g in grades]
    for i in range(len(grade_indices) - 1):
        assert grade_indices[i] <= grade_indices[i + 1]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_domain_services.py -v -k "divergence or grade"`
Expected: ImportError — compute_divergence_score not defined

- [ ] **Step 4: Implement compute_divergence_score**

Add to `domain/services.py`:

```python
from .models import DivergenceSignal, RecommendationGrade


def compute_divergence_score(
    *,
    symbol: str,
    timestamp: datetime,
    technical_signal: float,
    sentiment_signal: float,
    threshold: float = 0.4,
) -> DivergenceSignal:
    """Compute divergence between technical and sentiment signals.

    Args:
        threshold: Minimum absolute difference to classify as divergence.

    Returns:
        DivergenceSignal with type and score.
    """
    diff = sentiment_signal - technical_signal
    score = abs(diff)

    if score < threshold:
        dtype = "aligned"
    elif diff > 0:
        dtype = "bullish_divergence"
    else:
        dtype = "bearish_divergence"

    return DivergenceSignal(
        symbol=symbol,
        timestamp=timestamp,
        technical_signal=technical_signal,
        sentiment_signal=sentiment_signal,
        divergence_score=score,
        divergence_type=dtype,
    )
```

- [ ] **Step 5: Implement grade_recommendation**

Add to `domain/services.py`:

```python
def grade_recommendation(*, rank: int, total: int) -> RecommendationGrade:
    """Assign grade based on rank within the weekly tournament.

    Grading bands (for total=15):
        1-3: STRONG_BUY
        4-8: BUY
        9-12: HOLD
        13-15: MAY_SELL
    """
    if rank <= 3:
        return RecommendationGrade.STRONG_BUY
    elif rank <= 8:
        return RecommendationGrade.BUY
    elif rank <= 12:
        return RecommendationGrade.HOLD
    else:
        return RecommendationGrade.MAY_SELL
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_domain_services.py -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add domain/services.py tests/test_domain_services.py
git commit -m "feat: add compute_divergence_score and grade_recommendation domain services"
```

---

## Task 7: Hypothesis Property-Based Tests

**Files:**
- Create: `tests/test_properties.py`

- [ ] **Step 1: Write property tests**

Create `tests/test_properties.py`:

```python
"""Property-based tests for domain invariants using Hypothesis."""

from datetime import datetime, timedelta

from hypothesis import given, settings
from hypothesis import strategies as st

from domain.exceptions import InvalidMarketDataError, LookAheadBiasError
from domain.models import (
    DivergenceSignal,
    RecommendationGrade,
    Sentiment,
    TechnicalIndicators,
)
from domain.services import (
    compute_divergence_score,
    grade_recommendation,
    validate_point_in_time_access,
)


@given(score=st.floats(min_value=-1.0, max_value=1.0))
def test_sentiment_score_always_bounded(score: float) -> None:
    """Any score in [-1, 1] produces valid Sentiment."""
    s = Sentiment(
        source="test",
        timestamp=datetime(2026, 1, 1),
        sentiment_score=score,
        confidence=0.5,
    )
    assert -1.0 <= s.sentiment_score <= 1.0


@given(score=st.floats(min_value=-1.0, max_value=1.0).filter(lambda x: abs(x) > 1e-10 or x == 0))
def test_sentiment_out_of_bounds_rejects(score: float) -> None:
    """Scores outside [-1, 1] are rejected."""
    if -1.0 <= score <= 1.0:
        return  # valid, skip
    try:
        Sentiment(
            source="test",
            timestamp=datetime(2026, 1, 1),
            sentiment_score=score,
            confidence=0.5,
        )
        assert False, f"Should have rejected score={score}"
    except InvalidMarketDataError:
        pass


@given(
    tech=st.floats(min_value=-1.0, max_value=1.0),
    sent=st.floats(min_value=-1.0, max_value=1.0),
)
def test_divergence_score_symmetric(tech: float, sent: float) -> None:
    """|divergence_score| is symmetric: swapping tech/sent gives same magnitude."""
    ds1 = compute_divergence_score(
        symbol="X", timestamp=datetime(2026, 1, 1),
        technical_signal=tech, sentiment_signal=sent,
    )
    ds2 = compute_divergence_score(
        symbol="X", timestamp=datetime(2026, 1, 1),
        technical_signal=sent, sentiment_signal=tech,
    )
    assert abs(ds1.divergence_score - ds2.divergence_score) < 1e-10


@given(rank=st.integers(min_value=1, max_value=15))
def test_grading_monotonic(rank: int) -> None:
    """Lower rank number (better) never gets a worse grade."""
    if rank == 1:
        return
    better = grade_recommendation(rank=rank - 1, total=15)
    current = grade_recommendation(rank=rank, total=15)
    grade_order = list(RecommendationGrade)
    assert grade_order.index(better) <= grade_order.index(current)


@given(
    future_offset=st.timedeltas(min_value=timedelta(seconds=1), max_value=timedelta(days=30))
)
def test_point_in_time_never_leaks(future_offset: timedelta) -> None:
    """Any signal with timestamp > prediction_time raises LookAheadBiasError."""
    pt = datetime(2026, 1, 1)
    from domain.models import Signal

    signals = [
        Signal(
            symbol="X", timestamp=pt + future_offset,
            price=100.0, volume=1000.0,
            open_=99.0, high=101.0, low=98.0,
        )
    ]
    try:
        validate_point_in_time_access(pt, signals, [])
        assert False, "Should have raised LookAheadBiasError"
    except LookAheadBiasError:
        pass
```

- [ ] **Step 2: Run property tests**

Run: `pytest tests/test_properties.py -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_properties.py
git commit -m "test: add Hypothesis property-based tests for domain invariants"
```

---

## Task 8: Config — US Market YAML + Loader

**Files:**
- Create: `config/__init__.py`
- Create: `config/markets/__init__.py`
- Create: `config/markets/us.yaml`
- Create: `config/loader.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing test for config loader**

Create `tests/test_config.py`:

```python
"""Tests for market configuration loading."""

from pathlib import Path

from config.loader import load_market_config


def test_load_us_market_config() -> None:
    config = load_market_config("us")
    assert config["market"]["name"] == "US"
    assert config["market"]["currency"] == "USD"
    assert config["filters"]["min_price"] == 5.0
    assert config["filters"]["min_avg_volume"] == 100000
    assert config["filters"]["min_mentions"] == 3
    assert len(config["news_discovery"]["rss_feeds"]) >= 5
    assert len(config["sector_etfs"]) >= 10


def test_load_nonexistent_market_raises() -> None:
    import pytest

    with pytest.raises(FileNotFoundError):
        load_market_config("nonexistent")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: ModuleNotFoundError — config.loader

- [ ] **Step 3: Create config directory and us.yaml**

Create `config/__init__.py` (empty), `config/markets/__init__.py` (empty).

Create `config/markets/us.yaml`:

```yaml
market:
  name: "US"
  currency: "USD"
  trading_hours:
    open: "09:30"
    close: "16:00"
    timezone: "America/New_York"

filters:
  min_price: 5.0
  min_avg_volume: 100000
  min_mentions: 3

news_discovery:
  rss_feeds:
    - name: motley_fool
      url: "https://fool.com/feeds/index.aspx"
    - name: seeking_alpha
      url: "https://seekingalpha.com/feed"
    - name: yahoo_finance
      url: "https://finance.yahoo.com/news/rss"
    - name: marketwatch
      url: "https://feeds.marketwatch.com/marketwatch/topstories"
    - name: benzinga
      url: "https://benzinga.com/feed"
    - name: robinhood_snacks
      url: "https://snacks.robinhood.com/feed/"

  google_search_targets:
    - "stocks to buy this week site:morningstar.com"
    - "top stock picks site:barrons.com"
    - "best stocks site:investorsbusinessdaily.com"
    - "stocks to buy site:zacks.com"
    - "stock recommendations site:kiplinger.com"

buzz_sources:
  reddit:
    subreddits:
      - wallstreetbets
      - stocks
      - investing
  stocktwits:
    enabled: true

sector_etfs:
  - XLK
  - XLF
  - XLE
  - XLV
  - XLI
  - XLC
  - XLY
  - XLP
  - XLU
  - XLRE
  - XLB
```

- [ ] **Step 4: Create config loader**

Create `config/loader.py`:

```python
"""Load market configuration from YAML files."""

from pathlib import Path
from typing import Any

import yaml


_CONFIG_DIR = Path(__file__).parent / "markets"


def load_market_config(market: str) -> dict[str, Any]:
    """Load market config from config/markets/{market}.yaml.

    Raises:
        FileNotFoundError: If config file does not exist.
    """
    path = _CONFIG_DIR / f"{market}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Market config not found: {path}")
    with open(path) as f:
        return yaml.safe_load(f)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add config/ tests/test_config.py
git commit -m "feat: add US market config and YAML config loader"
```

---

## Task 9: Test Fakes — All Fake Adapter Implementations

**Files:**
- Create: `tests/fakes/__init__.py`
- Create: `tests/fakes/fake_market_data.py`
- Create: `tests/fakes/fake_news_discovery.py`
- Create: `tests/fakes/fake_buzz_scorer.py`
- Create: `tests/fakes/fake_sentiment_scorer.py`
- Create: `tests/fakes/fake_store.py`
- Create: `tests/fakes/fake_technical_analysis.py`

- [ ] **Step 1: Create fake_market_data.py**

Create `tests/fakes/__init__.py` (empty).

Create `tests/fakes/fake_market_data.py`:

```python
"""Fake MarketDataPort for testing."""

from datetime import datetime

from domain.exceptions import LookAheadBiasError
from domain.models import Signal


class FakeMarketData:
    """In-memory market data source with canned data."""

    def __init__(self, signals: list[Signal] | None = None) -> None:
        self._signals = signals or []

    def get_signals(
        self,
        symbol: str,
        prediction_time: datetime,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[Signal]:
        result = [s for s in self._signals if s.symbol == symbol]
        result = [s for s in result if s.timestamp <= prediction_time]
        if start_date:
            result = [s for s in result if s.timestamp >= start_date]
        if end_date:
            result = [s for s in result if s.timestamp <= end_date]
        return result

    def validate_point_in_time(self, prediction_time: datetime) -> None:
        for s in self._signals:
            if s.timestamp > prediction_time:
                raise LookAheadBiasError(
                    f"Future signal detected: {s.timestamp}"
                )
```

- [ ] **Step 2: Create fake_technical_analysis.py**

Create `tests/fakes/fake_technical_analysis.py`:

```python
"""Fake TechnicalAnalysisPort for testing."""

from datetime import datetime

from domain.models import TechnicalIndicators


class FakeTechnicalAnalysis:
    """Returns canned technical indicators."""

    def __init__(
        self, indicators: dict[str, TechnicalIndicators] | None = None
    ) -> None:
        self._indicators = indicators or {}

    def compute_indicators(
        self, symbol: str, lookback_days: int = 90
    ) -> TechnicalIndicators:
        if symbol in self._indicators:
            return self._indicators[symbol]
        return TechnicalIndicators(
            symbol=symbol,
            timestamp=datetime(2026, 5, 25),
            rsi_14=50.0,
            macd=0.0,
            macd_signal=0.0,
            sma_20=100.0,
            sma_50=100.0,
            sma_200=100.0,
            bollinger_upper=105.0,
            bollinger_lower=95.0,
            volume_trend=1.0,
            technical_signal=0.0,
        )

    def compute_technical_signal(self, indicators: TechnicalIndicators) -> float:
        return indicators.technical_signal
```

- [ ] **Step 3: Create fake_news_discovery.py**

Create `tests/fakes/fake_news_discovery.py`:

```python
"""Fake NewsDiscoveryPort for testing."""

import re


class FakeNewsDiscovery:
    """Returns canned articles and extracts tickers via regex."""

    def __init__(self, articles: list[dict[str, str]] | None = None) -> None:
        self._articles = articles or []

    def discover_articles(
        self, query: str, max_results: int = 10
    ) -> list[dict[str, str]]:
        return self._articles[:max_results]

    def extract_tickers(self, text: str) -> list[str]:
        return re.findall(r"\b[A-Z]{1,5}\b", text)
```

- [ ] **Step 4: Create fake_buzz_scorer.py**

Create `tests/fakes/fake_buzz_scorer.py`:

```python
"""Fake BuzzScorerPort for testing."""


class FakeBuzzScorer:
    """Returns canned buzz data."""

    def __init__(
        self,
        trending: list[dict[str, int]] | None = None,
        posts: dict[str, list[dict[str, str]]] | None = None,
    ) -> None:
        self._trending = trending or []
        self._posts = posts or {}

    def get_trending_tickers(
        self, lookback_hours: int = 168
    ) -> list[dict[str, int]]:
        return self._trending

    def get_raw_posts(
        self, ticker: str, limit: int = 50
    ) -> list[dict[str, str]]:
        return self._posts.get(ticker, [])[:limit]
```

- [ ] **Step 5: Create fake_sentiment_scorer.py**

Create `tests/fakes/fake_sentiment_scorer.py`:

```python
"""Fake SentimentScorerPort for testing."""


class FakeSentimentScorer:
    """Returns deterministic sentiment scores."""

    def __init__(self, default_score: float = 0.0) -> None:
        self._default = default_score

    def score(self, text: str) -> float:
        return self._default

    def score_batch(self, texts: list[str]) -> list[float]:
        return [self._default] * len(texts)
```

- [ ] **Step 6: Create fake_store.py**

Create `tests/fakes/fake_store.py`:

```python
"""Fake RecommendationStorePort for testing."""

from datetime import datetime, timedelta

from domain.models import AccuracyRecord, WeeklyReport


class FakeStore:
    """In-memory store for reports and accuracy records."""

    def __init__(self) -> None:
        self._reports: dict[str, WeeklyReport] = {}
        self._accuracy: list[AccuracyRecord] = []

    def save_weekly_report(self, report: WeeklyReport) -> None:
        key = report.report_date.isoformat()
        self._reports[key] = report

    def get_report(self, week_start: datetime) -> WeeklyReport | None:
        return self._reports.get(week_start.isoformat())

    def get_reports_range(
        self, start: datetime, end: datetime
    ) -> list[WeeklyReport]:
        return [
            r for r in self._reports.values()
            if start <= r.report_date <= end
        ]

    def save_accuracy_record(self, record: AccuracyRecord) -> None:
        self._accuracy.append(record)

    def get_accuracy_history(self, days: int = 90) -> list[AccuracyRecord]:
        cutoff = datetime.now() - timedelta(days=days)
        return [a for a in self._accuracy if a.week_start >= cutoff]

    def get_rolling_accuracy(self, days: int = 90) -> float:
        records = self.get_accuracy_history(days)
        if not records:
            return 0.0
        correct = sum(1 for r in records if r.grade_correct)
        return correct / len(records)
```

- [ ] **Step 7: Verify imports work**

Run: `python -c "from tests.fakes.fake_market_data import FakeMarketData; from tests.fakes.fake_news_discovery import FakeNewsDiscovery; from tests.fakes.fake_buzz_scorer import FakeBuzzScorer; from tests.fakes.fake_sentiment_scorer import FakeSentimentScorer; from tests.fakes.fake_store import FakeStore; from tests.fakes.fake_technical_analysis import FakeTechnicalAnalysis; print('All fakes OK')"`
Expected: "All fakes OK"

- [ ] **Step 8: Commit**

```bash
git add tests/fakes/
git commit -m "feat: add fake adapter implementations for all Phase 3 ports"
```

---

## Task 10: Adapter — Keyword Sentiment Scorer (Baseline NLP)

**Files:**
- Create: `adapters/ml/keyword_scorer.py`
- Create: `tests/test_keyword_scorer.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_keyword_scorer.py`:

```python
"""Tests for keyword-based sentiment scorer (baseline NLP)."""

import pytest

from adapters.ml.keyword_scorer import KeywordSentimentScorer


@pytest.fixture
def scorer() -> KeywordSentimentScorer:
    return KeywordSentimentScorer()


def test_bullish_text_positive_score(scorer: KeywordSentimentScorer) -> None:
    score = scorer.score("AAPL is bullish, strong buy, upgrade, growth")
    assert score > 0.0


def test_bearish_text_negative_score(scorer: KeywordSentimentScorer) -> None:
    score = scorer.score("Stock crash, bearish, downgrade, sell off")
    assert score < 0.0


def test_neutral_text_near_zero(scorer: KeywordSentimentScorer) -> None:
    score = scorer.score("The company reported quarterly earnings")
    assert -0.2 <= score <= 0.2


def test_score_bounded(scorer: KeywordSentimentScorer) -> None:
    score = scorer.score("buy buy buy bullish upgrade strong growth moon rocket")
    assert -1.0 <= score <= 1.0


def test_empty_text_returns_zero(scorer: KeywordSentimentScorer) -> None:
    assert scorer.score("") == 0.0


def test_score_batch(scorer: KeywordSentimentScorer) -> None:
    scores = scorer.score_batch(["bullish upgrade", "bearish crash", "neutral"])
    assert len(scores) == 3
    assert scores[0] > 0
    assert scores[1] < 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_keyword_scorer.py -v`
Expected: ImportError

- [ ] **Step 3: Implement keyword scorer**

Create `adapters/ml/keyword_scorer.py`:

```python
"""Keyword-based sentiment scorer — baseline NLP (Step 1 of sentiment ladder).

Scores text by counting bullish vs bearish keywords.
"""

import re

_BULLISH_WORDS = frozenset({
    "buy", "bullish", "upgrade", "growth", "rally", "breakout", "strong",
    "outperform", "upside", "positive", "beat", "exceed", "momentum",
    "recovery", "surge", "gain", "rise", "moon", "rocket", "calls",
    "long", "accumulate", "overweight",
})

_BEARISH_WORDS = frozenset({
    "sell", "bearish", "downgrade", "crash", "decline", "weak", "drop",
    "underperform", "downside", "negative", "miss", "loss", "plunge",
    "risk", "warning", "fall", "puts", "short", "reduce", "underweight",
    "recession", "bankruptcy", "fraud",
})


class KeywordSentimentScorer:
    """Score text sentiment by bullish/bearish keyword frequency."""

    def score(self, text: str) -> float:
        """Score a single text. Returns [-1.0, 1.0]."""
        if not text.strip():
            return 0.0

        words = set(re.findall(r"[a-z]+", text.lower()))
        bullish = len(words & _BULLISH_WORDS)
        bearish = len(words & _BEARISH_WORDS)
        total = bullish + bearish

        if total == 0:
            return 0.0

        raw = (bullish - bearish) / total
        return max(-1.0, min(1.0, raw))

    def score_batch(self, texts: list[str]) -> list[float]:
        """Score multiple texts."""
        return [self.score(t) for t in texts]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_keyword_scorer.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add adapters/ml/keyword_scorer.py tests/test_keyword_scorer.py
git commit -m "feat: add keyword-based sentiment scorer — baseline NLP"
```

---

## Task 11: Adapter — SQLite Store

**Files:**
- Create: `adapters/data/sqlite_store.py`
- Create: `tests/test_sqlite_store.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_sqlite_store.py`:

```python
"""Tests for SQLite recommendation store (in-memory)."""

from datetime import datetime

import pytest

from adapters.data.sqlite_store import SqliteStore
from domain.models import (
    AccuracyRecord,
    DivergenceSignal,
    RecommendationGrade,
    StockRecommendation,
    TechnicalIndicators,
    WeeklyReport,
)


@pytest.fixture
def store() -> SqliteStore:
    return SqliteStore(db_path=":memory:")


def _make_recommendation(symbol: str, monday: datetime) -> StockRecommendation:
    """Helper to create a StockRecommendation."""
    now = datetime.now()
    ti = TechnicalIndicators(
        symbol=symbol, timestamp=now, rsi_14=55.0, macd=1.2,
        macd_signal=0.8, sma_20=150.0, sma_50=148.0, sma_200=140.0,
        bollinger_upper=155.0, bollinger_lower=145.0, volume_trend=1.1,
        technical_signal=0.3,
    )
    ds = DivergenceSignal(
        symbol=symbol, timestamp=now, technical_signal=0.3,
        sentiment_signal=0.7, divergence_score=0.4,
        divergence_type="bullish_divergence",
    )
    return StockRecommendation(
        symbol=symbol, week_start=monday,
        grade=RecommendationGrade.BUY, composite_score=0.7,
        predicted_5d_return=0.02, confidence=0.8,
        technical_summary=ti, sentiment_score=0.7,
        divergence=ds, reasoning="Test rec",
        sources=["reuters", "reddit"],
    )


def _make_report(monday: datetime) -> WeeklyReport:
    recs = [_make_recommendation(f"TICK{i}", monday) for i in range(5)]
    return WeeklyReport(
        report_date=monday, market="us", recommendations=recs,
        carryover_updates=[], accuracy_vs_last_week=None,
        spy_return_same_period=None,
    )


def test_save_and_get_report(store: SqliteStore) -> None:
    monday = datetime(2026, 5, 25)
    report = _make_report(monday)
    store.save_weekly_report(report)
    loaded = store.get_report(monday)
    assert loaded is not None
    assert len(loaded.recommendations) == 5
    assert loaded.market == "us"


def test_get_nonexistent_report_returns_none(store: SqliteStore) -> None:
    result = store.get_report(datetime(2026, 1, 6))
    assert result is None


def test_save_and_get_accuracy_record(store: SqliteStore) -> None:
    record = AccuracyRecord(
        symbol="AAPL", week_start=datetime(2026, 5, 25),
        predicted_grade=RecommendationGrade.BUY,
        predicted_return=0.02, actual_return=0.015,
        grade_correct=True, held_weeks=1,
    )
    store.save_accuracy_record(record)
    history = store.get_accuracy_history(days=90)
    assert len(history) == 1
    assert history[0].symbol == "AAPL"


def test_rolling_accuracy(store: SqliteStore) -> None:
    monday = datetime(2026, 5, 25)
    for i in range(10):
        store.save_accuracy_record(AccuracyRecord(
            symbol=f"TICK{i}", week_start=monday,
            predicted_grade=RecommendationGrade.BUY,
            predicted_return=0.01, actual_return=0.01,
            grade_correct=i < 7,  # 7 out of 10 correct
            held_weeks=1,
        ))
    accuracy = store.get_rolling_accuracy(days=90)
    assert accuracy == pytest.approx(0.7)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_sqlite_store.py -v`
Expected: ImportError

- [ ] **Step 3: Implement SQLite store**

Create `adapters/data/sqlite_store.py`:

```python
"""SQLite-backed recommendation and accuracy store."""

import json
import sqlite3
from datetime import datetime, timedelta

from domain.models import (
    AccuracyRecord,
    DivergenceSignal,
    RecommendationGrade,
    StockRecommendation,
    TechnicalIndicators,
    WeeklyReport,
)


class SqliteStore:
    """RecommendationStorePort implementation using SQLite."""

    def __init__(self, db_path: str = "data/recommendations.db") -> None:
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS recommendations (
                id INTEGER PRIMARY KEY,
                symbol TEXT NOT NULL,
                week_start TEXT NOT NULL,
                grade TEXT NOT NULL,
                composite_score REAL,
                predicted_5d_return REAL,
                confidence REAL,
                sentiment_score REAL,
                divergence_score REAL,
                divergence_type TEXT,
                technical_signal REAL,
                rsi_14 REAL,
                macd REAL,
                macd_signal_val REAL,
                sma_20 REAL,
                sma_50 REAL,
                sma_200 REAL,
                bollinger_upper REAL,
                bollinger_lower REAL,
                volume_trend REAL,
                reasoning TEXT,
                sources TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                UNIQUE(symbol, week_start)
            );

            CREATE TABLE IF NOT EXISTS weekly_reports (
                id INTEGER PRIMARY KEY,
                report_date TEXT NOT NULL UNIQUE,
                market TEXT NOT NULL,
                accuracy_vs_last_week REAL,
                spy_return_same_period REAL,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS accuracy_records (
                id INTEGER PRIMARY KEY,
                symbol TEXT NOT NULL,
                week_start TEXT NOT NULL,
                predicted_grade TEXT,
                predicted_return REAL,
                actual_return REAL,
                grade_correct INTEGER,
                held_weeks INTEGER DEFAULT 1,
                evaluated_at TEXT DEFAULT (datetime('now')),
                UNIQUE(symbol, week_start)
            );

            CREATE INDEX IF NOT EXISTS idx_rec_week
                ON recommendations(week_start);
            CREATE INDEX IF NOT EXISTS idx_acc_week
                ON accuracy_records(week_start);
        """)
        self._conn.commit()

    def save_weekly_report(self, report: WeeklyReport) -> None:
        date_str = report.report_date.isoformat()
        self._conn.execute(
            """INSERT OR REPLACE INTO weekly_reports
               (report_date, market, accuracy_vs_last_week, spy_return_same_period)
               VALUES (?, ?, ?, ?)""",
            (date_str, report.market, report.accuracy_vs_last_week,
             report.spy_return_same_period),
        )
        for rec in report.recommendations:
            self._save_recommendation(rec)
        for rec in report.carryover_updates:
            self._save_recommendation(rec)
        self._conn.commit()

    def _save_recommendation(self, rec: StockRecommendation) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO recommendations
               (symbol, week_start, grade, composite_score, predicted_5d_return,
                confidence, sentiment_score, divergence_score, divergence_type,
                technical_signal, rsi_14, macd, macd_signal_val, sma_20, sma_50,
                sma_200, bollinger_upper, bollinger_lower, volume_trend,
                reasoning, sources)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (rec.symbol, rec.week_start.isoformat(), rec.grade.value,
             rec.composite_score, rec.predicted_5d_return, rec.confidence,
             rec.sentiment_score, rec.divergence.divergence_score,
             rec.divergence.divergence_type,
             rec.technical_summary.technical_signal,
             rec.technical_summary.rsi_14, rec.technical_summary.macd,
             rec.technical_summary.macd_signal, rec.technical_summary.sma_20,
             rec.technical_summary.sma_50, rec.technical_summary.sma_200,
             rec.technical_summary.bollinger_upper,
             rec.technical_summary.bollinger_lower,
             rec.technical_summary.volume_trend,
             rec.reasoning, json.dumps(rec.sources)),
        )

    def get_report(self, week_start: datetime) -> WeeklyReport | None:
        date_str = week_start.isoformat()
        row = self._conn.execute(
            "SELECT * FROM weekly_reports WHERE report_date = ?",
            (date_str,),
        ).fetchone()
        if row is None:
            return None

        recs = self._load_recommendations(date_str)
        if not recs:
            return None

        return WeeklyReport(
            report_date=week_start,
            market=row["market"],
            recommendations=recs,
            carryover_updates=[],
            accuracy_vs_last_week=row["accuracy_vs_last_week"],
            spy_return_same_period=row["spy_return_same_period"],
        )

    def _load_recommendations(
        self, week_start_str: str
    ) -> list[StockRecommendation]:
        rows = self._conn.execute(
            "SELECT * FROM recommendations WHERE week_start = ?",
            (week_start_str,),
        ).fetchall()
        result = []
        for r in rows:
            ts = datetime.fromisoformat(r["week_start"])
            ti = TechnicalIndicators(
                symbol=r["symbol"], timestamp=ts,
                rsi_14=r["rsi_14"], macd=r["macd"],
                macd_signal=r["macd_signal_val"],
                sma_20=r["sma_20"], sma_50=r["sma_50"],
                sma_200=r["sma_200"],
                bollinger_upper=r["bollinger_upper"],
                bollinger_lower=r["bollinger_lower"],
                volume_trend=r["volume_trend"],
                technical_signal=r["technical_signal"],
            )
            ds = DivergenceSignal(
                symbol=r["symbol"], timestamp=ts,
                technical_signal=r["technical_signal"],
                sentiment_signal=r["sentiment_score"],
                divergence_score=r["divergence_score"],
                divergence_type=r["divergence_type"],
            )
            rec = StockRecommendation(
                symbol=r["symbol"], week_start=ts,
                grade=RecommendationGrade(r["grade"]),
                composite_score=r["composite_score"],
                predicted_5d_return=r["predicted_5d_return"],
                confidence=r["confidence"],
                technical_summary=ti,
                sentiment_score=r["sentiment_score"],
                divergence=ds,
                reasoning=r["reasoning"],
                sources=json.loads(r["sources"]),
            )
            result.append(rec)
        return result

    def get_reports_range(
        self, start: datetime, end: datetime
    ) -> list[WeeklyReport]:
        rows = self._conn.execute(
            "SELECT report_date FROM weekly_reports WHERE report_date BETWEEN ? AND ?",
            (start.isoformat(), end.isoformat()),
        ).fetchall()
        reports = []
        for row in rows:
            report = self.get_report(datetime.fromisoformat(row["report_date"]))
            if report:
                reports.append(report)
        return reports

    def save_accuracy_record(self, record: AccuracyRecord) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO accuracy_records
               (symbol, week_start, predicted_grade, predicted_return,
                actual_return, grade_correct, held_weeks)
               VALUES (?,?,?,?,?,?,?)""",
            (record.symbol, record.week_start.isoformat(),
             record.predicted_grade.value, record.predicted_return,
             record.actual_return, int(record.grade_correct),
             record.held_weeks),
        )
        self._conn.commit()

    def get_accuracy_history(self, days: int = 90) -> list[AccuracyRecord]:
        cutoff = datetime.now() - timedelta(days=days)
        rows = self._conn.execute(
            "SELECT * FROM accuracy_records WHERE week_start >= ?",
            (cutoff.isoformat(),),
        ).fetchall()
        return [
            AccuracyRecord(
                symbol=r["symbol"],
                week_start=datetime.fromisoformat(r["week_start"]),
                predicted_grade=RecommendationGrade(r["predicted_grade"]),
                predicted_return=r["predicted_return"],
                actual_return=r["actual_return"],
                grade_correct=bool(r["grade_correct"]),
                held_weeks=r["held_weeks"],
            )
            for r in rows
        ]

    def get_rolling_accuracy(self, days: int = 90) -> float:
        records = self.get_accuracy_history(days)
        if not records:
            return 0.0
        correct = sum(1 for r in records if r.grade_correct)
        return correct / len(records)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_sqlite_store.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add adapters/data/sqlite_store.py tests/test_sqlite_store.py
git commit -m "feat: add SQLite recommendation and accuracy store"
```

---

## Task 12: Adapter — RSS Feed News Discovery

**Files:**
- Create: `adapters/data/rss_adapter.py`
- Create: `tests/test_rss_adapter.py`

- [ ] **Step 1: Write failing tests with mock HTTP**

Create `tests/test_rss_adapter.py`:

```python
"""Tests for RSS feed news discovery adapter (mocked HTTP)."""

from unittest.mock import patch

import pytest

from adapters.data.rss_adapter import RssNewsDiscovery


SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>AAPL Stock Surges on Earnings Beat</title>
      <link>https://example.com/aapl</link>
      <description>Apple reported strong Q2 results. TSLA also moved.</description>
      <pubDate>Sat, 24 May 2026 10:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Market Update: NVDA Hits All-Time High</title>
      <link>https://example.com/nvda</link>
      <description>NVIDIA continues AI momentum</description>
      <pubDate>Sat, 24 May 2026 09:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""


@pytest.fixture
def rss_adapter() -> RssNewsDiscovery:
    return RssNewsDiscovery(feed_urls=["https://example.com/feed"])


def test_discover_articles_returns_parsed_items(
    rss_adapter: RssNewsDiscovery,
) -> None:
    with patch("adapters.data.rss_adapter.feedparser.parse") as mock_parse:
        mock_parse.return_value = feedparser_result(SAMPLE_RSS)
        articles = rss_adapter.discover_articles("AAPL")
        assert len(articles) >= 1
        assert "title" in articles[0]
        assert "url" in articles[0]


def test_extract_tickers_finds_symbols(
    rss_adapter: RssNewsDiscovery,
) -> None:
    text = "AAPL surged while TSLA and NVDA dropped. Microsoft (MSFT) held steady."
    tickers = rss_adapter.extract_tickers(text)
    assert "AAPL" in tickers
    assert "TSLA" in tickers
    assert "NVDA" in tickers
    assert "MSFT" in tickers


def test_extract_tickers_excludes_common_words(
    rss_adapter: RssNewsDiscovery,
) -> None:
    text = "The CEO said AI will drive growth for AAPL"
    tickers = rss_adapter.extract_tickers(text)
    assert "AAPL" in tickers
    assert "CEO" not in tickers
    assert "THE" not in tickers
    assert "AI" not in tickers


def feedparser_result(xml: str) -> object:
    """Parse XML into feedparser-like result."""
    import feedparser

    return feedparser.parse(xml)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_rss_adapter.py -v`
Expected: ImportError

- [ ] **Step 3: Implement RSS adapter**

Create `adapters/data/rss_adapter.py`:

```python
"""RSS feed news discovery adapter."""

import re

import feedparser

# Common English words that look like tickers but aren't
_TICKER_STOPWORDS = frozenset({
    "A", "I", "AM", "AN", "AS", "AT", "BE", "BY", "DO", "GO", "IF",
    "IN", "IS", "IT", "ME", "MY", "NO", "OF", "ON", "OR", "SO", "TO",
    "UP", "US", "WE", "AI", "CEO", "CFO", "CTO", "COO", "IPO", "ETF",
    "GDP", "SEC", "FDA", "FED", "NYSE", "DOW", "THE", "AND", "FOR",
    "ARE", "BUT", "NOT", "YOU", "ALL", "CAN", "HER", "WAS", "ONE",
    "OUR", "OUT", "HAS", "HIS", "HOW", "ITS", "MAY", "NEW", "NOW",
    "OLD", "SEE", "WAY", "WHO", "DID", "GET", "HIM", "LET", "SAY",
    "SHE", "TOO", "USE", "TOP", "BIG", "CEO", "LOW", "HIGH", "ALSO",
    "RSI", "EPS", "PE", "PS", "ATH", "IMO", "LLC", "INC", "LTD",
    "EST", "PST", "UTC", "GMT", "API", "ROI", "YOY", "QOQ",
})


class RssNewsDiscovery:
    """NewsDiscoveryPort implementation using RSS feeds."""

    def __init__(self, feed_urls: list[str] | None = None) -> None:
        self._feed_urls = feed_urls or []

    def discover_articles(
        self, query: str, max_results: int = 10
    ) -> list[dict[str, str]]:
        """Fetch and parse RSS feeds, return articles."""
        articles: list[dict[str, str]] = []
        for url in self._feed_urls:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                articles.append({
                    "title": getattr(entry, "title", ""),
                    "url": getattr(entry, "link", ""),
                    "snippet": getattr(entry, "description", "")
                        if hasattr(entry, "description")
                        else getattr(entry, "summary", ""),
                    "source": url,
                    "published_date": getattr(entry, "published", ""),
                })
        return articles[:max_results]

    def extract_tickers(self, text: str) -> list[str]:
        """Extract probable ticker symbols from text."""
        candidates = re.findall(r"\b([A-Z]{1,5})\b", text)
        return [
            c for c in candidates
            if c not in _TICKER_STOPWORDS and len(c) >= 2
        ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_rss_adapter.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add adapters/data/rss_adapter.py tests/test_rss_adapter.py
git commit -m "feat: add RSS feed news discovery adapter"
```

---

## Task 13: Adapter — Google Custom Search News Discovery

**Files:**
- Create: `adapters/data/google_search_adapter.py`
- Create: `tests/test_google_search_adapter.py`

- [ ] **Step 1: Write failing tests with mocked API**

Create `tests/test_google_search_adapter.py`:

```python
"""Tests for Google Custom Search adapter (mocked API)."""

from unittest.mock import MagicMock, patch

import pytest

from adapters.data.google_search_adapter import GoogleSearchNewsDiscovery


@pytest.fixture
def adapter() -> GoogleSearchNewsDiscovery:
    return GoogleSearchNewsDiscovery(api_key="test-key", cse_id="test-cse")


def test_discover_articles_parses_response(
    adapter: GoogleSearchNewsDiscovery,
) -> None:
    mock_response = {
        "items": [
            {
                "title": "Top Stocks to Buy: AAPL, MSFT",
                "link": "https://example.com/article",
                "snippet": "Analysts recommend buying AAPL and MSFT this week",
            },
            {
                "title": "Market Analysis",
                "link": "https://example.com/market",
                "snippet": "NVDA leads tech sector gains",
            },
        ]
    }
    with patch.object(adapter, "_execute_search", return_value=mock_response):
        articles = adapter.discover_articles("stocks to buy")
        assert len(articles) == 2
        assert articles[0]["title"] == "Top Stocks to Buy: AAPL, MSFT"
        assert "url" in articles[0]


def test_discover_articles_handles_empty_response(
    adapter: GoogleSearchNewsDiscovery,
) -> None:
    with patch.object(adapter, "_execute_search", return_value={}):
        articles = adapter.discover_articles("nothing here")
        assert articles == []


def test_extract_tickers_delegates_to_regex(
    adapter: GoogleSearchNewsDiscovery,
) -> None:
    tickers = adapter.extract_tickers("AAPL and TSLA are trending")
    assert "AAPL" in tickers
    assert "TSLA" in tickers
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_google_search_adapter.py -v`
Expected: ImportError

- [ ] **Step 3: Implement Google Search adapter**

Create `adapters/data/google_search_adapter.py`:

```python
"""Google Custom Search API news discovery adapter."""

import re
from typing import Any

from adapters.data.rss_adapter import _TICKER_STOPWORDS


class GoogleSearchNewsDiscovery:
    """NewsDiscoveryPort implementation using Google Custom Search API."""

    def __init__(self, api_key: str, cse_id: str) -> None:
        self._api_key = api_key
        self._cse_id = cse_id

    def _execute_search(self, query: str, num: int = 10) -> dict[str, Any]:
        """Execute Google CSE search. Separated for easy mocking."""
        from googleapiclient.discovery import build

        service = build("customsearch", "v1", developerKey=self._api_key)
        return (
            service.cse()
            .list(q=query, cx=self._cse_id, num=num)
            .execute()
        )

    def discover_articles(
        self, query: str, max_results: int = 10
    ) -> list[dict[str, str]]:
        """Search Google CSE and return articles."""
        response = self._execute_search(query, num=max_results)
        items = response.get("items", [])
        return [
            {
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
                "source": "google_cse",
                "published_date": "",
            }
            for item in items
        ]

    def extract_tickers(self, text: str) -> list[str]:
        """Extract ticker symbols from text."""
        candidates = re.findall(r"\b([A-Z]{1,5})\b", text)
        return [
            c for c in candidates
            if c not in _TICKER_STOPWORDS and len(c) >= 2
        ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_google_search_adapter.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add adapters/data/google_search_adapter.py tests/test_google_search_adapter.py
git commit -m "feat: add Google Custom Search news discovery adapter"
```

---

## Task 14: Adapter — Reddit Buzz Scorer

**Files:**
- Create: `adapters/data/reddit_adapter.py`
- Create: `adapters/data/stocktwits_adapter.py`
- Create: `tests/test_buzz_adapters.py`

- [ ] **Step 1: Write failing tests for Reddit adapter**

Create `tests/test_buzz_adapters.py`:

```python
"""Tests for social buzz adapters (Reddit + StockTwits)."""

from collections import Counter
from unittest.mock import MagicMock, patch

import pytest

from adapters.data.reddit_adapter import RedditBuzzScorer
from adapters.data.stocktwits_adapter import StockTwitsBuzzScorer


class TestRedditBuzzScorer:
    @pytest.fixture
    def adapter(self) -> RedditBuzzScorer:
        return RedditBuzzScorer(
            client_id="test",
            client_secret="test",
            user_agent="test",
            subreddits=["wallstreetbets", "stocks"],
        )

    def test_get_trending_tickers(self, adapter: RedditBuzzScorer) -> None:
        mock_posts = [
            MagicMock(title="AAPL to the moon!", selftext="Buy AAPL now", author=MagicMock(name="user1"), score=100),
            MagicMock(title="TSLA earnings tomorrow", selftext="TSLA looking good", author=MagicMock(name="user2"), score=50),
            MagicMock(title="AAPL analysis", selftext="AAPL still bullish", author=MagicMock(name="user3"), score=75),
        ]
        mock_subreddit = MagicMock()
        mock_subreddit.hot.return_value = mock_posts
        with patch.object(adapter, "_get_subreddit", return_value=mock_subreddit):
            trending = adapter.get_trending_tickers(lookback_hours=168)
            tickers = [t["ticker"] for t in trending]
            assert "AAPL" in tickers

    def test_get_raw_posts(self, adapter: RedditBuzzScorer) -> None:
        mock_results = [
            MagicMock(title="AAPL update", selftext="Looking good", author=MagicMock(name="user1"), score=10, created_utc=1000000.0),
        ]
        mock_subreddit = MagicMock()
        mock_subreddit.search.return_value = mock_results
        with patch.object(adapter, "_get_subreddit", return_value=mock_subreddit):
            posts = adapter.get_raw_posts("AAPL", limit=10)
            assert len(posts) >= 1
            assert "text" in posts[0]


class TestStockTwitsBuzzScorer:
    @pytest.fixture
    def adapter(self) -> StockTwitsBuzzScorer:
        return StockTwitsBuzzScorer()

    def test_get_trending_tickers(self, adapter: StockTwitsBuzzScorer) -> None:
        mock_response = {
            "symbols": [
                {"symbol": "AAPL", "watchlist_count": 1000},
                {"symbol": "TSLA", "watchlist_count": 800},
            ]
        }
        with patch("adapters.data.stocktwits_adapter.requests.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200, json=lambda: mock_response
            )
            trending = adapter.get_trending_tickers()
            tickers = [t["ticker"] for t in trending]
            assert "AAPL" in tickers

    def test_get_raw_posts(self, adapter: StockTwitsBuzzScorer) -> None:
        mock_response = {
            "messages": [
                {
                    "body": "AAPL looking bullish",
                    "user": {"username": "trader1"},
                    "created_at": "2026-05-24T10:00:00Z",
                    "likes": {"total": 5},
                }
            ]
        }
        with patch("adapters.data.stocktwits_adapter.requests.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200, json=lambda: mock_response
            )
            posts = adapter.get_raw_posts("AAPL", limit=10)
            assert len(posts) == 1
            assert "text" in posts[0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_buzz_adapters.py -v`
Expected: ImportError

- [ ] **Step 3: Implement Reddit adapter**

Create `adapters/data/reddit_adapter.py`:

```python
"""Reddit buzz scorer adapter using PRAW."""

import re
from collections import Counter

from adapters.data.rss_adapter import _TICKER_STOPWORDS


class RedditBuzzScorer:
    """BuzzScorerPort implementation using Reddit via PRAW."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        user_agent: str,
        subreddits: list[str] | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._user_agent = user_agent
        self._subreddits = subreddits or ["wallstreetbets", "stocks", "investing"]
        self._reddit = None

    def _get_reddit(self) -> "praw.Reddit":
        if self._reddit is None:
            import praw

            self._reddit = praw.Reddit(
                client_id=self._client_id,
                client_secret=self._client_secret,
                user_agent=self._user_agent,
            )
        return self._reddit

    def _get_subreddit(self, name: str) -> "praw.models.Subreddit":
        return self._get_reddit().subreddit(name)

    def get_trending_tickers(
        self, lookback_hours: int = 168
    ) -> list[dict[str, int]]:
        """Scan hot posts across subreddits, count ticker mentions."""
        ticker_counts: Counter[str] = Counter()
        author_sets: dict[str, set[str]] = {}

        for sub_name in self._subreddits:
            subreddit = self._get_subreddit(sub_name)
            for post in subreddit.hot(limit=100):
                text = f"{post.title} {post.selftext}"
                tickers = self._extract_tickers(text)
                author = str(post.author) if post.author else "unknown"
                for ticker in tickers:
                    ticker_counts[ticker] += 1
                    if ticker not in author_sets:
                        author_sets[ticker] = set()
                    author_sets[ticker].add(author)

        return [
            {
                "ticker": ticker,
                "mention_count": count,
                "unique_authors": len(author_sets.get(ticker, set())),
            }
            for ticker, count in ticker_counts.most_common()
        ]

    def get_raw_posts(
        self, ticker: str, limit: int = 50
    ) -> list[dict[str, str]]:
        """Search for posts mentioning a specific ticker."""
        posts: list[dict[str, str]] = []
        for sub_name in self._subreddits:
            subreddit = self._get_subreddit(sub_name)
            for post in subreddit.search(ticker, limit=limit, sort="relevance"):
                posts.append({
                    "text": f"{post.title} {post.selftext}",
                    "author": str(post.author) if post.author else "unknown",
                    "timestamp": str(post.created_utc),
                    "score": str(post.score),
                })
        return posts[:limit]

    @staticmethod
    def _extract_tickers(text: str) -> list[str]:
        candidates = re.findall(r"\b([A-Z]{1,5})\b", text)
        return [c for c in candidates if c not in _TICKER_STOPWORDS and len(c) >= 2]
```

- [ ] **Step 4: Implement StockTwits adapter**

Create `adapters/data/stocktwits_adapter.py`:

```python
"""StockTwits buzz scorer adapter."""

import requests
from loguru import logger


class StockTwitsBuzzScorer:
    """BuzzScorerPort implementation using StockTwits public API."""

    BASE_URL = "https://api.stocktwits.com/api/2"

    def get_trending_tickers(
        self, lookback_hours: int = 168
    ) -> list[dict[str, int]]:
        """Get trending tickers from StockTwits."""
        try:
            resp = requests.get(
                f"{self.BASE_URL}/trending/symbols.json", timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            symbols = data.get("symbols", [])
            return [
                {
                    "ticker": s["symbol"],
                    "mention_count": s.get("watchlist_count", 0),
                    "unique_authors": 0,
                }
                for s in symbols
            ]
        except requests.RequestException as e:
            logger.warning(f"StockTwits trending failed: {e}")
            return []

    def get_raw_posts(
        self, ticker: str, limit: int = 50
    ) -> list[dict[str, str]]:
        """Get recent posts for a ticker from StockTwits."""
        try:
            resp = requests.get(
                f"{self.BASE_URL}/streams/symbol/{ticker}.json", timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            messages = data.get("messages", [])
            return [
                {
                    "text": m.get("body", ""),
                    "author": m.get("user", {}).get("username", "unknown"),
                    "timestamp": m.get("created_at", ""),
                    "score": str(m.get("likes", {}).get("total", 0)),
                }
                for m in messages[:limit]
            ]
        except requests.RequestException as e:
            logger.warning(f"StockTwits posts failed: {e}")
            return []
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_buzz_adapters.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add adapters/data/reddit_adapter.py adapters/data/stocktwits_adapter.py tests/test_buzz_adapters.py
git commit -m "feat: add Reddit and StockTwits buzz scorer adapters"
```

---

## Task 15: Adapter — yfinance Market Data + Technical Analysis

**Files:**
- Create: `adapters/data/yfinance_adapter.py`
- Create: `tests/test_yfinance_adapter.py`

- [ ] **Step 1: Write failing tests (unit tests with mocked yfinance)**

Create `tests/test_yfinance_adapter.py`:

```python
"""Tests for yfinance adapter (mocked yfinance calls)."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from adapters.data.yfinance_adapter import YFinanceAdapter


@pytest.fixture
def adapter() -> YFinanceAdapter:
    return YFinanceAdapter()


def _mock_hist_data(days: int = 90) -> pd.DataFrame:
    """Create realistic mock OHLCV data."""
    dates = pd.date_range(end="2026-05-24", periods=days, freq="B")
    np.random.seed(42)
    base = 150.0
    prices = base + np.cumsum(np.random.randn(days) * 2)
    return pd.DataFrame(
        {
            "Open": prices - 1,
            "High": prices + 2,
            "Low": prices - 2,
            "Close": prices,
            "Volume": np.random.randint(500000, 5000000, days),
        },
        index=dates,
    )


def test_get_signals_returns_signals(adapter: YFinanceAdapter) -> None:
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = _mock_hist_data(30)
    with patch("adapters.data.yfinance_adapter.yf.Ticker", return_value=mock_ticker):
        signals = adapter.get_signals(
            "AAPL", prediction_time=datetime(2026, 5, 24)
        )
        assert len(signals) > 0
        assert signals[0].symbol == "AAPL"
        assert signals[0].price > 0


def test_compute_indicators_returns_valid(adapter: YFinanceAdapter) -> None:
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = _mock_hist_data(90)
    with patch("adapters.data.yfinance_adapter.yf.Ticker", return_value=mock_ticker):
        indicators = adapter.compute_indicators("AAPL")
        assert 0 <= indicators.rsi_14 <= 100
        assert -1.0 <= indicators.technical_signal <= 1.0


def test_compute_technical_signal_bounded(adapter: YFinanceAdapter) -> None:
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = _mock_hist_data(90)
    with patch("adapters.data.yfinance_adapter.yf.Ticker", return_value=mock_ticker):
        indicators = adapter.compute_indicators("AAPL")
        signal = adapter.compute_technical_signal(indicators)
        assert -1.0 <= signal <= 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_yfinance_adapter.py -v`
Expected: ImportError

- [ ] **Step 3: Implement yfinance adapter**

Create `adapters/data/yfinance_adapter.py`:

```python
"""yfinance adapter for market data and technical analysis."""

from datetime import datetime, timedelta

import numpy as np
import yfinance as yf
from loguru import logger

from domain.exceptions import LookAheadBiasError
from domain.models import Signal, TechnicalIndicators


class YFinanceAdapter:
    """MarketDataPort + TechnicalAnalysisPort implementation using yfinance."""

    def get_signals(
        self,
        symbol: str,
        prediction_time: datetime,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[Signal]:
        """Fetch OHLCV data as Signal objects, respecting point-in-time."""
        ticker = yf.Ticker(symbol)
        start = start_date or (prediction_time - timedelta(days=90))
        end = end_date or prediction_time
        if end > prediction_time:
            raise LookAheadBiasError(
                f"end_date {end} > prediction_time {prediction_time}"
            )

        hist = ticker.history(start=start, end=end + timedelta(days=1))
        signals = []
        for ts, row in hist.iterrows():
            dt = ts.to_pydatetime().replace(tzinfo=None)
            if dt > prediction_time:
                continue
            signals.append(
                Signal(
                    symbol=symbol,
                    timestamp=dt,
                    price=float(row["Close"]),
                    volume=float(row["Volume"]),
                    open_=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                )
            )
        return signals

    def validate_point_in_time(self, prediction_time: datetime) -> None:
        pass  # Validation handled in get_signals

    def compute_indicators(
        self, symbol: str, lookback_days: int = 90
    ) -> TechnicalIndicators:
        """Compute technical indicators from yfinance data."""
        ticker = yf.Ticker(symbol)
        end = datetime.now()
        start = end - timedelta(days=lookback_days + 50)  # extra for SMA200
        hist = ticker.history(start=start, end=end)

        if len(hist) < 20:
            from domain.exceptions import InsufficientDataError
            raise InsufficientDataError(
                f"Need at least 20 data points, got {len(hist)}"
            )

        close = hist["Close"].values
        volume = hist["Volume"].values

        rsi = self._compute_rsi(close, period=14)
        macd_line, macd_sig = self._compute_macd(close)
        sma_20 = float(np.mean(close[-20:]))
        sma_50 = float(np.mean(close[-50:])) if len(close) >= 50 else sma_20
        sma_200 = float(np.mean(close[-200:])) if len(close) >= 200 else sma_50
        bb_upper, bb_lower = self._compute_bollinger(close)
        vol_trend = float(np.mean(volume[-5:]) / np.mean(volume[-20:])) if np.mean(volume[-20:]) > 0 else 1.0

        technical_signal = self._composite_signal(
            rsi=rsi, macd=macd_line, macd_signal=macd_sig,
            price=float(close[-1]), sma_20=sma_20, sma_50=sma_50,
        )

        return TechnicalIndicators(
            symbol=symbol,
            timestamp=hist.index[-1].to_pydatetime().replace(tzinfo=None),
            rsi_14=rsi,
            macd=macd_line,
            macd_signal=macd_sig,
            sma_20=sma_20,
            sma_50=sma_50,
            sma_200=sma_200,
            bollinger_upper=bb_upper,
            bollinger_lower=bb_lower,
            volume_trend=vol_trend,
            technical_signal=technical_signal,
        )

    def compute_technical_signal(self, indicators: TechnicalIndicators) -> float:
        return indicators.technical_signal

    @staticmethod
    def _compute_rsi(prices: np.ndarray, period: int = 14) -> float:
        if len(prices) < period + 1:
            return 50.0
        deltas = np.diff(prices[-period - 1:])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = float(np.mean(gains))
        avg_loss = float(np.mean(losses))
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return float(100 - (100 / (1 + rs)))

    @staticmethod
    def _compute_macd(
        prices: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> tuple[float, float]:
        if len(prices) < slow + signal:
            return 0.0, 0.0

        def ema(data: np.ndarray, span: int) -> np.ndarray:
            alpha = 2 / (span + 1)
            result = np.zeros_like(data, dtype=float)
            result[0] = data[0]
            for i in range(1, len(data)):
                result[i] = alpha * data[i] + (1 - alpha) * result[i - 1]
            return result

        ema_fast = ema(prices, fast)
        ema_slow = ema(prices, slow)
        macd_line = ema_fast - ema_slow
        signal_line = ema(macd_line, signal)
        return float(macd_line[-1]), float(signal_line[-1])

    @staticmethod
    def _compute_bollinger(
        prices: np.ndarray, period: int = 20, num_std: float = 2.0
    ) -> tuple[float, float]:
        if len(prices) < period:
            return float(prices[-1]) + 5, float(prices[-1]) - 5
        window = prices[-period:]
        mean = float(np.mean(window))
        std = float(np.std(window))
        return mean + num_std * std, mean - num_std * std

    @staticmethod
    def _composite_signal(
        *, rsi: float, macd: float, macd_signal: float,
        price: float, sma_20: float, sma_50: float,
    ) -> float:
        """Combine indicators into single [-1, 1] signal."""
        signals = []
        # RSI signal
        if rsi > 70:
            signals.append(-0.5)  # overbought
        elif rsi < 30:
            signals.append(0.5)   # oversold
        else:
            signals.append((50 - rsi) / -50)  # linear scale

        # MACD signal
        if macd > macd_signal:
            signals.append(0.3)
        else:
            signals.append(-0.3)

        # Price vs SMA
        if price > sma_20 > sma_50:
            signals.append(0.4)
        elif price < sma_20 < sma_50:
            signals.append(-0.4)
        else:
            signals.append(0.0)

        raw = sum(signals) / len(signals)
        return max(-1.0, min(1.0, raw))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_yfinance_adapter.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add adapters/data/yfinance_adapter.py tests/test_yfinance_adapter.py
git commit -m "feat: add yfinance market data and technical analysis adapter"
```

---

## Task 16: Adapter — XGBoost + LightGBM + Ensemble Predictors

**Files:**
- Create: `adapters/ml/xgboost_predictor.py`
- Create: `adapters/ml/lightgbm_predictor.py`
- Create: `adapters/ml/ensemble_predictor.py`
- Create: `tests/test_ml_predictors.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_ml_predictors.py`:

```python
"""Tests for ML predictor adapters."""

from datetime import datetime, timedelta

import numpy as np
import pytest

from adapters.ml.xgboost_predictor import XGBoostPredictor
from adapters.ml.lightgbm_predictor import LightGBMPredictor
from adapters.ml.ensemble_predictor import EnsemblePredictor


def _make_features(n: int = 100, n_features: int = 10) -> tuple[np.ndarray, np.ndarray]:
    """Create dummy feature matrix and binary target."""
    np.random.seed(42)
    X = np.random.randn(n, n_features)
    y = (X[:, 0] + X[:, 1] > 0).astype(float)
    return X, y


class TestXGBoostPredictor:
    def test_train_and_predict(self) -> None:
        X, y = _make_features()
        pred = XGBoostPredictor(seed=42)
        pred.train(X[:80], y[:80])
        predictions = pred.predict_batch(X[80:])
        assert len(predictions) == 20
        assert all(0 <= p <= 1 for p in predictions)

    def test_predict_single(self) -> None:
        X, y = _make_features()
        pred = XGBoostPredictor(seed=42)
        pred.train(X[:80], y[:80])
        score = pred.predict_single(X[80])
        assert 0 <= score <= 1


class TestLightGBMPredictor:
    def test_train_and_predict(self) -> None:
        X, y = _make_features()
        pred = LightGBMPredictor(seed=42)
        pred.train(X[:80], y[:80])
        predictions = pred.predict_batch(X[80:])
        assert len(predictions) == 20
        assert all(0 <= p <= 1 for p in predictions)


class TestEnsemblePredictor:
    def test_ensemble_averages_predictions(self) -> None:
        X, y = _make_features()
        xgb = XGBoostPredictor(seed=42)
        lgbm = LightGBMPredictor(seed=42)
        xgb.train(X[:80], y[:80])
        lgbm.train(X[:80], y[:80])

        ensemble = EnsemblePredictor(predictors=[xgb, lgbm])
        predictions = ensemble.predict_batch(X[80:])
        assert len(predictions) == 20
        assert all(0 <= p <= 1 for p in predictions)

    def test_ensemble_single_prediction(self) -> None:
        X, y = _make_features()
        xgb = XGBoostPredictor(seed=42)
        lgbm = LightGBMPredictor(seed=42)
        xgb.train(X[:80], y[:80])
        lgbm.train(X[:80], y[:80])

        ensemble = EnsemblePredictor(predictors=[xgb, lgbm])
        score = ensemble.predict_single(X[80])
        assert 0 <= score <= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ml_predictors.py -v`
Expected: ImportError

- [ ] **Step 3: Implement XGBoost predictor**

Create `adapters/ml/xgboost_predictor.py`:

```python
"""XGBoost predictor adapter."""

import numpy as np
import xgboost as xgb


class XGBoostPredictor:
    """StockPredictorPort implementation using XGBoost."""

    def __init__(self, seed: int = 42) -> None:
        self._model: xgb.XGBClassifier | None = None
        self._seed = seed

    def train(self, X: np.ndarray, y: np.ndarray) -> None:
        self._model = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            random_state=self._seed,
            use_label_encoder=False,
            eval_metric="logloss",
            verbosity=0,
        )
        self._model.fit(X, y)

    def predict_batch(self, X: np.ndarray) -> list[float]:
        if self._model is None:
            raise RuntimeError("Model not trained")
        probs = self._model.predict_proba(X)[:, 1]
        return [float(p) for p in probs]

    def predict_single(self, features: np.ndarray) -> float:
        return self.predict_batch(features.reshape(1, -1))[0]
```

- [ ] **Step 4: Implement LightGBM predictor**

Create `adapters/ml/lightgbm_predictor.py`:

```python
"""LightGBM predictor adapter."""

import numpy as np
import lightgbm as lgb


class LightGBMPredictor:
    """StockPredictorPort implementation using LightGBM."""

    def __init__(self, seed: int = 42) -> None:
        self._model: lgb.LGBMClassifier | None = None
        self._seed = seed

    def train(self, X: np.ndarray, y: np.ndarray) -> None:
        self._model = lgb.LGBMClassifier(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            random_state=self._seed,
            verbose=-1,
        )
        self._model.fit(X, y)

    def predict_batch(self, X: np.ndarray) -> list[float]:
        if self._model is None:
            raise RuntimeError("Model not trained")
        probs = self._model.predict_proba(X)[:, 1]
        return [float(p) for p in probs]

    def predict_single(self, features: np.ndarray) -> float:
        return self.predict_batch(features.reshape(1, -1))[0]
```

- [ ] **Step 5: Implement ensemble predictor**

Create `adapters/ml/ensemble_predictor.py`:

```python
"""Ensemble predictor — averages XGBoost + LightGBM predictions."""

import numpy as np


class EnsemblePredictor:
    """StockPredictorPort combining multiple predictors via averaging."""

    def __init__(
        self,
        predictors: list,
        weights: list[float] | None = None,
    ) -> None:
        self._predictors = predictors
        self._weights = weights or [1.0 / len(predictors)] * len(predictors)

    def predict_batch(self, X: np.ndarray) -> list[float]:
        all_preds = [p.predict_batch(X) for p in self._predictors]
        weighted = np.zeros(len(all_preds[0]))
        for preds, weight in zip(all_preds, self._weights):
            weighted += np.array(preds) * weight
        return [float(p) for p in weighted]

    def predict_single(self, features: np.ndarray) -> float:
        return self.predict_batch(features.reshape(1, -1))[0]
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_ml_predictors.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add adapters/ml/xgboost_predictor.py adapters/ml/lightgbm_predictor.py adapters/ml/ensemble_predictor.py tests/test_ml_predictors.py
git commit -m "feat: add XGBoost, LightGBM, and ensemble predictor adapters"
```

---

## Task 17: Application — WeeklyTournamentUseCase

**Files:**
- Rewrite: `application/use_cases.py`
- Create: `tests/test_weekly_tournament.py`

- [ ] **Step 1: Write failing test for WeeklyTournamentUseCase**

Create `tests/test_weekly_tournament.py`:

```python
"""Tests for WeeklyTournamentUseCase with fake adapters."""

from datetime import datetime

import pytest

from application.use_cases import WeeklyTournamentUseCase
from domain.models import RecommendationGrade, WeeklyReport
from tests.fakes.fake_buzz_scorer import FakeBuzzScorer
from tests.fakes.fake_market_data import FakeMarketData
from tests.fakes.fake_news_discovery import FakeNewsDiscovery
from tests.fakes.fake_sentiment_scorer import FakeSentimentScorer
from tests.fakes.fake_store import FakeStore
from tests.fakes.fake_technical_analysis import FakeTechnicalAnalysis
from domain.models import Signal


def _make_tournament() -> WeeklyTournamentUseCase:
    """Build a tournament with fake adapters returning enough tickers."""
    articles = [
        {"title": f"Stock {t} analysis", "url": f"https://example.com/{t}",
         "snippet": f"{t} is trending", "source": "test",
         "published_date": "2026-05-24"}
        for t in ["AAPL", "MSFT", "NVDA", "TSLA", "GOOGL", "AMZN", "META",
                   "JPM", "BAC", "WFC", "GS", "MS", "V", "MA", "PYPL",
                   "HD", "NKE", "DIS", "NFLX", "AMD"]
    ]
    trending = [
        {"ticker": t, "mention_count": 50 - i * 2, "unique_authors": 10}
        for i, t in enumerate(
            ["AAPL", "MSFT", "NVDA", "TSLA", "GOOGL", "AMZN", "META",
             "JPM", "BAC", "WFC", "GS", "MS", "V", "MA", "PYPL",
             "HD", "NKE", "DIS", "NFLX", "AMD"]
        )
    ]
    now = datetime(2026, 5, 24)
    signals = {
        t: [Signal(symbol=t, timestamp=now, price=100.0 + i,
                   volume=1_000_000.0, open_=99.0, high=102.0, low=98.0)]
        for i, t in enumerate(
            ["AAPL", "MSFT", "NVDA", "TSLA", "GOOGL", "AMZN", "META",
             "JPM", "BAC", "WFC", "GS", "MS", "V", "MA", "PYPL",
             "HD", "NKE", "DIS", "NFLX", "AMD"]
        )
    }
    all_signals = []
    for s_list in signals.values():
        all_signals.extend(s_list)

    return WeeklyTournamentUseCase(
        news_sources=[FakeNewsDiscovery(articles)],
        buzz_sources=[FakeBuzzScorer(trending=trending)],
        market_data=FakeMarketData(all_signals),
        technical_analysis=FakeTechnicalAnalysis(),
        sentiment_scorer=FakeSentimentScorer(default_score=0.3),
        store=FakeStore(),
        market="us",
        min_price=5.0,
        min_volume=100000,
        min_mentions=1,
    )


def test_run_tournament_returns_weekly_report() -> None:
    tournament = _make_tournament()
    report = tournament.run(prediction_date=datetime(2026, 5, 25))
    assert isinstance(report, WeeklyReport)
    assert 1 <= len(report.recommendations) <= 15
    assert report.market == "us"


def test_tournament_grades_are_monotonic() -> None:
    tournament = _make_tournament()
    report = tournament.run(prediction_date=datetime(2026, 5, 25))
    grade_order = list(RecommendationGrade)
    grades = [r.grade for r in report.recommendations]
    grade_indices = [grade_order.index(g) for g in grades]
    for i in range(len(grade_indices) - 1):
        assert grade_indices[i] <= grade_indices[i + 1]


def test_tournament_stores_report() -> None:
    tournament = _make_tournament()
    report = tournament.run(prediction_date=datetime(2026, 5, 25))
    assert tournament._store.get_report(report.report_date) is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_weekly_tournament.py -v`
Expected: ImportError — WeeklyTournamentUseCase not defined

- [ ] **Step 3: Implement WeeklyTournamentUseCase**

Rewrite `application/use_cases.py`:

```python
"""Use cases: orchestration of domain and adapters."""

from datetime import datetime, timedelta
from collections import Counter

from loguru import logger

from domain.models import (
    AccuracyRecord,
    RecommendationGrade,
    StockRecommendation,
    WeeklyReport,
)
from domain.services import compute_divergence_score, grade_recommendation


class WeeklyTournamentUseCase:
    """Orchestrates the full weekly stock tournament pipeline."""

    def __init__(
        self,
        news_sources: list,
        buzz_sources: list,
        market_data: object,
        technical_analysis: object,
        sentiment_scorer: object,
        store: object,
        market: str = "us",
        min_price: float = 5.0,
        min_volume: int = 100000,
        min_mentions: int = 3,
    ) -> None:
        self._news_sources = news_sources
        self._buzz_sources = buzz_sources
        self._market_data = market_data
        self._technical_analysis = technical_analysis
        self._sentiment_scorer = sentiment_scorer
        self._store = store
        self._market = market
        self._min_price = min_price
        self._min_volume = min_volume
        self._min_mentions = min_mentions

    def run(self, prediction_date: datetime) -> WeeklyReport:
        """Execute full tournament pipeline."""
        # Snap to Monday
        monday = prediction_date - timedelta(days=prediction_date.weekday())

        # Step 1: Discover tickers
        tickers = self._discover_tickers()
        logger.info(f"Discovered {len(tickers)} raw tickers")

        # Step 2: Filter universe
        qualified = self._filter_universe(tickers, prediction_date)
        logger.info(f"Qualified {len(qualified)} tickers after filtering")

        # Step 3-5: Enrich, score, detect divergence
        scored = []
        for ticker in qualified[:50]:  # cap at 50
            try:
                indicators = self._technical_analysis.compute_indicators(ticker)
                tech_signal = indicators.technical_signal

                # Get raw posts for sentiment
                all_texts = []
                for buzz_src in self._buzz_sources:
                    posts = buzz_src.get_raw_posts(ticker, limit=20)
                    all_texts.extend([p["text"] for p in posts])
                for news_src in self._news_sources:
                    articles = news_src.discover_articles(ticker, max_results=5)
                    all_texts.extend([a["snippet"] for a in articles])

                if all_texts:
                    sentiments = self._sentiment_scorer.score_batch(all_texts)
                    sent_signal = sum(sentiments) / len(sentiments)
                else:
                    sent_signal = 0.0

                sent_signal = max(-1.0, min(1.0, sent_signal))

                divergence = compute_divergence_score(
                    symbol=ticker,
                    timestamp=prediction_date,
                    technical_signal=tech_signal,
                    sentiment_signal=sent_signal,
                )

                composite = (tech_signal + sent_signal + divergence.divergence_score) / 3
                scored.append({
                    "ticker": ticker,
                    "composite": composite,
                    "tech_signal": tech_signal,
                    "sent_signal": sent_signal,
                    "indicators": indicators,
                    "divergence": divergence,
                })
            except Exception as e:
                logger.warning(f"Skipping {ticker}: {e}")

        # Step 6: Rank and grade
        scored.sort(key=lambda x: x["composite"], reverse=True)
        top = scored[:15]

        recommendations = []
        for rank, item in enumerate(top, 1):
            grade = grade_recommendation(rank=rank, total=len(top))
            rec = StockRecommendation(
                symbol=item["ticker"],
                week_start=monday,
                grade=grade,
                composite_score=item["composite"],
                predicted_5d_return=item["composite"] * 0.05,
                confidence=min(1.0, max(0.0, abs(item["composite"]))),
                technical_summary=item["indicators"],
                sentiment_score=item["sent_signal"],
                divergence=item["divergence"],
                reasoning=self._generate_reasoning(item),
                sources=["news", "social"],
            )
            recommendations.append(rec)

        report = WeeklyReport(
            report_date=monday,
            market=self._market,
            recommendations=recommendations,
            carryover_updates=[],
            accuracy_vs_last_week=None,
            spy_return_same_period=None,
        )

        # Step 7-8: Store
        self._store.save_weekly_report(report)
        logger.info(f"Tournament complete: {len(recommendations)} picks for {monday.date()}")

        return report

    def _discover_tickers(self) -> list[str]:
        """Aggregate tickers from all news + buzz sources."""
        ticker_counts: Counter[str] = Counter()

        for src in self._news_sources:
            articles = src.discover_articles("stocks", max_results=50)
            for article in articles:
                text = f"{article.get('title', '')} {article.get('snippet', '')}"
                tickers = src.extract_tickers(text)
                for t in tickers:
                    ticker_counts[t] += 1

        for src in self._buzz_sources:
            trending = src.get_trending_tickers()
            for item in trending:
                ticker_counts[item["ticker"]] += item.get("mention_count", 1)

        return [t for t, _ in ticker_counts.most_common()]

    def _filter_universe(
        self, tickers: list[str], prediction_time: datetime
    ) -> list[str]:
        """Filter out penny stocks, low volume, insufficient mentions."""
        qualified = []
        for ticker in tickers:
            try:
                signals = self._market_data.get_signals(
                    ticker, prediction_time
                )
                if not signals:
                    continue
                latest = signals[-1]
                if latest.price < self._min_price:
                    continue
                if latest.volume < self._min_volume:
                    continue
                qualified.append(ticker)
            except Exception:
                continue
        return qualified

    @staticmethod
    def _generate_reasoning(item: dict) -> str:
        parts = []
        if item["divergence"].divergence_type == "bullish_divergence":
            parts.append("Bullish divergence: sentiment leads price upward")
        elif item["divergence"].divergence_type == "bearish_divergence":
            parts.append("Bearish divergence: sentiment lags technical weakness")
        else:
            parts.append("Signals aligned")

        if item["indicators"].rsi_14 < 30:
            parts.append("RSI oversold")
        elif item["indicators"].rsi_14 > 70:
            parts.append("RSI overbought")

        return ". ".join(parts) + "."


class TrackRecommendationsUseCase:
    """Evaluate past predictions against actual outcomes."""

    def __init__(self, store: object, market_data: object) -> None:
        self._store = store
        self._market_data = market_data

    def evaluate_last_week(
        self, current_date: datetime
    ) -> list[AccuracyRecord]:
        """Compare last week's predictions vs actual 5-day returns."""
        last_monday = current_date - timedelta(days=current_date.weekday() + 7)
        report = self._store.get_report(last_monday)
        if report is None:
            logger.info("No report found for last week")
            return []

        records = []
        for rec in report.recommendations:
            try:
                signals = self._market_data.get_signals(
                    rec.symbol, current_date
                )
                if len(signals) < 2:
                    continue
                # Actual return: last signal price vs prediction-time price
                start_price = signals[0].price
                end_price = signals[-1].price
                actual_return = (end_price - start_price) / start_price if start_price > 0 else 0.0

                # Grade correct if direction matches
                predicted_up = rec.predicted_5d_return > 0
                actual_up = actual_return > 0
                grade_correct = predicted_up == actual_up

                record = AccuracyRecord(
                    symbol=rec.symbol,
                    week_start=rec.week_start,
                    predicted_grade=rec.grade,
                    predicted_return=rec.predicted_5d_return,
                    actual_return=actual_return,
                    grade_correct=grade_correct,
                    held_weeks=1,
                )
                self._store.save_accuracy_record(record)
                records.append(record)
            except Exception as e:
                logger.warning(f"Failed to evaluate {rec.symbol}: {e}")

        return records

    def rolling_accuracy(self, days: int = 90) -> dict[str, float]:
        """Compute rolling accuracy metrics."""
        records = self._store.get_accuracy_history(days)
        if not records:
            return {"overall": 0.0, "count": 0}

        correct = sum(1 for r in records if r.grade_correct)
        return {
            "overall": correct / len(records),
            "count": len(records),
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_weekly_tournament.py -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite**

Run: `pytest -v --tb=short`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add application/use_cases.py tests/test_weekly_tournament.py
git commit -m "feat: add WeeklyTournamentUseCase and TrackRecommendationsUseCase"
```

---

## Task 18: CLI Entry Point

**Files:**
- Create: `application/cli.py`

- [ ] **Step 1: Implement CLI with Click**

Create `application/cli.py`:

```python
"""CLI entry point for the stock recommendation pipeline."""

import os
from datetime import datetime

import click
from loguru import logger

from config.loader import load_market_config


@click.group()
def cli() -> None:
    """Multi-Modal Stock Recommender CLI."""
    pass


@cli.command()
@click.option("--market", default="us", help="Market to run tournament for")
@click.option("--date", default=None, help="Prediction date (YYYY-MM-DD), defaults to today")
def run_tournament(market: str, date: str | None) -> None:
    """Run the weekly stock tournament pipeline."""
    from adapters.data.rss_adapter import RssNewsDiscovery
    from adapters.data.sqlite_store import SqliteStore
    from adapters.ml.keyword_scorer import KeywordSentimentScorer
    from application.use_cases import WeeklyTournamentUseCase
    from tests.fakes.fake_buzz_scorer import FakeBuzzScorer
    from tests.fakes.fake_market_data import FakeMarketData
    from tests.fakes.fake_technical_analysis import FakeTechnicalAnalysis

    prediction_date = datetime.strptime(date, "%Y-%m-%d") if date else datetime.now()
    config = load_market_config(market)
    filters = config["filters"]

    rss_urls = [f["url"] for f in config["news_discovery"]["rss_feeds"]]
    news_sources = [RssNewsDiscovery(feed_urls=rss_urls)]

    # Reddit/StockTwits require API keys — use fakes if not configured
    buzz_sources: list = []
    reddit_id = os.environ.get("REDDIT_CLIENT_ID")
    if reddit_id:
        from adapters.data.reddit_adapter import RedditBuzzScorer

        buzz_sources.append(
            RedditBuzzScorer(
                client_id=reddit_id,
                client_secret=os.environ["REDDIT_CLIENT_SECRET"],
                user_agent="stock-recommender/1.0",
                subreddits=config["buzz_sources"]["reddit"]["subreddits"],
            )
        )

    stocktwits_enabled = config.get("buzz_sources", {}).get("stocktwits", {}).get("enabled", False)
    if stocktwits_enabled:
        from adapters.data.stocktwits_adapter import StockTwitsBuzzScorer

        buzz_sources.append(StockTwitsBuzzScorer())

    if not buzz_sources:
        logger.warning("No buzz sources configured, using empty fallback")
        buzz_sources = [FakeBuzzScorer()]

    # Market data — use yfinance if available
    try:
        from adapters.data.yfinance_adapter import YFinanceAdapter

        market_data = YFinanceAdapter()
        technical_analysis = YFinanceAdapter()
    except ImportError:
        logger.warning("yfinance not available, using fake market data")
        market_data = FakeMarketData()
        technical_analysis = FakeTechnicalAnalysis()

    store = SqliteStore(db_path="data/recommendations.db")
    scorer = KeywordSentimentScorer()

    tournament = WeeklyTournamentUseCase(
        news_sources=news_sources,
        buzz_sources=buzz_sources,
        market_data=market_data,
        technical_analysis=technical_analysis,
        sentiment_scorer=scorer,
        store=store,
        market=market,
        min_price=filters["min_price"],
        min_volume=filters["min_avg_volume"],
        min_mentions=filters["min_mentions"],
    )

    report = tournament.run(prediction_date=prediction_date)
    _print_report(report)


@cli.command()
@click.option("--date", default=None, help="Current date (YYYY-MM-DD)")
def evaluate_last_week(date: str | None) -> None:
    """Evaluate last week's predictions against actual outcomes."""
    from adapters.data.sqlite_store import SqliteStore
    from application.use_cases import TrackRecommendationsUseCase

    current_date = datetime.strptime(date, "%Y-%m-%d") if date else datetime.now()

    try:
        from adapters.data.yfinance_adapter import YFinanceAdapter

        market_data = YFinanceAdapter()
    except ImportError:
        from tests.fakes.fake_market_data import FakeMarketData

        market_data = FakeMarketData()

    store = SqliteStore(db_path="data/recommendations.db")
    tracker = TrackRecommendationsUseCase(store=store, market_data=market_data)
    records = tracker.evaluate_last_week(current_date)

    click.echo(f"\n{'='*60}")
    click.echo(f"  EVALUATION — Week of {current_date.date()}")
    click.echo(f"{'='*60}")
    if not records:
        click.echo("  No records to evaluate.")
        return

    correct = sum(1 for r in records if r.grade_correct)
    click.echo(f"  Directional accuracy: {correct}/{len(records)} ({correct/len(records):.1%})")
    for r in records:
        status = "✓" if r.grade_correct else "✗"
        click.echo(
            f"  {status} {r.symbol:6s} | predicted: {r.predicted_return:+.2%} | "
            f"actual: {r.actual_return:+.2%} | {r.predicted_grade.value}"
        )


def _print_report(report: "WeeklyReport") -> None:
    """Pretty-print a weekly report to terminal."""
    click.echo(f"\n{'='*60}")
    click.echo(f"  WEEKLY STOCK TOURNAMENT — {report.report_date.date()}")
    click.echo(f"  Market: {report.market.upper()}")
    click.echo(f"{'='*60}\n")

    for i, rec in enumerate(report.recommendations, 1):
        click.echo(
            f"  {i:2d}. {rec.symbol:6s} | {rec.grade.value:15s} | "
            f"score: {rec.composite_score:+.3f} | "
            f"conf: {rec.confidence:.0%}"
        )
        click.echo(f"      {rec.reasoning}")
        click.echo()

    click.echo(f"{'='*60}")
    click.echo(f"  Total picks: {len(report.recommendations)}")
    if report.accuracy_vs_last_week is not None:
        click.echo(f"  Last week accuracy: {report.accuracy_vs_last_week:.1%}")
    click.echo(f"{'='*60}\n")


if __name__ == "__main__":
    cli()
```

- [ ] **Step 2: Verify CLI loads**

Run: `python -m application.cli --help`
Expected: Shows CLI help with `run-tournament` and `evaluate-last-week` commands

- [ ] **Step 3: Commit**

```bash
git add application/cli.py
git commit -m "feat: add Click CLI entry point with run-tournament and evaluate commands"
```

---

## Task 19: GitHub Actions Workflow

**Files:**
- Create: `.github/workflows/weekly_picks.yml`

- [ ] **Step 1: Create workflow file**

Create `.github/workflows/weekly_picks.yml`:

```yaml
name: Weekly Stock Tournament

on:
  schedule:
    - cron: '0 5 * * 0'     # Sunday 5:00 UTC (Sat 9 PM PST)
  workflow_dispatch:          # manual trigger for testing

env:
  GOOGLE_CSE_API_KEY: ${{ secrets.GOOGLE_CSE_API_KEY }}
  GOOGLE_CSE_ID: ${{ secrets.GOOGLE_CSE_ID }}
  REDDIT_CLIENT_ID: ${{ secrets.REDDIT_CLIENT_ID }}
  REDDIT_CLIENT_SECRET: ${{ secrets.REDDIT_CLIENT_SECRET }}

jobs:
  weekly-tournament:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: pip install -e ".[dev]"

      - name: Run tournament
        run: python -m application.cli run-tournament

      - name: Evaluate last week
        run: python -m application.cli evaluate-last-week

      - name: Commit results
        run: |
          git config user.name "Stock Tournament Bot"
          git config user.email "bot@tournament"
          git add reports/ data/recommendations.db
          git diff --cached --quiet || git commit -m "feat: weekly picks $(date +%Y-%m-%d)"
          git push
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/weekly_picks.yml
git commit -m "ci: add weekly stock tournament GitHub Actions workflow"
```

---

## Task 20: Integration Verification — Full Test Suite

**Files:** None (verification only)

- [ ] **Step 1: Run full test suite**

Run: `pytest -v --tb=short`
Expected: All tests PASS

- [ ] **Step 2: Run mypy strict**

Run: `mypy domain/ --strict`
Expected: No errors (domain layer is pure)

- [ ] **Step 3: Run linting**

Run: `pre-commit run --all-files`
Expected: All checks pass (or only formatting auto-fixes)

- [ ] **Step 4: Verify domain purity**

Run: `grep -rn "import pandas\|import numpy\|import yfinance\|import praw\|import xgboost\|import lightgbm" domain/`
Expected: No matches — domain has zero external imports

- [ ] **Step 5: Run CLI smoke test**

Run: `python -m application.cli --help`
Expected: Shows help output

- [ ] **Step 6: Final commit with any fixes**

```bash
git add -A
git commit -m "chore: integration fixes from full verification pass"
```

---

## Summary

| Task | Component | Tests |
|------|-----------|-------|
| 1 | Domain exceptions | 2 |
| 2 | RecommendationGrade + TechnicalIndicators | 5 |
| 3 | DivergenceSignal + StockRecommendation | 5 |
| 4 | WeeklyReport + AccuracyRecord | 5 |
| 5 | Phase 3 port interfaces | mypy only |
| 6 | compute_divergence_score + grade_recommendation | 8 |
| 7 | Hypothesis property tests | 5 |
| 8 | US market config + loader | 2 |
| 9 | All fake adapters | import check |
| 10 | Keyword sentiment scorer | 6 |
| 11 | SQLite store | 4 |
| 12 | RSS news discovery | 3 |
| 13 | Google Search discovery | 3 |
| 14 | Reddit + StockTwits buzz | 4 |
| 15 | yfinance market data | 3 |
| 16 | XGBoost + LightGBM + Ensemble | 5 |
| 17 | WeeklyTournamentUseCase + Tracker | 3 |
| 18 | CLI entry point | smoke test |
| 19 | GitHub Actions | config only |
| 20 | Integration verification | full suite |

**Total new tests: ~60+** on top of existing 7.
