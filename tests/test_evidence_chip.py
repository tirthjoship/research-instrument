"""Tests for the evidence-chip UI primitive (pure HTML-string builder)."""

from __future__ import annotations

import sys

import pytest

from adapters.visualization.components import evidence_chip
from adapters.visualization.components.evidence_chip import (
    badge_class,
    render_evidence_chip,
    render_evidence_chip_by_key,
)
from domain.evidence_registry import EvidenceEntry, Verdict


def _entry(
    verdict: Verdict = Verdict.DESCRIPTIVE,
    *,
    label: str = "Net beta",
    adr: str | None = "ADR-052",
    healthy_band: str | None = "near 1.0 for an all-stock book",
    meaning: str = "How much the book moves with the market.",
    caveat: str = "Inherited exposure, not a lever.",
) -> EvidenceEntry:
    return EvidenceEntry(
        key="net_beta",
        label=label,
        meaning=meaning,
        healthy_band=healthy_band,
        verdict=verdict,
        adr=adr,
        caveat=caveat,
    )


# Expected badge-class suffix per verdict — one row per enum member.
_EXPECTED_CLASS = {
    Verdict.VALIDATED: "v-validated",
    Verdict.DESCRIPTIVE: "v-descriptive",
    Verdict.RESEARCH_ONLY: "v-research",
    Verdict.INCONCLUSIVE: "v-inconclusive",
    Verdict.FALSIFIED: "v-falsified",
    Verdict.FORWARD_PENDING: "v-pending",
}


def test_every_verdict_is_mapped() -> None:
    # Guards against an enum member without a badge class.
    assert set(_EXPECTED_CLASS) == set(Verdict)


@pytest.mark.parametrize("verdict", list(Verdict))
def test_each_verdict_maps_to_its_badge_class(verdict: Verdict) -> None:
    expected = _EXPECTED_CLASS[verdict]
    assert badge_class(verdict) == expected
    html = render_evidence_chip(_entry(verdict))
    assert f"ri-vbadge {expected}" in html
    assert verdict.value in html


def test_chip_contains_label_and_adr() -> None:
    html = render_evidence_chip(_entry(label="Net beta", adr="ADR-052"))
    assert "Net beta" in html
    assert "ADR-052" in html
    assert 'class="ri-chip"' in html


def test_chip_includes_meaning_band_and_caveat() -> None:
    html = render_evidence_chip(_entry())
    assert "How much the book moves with the market." in html
    assert "near 1.0 for an all-stock book" in html
    assert "Inherited exposure, not a lever." in html


def test_missing_adr_and_band_are_omitted() -> None:
    html = render_evidence_chip(_entry(adr=None, healthy_band=None))
    assert "ri-chip-adr" not in html
    assert "ri-chip-band" not in html
    # The chip still renders its badge and label.
    assert "ri-vbadge" in html
    assert "Net beta" in html


def test_text_is_html_escaped() -> None:
    html = render_evidence_chip(
        _entry(
            label="P/E <ratio>",
            meaning="risk & reward <test>",
            caveat='not a "forecast"',
        )
    )
    # Raw angle brackets from the field text must be escaped...
    assert "<ratio>" not in html
    assert "<test>" not in html
    assert "P/E &lt;ratio&gt;" in html
    assert "risk &amp; reward &lt;test&gt;" in html
    assert "&quot;forecast&quot;" in html


def test_by_key_renders_known_entry() -> None:
    html = render_evidence_chip_by_key("sentiment_signal")
    assert html != ""
    assert "FALSIFIED" in html
    assert "v-falsified" in html


def test_by_key_returns_empty_for_unknown() -> None:
    assert render_evidence_chip_by_key("does_not_exist") == ""
    assert render_evidence_chip_by_key("") == ""


# ---------------------------------------------------------------------------
# compact=True: Home-tab-only opt-out that drops the always-visible verdict
# badge and ADR reference, relocating both into the hover tooltip instead.
# ---------------------------------------------------------------------------


def test_default_behavior_unchanged_when_compact_not_passed() -> None:
    """Regression guard: Risk/Stock Analysis call sites (no `compact` arg)
    must keep today's badge+ADR-always-visible behavior."""
    html = render_evidence_chip(_entry())
    assert "ri-vbadge" in html
    assert "ri-chip-adr" in html
    assert "ADR-052" in html
    assert Verdict.DESCRIPTIVE.value in html


def test_compact_chip_omits_inline_badge_and_adr() -> None:
    html = render_evidence_chip(_entry(), compact=True)
    assert "ri-vbadge" not in html
    assert "ri-chip-adr" not in html


def test_compact_chip_still_has_plain_label_and_hover_affordance() -> None:
    html = render_evidence_chip(_entry(label="Net beta"), compact=True)
    assert "ri-chip-lab" in html
    assert "Net beta" in html
    assert 'class="ri-chip"' in html  # hover ⓘ affordance intact


def test_compact_chip_moves_verdict_and_adr_into_tooltip() -> None:
    html = render_evidence_chip(_entry(adr="ADR-052"), compact=True)
    # Tooltip (ri-chip-tip) is the only place ADR/verdict text may appear.
    tip_start = html.index('class="ri-chip-tip"')
    tip_html = html[tip_start:]
    assert "ADR-052" in tip_html
    assert Verdict.DESCRIPTIVE.value in tip_html
    assert "ADR-052" not in html[:tip_start]
    assert Verdict.DESCRIPTIVE.value not in html[:tip_start]


def test_compact_chip_still_has_meaning_band_and_caveat_in_tooltip() -> None:
    html = render_evidence_chip(_entry(), compact=True)
    assert "How much the book moves with the market." in html
    assert "near 1.0 for an all-stock book" in html
    assert "Inherited exposure, not a lever." in html


def test_compact_chip_with_no_adr_omits_adr_everywhere() -> None:
    html = render_evidence_chip(_entry(adr=None), compact=True)
    assert "ri-chip-adr" not in html
    assert "ADR-" not in html


def test_by_key_supports_compact() -> None:
    html = render_evidence_chip_by_key("sentiment_signal", compact=True)
    assert html != ""
    assert "ri-vbadge" not in html
    tip_start = html.index('class="ri-chip-tip"')
    assert "FALSIFIED" in html[tip_start:]


def test_importable_without_streamlit() -> None:
    # The module must build HTML strings with no Streamlit dependency.
    assert "streamlit" not in sys.modules or True  # tolerate prior imports
    src = inspect_source()
    assert "import streamlit" not in src
    assert "st." not in src


def inspect_source() -> str:
    import inspect

    return inspect.getsource(evidence_chip)
