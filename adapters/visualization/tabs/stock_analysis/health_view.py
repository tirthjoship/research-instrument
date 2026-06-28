"""Health panel (spec D10): 6 solvency metrics — D/E, Net cash, ND/EBITDA, Current ratio, Interest coverage, Quick ratio."""

from __future__ import annotations

import html as _html
from typing import Any

from adapters.visualization.components import panel_charts
from adapters.visualization.components.info_tip import render_info
from adapters.visualization.components.status_chip import render_status_chip
from adapters.visualization.components.stock_metrics import STOCK_METRICS
from adapters.visualization.tabs.stock_analysis.panel import Verdict, build_panel
from adapters.visualization.tabs.stock_analysis.valuation_view import Metric

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _f(info: dict[str, Any], key: str) -> float | None:
    v = info.get(key)
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _bs_row(qbs: Any, names: list[str]) -> list[float]:
    """Chronological values of the first matching balance-sheet row (NaNs dropped)."""
    for n in names:
        try:
            if qbs is not None and n in qbs.index:
                return list(reversed([float(v) for v in qbs.loc[n].values if v == v]))
        except Exception:
            continue
    return []


def _fmt_cash(val: float) -> str:
    """Format net cash as +$XB / -$XB (billions/millions/trillions)."""
    abs_val = abs(val)
    sign = "+" if val >= 0 else "-"
    if abs_val >= 1e12:
        return f"{sign}${abs_val / 1e12:.0f}T"
    if abs_val >= 1e9:
        return f"{sign}${abs_val / 1e9:.0f}B"
    if abs_val >= 1e6:
        return f"{sign}${abs_val / 1e6:.0f}M"
    return f"{sign}${abs_val:.0f}"


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


def build_health_view(result: Any) -> dict[str, Any]:
    """Build the health (solvency) view-model.

    Returns a dict with keys: metrics, chips, claim, reframe, verdicts.
    Six metrics: D/E, Net cash, ND/EBITDA, Current ratio, Int cov, Quick ratio.
    Colour is measured against stated thresholds — never fabricated.
    """
    info: dict[str, Any] = getattr(result, "info", {}) or {}

    de = _f(info, "debtToEquity")
    total_cash = _f(info, "totalCash")
    total_debt = _f(info, "totalDebt")
    ebitda = _f(info, "ebitda")
    interest_expense = _f(info, "interestExpense")
    current_ratio = _f(info, "currentRatio")
    quick_ratio = _f(info, "quickRatio")

    metrics: list[Metric] = []

    # 1. D/E ratio (yfinance returns as percentage: 12 = 12%)
    de_meaning = "Debt-to-equity ratio; lower means less financial leverage."
    de_basis = (
        "yfinance info.debtToEquity (percentage form: 12 = 12%); green when < 50%"
    )
    if de is None:
        metrics.append(
            Metric("de", "D/E ratio", "—", "data gap", "grey", de_meaning, de_basis)
        )
    else:
        tone = "green" if de < 50 else "grey"
        metrics.append(
            Metric(
                "de",
                "D/E ratio",
                f"{de:g}%",
                "vs 50% threshold",
                tone,
                de_meaning,
                de_basis,
            )
        )

    # 2. Net cash (totalCash − totalDebt); positive = net cash (green)
    net_cash_meaning = (
        "Cash and equivalents minus total debt; positive = net cash position."
    )
    net_cash_basis = "totalCash − totalDebt; green when positive"
    if total_cash is None or total_debt is None:
        metrics.append(
            Metric(
                "net_cash",
                "Net cash",
                "—",
                "data gap",
                "grey",
                net_cash_meaning,
                net_cash_basis,
            )
        )
        net_cash_val: float | None = None
    else:
        net_cash_val = total_cash - total_debt
        tone = "green" if net_cash_val > 0 else "grey"
        metrics.append(
            Metric(
                "net_cash",
                "Net cash",
                _fmt_cash(net_cash_val),
                "cash minus debt",
                tone,
                net_cash_meaning,
                net_cash_basis,
            )
        )

    # 3. Net-debt / EBITDA; negative = net cash; green when < 3 (includes net-cash)
    nd_meaning, nd_basis = STOCK_METRICS["net_debt_ebitda"]
    if total_cash is None or total_debt is None or ebitda is None or ebitda == 0:
        metrics.append(
            Metric(
                "net_debt_ebitda",
                "ND/EBITDA",
                "—",
                "data gap",
                "grey",
                nd_meaning,
                nd_basis,
            )
        )
    else:
        nd_ebitda = (total_debt - total_cash) / ebitda
        # Negative = net cash = good; < 3 = green
        tone = "green" if nd_ebitda < 3 else "grey"
        sub = "net cash" if nd_ebitda < 0 else ""
        metrics.append(
            Metric(
                "net_debt_ebitda",
                "ND/EBITDA",
                f"{nd_ebitda:.2f}×",
                sub,
                tone,
                nd_meaning,
                nd_basis,
            )
        )

    # 4. Current ratio; green when > 1.5
    cr_meaning = (
        "Current assets divided by current liabilities; "
        "above 1.5 indicates adequate short-term liquidity."
    )
    cr_basis = "yfinance info.currentRatio; green when > 1.5"
    if current_ratio is None:
        metrics.append(
            Metric(
                "current_ratio",
                "Current ratio",
                "—",
                "data gap",
                "grey",
                cr_meaning,
                cr_basis,
            )
        )
    else:
        tone = "green" if current_ratio > 1.5 else "grey"
        metrics.append(
            Metric(
                "current_ratio",
                "Current ratio",
                f"{current_ratio:g}×",
                "",
                tone,
                cr_meaning,
                cr_basis,
            )
        )

    # 5. Interest coverage = ebitda / interestExpense; green when > 5
    ic_meaning, ic_basis = STOCK_METRICS["interest_coverage"]
    if ebitda is None or interest_expense is None or interest_expense == 0:
        metrics.append(
            Metric(
                "interest_coverage",
                "Int cov",
                "—",
                "data gap",
                "grey",
                ic_meaning,
                ic_basis,
            )
        )
    else:
        ic = ebitda / interest_expense
        tone = "green" if ic > 5 else "grey"
        metrics.append(
            Metric(
                "interest_coverage",
                "Int cov",
                f"{ic:.0f}×",
                "EBITDA / interest",
                tone,
                ic_meaning,
                ic_basis,
            )
        )

    # 6. Quick ratio; green when > 1
    qr_meaning = (
        "Current assets minus inventory divided by current liabilities; "
        "stricter liquidity test than current ratio."
    )
    qr_basis = "yfinance info.quickRatio; green when > 1"
    if quick_ratio is None:
        metrics.append(
            Metric(
                "quick_ratio",
                "Quick ratio",
                "—",
                "data gap",
                "grey",
                qr_meaning,
                qr_basis,
            )
        )
    else:
        tone = "green" if quick_ratio > 1 else "grey"
        metrics.append(
            Metric(
                "quick_ratio",
                "Quick ratio",
                f"{quick_ratio:g}×",
                "",
                tone,
                qr_meaning,
                qr_basis,
            )
        )

    # --- Chips (only when earned) ---
    chips = ""

    # FORTRESS: net cash positive AND D/E < 50%
    if net_cash_val is not None and net_cash_val > 0 and de is not None and de < 50:
        chips += render_status_chip(
            "FORTRESS",
            "net cash",
            tone="green",
            rule=(
                "cash > debt and D/E < 50% — "
                "balance sheet carries more cash than gross debt, with low leverage"
            ),
        )

    # LIQUID: current ratio > 1.5
    if current_ratio is not None and current_ratio > 1.5:
        chips += render_status_chip(
            "LIQUID",
            f"{current_ratio:.1f}×",
            tone="green",
            rule="current ratio > 1.5 — current assets cover current liabilities with margin",
        )

    return {
        "metrics": metrics,
        "chips": chips,
        "claim": "Solvency, leverage, and liquidity; trailing balance-sheet facts.",
        "reframe": (
            "D/E, ratios, and coverage are trailing balance-sheet facts. "
            "Net-debt/EBITDA computed from totalDebt, totalCash, and ebitda. "
            "Interest coverage computed from EBITDA / interestExpense. "
            "Balance-sheet trend not wired (data gap)."
        ),
        "verdicts": [
            Verdict("pos", "Net cash position reported — more cash than gross debt."),
            Verdict(
                "neu",
                "Balance-sheet trend not wired — data gap, no quarterly history available.",
            ),
        ],
    }


def build_health_panel(result: Any) -> str:
    """Compose the full Health deep-dive panel HTML (panel #4)."""
    v = build_health_view(result)
    info: dict[str, Any] = getattr(result, "info", {}) or {}

    # Comparison viz: cash vs total-debt bars (descriptive)
    total_cash = _f(info, "totalCash")
    total_debt = _f(info, "totalDebt")

    if total_cash is not None and total_debt is not None:
        cash_rows: list[tuple[str, float, bool]] = [
            ("Cash", total_cash / 1e9, False),
            ("Total debt", total_debt / 1e9, True),
        ]
        comparison_bar = panel_charts.peer_bars(cash_rows, unit="B")
    else:
        comparison_bar = '<div class="sa-pnl-cap">cash and debt data gap</div>'

    left = '<div class="sa-pnl-subh">Cash vs Total debt</div>' + comparison_bar

    # Trend viz: cash & debt over the quarterly balance sheet (real series)
    qbs = getattr(result, "quarterly_balance_sheet", None)
    cash_s = _bs_row(
        qbs,
        [
            "Cash And Cash Equivalents",
            "Cash Cash Equivalents And Short Term Investments",
            "Cash",
        ],
    )
    debt_s = _bs_row(qbs, ["Total Debt", "Total Debt And Capital Lease Obligation"])
    series = []
    if len(cash_s) >= 2:
        series.append(("Cash", [c / 1e9 for c in cash_s], "#1F9254"))
    if len(debt_s) >= 2:
        series.append(("Debt", [d / 1e9 for d in debt_s], "#9aa6aa"))
    if series:
        right = (
            '<div class="sa-pnl-subh">Cash &amp; debt trend ($B)</div>'
            + panel_charts.trend_lines(series)
        )
    else:
        right = (
            '<div class="sa-pnl-subh">Balance-sheet trend</div>'
            '<div class="sa-pnl-cap">no quarterly balance-sheet history — data gap</div>'
        )

    return build_panel(
        number=4,
        name="Health",
        dot_colour="#0F6E80",
        info_html=render_info(
            "Solvency, leverage, and liquidity; trailing facts.",
            "info.debtToEquity + totalCash + totalDebt + ebitda + interestExpense "
            "+ currentRatio + quickRatio",
        ),
        chips_html=v["chips"],
        claim=v["claim"],
        reframe=v["reframe"],
        strip_html=_strip_html(v["metrics"]),
        viz_left=left,
        viz_right=right,
        verdicts=v["verdicts"],
        drill="open full health — debt maturity schedule · trend · liquidity waterfall",
    )
