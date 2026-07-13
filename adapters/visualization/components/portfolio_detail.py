"""Shared detail panel for the portfolio tab.

Opened via ?inspect=TICKER from review cards, treemap tiles, or table rows.
Reuses decision_card.render_expanded_card with live RAG/case fetched lazily.
"""

from __future__ import annotations

import streamlit as st

from adapters.visualization.card_fetch import (
    fetch_card,
    get_case_on_expand,
    implied_cost,
    window_returns,
)
from adapters.visualization.components.decision_card import render_expanded_card
from adapters.visualization.portfolio_view import PortfolioRow
from adapters.visualization.price_cache import fetch_price_history, fetch_prices
from application.card_loading import select_case_summarizer
from application.personal_case_facts import (
    personal_case_extra_facts,
    personal_case_news,
)
from domain.discipline import Verdict


def resolve_case(
    ticker: str, card: object, *, verdict: str = "", why: str = ""
) -> object | None:
    """Fetch the cited Google-AI case (cache-first, lazy) for a holding.

    Mirrors Home's wiring (``select_case_summarizer`` + real news/extra facts
    via ``application.personal_case_facts``, shared with the weekly CLI
    prefetch so cache and live never disagree): a weekly cache hit returns
    with zero network; a miss makes one throttled Gemini call, fed real news
    + verdict/why + real buzz sentiment. Any failure degrades to None
    (DATA-GAP) — never crash, never fabricate.
    """
    try:
        summarizer = select_case_summarizer()
        news = personal_case_news(ticker)
        extra_facts = personal_case_extra_facts(ticker, verdict=verdict, why=why)
        return get_case_on_expand(
            ticker,
            card,  # type: ignore[arg-type]
            news=news,
            expanded=True,
            summarizer=summarizer,
            extra_facts=extra_facts,
        )
    except Exception:  # noqa: BLE001
        return None


def build_detail_header_html(row: PortfolioRow) -> str:
    """Pure HTML builder for the inspect-panel header strip.

    Shows ticker, sector, weight, lifetime P&L, and today's change.
    The verdict field is embedded in the panel title for screen-reader / search.
    """
    pnl_c = "#16A34A" if row.pnl >= 0 else "#DC2626"
    today_c = "#16A34A" if row.today >= 0 else "#DC2626"
    pnl_sign = "+" if row.pnl >= 0 else ""
    today_sign = "+" if row.today >= 0 else ""
    return (
        '<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;'
        'padding:13px 17px;background:#F7FDFE;border-bottom:1px solid var(--ri-line);">'
        f"<span style=\"font-family:'Fraunces',serif;font-weight:700;font-size:1.35rem;\">"
        f"{row.ticker}</span>"
        f'<span style="color:var(--ri-muted);font-size:.8rem;">'
        f"{row.sector} · {row.weight:.1f}% of book</span>"
        f'<span style="color:{pnl_c};font-size:.8rem;">'
        f"lifetime {pnl_sign}{row.pnl:.1f}%</span>"
        f'<span style="color:{today_c};font-size:.8rem;">'
        f"today {today_sign}{row.today:.1f}%</span>"
        f'<span style="color:var(--ri-muted);font-size:.8rem;margin-left:auto;">'
        f"{row.verdict}</span>"
        "</div>"
    )


def render_inspect_detail(row: PortfolioRow) -> None:
    """Render the shared detail panel for an inspected holding (live fetch)."""
    st.markdown(
        f'<div style="border:1px solid var(--ri-teal);border-radius:12px;'
        f'overflow:hidden;margin-top:6px;">{build_detail_header_html(row)}</div>',
        unsafe_allow_html=True,
    )
    if st.button("✕ Close", key=f"close_inspect_{row.ticker}"):
        st.query_params.clear()
        st.rerun()
    try:
        card = fetch_card(row.ticker)
        price_data = fetch_prices((row.ticker,)).get(row.ticker, {})
        live_price = float(price_data.get("price") or 0.0) or None
        cost = implied_cost(live_price, row.pnl) if live_price else None
        hist = fetch_price_history(row.ticker) or {}
        closes = hist.get("closes") if isinstance(hist, dict) else None
        rets = window_returns(list(closes) if closes else [])
        try:
            verdict = Verdict(row.verdict)
        except ValueError:
            verdict = Verdict.REVIEW
        # Google-AI case: cache-first lazy fetch, DATA-GAP (None) on any failure
        case = resolve_case(row.ticker, card, verdict=row.verdict, why=row.why)
        html = render_expanded_card(
            card,
            case=case,
            verdict=verdict,
            name=row.ticker,
            unrealized_pct=row.pnl,
            means=row.why or "Discipline review prompt — not a forecast.",
            price=live_price,
            cost=cost,
            returns=rets,
            reliability="live",
        )
        st.markdown(html, unsafe_allow_html=True)
    except Exception:  # noqa: BLE001
        st.info(f"Evidence for {row.ticker} is loading or unavailable (DATA-GAP).")
    if st.button(f"↗ Analyze {row.ticker}", key=f"analyze_inspect_{row.ticker}"):
        st.session_state["analyze_ticker"] = row.ticker
        st.info(f"{row.ticker} pre-filled — open the Stock Analysis tab.")
    st.caption(
        f"↗ {row.ticker} also appears in the Weekly Brief (Home tab) "
        "when the discipline rule flags it."
    )
