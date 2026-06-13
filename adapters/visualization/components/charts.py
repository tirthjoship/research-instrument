"""Shared Plotly chart builders for dashboard — consistent palette, clean layout."""

from __future__ import annotations

import math

import pandas as pd
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


def apply_dossier_template(fig: go.Figure) -> go.Figure:
    """Apply the shared dossier visual theme (transparent bg, IBM Plex Sans, teal colorway)."""
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="IBM Plex Sans, sans-serif", color="#3A4250", size=13),
        margin=dict(l=8, r=8, t=28, b=8),
        colorway=["#0F6E80", "#1F9254", "#C9810E", "#CE2F26", "#717885"],
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor="#E3E7EC")
    fig.update_yaxes(showgrid=True, gridcolor="#EDF0F3", zeroline=False)
    return fig


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


# ── Phase 5.4 chart builders ──────────────────────────────────────────────────


def signal_radar(scores: dict[str, float], max_val: float = 10.0) -> go.Figure:
    """Scatterpolar radar chart for multi-signal scores."""
    categories = list(scores.keys())
    values = [max(0.0, min(max_val, scores[c])) for c in categories]
    # Close polygon
    categories_closed = categories + [categories[0]]
    values_closed = values + [values[0]]

    fig = go.Figure()
    fig.add_trace(
        go.Scatterpolar(
            r=values_closed,
            theta=categories_closed,
            fill="toself",
            fillcolor="rgba(37,99,235,0.15)",
            line={"color": "#2563EB"},
        )
    )
    fig.update_layout(
        polar={"radialaxis": {"visible": True, "range": [0, max_val]}},
        showlegend=False,
        height=300,
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin={"l": 40, "r": 40, "t": 40, "b": 40},
    )
    return fig


def gauge_chart(
    value: float,
    min_v: float,
    max_v: float,
    label: str,
    thresholds: tuple[float, float] | None = None,
) -> go.Figure:
    """Gauge indicator chart with three color zones."""
    rng = max_v - min_v
    if thresholds is None:
        low = min_v + rng * 0.33
        high = min_v + rng * 0.66
    else:
        low, high = thresholds

    fig = go.Figure()
    fig.add_trace(
        go.Indicator(
            mode="gauge+number",
            value=value,
            title={"text": label},
            gauge={
                "axis": {"range": [min_v, max_v]},
                "bar": {"color": "#2563EB"},
                "steps": [
                    {"range": [min_v, low], "color": "#FEE2E2"},
                    {"range": [low, high], "color": "#FEF3C7"},
                    {"range": [high, max_v], "color": "#DCFCE7"},
                ],
            },
        )
    )
    fig.update_layout(height=200, margin={"l": 20, "r": 20, "t": 50, "b": 20})
    return fig


def comparison_bars(
    items: list[dict[str, object]],
    highlight: str | None = None,
    value_suffix: str = "",
) -> go.Figure:
    """Horizontal bar chart with optional highlighted entry."""
    names = [str(item["name"]) for item in items]
    values = [float(item["value"]) for item in items]  # type: ignore[arg-type]
    colors = ["#2563EB" if n == highlight else "#94A3B8" for n in names]
    text = [f"{v}{value_suffix}" for v in values]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=values,
            y=names,
            orientation="h",
            marker={"color": colors},
            text=text,
            textposition="inside",
            insidetextanchor="middle",
            textfont={"color": "white", "family": "JetBrains Mono"},
        )
    )
    height = max(200, len(items) * 40 + 60)
    fig.update_layout(
        yaxis={"autorange": "reversed"},
        height=height,
        margin={"l": 80, "r": 20, "t": 40, "b": 40},
        showlegend=False,
        paper_bgcolor="white",
    )
    return fig


def ownership_pie(institutional: float, insider: float, public: float) -> go.Figure:
    """Donut chart for ownership breakdown."""
    fig = go.Figure()
    fig.add_trace(
        go.Pie(
            labels=["Institutional", "Insider", "Public"],
            values=[institutional, insider, public],
            hole=0.55,
            marker={"colors": ["#2563EB", "#16A34A", "#94A3B8"]},
            textinfo="label+percent",
        )
    )
    fig.update_layout(
        showlegend=False,
        height=280,
        margin={"l": 20, "r": 20, "t": 40, "b": 20},
    )
    return fig


def insider_bars(txns: list[dict[str, object]]) -> go.Figure:
    """Grouped bar chart of insider buy/sell activity."""
    quarters = [str(t["quarter"]) for t in txns]
    buy_vals = [float(t["buy_value"]) / 1e6 for t in txns]  # type: ignore[arg-type]
    sell_vals = [-(float(t["sell_value"]) / 1e6) for t in txns]  # type: ignore[arg-type]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            name="Buys",
            x=quarters,
            y=buy_vals,
            marker={"color": "#16A34A"},
        )
    )
    fig.add_trace(
        go.Bar(
            name="Sells",
            x=quarters,
            y=sell_vals,
            marker={"color": "#DC2626"},
        )
    )
    fig.update_layout(
        barmode="relative",
        legend={"orientation": "h"},
        height=250,
        margin={"l": 40, "r": 20, "t": 40, "b": 40},
    )
    return fig


def financials_line(data: pd.DataFrame, metrics: list[str]) -> go.Figure:
    """Multi-line chart of financial metrics (values in billions)."""
    _COLORS = ["#2563EB", "#16A34A", "#7C3AED", "#EA580C", "#DC2626"]

    fig = go.Figure()
    for i, metric in enumerate(metrics):
        if metric not in data.columns:
            continue
        color = _COLORS[i % len(_COLORS)]
        fig.add_trace(
            go.Scatter(
                x=data.index.tolist(),
                y=(data[metric] / 1e9).tolist(),
                mode="lines+markers",
                name=metric,
                line={"color": color},
            )
        )
    fig.update_layout(
        height=300,
        hovermode="x unified",
        yaxis_title="Billions ($)",
        margin={"l": 60, "r": 20, "t": 40, "b": 40},
    )
    return fig


def cluster_bubble(
    tickers: list[dict[str, object]],
    group_name: str,
    highlight: str | None = None,
) -> go.Figure:
    """Scatter bubble chart for a ticker cluster."""
    if not tickers:
        fig = go.Figure()
        fig.update_layout(title=group_name)
        return fig

    max_mc = float(max(float(t["market_cap"]) for t in tickers))  # type: ignore[arg-type]

    x_vals, y_vals, sizes, colors, texts, border_colors, border_widths, custom = (
        [],
        [],
        [],
        [],
        [],
        [],
        [],
        [],
    )
    for t in tickers:
        mc = float(t["market_cap"])  # type: ignore[arg-type]
        chg = float(t["change_pct"])  # type: ignore[arg-type]
        x_vals.append(mc / 1e9)
        y_vals.append(chg)
        size = max(15.0, math.sqrt(mc / max_mc) * 80)
        sizes.append(size)
        colors.append("#16A34A" if chg >= 0 else "#DC2626")
        texts.append(str(t["ticker"]))
        is_highlight = t["ticker"] == highlight
        border_colors.append("#2563EB" if is_highlight else "rgba(0,0,0,0.2)")
        border_widths.append(3 if is_highlight else 1)
        custom.append([mc / 1e9, str(t["role"])])

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x_vals,
            y=y_vals,
            mode="markers+text",
            text=texts,
            textposition="top center",
            marker={
                "size": sizes,
                "color": colors,
                "line": {"color": border_colors, "width": border_widths},
            },
            customdata=custom,
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Market Cap: $%{customdata[0]:.1f}B<br>"
                "Change: %{y:.2f}%<br>"
                "Role: %{customdata[1]}<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        title=group_name,
        xaxis_title="Market Cap (B)",
        yaxis_title="Change (%)",
        showlegend=False,
        height=350,
        margin={"l": 40, "r": 20, "t": 50, "b": 40},
    )
    return fig
