"""Profitability panel (spec D10): margins/ROE/ROIC/FCF-margin (LEVELS & returns).

Profitability = margin levels and capital-return efficiency.
Six metrics: Gross, Operating, Net margin, ROE, ROIC (computed when inputs present),
FCF margin (computed). Comparison: peer margin median not wired — self-only bar shown.
Trend: quarterly gross/operating margin from quarterly_financials when available.
"""

from __future__ import annotations

import html as _html
from typing import Any

from adapters.visualization.components import panel_charts
from adapters.visualization.components.info_tip import render_info
from adapters.visualization.components.status_chip import render_status_chip
from adapters.visualization.components.stock_metrics import STOCK_METRICS
from adapters.visualization.tabs.stock_analysis.panel import Verdict, build_panel
from adapters.visualization.tabs.stock_analysis.valuation_view import Metric

# Statutory effective tax rate used for NOPAT in ROIC computation
_TAX_RATE: float = 0.21


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _f(info: dict[str, Any], key: str) -> float | None:
    v = info.get(key)
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _pct(val: float) -> str:
    """Convert decimal rate (0.75) to display string ('75%')."""
    return f"{int(round(val * 100))}%"


def _margin_metric(
    info: dict[str, Any],
    key: str,
    label: str,
    meaning: str,
    basis: str,
) -> Metric:
    """Return a margin metric tile: green when positive, grey when absent or zero."""
    val = _f(info, key)
    if val is None:
        return Metric(key, label, "—", "data gap", "grey", meaning, basis)
    tone = "green" if val > 0 else "grey"
    return Metric(key, label, _pct(val), "", tone, meaning, basis)


def _compute_roic(info: dict[str, Any], result: Any) -> Metric:
    """Compute ROIC = ebit*(1-tax)/(equity+totalDebt-totalCash).

    DATA-GAP if any input is missing.  Equity is read from info first
    (key: totalStockholdersEquity), then from the most-recent balance-sheet column.
    """
    meaning, basis = STOCK_METRICS["roic"]

    ebit = _f(info, "ebit")
    total_debt = _f(info, "totalDebt")
    total_cash = _f(info, "totalCash")

    # Equity: try info key, then quarterly balance sheet
    equity: float | None = _f(info, "totalStockholdersEquity")
    if equity is None:
        try:
            bs = getattr(result, "quarterly_balance_sheet", None)
            if bs is not None:
                for key in (
                    "Stockholders Equity",
                    "Total Stockholders Equity",
                    "Common Stock Equity",
                ):
                    if key in bs.index:
                        equity = float(bs.loc[key].iloc[0])
                        break
        except Exception:
            equity = None

    if any(v is None for v in (ebit, total_debt, total_cash, equity)):
        return Metric("roic", "ROIC", "—", "data gap", "grey", meaning, basis)

    denominator = equity + total_debt - total_cash  # type: ignore[operator]
    if denominator <= 0:
        return Metric("roic", "ROIC", "—", "data gap", "grey", meaning, basis)

    nopat = ebit * (1 - _TAX_RATE)  # type: ignore[operator]
    val = nopat / denominator
    tone = "green" if val > 0 else "grey"
    return Metric("roic", "ROIC", _pct(val), "", tone, meaning, basis)


def _compute_fcf_margin(info: dict[str, Any]) -> Metric:
    """Compute FCF margin = freeCashflow/totalRevenue.  DATA-GAP if either missing."""
    meaning = (
        "Free cash flow as a fraction of revenue; "
        "measures how efficiently the business converts revenue into cash."
    )
    basis = "freeCashflow / totalRevenue"
    fcf = _f(info, "freeCashflow")
    rev = _f(info, "totalRevenue")
    if fcf is None or rev is None or rev == 0:
        return Metric(
            "fcf_margin", "FCF Margin", "—", "data gap", "grey", meaning, basis
        )
    val = fcf / rev
    tone = "green" if val > 0 else "grey"
    return Metric("fcf_margin", "FCF Margin", _pct(val), "", tone, meaning, basis)


def _quarterly_margin_series(result: Any) -> tuple[list[float], list[float]]:
    """
    Extract gross and operating margin quarterly series from result.quarterly_financials.

    Returns (gross_series, op_series) in chronological order.
    On any failure (None DataFrame, missing rows, parse error) returns empty lists —
    caller renders DATA-GAP / empty trend when either list is empty.
    """
    try:
        qf = getattr(result, "quarterly_financials", None)
        if qf is None:
            return [], []

        rev_row = qf.loc["Total Revenue"] if "Total Revenue" in qf.index else None
        gross_row = qf.loc["Gross Profit"] if "Gross Profit" in qf.index else None
        op_row = qf.loc["Operating Income"] if "Operating Income" in qf.index else None

        if rev_row is None:
            return [], []

        rev_vals = [float(v) for v in rev_row.values]

        def _ratio_series(num_row: Any) -> list[float]:
            out: list[float] = []
            for num, rv in zip(num_row.values, rev_vals):
                try:
                    out.append(float(num) / float(rv) if rv else 0.0)
                except (TypeError, ValueError, ZeroDivisionError):
                    out.append(0.0)
            return list(reversed(out))

        gross_series = _ratio_series(gross_row) if gross_row is not None else []
        op_series = _ratio_series(op_row) if op_row is not None else []
        return gross_series, op_series
    except Exception:
        return [], []


def _margin_direction(series: list[float]) -> str:
    """Slope of the gross-margin series: 'up' widening, 'down' narrowing, 'flat'
    roughly steady, or '' when <2 points. Series are fractions; a +/-1pp net
    change (0.01) is the flat band so quarter noise doesn't flip the badge."""
    if len(series) < 2:
        return ""
    delta = series[-1] - series[0]
    if delta > 0.01:
        return "up"
    if delta < -0.01:
        return "down"
    return "flat"


# Gross-margin slope -> (chip label, chip tone) and a verb for the rule/caption.
_MARGIN_CHIP = {
    "up": ("WIDENING", "green"),
    "down": ("NARROWING", "amber"),
    "flat": ("STEADY", "grey"),
}
_MARGIN_WORD = {"up": "widening", "down": "narrowing", "flat": "roughly steady"}


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


def build_profitability_view(result: Any) -> dict[str, Any]:
    """Build the profitability view-model.

    Returns a dict with keys: metrics, gross_series, op_series, chips,
    claim, reframe, verdicts.
    """
    info: dict[str, Any] = getattr(result, "info", {}) or {}

    metrics: list[Metric] = [
        _margin_metric(
            info,
            "grossMargins",
            "Gross Margin",
            "Revenue minus cost of goods sold, as a fraction of revenue.",
            "yfinance info.grossMargins",
        ),
        _margin_metric(
            info,
            "operatingMargins",
            "Operating Margin",
            "Operating income as a fraction of revenue; captures operating leverage.",
            "yfinance info.operatingMargins",
        ),
        _margin_metric(
            info,
            "profitMargins",
            "Net Margin",
            "Net income as a fraction of revenue; bottom-line profitability.",
            "yfinance info.profitMargins",
        ),
        _margin_metric(
            info,
            "returnOnEquity",
            "ROE",
            "Net income divided by shareholders' equity; return earned for equity holders.",
            "yfinance info.returnOnEquity",
        ),
        _compute_roic(info, result),
        _compute_fcf_margin(info),
    ]

    gross_series, op_series = _quarterly_margin_series(result)
    margin_dir = _margin_direction(gross_series)

    # Direction chip driven by the gross-margin slope over the shown window, so
    # it tracks the same line the trend chart plots (WIDENING / NARROWING / STEADY).
    chips = ""
    if margin_dir:
        label, tone = _MARGIN_CHIP[margin_dir]
        chips += render_status_chip(
            label,
            "",
            tone=tone,
            rule=(
                f"Gross margin {_MARGIN_WORD[margin_dir]} "
                f"{gross_series[0] * 100:.0f}% → {gross_series[-1] * 100:.0f}% "
                "across the shown window — measured from quarterly_financials "
                "Gross Profit / Total Revenue."
            ),
        )

    return {
        "metrics": metrics,
        "gross_series": gross_series,
        "op_series": op_series,
        "margin_dir": margin_dir,
        "chips": chips,
        "claim": "Margin levels and capital-return efficiency.",
        "reframe": (
            "Margins and ROE are trailing facts. "
            "ROIC computed from EBIT, debt, and equity when all inputs present. "
            "Gross margin shown vs peers with the peer median."
        ),
        "verdicts": [
            Verdict("pos", "Positive gross, operating, and net margins reported."),
            Verdict("neu", "Gross margin compared against peers — a descriptive fact."),
        ],
    }


def build_profitability_panel(result: Any) -> str:
    """Compose the full Profitability deep-dive panel HTML (panel #3)."""
    v = build_profitability_view(result)
    info: dict[str, Any] = getattr(result, "info", {}) or {}
    ticker = getattr(result, "ticker", "") or ""

    # Comparison viz: subject gross margin vs peers + peer median (real)
    gross_val = _f(info, "grossMargins")
    peers = getattr(result, "peer_data", []) or []
    peer_margins = [
        float(p["gross_margins"]) * 100
        for p in peers
        if p.get("gross_margins") is not None
    ]
    if gross_val is not None:
        margin_rows: list[tuple[str, float, bool]] = [
            (ticker or "Self", round(gross_val * 100, 1), True)
        ]
        margin_rows += [
            (p.get("ticker", "?"), round(float(p["gross_margins"]) * 100, 1), False)
            for p in peers
            if p.get("gross_margins") is not None
        ][:4]
        margin_bar = panel_charts.peer_bars(margin_rows, unit="%")
        if peer_margins:
            med = sorted(peer_margins)[len(peer_margins) // 2]
            margin_bar += (
                f'<div class="sa-pnl-cap">peer median gross margin {med:.0f}%</div>'
            )
        else:
            margin_bar += (
                '<div class="sa-pnl-cap">peer margins unavailable — self only</div>'
            )
    else:
        margin_bar = '<div class="sa-pnl-cap">gross margin data gap</div>'

    left = '<div class="sa-pnl-subh">Gross margin vs peers</div>' + margin_bar

    # Trend viz: quarterly gross + operating margin. Series are fractions
    # (0.74) — scale to percent so the axis reads 74%, matching the tiles.
    gross_pct = [g * 100 for g in v["gross_series"]]
    op_pct = [o * 100 for o in v["op_series"]]
    trend_viz = panel_charts.trend_lines(
        [
            ("Gross %", gross_pct, "#7c5cbf"),
            ("Op %", op_pct, "#5c8cbf"),
        ],
        unit="%",
    )
    if trend_viz:
        mdir = v["margin_dir"]
        cap = ""
        if mdir and gross_pct:
            cap = (
                '<div class="sa-pnl-cap">gross margin '
                f"{gross_pct[0]:.0f}% → {gross_pct[-1]:.0f}% — {_MARGIN_WORD[mdir]}</div>"
            )
        right = (
            '<div class="sa-pnl-subh">Quarterly margin trend</div>' + trend_viz + cap
        )
    else:
        right = ""

    return build_panel(
        number=3,
        name="Profitability",
        dot_colour="#7c5cbf",
        info_html=render_info(
            "Margin levels and capital-return efficiency; trailing facts.",
            "info.grossMargins / operatingMargins / profitMargins + ROIC computed",
        ),
        chips_html=v["chips"],
        claim=v["claim"],
        reframe=v["reframe"],
        strip_html=_strip_html(v["metrics"]),
        viz_left=left,
        viz_right=right,
        verdicts=v["verdicts"],
        drill="open full profitability — margin history · ROIC trend · FCF yield",
    )
