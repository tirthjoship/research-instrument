"""Shared detail panel for the portfolio tab.

Opened via st.session_state["pf_inspect_ticker"] — set by a real st.button
(review cards) or the "Inspect a holding" selectbox, never by a raw HTML
anchor/query-param (that pattern caused real browser navigations on
Streamlit Cloud, wiping session state — see PORTFOLIO_INSPECT_STATE_KEY).
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

#: st.session_state key holding the ticker to show in the inspect panel, or
#: absent/None when closed. Native Streamlit state only — never a URL query
#: param (see module docstring for why).
PORTFOLIO_INSPECT_STATE_KEY = "pf_inspect_ticker"

#: Widget key of positions.py's "Inspect a holding" selectbox. Closing the
#: panel must also reset this — a Streamlit widget's own persisted state
#: overrides its `index=` default on rerun, so clearing only
#: PORTFOLIO_INSPECT_STATE_KEY would leave the selectbox still showing the
#: old ticker, which would immediately re-derive and reopen the panel.
PORTFOLIO_INSPECT_PICKER_KEY = "pf_inspect_picker"


def resolve_case(
    ticker: str,
    card: object,
    *,
    verdict: str = "",
    why: str = "",
    reports_dir: str | None = None,
) -> object | None:
    """Fetch the cited Google-AI case (cache-first, lazy) for a holding.

    Mirrors Home's wiring (``select_case_summarizer`` + real news/extra facts
    via ``application.personal_case_facts``, shared with the weekly CLI
    prefetch so cache and live never disagree): a weekly cache hit returns
    with zero network; a miss makes one throttled Gemini call, fed real news
    + verdict/why + real buzz sentiment. Any failure degrades to None
    (DATA-GAP) — never crash, never fabricate.

    ``reports_dir``: same {reports_dir}/home_cited_cases.json cache Home uses
    — without it this call falls back to card_fetch's hardcoded, gitignored
    default (never exists on Cloud), so every inspect-panel click would fire
    an uncached live Gemini call.
    """
    try:
        summarizer = select_case_summarizer()
        news = personal_case_news(ticker)
        extra_facts = personal_case_extra_facts(ticker, verdict=verdict, why=why)
        cache_path = (
            f"{reports_dir}/home_cited_cases.json" if reports_dir is not None else None
        )
        return get_case_on_expand(
            ticker,
            card,  # type: ignore[arg-type]
            news=news,
            expanded=True,
            summarizer=summarizer,
            extra_facts=extra_facts,
            cache_path=cache_path,
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


def render_inspect_body(row: PortfolioRow, reports_dir: str | None = None) -> None:
    """Render just the evidence card content (live fetch) — no header, no
    close button. Used both by render_inspect_detail() (standalone panel,
    needs its own header/close) and directly inside an st.expander (the
    expander's own label/toggle already provides both, matching Home tab's
    render_collapsed_row + st.expander pattern)."""
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
        case = resolve_case(
            row.ticker,
            card,
            verdict=row.verdict,
            why=row.why,
            reports_dir=reports_dir,
        )
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


def render_inspect_detail(row: PortfolioRow, reports_dir: str | None = None) -> None:
    """Render the shared detail panel for an inspected holding (live fetch).

    Standalone version with its own header + Close button — used by the
    "Inspect a holding" selectbox panel. For a holding already inside an
    st.expander (e.g. the Needs Review list), call render_inspect_body()
    directly instead — the expander already provides both.
    """
    st.markdown(
        f'<div style="border:1px solid var(--ri-teal);border-radius:12px;'
        f'overflow:hidden;margin-top:6px;">{build_detail_header_html(row)}</div>',
        unsafe_allow_html=True,
    )
    if st.button("✕ Close", key=f"close_inspect_{row.ticker}"):
        st.session_state.pop(PORTFOLIO_INSPECT_STATE_KEY, None)
        st.session_state.pop(PORTFOLIO_INSPECT_PICKER_KEY, None)
        st.rerun()
    render_inspect_body(row, reports_dir)
