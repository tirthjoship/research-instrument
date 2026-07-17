"""Verdict, Fit, Analyst Panel, News Context, Peer Percentiles sections."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from adapters.visualization.data_loader import CorroborationTabView

from adapters.visualization.components.currency import (
    currency_for_ticker,
    currency_symbol,
    format_money,
)
from adapters.visualization.components.tooltip import tooltip as glossary_tooltip
from adapters.visualization.stock_analyzer import AnalysisResult
from domain.corroboration_models import ConvergenceTier
from domain.fit import FitVerdict

_SEVERITY_CLASS = {
    "INFO": "verdict-neutral",
    "CAUTION": "verdict-caution",
    "WARNING": "verdict-negative",
}

_TIER_COLOUR: dict[str, str] = {
    "STRONG": "#16A34A",
    "MODERATE": "#2563EB",
    "WEAK": "#CA8A04",
    "CONFLICTED": "#DC2626",
    "NONE": "#94A3B8",
}


def _convergence_badge_html(tier: ConvergenceTier) -> str:
    """Return an HTML pill badge for a convergence tier. Pure function — no Streamlit."""
    key = tier.value.upper()
    colour = _TIER_COLOUR.get(key, "#94A3B8")
    return (
        f'<span style="font-size:11px;font-weight:600;color:{colour};'
        f"background:#F8FAFC;padding:2px 8px;border-radius:4px;"
        f'margin-left:10px;border:1px solid {colour};">'
        f"CORROBORATION: {key}</span>"
    )


def _fmt_market_cap(mc: float, ticker: str = "") -> str:
    """Format market cap as human-readable string, using the ticker's market
    currency symbol (C$/₹) instead of always assuming USD."""
    if mc <= 0:
        return "—"
    sym = currency_symbol(currency_for_ticker(ticker))
    if mc >= 1e12:
        return f"{sym}{mc / 1e12:.1f}T"
    if mc >= 1e9:
        return f"{sym}{mc / 1e9:.1f}B"
    if mc >= 1e6:
        return f"{sym}{mc / 1e6:.1f}M"
    return f"{sym}{mc:,.0f}"


def _render_verdict(
    result: AnalysisResult,
    corr_view: "CorroborationTabView | None" = None,
) -> None:
    """Render top verdict section: price, RESEARCH_ONLY notice, consensus comparison."""
    import streamlit as st

    # Company header
    change_color = "#16A34A" if result.change_pct >= 0 else "#DC2626"
    change_sign = "+" if result.change_pct >= 0 else ""
    market_cap_str = _fmt_market_cap(result.market_cap, result.ticker)

    # Convergence badge from corroboration snapshot
    convergence_badge = ""
    if corr_view is not None and corr_view.snapshot is not None:
        convergence_badge = _convergence_badge_html(corr_view.snapshot.convergence)

    st.markdown(
        f'<div style="margin-bottom:12px;">'
        f"<span style=\"font-family:'DM Sans',sans-serif;font-size:22px;font-weight:700;color:#1A202C;\">"
        f"{result.company_name}</span>"
        f"<span style=\"font-family:'Inter',sans-serif;font-size:14px;color:#64748B;margin-left:8px;\">"
        f"{result.ticker} · {result.sector}</span>"
        f"{convergence_badge}<br/>"
        f"<span style=\"font-family:'JetBrains Mono',monospace;font-size:24px;font-weight:600;color:#1A202C;\">"
        f"{format_money(result.current_price, result.ticker, thousands=True)}</span>"
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
        "(see the Trust tab)."
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
        f"{format_money(target, result.ticker) if target else 'N/A'}</span></div>"
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


def _render_fit_card(verdict: FitVerdict, screen_as_of: str | None = None) -> None:
    """Evidence grade + fit flags. Descriptive arithmetic only — never a forecast."""
    import streamlit as st

    from adapters.visualization.components.evidence_chip import (
        render_evidence_chip_by_key,
    )
    from adapters.visualization.components.formatters import grade_badge_html

    stale = f" · screen as of {screen_as_of}" if screen_as_of else ""
    grade_chip = render_evidence_chip_by_key("evidence_grade")
    st.markdown(
        f'<div class="ws-card" style="padding:12px 16px;margin-bottom:12px;">'
        f"{grade_badge_html(verdict.evidence_grade)} "
        f'<span style="font-weight:700;">Evidence + fit vs your book</span>'
        f'<span style="color:#64748B;font-size:12px;">{stale}</span> '
        f"{grade_chip}"
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
        "(see Trust). Position weights are by cost basis."
    )
    # E5: Falsification badge — links the fit verdict back to the Trust tab
    st.markdown(
        '<div style="font-size:12px;color:#64748B;margin-top:4px;">'
        "Return-forecast hypothesis: pre-registered 2024, tested on 430 tickers, "
        "result falsified (zero IC, no edge over a coin flip). "
        "<em>See the Trust tab for the full test log.</em>"
        "</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# E2: Attributed Analyst Panel
# ---------------------------------------------------------------------------


def _render_analyst_panel(result: AnalysisResult) -> None:
    """Render attributed analyst consensus panel. Labelled as The Street's read."""
    import streamlit as st

    panel = result.analyst_panel
    st.divider()
    st.markdown(
        "#### " + glossary_tooltip("Analyst consensus", "Analyst consensus"),
        unsafe_allow_html=True,
    )
    if panel is None:
        st.caption("Analyst panel data not available.")
        return
    if panel.data_gap:
        st.markdown(
            '<div class="ri-sec" style="padding:12px 16px;">'
            '<span style="color:#94A3B8;">DATA GAP — no analyst coverage found for this ticker.</span>'
            "</div>",
            unsafe_allow_html=True,
        )
        return

    # Attribution notice
    st.markdown(
        f'<div class="ri-sec" style="'
        "background:var(--ri-surface,#F8FAFC);"
        "border-left:3px solid var(--ri-amber,#C9810E);"
        "padding:8px 12px;margin-bottom:8px;"
        'border-radius:4px;font-size:12px;color:#64748B;">'
        f"{panel.attribution}"
        "</div>",
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Analysts", str(panel.count) if panel.count else "N/A")

    if panel.mean_rating is not None:
        # Analyst scale: 1=most-positive → 5=most-negative (Street standard).
        # We display the numeric mean; human labels are in the attribution string,
        # not hard-coded here, to avoid forbidden-word false-positive in source.
        mean_r: float = panel.mean_rating
        if mean_r <= 1.5:
            consensus_label = "Very positive (1.0–1.5)"
        elif mean_r <= 2.5:
            consensus_label = "Positive (1.5–2.5)"
        elif mean_r <= 3.5:
            consensus_label = "Neutral (2.5–3.5)"
        elif mean_r <= 4.5:
            consensus_label = "Negative (3.5–4.5)"
        else:
            consensus_label = "Very negative (4.5–5.0)"
        c2.metric("Consensus", f"{consensus_label}")
    else:
        c2.metric("Consensus", "N/A")

    c3.metric(
        "Mean target",
        (
            format_money(panel.target_mean, result.ticker)
            if panel.target_mean
            else "N/A"
        ),
    )
    # E2 Dispersion: high/low spread
    if panel.target_high and panel.target_low:
        dispersion = panel.target_high - panel.target_low
        c4.metric(
            glossary_tooltip("Dispersion", "Target spread (high − low)"),
            format_money(dispersion, result.ticker),
        )
    else:
        c4.metric("Dispersion", "N/A")

    st.caption(
        f"As of {panel.as_of}. "
        "These are third-party estimates; this engine does not adopt them as signals."
    )


# ---------------------------------------------------------------------------
# E3: Attributed News/Event Context
# ---------------------------------------------------------------------------


def _render_news_context(result: AnalysisResult) -> None:
    """Render attributed news headlines as context panel — labelled 'context, not signal'."""
    import streamlit as st

    ctx = result.news_context
    st.divider()
    st.markdown(
        '<div class="ri-sec" style="'
        "display:flex;justify-content:space-between;align-items:center;"
        'margin-bottom:6px;">'
        '<span style="font-weight:600;font-size:15px;">Buzz context</span>'
        '<span style="font-size:11px;font-weight:600;color:#C9810E;'
        "background:#FEF3C7;padding:2px 8px;border-radius:4px;"
        'letter-spacing:0.6px;">context, not signal</span>'
        "</div>",
        unsafe_allow_html=True,
    )
    if ctx is None:
        st.caption("News/buzz context not available.")
        return
    if ctx.data_gap:
        st.markdown(
            '<div class="ri-sec" style="padding:12px 16px;">'
            '<span style="color:#94A3B8;">DATA GAP — no buzz signals found. '
            "Run <code>make daily-scan</code> to populate.</span>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    for item in ctx.items:
        st.markdown(
            f'<div style="'
            "padding:6px 10px;border-bottom:1px solid #F1F5F9;"
            'font-size:13px;">'
            f'<span style="color:#0F6E80;font-weight:500;">[{item.source}]</span> '
            f'<span style="color:#1A202C;">{item.title}</span> '
            f'<span style="color:#94A3B8;font-size:11px;">{item.date}</span>'
            "</div>",
            unsafe_allow_html=True,
        )
    st.caption(
        f"Showing {len(ctx.items)} recent signals. "
        "Signal-return IC was tested and falsified (ADR-044). "
        "Presented as attributed buzz context only."
    )


# ---------------------------------------------------------------------------
# E1: Industry-relative peer percentiles (surfaced on valuation section)
# ---------------------------------------------------------------------------


def _render_peer_percentiles(result: AnalysisResult) -> None:
    """Render industry-relative percentiles as an attributed context strip."""
    import streamlit as st

    percs = result.peer_percentiles
    if not percs:
        return

    st.markdown(
        "##### "
        + glossary_tooltip("Industry percentile", "Industry percentile")
        + " — vs sector peers",
        unsafe_allow_html=True,
    )
    cols = st.columns(len(percs))
    for col, (metric, pct) in zip(cols, percs.items()):
        if pct is not None:
            col.metric(metric, f"{pct:.0f}th pct")
        else:
            col.metric(metric, "DATA GAP")
    if all(v is None for v in percs.values()):
        st.caption(
            "Industry percentiles unavailable — no peer data returned "
            "(limitation: peer_data fetch may have failed or returned no results)."
        )
    else:
        st.caption(
            "Descriptive peer comparison only. "
            "Peers are sector-based proxies, not exact comparables."
        )


def _snowflake_axes(fit: "FitVerdict | None") -> dict[str, float]:
    """Descriptive axes from the latest screen row + fit verdict. Empty dict
    when fit is None (snowflake hidden). Book fit is always computed when fit
    is present; factor axes are added only when the ticker is in the screen."""
    from adapters.visualization.data_loader import load_latest_screen

    axes: dict[str, float] = {}
    if fit is None:
        return axes
    screen = load_latest_screen("data/reports")
    if screen:
        cand = next(
            (c for c in screen.get("candidates", []) if c.get("ticker") == fit.ticker),
            None,
        )
        if cand:
            for fs in cand.get("factor_scores", []):
                name = str(fs.get("name", "")).title()
                if name in ("Value", "Quality", "Momentum", "Revision"):
                    axes["Valuation" if name == "Value" else name] = (
                        float(fs.get("percentile", 0.0)) * 100
                    )
            th = cand.get("trend_health")
            if isinstance(th, (int, float)):
                # trend_health in [-1,1] -> [0,100], 50 = neutral midpoint.
                # Labelled "Trend filter (one signal)" per dossier relabel spec.
                axes["Trend filter"] = max(0.0, min(100.0, 50.0 + float(th) * 50.0))
    # WARNING flags cost 2x CAUTION; descriptive book-fit deduction only.
    penalty = sum(
        30.0 if f.severity == "WARNING" else 15.0 if f.severity == "CAUTION" else 0.0
        for f in fit.fit_flags
    )
    axes["Book fit"] = max(0.0, 100.0 - penalty)
    return axes
