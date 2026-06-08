"""Tests for application/evaluation.py — evaluation framework."""

from __future__ import annotations

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

        assert len(splits) == 3
        # First test month is the 3rd month (index 2)
        assert splits[0][1] == "2024-03"

    def test_expanding_window(self) -> None:
        months = ["2024-01", "2024-02", "2024-03", "2024-04", "2024-05"]
        validator = WalkForwardValidator(min_train_months=2)
        splits = validator.generate_splits(months)

        for i in range(1, len(splits)):
            assert len(splits[i][0]) > len(splits[i - 1][0])


class TestPermutationTester:
    def test_random_model_not_significant(self) -> None:
        rng = __import__("random").Random(42)
        predictions = [rng.choice([-1.0, 1.0]) for _ in range(100)]
        actuals = [rng.choice([-1.0, 1.0]) for _ in range(100)]

        tester = PermutationTester(n_shuffles=200, random_seed=42)
        p = tester.test_directional_accuracy(predictions, actuals)
        assert p > 0.05

    def test_perfect_model_is_significant(self) -> None:
        actuals = [1.0, -1.0, 1.0, -1.0, 1.0] * 20
        predictions = actuals[:]  # perfect alignment

        tester = PermutationTester(n_shuffles=200, random_seed=42)
        p = tester.test_directional_accuracy(predictions, actuals)
        assert p < 0.05


class TestTransactionCostModel:
    def test_apply_costs(self) -> None:
        model = TransactionCostModel(cost_per_trade=0.001)
        gross = [0.05, 0.03, -0.02]
        net = model.apply_costs(gross, n_trades_per_period=2)

        for g, n in zip(gross, net):
            assert n == pytest.approx(g - 0.002)

    def test_total_costs(self) -> None:
        model = TransactionCostModel(cost_per_trade=0.001)
        total = model.total_costs(n_periods=52, n_trades_per_period=2)
        assert total == pytest.approx(0.104)


def test_cost_for_turnover():
    from application.evaluation import TransactionCostModel

    m = TransactionCostModel(cost_per_trade=0.001)
    assert abs(m.cost_for_turnover(0.5) - 0.0005) < 1e-12
    assert m.cost_for_turnover(0.0) == 0.0


class TestRegimeSplitter:
    def test_classify_bull(self) -> None:
        splitter = RegimeSplitter()
        returns = [0.02] * 12
        labels = splitter.classify_monthly(returns)
        assert all(label == "bull" for label in labels)

    def test_classify_bear(self) -> None:
        splitter = RegimeSplitter()
        returns = [-0.03] * 12
        labels = splitter.classify_monthly(returns)
        assert all(label == "bear" for label in labels)

    def test_classify_sideways(self) -> None:
        splitter = RegimeSplitter()
        returns = [0.005] * 12
        labels = splitter.classify_monthly(returns)
        assert all(label == "sideways" for label in labels)


class TestDrawdownTracker:
    def test_max_drawdown(self) -> None:
        tracker = DrawdownTracker()
        result = tracker.compute([0.10, 0.05, -0.15, -0.10, 0.20])
        assert result["max_drawdown"] < 0.0

    def test_no_drawdown(self) -> None:
        tracker = DrawdownTracker()
        result = tracker.compute([0.05, 0.03, 0.02, 0.04])
        assert result["max_drawdown"] == 0.0

    def test_full_drawdown(self) -> None:
        tracker = DrawdownTracker()
        result = tracker.compute([-0.5, -0.5])
        assert result["max_drawdown"] < -0.5


class TestFullEvaluationSuite:
    def test_evaluate_walk_forward_results(self) -> None:
        from application.evaluation import FullEvaluationSuite

        predictions = [0.03, -0.01, 0.05, 0.02, -0.03, 0.01, 0.04, -0.02, 0.03, 0.01]
        actuals = [0.02, -0.02, 0.03, 0.01, -0.01, -0.01, 0.02, -0.03, 0.01, 0.02]
        spy_monthly = [0.02, -0.01, 0.03, 0.01, -0.02, 0.01, 0.02, -0.01, 0.01, 0.02]

        suite = FullEvaluationSuite()
        report = suite.evaluate(
            predictions=predictions,
            actuals=actuals,
            spy_monthly_returns=spy_monthly,
        )

        assert "directional_accuracy" in report
        assert "p_value" in report
        assert "cost_adjusted_returns" in report
        assert "regime_labels" in report
        assert "max_drawdown" in report

    def test_evaluate_returns_numeric_values(self) -> None:
        from application.evaluation import FullEvaluationSuite

        predictions = [0.05] * 20
        actuals = [0.03] * 20
        spy_monthly = [0.02] * 20

        suite = FullEvaluationSuite()
        report = suite.evaluate(
            predictions=predictions,
            actuals=actuals,
            spy_monthly_returns=spy_monthly,
        )

        assert isinstance(report["directional_accuracy"], float)
        assert isinstance(report["p_value"], float)
        assert isinstance(report["max_drawdown"], float)


class TestBaselineRanker:
    def test_momentum_baseline(self) -> None:
        from application.evaluation import BaselineRanker

        features = {
            "AAPL": {"return_6m": 0.20, "volatility_20d": 0.02},
            "GOOG": {"return_6m": 0.10, "volatility_20d": 0.03},
            "MSFT": {"return_6m": 0.30, "volatility_20d": 0.01},
        }
        ranker = BaselineRanker()
        top = ranker.momentum(features, top_n=2)
        assert top == ["MSFT", "AAPL"]

    def test_low_vol_baseline(self) -> None:
        from application.evaluation import BaselineRanker

        features = {
            "AAPL": {"return_6m": 0.20, "volatility_20d": 0.02},
            "GOOG": {"return_6m": 0.10, "volatility_20d": 0.03},
            "MSFT": {"return_6m": 0.30, "volatility_20d": 0.01},
        }
        ranker = BaselineRanker()
        top = ranker.low_volatility(features, top_n=2)
        assert top == ["MSFT", "AAPL"]

    def test_random_baseline(self) -> None:
        from application.evaluation import BaselineRanker

        features = {f"TICK{i}": {} for i in range(20)}
        ranker = BaselineRanker()
        top = ranker.random_selection(features, top_n=5, n_trials=100, seed=42)
        assert len(top) == 5
        assert all(t in features for t in top)

    def test_equal_weight_baseline(self) -> None:
        from application.evaluation import BaselineRanker

        features = {"AAPL": {}, "GOOG": {}, "MSFT": {}}
        ranker = BaselineRanker()
        top = ranker.equal_weight(features)
        assert set(top) == {"AAPL", "GOOG", "MSFT"}
