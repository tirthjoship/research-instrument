"""Weekly Brief tab — the decision cockpit. Renders brief_summary.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

from adapters.visualization.components.formatters import status_pill_html
from adapters.visualization.components.ledger import render_ledger
from adapters.visualization.components.proof_tile import render_tile
from adapters.visualization.components.tooltip import tooltip
from adapters.visualization.data_loader import (
    load_ablation_results,
    load_adherence_log,
    load_brief_summary,
    load_latest_screen,
    load_weekly_brief,
    staleness_days,
)
from domain.risk_rubric import classify_net_beta
from domain.screen_diagnostics import ScreenDiagnostics, ScreenVerdict, classify_screen

_SUMMARY_PATH = "data/personal/brief_summary.json"
_BRIEF_MD_PATH = "data/personal/weekly_brief.md"
_ADHERENCE_PATH = "data/personal/adherence_log.jsonl"
_REPORTS_DIR = "data/reports"
_GRADE_ORDER = ["REDUCE", "TRIM", "REVIEW", "HOLD", "ADD_OK"]
_SCREEN_COVERAGE_FLOOR = 0.5  # mirrors research_candidates.py
_GRADE_COLOR = {
    "REDUCE": "#DC2626",
    "TRIM": "#EA580C",
    "REVIEW": "#CA8A04",
    "HOLD": "#64748B",
    "ADD_OK": "#16A34A",
}


# Rank-IC primary result: mean IC = 0.004 over 496 dates (1m/21d horizon).
# Source: data/reports/divergence_ic_1m_*.json — ADR-044 divergence-ic-verdict
# (KILL; bootstrap CI spans zero). A degenerate run (n_dates == 0) is ignored, and
# we fall back to the ADR-recorded value, so the tile always reflects the real
# falsification finding rather than an empty regeneration.
_RANK_IC_FALSIFIED = "0.004"  # ADR-044: mean IC = 0.0040 over 496 dates, KILL


def _load_rank_ic(reports_dir: str) -> str:
    """Mean rank-IC from the primary divergence-IC run (ADR-044).

    Reads the real artifact (``divergence_ic_1m_*.json``, n_dates > 0) and formats
    its mean IC. Falls back to the ADR-recorded value when no genuine run is present;
    never reports a degenerate empty run.
    """
    for path in sorted(Path(reports_dir).glob("divergence_ic_1m_*.json"), reverse=True):
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if data.get("n_dates", 0) and data.get("mean_ic") is not None:
            return f"{data['mean_ic']:.3f}"
    return _RANK_IC_FALSIFIED


def _load_directional_accuracy(reports_dir: str) -> str:
    """Load baseline (technical_only) directional accuracy. Returns formatted % or DATA_GAP."""
    rows = load_ablation_results(reports_dir)
    if not rows:
        return "—"
    # Use the technical_only (baseline) variant — most conservative honest number
    for row in rows:
        if row.get("variant") == "technical_only":
            val = row.get("directional_accuracy")
            if val is not None:
                return f"{val * 100:.1f}%"
    # Fallback: use first row if no technical_only found
    val = rows[0].get("directional_accuracy")
    if val is not None:
        return f"{val * 100:.1f}%"
    return "—"


def _verdict_pill(grade: str) -> str:
    tone_map = {
        "REDUCE": "danger",
        "TRIM": "warning",
        "REVIEW": "warning",
        "HOLD": "neutral",
        "ADD_OK": "success",
    }
    return status_pill_html(tone_map.get(grade, "neutral"), grade)


def _parse_screen_diagnostics(
    screen: dict[str, Any] | None
) -> ScreenDiagnostics | None:
    """Parse ScreenDiagnostics from a screen JSON dict.

    Mirrors the same defensive parsing used in research_candidates.py.
    Returns None when diagnostics are absent or malformed.
    """
    if screen is None:
        return None
    raw_diag = screen.get("diagnostics")
    if not isinstance(raw_diag, dict):
        return None
    try:
        return ScreenDiagnostics(
            scanned=int(raw_diag["scanned"]),
            had_history=int(raw_diag["had_history"]),
            above_trend=int(raw_diag["above_trend"]),
            cleared=int(raw_diag["cleared"]),
        )
    except (KeyError, ValueError, TypeError):
        return None


def _screen_tile_content(
    screen: dict[str, Any] | None,
) -> tuple[str, str | None, str, str]:
    """Derive honest (number, stamp, tone, sub) for the screen evidence tile.

    Rules:
    - HAS_CANDIDATES  → "{cleared} cleared / {scanned}" · no stamp · muted
    - UNDER_POWERED   → "screen under-powered" · no stamp · muted
    - EARNED_ABSTENTION → "{scanned} scanned / 0 cleared" · no stamp · muted
    - No diagnostics (old JSON) → "screen: re-run" · no stamp · muted
    - No screen file → "—" · no stamp · muted

    The =EMH / ABSTAINED stamp is NEVER applied here — it belongs only on the
    return-model falsification tiles (directional accuracy, Rank-IC).
    """
    if screen is None:
        return "—", None, "muted", "No screen file found (DATA GAP)."

    diag = _parse_screen_diagnostics(screen)

    if diag is None:
        # Old cached JSON without diagnostics: neutral, no verdict claim
        return (
            "screen: re-run",
            None,
            "muted",
            "Screen diagnostics unavailable — re-run screen-candidates for a full readout.",
        )

    verdict = classify_screen(diag, _SCREEN_COVERAGE_FLOOR)

    if verdict == ScreenVerdict.HAS_CANDIDATES:
        return (
            f"{diag.cleared} cleared / {diag.scanned}",
            None,
            "muted",
            f"{diag.cleared} name(s) cleared every gate this week.",
        )
    if verdict == ScreenVerdict.UNDER_POWERED:
        return (
            "screen under-powered",
            None,
            "muted",
            f"Only {diag.had_history} of {diag.scanned} had usable price history.",
        )
    # EARNED_ABSTENTION: all names scored, none cleared the bar
    return (
        f"{diag.scanned} scanned / 0 cleared",
        None,
        "muted",
        "All names scored — none cleared the evidence bar this week.",
    )


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


_NEEDS_REVIEW: set[str] = {"REDUCE", "TRIM", "REVIEW"}


def _render_book_strip_html(
    *,
    need_review: int,
    total: int,
    vs_market: float | None,
    net_beta: float | None,
    regime: str,
    screen_cleared: int,
    screen_universe: int,
) -> str:
    t_review = render_tile(
        label=tooltip("Need review"),
        number=f"{need_review} / {total}",
        tone="crimson" if need_review else "muted",
        sub="holdings a rule fired on",
    )
    vm = "—" if vs_market is None else f"{vs_market:+.1f}%"
    t_vm = render_tile(
        label=tooltip("vs Market (1y)"), number=vm, tone="muted", sub="realized, vs SPY"
    )
    if net_beta is None:
        t_nb = render_tile(
            label=tooltip("Net beta"), number="—", tone="muted", sub="no macro data"
        )
    else:
        band = classify_net_beta(net_beta).value
        t_nb = render_tile(
            label=tooltip("Net beta"),
            number=f"{net_beta:.2f}",
            stamp=band.upper(),
            tone="muted",
            sub=f"moves ~{net_beta:.2f}x the market",
        )
    t_scr = render_tile(
        label=tooltip("Screen"),
        number=str(screen_cleared),
        tone="green" if screen_cleared else "muted",
        sub=f"cleared of {screen_universe}",
    )
    regime_badge = (
        f"<span style=\"font-family:'IBM Plex Mono';font-size:10px;text-transform:uppercase;"
        f'color:#0F6E80;background:#e6f1f3;border-radius:6px;padding:2px 7px;margin-left:8px">'
        f"{regime}</span>"
    )
    return (
        f"<div>"
        f'<div style="display:flex;align-items:center;margin-bottom:8px">'
        f"<span style=\"font-family:'IBM Plex Mono';font-size:10px;text-transform:uppercase;color:#94a8ad\">Macro regime</span>"
        f"{regime_badge}</div>"
        f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px">'
        f"{t_review}{t_vm}{t_nb}{t_scr}</div></div>"
    )


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

    holdings = summary.get("holdings", [])
    attention = [h for h in holdings if h.get("verdict") in ("REDUCE", "TRIM")]
    review_count = len(
        [h for h in holdings if h.get("verdict") in ("REDUCE", "TRIM", "REVIEW")]
    )
    total_holdings = len(holdings)
    macro = summary.get("macro") or {}
    share = float(macro.get("systematic_share", 0.0))

    # ── Hero headline (Research Instrument system) ──────────────────────────────
    as_of = summary.get("as_of", "?")
    regime = summary.get("regime", "?")
    st.markdown(
        '<div class="ri-h1">A research instrument that knows when not to call it.</div>'
        '<div class="ri-sub">It earns trust by staying silent when the evidence is thin.</div>',
        unsafe_allow_html=True,
    )

    # ── TRIAGE STRIP (action-lead, above evidence ledger) ───────────────────────
    screen = load_latest_screen(reports_dir)
    universe_size = screen.get("universe_size", "?") if screen else "?"
    candidates = screen.get("candidates", []) if screen else []
    adherence_rows = load_adherence_log(adherence_path)

    # Net beta from macro block (SPY factor coefficient is the headline net-beta proxy)
    spy_beta = macro.get("net_beta_by_factor", {}).get("SPY")
    net_beta_val: float | None = float(spy_beta) if spy_beta is not None else None
    net_beta_display = f"{net_beta_val:.2f}" if net_beta_val is not None else "—"
    net_beta_band_str = (
        classify_net_beta(net_beta_val).value if net_beta_val is not None else ""
    )

    # "Need review" = REDUCE + TRIM + REVIEW verdicts (discipline review prompts)
    need_review_label = f"{review_count} / {total_holdings}"
    triage_plain = (
        f"{review_count} of your {total_holdings} holdings "
        f"{'has' if review_count == 1 else 'have'} signals worth reviewing."
    )

    st.markdown('<div class="ri-sec">TRIAGE</div>', unsafe_allow_html=True)
    triage_cols = st.columns(4)
    with triage_cols[0]:
        # Dominant tile: "Need review" count
        tone_review = "amber" if review_count > 0 else "muted"
        st.markdown(
            render_tile(
                label=tooltip("Need review"),
                number=need_review_label,
                stamp=None,
                tone=tone_review,
                sub="holdings with REDUCE / TRIM / REVIEW signals",
            ),
            unsafe_allow_html=True,
        )
    with triage_cols[1]:
        # vs Market (1y): not pre-computed in brief — show DATA GAP honestly
        st.markdown(
            render_tile(
                label=tooltip("vs Market (1y)"),
                number="—",
                stamp=None,
                tone="muted",
                sub="not pre-computed in brief (re-run macro-beta report)",
            ),
            unsafe_allow_html=True,
        )
    with triage_cols[2]:
        band_sub = f"{net_beta_band_str} band" if net_beta_band_str else "no macro data"
        st.markdown(
            render_tile(
                label=tooltip("Net beta"),
                number=net_beta_display,
                stamp=None,
                tone="muted",
                sub=band_sub,
            ),
            unsafe_allow_html=True,
        )
    with triage_cols[3]:
        st.markdown(
            render_tile(
                label=tooltip("Regime"),
                number=str(regime).upper(),
                stamp=None,
                tone="muted",
                sub="macro regime classification",
            ),
            unsafe_allow_html=True,
        )
    st.markdown(
        f'<div style="color:#64748B;font-size:13px;margin:-4px 0 16px 0;">'
        f"{triage_plain}</div>",
        unsafe_allow_html=True,
    )

    # ── Evidence ledger strip ────────────────────────────────────────────────────
    net_beta_str = "—"
    if macro.get("systematic_share") is not None:
        net_beta_str = f"{share:.0%}"

    ledger_html = render_ledger(
        [
            (tooltip("Universe"), str(universe_size)),
            ("CLEARED", str(len(candidates))),
            (tooltip("Net beta"), net_beta_str),
            ("HOLDINGS", str(len(holdings))),
            ("AS OF", as_of),
            ("REGIME", str(regime).upper()),
            ("ADHERENCE LOG", str(len(adherence_rows)) + " records"),
        ]
    )
    st.markdown(ledger_html, unsafe_allow_html=True)

    # ── Anti-KPI tiles — the three honest verdicts ──────────────────────────────
    st.markdown('<div class="ri-sec">VALIDATION FINDINGS</div>', unsafe_allow_html=True)

    # Tile 1: Screen verdict — honest, derived from diagnostics + classify_screen.
    # NEVER shows "512→0 ABSTAINED =EMH" — that was a bug-driven false claim.
    # =EMH framing is reserved for the return-model falsification tiles (tiles 2 & 3).
    tile1_number, tile1_stamp, tile1_tone, tile1_sub = _screen_tile_content(screen)

    # Tile 2: Directional accuracy
    da_str = _load_directional_accuracy(reports_dir)
    if da_str == "—":
        tile2_number = "—"
        tile2_stamp = None
        tile2_tone = "muted"
        tile2_sub = "Directional accuracy unavailable (DATA GAP)."
    else:
        tile2_number = da_str
        tile2_stamp = "= EMH"
        tile2_tone = "muted"
        tile2_sub = "no edge over a coin flip on direction (technical-only baseline)"

    # Tile 3: Rank-IC — sourced from divergence_ic_1m_*.json (real run) / ADR-044
    rank_ic_str = _load_rank_ic(reports_dir)
    tile3 = render_tile(
        label=tooltip("Rank-IC"),
        number=rank_ic_str,
        stamp="FALSIFIED",
        tone="crimson",
        sub="the ranking signal knows ~nothing (ADR-044, 1m primary horizon)",
    )

    tile_cols = st.columns(3)
    with tile_cols[0]:
        st.markdown(
            render_tile(
                label=tooltip("Evidence screen"),
                number=tile1_number,
                stamp=tile1_stamp,
                tone=tile1_tone,
                sub=tile1_sub,
            ),
            unsafe_allow_html=True,
        )
    with tile_cols[1]:
        st.markdown(
            render_tile(
                label=tooltip("Directional accuracy"),
                number=tile2_number,
                stamp=tile2_stamp,
                tone=tile2_tone,
                sub=tile2_sub,
            ),
            unsafe_allow_html=True,
        )
    with tile_cols[2]:
        st.markdown(tile3, unsafe_allow_html=True)

    # ── Book health gauge + systematic share ─────────────────────────────────────
    if macro:
        st.markdown('<div class="ri-sec">BOOK HEALTH</div>', unsafe_allow_html=True)
        gauge_cols = st.columns([1, 3])
        with gauge_cols[0]:
            st.plotly_chart(_gauge(share), use_container_width=True)
            st.caption(
                f"{tooltip('Systematic share')} — flag at 60%", unsafe_allow_html=True
            )

    st.divider()

    # ── Attention row: REDUCE / TRIM cards ──────────────────────────────────────
    st.markdown('<div class="ri-sec">DISCIPLINE FLAGS</div>', unsafe_allow_html=True)
    if attention:
        top5 = attention[:5]
        attn_cols = st.columns(len(top5))
        for col, h in zip(attn_cols, top5):
            verdict = h.get("verdict", "?")
            css_class = "verdict-negative"
            unrealized = h.get("unrealized_pct")
            unrealized_str = f"{unrealized:.1f}%" if unrealized is not None else "?"
            pill_html = _verdict_pill(verdict)
            trend_state = h.get("trend_state", "?")
            col.markdown(
                f'<div class="ws-card {css_class}" style="padding:10px 12px;">'
                f'<div style="font-weight:700;font-size:15px;">{h.get("ticker", "?")}</div>'
                f'<div style="margin:4px 0;">{pill_html}</div>'
                f'<div style="font-size:13px;color:#64748B;">{unrealized_str}</div>'
                f'<div style="font-size:12px;color:#94A3B8;margin-top:4px;">'
                f'{tooltip("Trend filter")}: {trend_state}</div>'
                f'<div style="font-size:12px;color:#94A3B8;margin-top:2px;">{h.get("why", "")}</div>'
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

    # ── Abstention notice ────────────────────────────────────────────────────────
    st.markdown('<div class="ri-sec">RESEARCH SCREEN</div>', unsafe_allow_html=True)
    if summary.get("abstained", True):
        st.markdown(
            '<div class="ws-card" style="padding:12px 16px;margin-bottom:12px;">'
            f'<span style="font-weight:700;color:#64748B;">RESEARCH_ONLY</span> — '
            f'{tooltip("Evidence screen")}: 0 names met the bar this week — '
            f"the screen {tooltip('Abstention','abstained')} (no recommendation language)."
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        candidates_list = summary.get("candidates", [])
        st.markdown(
            '<div class="ws-card" style="padding:12px 16px;margin-bottom:12px;">'
            f'<span style="font-weight:700;color:#16A34A;">CANDIDATES</span> — '
            f"{len(candidates_list)} name(s) surfaced this week (RESEARCH_ONLY, not a recommendation)."
            "</div>",
            unsafe_allow_html=True,
        )

    # ── Concentration flags ──────────────────────────────────────────────────────
    concentration = summary.get("concentration", [])
    if concentration:
        st.markdown(
            f'<div class="ri-sec">{tooltip("Concentrated risk","CONCENTRATION FLAGS")}</div>',
            unsafe_allow_html=True,
        )
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

    # ── Grade chip strip ─────────────────────────────────────────────────────────
    grades_present = [
        g for g in _GRADE_ORDER if any(h.get("verdict") == g for h in holdings)
    ]

    if grades_present:
        st.markdown(
            '<div class="ri-sec">VERDICT DISTRIBUTION</div>', unsafe_allow_html=True
        )
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

        # All attention items: REDUCE + TRIM dataframe
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
                        "Trend filter": h.get("trend_state", "?"),
                        "Why": h.get("why", ""),
                    }
                    for h in urgent_rows
                ]
            )
            st.dataframe(df_urgent, use_container_width=True, hide_index=True)

        # Everything else: REVIEW / HOLD / ADD_OK collapsed
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
                            "Trend filter": h.get("trend_state", "?"),
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

    # ── Adherence tracker ─────────────────────────────────────────────────────────
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
