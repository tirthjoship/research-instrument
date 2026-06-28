"""Stock Analysis tab — compose.py: render() entry point and decision-lead helpers."""

from __future__ import annotations

from collections.abc import Callable, MutableMapping
from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from domain.fit import FitVerdict

# Pure builder imports — no Streamlit, safe at module level
from adapters.visualization.components.radar_svg import RadarAxis
from adapters.visualization.data_loader import load_corroboration_snapshot
from adapters.visualization.tabs.stock_analysis.corroboration_section import (
    render_corroboration_section,
)
from adapters.visualization.tabs.stock_analysis.financials_section import (
    _render_growth,
    _render_health,
    _render_valuation,
)
from adapters.visualization.tabs.stock_analysis.fit_card import (
    COLOUR_KEY_HTML,
    build_fit_card_html,
    build_fit_card_view,
    build_snowflake_fit_html,
)
from adapters.visualization.tabs.stock_analysis.group import (
    MicroTile,
    build_group_shell,
)
from adapters.visualization.tabs.stock_analysis.growth_view import build_growth_panel
from adapters.visualization.tabs.stock_analysis.health_view import build_health_panel
from adapters.visualization.tabs.stock_analysis.hero import (
    build_hero_html,
    build_hero_view,
)
from adapters.visualization.tabs.stock_analysis.market_section import (
    _render_ownership,
    _render_performance,
)
from adapters.visualization.tabs.stock_analysis.profitability_view import (
    build_profitability_panel,
)
from adapters.visualization.tabs.stock_analysis.signals_section import (
    _render_sentiment,
    _render_supply_chain,
)
from adapters.visualization.tabs.stock_analysis.synthesis import (
    build_synthesis_html,
    build_synthesis_view,
)
from adapters.visualization.tabs.stock_analysis.valuation_view import (
    build_valuation_panel,
)
from adapters.visualization.tabs.stock_analysis.verdict_section import (
    _render_analyst_panel,
    _render_news_context,
    _snowflake_axes,
)
from adapters.visualization.tabs.stock_analysis.vitals import (
    build_vitals_html,
    build_vitals_view,
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

# ---------------------------------------------------------------------------
# Phase-2 answer-first top — pure assembler + Tier-2 wrapper
# ---------------------------------------------------------------------------

# Fixed navigation hues (spec D7) — category, never status
_AXIS_COLOUR: dict[str, str] = {
    "Valuation": "#d08218",
    "Quality": "#0F6E80",
    "Momentum": "#2f9e44",
    "Revision": "#5c6bc0",
    "Trend filter": "#2aa198",
    "Book fit": "#6b7d84",
}


def _snowflake_radar_axes(fit: object | None) -> list[RadarAxis]:
    """Adapt _snowflake_axes dict into a category-coloured RadarAxis list.

    Degrades to an empty list when fit is None or lacks the attributes that
    _snowflake_axes requires (e.g. ticker not present on a stub/simplified object).
    """
    if fit is None:
        return []
    try:
        axes_map = _snowflake_axes(fit)  # type: ignore[arg-type]
    except AttributeError:
        axes_map = {}
    out: list[RadarAxis] = []
    for name, value in axes_map.items():
        out.append(RadarAxis(name, float(value), _AXIS_COLOUR.get(name, "#6b7d84")))
    return out


def _fundamentals_tile_values(result: object) -> tuple[str, str, str]:
    """Compute the (valuation, growth, health) micro-tile glance values from result.

    Pure + robust: every access is guarded so a sparse result never raises;
    each value falls back to "—" when its source data is missing.
    """
    val = "—"
    try:
        percs = getattr(result, "peer_percentiles", None) or {}
        pct = percs.get("P/E")
        if pct is not None:
            val = f"{int(round(float(pct)))}th"
    except (TypeError, ValueError, AttributeError):
        val = "—"

    grow = "—"
    info = getattr(result, "info", None) or {}
    try:
        g = info.get("revenueGrowth")
        if g is not None:
            pct_g = round(float(g) * 100)
            grow = f"+{pct_g}%" if pct_g >= 0 else f"{pct_g}%"
    except (TypeError, ValueError, AttributeError):
        grow = "—"

    health = "—"
    try:
        cash = info.get("totalCash")
        debt = info.get("totalDebt")
        if cash is not None and debt is not None:
            net = float(cash) - float(debt)
            health = "net cash" if net > 0 else "net debt" if net < 0 else "—"
    except (TypeError, ValueError, AttributeError):
        health = "—"

    return val, grow, health


def build_fundamentals_inner(result: object) -> str:
    """Pure assembler: concatenate the 4 Fundamentals panels into one HTML string.

    Returns the inner content for the Fundamentals group shell (sa-fundamentals).
    No Streamlit dependency — safe to call in tests and at module level.
    """
    return (
        build_valuation_panel(result)
        + build_growth_panel(result)
        + build_profitability_panel(result)
        + build_health_panel(result)
    )


def build_top_html(result: object, fit: object | None, *, as_of: str = "") -> str:
    """Pure assembler: produce the locked D0 answer-first top as a single HTML string.

    Order: stage-wrapper → hero → synthesis → vitals → snowflake/fit → colour key
    → 3 empty group shells (sa-fundamentals, sa-market, sa-signals).

    Degrades gracefully when fit is None (no snowflake, fit-card-only fallback).
    No Streamlit dependency — safe to call in tests.
    """
    grade = getattr(fit, "evidence_grade", None) if fit is not None else None
    hero = build_hero_html(build_hero_view(result, grade=grade, as_of=as_of))
    synth = build_synthesis_html(build_synthesis_view(result))
    vit = build_vitals_html(build_vitals_view(result))
    axes = _snowflake_radar_axes(fit)
    fit_view = build_fit_card_view(fit)
    # sa-twocol-fit wrapper is always present for consistent layout;
    # radar only rendered when >= 3 axes are available.
    snowfit = (
        build_snowflake_fit_html(axes, fit_view)
        if len(axes) >= 3
        else f'<div class="sa-twocol-fit">{build_fit_card_html(fit_view)}</div>'
    )
    val_tile, grow_tile, health_tile = _fundamentals_tile_values(result)
    groups = (
        build_group_shell(
            anchor="sa-fundamentals",
            name="Fundamentals",
            grade=fit_view.grade,
            week_delta="",
            micro_tiles=[
                MicroTile("Valuation", val_tile, "#d08218"),
                MicroTile("Growth", grow_tile, "#2f9e44"),
                MicroTile("Health", health_tile, "#0F6E80"),
            ],
            inner_html=build_fundamentals_inner(result),
        )
        + build_group_shell(
            anchor="sa-market",
            name="Market",
            grade=fit_view.grade,
            week_delta="",
            micro_tiles=[
                MicroTile("Performance", "—", "#2aa198"),
                MicroTile("Ownership", "—", "#6b7d84"),
            ],
        )
        + build_group_shell(
            anchor="sa-signals",
            name="Signals",
            grade=fit_view.grade,
            week_delta="",
            micro_tiles=[
                MicroTile("Analyst", "—", "#5c6bc0"),
                MicroTile("Buzz", "—", "#5c6bc0"),
                MicroTile("Sentiment", "—", "#b91c1c"),
            ],
        )
    )
    sep = '<hr style="border:none;border-top:1px solid var(--ri-hair);margin:20px 0">'
    return (
        '<div class="sa-stage">'
        f"{hero}"
        f"{sep}{synth}"
        f"{sep}{vit}"
        f"{sep}{snowfit}"
        f"{sep}{COLOUR_KEY_HTML}"
        f"{groups}"
        "</div>"
    )


def _render_top(result: object, fit: object | None, *, as_of: str = "") -> None:
    """Tier-2 wrapper: render the answer-first top via st.markdown (lazy Streamlit import)."""
    import streamlit as st

    st.markdown(build_top_html(result, fit, as_of=as_of), unsafe_allow_html=True)


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
        # Answer-first top: hero → synthesis → vitals → snowflake/fit → colour key → group shells
        _render_top(result, fit)
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
