"""Fake TechnicalAnalysisPort implementation for testing."""
from domain.models import Signal


class FakeTechnicalAnalysis:
    def __init__(self, indicators: dict[str, float] | None = None) -> None:
        self._indicators = indicators or {
            "rsi_14": 50.0, "macd": 0.0, "macd_signal": 0.0,
            "macd_histogram": 0.0, "stochastic_k": 50.0,
            "stochastic_d": 50.0, "sma_20": 100.0, "sma_50": 100.0,
            "obv_trend": 0.0,
        }

    def compute_indicators(self, signals: list[Signal]) -> dict[str, float]:
        return dict(self._indicators)
