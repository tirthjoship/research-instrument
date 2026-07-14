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


def render_evidence_chip(entry: EvidenceEntry, *, compact: bool = False) -> str:
    """Return an inline HTML chip for one :class:`EvidenceEntry`.

    The chip shows the metric label, a small colored badge carrying the verdict, and
    (when present) the ADR reference. Hovering reveals a tooltip with the meaning, the
    healthy-band context, and the caveat. All entry text is HTML-escaped.

    Args:
        entry: The evidence backing for a metric, looked up from the registry.
        compact: When ``True``, omits the always-visible verdict badge and ADR
            reference — only the plain label + hover affordance stay inline.
            The verdict word and ADR reference still appear inside the hover
            tooltip alongside the meaning/healthy-band/caveat, so nothing is
            lost, only relocated off the always-visible surface. Defaults to
            ``False`` (today's behavior — badge + ADR always visible).

    Returns:
        An HTML ``<span class="ri-chip">`` string ready to drop next to a number.
    """
    cls = _BADGE_CLASS[entry.verdict]

    safe_label = _html.escape(entry.label)
    safe_verdict = _html.escape(entry.verdict.value)
    safe_meaning = _html.escape(entry.meaning)
    safe_caveat = _html.escape(entry.caveat)

    band_html = ""
    if entry.healthy_band:
        safe_band = _html.escape(entry.healthy_band)
        band_html = f'<span class="ri-chip-band">{safe_band}</span>\n'

    if compact:
        badge_html = ""
        adr_html = ""
        adr_tip = f" · {_html.escape(entry.adr)}" if entry.adr else ""
        verdict_tip_html = (
            f'<span class="ri-chip-tip-verdict">{safe_verdict}{adr_tip}</span>\n'
        )
    else:
        badge_html = f'<span class="ri-vbadge {cls}">{safe_verdict}</span>'
        adr_html = (
            f'<span class="ri-chip-adr">{_html.escape(entry.adr)}</span>\n'
            if entry.adr
            else ""
        )
        verdict_tip_html = ""

    return (
        f'<span class="ri-chip" tabindex="0">'
        f'<span class="ri-chip-lab">{safe_label}</span>'
        f"{badge_html}"
        f"{adr_html}"
        f'<span class="ri-chip-tip">'
        f'<span class="ri-chip-meaning">{safe_meaning}</span>\n'
        f"{band_html}"
        f"{verdict_tip_html}"
        f'<span class="ri-chip-caveat">{safe_caveat}</span>'
        f"</span>"
        f"</span>"
    )


def render_evidence_chip_by_key(key: str, *, compact: bool = False) -> str:
    """Look up *key* in the evidence registry and render its chip.

    Returns an empty string when the key is unregistered, so callers can splice the
    result into markup unconditionally without guarding against ``None``.
    """
    entry = get_evidence(key)
    if entry is None:
        return ""
    return render_evidence_chip(entry, compact=compact)
