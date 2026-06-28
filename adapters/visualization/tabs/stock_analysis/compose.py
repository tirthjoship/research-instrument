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
from adapters.visualization.tabs.stock_analysis.analyst_view import (
    build_analyst_panel as _build_analyst_panel,
)
from adapters.visualization.tabs.stock_analysis.buzz_view import (
    build_buzz_panel as _build_buzz_panel,
)
from adapters.visualization.tabs.stock_analysis.corroboration_section import (
    render_corroboration_section,
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
from adapters.visualization.tabs.stock_analysis.ownership_view import (
    build_ownership_panel as _build_ownership_panel,
)
from adapters.visualization.tabs.stock_analysis.performance_view import (
    build_performance_panel as _build_performance_panel,
)
from adapters.visualization.tabs.stock_analysis.profitability_view import (
    build_profitability_panel,
)
from adapters.visualization.tabs.stock_analysis.sentiment_view import (
    build_sentiment_panel as _build_sentiment_panel,
)
from adapters.visualization.tabs.stock_analysis.supply_chain_view import (
    build_supply_chain_panel as _build_supply_chain_panel,
)
from adapters.visualization.tabs.stock_analysis.synthesis import (
    build_synthesis_html,
    build_synthesis_view,
)
from adapters.visualization.tabs.stock_analysis.valuation_view import (
    build_valuation_panel,
)
from adapters.visualization.tabs.stock_analysis.verdict_section import (
    _render_news_context,
    _snowflake_axes,
)
from adapters.visualization.tabs.stock_analysis.vitals import (
    build_vitals_html,
    build_vitals_view,
)

_SECTION_LABELS: list[str] = [
    "Hero",
    "Fundamentals",
    "Market",
    "Signals",
    "Corroboration",
]

_SECTION_ANCHORS: dict[str, str] = {
    "Hero": "sa-hero",
    "Fundamentals": "sa-fundamentals",
    "Market": "sa-market",
    "Signals": "sa-signals",
    "Corroboration": "sa-corroboration",
}

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


def _market_tile_values(result: object) -> tuple[str, str]:
    """Compute (performance_1y, ownership_inst) micro-tile glance values from result.

    Pure + robust: guarded access; falls back to "—" when data is missing.
    """
    info = getattr(result, "info", None) or {}

    perf = "—"
    try:
        chg = info.get("52WeekChange")
        if chg is not None:
            pct = round(float(chg) * 100)
            perf = f"+{pct}%" if pct >= 0 else f"{pct}%"
    except (TypeError, ValueError, AttributeError):
        perf = "—"

    own = "—"
    try:
        inst = info.get("heldPercentInstitutions")
        if inst is not None:
            own = f"{round(float(inst) * 100)}%"
    except (TypeError, ValueError, AttributeError):
        own = "—"

    return perf, own


def _signals_tile_values(result: object) -> tuple[str, str, str]:
    """Compute (analyst_consensus, sentiment_ic, buzz_sources) micro-tile values.

    Pure + robust: guarded access; falls back to "—" when data is missing.
    Sentiment IC is always "IC 0" (the hypothesis was tested and FALSIFIED).
    """
    analyst = "—"
    try:
        panel = getattr(result, "analyst_panel", None)
        if panel is not None:
            rating = getattr(panel, "mean_rating", None)
            if rating is not None:
                analyst = f"{float(rating):.1f}"
    except (TypeError, ValueError, AttributeError):
        analyst = "—"

    sentiment_ic = "IC 0"

    buzz = "—"
    try:
        signals = getattr(result, "buzz_signals", None) or []
        n = len(list(signals))
        if n > 0:
            word = "src" if n == 1 else "srcs"
            buzz = f"{n} {word}"
    except (TypeError, ValueError, AttributeError):
        buzz = "—"

    return analyst, sentiment_ic, buzz


# D12 falsified banner — shown at the top of the Signals group.
# Inline-styled amber/red. Must not contain any FORBIDDEN_WORDS
# ({alpha, buy, conviction, outperform, predict, sell, winner}).
_D12_FALSIFIED_BANNER = (
    '<div style="background:#FEF3C7;border-left:4px solid #D97706;'
    "padding:8px 14px;border-radius:4px;margin-bottom:10px;"
    'font-size:12px;color:#92400E;">'
    "<strong>Context only — not a signal:</strong> "
    "These indicators were tested as return signals and FALSIFIED "
    "(IC ≈ 0 across 2006–2024). They are shown here as context only, "
    "never as a trade signal. See the Trust tab."
    "</div>"
)


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


def build_market_inner(result: object) -> str:
    """Pure assembler: concatenate the 2 Market panels into one HTML string.

    Returns the inner content for the Market group shell (sa-market).
    No Streamlit dependency — safe to call in tests and at module level.
    """
    return _build_performance_panel(result) + _build_ownership_panel(result)


def build_signals_inner(result: object) -> str:
    """Pure assembler: D12 falsified banner + 4 Signals panels into one HTML string.

    Returns the inner content for the Signals group shell (sa-signals).
    The banner makes clear these indicators were FALSIFIED as return signals.
    No Streamlit dependency — safe to call in tests and at module level.
    """
    return (
        _D12_FALSIFIED_BANNER
        + _build_analyst_panel(result)
        + _build_buzz_panel(result)
        + _build_sentiment_panel(result)
        + _build_supply_chain_panel(result)
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
    perf_tile, own_tile = _market_tile_values(result)
    analyst_tile, sentiment_tile, buzz_tile = _signals_tile_values(result)
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
                MicroTile("Performance", perf_tile, "#2aa198"),
                MicroTile("Ownership", own_tile, "#6b7d84"),
            ],
            inner_html=build_market_inner(result),
        )
        + build_group_shell(
            anchor="sa-signals",
            name="Signals",
            grade=fit_view.grade,
            week_delta="",
            micro_tiles=[
                MicroTile("Analyst", analyst_tile, "#5c6bc0"),
                MicroTile("Buzz", buzz_tile, "#5c6bc0"),
                MicroTile("Sentiment", sentiment_tile, "#b91c1c"),
            ],
            inner_html=build_signals_inner(result),
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


def _post_top_render_plan() -> list[str]:
    """Return the ordered list of section names rendered AFTER _render_top().

    Pure helper — no Streamlit, safe to call in tests.
    Sections that live inside the sa-* group shells (build_top_html) must NOT
    appear here; only the two sections not covered by the groups are kept:
    news_context (verdict_section, not in any group) and
    corroboration (its own section below the groups).
    """
    return ["news_context", "corroboration"]


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
                f'<a class="section-chip" href="#{_SECTION_ANCHORS[name]}"'
                f' style="text-decoration:none;">{i}</a>'
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

        now = datetime.now(timezone.utc)
        fit = _ensure_fit_cached(
            st.session_state,
            fit_key,
            lambda: gather_and_assess(
                ticker=lookup_key,
                reports_dir="data/reports",
                summary_path="data/personal/brief_summary.json",
                holdings_path="data/personal/holdings.csv",
                beta_fn=default_beta_fn,
                as_of=now,
                systematic_share_threshold=market_systematic_share_threshold(),
            ),
        )
        # Answer-first top: hero → synthesis → vitals → snowflake/fit → colour key → group shells
        # Deep-dive sections (valuation, growth, health, performance, ownership,
        # sentiment, supply_chain, analyst_panel) now live inside the sa-* group
        # shells rendered by build_top_html — do NOT re-render them flat here.
        _render_top(result, fit, as_of=now.strftime("%b %d %Y"))
        _render_news_context(result)
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
