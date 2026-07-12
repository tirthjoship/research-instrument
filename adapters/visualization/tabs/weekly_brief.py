"""Weekly Brief tab — the decision cockpit. Renders brief_summary.json."""

from __future__ import annotations

import tempfile
import threading
from collections.abc import Callable, Sequence
from datetime import timedelta
from pathlib import Path
from typing import Any

import streamlit as st

from adapters.visualization.book_context import (
    SESSION_BRIEF_PATH_KEY,
    SESSION_HOLDINGS_CSV_KEY,
    SESSION_REPORTS_DIR_KEY,
    SESSION_SAMPLE_REFRESH_BRIEF_KEY,
    SESSION_SAMPLE_REFRESH_REPORTS_KEY,
    UIBookContext,
    resolve_ui_book_context,
)
from adapters.visualization.card_fetch import (
    _home_evidence_card,
    fetch_card,
    get_case_on_expand,
    implied_cost,
    window_returns,
)
from adapters.visualization.components.decision_card import (
    render_collapsed_row,
    render_expanded_card,
)
from adapters.visualization.components.evidence_chip import (
    render_evidence_chip,
    render_evidence_chip_by_key,
)
from adapters.visualization.components.formatters import status_pill_html
from adapters.visualization.components.onboarding import render_sample_banner_html
from adapters.visualization.components.proof_tile import render_tile
from adapters.visualization.components.tooltip import tooltip
from adapters.visualization.data_loader import (
    load_brief_summary,
    load_latest_screen,
    load_weekly_brief,
    staleness_days,
)
from adapters.visualization.holdings_syncer import rebuild_weekly_brief_cached
from adapters.visualization.run_gate import RUN_GATE_HELP, evaluate_run_gate
from application.card_loading import select_case_summarizer
from application.holdings_reader import read_holdings
from application.runtime_guard import holdings_upload_enabled
from domain.discipline import Verdict
from domain.evidence_registry import EvidenceEntry
from domain.evidence_registry import Verdict as EvidenceVerdict
from domain.evidence_registry import entries_by_verdict
from domain.risk_rubric import classify_net_beta, classify_systematic_share
from domain.screen_diagnostics import ScreenDiagnostics, ScreenVerdict, classify_screen


# st.fragment fallback: no-op decorator if the Streamlit version doesn't have it.
def _fragment_noop(*_args: object, **_kwargs: object) -> Callable[[Any], Any]:
    def _wrap(func: Any) -> Any:
        return func

    return _wrap


_fragment: Callable[..., Callable[[Any], Any]] = getattr(st, "fragment", _fragment_noop)

_SUMMARY_PATH = "data/personal/brief_summary.json"
_BRIEF_MD_PATH = "data/personal/weekly_brief.md"
_ADHERENCE_PATH = "data/personal/adherence_log.jsonl"
_REPORTS_DIR = "data/reports"
_SCREEN_COVERAGE_FLOOR = 0.5  # mirrors research_candidates.py


def _render_onboarding_html() -> str:
    """Return compact sample-book banner HTML for the Home tab."""
    return render_sample_banner_html()


def _clear_tab_loading_overlay() -> None:
    """Remove stuck cross-tab loading overlay so Home stays interactive."""
    import streamlit.components.v1 as components

    components.html(
        """<script>
        (function () {
          var doc = window.parent.document;
          var overlay = doc.getElementById("scr-load-overlay");
          if (overlay) overlay.remove();
          delete doc.body.dataset.scrPending;
        })();
        </script>""",
        height=0,
    )


def _parse_screen_diagnostics(
    screen: dict[str, Any] | None,
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
_CASE_PENDING: object = (
    object()
)  # sentinel: background thread not yet done for this ticker


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
        label=tooltip("Need review")
        + render_evidence_chip_by_key("need_review", compact=True),
        number=f"{need_review} / {total}",
        tone="crimson" if need_review else "muted",
        sub="holdings a rule fired on",
    )
    vm = "—" if vs_market is None else f"{vs_market:+.1f}%"
    t_vm = render_tile(
        label=tooltip("vs Market (1y)")
        + render_evidence_chip_by_key("vs_market_1y", compact=True),
        number=vm,
        tone="muted",
        sub="realized, vs SPY",
    )
    nb_label = tooltip("Net beta") + render_evidence_chip_by_key(
        "net_beta", compact=True
    )
    if net_beta is None:
        t_nb = render_tile(
            label=nb_label, number="—", tone="muted", sub="no macro data"
        )
    else:
        band = classify_net_beta(net_beta).value
        t_nb = render_tile(
            label=nb_label,
            number=f"{net_beta:.2f}",
            stamp=band.upper(),
            tone="muted",
            sub=f"moves ~{net_beta:.2f}x the market",
        )
    t_scr = render_tile(
        label=tooltip("Screen")
        + render_evidence_chip_by_key("screen_cleared", compact=True),
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
        f'{tooltip("Systematic share", "Book health — systematic share")}'
        f'{render_evidence_chip_by_key("systematic_share", compact=True)}</div>'
        f'<div style="font-size:13px;margin-top:3px"><b>{pct}% {band.lower()}</b> &middot; {flag} &mdash; '
        f"adding another same-direction name won't diversify.</div></div></div>"
    )


def _needs_review_cards(
    holdings: list[dict[str, Any]],
) -> list[tuple[str, dict[str, Any]]]:
    """Return (ticker, holding) pairs for holdings that need review."""
    return [(h["ticker"], h) for h in holdings if h.get("verdict") in _NEEDS_REVIEW]


def _launch_case_fetcher(
    cards: list[tuple[str, dict[str, Any]]],
    summarizer: object,
    cases: dict[str, Any],
) -> None:
    """Start a daemon thread that pre-fetches Gemini case data into `cases` dict.

    The thread runs independently of tab navigation — the user can switch tabs
    while it works.  Results land in `cases` (same object held in session_state)
    so subsequent Home renders use cached data with zero Gemini re-calls.
    """

    def _worker() -> None:
        for ticker, _h in cards:
            if ticker in cases:
                continue
            try:
                card = fetch_card(ticker)
                result = get_case_on_expand(
                    ticker, card, news=[], expanded=True, summarizer=summarizer
                )
                cases[ticker] = result
            except Exception:  # noqa: BLE001
                cases[ticker] = None  # mark attempted; expander shows honest "—"

    threading.Thread(target=_worker, daemon=True).start()


def _render_one_holding(
    ticker: str,
    h: dict[str, Any],
    summarizer: object,
    cached_case: object = _CASE_PENDING,
) -> None:
    """Render one holding row: collapsed row + expander with expanded card.

    This is the inner implementation.  Production callers must use
    ``_render_one_holding_fragment`` (the ``st.fragment``-wrapped version) so
    that each row gets an isolated render cycle in Streamlit (spec §7).

    ``cached_case``: when provided (not ``_CASE_PENDING``), skips the Gemini
    call and uses the pre-fetched result.  Pass ``_CASE_PENDING`` (default)
    to fall back to the live path (tests and first-render edge cases only).
    """
    from adapters.visualization.price_cache import (  # noqa: PLC0415
        fetch_price_history,
        fetch_prices,
    )

    card = fetch_card(ticker)
    verdict = Verdict(str(h["verdict"]))
    unrealized = h.get("unrealized_pct")
    unrealized_f = float(unrealized) if unrealized is not None else None
    oneliner = str(h.get("why", ""))

    price_data = fetch_prices((ticker,)).get(ticker, {})
    live_price: float | None = price_data.get("price")

    hist = fetch_price_history(ticker) or {}
    closes: list[float] = hist.get("closes") or []

    cost = implied_cost(live_price, unrealized_f)
    rets = window_returns(closes)

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
        if cached_case is _CASE_PENDING:
            # Background thread not yet done for this ticker — show placeholder
            st.caption(
                "⟳  Case loading in background — return to this tab to see full analysis."
            )
        else:
            # cached_case may be None (fetch failed) or a CaseResult (possibly
            # data_gap=True) — render_expanded_card/_case_html already give
            # both the same honest "no evidence found" treatment.
            st.markdown(
                render_expanded_card(
                    card,
                    case=cached_case,
                    verdict=verdict,
                    name=ticker,
                    unrealized_pct=unrealized_f,
                    means=oneliner,
                    price=live_price,
                    cost=cost,
                    returns=rets,
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


_HOME_CASES_KEY = "_home_holding_cases"  # dict[ticker -> CaseResult|None]
_HOME_FETCH_STARTED_KEY = "_home_fetch_started"
_HOME_FETCH_LANDED_KEY = "_home_fetch_landed"  # one-shot: already reran on completion
_HOME_BRIEF_PROCESSING_KEY = "home_brief_processing"
_UPLOAD_KEY_VER = "ob_upload_key_ver"


def _start_dashboard_rebuild_background(
    holdings_csv: str | None = None, out_path: str | None = None
) -> None:
    """Rebuild brief_summary.json in a daemon thread (non-blocking).

    ``holdings_csv``/``out_path`` default to the personal dogfood paths; the
    session-upload path passes a session/temp pair so the rebuild never
    touches ``data/personal/``.
    """
    if st.session_state.get(_HOME_BRIEF_PROCESSING_KEY):
        return
    st.session_state[_HOME_BRIEF_PROCESSING_KEY] = True
    st.session_state.pop("home_brief_rebuild_error", None)

    def _worker() -> None:
        try:
            rebuild_weekly_brief_cached(holdings_csv=holdings_csv, out_path=out_path)
        except Exception:  # noqa: BLE001
            st.session_state["home_brief_rebuild_error"] = True
        finally:
            st.session_state[_HOME_BRIEF_PROCESSING_KEY] = False
            st.session_state["home_brief_rebuild_done"] = True

    threading.Thread(target=_worker, daemon=True).start()


_HOME_LAST_BRIEF_RUN_KEY = "home_brief_last_run_ts"


def _trigger_brief_run(ctx: UIBookContext) -> None:
    """Kick off a background brief rebuild for the resolved context.

    Sample book: reads the committed sample CSV but writes into a fresh
    session-scoped temp dir — never overwrites data/sample/brief_summary.json.
    Uploaded book: rebuilds from its session holdings CSV into a fresh temp
    dir too, so each Run click never collides with an earlier one.
    """
    import time as _time  # noqa: PLC0415

    st.session_state[_HOME_LAST_BRIEF_RUN_KEY] = _time.time()
    tmp_dir = tempfile.mkdtemp(prefix="stockrec_brief_run_")
    out_path = str(Path(tmp_dir) / "weekly_brief.md")
    brief_path = str(Path(tmp_dir) / "brief_summary.json")

    if ctx.is_sample:
        st.session_state[SESSION_SAMPLE_REFRESH_BRIEF_KEY] = brief_path
        st.session_state[SESSION_SAMPLE_REFRESH_REPORTS_KEY] = _REPORTS_DIR
        _start_dashboard_rebuild_background(
            holdings_csv="data/sample/sample_book.csv", out_path=out_path
        )
    else:
        holdings_csv = st.session_state.get(SESSION_HOLDINGS_CSV_KEY)
        st.session_state[SESSION_BRIEF_PATH_KEY] = brief_path
        st.session_state[SESSION_REPORTS_DIR_KEY] = _REPORTS_DIR
        _start_dashboard_rebuild_background(
            holdings_csv=holdings_csv, out_path=out_path
        )


def _render_run_brief_gate(ctx: UIBookContext, days: int | None) -> None:
    """Status caption + gated Run button for the weekly brief."""
    age_label = (
        f"{days} day{'s' if days != 1 else ''} old"
        if days is not None
        else "no brief yet"
    )
    gate = evaluate_run_gate(
        staleness_days=days,
        is_running=bool(st.session_state.get(_HOME_BRIEF_PROCESSING_KEY)),
        last_run_ts=st.session_state.get(_HOME_LAST_BRIEF_RUN_KEY),
    )
    with st.container(horizontal=True, vertical_alignment="center", gap="small"):
        st.caption(f"Weekly brief — {age_label}")
        clicked = st.button(
            "↻ Run brief",
            key="home_run_brief",
            disabled=not gate.can_run,
            help=RUN_GATE_HELP[gate.reason],
        )
    if clicked:
        _trigger_brief_run(ctx)
        st.rerun()


@_fragment(run_every=timedelta(seconds=2))
def _poll_dashboard_rebuild() -> None:
    """Rerun Home when background brief rebuild finishes."""
    if st.session_state.get(_HOME_BRIEF_PROCESSING_KEY):
        return
    if st.session_state.pop("home_brief_rebuild_done", None):
        st.session_state.pop(_HOME_CASES_KEY, None)
        st.session_state[_HOME_FETCH_STARTED_KEY] = False
        st.session_state[_HOME_FETCH_LANDED_KEY] = False
        st.rerun()


def _ensure_evidence_fetch_started(
    cards: list[tuple[str, dict[str, Any]]],
    summarizer: object,
    cases: dict[str, Any],
) -> None:
    """Kick off the background evidence fetch automatically, once per session."""
    if st.session_state.get(_HOME_FETCH_STARTED_KEY, False):
        return
    st.session_state[_HOME_FETCH_STARTED_KEY] = True
    _launch_case_fetcher(cards, summarizer, cases)


def _render_needs_review_status(cards: list[tuple[str, dict[str, Any]]]) -> None:
    """Single status region for the needs-review evidence fetch.

    One live progress bar while fetching; auto-lands on "Evidence ready" with
    exactly one full rerun once every holding is done (so the per-row
    expanders, rendered outside this fragment's scope, pick up the finished
    ``cases`` dict) — no Fetch/Refresh button, ever.

    This is the inner implementation; production callers must use
    ``_render_needs_review_status_fragment`` (mirrors ``_render_one_holding`` /
    ``_render_one_holding_fragment``) so the status region gets its own
    ``st.fragment`` polling cycle.
    """
    cases: dict[str, Any] = st.session_state.get(_HOME_CASES_KEY, {})
    total = len(cards)
    done = sum(1 for ticker, _ in cards if ticker in cases)

    if done < total:
        st.progress(
            done / total, text=f"Fetching evidence — {done} / {total} holdings…"
        )
        return

    if not st.session_state.get(_HOME_FETCH_LANDED_KEY, False):
        st.session_state[_HOME_FETCH_LANDED_KEY] = True
        st.rerun()
        return

    st.success(f"Evidence ready for {total} holdings.", icon="✅")


_render_needs_review_status_fragment: Any = _fragment(run_every=timedelta(seconds=2))(
    _render_needs_review_status
)


def _render_needs_review(holdings: list[dict[str, Any]]) -> None:
    """Render holdings using background-fetched case data (fully automatic)."""
    cards = _needs_review_cards(holdings)
    if not cards:
        st.markdown(_render_needs_review_html([]), unsafe_allow_html=True)
        return

    summarizer = select_case_summarizer()

    if _HOME_CASES_KEY not in st.session_state:
        st.session_state[_HOME_CASES_KEY] = {}
        st.session_state[_HOME_FETCH_STARTED_KEY] = False
        st.session_state[_HOME_FETCH_LANDED_KEY] = False

    cases: dict[str, Any] = st.session_state[_HOME_CASES_KEY]

    _ensure_evidence_fetch_started(cards, summarizer, cases)
    _render_needs_review_status_fragment(cards)

    for ticker, h in cards:
        cached = cases.get(ticker, _CASE_PENDING)
        _render_one_holding_fragment(ticker, h, summarizer, cached)


def _render_honesty_line_html() -> str:
    return (
        '<div style="margin-top:12px;font-size:12px;color:#5b7178;background:#fff;'
        'border:1px dashed #dde7e9;border-radius:10px;padding:9px 13px">'
        "<b>Why doubt us:</b> our return forecasts test = a coin flip, and the ranking signal is "
        "FALSIFIED. We show evidence, never forecasts. "
        '<a href="#" style="color:#0F6E80;font-weight:600;text-decoration:none">'
        "See the proof → Trust</a></div>"
    )


def _evidence_record_row_html(
    title: str, blurb: str, entries: Sequence[EvidenceEntry]
) -> str:
    """One row of the credibility panel: a heading + the entries as evidence chips.

    *title* and *blurb* are trusted in-house literals; *entries* come straight from
    the evidence registry and are rendered through the shared evidence-chip component
    (so each carries its own meaning / band / ADR / caveat on hover).
    """
    if entries:
        chips = "".join(render_evidence_chip(e, compact=True) for e in entries)
    else:
        chips = '<span style="font-size:12px;color:#94a8ad">— none —</span>'
    return (
        f'<div style="padding:9px 0;border-top:1px solid #eef2f3">'
        f"<div style=\"font-family:'IBM Plex Mono';font-size:10px;text-transform:uppercase;"
        f'letter-spacing:.04em;color:#5b7178">{title}</div>'
        f'<div style="font-size:12px;color:#5b7178;margin:2px 0 6px">{blurb}</div>'
        f'<div style="display:flex;flex-wrap:wrap;gap:6px">{chips}</div>'
        f"</div>"
    )


def _render_evidence_record_html(
    *,
    known: Sequence[EvidenceEntry],
    unproven: Sequence[EvidenceEntry],
    killed: Sequence[EvidenceEntry],
    testing: Sequence[EvidenceEntry],
) -> str:
    """The 'What we know / don't know / still testing' credibility panel.

    A living view of the research record: every product metric, grouped by how much
    trust it has earned. Pure HTML builder — drive it from
    :func:`domain.evidence_registry.entries_by_verdict`. Descriptive only.
    """
    rows = (
        _evidence_record_row_html(
            "What we know",
            "Facts about today, and gates already cleared.",
            known,
        )
        + _evidence_record_row_html(
            "Don't know yet — still researching",
            "Surfaced for research; no measured edge demonstrated.",
            unproven,
        )
        + _evidence_record_row_html(
            "Killed in testing",
            "Tested against a pre-registered gate and discarded.",
            killed,
        )
        + _evidence_record_row_html(
            "Still testing — live gate",
            "Pre-registered, thresholds locked, verdict not yet in.",
            testing,
        )
    )
    return (
        f'<div class="ws-card" style="padding:12px 16px;margin-top:12px">'
        f'<div style="font-family:Fraunces,serif;font-weight:800;font-size:14px;'
        f'margin-bottom:2px">What we know &middot; don&rsquo;t know &middot; '
        f"still testing</div>"
        f'<div style="font-size:12px;color:#5b7178;margin-bottom:2px">'
        f"Every number on this page, graded by how much it has earned. "
        f"Hover any chip for its meaning, healthy band, ADR and caveat. "
        f"Descriptive only.</div>"
        f"{rows}</div>"
    )


def _home_evidence_record_html() -> str:
    """Assemble the credibility panel from the live evidence registry."""
    return _render_evidence_record_html(
        known=(
            entries_by_verdict(EvidenceVerdict.VALIDATED)
            + entries_by_verdict(EvidenceVerdict.DESCRIPTIVE)
        ),
        unproven=(
            entries_by_verdict(EvidenceVerdict.RESEARCH_ONLY)
            + entries_by_verdict(EvidenceVerdict.INCONCLUSIVE)
        ),
        killed=entries_by_verdict(EvidenceVerdict.FALSIFIED),
        testing=entries_by_verdict(EvidenceVerdict.FORWARD_PENDING),
    )


def _stage_csv_upload(uploaded: Any) -> None:
    """Parse an uploaded CSV into the session book (session-only — never
    written to data/personal/), then kick off a background brief rebuild into
    a session-scoped temp directory."""
    try:
        content = uploaded.getvalue().decode("utf-8")
        holdings = read_holdings_from_string(content)
        if not holdings:
            st.error(
                "No valid holdings found. Columns: symbol, quantity, "
                "book value (cad), exchange, account type."
            )
            return

        tmp_dir = tempfile.mkdtemp(prefix="stockrec_session_")
        session_csv = Path(tmp_dir) / "holdings.csv"
        session_csv.write_text(content, encoding="utf-8")
        session_out = Path(tmp_dir) / "weekly_brief.md"

        st.session_state["book"] = holdings
        st.session_state["is_sample_book"] = False
        st.session_state[SESSION_BRIEF_PATH_KEY] = str(
            Path(tmp_dir) / "brief_summary.json"
        )
        st.session_state[SESSION_REPORTS_DIR_KEY] = _REPORTS_DIR
        st.session_state[SESSION_HOLDINGS_CSV_KEY] = str(session_csv)
        st.session_state.pop(_HOME_CASES_KEY, None)
        st.session_state[_HOME_FETCH_STARTED_KEY] = False
        st.session_state[_HOME_FETCH_LANDED_KEY] = False
        st.session_state[_UPLOAD_KEY_VER] = (
            int(st.session_state.get(_UPLOAD_KEY_VER, 0)) + 1
        )
        _start_dashboard_rebuild_background(
            holdings_csv=str(session_csv), out_path=str(session_out)
        )
        st.toast(f"Processing {len(holdings)} holdings from {uploaded.name}")
        st.rerun()
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not parse or sync CSV: {exc}")


def read_holdings_from_string(content: str) -> list[Any]:
    """Parse holdings CSV text via a temp file (read_holdings expects a path)."""
    import tempfile  # noqa: PLC0415

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    return read_holdings(tmp_path)


def _handle_onboarding() -> None:
    """Load the book via the resolver (session upload, else sample); show
    sample banner + inline upload CTA. Never auto-reads data/personal/ — that
    stays a CLI-only dogfood path, outside the public UI."""
    if "book" not in st.session_state:
        ctx = resolve_ui_book_context()
        st.session_state["book"] = ctx.book
        st.session_state["is_sample_book"] = ctx.is_sample

        st.session_state.pop(_HOME_CASES_KEY, None)
        st.session_state.pop(_HOME_FETCH_STARTED_KEY, None)
        st.session_state.pop(_HOME_FETCH_LANDED_KEY, None)

    ver = int(st.session_state.get(_UPLOAD_KEY_VER, 0))
    upload_key = f"ob_csv_uploader_{ver}"

    with st.container(horizontal=True, vertical_alignment="center", gap="medium"):
        st.markdown(_render_onboarding_html(), unsafe_allow_html=True)
        if holdings_upload_enabled():
            uploaded = st.file_uploader(
                "Upload your holdings",
                type=["csv"],
                key=upload_key,
                label_visibility="collapsed",
            )
            if uploaded is not None:
                file_sig = f"{uploaded.name}:{getattr(uploaded, 'size', 0)}"
                if st.session_state.get("_ob_last_csv_sig") != file_sig:
                    st.session_state["_ob_last_csv_sig"] = file_sig
                    _stage_csv_upload(uploaded)


def _compute_vs_market_1y(holdings: list[dict[str, Any]]) -> float | None:
    """Compute approximate portfolio 1Y return minus SPY 1Y return.

    Uses 252-day window returns (index 4 from window_returns).
    Returns None if SPY data unavailable or no holdings have history.
    """
    from adapters.visualization.price_cache import fetch_price_history  # noqa: PLC0415

    spy_hist = fetch_price_history("SPY") or {}
    spy_closes: list[float] = spy_hist.get("closes") or []
    spy_rets = window_returns(spy_closes)
    if len(spy_rets) < 5 or spy_rets[4] is None:
        return None
    spy_1y = spy_rets[4]

    weighted_returns: list[float] = []
    weights: list[float] = []
    for h in holdings:
        ticker = h.get("ticker", "")
        if not ticker:
            continue
        book_val = float(h.get("book_value") or h.get("cost_basis") or 1.0)
        hist = fetch_price_history(ticker) or {}
        closes: list[float] = hist.get("closes") or []
        rets = window_returns(closes)
        if len(rets) >= 5 and rets[4] is not None:
            weighted_returns.append(float(rets[4]) * book_val)
            weights.append(book_val)

    if not weights:
        return None

    portfolio_1y = sum(weighted_returns) / sum(weights)
    return round(portfolio_1y - spy_1y, 2)


def render(
    path: str | None = None,
    adherence_path: str = _ADHERENCE_PATH,
    reports_dir: str | None = None,
) -> None:
    # ── Landing door — ALWAYS rendered (FIX A: persistent so CSV/manual stay
    #    reachable even when a book/brief is loaded).  Button handlers set
    #    st.session_state["book"] and call st.rerun() so the Front-Desk below
    #    picks up the new book on the next cycle. ──────────────────────────────
    _handle_onboarding()
    _clear_tab_loading_overlay()
    _poll_dashboard_rebuild()

    # Explicit path/reports_dir (tests, or a future personal CLI-driven view)
    # win; production's no-arg call resolves through the book-context resolver
    # so cold start / session upload always land on the right artifacts.
    ctx = resolve_ui_book_context()
    path = path if path is not None else ctx.brief_path
    reports_dir = reports_dir if reports_dir is not None else ctx.reports_dir

    summary = load_brief_summary(path)

    if st.session_state.get(_HOME_BRIEF_PROCESSING_KEY):
        st.info(
            "⟳ Processing your uploaded holdings — fetching tickers and rebuilding metrics…",
            icon="ℹ️",
        )
    elif st.session_state.get("home_brief_rebuild_error"):
        st.error(
            "Dashboard rebuild failed. Check terminal logs or run "
            "`python -m application.cli weekly-brief --holdings data/personal/holdings.csv`."
        )

    # ── If no brief and no session book, nothing to show below the door ──────
    if summary is None and "book" not in st.session_state:
        st.warning(
            "No structured brief found. Run "
            "`python -m application.cli weekly-brief` to generate it "
            "(stays on your machine)."
        )
        return

    if summary is None:
        # Session book present (uploaded or sample) but no brief_summary.json —
        # should not happen in the shipped tree (sample artifacts are
        # committed); offer an honest Run CTA rather than a dead end.
        st.info("Book loaded from session. Run weekly-brief to see Front-Desk vitals.")
        _render_run_brief_gate(ctx, None)
        return

    days = staleness_days(summary.get("as_of", ""))
    if days is not None and days > 8:
        st.error(
            f"Brief is {days} days old — run "
            "`python -m application.cli weekly-brief` for a fresh one."
        )
    _render_run_brief_gate(ctx, days)

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
    vs_market = summary.get("vs_market_1y") or _compute_vs_market_1y(holdings)

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

    # ── Credibility panel: what we know / don't know / still testing ─────────
    st.markdown(_home_evidence_record_html(), unsafe_allow_html=True)

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
