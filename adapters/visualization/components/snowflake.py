"""Evidence snowflake — descriptive Plotly radar. Factual percentiles only.

NOT the falsified-era radar (deleted in the realignment): every axis is a
present-tense fact (factor percentile, trend state, book-fit arithmetic).
NOTE: this module's source must stay clean of domain.fit.FORBIDDEN_WORDS —
do not reintroduce forecasting vocabulary even in comments.
"""

from __future__ import annotations

import plotly.graph_objects as go

_MIN_AXES = 3


def build_snowflake(axes: dict[str, float]) -> go.Figure | None:
    """Radar figure from axis-name -> 0..100 score. None if < 3 axes."""
    if len(axes) < _MIN_AXES:
        return None
    names = list(axes.keys())
    values = [max(0.0, min(100.0, float(v))) for v in axes.values()]
    fig = go.Figure(
        go.Scatterpolar(
            r=values + [values[0]],
            theta=names + [names[0]],
            fill="toself",
            fillcolor="rgba(29,78,216,0.18)",
            line={"color": "#1D4ED8", "width": 2},
        )
    )
    fig.update_layout(
        polar={
            "radialaxis": {
                "range": [0, 100],
                "showticklabels": False,
                "gridcolor": "#E7E5E4",
            },
            "angularaxis": {
                "gridcolor": "#E7E5E4",
                "tickfont": {"size": 12, "color": "#5C6370"},
            },
            "bgcolor": "rgba(0,0,0,0)",
        },
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        height=320,
        margin={"l": 60, "r": 60, "t": 30, "b": 30},
    )
    return fig
