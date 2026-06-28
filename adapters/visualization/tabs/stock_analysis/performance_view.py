"""Performance panel (spec D11): price/return behaviour — 1Y, vs S&P, beta, vs 200-day.

Margins and ROE live in the Profitability panel (Phase 3); they must NOT appear here.
3Y return and max-drawdown have no point-in-time source wired — both are DATA-GAP.
Returns-by-horizon and relative-strength series are also DATA-GAP (no price series).
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


def _closes(result: Any) -> list[float]:
    ph = getattr(result, "price_history", None) or {}
    cl = ph.get("closes") if isinstance(ph, dict) else None
    return [float(c) for c in cl] if cl else []


def _spy_closes(result: Any) -> list[float]:
    ph = getattr(result, "price_history", None) or {}
    cl = ph.get("spy_closes") if isinstance(ph, dict) else None
    return [float(c) for c in cl] if cl else []


_HORIZONS = [("3M", 63), ("6M", 126), ("1Y", 252), ("2Y", 504), ("3Y", 756)]


def _horizon_returns(closes: list[float]) -> list[tuple[str, float]]:
    """(label, return %) for each trailing horizon the series can cover."""
    out: list[tuple[str, float]] = []
    if not closes:
        return out
    cur = closes[-1]
    for label, days in _HORIZONS:
        if len(closes) > days and closes[-(days + 1)]:
            base = closes[-(days + 1)]
            out.append((label, (cur - base) / base * 100))
    return out


def _max_drawdown(closes: list[float]) -> float | None:
    """Largest peak-to-trough decline (%, negative) over the series."""
    if len(closes) < 2:
        return None
    peak = closes[0]
    mdd = 0.0
    for c in closes:
        peak = max(peak, c)
        if peak:
            mdd = min(mdd, (c - peak) / peak * 100)
    return mdd


def _relative_strength(closes: list[float], spy: list[float]) -> list[float]:
    """Cumulative relative-strength vs SPY over the aligned tail (100 = in line)."""
    n = min(len(closes), len(spy))
    if n < 30:
        return []
    a, b = closes[-n:], spy[-n:]
    if not a[0] or not b[0]:
        return []
    return [((a[i] / a[0]) / (b[i] / b[0])) * 100 for i in range(n)]


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


def build_performance_view(result: Any) -> dict[str, Any]:
    """Build the performance view-model.

    Returns a dict with keys: metrics, chips, claim, reframe, verdicts.
    Six metrics: 1Y return, 1Y vs S&P, 3Y (DATA-GAP), Beta, Max drawdown (DATA-GAP),
    vs 200-day MA.
    """
    info: dict[str, Any] = getattr(result, "info", {}) or {}
    current_price: float | None = getattr(result, "current_price", None)
    try:
        current_price = float(current_price) if current_price is not None else None
    except (TypeError, ValueError):
        current_price = None

    ret_1y = _f(info, "52WeekChange")
    spy_1y = _f(info, "SandP52WeekChange")
    beta = _f(info, "beta")
    ma200 = _f(info, "twoHundredDayAverage")
    closes = _closes(result)

    metrics: list[Metric] = []

    # 1. 1Y return (decimal to percentage, signed)
    ret_meaning = "Stock price change over the trailing 52 weeks, as a percentage."
    ret_basis = "yfinance info.52WeekChange (decimal); displayed as signed percentage"
    if ret_1y is None:
        metrics.append(
            Metric(
                "ret_1y", "1Y return", "—", "data gap", "grey", ret_meaning, ret_basis
            )
        )
    else:
        pct = ret_1y * 100
        sign = "+" if pct >= 0 else ""
        tone = "green" if pct > 0 else "grey"
        metrics.append(
            Metric(
                "ret_1y",
                "1Y return",
                f"{sign}{pct:.0f}%",
                "52-week price change",
                tone,
                ret_meaning,
                ret_basis,
            )
        )

    # 2. 1Y vs S&P (excess = stock 1Y − S&P 1Y, in percentage points)
    excess_meaning = (
        "Difference between the stock's 1-year return and the S&P 500's 1-year return, "
        "in percentage points. A positive number means the stock moved more than the index."
    )
    excess_basis = "1Y return minus S&P 1Y return"
    if ret_1y is None or spy_1y is None:
        metrics.append(
            Metric(
                "ret_vs_spy",
                "1Y vs S&P",
                "—",
                "data gap",
                "grey",
                excess_meaning,
                excess_basis,
            )
        )
        excess: float | None = None
    else:
        excess = (ret_1y - spy_1y) * 100  # in percentage points
        sign = "+" if excess >= 0 else ""
        tone = "green" if excess > 0 else "grey"
        metrics.append(
            Metric(
                "ret_vs_spy",
                "1Y vs S&P",
                f"{sign}{excess:.0f} pts",
                "stock minus index",
                tone,
                excess_meaning,
                excess_basis,
            )
        )

    # 3. Long-horizon return — the longest trailing window the price series covers
    #    (3Y when available, else 2Y/1Y); honest dynamic label, never faked.
    hz = _horizon_returns(closes)
    if hz:
        lbl, r = hz[-1]
        sign = "+" if r >= 0 else ""
        metrics.append(
            Metric(
                "ret_long",
                f"{lbl} return",
                f"{sign}{r:.0f}%",
                "from price history",
                "green" if r > 0 else "grey",
                f"Trailing {lbl} price change, from the daily close series.",
                "price_history.closes",
            )
        )
    else:
        metrics.append(
            Metric(
                "ret_3y",
                "3Y return",
                "—",
                "data gap",
                "grey",
                "Multi-year price change; requires a price series.",
                "data gap — price history unavailable",
            )
        )

    # 4. Beta (market sensitivity)
    beta_meaning = (
        "Sensitivity of the stock's returns relative to the market (S&P 500). "
        "Above 1 = amplified moves; below 1 = dampened moves."
    )
    beta_basis = "yfinance info.beta; beta>1.3 = amplified vs market; a risk characteristic, not good/bad"
    if beta is None:
        metrics.append(
            Metric("beta", "Beta", "—", "data gap", "grey", beta_meaning, beta_basis)
        )
    else:
        tone = "amber" if beta > 1.3 else "grey"
        metrics.append(
            Metric(
                "beta",
                "Beta",
                f"{beta:.2f}×",
                "vs market",
                tone,
                beta_meaning,
                beta_basis,
            )
        )

    # 5. Max drawdown — largest peak-to-trough decline over the price series
    mdd = _max_drawdown(closes)
    if mdd is not None:
        metrics.append(
            Metric(
                "max_drawdown",
                "Max drawdown",
                f"{mdd:.0f}%",
                "peak-to-trough",
                "amber" if mdd < -20 else "grey",
                "Largest peak-to-trough decline over the available daily price history.",
                "price_history.closes",
            )
        )
    else:
        metrics.append(
            Metric(
                "max_drawdown",
                "Max drawdown",
                "—",
                "data gap",
                "grey",
                "Largest peak-to-trough decline; requires a price series.",
                "data gap — price history unavailable",
            )
        )

    # 6. vs 200-day MA ((price − MA200) / MA200 * 100)
    ma200_meaning = (
        "Percentage distance of the current price from the 200-day moving average. "
        "Positive = trading above long-term trend; negative = below."
    )
    ma200_basis = "(price − 200-day MA) / 200-day MA × 100"
    if current_price is None or ma200 is None or ma200 == 0:
        metrics.append(
            Metric(
                "vs_200d",
                "vs 200-day",
                "—",
                "data gap",
                "grey",
                ma200_meaning,
                ma200_basis,
            )
        )
    else:
        pct_vs_200 = (current_price - ma200) / ma200 * 100
        sign = "+" if pct_vs_200 >= 0 else ""
        tone = "grey"  # measured — not a good/bad signal by itself
        metrics.append(
            Metric(
                "vs_200d",
                "vs 200-day",
                f"{sign}{pct_vs_200:.0f}%",
                "price vs 200-day MA",
                tone,
                ma200_meaning,
                ma200_basis,
            )
        )

    # --- Chips ---
    chips = ""

    # AHEAD OF S&P: green only when excess > 0
    if excess is not None and excess > 0:
        chips += render_status_chip(
            "AHEAD OF S&P",
            f"+{excess:.0f}pts",
            tone="green",
            rule="1Y return minus S&P 1Y return; positive = stock moved more than the index this year",
        )

    # HIGH-BETA: amber when beta > 1.3
    if beta is not None and beta > 1.3:
        chips += render_status_chip(
            "HIGH-BETA",
            f"{beta:.1f}×",
            tone="amber",
            rule="beta>1.3 = amplified vs market; a risk characteristic, not good/bad",
        )

    return {
        "metrics": metrics,
        "chips": chips,
        "claim": "Price and return behaviour over trailing horizons.",
        "reframe": (
            "Returns, drawdown, and relative strength are computed from the daily "
            "close series. Beta is the trailing regression coefficient, not a forecast."
            if closes
            else (
                "1Y return and vs-200d are trailing price facts. "
                "Multi-horizon returns and drawdown need a price series (data gap)."
            )
        ),
        "verdicts": (
            [
                Verdict(
                    "pos",
                    "Multi-horizon returns and drawdown computed from price history.",
                ),
                Verdict(
                    "neu",
                    "Relative strength vs the S&P is descriptive, not a forecast.",
                ),
            ]
            if closes
            else [
                Verdict("neu", "Returns-by-horizon series not wired — data gap."),
                Verdict("neu", "Relative-strength series not wired — data gap."),
            ]
        ),
    }


def build_performance_panel(result: Any) -> str:
    """Compose the full Performance deep-dive panel HTML (panel #1)."""
    v = build_performance_view(result)

    closes = _closes(result)
    hz = _horizon_returns(closes)
    if hz:
        left = (
            '<div class="sa-pnl-subh">Returns by horizon</div>'
            + panel_charts.peer_bars([(lbl, r, lbl == "1Y") for lbl, r in hz], unit="%")
        )
    else:
        left = (
            '<div class="sa-pnl-subh">Returns by horizon</div>'
            '<div class="sa-pnl-cap">returns-by-horizon — data gap (no price series)</div>'
        )

    rs = _relative_strength(closes, _spy_closes(result))
    if len(rs) >= 30:
        right = (
            '<div class="sa-pnl-subh">Relative strength vs S&P (100 = in line)</div>'
            + panel_charts.trend_lines([("RS", rs, "#0F6E80")])
        )
    else:
        right = (
            '<div class="sa-pnl-subh">Relative strength vs S&P</div>'
            '<div class="sa-pnl-cap">relative-strength — data gap (no index series)</div>'
        )

    return build_panel(
        number=1,
        name="Performance",
        dot_colour="#2aa198",
        info_html=render_info(
            "Price and return behaviour; trailing facts.",
            "info.52WeekChange + SandP52WeekChange + beta + twoHundredDayAverage",
        ),
        chips_html=v["chips"],
        claim=v["claim"],
        reframe=v["reframe"],
        strip_html=_strip_html(v["metrics"]),
        viz_left=left,
        viz_right=right,
        verdicts=v["verdicts"],
        drill="open full performance — return history · drawdown · relative strength",
    )
