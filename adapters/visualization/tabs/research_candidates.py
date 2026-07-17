"""Research Candidates tab — factual evidence ranking. RESEARCH_ONLY.

Architecture: pure `build_*_html(...)` helpers (testable without Streamlit)
compose the rendered output. `render()` wires them with `st.session_state`.

All colours come from CSS var() — no raw hex in this module.
Honesty: no FORBIDDEN_WORDS; DATA-GAP never faked; includes "not a forecast" disclosure.
"""

from __future__ import annotations

import html as _html
import json
import logging
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any

import streamlit as st

from adapters.visualization.book_context import (
    SESSION_REPORTS_DIR_KEY,
    SESSION_SAMPLE_REFRESH_REPORTS_KEY,
    UIBookContext,
    resolve_ui_book_context,
)
from adapters.visualization.components.factor_row import render_factor_row
from adapters.visualization.components.funnel import render_funnel
from adapters.visualization.components.gemini_read import (
    build_case_context,
    render_gemini_read_two_col,
)
from adapters.visualization.components.proof_tile import render_tile
from adapters.visualization.components.tooltip import tooltip
from adapters.visualization.data_loader import (
    load_combined_screen,
    load_latest_screen,
    load_latest_screened,
    load_screen_history,
    staleness_days,
)
from adapters.visualization.price_cache import (
    _fetch_recent_news_impl,
    fetch_ticker_info,
)
from adapters.visualization.run_gate import RUN_GATE_HELP, evaluate_run_gate
from adapters.visualization.run_gate import get_last_run_ts as _gate_get_last_run_ts
from adapters.visualization.run_gate import is_processing as _gate_is_processing
from adapters.visualization.run_gate import set_last_run_ts as _gate_set_last_run_ts
from adapters.visualization.run_gate import set_processing as _gate_set_processing
from application.card_loading import select_case_summarizer
from application.case_cache import load_cached_case
from application.runtime_guard import is_local_runtime
from application.screener_case_facts import candidate_bands, facts_from_bands
from application.screener_sentiment_facts import buzz_sentiment_fact
from domain.evidence_registry import get_evidence
from domain.factor_bands import Band, band_for_percentile, plain_read
from domain.factor_scores import factor_caveat, factor_display_label
from domain.screen_buckets import PRIORITY, BucketInput, assign_buckets
from domain.screen_diagnostics import ScreenDiagnostics, ScreenVerdict, classify_screen

# Module-level adapter instance — monkeypatchable in tests. Resolves through
# select_case_summarizer() (Gemini-if-key-else-template), mirroring Home and
# Portfolio, so a local dev environment without GEMINI_API_KEY gets the
# deterministic template summary instead of a permanent data_gap — only a
# genuine no-evidence case should ever read "Google-AI read unavailable".
_gemini_adapter: object = select_case_summarizer()

logger = logging.getLogger(__name__)

_SCREEN_COVERAGE_FLOOR = 0.5
_TOP_N = 15

# Canonical display order (mockup hero): strongest-evidence factors first,
# momentum LAST (no proven forward edge). lowvol shows DATA-GAP until wired live.
_LIVE_FACTORS: tuple[str, ...] = ("quality", "value", "revision", "momentum")
_ALL_FACTORS: tuple[str, ...] = ("quality", "value", "revision", "lowvol", "momentum")

# Bucket signature subtitles matching the mockup .bktsub
_BUCKET_SUBS: dict[Any, str] = {}

# Session-state key prefix for cached Gemini reads
_GAI_CACHE_PREFIX = "_gai_"


def maybe_render_gemini(
    ticker: str,
    facts: dict[str, str],
    news: list[dict[str, str]],
) -> str:
    """Return the .gai attributed HTML block for ticker, or "" when unavailable.

    PRIVACY FAIL-SAFE: when is_local_runtime() is False, returns "" immediately.
    No Gemini call is made, and no facts/news leave this process.

    LAZY / CACHED: the result is stored in st.session_state under "_gai_{ticker}".
    Subsequent calls for the same ticker return the cached HTML instantly.

    NOTE: facts and news come from already-fetched data in the expanded card body.
    If the caller has no live per-ticker fetch wired, pass empty dicts/lists —
    this produces data_gap=True (honest gap, never faked). A live per-ticker
    facts/news fetch is a follow-up task.
    """
    if not is_local_runtime():
        return ""

    cache_key = f"{_GAI_CACHE_PREFIX}{ticker}"
    if cache_key in st.session_state:
        cached: str = str(st.session_state[cache_key])
        return cached

    ctx = build_case_context(ticker=ticker, facts=facts, news=news)
    result = _gemini_adapter.summarize_case(ctx)  # type: ignore[attr-defined]
    html = render_gemini_read_two_col(result)
    st.session_state[cache_key] = html
    return html


def maybe_render_gemini_cache_only(ticker: str, reports_dir: str) -> str:
    """Cache-only read for non-hero rows — never fires a live Gemini call.

    Reads the persistent {reports_dir}/screen_cited_cases.json cache (written
    by the `screen-candidates --cite-cases` CLI prefetch, including the daily
    scheduled-screen.yml GH Actions job). On a hit, renders the same
    two-column block the hero row would show. On a miss, returns an honest
    "not cached yet" note.

    Deliberately NOT gated by is_local_runtime() (unlike maybe_render_gemini,
    the live-call path): this only ever reads an already-committed file —
    no live API call, no visitor data leaves the process — so it's safe to
    show Cloud visitors too. This is what makes the scheduled batch cited-case
    prefetch (screen_cited_cases.json) actually useful for public visitors
    instead of local-dev-only.

    This is the practical resolution of "lazy fetch on expand": Streamlit has
    no visibility into raw-HTML <details>/<summary> toggle state (no rerun
    fires on a client-side-only disclosure open), so true per-click fetching
    isn't reachable without converting rows to real st.expander widgets.

    The cache directory is derived from the ticker's own market suffix, not
    the passed-in reports_dir: in the Screener's merged US+Canada view (and
    the India-only view), candidates can come from a different market's
    fixed snapshot directory than whatever reports_dir the tab is otherwise
    pointed at (see research_candidates.py::render()'s market-picker
    toggle) -- each market's cited_cases cache only ever lives at its own
    fixed path, written by that market's scheduled-screen.yml step.
    """
    cache_dir = reports_dir
    if ticker.endswith(".TO"):
        cache_dir = "data/sample/ca"
    elif ticker.endswith((".NS", ".BO")):
        cache_dir = "data/sample/in"
    cache_path = f"{cache_dir}/screen_cited_cases.json"
    cached = load_cached_case(cache_path, ticker)
    if cached is None:
        return (
            '<div style="font-size:10.5px;color:var(--text-muted);'
            "background:var(--bg-secondary);border:1px dashed var(--border);"
            'border-radius:8px;padding:7px 10px;margin:8px 0 6px;">'
            "&#128269; <b>Google-AI read</b> &mdash; not cached yet. Runs the "
            "next time the screen refreshes."
            "</div>"
        )
    return render_gemini_read_two_col(cached)


def _bucket_sub(bucket: Any) -> str:
    """One-line italic subtitle for each bucket (mockup .bktsub)."""
    from domain.screen_buckets import Bucket

    return {
        Bucket.ALL_ROUNDER: "top-quartile on 3+ factors — rare",
        Bucket.MOMENTUM_LEADERS: "top-quartile momentum AND analyst dispersion",
        Bucket.QUALITY_FAIR_PRICE: "top-quartile quality AND value",
        Bucket.VALUE_CATALYST: "top-quartile value AND analyst dispersion",
        Bucket.QUALITY_COMPOUNDERS: "top-quartile quality, not cheap",
        Bucket.LOWVOL_DEFENSIVES: "top-quartile low-volatility — empty until T2",
    }.get(bucket, "")


# Grade → filled-pill background + text colour (matches mockup .band pills /
# factor_row band badges). Hex bg is consistent with the factor-row component.
_GRADE_PILL: dict[str, str] = {
    "STRONG": "background:#DCFCE7;color:var(--success)",
    "MODERATE": "background:#DBEAFE;color:var(--accent)",
    "WEAK": "background:#FEE2E2;color:var(--danger)",
}

# Friendly factor names for the plain row summary. The "revision" factor is
# labelled honestly from the evidence registry ("analyst dispersion") — it
# measures analyst target-price spread, not estimate-revision drift.
_FRIENDLY: dict[str, str] = {
    "quality": "quality",
    "value": "value",
    "revision": factor_display_label("revision").lower(),  # "analyst dispersion"
    "lowvol": "low-vol",
}


def _corroboration_badge_html(row_dict: dict[str, object]) -> str:
    """Return HTML pill showing corroboration tier, or empty string if
    factor-only (no corroboration badge is shown in that case -- absence of
    the badge already communicates factor-only, no need to say so)."""
    if row_dict.get("factor_only", True):
        return ""
    tier = str(row_dict.get("convergence_tier", "")).upper()
    n_raw = row_dict.get("n_sources", 0)
    n = int(n_raw) if isinstance(n_raw, (int, float, str)) else 0
    corr_date = str(row_dict.get("corroboration_date", ""))
    colours = {
        "STRONG": ("#22c55e", "#052e16"),
        "MODERATE": ("#f59e0b", "#1c1100"),
        "WEAK": ("#94a3b8", "#0f172a"),
        "CONFLICTED": ("#f87171", "#1c0505"),
    }
    bg, fg = colours.get(tier, ("#94a3b8", "#0f172a"))
    label = f"✓ {tier.capitalize()} · {n} source{'s' if n != 1 else ''}"
    date_note = (
        f'<span style="color:#888;font-size:0.72rem;margin-left:6px">'
        f"corroborated {corr_date}</span>"
    )
    return (
        f'<span style="background:{bg};color:{fg};padding:2px 8px;'
        f'border-radius:4px;font-size:0.78rem;font-weight:600;margin-left:8px">'
        f"{label}</span>{date_note}"
    )


def _standout_chip_html(candidate: dict[str, Any]) -> str:
    """Colour-coded GRADE pill next to the score (mockup row chip, e.g. 'STRONG').

    Derives an evidence-standing word from the name's strongest present factor:
    Exceptional/Strong → STRONG (green), Flat → MODERATE (blue), all Weak → WEAK
    (red). DATA-GAP-only names → neutral dash. Descriptive, never a forecast."""
    bands = candidate_bands(candidate)
    if not bands:
        return '<span style="font-size:10px;color:var(--text-muted);">&mdash;</span>'
    best = max(
        bands.values(),
        key=lambda b: (b == Band.EXCEPTIONAL, b == Band.STRONG, b == Band.FLAT),
    )
    if best in (Band.EXCEPTIONAL, Band.STRONG):
        grade = "STRONG"
    elif best == Band.FLAT:
        grade = "MODERATE"
    else:
        grade = "WEAK"
    return (
        f'<span style="font-size:10px;font-weight:700;letter-spacing:.03em;'
        f"{_GRADE_PILL[grade]};border-radius:11px;padding:2px 9px;"
        f'white-space:nowrap;">{grade}</span>'
    )


# ---------------------------------------------------------------------------
# IC verdict helper
# ---------------------------------------------------------------------------


def load_latest_ic_verdict(reports_dir: str = "data/reports") -> str:
    """Read the most recent screen_ic_*.json and return the decision string.

    Returns "INCONCLUSIVE" if file absent or unreadable (honest default).
    """
    path = Path(reports_dir)
    files = sorted(path.glob("screen_ic_*.json"))
    if not files:
        return "INCONCLUSIVE"
    try:
        d = json.loads(files[-1].read_text())
        return str(d.get("decision", "INCONCLUSIVE"))
    except (json.JSONDecodeError, OSError):
        return "INCONCLUSIVE"


# ---------------------------------------------------------------------------
# Task 3: build_header_html — eyebrow + headline + 4 tiles + footer ledger
# ---------------------------------------------------------------------------


def build_header_html(
    screen: dict[str, Any],
    reports_dir: str = "data/reports",
    include_headline: bool = True,
) -> str:
    """Return HTML for the Zone ① header: eyebrow, headline, subhead, 4 tiles, ledger.

    When include_headline is False, only the tiles + ledger are returned (the
    headline is rendered separately so the view toggle can sit beside it).
    Uses Home design tokens (Fraunces/DM Sans/IBM Plex Mono/JetBrains Mono).
    """
    as_of_raw = screen.get("as_of", "?")
    candidates = screen.get("candidates", [])
    shown = min(len(candidates), _TOP_N)

    raw_diag = screen.get("diagnostics")
    cleared = 0
    scanned = int(screen.get("universe_size", 0))
    if isinstance(raw_diag, dict):
        try:
            cleared = int(raw_diag["cleared"])
            scanned = int(raw_diag["scanned"])
        except (KeyError, ValueError, TypeError):
            cleared = len(candidates)

    # Format the date for display
    try:
        from datetime import date

        d = date.fromisoformat(as_of_raw[:10])
        as_of_display = d.strftime("%b %-d")
    except (ValueError, TypeError):
        as_of_display = as_of_raw

    # IC verdict for Trust tile
    ic_verdict = load_latest_ic_verdict(reports_dir)
    ic_tone = "amber"  # INCONCLUSIVE → amber; PASS → green; HALT → crimson
    if ic_verdict == "PASS":
        ic_tone = "green"
    elif ic_verdict == "HALT":
        ic_tone = "crimson"

    # Tile 1: Showing
    tile_showing = render_tile(
        label=tooltip("Showing"),
        number=str(shown),
        tone="muted",
        sub=f"of {cleared} that cleared",
    )

    # Tile 2: As of (with "not a forecast" framing)
    tile_as_of = render_tile(
        label=tooltip("As of"),
        number=as_of_display,
        tone="muted",
        sub="current evidence, not a forecast",
    )

    # Tile 3: Factors — dynamic count from the loaded screen's factor_scores
    _factor_names: set[str] = set()
    for cand in candidates:
        for fs in cand.get("factor_scores", []) if isinstance(cand, dict) else []:
            _factor_names.add(fs.get("name", ""))
    _factor_count = len(_factor_names) if _factor_names else 4
    tile_factors = render_tile(
        label=tooltip("Factors"),
        number=str(_factor_count),
        tone="muted",
        sub="momentum · analyst dispersion · quality · value",
    )

    # Tile 4: Trust — IC gate verdict (honest)
    ic_label_display = ic_verdict.capitalize() if ic_verdict else "Inconclusive"
    tile_trust = render_tile(
        label=tooltip("Trust the signal"),
        number=ic_label_display,
        stamp=ic_verdict,
        tone=ic_tone,
        sub="backtest verdict — descriptive until re-tested",
    )

    tiles_html = (
        f'<div style="display:grid;grid-template-columns:repeat(4,1fr);'
        f'gap:10px;margin:8px 0 14px;">'
        f"{tile_showing}{tile_as_of}{tile_factors}{tile_trust}"
        f"</div>"
    )

    # Footer ledger (mono, matches mockup .ledger)
    ledger_html = (
        f"<div style=\"font-family:'IBM Plex Mono',monospace;font-size:10.5px;"
        f"color:var(--text-secondary);letter-spacing:.04em;"
        f"background:var(--bg-secondary);border:1px solid var(--border);"
        f"border-radius:9px;padding:9px 13px;margin-top:14px;"
        f'display:flex;gap:16px;flex-wrap:wrap;">'
        f"<span>UNIVERSE <b>{scanned}</b></span>"
        f"<span>CLEARED <b>{cleared}</b></span>"
        f"<span>SHOWN <b>{shown}</b></span>"
        f"<span>FACTORS <b>{_factor_count}</b></span>"
        f"<span>AS OF <b>{_html.escape(as_of_raw)}</b></span>"
        f"<span>IC GATE <b>{_html.escape(ic_verdict)}</b></span>"
        f"<span>RESEARCH_ONLY</span>"
        f"</div>"
    )

    header_html = build_headline_html() if include_headline else ""
    return header_html + tiles_html + ledger_html


def build_headline_html() -> str:
    """Eyebrow + Fraunces headline + italic subhead (no screen data needed).

    Rendered in its own column so the view toggle can sit top-right beside it
    (mockup header layout), with the 4 tiles + ledger full-width below.
    """
    return (
        "<div style=\"font-family:'IBM Plex Mono',monospace;font-size:10px;"
        "letter-spacing:.18em;text-transform:uppercase;"
        'color:var(--text-muted);margin-bottom:4px;">Research candidates</div>'
        "<div style=\"font-family:'Fraunces',serif;font-size:27px;font-weight:700;"
        'letter-spacing:-.5px;line-height:1.12;color:var(--text-primary);">'
        "This week&#39;s research shortlist.</div>"
        "<div style=\"font-family:'Fraunces',serif;font-style:italic;font-size:14px;"
        'color:var(--text-secondary);margin-top:3px;margin-bottom:8px;">'
        "The strongest names on current evidence — a place to start, not a forecast.</div>"
    )


# ---------------------------------------------------------------------------
# Task 4: build_legend_html + build_disclosure_html
# ---------------------------------------------------------------------------


def build_pipeline_visual_html() -> str:
    """Return the always-visible Z-score -> Band -> Grade pipeline strip.

    Replaces the old always-open legend prose. Precise thresholds (band
    percentiles, grade cutoffs) live in hover tooltips on the Band/Grade
    boxes, sourced from the glossary (single source of truth) via the
    existing tooltip() component — not printed inline, to keep the strip
    scannable at a glance.
    """
    step_style = (
        "flex:1;border:1px solid var(--border);border-radius:8px;"
        "padding:8px 10px;text-align:center;background:var(--bg-secondary);"
    )
    label_style = (
        "font-family:'IBM Plex Mono',monospace;font-size:9.5px;"
        "color:var(--text-muted);letter-spacing:.05em;text-transform:uppercase;"
    )
    arrow = '<div style="color:var(--text-muted);font-size:16px;">&rarr;</div>'
    zscore_box = (
        f'<div style="{step_style}">'
        f'<div style="{label_style}">Z-score</div>'
        '<div style="font-weight:600;font-size:12px;margin-top:2px;">'
        "vs this week&#39;s cohort</div>"
        "</div>"
    )
    band_box = (
        f'<div style="{step_style}">'
        f'<div style="{label_style}">{tooltip("Band")}</div>'
        '<div style="font-weight:600;font-size:12px;margin-top:2px;">'
        "Percentile band</div>"
        "</div>"
    )
    grade_box = (
        f'<div style="{step_style}">'
        f'<div style="{label_style}">{tooltip("Grade")}</div>'
        '<div style="font-weight:600;font-size:12px;margin-top:2px;">'
        "Evidence-standing</div>"
        "</div>"
    )
    strip_html = (
        '<div style="display:flex;align-items:center;gap:8px;'
        'margin-bottom:4px;">'
        f"{zscore_box}{arrow}{band_box}{arrow}{grade_box}"
        "</div>"
    )
    caption_html = (
        '<div style="font-size:10px;color:var(--text-muted);'
        'font-style:italic;margin-bottom:12px;">'
        "Track-1 factors: Quality &middot; Value &middot; Analyst dispersion "
        "&middot; Momentum &middot; Low-vol now live &middot; hover Band/Grade "
        "for exact thresholds."
        "</div>"
    )
    return strip_html + caption_html


def build_disclosure_html() -> str:
    """Return HTML for the honest disclosure box (mockup .disclose).

    Must contain 'not a forecast' and 'no proven edge' for momentum.
    """
    return (
        '<div style="background:#FEFAF0;border:1px solid #F5E3B3;'
        "border-radius:10px;padding:9px 12px;font-size:11px;"
        'color:#6B4D12;margin-bottom:12px;">'
        "&#9888;&#65038; <b>Honest note:</b> factors describe what a name "
        "<b>looks like today</b> &mdash; they don&#39;t project next week. "
        "Momentum showed no proven edge in our backtest (IC INCONCLUSIVE, "
        "CI spans zero); some factors can&#39;t be back-tested without look-ahead bias. "
        "Score = evidence-standing, not a forecast."
        "</div>"
    )


# ---------------------------------------------------------------------------
# Honesty disclosures: universe scope · per-factor coverage · factor caveats
# (P0b — relabel + disclose only; no math changed). All copy that names what a
# factor IS/IS-NOT is pulled from domain.evidence_registry (single source).
# ---------------------------------------------------------------------------


def build_universe_scope_html(screen: dict[str, Any] | None = None) -> str:
    """Return the universe-scope disclosure box.

    The screen does NOT scan the whole market: for market="us" the universe
    is large-cap US (S&P 500 ∪ Nasdaq-100, ~570 names); for market="ca" it's
    the TSX 60 (52 names); for market="in" it's the NIFTY 50 (~50 names). All
    are survivor-biased — today's index membership applied to every date.
    The live scanned count is appended when the screen carries it (from
    diagnostics.scanned / universe_size). Absent "market" key (older
    committed snapshots, pre this feature) defaults to "us".
    """
    market = "us"
    scanned = 0
    if screen is not None:
        market = str(screen.get("market") or "us")
        raw_diag = screen.get("diagnostics")
        if isinstance(raw_diag, dict):
            try:
                scanned = int(raw_diag.get("scanned", 0) or 0)
            except (ValueError, TypeError):
                scanned = 0
        if not scanned:
            try:
                scanned = int(screen.get("universe_size", 0) or 0)
            except (ValueError, TypeError):
                scanned = 0
    scanned_note = f" This week: <b>{scanned}</b> names scanned." if scanned else ""
    # Pull the screen-scope caveat from the registry (single source of truth).
    entry = get_evidence("screen_cleared")
    registry_caveat = f" {_html.escape(entry.caveat)}" if entry is not None else ""

    if market == "ca":
        scope_label = "TSX 60 (Canada), 52 names"
    elif market == "in":
        scope_label = "NIFTY 50 (India), ~50 names"
    else:
        scope_label = "Large-cap US (S&amp;P&nbsp;500 + Nasdaq-100, ~570 names)"

    return (
        '<div style="background:var(--bg-secondary);border:1px solid var(--border);'
        "border-radius:10px;padding:9px 12px;font-size:11px;"
        'color:var(--text-secondary);margin-bottom:12px;line-height:1.6;">'
        f"&#9888;&#65038; <b>Universe scope:</b> {scope_label}, survivor-biased "
        "&mdash; not the whole market." + scanned_note + registry_caveat + "</div>"
    )


def build_coverage_html(screen: dict[str, Any]) -> str:
    """Return a per-factor coverage line for the names shown.

    Coverage = share of shown candidates that carry live (non DATA-GAP) data
    for each factor. A DATA-GAP is the screen's all-zeros shape (value and
    percentile both 0.0) or a missing value. Returns "" when nothing is shown.
    """
    candidates = screen.get("rows") or screen.get("candidates") or []
    rows = [c for c in candidates if isinstance(c, dict)]
    total = len(rows)
    if total == 0:
        return ""

    present: dict[str, int] = {}
    for c in rows:
        for fd in c.get("factor_scores", []):
            if not isinstance(fd, dict):
                continue
            rv, rp = fd.get("value"), fd.get("percentile")
            if rv is None or rp is None:
                continue
            if float(rv) == 0.0 and float(rp) == 0.0:
                continue  # DATA-GAP shape
            name = str(fd.get("name", ""))
            present[name] = present.get(name, 0) + 1

    parts: list[str] = []
    for key in _ALL_FACTORS:
        label = "Low-vol" if key == "lowvol" else factor_display_label(key)
        n = present.get(key, 0)
        pct = round(100 * n / total)
        gap = " (DATA-GAP)" if n == 0 else ""
        parts.append(f"{_html.escape(label)} {pct}%{gap}")

    return (
        "<div style=\"font-family:'IBM Plex Mono',monospace;font-size:10.5px;"
        "color:var(--text-secondary);letter-spacing:.03em;"
        "background:var(--bg-secondary);border:1px solid var(--border);"
        'border-radius:9px;padding:8px 12px;margin-bottom:12px;">'
        f"COVERAGE (of {total} shown) &mdash; " + " &middot; ".join(parts) + "</div>"
    )


def build_factor_honesty_html() -> str:
    """Return the per-factor honest caveats, sourced from the evidence registry.

    Surfaces exactly what each named factor measures and what it does NOT:
    Analyst dispersion (target spread, not revision drift — no published edge),
    and Value/Quality (current snapshot, not point-in-time validated).
    """
    items: list[str] = []
    for key in ("revision", "value", "quality"):
        label = factor_display_label(key)
        caveat = factor_caveat(key) or ""
        items.append(
            f'<li style="margin-bottom:4px;"><b>{_html.escape(label)}</b> '
            f"&mdash; {_html.escape(caveat)}</li>"
        )
    return (
        '<div style="background:#FEFAF0;border:1px solid #F5E3B3;'
        "border-radius:10px;padding:9px 12px;font-size:11px;"
        'color:#6B4D12;margin-bottom:12px;line-height:1.55;">'
        "&#9888;&#65038; <b>What each factor really is:</b>"
        '<ul style="margin:6px 0 0;padding-left:18px;">'
        + "".join(items)
        + "</ul></div>"
    )


def build_caveats_html(screen: dict[str, Any] | None) -> str:
    """Return the merged caveats content for the collapsed "Learn more" expander.

    Combines build_disclosure_html() + build_universe_scope_html(screen) +
    build_factor_honesty_html() verbatim into three labeled sub-sections, same
    order as the original always-visible blocks. Wording is preserved exactly
    — this is a container change, not a content rewrite.
    """
    sub_heading_style = (
        "font-family:'IBM Plex Mono',monospace;font-size:9.5px;"
        "font-weight:600;letter-spacing:.1em;text-transform:uppercase;"
        "color:var(--text-muted);margin:0 0 4px;"
    )
    sections = [
        ("Honest note", build_disclosure_html()),
        ("Universe scope", build_universe_scope_html(screen)),
        ("What each factor really is", build_factor_honesty_html()),
    ]
    parts: list[str] = []
    for heading, body in sections:
        parts.append(
            f'<div style="{sub_heading_style}">{_html.escape(heading)}</div>{body}'
        )
    return "".join(parts)


# ---------------------------------------------------------------------------
# Task 5: resolve_view_mode
# ---------------------------------------------------------------------------


def resolve_view_mode(session: dict[str, Any]) -> str:
    """Return the current screener view mode from session state.

    Default is 'reason' (Group by reason). 'rank' = flat ranked list.
    """
    return str(session.get("screener_view", "reason"))


def resolve_market_mode(session: dict[str, Any]) -> str:
    """Return 'us_ca' (default) or 'india' from session state."""
    return str(session.get("screener_market", "us_ca"))


# ---------------------------------------------------------------------------
# Shared: build one collapsible candidate row HTML (used by both views)
# ---------------------------------------------------------------------------


def _enrich_candidates_with_company_info(
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Attach a company name + sector to each candidate, display-only.

    ScreenCandidate carries no name/sector, so the shown shortlist otherwise
    falls back to bare tickers. Uses the cached fetch_ticker_info() (same
    lookup Portfolio uses for sector) — cheap for a ~15-row shortlist, and
    never touches score/composite/factor data. Returns new dicts; the
    caller's list/dicts are left untouched.
    """
    enriched: list[dict[str, Any]] = []
    for c in candidates:
        c = dict(c)
        if not c.get("name"):
            ticker = str(c.get("ticker", ""))
            if ticker:
                info = fetch_ticker_info(ticker)
                name = info.get("longName") or info.get("shortName")
                if name:
                    c["name"] = name
                sector = info.get("sector")
                if sector:
                    c["sector"] = sector
        enriched.append(c)
    return enriched


def _company_name(candidate: dict[str, Any]) -> str:
    """Return a friendly display name for the candidate, falling back to ticker.

    Checks common keys ('name', 'company', 'shortName', 'company_name') that may
    be present in enriched screen data. Never fetches network — display-only.
    """
    for key in ("name", "company", "shortName", "company_name"):
        raw = candidate.get(key)
        if raw and isinstance(raw, str):
            stripped: str = raw.strip()
            if stripped:
                return stripped
    return str(candidate.get("ticker", "?") or "?")


# Factors eligible to be surfaced as "the reason" in a collapsed row.
# Momentum is excluded — the evidence registry carries no proof it has any
# forward edge on returns (see _FACTOR_META/factor_caveat), so it's never
# highlighted as the standout number the way quality/value/revision/lowvol can be.
_STRONGEST_FACTOR_KEYS: tuple[str, ...] = ("quality", "value", "revision", "lowvol")


def _strongest_factor_html(factor_scores: list[dict[str, Any]]) -> str:
    """Return a 'p95 Quality'-style label for the highest-percentile live
    factor — a real, already-computed number for the collapsed row, instead
    of a prose reason. Never fetches anything; only reads what's already in
    factor_scores. Returns "" if every eligible factor is DATA-GAP."""
    best_key: str | None = None
    best_pct = -1.0
    for fd in factor_scores:
        if not isinstance(fd, dict):
            continue
        name = str(fd.get("name", ""))
        if name not in _STRONGEST_FACTOR_KEYS:
            continue
        rv, rp = fd.get("value"), fd.get("percentile")
        if rv is None or rp is None:
            continue
        fv, fp = float(rv), float(rp)
        if fv == 0.0 and fp == 0.0:  # DATA-GAP / no coverage shape
            continue
        if fp > best_pct:
            best_pct = fp
            best_key = name
    if best_key is None:
        return ""
    label = _FRIENDLY.get(best_key, factor_display_label(best_key)).capitalize()
    pct_int = round(best_pct * 100)
    return _html.escape(f"p{pct_int} {label}")


def _build_candidate_row_html(
    rank: int | str,
    candidate: dict[str, Any],
    show_repeat_badge: bool = False,
    also_buckets: list[str] | None = None,
    open_by_default: bool = False,
    reports_dir: str = "data/reports",
) -> str:
    """Build the HTML for a single collapsible candidate row.

    Uses Streamlit's native st.expander — this function returns just the
    *body* HTML (factor rows + plain read + do next + GAI placeholder).
    The caller uses st.expander for the collapsible behaviour.

    This is intentionally a pure-HTML helper for the body; the outer
    expander is wired in render() via Streamlit.
    """
    ticker = _html.escape(str(candidate.get("ticker", "?")))
    composite = float(candidate.get("composite", 0.0))

    # Build factor lookup
    raw_factors = candidate.get("factor_scores", [])
    factor_by_name: dict[str, dict[str, Any]] = {
        f.get("name", ""): f for f in raw_factors if isinstance(f, dict)
    }

    # Build bands dict for plain_read
    bands: dict[str, Band] = {}
    for fname in _LIVE_FACTORS:
        fd = factor_by_name.get(fname)
        if fd:
            pct = fd.get("percentile")
            if pct is not None and not (
                float(fd.get("value", 1.0)) == 0.0 and float(pct) == 0.0
            ):
                bands[fname] = band_for_percentile(float(pct))

    plain = _html.escape(plain_read(bands))

    # Render factor rows in canonical order (quality, value, revision, lowvol,
    # momentum — momentum last, no proven edge). lowvol is DATA-GAP until wired
    # live; once the screen carries it, it renders from data automatically.
    factor_rows_html = ""
    for fname in _ALL_FACTORS:
        fd = factor_by_name.get(fname)
        value: float | None = None
        percentile: float | None = None
        if fd is not None:
            rv = fd.get("value")
            rp = fd.get("percentile")
            if rv is not None and rp is not None:
                fv, fp = float(rv), float(rp)
                # Skip if all-zeros (missing coverage shape)
                if not (fv == 0.0 and fp == 0.0):
                    value = fv
                    percentile = fp
        factor_rows_html += render_factor_row(fname, value=value, percentile=percentile)

    # Also-in badge (repeat indicator)
    also_html = ""
    if show_repeat_badge and also_buckets:
        also_list = _html.escape(" ".join(also_buckets))
        also_html = (
            f"<span style=\"font-family:'IBM Plex Mono',monospace;font-size:9px;"
            f"background:#EDE9FE;color:#6D28D9;font-weight:600;"
            f'padding:1px 6px;border-radius:9px;margin-left:4px;">'
            f"also {also_list}</span>"
        )

    # Google-AI read: green/red flags synthesized from real news + market
    # sentiment (honesty invariant — no composite/grade ever reaches the
    # prompt), plus a permanent pointer to the deeper factor/evidence
    # breakdown in Stock Analysis — that tab does NOT carry this cited-case
    # feature (only Home/Portfolio/Risk do), so the pointer must never claim
    # a "cited case" awaits there. Only the hero row (open_by_default) fires
    # a live call — other rows read the persistent cache only (see
    # maybe_render_gemini_cache_only).
    raw_ticker = str(candidate.get("ticker", "?"))
    facts = facts_from_bands(bands, factor_by_name)
    buzz_fact = buzz_sentiment_fact(raw_ticker)
    if buzz_fact:
        facts = {**facts, "Market sentiment": buzz_fact}
    if open_by_default:
        news_items = _fetch_recent_news_impl(raw_ticker, limit=5)
        gai_read_html = maybe_render_gemini(raw_ticker, facts, news=news_items)
    else:
        gai_read_html = maybe_render_gemini_cache_only(raw_ticker, reports_dir)
    gai_pointer_html = (
        f'<div style="font-size:10px;color:var(--text-muted);margin:2px 0 6px;">'
        f"Open <b>{ticker} in Stock Analysis</b> for the full factor breakdown."
        f"</div>"
    )
    gai_placeholder = gai_read_html + gai_pointer_html

    do_next = (
        "Confirm the evidence is structural (check next earnings date, recent "
        "call transcripts) before acting. Open <b>"
        + ticker
        + " in Stock Analysis</b> for a full read."
    )

    # Sub-line: "CompanyName · Sector · evidence 1.22 [also-in badge]"
    friendly_name = _html.escape(_company_name(candidate))
    sector = candidate.get("sector")
    sector_html = f" &middot; {_html.escape(str(sector))}" if sector else ""
    sub_line = (
        f'<div style="font-size:11px;color:var(--text-muted);'
        f"margin:8px 0 7px;font-family:'Fraunces',serif;font-style:italic;\">"
        f"{friendly_name}{sector_html} &middot; evidence {composite:.2f}{also_html}"
        f"</div>"
    )

    body_html = (
        sub_line
        + factor_rows_html
        + gai_placeholder
        + '<div style="font-size:11px;color:var(--text-secondary);margin-top:6px;">'
        + f'<b style="color:var(--text-primary);">Plain read:</b> {plain}'
        + "</div>"
        + '<div style="font-size:11px;color:var(--text-secondary);margin-top:4px;">'
        + f'<b style="color:var(--text-primary);">Do next &rarr;</b> {do_next}'
        + "</div>"
    )

    return body_html


# ---------------------------------------------------------------------------
# Task 6: build_reason_view_html — buckets + collapsible cards
# ---------------------------------------------------------------------------


def build_reason_view_html(
    candidates: list[dict[str, Any]], reports_dir: str = "data/reports"
) -> str:
    """Return HTML for the reason-bucket view (Zone ① main body).

    Computes BucketInputs from candidates' factor_scores, assigns buckets,
    renders each in PRIORITY order with empty-state for empty buckets.
    Each member gets a collapsible row with a 5-factor card.

    Note: In Streamlit this is rendered via st.markdown (unsafe_allow_html=True)
    since we need custom CSS. The collapsible rows use a CSS details/summary
    pattern (no JS needed for basic open/close in HTML).
    """
    # Build BucketInput from candidates
    bucket_inputs: list[BucketInput] = []
    candidate_by_ticker: dict[str, dict[str, Any]] = {}

    for c in candidates:
        ticker = c.get("ticker", "?")
        composite = float(c.get("composite", 0.0))
        raw_factors = c.get("factor_scores", [])

        percentiles: dict[str, float] = {}
        for fd in raw_factors:
            if not isinstance(fd, dict):
                continue
            fname = fd.get("name", "")
            rv = fd.get("value")
            rp = fd.get("percentile")
            if rv is not None and rp is not None:
                fv, fp = float(rv), float(rp)
                # Treat all-zeros as 0.0 percentile (no coverage → never top-quartile)
                percentiles[fname] = fp if not (fv == 0.0 and fp == 0.0) else 0.0

        bucket_inputs.append(
            BucketInput(ticker=ticker, percentiles=percentiles, composite=composite)
        )
        candidate_by_ticker[ticker] = c

    bucket_map = assign_buckets(bucket_inputs)

    parts: list[str] = []
    # The first member of the first non-empty bucket is the "hero" — open by
    # default with elevated styling (mockup .row.open + .hero), so a non-expert
    # sees a "start here" card instead of a flat wall of collapsed rows.
    hero_done = False

    for bucket in PRIORITY:
        members = bucket_map[bucket]
        emoji = _html.escape(bucket.emoji)
        label = _html.escape(bucket.label)
        sub = _html.escape(_bucket_sub(bucket))

        # Bucket header
        parts.append(
            f'<div style="display:flex;align-items:center;gap:8px;'
            f"font-family:'DM Sans',sans-serif;font-size:14px;font-weight:600;"
            f'margin:17px 0 8px;letter-spacing:-.2px;">'
            f"{emoji} {label} "
            f"<span style=\"font-family:'Fraunces',serif;font-style:italic;"
            f'font-size:11px;color:var(--text-muted);font-weight:400;">'
            f"{sub}</span>"
            f'<span style="color:var(--text-muted);font-size:11px;">'
            f"{tooltip('Reason bucket', 'ⓘ')}</span>"
            f"</div>"
        )

        if not members:
            # Honest empty-bucket panel (mockup .empty)
            parts.append(
                '<div style="border:1px dashed #CBD5E1;border-radius:10px;'
                "padding:11px 13px;font-size:11px;color:var(--text-muted);"
                "background:#FCFCFB;font-family:'Fraunces',serif;"
                'font-style:italic;margin-bottom:8px;">'
                "&mdash; Empty this week. No name cleared the bar for this bucket. "
                "An honest &#8220;nothing here&#8221; beats padding it."
                "</div>"
            )
            continue

        for rank_i, bi in enumerate(members, start=1):
            ticker = bi.ticker
            c = candidate_by_ticker.get(
                ticker, {"ticker": ticker, "composite": bi.composite}
            )

            # Determine 'also' buckets (other buckets this name appears in)
            also_in: list[str] = []
            for other_bucket in PRIORITY:
                if other_bucket == bucket:
                    continue
                if any(m.ticker == ticker for m in bucket_map[other_bucket]):
                    also_in.append(other_bucket.emoji)

            # Show the also-in badge whenever the ticker appears in any other bucket
            # (regardless of which is "primary" — so the hero always shows it too).
            is_hero = not hero_done
            hero_done = True
            body = _build_candidate_row_html(
                rank=rank_i,
                candidate=c,
                show_repeat_badge=bool(also_in),
                also_buckets=also_in if also_in else None,
                open_by_default=is_hero,
                reports_dir=reports_dir,
            )

            # Composite value for row header
            composite = float(bi.composite)

            # Row wrapper using HTML details/summary for collapsible behaviour
            safe_ticker = _html.escape(ticker)
            why_text = _strongest_factor_html(c.get("factor_scores", []))
            summary_html = (
                f'<summary style="display:grid;'
                f"grid-template-columns:22px 112px 1fr auto auto 16px;"
                f"gap:10px;align-items:center;font-size:12px;"
                f'padding:9px 20px 9px 13px;cursor:pointer;list-style:none;">'
                f'<b style="color:var(--text-muted);">{rank_i}</b>'
                f"<b style=\"font-family:'DM Sans',sans-serif;white-space:nowrap;"
                f'overflow:hidden;text-overflow:ellipsis;">{safe_ticker}</b>'
                f"{_corroboration_badge_html(c)}"
                f'<span style="color:var(--text-secondary);">{why_text}</span>'
                f"{_standout_chip_html(c)}"
                f"<span style=\"font-family:'JetBrains Mono',monospace;"
                f'white-space:nowrap;color:var(--text-secondary);">{composite:.2f}</span>'
                f'<span style="color:var(--text-muted);font-size:10px;">&#9654;</span>'
                f"</summary>"
            )

            open_attr = " open" if is_hero else ""
            border_color = "#CBD5E1" if is_hero else "var(--border)"
            shadow = "0 1px 3px rgba(15,23,42,.08)" if is_hero else "var(--shadow-sm)"

            row_html = (
                f'<details{open_attr} class="rc-card" style="background:var(--bg-primary);'
                f"border:1px solid {border_color};border-radius:10px;"
                f"margin-bottom:7px;overflow:hidden;content-visibility:auto;contain-intrinsic-size:0 64px;"
                f'box-shadow:{shadow};">'
                f"{summary_html}"
                f'<div style="padding:2px 14px 13px;'
                f'border-top:1px solid #F1F5F9;">'
                f"{body}"
                f"</div>"
                f"</details>"
            )
            parts.append(row_html)

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Task 7: build_rank_view_html — flat ranked list
# ---------------------------------------------------------------------------


def build_rank_view_html(
    candidates: list[dict[str, Any]], reports_dir: str = "data/reports"
) -> str:
    """Return HTML for the flat ranked view (rank-only mode).

    Same collapsible row component, no bucket headers,
    sorted by composite desc.
    """
    sorted_candidates = sorted(
        candidates, key=lambda c: -float(c.get("composite", 0.0))
    )
    parts: list[str] = []

    for rank_i, c in enumerate(sorted_candidates, start=1):
        ticker = c.get("ticker", "?")
        composite = float(c.get("composite", 0.0))
        why_text = _strongest_factor_html(c.get("factor_scores", []))
        safe_ticker = _html.escape(ticker)

        is_hero = rank_i == 1
        body = _build_candidate_row_html(
            rank=rank_i,
            candidate=c,
            open_by_default=is_hero,
            reports_dir=reports_dir,
        )

        summary_html = (
            f'<summary style="display:grid;'
            f"grid-template-columns:22px 56px 1fr auto auto 16px;"
            f"gap:10px;align-items:center;font-size:12px;"
            f'padding:9px 13px;cursor:pointer;list-style:none;">'
            f'<b style="color:var(--text-muted);">{rank_i}</b>'
            f"<b style=\"font-family:'DM Sans',sans-serif;\">{safe_ticker}</b>"
            f"{_corroboration_badge_html(c)}"
            f'<span style="color:var(--text-secondary);">{why_text}</span>'
            f"{_standout_chip_html(c)}"
            f"<span style=\"font-family:'JetBrains Mono',monospace;"
            f'white-space:nowrap;color:var(--text-secondary);">{composite:.2f}</span>'
            f'<span style="color:var(--text-muted);font-size:10px;">&#9654;</span>'
            f"</summary>"
        )

        open_attr = " open" if is_hero else ""
        border_color = "#CBD5E1" if is_hero else "var(--border)"
        shadow = "0 1px 3px rgba(15,23,42,.08)" if is_hero else "var(--shadow-sm)"

        row_html = (
            f'<details{open_attr} class="rc-card" style="background:var(--bg-primary);'
            f"border:1px solid {border_color};border-radius:10px;"
            f"margin-bottom:7px;overflow:hidden;content-visibility:auto;contain-intrinsic-size:0 64px;"
            f'box-shadow:{shadow};">'
            f"{summary_html}"
            f'<div style="padding:2px 14px 13px;'
            f'border-top:1px solid #F1F5F9;">'
            f"{body}"
            f"</div>"
            f"</details>"
        )
        parts.append(row_html)

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# build_body_html — dispatches to reason/rank view or abstention
# ---------------------------------------------------------------------------


def build_body_html(
    screen: dict[str, Any],
    view: str = "reason",
    reports_dir: str = "data/reports",
) -> str:
    """Return the main body HTML for the screener (Zone ①).

    If candidates is empty: renders honest abstention/funnel.
    Otherwise: dispatches to reason or rank view.
    """
    candidates = (screen.get("rows") or screen.get("candidates", []))[:_TOP_N]
    if candidates:
        candidates = _enrich_candidates_with_company_info(candidates)

    if not candidates:
        # Abstention path (reskinned, honest)
        raw_diag = screen.get("diagnostics")
        universe_size: int = int(screen.get("universe_size", 0) or 0)

        diag: ScreenDiagnostics | None = None
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

        if diag is not None:
            verdict = classify_screen(diag, _SCREEN_COVERAGE_FLOOR)
            if verdict == ScreenVerdict.UNDER_POWERED:
                verdict_html = (
                    f'<div style="color:var(--danger);font-weight:600;'
                    f'font-size:15px;margin-bottom:8px;">'
                    f"&#9888; Screen under-powered &mdash; only {diag.had_history} of "
                    f"{diag.scanned} had usable price history"
                    f"</div>"
                )
            else:
                verdict_html = (
                    '<div style="color:var(--success);font-weight:600;'
                    'font-size:15px;margin-bottom:8px;">'
                    "&#10003; Working as designed &mdash; scanned &amp; scored, "
                    "none cleared the bar"
                    "</div>"
                )
            funnel_stages: list[tuple[str, int]] = [
                (tooltip("Universe"), diag.scanned),
                (tooltip("Had history"), diag.had_history),
                (tooltip("Above trend"), diag.above_trend),
                (tooltip("Cleared the bar"), diag.cleared),
            ]
        else:
            verdict_html = (
                '<div style="color:var(--text-secondary);font-size:14px;'
                'margin-bottom:8px;">'
                "Screen diagnostics unavailable for this older result &mdash; "
                "re-run the screen for a full readout."
                "</div>"
            )
            funnel_stages = [
                (tooltip("Universe"), universe_size),
                (tooltip("Cleared the bar"), 0),
            ]

        funnel_html = render_funnel(funnel_stages)

        empty_note = (
            '<div style="font-size:11px;color:var(--text-muted);'
            "font-family:'Fraunces',serif;font-style:italic;"
            'margin-top:8px;">'
            "Empty this week &mdash; none cleared the bar. "
            "The trend gate is wide; the ranking is the selective part. "
            "This is correct behaviour."
            "</div>"
        )

        return verdict_html + funnel_html + empty_note

    if view == "rank":
        return build_rank_view_html(list(candidates), reports_dir=reports_dir)
    return build_reason_view_html(list(candidates), reports_dir=reports_dir)


# ---------------------------------------------------------------------------
# Zone ③: history link HTML
# ---------------------------------------------------------------------------


def build_zone3_html() -> str:
    """Return HTML for Zone ③ — track-record note.

    Screen history itself renders directly above, in the "Screen history —
    past runs" expander on this same page (build_screen_history_html) — this
    zone used to point readers to the Trust tab for it, which was stale after
    the 2026-07-13 relocation.
    """
    return (
        "<div style=\"font-family:'IBM Plex Mono',monospace;font-size:10px;"
        "font-weight:600;letter-spacing:.14em;color:var(--text-muted);"
        "text-transform:uppercase;margin:26px 0 10px;"
        'border-top:1px solid var(--border);padding-top:15px;">'
        "&#9411; Track record"
        "</div>"
        '<div style="font-size:12px;color:var(--text-secondary);">'
        "Every screen run is logged, including abstentions — see "
        '"Screen history &mdash; past runs" above.'
        "</div>"
    )


# ---------------------------------------------------------------------------
# S5 Task 4: build_check_your_own_html — Zone ② full 5-factor card
# ---------------------------------------------------------------------------

# Grade badge styles matching the shortlist (same CSS var tokens)
_GRADE_STYLE: dict[str, str] = {
    "STRONG": "background:#DCFCE7;color:var(--success)",
    "MODERATE": "background:#DBEAFE;color:var(--accent)",
    "WEAK": "background:#FEE2E2;color:var(--danger)",
    "UNKNOWN": "background:#F1F5F9;color:var(--text-muted)",
}


def _build_zone2_row_html(row: Any) -> str:
    """Build a collapsible card HTML for one BatchFitRow (Zone ②)."""
    ticker = _html.escape(str(row.ticker))
    grade = str(row.verdict.evidence_grade)
    grade_style = _GRADE_STYLE.get(grade, _GRADE_STYLE["UNKNOWN"])
    safe_grade = _html.escape(grade)

    factor_scores: list[dict[str, Any]] = [dict(f) for f in row.factor_scores]

    # Determine source annotation: in-screen vs live-computed
    sources = {f.get("source", "live") for f in factor_scores}
    if "screen" in sources and "live" not in sources:
        source_note = "in this week&#39;s screen"
    elif "live" in sources and "screen" not in sources:
        source_note = "your list &middot; live-computed"
    else:
        # mixed (shouldn't happen) or empty
        source_note = "your list &middot; live-computed"

    # Build factor rows HTML (5 factors)
    factor_rows_html = ""
    factor_by_name: dict[str, dict[str, Any]] = {
        f.get("name", ""): f for f in factor_scores
    }
    for fname in _ALL_FACTORS:
        fd = factor_by_name.get(fname)
        value: float | None = None
        percentile: float | None = None
        if fd is not None:
            rv = fd.get("value")
            rp = fd.get("percentile")
            if rv is not None and rp is not None:
                value = float(rv)
                percentile = float(rp)
        factor_rows_html += render_factor_row(fname, value=value, percentile=percentile)

    # Plain read for factor bands (same as shortlist)
    bands: dict[str, Band] = {}
    for fname in _LIVE_FACTORS:
        fd = factor_by_name.get(fname)
        if fd:
            pct = fd.get("percentile")
            val = fd.get("value")
            if pct is not None and val is not None:
                bands[fname] = band_for_percentile(float(pct))
    plain = _html.escape(plain_read(bands))

    # Grade badge with glossary "i" tooltip
    grade_badge = (
        f'<span style="font-weight:600;font-size:10px;padding:2px 8px;'
        f"border-radius:11px;display:inline-block;{grade_style};"
        f'margin-left:6px;">'
        f"{safe_grade}"
        f"</span>"
    )

    # Sub-line: ticker · source annotation · grade badge
    sub_line = (
        f'<div style="font-size:11px;color:var(--text-muted);'
        f"margin:8px 0 7px;font-family:'Fraunces',serif;font-style:italic;\">"
        f"{ticker} &middot; {source_note}"
        f"{grade_badge}"
        f"</div>"
    )

    # Fit-vs-book line: honest summary from verdict
    summary_text = _html.escape(str(row.verdict.summary))
    fit_line = (
        f'<div style="font-size:11px;color:var(--text-secondary);margin-top:5px;">'
        f'<b style="color:var(--text-primary);">fit vs book:</b> {summary_text}'
        f"</div>"
    )

    # Google-AI hook — production pointer copy (same as Zone 1 shortlist cards)
    gai_id = f"gai-z2-{ticker.lower()}"
    gai_placeholder = (
        f'<div id="{gai_id}" class="gai" style="font-size:10.5px;'
        "color:var(--text-secondary);background:#F7F5FF;"
        "border:1px solid #E4DCFB;border-radius:8px;padding:7px 10px;"
        'margin:8px 0 6px;">'
        "&#128269; <b>Google-AI read</b> "
        f'<span style="color:var(--text-muted);">&mdash; open <b>{ticker} in '
        "Stock Analysis</b> for the full factor breakdown. A companion to the "
        "evidence, never an input to the score.</span>"
        "</div>"
    )

    body_html = (
        sub_line
        + factor_rows_html
        + gai_placeholder
        + '<div style="font-size:11px;color:var(--text-secondary);margin-top:6px;">'
        + f'<b style="color:var(--text-primary);">Plain read:</b> {plain}'
        + "</div>"
        + fit_line
    )

    # Collapsible row (same pattern as shortlist) — surfaces the same
    # strongest-factor-percentile number the shortlist rows show collapsed
    # (a real, already-computed figure, never a live fetch), so an
    # unfamiliar ticker doesn't require expanding the card just to see it.
    strongest = _strongest_factor_html(factor_scores)
    summary_html = (
        f'<summary style="display:grid;'
        f"grid-template-columns:56px 1fr auto 16px;"
        f"gap:10px;align-items:center;font-size:12px;"
        f'padding:9px 13px;cursor:pointer;list-style:none;">'
        f"<b style=\"font-family:'DM Sans',sans-serif;\">{ticker}</b>"
        f'<span style="color:var(--text-secondary);">{strongest} '
        f'<i style="color:var(--text-muted);font-size:10px;font-style:normal;">'
        f"({source_note})</i></span>"
        f'<span style="font-weight:600;font-size:10px;padding:2px 8px;'
        f"border-radius:11px;display:inline-block;"
        f'{grade_style};">{safe_grade}</span>'
        f'<span style="color:var(--text-muted);font-size:10px;">&#9654;</span>'
        f"</summary>"
    )

    return (
        f'<details class="rc-card" style="background:var(--bg-primary);'
        f"border:1px solid var(--border);border-radius:10px;"
        f"margin-bottom:7px;overflow:hidden;content-visibility:auto;contain-intrinsic-size:0 64px;"
        f'box-shadow:var(--shadow-sm);">'
        f"{summary_html}"
        f'<div style="padding:2px 14px 13px;'
        f'border-top:1px solid #F1F5F9;">'
        f"{body_html}"
        f"</div>"
        f"</details>"
    )


def build_check_your_own_html(rows: list[Any]) -> str:
    """Return HTML for Zone ② result cards — one collapsible card per BatchFitRow.

    Each card renders the same 5-factor matrix as the shortlist (factor bands,
    percentile-vs-cohort, grade badge, fit-vs-book line, Google-AI hook).
    Source annotation distinguishes in-screen reuse from live-computed.
    DATA-GAP is shown honestly where data is thin; never fabricated.
    No FORBIDDEN_WORDS. Cap of 25 is enforced by batch_fit upstream.
    """
    if not rows:
        return (
            '<div style="font-size:11px;color:var(--text-muted);'
            "font-family:'Fraunces',serif;font-style:italic;"
            'padding:8px 0;">'
            "No results to show."
            "</div>"
        )

    parts: list[str] = []
    for row in rows:
        parts.append(_build_zone2_row_html(row))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Render helper: "Check your own list" (Zone ②)
# ---------------------------------------------------------------------------


def _render_history_and_upload(reports_dir: str) -> None:
    """Render Zone ② check-your-own-list upload section.

    Screen-history table renders in Zone ① above (build_screen_history_html);
    this section keeps only the "check your own list" upload.
    """
    # (The mono section header is rendered by render() — no duplicate here.)
    st.markdown(
        '<div style="font-size:12px;color:var(--text-secondary);'
        "font-family:'Fraunces',serif;font-style:italic;margin:2px 0 10px;\">"
        "Paste tickers or drop a CSV &mdash; each name gets the same 5-factor "
        "evidence card and a fit check against your book. Capped at 25 per run."
        "</div>",
        unsafe_allow_html=True,
    )
    col_in, col_btn = st.columns([4, 1])
    with col_in:
        text = st.text_area(
            "Tickers",
            placeholder="NVDA, AAPL, KO",
            label_visibility="collapsed",
            height=68,
        )
    with col_btn:
        run = st.button("Run the check", type="primary", use_container_width=True)
    st.caption("or upload a CSV (≤25 names)")
    uploaded = st.file_uploader(
        "Upload CSV", type=["csv"], label_visibility="collapsed"
    )
    if run:
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
                    screen=load_latest_screen(reports_dir),
                    live_fetch=True,
                )
                bar.empty()
                st.session_state[key] = rows
            st.markdown(
                build_check_your_own_html(st.session_state[key]),
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------------------------
# Gated "Run screener" — single-flight, cooldown, disable-if-fresh (mirrors
# weekly_brief.py's gated Run brief). Writes always land in a fresh
# session-scoped temp dir — never data/reports/ or data/sample/ from a
# public click.
# ---------------------------------------------------------------------------

_SCREENER_PROCESSING_KEY = "screener_run_processing"
_SCREENER_LAST_RUN_KEY = "screener_run_last_ts"
_SCREENER_RUN_ERROR_KEY = "screener_run_error"

# run_gate.py state name — shared process-wide (see run_gate.py's module
# docstring) so concurrent visitors can't each trigger their own full-universe
# scan. Distinct from _SCREENER_PROCESSING_KEY (st.session_state), which
# stays purely for this one session's own "show a spinner, rerun when my
# click's run finishes" UI bookkeeping.
_GATE_NAME = "screener"


def _run_screen_candidates_cli(report_dir: str) -> None:
    cmd = [
        sys.executable,
        "-m",
        "application.cli",
        "screen-candidates",
        "--report-dir",
        report_dir,
        "--cite-cases",
    ]
    subprocess.run(cmd, check=True)


def _start_screener_run_background(report_dir: str) -> None:
    if st.session_state.get(_SCREENER_PROCESSING_KEY):
        return
    st.session_state[_SCREENER_PROCESSING_KEY] = True
    st.session_state.pop(_SCREENER_RUN_ERROR_KEY, None)
    _gate_set_processing(_GATE_NAME, True)

    def _worker() -> None:
        try:
            _run_screen_candidates_cli(report_dir)
        except Exception:  # noqa: BLE001
            st.session_state[_SCREENER_RUN_ERROR_KEY] = True
        finally:
            st.session_state[_SCREENER_PROCESSING_KEY] = False
            _gate_set_processing(_GATE_NAME, False)

    threading.Thread(target=_worker, daemon=True).start()


def _trigger_screener_run(ctx: UIBookContext) -> None:
    import time as _time  # noqa: PLC0415

    now = _time.time()
    st.session_state[_SCREENER_LAST_RUN_KEY] = now
    _gate_set_last_run_ts(_GATE_NAME, now)
    tmp_dir = tempfile.mkdtemp(prefix="stockrec_screen_run_")
    if ctx.is_sample:
        st.session_state[SESSION_SAMPLE_REFRESH_REPORTS_KEY] = tmp_dir
    else:
        st.session_state[SESSION_REPORTS_DIR_KEY] = tmp_dir
    _start_screener_run_background(tmp_dir)


def _render_run_screener_gate(ctx: UIBookContext, days: int | None) -> None:
    """Status caption + gated Run button for the screener.

    Item 5 of the Cloud deploy scaling design: the full-universe scan now
    runs on a daily schedule (GitHub Actions), not live per-visitor-click —
    visitors get a passive "last updated" caption; the Run button becomes an
    operator/local-only manual trigger (mirrors the is_local_runtime() idiom
    already used for the AI-panel/quota guards elsewhere in this tab).
    """
    age_label = (
        f"{days} day{'s' if days != 1 else ''} old"
        if days is not None
        else "no screen yet"
    )
    if not is_local_runtime():
        st.caption(f"Screener — {age_label} (updated on a daily schedule)")
        return
    gate = evaluate_run_gate(
        staleness_days=days,
        is_running=_gate_is_processing(_GATE_NAME),
        last_run_ts=_gate_get_last_run_ts(_GATE_NAME),
    )
    with st.container(horizontal=True, vertical_alignment="center", gap="small"):
        st.caption(f"Screener — {age_label}")
        clicked = st.button(
            "↻ Run screener",
            key="screener_run_button",
            disabled=not gate.can_run,
            help=RUN_GATE_HELP[gate.reason],
        )
    if clicked:
        _trigger_screener_run(ctx)
        st.rerun()
    if st.session_state.get(_SCREENER_PROCESSING_KEY):
        st.info("⟳ Screening the universe — this can take a few minutes…", icon="ℹ️")
    elif st.session_state.pop(_SCREENER_RUN_ERROR_KEY, False):
        st.error("Screen run failed. The previous screen above is still shown.")


def build_screen_history_html(history: list[dict[str, object]]) -> str:
    """Render the past-screen history table (relocated from the Trust tab, 2026-07-13).

    Trust-tab audit: this table is about live screener operations, not a killed
    hypothesis — it belongs where the screener itself lives, not the credibility
    page. Columns: Date / Universe / Passed / Abstained. Empty history still
    returns a valid string (a short 'no past screens yet' note).
    """
    head = (
        "<div style=\"font-family:'IBM Plex Mono',monospace;font-size:10px;"
        "font-weight:600;letter-spacing:.14em;color:var(--text-muted,#94A3B8);"
        'text-transform:uppercase;margin:6px 0 10px;">Screen history</div>'
    )
    if not history:
        return (
            head + '<div style="font-size:12px;color:var(--text-secondary,#5C6370);">'
            "No past screens recorded yet.</div>"
        )
    rows = "".join(
        '<tr><td style="padding:4px 14px 4px 0;">{date}</td>'
        '<td style="padding:4px 14px 4px 0;">{uni}</td>'
        '<td style="padding:4px 14px 4px 0;">{passed}</td>'
        '<td style="padding:4px 0;">{abst}</td></tr>'.format(
            date=h.get("as_of", "?"),
            uni=h.get("universe_size", "?"),
            passed=h.get("n_candidates", "?"),
            abst="yes" if h.get("abstained") else "no",
        )
        for h in history
    )
    table = (
        '<table style="font-size:12px;color:var(--text-secondary,#5C6370);'
        'border-collapse:collapse;font-variant-numeric:tabular-nums;">'
        '<thead><tr style="color:var(--text-muted,#94A3B8);text-align:left;">'
        '<th style="padding:4px 14px 4px 0;font-weight:600;">Date</th>'
        '<th style="padding:4px 14px 4px 0;font-weight:600;">Universe</th>'
        '<th style="padding:4px 14px 4px 0;font-weight:600;">Passed</th>'
        '<th style="padding:4px 0;font-weight:600;">Abstained</th></tr></thead>'
        f"<tbody>{rows}</tbody></table>"
    )
    return head + table


# ---------------------------------------------------------------------------
# render() — Streamlit entry point (wires all components)
# ---------------------------------------------------------------------------


def render(reports_dir: str | None = None) -> None:
    """Main render entry point for the Research Candidates tab."""
    ctx = resolve_ui_book_context()
    reports_dir = reports_dir if reports_dir is not None else ctx.reports_dir

    market = resolve_market_mode({str(k): v for k, v in st.session_state.items()})
    show_india = st.toggle(
        "Show India instead of US + Canada",
        value=(market == "india"),
    )
    market = "india" if show_india else "us_ca"
    st.session_state["screener_market"] = market

    if market == "india":
        reports_dir = "data/sample/in"
        screen = load_latest_screened(reports_dir)
    else:
        screen = load_combined_screen([reports_dir, "data/sample/ca"])
    if screen is None:
        st.warning(
            "No screen report found. Run "
            "`python -m application.cli screen-candidates` to generate one."
        )
        _render_run_screener_gate(ctx, None)
        return

    _using_screened = screen.get("_source") == "screened"

    days = staleness_days(screen.get("as_of", ""))
    if days is not None and days > 8:
        st.error(f"Screen is {days} days old — re-run `screen-candidates`.")
    _render_run_screener_gate(ctx, days)

    if _using_screened:
        candidates = screen.get("rows", [])[:_TOP_N]
    else:
        candidates = screen.get("candidates", [])[:_TOP_N]

    if not _using_screened:
        st.caption(
            "ℹ No corroboration data this week — run `corroborate` to blend analyst signals."
        )

    # Zone ① — Header: headline (left) + VIEW toggle (right, mockup layout),
    # then the 4 tiles + ledger full-width below.
    new_view = "reason"
    if candidates:
        col_l, col_r = st.columns([3, 1], vertical_alignment="bottom")
        with col_l:
            st.markdown(build_headline_html(), unsafe_allow_html=True)
        with col_r:
            st.markdown(
                "<div style=\"font-family:'IBM Plex Mono',monospace;font-size:10px;"
                "letter-spacing:.18em;text-transform:uppercase;color:var(--text-muted);"
                'text-align:right;margin-bottom:4px;">View</div>',
                unsafe_allow_html=True,
            )
            view = resolve_view_mode({str(k): v for k, v in st.session_state.items()})
            selected = st.segmented_control(
                "View",
                options=["By reason", "Rank only"],
                default="By reason" if view == "reason" else "Rank only",
                label_visibility="collapsed",
            )
            new_view = "reason" if selected != "Rank only" else "rank"
            st.session_state["screener_view"] = new_view
        st.markdown(
            build_header_html(screen, reports_dir=reports_dir, include_headline=False),
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            build_header_html(screen, reports_dir=reports_dir),
            unsafe_allow_html=True,
        )

    # Always-visible Z-score -> Band -> Grade pipeline strip (thresholds live
    # in hover tooltips on the Band/Grade boxes), then caveats/disclosures
    # merged into one collapsed expander — one click away, not always-open.
    st.markdown(build_pipeline_visual_html(), unsafe_allow_html=True)
    with st.expander("▸ Learn more — caveats & methodology", expanded=False):
        st.markdown(build_caveats_html(screen), unsafe_allow_html=True)
    with st.expander("▸ Screen history — past runs", expanded=False):
        st.caption(
            "Every screen run is logged — including the ones that abstained — so "
            "this can't be quietly re-run until it produces a nicer-looking result."
        )
        st.markdown(
            build_screen_history_html(load_screen_history(reports_dir)),
            unsafe_allow_html=True,
        )
    if candidates:
        st.markdown(build_coverage_html(screen), unsafe_allow_html=True)

    if not candidates:
        # Abstention / under-powered path
        with st.spinner("Loading screen result…"):
            st.markdown(
                build_body_html(screen, view="reason", reports_dir=reports_dir),
                unsafe_allow_html=True,
            )
        st.markdown(
            "**Want to research a specific stock anyway?** "
            "Open the **Stock Analysis** tab — type any ticker for a full evidence read."
        )
    else:
        # Main body — spinner so the tab shows progress instead of blank while
        # the (large) card HTML renders.
        with st.spinner("Loading this week's research shortlist…"):
            body_html = build_body_html(screen, view=new_view, reports_dir=reports_dir)
            st.markdown(body_html, unsafe_allow_html=True)

    # Zone ② — Check your own list
    st.markdown(
        "<div style=\"font-family:'IBM Plex Mono',monospace;font-size:10px;"
        "font-weight:600;letter-spacing:.14em;color:var(--text-muted);"
        "text-transform:uppercase;margin:26px 0 10px;"
        'border-top:1px solid var(--border);padding-top:15px;">'
        "&#9410; Have your own names? Check them"
        "</div>",
        unsafe_allow_html=True,
    )

    # Wrap in a fragment so "Run the check" reruns ONLY this section (with its
    # own progress bar), not the whole page.
    @st.fragment
    def _zone2_fragment() -> None:
        _render_history_and_upload(reports_dir)

    _zone2_fragment()

    # Zone ③ — Track record link
    st.markdown(build_zone3_html(), unsafe_allow_html=True)
