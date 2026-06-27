"""Stock Analysis tab — compose.py: render() entry point and decision-lead helpers."""

from __future__ import annotations

from collections.abc import Callable, MutableMapping
from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from domain.fit import FitVerdict

from adapters.visualization.components.charts import apply_dossier_template
from adapters.visualization.components.snowflake import build_snowflake
from adapters.visualization.data_loader import load_corroboration_snapshot
from adapters.visualization.tabs.stock_analysis.corroboration_section import (
    render_corroboration_section,
)
from adapters.visualization.tabs.stock_analysis.financials_section import (
    _render_growth,
    _render_health,
    _render_valuation,
)
from adapters.visualization.tabs.stock_analysis.market_section import (
    _render_ownership,
    _render_performance,
)
from adapters.visualization.tabs.stock_analysis.signals_section import (
    _render_sentiment,
    _render_supply_chain,
)
from adapters.visualization.tabs.stock_analysis.verdict_section import (
    _render_analyst_panel,
    _render_fit_card,
    _render_news_context,
    _render_verdict,
    _snowflake_axes,
)

_SECTION_LABELS: list[str] = [
    "Verdict",
    "Fit",
    "Valuation",
    "Growth",
    "Performance",
    "Health",
    "Ownership",
    "Sentiment",
    "Supply chain",
    "Corroboration",
]

_CORR_DB_PATH = "data/corroboration.db"


def _ensure_fit_cached(
    session_state: MutableMapping[str | int, Any],
    key: str,
    compute_fn: Callable[[], "FitVerdict"],
) -> "FitVerdict | None":
    """Compute the fit verdict once per key; cache in session_state.

    On compute failure, return None and do NOT cache (so a later rerun retries).
    """
    if key in session_state:
        return session_state[key]  # type: ignore[no-any-return]
    try:
        verdict = compute_fn()
    except Exception:
        logger.warning("fit verdict computation failed")
        return None
    session_state[key] = verdict
    return verdict


def render() -> None:
    """Render the Stock Analysis tab."""
    import streamlit as st

    # Page-level RESEARCH_ONLY banner — always visible, before ticker input.
    st.markdown(
        '<div style="background:#FEF9C3;border-left:4px solid #CA8A04;'
        "padding:10px 16px;border-radius:4px;margin-bottom:16px;"
        'font-size:13px;">'
        "<strong>RESEARCH ONLY</strong> — this tab surfaces attributed evidence. "
        "It makes no buy/sell recommendation. Every predictive signal tested "
        "2006–2024 was falsified. See the Trust tab."
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown("### Stock Analysis")
    st.markdown(
        '<div style="color:#64748B;font-size:14px;margin-bottom:16px;">'
        "Deep-dive analysis for any ticker — valuation, growth, health, sentiment, and supply chain."
        "</div>",
        unsafe_allow_html=True,
    )

    pending = st.session_state.pop("analyze_ticker", None)

    cols = st.columns([4, 1])
    ticker_input = cols[0].text_input(
        "Ticker", value=pending or "", placeholder="NVDA", label_visibility="collapsed"
    )
    analyze = cols[1].button("Run Analysis", type="primary") or pending is not None

    if analyze and ticker_input:
        ticker = ticker_input.upper().strip()
        try:
            from adapters.visualization.stock_analyzer import analyze_ticker

            with st.spinner(
                f"Analyzing {ticker} — fetching live market data, fundamentals, "
                "and sentiment (typically 20-60s)..."
            ):
                result = analyze_ticker(ticker, db_path="data/recommendations.db")
                st.session_state[f"analysis_{ticker}"] = result
                st.session_state.pop(f"fit_{ticker}", None)
        except Exception as exc:
            st.error(f"Analysis failed for {ticker}: {exc}")
            import traceback

            st.code(traceback.format_exc())
            return
    elif analyze and not ticker_input:
        st.warning("Type a ticker first — e.g. NVDA or AAPL.")

    # Show cached result
    lookup_key = ticker_input.upper().strip() if ticker_input else ""
    if lookup_key and f"analysis_{lookup_key}" in st.session_state:
        result = st.session_state[f"analysis_{lookup_key}"]

        # Load corroboration snapshot (None if store empty / DB missing)
        corr_view = load_corroboration_snapshot(lookup_key, db_path=_CORR_DB_PATH)

        st.markdown(
            " ".join(
                f'<span class="section-chip">{i}</span>'
                f'<span style="margin-right:14px;font-size:13px;color:#5C6370;">'
                f"{name}</span>"
                for i, name in enumerate(_SECTION_LABELS, start=1)
            ),
            unsafe_allow_html=True,
        )
        _render_decision_lead(result)
        _render_story_banner(result)
        _render_verdict(result, corr_view=corr_view)
        # Evidence-status framing header — make explicit this is attributed
        # evidence, not a forecast, before any data panels.
        st.markdown(
            '<div class="ri-sec" style="'
            "background:var(--ri-surface,#F8FAFC);"
            "border-left:3px solid var(--ri-teal,#0F6E80);"
            "padding:10px 14px;margin-bottom:12px;"
            'border-radius:4px;">'
            '<span style="font-weight:700;color:var(--ri-teal,#0F6E80);">'
            "Evidence Status: not a forecast</span>"
            '<span style="font-size:13px;color:#64748B;margin-left:8px;">'
            "All panels below surface attributed third-party data "
            "(yfinance, analyst consensus, buzz sources). "
            "This tool describes what is true today; it does not forecast returns."
            "</span></div>",
            unsafe_allow_html=True,
        )
        fit_key = f"fit_{lookup_key}"

        from datetime import datetime, timezone

        from application.fit_use_case import (
            default_beta_fn,
            gather_and_assess,
            market_systematic_share_threshold,
        )

        fit = _ensure_fit_cached(
            st.session_state,
            fit_key,
            lambda: gather_and_assess(
                ticker=lookup_key,
                reports_dir="data/reports",
                summary_path="data/personal/brief_summary.json",
                holdings_path="data/personal/holdings.csv",
                beta_fn=default_beta_fn,
                as_of=datetime.now(timezone.utc),
                systematic_share_threshold=market_systematic_share_threshold(),
            ),
        )
        if fit is not None:
            _render_fit_card(fit)
        else:
            st.caption("Fit verdict unavailable (see logs).")
        axes = _snowflake_axes(fit)
        fig = build_snowflake(axes)
        if fig is not None:
            st.markdown("##### Evidence snowflake")
            apply_dossier_template(fig)
            st.plotly_chart(fig, use_container_width=True)
            st.caption(
                "Factual percentiles vs the screened universe + fit "
                "arithmetic — a description of today, not a forecast."
            )
        _render_analyst_panel(result)
        _render_news_context(result)
        _render_valuation(result)
        _render_growth(result)
        _render_performance(result)
        _render_health(result)
        _render_ownership(result)
        _render_sentiment(result)
        _render_supply_chain(result)
        render_corroboration_section(corr_view)
    elif not ticker_input:
        st.markdown(
            '<div class="ws-card" style="text-align:center;padding:2rem;">'
            '<div style="font-size:15px;font-weight:500;color:#1A202C;">Enter a ticker above to start</div>'
            '<div style="font-size:13px;color:#64748B;margin-top:4px;">'
            "Get valuation, growth, financial health, sentiment, and fit analysis"
            "</div></div>",
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# S3: Decision-card lead (v9 expanded card above the deep-dive)
# ---------------------------------------------------------------------------


def _snake_info(raw: dict[str, Any]) -> dict[str, Any]:
    """Map raw yfinance camelCase info keys to the snake_case keys S1 expects."""
    _MAP = {
        "trailingPE": "trailing_pe",
        "debtToEquity": "debt_to_equity",
        "pegRatio": "peg_ratio",
        "freeCashflow": "free_cashflow",
        "marketCap": "market_cap",
    }
    return {_MAP.get(k, k): v for k, v in raw.items()}


def select_case_summarizer() -> object:
    """Proxy to application.card_loading.select_case_summarizer (patchable in tests)."""
    from application.card_loading import select_case_summarizer as _sel

    return _sel()


def _render_decision_lead_html(
    result: Any, verdict_value: str, *, with_case: bool = False
) -> str:
    """Pure function: build and return the v9 decision-card HTML for a ticker result.

    Testable without Streamlit. Uses getattr with defaults for optional fields
    (price_series, atr, ma200, vs_spy_pct) that may not exist on AnalysisResult.

    When with_case=True, fetches the lazy cited case via the summarizer and renders it
    in the expanded card (S5). Default False for backward compat.
    """
    from adapters.data.earnings_history_adapter import fetch_earnings_history
    from adapters.visualization.card_fetch import get_case_on_expand
    from adapters.visualization.components.decision_card import render_expanded_card
    from application.analyst_panel import build_analyst_panel
    from application.evidence_card import build_evidence_card
    from domain.discipline import Verdict

    info = _snake_info(result.info or {})
    info["current_price"] = result.current_price

    panel = result.analyst_panel or build_analyst_panel({}, "")
    earnings = fetch_earnings_history(result.ticker)

    prices: dict[str, Any] = {
        "closes": getattr(result, "price_series", None) or [],
        "atr": getattr(result, "atr", None),
        "ma200": getattr(result, "ma200", None),
        "spy_1y": None,
        "book_1y": getattr(result, "vs_spy_pct", None),
    }
    peers = [p.get("pe") for p in (result.peer_data or [])]

    card = build_evidence_card(
        result.ticker,
        info=info,
        prices=prices,
        panel=panel,
        earnings=earnings,
        peers=peers,
    )

    # S5: fetch lazy cited case when requested (expanded=True → always fetch here)
    # Look up select_case_summarizer through the package namespace so tests can
    # monkeypatch it via `sa.select_case_summarizer` (sa = the package __init__).
    import sys

    _pkg = sys.modules.get("adapters.visualization.tabs.stock_analysis", None)
    _scsfn = getattr(_pkg, "select_case_summarizer", None) or select_case_summarizer
    case = None
    if with_case:
        result_case = get_case_on_expand(
            result.ticker,
            card,
            news=[],
            expanded=True,
            summarizer=_scsfn(),
        )
        # data_gap → pass None so _case_html renders honest placeholder
        case = None if (result_case is None or result_case.data_gap) else result_case

    verdict = Verdict(verdict_value)
    return render_expanded_card(
        card,
        case=case,
        verdict=verdict,
        name=result.company_name,
        unrealized_pct=None,
        means=(
            f"{result.ticker} — attributed evidence below; "
            f"your rule's verdict is {verdict.value}."
        ),
        price=result.current_price,
        cost=None,
        returns=(),
        reliability="measured forward; see Trust tab",
    )


def _render_decision_lead(result: Any) -> None:
    """Render the v9 decision-card lead via st.markdown. Calls _render_decision_lead_html."""
    import streamlit as st

    verdict_value = getattr(result, "verdict", "REVIEW")
    st.markdown(
        _render_decision_lead_html(result, verdict_value, with_case=True),
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# "Story this week" — a 1-2 sentence DESCRIPTIVE synthesis of the current
# sentiment / flow / valuation state. No predictions.
# ---------------------------------------------------------------------------


def _build_story_phrases(result: Any) -> list[str]:
    """Build the descriptive story phrases for a ticker. Pure — no Streamlit.

    Synthesises three already-computed, attributed facts — buzz mix, insider net
    stance last quarter, and valuation percentile vs peers — into short descriptive
    clauses. Returns only the phrases for which data exists; never a forecast.
    """
    from adapters.visualization.stock_analyzer import aggregate_insider_by_quarter
    from adapters.visualization.tabs.stock_analysis.market_section import (
        _build_ownership_delta,
    )
    from adapters.visualization.tabs.stock_analysis.signals_section import (
        _build_sentiment_digest,
    )

    phrases: list[str] = []

    # 1. Sentiment mix across sources.
    digest = _build_sentiment_digest(getattr(result, "buzz_signals", []) or [])
    if digest is not None:
        n = len(digest.sources)
        src_word = "source" if n == 1 else "sources"
        if digest.positive > digest.negative * 1.5:
            mix = "leans positive"
        elif digest.negative > digest.positive * 1.5:
            mix = "leans negative"
        else:
            mix = "mixed"
        phrases.append(f"sentiment {mix} across {n} {src_word}")

    # 2. Insider net stance last quarter.
    txns = getattr(result, "insider_transactions", []) or []
    delta = _build_ownership_delta(aggregate_insider_by_quarter(txns))
    if delta is not None:
        if delta.net_value > 0:
            phrases.append(f"insiders net buyers in {delta.latest_quarter}")
        elif delta.net_value < 0:
            phrases.append(f"insiders net sellers in {delta.latest_quarter}")
        else:
            phrases.append(f"insider activity balanced in {delta.latest_quarter}")

    # 3. Valuation percentile vs peers.
    percs = getattr(result, "peer_percentiles", {}) or {}
    pe_pct = percs.get("P/E")
    if pe_pct is not None:
        phrases.append(f"P/E at {float(pe_pct):.0f}th percentile vs peers")

    return phrases


def _build_story_banner_html(result: Any) -> str:
    """Build the 'story this week' synthesis banner HTML. Pure — testable.

    Returns an empty string when no descriptive facts are available, so the caller
    can splice it unconditionally.
    """
    phrases = _build_story_phrases(result)
    if not phrases:
        return ""
    sentence = "; ".join(phrases)
    sentence = sentence[0].upper() + sentence[1:] + "."
    return (
        '<div class="ws-card" style="padding:12px 16px;margin-bottom:12px;'
        'border-left:3px solid var(--ri-teal,#0F6E80);">'
        '<span style="font-size:11px;font-weight:700;letter-spacing:0.8px;'
        'text-transform:uppercase;color:var(--ri-teal,#0F6E80);">Story this week</span>'
        f'<div style="font-size:14px;color:#1A202C;margin-top:4px;">{sentence}</div>'
        '<div style="font-size:11px;color:#94A3B8;margin-top:4px;">'
        "A description of today&apos;s attributed facts — not a forecast.</div>"
        "</div>"
    )


def _render_story_banner(result: Any) -> None:
    """Render the descriptive 'story this week' banner via st.markdown."""
    import streamlit as st

    html = _build_story_banner_html(result)
    if html:
        st.markdown(html, unsafe_allow_html=True)
