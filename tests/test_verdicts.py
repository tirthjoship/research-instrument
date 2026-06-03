"""Tests for plain-English verdict generators."""

from __future__ import annotations


class TestCommandCenterVerdict:
    def test_no_data(self) -> None:
        from adapters.visualization.components.verdicts import command_center_verdict

        v = command_center_verdict(
            n_holdings=0, n_recommendations=0, n_sell_signals=0, freshness_hours=None
        )
        assert "get started" in v.lower() or "no data" in v.lower()

    def test_with_data_fresh(self) -> None:
        from adapters.visualization.components.verdicts import command_center_verdict

        v = command_center_verdict(
            n_holdings=4, n_recommendations=15, n_sell_signals=0, freshness_hours=2.0
        )
        assert "15" in v or "action" in v.lower()

    def test_with_sell_signals(self) -> None:
        from adapters.visualization.components.verdicts import command_center_verdict

        v = command_center_verdict(
            n_holdings=4, n_recommendations=15, n_sell_signals=2, freshness_hours=1.0
        )
        assert "2" in v or "sell" in v.lower() or "urgent" in v.lower()


class TestModelConfidenceVerdict:
    def test_beats_random(self) -> None:
        from adapters.visualization.components.verdicts import model_confidence_verdict

        v = model_confidence_verdict(accuracy=0.65, p_value=0.01, n_folds=19)
        assert "edge" in v.lower() or "proven" in v.lower()

    def test_not_beating_random(self) -> None:
        from adapters.visualization.components.verdicts import model_confidence_verdict

        v = model_confidence_verdict(accuracy=0.52, p_value=0.15, n_folds=19)
        assert "proven" in v.lower() or "random" in v.lower()


class TestSignalLayerVerdict:
    def test_bullish(self) -> None:
        from adapters.visualization.components.verdicts import signal_layer_verdict

        v = signal_layer_verdict("technical", 0.5)
        assert (
            "bullish" in v.lower() or "upward" in v.lower() or "positive" in v.lower()
        )

    def test_neutral(self) -> None:
        from adapters.visualization.components.verdicts import signal_layer_verdict

        v = signal_layer_verdict("technical", 0.05)
        assert "neutral" in v.lower() or "no strong" in v.lower()

    def test_none(self) -> None:
        from adapters.visualization.components.verdicts import signal_layer_verdict

        v = signal_layer_verdict("fundamental", None)
        assert "not yet" in v.lower() or "run" in v.lower()


class TestPickVerdict:
    def test_strong_buy(self) -> None:
        from adapters.visualization.components.verdicts import pick_verdict

        v = pick_verdict(
            grade="strong_buy", n_bullish=3, n_total=3, reasoning="AI demand surge"
        )
        assert "conviction" in v.lower() or "bullish" in v.lower()

    def test_hold(self) -> None:
        from adapters.visualization.components.verdicts import pick_verdict

        v = pick_verdict(
            grade="hold", n_bullish=1, n_total=3, reasoning="mixed signals"
        )
        assert "mixed" in v.lower() or "wait" in v.lower() or "hold" in v.lower()


class TestAblationVerdict:
    def test_significant_lift(self) -> None:
        from adapters.visualization.components.verdicts import ablation_verdict

        v = ablation_verdict(tech_accuracy=0.474, combined_accuracy=0.697)
        assert "help" in v.lower() or "lift" in v.lower()

    def test_no_data(self) -> None:
        from adapters.visualization.components.verdicts import ablation_verdict

        v = ablation_verdict(tech_accuracy=None, combined_accuracy=None)
        assert "run" in v.lower()
