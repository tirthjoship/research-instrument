"""Port interfaces (protocols) for multi-modal stock recommender.

Adapters implement these ports; domain and application depend only
on these abstractions. Ports support point-in-time access and leakage pruning.
"""

from datetime import datetime
from typing import Protocol, runtime_checkable

from .models import (
    AccuracyRecord,
    BacktestResult,
    BuzzSignal,
    ClassifiedEvent,
    CorrelationEdge,
    EvaluationRun,
    Holding,
    Sentiment,
    Signal,
    SourceReliability,
    StockRecommendation,
    WeeklyReport,
)


class MarketDataPort(Protocol):
    """Port: load market data with point-in-time and leakage prevention."""

    def get_signals(
        self,
        symbol: str,
        prediction_time: datetime,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[Signal]: ...

    def get_ticker_info(self, symbol: str) -> dict[str, float]: ...

    def get_options_summary(
        self, symbol: str, prediction_time: datetime
    ) -> dict[str, float] | None: ...

    def get_analyst_data(
        self, symbol: str, prediction_time: datetime
    ) -> dict[str, float] | None: ...

    def validate_point_in_time(self, prediction_time: datetime) -> None: ...


class SentimentPort(Protocol):
    """Port: extract sentiment signals. Phase 3B — not used in Phase 3A."""

    def get_sentiment(
        self,
        symbol: str,
        prediction_time: datetime,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[Sentiment]: ...


class TechnicalAnalysisPort(Protocol):
    """Port: compute technical indicators from OHLCV signals."""

    def compute_indicators(self, signals: list[Signal]) -> dict[str, float]: ...


class StockPredictorPort(Protocol):
    """Port: ML model that predicts stock returns from features."""

    def fit(self, features: list[dict[str, float]], targets: list[float]) -> None: ...
    def predict(self, features: list[dict[str, float]]) -> list[float]: ...
    def save_model(self, path: str) -> None: ...
    def load_model(self, path: str) -> None: ...


class FeatureEngineerPort(Protocol):
    """Port: compute feature vector from raw market data."""

    def compute(
        self,
        signals: list[Signal],
        indicators: dict[str, float],
        ticker_info: dict[str, float],
        options_summary: dict[str, float] | None,
        analyst_data: dict[str, float] | None,
        macro_signals: dict[str, list[Signal]],
        sector_signals: list[Signal] | None,
    ) -> dict[str, float]: ...

    def get_feature_names(self) -> list[str]: ...


class RecommendationStorePort(Protocol):
    """Port: persist and retrieve recommendations, accuracy, evaluations, reports."""

    def save_recommendation(self, rec: StockRecommendation) -> None: ...
    def get_recommendations(
        self, week_start: str | None = None, symbol: str | None = None
    ) -> list[StockRecommendation]: ...
    def save_accuracy_record(self, record: AccuracyRecord) -> None: ...
    def get_accuracy_records(
        self, week_start: str | None = None, symbol: str | None = None
    ) -> list[AccuracyRecord]: ...
    def save_evaluation_run(self, run: EvaluationRun) -> None: ...
    def get_evaluation_runs(
        self, run_date: str | None = None, eval_type: str | None = None
    ) -> list[EvaluationRun]: ...
    def save_weekly_report(self, report: WeeklyReport) -> None: ...
    def get_weekly_report(self, report_date: str) -> WeeklyReport | None: ...


class BacktestResultPort(Protocol):
    """Port: persist and retrieve backtest results for recursive learning."""

    def save_result(self, result: BacktestResult) -> None: ...
    def get_results(
        self,
        symbol: str | None = None,
        model_version: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[BacktestResult]: ...


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


@runtime_checkable
class HistoricalSentimentPort(Protocol):
    """Retrieves historical news/headline sentiment for backtesting."""

    def get_historical_sentiment(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[Sentiment]:
        """Return sentiment observations for symbol in date range."""
        ...


@runtime_checkable
class HoldingsPort(Protocol):
    """Manages portfolio holdings."""

    def add_holding(self, holding: Holding) -> None: ...
    def remove_holding(self, symbol: str) -> None: ...
    def get_holdings(self) -> list[Holding]: ...
    def get_holding(self, symbol: str) -> Holding | None: ...


@runtime_checkable
class CrossAssetPort(Protocol):
    """Builds and queries cross-asset correlation graph."""

    def build_graph(
        self,
        signals_by_ticker: dict[str, list[Signal]],
        window_days: int = 60,
    ) -> None: ...

    def get_upstream_signals(self, ticker: str) -> list[CorrelationEdge]: ...

    def get_cluster_peers(self, ticker: str) -> list[str]: ...

    def get_correlation(self, ticker_a: str, ticker_b: str) -> float: ...


@runtime_checkable
class EventClassifierPort(Protocol):
    """Classifies news headlines into event categories."""

    def classify(self, headline: str, date: str) -> ClassifiedEvent | None: ...

    def classify_batch(
        self, headlines: list[tuple[str, str]]
    ) -> list[ClassifiedEvent]: ...
