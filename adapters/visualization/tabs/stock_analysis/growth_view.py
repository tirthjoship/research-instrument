"""Growth panel (spec D10): rev/eps YoY rates + quarterly trend -> measured colour.

Growth = RATES only. Six metrics: Rev YoY and EPS YoY (from yfinance info),
plus Rev 3y CAGR (annual financials), FCF YoY (quarterly cashflow), Fwd rev
(third-party analyst estimate), and Peer rank (vs peer_data revenue growth) —
each falls back to an honest DATA-GAP tile only when its own source is
genuinely missing (e.g. <4y of annual revenue, no peer data), not always.
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


def _fcf_series(result: Any) -> list[float]:
    """Chronological quarterly free-cash-flow series from result.quarterly_cashflow.

    Prefers the 'Free Cash Flow' row; falls back to Operating CF − CapEx. Drops NaNs.
    Empty list on any failure (caller treats as DATA-GAP).
    """
    try:
        qcf = result.quarterly_cashflow
        if qcf is None:
            return []

        def _row(name: str) -> list[float] | None:
            if name in qcf.index:
                return [float(v) for v in qcf.loc[name].values]
            return None

        fcf = _row("Free Cash Flow")
        if fcf is None:
            ocf = _row("Operating Cash Flow")
            capex = _row("Capital Expenditure")
            if ocf is not None and capex is not None and len(ocf) == len(capex):
                fcf = [o + c for o, c in zip(ocf, capex)]  # capex is negative
        if fcf is None:
            return []
        # yfinance columns are newest-first → reverse to chronological; drop NaN
        return list(reversed([v for v in fcf if v == v]))
    except Exception:
        return []


def _fcf_yoy(result: Any) -> float | None:
    """YoY free-cash-flow growth (latest quarter vs the same quarter a year ago)."""
    s = _fcf_series(result)
    if len(s) >= 5 and s[-5] != 0:
        return (s[-1] - s[-5]) / abs(s[-5])
    return None


def _peer_growth_rank(result: Any) -> float | None:
    """Percentile of the subject's revenue growth vs its peers' (0-100)."""
    info: dict[str, Any] = getattr(result, "info", {}) or {}
    own = info.get("revenueGrowth")
    if own is None:
        return None
    subject = getattr(result, "ticker", None)
    peers = [
        float(p["revenue_growth"])
        for p in (getattr(result, "peer_data", []) or [])
        if p.get("revenue_growth") is not None and p.get("ticker") != subject
    ]
    if not peers:
        return None
    beaten = sum(1 for g in peers if float(own) > g)
    return beaten / len(peers) * 100


def _yoy_trajectory(rev_series: list[float]) -> list[float]:
    """YoY revenue-growth % per quarter (needs >=5 quarters); chronological."""
    if len(rev_series) < 5:
        return []
    return [
        (rev_series[i] - rev_series[i - 4]) / abs(rev_series[i - 4]) * 100
        for i in range(4, len(rev_series))
        if rev_series[i - 4]
    ]


def _annual_yoy(result: Any) -> list[float]:
    """Year-over-year revenue growth % from the annual-revenue series (chronological)."""
    ann = [float(v) for v in (getattr(result, "annual_revenue", []) or []) if v == v]
    return [
        (ann[i] - ann[i - 1]) / abs(ann[i - 1]) * 100
        for i in range(1, len(ann))
        if ann[i - 1]
    ]


def _traj_direction(traj: list[float]) -> str:
    """Direction of the YoY-rate trajectory over the shown window.

    'up' (accelerating), 'down' (decelerating), 'flat' (roughly steady), or ''
    when fewer than 2 points. Net change first->last in percentage points;
    a +/-3pp band counts as flat so noise doesn't flip the colour.
    """
    if len(traj) < 2:
        return ""
    delta = traj[-1] - traj[0]
    if delta > 3.0:
        return "up"
    if delta < -3.0:
        return "down"
    return "flat"


# Trajectory direction -> (line colour, chip label, chip tone). Colour is
# descriptive of the slope, never a forecast: green rising, amber easing
# (still positive but slowing), grey roughly flat — matches the colour key.
_TRAJ_COLOUR = {"up": "#2f9e44", "down": "#b45309", "flat": "#9aa6aa"}
_TRAJ_CHIP = {
    "up": ("ACCELERATING", "green"),
    "down": ("DECELERATING", "amber"),
    "flat": ("STEADY", "grey"),
}
_TRAJ_WORD = {"up": "accelerating", "down": "decelerating", "flat": "roughly steady"}


def _fcf_yoy_metric(result: Any) -> Metric:
    meaning = "Year-over-year free cash flow growth (latest quarter vs a year ago)."
    y = _fcf_yoy(result)
    if y is None:
        return _data_gap(
            "fcf_yoy", "FCF YoY", meaning, "needs >=5 quarters of cashflow"
        )
    return Metric(
        "fcf_yoy",
        "FCF YoY",
        _pct(y),
        "yoy",
        "green" if y > 0 else "grey",
        meaning,
        "quarterly_cashflow · Free Cash Flow",
    )


def _rev_3y_cagr_metric(result: Any) -> Metric:
    meaning = "Three-year compounded annual growth rate of revenue (annual financials)."
    rev = list(getattr(result, "annual_revenue", []) or [])
    if len(rev) >= 4 and rev[-4] > 0:
        cagr = (rev[-1] / rev[-4]) ** (1 / 3) - 1
        return Metric(
            "rev_3y_cagr",
            "Rev 3y CAGR",
            _pct(cagr),
            "3y annualized",
            "green" if cagr > 0 else "grey",
            meaning,
            "income_stmt Total Revenue (3y)",
        )
    return _data_gap(
        "rev_3y_cagr", "Rev 3y CAGR", meaning, "needs 4y of annual revenue"
    )


def _fwd_rev_metric(result: Any) -> Metric:
    meaning = "Forward revenue growth from analyst consensus; a third-party figure, not our estimate."
    g = getattr(result, "forward_revenue_growth", None)
    if g is not None:
        return Metric(
            "fwd_rev",
            "Fwd rev (3rd-party)",
            _pct(float(g)),
            "3rd-pty",
            "green" if float(g) > 0 else "grey",
            meaning,
            "revenue_estimate +1y growth",
        )
    return _data_gap(
        "fwd_rev", "Fwd rev (3rd-party)", meaning, "analyst estimate unavailable"
    )


def _peer_rank_metric(result: Any) -> Metric:
    meaning = "Revenue-growth percentile versus the peer group."
    r = _peer_growth_rank(result)
    if r is None:
        return _data_gap(
            "peer_rank", "Peer rank", meaning, "needs peer growth — not wired"
        )
    return Metric(
        "peer_rank",
        "Peer rank",
        f"{int(round(r))}th",
        "vs peers",
        "green" if r >= 50 else "grey",
        meaning,
        "rank of info.revenueGrowth vs peer revenue_growth",
    )


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
        _rev_3y_cagr_metric(result),
        _fcf_yoy_metric(result),
        _fwd_rev_metric(result),
        _peer_rank_metric(result),
    ]

    rev_series, ni_series = _quarterly_series(result)

    # prefer annual YoY (yfinance gives ~4 annual points -> 3-pt trajectory);
    # fall back to quarterly YoY when annual statements are unavailable
    traj = _annual_yoy(result) or _yoy_trajectory(rev_series)
    traj_dir = _traj_direction(traj)

    # Direction chip is driven by the SAME YoY-rate series the trajectory chart
    # plots, so the badge can never contradict the line the user sees.
    chips = ""
    if traj_dir:
        label, tone = _TRAJ_CHIP[traj_dir]
        chips += render_status_chip(
            label,
            "",
            tone=tone,
            rule=(
                f"YoY revenue-growth rate {_TRAJ_WORD[traj_dir]}: "
                f"{traj[0]:+.0f}% → {traj[-1]:+.0f}% across the shown window "
                "(annual statements, else quarterly_financials)."
            ),
        )

    verdicts = _trajectory_verdicts(traj, traj_dir)

    return {
        "metrics": metrics,
        "rev_series": rev_series,
        "ni_series": ni_series,
        "yoy_traj": traj,
        "traj_dir": traj_dir,
        "chips": chips,
        "claim": "Revenue and earnings expanding year-on-year.",
        "reframe": (
            "Rates from trailing financials; 3y CAGR from annual statements; "
            "the forward estimate is third-party (shown when available)."
        ),
        "verdicts": verdicts,
    }


def _trajectory_verdicts(traj: list[float], traj_dir: str) -> list[Verdict]:
    """Direction-aware footer verdicts: state the slope honestly, count the
    positive periods, and keep the forward-estimate disclosure."""
    out: list[Verdict] = []
    if traj_dir == "up":
        out.append(
            Verdict(
                "pos", f"YoY growth rate rising: {traj[0]:+.0f}% → {traj[-1]:+.0f}%."
            )
        )
    elif traj_dir == "down":
        tail = ", still positive" if traj[-1] > 0 else ""
        out.append(
            Verdict(
                "cau",
                f"YoY growth rate easing: {traj[0]:+.0f}% → {traj[-1]:+.0f}%{tail}.",
            )
        )
    elif traj_dir == "flat":
        out.append(
            Verdict("neu", f"YoY growth rate roughly steady near {traj[-1]:+.0f}%.")
        )
    else:
        out.append(Verdict("pos", "Positive YoY revenue growth reported."))
    if traj:
        npos = sum(1 for v in traj if v > 0)
        out.append(
            Verdict(
                "neu", f"YoY growth positive in {npos} of {len(traj)} periods shown."
            )
        )
    out.append(Verdict("neu", "Forward estimate is a third-party figure, not adopted."))
    return out


def build_growth_panel(result: Any) -> str:
    """Compose the full Growth deep-dive panel HTML (panel #2)."""
    v = build_growth_view(result)
    rev_b = [r / 1e9 for r in v["rev_series"]]
    ni_b = [n / 1e9 for n in v["ni_series"]]
    nq = len(rev_b)
    combo = panel_charts.bars_and_line(
        rev_b, ni_b, unit="B", x_labels=(f"{nq}q ago", "latest") if nq >= 2 else None
    )
    if combo:
        rev_txt = (
            f"${panel_charts.fmt_num(rev_b[0])}B → ${panel_charts.fmt_num(rev_b[-1])}B"
            if rev_b
            else ""
        )
        left = (
            '<div class="sa-pnl-subh">Revenue &amp; net income ($B, by quarter)</div>'
            + combo
            + f'<div class="sa-pnl-cap">bars = revenue ({rev_txt}) · line = net income</div>'
        )
    else:
        left = (
            '<div class="sa-pnl-subh">Revenue &amp; net income</div>'
            '<div class="sa-pnl-cap">quarterly financials unavailable — data gap</div>'
        )
    # Second graph: YoY revenue-growth trajectory (annual YoY preferred).
    # Line colour tracks the slope (green rising / amber easing / grey flat) so a
    # decelerating-but-positive series isn't painted as if it were climbing.
    traj = v["yoy_traj"]
    traj_dir = v["traj_dir"]
    if len(traj) >= 2:
        colour = _TRAJ_COLOUR.get(traj_dir, "#9aa6aa")
        word = _TRAJ_WORD.get(traj_dir, "")
        tail = ", still positive" if traj_dir == "down" and traj[-1] > 0 else ""
        descr = f" — {word}{tail}" if word else ""
        right = (
            '<div class="sa-pnl-subh">YoY growth trajectory (%)</div>'
            + panel_charts.trend_lines(
                [("YoY %", traj, colour)],
                unit="%",
                x_labels=("earliest", "latest"),
            )
            + f'<div class="sa-pnl-cap">year-over-year revenue growth: '
            f"{traj[0]:+.0f}% → {traj[-1]:+.0f}%{descr} (most recent at right)</div>"
        )
    else:
        right = (
            '<div class="sa-pnl-subh">YoY growth trajectory</div>'
            '<div class="sa-pnl-cap">needs multiple years/quarters of revenue — data gap</div>'
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
        viz_right=right,
        verdicts=v["verdicts"],
        drill="",
    )
