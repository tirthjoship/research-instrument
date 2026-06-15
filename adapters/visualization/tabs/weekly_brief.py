"""Weekly Brief tab — the decision cockpit. Renders brief_summary.json."""

from __future__ import annotations

from typing import Any

import streamlit as st

from adapters.visualization.card_fetch import get_case_on_expand
from adapters.visualization.components.decision_card import (
    render_collapsed_row,
    render_expanded_card,
)
from adapters.visualization.components.formatters import status_pill_html
from adapters.visualization.components.onboarding import render_landing_door_html
from adapters.visualization.components.proof_tile import render_tile
from adapters.visualization.components.tooltip import tooltip
from adapters.visualization.data_loader import (
    load_brief_summary,
    load_latest_screen,
    load_weekly_brief,
    staleness_days,
)
from application.card_loading import select_case_summarizer
from application.evidence_card import EvidenceCard
from application.holdings_reader import make_manual_holding, read_holdings
from application.runtime_guard import is_local_runtime
from application.sample_book import load_sample_book
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
_SCREEN_COVERAGE_FLOOR = 0.5  # mirrors research_candidates.py

_WINDOW_DAYS = (7, 30, 90, 180, 252)


# ---------------------------------------------------------------------------
# FIX B — pure helpers for price / cost / windowed returns
# ---------------------------------------------------------------------------


def implied_cost(price: float | None, unrealized_pct: float | None) -> float | None:
    """Back-calculate cost basis from price and unrealized %.

    Formula: cost = price / (1 + unrealized_pct / 100)

    Returns None when either input is None so the card shows "—" honestly.

    Examples:
        implied_cost(44.63, 22.7) → ~36.37
        implied_cost(100.0, 0.0) → 100.0
        implied_cost(None, 22.7) → None
        implied_cost(100.0, None) → None
    """
    if price is None or unrealized_pct is None:
        return None
    divisor = 1.0 + unrealized_pct / 100.0
    if divisor == 0.0:
        return None
    return price / divisor


def window_returns(
    closes: list[float],
    windows: tuple[int, ...] = _WINDOW_DAYS,
) -> tuple[float, ...]:
    """Compute % change for each look-back window from a list of daily closes.

    For each window W in ``windows``, returns ``(closes[-1] / closes[-1-W] - 1) * 100``
    when there are enough data points (at least W+1 closes), otherwise skips that window.

    Returns a tuple of available returns (may be shorter than ``windows``).
    Empty closes → empty tuple.

    Examples:
        window_returns([], (7, 30)) → ()
        window_returns(closes_200, (7, 30, 90, 180)) → 4-tuple of floats
    """
    if not closes:
        return ()
    last = closes[-1]
    results: list[float] = []
    for w in windows:
        if len(closes) >= w + 1:
            base = closes[-1 - w]
            if base != 0.0:
                results.append((last / base - 1.0) * 100.0)
    return tuple(results)


def _render_onboarding_html(
    has_book: bool,
) -> str:  # noqa: ARG001 — has_book kept for API compat
    """Return landing-door HTML — ALWAYS rendered so the user can always reach
    Upload/Add-manually even when a book is already loaded (FIX A).

    The ``has_book`` parameter is retained for call-site compatibility and may be
    used in the future to adjust copy (e.g. "Switch book" vs "Load a book").
    """
    return render_landing_door_html(local=is_local_runtime())


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
        from adapters.visualization.price_cache import (
            fetch_price_history,
            fetch_prices,
            fetch_ticker_info,
        )
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
        # Fetch 1-year price history for closes/ATR/MA200 (lights Technicals + sparkline)
        hist = fetch_price_history(ticker) or {}
        prices: dict[str, Any] = {
            "closes": hist.get("closes", []),
            "atr": hist.get("atr"),
            "ma200": hist.get("ma200"),
            "spy_1y": None,  # DATA-GAP: not tracked per holding on Home
            "book_1y": None,  # DATA-GAP: not tracked per holding on Home
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

    FIX B: wires real price (from fetch_prices), implied cost (back-calculated),
    and windowed returns (from fetch_price_history closes) into the expanded card.
    Where data is genuinely unavailable, passes None/() so the card shows "—"
    honestly — never fabricates.
    """
    from adapters.visualization.price_cache import (  # noqa: PLC0415
        fetch_price_history,
        fetch_prices,
    )

    card = _fetch_card(ticker)
    verdict = Verdict(str(h["verdict"]))
    unrealized = h.get("unrealized_pct")
    unrealized_f = float(unrealized) if unrealized is not None else None
    oneliner = str(h.get("why", ""))

    # ── FIX B: fetch real price + history ─────────────────────────────────────
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


def _handle_onboarding() -> None:
    """Render landing door + 3-button action row — ALWAYS (FIX A: persistent).

    Layout:
    - Banner (render_landing_door_html) — heading + copy only, no action buttons.
    - 3-column button row (equal width):
        col1: "▸ Explore sample book" → loads sample book immediately.
        col2: "↓ Upload holdings CSV" (local only) → toggles _show_csv_upload.
        col3: "+ Add manually" → toggles _show_manual_form.
    - Below the row (full width): file_uploader appears when _show_csv_upload is
      True AND is_local_runtime(). This avoids the garbled cramped dropzone.
    - Below: manual-entry form when _show_manual_form is True.

    Returns nothing — caller always proceeds to render Front-Desk afterwards.
    """
    has_book = "book" in st.session_state
    door_html = _render_onboarding_html(has_book=has_book)
    st.markdown(door_html, unsafe_allow_html=True)

    # ── 3-button action row ───────────────────────────────────────────────────
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button(
            "▸ Explore sample book (10 stocks)", key="ob_sample", type="primary"
        ):
            st.session_state["book"] = load_sample_book()
            st.rerun()

    with col2:
        if is_local_runtime():
            if st.button("↓ Upload holdings CSV", key="ob_csv_toggle"):
                st.session_state["_show_csv_upload"] = not st.session_state.get(
                    "_show_csv_upload", False
                )

    with col3:
        if st.button("+ Add manually", key="ob_manual"):
            st.session_state["_show_manual_form"] = not st.session_state.get(
                "_show_manual_form", False
            )

    # ── Full-width CSV uploader — revealed on toggle (outside narrow columns) ─
    if st.session_state.get("_show_csv_upload", False) and is_local_runtime():
        uploaded = st.file_uploader(
            "Drop a CSV with columns: symbol, quantity, book value (cad), exchange, account type",
            type=["csv"],
            key="ob_csv",
            label_visibility="visible",
        )
        if uploaded is not None:
            try:
                content = uploaded.read().decode("utf-8")
                import tempfile  # noqa: PLC0415

                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".csv", delete=False
                ) as tmp:
                    tmp.write(content)
                    tmp_path = tmp.name
                holdings = read_holdings(tmp_path)
                if not holdings:
                    st.error(
                        "No valid holdings found. Check columns: "
                        "symbol, quantity, book value (cad), exchange, account type."
                    )
                else:
                    st.session_state["book"] = holdings
                    st.session_state["_show_csv_upload"] = False
                    st.rerun()
            except Exception as exc:  # noqa: BLE001
                st.error(f"Could not parse holdings CSV: {exc}")

    # Manual-entry form — toggled by the button above
    if st.session_state.get("_show_manual_form", False):
        with st.form("manual_holding_form", clear_on_submit=True):
            st.markdown(
                '<div class="ri-sec">Add holding manually</div>',
                unsafe_allow_html=True,
            )
            f_ticker = st.text_input("Ticker symbol", placeholder="e.g. AAPL")
            f_shares = st.number_input("Shares", min_value=0.0, step=1.0, value=1.0)
            f_cost = st.number_input(
                "Cost basis / book value", min_value=0.0, step=0.01, value=0.0
            )
            f_account = st.text_input(
                "Account type", value="TFSA", placeholder="e.g. TFSA, RRSP, Non-reg"
            )
            submitted = st.form_submit_button("Add to book")
            if submitted:
                ticker_clean = f_ticker.strip().upper()
                if not ticker_clean:
                    st.error("Ticker symbol is required.")
                else:
                    holding = make_manual_holding(
                        ticker=ticker_clean,
                        shares=float(f_shares),
                        cost_basis=float(f_cost),
                        account_type=f_account.strip() or "TFSA",
                    )
                    existing: list[object] = list(st.session_state.get("book", []))
                    existing.append(holding)
                    st.session_state["book"] = existing
                    st.session_state["_show_manual_form"] = False
                    st.rerun()


def render(
    path: str = _SUMMARY_PATH,
    adherence_path: str = _ADHERENCE_PATH,
    reports_dir: str = _REPORTS_DIR,
) -> None:
    summary = load_brief_summary(path)

    # ── Landing door — ALWAYS rendered (FIX A: persistent so CSV/manual stay
    #    reachable even when a book/brief is loaded).  Button handlers set
    #    st.session_state["book"] and call st.rerun() so the Front-Desk below
    #    picks up the new book on the next cycle. ──────────────────────────────
    _handle_onboarding()

    # ── If no brief and no session book, nothing to show below the door ──────
    if summary is None and "book" not in st.session_state:
        st.warning(
            "No structured brief found. Run "
            "`python -m application.cli weekly-brief` to generate it "
            "(stays on your machine)."
        )
        return

    if summary is None:
        # Session book present (uploaded or sample) but no brief_summary.json.
        # Defer to future sprint: for now show a neutral notice.
        st.info("Book loaded from session. Run weekly-brief to see Front-Desk vitals.")
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
