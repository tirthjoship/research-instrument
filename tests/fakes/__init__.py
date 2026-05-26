"""Fake adapter implementations for testing."""

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
