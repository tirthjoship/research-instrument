"""Evidence-chip component — inline research backing rendered next to any metric.

A chip pins a number to its :class:`~domain.evidence_registry.EvidenceEntry`: a small
colored verdict badge (how much trust the metric has earned), the ADR reference that
validated or killed related work, and an on-hover tooltip carrying the plain-English
meaning, healthy-band context, and the honest caveat. The goal is simple — a number is
never shown without its backing.

No Streamlit or third-party imports are needed; the module is a pure HTML-string builder
so it can be unit-tested without a browser environment. The verdict-to-badge color rules
live in ``styles.py`` (classes ``ri-chip`` / ``ri-vbadge`` / ``v-*``).
"""

from __future__ import annotations

import html as _html

from domain.evidence_registry import EvidenceEntry, Verdict, get_evidence

# Verdict → badge CSS-class suffix. The matching ``.ri-vbadge.v-*`` color rules live in
# styles.py. Keep these in sync with the Verdict enum (one class per member).
_BADGE_CLASS: dict[Verdict, str] = {
    Verdict.VALIDATED: "v-validated",  # green — cleared a pre-registered gate
    Verdict.DESCRIPTIVE: "v-descriptive",  # slate — a fact about today
    Verdict.RESEARCH_ONLY: "v-research",  # amber — surfaced for research only
    Verdict.INCONCLUSIVE: "v-inconclusive",  # grey — tested, CI spanned 0
    Verdict.FALSIFIED: "v-falsified",  # red — tested and killed
    Verdict.FORWARD_PENDING: "v-pending",  # blue — live gate, verdict not yet in
}


def badge_class(verdict: Verdict) -> str:
    """Return the CSS-class suffix for a verdict's badge (e.g. ``"v-falsified"``)."""
    return _BADGE_CLASS[verdict]


def render_evidence_chip(entry: EvidenceEntry) -> str:
    """Return an inline HTML chip for one :class:`EvidenceEntry`.

    The chip shows the metric label, a small colored badge carrying the verdict, and
    (when present) the ADR reference. Hovering reveals a tooltip with the meaning, the
    healthy-band context, and the caveat. All entry text is HTML-escaped.

    Args:
        entry: The evidence backing for a metric, looked up from the registry.

    Returns:
        An HTML ``<span class="ri-chip">`` string ready to drop next to a number.
    """
    cls = _BADGE_CLASS[entry.verdict]

    safe_label = _html.escape(entry.label)
    safe_verdict = _html.escape(entry.verdict.value)
    safe_meaning = _html.escape(entry.meaning)
    safe_caveat = _html.escape(entry.caveat)

    adr_html = ""
    if entry.adr:
        safe_adr = _html.escape(entry.adr)
        adr_html = f'<span class="ri-chip-adr">{safe_adr}</span>\n'

    band_html = ""
    if entry.healthy_band:
        safe_band = _html.escape(entry.healthy_band)
        band_html = f'<span class="ri-chip-band">{safe_band}</span>\n'

    return (
        f'<span class="ri-chip" tabindex="0">'
        f'<span class="ri-chip-lab">{safe_label}</span>'
        f'<span class="ri-vbadge {cls}">{safe_verdict}</span>'
        f"{adr_html}"
        f'<span class="ri-chip-tip">'
        f'<span class="ri-chip-meaning">{safe_meaning}</span>\n'
        f"{band_html}"
        f'<span class="ri-chip-caveat">{safe_caveat}</span>'
        f"</span>"
        f"</span>"
    )


def render_evidence_chip_by_key(key: str) -> str:
    """Look up *key* in the evidence registry and render its chip.

    Returns an empty string when the key is unregistered, so callers can splice the
    result into markup unconditionally without guarding against ``None``.
    """
    entry = get_evidence(key)
    if entry is None:
        return ""
    return render_evidence_chip(entry)
