"""Research Candidates tab — factual evidence ranking. RESEARCH_ONLY, no buy language."""

from __future__ import annotations

import streamlit as st

from adapters.visualization.components.formatters import status_pill_html
from adapters.visualization.data_loader import (
    load_latest_screen,
    load_screen_history,
    staleness_days,
)

_TOP_N = 15

_DISCLAIMER = (
    "Ranked by <strong>current factual evidence</strong> (valuation · quality · health) — "
    "<strong>NOT predicted returns</strong>. Prediction was tested 2006–2024 and falsified "
    "(see the Falsification Lab tab)."
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
            )[:25]
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
        universe_size = screen.get("universe_size", "?")
        as_of = screen.get("as_of", "?")
        st.markdown(
            '<div class="ws-card" style="padding:16px 20px;margin-bottom:12px;">'
            f'<p style="font-size:16px;font-weight:700;margin:0 0 6px 0;">'
            f"The screen looked at {universe_size} names — none met the evidence bar this week."
            "</p>"
            '<p style="color:#6B7280;margin:0 0 8px 0;">'
            "That is the discipline working, not failing. A ranked list appears only when "
            "names clear the pre-registered bar."
            "</p>"
            f'<span style="font-size:12px;color:#9CA3AF;">As of {as_of}</span>'
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
