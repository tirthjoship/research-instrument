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
    for sym, base in [
        ("^VIX", 20.0),
        ("^TNX", 4.5),
        ("DX-Y.NYB", 104.0),
        ("^IRX", 5.0),
        ("SPY", 450.0),
    ]:
        sigs: list[Signal] = []
        price = base
        for i in range(260):
            price = max(price + random.gauss(0, base * 0.01), 0.1)
            sigs.append(
                Signal(
                    symbol=sym,
                    timestamp=datetime(2025, 1, 2) + timedelta(days=i),
                    price=price,
                    volume=1_000_000,
                    open_=price,
                    high=price + 0.1,
                    low=price - 0.1,
                )
            )
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
        options_summary={
            "put_call_ratio": 0.8,
            "unusual_options_volume": 50000,
            "iv_skew_25d": 0.05,
        },
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


def test_sector_relative_strength_computed(
    engineer: FeatureEngineer,
    signals: list[Signal],
    indicators: dict[str, float],
    ticker_info: dict[str, float],
    macro_signals: dict[str, list[Signal]],
) -> None:
    """sector_relative_strength_6m should be computed when sector signals exist."""
    import random

    random.seed(77)
    sector_sigs: list[Signal] = []
    price = 100.0
    for i in range(260):
        price = max(price + random.gauss(0, 1.5), 1.0)
        sector_sigs.append(
            Signal(
                symbol="XLK",
                timestamp=signals[i].timestamp,
                price=price,
                volume=500_000,
                open_=price - 0.5,
                high=price + 1.0,
                low=price - 1.0,
            )
        )

    features = engineer.compute(
        signals=signals,
        indicators=indicators,
        ticker_info=ticker_info,
        options_summary=None,
        analyst_data=None,
        macro_signals=macro_signals,
        sector_signals=sector_sigs,
    )

    import math

    assert not math.isnan(features["sector_relative_strength_6m"])


def test_handles_short_history(engineer: FeatureEngineer) -> None:
    """With only 30 days of data, long-horizon features become NaN."""
    short_signals = _make_signals(30)
    features = engineer.compute(
        signals=short_signals,
        indicators={
            "rsi_14": 50.0,
            "macd": 0.0,
            "macd_signal": 0.0,
            "macd_histogram": 0.0,
            "stochastic_k": 50.0,
            "stochastic_d": 50.0,
            "sma_20": 100.0,
            "obv_trend": 0.0,
        },
        ticker_info={},
        options_summary=None,
        analyst_data=None,
        macro_signals={},
        sector_signals=None,
    )
    assert len(features) == 45
    import math

    assert math.isnan(features["return_12m"])  # not enough history
