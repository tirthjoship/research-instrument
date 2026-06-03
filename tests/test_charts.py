"""Tests for Plotly chart builders."""

from __future__ import annotations


class TestColorPalette:
    def test_palette_has_required_colors(self) -> None:
        from adapters.visualization.components.charts import COLOR_PALETTE

        assert COLOR_PALETTE["green"] == "#00C853"
        assert COLOR_PALETTE["red"] == "#FF1744"
        assert COLOR_PALETTE["blue"] == "#2979FF"
        assert COLOR_PALETTE["amber"] == "#FFD600"
        assert COLOR_PALETTE["gray"] == "#9E9E9E"


class TestAccuracyLineChart:
    def test_returns_plotly_figure(self) -> None:
        from adapters.visualization.components.charts import accuracy_line_chart

        fig = accuracy_line_chart(
            fold_accuracies=[0.48, 0.52, 0.55, 0.50],
            baseline=0.5,
        )
        import plotly.graph_objects as go

        assert isinstance(fig, go.Figure)

    def test_has_two_traces(self) -> None:
        from adapters.visualization.components.charts import accuracy_line_chart

        fig = accuracy_line_chart(fold_accuracies=[0.5, 0.6], baseline=0.5)
        assert len(fig.data) == 2

    def test_empty_folds_returns_figure(self) -> None:
        from adapters.visualization.components.charts import accuracy_line_chart

        fig = accuracy_line_chart(fold_accuracies=[], baseline=0.5)
        import plotly.graph_objects as go

        assert isinstance(fig, go.Figure)


class TestGradeDonut:
    def test_returns_figure(self) -> None:
        from adapters.visualization.components.charts import grade_donut

        fig = grade_donut(
            {"Strong Buy": 3, "Buy": 5, "Hold": 4, "May Sell": 2, "Immediate Sell": 1}
        )
        import plotly.graph_objects as go

        assert isinstance(fig, go.Figure)

    def test_empty_counts_returns_figure(self) -> None:
        from adapters.visualization.components.charts import grade_donut

        fig = grade_donut({})
        import plotly.graph_objects as go

        assert isinstance(fig, go.Figure)


class TestSectorHeatmap:
    def test_returns_figure(self) -> None:
        from adapters.visualization.components.charts import sector_heatmap

        data = {
            "Technology": {"1d": 0.02, "5d": 0.05, "10d": -0.01},
            "Healthcare": {"1d": -0.01, "5d": 0.02, "10d": 0.03},
        }
        fig = sector_heatmap(data)
        import plotly.graph_objects as go

        assert isinstance(fig, go.Figure)

    def test_empty_data_returns_figure(self) -> None:
        from adapters.visualization.components.charts import sector_heatmap

        fig = sector_heatmap({})
        import plotly.graph_objects as go

        assert isinstance(fig, go.Figure)


class TestDecayCurve:
    def test_returns_figure(self) -> None:
        from adapters.visualization.components.charts import decay_curve

        fig = decay_curve(magnitude=0.05, half_life=5.0, days=10)
        import plotly.graph_objects as go

        assert isinstance(fig, go.Figure)

    def test_has_one_trace(self) -> None:
        from adapters.visualization.components.charts import decay_curve

        fig = decay_curve(magnitude=0.05, half_life=3.0, days=7)
        assert len(fig.data) == 1


class TestShapBarChart:
    def test_returns_figure(self) -> None:
        from adapters.visualization.components.charts import shap_bar_chart

        fig = shap_bar_chart(
            features=["correlation_with_spy", "return_1d", "obv_trend"],
            importances=[0.015, 0.010, 0.009],
        )
        import plotly.graph_objects as go

        assert isinstance(fig, go.Figure)

    def test_empty_returns_figure(self) -> None:
        from adapters.visualization.components.charts import shap_bar_chart

        fig = shap_bar_chart(features=[], importances=[])
        import plotly.graph_objects as go

        assert isinstance(fig, go.Figure)


class TestAblationBarChart:
    def test_returns_figure(self) -> None:
        from adapters.visualization.components.charts import ablation_bar_chart

        fig = ablation_bar_chart(
            variants=["technical_only", "technical_plus_sentiment", "all_features"],
            accuracies=[0.474, 0.697, 0.697],
        )
        import plotly.graph_objects as go

        assert isinstance(fig, go.Figure)

    def test_empty_returns_figure(self) -> None:
        from adapters.visualization.components.charts import ablation_bar_chart

        fig = ablation_bar_chart(variants=[], accuracies=[])
        import plotly.graph_objects as go

        assert isinstance(fig, go.Figure)


class TestGradeDonutWithEnumValues:
    def test_enum_values_get_correct_colors(self) -> None:
        from adapters.visualization.components.charts import grade_donut

        fig = grade_donut(
            {"strong_buy": 2, "buy": 5, "hold": 4, "may_sell": 2, "immediate_sell": 1}
        )
        import plotly.graph_objects as go

        assert isinstance(fig, go.Figure)
        if fig.data:
            colors = fig.data[0].marker.colors
            assert "#9E9E9E" not in colors  # no gray fallback


class TestAblationHumanReadable:
    def test_human_readable_labels(self) -> None:
        from adapters.visualization.components.charts import ablation_bar_chart

        fig = ablation_bar_chart(
            variants=["technical_only", "technical_plus_sentiment"],
            accuracies=[0.474, 0.697],
        )
        assert fig.data[0].x[0] == "Technical Only"
        assert fig.data[0].x[1] == "Technical + Sentiment"
