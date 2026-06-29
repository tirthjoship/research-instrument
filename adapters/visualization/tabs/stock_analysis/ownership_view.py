"""Ownership panel (spec D11): holder composition + insider flow + short data.

Insider-cluster signal is FALSIFIED (ADR-053): hypothesis tests found no
systematic edge from insider-cluster ownership changes.  All metrics here are
descriptive, never directional.
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
# Internal helpers
# ---------------------------------------------------------------------------

_STRIP_TILE = (
    '<div class="sa-tile t-{tone}"><div class="lab">{label} {info}</div>'
    '<div class="num">{value}</div><div class="sub">{sub}</div></div>'
)


def _f(info: dict[str, Any], key: str) -> float | None:
    """Defensive float parse — returns None on any missing/unconvertible value."""
    v = info.get(key)
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _insider_quarterly_net(txns: list[dict[str, Any]]) -> list[tuple[str, float]]:
    """Net signed insider transaction value per quarter (last 8), chronological."""
    from collections import defaultdict
    from datetime import datetime

    buckets: dict[tuple[int, int], float] = defaultdict(float)
    for t in txns:
        d = t.get("Start Date") or t.get("Date") or t.get("startDate")
        if d is None:
            continue
        try:
            if hasattr(d, "year"):
                y, m = int(d.year), int(d.month)
            else:
                dt = datetime.fromisoformat(str(d)[:10])
                y, m = dt.year, dt.month
            buckets[(y, (m - 1) // 3 + 1)] += float(t.get("value", 0) or 0)
        except Exception:
            continue
    items = sorted(buckets.items())[-8:]
    return [(f"Q{q} {y}", v) for (y, q), v in items]


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


def _fmt_net_q(net_q: float) -> str:
    """Format insider net quarterly transaction value as abbreviated dollar amount."""
    abs_val = abs(net_q)
    sign = "-" if net_q < 0 else "+"
    if abs_val >= 1_000_000_000:
        return f"{sign}${abs_val / 1_000_000_000:.1f}B"
    if abs_val >= 1_000_000:
        return f"{sign}${abs_val / 1_000_000:.0f}M"
    if abs_val >= 1_000:
        return f"{sign}${abs_val / 1_000:.0f}K"
    return f"{sign}${abs_val:.0f}"


def _short_interest_metric(info: dict[str, Any]) -> Metric:
    """Short interest as % of float. Prefer shortPercentOfFloat; else compute
    sharesShort / floatShares (or sharesOutstanding). yfinance often drops the
    headline ratio while keeping the primitives, so this keeps the tile live."""
    meaning = (
        "Short interest as a percentage of float — shares short divided by shares "
        "available to trade. High short interest raises borrowing costs; descriptive."
    )
    pct = _f(info, "shortPercentOfFloat")
    basis = "yfinance info.shortPercentOfFloat; percentage of float; descriptive"
    if pct is None:
        shares_short = _f(info, "sharesShort")
        base = _f(info, "floatShares") or _f(info, "sharesOutstanding")
        if shares_short is not None and base:
            pct = shares_short / base
            basis = "sharesShort / floatShares (computed; shortPercentOfFloat absent)"
    if pct is None:
        return Metric(
            "short_interest", "Short interest", "—", "data gap", "grey", meaning, basis
        )
    si = pct * 100
    # measured risk bands: amber when elevated (>5% of float), grey otherwise
    tone = "amber" if si > 5 else "grey"
    return Metric(
        "short_interest",
        "Short interest",
        f"{si:.1f}%",
        "of float",
        tone,
        meaning,
        basis + "; amber >5% of float (elevated borrow/squeeze risk)",
    )


def _days_to_cover_metric(info: dict[str, Any]) -> Metric:
    """Days-to-cover. Prefer shortRatio; else sharesShort / average daily volume."""
    meaning = (
        "Days-to-cover (short ratio): short interest divided by average daily volume — "
        "how many trading days it would take to close all short positions."
    )
    dtc = _f(info, "shortRatio")
    basis = "yfinance info.shortRatio; days to close short at average volume"
    if dtc is None:
        shares_short = _f(info, "sharesShort")
        vol = _f(info, "averageDailyVolume10Day") or _f(info, "averageVolume")
        if shares_short is not None and vol:
            dtc = shares_short / vol
            basis = "sharesShort / 10-day average volume (computed; shortRatio absent)"
    if dtc is None:
        return Metric(
            "days_to_cover", "Days-to-cover", "—", "data gap", "grey", meaning, basis
        )
    # amber when a crowded short would take many days to unwind (>5)
    tone = "amber" if dtc > 5 else "grey"
    return Metric(
        "days_to_cover",
        "Days-to-cover",
        f"{dtc:.1f}d",
        "to close short",
        tone,
        meaning,
        basis + "; amber >5 days (crowded short)",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_ownership_view(result: Any) -> dict[str, Any]:
    """Build the ownership view-model.

    Returns a dict with keys: metrics, chips, claim, reframe, verdicts.
    Six metrics: Institutional %, Insiders %, Public float, Insider net Q,
    Short interest, Days-to-cover.
    """
    info: dict[str, Any] = getattr(result, "info", {}) or {}
    txns: list[dict[str, Any]] = getattr(result, "insider_transactions", []) or []

    inst_raw = _f(info, "heldPercentInstitutions")
    insider_raw = _f(info, "heldPercentInsiders")

    # 1. Institutional %
    inst_meaning = (
        "Percentage of shares held by institutional investors (funds, ETFs, pensions). "
        "High institutional ownership is common among large-cap equities."
    )
    inst_basis = (
        "yfinance info.heldPercentInstitutions × 100; descriptive, not directional"
    )
    inst_pct: float | None
    if inst_raw is None:
        inst_pct = None
        m_inst = Metric(
            "inst_pct",
            "Institutional %",
            "—",
            "data gap",
            "grey",
            inst_meaning,
            inst_basis,
        )
    else:
        inst_pct = inst_raw * 100
        # green = passes the "majority institutionally held" threshold (descriptive)
        m_inst = Metric(
            "inst_pct",
            "Institutional %",
            f"{inst_pct:.0f}%",
            "of shares outstanding",
            "green" if inst_pct >= 50 else "grey",
            inst_meaning,
            inst_basis + "; green ≥50% (majority institutionally held)",
        )

    # 2. Insiders %
    insider_meaning = (
        "Percentage of shares held by corporate insiders (directors, officers). "
        "A factual ownership level — no directional inference is drawn."
    )
    insider_basis = "yfinance info.heldPercentInsiders × 100; descriptive"
    insider_pct: float | None
    if insider_raw is None:
        insider_pct = None
        m_insider = Metric(
            "insider_pct",
            "Insiders %",
            "—",
            "data gap",
            "grey",
            insider_meaning,
            insider_basis,
        )
    else:
        insider_pct = insider_raw * 100
        m_insider = Metric(
            "insider_pct",
            "Insiders %",
            f"{insider_pct:.0f}%",
            "of shares outstanding",
            "grey",
            insider_meaning,
            insider_basis,
        )

    # 3. Public float (100 − inst − insider)
    float_meaning = (
        "Estimated public float: shares not held by institutions or insiders. "
        "Derived from ownership percentages, not direct float data."
    )
    float_basis = "100 − heldPercentInstitutions% − heldPercentInsiders%; approximate"
    if inst_pct is None or insider_pct is None:
        m_float = Metric(
            "public_float",
            "Public float",
            "—",
            "data gap",
            "grey",
            float_meaning,
            float_basis,
        )
    else:
        float_pct = max(0.0, 100.0 - inst_pct - insider_pct)
        # amber = thin float (<20%): a liquidity/volatility risk characteristic
        m_float = Metric(
            "public_float",
            "Public float",
            f"{float_pct:.0f}%",
            "approx. unaffiliated",
            "amber" if float_pct < 20 else "grey",
            float_meaning,
            float_basis + "; amber <20% (thin float can amplify volatility)",
        )

    # 4. Insider net Q (sum of transaction values — reducing/accumulating, never labelled as direction)
    net_q_meaning = (
        "Net transaction value of insider activity reported for the latest quarter. "
        "Negative = net reducing; positive = net accumulating. "
        "Insider-cluster signal is falsified (ADR-053) — descriptive only."
    )
    net_q_basis = (
        "sum of insider_transactions[*].value; quarterly net position change in dollars"
    )
    net_q: float | None = None
    if txns:
        try:
            net_q = float(sum(float(t.get("value", 0) or 0) for t in txns))
        except (TypeError, ValueError):
            net_q = None

    net_q_direction: str
    if net_q is None:
        net_q_direction = "no data"
        m_netq = Metric(
            "insider_net_q",
            "Insider net Q",
            "—",
            "data gap",
            "grey",
            net_q_meaning,
            net_q_basis,
        )
    else:
        net_q_str = _fmt_net_q(net_q)
        net_q_direction = "net reducing" if net_q < 0 else "net accumulating"
        m_netq = Metric(
            "insider_net_q",
            "Insider net Q",
            net_q_str,
            net_q_direction,
            "grey",
            net_q_meaning,
            net_q_basis,
        )

    # 5/6. Short interest + days-to-cover (computed from primitives when the
    # yfinance convenience ratios are absent — they often are).
    m_short = _short_interest_metric(info)
    m_dtc = _days_to_cover_metric(info)

    metrics: list[Metric] = [m_inst, m_insider, m_float, m_netq, m_short, m_dtc]

    # --- Chips ---
    inst_chip_val = f"{inst_pct:.0f}%" if inst_pct is not None else "n/a"
    chips = render_status_chip(
        "INSTITUTIONAL",
        inst_chip_val,
        tone="grey",
        rule="institutional ownership level — descriptive, not directional",
    )
    chips += render_status_chip(
        "INSIDERS",
        net_q_direction,
        tone="grey",
        rule=(
            "insider-cluster signal falsified (ADR-053); net transaction value is descriptive only — "
            "reducing = net outflow, accumulating = net inflow; no directional inference drawn"
        ),
    )

    return {
        "metrics": metrics,
        "chips": chips,
        "claim": "Holder composition and insider activity — descriptive ownership facts.",
        "reframe": (
            "Institutional ownership is a structural characteristic of large-cap equities, not a signal. "
            "Insider-cluster signal is falsified (ADR-053): hypothesis tests found no systematic edge. "
            "Short interest and days-to-cover are computed from shares-short and float/volume when "
            "the headline ratios are absent; data gap only when shares-short is unavailable."
        ),
        "verdicts": [
            Verdict(
                "neu",
                "Holder composition is a trailing structural fact — no directional inference.",
            ),
            Verdict(
                "cau",
                "Insider-cluster signal falsified (ADR-053): net transaction value is descriptive only.",
            ),
        ],
    }


def build_ownership_panel(result: Any) -> str:
    """Compose the full Ownership deep-dive panel HTML (panel #2)."""
    v = build_ownership_view(result)
    info: dict[str, Any] = getattr(result, "info", {}) or {}

    inst_raw = _f(info, "heldPercentInstitutions")
    insider_raw = _f(info, "heldPercentInsiders")

    # Comparison viz: holder composition as one segmented bar (Inst/Insiders/Public)
    if inst_raw is not None and insider_raw is not None:
        inst_pct = inst_raw * 100
        insider_pct = insider_raw * 100
        public_pct = max(0.0, 100.0 - inst_pct - insider_pct)
        left = (
            '<div class="sa-pnl-subh">Holder composition</div>'
            + panel_charts.stacked_bar(
                [
                    ("Institutions", inst_pct, "#0F6E80"),
                    ("Insiders", insider_pct, "#b45309"),
                    ("Public", public_pct, "#cdd7d9"),
                ]
            )
        )
    else:
        left = (
            '<div class="sa-pnl-subh">Holder composition</div>'
            '<div class="sa-pnl-cap">holder composition not available — data gap</div>'
        )

    # Trend viz: net insider transaction value per quarter (signed; grey = falsified, ADR-053)
    qn = _insider_quarterly_net(getattr(result, "insider_transactions", []) or [])
    if len(qn) >= 2:
        right = (
            '<div class="sa-pnl-subh">Insider net activity ($M/qtr)</div>'
            + panel_charts.trend_lines(
                [("Net", [v / 1e6 for _, v in qn], "#9aa6aa")],
                unit="M",
                x_labels=(qn[0][0], qn[-1][0]),
            )
            + '<div class="sa-pnl-cap">disclosed fact; insider-cluster signal falsified (ADR-053)</div>'
        )
    else:
        right = (
            '<div class="sa-pnl-subh">Insider net activity</div>'
            '<div class="sa-pnl-cap">no quarterly insider history — data gap; '
            "signal falsified (ADR-053)</div>"
        )

    return build_panel(
        number=2,
        name="Ownership",
        dot_colour="#6b7d84",
        info_html=render_info(
            "Holder composition and insider transaction flow; trailing facts.",
            "info.heldPercentInstitutions + heldPercentInsiders + insider_transactions",
        ),
        chips_html=v["chips"],
        claim=v["claim"],
        reframe=v["reframe"],
        strip_html=_strip_html(v["metrics"]),
        viz_left=left,
        viz_right=right,
        verdicts=v["verdicts"],
        drill="open full ownership — institutional 13F history · insider 6-quarter trend",
    )
