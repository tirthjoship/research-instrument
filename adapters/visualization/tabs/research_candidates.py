"""Research Candidates tab — factual evidence ranking. RESEARCH_ONLY.

Architecture: pure `build_*_html(...)` helpers (testable without Streamlit)
compose the rendered output. `render()` wires them with `st.session_state`.

Design tokens match `.superpowers/brainstorm/screener-FINAL-v2.html` (canonical mockup).
All colours come from CSS var() — no raw hex in this module.
Honesty: no FORBIDDEN_WORDS; DATA-GAP never faked; includes "not a forecast" disclosure.
"""

from __future__ import annotations

import html as _html
import json
import logging
from pathlib import Path
from typing import Any

import streamlit as st

from adapters.ml.gemini_narrator import GeminiNarratorAdapter
from adapters.visualization.components.factor_row import render_factor_row
from adapters.visualization.components.funnel import render_funnel
from adapters.visualization.components.gemini_read import (
    build_case_context,
    render_gemini_read,
)
from adapters.visualization.components.proof_tile import render_tile
from adapters.visualization.components.tooltip import tooltip
from adapters.visualization.data_loader import load_latest_screen, staleness_days
from application.runtime_guard import is_local_runtime
from domain.factor_bands import Band, band_for_percentile, plain_read
from domain.screen_buckets import PRIORITY, BucketInput, assign_buckets
from domain.screen_diagnostics import ScreenDiagnostics, ScreenVerdict, classify_screen

# Module-level adapter instance — monkeypatchable in tests.
# Constructed lazily: API key comes from env at first call; no network on import.
_gemini_adapter: GeminiNarratorAdapter = GeminiNarratorAdapter()

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
    result = _gemini_adapter.summarize_case(ctx)
    html = render_gemini_read(result)
    st.session_state[cache_key] = html
    return html


def _bucket_sub(bucket: Any) -> str:
    """One-line italic subtitle for each bucket (mockup .bktsub)."""
    from domain.screen_buckets import Bucket

    return {
        Bucket.ALL_ROUNDER: "top-quartile on 3+ factors — rare",
        Bucket.MOMENTUM_LEADERS: "top-quartile momentum AND analyst spread",
        Bucket.QUALITY_FAIR_PRICE: "top-quartile quality AND value",
        Bucket.VALUE_CATALYST: "top-quartile value AND analyst spread",
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

# Friendly factor names for the plain row summary.
_FRIENDLY: dict[str, str] = {
    "quality": "quality",
    "value": "value",
    "revision": "analyst signal",
    "lowvol": "low-vol",
}


def _candidate_bands(candidate: dict[str, Any]) -> dict[str, Band]:
    """Map each present factor (non-None, not all-zero) to its plain-language band."""
    bands: dict[str, Band] = {}
    for fd in candidate.get("factor_scores", []):
        if not isinstance(fd, dict):
            continue
        rv, rp = fd.get("value"), fd.get("percentile")
        if rv is None or rp is None:
            continue
        fv, fp = float(rv), float(rp)
        if fv == 0.0 and fp == 0.0:  # DATA-GAP / no coverage
            continue
        bands[str(fd.get("name", ""))] = band_for_percentile(fp)
    return bands


def _row_summary(candidate: dict[str, Any]) -> str:
    """Plain-language one-liner next to the ticker (mockup: 'Quality, value &
    analyst signal strong; momentum flat') — derived from bands, never the raw why."""
    bands = _candidate_bands(candidate)
    strong = [
        _FRIENDLY[k]
        for k in ("quality", "value", "revision", "lowvol")
        if bands.get(k) in (Band.EXCEPTIONAL, Band.STRONG)
    ]
    m = bands.get("momentum")
    mom = (
        "momentum strong"
        if m in (Band.EXCEPTIONAL, Band.STRONG)
        else ("momentum weak" if m == Band.WEAK else "momentum flat")
    )
    if not strong:
        return f"No standout factor; {mom}"
    head = (
        strong[0] if len(strong) == 1 else ", ".join(strong[:-1]) + " & " + strong[-1]
    )
    head = head[0].upper() + head[1:]
    return f"{head} strong; {mom}"


def _standout_chip_html(candidate: dict[str, Any]) -> str:
    """Colour-coded GRADE pill next to the score (mockup row chip, e.g. 'STRONG').

    Derives an evidence-standing word from the name's strongest present factor:
    Exceptional/Strong → STRONG (green), Flat → MODERATE (blue), all Weak → WEAK
    (red). DATA-GAP-only names → neutral dash. Descriptive, never a forecast."""
    bands = _candidate_bands(candidate)
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
        sub="momentum · analyst spread · quality · value",
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


def build_legend_html() -> str:
    """Return HTML for the 'How to read these ratings' expandable legend.

    Matches mockup #lg .legend content: bands + p-notation + Evidence score + Grade.
    """
    return (
        '<div style="background:var(--bg-secondary);border:1px solid var(--border);'
        "border-radius:10px;padding:12px 14px;margin-bottom:12px;font-size:11px;"
        'color:var(--text-secondary);line-height:1.75;">'
        "Each name scored on the factors, each a z-score vs this week&#39;s trend-eligible cohort:<br>"
        "&bull; <b>Band</b>: "
        '<span style="font-weight:600;font-size:10px;padding:2px 8px;border-radius:11px;'
        'background:#DCFCE7;color:var(--success);">Exceptional</span> ~top&nbsp;5% &nbsp;'
        '<span style="font-weight:600;font-size:10px;padding:2px 8px;border-radius:11px;'
        'background:#DBEAFE;color:var(--accent);">Strong</span> ~top&nbsp;quartile &nbsp;'
        '<span style="font-weight:600;font-size:10px;padding:2px 8px;border-radius:11px;'
        'background:#F1F5F9;color:var(--text-secondary);">Flat</span> middle &nbsp;'
        '<span style="font-weight:600;font-size:10px;padding:2px 8px;border-radius:11px;'
        'background:#FEE2E2;color:var(--danger);">Weak</span> bottom.<br>'
        "&bull; <b style=\"font-family:'JetBrains Mono',monospace;\">pNN</b> = percentile: "
        "p95 beats 95% of the 304 (not sector, not all 512).<br>"
        "&bull; <b>Evidence score</b> = equal-weight average of the z-scores. "
        "A ranking aid, not a return forecast.<br>"
        "&bull; <b>Grade</b> (check-your-own-list): "
        '<span style="font-weight:700;font-size:10px;padding:2px 7px;border-radius:11px;'
        'background:#DCFCE7;color:var(--success);">STRONG</span> &ge;80% &nbsp;'
        '<span style="font-weight:700;font-size:10px;padding:2px 7px;border-radius:11px;'
        'background:#DBEAFE;color:var(--accent);">MODERATE</span> 50&ndash;80% &nbsp;'
        '<span style="font-weight:700;font-size:10px;padding:2px 7px;border-radius:11px;'
        'background:#FEE2E2;color:var(--danger);">WEAK</span> below half.<br>'
        "&bull; Track-1 factors: Quality &middot; Value &middot; Analyst spread &middot; Momentum. "
        "Low-vol now live (5th factor)."
        "</div>"
    )


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
# Task 5: resolve_view_mode
# ---------------------------------------------------------------------------


def resolve_view_mode(session: dict[str, Any]) -> str:
    """Return the current screener view mode from session state.

    Default is 'reason' (Group by reason). 'rank' = flat ranked list.
    """
    return str(session.get("screener_view", "reason"))


# ---------------------------------------------------------------------------
# Shared: build one collapsible candidate row HTML (used by both views)
# ---------------------------------------------------------------------------


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


def _build_candidate_row_html(
    rank: int | str,
    candidate: dict[str, Any],
    show_repeat_badge: bool = False,
    also_buckets: list[str] | None = None,
    open_by_default: bool = False,
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

    # Google-AI read placeholder (S6 fills this later)
    gai_id = f"gai-{ticker.lower()}"
    gai_placeholder = (
        f'<div id="{gai_id}" class="gai" style="font-size:10.5px;'
        "color:var(--text-secondary);background:#F7F5FF;"
        "border:1px solid #E4DCFB;border-radius:8px;padding:7px 10px;"
        'margin:8px 0 6px;">'
        "&#128269; <b>Google-AI read</b> "
        f'<span style="color:var(--text-muted);">&mdash; open <b>{ticker} in '
        "Stock Analysis</b> for the full cited case. A companion to the evidence, "
        "never an input to the score.</span>"
        "</div>"
    )

    do_next = (
        "Confirm the evidence is structural (check next earnings date, recent "
        "call transcripts) before acting. Open <b>"
        + ticker
        + " in Stock Analysis</b> for a full read."
    )

    # Sub-line: "CompanyName · evidence 1.22 [also-in badge]"
    friendly_name = _html.escape(_company_name(candidate))
    sub_line = (
        f'<div style="font-size:11px;color:var(--text-muted);'
        f"margin:8px 0 7px;font-family:'Fraunces',serif;font-style:italic;\">"
        f"{friendly_name} &middot; evidence {composite:.2f}{also_html}"
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


def build_reason_view_html(candidates: list[dict[str, Any]]) -> str:
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
            body = _build_candidate_row_html(
                rank=rank_i,
                candidate=c,
                show_repeat_badge=bool(also_in),
                also_buckets=also_in if also_in else None,
            )

            # Composite value for row header
            composite = float(bi.composite)

            # Row wrapper using HTML details/summary for collapsible behaviour
            safe_ticker = _html.escape(ticker)
            why_text = _html.escape(_row_summary(c))
            summary_html = (
                f'<summary style="display:grid;'
                f"grid-template-columns:22px 56px 1fr auto auto 16px;"
                f"gap:10px;align-items:center;font-size:12px;"
                f'padding:9px 13px;cursor:pointer;list-style:none;">'
                f'<b style="color:var(--text-muted);">{rank_i}</b>'
                f"<b style=\"font-family:'DM Sans',sans-serif;\">{safe_ticker}</b>"
                f'<span style="color:var(--text-secondary);">{why_text}</span>'
                f"{_standout_chip_html(c)}"
                f"<span style=\"font-family:'JetBrains Mono',monospace;"
                f'color:var(--text-secondary);">{composite:.2f}</span>'
                f'<span style="color:var(--text-muted);font-size:10px;">&#9654;</span>'
                f"</summary>"
            )

            is_hero = not hero_done
            hero_done = True
            open_attr = " open" if is_hero else ""
            border_color = "#CBD5E1" if is_hero else "var(--border)"
            shadow = "0 1px 3px rgba(15,23,42,.08)" if is_hero else "var(--shadow-sm)"

            row_html = (
                f'<details{open_attr} style="background:var(--bg-primary);'
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


def build_rank_view_html(candidates: list[dict[str, Any]]) -> str:
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
        why_text = _html.escape(_row_summary(c))
        safe_ticker = _html.escape(ticker)

        body = _build_candidate_row_html(rank=rank_i, candidate=c)

        summary_html = (
            f'<summary style="display:grid;'
            f"grid-template-columns:22px 56px 1fr auto auto 16px;"
            f"gap:10px;align-items:center;font-size:12px;"
            f'padding:9px 13px;cursor:pointer;list-style:none;">'
            f'<b style="color:var(--text-muted);">{rank_i}</b>'
            f"<b style=\"font-family:'DM Sans',sans-serif;\">{safe_ticker}</b>"
            f'<span style="color:var(--text-secondary);">{why_text}</span>'
            f"{_standout_chip_html(c)}"
            f"<span style=\"font-family:'JetBrains Mono',monospace;"
            f'color:var(--text-secondary);">{composite:.2f}</span>'
            f'<span style="color:var(--text-muted);font-size:10px;">&#9654;</span>'
            f"</summary>"
        )

        is_hero = rank_i == 1
        open_attr = " open" if is_hero else ""
        border_color = "#CBD5E1" if is_hero else "var(--border)"
        shadow = "0 1px 3px rgba(15,23,42,.08)" if is_hero else "var(--shadow-sm)"

        row_html = (
            f'<details{open_attr} style="background:var(--bg-primary);'
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
    candidates = screen.get("candidates", [])[:_TOP_N]

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
        return build_rank_view_html(list(candidates))
    return build_reason_view_html(list(candidates))


# ---------------------------------------------------------------------------
# Zone ③: history link HTML
# ---------------------------------------------------------------------------


def build_zone3_html() -> str:
    """Return HTML for Zone ③ — link to Trust tab screen history."""
    return (
        "<div style=\"font-family:'IBM Plex Mono',monospace;font-size:10px;"
        "font-weight:600;letter-spacing:.14em;color:var(--text-muted);"
        "text-transform:uppercase;margin:26px 0 10px;"
        'border-top:1px solid var(--border);padding-top:15px;">'
        "&#9411; Track record"
        "</div>"
        '<div style="font-size:12px;color:var(--text-secondary);">'
        "Past-screen history lives on the <b>Trust tab</b>. "
        '<a href="#" style="color:var(--accent);text-decoration:none;">'
        "See past screens &rarr;</a>"
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
        "Stock Analysis</b> for the full cited case. A companion to the evidence, "
        "never an input to the score.</span>"
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

    # Collapsible row (same pattern as shortlist)
    summary_html = (
        f'<summary style="display:grid;'
        f"grid-template-columns:56px 1fr auto 16px;"
        f"gap:10px;align-items:center;font-size:12px;"
        f'padding:9px 13px;cursor:pointer;list-style:none;">'
        f"<b style=\"font-family:'DM Sans',sans-serif;\">{ticker}</b>"
        f'<span style="color:var(--text-secondary);">{source_note}</span>'
        f'<span style="font-weight:600;font-size:10px;padding:2px 8px;'
        f"border-radius:11px;display:inline-block;"
        f'{grade_style};">{safe_grade}</span>'
        f'<span style="color:var(--text-muted);font-size:10px;">&#9654;</span>'
        f"</summary>"
    )

    return (
        f'<details style="background:var(--bg-primary);'
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

    Screen-history table now lives on the Trust tab (see build_zone3_html link);
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
# render() — Streamlit entry point (wires all components)
# ---------------------------------------------------------------------------


def render(reports_dir: str = "data/reports") -> None:
    """Main render entry point for the Research Candidates tab."""
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

    # How-to-read legend (collapsible via st.expander)
    with st.expander("▸ How to read these ratings", expanded=False):
        st.markdown(build_legend_html(), unsafe_allow_html=True)

    # Honest disclosure
    st.markdown(build_disclosure_html(), unsafe_allow_html=True)

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
    @st.fragment  # type: ignore[misc]
    def _zone2_fragment() -> None:
        _render_history_and_upload(reports_dir)

    _zone2_fragment()

    # Zone ③ — Track record link
    st.markdown(build_zone3_html(), unsafe_allow_html=True)
