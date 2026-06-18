"""Portfolio-vs-SPY cumulative return chart (attributed actual, no projection)."""

from __future__ import annotations

import plotly.graph_objects as go

from adapters.visualization.components.charts import apply_dossier_template


def alpha_vs_spy(port_pct: float, spy_pct: float | None) -> float | None:
    if spy_pct is None:
        return None
    return port_pct - spy_pct


def build_perf_figure(
    *, port_pct: list[float], spy_pct: list[float], labels: list[str]
) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=spy_pct,
            name="SPY",
            mode="lines",
            line={"color": "#94A3B8", "width": 2, "dash": "dash"},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=port_pct,
            name="Portfolio",
            mode="lines",
            line={"color": "#16A34A", "width": 2.5},
            fill="tozeroy",
            fillcolor="rgba(22,163,74,0.15)",
        )
    )
    fig.update_layout(
        height=220, showlegend=False, margin={"l": 30, "r": 10, "t": 10, "b": 20}
    )
    return apply_dossier_template(fig)
