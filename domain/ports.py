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
    """Port: load market data with point-in-time and leakage prevention."""

    def get_signals(
        self, symbol: str, prediction_time: datetime,
        start_date: datetime | None = None, end_date: datetime | None = None,
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
        self, symbol: str, prediction_time: datetime,
        start_date: datetime | None = None, end_date: datetime | None = None,
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
        self, signals: list[Signal], indicators: dict[str, float],
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
    def get_recommendations(self, week_start: str | None = None, symbol: str | None = None) -> list[StockRecommendation]: ...
    def save_accuracy_record(self, record: AccuracyRecord) -> None: ...
    def get_accuracy_records(self, week_start: str | None = None, symbol: str | None = None) -> list[AccuracyRecord]: ...
    def save_evaluation_run(self, run: EvaluationRun) -> None: ...
    def get_evaluation_runs(self, run_date: str | None = None, eval_type: str | None = None) -> list[EvaluationRun]: ...
    def save_weekly_report(self, report: WeeklyReport) -> None: ...
    def get_weekly_report(self, report_date: str) -> WeeklyReport | None: ...


class BacktestResultPort(Protocol):
    """Port: persist and retrieve backtest results for recursive learning."""

    def save_result(self, result: BacktestResult) -> None: ...
    def get_results(
        self, symbol: str | None = None, model_version: str | None = None,
        start_date: datetime | None = None, end_date: datetime | None = None,
    ) -> list[BacktestResult]: ...
