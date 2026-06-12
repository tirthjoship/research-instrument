"""Weekly Brief tab — the decision cockpit. Renders brief_summary.json."""

from __future__ import annotations

import streamlit as st

from adapters.visualization.components.formatters import status_pill_html
from adapters.visualization.components.metrics import render_verdict_card
from adapters.visualization.data_loader import (
    load_adherence_log,
    load_brief_summary,
    load_weekly_brief,
    staleness_days,
)

_SUMMARY_PATH = "data/personal/brief_summary.json"
_BRIEF_MD_PATH = "data/personal/weekly_brief.md"
_ADHERENCE_PATH = "data/personal/adherence_log.jsonl"
_GRADE_ORDER = ["REDUCE", "TRIM", "REVIEW", "HOLD", "ADD_OK"]
_GRADE_COLOR = {
    "REDUCE": "#DC2626",
    "TRIM": "#EA580C",
    "REVIEW": "#CA8A04",
    "HOLD": "#64748B",
    "ADD_OK": "#16A34A",
}
_GRADE_TONE = {
    "REDUCE": "negative",
    "TRIM": "negative",
    "REVIEW": "neutral",
    "HOLD": "neutral",
    "ADD_OK": "positive",
}


def _verdict_pill(grade: str) -> str:
    tone_map = {
        "REDUCE": "danger",
        "TRIM": "warning",
        "REVIEW": "warning",
        "HOLD": "neutral",
        "ADD_OK": "success",
    }
    return status_pill_html(tone_map.get(grade, "neutral"), grade)


def render(path: str = _SUMMARY_PATH, adherence_path: str = _ADHERENCE_PATH) -> None:
    st.subheader("Weekly Brief")
    summary = load_brief_summary(path)
    if summary is None:
        st.warning(
            "No structured brief found. Run "
            "`python -m application.cli weekly-brief` to generate it "
            "(stays on your machine)."
        )
        return

    days = staleness_days(summary.get("as_of", ""))
    if days is not None and days > 8:
        st.error(
            f"Brief is {days} days old — run "
            "`python -m application.cli weekly-brief` for a fresh one."
        )

    # Regime banner
    regime = summary.get("regime", "?")
    as_of = summary.get("as_of", "?")
    screen_label = summary.get("screen_label", "RESEARCH_ONLY")
    render_verdict_card(
        st,
        verdict=f"Regime: {regime.upper()} · {screen_label}",
        tone="neutral",
        details=f"As of {as_of}",
    )

    st.divider()

    # Buy side abstention info
    if summary.get("abstained", True):
        st.markdown(
            '<div class="ws-card" style="padding:12px 16px;margin-bottom:12px;">'
            '<span style="font-weight:700;color:#64748B;">RESEARCH_ONLY</span> — '
            "Evidence screen: 0 buy candidates met the bar this week — "
            "the screen abstained (no buy language)."
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        candidates = summary.get("candidates", [])
        st.markdown(
            '<div class="ws-card" style="padding:12px 16px;margin-bottom:12px;">'
            f'<span style="font-weight:700;color:#16A34A;">CANDIDATES</span> — '
            f"{len(candidates)} name(s) surfaced this week (RESEARCH_ONLY, not a buy call)."
            "</div>",
            unsafe_allow_html=True,
        )

    # Concentration flags
    concentration = summary.get("concentration", [])
    if concentration:
        st.markdown("**Concentration flags**")
        for flag in concentration:
            pill = status_pill_html(
                "warning" if flag.get("soft_warning") else "danger", "FLAG"
            )
            st.markdown(
                f'<div class="ws-card" style="padding:8px 14px;margin-bottom:6px;">'
                f"{pill} {flag.get('descriptor', '')}"
                "</div>",
                unsafe_allow_html=True,
            )
        st.divider()

    # --- NEW: Hero count-chip strip ---
    holdings = summary.get("holdings", [])
    grades_present = [
        g for g in _GRADE_ORDER if any(h.get("verdict") == g for h in holdings)
    ]

    if grades_present:
        st.markdown("**Discipline flags** — grouped by urgency")
        chip_cols = st.columns(len(grades_present))
        for col, grade in zip(chip_cols, grades_present):
            count = sum(1 for h in holdings if h.get("verdict") == grade)
            color = _GRADE_COLOR[grade]
            col.markdown(
                f'<div class="ws-card" style="text-align:center;padding:10px 6px;">'
                f'<span style="color:{color};font-weight:700;font-size:14px;">{grade}</span>'
                f'<br><span style="font-size:20px;font-weight:700;">{count}</span>'
                "</div>",
                unsafe_allow_html=True,
            )

        # --- Urgent section: REDUCE + TRIM as compact dataframe ---
        urgent_rows = [h for h in holdings if h.get("verdict") in ("REDUCE", "TRIM")]
        if urgent_rows:
            st.markdown("#### Needs attention this week")
            import pandas as pd

            df_urgent = pd.DataFrame(
                [
                    {
                        "Ticker": h.get("ticker", "?"),
                        "Grade": h.get("verdict", "?"),
                        "Unrealized %": (
                            f"{h.get('unrealized_pct', 0):.1f}%"
                            if h.get("unrealized_pct") is not None
                            else "?"
                        ),
                        "Trend": h.get("trend_state", "?"),
                        "Why": h.get("why", ""),
                    }
                    for h in urgent_rows
                ]
            )
            st.dataframe(df_urgent, use_container_width=True, hide_index=True)

        # --- Everything else: REVIEW / HOLD / ADD_OK collapsed ---
        other_rows = [
            h for h in holdings if h.get("verdict") in ("REVIEW", "HOLD", "ADD_OK")
        ]
        with st.expander("Everything else (REVIEW · HOLD · ADD_OK)"):
            if other_rows:
                import pandas as pd

                df_other = pd.DataFrame(
                    [
                        {
                            "Ticker": h.get("ticker", "?"),
                            "Grade": h.get("verdict", "?"),
                            "Unrealized %": (
                                f"{h.get('unrealized_pct', 0):.1f}%"
                                if h.get("unrealized_pct") is not None
                                else "?"
                            ),
                            "Trend": h.get("trend_state", "?"),
                            "Why": h.get("why", ""),
                        }
                        for h in other_rows
                    ]
                )
                st.dataframe(df_other, use_container_width=True, hide_index=True)
            else:
                st.caption("No REVIEW / HOLD / ADD_OK positions this week.")

        st.divider()
    else:
        st.info("No discipline flags this week.")
        st.divider()

    # --- Adherence tracker: collapsed in expander ---
    with st.expander("Adherence tracker — tool said vs you did"):
        st.caption(
            "Tool-said vs you-did (resolved, 21d horizon). "
            "Advisory only (L0), descriptive — no significance claims."
        )
        adherence = load_adherence_log(adherence_path)
        if not adherence:
            st.caption(
                "No resolved adherence records yet. Run "
                "`python -m application.cli adherence-report` after flags age 21 days "
                "(records stay on your machine)."
            )
        else:
            cols_header = st.columns([1, 2, 2, 2, 1, 2, 2])
            for col, label in zip(
                cols_header,
                [
                    "Flagged",
                    "Ticker",
                    "Verdict",
                    "You did",
                    "Cut",
                    "Gap (CAD)",
                    "Gap (bps)",
                ],
            ):
                col.markdown(f"**{label}**")
            for r in adherence[-12:]:
                c1, c2, c3, c4, c5, c6, c7 = st.columns([1, 2, 2, 2, 1, 2, 2])
                c1.caption(r.get("flag_date", "?"))
                c2.markdown(r.get("ticker", "?"))
                c3.markdown(
                    _verdict_pill(r.get("verdict", "?")), unsafe_allow_html=True
                )
                label_val = r.get("label", "?")
                done_pill = status_pill_html(
                    "success" if label_val == "FOLLOWED" else "danger", label_val
                )
                c4.markdown(done_pill, unsafe_allow_html=True)
                c5.caption(f"{r.get('actual_cut_fraction', 0) * 100:.0f}%")
                gap_cad = r.get("gap_cad", 0)
                c6.markdown(
                    f'<span style="color:{"#16A34A" if gap_cad >= 0 else "#DC2626"};">'
                    f"{gap_cad:+.0f}</span>",
                    unsafe_allow_html=True,
                )
                c7.caption(f"{r.get('gap_bps', 0):+.1f}")
            st.caption(
                "Gap = counterfactual CAD difference if you had cut per the verdict "
                "(f=0.5). Descriptive, underpowered by design."
            )

    with st.expander("Full markdown brief"):
        md = load_weekly_brief(_BRIEF_MD_PATH)
        st.markdown(md if md else "_No markdown brief found._")
