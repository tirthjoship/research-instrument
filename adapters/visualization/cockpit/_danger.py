"""Section 1 — book danger strip. Red only when real; tap opens risk drill-down."""

from __future__ import annotations

import streamlit as st

from adapters.visualization.data_loader import load_brief_summary


def render(*, summary_path: str, discipline_log_path: str) -> None:
    summary = load_brief_summary(summary_path)
    if summary is None:
        st.info(
            "No weekly brief yet — run the weekly brief CLI to populate the cockpit."
        )
        return

    macro = summary.get("macro")
    score = summary.get("scorecard", {})
    bits: list[str] = []
    danger = False
    if macro:
        share = macro.get("systematic_share")
        dom = macro.get("dominant_factor")
        beta = (macro.get("net_beta_by_factor") or {}).get(dom or "", None)
        if share is not None and dom:
            pct = f"{share:.0%}"
            beta_txt = f" · {dom} β {beta:.2f}" if beta is not None else ""
            bits.append(f"{pct} one macro bet ({dom}){beta_txt}")
            danger = danger or bool(macro.get("flags"))
    gate = score.get("discipline_gate_status")
    if gate:
        bits.append(
            f"Discipline gate {gate} · n={score.get('discipline_n', 0)}"
            f" · window {score.get('discipline_window', '—')}"
        )

    color = "var(--danger)" if danger else "var(--text-secondary)"
    st.markdown(
        '<div class="ws-card" style="padding:10px 16px;">'
        f'<span style="font-weight:700;color:{color};">Book danger</span> — '
        + " · ".join(bits)
        + "</div>",
        unsafe_allow_html=True,
    )

    with st.expander("Risk drill-down"):
        from adapters.visualization.tabs.risk import render as render_risk

        render_risk(path=summary_path)
