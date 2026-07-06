"""Valuation panel (spec D10): 6 multiples vs peers + P/E-vs-1yr-range + analyst-target fair value -> measured colour."""

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
    return Metric(
        mkey, label, f"{panel_charts.fmt_num(val)}{suffix}", sub, tone, meaning, basis
    )


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
        _multiple(info, "priceToSalesTrailing12Months", "P/S", "ps"),
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

    # Put the subject ticker first (highlighted), then its peers — so the P/E-vs-peers
    # bars actually show where THIS stock sits, not just the peer set.
    subject = getattr(result, "ticker", "?")
    own_pe = _f(info, "trailingPE")
    peer_rows: list[tuple[str, float, bool]] = []
    if own_pe:
        peer_rows.append((subject, float(own_pe), True))
    peer_rows += [
        (p.get("ticker", "?"), float(p.get("pe") or 0), False)
        for p in (getattr(result, "peer_data", []) or [])
        if p.get("pe") and p.get("ticker") != subject
    ]

    # Percentile-aware label — never call a bottom-quartile stock "RICH".
    chips = ""
    if pe_pct is not None:
        p = int(round(float(pe_pct)))
        if pe_pct >= 75:
            chips += render_status_chip(
                "RICH",
                f"{p}th",
                tone="amber",
                rule="multiples in the top quartile vs peers; price level only, not over/undervalued",
            )
        elif pe_pct <= 25:
            chips += render_status_chip(
                "LOW MULT",
                f"{p}th",
                tone="grey",
                rule="multiples in the bottom quartile vs peers; price level only, descriptive",
            )
        else:
            chips += render_status_chip(
                "MID MULT",
                f"{p}th",
                tone="grey",
                rule="mid-range multiples vs peers; price level only, descriptive",
            )
    if peg_val is not None and peg_val < 1:
        chips += render_status_chip(
            "PEG",
            panel_charts.fmt_num(peg_val),
            tone="green",
            rule="PEG <1 = P/E below the growth rate; a fact, not a call",
        )

    if pe_pct is not None and pe_pct >= 75:
        claim = (
            "Rich on price, fair on growth"
            if (peg_val and peg_val < 1)
            else "Top-quartile multiples"
        )
    elif pe_pct is not None and pe_pct <= 25:
        claim = "Lower multiples than peers"
    else:
        claim = "Mid-range on its multiples"

    is_rich = pe_pct is not None and pe_pct >= 75
    verdicts: list[Verdict] = []
    if is_rich:
        verdicts.append(
            Verdict("cau", "Top-quartile multiples — little margin for a miss.")
        )
    else:
        verdicts.append(
            Verdict(
                "neu", "Multiples mid/low vs peers — a price-level fact, not a call."
            )
        )
    if peg_val is not None and peg_val < 1:
        verdicts.append(Verdict("pos", "PEG below 1 — P/E below the growth rate."))

    return {
        "metrics": metrics,
        "peer_rows": peer_rows,
        "chips": chips,
        "claim": claim,
        "reframe": "Shown vs its 1-yr P/E range and the analyst-target range; multiples are a price-level fact, not over/undervalued.",
        "verdicts": verdicts,
    }


def _valuation_ranges_html(result: Any) -> str:
    """Right-column visuals: P/E vs its 1-yr range + analyst-target fair-value range.

    Both are built from data already on the result (52-wk prices + trailing P/E;
    analyst target low/mean/high) — no new fetch. Honest labels: a 1-yr price-implied
    P/E range (not a multi-year history) and analyst targets (a 3rd-party range, not DCF).
    """
    info: dict[str, Any] = getattr(result, "info", {}) or {}
    price = getattr(result, "current_price", None) or _f(info, "currentPrice")
    pe_now = _f(info, "trailingPE")
    lo52 = _f(info, "fiftyTwoWeekLow")
    hi52 = _f(info, "fiftyTwoWeekHigh")
    parts: list[str] = []

    # P/E vs 1-yr range: the 52-wk price range valued at the current trailing EPS.
    if pe_now and price and lo52 and hi52 and hi52 > lo52:
        pe_lo = lo52 / price * pe_now
        pe_hi = hi52 / price * pe_now
        parts.append('<div class="sa-pnl-subh">P/E vs 1-yr range</div>')
        parts.append(
            panel_charts.marker_range(
                pe_lo,
                pe_hi,
                [(pe_now, f"now {panel_charts.fmt_num(pe_now)}×", "#0F6E80")],
            )
        )

    # Fair value · analyst target range (third-party): low/mean/high vs current price.
    panel = getattr(result, "analyst_panel", None)
    t_lo = getattr(panel, "target_low", None) if panel is not None else None
    t_mean = getattr(panel, "target_mean", None) if panel is not None else None
    t_hi = getattr(panel, "target_high", None) if panel is not None else None
    if t_lo and t_hi and t_hi > t_lo:
        markers: list[tuple[float, str, str]] = []
        if price:
            markers.append(
                (float(price), f"now ${panel_charts.fmt_num(price)}", "#0F6E80")
            )
        if t_mean:
            markers.append(
                (float(t_mean), f"base ${panel_charts.fmt_num(t_mean)}", "#1a2226")
            )
        parts.append(
            '<div class="sa-pnl-subh" style="margin-top:12px">'
            "Fair value · analyst target (3rd-party)</div>"
        )
        parts.append(
            panel_charts.marker_range(
                float(t_lo),
                float(t_hi),
                markers,
                left_label=f"bear ${panel_charts.fmt_num(t_lo)}",
                right_label=f"bull ${panel_charts.fmt_num(t_hi)}",
                gradient=True,
            )
        )

    if not parts:
        return (
            '<div class="sa-pnl-subh">P/E vs history · fair value</div>'
            + panel_charts.marker_range(0.0, 0.0, [])
        )
    return "".join(parts)


def build_valuation_panel(result: Any) -> str:
    v = build_valuation_view(result)
    left = '<div class="sa-pnl-subh">P/E vs peers</div>' + panel_charts.peer_bars(
        v["peer_rows"]
    )
    right = _valuation_ranges_html(result)
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
