"""Performance, Ownership sections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from adapters.visualization.components.cards import criteria_card, verdict_bullet
from adapters.visualization.components.charts import (
    comparison_bars,
    gauge_chart,
    insider_bars,
    ownership_pie,
)
from adapters.visualization.components.currency import (
    currency_for_ticker,
    currency_symbol,
)
from adapters.visualization.stock_analyzer import AnalysisResult
from adapters.visualization.tabs.stock_analysis.financials_section import (
    _build_margin_items,
)

# ---------------------------------------------------------------------------
# Section 3: Performance — vs-market / technicals descriptive card
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VsMarketCard:
    """Descriptive vs-market + trend-position facts pulled from the info snapshot.

    All fields are realized, point-in-time descriptions (trailing 1y change, moving
    averages, beta). Nothing here is a forecast — it describes where the name sits
    relative to the market and its own trend today.
    """

    stock_1y_pct: float | None
    spy_1y_pct: float | None
    excess_1y_pct: float | None
    beta: float | None
    ma200: float | None
    ma50: float | None
    price_vs_ma200_pct: float | None
    price_vs_ma50_pct: float | None


def _build_vs_market_card(info: dict[str, Any], current_price: float) -> VsMarketCard:
    """Extract vs-market / technicals facts from a yfinance info dict. Pure function.

    Uses keys yfinance already returns (``52WeekChange``, ``SandP52WeekChange``,
    ``twoHundredDayAverage``, ``fiftyDayAverage``, ``beta``) that compose.py fetches
    but the tab never surfaced. Missing keys degrade to ``None`` (honest DATA GAP).
    """

    def _pct(key: str) -> float | None:
        raw = info.get(key)
        return float(raw) * 100.0 if raw is not None else None

    def _flt(key: str) -> float | None:
        raw = info.get(key)
        return float(raw) if raw is not None else None

    stock_1y = _pct("52WeekChange")
    spy_1y = _pct("SandP52WeekChange")
    excess = stock_1y - spy_1y if stock_1y is not None and spy_1y is not None else None

    ma200 = _flt("twoHundredDayAverage")
    ma50 = _flt("fiftyDayAverage")
    price = float(current_price or 0.0)
    vs_200 = (price - ma200) / ma200 * 100.0 if ma200 and price > 0 else None
    vs_50 = (price - ma50) / ma50 * 100.0 if ma50 and price > 0 else None

    return VsMarketCard(
        stock_1y_pct=stock_1y,
        spy_1y_pct=spy_1y,
        excess_1y_pct=excess,
        beta=_flt("beta"),
        ma200=ma200,
        ma50=ma50,
        price_vs_ma200_pct=vs_200,
        price_vs_ma50_pct=vs_50,
    )


def _vs_market_card_html(card: VsMarketCard) -> str:
    """Render the vs-market / technicals card as HTML. Pure function — testable."""

    def _row(label: str, value: str, colour: str = "#1A202C") -> str:
        return (
            f'<div style="display:flex;justify-content:space-between;'
            f'padding:3px 0;font-size:13px;">'
            f'<span style="color:#64748B;">{label}</span>'
            f'<span style="font-weight:600;color:{colour};">{value}</span></div>'
        )

    def _signed(v: float | None, suffix: str = "%") -> tuple[str, str]:
        if v is None:
            return "DATA GAP", "#94A3B8"
        colour = "#16A34A" if v > 0 else "#DC2626" if v < 0 else "#64748B"
        return f"{v:+.1f}{suffix}", colour

    rows: list[str] = []
    s_txt, s_col = _signed(card.stock_1y_pct)
    rows.append(_row("Stock 1y change", s_txt, s_col))
    spy_txt, spy_col = _signed(card.spy_1y_pct)
    rows.append(_row("S&P 500 1y change", spy_txt, spy_col))
    ex_txt, ex_col = _signed(card.excess_1y_pct)
    rows.append(_row("Excess vs S&P (1y)", ex_txt, ex_col))
    if card.beta is not None:
        rows.append(_row("Beta (vs market)", f"{card.beta:.2f}"))
    if card.price_vs_ma200_pct is not None:
        v_txt, v_col = _signed(card.price_vs_ma200_pct)
        rows.append(_row("Price vs 200-day MA", v_txt, v_col))
    if card.price_vs_ma50_pct is not None:
        v_txt, v_col = _signed(card.price_vs_ma50_pct)
        rows.append(_row("Price vs 50-day MA", v_txt, v_col))

    return (
        f'<div class="ws-card" style="padding:12px 16px;margin-bottom:10px;">'
        f'<div style="font-weight:600;font-size:14px;color:#1A202C;margin-bottom:6px;">'
        f"vs Market &amp; trend position</div>"
        f"{''.join(rows)}"
        f'<div style="font-size:11px;color:#94A3B8;margin-top:6px;">'
        "Realized trailing facts vs SPY and the name&apos;s own moving averages — "
        "a description of where it sits today, not a forecast.</div>"
        f"</div>"
    )


def _render_performance(result: AnalysisResult) -> None:
    import streamlit as st

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

    # vs-market / technicals descriptive card (FLOW + relative performance).
    vs_market = _build_vs_market_card(info, result.current_price)
    st.markdown(_vs_market_card_html(vs_market), unsafe_allow_html=True)
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
# Section 5: Ownership — insider net stance + quarter-over-quarter delta
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OwnershipDelta:
    """Descriptive insider net stance for the latest quarter + QoQ change.

    Built from the per-quarter aggregation the ownership chart already uses, so it
    adds context without new data. Insider buying/selling is a disclosed fact, not a
    forecast — the card frames it that way.
    """

    latest_quarter: str
    net_value: float  # buy_value - sell_value for the latest quarter
    buys: int
    sells: int
    prior_quarter: str | None
    prior_net_value: float | None
    qoq_delta: float | None  # net_value - prior_net_value


def _build_ownership_delta(quarters: list[dict[str, Any]]) -> OwnershipDelta | None:
    """Summarise the latest quarter's insider net stance + QoQ swing. Pure function.

    ``quarters`` is the output of ``aggregate_insider_by_quarter`` (sorted ascending).
    Returns ``None`` when empty so the caller can skip the card.
    """
    if not quarters:
        return None

    latest = quarters[-1]
    net = float(latest.get("buy_value", 0.0) or 0.0) - float(
        latest.get("sell_value", 0.0) or 0.0
    )
    prior_q: str | None = None
    prior_net: float | None = None
    qoq: float | None = None
    if len(quarters) >= 2:
        prev = quarters[-2]
        prior_q = str(prev.get("quarter", ""))
        prior_net = float(prev.get("buy_value", 0.0) or 0.0) - float(
            prev.get("sell_value", 0.0) or 0.0
        )
        qoq = net - prior_net

    return OwnershipDelta(
        latest_quarter=str(latest.get("quarter", "")),
        net_value=net,
        buys=int(latest.get("buys", 0) or 0),
        sells=int(latest.get("sells", 0) or 0),
        prior_quarter=prior_q,
        prior_net_value=prior_net,
        qoq_delta=qoq,
    )


def _fmt_money(v: float, ticker: str = "") -> str:
    """Compact signed dollar formatting for insider values, using the ticker's
    market currency symbol (C$/₹) instead of always assuming USD."""
    sign = "-" if v < 0 else ""
    a = abs(v)
    sym = currency_symbol(currency_for_ticker(ticker))
    if a >= 1e9:
        return f"{sign}{sym}{a / 1e9:.1f}B"
    if a >= 1e6:
        return f"{sign}{sym}{a / 1e6:.1f}M"
    if a >= 1e3:
        return f"{sign}{sym}{a / 1e3:.0f}K"
    return f"{sign}{sym}{a:.0f}"


def _ownership_delta_html(delta: OwnershipDelta, ticker: str = "") -> str:
    """Render the insider net-stance + QoQ delta card as HTML. Pure function."""
    if delta.net_value > 0:
        stance, colour = "net buyers", "#16A34A"
    elif delta.net_value < 0:
        stance, colour = "net sellers", "#DC2626"
    else:
        stance, colour = "balanced", "#64748B"

    qoq_html = ""
    if delta.qoq_delta is not None and delta.prior_quarter:
        d_col = (
            "#16A34A"
            if delta.qoq_delta > 0
            else "#DC2626" if delta.qoq_delta < 0 else "#64748B"
        )
        qoq_html = (
            f'<div style="font-size:12px;color:#64748B;margin-top:4px;">'
            f"Quarter-over-quarter: "
            f'<span style="color:{d_col};font-weight:600;">'
            f"{_fmt_money(delta.qoq_delta, ticker)}</span> "
            f"vs {delta.prior_quarter} ({_fmt_money(delta.prior_net_value or 0.0, ticker)})</div>"
        )

    return (
        f'<div class="ws-card" style="padding:12px 16px;margin-bottom:10px;">'
        f'<div style="font-size:14px;color:#1A202C;">'
        f'Insiders were <span style="color:{colour};font-weight:700;">{stance}</span> '
        f"in {delta.latest_quarter} "
        f'<span style="color:#94A3B8;">'
        f"({delta.buys} buy(s), {delta.sells} sell(s), net {_fmt_money(delta.net_value, ticker)})</span>"
        f"</div>"
        f"{qoq_html}"
        f'<div style="font-size:11px;color:#94A3B8;margin-top:6px;">'
        "Disclosed Form-4 activity — a fact about insider behaviour, not a forecast.</div>"
        f"</div>"
    )


def _render_ownership(result: AnalysisResult) -> None:
    import streamlit as st

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

        quarters: list[Any] = []
        if result.insider_transactions:
            quarters = aggregate_insider_by_quarter(result.insider_transactions)
            if quarters:
                fig = insider_bars(quarters)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.caption("Could not parse insider transaction dates")
        else:
            st.caption("No insider transactions found")

    # Insider net-stance + quarter-over-quarter delta context (FLOW of ownership).
    delta = _build_ownership_delta(quarters)
    if delta is not None:
        st.markdown(_ownership_delta_html(delta, result.ticker), unsafe_allow_html=True)

    for status, text in section.verdicts:
        st.markdown(verdict_bullet(status, text), unsafe_allow_html=True)
