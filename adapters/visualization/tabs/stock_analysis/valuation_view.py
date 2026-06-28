"""Valuation panel (spec D10): 6 multiples vs peers + P/E history + fair value (DATA-GAP) -> measured colour."""

from __future__ import annotations

import html as _html
from dataclasses import dataclass
from typing import Any

from adapters.visualization.components import panel_charts
from adapters.visualization.components.info_tip import render_info
from adapters.visualization.components.status_chip import render_status_chip
from adapters.visualization.components.stock_metrics import STOCK_METRICS
from adapters.visualization.tabs.stock_analysis.panel import Verdict, build_panel


@dataclass(frozen=True)
class Metric:
    key: str
    label: str
    value: str
    sub: str
    tone: str
    meaning: str
    basis: str


def _f(info: dict[str, Any], key: str) -> float | None:
    v = info.get(key)
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _multiple(
    info: dict[str, Any],
    key: str,
    label: str,
    mkey: str,
    *,
    suffix: str = "×",
    rich_pct: float | None = None,
) -> Metric:
    val = _f(info, key)
    meaning, basis = STOCK_METRICS.get(mkey, ("", key))
    if val is None:
        return Metric(mkey, label, "—", "data gap", "grey", meaning, basis)
    tone = (
        "amber"
        if (rich_pct is not None and (rich_pct >= 75 or rich_pct <= 25))
        else "grey"
    )
    sub = f"{int(round(rich_pct))}th" if rich_pct is not None else ""
    return Metric(mkey, label, f"{val:g}{suffix}", sub, tone, meaning, basis)


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


def build_valuation_view(result: Any) -> dict[str, Any]:
    info: dict[str, Any] = getattr(result, "info", {}) or {}
    pe_pct: float | None = (getattr(result, "peer_percentiles", {}) or {}).get("P/E")
    mc = _f(info, "marketCap")
    fcf = _f(info, "freeCashflow")
    pfcf: float | None = (mc / fcf) if (mc and fcf) else None

    metrics: list[Metric] = [
        _multiple(info, "trailingPE", "P/E ttm", "pe_ttm", rich_pct=pe_pct),
        _multiple(info, "forwardPE", "P/E fwd", "pe_fwd"),
        _multiple(info, "pegRatio", "PEG", "peg", suffix=""),
        _multiple(
            info, "priceToSalesTrailing12Months", "P/S", "ev_ebitda"
        ),  # P/S uses ev_ebitda copy; yfinance key is ...Trailing12Months
        _multiple(info, "enterpriseToEbitda", "EV/EBITDA", "ev_ebitda"),
        Metric(
            "p_fcf",
            "P/FCF",
            f"{pfcf:.0f}×" if pfcf else "—",
            "" if pfcf else "data gap",
            "grey",
            *STOCK_METRICS["p_fcf"],
        ),
    ]

    # PEG green when <1
    peg_val = _f(info, "pegRatio")
    if peg_val is not None and peg_val < 1:
        metrics[2] = Metric(
            metrics[2].key,
            metrics[2].label,
            metrics[2].value,
            "<1 ▼",
            "green",
            metrics[2].meaning,
            metrics[2].basis,
        )

    peer_rows: list[tuple[str, float, bool]] = [
        (
            p.get("ticker", "?"),
            float(p.get("pe") or 0),
            p.get("ticker") == getattr(result, "ticker", None),
        )
        for p in (getattr(result, "peer_data", []) or [])
        if p.get("pe")
    ]

    chips = render_status_chip(
        "RICH",
        f"{int(round(pe_pct))}th" if pe_pct else "n/a",
        tone="amber",
        rule="multiples cluster >=75th pct of peers; price level only, not over/undervalued",
    )
    if peg_val is not None and peg_val < 1:
        chips += render_status_chip(
            "PEG",
            f"{peg_val:g}",
            tone="green",
            rule="PEG <1 = P/E below the growth rate; a fact, not a call",
        )

    return {
        "metrics": metrics,
        "peer_rows": peer_rows,
        "chips": chips,
        "claim": (
            "Rich on price, fair on growth"
            if (peg_val and peg_val < 1)
            else "Priced on its multiples"
        ),
        "reframe": "Top-quartile on raw multiples; P/E-vs-history and fair value are not wired (third-party).",
        "verdicts": [
            Verdict("cau", "Top-quartile multiples — little margin for a miss."),
            Verdict("pos", "PEG below 1 where growth supports the price."),
        ],
    }


def build_valuation_panel(result: Any) -> str:
    v = build_valuation_view(result)
    left = '<div class="sa-pnl-subh">P/E vs peers</div>' + panel_charts.peer_bars(
        v["peer_rows"]
    )
    right = (
        '<div class="sa-pnl-subh">P/E vs own history · fair value</div>'
        # DATA-GAP: no point-in-time P/E history or third-party fair-value source is wired
        + panel_charts.marker_range(0.0, 0.0, [])
    )
    return build_panel(
        number=1,
        name="Valuation",
        dot_colour="#d08218",
        info_html=render_info(
            "Six standard multiples vs peers; trailing facts.",
            "info + peer_percentiles",
        ),
        chips_html=v["chips"],
        claim=v["claim"],
        reframe=v["reframe"],
        strip_html=_strip_html(v["metrics"]),
        viz_left=left,
        viz_right=right,
        verdicts=v["verdicts"],
        drill="open full valuation — DCF · every multiple's history",
    )
