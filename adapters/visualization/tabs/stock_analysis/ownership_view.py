"""Ownership panel (spec D11): holder composition + insider flow + short data.

Insider-cluster signal is FALSIFIED (ADR-057): the Lazy Prices hypothesis run
showed no systematic edge from institutional ownership changes.  All metrics
here are descriptive, never directional.
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
        m_inst = Metric(
            "inst_pct",
            "Institutional %",
            f"{inst_pct:.0f}%",
            "of shares outstanding",
            "grey",
            inst_meaning,
            inst_basis,
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
        m_float = Metric(
            "public_float",
            "Public float",
            f"{float_pct:.0f}%",
            "approx. unaffiliated",
            "grey",
            float_meaning,
            float_basis,
        )

    # 4. Insider net Q (sum of transaction values — reducing/accumulating, never labelled as direction)
    net_q_meaning = (
        "Net transaction value of insider activity reported for the latest quarter. "
        "Negative = net reducing; positive = net accumulating. "
        "Insider-cluster signal is falsified (ADR-057) — descriptive only."
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

    # 5. Short interest (% of float)
    short_meaning = (
        "Short interest as a percentage of float — shares short divided by shares available "
        "to trade. High short interest raises borrowing costs; descriptive, not directional."
    )
    short_basis = "yfinance info.shortPercentOfFloat; percentage of float; descriptive"
    short_raw = _f(info, "shortPercentOfFloat")
    if short_raw is None:
        m_short = Metric(
            "short_interest",
            "Short interest",
            "—",
            "data gap",
            "grey",
            short_meaning,
            short_basis,
        )
    else:
        m_short = Metric(
            "short_interest",
            "Short interest",
            f"{short_raw * 100:.1f}%",
            "of float",
            "grey",
            short_meaning,
            short_basis,
        )

    # 6. Days-to-cover (short ratio)
    dtc_meaning = (
        "Days-to-cover (short ratio): current short interest divided by average daily volume. "
        "Indicates how many trading days it would take to close all short positions."
    )
    dtc_basis = (
        "yfinance info.shortRatio; days to close short at average volume; descriptive"
    )
    dtc_raw = _f(info, "shortRatio")
    if dtc_raw is None:
        m_dtc = Metric(
            "days_to_cover",
            "Days-to-cover",
            "—",
            "data gap",
            "grey",
            dtc_meaning,
            dtc_basis,
        )
    else:
        m_dtc = Metric(
            "days_to_cover",
            "Days-to-cover",
            f"{dtc_raw:.1f}d",
            "to close short",
            "grey",
            dtc_meaning,
            dtc_basis,
        )

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
            "insider-cluster signal falsified (ADR-057); net transaction value is descriptive only — "
            "reducing = net outflow, accumulating = net inflow; no directional inference drawn"
        ),
    )

    return {
        "metrics": metrics,
        "chips": chips,
        "claim": "Holder composition and insider activity — descriptive ownership facts.",
        "reframe": (
            "Institutional ownership is a structural characteristic of large-cap equities, not a signal. "
            "Insider-cluster signal is falsified (ADR-057): hypothesis tests found no systematic edge. "
            "Short data is absent for many tickers — shown as data gap."
        ),
        "verdicts": [
            Verdict(
                "neu",
                "Holder composition is a trailing structural fact — no directional inference.",
            ),
            Verdict(
                "cau",
                "Insider-cluster signal falsified (ADR-057): net transaction value is descriptive only.",
            ),
        ],
    }


def build_ownership_panel(result: Any) -> str:
    """Compose the full Ownership deep-dive panel HTML (panel #2)."""
    v = build_ownership_view(result)
    info: dict[str, Any] = getattr(result, "info", {}) or {}

    inst_raw = _f(info, "heldPercentInstitutions")
    insider_raw = _f(info, "heldPercentInsiders")

    # Comparison viz: holder composition bars (Institutions, Insiders, Public)
    holder_rows: list[tuple[str, float, bool]]
    if inst_raw is not None and insider_raw is not None:
        inst_pct = inst_raw * 100
        insider_pct = insider_raw * 100
        public_pct = max(0.0, 100.0 - inst_pct - insider_pct)
        holder_rows = [
            ("Institutions", inst_pct, True),
            ("Insiders", insider_pct, False),
            ("Public", public_pct, False),
        ]
        left = (
            '<div class="sa-pnl-subh">Holder composition</div>'
            + panel_charts.peer_bars(holder_rows, unit="%", width=150)
        )
    else:
        left = (
            '<div class="sa-pnl-subh">Holder composition</div>'
            '<div class="sa-pnl-cap">holder composition not available — data gap</div>'
        )

    # Trend viz: insider net activity — DATA-GAP (signal falsified per ADR-057)
    right = (
        '<div class="sa-pnl-subh">Insider net activity</div>'
        '<div class="sa-pnl-cap">insider quarterly trend not wired — data gap; '
        "signal falsified (ADR-057)</div>"
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
