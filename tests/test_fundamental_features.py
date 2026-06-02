"""Tests for FundamentalFeatureEngineer — 16 valuation features."""

from __future__ import annotations

import math

import pytest

from adapters.ml.fundamental_feature_engineer import (
    FUNDAMENTAL_FEATURE_NAMES,
    FundamentalFeatureEngineer,
)

_AAPL_INFO: dict[str, float] = {
    "trailing_pe": 28.5,
    "peg_ratio": 1.5,
    "price_to_book": 45.0,
    "debt_to_equity": 150.0,
    "free_cashflow": 50_000_000_000,
    "market_cap": 3_000_000_000_000,
    "dividend_yield": 0.005,
    "revenue_growth": 0.08,
    "current_ratio": 1.1,
    "gross_margins": 0.45,
    "operating_margins": 0.30,
    "institutional_ownership": 0.60,
}

_SECTOR_INFOS: list[dict[str, float]] = [
    {"trailing_pe": 25.0, "price_to_book": 10.0, "peg_ratio": 1.2},
    {"trailing_pe": 30.0, "price_to_book": 50.0, "peg_ratio": 2.0},
    {"trailing_pe": 35.0, "price_to_book": 20.0, "peg_ratio": 1.8},
]


@pytest.fixture()
def eng() -> FundamentalFeatureEngineer:
    return FundamentalFeatureEngineer()


# --- Feature list ---


def test_feature_names_count() -> None:
    assert len(FUNDAMENTAL_FEATURE_NAMES) == 16


def test_feature_names_are_expected() -> None:
    expected = {
        "peg_ratio",
        "pe_ratio",
        "pe_vs_sector",
        "price_to_book",
        "debt_to_equity",
        "free_cash_flow_yield",
        "dividend_yield",
        "revenue_growth_yoy",
        "earnings_surprise_last",
        "earnings_surprise_streak",
        "institutional_ownership_change",
        "current_ratio",
        "gross_margin",
        "operating_margin",
        "valuation_z_score",
        "insider_net_purchases_90d",
    }
    assert set(FUNDAMENTAL_FEATURE_NAMES) == expected


def test_get_feature_names_matches_constant(eng: FundamentalFeatureEngineer) -> None:
    assert eng.get_feature_names() == FUNDAMENTAL_FEATURE_NAMES


# --- Direct pass-through features ---


def test_peg_ratio(eng: FundamentalFeatureEngineer) -> None:
    result = eng.compute(_AAPL_INFO, _SECTOR_INFOS)
    assert result["peg_ratio"] == pytest.approx(1.5)


def test_pe_ratio(eng: FundamentalFeatureEngineer) -> None:
    result = eng.compute(_AAPL_INFO, _SECTOR_INFOS)
    assert result["pe_ratio"] == pytest.approx(28.5)


def test_price_to_book(eng: FundamentalFeatureEngineer) -> None:
    result = eng.compute(_AAPL_INFO, _SECTOR_INFOS)
    assert result["price_to_book"] == pytest.approx(45.0)


def test_debt_to_equity(eng: FundamentalFeatureEngineer) -> None:
    result = eng.compute(_AAPL_INFO, _SECTOR_INFOS)
    assert result["debt_to_equity"] == pytest.approx(150.0)


def test_dividend_yield(eng: FundamentalFeatureEngineer) -> None:
    result = eng.compute(_AAPL_INFO, _SECTOR_INFOS)
    assert result["dividend_yield"] == pytest.approx(0.005)


def test_revenue_growth_yoy(eng: FundamentalFeatureEngineer) -> None:
    result = eng.compute(_AAPL_INFO, _SECTOR_INFOS)
    assert result["revenue_growth_yoy"] == pytest.approx(0.08)


def test_current_ratio(eng: FundamentalFeatureEngineer) -> None:
    result = eng.compute(_AAPL_INFO, _SECTOR_INFOS)
    assert result["current_ratio"] == pytest.approx(1.1)


def test_gross_margin(eng: FundamentalFeatureEngineer) -> None:
    result = eng.compute(_AAPL_INFO, _SECTOR_INFOS)
    assert result["gross_margin"] == pytest.approx(0.45)


def test_operating_margin(eng: FundamentalFeatureEngineer) -> None:
    result = eng.compute(_AAPL_INFO, _SECTOR_INFOS)
    assert result["operating_margin"] == pytest.approx(0.30)


# --- Computed: FCF yield ---


def test_free_cash_flow_yield(eng: FundamentalFeatureEngineer) -> None:
    result = eng.compute(_AAPL_INFO, _SECTOR_INFOS)
    # 50B / 3T = 0.01666...
    assert result["free_cash_flow_yield"] == pytest.approx(
        50_000_000_000 / 3_000_000_000_000
    )


def test_free_cash_flow_yield_nan_when_no_market_cap(
    eng: FundamentalFeatureEngineer,
) -> None:
    info = {**_AAPL_INFO}
    del info["market_cap"]
    result = eng.compute(info, _SECTOR_INFOS)
    assert math.isnan(result["free_cash_flow_yield"])


def test_free_cash_flow_yield_nan_when_zero_market_cap(
    eng: FundamentalFeatureEngineer,
) -> None:
    info = {**_AAPL_INFO, "market_cap": 0}
    result = eng.compute(info, _SECTOR_INFOS)
    assert math.isnan(result["free_cash_flow_yield"])


# --- Computed: PE vs sector ---


def test_pe_vs_sector(eng: FundamentalFeatureEngineer) -> None:
    result = eng.compute(_AAPL_INFO, _SECTOR_INFOS)
    # Sector PEs [25, 30, 35] → median=30, ticker=28.5 → (28.5-30)/30 = -0.05
    assert result["pe_vs_sector"] == pytest.approx(-0.05)


def test_pe_vs_sector_nan_when_no_pe(eng: FundamentalFeatureEngineer) -> None:
    info = {**_AAPL_INFO}
    del info["trailing_pe"]
    result = eng.compute(info, _SECTOR_INFOS)
    assert math.isnan(result["pe_vs_sector"])


def test_pe_vs_sector_nan_when_no_sector_peers(eng: FundamentalFeatureEngineer) -> None:
    result = eng.compute(_AAPL_INFO, [])
    assert math.isnan(result["pe_vs_sector"])


# --- Earnings features from analyst_data ---


def test_earnings_surprise_last_from_analyst_data(
    eng: FundamentalFeatureEngineer,
) -> None:
    ad = {"earnings_surprise_pct": 0.07, "earnings_surprise_streak": 3.0}
    result = eng.compute(_AAPL_INFO, _SECTOR_INFOS, analyst_data=ad)
    assert result["earnings_surprise_last"] == pytest.approx(0.07)


def test_earnings_surprise_streak_from_analyst_data(
    eng: FundamentalFeatureEngineer,
) -> None:
    ad = {"earnings_surprise_pct": 0.07, "earnings_surprise_streak": 3.0}
    result = eng.compute(_AAPL_INFO, _SECTOR_INFOS, analyst_data=ad)
    assert result["earnings_surprise_streak"] == pytest.approx(3.0)


def test_earnings_features_nan_when_no_analyst_data(
    eng: FundamentalFeatureEngineer,
) -> None:
    result = eng.compute(_AAPL_INFO, _SECTOR_INFOS)
    assert math.isnan(result["earnings_surprise_last"])
    assert math.isnan(result["earnings_surprise_streak"])


# --- Institutional ownership change ---


def test_institutional_ownership_change(eng: FundamentalFeatureEngineer) -> None:
    result = eng.compute(_AAPL_INFO, _SECTOR_INFOS, prior_institutional_ownership=0.55)
    assert result["institutional_ownership_change"] == pytest.approx(0.05)


def test_institutional_ownership_change_nan_when_no_prior(
    eng: FundamentalFeatureEngineer,
) -> None:
    result = eng.compute(_AAPL_INFO, _SECTOR_INFOS)
    assert math.isnan(result["institutional_ownership_change"])


# --- Valuation Z-score ---


def test_valuation_z_score_is_numeric(eng: FundamentalFeatureEngineer) -> None:
    result = eng.compute(_AAPL_INFO, _SECTOR_INFOS)
    assert not math.isnan(result["valuation_z_score"])


def test_valuation_z_score_nan_when_missing_peg(
    eng: FundamentalFeatureEngineer,
) -> None:
    info = {**_AAPL_INFO}
    del info["peg_ratio"]
    result = eng.compute(info, _SECTOR_INFOS)
    assert math.isnan(result["valuation_z_score"])


def test_valuation_z_score_nan_when_missing_price_to_book(
    eng: FundamentalFeatureEngineer,
) -> None:
    info = {**_AAPL_INFO}
    del info["price_to_book"]
    result = eng.compute(info, _SECTOR_INFOS)
    assert math.isnan(result["valuation_z_score"])


def test_valuation_z_score_nan_when_no_sector(eng: FundamentalFeatureEngineer) -> None:
    result = eng.compute(_AAPL_INFO, [])
    assert math.isnan(result["valuation_z_score"])


# --- Graceful degradation ---


def test_all_features_nan_for_empty_ticker_info(
    eng: FundamentalFeatureEngineer,
) -> None:
    result = eng.compute({}, [])
    for key, val in result.items():
        assert math.isnan(val), f"Expected NaN for {key!r}, got {val}"


def test_output_has_all_16_feature_keys(eng: FundamentalFeatureEngineer) -> None:
    result = eng.compute(_AAPL_INFO, _SECTOR_INFOS)
    assert set(result.keys()) == set(FUNDAMENTAL_FEATURE_NAMES)


# --- Insider purchases always NaN ---


def test_insider_net_purchases_90d_always_nan(eng: FundamentalFeatureEngineer) -> None:
    result = eng.compute(_AAPL_INFO, _SECTOR_INFOS)
    assert math.isnan(result["insider_net_purchases_90d"])
