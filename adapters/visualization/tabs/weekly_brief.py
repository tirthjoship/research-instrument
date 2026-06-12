"""Weekly Brief tab — the decision cockpit. Renders brief_summary.json."""

from __future__ import annotations

from typing import Any

import streamlit as st

from adapters.visualization.components.formatters import status_pill_html
from adapters.visualization.data_loader import (
    load_adherence_log,
    load_brief_summary,
    load_latest_screen,
    load_weekly_brief,
    staleness_days,
)

_SUMMARY_PATH = "data/personal/brief_summary.json"
_BRIEF_MD_PATH = "data/personal/weekly_brief.md"
_ADHERENCE_PATH = "data/personal/adherence_log.jsonl"
_REPORTS_DIR = "data/reports"
_GRADE_ORDER = ["REDUCE", "TRIM", "REVIEW", "HOLD", "ADD_OK"]
_GRADE_COLOR = {
    "REDUCE": "#DC2626",
    "TRIM": "#EA580C",
    "REVIEW": "#CA8A04",
    "HOLD": "#64748B",
    "ADD_OK": "#16A34A",
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


def _gauge(share: float) -> Any:
    import plotly.graph_objects as go

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=share * 100,
            number={"suffix": "%", "font": {"size": 22}},
            gauge={
                "axis": {"range": [0, 100], "visible": False},
                "bar": {"color": "#1D4ED8"},
                "threshold": {
                    "line": {"color": "#B91C1C", "width": 2},
                    "thickness": 0.9,
                    "value": 60,
                },
            },
        )
    )
    fig.update_layout(
        height=120,
        margin={"l": 8, "r": 8, "t": 8, "b": 8},
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def render(
    path: str = _SUMMARY_PATH,
    adherence_path: str = _ADHERENCE_PATH,
    reports_dir: str = _REPORTS_DIR,
) -> None:
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

    # --- Hero: book-health banner + systematic-share gauge ---
    holdings = summary.get("holdings", [])
    attention = [h for h in holdings if h.get("verdict") in ("REDUCE", "TRIM")]
    macro = summary.get("macro") or {}
    share = float(macro.get("systematic_share", 0.0))

    hero_cols = st.columns([3, 1])
    with hero_cols[0]:
        st.markdown(
            f'<div class="ws-card hero-gradient" style="padding:20px 24px;">'
            f'<div style="font-size:13px;color:#5C6370;">YOUR BOOK · '
            f'{summary.get("as_of", "?")} · regime {summary.get("regime", "?")}</div>'
            f'<div style="font-size:26px;font-weight:800;margin-top:4px;">'
            f"{len(attention)} things need attention this week</div>"
            f'<div style="font-size:14px;color:#5C6370;margin-top:4px;">'
            f"{len(holdings)} holdings tracked · "
            f"{share:.0%} of movement is one market-wide bet</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with hero_cols[1]:
        if macro:
            st.plotly_chart(_gauge(share), use_container_width=True)
            st.caption("Systematic share — flag at 60%")

    # --- Attention row: top 5 REDUCE / TRIM as compact cards ---
    if attention:
        st.markdown("**Needs attention this week**")
        top5 = attention[:5]
        attn_cols = st.columns(len(top5))
        for col, h in zip(attn_cols, top5):
            verdict = h.get("verdict", "?")
            css_class = "verdict-negative"
            unrealized = h.get("unrealized_pct")
            unrealized_str = f"{unrealized:.1f}%" if unrealized is not None else "?"
            pill_html = _verdict_pill(verdict)
            col.markdown(
                f'<div class="ws-card {css_class}" style="padding:10px 12px;">'
                f'<div style="font-weight:700;font-size:15px;">{h.get("ticker", "?")}</div>'
                f'<div style="margin:4px 0;">{pill_html}</div>'
                f'<div style="font-size:13px;color:#64748B;">{unrealized_str}</div>'
                f'<div style="font-size:12px;color:#94A3B8;margin-top:4px;">{h.get("why", "")}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            '<div class="ws-card" style="padding:12px 16px;color:#16A34A;">'
            "Nothing needs attention this week — all positions within discipline."
            "</div>",
            unsafe_allow_html=True,
        )

    # --- Week strip: 3 small ws-cards ---
    strip_cols = st.columns(3)

    # Card 1: Screen one-liner
    with strip_cols[0]:
        screen = load_latest_screen(reports_dir)
        if screen is None:
            screen_text = "no screen yet"
        else:
            universe_size = screen.get("universe_size", "?")
            candidates = screen.get("candidates", [])
            screen_text = f"{universe_size} screened · {len(candidates)} passed"
        st.markdown(
            f'<div class="ws-card" style="padding:12px 14px;">'
            f'<div style="font-size:11px;font-weight:600;color:#64748B;margin-bottom:4px;">SCREEN</div>'
            f'<div style="font-size:14px;">{screen_text}</div>'
            f"</div>",
            unsafe_allow_html=True,
        )

    # Card 2: Adherence count
    with strip_cols[1]:
        adherence_rows = load_adherence_log(adherence_path)
        adherence_count = len(adherence_rows)
        st.markdown(
            f'<div class="ws-card" style="padding:12px 14px;">'
            f'<div style="font-size:11px;font-weight:600;color:#64748B;margin-bottom:4px;">ADHERENCE</div>'
            f'<div style="font-size:14px;">{adherence_count} resolved records</div>'
            f"</div>",
            unsafe_allow_html=True,
        )

    # Card 3: Gate line
    with strip_cols[2]:
        st.markdown(
            '<div class="ws-card" style="padding:12px 14px;">'
            '<div style="font-size:11px;font-weight:600;color:#64748B;margin-bottom:4px;">FORWARD GATE</div>'
            '<div style="font-size:14px;">resolves ~mid-July 2026</div>'
            "</div>",
            unsafe_allow_html=True,
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

    # --- Grade chip strip ---
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

        # --- All attention items: REDUCE + TRIM dataframe ---
        urgent_rows = [h for h in holdings if h.get("verdict") in ("REDUCE", "TRIM")]
        if urgent_rows:
            st.markdown("#### All attention items")
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
