"""Evaluation framework for stock recommendation engine (ADR-011).

Five components: walk-forward validation, permutation testing,
transaction cost modeling, regime splitting, and drawdown tracking.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class WalkForwardValidator:
    """Expanding-window walk-forward validation."""

    min_train_months: int = 12

    def generate_splits(self, months: list[str]) -> list[tuple[list[str], str]]:
        """Return expanding-window splits.

        Each split: (training_months, test_month).
        First test month is at index ``min_train_months``.
        """
        splits: list[tuple[list[str], str]] = []
        for i in range(self.min_train_months, len(months)):
            train = months[:i]
            test = months[i]
            splits.append((train, test))
        return splits


@dataclass
class PermutationTester:
    """Permutation test for directional accuracy significance."""

    n_shuffles: int = 1000
    random_seed: int = 42

    def test_directional_accuracy(
        self, predictions: list[float], actuals: list[float]
    ) -> float:
        """Return p-value: fraction of shuffled accuracies >= observed.

        Directional accuracy = fraction of matching signs.
        """
        n = len(predictions)
        if n == 0:
            return 1.0

        observed = self._directional_accuracy(predictions, actuals)

        rng = random.Random(self.random_seed)
        count_ge = 0
        for _ in range(self.n_shuffles):
            shuffled = actuals[:]
            rng.shuffle(shuffled)
            shuffled_acc = self._directional_accuracy(predictions, shuffled)
            if shuffled_acc >= observed:
                count_ge += 1

        return count_ge / self.n_shuffles

    @staticmethod
    def _directional_accuracy(predictions: list[float], actuals: list[float]) -> float:
        n = len(predictions)
        matches = sum(1 for p, a in zip(predictions, actuals) if (p >= 0) == (a >= 0))
        return matches / n


@dataclass
class TransactionCostModel:
    """Simple proportional transaction cost model."""

    cost_per_trade: float = 0.001

    def apply_costs(
        self,
        gross_returns: list[float],
        n_trades_per_period: int = 2,
    ) -> list[float]:
        """Subtract transaction costs from each period's gross return."""
        total_cost = self.cost_per_trade * n_trades_per_period
        return [r - total_cost for r in gross_returns]

    def total_costs(self, n_periods: int, n_trades_per_period: int = 2) -> float:
        """Total cumulative cost over all periods."""
        return self.cost_per_trade * n_trades_per_period * n_periods


@dataclass
class RegimeSplitter:
    """Classify market regime from monthly SPY returns."""

    bull_threshold: float = 0.10
    bear_threshold: float = -0.10

    def classify_monthly(self, spy_monthly_returns: list[float]) -> list[str]:
        """Classify each month using rolling 12-month annualized return.

        Returns one label per month (starting from month index 0).
        For months with fewer than 12 prior returns, uses whatever
        history is available.
        """
        labels: list[str] = []
        for i in range(len(spy_monthly_returns)):
            # Use up to 12 months ending at current month (inclusive)
            start = max(0, i - 11)
            window = spy_monthly_returns[start : i + 1]
            # Annualize: multiply average monthly return by 12
            avg_monthly = sum(window) / len(window)
            annualized = avg_monthly * 12
            if annualized > self.bull_threshold:
                labels.append("bull")
            elif annualized < self.bear_threshold:
                labels.append("bear")
            else:
                labels.append("sideways")
        return labels


@dataclass
class DrawdownTracker:
    """Compute max drawdown and recovery periods from a return series."""

    def compute(self, returns: list[float]) -> dict[str, float | int | None]:
        """Return max_drawdown (negative float) and recovery_periods.

        max_drawdown: worst peak-to-trough decline (0.0 if no decline).
        recovery_periods: number of periods from trough back to peak,
            or None if not recovered by end of series.
        """
        if not returns:
            return {"max_drawdown": 0.0, "recovery_periods": None}

        # Build cumulative equity curve (starting at 1.0)
        equity = [1.0]
        for r in returns:
            equity.append(equity[-1] * (1 + r))

        peak = equity[0]
        max_drawdown = 0.0
        worst_trough_idx: int | None = None
        worst_peak_val = peak
        for i in range(1, len(equity)):
            if equity[i] > peak:
                peak = equity[i]
            drawdown = (equity[i] - peak) / peak
            if drawdown < max_drawdown:
                max_drawdown = drawdown
                worst_trough_idx = i
                worst_peak_val = peak

        # Recovery: find first index after trough where equity >= peak
        recovery_periods: int | None = None
        if worst_trough_idx is not None:
            for i in range(worst_trough_idx + 1, len(equity)):
                if equity[i] >= worst_peak_val:
                    recovery_periods = i - worst_trough_idx
                    break

        return {
            "max_drawdown": max_drawdown,
            "recovery_periods": recovery_periods,
        }
