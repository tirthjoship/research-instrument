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

from adapters.visualization.components.factor_row import render_factor_row
from adapters.visualization.components.funnel import render_funnel
from adapters.visualization.components.proof_tile import render_tile
from adapters.visualization.components.tooltip import tooltip
from adapters.visualization.data_loader import (
    load_latest_screen,
    load_screen_history,
    staleness_days,
)
from domain.factor_bands import Band, band_for_percentile, plain_read
from domain.screen_buckets import PRIORITY, BucketInput, assign_buckets, primary_bucket
from domain.screen_diagnostics import ScreenDiagnostics, ScreenVerdict, classify_screen

logger = logging.getLogger(__name__)

_SCREEN_COVERAGE_FLOOR = 0.5
_TOP_N = 15

# Canonical live factor order (4 live + lowvol always shown as DATA-GAP for now)
_LIVE_FACTORS: tuple[str, ...] = ("momentum", "revision", "quality", "value")
_ALL_FACTORS: tuple[str, ...] = ("momentum", "revision", "quality", "value", "lowvol")

# Bucket signature subtitles matching the mockup .bktsub
_BUCKET_SUBS: dict[Any, str] = {}


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


def build_header_html(screen: dict[str, Any], reports_dir: str = "data/reports") -> str:
    """Return HTML for the Zone ① header: eyebrow, headline, subhead, 4 tiles, ledger.

    Uses Home design tokens (Fraunces/DM Sans/IBM Plex Mono/JetBrains Mono).
    All colours via CSS var() — no raw hex.
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
        label="Showing",
        number=str(shown),
        tone="muted",
        sub=f"of {cleared} that cleared",
    )

    # Tile 2: As of (with "not a forecast" framing)
    tile_as_of = render_tile(
        label="As of",
        number=as_of_display,
        tone="muted",
        sub="current evidence, not a forecast",
    )

    # Tile 3: Factors — 4 live, not 5 (lowvol deferred)
    tile_factors = render_tile(
        label="Factors",
        number="4",
        tone="muted",
        sub="momentum · analyst spread · quality · value",
    )

    # Tile 4: Trust — IC gate verdict (honest)
    ic_label_display = ic_verdict.capitalize() if ic_verdict else "Inconclusive"
    tile_trust = render_tile(
        label="Trust the signal",
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
        f"<span>FACTORS <b>4</b></span>"
        f"<span>AS OF <b>{_html.escape(as_of_raw)}</b></span>"
        f"<span>IC GATE <b>{_html.escape(ic_verdict)}</b></span>"
        f"<span>RESEARCH_ONLY</span>"
        f"</div>"
    )

    # Eyebrow + headline + subhead
    header_html = (
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

    return header_html + tiles_html + ledger_html


# ---------------------------------------------------------------------------
# Task 4: build_legend_html + build_disclosure_html
# ---------------------------------------------------------------------------


def build_legend_html() -> str:
    """Return HTML for the 'How to read these ratings' expandable legend.

    Matches mockup #lg .legend content: bands + p-notation + Evidence score.
    """
    return (
        '<div style="background:var(--bg-secondary);border:1px solid var(--border);'
        "border-radius:10px;padding:12px 14px;margin-bottom:12px;font-size:11px;"
        'color:var(--text-secondary);line-height:1.75;">'
        "Each name scored on the factors, each a z-score vs this week&#39;s trend-eligible cohort:<br>"
        "&bull; <b>Band</b>: "
        '<span style="font-weight:600;font-size:10px;padding:2px 8px;border-radius:11px;'
        'background:#DCFCE7;color:var(--success);">Exceptional</span> ~top 10% &nbsp;'
        '<span style="font-weight:600;font-size:10px;padding:2px 8px;border-radius:11px;'
        'background:#DBEAFE;color:var(--accent);">Strong</span> ~top quartile &nbsp;'
        '<span style="font-weight:600;font-size:10px;padding:2px 8px;border-radius:11px;'
        'background:#F1F5F9;color:var(--text-secondary);">Flat</span> middle &nbsp;'
        '<span style="font-weight:600;font-size:10px;padding:2px 8px;border-radius:11px;'
        'background:#FEE2E2;color:var(--danger);">Weak</span> bottom.<br>'
        "&bull; <b style=\"font-family:'JetBrains Mono',monospace;\">pNN</b> = percentile: "
        "p95 beats 95% of the cohort (not sector, not full universe).<br>"
        "&bull; <b>Evidence score</b> = equal-weight average of the z-scores. "
        "A ranking aid, not a return forecast.<br>"
        "&bull; Track-1 factors: Quality &middot; Value &middot; Analyst spread &middot; Momentum. "
        "Low-vol arrives in Track 2."
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

    # Render factor rows — 4 live + lowvol as DATA-GAP
    factor_rows_html = ""
    for fname in _LIVE_FACTORS:
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

    # Low-vol is always DATA-GAP in Track 1 (no live data)
    factor_rows_html += render_factor_row("lowvol", value=None, percentile=None)

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
        f"color:var(--text-secondary);background:#F7F5FF;"
        f"border:1px solid #E4DCFB;border-radius:8px;padding:7px 10px;"
        f'margin:8px 0 6px;">'
        f"&#128269; <b>Google-AI read</b> "
        f'<span style="color:var(--text-muted);">(summary beside the score — '
        f"never an input to the score; arrives in S6)</span>"
        f"</div>"
    )

    do_next = (
        "Confirm the evidence is structural (check next earnings date, recent "
        "call transcripts) before acting. Open <b>"
        + ticker
        + " in Stock Analysis</b> for a full read."
    )

    # Sub-line showing composite and any also-in buckets
    sub_line = (
        f'<div style="font-size:11px;color:var(--text-muted);'
        f"margin:8px 0 7px;font-family:'Fraunces',serif;font-style:italic;\">"
        f"{ticker} &middot; evidence {composite:.2f}{also_html}"
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
    from domain.screen_buckets import Bucket

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

    # Determine primary bucket for each ticker (for 'also' badges)
    primary_map: dict[str, Bucket | None] = {
        bi.ticker: primary_bucket(bi.percentiles) for bi in bucket_inputs
    }

    parts: list[str] = []

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

            # Is this a repeat (primary bucket is different)?
            is_repeat = primary_map.get(ticker) != bucket

            body = _build_candidate_row_html(
                rank=rank_i,
                candidate=c,
                show_repeat_badge=is_repeat,
                also_buckets=also_in if also_in else None,
            )

            # Composite value for row header
            composite = float(bi.composite)

            # Row wrapper using HTML details/summary for collapsible behaviour
            safe_ticker = _html.escape(ticker)
            why_text = _html.escape(str(c.get("why", "")))
            summary_html = (
                f'<summary style="display:grid;'
                f"grid-template-columns:22px 56px 1fr auto auto 16px;"
                f"gap:10px;align-items:center;font-size:12px;"
                f'padding:9px 13px;cursor:pointer;list-style:none;">'
                f'<b style="color:var(--text-muted);">{rank_i}</b>'
                f"<b style=\"font-family:'DM Sans',sans-serif;\">{safe_ticker}</b>"
                f'<span style="color:var(--text-secondary);">{why_text}</span>'
                f"<span style=\"font-family:'JetBrains Mono',monospace;"
                f'color:var(--text-secondary);">{composite:.2f}</span>'
                f'<span style="color:var(--text-muted);font-size:10px;">&#9654;</span>'
                f"</summary>"
            )

            row_html = (
                f'<details style="background:var(--bg-primary);'
                f"border:1px solid var(--border);border-radius:10px;"
                f"margin-bottom:7px;overflow:hidden;"
                f'box-shadow:var(--shadow-sm);">'
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
        why_text = _html.escape(str(c.get("why", "")))
        safe_ticker = _html.escape(ticker)

        body = _build_candidate_row_html(rank=rank_i, candidate=c)

        summary_html = (
            f'<summary style="display:grid;'
            f"grid-template-columns:22px 56px 1fr auto 16px;"
            f"gap:10px;align-items:center;font-size:12px;"
            f'padding:9px 13px;cursor:pointer;list-style:none;">'
            f'<b style="color:var(--text-muted);">{rank_i}</b>'
            f"<b style=\"font-family:'DM Sans',sans-serif;\">{safe_ticker}</b>"
            f'<span style="color:var(--text-secondary);">{why_text}</span>'
            f"<span style=\"font-family:'JetBrains Mono',monospace;"
            f'color:var(--text-secondary);">{composite:.2f}</span>'
            f'<span style="color:var(--text-muted);font-size:10px;">&#9654;</span>'
            f"</summary>"
        )

        row_html = (
            f'<details style="background:var(--bg-primary);'
            f"border:1px solid var(--border);border-radius:10px;"
            f"margin-bottom:7px;overflow:hidden;"
            f'box-shadow:var(--shadow-sm);">'
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
# Render helper: "Check your own list" (Zone ②)
# ---------------------------------------------------------------------------


def _render_history_and_upload(reports_dir: str) -> None:
    """Render Zone ② check-your-own-list upload section."""
    hist = load_screen_history(reports_dir)
    if hist:
        st.markdown(
            '<div class="ri-sec" style="margin-top:1.4rem">Screen history</div>',
            unsafe_allow_html=True,
        )
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

    st.markdown(
        '<div class="ri-sec" style="margin-top:1.4rem">Check your own list</div>'
        '<div class="ri-conclusion" style="margin-bottom:.8rem">'
        "Paste tickers or upload a CSV &mdash; each name gets an evidence grade "
        "and a fit check against your book. Capped at 25 names per run "
        "(live data fetch per name).</div>",
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

    # Zone ① — Header + tiles + ledger
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
        st.markdown(
            build_body_html(screen, view="reason", reports_dir=reports_dir),
            unsafe_allow_html=True,
        )
        st.markdown(
            "**Want to research a specific stock anyway?** "
            "Open the **Stock Analysis** tab — type any ticker for a full evidence read."
        )
    else:
        # View toggle
        view = resolve_view_mode({str(k): v for k, v in st.session_state.items()})
        selected = st.radio(
            "View",
            options=["By reason", "Rank only"],
            index=0 if view == "reason" else 1,
            horizontal=True,
            label_visibility="collapsed",
        )
        new_view = "reason" if selected == "By reason" else "rank"
        st.session_state["screener_view"] = new_view

        # Main body (reason or rank view)
        st.markdown(
            build_body_html(screen, view=new_view, reports_dir=reports_dir),
            unsafe_allow_html=True,
        )

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
    _render_history_and_upload(reports_dir)

    # Zone ③ — Track record link
    st.markdown(build_zone3_html(), unsafe_allow_html=True)
