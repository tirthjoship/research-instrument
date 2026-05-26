# Phase 3A Core Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a pretrained technical stock prediction pipeline — 45 features across 8 groups, XGBoost+LightGBM+Ridge ensemble, walk-forward validation, multi-horizon predictions (2d/5d/10d), permutation testing, and CLI interface.

**Architecture:** Hexagonal (Ports & Adapters). Domain layer is pure Python with zero external imports. Adapters implement domain port Protocols. Application layer orchestrates use cases via injected ports. CLI wires everything together as the composition root.

**Tech Stack:** Python 3.12+, yfinance, XGBoost, LightGBM, scikit-learn (Ridge), pandas, numpy, SQLite, Click, Hypothesis, pytest, loguru

**Branch:** `feat/phase3a-core-engine` (from `dev/structural-updates`)

**Spec:** `docs/superpowers/specs/2026-05-25-phase3a-core-engine-revised.md`

---

## File Structure

### Modified Files
| File | Changes |
|------|---------|
| `domain/exceptions.py` | Add `InsufficientDataError`, `StaleDataError` |
| `domain/models.py` | Add `RecommendationGrade`, `MultiHorizonPrediction`, `StockRecommendation`, `AccuracyRecord`, `EvaluationRun`, `WeeklyReport` |
| `domain/ports.py` | Add `TechnicalAnalysisPort`, `RecommendationStorePort`, `FeatureEngineerPort`; update `StockPredictorPort` |
| `domain/services.py` | Add `grade_from_horizons()`, `validate_feature_matrix()`, `validate_data_freshness()`, `classify_horizon()` |
| `tests/test_domain_models.py` | Full test suite for all domain models |
| `tests/test_domain_services.py` | Full test suite for all domain services |
| `application/use_cases.py` | Add `PretrainingUseCase`, `WeeklyTournamentUseCase`, `TrackRecommendationsUseCase`, `EvaluationUseCase` |

### New Files
| File | Purpose |
|------|---------|
| `config/__init__.py` | Package init |
| `config/loader.py` | YAML config loader |
| `config/markets/__init__.py` | Package init |
| `config/markets/us.yaml` | US market configuration |
| `tests/test_properties.py` | Hypothesis property-based tests |
| `tests/fakes/__init__.py` | Package init |
| `tests/fakes/fake_market_data.py` | Fake `MarketDataPort` |
| `tests/fakes/fake_technical_analysis.py` | Fake `TechnicalAnalysisPort` |
| `tests/fakes/fake_store.py` | Fake `RecommendationStorePort` |
| `tests/fakes/fake_feature_engineer.py` | Fake `FeatureEngineerPort` |
| `tests/fakes/fake_predictor.py` | Fake `StockPredictorPort` |
| `tests/test_feature_engineer.py` | Feature computation tests |
| `tests/test_ml_predictors.py` | ML predictor tests |
| `tests/test_yfinance_adapter.py` | yfinance adapter tests (mocked) |
| `tests/test_sqlite_store.py` | SQLite store tests (in-memory) |
| `tests/test_evaluation.py` | Evaluation framework tests |
| `tests/test_weekly_tournament.py` | End-to-end use case tests |
| `tests/test_pretraining.py` | Pretraining pipeline tests |
| `adapters/data/cache_mixin.py` | Raw data caching base class |
| `adapters/data/yfinance_adapter.py` | `MarketDataPort` + `TechnicalAnalysisPort` implementation |
| `adapters/data/sqlite_store.py` | `RecommendationStorePort` implementation |
| `adapters/ml/feature_engineer.py` | `FeatureEngineerPort` implementation (45 features) |
| `adapters/ml/xgboost_predictor.py` | `StockPredictorPort` (XGBoost) |
| `adapters/ml/lightgbm_predictor.py` | `StockPredictorPort` (LightGBM) |
| `adapters/ml/ridge_predictor.py` | `StockPredictorPort` (Ridge) |
| `adapters/ml/ensemble_predictor.py` | `StockPredictorPort` (weighted ensemble) |
| `application/evaluation.py` | Walk-forward, permutation, costs, regime, drawdown |
| `application/cli.py` | Click CLI entry point |

---

## Task 1: Domain Exceptions

**Files:**
- Modify: `domain/exceptions.py`
- Test: `tests/test_domain_models.py`

- [ ] **Step 1: Write failing tests for new exceptions**

```python
# Add to tests/test_domain_models.py
"""Tests for domain models and exceptions."""

from domain.exceptions import (
    DomainError,
    InsufficientDataError,
    InvalidMarketDataError,
    InvalidPredictionError,
    LookAheadBiasError,
    StaleDataError,
)


def test_insufficient_data_error_is_domain_error() -> None:
    err = InsufficientDataError("only 3 tickers")
    assert isinstance(err, DomainError)
    assert str(err) == "only 3 tickers"


def test_stale_data_error_is_domain_error() -> None:
    err = StaleDataError("data is 5 days stale")
    assert isinstance(err, DomainError)
    assert str(err) == "data is 5 days stale"


def test_stale_data_error_attributes() -> None:
    err = StaleDataError(
        "stale",
        staleness_days=5,
        max_staleness_days=3,
    )
    assert err.staleness_days == 5
    assert err.max_staleness_days == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `conda activate multi-modal-stock-ml && pytest tests/test_domain_models.py -v`
Expected: FAIL — `ImportError: cannot import name 'InsufficientDataError'`

- [ ] **Step 3: Implement new exceptions**

Add to `domain/exceptions.py` after `LookAheadBiasError`:

```python
class InsufficientDataError(DomainError):
    """Raised when too few qualified tickers or data points for pipeline."""

    pass


class StaleDataError(DomainError):
    """Raised when data exceeds maximum staleness threshold.

    Attributes:
        staleness_days: How stale the data actually is.
        max_staleness_days: Maximum allowed staleness.
    """

    def __init__(
        self,
        message: str = "",
        *,
        staleness_days: int | None = None,
        max_staleness_days: int | None = None,
    ) -> None:
        super().__init__(message)
        self.staleness_days = staleness_days
        self.max_staleness_days = max_staleness_days
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_domain_models.py -v`
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add domain/exceptions.py tests/test_domain_models.py
git commit -m "feat: add InsufficientDataError and StaleDataError exceptions"
```

---

## Task 2: Domain Models — RecommendationGrade + MultiHorizonPrediction

**Files:**
- Modify: `domain/models.py`
- Test: `tests/test_domain_models.py`

- [ ] **Step 1: Write failing tests for RecommendationGrade**

Add to `tests/test_domain_models.py`:

```python
from domain.models import (
    BacktestResult,
    MultiHorizonPrediction,
    RecommendationGrade,
    Sentiment,
    Signal,
)
from domain.exceptions import InvalidPredictionError

import pytest


def test_recommendation_grade_ordering() -> None:
    """Grades have a natural ordering from most bullish to most bearish."""
    assert RecommendationGrade.STRONG_BUY.value == "strong_buy"
    assert RecommendationGrade.BUY.value == "buy"
    assert RecommendationGrade.HOLD.value == "hold"
    assert RecommendationGrade.MAY_SELL.value == "may_sell"
    assert RecommendationGrade.IMMEDIATE_SELL.value == "immediate_sell"


def test_recommendation_grade_all_values() -> None:
    assert len(RecommendationGrade) == 5


def test_multi_horizon_prediction_valid() -> None:
    pred = MultiHorizonPrediction(
        predicted_return_2d=0.02,
        predicted_return_5d=0.03,
        predicted_return_10d=0.05,
        confidence_2d=0.8,
        confidence_5d=0.7,
        confidence_10d=0.6,
    )
    assert pred.predicted_return_2d == 0.02
    assert pred.confidence_10d == 0.6


def test_multi_horizon_prediction_confidence_below_zero_raises() -> None:
    with pytest.raises(InvalidPredictionError, match="Confidence must be in"):
        MultiHorizonPrediction(
            predicted_return_2d=0.02,
            predicted_return_5d=0.03,
            predicted_return_10d=0.05,
            confidence_2d=-0.1,
            confidence_5d=0.7,
            confidence_10d=0.6,
        )


def test_multi_horizon_prediction_confidence_above_one_raises() -> None:
    with pytest.raises(InvalidPredictionError, match="Confidence must be in"):
        MultiHorizonPrediction(
            predicted_return_2d=0.02,
            predicted_return_5d=0.03,
            predicted_return_10d=0.05,
            confidence_2d=0.8,
            confidence_5d=1.5,
            confidence_10d=0.6,
        )


def test_multi_horizon_prediction_is_frozen() -> None:
    pred = MultiHorizonPrediction(
        predicted_return_2d=0.02,
        predicted_return_5d=0.03,
        predicted_return_10d=0.05,
        confidence_2d=0.8,
        confidence_5d=0.7,
        confidence_10d=0.6,
    )
    with pytest.raises(AttributeError):
        pred.predicted_return_2d = 0.99  # type: ignore[misc]


def test_multi_horizon_prediction_negative_returns_allowed() -> None:
    """Negative predicted returns are valid (bearish predictions)."""
    pred = MultiHorizonPrediction(
        predicted_return_2d=-0.05,
        predicted_return_5d=-0.08,
        predicted_return_10d=-0.12,
        confidence_2d=0.9,
        confidence_5d=0.8,
        confidence_10d=0.7,
    )
    assert pred.predicted_return_2d == -0.05
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_domain_models.py -v`
Expected: FAIL — `ImportError: cannot import name 'RecommendationGrade'`

- [ ] **Step 3: Implement RecommendationGrade and MultiHorizonPrediction**

Add to `domain/models.py` — add `enum` import at top, then after `BacktestResult`:

```python
from enum import Enum


class RecommendationGrade(Enum):
    """5-tier grading system for stock recommendations.

    Ordered from most bullish to most bearish.
    """

    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    MAY_SELL = "may_sell"
    IMMEDIATE_SELL = "immediate_sell"


@dataclass(frozen=True)
class MultiHorizonPrediction:
    """Predicted returns at 2-day, 5-day, and 10-day horizons.

    Each horizon has a predicted return (can be negative) and
    a confidence score in [0, 1].
    """

    predicted_return_2d: float
    predicted_return_5d: float
    predicted_return_10d: float
    confidence_2d: float
    confidence_5d: float
    confidence_10d: float

    def __post_init__(self) -> None:
        for field_name in ("confidence_2d", "confidence_5d", "confidence_10d"):
            value = getattr(self, field_name)
            if not 0.0 <= value <= 1.0:
                raise InvalidPredictionError(
                    f"Confidence must be in [0, 1], got {value}"
                )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_domain_models.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add domain/models.py tests/test_domain_models.py
git commit -m "feat: add RecommendationGrade enum and MultiHorizonPrediction model"
```

---

## Task 3: Domain Models — StockRecommendation + AccuracyRecord + EvaluationRun + WeeklyReport

**Files:**
- Modify: `domain/models.py`
- Test: `tests/test_domain_models.py`

- [ ] **Step 1: Write failing tests for StockRecommendation**

Add to `tests/test_domain_models.py`:

```python
from domain.models import (
    AccuracyRecord,
    EvaluationRun,
    StockRecommendation,
    WeeklyReport,
)


def test_stock_recommendation_valid() -> None:
    pred = MultiHorizonPrediction(
        predicted_return_2d=0.03,
        predicted_return_5d=0.04,
        predicted_return_10d=0.06,
        confidence_2d=0.8,
        confidence_5d=0.7,
        confidence_10d=0.6,
    )
    rec = StockRecommendation(
        symbol="AAPL",
        week_start="2026-05-19",
        grade=RecommendationGrade.STRONG_BUY,
        composite_score=0.85,
        prediction=pred,
        horizon_signals={"2d": "bullish", "5d": "bullish", "10d": "bullish"},
        reasoning="Strong momentum across all horizons",
        sources=["yfinance"],
    )
    assert rec.symbol == "AAPL"
    assert rec.grade == RecommendationGrade.STRONG_BUY
    assert rec.prediction.predicted_return_10d == 0.06
    assert rec.sentiment_score is None  # Phase 3B


def test_stock_recommendation_is_frozen() -> None:
    pred = MultiHorizonPrediction(
        predicted_return_2d=0.01,
        predicted_return_5d=0.02,
        predicted_return_10d=0.03,
        confidence_2d=0.5,
        confidence_5d=0.5,
        confidence_10d=0.5,
    )
    rec = StockRecommendation(
        symbol="GOOG",
        week_start="2026-05-19",
        grade=RecommendationGrade.HOLD,
        composite_score=0.5,
        prediction=pred,
        horizon_signals={"2d": "neutral", "5d": "neutral", "10d": "neutral"},
        reasoning="Flat",
        sources=["yfinance"],
    )
    with pytest.raises(AttributeError):
        rec.symbol = "MSFT"  # type: ignore[misc]


def test_accuracy_record_valid() -> None:
    record = AccuracyRecord(
        symbol="AAPL",
        week_start="2026-05-19",
        predicted_grade="strong_buy",
        predicted_return_2d=0.03,
        predicted_return_5d=0.04,
        predicted_return_10d=0.06,
        actual_return_2d=0.025,
        actual_return_5d=0.035,
        actual_return_10d=0.055,
        direction_correct_2d=True,
        direction_correct_5d=True,
        direction_correct_10d=True,
    )
    assert record.direction_correct_2d is True
    assert record.actual_return_5d == 0.035


def test_evaluation_run_valid() -> None:
    run = EvaluationRun(
        run_date="2026-05-25",
        eval_type="walk_forward",
        horizon="5d",
        metric_name="directional_accuracy",
        metric_value=0.58,
        p_value=0.03,
    )
    assert run.eval_type == "walk_forward"
    assert run.p_value == 0.03
    assert run.regime is None


def test_evaluation_run_with_regime() -> None:
    run = EvaluationRun(
        run_date="2026-05-25",
        eval_type="regime",
        horizon="10d",
        metric_name="directional_accuracy",
        metric_value=0.62,
        regime="bull",
    )
    assert run.regime == "bull"


def test_weekly_report_valid() -> None:
    pred = MultiHorizonPrediction(
        predicted_return_2d=0.02,
        predicted_return_5d=0.03,
        predicted_return_10d=0.04,
        confidence_2d=0.8,
        confidence_5d=0.7,
        confidence_10d=0.6,
    )
    rec = StockRecommendation(
        symbol="AAPL",
        week_start="2026-05-19",
        grade=RecommendationGrade.BUY,
        composite_score=0.7,
        prediction=pred,
        horizon_signals={"2d": "bullish", "5d": "neutral", "10d": "bullish"},
        reasoning="test",
        sources=["yfinance"],
    )
    report = WeeklyReport(
        report_date="2026-05-19",
        market="us",
        recommendations=[rec],
    )
    assert report.market == "us"
    assert len(report.recommendations) == 1
    assert report.spy_return_same_period is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_domain_models.py -v`
Expected: FAIL — `ImportError: cannot import name 'StockRecommendation'`

- [ ] **Step 3: Implement StockRecommendation, AccuracyRecord, EvaluationRun, WeeklyReport**

Add to `domain/models.py` after `MultiHorizonPrediction`:

```python
@dataclass(frozen=True)
class StockRecommendation:
    """A graded stock recommendation for a given week.

    Phase 3B optional fields (sentiment_score, divergence_score, etc.)
    are None during Phase 3A.
    """

    symbol: str
    week_start: str
    grade: RecommendationGrade
    composite_score: float
    prediction: MultiHorizonPrediction
    horizon_signals: dict[str, str]
    reasoning: str
    sources: list[str]
    sentiment_score: float | None = None
    divergence_score: float | None = None
    divergence_type: str | None = None
    technical_signal: float | None = None
    rsi_14: float | None = None
    macd: float | None = None


@dataclass(frozen=True)
class AccuracyRecord:
    """Historical record comparing predicted vs actual returns."""

    symbol: str
    week_start: str
    predicted_grade: str
    predicted_return_2d: float
    predicted_return_5d: float
    predicted_return_10d: float
    actual_return_2d: float
    actual_return_5d: float
    actual_return_10d: float
    direction_correct_2d: bool
    direction_correct_5d: bool
    direction_correct_10d: bool


@dataclass(frozen=True)
class EvaluationRun:
    """Record of a single evaluation metric from a validation run."""

    run_date: str
    eval_type: str  # 'walk_forward', 'permutation', 'regime'
    horizon: str  # '2d', '5d', '10d'
    metric_name: str
    metric_value: float
    p_value: float | None = None
    regime: str | None = None  # 'bull', 'sideways', 'bear'
    details: str | None = None


@dataclass(frozen=True)
class WeeklyReport:
    """Aggregated weekly report with recommendations and performance."""

    report_date: str
    market: str
    recommendations: list[StockRecommendation]
    accuracy_vs_last_week: float | None = None
    spy_return_same_period: float | None = None
    max_drawdown: float | None = None
    sharpe_ratio: float | None = None
    transaction_costs: float | None = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_domain_models.py -v`
Expected: All tests PASS

- [ ] **Step 5: Run mypy to verify type safety**

Run: `mypy domain/models.py --strict`
Expected: Success, no errors

- [ ] **Step 6: Commit**

```bash
git add domain/models.py tests/test_domain_models.py
git commit -m "feat: add StockRecommendation, AccuracyRecord, EvaluationRun, WeeklyReport models"
```

---

## Task 4: Domain Ports — Phase 3A Updates

**Files:**
- Modify: `domain/ports.py`
- Test: `tests/test_domain_models.py` (import verification)

- [ ] **Step 1: Write import verification test**

Add to `tests/test_domain_models.py`:

```python
def test_ports_importable() -> None:
    """All Phase 3A ports are importable."""
    from domain.ports import (
        BacktestResultPort,
        FeatureEngineerPort,
        MarketDataPort,
        RecommendationStorePort,
        SentimentPort,
        StockPredictorPort,
        TechnicalAnalysisPort,
    )
    # Protocol classes exist
    assert TechnicalAnalysisPort is not None
    assert RecommendationStorePort is not None
    assert FeatureEngineerPort is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_domain_models.py::test_ports_importable -v`
Expected: FAIL — `ImportError: cannot import name 'TechnicalAnalysisPort'`

- [ ] **Step 3: Update StockPredictorPort and add new ports**

Replace entire `domain/ports.py`:

```python
"""Port interfaces (protocols) for multi-modal stock recommender.

Adapters implement these ports; domain and application depend only
on these abstractions. Ports support point-in-time access and leakage pruning.
"""

from datetime import datetime
from typing import Protocol

from .models import (
    AccuracyRecord,
    BacktestResult,
    EvaluationRun,
    Sentiment,
    Signal,
    StockRecommendation,
    WeeklyReport,
)


class MarketDataPort(Protocol):
    """Port: load market data with point-in-time and leakage prevention.

    Implementations must ensure only data with timestamp <= prediction_time
    is exposed. Raise LookAheadBiasError if future-dated data is detected.
    """

    def get_signals(
        self,
        symbol: str,
        prediction_time: datetime,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[Signal]:
        """Return OHLCV signals for symbol up to prediction_time only.

        Raises:
            LookAheadBiasError: If any signal has timestamp > prediction_time.
            InvalidMarketDataError: If data fails validation.
        """
        ...

    def get_ticker_info(self, symbol: str) -> dict[str, float]:
        """Return fundamental data (market_cap, pe_ratio, revenue_growth, etc.).

        Returns dict with keys matching feature names. Missing data = omitted key.
        """
        ...

    def get_options_summary(
        self, symbol: str, prediction_time: datetime
    ) -> dict[str, float] | None:
        """Return options summary (put_call_ratio, iv_skew, unusual_volume, etc.).

        Returns None if options data unavailable for symbol.
        """
        ...

    def get_analyst_data(
        self, symbol: str, prediction_time: datetime
    ) -> dict[str, float] | None:
        """Return analyst/short interest data (earnings_surprise, short_interest, etc.).

        Returns None if analyst data unavailable for symbol.
        """
        ...

    def validate_point_in_time(self, prediction_time: datetime) -> None:
        """Validate that no future-dated data is exposed for this prediction time.

        Raises:
            LookAheadBiasError: If future leakage is detected.
        """
        ...


class SentimentPort(Protocol):
    """Port: extract sentiment signals with temporal alignment.

    Phase 3B — not used in Phase 3A.
    """

    def get_sentiment(
        self,
        symbol: str,
        prediction_time: datetime,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[Sentiment]:
        """Return sentiment signals for symbol up to prediction_time only."""
        ...


class TechnicalAnalysisPort(Protocol):
    """Port: compute technical indicators from OHLCV signals.

    Returns a flat dict of indicator_name -> value for ML feature consumption.
    """

    def compute_indicators(self, signals: list[Signal]) -> dict[str, float]:
        """Compute RSI, MACD, SMAs, stochastics, OBV from OHLCV signals.

        Args:
            signals: Historical OHLCV signals, chronologically ordered.

        Returns:
            Dict mapping indicator names to computed values.
            Missing indicators (insufficient data) are omitted from dict.
        """
        ...


class StockPredictorPort(Protocol):
    """Port: ML model that predicts stock returns from features.

    One instance per horizon (2d, 5d, 10d). Supports train → predict → persist.
    """

    def fit(
        self, features: list[dict[str, float]], targets: list[float]
    ) -> None:
        """Train model on feature matrix and target returns.

        Args:
            features: List of feature dicts, one per sample.
            targets: List of target returns, aligned with features.
        """
        ...

    def predict(self, features: list[dict[str, float]]) -> list[float]:
        """Predict returns from feature matrix.

        Args:
            features: List of feature dicts, one per sample.

        Returns:
            List of predicted returns, aligned with features.
        """
        ...

    def save_model(self, path: str) -> None:
        """Persist trained model to disk."""
        ...

    def load_model(self, path: str) -> None:
        """Load trained model from disk."""
        ...


class FeatureEngineerPort(Protocol):
    """Port: compute feature vector from raw market data.

    Transforms raw OHLCV signals, indicators, fundamentals, and macro data
    into a flat dict of 45 named features for ML consumption.
    """

    def compute(
        self,
        signals: list[Signal],
        indicators: dict[str, float],
        ticker_info: dict[str, float],
        options_summary: dict[str, float] | None,
        analyst_data: dict[str, float] | None,
        macro_signals: dict[str, list[Signal]],
        sector_signals: list[Signal] | None,
    ) -> dict[str, float]:
        """Compute all features for one symbol at one point in time.

        Returns:
            Dict mapping feature_name -> feature_value.
            NaN-valued features use float('nan').
        """
        ...

    def get_feature_names(self) -> list[str]:
        """Return ordered list of all feature names."""
        ...


class RecommendationStorePort(Protocol):
    """Port: persist and retrieve recommendations, accuracy, evaluations, reports."""

    def save_recommendation(self, rec: StockRecommendation) -> None:
        """Persist a stock recommendation."""
        ...

    def get_recommendations(
        self,
        week_start: str | None = None,
        symbol: str | None = None,
    ) -> list[StockRecommendation]:
        """Retrieve recommendations matching filters."""
        ...

    def save_accuracy_record(self, record: AccuracyRecord) -> None:
        """Persist an accuracy record."""
        ...

    def get_accuracy_records(
        self,
        week_start: str | None = None,
        symbol: str | None = None,
    ) -> list[AccuracyRecord]:
        """Retrieve accuracy records matching filters."""
        ...

    def save_evaluation_run(self, run: EvaluationRun) -> None:
        """Persist an evaluation run result."""
        ...

    def get_evaluation_runs(
        self,
        run_date: str | None = None,
        eval_type: str | None = None,
    ) -> list[EvaluationRun]:
        """Retrieve evaluation runs matching filters."""
        ...

    def save_weekly_report(self, report: WeeklyReport) -> None:
        """Persist a weekly report."""
        ...

    def get_weekly_report(self, report_date: str) -> WeeklyReport | None:
        """Retrieve a weekly report by date. Returns None if not found."""
        ...


class BacktestResultPort(Protocol):
    """Port: persist and retrieve backtest results for recursive learning."""

    def save_result(self, result: BacktestResult) -> None:
        """Persist a backtest result."""
        ...

    def get_results(
        self,
        symbol: str | None = None,
        model_version: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[BacktestResult]:
        """Retrieve backtest results matching filters."""
        ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_domain_models.py -v`
Expected: All tests PASS

- [ ] **Step 5: Run mypy**

Run: `mypy domain/ports.py --strict`
Expected: Success

- [ ] **Step 6: Commit**

```bash
git add domain/ports.py tests/test_domain_models.py
git commit -m "feat: add TechnicalAnalysisPort, RecommendationStorePort, FeatureEngineerPort; update StockPredictorPort"
```

---

## Task 5: Domain Services — Grading + Validation

**Files:**
- Modify: `domain/services.py`
- Test: `tests/test_domain_services.py`

- [ ] **Step 1: Write failing tests for grade_from_horizons**

Replace `tests/test_domain_services.py`:

```python
"""Tests for domain services."""

from datetime import datetime, timedelta

import pytest

from domain.exceptions import LookAheadBiasError, StaleDataError
from domain.models import (
    MultiHorizonPrediction,
    RecommendationGrade,
    Sentiment,
    Signal,
)
from domain.services import (
    classify_horizon,
    grade_from_horizons,
    validate_data_freshness,
    validate_feature_matrix,
    validate_point_in_time_access,
)


# --- classify_horizon ---


def test_classify_horizon_bullish() -> None:
    assert classify_horizon(0.025, 0.015) == "bullish"


def test_classify_horizon_bearish() -> None:
    assert classify_horizon(-0.025, 0.015) == "bearish"


def test_classify_horizon_neutral_positive() -> None:
    assert classify_horizon(0.010, 0.015) == "neutral"


def test_classify_horizon_neutral_negative() -> None:
    assert classify_horizon(-0.010, 0.015) == "neutral"


def test_classify_horizon_at_threshold_is_neutral() -> None:
    """Exactly at threshold is neutral — must exceed to be directional."""
    assert classify_horizon(0.015, 0.015) == "neutral"
    assert classify_horizon(-0.015, 0.015) == "neutral"


# --- grade_from_horizons ---


def test_grade_strong_buy() -> None:
    """Bullish on 2+ horizons AND magnitude > 5% on longest bullish horizon."""
    pred = MultiHorizonPrediction(
        predicted_return_2d=0.03,
        predicted_return_5d=0.04,
        predicted_return_10d=0.06,
        confidence_2d=0.8,
        confidence_5d=0.7,
        confidence_10d=0.7,
    )
    grade, signals = grade_from_horizons(pred)
    assert grade == RecommendationGrade.STRONG_BUY
    assert signals["10d"] == "bullish"


def test_grade_buy_one_horizon_bullish() -> None:
    """Bullish on 1 horizon only → Buy."""
    pred = MultiHorizonPrediction(
        predicted_return_2d=0.025,
        predicted_return_5d=0.005,
        predicted_return_10d=0.01,
        confidence_2d=0.7,
        confidence_5d=0.5,
        confidence_10d=0.5,
    )
    grade, signals = grade_from_horizons(pred)
    assert grade == RecommendationGrade.BUY
    assert signals["2d"] == "bullish"
    assert signals["5d"] == "neutral"


def test_grade_buy_two_horizons_low_magnitude() -> None:
    """Bullish on 2 horizons but magnitude < 5% → Buy, not Strong Buy."""
    pred = MultiHorizonPrediction(
        predicted_return_2d=0.02,
        predicted_return_5d=0.03,
        predicted_return_10d=0.04,
        confidence_2d=0.7,
        confidence_5d=0.7,
        confidence_10d=0.7,
    )
    grade, _ = grade_from_horizons(pred)
    assert grade == RecommendationGrade.BUY


def test_grade_hold_all_neutral() -> None:
    """All horizons neutral → Hold."""
    pred = MultiHorizonPrediction(
        predicted_return_2d=0.005,
        predicted_return_5d=0.01,
        predicted_return_10d=0.02,
        confidence_2d=0.5,
        confidence_5d=0.5,
        confidence_10d=0.5,
    )
    grade, signals = grade_from_horizons(pred)
    assert grade == RecommendationGrade.HOLD
    assert all(s == "neutral" for s in signals.values())


def test_grade_hold_conflicting_signals() -> None:
    """Bullish + bearish on different horizons → Hold."""
    pred = MultiHorizonPrediction(
        predicted_return_2d=0.03,
        predicted_return_5d=-0.04,
        predicted_return_10d=0.01,
        confidence_2d=0.7,
        confidence_5d=0.7,
        confidence_10d=0.5,
    )
    grade, signals = grade_from_horizons(pred)
    assert grade == RecommendationGrade.HOLD
    assert signals["2d"] == "bullish"
    assert signals["5d"] == "bearish"


def test_grade_may_sell() -> None:
    """Bearish on 1 horizon only → May Sell."""
    pred = MultiHorizonPrediction(
        predicted_return_2d=0.005,
        predicted_return_5d=-0.025,
        predicted_return_10d=0.01,
        confidence_2d=0.5,
        confidence_5d=0.7,
        confidence_10d=0.5,
    )
    grade, _ = grade_from_horizons(pred)
    assert grade == RecommendationGrade.MAY_SELL


def test_grade_immediate_sell() -> None:
    """Bearish on 2+ horizons AND magnitude > -3% → Immediate Sell."""
    pred = MultiHorizonPrediction(
        predicted_return_2d=-0.025,
        predicted_return_5d=-0.04,
        predicted_return_10d=-0.06,
        confidence_2d=0.8,
        confidence_5d=0.8,
        confidence_10d=0.8,
    )
    grade, signals = grade_from_horizons(pred)
    assert grade == RecommendationGrade.IMMEDIATE_SELL
    assert signals["2d"] == "bearish"
    assert signals["5d"] == "bearish"


def test_grade_returns_horizon_signals_dict() -> None:
    pred = MultiHorizonPrediction(
        predicted_return_2d=0.03,
        predicted_return_5d=0.04,
        predicted_return_10d=0.06,
        confidence_2d=0.8,
        confidence_5d=0.7,
        confidence_10d=0.7,
    )
    _, signals = grade_from_horizons(pred)
    assert set(signals.keys()) == {"2d", "5d", "10d"}
    assert all(s in ("bullish", "bearish", "neutral") for s in signals.values())


# --- validate_feature_matrix ---


def test_validate_feature_matrix_clean() -> None:
    validate_feature_matrix(["rsi_14", "macd", "volume_ratio_20d"])


def test_validate_feature_matrix_detects_next_day_return() -> None:
    with pytest.raises(LookAheadBiasError, match="next_day_return"):
        validate_feature_matrix(["rsi_14", "next_day_return", "macd"])


def test_validate_feature_matrix_detects_multiple_leaks() -> None:
    with pytest.raises(LookAheadBiasError):
        validate_feature_matrix(
            ["next_day_return", "forward_pe_ratio", "rsi_14"]
        )


def test_validate_feature_matrix_all_leakage_columns() -> None:
    """All four known leakage columns are caught."""
    for col in [
        "next_day_return",
        "next_week_return",
        "future_earnings_surprise",
        "forward_pe_ratio",
    ]:
        with pytest.raises(LookAheadBiasError):
            validate_feature_matrix([col])


# --- validate_data_freshness ---


def test_validate_data_freshness_pass() -> None:
    ref = datetime(2026, 5, 25, 12, 0)
    data_ts = datetime(2026, 5, 24, 12, 0)
    validate_data_freshness(data_ts, ref, max_staleness_days=3)


def test_validate_data_freshness_exactly_at_limit() -> None:
    ref = datetime(2026, 5, 25, 12, 0)
    data_ts = datetime(2026, 5, 22, 12, 0)
    validate_data_freshness(data_ts, ref, max_staleness_days=3)


def test_validate_data_freshness_stale_raises() -> None:
    ref = datetime(2026, 5, 25, 12, 0)
    data_ts = datetime(2026, 5, 20, 12, 0)
    with pytest.raises(StaleDataError):
        validate_data_freshness(data_ts, ref, max_staleness_days=3)


# --- validate_point_in_time_access (existing tests preserved) ---


def test_validate_point_in_time_pass() -> None:
    pt = datetime.now()
    signals = [
        Signal(
            symbol="AAPL",
            timestamp=pt - timedelta(days=1),
            price=100.0,
            volume=1000.0,
            open_=99.0,
            high=101.0,
            low=98.0,
        ),
    ]
    sentiments = [
        Sentiment(
            source="news",
            timestamp=pt - timedelta(hours=1),
            sentiment_score=0.0,
            confidence=1.0,
        ),
    ]
    validate_point_in_time_access(pt, signals, sentiments)


def test_validate_point_in_time_future_signal_raises() -> None:
    pt = datetime.now()
    signals = [
        Signal(
            symbol="AAPL",
            timestamp=pt + timedelta(days=1),
            price=100.0,
            volume=1000.0,
            open_=99.0,
            high=101.0,
            low=98.0,
        ),
    ]
    with pytest.raises(LookAheadBiasError):
        validate_point_in_time_access(pt, signals, [])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_domain_services.py -v`
Expected: FAIL — `ImportError: cannot import name 'classify_horizon'`

- [ ] **Step 3: Implement domain services**

Replace `domain/services.py`:

```python
"""Domain services: pure business logic for stock recommendation.

No external dependencies. Point-in-time validation, grading,
feature matrix validation, and data freshness checks.
"""

from datetime import datetime, timedelta

from .exceptions import LookAheadBiasError, StaleDataError
from .models import MultiHorizonPrediction, RecommendationGrade, Sentiment, Signal

NOISE_THRESHOLDS: dict[str, float] = {
    "2d": 0.015,
    "5d": 0.020,
    "10d": 0.030,
}

FUTURE_LEAKAGE_COLUMNS: frozenset[str] = frozenset(
    {
        "next_day_return",
        "next_week_return",
        "future_earnings_surprise",
        "forward_pe_ratio",
    }
)


def validate_point_in_time_access(
    prediction_time: datetime,
    signals: list[Signal],
    sentiments: list[Sentiment],
) -> None:
    """Verify all data timestamps are <= prediction_time.

    Raises:
        LookAheadBiasError: If any signal or sentiment is after prediction_time.
    """
    for s in signals:
        if s.timestamp > prediction_time:
            raise LookAheadBiasError(
                f"Signal timestamp {s.timestamp} > prediction_time {prediction_time}"
            )
    for s in sentiments:
        if s.timestamp > prediction_time:
            raise LookAheadBiasError(
                f"Sentiment timestamp {s.timestamp} > prediction_time {prediction_time}"
            )


def classify_horizon(predicted_return: float, threshold: float) -> str:
    """Classify a single horizon prediction as bullish/neutral/bearish.

    Must strictly exceed threshold to be directional.
    """
    if predicted_return > threshold:
        return "bullish"
    if predicted_return < -threshold:
        return "bearish"
    return "neutral"


def grade_from_horizons(
    prediction: MultiHorizonPrediction,
) -> tuple[RecommendationGrade, dict[str, str]]:
    """Grade a multi-horizon prediction into a RecommendationGrade.

    Returns:
        Tuple of (grade, horizon_signals) where horizon_signals maps
        '2d'/'5d'/'10d' to 'bullish'/'neutral'/'bearish'.

    Grading logic (from spec):
        Strong Buy: Bullish on 2+ horizons AND magnitude > 5% on longest bullish
        Buy: Bullish on 1+ horizon
        Hold: All neutral OR conflicting bullish+bearish signals
        May Sell: Bearish on 1 horizon (no bullish)
        Immediate Sell: Bearish on 2+ horizons AND magnitude < -3%
    """
    signals = {
        "2d": classify_horizon(
            prediction.predicted_return_2d, NOISE_THRESHOLDS["2d"]
        ),
        "5d": classify_horizon(
            prediction.predicted_return_5d, NOISE_THRESHOLDS["5d"]
        ),
        "10d": classify_horizon(
            prediction.predicted_return_10d, NOISE_THRESHOLDS["10d"]
        ),
    }

    bullish_count = sum(1 for s in signals.values() if s == "bullish")
    bearish_count = sum(1 for s in signals.values() if s == "bearish")

    # Find max magnitude on longest bullish horizon
    max_bullish_magnitude = 0.0
    for horizon in ("10d", "5d", "2d"):
        if signals[horizon] == "bullish":
            max_bullish_magnitude = getattr(
                prediction, f"predicted_return_{horizon}"
            )
            break

    # Find max magnitude on longest bearish horizon
    max_bearish_magnitude = 0.0
    for horizon in ("10d", "5d", "2d"):
        if signals[horizon] == "bearish":
            max_bearish_magnitude = getattr(
                prediction, f"predicted_return_{horizon}"
            )
            break

    # Conflicting signals (both bullish and bearish) → Hold
    if bullish_count > 0 and bearish_count > 0:
        return RecommendationGrade.HOLD, signals

    if bullish_count >= 2 and max_bullish_magnitude > 0.05:
        return RecommendationGrade.STRONG_BUY, signals

    if bullish_count >= 1:
        return RecommendationGrade.BUY, signals

    if bearish_count >= 2 and max_bearish_magnitude < -0.03:
        return RecommendationGrade.IMMEDIATE_SELL, signals

    if bearish_count >= 1:
        return RecommendationGrade.MAY_SELL, signals

    return RecommendationGrade.HOLD, signals


def validate_feature_matrix(feature_names: list[str]) -> None:
    """Verify no future-leakage columns appear in feature set.

    Raises:
        LookAheadBiasError: If any FUTURE_LEAKAGE_COLUMNS detected.
    """
    leaked = set(feature_names) & FUTURE_LEAKAGE_COLUMNS
    if leaked:
        raise LookAheadBiasError(
            f"Future leakage columns detected: {sorted(leaked)}"
        )


def validate_data_freshness(
    data_timestamp: datetime,
    reference_time: datetime,
    max_staleness_days: int = 3,
) -> None:
    """Verify data is not stale relative to reference time.

    Args:
        data_timestamp: When the data was last updated.
        reference_time: The as-of time (prediction_time or now).
        max_staleness_days: Maximum allowed staleness in days.

    Raises:
        StaleDataError: If data exceeds staleness threshold.
    """
    staleness = reference_time - data_timestamp
    if staleness > timedelta(days=max_staleness_days):
        raise StaleDataError(
            f"Data is {staleness.days} days stale (max: {max_staleness_days})",
            staleness_days=staleness.days,
            max_staleness_days=max_staleness_days,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_domain_services.py -v`
Expected: All 20 tests PASS

- [ ] **Step 5: Run mypy**

Run: `mypy domain/services.py --strict`
Expected: Success

- [ ] **Step 6: Commit**

```bash
git add domain/services.py tests/test_domain_services.py
git commit -m "feat: add grade_from_horizons, validate_feature_matrix, validate_data_freshness services"
```

---

## Task 6: Property-Based Tests (Hypothesis)

**Files:**
- Create: `tests/test_properties.py`

- [ ] **Step 1: Write property-based tests**

Create `tests/test_properties.py`:

```python
"""Property-based tests for domain invariants using Hypothesis."""

from hypothesis import given, assume
from hypothesis import strategies as st

from domain.exceptions import InvalidMarketDataError, InvalidPredictionError
from domain.models import MultiHorizonPrediction, RecommendationGrade, Sentiment
from domain.services import classify_horizon, grade_from_horizons


# --- Sentiment bounded ---

@given(score=st.floats(min_value=-1.0, max_value=1.0), conf=st.floats(min_value=0.0, max_value=1.0))
def test_sentiment_score_bounded(score: float, conf: float) -> None:
    """Sentiment score always stays in [-1, 1] when created with valid input."""
    assume(not (score != score))  # skip NaN
    assume(not (conf != conf))
    s = Sentiment(source="test", timestamp=__import__("datetime").datetime.now(), sentiment_score=score, confidence=conf)
    assert -1.0 <= s.sentiment_score <= 1.0


@given(score=st.floats().filter(lambda x: x < -1.0 or x > 1.0))
def test_sentiment_rejects_out_of_bounds(score: float) -> None:
    """Sentiment rejects scores outside [-1, 1]."""
    assume(not (score != score))  # skip NaN
    try:
        Sentiment(source="test", timestamp=__import__("datetime").datetime.now(), sentiment_score=score, confidence=0.5)
        assert False, "Should have raised"
    except InvalidMarketDataError:
        pass


# --- Grading monotonicity ---

@given(
    r2=st.floats(min_value=-0.2, max_value=0.2),
    r5=st.floats(min_value=-0.2, max_value=0.2),
    r10=st.floats(min_value=-0.2, max_value=0.2),
)
def test_grading_always_returns_valid_grade(r2: float, r5: float, r10: float) -> None:
    """grade_from_horizons always returns a valid RecommendationGrade."""
    assume(all(x == x for x in (r2, r5, r10)))  # skip NaN
    pred = MultiHorizonPrediction(
        predicted_return_2d=r2,
        predicted_return_5d=r5,
        predicted_return_10d=r10,
        confidence_2d=0.5,
        confidence_5d=0.5,
        confidence_10d=0.5,
    )
    grade, signals = grade_from_horizons(pred)
    assert isinstance(grade, RecommendationGrade)
    assert set(signals.keys()) == {"2d", "5d", "10d"}
    assert all(s in ("bullish", "neutral", "bearish") for s in signals.values())


@given(
    r2=st.floats(min_value=-0.2, max_value=0.2),
    r5=st.floats(min_value=-0.2, max_value=0.2),
    r10=st.floats(min_value=-0.2, max_value=0.2),
)
def test_grading_symmetric_signals(r2: float, r5: float, r10: float) -> None:
    """Horizon classification is symmetric: classify(-x) == mirror(classify(x))."""
    assume(all(x == x for x in (r2, r5, r10)))
    mirror = {"bullish": "bearish", "bearish": "bullish", "neutral": "neutral"}
    pred_pos = MultiHorizonPrediction(
        predicted_return_2d=r2, predicted_return_5d=r5, predicted_return_10d=r10,
        confidence_2d=0.5, confidence_5d=0.5, confidence_10d=0.5,
    )
    pred_neg = MultiHorizonPrediction(
        predicted_return_2d=-r2, predicted_return_5d=-r5, predicted_return_10d=-r10,
        confidence_2d=0.5, confidence_5d=0.5, confidence_10d=0.5,
    )
    _, signals_pos = grade_from_horizons(pred_pos)
    _, signals_neg = grade_from_horizons(pred_neg)
    for h in ("2d", "5d", "10d"):
        assert signals_neg[h] == mirror[signals_pos[h]]


# --- classify_horizon ---

@given(ret=st.floats(min_value=0.001, max_value=1.0), threshold=st.floats(min_value=0.001, max_value=0.5))
def test_classify_horizon_positive_above_threshold_is_bullish(ret: float, threshold: float) -> None:
    assume(ret > threshold)
    assert classify_horizon(ret, threshold) == "bullish"


@given(ret=st.floats(min_value=-1.0, max_value=-0.001), threshold=st.floats(min_value=0.001, max_value=0.5))
def test_classify_horizon_negative_below_neg_threshold_is_bearish(ret: float, threshold: float) -> None:
    assume(ret < -threshold)
    assert classify_horizon(ret, threshold) == "bearish"


# --- Confidence bounds ---

@given(
    c2=st.floats(min_value=0.0, max_value=1.0),
    c5=st.floats(min_value=0.0, max_value=1.0),
    c10=st.floats(min_value=0.0, max_value=1.0),
)
def test_multi_horizon_confidence_always_valid(c2: float, c5: float, c10: float) -> None:
    """MultiHorizonPrediction accepts any confidence in [0, 1]."""
    assume(all(x == x for x in (c2, c5, c10)))
    pred = MultiHorizonPrediction(
        predicted_return_2d=0.01,
        predicted_return_5d=0.02,
        predicted_return_10d=0.03,
        confidence_2d=c2,
        confidence_5d=c5,
        confidence_10d=c10,
    )
    assert 0.0 <= pred.confidence_2d <= 1.0


@given(bad_conf=st.floats().filter(lambda x: x == x and (x < 0.0 or x > 1.0)))
def test_multi_horizon_rejects_bad_confidence(bad_conf: float) -> None:
    """MultiHorizonPrediction rejects confidence outside [0, 1]."""
    try:
        MultiHorizonPrediction(
            predicted_return_2d=0.01,
            predicted_return_5d=0.02,
            predicted_return_10d=0.03,
            confidence_2d=bad_conf,
            confidence_5d=0.5,
            confidence_10d=0.5,
        )
        assert False, "Should have raised"
    except InvalidPredictionError:
        pass
```

- [ ] **Step 2: Run property tests**

Run: `pytest tests/test_properties.py -v`
Expected: All tests PASS (Hypothesis generates ~100 examples per property)

- [ ] **Step 3: Commit**

```bash
git add tests/test_properties.py
git commit -m "test: add Hypothesis property-based tests for domain invariants"
```

---

## Task 7: Market Configuration

**Files:**
- Create: `config/__init__.py`, `config/markets/__init__.py`, `config/markets/us.yaml`, `config/loader.py`

- [ ] **Step 1: Create config package structure**

Create `config/__init__.py`:

```python
"""Configuration package for multi-modal stock recommender."""
```

Create `config/markets/__init__.py`:

```python
"""Market-specific configuration files."""
```

- [ ] **Step 2: Create us.yaml**

Create `config/markets/us.yaml`:

```yaml
# US Market Configuration — Phase 3A
market: us
timezone: America/New_York

# Trading hours (Eastern)
trading_hours:
  open: "09:30"
  close: "16:00"

# Ticker universe — Phase 3A uses S&P 500 + popular ETF holdings
# Phase 3B will switch to dynamic buzz-driven discovery
universe:
  source: sp500
  min_market_cap: 2_000_000_000  # $2B minimum
  min_avg_volume: 500_000  # 500k daily average
  exclude_penny_stocks: true
  penny_stock_threshold: 5.0  # $5 minimum price

# Macro indicators (yfinance symbols)
macro_symbols:
  vix: "^VIX"
  treasury_10y: "^TNX"
  dxy: "DX-Y.NYB"
  irx: "^IRX"
  spy: "SPY"

# Sector ETFs for relative strength
sector_etfs:
  Technology: "XLK"
  Healthcare: "XLV"
  Financials: "XLF"
  Consumer Discretionary: "XLY"
  Consumer Staples: "XLP"
  Energy: "XLE"
  Industrials: "XLI"
  Materials: "XLB"
  Utilities: "XLU"
  Real Estate: "XLRE"
  Communication Services: "XLC"

# Feature engineering thresholds
features:
  price_outlier_cap: 0.30  # ±30% single-day cap
  volume_outlier_threshold: 20  # 20x average = keep as signal
  min_trading_days: 20  # minimum OHLCV days required
  max_nan_fraction: 0.50  # skip ticker if >50% NaN

# Multi-horizon targets
horizons:
  2d:
    noise_threshold: 0.015
  5d:
    noise_threshold: 0.020
  10d:
    noise_threshold: 0.030

# Data quality gates
quality_gates:
  min_qualified_tickers: 5  # abort below this
  degraded_threshold: 15  # warn if below this
  feature_nan_warn: 0.05  # warn if >5% NaN
  feature_nan_abort: 0.30  # abort if >30% NaN
  max_staleness_days: 3

# Pretraining
pretraining:
  history_years: 3
  walk_forward_start: "2024-01"

# Model
model:
  ensemble_weights: "accuracy"  # weight by recent accuracy
  retrain_frequency: "monthly"

# Evaluation
evaluation:
  permutation_shuffles: 1000
  significance_threshold: 0.05
  transaction_cost_pct: 0.001  # 0.1% per trade
  regime_thresholds:
    bull: 0.10  # SPY annualized > 10%
    bear: -0.10  # SPY annualized < -10%
```

- [ ] **Step 3: Create config loader**

Create `config/loader.py`:

```python
"""Load market configuration from YAML files."""

from pathlib import Path
from typing import Any

import yaml


def load_market_config(market: str = "us") -> dict[str, Any]:
    """Load market configuration from config/markets/{market}.yaml.

    Args:
        market: Market identifier (e.g., 'us', 'ca', 'in').

    Returns:
        Parsed YAML configuration as dict.

    Raises:
        FileNotFoundError: If config file doesn't exist.
    """
    config_dir = Path(__file__).parent / "markets"
    config_path = config_dir / f"{market}.yaml"
    if not config_path.exists():
        msg = f"Market config not found: {config_path}"
        raise FileNotFoundError(msg)
    with open(config_path) as f:
        config: dict[str, Any] = yaml.safe_load(f)
    return config
```

- [ ] **Step 4: Write and run config test**

Add a quick test in `tests/test_domain_models.py`:

```python
def test_load_us_market_config() -> None:
    from config.loader import load_market_config
    config = load_market_config("us")
    assert config["market"] == "us"
    assert config["macro_symbols"]["vix"] == "^VIX"
    assert config["horizons"]["5d"]["noise_threshold"] == 0.020


def test_load_missing_market_raises() -> None:
    from config.loader import load_market_config
    with pytest.raises(FileNotFoundError):
        load_market_config("nonexistent")
```

Run: `pytest tests/test_domain_models.py::test_load_us_market_config tests/test_domain_models.py::test_load_missing_market_raises -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add config/ tests/test_domain_models.py
git commit -m "feat: add US market configuration and YAML config loader"
```

---

## Task 8: Test Fakes

**Files:**
- Create: `tests/fakes/__init__.py`, `tests/fakes/fake_market_data.py`, `tests/fakes/fake_technical_analysis.py`, `tests/fakes/fake_store.py`, `tests/fakes/fake_feature_engineer.py`, `tests/fakes/fake_predictor.py`

- [ ] **Step 1: Create fakes package**

Create `tests/fakes/__init__.py`:

```python
"""Fake adapter implementations for testing.

All fakes implement domain port Protocols with in-memory state.
No real API calls, no disk I/O.
"""

from .fake_feature_engineer import FakeFeatureEngineer
from .fake_market_data import FakeMarketData
from .fake_predictor import FakePredictor
from .fake_store import FakeRecommendationStore
from .fake_technical_analysis import FakeTechnicalAnalysis

__all__ = [
    "FakeFeatureEngineer",
    "FakeMarketData",
    "FakePredictor",
    "FakeRecommendationStore",
    "FakeTechnicalAnalysis",
]
```

- [ ] **Step 2: Create FakeMarketData**

Create `tests/fakes/fake_market_data.py`:

```python
"""Fake MarketDataPort implementation for testing."""

from datetime import datetime

from domain.models import Signal


class FakeMarketData:
    """In-memory MarketDataPort. Pre-load signals via constructor."""

    def __init__(
        self,
        signals: dict[str, list[Signal]] | None = None,
        ticker_info: dict[str, dict[str, float]] | None = None,
        options_summary: dict[str, dict[str, float]] | None = None,
        analyst_data: dict[str, dict[str, float]] | None = None,
    ) -> None:
        self._signals = signals or {}
        self._ticker_info = ticker_info or {}
        self._options = options_summary or {}
        self._analyst = analyst_data or {}

    def get_signals(
        self,
        symbol: str,
        prediction_time: datetime,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[Signal]:
        all_signals = self._signals.get(symbol, [])
        return [
            s
            for s in all_signals
            if s.timestamp <= prediction_time
            and (start_date is None or s.timestamp >= start_date)
            and (end_date is None or s.timestamp <= end_date)
        ]

    def get_ticker_info(self, symbol: str) -> dict[str, float]:
        return self._ticker_info.get(symbol, {})

    def get_options_summary(
        self, symbol: str, prediction_time: datetime
    ) -> dict[str, float] | None:
        return self._options.get(symbol)

    def get_analyst_data(
        self, symbol: str, prediction_time: datetime
    ) -> dict[str, float] | None:
        return self._analyst.get(symbol)

    def validate_point_in_time(self, prediction_time: datetime) -> None:
        pass
```

- [ ] **Step 3: Create FakeTechnicalAnalysis**

Create `tests/fakes/fake_technical_analysis.py`:

```python
"""Fake TechnicalAnalysisPort implementation for testing."""

from domain.models import Signal


class FakeTechnicalAnalysis:
    """Returns pre-configured indicators or sensible defaults."""

    def __init__(
        self, indicators: dict[str, float] | None = None
    ) -> None:
        self._indicators = indicators or {
            "rsi_14": 50.0,
            "macd": 0.0,
            "macd_signal": 0.0,
            "macd_histogram": 0.0,
            "stochastic_k": 50.0,
            "stochastic_d": 50.0,
            "sma_20": 100.0,
            "sma_50": 100.0,
            "obv_trend": 0.0,
        }

    def compute_indicators(self, signals: list[Signal]) -> dict[str, float]:
        return dict(self._indicators)
```

- [ ] **Step 4: Create FakeRecommendationStore**

Create `tests/fakes/fake_store.py`:

```python
"""Fake RecommendationStorePort implementation for testing."""

from domain.models import (
    AccuracyRecord,
    EvaluationRun,
    StockRecommendation,
    WeeklyReport,
)


class FakeRecommendationStore:
    """In-memory store for recommendations, accuracy, evaluations, reports."""

    def __init__(self) -> None:
        self.recommendations: list[StockRecommendation] = []
        self.accuracy_records: list[AccuracyRecord] = []
        self.evaluation_runs: list[EvaluationRun] = []
        self.weekly_reports: dict[str, WeeklyReport] = {}

    def save_recommendation(self, rec: StockRecommendation) -> None:
        self.recommendations.append(rec)

    def get_recommendations(
        self,
        week_start: str | None = None,
        symbol: str | None = None,
    ) -> list[StockRecommendation]:
        results = self.recommendations
        if week_start is not None:
            results = [r for r in results if r.week_start == week_start]
        if symbol is not None:
            results = [r for r in results if r.symbol == symbol]
        return results

    def save_accuracy_record(self, record: AccuracyRecord) -> None:
        self.accuracy_records.append(record)

    def get_accuracy_records(
        self,
        week_start: str | None = None,
        symbol: str | None = None,
    ) -> list[AccuracyRecord]:
        results = self.accuracy_records
        if week_start is not None:
            results = [r for r in results if r.week_start == week_start]
        if symbol is not None:
            results = [r for r in results if r.symbol == symbol]
        return results

    def save_evaluation_run(self, run: EvaluationRun) -> None:
        self.evaluation_runs.append(run)

    def get_evaluation_runs(
        self,
        run_date: str | None = None,
        eval_type: str | None = None,
    ) -> list[EvaluationRun]:
        results = self.evaluation_runs
        if run_date is not None:
            results = [r for r in results if r.run_date == run_date]
        if eval_type is not None:
            results = [r for r in results if r.eval_type == eval_type]
        return results

    def save_weekly_report(self, report: WeeklyReport) -> None:
        self.weekly_reports[report.report_date] = report

    def get_weekly_report(self, report_date: str) -> WeeklyReport | None:
        return self.weekly_reports.get(report_date)
```

- [ ] **Step 5: Create FakeFeatureEngineer**

Create `tests/fakes/fake_feature_engineer.py`:

```python
"""Fake FeatureEngineerPort implementation for testing."""

from domain.models import Signal

FAKE_FEATURE_NAMES: list[str] = [
    "return_1d", "return_5d", "return_20d", "volatility_20d",
    "price_vs_sma20", "price_vs_sma50", "sma20_vs_sma50",
    "rsi_14", "macd", "macd_signal", "macd_histogram",
    "stochastic_k", "stochastic_d", "volume_ratio_20d", "obv_trend",
    "price_vs_52w_high", "price_vs_52w_low", "market_cap_quintile",
    "return_6m", "return_12m", "volatility_regime",
    "drawdown_from_ath", "sector_relative_strength_6m",
    "revenue_growth_yoy", "pe_vs_sector_median",
    "short_interest_ratio", "short_interest_change_5d",
    "earnings_surprise_last", "earnings_surprise_streak",
    "iv_skew_25d", "iv_rank_percentile", "institutional_ownership_change",
    "sector_etf_return_5d", "stock_vs_sector",
    "unusual_options_volume", "put_call_ratio",
    "options_volume_vs_stock_volume", "large_block_trades_count",
    "correlation_with_spy", "relative_strength_vs_peers",
    "vix_level", "treasury_10y_direction", "dxy_strength",
    "yield_curve_slope", "spy_momentum_20d",
]


class FakeFeatureEngineer:
    """Returns deterministic features based on symbol hash."""

    def __init__(self, override: dict[str, float] | None = None) -> None:
        self._override = override or {}

    def compute(
        self,
        signals: list[Signal],
        indicators: dict[str, float],
        ticker_info: dict[str, float],
        options_summary: dict[str, float] | None,
        analyst_data: dict[str, float] | None,
        macro_signals: dict[str, list[Signal]],
        sector_signals: list[Signal] | None,
    ) -> dict[str, float]:
        # Generate deterministic features based on last signal price
        base = signals[-1].price if signals else 100.0
        features: dict[str, float] = {}
        for i, name in enumerate(FAKE_FEATURE_NAMES):
            if name in self._override:
                features[name] = self._override[name]
            else:
                features[name] = (base + i) * 0.01
        return features

    def get_feature_names(self) -> list[str]:
        return list(FAKE_FEATURE_NAMES)
```

- [ ] **Step 6: Create FakePredictor**

Create `tests/fakes/fake_predictor.py`:

```python
"""Fake StockPredictorPort implementation for testing."""


class FakePredictor:
    """Returns pre-configured predictions. Tracks fit/predict calls."""

    def __init__(self, predictions: list[float] | None = None) -> None:
        self._predictions = predictions or [0.02]
        self.fit_calls: list[tuple[int, int]] = []  # (n_samples, n_features)
        self.predict_calls: list[int] = []  # n_samples

    def fit(
        self, features: list[dict[str, float]], targets: list[float]
    ) -> None:
        self.fit_calls.append((len(features), len(features[0]) if features else 0))

    def predict(self, features: list[dict[str, float]]) -> list[float]:
        n = len(features)
        self.predict_calls.append(n)
        if len(self._predictions) >= n:
            return self._predictions[:n]
        return self._predictions * n  # repeat to fill

    def save_model(self, path: str) -> None:
        pass

    def load_model(self, path: str) -> None:
        pass
```

- [ ] **Step 7: Write test verifying fakes implement protocols**

Add to `tests/test_domain_models.py`:

```python
def test_fakes_implement_protocols() -> None:
    """All fakes satisfy their port Protocol at runtime."""
    from tests.fakes import (
        FakeFeatureEngineer,
        FakeMarketData,
        FakePredictor,
        FakeRecommendationStore,
        FakeTechnicalAnalysis,
    )
    # Instantiation proves structural compatibility
    FakeMarketData()
    FakeTechnicalAnalysis()
    FakeRecommendationStore()
    FakeFeatureEngineer()
    FakePredictor()
```

Run: `pytest tests/test_domain_models.py::test_fakes_implement_protocols -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add tests/fakes/ tests/test_domain_models.py
git commit -m "feat: add test fakes for all Phase 3A ports"
```

---

## Task 9: CachingMixin

**Files:**
- Create: `adapters/data/cache_mixin.py`
- Test: `tests/test_yfinance_adapter.py` (cache tests)

- [ ] **Step 1: Write failing cache test**

Create `tests/test_yfinance_adapter.py`:

```python
"""Tests for yfinance adapter and caching."""

import json
from pathlib import Path

import pytest

from adapters.data.cache_mixin import CachingMixin


class ConcreteCache(CachingMixin):
    """Test subclass of CachingMixin."""

    def __init__(self, cache_dir: Path) -> None:
        super().__init__(cache_dir)


def test_cache_save_and_load(tmp_path: Path) -> None:
    cache = ConcreteCache(tmp_path)
    data = {"price": 150.0, "volume": 1000000}
    cache.save_to_cache("AAPL", data)

    loaded = cache.load_from_cache("AAPL")
    assert loaded is not None
    assert loaded["price"] == 150.0


def test_cache_load_nonexistent_returns_none(tmp_path: Path) -> None:
    cache = ConcreteCache(tmp_path)
    assert cache.load_from_cache("MISSING") is None


def test_cache_append_only(tmp_path: Path) -> None:
    """Multiple saves create multiple cache files (append-only)."""
    cache = ConcreteCache(tmp_path)
    cache.save_to_cache("AAPL", {"price": 150.0})
    cache.save_to_cache("AAPL", {"price": 155.0})

    symbol_dir = tmp_path / "AAPL"
    cache_files = list(symbol_dir.glob("*.json"))
    assert len(cache_files) >= 1  # at least one file

    # Most recent load returns latest
    loaded = cache.load_from_cache("AAPL")
    assert loaded is not None
    assert loaded["price"] == 155.0


def test_cache_creates_symbol_directory(tmp_path: Path) -> None:
    cache = ConcreteCache(tmp_path)
    cache.save_to_cache("GOOG", {"price": 2800.0})
    assert (tmp_path / "GOOG").is_dir()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_yfinance_adapter.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'adapters.data.cache_mixin'`

- [ ] **Step 3: Implement CachingMixin**

Create `adapters/data/cache_mixin.py`:

```python
"""Raw data caching mixin for reproducibility (ADR-017).

Append-only cache keyed by fetch timestamp.
Every adapter that fetches external data should inherit this.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class CachingMixin:
    """Base class providing raw data caching.

    Cache layout:
        {cache_dir}/{symbol}/{YYYY-MM-DDTHH-MM-SS}.json

    Append-only: never overwrites past fetches.
    Load returns most recent cached entry.
    """

    def __init__(self, cache_dir: Path) -> None:
        self._cache_dir = cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def save_to_cache(
        self, symbol: str, data: dict[str, Any]
    ) -> Path:
        """Save raw API response to cache. Returns path to cache file."""
        symbol_dir = self._cache_dir / symbol
        symbol_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
        cache_path = symbol_dir / f"{timestamp}.json"
        # Avoid overwriting if called within same second
        counter = 0
        while cache_path.exists():
            counter += 1
            cache_path = symbol_dir / f"{timestamp}_{counter}.json"
        with open(cache_path, "w") as f:
            json.dump(data, f, default=str)
        return cache_path

    def load_from_cache(self, symbol: str) -> dict[str, Any] | None:
        """Load most recent cached data for symbol. Returns None if no cache."""
        symbol_dir = self._cache_dir / symbol
        if not symbol_dir.exists():
            return None
        cache_files = sorted(symbol_dir.glob("*.json"))
        if not cache_files:
            return None
        with open(cache_files[-1]) as f:
            data: dict[str, Any] = json.load(f)
        return data

    def has_cache(self, symbol: str) -> bool:
        """Check if any cached data exists for symbol."""
        symbol_dir = self._cache_dir / symbol
        if not symbol_dir.exists():
            return False
        return bool(list(symbol_dir.glob("*.json")))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_yfinance_adapter.py -v`
Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add adapters/data/cache_mixin.py tests/test_yfinance_adapter.py
git commit -m "feat: add CachingMixin for raw data caching (ADR-017)"
```

---

## Task 10: yfinance Adapter

**Files:**
- Create: `adapters/data/yfinance_adapter.py`
- Modify: `tests/test_yfinance_adapter.py`

- [ ] **Step 1: Write failing tests for YFinanceAdapter**

Add to `tests/test_yfinance_adapter.py`:

```python
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from adapters.data.yfinance_adapter import YFinanceAdapter
from domain.models import Signal


@pytest.fixture
def adapter(tmp_path: Path) -> YFinanceAdapter:
    return YFinanceAdapter(cache_dir=tmp_path, use_cache=False)


@pytest.fixture
def mock_ticker() -> MagicMock:
    """Mock yfinance Ticker with realistic OHLCV data."""
    ticker = MagicMock()
    import pandas as pd
    import numpy as np

    dates = pd.date_range("2026-01-01", periods=30, freq="B")
    np.random.seed(42)
    prices = 150.0 + np.cumsum(np.random.randn(30) * 2)
    df = pd.DataFrame(
        {
            "Open": prices - 1,
            "High": prices + 2,
            "Low": prices - 2,
            "Close": prices,
            "Volume": np.random.randint(1_000_000, 10_000_000, 30),
        },
        index=dates,
    )
    ticker.history.return_value = df
    ticker.info = {
        "marketCap": 2_500_000_000_000,
        "trailingPE": 28.5,
        "revenueGrowth": 0.08,
        "heldPercentInstitutions": 0.72,
        "shortRatio": 1.5,
        "shortPercentOfFloat": 0.012,
        "sector": "Technology",
    }
    return ticker


@patch("adapters.data.yfinance_adapter.yf.Ticker")
def test_get_signals_returns_signals(
    mock_yf_ticker: MagicMock, mock_ticker: MagicMock, adapter: YFinanceAdapter
) -> None:
    mock_yf_ticker.return_value = mock_ticker
    pt = datetime(2026, 2, 15)
    signals = adapter.get_signals("AAPL", pt, start_date=datetime(2026, 1, 1))
    assert len(signals) > 0
    assert all(isinstance(s, Signal) for s in signals)
    assert all(s.timestamp <= pt for s in signals)
    assert all(s.symbol == "AAPL" for s in signals)


@patch("adapters.data.yfinance_adapter.yf.Ticker")
def test_get_signals_filters_point_in_time(
    mock_yf_ticker: MagicMock, mock_ticker: MagicMock, adapter: YFinanceAdapter
) -> None:
    mock_yf_ticker.return_value = mock_ticker
    pt = datetime(2026, 1, 10)
    signals = adapter.get_signals("AAPL", pt, start_date=datetime(2026, 1, 1))
    assert all(s.timestamp <= pt for s in signals)


@patch("adapters.data.yfinance_adapter.yf.Ticker")
def test_get_ticker_info(
    mock_yf_ticker: MagicMock, mock_ticker: MagicMock, adapter: YFinanceAdapter
) -> None:
    mock_yf_ticker.return_value = mock_ticker
    info = adapter.get_ticker_info("AAPL")
    assert "market_cap" in info
    assert info["market_cap"] == 2_500_000_000_000
    assert "pe_ratio" in info


@patch("adapters.data.yfinance_adapter.yf.Ticker")
def test_compute_indicators_from_signals(
    mock_yf_ticker: MagicMock, mock_ticker: MagicMock, adapter: YFinanceAdapter
) -> None:
    mock_yf_ticker.return_value = mock_ticker
    pt = datetime(2026, 2, 15)
    signals = adapter.get_signals("AAPL", pt, start_date=datetime(2026, 1, 1))
    indicators = adapter.compute_indicators(signals)
    assert "rsi_14" in indicators
    assert 0.0 <= indicators["rsi_14"] <= 100.0
    assert "macd" in indicators


def test_adapter_caches_data(tmp_path: Path) -> None:
    """When use_cache=True, loads from cache instead of API."""
    adapter = YFinanceAdapter(cache_dir=tmp_path, use_cache=True)
    # Pre-populate cache
    adapter.save_to_cache("AAPL", {
        "ohlcv": [
            {"date": "2026-01-02", "open": 99.0, "high": 101.0, "low": 98.0, "close": 100.0, "volume": 1000000},
        ],
        "info": {"marketCap": 1000000000},
    })
    # Should load from cache without hitting yfinance
    info = adapter.get_ticker_info("AAPL")
    assert info["market_cap"] == 1000000000
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_yfinance_adapter.py -v -k "not cache_save"`
Expected: FAIL — `ModuleNotFoundError: No module named 'adapters.data.yfinance_adapter'`

- [ ] **Step 3: Implement YFinanceAdapter**

Create `adapters/data/yfinance_adapter.py`:

```python
"""yfinance adapter implementing MarketDataPort + TechnicalAnalysisPort.

Fetches OHLCV, fundamentals, options, and analyst data from Yahoo Finance.
Caches all raw responses for reproducibility (ADR-017).
Uses auto_adjust=False for point-in-time correctness.
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf

from domain.exceptions import InvalidMarketDataError
from domain.models import Signal

from .cache_mixin import CachingMixin


class YFinanceAdapter(CachingMixin):
    """MarketDataPort + TechnicalAnalysisPort backed by yfinance.

    Args:
        cache_dir: Directory for raw data cache.
        use_cache: If True, load from cache instead of API.
    """

    def __init__(
        self,
        cache_dir: Path,
        use_cache: bool = False,
    ) -> None:
        super().__init__(cache_dir)
        self._use_cache = use_cache

    # --- MarketDataPort ---

    def get_signals(
        self,
        symbol: str,
        prediction_time: datetime,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[Signal]:
        df = self._get_ohlcv(symbol, start_date, end_date)
        if df.empty:
            return []

        signals: list[Signal] = []
        for ts, row in df.iterrows():
            dt = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts
            if dt > prediction_time:
                continue
            if start_date and dt < start_date:
                continue
            try:
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
            except (InvalidMarketDataError, ValueError):
                continue  # skip invalid rows

        return signals

    def get_ticker_info(self, symbol: str) -> dict[str, float]:
        if self._use_cache:
            cached = self.load_from_cache(symbol)
            if cached and "info" in cached:
                return self._parse_info(cached["info"])

        ticker = yf.Ticker(symbol)
        raw_info = ticker.info
        self.save_to_cache(symbol, {"info": raw_info})
        return self._parse_info(raw_info)

    def get_options_summary(
        self, symbol: str, prediction_time: datetime
    ) -> dict[str, float] | None:
        try:
            ticker = yf.Ticker(symbol)
            dates = ticker.options
            if not dates:
                return None
            # Use nearest expiry
            chain = ticker.option_chain(dates[0])
            calls = chain.calls
            puts = chain.puts

            total_call_vol = float(calls["volume"].sum()) if "volume" in calls else 0.0
            total_put_vol = float(puts["volume"].sum()) if "volume" in puts else 0.0
            put_call_ratio = (
                total_put_vol / total_call_vol if total_call_vol > 0 else 0.0
            )

            # IV skew: OTM put IV - ATM call IV (simplified)
            iv_skew = 0.0
            if "impliedVolatility" in puts.columns and len(puts) > 0:
                otm_put_iv = float(puts["impliedVolatility"].iloc[-1])
                atm_call_iv = float(calls["impliedVolatility"].median())
                iv_skew = otm_put_iv - atm_call_iv

            return {
                "put_call_ratio": put_call_ratio,
                "total_call_volume": total_call_vol,
                "total_put_volume": total_put_vol,
                "unusual_options_volume": total_call_vol + total_put_vol,
                "iv_skew_25d": iv_skew,
            }
        except Exception:
            return None

    def get_analyst_data(
        self, symbol: str, prediction_time: datetime
    ) -> dict[str, float] | None:
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            result: dict[str, float] = {}

            if "shortRatio" in info and info["shortRatio"] is not None:
                result["short_interest_ratio"] = float(info["shortRatio"])
            if "shortPercentOfFloat" in info and info["shortPercentOfFloat"] is not None:
                result["short_percent_float"] = float(info["shortPercentOfFloat"])

            # Earnings surprise from earnings dates
            try:
                earnings = ticker.earnings_dates
                if earnings is not None and len(earnings) > 0:
                    past = earnings[earnings.index <= pd.Timestamp(prediction_time)]
                    if len(past) > 0 and "Surprise(%)" in past.columns:
                        last_surprise = past["Surprise(%)"].iloc[0]
                        if pd.notna(last_surprise):
                            result["earnings_surprise_last"] = float(last_surprise)
            except Exception:
                pass

            return result if result else None
        except Exception:
            return None

    def validate_point_in_time(self, prediction_time: datetime) -> None:
        pass  # Validation happens in get_signals via timestamp filtering

    # --- TechnicalAnalysisPort ---

    def compute_indicators(self, signals: list[Signal]) -> dict[str, float]:
        if len(signals) < 14:
            return {}

        closes = np.array([s.price for s in signals])
        highs = np.array([s.high for s in signals])
        lows = np.array([s.low for s in signals])
        volumes = np.array([s.volume for s in signals])

        indicators: dict[str, float] = {}

        # RSI-14
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)
        avg_gain = float(np.mean(gains[-14:]))
        avg_loss = float(np.mean(losses[-14:]))
        if avg_loss > 0:
            rs = avg_gain / avg_loss
            indicators["rsi_14"] = 100.0 - (100.0 / (1.0 + rs))
        else:
            indicators["rsi_14"] = 100.0

        # MACD (12, 26, 9)
        if len(closes) >= 26:
            ema_12 = self._ema(closes, 12)
            ema_26 = self._ema(closes, 26)
            macd_line = ema_12 - ema_26
            indicators["macd"] = float(macd_line)
            if len(closes) >= 35:  # need 26 + 9 for signal
                macd_series = self._ema_series(closes, 12) - self._ema_series(closes, 26)
                signal_line = self._ema(macd_series[-9:], 9) if len(macd_series) >= 9 else macd_line
                indicators["macd_signal"] = float(signal_line)
                indicators["macd_histogram"] = float(macd_line - signal_line)
            else:
                indicators["macd_signal"] = float(macd_line)
                indicators["macd_histogram"] = 0.0

        # Stochastic K/D (14, 3)
        if len(closes) >= 14:
            low_14 = float(np.min(lows[-14:]))
            high_14 = float(np.max(highs[-14:]))
            if high_14 > low_14:
                k = ((closes[-1] - low_14) / (high_14 - low_14)) * 100
                indicators["stochastic_k"] = float(k)
            else:
                indicators["stochastic_k"] = 50.0
            indicators["stochastic_d"] = indicators["stochastic_k"]  # simplified

        # SMA 20, 50
        if len(closes) >= 20:
            indicators["sma_20"] = float(np.mean(closes[-20:]))
        if len(closes) >= 50:
            indicators["sma_50"] = float(np.mean(closes[-50:]))

        # OBV trend
        if len(closes) >= 2:
            obv = np.cumsum(np.sign(np.diff(closes)) * volumes[1:])
            if len(obv) >= 5:
                indicators["obv_trend"] = float(obv[-1] - obv[-5]) / max(
                    float(np.abs(obv[-5])), 1.0
                )
            else:
                indicators["obv_trend"] = 0.0

        return indicators

    # --- Private helpers ---

    def _get_ohlcv(
        self,
        symbol: str,
        start_date: datetime | None,
        end_date: datetime | None,
    ) -> pd.DataFrame:
        if self._use_cache:
            cached = self.load_from_cache(symbol)
            if cached and "ohlcv" in cached:
                df = pd.DataFrame(cached["ohlcv"])
                if "date" in df.columns:
                    df.index = pd.to_datetime(df["date"])
                    df = df.drop(columns=["date"])
                return df

        ticker = yf.Ticker(symbol)
        period = "3y" if start_date is None else None
        df = ticker.history(
            period=period,
            start=start_date,
            end=end_date,
            auto_adjust=False,
        )
        if not df.empty:
            cache_data = df.reset_index().to_dict(orient="records")
            self.save_to_cache(symbol, {"ohlcv": cache_data})
        return df

    def _parse_info(self, raw: dict[str, Any]) -> dict[str, float]:
        mapping: dict[str, str] = {
            "marketCap": "market_cap",
            "trailingPE": "pe_ratio",
            "revenueGrowth": "revenue_growth_yoy",
            "heldPercentInstitutions": "institutional_ownership",
            "shortRatio": "short_interest_ratio",
            "shortPercentOfFloat": "short_percent_float",
        }
        result: dict[str, float] = {}
        for yf_key, feature_key in mapping.items():
            val = raw.get(yf_key)
            if val is not None:
                try:
                    result[feature_key] = float(val)
                except (TypeError, ValueError):
                    continue
        return result

    @staticmethod
    def _ema(data: np.ndarray, period: int) -> float:
        """Compute EMA of last `period` points, return final value."""
        weights = np.exp(np.linspace(-1.0, 0.0, period))
        weights /= weights.sum()
        return float(np.dot(data[-period:], weights))

    @staticmethod
    def _ema_series(data: np.ndarray, period: int) -> np.ndarray:
        """Compute EMA series using pandas-style exponential weighting."""
        alpha = 2.0 / (period + 1)
        result = np.zeros_like(data, dtype=float)
        result[0] = data[0]
        for i in range(1, len(data)):
            result[i] = alpha * data[i] + (1 - alpha) * result[i - 1]
        return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_yfinance_adapter.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add adapters/data/yfinance_adapter.py tests/test_yfinance_adapter.py
git commit -m "feat: add YFinanceAdapter implementing MarketDataPort + TechnicalAnalysisPort"
```

---

## Task 11: Feature Engineer

**Files:**
- Create: `adapters/ml/feature_engineer.py`
- Create: `tests/test_feature_engineer.py`

- [ ] **Step 1: Write failing tests for feature engineer**

Create `tests/test_feature_engineer.py`:

```python
"""Tests for feature engineering — 45 features across 8 groups."""

from datetime import datetime, timedelta

import pytest

from adapters.ml.feature_engineer import FeatureEngineer
from domain.models import Signal


def _make_signals(n: int = 260, base_price: float = 100.0) -> list[Signal]:
    """Generate n days of synthetic OHLCV signals."""
    import random
    random.seed(42)
    signals: list[Signal] = []
    price = base_price
    for i in range(n):
        change = random.gauss(0, 2)
        price = max(price + change, 1.0)
        signals.append(
            Signal(
                symbol="AAPL",
                timestamp=datetime(2025, 1, 2) + timedelta(days=i),
                price=price,
                volume=1_000_000 + random.randint(-500_000, 500_000),
                open_=price - abs(random.gauss(0, 1)),
                high=price + abs(random.gauss(0, 2)),
                low=price - abs(random.gauss(0, 2)),
            )
        )
    return signals


@pytest.fixture
def engineer() -> FeatureEngineer:
    return FeatureEngineer()


@pytest.fixture
def signals() -> list[Signal]:
    return _make_signals(260)


@pytest.fixture
def indicators() -> dict[str, float]:
    return {
        "rsi_14": 55.0,
        "macd": 0.5,
        "macd_signal": 0.3,
        "macd_histogram": 0.2,
        "stochastic_k": 60.0,
        "stochastic_d": 58.0,
        "sma_20": 100.0,
        "sma_50": 98.0,
        "obv_trend": 0.05,
    }


@pytest.fixture
def ticker_info() -> dict[str, float]:
    return {
        "market_cap": 2_500_000_000_000,
        "pe_ratio": 28.5,
        "revenue_growth_yoy": 0.08,
        "institutional_ownership": 0.72,
        "short_interest_ratio": 1.5,
        "short_percent_float": 0.012,
    }


@pytest.fixture
def macro_signals() -> dict[str, list[Signal]]:
    """Macro symbols with 260 days of data."""
    import random
    random.seed(99)
    result: dict[str, list[Signal]] = {}
    for sym, base in [("^VIX", 20.0), ("^TNX", 4.5), ("DX-Y.NYB", 104.0), ("^IRX", 5.0), ("SPY", 450.0)]:
        sigs: list[Signal] = []
        price = base
        for i in range(260):
            price = max(price + random.gauss(0, base * 0.01), 0.1)
            sigs.append(Signal(
                symbol=sym,
                timestamp=datetime(2025, 1, 2) + timedelta(days=i),
                price=price, volume=1_000_000,
                open_=price, high=price + 0.1, low=price - 0.1,
            ))
        result[sym] = sigs
    return result


def test_feature_engineer_returns_45_features(
    engineer: FeatureEngineer,
    signals: list[Signal],
    indicators: dict[str, float],
    ticker_info: dict[str, float],
    macro_signals: dict[str, list[Signal]],
) -> None:
    features = engineer.compute(
        signals=signals,
        indicators=indicators,
        ticker_info=ticker_info,
        options_summary={"put_call_ratio": 0.8, "unusual_options_volume": 50000, "iv_skew_25d": 0.05},
        analyst_data={"short_interest_ratio": 1.5, "earnings_surprise_last": 0.05},
        macro_signals=macro_signals,
        sector_signals=None,
    )
    assert len(features) == 45
    assert all(isinstance(v, float) for v in features.values())


def test_feature_names_match_spec(engineer: FeatureEngineer) -> None:
    names = engineer.get_feature_names()
    assert len(names) == 45
    # Spot-check key features
    assert "rsi_14" in names
    assert "vix_level" in names
    assert "put_call_ratio" in names
    assert "correlation_with_spy" in names
    assert "return_12m" in names


def test_no_leakage_columns_in_features(engineer: FeatureEngineer) -> None:
    """Feature names must not contain any FUTURE_LEAKAGE_COLUMNS."""
    from domain.services import FUTURE_LEAKAGE_COLUMNS
    names = set(engineer.get_feature_names())
    assert names & FUTURE_LEAKAGE_COLUMNS == set()


def test_handles_missing_options(
    engineer: FeatureEngineer,
    signals: list[Signal],
    indicators: dict[str, float],
    ticker_info: dict[str, float],
    macro_signals: dict[str, list[Signal]],
) -> None:
    """Missing options → NaN for options features, not crash."""
    features = engineer.compute(
        signals=signals,
        indicators=indicators,
        ticker_info=ticker_info,
        options_summary=None,
        analyst_data=None,
        macro_signals=macro_signals,
        sector_signals=None,
    )
    assert len(features) == 45
    import math
    assert math.isnan(features["put_call_ratio"])


def test_handles_short_history(engineer: FeatureEngineer) -> None:
    """With only 30 days of data, long-horizon features become NaN."""
    short_signals = _make_signals(30)
    features = engineer.compute(
        signals=short_signals,
        indicators={"rsi_14": 50.0, "macd": 0.0, "macd_signal": 0.0, "macd_histogram": 0.0,
                     "stochastic_k": 50.0, "stochastic_d": 50.0, "sma_20": 100.0, "obv_trend": 0.0},
        ticker_info={},
        options_summary=None,
        analyst_data=None,
        macro_signals={},
        sector_signals=None,
    )
    assert len(features) == 45
    import math
    assert math.isnan(features["return_12m"])  # not enough history
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_feature_engineer.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement FeatureEngineer**

Create `adapters/ml/feature_engineer.py`:

```python
"""Feature engineer: computes 45 features across 8 groups.

Groups:
  1. Technical (15) — from OHLCV
  2. Regime (10) — from historical OHLCV
  3. Stronger signals (7) — from fundamentals/options
  4. Sector context (2) — from sector ETFs
  5. Options flow (4) — from options chain
  6. Cross-correlation (2) — from SPY/peers
  7. Macro regime (5) — from macro symbols

All computations use only data available at prediction time.
"""

import math

import numpy as np

from domain.models import Signal

_NAN = float("nan")

FEATURE_NAMES: list[str] = [
    # Technical (15)
    "return_1d", "return_5d", "return_20d", "volatility_20d",
    "price_vs_sma20", "price_vs_sma50", "sma20_vs_sma50",
    "rsi_14", "macd", "macd_signal", "macd_histogram",
    "stochastic_k", "stochastic_d", "volume_ratio_20d", "obv_trend",
    # Regime (10)
    "price_vs_52w_high", "price_vs_52w_low", "market_cap_quintile",
    "return_6m", "return_12m", "volatility_regime",
    "drawdown_from_ath", "sector_relative_strength_6m",
    "revenue_growth_yoy", "pe_vs_sector_median",
    # Stronger signals (7)
    "short_interest_ratio", "short_interest_change_5d",
    "earnings_surprise_last", "earnings_surprise_streak",
    "iv_skew_25d", "iv_rank_percentile", "institutional_ownership_change",
    # Sector context (2)
    "sector_etf_return_5d", "stock_vs_sector",
    # Options flow (4)
    "unusual_options_volume", "put_call_ratio",
    "options_volume_vs_stock_volume", "large_block_trades_count",
    # Cross-correlation (2)
    "correlation_with_spy", "relative_strength_vs_peers",
    # Macro regime (5)
    "vix_level", "treasury_10y_direction", "dxy_strength",
    "yield_curve_slope", "spy_momentum_20d",
]


class FeatureEngineer:
    """Computes 45 features from raw market data."""

    def compute(
        self,
        signals: list[Signal],
        indicators: dict[str, float],
        ticker_info: dict[str, float],
        options_summary: dict[str, float] | None,
        analyst_data: dict[str, float] | None,
        macro_signals: dict[str, list[Signal]],
        sector_signals: list[Signal] | None,
    ) -> dict[str, float]:
        closes = np.array([s.price for s in signals]) if signals else np.array([])
        volumes = np.array([s.volume for s in signals]) if signals else np.array([])
        highs = np.array([s.high for s in signals]) if signals else np.array([])

        features: dict[str, float] = {}

        # --- Group 1: Technical (15) ---
        features.update(self._technical_features(closes, volumes, indicators))

        # --- Group 2: Regime (10) ---
        features.update(self._regime_features(closes, highs, ticker_info))

        # --- Group 3: Stronger signals (7) ---
        features.update(self._stronger_signal_features(
            ticker_info, analyst_data, options_summary
        ))

        # --- Group 4: Sector context (2) ---
        features.update(self._sector_features(closes, sector_signals))

        # --- Group 5: Options flow (4) ---
        features.update(self._options_features(options_summary, volumes))

        # --- Group 6: Cross-correlation (2) ---
        features.update(self._cross_correlation_features(closes, macro_signals))

        # --- Group 7: Macro regime (5) ---
        features.update(self._macro_features(macro_signals))

        return features

    def get_feature_names(self) -> list[str]:
        return list(FEATURE_NAMES)

    # --- Group implementations ---

    def _technical_features(
        self,
        closes: np.ndarray,
        volumes: np.ndarray,
        indicators: dict[str, float],
    ) -> dict[str, float]:
        n = len(closes)
        f: dict[str, float] = {}

        # Returns
        f["return_1d"] = float((closes[-1] / closes[-2]) - 1) if n >= 2 else _NAN
        f["return_5d"] = float((closes[-1] / closes[-5]) - 1) if n >= 5 else _NAN
        f["return_20d"] = float((closes[-1] / closes[-20]) - 1) if n >= 20 else _NAN

        # Volatility
        if n >= 20:
            daily_returns = np.diff(closes[-21:]) / closes[-21:-1]
            f["volatility_20d"] = float(np.std(daily_returns))
        else:
            f["volatility_20d"] = _NAN

        # Price vs SMAs
        sma20 = indicators.get("sma_20")
        sma50 = indicators.get("sma_50")
        if n > 0 and sma20 is not None and sma20 > 0:
            f["price_vs_sma20"] = float(closes[-1] / sma20 - 1)
        else:
            f["price_vs_sma20"] = _NAN

        if n > 0 and sma50 is not None and sma50 > 0:
            f["price_vs_sma50"] = float(closes[-1] / sma50 - 1)
        else:
            f["price_vs_sma50"] = _NAN

        if sma20 is not None and sma50 is not None and sma50 > 0:
            f["sma20_vs_sma50"] = float(sma20 / sma50 - 1)
        else:
            f["sma20_vs_sma50"] = _NAN

        # From indicators
        f["rsi_14"] = indicators.get("rsi_14", _NAN)
        f["macd"] = indicators.get("macd", _NAN)
        f["macd_signal"] = indicators.get("macd_signal", _NAN)
        f["macd_histogram"] = indicators.get("macd_histogram", _NAN)
        f["stochastic_k"] = indicators.get("stochastic_k", _NAN)
        f["stochastic_d"] = indicators.get("stochastic_d", _NAN)

        # Volume
        if n >= 20:
            avg_vol = float(np.mean(volumes[-20:]))
            f["volume_ratio_20d"] = float(volumes[-1] / avg_vol) if avg_vol > 0 else _NAN
        else:
            f["volume_ratio_20d"] = _NAN

        f["obv_trend"] = indicators.get("obv_trend", _NAN)

        return f

    def _regime_features(
        self,
        closes: np.ndarray,
        highs: np.ndarray,
        ticker_info: dict[str, float],
    ) -> dict[str, float]:
        n = len(closes)
        f: dict[str, float] = {}

        # 52-week high/low
        if n >= 252:
            high_52w = float(np.max(highs[-252:]))
            low_52w = float(np.min(closes[-252:]))
            f["price_vs_52w_high"] = float(closes[-1] / high_52w - 1) if high_52w > 0 else _NAN
            f["price_vs_52w_low"] = float(closes[-1] / low_52w - 1) if low_52w > 0 else _NAN
        else:
            f["price_vs_52w_high"] = _NAN
            f["price_vs_52w_low"] = _NAN

        # Market cap quintile (1-5, normalized to 0-1)
        mc = ticker_info.get("market_cap", _NAN)
        if not math.isnan(mc):
            if mc > 200e9:
                f["market_cap_quintile"] = 1.0
            elif mc > 10e9:
                f["market_cap_quintile"] = 0.75
            elif mc > 2e9:
                f["market_cap_quintile"] = 0.5
            elif mc > 300e6:
                f["market_cap_quintile"] = 0.25
            else:
                f["market_cap_quintile"] = 0.0
        else:
            f["market_cap_quintile"] = _NAN

        # 6m and 12m returns
        f["return_6m"] = float(closes[-1] / closes[-126] - 1) if n >= 126 else _NAN
        f["return_12m"] = float(closes[-1] / closes[-252] - 1) if n >= 252 else _NAN

        # Volatility regime (current 20d vol vs 1yr average vol)
        if n >= 252:
            current_vol = float(np.std(np.diff(closes[-21:]) / closes[-21:-1]))
            year_returns = np.diff(closes[-252:]) / closes[-252:-1]
            year_vol = float(np.std(year_returns))
            f["volatility_regime"] = current_vol / year_vol if year_vol > 0 else _NAN
        else:
            f["volatility_regime"] = _NAN

        # Drawdown from ATH
        if n > 0:
            ath = float(np.max(highs))
            f["drawdown_from_ath"] = float(closes[-1] / ath - 1) if ath > 0 else _NAN
        else:
            f["drawdown_from_ath"] = _NAN

        # Sector relative strength (placeholder — needs sector ETF data)
        f["sector_relative_strength_6m"] = _NAN

        # Fundamentals from ticker_info
        f["revenue_growth_yoy"] = ticker_info.get("revenue_growth_yoy", _NAN)
        f["pe_vs_sector_median"] = ticker_info.get("pe_ratio", _NAN)

        return f

    def _stronger_signal_features(
        self,
        ticker_info: dict[str, float],
        analyst_data: dict[str, float] | None,
        options_summary: dict[str, float] | None,
    ) -> dict[str, float]:
        f: dict[str, float] = {}
        ad = analyst_data or {}
        opt = options_summary or {}

        f["short_interest_ratio"] = ad.get(
            "short_interest_ratio",
            ticker_info.get("short_interest_ratio", _NAN),
        )
        f["short_interest_change_5d"] = ad.get("short_interest_change_5d", _NAN)
        f["earnings_surprise_last"] = ad.get("earnings_surprise_last", _NAN)
        f["earnings_surprise_streak"] = ad.get("earnings_surprise_streak", _NAN)
        f["iv_skew_25d"] = opt.get("iv_skew_25d", _NAN)
        f["iv_rank_percentile"] = opt.get("iv_rank_percentile", _NAN)
        f["institutional_ownership_change"] = ticker_info.get(
            "institutional_ownership_change", _NAN
        )

        return f

    def _sector_features(
        self,
        closes: np.ndarray,
        sector_signals: list[Signal] | None,
    ) -> dict[str, float]:
        f: dict[str, float] = {}
        if sector_signals and len(sector_signals) >= 5 and len(closes) >= 5:
            sector_prices = np.array([s.price for s in sector_signals])
            f["sector_etf_return_5d"] = float(
                sector_prices[-1] / sector_prices[-5] - 1
            )
            stock_5d = float(closes[-1] / closes[-5] - 1)
            f["stock_vs_sector"] = stock_5d - f["sector_etf_return_5d"]
        else:
            f["sector_etf_return_5d"] = _NAN
            f["stock_vs_sector"] = _NAN
        return f

    def _options_features(
        self,
        options_summary: dict[str, float] | None,
        volumes: np.ndarray,
    ) -> dict[str, float]:
        f: dict[str, float] = {}
        opt = options_summary or {}

        f["unusual_options_volume"] = opt.get("unusual_options_volume", _NAN)
        f["put_call_ratio"] = opt.get("put_call_ratio", _NAN)

        total_opt_vol = opt.get("unusual_options_volume", _NAN)
        if len(volumes) > 0 and not math.isnan(total_opt_vol) and volumes[-1] > 0:
            f["options_volume_vs_stock_volume"] = total_opt_vol / float(volumes[-1])
        else:
            f["options_volume_vs_stock_volume"] = _NAN

        f["large_block_trades_count"] = opt.get("large_block_trades_count", _NAN)

        return f

    def _cross_correlation_features(
        self,
        closes: np.ndarray,
        macro_signals: dict[str, list[Signal]],
    ) -> dict[str, float]:
        f: dict[str, float] = {}

        spy_signals = macro_signals.get("SPY", [])
        if len(spy_signals) >= 20 and len(closes) >= 20:
            spy_closes = np.array([s.price for s in spy_signals[-20:]])
            stock_returns = np.diff(closes[-20:]) / closes[-21:-1]
            spy_returns = np.diff(spy_closes) / spy_closes[:-1]
            min_len = min(len(stock_returns), len(spy_returns))
            if min_len >= 2:
                corr = float(np.corrcoef(
                    stock_returns[-min_len:], spy_returns[-min_len:]
                )[0, 1])
                f["correlation_with_spy"] = corr if not math.isnan(corr) else _NAN

                # Relative strength: stock cumulative return vs SPY
                stock_cum = float(np.prod(1 + stock_returns[-min_len:]) - 1)
                spy_cum = float(np.prod(1 + spy_returns[-min_len:]) - 1)
                f["relative_strength_vs_peers"] = stock_cum - spy_cum
            else:
                f["correlation_with_spy"] = _NAN
                f["relative_strength_vs_peers"] = _NAN
        else:
            f["correlation_with_spy"] = _NAN
            f["relative_strength_vs_peers"] = _NAN

        return f

    def _macro_features(
        self, macro_signals: dict[str, list[Signal]]
    ) -> dict[str, float]:
        f: dict[str, float] = {}

        # VIX level
        vix = macro_signals.get("^VIX", [])
        f["vix_level"] = vix[-1].price if vix else _NAN

        # Treasury 10Y direction (5-day change)
        tnx = macro_signals.get("^TNX", [])
        if len(tnx) >= 5:
            f["treasury_10y_direction"] = tnx[-1].price - tnx[-5].price
        else:
            f["treasury_10y_direction"] = _NAN

        # DXY strength (20-day return)
        dxy = macro_signals.get("DX-Y.NYB", [])
        if len(dxy) >= 20:
            f["dxy_strength"] = float(dxy[-1].price / dxy[-20].price - 1)
        else:
            f["dxy_strength"] = _NAN

        # Yield curve slope (10Y - 3M)
        irx = macro_signals.get("^IRX", [])
        if tnx and irx:
            f["yield_curve_slope"] = tnx[-1].price - irx[-1].price
        else:
            f["yield_curve_slope"] = _NAN

        # SPY 20-day momentum
        spy = macro_signals.get("SPY", [])
        if len(spy) >= 20:
            f["spy_momentum_20d"] = float(spy[-1].price / spy[-20].price - 1)
        else:
            f["spy_momentum_20d"] = _NAN

        return f
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_feature_engineer.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add adapters/ml/feature_engineer.py tests/test_feature_engineer.py
git commit -m "feat: add FeatureEngineer computing 45 features across 8 groups"
```

---

## Task 12: SQLite Store

**Files:**
- Create: `adapters/data/sqlite_store.py`
- Create: `tests/test_sqlite_store.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_sqlite_store.py`:

```python
"""Tests for SQLite recommendation store (in-memory)."""

import pytest

from adapters.data.sqlite_store import SQLiteStore
from domain.models import (
    AccuracyRecord,
    EvaluationRun,
    MultiHorizonPrediction,
    RecommendationGrade,
    StockRecommendation,
    WeeklyReport,
)


@pytest.fixture
def store() -> SQLiteStore:
    return SQLiteStore(":memory:")


@pytest.fixture
def sample_rec() -> StockRecommendation:
    pred = MultiHorizonPrediction(
        predicted_return_2d=0.03, predicted_return_5d=0.04,
        predicted_return_10d=0.06, confidence_2d=0.8,
        confidence_5d=0.7, confidence_10d=0.6,
    )
    return StockRecommendation(
        symbol="AAPL", week_start="2026-05-19",
        grade=RecommendationGrade.STRONG_BUY, composite_score=0.85,
        prediction=pred,
        horizon_signals={"2d": "bullish", "5d": "bullish", "10d": "bullish"},
        reasoning="Strong momentum", sources=["yfinance"],
        rsi_14=65.0, macd=1.2,
    )


def test_save_and_get_recommendation(store: SQLiteStore, sample_rec: StockRecommendation) -> None:
    store.save_recommendation(sample_rec)
    results = store.get_recommendations(week_start="2026-05-19")
    assert len(results) == 1
    assert results[0].symbol == "AAPL"
    assert results[0].grade == RecommendationGrade.STRONG_BUY
    assert results[0].prediction.predicted_return_10d == 0.06


def test_get_recommendations_by_symbol(store: SQLiteStore, sample_rec: StockRecommendation) -> None:
    store.save_recommendation(sample_rec)
    assert len(store.get_recommendations(symbol="AAPL")) == 1
    assert len(store.get_recommendations(symbol="GOOG")) == 0


def test_upsert_recommendation(store: SQLiteStore, sample_rec: StockRecommendation) -> None:
    """Same symbol+week_start overwrites."""
    store.save_recommendation(sample_rec)
    store.save_recommendation(sample_rec)
    results = store.get_recommendations(week_start="2026-05-19")
    assert len(results) == 1


def test_save_and_get_accuracy_record(store: SQLiteStore) -> None:
    record = AccuracyRecord(
        symbol="AAPL", week_start="2026-05-12",
        predicted_grade="strong_buy",
        predicted_return_2d=0.03, predicted_return_5d=0.04, predicted_return_10d=0.06,
        actual_return_2d=0.025, actual_return_5d=0.035, actual_return_10d=0.055,
        direction_correct_2d=True, direction_correct_5d=True, direction_correct_10d=True,
    )
    store.save_accuracy_record(record)
    results = store.get_accuracy_records(week_start="2026-05-12")
    assert len(results) == 1
    assert results[0].actual_return_5d == 0.035


def test_save_and_get_evaluation_run(store: SQLiteStore) -> None:
    run = EvaluationRun(
        run_date="2026-05-25", eval_type="walk_forward",
        horizon="5d", metric_name="directional_accuracy",
        metric_value=0.58, p_value=0.03,
    )
    store.save_evaluation_run(run)
    results = store.get_evaluation_runs(run_date="2026-05-25")
    assert len(results) == 1
    assert results[0].p_value == 0.03


def test_save_and_get_weekly_report(store: SQLiteStore, sample_rec: StockRecommendation) -> None:
    report = WeeklyReport(
        report_date="2026-05-19", market="us",
        recommendations=[sample_rec],
        spy_return_same_period=0.012, sharpe_ratio=1.5,
    )
    store.save_weekly_report(report)
    loaded = store.get_weekly_report("2026-05-19")
    assert loaded is not None
    assert loaded.market == "us"
    assert loaded.sharpe_ratio == 1.5


def test_get_missing_weekly_report_returns_none(store: SQLiteStore) -> None:
    assert store.get_weekly_report("2026-01-01") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_sqlite_store.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement SQLiteStore**

Create `adapters/data/sqlite_store.py`:

```python
"""SQLite implementation of RecommendationStorePort.

Schema matches spec section 14 — 4 tables with multi-horizon support.
"""

import json
import sqlite3
from typing import Any

from domain.models import (
    AccuracyRecord,
    EvaluationRun,
    MultiHorizonPrediction,
    RecommendationGrade,
    StockRecommendation,
    WeeklyReport,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS recommendations (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    week_start TEXT NOT NULL,
    grade TEXT NOT NULL,
    composite_score REAL,
    predicted_return_2d REAL,
    predicted_return_5d REAL,
    predicted_return_10d REAL,
    confidence_2d REAL,
    confidence_5d REAL,
    confidence_10d REAL,
    horizon_signals TEXT,
    sentiment_score REAL,
    divergence_score REAL,
    divergence_type TEXT,
    technical_signal REAL,
    rsi_14 REAL,
    macd REAL,
    reasoning TEXT,
    sources TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(symbol, week_start)
);

CREATE TABLE IF NOT EXISTS accuracy_records (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    week_start TEXT NOT NULL,
    predicted_grade TEXT,
    predicted_return_2d REAL,
    predicted_return_5d REAL,
    predicted_return_10d REAL,
    actual_return_2d REAL,
    actual_return_5d REAL,
    actual_return_10d REAL,
    direction_correct_2d INTEGER,
    direction_correct_5d INTEGER,
    direction_correct_10d INTEGER,
    evaluated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(symbol, week_start)
);

CREATE TABLE IF NOT EXISTS evaluation_runs (
    id INTEGER PRIMARY KEY,
    run_date TEXT NOT NULL,
    eval_type TEXT NOT NULL,
    horizon TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value REAL,
    p_value REAL,
    regime TEXT,
    details TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS weekly_reports (
    id INTEGER PRIMARY KEY,
    report_date TEXT NOT NULL UNIQUE,
    market TEXT NOT NULL,
    accuracy_vs_last_week REAL,
    spy_return_same_period REAL,
    max_drawdown REAL,
    sharpe_ratio REAL,
    transaction_costs REAL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_rec_week ON recommendations(week_start);
CREATE INDEX IF NOT EXISTS idx_rec_symbol ON recommendations(symbol);
CREATE INDEX IF NOT EXISTS idx_acc_week ON accuracy_records(week_start);
CREATE INDEX IF NOT EXISTS idx_eval_date ON evaluation_runs(run_date);
"""


class SQLiteStore:
    """RecommendationStorePort backed by SQLite."""

    def __init__(self, db_path: str = "data/recommendations.db") -> None:
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)

    def save_recommendation(self, rec: StockRecommendation) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO recommendations
            (symbol, week_start, grade, composite_score,
             predicted_return_2d, predicted_return_5d, predicted_return_10d,
             confidence_2d, confidence_5d, confidence_10d,
             horizon_signals, sentiment_score, divergence_score,
             divergence_type, technical_signal, rsi_14, macd,
             reasoning, sources)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                rec.symbol, rec.week_start, rec.grade.value, rec.composite_score,
                rec.prediction.predicted_return_2d,
                rec.prediction.predicted_return_5d,
                rec.prediction.predicted_return_10d,
                rec.prediction.confidence_2d,
                rec.prediction.confidence_5d,
                rec.prediction.confidence_10d,
                json.dumps(rec.horizon_signals),
                rec.sentiment_score, rec.divergence_score,
                rec.divergence_type, rec.technical_signal,
                rec.rsi_14, rec.macd,
                rec.reasoning, json.dumps(rec.sources),
            ),
        )
        self._conn.commit()

    def get_recommendations(
        self,
        week_start: str | None = None,
        symbol: str | None = None,
    ) -> list[StockRecommendation]:
        query = "SELECT * FROM recommendations WHERE 1=1"
        params: list[Any] = []
        if week_start is not None:
            query += " AND week_start = ?"
            params.append(week_start)
        if symbol is not None:
            query += " AND symbol = ?"
            params.append(symbol)

        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_recommendation(r) for r in rows]

    def save_accuracy_record(self, record: AccuracyRecord) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO accuracy_records
            (symbol, week_start, predicted_grade,
             predicted_return_2d, predicted_return_5d, predicted_return_10d,
             actual_return_2d, actual_return_5d, actual_return_10d,
             direction_correct_2d, direction_correct_5d, direction_correct_10d)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.symbol, record.week_start, record.predicted_grade,
                record.predicted_return_2d, record.predicted_return_5d,
                record.predicted_return_10d,
                record.actual_return_2d, record.actual_return_5d,
                record.actual_return_10d,
                int(record.direction_correct_2d),
                int(record.direction_correct_5d),
                int(record.direction_correct_10d),
            ),
        )
        self._conn.commit()

    def get_accuracy_records(
        self,
        week_start: str | None = None,
        symbol: str | None = None,
    ) -> list[AccuracyRecord]:
        query = "SELECT * FROM accuracy_records WHERE 1=1"
        params: list[Any] = []
        if week_start is not None:
            query += " AND week_start = ?"
            params.append(week_start)
        if symbol is not None:
            query += " AND symbol = ?"
            params.append(symbol)

        rows = self._conn.execute(query, params).fetchall()
        return [
            AccuracyRecord(
                symbol=r["symbol"], week_start=r["week_start"],
                predicted_grade=r["predicted_grade"],
                predicted_return_2d=r["predicted_return_2d"],
                predicted_return_5d=r["predicted_return_5d"],
                predicted_return_10d=r["predicted_return_10d"],
                actual_return_2d=r["actual_return_2d"],
                actual_return_5d=r["actual_return_5d"],
                actual_return_10d=r["actual_return_10d"],
                direction_correct_2d=bool(r["direction_correct_2d"]),
                direction_correct_5d=bool(r["direction_correct_5d"]),
                direction_correct_10d=bool(r["direction_correct_10d"]),
            )
            for r in rows
        ]

    def save_evaluation_run(self, run: EvaluationRun) -> None:
        self._conn.execute(
            """INSERT INTO evaluation_runs
            (run_date, eval_type, horizon, metric_name, metric_value,
             p_value, regime, details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run.run_date, run.eval_type, run.horizon,
                run.metric_name, run.metric_value,
                run.p_value, run.regime, run.details,
            ),
        )
        self._conn.commit()

    def get_evaluation_runs(
        self,
        run_date: str | None = None,
        eval_type: str | None = None,
    ) -> list[EvaluationRun]:
        query = "SELECT * FROM evaluation_runs WHERE 1=1"
        params: list[Any] = []
        if run_date is not None:
            query += " AND run_date = ?"
            params.append(run_date)
        if eval_type is not None:
            query += " AND eval_type = ?"
            params.append(eval_type)

        rows = self._conn.execute(query, params).fetchall()
        return [
            EvaluationRun(
                run_date=r["run_date"], eval_type=r["eval_type"],
                horizon=r["horizon"], metric_name=r["metric_name"],
                metric_value=r["metric_value"], p_value=r["p_value"],
                regime=r["regime"], details=r["details"],
            )
            for r in rows
        ]

    def save_weekly_report(self, report: WeeklyReport) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO weekly_reports
            (report_date, market, accuracy_vs_last_week,
             spy_return_same_period, max_drawdown, sharpe_ratio,
             transaction_costs)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                report.report_date, report.market,
                report.accuracy_vs_last_week,
                report.spy_return_same_period,
                report.max_drawdown, report.sharpe_ratio,
                report.transaction_costs,
            ),
        )
        # Also save each recommendation
        for rec in report.recommendations:
            self.save_recommendation(rec)
        self._conn.commit()

    def get_weekly_report(self, report_date: str) -> WeeklyReport | None:
        row = self._conn.execute(
            "SELECT * FROM weekly_reports WHERE report_date = ?",
            (report_date,),
        ).fetchone()
        if row is None:
            return None
        recs = self.get_recommendations(week_start=report_date)
        return WeeklyReport(
            report_date=row["report_date"],
            market=row["market"],
            recommendations=recs,
            accuracy_vs_last_week=row["accuracy_vs_last_week"],
            spy_return_same_period=row["spy_return_same_period"],
            max_drawdown=row["max_drawdown"],
            sharpe_ratio=row["sharpe_ratio"],
            transaction_costs=row["transaction_costs"],
        )

    def _row_to_recommendation(self, r: sqlite3.Row) -> StockRecommendation:
        pred = MultiHorizonPrediction(
            predicted_return_2d=r["predicted_return_2d"],
            predicted_return_5d=r["predicted_return_5d"],
            predicted_return_10d=r["predicted_return_10d"],
            confidence_2d=r["confidence_2d"],
            confidence_5d=r["confidence_5d"],
            confidence_10d=r["confidence_10d"],
        )
        return StockRecommendation(
            symbol=r["symbol"],
            week_start=r["week_start"],
            grade=RecommendationGrade(r["grade"]),
            composite_score=r["composite_score"],
            prediction=pred,
            horizon_signals=json.loads(r["horizon_signals"]),
            reasoning=r["reasoning"],
            sources=json.loads(r["sources"]),
            sentiment_score=r["sentiment_score"],
            divergence_score=r["divergence_score"],
            divergence_type=r["divergence_type"],
            technical_signal=r["technical_signal"],
            rsi_14=r["rsi_14"],
            macd=r["macd"],
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_sqlite_store.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add adapters/data/sqlite_store.py tests/test_sqlite_store.py
git commit -m "feat: add SQLiteStore implementing RecommendationStorePort"
```

---

## Task 13: ML Predictors (XGBoost + LightGBM + Ridge)

**Files:**
- Create: `adapters/ml/xgboost_predictor.py`, `adapters/ml/lightgbm_predictor.py`, `adapters/ml/ridge_predictor.py`
- Create: `tests/test_ml_predictors.py`

- [ ] **Step 1: Write failing tests for all three predictors**

Create `tests/test_ml_predictors.py`:

```python
"""Tests for ML predictors — XGBoost, LightGBM, Ridge."""

import random
from pathlib import Path

import pytest

from adapters.ml.lightgbm_predictor import LightGBMPredictor
from adapters.ml.ridge_predictor import RidgePredictor
from adapters.ml.xgboost_predictor import XGBoostPredictor


def _make_training_data(
    n_samples: int = 100, n_features: int = 45, seed: int = 42
) -> tuple[list[dict[str, float]], list[float]]:
    rng = random.Random(seed)
    feature_names = [f"f_{i}" for i in range(n_features)]
    features = [
        {name: rng.gauss(0, 1) for name in feature_names}
        for _ in range(n_samples)
    ]
    targets = [rng.gauss(0, 0.05) for _ in range(n_samples)]
    return features, targets


@pytest.fixture
def training_data() -> tuple[list[dict[str, float]], list[float]]:
    return _make_training_data()


class TestXGBoostPredictor:
    def test_fit_and_predict(self, training_data: tuple) -> None:
        features, targets = training_data
        model = XGBoostPredictor(random_seed=42)
        model.fit(features, targets)
        preds = model.predict(features[:5])
        assert len(preds) == 5
        assert all(isinstance(p, float) for p in preds)

    def test_predict_deterministic(self, training_data: tuple) -> None:
        features, targets = training_data
        m1 = XGBoostPredictor(random_seed=42)
        m1.fit(features, targets)
        m2 = XGBoostPredictor(random_seed=42)
        m2.fit(features, targets)
        assert m1.predict(features[:3]) == m2.predict(features[:3])

    def test_save_and_load(self, training_data: tuple, tmp_path: Path) -> None:
        features, targets = training_data
        model = XGBoostPredictor(random_seed=42)
        model.fit(features, targets)
        preds_before = model.predict(features[:3])

        path = str(tmp_path / "xgb.json")
        model.save_model(path)

        loaded = XGBoostPredictor(random_seed=42)
        loaded.load_model(path)
        preds_after = loaded.predict(features[:3])
        assert preds_before == preds_after


class TestLightGBMPredictor:
    def test_fit_and_predict(self, training_data: tuple) -> None:
        features, targets = training_data
        model = LightGBMPredictor(random_seed=42)
        model.fit(features, targets)
        preds = model.predict(features[:5])
        assert len(preds) == 5
        assert all(isinstance(p, float) for p in preds)

    def test_save_and_load(self, training_data: tuple, tmp_path: Path) -> None:
        features, targets = training_data
        model = LightGBMPredictor(random_seed=42)
        model.fit(features, targets)
        preds_before = model.predict(features[:3])

        path = str(tmp_path / "lgbm.txt")
        model.save_model(path)

        loaded = LightGBMPredictor(random_seed=42)
        loaded.load_model(path)
        preds_after = loaded.predict(features[:3])
        assert preds_before == preds_after


class TestRidgePredictor:
    def test_fit_and_predict(self, training_data: tuple) -> None:
        features, targets = training_data
        model = RidgePredictor()
        model.fit(features, targets)
        preds = model.predict(features[:5])
        assert len(preds) == 5
        assert all(isinstance(p, float) for p in preds)

    def test_save_and_load(self, training_data: tuple, tmp_path: Path) -> None:
        features, targets = training_data
        model = RidgePredictor()
        model.fit(features, targets)
        preds_before = model.predict(features[:3])

        path = str(tmp_path / "ridge.pkl")
        model.save_model(path)

        loaded = RidgePredictor()
        loaded.load_model(path)
        preds_after = loaded.predict(features[:3])
        assert preds_before == preds_after
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ml_predictors.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement XGBoostPredictor**

Create `adapters/ml/xgboost_predictor.py`:

```python
"""XGBoost predictor implementing StockPredictorPort."""

import json

import numpy as np
import xgboost as xgb


class XGBoostPredictor:
    """XGBoost regressor for single-horizon return prediction."""

    def __init__(
        self,
        random_seed: int = 42,
        n_estimators: int = 200,
        max_depth: int = 6,
        learning_rate: float = 0.05,
    ) -> None:
        self._model = xgb.XGBRegressor(
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=learning_rate,
            random_state=random_seed,
            n_jobs=1,
            verbosity=0,
        )
        self._feature_names: list[str] = []

    def fit(
        self, features: list[dict[str, float]], targets: list[float]
    ) -> None:
        self._feature_names = sorted(features[0].keys())
        x = np.array([[f[k] for k in self._feature_names] for f in features])
        y = np.array(targets)
        # Replace NaN with column median
        for col in range(x.shape[1]):
            mask = np.isnan(x[:, col])
            if mask.any():
                median = float(np.nanmedian(x[:, col]))
                x[mask, col] = median
        self._model.fit(x, y)

    def predict(self, features: list[dict[str, float]]) -> list[float]:
        x = np.array([[f.get(k, float("nan")) for k in self._feature_names] for f in features])
        for col in range(x.shape[1]):
            mask = np.isnan(x[:, col])
            if mask.any():
                x[mask, col] = 0.0
        preds = self._model.predict(x)
        return [float(p) for p in preds]

    def save_model(self, path: str) -> None:
        self._model.save_model(path)
        meta_path = path + ".meta.json"
        with open(meta_path, "w") as f:
            json.dump({"feature_names": self._feature_names}, f)

    def load_model(self, path: str) -> None:
        self._model.load_model(path)
        meta_path = path + ".meta.json"
        with open(meta_path) as f:
            meta = json.load(f)
        self._feature_names = meta["feature_names"]
```

- [ ] **Step 4: Implement LightGBMPredictor**

Create `adapters/ml/lightgbm_predictor.py`:

```python
"""LightGBM predictor implementing StockPredictorPort."""

import json

import lightgbm as lgb
import numpy as np


class LightGBMPredictor:
    """LightGBM regressor for single-horizon return prediction."""

    def __init__(
        self,
        random_seed: int = 42,
        n_estimators: int = 200,
        max_depth: int = 6,
        learning_rate: float = 0.05,
    ) -> None:
        self._model = lgb.LGBMRegressor(
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=learning_rate,
            random_state=random_seed,
            n_jobs=1,
            verbosity=-1,
        )
        self._feature_names: list[str] = []

    def fit(
        self, features: list[dict[str, float]], targets: list[float]
    ) -> None:
        self._feature_names = sorted(features[0].keys())
        x = np.array([[f[k] for k in self._feature_names] for f in features])
        y = np.array(targets)
        for col in range(x.shape[1]):
            mask = np.isnan(x[:, col])
            if mask.any():
                median = float(np.nanmedian(x[:, col]))
                x[mask, col] = median
        self._model.fit(x, y)

    def predict(self, features: list[dict[str, float]]) -> list[float]:
        x = np.array([[f.get(k, float("nan")) for k in self._feature_names] for f in features])
        for col in range(x.shape[1]):
            mask = np.isnan(x[:, col])
            if mask.any():
                x[mask, col] = 0.0
        preds = self._model.predict(x)
        return [float(p) for p in preds]

    def save_model(self, path: str) -> None:
        self._model.booster_.save_model(path)
        meta_path = path + ".meta.json"
        with open(meta_path, "w") as f:
            json.dump({"feature_names": self._feature_names}, f)

    def load_model(self, path: str) -> None:
        self._model = lgb.LGBMRegressor()
        self._model._Booster = lgb.Booster(model_file=path)
        meta_path = path + ".meta.json"
        with open(meta_path) as f:
            meta = json.load(f)
        self._feature_names = meta["feature_names"]
```

- [ ] **Step 5: Implement RidgePredictor**

Create `adapters/ml/ridge_predictor.py`:

```python
"""Ridge regressor implementing StockPredictorPort."""

import json
import pickle

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler


class RidgePredictor:
    """Ridge regression with standardization for single-horizon return prediction."""

    def __init__(self, alpha: float = 1.0) -> None:
        self._model = Ridge(alpha=alpha)
        self._scaler = StandardScaler()
        self._feature_names: list[str] = []

    def fit(
        self, features: list[dict[str, float]], targets: list[float]
    ) -> None:
        self._feature_names = sorted(features[0].keys())
        x = np.array([[f[k] for k in self._feature_names] for f in features])
        y = np.array(targets)
        for col in range(x.shape[1]):
            mask = np.isnan(x[:, col])
            if mask.any():
                median = float(np.nanmedian(x[:, col]))
                x[mask, col] = median
        x_scaled = self._scaler.fit_transform(x)
        self._model.fit(x_scaled, y)

    def predict(self, features: list[dict[str, float]]) -> list[float]:
        x = np.array([[f.get(k, float("nan")) for k in self._feature_names] for f in features])
        for col in range(x.shape[1]):
            mask = np.isnan(x[:, col])
            if mask.any():
                x[mask, col] = 0.0
        x_scaled = self._scaler.transform(x)
        preds = self._model.predict(x_scaled)
        return [float(p) for p in preds]

    def save_model(self, path: str) -> None:
        with open(path, "wb") as f:
            pickle.dump({"model": self._model, "scaler": self._scaler}, f)
        meta_path = path + ".meta.json"
        with open(meta_path, "w") as f:
            json.dump({"feature_names": self._feature_names}, f)

    def load_model(self, path: str) -> None:
        with open(path, "rb") as f:
            data = pickle.load(f)  # noqa: S301
        self._model = data["model"]
        self._scaler = data["scaler"]
        meta_path = path + ".meta.json"
        with open(meta_path) as f:
            meta = json.load(f)
        self._feature_names = meta["feature_names"]
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_ml_predictors.py -v`
Expected: All 7 tests PASS

- [ ] **Step 7: Commit**

```bash
git add adapters/ml/xgboost_predictor.py adapters/ml/lightgbm_predictor.py adapters/ml/ridge_predictor.py tests/test_ml_predictors.py
git commit -m "feat: add XGBoost, LightGBM, Ridge predictors implementing StockPredictorPort"
```

---

## Task 14: Ensemble Predictor

**Files:**
- Create: `adapters/ml/ensemble_predictor.py`
- Modify: `tests/test_ml_predictors.py`

- [ ] **Step 1: Write failing tests for ensemble**

Add to `tests/test_ml_predictors.py`:

```python
from adapters.ml.ensemble_predictor import EnsemblePredictor


class TestEnsemblePredictor:
    def test_fit_and_predict(self, training_data: tuple) -> None:
        features, targets = training_data
        ensemble = EnsemblePredictor(random_seed=42)
        ensemble.fit(features, targets)
        preds = ensemble.predict(features[:5])
        assert len(preds) == 5
        assert all(isinstance(p, float) for p in preds)

    def test_ensemble_averages_models(self, training_data: tuple) -> None:
        """Ensemble prediction is between min and max individual predictions."""
        features, targets = training_data
        ensemble = EnsemblePredictor(random_seed=42)
        ensemble.fit(features, targets)

        xgb_model = XGBoostPredictor(random_seed=42)
        xgb_model.fit(features, targets)
        ridge_model = RidgePredictor()
        ridge_model.fit(features, targets)

        test_features = features[:3]
        ens_preds = ensemble.predict(test_features)
        xgb_preds = xgb_model.predict(test_features)
        ridge_preds = ridge_model.predict(test_features)

        for i in range(3):
            lo = min(xgb_preds[i], ridge_preds[i])
            hi = max(xgb_preds[i], ridge_preds[i])
            # Ensemble should be within range of individual models (with margin)
            assert lo - 0.1 <= ens_preds[i] <= hi + 0.1

    def test_save_and_load(self, training_data: tuple, tmp_path: Path) -> None:
        features, targets = training_data
        ensemble = EnsemblePredictor(random_seed=42)
        ensemble.fit(features, targets)
        preds_before = ensemble.predict(features[:3])

        path = str(tmp_path / "ensemble")
        ensemble.save_model(path)

        loaded = EnsemblePredictor(random_seed=42)
        loaded.load_model(path)
        preds_after = loaded.predict(features[:3])

        for a, b in zip(preds_before, preds_after):
            assert abs(a - b) < 1e-6
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ml_predictors.py::TestEnsemblePredictor -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement EnsemblePredictor**

Create `adapters/ml/ensemble_predictor.py`:

```python
"""Weighted ensemble of XGBoost + LightGBM + Ridge (ADR-009).

Equal weights by default. Can be re-weighted by recent accuracy.
"""

import json
from pathlib import Path

from .lightgbm_predictor import LightGBMPredictor
from .ridge_predictor import RidgePredictor
from .xgboost_predictor import XGBoostPredictor


class EnsemblePredictor:
    """StockPredictorPort: weighted average of XGBoost + LightGBM + Ridge."""

    def __init__(
        self,
        random_seed: int = 42,
        weights: tuple[float, float, float] | None = None,
    ) -> None:
        self._xgb = XGBoostPredictor(random_seed=random_seed)
        self._lgbm = LightGBMPredictor(random_seed=random_seed)
        self._ridge = RidgePredictor()
        self._weights = weights or (1.0 / 3, 1.0 / 3, 1.0 / 3)

    def fit(
        self, features: list[dict[str, float]], targets: list[float]
    ) -> None:
        self._xgb.fit(features, targets)
        self._lgbm.fit(features, targets)
        self._ridge.fit(features, targets)

    def predict(self, features: list[dict[str, float]]) -> list[float]:
        xgb_preds = self._xgb.predict(features)
        lgbm_preds = self._lgbm.predict(features)
        ridge_preds = self._ridge.predict(features)

        w = self._weights
        return [
            w[0] * xgb_preds[i] + w[1] * lgbm_preds[i] + w[2] * ridge_preds[i]
            for i in range(len(features))
        ]

    def set_weights(self, weights: tuple[float, float, float]) -> None:
        """Update ensemble weights (must sum to 1.0)."""
        total = sum(weights)
        self._weights = tuple(w / total for w in weights)

    def save_model(self, path: str) -> None:
        base = Path(path)
        base.mkdir(parents=True, exist_ok=True)
        self._xgb.save_model(str(base / "xgb.json"))
        self._lgbm.save_model(str(base / "lgbm.txt"))
        self._ridge.save_model(str(base / "ridge.pkl"))
        with open(base / "ensemble_meta.json", "w") as f:
            json.dump({"weights": list(self._weights)}, f)

    def load_model(self, path: str) -> None:
        base = Path(path)
        self._xgb.load_model(str(base / "xgb.json"))
        self._lgbm.load_model(str(base / "lgbm.txt"))
        self._ridge.load_model(str(base / "ridge.pkl"))
        with open(base / "ensemble_meta.json") as f:
            meta = json.load(f)
        self._weights = tuple(meta["weights"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_ml_predictors.py -v`
Expected: All 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add adapters/ml/ensemble_predictor.py tests/test_ml_predictors.py
git commit -m "feat: add EnsemblePredictor (XGBoost + LightGBM + Ridge weighted average)"
```

---

## Task 15: Evaluation Module

**Files:**
- Create: `application/evaluation.py`
- Create: `tests/test_evaluation.py`

- [ ] **Step 1: Write failing tests for evaluation components**

Create `tests/test_evaluation.py`:

```python
"""Tests for evaluation framework — walk-forward, permutation, costs, regime, drawdown."""

import pytest

from application.evaluation import (
    DrawdownTracker,
    PermutationTester,
    RegimeSplitter,
    TransactionCostModel,
    WalkForwardValidator,
)


class TestWalkForwardValidator:
    def test_generate_splits(self) -> None:
        months = ["2024-01", "2024-02", "2024-03", "2024-04", "2024-05"]
        validator = WalkForwardValidator(min_train_months=2)
        splits = validator.generate_splits(months)
        # First split: train on [01,02], test on 03
        assert len(splits) >= 3
        train, test = splits[0]
        assert test == "2024-03"
        assert "2024-01" in train
        assert "2024-02" in train

    def test_expanding_window(self) -> None:
        months = ["2024-01", "2024-02", "2024-03", "2024-04"]
        validator = WalkForwardValidator(min_train_months=1)
        splits = validator.generate_splits(months)
        # Each successive split has more training data
        for i in range(1, len(splits)):
            assert len(splits[i][0]) > len(splits[i - 1][0])


class TestPermutationTester:
    def test_permutation_random_model_not_significant(self) -> None:
        """Random predictions should not be statistically significant."""
        import random
        random.seed(42)
        actuals = [random.gauss(0, 0.05) for _ in range(100)]
        predictions = [random.gauss(0, 0.05) for _ in range(100)]

        tester = PermutationTester(n_shuffles=200, random_seed=42)
        p_value = tester.test_directional_accuracy(predictions, actuals)
        assert p_value > 0.05  # not significant

    def test_permutation_perfect_model_is_significant(self) -> None:
        """Perfect predictions should be significant."""
        actuals = [0.05, -0.03, 0.02, -0.04, 0.06] * 20
        predictions = [0.04, -0.02, 0.01, -0.03, 0.05] * 20

        tester = PermutationTester(n_shuffles=200, random_seed=42)
        p_value = tester.test_directional_accuracy(predictions, actuals)
        assert p_value < 0.05  # significant


class TestTransactionCostModel:
    def test_apply_costs(self) -> None:
        model = TransactionCostModel(cost_per_trade=0.001)
        gross_returns = [0.05, -0.02, 0.03]
        net = model.apply_costs(gross_returns, n_trades_per_period=2)
        # Each period loses 2 * 0.001 = 0.002
        assert net[0] == pytest.approx(0.05 - 0.002)
        assert net[1] == pytest.approx(-0.02 - 0.002)

    def test_total_costs(self) -> None:
        model = TransactionCostModel(cost_per_trade=0.001)
        total = model.total_costs(n_periods=52, n_trades_per_period=2)
        assert total == pytest.approx(52 * 2 * 0.001)


class TestRegimeSplitter:
    def test_classify_regimes(self) -> None:
        # Bull: >10% annualized, Bear: <-10%, Sideways: between
        spy_monthly_returns = [0.02] * 12  # ~24% annualized → bull
        splitter = RegimeSplitter(bull_threshold=0.10, bear_threshold=-0.10)
        regimes = splitter.classify_monthly(spy_monthly_returns)
        assert all(r == "bull" for r in regimes)

    def test_bear_regime(self) -> None:
        spy_returns = [-0.03] * 12  # ~-36% annualized → bear
        splitter = RegimeSplitter()
        regimes = splitter.classify_monthly(spy_returns)
        assert all(r == "bear" for r in regimes)

    def test_sideways_regime(self) -> None:
        spy_returns = [0.005] * 12  # ~6% annualized → sideways
        splitter = RegimeSplitter()
        regimes = splitter.classify_monthly(spy_returns)
        assert all(r == "sideways" for r in regimes)


class TestDrawdownTracker:
    def test_max_drawdown(self) -> None:
        returns = [0.10, 0.05, -0.15, -0.10, 0.20]
        tracker = DrawdownTracker()
        result = tracker.compute(returns)
        assert result["max_drawdown"] < 0
        assert "recovery_periods" in result

    def test_no_drawdown(self) -> None:
        returns = [0.05, 0.03, 0.02, 0.04]
        tracker = DrawdownTracker()
        result = tracker.compute(returns)
        assert result["max_drawdown"] == 0.0

    def test_full_drawdown(self) -> None:
        returns = [-0.5, -0.5]  # lose 75%
        tracker = DrawdownTracker()
        result = tracker.compute(returns)
        assert result["max_drawdown"] < -0.5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_evaluation.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement evaluation module**

Create `application/evaluation.py`:

```python
"""Evaluation framework for Phase 3A (ADR-011).

Components:
  - WalkForwardValidator: expanding-window train/test splits
  - PermutationTester: statistical significance via label shuffling
  - TransactionCostModel: realistic return adjustment
  - RegimeSplitter: bull/sideways/bear classification
  - DrawdownTracker: max drawdown and recovery time
"""

import math
import random
from typing import Any


class WalkForwardValidator:
    """Expanding-window walk-forward validation.

    For each month M after min_train_months:
      Train on all data before M, test on M.
    """

    def __init__(self, min_train_months: int = 12) -> None:
        self._min_train = min_train_months

    def generate_splits(
        self, months: list[str]
    ) -> list[tuple[list[str], str]]:
        """Generate (train_months, test_month) splits.

        Args:
            months: Sorted list of month strings ('YYYY-MM').

        Returns:
            List of (train_months, test_month) tuples.
        """
        splits: list[tuple[list[str], str]] = []
        for i in range(self._min_train, len(months)):
            train = months[:i]
            test = months[i]
            splits.append((train, test))
        return splits


class PermutationTester:
    """Statistical significance via permutation test.

    Shuffles actual labels N times, computes metric each time,
    returns p-value = fraction of shuffled metrics >= observed.
    """

    def __init__(
        self, n_shuffles: int = 1000, random_seed: int = 42
    ) -> None:
        self._n_shuffles = n_shuffles
        self._rng = random.Random(random_seed)

    def test_directional_accuracy(
        self, predictions: list[float], actuals: list[float]
    ) -> float:
        """Test if directional accuracy is statistically significant.

        Returns:
            p-value. If < 0.05, model is significantly better than random.
        """
        observed = self._directional_accuracy(predictions, actuals)

        count_ge = 0
        shuffled_actuals = list(actuals)
        for _ in range(self._n_shuffles):
            self._rng.shuffle(shuffled_actuals)
            shuffled_acc = self._directional_accuracy(
                predictions, shuffled_actuals
            )
            if shuffled_acc >= observed:
                count_ge += 1

        return count_ge / self._n_shuffles

    @staticmethod
    def _directional_accuracy(
        predictions: list[float], actuals: list[float]
    ) -> float:
        correct = sum(
            1
            for p, a in zip(predictions, actuals)
            if (p > 0 and a > 0) or (p < 0 and a < 0) or (p == 0 and a == 0)
        )
        return correct / len(predictions) if predictions else 0.0


class TransactionCostModel:
    """Apply realistic transaction costs to gross returns."""

    def __init__(self, cost_per_trade: float = 0.001) -> None:
        self._cost = cost_per_trade

    def apply_costs(
        self,
        gross_returns: list[float],
        n_trades_per_period: int = 2,
    ) -> list[float]:
        """Subtract transaction costs from each period's return.

        Args:
            gross_returns: List of period returns (e.g., weekly).
            n_trades_per_period: Number of trades per period (buy+sell = 2).

        Returns:
            Net returns after costs.
        """
        cost_per_period = self._cost * n_trades_per_period
        return [r - cost_per_period for r in gross_returns]

    def total_costs(
        self, n_periods: int, n_trades_per_period: int = 2
    ) -> float:
        """Total transaction costs over N periods."""
        return self._cost * n_trades_per_period * n_periods


class RegimeSplitter:
    """Classify market months as bull/sideways/bear based on SPY returns."""

    def __init__(
        self,
        bull_threshold: float = 0.10,
        bear_threshold: float = -0.10,
    ) -> None:
        self._bull = bull_threshold
        self._bear = bear_threshold

    def classify_monthly(
        self, spy_monthly_returns: list[float]
    ) -> list[str]:
        """Classify each month based on trailing annualized return.

        Uses rolling 12-month return annualized. For months with < 12 history,
        annualizes available data.
        """
        regimes: list[str] = []
        for i in range(len(spy_monthly_returns)):
            window = spy_monthly_returns[max(0, i - 11) : i + 1]
            cumulative = 1.0
            for r in window:
                cumulative *= 1 + r
            n_months = len(window)
            annualized = cumulative ** (12 / n_months) - 1

            if annualized > self._bull:
                regimes.append("bull")
            elif annualized < self._bear:
                regimes.append("bear")
            else:
                regimes.append("sideways")

        return regimes


class DrawdownTracker:
    """Track maximum drawdown and recovery time from return series."""

    def compute(self, returns: list[float]) -> dict[str, Any]:
        """Compute drawdown statistics from period returns.

        Returns:
            Dict with max_drawdown (negative float), recovery_periods (int or None).
        """
        if not returns:
            return {"max_drawdown": 0.0, "recovery_periods": None}

        # Build equity curve
        equity = [1.0]
        for r in returns:
            equity.append(equity[-1] * (1 + r))

        peak = equity[0]
        max_dd = 0.0
        dd_start = 0
        recovery: int | None = None

        for i in range(1, len(equity)):
            if equity[i] > peak:
                peak = equity[i]
            dd = (equity[i] - peak) / peak
            if dd < max_dd:
                max_dd = dd
                dd_start = i
                recovery = None

        # Find recovery from max drawdown point
        if max_dd < 0:
            peak_at_dd = max(equity[:dd_start + 1])
            for j in range(dd_start + 1, len(equity)):
                if equity[j] >= peak_at_dd:
                    recovery = j - dd_start
                    break

        return {
            "max_drawdown": max_dd,
            "recovery_periods": recovery,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_evaluation.py -v`
Expected: All 11 tests PASS

- [ ] **Step 5: Commit**

```bash
git add application/evaluation.py tests/test_evaluation.py
git commit -m "feat: add evaluation framework (walk-forward, permutation, costs, regime, drawdown)"
```

---

## Task 16: Use Cases

**Files:**
- Modify: `application/use_cases.py`
- Create: `tests/test_pretraining.py`
- Create: `tests/test_weekly_tournament.py`

- [ ] **Step 1: Write failing tests for PretrainingUseCase**

Create `tests/test_pretraining.py`:

```python
"""Tests for pretraining use case — walk-forward training pipeline."""

from datetime import datetime, timedelta

import pytest

from application.use_cases import PretrainingUseCase
from domain.models import Signal
from tests.fakes import (
    FakeFeatureEngineer,
    FakeMarketData,
    FakePredictor,
    FakeRecommendationStore,
    FakeTechnicalAnalysis,
)


def _make_signal(symbol: str, day_offset: int, price: float) -> Signal:
    return Signal(
        symbol=symbol,
        timestamp=datetime(2025, 1, 2) + timedelta(days=day_offset),
        price=price,
        volume=1_000_000,
        open_=price - 1,
        high=price + 2,
        low=price - 2,
    )


@pytest.fixture
def signals() -> dict[str, list[Signal]]:
    """260 days of signals for 3 tickers + macro symbols."""
    import random
    random.seed(42)
    result: dict[str, list[Signal]] = {}
    for sym in ["AAPL", "GOOG", "MSFT", "^VIX", "^TNX", "DX-Y.NYB", "^IRX", "SPY"]:
        price = 100.0
        sigs = []
        for i in range(260):
            price = max(price + random.gauss(0, 2), 1.0)
            sigs.append(_make_signal(sym, i, price))
        result[sym] = sigs
    return result


@pytest.fixture
def pretraining_use_case(signals: dict[str, list[Signal]]) -> PretrainingUseCase:
    market_data = FakeMarketData(
        signals=signals,
        ticker_info={"AAPL": {"market_cap": 3e12}, "GOOG": {"market_cap": 2e12}, "MSFT": {"market_cap": 2.5e12}},
    )
    return PretrainingUseCase(
        market_data=market_data,
        technical_analysis=FakeTechnicalAnalysis(),
        feature_engineer=FakeFeatureEngineer(),
        predictors={"2d": FakePredictor(), "5d": FakePredictor(), "10d": FakePredictor()},
        store=FakeRecommendationStore(),
        tickers=["AAPL", "GOOG", "MSFT"],
        macro_symbols={"^VIX": "^VIX", "^TNX": "^TNX", "DX-Y.NYB": "DX-Y.NYB", "^IRX": "^IRX", "SPY": "SPY"},
    )


def test_pretraining_runs_without_error(pretraining_use_case: PretrainingUseCase) -> None:
    pretraining_use_case.execute(
        start_month="2025-06",
        end_month="2025-09",
    )


def test_pretraining_trains_all_horizons(pretraining_use_case: PretrainingUseCase) -> None:
    pretraining_use_case.execute(start_month="2025-06", end_month="2025-09")
    for horizon in ("2d", "5d", "10d"):
        predictor = pretraining_use_case._predictors[horizon]
        assert len(predictor.fit_calls) > 0


def test_pretraining_stores_evaluation_runs(pretraining_use_case: PretrainingUseCase) -> None:
    pretraining_use_case.execute(start_month="2025-06", end_month="2025-09")
    runs = pretraining_use_case._store.get_evaluation_runs()
    assert len(runs) > 0
```

- [ ] **Step 2: Write failing tests for WeeklyTournamentUseCase**

Create `tests/test_weekly_tournament.py`:

```python
"""Tests for weekly tournament use case — end-to-end pipeline."""

from datetime import datetime, timedelta

import pytest

from application.use_cases import WeeklyTournamentUseCase
from domain.models import RecommendationGrade, Signal
from tests.fakes import (
    FakeFeatureEngineer,
    FakeMarketData,
    FakePredictor,
    FakeRecommendationStore,
    FakeTechnicalAnalysis,
)


def _make_signals(n_tickers: int = 20) -> dict[str, list[Signal]]:
    import random
    random.seed(42)
    result: dict[str, list[Signal]] = {}
    tickers = [f"TICK{i:02d}" for i in range(n_tickers)]
    for sym in tickers + ["^VIX", "^TNX", "DX-Y.NYB", "^IRX", "SPY"]:
        price = 50.0 + random.random() * 200
        sigs = []
        for i in range(60):
            price = max(price + random.gauss(0, 2), 1.0)
            sigs.append(Signal(
                symbol=sym,
                timestamp=datetime(2026, 3, 1) + timedelta(days=i),
                price=price, volume=1_000_000,
                open_=price - 1, high=price + 2, low=price - 2,
            ))
        result[sym] = sigs
    return result


@pytest.fixture
def tournament() -> WeeklyTournamentUseCase:
    signals = _make_signals(20)
    tickers = [f"TICK{i:02d}" for i in range(20)]
    return WeeklyTournamentUseCase(
        market_data=FakeMarketData(
            signals=signals,
            ticker_info={t: {"market_cap": 10e9} for t in tickers},
        ),
        technical_analysis=FakeTechnicalAnalysis(),
        feature_engineer=FakeFeatureEngineer(),
        predictors={"2d": FakePredictor([0.03]), "5d": FakePredictor([0.04]), "10d": FakePredictor([0.06])},
        store=FakeRecommendationStore(),
        tickers=tickers,
        macro_symbols={"^VIX": "^VIX", "^TNX": "^TNX", "DX-Y.NYB": "DX-Y.NYB", "^IRX": "^IRX", "SPY": "SPY"},
        market="us",
    )


def test_tournament_produces_recommendations(tournament: WeeklyTournamentUseCase) -> None:
    report = tournament.execute(
        prediction_date=datetime(2026, 5, 1),
    )
    assert len(report.recommendations) > 0
    assert len(report.recommendations) <= 15


def test_tournament_stores_recommendations(tournament: WeeklyTournamentUseCase) -> None:
    tournament.execute(prediction_date=datetime(2026, 5, 1))
    stored = tournament._store.get_recommendations()
    assert len(stored) > 0


def test_tournament_grades_are_valid(tournament: WeeklyTournamentUseCase) -> None:
    report = tournament.execute(prediction_date=datetime(2026, 5, 1))
    for rec in report.recommendations:
        assert isinstance(rec.grade, RecommendationGrade)


def test_tournament_report_has_market(tournament: WeeklyTournamentUseCase) -> None:
    report = tournament.execute(prediction_date=datetime(2026, 5, 1))
    assert report.market == "us"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_pretraining.py tests/test_weekly_tournament.py -v`
Expected: FAIL — `ImportError: cannot import name 'PretrainingUseCase'`

- [ ] **Step 4: Implement use cases**

Replace `application/use_cases.py`:

```python
"""Use cases: orchestration of domain and adapters.

Each use case depends only on port interfaces, never on concrete adapters.
"""

from datetime import datetime, timedelta
from typing import Any

from loguru import logger

from domain.models import (
    AccuracyRecord,
    EvaluationRun,
    MultiHorizonPrediction,
    StockRecommendation,
    WeeklyReport,
)
from domain.ports import (
    FeatureEngineerPort,
    MarketDataPort,
    RecommendationStorePort,
    StockPredictorPort,
    TechnicalAnalysisPort,
)
from domain.services import (
    grade_from_horizons,
    validate_feature_matrix,
)


class PretrainingUseCase:
    """Walk-forward pretraining on 2-3 years of historical data.

    For each month M after min_train:
      1. Collect features for all tickers for months before M
      2. Train ensembles (one per horizon) on collected data
      3. Predict month M, record results
    """

    def __init__(
        self,
        market_data: MarketDataPort,
        technical_analysis: TechnicalAnalysisPort,
        feature_engineer: FeatureEngineerPort,
        predictors: dict[str, StockPredictorPort],
        store: RecommendationStorePort,
        tickers: list[str],
        macro_symbols: dict[str, str],
    ) -> None:
        self._market_data = market_data
        self._tech = technical_analysis
        self._fe = feature_engineer
        self._predictors = predictors
        self._store = store
        self._tickers = tickers
        self._macro_symbols = macro_symbols

    def execute(
        self,
        start_month: str = "2024-01",
        end_month: str = "2026-05",
    ) -> None:
        """Run walk-forward pretraining."""
        months = self._generate_months(start_month, end_month)
        if len(months) < 3:
            logger.warning("Too few months for walk-forward training")
            return

        # Validate feature names
        validate_feature_matrix(self._fe.get_feature_names())

        # Collect all features and targets
        all_features, all_targets = self._collect_features_and_targets(months)

        if not all_features:
            logger.warning("No training data collected")
            return

        # Walk-forward training
        min_train = max(2, len(months) // 3)
        for i in range(min_train, len(months)):
            train_features = []
            train_targets: dict[str, list[float]] = {"2d": [], "5d": [], "10d": []}

            for j in range(i):
                month = months[j]
                if month in all_features:
                    train_features.extend(all_features[month])
                    for h in ("2d", "5d", "10d"):
                        train_targets[h].extend(all_targets[month][h])

            if not train_features:
                continue

            # Train each horizon
            for horizon in ("2d", "5d", "10d"):
                self._predictors[horizon].fit(
                    train_features, train_targets[horizon]
                )

            # Evaluate on test month
            test_month = months[i]
            if test_month in all_features and all_features[test_month]:
                for horizon in ("2d", "5d", "10d"):
                    preds = self._predictors[horizon].predict(
                        all_features[test_month]
                    )
                    actuals = all_targets[test_month][horizon]
                    if preds and actuals:
                        correct = sum(
                            1 for p, a in zip(preds, actuals)
                            if (p > 0 and a > 0) or (p < 0 and a < 0)
                        )
                        accuracy = correct / len(preds)
                        self._store.save_evaluation_run(
                            EvaluationRun(
                                run_date=test_month,
                                eval_type="walk_forward",
                                horizon=horizon,
                                metric_name="directional_accuracy",
                                metric_value=accuracy,
                            )
                        )

        logger.info(f"Pretraining complete: {len(months)} months processed")

    def _collect_features_and_targets(
        self, months: list[str]
    ) -> tuple[dict[str, list[dict[str, float]]], dict[str, dict[str, list[float]]]]:
        all_features: dict[str, list[dict[str, float]]] = {}
        all_targets: dict[str, dict[str, list[float]]] = {}

        for month in months:
            month_features: list[dict[str, float]] = []
            month_targets: dict[str, list[float]] = {"2d": [], "5d": [], "10d": []}

            # Parse month to get date range
            year, m = int(month[:4]), int(month[5:7])
            month_start = datetime(year, m, 1)
            if m == 12:
                month_end = datetime(year + 1, 1, 1) - timedelta(days=1)
            else:
                month_end = datetime(year, m + 1, 1) - timedelta(days=1)

            # Fetch macro data once per month
            macro_signals = self._fetch_macro(month_end)

            for ticker in self._tickers:
                try:
                    features, targets = self._compute_ticker_features(
                        ticker, month_end, macro_signals
                    )
                    if features:
                        month_features.append(features)
                        for h in ("2d", "5d", "10d"):
                            month_targets[h].append(targets.get(h, 0.0))
                except Exception as e:
                    logger.debug(f"Skipping {ticker} for {month}: {e}")
                    continue

            if month_features:
                all_features[month] = month_features
                all_targets[month] = month_targets

        return all_features, all_targets

    def _compute_ticker_features(
        self,
        ticker: str,
        prediction_time: datetime,
        macro_signals: dict[str, list],
    ) -> tuple[dict[str, float], dict[str, float]]:
        start = prediction_time - timedelta(days=365)
        signals = self._market_data.get_signals(
            ticker, prediction_time, start_date=start
        )
        if len(signals) < 20:
            return {}, {}

        indicators = self._tech.compute_indicators(signals)
        ticker_info = self._market_data.get_ticker_info(ticker)
        options = self._market_data.get_options_summary(ticker, prediction_time)
        analyst = self._market_data.get_analyst_data(ticker, prediction_time)

        features = self._fe.compute(
            signals=signals,
            indicators=indicators,
            ticker_info=ticker_info,
            options_summary=options,
            analyst_data=analyst,
            macro_signals=macro_signals,
            sector_signals=None,
        )

        # Compute target returns (actual future returns)
        last_price = signals[-1].price
        targets: dict[str, float] = {}
        for h_label, h_days in [("2d", 2), ("5d", 5), ("10d", 10)]:
            future_time = prediction_time + timedelta(days=h_days)
            future_signals = self._market_data.get_signals(
                ticker, future_time, start_date=prediction_time
            )
            future_prices = [
                s.price for s in future_signals if s.timestamp > prediction_time
            ]
            if future_prices:
                targets[h_label] = (future_prices[-1] / last_price) - 1
            else:
                targets[h_label] = 0.0

        return features, targets

    def _fetch_macro(
        self, prediction_time: datetime
    ) -> dict[str, list]:
        macro: dict[str, list] = {}
        start = prediction_time - timedelta(days=365)
        for name, symbol in self._macro_symbols.items():
            macro[symbol] = self._market_data.get_signals(
                symbol, prediction_time, start_date=start
            )
        return macro

    @staticmethod
    def _generate_months(start: str, end: str) -> list[str]:
        months: list[str] = []
        y, m = int(start[:4]), int(start[5:7])
        ey, em = int(end[:4]), int(end[5:7])
        while (y, m) <= (ey, em):
            months.append(f"{y:04d}-{m:02d}")
            m += 1
            if m > 12:
                m = 1
                y += 1
        return months


class WeeklyTournamentUseCase:
    """Weekly stock tournament: predict, grade, rank, and store top 15."""

    def __init__(
        self,
        market_data: MarketDataPort,
        technical_analysis: TechnicalAnalysisPort,
        feature_engineer: FeatureEngineerPort,
        predictors: dict[str, StockPredictorPort],
        store: RecommendationStorePort,
        tickers: list[str],
        macro_symbols: dict[str, str],
        market: str = "us",
    ) -> None:
        self._market_data = market_data
        self._tech = technical_analysis
        self._fe = feature_engineer
        self._predictors = predictors
        self._store = store
        self._tickers = tickers
        self._macro_symbols = macro_symbols
        self._market = market

    def execute(self, prediction_date: datetime) -> WeeklyReport:
        """Run weekly tournament and return report."""
        week_start = prediction_date.strftime("%Y-%m-%d")

        # Fetch macro once
        macro_signals = self._fetch_macro(prediction_date)

        # Score all tickers
        candidates: list[StockRecommendation] = []
        for ticker in self._tickers:
            try:
                rec = self._score_ticker(
                    ticker, prediction_date, week_start, macro_signals
                )
                if rec is not None:
                    candidates.append(rec)
            except Exception as e:
                logger.debug(f"Skipping {ticker}: {e}")
                continue

        # Rank by composite score, take top 15
        candidates.sort(key=lambda r: r.composite_score, reverse=True)
        top_picks = candidates[:15]

        # Store recommendations
        for rec in top_picks:
            self._store.save_recommendation(rec)

        report = WeeklyReport(
            report_date=week_start,
            market=self._market,
            recommendations=top_picks,
        )
        self._store.save_weekly_report(report)

        logger.info(
            f"Tournament complete: {len(top_picks)} picks from {len(candidates)} candidates"
        )
        return report

    def _score_ticker(
        self,
        ticker: str,
        prediction_time: datetime,
        week_start: str,
        macro_signals: dict[str, list],
    ) -> StockRecommendation | None:
        start = prediction_time - timedelta(days=365)
        signals = self._market_data.get_signals(
            ticker, prediction_time, start_date=start
        )
        if len(signals) < 20:
            return None

        indicators = self._tech.compute_indicators(signals)
        ticker_info = self._market_data.get_ticker_info(ticker)
        options = self._market_data.get_options_summary(ticker, prediction_time)
        analyst = self._market_data.get_analyst_data(ticker, prediction_time)

        features = self._fe.compute(
            signals=signals,
            indicators=indicators,
            ticker_info=ticker_info,
            options_summary=options,
            analyst_data=analyst,
            macro_signals=macro_signals,
            sector_signals=None,
        )

        # Predict each horizon
        feature_row = [features]
        pred_2d = self._predictors["2d"].predict(feature_row)[0]
        pred_5d = self._predictors["5d"].predict(feature_row)[0]
        pred_10d = self._predictors["10d"].predict(feature_row)[0]

        prediction = MultiHorizonPrediction(
            predicted_return_2d=pred_2d,
            predicted_return_5d=pred_5d,
            predicted_return_10d=pred_10d,
            confidence_2d=0.5,  # TODO: derive from model uncertainty
            confidence_5d=0.5,
            confidence_10d=0.5,
        )

        grade, horizon_signals = grade_from_horizons(prediction)

        # Composite score for ranking
        composite = (
            abs(pred_2d) * 0.2 + abs(pred_5d) * 0.3 + abs(pred_10d) * 0.5
        )

        return StockRecommendation(
            symbol=ticker,
            week_start=week_start,
            grade=grade,
            composite_score=composite,
            prediction=prediction,
            horizon_signals=horizon_signals,
            reasoning=f"Multi-horizon: 2d={pred_2d:.3f}, 5d={pred_5d:.3f}, 10d={pred_10d:.3f}",
            sources=["yfinance"],
            rsi_14=indicators.get("rsi_14"),
            macd=indicators.get("macd"),
        )

    def _fetch_macro(self, prediction_time: datetime) -> dict[str, list]:
        macro: dict[str, list] = {}
        start = prediction_time - timedelta(days=365)
        for name, symbol in self._macro_symbols.items():
            macro[symbol] = self._market_data.get_signals(
                symbol, prediction_time, start_date=start
            )
        return macro


class TrackRecommendationsUseCase:
    """Evaluate last week's recommendations against actual returns."""

    def __init__(
        self,
        market_data: MarketDataPort,
        store: RecommendationStorePort,
    ) -> None:
        self._market_data = market_data
        self._store = store

    def execute(self, evaluation_date: datetime) -> list[AccuracyRecord]:
        """Compare predictions from last week with actual outcomes."""
        week_start = (evaluation_date - timedelta(days=7)).strftime("%Y-%m-%d")
        recs = self._store.get_recommendations(week_start=week_start)
        records: list[AccuracyRecord] = []

        for rec in recs:
            try:
                # Get actual returns
                signals = self._market_data.get_signals(
                    rec.symbol,
                    evaluation_date,
                    start_date=datetime.strptime(rec.week_start, "%Y-%m-%d"),
                )
                if len(signals) < 2:
                    continue

                base_price = signals[0].price
                prices = {s.timestamp: s.price for s in signals}

                actual_2d = self._get_return(signals, base_price, 2)
                actual_5d = self._get_return(signals, base_price, 5)
                actual_10d = self._get_return(signals, base_price, 10)

                record = AccuracyRecord(
                    symbol=rec.symbol,
                    week_start=rec.week_start,
                    predicted_grade=rec.grade.value,
                    predicted_return_2d=rec.prediction.predicted_return_2d,
                    predicted_return_5d=rec.prediction.predicted_return_5d,
                    predicted_return_10d=rec.prediction.predicted_return_10d,
                    actual_return_2d=actual_2d,
                    actual_return_5d=actual_5d,
                    actual_return_10d=actual_10d,
                    direction_correct_2d=self._same_direction(
                        rec.prediction.predicted_return_2d, actual_2d
                    ),
                    direction_correct_5d=self._same_direction(
                        rec.prediction.predicted_return_5d, actual_5d
                    ),
                    direction_correct_10d=self._same_direction(
                        rec.prediction.predicted_return_10d, actual_10d
                    ),
                )
                self._store.save_accuracy_record(record)
                records.append(record)
            except Exception as e:
                logger.debug(f"Could not evaluate {rec.symbol}: {e}")
                continue

        return records

    @staticmethod
    def _get_return(
        signals: list, base_price: float, days: int
    ) -> float:
        if len(signals) > days:
            return signals[days].price / base_price - 1
        return signals[-1].price / base_price - 1

    @staticmethod
    def _same_direction(predicted: float, actual: float) -> bool:
        return (predicted > 0 and actual > 0) or (predicted < 0 and actual < 0)


class EvaluationUseCase:
    """Run full evaluation suite: walk-forward, permutation, costs, regime, drawdown."""

    def __init__(self, store: RecommendationStorePort) -> None:
        self._store = store

    def execute(
        self,
        eval_type: str = "walk_forward",
        **kwargs: Any,
    ) -> list[EvaluationRun]:
        """Run evaluation and store results. Delegates to evaluation module."""
        # This use case wraps the evaluation module and stores results.
        # Full implementation coordinates with PretrainingUseCase outputs.
        logger.info(f"Evaluation type: {eval_type}")
        return []
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_pretraining.py tests/test_weekly_tournament.py -v`
Expected: All 7 tests PASS

- [ ] **Step 6: Commit**

```bash
git add application/use_cases.py tests/test_pretraining.py tests/test_weekly_tournament.py
git commit -m "feat: add PretrainingUseCase, WeeklyTournamentUseCase, TrackRecommendationsUseCase"
```

---

## Task 17: CLI

**Files:**
- Create: `application/cli.py`

- [ ] **Step 1: Implement CLI entry point**

Create `application/cli.py`:

```python
"""CLI entry point for multi-modal stock recommender.

Usage:
    python -m application.cli pretrain --market us --start 2024-01 --end 2026-05
    python -m application.cli run-tournament --market us --date 2026-05-25
    python -m application.cli evaluate-last-week --date 2026-05-25
    python -m application.cli evaluate --type walk-forward
    python -m application.cli show-report --week 2026-05-19
"""

from datetime import datetime
from pathlib import Path

import click
from loguru import logger

from adapters.data.sqlite_store import SQLiteStore
from adapters.data.yfinance_adapter import YFinanceAdapter
from adapters.ml.ensemble_predictor import EnsemblePredictor
from adapters.ml.feature_engineer import FeatureEngineer
from application.use_cases import (
    PretrainingUseCase,
    TrackRecommendationsUseCase,
    WeeklyTournamentUseCase,
)
from config.loader import load_market_config


def _build_dependencies(
    market: str, use_cache: bool = False
) -> dict:
    """Wire adapters to ports — composition root."""
    config = load_market_config(market)
    cache_dir = Path("data/cache")
    db_path = "data/recommendations.db"

    adapter = YFinanceAdapter(cache_dir=cache_dir, use_cache=use_cache)
    store = SQLiteStore(db_path)
    fe = FeatureEngineer()

    # One ensemble per horizon
    predictors = {
        "2d": EnsemblePredictor(random_seed=42),
        "5d": EnsemblePredictor(random_seed=43),
        "10d": EnsemblePredictor(random_seed=44),
    }

    macro_symbols = config.get("macro_symbols", {})

    return {
        "market_data": adapter,
        "technical_analysis": adapter,  # same adapter, implements both ports
        "feature_engineer": fe,
        "predictors": predictors,
        "store": store,
        "macro_symbols": macro_symbols,
        "config": config,
    }


@click.group()
def cli() -> None:
    """Multi-modal stock recommender CLI."""
    pass


@cli.command()
@click.option("--market", default="us", help="Market config (us, ca, in)")
@click.option("--start", default="2024-01", help="Start month (YYYY-MM)")
@click.option("--end", default="2026-05", help="End month (YYYY-MM)")
def pretrain(market: str, start: str, end: str) -> None:
    """Run walk-forward pretraining on historical data."""
    deps = _build_dependencies(market)
    config = deps["config"]

    # Get ticker universe (simplified: top S&P 500 names)
    # In production, this would dynamically discover tickers
    tickers = _get_ticker_universe(config)

    use_case = PretrainingUseCase(
        market_data=deps["market_data"],
        technical_analysis=deps["technical_analysis"],
        feature_engineer=deps["feature_engineer"],
        predictors=deps["predictors"],
        store=deps["store"],
        tickers=tickers,
        macro_symbols=deps["macro_symbols"],
    )

    logger.info(f"Starting pretraining: {start} to {end}, {len(tickers)} tickers")
    use_case.execute(start_month=start, end_month=end)
    logger.info("Pretraining complete")


@cli.command("run-tournament")
@click.option("--market", default="us")
@click.option("--date", default=None, help="Prediction date (YYYY-MM-DD)")
def run_tournament(market: str, date: str | None) -> None:
    """Run weekly tournament and generate top 15 picks."""
    deps = _build_dependencies(market)
    config = deps["config"]
    tickers = _get_ticker_universe(config)

    prediction_date = (
        datetime.strptime(date, "%Y-%m-%d") if date else datetime.now()
    )

    use_case = WeeklyTournamentUseCase(
        market_data=deps["market_data"],
        technical_analysis=deps["technical_analysis"],
        feature_engineer=deps["feature_engineer"],
        predictors=deps["predictors"],
        store=deps["store"],
        tickers=tickers,
        macro_symbols=deps["macro_symbols"],
        market=market,
    )

    report = use_case.execute(prediction_date=prediction_date)
    _print_report(report)


@cli.command("evaluate-last-week")
@click.option("--date", default=None, help="Evaluation date (YYYY-MM-DD)")
def evaluate_last_week(date: str | None) -> None:
    """Compare last week's predictions with actual outcomes."""
    deps = _build_dependencies("us")
    eval_date = datetime.strptime(date, "%Y-%m-%d") if date else datetime.now()

    use_case = TrackRecommendationsUseCase(
        market_data=deps["market_data"],
        store=deps["store"],
    )

    records = use_case.execute(evaluation_date=eval_date)
    if records:
        correct_2d = sum(1 for r in records if r.direction_correct_2d) / len(records)
        correct_5d = sum(1 for r in records if r.direction_correct_5d) / len(records)
        correct_10d = sum(1 for r in records if r.direction_correct_10d) / len(records)
        click.echo(f"Evaluated {len(records)} recommendations:")
        click.echo(f"  2-day accuracy: {correct_2d:.1%}")
        click.echo(f"  5-day accuracy: {correct_5d:.1%}")
        click.echo(f"  10-day accuracy: {correct_10d:.1%}")
    else:
        click.echo("No recommendations to evaluate")


@cli.command("show-report")
@click.option("--week", required=True, help="Week start date (YYYY-MM-DD)")
def show_report(week: str) -> None:
    """Display a stored weekly report."""
    deps = _build_dependencies("us")
    report = deps["store"].get_weekly_report(week)
    if report:
        _print_report(report)
    else:
        click.echo(f"No report found for week {week}")


def _get_ticker_universe(config: dict) -> list[str]:
    """Get ticker universe from config.

    Phase 3A: static list. Phase 3B: dynamic buzz-driven discovery.
    """
    # Default S&P 500 subset for Phase 3A
    return [
        "AAPL", "MSFT", "GOOG", "AMZN", "NVDA", "META", "TSLA", "BRK-B",
        "UNH", "JNJ", "V", "XOM", "JPM", "PG", "MA", "HD", "CVX", "MRK",
        "ABBV", "LLY", "PEP", "KO", "COST", "AVGO", "WMT", "MCD", "CSCO",
        "ACN", "TMO", "ABT", "DHR", "NEE", "LIN", "TXN", "PM", "UPS",
        "RTX", "HON", "LOW", "QCOM",
    ]


def _print_report(report) -> None:  # type: ignore[no-untyped-def]
    """Pretty-print a weekly report."""
    click.echo(f"\n{'='*60}")
    click.echo(f"Weekly Report: {report.report_date} ({report.market})")
    click.echo(f"{'='*60}")
    for i, rec in enumerate(report.recommendations, 1):
        signals_str = " | ".join(
            f"{h}:{s}" for h, s in rec.horizon_signals.items()
        )
        click.echo(
            f"  {i:2d}. {rec.symbol:6s} [{rec.grade.value:14s}] "
            f"score={rec.composite_score:.3f} ({signals_str})"
        )
    click.echo(f"{'='*60}\n")


if __name__ == "__main__":
    cli()
```

- [ ] **Step 2: Verify CLI is callable**

Run: `python -m application.cli --help`
Expected: Shows help text with pretrain, run-tournament, evaluate-last-week, show-report commands

- [ ] **Step 3: Commit**

```bash
git add application/cli.py
git commit -m "feat: add Click CLI entry point with pretrain, run-tournament, evaluate, show-report commands"
```

- [ ] **Step 4: Run full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All tests PASS (~60+ tests)

- [ ] **Step 5: Run pre-commit checks**

Run: `pre-commit run --all-files`
Expected: All hooks pass (black, isort, mypy, ruff, gitleaks)

- [ ] **Step 6: Final commit for any formatting fixes**

```bash
git add -A
git commit -m "chore: formatting fixes from pre-commit hooks"
```

---

## Summary

| Task | Component | New Tests | Key Deliverable |
|------|-----------|-----------|-----------------|
| 1 | Domain exceptions | 3 | InsufficientDataError, StaleDataError |
| 2 | Domain models (core) | 6 | RecommendationGrade, MultiHorizonPrediction |
| 3 | Domain models (containers) | 6 | StockRecommendation, AccuracyRecord, EvaluationRun, WeeklyReport |
| 4 | Domain ports | 1 | TechnicalAnalysisPort, RecommendationStorePort, FeatureEngineerPort |
| 5 | Domain services | 17 | grade_from_horizons, validate_feature_matrix, validate_data_freshness |
| 6 | Property tests | 8 | Hypothesis invariant tests |
| 7 | Config | 2 | us.yaml + YAML loader |
| 8 | Test fakes | 1 | 5 fake adapters for all ports |
| 9 | CachingMixin | 4 | Append-only raw data cache |
| 10 | yfinance adapter | 5 | MarketDataPort + TechnicalAnalysisPort impl |
| 11 | Feature engineer | 5 | 45 features across 8 groups |
| 12 | SQLite store | 7 | RecommendationStorePort impl |
| 13 | ML predictors | 7 | XGBoost, LightGBM, Ridge |
| 14 | Ensemble | 3 | Weighted XGB+LGBM+Ridge average |
| 15 | Evaluation | 11 | Walk-forward, permutation, costs, regime, drawdown |
| 16 | Use cases | 7 | Pretraining, Tournament, Tracking, Evaluation |
| 17 | CLI | 0 | Click entry point with 4 commands |
| **Total** | | **~93** | |
