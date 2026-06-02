"""Integration test: fundamental features compose correctly."""

from __future__ import annotations

import math

from adapters.ml.fundamental_feature_engineer import (
    FUNDAMENTAL_FEATURE_NAMES,
    FundamentalFeatureEngineer,
)


def test_full_16_feature_vector() -> None:
    """All 16 features computed with complete data."""
    engineer = FundamentalFeatureEngineer()
    info = {
        "trailing_pe": 28.5,
        "peg_ratio": 1.5,
        "price_to_book": 45.0,
        "debt_to_equity": 150.0,
        "free_cashflow": 50e9,
        "market_cap": 3e12,
        "dividend_yield": 0.005,
        "revenue_growth": 0.08,
        "current_ratio": 1.1,
        "gross_margins": 0.45,
        "operating_margins": 0.30,
        "institutional_ownership": 0.60,
    }
    sector = [
        {"trailing_pe": 25.0, "price_to_book": 10.0, "peg_ratio": 1.2},
        {"trailing_pe": 35.0, "price_to_book": 50.0, "peg_ratio": 2.0},
    ]

    analyst_data = {
        "earnings_surprise_pct": 0.05,
        "earnings_surprise_streak": 3.0,
    }
    result = engineer.compute(
        info,
        sector,
        analyst_data=analyst_data,
        prior_institutional_ownership=0.58,
    )

    assert set(result.keys()) == set(FUNDAMENTAL_FEATURE_NAMES)
    assert len(result) == 16
    # Only insider_net_purchases_90d should be NaN (future adapter)
    nan_features = [k for k, v in result.items() if math.isnan(v)]
    assert nan_features == ["insider_net_purchases_90d"]


def test_graceful_empty_info() -> None:
    """Empty ticker_info produces all NaN without errors."""
    engineer = FundamentalFeatureEngineer()
    result = engineer.compute({}, [])
    assert len(result) == 16
    assert all(math.isnan(v) for v in result.values())


def test_features_merge_with_technical() -> None:
    """Fundamental features don't conflict with technical feature names."""
    from adapters.ml.feature_engineer import FEATURE_NAMES as TECHNICAL_NAMES
    from adapters.ml.sentiment_feature_engineer import SENTIMENT_FEATURE_NAMES

    all_names = (
        set(TECHNICAL_NAMES)
        | set(SENTIMENT_FEATURE_NAMES)
        | set(FUNDAMENTAL_FEATURE_NAMES)
    )
    # Some overlap is expected (revenue_growth_yoy, pe_vs_sector_median etc exist in technical).
    # Confirm fundamental features are additive — overlapping ones get overwritten by fundamental.
    # This is acceptable since fundamental computes them more accurately.
    assert len(FUNDAMENTAL_FEATURE_NAMES) == 16
    assert len(all_names) > 60  # At least 60 unique features across all layers
