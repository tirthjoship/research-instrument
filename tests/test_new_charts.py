"""Tests for Phase 5.4 Plotly chart builders."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go


class TestSignalRadar:
    def test_returns_figure(self) -> None:
        from adapters.visualization.components.charts import signal_radar

        scores = {
            "Technical": 7.0,
            "Sentiment": 5.0,
            "Fundamental": 8.0,
            "Cross-Asset": 3.0,
            "Event": 6.0,
            "Momentum": 9.0,
        }
        fig = signal_radar(scores)
        assert isinstance(fig, go.Figure)

    def test_has_scatterpolar_trace(self) -> None:
        from adapters.visualization.components.charts import signal_radar

        scores = {"A": 5.0, "B": 3.0, "C": 7.0, "D": 2.0, "E": 8.0, "F": 4.0}
        fig = signal_radar(scores)
        assert len(fig.data) == 1
        assert isinstance(fig.data[0], go.Scatterpolar)

    def test_clamps_values_above_max(self) -> None:
        from adapters.visualization.components.charts import signal_radar

        scores = {"A": 15.0, "B": 3.0, "C": 7.0, "D": 2.0, "E": 8.0, "F": 4.0}
        fig = signal_radar(scores, max_val=10.0)
        # First value (A=15) should be clamped to 10.0
        assert fig.data[0].r[0] == 10.0

    def test_clamps_values_below_zero(self) -> None:
        from adapters.visualization.components.charts import signal_radar

        scores = {"A": -5.0, "B": 3.0, "C": 7.0, "D": 2.0, "E": 8.0, "F": 4.0}
        fig = signal_radar(scores, max_val=10.0)
        assert fig.data[0].r[0] == 0.0


class TestGaugeChart:
    def test_returns_figure(self) -> None:
        from adapters.visualization.components.charts import gauge_chart

        fig = gauge_chart(value=7.5, min_v=0.0, max_v=10.0, label="Conviction")
        assert isinstance(fig, go.Figure)

    def test_has_indicator_trace(self) -> None:
        from adapters.visualization.components.charts import gauge_chart

        fig = gauge_chart(value=50.0, min_v=0.0, max_v=100.0, label="Score")
        assert len(fig.data) == 1
        assert isinstance(fig.data[0], go.Indicator)

    def test_custom_thresholds(self) -> None:
        from adapters.visualization.components.charts import gauge_chart

        fig = gauge_chart(
            value=60.0, min_v=0.0, max_v=100.0, label="Score", thresholds=(40.0, 70.0)
        )
        assert isinstance(fig, go.Figure)


class TestComparisonBars:
    def test_returns_figure(self) -> None:
        from adapters.visualization.components.charts import comparison_bars

        items = [{"name": "AAPL", "value": 8.5}, {"name": "MSFT", "value": 7.2}]
        fig = comparison_bars(items)
        assert isinstance(fig, go.Figure)

    def test_has_bar_trace(self) -> None:
        from adapters.visualization.components.charts import comparison_bars

        items = [{"name": "AAPL", "value": 8.5}, {"name": "MSFT", "value": 7.2}]
        fig = comparison_bars(items)
        assert len(fig.data) == 1
        assert isinstance(fig.data[0], go.Bar)

    def test_highlight_sets_blue_color(self) -> None:
        from adapters.visualization.components.charts import comparison_bars

        items = [{"name": "AAPL", "value": 8.5}, {"name": "MSFT", "value": 7.2}]
        fig = comparison_bars(items, highlight="AAPL")
        colors = list(fig.data[0].marker.color)
        assert colors[0] == "#2563EB"
        assert colors[1] == "#94A3B8"


class TestOwnershipPie:
    def test_returns_figure(self) -> None:
        from adapters.visualization.components.charts import ownership_pie

        fig = ownership_pie(institutional=65.0, insider=5.0, public=30.0)
        assert isinstance(fig, go.Figure)

    def test_has_pie_trace(self) -> None:
        from adapters.visualization.components.charts import ownership_pie

        fig = ownership_pie(institutional=65.0, insider=5.0, public=30.0)
        assert len(fig.data) == 1
        assert isinstance(fig.data[0], go.Pie)

    def test_donut_hole(self) -> None:
        from adapters.visualization.components.charts import ownership_pie

        fig = ownership_pie(institutional=65.0, insider=5.0, public=30.0)
        assert fig.data[0].hole == 0.55


class TestInsiderBars:
    def test_returns_figure(self) -> None:
        from adapters.visualization.components.charts import insider_bars

        txns = [
            {
                "quarter": "Q1 2024",
                "buys": 5,
                "sells": 2,
                "buy_value": 1e6,
                "sell_value": 5e5,
            }
        ]
        fig = insider_bars(txns)
        assert isinstance(fig, go.Figure)

    def test_has_two_bar_traces(self) -> None:
        from adapters.visualization.components.charts import insider_bars

        txns = [
            {
                "quarter": "Q1 2024",
                "buys": 5,
                "sells": 2,
                "buy_value": 1e6,
                "sell_value": 5e5,
            }
        ]
        fig = insider_bars(txns)
        assert len(fig.data) == 2
        assert all(isinstance(t, go.Bar) for t in fig.data)


class TestFinancialsLine:
    def test_returns_figure(self) -> None:
        from adapters.visualization.components.charts import financials_line

        idx = pd.date_range("2022-01-01", periods=4, freq="QE")
        df = pd.DataFrame(
            {
                "revenue": [1e9, 1.1e9, 1.2e9, 1.3e9],
                "net_income": [2e8, 2.2e8, 2.4e8, 2.6e8],
            },
            index=idx,
        )
        fig = financials_line(df, metrics=["revenue", "net_income"])
        assert isinstance(fig, go.Figure)

    def test_has_correct_trace_count(self) -> None:
        from adapters.visualization.components.charts import financials_line

        idx = pd.date_range("2022-01-01", periods=4, freq="QE")
        df = pd.DataFrame(
            {
                "revenue": [1e9, 1.1e9, 1.2e9, 1.3e9],
                "net_income": [2e8, 2.2e8, 2.4e8, 2.6e8],
            },
            index=idx,
        )
        fig = financials_line(df, metrics=["revenue", "net_income"])
        assert len(fig.data) == 2


class TestClusterBubble:
    def test_returns_figure(self) -> None:
        from adapters.visualization.components.charts import cluster_bubble

        tickers = [
            {"ticker": "AAPL", "market_cap": 3e12, "change_pct": 1.5, "role": "leader"},
            {
                "ticker": "MSFT",
                "market_cap": 2.5e12,
                "change_pct": -0.5,
                "role": "follower",
            },
        ]
        fig = cluster_bubble(tickers, group_name="Big Tech")
        assert isinstance(fig, go.Figure)

    def test_has_scatter_trace(self) -> None:
        from adapters.visualization.components.charts import cluster_bubble

        tickers = [
            {"ticker": "AAPL", "market_cap": 3e12, "change_pct": 1.5, "role": "leader"},
        ]
        fig = cluster_bubble(tickers, group_name="Big Tech")
        assert len(fig.data) == 1
        assert isinstance(fig.data[0], go.Scatter)
