"""Growth panel (spec D10): rev/eps YoY rates + quarterly trend -> measured colour.

Growth = RATES only. Six metrics: Rev YoY and EPS YoY (from yfinance info),
plus four honest DATA-GAP metrics (Rev 3y CAGR, FCF YoY, Fwd rev, Peer rank)
for which no point-in-time source is wired.
"""

from __future__ import annotations

import html as _html
from typing import Any

from adapters.visualization.components import panel_charts
from adapters.visualization.components.info_tip import render_info
from adapters.visualization.components.status_chip import render_status_chip
from adapters.visualization.tabs.stock_analysis.panel import Verdict, build_panel
from adapters.visualization.tabs.stock_analysis.valuation_view import Metric

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pct(val: float) -> str:
    """Convert decimal growth rate (0.69) to display string ('+69%')."""
    p = int(round(val * 100))
    prefix = "+" if p >= 0 else ""
    return f"{prefix}{p}%"


def _growth_metric(
    info: dict[str, Any],
    key: str,
    label: str,
    meaning: str,
    basis: str,
) -> Metric:
    """Return a YoY metric: green when positive, grey when absent or non-positive."""
    raw = info.get(key)
    try:
        val: float | None = float(raw) if raw is not None else None
    except (TypeError, ValueError):
        val = None
    if val is None:
        return Metric(key, label, "—", "data gap", "grey", meaning, basis)
    tone = "green" if val > 0 else "grey"
    return Metric(key, label, _pct(val), "", tone, meaning, basis)


def _data_gap(key: str, label: str, meaning: str, basis: str) -> Metric:
    """Return a DATA-GAP placeholder: value '—', tone grey, sub 'data gap'."""
    return Metric(key, label, "—", "data gap", "grey", meaning, basis)


def _quarterly_series(result: Any) -> tuple[list[float], list[float]]:
    """
    Extract revenue and net income quarterly series from result.quarterly_financials.

    Returns (rev_series, ni_series) in chronological order.
    On any failure returns empty lists — caller treats them as DATA-GAP for the trend.
    """
    try:
        qf = result.quarterly_financials
        if qf is None:
            return [], []
        rev_row = qf.loc["Total Revenue"] if "Total Revenue" in qf.index else None
        ni_row = qf.loc["Net Income"] if "Net Income" in qf.index else None
        rev: list[float] = (
            list(reversed([float(v) for v in rev_row.values]))
            if rev_row is not None
            else []
        )
        ni: list[float] = (
            list(reversed([float(v) for v in ni_row.values]))
            if ni_row is not None
            else []
        )
        return rev, ni
    except Exception:
        return [], []


# ---------------------------------------------------------------------------
# Strip tile
# ---------------------------------------------------------------------------

_STRIP_TILE = (
    '<div class="sa-tile t-{tone}"><div class="lab">{label} {info}</div>'
    '<div class="num">{value}</div><div class="sub">{sub}</div></div>'
)


def _strip_html(metrics: list[Metric]) -> str:
    tiles = "".join(
        _STRIP_TILE.format(
            tone=m.tone,
            label=_html.escape(m.label),
            info=render_info(m.meaning, m.basis) if m.meaning else "",
            value=_html.escape(m.value),
            sub=_html.escape(m.sub),
        )
        for m in metrics
    )
    return f'<div class="sa-strip">{tiles}</div>'


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_growth_view(result: Any) -> dict[str, Any]:
    """Build the growth view-model.

    Returns a dict with keys: metrics, rev_series, ni_series, chips, claim,
    reframe, verdicts.
    """
    info: dict[str, Any] = getattr(result, "info", {}) or {}

    metrics: list[Metric] = [
        _growth_metric(
            info,
            "revenueGrowth",
            "Rev YoY",
            "Year-over-year revenue growth; trailing twelve months vs prior year.",
            "yfinance info.revenueGrowth",
        ),
        _growth_metric(
            info,
            "earningsGrowth",
            "EPS YoY",
            "Year-over-year earnings growth; trailing vs prior year.",
            "yfinance info.earningsGrowth",
        ),
        _data_gap(
            "rev_3y_cagr",
            "Rev 3y CAGR",
            "Three-year compounded annual growth rate of revenue.",
            "no source wired",
        ),
        _data_gap(
            "fcf_yoy",
            "FCF YoY",
            "Year-over-year free cash flow growth.",
            "no source wired",
        ),
        _data_gap(
            "fwd_rev",
            "Fwd rev (3rd-party)",
            "Forward revenue growth from analyst consensus; a third-party figure, not our estimate.",
            "attributed / analyst consensus — not wired",
        ),
        _data_gap(
            "peer_rank",
            "Peer rank",
            "Growth percentile vs peer group.",
            "no source wired",
        ),
    ]

    rev_series, ni_series = _quarterly_series(result)

    # ACCELERATING chip: emitted only when the QoQ revenue increment genuinely rose
    chips = ""
    if len(rev_series) >= 3:
        qoq = [rev_series[i] - rev_series[i - 1] for i in range(1, len(rev_series))]
        if len(qoq) >= 2 and qoq[-1] > qoq[-2]:
            chips += render_status_chip(
                "ACCELERATING",
                "",
                tone="green",
                rule=(
                    "Most recent quarterly revenue increment exceeds prior quarter's — "
                    "acceleration measured from quarterly_financials."
                ),
            )

    return {
        "metrics": metrics,
        "rev_series": rev_series,
        "ni_series": ni_series,
        "chips": chips,
        "claim": "Revenue and earnings expanding year-on-year.",
        "reframe": (
            "YoY rates are trailing facts. "
            "3y CAGR, FCF growth, forward estimates, and peer rank are not wired (data gap)."
        ),
        "verdicts": [
            Verdict("pos", "Positive YoY revenue growth reported."),
            Verdict("neu", "Longer-run CAGR and FCF trend require additional data."),
        ],
    }


def build_growth_panel(result: Any) -> str:
    """Compose the full Growth deep-dive panel HTML (panel #2)."""
    v = build_growth_view(result)
    trend_viz = panel_charts.trend_lines(
        [
            ("Rev", v["rev_series"], "#2f9e44"),
            ("Net Inc", v["ni_series"], "#1971c2"),
        ]
    )
    left = (
        '<div class="sa-pnl-subh">Quarterly revenue &amp; net income</div>' + trend_viz
    )
    return build_panel(
        number=2,
        name="Growth",
        dot_colour="#2f9e44",
        info_html=render_info(
            "YoY growth rates from trailing data; quarterly trend from financials.",
            "info.revenueGrowth / info.earningsGrowth + quarterly_financials",
        ),
        chips_html=v["chips"],
        claim=v["claim"],
        reframe=v["reframe"],
        strip_html=_strip_html(v["metrics"]),
        viz_left=left,
        viz_right="",
        verdicts=v["verdicts"],
        drill="open full growth — 3y CAGR · FCF growth · forward estimates",
    )
