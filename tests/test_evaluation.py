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
