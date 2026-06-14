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

# Canonical factor order shown in every rich card.  If a factor is absent
# from the candidate's factor_scores list it renders as DATA-GAP.
_CANONICAL_FACTORS: tuple[str, ...] = ("momentum", "revision", "quality", "value")

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

        # --- Build funnel stages and verdict headline ---
        # 4-stage when diagnostics available; honest neutral fallback for old cached JSON.
        if diag is not None:
            funnel_stages: list[tuple[str, int]] = [
                (tooltip("Universe"), diag.scanned),
                (tooltip("Had history"), diag.had_history),
                (tooltip("Above trend"), diag.above_trend),
                (tooltip("Cleared the bar"), diag.cleared),
            ]
            verdict = classify_screen(diag, _SCREEN_COVERAGE_FLOOR)

            # Verdict headline (truthful, driven by domain logic)
            if verdict == ScreenVerdict.UNDER_POWERED:
                headline = (
                    f'<div style="color:#DC2626;font-weight:600;font-size:15px;margin-bottom:8px;">'
                    f"&#9888; Screen under-powered — only {diag.had_history} of {diag.scanned} "
                    "had usable price history"
                    "</div>"
                )
            else:
                # EARNED_ABSTENTION: all names scored, none cleared the bar
                headline = (
                    '<div style="color:#16A34A;font-weight:600;font-size:15px;margin-bottom:8px;">'
                    "&#10003; Working as designed — scanned &amp; scored, none cleared the bar"
                    "</div>"
                )
        else:
            # Old cached JSON without diagnostics: we do NOT know whether names were
            # scored. Do NOT fabricate a verdict or render a green "working as designed".
            # Show only the numbers we actually have and a neutral advisory.
            funnel_stages = [
                (tooltip("Universe"), universe_size),
                (tooltip("Cleared the bar"), 0),
            ]
            headline = ""

        st.markdown(
            '<div class="ri-sec">Screen result</div>',
            unsafe_allow_html=True,
        )
        if diag is None:
            # Neutral, honest fallback — no verdict claim, no color
            st.markdown(
                '<div style="color:#717885;font-size:14px;margin-bottom:8px;">'
                "Screen diagnostics unavailable for this older result — "
                "re-run the screen for a full readout."
                "</div>",
                unsafe_allow_html=True,
            )
        elif headline:
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
    raw_universe_size = screen.get("universe_size", "?")
    first_label = screen.get("candidates", [{}])[0].get("label", "RESEARCH_ONLY")

    # --- HAS_CANDIDATES headline: "{cleared} cleared, of {scanned} scanned" ---
    # Prefer real diagnostics counts; fall back to len(candidates)/universe_size.
    raw_diag_has = screen.get("diagnostics")
    if isinstance(raw_diag_has, dict):
        try:
            _cleared = int(raw_diag_has["cleared"])
            _scanned = int(raw_diag_has["scanned"])
            cleared_headline = f"{_cleared} cleared, of {_scanned} scanned"
        except (KeyError, ValueError, TypeError):
            cleared_headline = (
                f"{len(candidates)} cleared, of {raw_universe_size} scanned"
            )
    else:
        cleared_headline = f"{len(candidates)} cleared, of {raw_universe_size} scanned"
    st.markdown(
        f'<div style="font-weight:600;font-size:15px;margin-bottom:4px;">'
        f"{cleared_headline}"
        "</div>",
        unsafe_allow_html=True,
    )

    st.caption(
        f"Top {len(candidates)} of {raw_universe_size} by factual composite · "
        f"as of {as_of} · label: {first_label}"
    )

    rich_candidates = candidates[:10]
    compact_candidates = candidates[10:]

    for i, c in enumerate(rich_candidates, start=1):
        ticker = c.get("ticker", "?")
        composite = c.get("composite", 0.0)
        why = c.get("why", "")
        label = c.get("label", "RESEARCH_ONLY")
        pill = status_pill_html("neutral", label)

        # Build a lookup of factor data keyed by name
        raw_factors = c.get("factor_scores", [])
        factor_by_name: dict[str, dict[str, object]] = {
            f.get("name", ""): f for f in raw_factors if isinstance(f, dict)
        }

        # --- Factor rows (all 4 canonical factors, DATA-GAP for missing) ---
        factor_rows_html = ""
        for fname in _CANONICAL_FACTORS:
            fd = factor_by_name.get(fname)
            raw_value: object = fd.get("value") if fd else None
            raw_pct: object = fd.get("percentile") if fd else None

            if raw_value is None or raw_pct is None:
                # DATA-GAP: factor absent or None — never fabricate a number
                factor_rows_html += (
                    f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">'
                    f'<span style="width:80px;font-size:12px;color:#6B7280;">{fname}</span>'
                    f'<span style="font-size:12px;color:#9CA3AF;font-style:italic;">DATA-GAP</span>'
                    f"</div>"
                )
            else:
                val = float(raw_value)  # type: ignore[arg-type]
                pct_frac = float(raw_pct)  # type: ignore[arg-type]
                pct_display = pct_frac * 100  # 0–1 fraction → 0–100
                val_color = "#16A34A" if val >= 0 else "#DC2626"
                sign = "+" if val >= 0 else ""
                # Diverging bar: width proportional to abs(val), capped at ±3σ
                bar_pct = min(100.0, abs(val) / 3.0 * 100)
                if val >= 0:
                    bar_html = (
                        f'<div style="display:inline-block;width:60px;height:8px;'
                        f'background:#E5E7EB;border-radius:4px;vertical-align:middle;">'
                        f'<div style="width:{bar_pct:.0f}%;height:8px;background:#16A34A;'
                        f'border-radius:4px;"></div></div>'
                    )
                else:
                    bar_html = (
                        f'<div style="display:inline-block;width:60px;height:8px;'
                        f"background:#E5E7EB;border-radius:4px;vertical-align:middle;"
                        f'direction:rtl;">'
                        f'<div style="width:{bar_pct:.0f}%;height:8px;background:#DC2626;'
                        f'border-radius:4px;"></div></div>'
                    )
                factor_rows_html += (
                    f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">'
                    f'<span style="width:80px;font-size:12px;color:#6B7280;">{fname}</span>'
                    f'<span style="font-size:12px;font-weight:600;color:{val_color};'
                    f'min-width:40px;">{sign}{val:.2f}</span>'
                    f"{bar_html}"
                    f'<span style="font-size:11px;color:#9CA3AF;min-width:52px;">'
                    f"p{pct_display:.0f}/100</span>"
                    f"</div>"
                )

        # --- "What this tells you" research read ---
        # Derive the top positive factor for the read line (highest z-value present).
        best_factor: str | None = None
        best_val: float = -999.0
        best_pct_display: float = 0.0
        for fname in _CANONICAL_FACTORS:
            fd = factor_by_name.get(fname)
            if fd is None:
                continue
            rv: object = fd.get("value")
            rp: object = fd.get("percentile")
            if rv is None or rp is None:
                continue
            fv = float(rv)  # type: ignore[arg-type]
            if fv > best_val:
                best_val = fv
                best_factor = fname
                best_pct_display = float(rp) * 100  # type: ignore[arg-type]

        if best_factor is not None and best_val > 0:
            research_read = (
                f"Strongest signal on <strong>{best_factor}</strong> "
                f"(top {100 - best_pct_display:.0f}% of universe) — {why}. "
                "A reason to investigate this name, not a return forecast."
            )
        else:
            research_read = (
                f"{why} — check the Stock Analysis tab for a full evidence read."
            )

        # --- "Do next" investigation step ---
        do_next = (
            "Check next earnings date, read the last two earnings call transcripts, "
            "and verify why the stock appears cheap or strong on these factors — "
            "look for a structural reason before acting."
        )

        st.markdown(
            f'<div class="ws-card" style="padding:14px 16px;margin-bottom:10px;">'
            # Header: ticker + composite (labelled as research-priority score, not a forecast)
            f'<div style="display:flex;align-items:baseline;gap:8px;margin-bottom:8px;">'
            f'<strong style="font-size:16px;">{i}. {ticker}</strong>'
            f"{pill}"
            f'<span style="font-size:12px;color:#6B7280;margin-left:4px;">'
            f"research-priority score {composite:.2f} &nbsp;"
            f'<span style="font-style:italic;">(not a forecast)</span></span>'
            f"</div>"
            # Factor rows
            f"{factor_rows_html}"
            # Divider
            f'<div style="border-top:1px solid #E5E7EB;margin:8px 0;"></div>'
            # What this tells you
            f'<div style="margin-bottom:6px;">'
            f'<span style="font-size:12px;font-weight:600;color:#374151;">'
            f"What this tells you:</span> "
            f'<span style="font-size:13px;color:#4B5563;">{research_read}</span>'
            f"</div>"
            # Do next
            f"<div>"
            f'<span style="font-size:12px;font-weight:600;color:#374151;">'
            f"Do next:</span> "
            f'<span style="font-size:13px;color:#4B5563;">{do_next}</span>'
            f"</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    # Compact list for candidates beyond the top 10
    if compact_candidates:
        st.markdown(
            '<div style="font-size:13px;font-weight:600;color:#374151;margin:12px 0 6px 0;">'
            f"Remaining {len(compact_candidates)} candidates — open in Stock Analysis tab for full read"
            "</div>",
            unsafe_allow_html=True,
        )
        for c in compact_candidates:
            ticker = c.get("ticker", "?")
            composite = c.get("composite", 0.0)
            raw_factors = c.get("factor_scores", [])
            # Top factor by value (skip missing)
            top_f: str = "—"
            top_v: float = -999.0
            for fd in raw_factors:
                if not isinstance(fd, dict):
                    continue
                rv2: object = fd.get("value")
                if rv2 is None:
                    continue
                fv2 = float(rv2)  # type: ignore[arg-type]
                if fv2 > top_v:
                    top_v = fv2
                    top_f = str(fd.get("name", "?"))
            st.markdown(
                f'<div style="font-size:13px;color:#4B5563;padding:3px 0;">'
                f"<strong>{ticker}</strong> &nbsp;·&nbsp; score {composite:.2f} "
                f"&nbsp;·&nbsp; top factor: {top_f}"
                f"</div>",
                unsafe_allow_html=True,
            )

    _render_history_and_upload(reports_dir)
