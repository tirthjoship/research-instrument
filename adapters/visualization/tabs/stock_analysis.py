"""Tab 4: Stock Analysis — SWST-grade deep dive for any ticker."""

from __future__ import annotations

import time
from typing import Any

import streamlit as st

from adapters.visualization.components.cards import (
    criteria_card,
    metric_kpi,
    price_range_bar,
    tooltip,
    verdict_bullet,
)
from adapters.visualization.components.charts import (
    cluster_bubble,
    comparison_bars,
    financials_line,
    gauge_chart,
    insider_bars,
    ownership_pie,
)
from adapters.visualization.stock_analyzer import AnalysisResult
from domain.fit import FitVerdict


def render() -> None:
    """Render the Stock Analysis tab."""
    st.markdown("### Stock Analysis")
    st.markdown(
        '<div style="color:#64748B;font-size:14px;margin-bottom:16px;">'
        "Deep-dive analysis for any ticker — valuation, growth, health, sentiment, and supply chain."
        "</div>",
        unsafe_allow_html=True,
    )

    cols = st.columns([4, 1])
    ticker_input = cols[0].text_input(
        "Ticker", placeholder="NVDA", label_visibility="collapsed"
    )
    analyze = cols[1].button("Run Analysis", type="primary")

    if analyze and ticker_input:
        ticker = ticker_input.upper().strip()
        try:
            from adapters.visualization.stock_analyzer import analyze_ticker

            progress = st.progress(0)
            status = st.empty()
            steps = [
                "Fetching market data...",
                "Loading fundamentals...",
                "Computing indicators...",
                "Checking sentiment...",
                "Querying insiders...",
                "Computing scores...",
                "Building analysis...",
            ]
            for i, step in enumerate(steps):
                progress.progress((i + 1) / len(steps))
                status.text(step)

            result = analyze_ticker(ticker, db_path="data/recommendations.db")
            st.session_state[f"analysis_{ticker}"] = result
            progress.empty()
            status.empty()
        except Exception as exc:
            st.error(f"Analysis failed for {ticker}: {exc}")
            import traceback

            st.code(traceback.format_exc())
            return

    # Show cached result
    lookup_key = ticker_input.upper().strip() if ticker_input else ""
    if lookup_key and f"analysis_{lookup_key}" in st.session_state:
        result = st.session_state[f"analysis_{lookup_key}"]
        _render_verdict(result)
        fit_key = f"fit_{lookup_key}"
        if fit_key not in st.session_state:
            try:
                from datetime import datetime, timezone

                from application.fit_use_case import (
                    default_beta_fn,
                    gather_and_assess,
                    market_systematic_share_threshold,
                )

                fit = gather_and_assess(
                    ticker=lookup_key,
                    reports_dir="data/reports",
                    summary_path="data/personal/brief_summary.json",
                    holdings_path="data/personal/holdings.csv",
                    beta_fn=default_beta_fn,
                    as_of=datetime.now(timezone.utc),
                    systematic_share_threshold=market_systematic_share_threshold(),
                )
                st.session_state[fit_key] = fit
            except Exception:
                st.caption("Fit verdict unavailable (see logs).")
        if fit_key in st.session_state:
            _render_fit_card(st.session_state[fit_key])
        _render_valuation(result)
        _render_growth(result)
        _render_performance(result)
        _render_health(result)
        _render_ownership(result)
        _render_sentiment(result)
        _render_supply_chain(result)
    elif not ticker_input:
        st.markdown(
            '<div class="ws-card" style="text-align:center;padding:2rem;">'
            '<div style="font-size:15px;font-weight:500;color:#1A202C;">Enter a ticker above to start</div>'
            '<div style="font-size:13px;color:#64748B;margin-top:4px;">'
            "Get valuation, growth, financial health, sentiment, and conviction analysis"
            "</div></div>",
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Loading state
# ---------------------------------------------------------------------------


def _show_loading_steps(ticker: str) -> None:
    """Show progressive step indicators while analysis runs."""
    steps = [
        f"Fetching {ticker} market data...",
        "Loading fundamental data...",
        "Computing technical indicators...",
        "Checking sentiment signals...",
        "Querying insider transactions...",
        "Computing scores...",
        "Building analysis...",
    ]
    progress = st.progress(0)
    status = st.empty()
    for i, step in enumerate(steps):
        progress.progress((i + 1) / len(steps))
        status.text(step)
        time.sleep(0.08)
    progress.empty()
    status.empty()


# ---------------------------------------------------------------------------
# Section 0: Verdict / Header
# ---------------------------------------------------------------------------


def _render_verdict(result: AnalysisResult) -> None:
    """Render top verdict section: price, RESEARCH_ONLY notice, consensus comparison."""
    # Company header
    change_color = "#16A34A" if result.change_pct >= 0 else "#DC2626"
    change_sign = "+" if result.change_pct >= 0 else ""
    market_cap_str = _fmt_market_cap(result.market_cap)

    st.markdown(
        f'<div style="margin-bottom:12px;">'
        f"<span style=\"font-family:'DM Sans',sans-serif;font-size:22px;font-weight:700;color:#1A202C;\">"
        f"{result.company_name}</span>"
        f"<span style=\"font-family:'Inter',sans-serif;font-size:14px;color:#64748B;margin-left:8px;\">"
        f"{result.ticker} · {result.sector}</span><br/>"
        f"<span style=\"font-family:'JetBrains Mono',monospace;font-size:24px;font-weight:600;color:#1A202C;\">"
        f"${result.current_price:,.2f}</span>"
        f"<span style=\"font-family:'Inter',sans-serif;font-size:14px;color:{change_color};margin-left:8px;\">"
        f"{change_sign}{result.change_pct:.2f}%</span>"
        f"<span style=\"font-family:'Inter',sans-serif;font-size:13px;color:#94A3B8;margin-left:12px;\">"
        f"Market Cap: {market_cap_str}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # RESEARCH_ONLY reframe (dashboard spec §2.5): no grade, no radar,
    # no buy/sell call — prediction was falsified (ADR-039..050, ADR-053).
    st.markdown(
        '<div class="ws-card" style="padding:12px 16px;margin-bottom:12px;">'
        '<span style="font-weight:700;color:#CA8A04;">RESEARCH ONLY</span> — '
        "descriptive data below; this tool makes no buy/sell call. "
        "Why: every predictive signal tested 2006–2024 was falsified "
        "(see the Falsification Lab tab)."
        "</div>",
        unsafe_allow_html=True,
    )

    # Our system vs Wall Street
    ws_rec = result.analyst_recommendation or "N/A"
    analyst_count = result.analyst_count
    target = result.analyst_mean_target
    st.markdown(
        f'<div class="ws-card" style="padding:12px;margin-top:8px;">'
        f"<div style=\"font-size:12px;color:#94A3B8;font-family:'DM Sans',sans-serif;"
        f'text-transform:uppercase;letter-spacing:0.8px;margin-bottom:8px;">Analyst Consensus</div>'
        f'<div style="display:flex;justify-content:space-between;margin-bottom:4px;">'
        f'<span style="font-size:13px;color:#64748B;">Recommendation</span>'
        f'<span style="font-size:13px;font-weight:600;color:#1A202C;">{ws_rec}</span></div>'
        f'<div style="display:flex;justify-content:space-between;margin-bottom:4px;">'
        f'<span style="font-size:13px;color:#64748B;">Price Target</span>'
        f'<span style="font-size:13px;font-weight:600;color:#1A202C;">'
        f"{'${:.2f}'.format(target) if target else 'N/A'}</span></div>"
        f'<div style="display:flex;justify-content:space-between;">'
        f'<span style="font-size:13px;color:#64748B;">Analysts</span>'
        f'<span style="font-size:13px;font-weight:600;color:#1A202C;">{analyst_count}</span></div>'
        f"</div>",
        unsafe_allow_html=True,
    )

    # Watchlist / Portfolio buttons
    c1, c2, _ = st.columns([1, 1, 4])
    with c1:
        if st.button("+ Watchlist", key=f"watchlist_{result.ticker}"):
            st.info(
                f"{result.ticker} added to watchlist (use CLI: add-watchlist {result.ticker})"
            )
    with c2:
        if st.button("+ Portfolio", key=f"portfolio_{result.ticker}"):
            st.info(f"Use CLI: add-holding {result.ticker} <price> <shares>")


_SEVERITY_CLASS = {
    "INFO": "verdict-neutral",
    "CAUTION": "verdict-caution",
    "WARNING": "verdict-negative",
}


def _render_fit_card(verdict: FitVerdict, screen_as_of: str | None = None) -> None:
    """Evidence grade + fit flags. Descriptive arithmetic only — never a forecast."""
    from adapters.visualization.components.formatters import grade_badge_html

    stale = f" · screen as of {screen_as_of}" if screen_as_of else ""
    st.markdown(
        f'<div class="ws-card" style="padding:12px 16px;margin-bottom:12px;">'
        f"{grade_badge_html(verdict.evidence_grade)} "
        f'<span style="font-weight:700;">Evidence + fit vs your book</span>'
        f'<span style="color:#64748B;font-size:12px;">{stale}</span>'
        f'<div style="font-size:14px;margin-top:8px;">{verdict.summary}</div>'
        "</div>",
        unsafe_allow_html=True,
    )
    for flag in verdict.fit_flags:
        css = _SEVERITY_CLASS.get(flag.severity, "verdict-neutral")
        st.markdown(
            f'<div class="verdict-card {css}">'
            f'<div style="font-size:14px;color:#111827;">{flag.message}</div>'
            "</div>",
            unsafe_allow_html=True,
        )
    st.caption(
        "Evidence + fit only — this tool does not forecast returns "
        "(see Falsification Lab). Position weights are by cost basis."
    )


# ---------------------------------------------------------------------------
# Section 1: Valuation
# ---------------------------------------------------------------------------


def _render_valuation(result: AnalysisResult) -> None:
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
# Section 3: Performance
# ---------------------------------------------------------------------------


def _render_performance(result: AnalysisResult) -> None:
    st.divider()
    section = result.performance
    if not section:
        return
    st.markdown("#### 3. Performance")
    st.markdown(
        criteria_card(section.title, section.score, section.max_score, section.summary),
        unsafe_allow_html=True,
    )

    info = result.info
    col_roe, col_margins = st.columns([1, 1])
    with col_roe:
        roe = info.get("returnOnEquity")
        if roe is not None:
            fig = gauge_chart(
                value=float(roe * 100),
                min_v=0,
                max_v=50,
                label="ROE (%)",
                thresholds=(10, 20),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("ROE data not available")

    with col_margins:
        margin_items = _build_margin_items(info)
        if margin_items:
            fig = comparison_bars(margin_items, value_suffix="%")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("Margin data not available")

    for status, text in section.verdicts:
        st.markdown(verdict_bullet(status, text), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Section 4: Financial Health
# ---------------------------------------------------------------------------


def _render_health(result: AnalysisResult) -> None:
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
        cash_str = f"${cash / 1e9:.1f}B" if cash else "N/A"
        debt_str = f"${debt / 1e9:.1f}B" if debt else "N/A"
        fcf_str = f"${fcf / 1e9:.1f}B" if fcf else "N/A"
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


# ---------------------------------------------------------------------------
# Section 5: Ownership
# ---------------------------------------------------------------------------


def _render_ownership(result: AnalysisResult) -> None:
    st.divider()
    section = result.ownership
    if not section:
        return
    st.markdown("#### 5. Ownership")
    st.markdown(
        criteria_card(section.title, section.score, section.max_score, section.summary),
        unsafe_allow_html=True,
    )

    info = result.info
    col_pie, col_insider = st.columns([1, 1])
    with col_pie:
        inst = float((info.get("heldPercentInstitutions") or 0) * 100)
        insider = float((info.get("heldPercentInsiders") or 0) * 100)
        public = max(0.0, 100.0 - inst - insider)
        if inst > 0 or insider > 0:
            fig = ownership_pie(inst, insider, public)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("Ownership breakdown not available")

    with col_insider:
        from adapters.visualization.stock_analyzer import aggregate_insider_by_quarter

        if result.insider_transactions:
            quarters = aggregate_insider_by_quarter(result.insider_transactions)
            if quarters:
                fig = insider_bars(quarters)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.caption("Could not parse insider transaction dates")
        else:
            st.caption("No insider transactions found")

    for status, text in section.verdicts:
        st.markdown(verdict_bullet(status, text), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Section 6: Sentiment
# ---------------------------------------------------------------------------


def _render_sentiment(result: AnalysisResult) -> None:
    st.divider()
    section = result.sentiment
    if not section:
        return
    st.markdown("#### 6. Sentiment")
    st.caption(
        "Descriptive buzz only — predictive value was tested and falsified "
        "(ADR-044: no cross-sectional IC on a clean 430-ticker universe)."
    )
    st.markdown(
        criteria_card(section.title, section.score, section.max_score, section.summary),
        unsafe_allow_html=True,
    )

    buzz = result.buzz_signals
    if buzz:
        # Show summary table of recent buzz
        rows = []
        for b in buzz[:10]:
            rows.append(
                {
                    "Source": getattr(b, "source", "unknown"),
                    "Sentiment": f"{getattr(b, 'sentiment_raw', 0):.2f}",
                    "Mentions": getattr(b, "mention_count", 0),
                    "Date": str(getattr(b, "fetched_at", ""))[:10],
                }
            )
        if rows:
            import pandas as pd

            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.markdown(
            '<div class="ws-card" style="text-align:center;padding:16px;">'
            '<div style="font-size:14px;color:#64748B;">No sentiment signals in database</div>'
            '<div style="font-size:12px;color:#94A3B8;margin-top:4px;">'
            "Run <code>make daily-scan</code> to populate sentiment data"
            "</div></div>",
            unsafe_allow_html=True,
        )

    for status, text in section.verdicts:
        st.markdown(verdict_bullet(status, text), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Section 7: Supply Chain
# ---------------------------------------------------------------------------


def _render_supply_chain(result: AnalysisResult) -> None:
    st.divider()
    section = result.supply_chain
    if not section:
        return
    st.markdown("#### 7. Supply Chain")
    st.markdown(
        criteria_card(section.title, section.score, section.max_score, section.summary),
        unsafe_allow_html=True,
    )

    sc_group = result.supply_chain_group
    if sc_group:
        # Build bubble chart data from peers + self
        all_tickers_in_group = sc_group.get("leaders", []) + sc_group.get(
            "followers", []
        )
        # Use peer_data for market caps; fill in self
        peer_lookup = {p["ticker"]: p for p in result.peer_data}
        bubble_data = []
        for t in all_tickers_in_group[:10]:
            pd_info = peer_lookup.get(t, {})
            mc = float(pd_info.get("market_cap", 0) or 0)
            if t == result.ticker:
                mc = result.market_cap
            role = "leader" if t in sc_group.get("leaders", []) else "follower"
            bubble_data.append(
                {
                    "ticker": t,
                    "market_cap": mc if mc > 0 else 1e9,
                    "change_pct": float(pd_info.get("change_pct", 0) or 0),
                    "role": role,
                }
            )
        if bubble_data:
            group_name = (
                sc_group.get("group", "Supply Chain Group").replace("_", " ").title()
            )
            fig = cluster_bubble(bubble_data, group_name, highlight=result.ticker)
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.markdown(
            '<div class="ws-card" style="text-align:center;padding:16px;">'
            '<div style="font-size:14px;color:#64748B;">Not in a tracked supply chain group</div>'
            '<div style="font-size:12px;color:#94A3B8;margin-top:4px;">'
            "Cross-asset supply chain signals are not available for this ticker"
            "</div></div>",
            unsafe_allow_html=True,
        )

    for status, text in section.verdicts:
        st.markdown(verdict_bullet(status, text), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


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


def _fmt_market_cap(mc: float) -> str:
    """Format market cap as human-readable string."""
    if mc >= 1e12:
        return f"${mc / 1e12:.1f}T"
    if mc >= 1e9:
        return f"${mc / 1e9:.1f}B"
    if mc >= 1e6:
        return f"${mc / 1e6:.1f}M"
    return f"${mc:,.0f}"
