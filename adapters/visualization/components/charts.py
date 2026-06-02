"""Shared Plotly chart builders for dashboard — consistent palette, clean layout."""

from __future__ import annotations

import plotly.graph_objects as go

COLOR_PALETTE: dict[str, str] = {
    "green": "#00C853",
    "red": "#FF1744",
    "blue": "#2979FF",
    "amber": "#FFD600",
    "gray": "#9E9E9E",
}

_GRADE_CHART_COLORS: dict[str, str] = {
    "Strong Buy": "#00C853",
    "Buy": "#69F0AE",
    "Hold": "#FFD600",
    "May Sell": "#FF9100",
    "Immediate Sell": "#FF1744",
}

_LAYOUT_DEFAULTS: dict[str, object] = {
    "template": "plotly_white",
    "margin": {"l": 40, "r": 20, "t": 40, "b": 40},
    "font": {"size": 12},
}


def accuracy_line_chart(
    fold_accuracies: list[float],
    baseline: float = 0.5,
) -> go.Figure:
    """Line chart of per-fold directional accuracy with baseline."""
    fig = go.Figure()

    if fold_accuracies:
        folds = list(range(1, len(fold_accuracies) + 1))
        fig.add_trace(
            go.Scatter(
                x=folds,
                y=fold_accuracies,
                mode="lines+markers",
                name="Accuracy",
                line={"color": COLOR_PALETTE["blue"]},
            )
        )
        fig.add_trace(
            go.Scatter(
                x=folds,
                y=[baseline] * len(folds),
                mode="lines",
                name=f"Random ({baseline:.0%})",
                line={"color": COLOR_PALETTE["gray"], "dash": "dash"},
            )
        )
    else:
        fig.add_trace(go.Scatter(x=[], y=[], name="Accuracy"))
        fig.add_trace(go.Scatter(x=[], y=[], name="Baseline"))

    fig.update_layout(
        title="Walk-Forward Directional Accuracy",
        xaxis_title="Fold",
        yaxis_title="Accuracy",
        yaxis={"range": [0, 1]},
        **_LAYOUT_DEFAULTS,
    )
    return fig


def grade_donut(grade_counts: dict[str, int]) -> go.Figure:
    """Donut chart of recommendation grade distribution."""
    fig = go.Figure()

    if grade_counts:
        labels = list(grade_counts.keys())
        values = list(grade_counts.values())
        colors = [_GRADE_CHART_COLORS.get(g, COLOR_PALETTE["gray"]) for g in labels]
        fig.add_trace(
            go.Pie(
                labels=labels,
                values=values,
                hole=0.4,
                marker={"colors": colors},
            )
        )

    fig.update_layout(title="Grade Distribution", **_LAYOUT_DEFAULTS)
    return fig


def sector_heatmap(data: dict[str, dict[str, float]]) -> go.Figure:
    """Heatmap of sector × timeframe returns."""
    fig = go.Figure()

    if data:
        sectors = list(data.keys())
        timeframes = list(next(iter(data.values())).keys()) if data else []
        z = [[data[s].get(t, 0.0) for t in timeframes] for s in sectors]

        fig.add_trace(
            go.Heatmap(
                z=z,
                x=timeframes,
                y=sectors,
                colorscale=[
                    [0, COLOR_PALETTE["red"]],
                    [0.5, "white"],
                    [1, COLOR_PALETTE["green"]],
                ],
                zmid=0,
                text=[[f"{v:.1%}" for v in row] for row in z],
                texttemplate="%{text}",
            )
        )

    fig.update_layout(title="Sector Momentum", **_LAYOUT_DEFAULTS)
    return fig


def decay_curve(magnitude: float, half_life: float, days: int = 10) -> go.Figure:
    """Exponential decay curve for event impact visualization."""
    x = list(range(days + 1))
    y = [magnitude * (0.5 ** (d / half_life)) for d in x]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x,
            y=y,
            mode="lines+markers",
            name="Impact",
            line={"color": COLOR_PALETTE["amber"]},
            fill="tozeroy",
        )
    )
    fig.update_layout(
        title="Event Impact Decay",
        xaxis_title="Days Since Event",
        yaxis_title="Remaining Impact",
        **_LAYOUT_DEFAULTS,
    )
    return fig


def shap_bar_chart(
    features: list[str],
    importances: list[float],
) -> go.Figure:
    """Horizontal bar chart of SHAP feature importance."""
    fig = go.Figure()

    if features and importances:
        paired = sorted(zip(importances, features), reverse=True)[:20]
        vals, names = zip(*paired) if paired else ([], [])
        fig.add_trace(
            go.Bar(
                x=list(vals),
                y=list(names),
                orientation="h",
                marker={"color": COLOR_PALETTE["blue"]},
            )
        )

    fig.update_layout(
        title="SHAP Feature Importance (Top 20)",
        xaxis_title="Mean |SHAP|",
        yaxis={"autorange": "reversed"},
        **_LAYOUT_DEFAULTS,
    )
    return fig


def ablation_bar_chart(
    variants: list[str],
    accuracies: list[float],
) -> go.Figure:
    """Grouped bar chart for ablation study variants."""
    fig = go.Figure()

    if variants and accuracies:
        colors = [COLOR_PALETTE["blue"], COLOR_PALETTE["amber"], COLOR_PALETTE["green"]]
        bar_colors = [colors[i % len(colors)] for i in range(len(variants))]
        fig.add_trace(
            go.Bar(
                x=variants,
                y=accuracies,
                marker={"color": bar_colors},
                text=[f"{a:.1%}" for a in accuracies],
                textposition="auto",
            )
        )

    fig.update_layout(
        title="Ablation Study — Directional Accuracy by Variant",
        yaxis_title="Accuracy",
        yaxis={"range": [0, 1]},
        **_LAYOUT_DEFAULTS,
    )
    return fig
