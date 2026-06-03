"""Shared Plotly chart builders for dashboard — consistent palette, clean layout."""

from __future__ import annotations

import plotly.graph_objects as go

from adapters.visualization.components.formatters import grade_display_name

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
    "margin": {"l": 40, "r": 20, "t": 50, "b": 40},
    "font": {"size": 14},
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
        normalized = {grade_display_name(k): v for k, v in grade_counts.items()}
        labels = list(normalized.keys())
        values = list(normalized.values())
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


_FEATURE_LAYER_COLORS: dict[str, str] = {
    "rsi_14": "#2979FF",
    "macd": "#2979FF",
    "macd_histogram": "#2979FF",
    "macd_signal": "#2979FF",
    "stochastic_k": "#2979FF",
    "stochastic_d": "#2979FF",
    "obv_trend": "#2979FF",
    "return_1d": "#2979FF",
    "return_5d": "#2979FF",
    "price_vs_sma20": "#2979FF",
    "sma20_vs_sma50": "#2979FF",
    "volume_ratio_20d": "#2979FF",
    "price_vs_sma50": "#2979FF",
    "bollinger_pct_b": "#2979FF",
    "atr_14": "#2979FF",
    "price_vs_52w_high": "#2979FF",
    "price_vs_52w_low": "#2979FF",
    "return_6m": "#2979FF",
    "return_12m": "#2979FF",
    "volatility_regime": "#2979FF",
    "drawdown_from_ath": "#2979FF",
    "correlation_with_spy": "#2979FF",
    "relative_strength_vs_peers": "#2979FF",
    "vix_level": "#2979FF",
    "yield_curve_slope": "#2979FF",
    "buzz_volume": "#7C4DFF",
    "buzz_acceleration": "#7C4DFF",
    "sentiment_keyword": "#7C4DFF",
    "sentiment_flan_t5": "#7C4DFF",
    "google_trends_current": "#7C4DFF",
    "stocktwits_bullish_ratio": "#7C4DFF",
    "peg_ratio": "#00C853",
    "pe_ratio": "#00C853",
    "price_to_book": "#00C853",
    "fcf_yield": "#00C853",
    "debt_to_equity": "#00C853",
    "upstream_leader_return_1d": "#FF9100",
    "cluster_momentum_1w": "#FF9100",
    "granger_lead_signal": "#FF9100",
    "event_impact_score": "#FF1744",
    "event_count_7d": "#FF1744",
}


def shap_bar_chart(
    features: list[str],
    importances: list[float],
) -> go.Figure:
    """Horizontal bar chart of SHAP feature importance, colored by layer."""
    fig = go.Figure()

    if features and importances:
        paired = sorted(zip(importances, features), reverse=True)[:20]
        vals, names = zip(*paired) if paired else ([], [])
        bar_colors = [
            _FEATURE_LAYER_COLORS.get(n, COLOR_PALETTE["gray"]) for n in names
        ]
        fig.add_trace(
            go.Bar(
                x=list(vals),
                y=list(names),
                orientation="h",
                marker={"color": bar_colors},
            )
        )

    fig.update_layout(
        title="SHAP Feature Importance (Top 20)",
        xaxis_title="Mean |SHAP|",
        yaxis={"autorange": "reversed"},
        height=500,
        **_LAYOUT_DEFAULTS,
    )
    return fig


_ABLATION_DISPLAY_NAMES: dict[str, str] = {
    "technical_only": "Technical Only",
    "technical_plus_sentiment": "Technical + Sentiment",
    "technical_plus_sentiment_plus_source_weights": "All Features",
}


def ablation_bar_chart(
    variants: list[str],
    accuracies: list[float],
) -> go.Figure:
    """Grouped bar chart for ablation study variants."""
    fig = go.Figure()

    if variants and accuracies:
        display_names = [
            _ABLATION_DISPLAY_NAMES.get(v, v.replace("_", " ").title())
            for v in variants
        ]
        colors = [COLOR_PALETTE["blue"], COLOR_PALETTE["amber"], COLOR_PALETTE["green"]]
        bar_colors = [colors[i % len(colors)] for i in range(len(variants))]
        fig.add_trace(
            go.Bar(
                x=display_names,
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
