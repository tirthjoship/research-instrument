"""Weekly Brief tab — the decision cockpit. Renders brief_summary.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

from adapters.visualization.card_fetch import get_case_on_expand
from adapters.visualization.components.decision_card import (
    render_collapsed_row,
    render_expanded_card,
)
from adapters.visualization.components.formatters import status_pill_html
from adapters.visualization.components.proof_tile import render_tile
from adapters.visualization.components.tooltip import tooltip
from adapters.visualization.data_loader import (
    load_ablation_results,
    load_brief_summary,
    load_latest_screen,
    load_weekly_brief,
    staleness_days,
)
from application.card_loading import select_case_summarizer
from application.evidence_card import EvidenceCard
from domain.discipline import Verdict
from domain.evidence_rag import DIMENSIONS, RagColor, RagSignal
from domain.risk_rubric import classify_net_beta, classify_systematic_share
from domain.screen_diagnostics import ScreenDiagnostics, ScreenVerdict, classify_screen

# st.fragment fallback: no-op decorator if the Streamlit version doesn't have it.
_fragment = getattr(st, "fragment", lambda f: f)

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


def _render_book_health_html(systematic_share: float) -> str:
    pct = round(systematic_share * 100)
    band = classify_systematic_share(systematic_share).value  # e.g. "Macro-leaning"
    flag = (
        '<span style="color:#C9810E">&#x2691; above the 60% flag</span>'
        if systematic_share >= 0.60
        else ""
    )
    ring = (
        f'<div style="width:54px;height:54px;border-radius:50%;flex-shrink:0;'
        f"background:conic-gradient(#0F6E80 {pct}%, #eef2f3 0);display:flex;"
        f'align-items:center;justify-content:center">'
        f'<div style="width:40px;height:40px;border-radius:50%;background:#fff;display:flex;'
        f"align-items:center;justify-content:center;font-family:Fraunces,serif;"
        f'font-weight:800;font-size:13px">{pct}%</div></div>'
    )
    return (
        f'<div style="display:flex;align-items:center;gap:14px;background:#fff;'
        f'border:1px solid #dde7e9;border-radius:12px;padding:12px 15px;margin-top:12px">'
        f"{ring}"
        f"<div><div style=\"font-family:'IBM Plex Mono';font-size:10px;"
        f'text-transform:uppercase;color:#94a8ad">'
        f'{tooltip("Systematic share", "Book health — systematic share")}</div>'
        f'<div style="font-size:13px;margin-top:3px"><b>{pct}% {band.lower()}</b> &middot; {flag} &mdash; '
        f"adding another same-direction name won't diversify.</div></div></div>"
    )


def _home_evidence_card(ticker: str) -> EvidenceCard:
    """Minimal GAP card for S4 (squares light up once S5 wires per-holding fetch)."""
    sigs = tuple(
        RagSignal(d, RagColor.GAP, "DATA-GAP: loads on open") for d in DIMENSIONS
    )
    return EvidenceCard(ticker=ticker, signals=sigs, sparkline=())


def _fetch_card(ticker: str) -> EvidenceCard:
    """Fetch a real EvidenceCard for a ticker via cached adapters (S5).

    On any fetch failure (network, bare-mode CI) falls back to the GAP card
    so the UI remains honest rather than crashing.
    """
    try:
        from adapters.data.earnings_history_adapter import fetch_earnings_history
        from adapters.visualization.price_cache import fetch_prices, fetch_ticker_info
        from application.analyst_panel import build_analyst_panel
        from application.evidence_card import build_evidence_card

        raw = fetch_ticker_info(ticker)
        info = {k: v for k, v in raw.items()}
        px = fetch_prices((ticker,)).get(ticker, {})
        info["current_price"] = px.get("price")
        # snake_case keys S1 expects
        info["trailing_pe"] = raw.get("trailingPE")
        info["peg_ratio"] = raw.get("pegRatio")
        info["free_cashflow"] = raw.get("freeCashflow")
        info["debt_to_equity"] = raw.get("debtToEquity")
        # Remap yfinance raw keys → build_analyst_panel's expected keys (mirror stock_analyzer)
        panel_info: dict[str, Any] = dict(raw)
        panel_info["analyst_count"] = raw.get("numberOfAnalystOpinions", 0)
        panel_info["analyst_recommendation_mean"] = raw.get("recommendationMean")
        # target keys are already camelCase and match build_analyst_panel directly:
        # targetMeanPrice, targetHighPrice, targetLowPrice — no remap needed
        panel = build_analyst_panel(panel_info, "")
        # fetch_prices returns {"price", "change_pct"} — no closes/atr/ma200/vs_spy
        prices: dict[str, Any] = {
            "closes": [],  # DATA-GAP: batch price fetch returns no history
            "atr": None,  # DATA-GAP: not available from price_cache
            "ma200": None,  # DATA-GAP: not available from price_cache
            "spy_1y": None,  # DATA-GAP: not tracked per holding
            "book_1y": None,  # DATA-GAP: not tracked per holding
        }
        peers: list[float | None] = []  # DATA-GAP: peer data not fetched on Home
        return build_evidence_card(
            ticker,
            info=info,
            prices=prices,
            panel=panel,
            earnings=fetch_earnings_history(ticker),
            peers=peers,
        )
    except Exception:  # noqa: BLE001 — network/CI failures → GAP card (honest)
        return _home_evidence_card(ticker)


def _needs_review_cards(
    holdings: list[dict[str, Any]]
) -> list[tuple[str, dict[str, Any]]]:
    """Return (ticker, holding) pairs for holdings that need review."""
    return [(h["ticker"], h) for h in holdings if h.get("verdict") in _NEEDS_REVIEW]


def _render_one_holding(ticker: str, h: dict[str, Any], summarizer: object) -> None:
    """Render one holding row: collapsed row + expander with expanded card.

    This is the inner implementation.  Production callers must use
    ``_render_one_holding_fragment`` (the ``st.fragment``-wrapped version) so
    that each row gets an isolated render cycle in Streamlit (spec §7).
    """
    card = _fetch_card(ticker)
    verdict = Verdict(str(h["verdict"]))
    unrealized = h.get("unrealized_pct")
    unrealized_f = float(unrealized) if unrealized is not None else None
    oneliner = str(h.get("why", ""))

    st.markdown(
        render_collapsed_row(
            card,
            verdict=verdict,
            name=ticker,
            unrealized_pct=unrealized_f,
            oneliner=oneliner,
        ),
        unsafe_allow_html=True,
    )
    with st.expander(f"{ticker} — {verdict.value} (expand for full evidence)"):
        # Inside expander body — fetch lazy case (always expanded=True here)
        case = get_case_on_expand(
            ticker, card, news=[], expanded=True, summarizer=summarizer
        )
        # data_gap: pass case=None so _case_html shows honest "loads on open" placeholder
        case_to_render = None if (case is None or case.data_gap) else case
        st.markdown(
            render_expanded_card(
                card,
                case=case_to_render,
                verdict=verdict,
                name=ticker,
                unrealized_pct=unrealized_f,
                means=oneliner,
                price=None,
                cost=None,
                returns=(),
                reliability="measured forward; see Trust",
            ),
            unsafe_allow_html=True,
        )


# Fragment-wrapped version for production use (each row independent render cycle).
# In bare mode (CI/tests), st.fragment silently no-ops — _render_needs_review calls
# _render_one_holding directly so tests can capture the output.
_render_one_holding_fragment: Any = _fragment(_render_one_holding)


def _render_needs_review_html(holdings: list[dict[str, Any]]) -> str:
    rows = []
    for h in holdings:
        if h.get("verdict") not in _NEEDS_REVIEW:
            continue
        ticker = str(h.get("ticker", "?"))
        card = _home_evidence_card(ticker)
        unrealized = h.get("unrealized_pct")
        rows.append(
            render_collapsed_row(
                card,
                verdict=Verdict(str(h["verdict"])),
                name=ticker,
                unrealized_pct=float(unrealized) if unrealized is not None else None,
                oneliner=str(h.get("why", "")),
            )
        )
    if not rows:
        return (
            '<div class="ws-card" style="padding:12px 16px;color:#1F9254">'
            "Nothing needs review this week — all positions within discipline.</div>"
        )
    return f'<div class="ws-card" style="padding:0">{"".join(rows)}</div>'


def _render_needs_review(holdings: list[dict[str, Any]]) -> None:
    """Progressive render: progress bar + per-holding fragment render + lazy case.

    Each holding row is rendered via ``_render_one_holding_fragment`` which is
    wrapped with ``st.fragment`` in a live Streamlit session, providing per-row
    render isolation (spec §7).  In bare-mode / CI the ``_fragment`` fallback is
    a no-op decorator, so ``_render_one_holding_fragment`` is identical to
    ``_render_one_holding`` — tests capture ``st.markdown`` output unchanged.
    """
    cards = _needs_review_cards(holdings)
    if not cards:
        st.markdown(_render_needs_review_html([]), unsafe_allow_html=True)
        return
    bar = st.progress(0.0, text=f"Fetching 0 / {len(cards)} holdings…")
    summarizer = select_case_summarizer()
    for i, (ticker, h) in enumerate(cards, 1):
        _render_one_holding_fragment(ticker, h, summarizer)
        bar.progress(i / len(cards), text=f"Fetching {i} / {len(cards)} holdings…")
    bar.empty()


def _render_honesty_line_html() -> str:
    return (
        '<div style="margin-top:12px;font-size:12px;color:#5b7178;background:#fff;'
        'border:1px dashed #dde7e9;border-radius:10px;padding:9px 13px">'
        "<b>Why doubt us:</b> our return forecasts test = a coin flip, and the ranking signal is "
        "FALSIFIED. We show evidence, never forecasts. "
        '<a href="#" style="color:#0F6E80;font-weight:600;text-decoration:none">'
        "See the proof → Trust</a></div>"
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
    macro = summary.get("macro") or {}
    sys_share = macro.get("systematic_share")

    # ── Hero headline (Research Instrument system) ──────────────────────────────
    regime = summary.get("regime", "?")
    st.markdown(
        '<div class="ri-h1">A research instrument that knows when not to call it.</div>'
        '<div class="ri-sub">It earns trust by staying silent when the evidence is thin.</div>',
        unsafe_allow_html=True,
    )

    # ── Book strip: 4 vitals (ONE net-beta) ────────────────────────────────────
    screen = load_latest_screen(reports_dir)
    cleared = len(screen.get("candidates", [])) if screen else 0
    universe = screen.get("universe_size", 0) if screen else 0
    spy_beta = macro.get("net_beta_by_factor", {}).get("SPY")
    net_beta_val: float | None = float(spy_beta) if spy_beta is not None else None
    need = sum(1 for h in holdings if h.get("verdict") in _NEEDS_REVIEW)
    vs_market = summary.get("vs_market_1y")

    st.markdown('<div class="ri-sec">YOUR BOOK — TODAY</div>', unsafe_allow_html=True)
    st.markdown(
        _render_book_strip_html(
            need_review=need,
            total=len(holdings),
            vs_market=vs_market,
            net_beta=net_beta_val,
            regime=str(regime),
            screen_cleared=cleared,
            screen_universe=universe,
        ),
        unsafe_allow_html=True,
    )
    if sys_share is not None:
        st.markdown(_render_book_health_html(float(sys_share)), unsafe_allow_html=True)
    st.markdown(_render_honesty_line_html(), unsafe_allow_html=True)

    # ── Concentration flags (optional — keep if present) ─────────────────────
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

    # ── Needs-review rows ────────────────────────────────────────────────────────
    st.markdown(
        '<div class="ri-sec">NEEDS REVIEW — A RULE FIRED, YOUR CALL</div>',
        unsafe_allow_html=True,
    )
    _render_needs_review(holdings)

    steady = sum(1 for h in holdings if h.get("verdict") in ("HOLD", "ADD_OK"))
    st.caption(f"Holding steady · {steady} — no rule fired, nothing to do")

    # ── Footer: brief as download, not an inline dump ────────────────────────────
    md = load_weekly_brief(path.replace("brief_summary.json", "weekly_brief.md"))
    if md:
        st.download_button(
            "⬇ Download full weekly brief (.md)", md, file_name="weekly_brief.md"
        )
