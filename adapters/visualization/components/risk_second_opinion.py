"""Render the attributed Google-AI second-opinion panel for the Risk tab.

HONESTY + PRIVACY RAILS:
  - Returns "" (empty string) when is_local_runtime() is False — nothing reaches
    the HTML off-local.
  - Returns "" when result is None.
  - All rendered text is ATTRIBUTED · RESEARCH ONLY — never a verdict or trade call.
  - FORBIDDEN_WORDS are never emitted here.

CSS classes used are from Task 10 (styles.py): risk-ai, risk-aihd, risk-at,
risk-ab, risk-aibody, risk-aiq, risk-aipt, risk-n, risk-aifoot, risk-gdot
(.gb/.gr/.gy/.gg).
"""

from __future__ import annotations

import html as _html

from application.runtime_guard import is_local_runtime
from domain.case_models import CaseResult

# Module-level alias makes is_local_runtime monkeypatchable in tests without
# patching the whole runtime_guard module.
is_local_runtime = is_local_runtime  # noqa: PLW0127 — intentional re-bind


def render_risk_second_opinion(result: CaseResult | None) -> str:
    """Render the Google-AI second-opinion panel as HTML.

    Returns "" when:
      - is_local_runtime() is False (privacy fail-safe — nothing reaches HTML off-local)
      - result is None AND is_local_runtime() is False

    When LOCAL and result is None (cache empty), returns a small honest data-gap
    stub prompting the user to run weekly-brief with GEMINI_API_KEY.

    Args:
        result: CaseResult to render; pass None for empty/stub output.

    Returns:
        HTML string.  Empty string only when off-local (never reveals anything
        off-local regardless of result).
    """
    if not is_local_runtime():
        # Privacy fail-safe: off-local → never emit anything.
        return ""

    # LOCAL runtime below this point.

    if result is None:
        # Cache empty — show honest data-gap stub (local only).
        return (
            '<div class="ri-sec">'
            '<span class="ri-tg" style="color:var(--petrol)">Second opinion</span>'
            " · Google AI"
            "</div>"
            '<div class="risk-ai">'
            '<div class="risk-aifoot">'
            "Run <code>weekly-brief</code> with <code>GEMINI_API_KEY</code> set "
            "to populate the Google AI second opinion."
            "</div>"
            "</div>"
        )

    if result.data_gap:
        return (
            '<div class="ri-sec">'
            '<span class="ri-tg" style="color:var(--petrol)">Second opinion</span>'
            " · Google AI"
            "</div>"
            '<div class="risk-ai">'
            '<div class="risk-aifoot">'
            "&#128269; Google AI second opinion unavailable — data gap or service unreachable."
            "</div>"
            "</div>"
        )

    # Build numbered in_favor + to_watch point items
    def _norm(s: str) -> str:
        return s.strip().rstrip(":.").strip().lower()

    def _point_html(n: int, text: str, source_tag: str) -> str:
        # Only show the [source] tag when it adds information — i.e. it is not
        # an echo of the point text. The TemplateCaseSummarizer (offline / no
        # GEMINI key) echoes the metric into both text and source_tag, which
        # would otherwise render as a confusing "metric: [metric]" duplicate.
        nt, ns = _norm(text), _norm(source_tag)
        src = (
            f'<span style="font-size:9px;color:var(--risk-faint);margin-left:4px;">'
            f"[{_html.escape(source_tag)}]</span>"
            if ns and ns != nt and ns not in nt and nt not in ns
            else ""
        )
        return (
            f'<div class="risk-aipt">'
            f'<span class="risk-n">{n}</span>'
            f"<div>{_html.escape(text)}{src}</div>"
            f"</div>"
        )

    points: list[str] = []
    idx = 1
    for pt in result.in_favor:
        points.append(_point_html(idx, pt.text, pt.source_tag))
        idx += 1
    for pt in result.to_watch:
        points.append(_point_html(idx, pt.text, pt.source_tag))
        idx += 1

    points_html = (
        "".join(points)
        if points
        else (
            '<div class="risk-aipt">'
            '<span class="risk-n">&#8212;</span>'
            "<div>No additional blind spots identified.</div>"
            "</div>"
        )
    )

    # Re-run instruction: a non-interactive label explaining how to refresh the
    # cached result via the CLI. A live Gemini call at render time is out of scope
    # (cache-first, spec §9). Rendered as a styled span so it reads as an
    # instruction, not a broken disabled widget.
    rerun_btn = (
        '<span class="risk-aibtn">'
        "&#8635; Re-run: <code>weekly-brief --gemini</code>"
        "</span>"
    )

    return (
        # Section heading matching ri-sec style used by other Risk sections
        '<div class="ri-sec">'
        '<span class="ri-tg" style="color:var(--petrol)">Second opinion</span>'
        " · Google AI"
        "</div>"
        # Card
        '<div class="risk-ai">'
        # Header: Google dots + title + ATTRIBUTED badge
        '<div class="risk-aihd">'
        '<span class="risk-gdot">'
        '<i class="gb"></i><i class="gr"></i><i class="gy"></i><i class="gg"></i>'
        "</span>"
        '<span class="risk-at">What might this risk read be missing?</span>'
        '<span class="risk-ab">ATTRIBUTED · RESEARCH ONLY</span>'
        "</div>"
        # Body
        '<div class="risk-aibody">'
        '<div class="risk-aiq">'
        "Google AI was asked to find blind spots in the dials above — "
        "it does not set the verdict"
        "</div>" + points_html + rerun_btn + "</div>"
        # Footer / attribution
        '<div class="risk-aifoot">'
        "<b>This is a third-party second opinion, shown as Google AI's — "
        "not adopted as the dashboard's view.</b> "
        "It can be wrong, cites no trade, and never overrides the deterministic dials. "
        "Runs only on your machine; throttled &amp; cached. "
        "If Google AI is unreachable, this panel is simply hidden."
        "</div>"
        "</div>"
    )
