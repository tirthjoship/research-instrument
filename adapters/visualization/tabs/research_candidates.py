"""Research Candidates tab — factual evidence ranking. RESEARCH_ONLY."""

from __future__ import annotations

import streamlit as st

from adapters.visualization.components.formatters import status_pill_html
from adapters.visualization.components.funnel import render_funnel
from adapters.visualization.components.tooltip import tooltip
from adapters.visualization.data_loader import (
    load_latest_screen,
    load_screen_history,
    staleness_days,
)
from domain.screen_diagnostics import ScreenDiagnostics, ScreenVerdict, classify_screen

_SCREEN_COVERAGE_FLOOR = 0.5  # default; no key in us.yaml yet

_TOP_N = 15

_DISCLAIMER = (
    "Ranked by <strong>current factual evidence</strong> (valuation · quality · health) — "
    "<strong>NOT forecast returns</strong>. The return-forecast hypothesis was tested 2006–2024 and falsified "
    "(see the Trust tab)."
)


def _render_history_and_upload(reports_dir: str) -> None:
    """Render Screen history strip and 'Check your own list' upload section.

    Called on both the abstention/no-candidates path AND the normal candidates path
    so that the upload scoreboard is always reachable.
    """
    hist = load_screen_history(reports_dir)
    if hist:
        st.divider()
        st.markdown("#### Screen history")
        hist_rows = [
            {
                "Date": h["as_of"],
                "Universe": h["universe_size"],
                "Passed": h["n_candidates"],
                "Abstained": h["abstained"],
            }
            for h in hist
        ]
        st.dataframe(hist_rows, hide_index=True)

    st.divider()
    st.markdown("#### Check your own list")
    st.markdown(
        '<div style="color:#5C6370;font-size:14px;">Paste tickers or upload a '
        "CSV — each name gets an evidence grade and a fit check against your "
        "book. Capped at 25 names per run (live data fetch per name).</div>",
        unsafe_allow_html=True,
    )
    text = st.text_area(
        "Tickers", placeholder="NVDA, AAPL, KO", label_visibility="collapsed"
    )
    uploaded = st.file_uploader("or upload CSV", type=["csv"])
    if st.button("Run the check", type="primary"):
        from application.batch_fit_use_case import (
            MAX_TICKERS,
            batch_fit,
            default_fit_fn,
            parse_csv_tickers,
            parse_tickers,
        )

        tickers = parse_tickers(text or "")
        if uploaded is not None:
            tickers = (
                tickers
                + [
                    t
                    for t in parse_csv_tickers(
                        uploaded.getvalue().decode("utf-8", "replace")
                    )
                    if t not in tickers
                ]
            )[:MAX_TICKERS]
        if not tickers:
            st.warning("No valid tickers found — paste e.g. NVDA, AAPL.")
        else:
            key = "batchfit_" + ",".join(tickers)
            if key not in st.session_state:
                bar = st.progress(0.0, text="Starting…")

                def _update_progress(frac: float, t: str) -> None:
                    bar.progress(frac, text=f"Checking {t}…")

                rows = batch_fit(
                    tickers,
                    fit_fn=default_fit_fn,
                    progress=_update_progress,
                )
                bar.empty()
                st.session_state[key] = rows
            from adapters.visualization.components.scorecard import render_scorecard

            render_scorecard(st.session_state[key])


def render(reports_dir: str = "data/reports") -> None:
    st.subheader("Research Candidates")
    st.markdown(
        '<div style="color:#64748B;font-size:14px;margin-bottom:16px;">'
        "The evidence screen's ranked research list — only names that cleared the locked bar."
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="ws-card" style="padding:10px 16px;margin-bottom:12px;">'
        f"{_DISCLAIMER}"
        "</div>",
        unsafe_allow_html=True,
    )

    screen = load_latest_screen(reports_dir)
    if screen is None:
        st.warning(
            "No screen report found. Run "
            "`python -m application.cli screen-candidates` to generate one."
        )
        return

    days = staleness_days(screen.get("as_of", ""))
    if days is not None and days > 8:
        st.error(f"Screen is {days} days old — re-run `screen-candidates`.")

    candidates = screen.get("candidates", [])[:_TOP_N]

    # Treat empty candidates as abstention regardless of the abstained flag.
    # Real data pattern: abstained=false but candidates=[] (eligibility filtered all out).
    if not candidates:
        raw_universe = screen.get("universe_size")
        universe_size: int = (
            int(raw_universe) if isinstance(raw_universe, (int, float)) else 0
        )
        as_of = screen.get("as_of", "?")

        # --- Parse diagnostics from persisted JSON (4 ints, present from this sprint) ---
        diag: ScreenDiagnostics | None = None
        raw_diag = screen.get("diagnostics")
        if isinstance(raw_diag, dict):
            try:
                diag = ScreenDiagnostics(
                    scanned=int(raw_diag["scanned"]),
                    had_history=int(raw_diag["had_history"]),
                    above_trend=int(raw_diag["above_trend"]),
                    cleared=int(raw_diag["cleared"]),
                )
            except (KeyError, ValueError, TypeError):
                diag = None

        # --- Build funnel stages ---
        # 4-stage when diagnostics available; 2-stage fallback for old cached JSON.
        if diag is not None:
            funnel_stages: list[tuple[str, int]] = [
                (tooltip("Universe"), diag.scanned),
                (tooltip("Had history"), diag.had_history),
                (tooltip("Above trend"), diag.above_trend),
                (tooltip("Cleared the bar"), diag.cleared),
            ]
            verdict = classify_screen(diag, _SCREEN_COVERAGE_FLOOR)
        else:
            # Graceful fallback: synthesize minimal diagnostics from universe_size.
            # cleared=0 by definition (no candidates), had_history = universe_size
            # (we don't know better — this path only fires for pre-threading JSON).
            # Use EARNED_ABSTENTION as the conservative, honest default: we cannot
            # distinguish UNDER_POWERED from EARNED_ABSTENTION without the counts.
            fallback_diag = ScreenDiagnostics(
                scanned=universe_size,
                had_history=universe_size,
                above_trend=0,
                cleared=0,
            )
            funnel_stages = [
                (tooltip("Universe"), universe_size),
                (tooltip("Cleared the bar"), 0),
            ]
            verdict = classify_screen(fallback_diag, _SCREEN_COVERAGE_FLOOR)

        # --- Verdict headline (truthful, driven by domain logic) ---
        if verdict == ScreenVerdict.UNDER_POWERED:
            assert diag is not None  # HAS_CANDIDATES is impossible here (cleared=0)
            headline = (
                f'<div style="color:#DC2626;font-weight:600;font-size:15px;margin-bottom:8px;">'
                f"&#9888; Screen under-powered — only {diag.had_history} of {diag.scanned} "
                "had usable price history"
                "</div>"
            )
        elif verdict == ScreenVerdict.EARNED_ABSTENTION:
            headline = (
                '<div style="color:#16A34A;font-weight:600;font-size:15px;margin-bottom:8px;">'
                "&#10003; Working as designed — scanned &amp; scored, none cleared the bar"
                "</div>"
            )
        else:
            # HAS_CANDIDATES cannot reach here (candidates is empty), but be safe.
            headline = ""

        st.markdown(
            '<div class="ri-sec">Screen result</div>',
            unsafe_allow_html=True,
        )
        if headline:
            st.markdown(headline, unsafe_allow_html=True)
        st.markdown(render_funnel(funnel_stages), unsafe_allow_html=True)
        st.markdown(
            f'<div style="color:var(--ri-muted,#717885);font-size:13px;margin-top:-8px;margin-bottom:16px;">'
            f"RESEARCH_ONLY &nbsp;·&nbsp; As of {as_of}"
            "</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "**Want to research a specific stock anyway?** "
            "Open the **Stock Analysis** tab — type any ticker for a full evidence + portfolio-fit read."
        )
        # History strip + upload section still render on abstention weeks so the
        # scorecard feature is reachable even when the weekly screen abstains.
        _render_history_and_upload(reports_dir)
        return

    as_of = screen.get("as_of", "?")
    universe_size = screen.get("universe_size", "?")
    first_label = screen.get("candidates", [{}])[0].get("label", "RESEARCH_ONLY")
    st.caption(
        f"Top {len(candidates)} of {universe_size} by factual composite · "
        f"as of {as_of} · label: {first_label}"
    )

    for i, c in enumerate(candidates, start=1):
        factors = c.get("factor_scores", [])
        # percentile is a 0–1 FRACTION in the screen JSON — multiply by 100 for display
        chips = " · ".join(
            f"{f.get('name', '?')} p{f.get('percentile', 0) * 100:.0f}" for f in factors
        )
        ticker = c.get("ticker", "?")
        composite = c.get("composite", 0)
        why = c.get("why", "")
        label = c.get("label", "RESEARCH_ONLY")
        pill = status_pill_html("neutral", label)
        st.markdown(
            f'<div class="ws-card" style="padding:12px 16px;margin-bottom:8px;">'
            f"<strong>{i}. {ticker}</strong> — composite {composite:.2f} {pill}<br>"
            f'<span style="color:#6B7280;font-size:13px;">{chips}</span><br>'
            f"<em>{why}</em> — research it in the Stock Analysis tab."
            "</div>",
            unsafe_allow_html=True,
        )

    _render_history_and_upload(reports_dir)
