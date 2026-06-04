"""Tests for SmartMoneyFeatureEngineer — TDD first."""

from __future__ import annotations

from datetime import datetime

import pytest

from adapters.ml.smart_money_engineer import SmartMoneyFeatureEngineer
from domain.conviction import SmartMoneySignal, SmartMoneyType

PREDICTION_TIME = datetime(2026, 6, 1, 12, 0, 0)


def _make_13d(
    ticker: str = "AAPL",
    stake_pct: float = 5.2,
    is_activist: bool = True,
    transaction_value: float = 1_000_000.0,
) -> SmartMoneySignal:
    return SmartMoneySignal(
        ticker=ticker,
        signal_type=SmartMoneyType.FORM_13D,
        filer_name="Activist Fund LLC",
        stake_pct=stake_pct,
        transaction_value=transaction_value,
        filed_date="2026-05-30",
        is_activist=is_activist,
    )


def _make_form4(
    ticker: str = "AAPL",
    transaction_type: str = "Purchase",
    transaction_value: float = 50_000.0,
) -> SmartMoneySignal:
    return SmartMoneySignal(
        ticker=ticker,
        signal_type=SmartMoneyType.FORM_4,
        filer_name="John Doe",
        stake_pct=None,
        transaction_value=transaction_value,
        filed_date="2026-05-31",
        is_activist=False,
        insider_role="CFO",
        transaction_type=transaction_type,
    )


class TestSmartMoneyFeatureEngineer:
    def setup_method(self) -> None:
        self.eng = SmartMoneyFeatureEngineer()

    def test_no_signals_returns_all_zeros(self) -> None:
        result = self.eng.compute("AAPL", [], PREDICTION_TIME)
        assert result["sm_13d_count"] == 0.0
        assert result["sm_activist_count"] == 0.0
        assert result["sm_max_stake_pct"] == 0.0
        assert result["sm_form4_buy_count"] == 0.0
        assert result["sm_form4_sell_count"] == 0.0
        assert result["sm_total_buy_value"] == 0.0
        assert result["sm_total_sell_value"] == 0.0
        assert result["sm_insider_cluster"] == 0.0

    def test_13d_filing_sets_stake_and_activist(self) -> None:
        signals = [_make_13d(ticker="AAPL", stake_pct=5.2, is_activist=True)]
        result = self.eng.compute("AAPL", signals, PREDICTION_TIME)
        assert result["sm_13d_count"] == 1.0
        assert result["sm_activist_count"] == 1.0
        assert result["sm_max_stake_pct"] == pytest.approx(5.2)

    def test_four_insider_buys_cluster_score(self) -> None:
        signals = [
            _make_form4(ticker="MSFT", transaction_type="Purchase") for _ in range(4)
        ]
        result = self.eng.compute("MSFT", signals, PREDICTION_TIME)
        assert result["sm_form4_buy_count"] == 4.0
        assert result["sm_insider_cluster"] >= 0.8

    def test_sell_signal_only(self) -> None:
        signals = [
            _make_form4(
                ticker="TSLA", transaction_type="Sale", transaction_value=200_000.0
            )
        ]
        result = self.eng.compute("TSLA", signals, PREDICTION_TIME)
        assert result["sm_form4_sell_count"] == 1.0
        assert result["sm_form4_buy_count"] == 0.0
        assert result["sm_total_sell_value"] == pytest.approx(200_000.0)
        assert result["sm_total_buy_value"] == 0.0

    def test_feature_names_returns_8(self) -> None:
        names = self.eng.get_feature_names()
        assert len(names) == 8
        expected = {
            "sm_13d_count",
            "sm_activist_count",
            "sm_max_stake_pct",
            "sm_form4_buy_count",
            "sm_form4_sell_count",
            "sm_total_buy_value",
            "sm_total_sell_value",
            "sm_insider_cluster",
        }
        assert set(names) == expected

    def test_filters_by_ticker(self) -> None:
        signals = [
            _make_form4(ticker="AAPL", transaction_type="Purchase"),
            _make_form4(ticker="MSFT", transaction_type="Purchase"),
        ]
        result = self.eng.compute("AAPL", signals, PREDICTION_TIME)
        assert result["sm_form4_buy_count"] == 1.0

    def test_cluster_score_capped_at_1(self) -> None:
        signals = [
            _make_form4(ticker="AAPL", transaction_type="Purchase") for _ in range(10)
        ]
        result = self.eng.compute("AAPL", signals, PREDICTION_TIME)
        assert result["sm_insider_cluster"] == pytest.approx(1.0)

    def test_non_activist_13d_not_counted_as_activist(self) -> None:
        signals = [_make_13d(ticker="AAPL", is_activist=False)]
        result = self.eng.compute("AAPL", signals, PREDICTION_TIME)
        assert result["sm_13d_count"] == 1.0
        assert result["sm_activist_count"] == 0.0

    def test_compute_returns_all_8_keys(self) -> None:
        result = self.eng.compute("AAPL", [], PREDICTION_TIME)
        assert set(result.keys()) == set(self.eng.get_feature_names())
