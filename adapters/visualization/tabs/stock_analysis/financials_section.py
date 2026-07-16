"""Valuation, Growth, Health sections."""

from __future__ import annotations

from typing import Any

from adapters.visualization.components.cards import (
    criteria_card,
    metric_kpi,
    price_range_bar,
    tooltip,
    verdict_bullet,
)
from adapters.visualization.components.charts import (
    apply_dossier_template,
    comparison_bars,
    financials_line,
    gauge_chart,
)
from adapters.visualization.components.currency import (
    currency_for_ticker,
    currency_symbol,
)
from adapters.visualization.stock_analyzer import AnalysisResult
from adapters.visualization.tabs.stock_analysis.verdict_section import (
    _render_peer_percentiles,
)


def _build_pe_items(
    ticker: str, info: dict[str, Any], peers: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Build P/E comparison items for all tickers including self."""
    items = []
    pe = info.get("trailingPE")
    if pe is not None:
        items.append({"name": ticker, "value": round(float(pe), 1)})
    for p in peers:
        pt = p.get("pe")
        if pt is not None:
            items.append({"name": p["ticker"], "value": round(float(pt), 1)})
    return items


def _fmt_b(val: float | None, ticker: str) -> str:
    """Format a balance-sheet dollar value in billions, using the ticker's
    market currency symbol (C$/₹) instead of always assuming USD. Returns
    "N/A" for falsy/None input."""
    if not val:
        return "N/A"
    sym = currency_symbol(currency_for_ticker(ticker))
    return f"{sym}{val / 1e9:.1f}B"


def _build_margin_items(info: dict[str, Any]) -> list[dict[str, Any]]:
    """Build margin comparison items."""
    items = []
    gross = info.get("grossMargins")
    operating = info.get("operatingMargins")
    net = info.get("profitMargins")
    if gross is not None:
        items.append({"name": "Gross Margin", "value": round(float(gross * 100), 1)})
    if operating is not None:
        items.append(
            {"name": "Operating Margin", "value": round(float(operating * 100), 1)}
        )
    if net is not None:
        items.append({"name": "Net Margin", "value": round(float(net * 100), 1)})
    return items


def _render_valuation(result: AnalysisResult) -> None:
    import streamlit as st

    st.divider()
    section = result.valuation
    if not section:
        return
    st.markdown(
        "#### "
        + tooltip(
            "1. Valuation",
            "Evaluates whether the stock is fairly priced using P/E, PEG (Price/Earnings-to-Growth, "
            "below 1 = undervalued, above 2 = overvalued), P/B, analyst targets, and FCF yield.",
        ),
        unsafe_allow_html=True,
    )
    st.markdown(
        criteria_card(section.title, section.score, section.max_score, section.summary),
        unsafe_allow_html=True,
    )
    # E1: Industry-relative percentiles surfaced in valuation section
    _render_peer_percentiles(result)

    # Charts
    info = result.info
    col_chart, col_range = st.columns([1, 1])
    with col_chart:
        # P/E comparison bars
        pe_items = _build_pe_items(result.ticker, info, result.peer_data)
        if pe_items:
            st.markdown(
                tooltip(
                    "**P/E vs Peers**",
                    "Price-to-Earnings ratio: how much investors pay per $1 of earnings. "
                    "Lower P/E vs peers can signal undervaluation; much higher P/E signals "
                    "growth premium or overvaluation.",
                ),
                unsafe_allow_html=True,
            )
            fig = comparison_bars(pe_items, highlight=result.ticker, value_suffix="x")
            apply_dossier_template(fig)
            st.plotly_chart(fig, use_container_width=True)

    with col_range:
        # Price vs analyst target
        current = result.current_price
        low52 = info.get("fiftyTwoWeekLow") or current * 0.8
        high52 = info.get("fiftyTwoWeekHigh") or current * 1.2
        target = info.get("targetMeanPrice")
        if current > 0:
            st.markdown(
                price_range_bar(
                    current,
                    float(low52),
                    float(high52),
                    float(target) if target else None,
                    ticker=result.ticker,
                ),
                unsafe_allow_html=True,
            )
            st.markdown(
                '<div style="font-size:11px;color:#94A3B8;text-align:center;">52-week range with analyst target</div>',
                unsafe_allow_html=True,
            )

    for status, text in section.verdicts:
        st.markdown(verdict_bullet(status, text), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Section 2: Growth
# ---------------------------------------------------------------------------


def _render_growth(result: AnalysisResult) -> None:
    import streamlit as st

    st.divider()
    section = result.growth
    if not section:
        return
    st.markdown("#### 2. Growth")
    st.markdown(
        criteria_card(section.title, section.score, section.max_score, section.summary),
        unsafe_allow_html=True,
    )

    info = result.info
    col_kpis, col_chart = st.columns([1, 2])
    with col_kpis:
        rev_growth = info.get("revenueGrowth")
        eps_growth = info.get("earningsGrowth")
        rev_str = f"{rev_growth * 100:.1f}%" if rev_growth is not None else "N/A"
        eps_str = f"{eps_growth * 100:.1f}%" if eps_growth is not None else "N/A"
        rev_color = "#16A34A" if (rev_growth or 0) > 0 else "#DC2626"
        eps_color = "#16A34A" if (eps_growth or 0) > 0 else "#DC2626"
        st.markdown(
            metric_kpi("Revenue Growth", rev_str, "Year-over-year", rev_color),
            unsafe_allow_html=True,
        )
        st.markdown(
            metric_kpi("Earnings Growth", eps_str, "Year-over-year", eps_color),
            unsafe_allow_html=True,
        )

    with col_chart:
        qf = result.quarterly_financials
        if qf is not None and not qf.empty:
            try:
                df = qf.T  # dates as rows, metrics as columns
                available = [
                    m for m in ["Total Revenue", "Net Income"] if m in df.columns
                ]
                if available:
                    fig = financials_line(df, available)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.caption("Quarterly revenue chart not available")
            except Exception:
                st.caption("Could not render quarterly financials")
        else:
            st.caption("Quarterly financials not available")

    for status, text in section.verdicts:
        st.markdown(verdict_bullet(status, text), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Section 4: Financial Health
# ---------------------------------------------------------------------------


def _render_health(result: AnalysisResult) -> None:
    import streamlit as st

    st.divider()
    section = result.health
    if not section:
        return
    st.markdown("#### 4. Financial Health")
    st.markdown(
        criteria_card(section.title, section.score, section.max_score, section.summary),
        unsafe_allow_html=True,
    )

    info = result.info
    col_gauge, col_metrics = st.columns([1, 1])
    with col_gauge:
        de = info.get("debtToEquity")
        if de is not None:
            fig = gauge_chart(
                value=float(de),
                min_v=0,
                max_v=300,
                label="Debt/Equity (%)",
                thresholds=(50, 150),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("D/E data not available")

    with col_metrics:
        cash = info.get("totalCash")
        debt = info.get("totalDebt")
        fcf = info.get("freeCashflow")
        cr = info.get("currentRatio")
        cash_str = _fmt_b(cash, result.ticker)
        debt_str = _fmt_b(debt, result.ticker)
        fcf_str = _fmt_b(fcf, result.ticker)
        cr_str = f"{cr:.2f}x" if cr else "N/A"
        fcf_color = "#16A34A" if (fcf or 0) > 0 else "#DC2626"
        st.markdown(
            metric_kpi("Total Cash", cash_str, "On balance sheet"),
            unsafe_allow_html=True,
        )
        st.markdown(
            metric_kpi("Total Debt", debt_str, "Outstanding"), unsafe_allow_html=True
        )
        st.markdown(
            metric_kpi("Free Cash Flow", fcf_str, "Trailing twelve months", fcf_color),
            unsafe_allow_html=True,
        )
        st.markdown(
            metric_kpi("Current Ratio", cr_str, "Current assets / liabilities"),
            unsafe_allow_html=True,
        )

    for status, text in section.verdicts:
        st.markdown(verdict_bullet(status, text), unsafe_allow_html=True)
