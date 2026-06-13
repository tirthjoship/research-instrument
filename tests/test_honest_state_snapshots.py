"""Honest-state snapshot guards — regression tests for UI states that must
never silently regress to fabricated/promotional language.

These tests assert structural invariants and vocabulary cleanliness against
the *actual rendered HTML* (runtime output, not source inspection).  They
complement the source-inspection tests in test_funnel.py / test_proof_tile.py
/ test_ledger.py and the full-dossier render tests in test_dossier_render.py.

Guards added here:
  - Abstention funnel zero-state: counts present, amber class applied, no
    forbidden words in rendered output.
  - Falsified proof-tile: stamp and value rendered, no forbidden words.
  - Evidence ledger zero-state: both segments rendered, no forbidden words.
  - Proof-tile DATA_GAP state: dash rendered, no stamp element present.
  - Proof-tile no-stamp path: ri-stamp absent when stamp=None.
  - Evidence ledger multi-segment: tooltip-wrapped label still vocab-clean.
"""

from __future__ import annotations

from adapters.visualization.components import funnel, ledger, proof_tile
from domain.fit import FORBIDDEN_WORDS

# ---------------------------------------------------------------------------
# Abstention funnel — zero-state
# ---------------------------------------------------------------------------


def test_abstention_funnel_renders_zero_state_without_forbidden_words() -> None:
    """Universe count and zero cleared-count both appear; output is clean."""
    html = funnel.render_funnel([("Universe", 512), ("Evidence bar", 0)]).lower()
    assert "512" in html, "Universe count must be present"
    assert "0" in html, "Zero cleared-count must be present"
    for w in FORBIDDEN_WORDS:
        assert w not in html, f"Forbidden word '{w}' found in funnel zero-state output"


def test_abstention_funnel_zero_state_applies_amber_class() -> None:
    """When the final stage count is 0, the amber modifier class must be set."""
    html = funnel.render_funnel([("Universe", 512), ("Evidence bar", 0)])
    assert (
        "ri-funnel-step--amber" in html
    ), "Amber modifier class must be applied to the zero-count final stage"


def test_abstention_funnel_non_zero_final_stage_no_amber() -> None:
    """When cleared > 0 no amber warning class should appear."""
    html = funnel.render_funnel([("Universe", 512), ("Evidence bar", 7)])
    assert (
        "ri-funnel-step--amber" not in html
    ), "Amber class must NOT appear when final count is non-zero"


# ---------------------------------------------------------------------------
# Falsified proof-tile
# ---------------------------------------------------------------------------


def test_falsified_tile_renders_without_forbidden_words() -> None:
    """Value and FALSIFIED stamp are rendered; output is vocab-clean."""
    html = proof_tile.render_tile(
        "Rank-IC", "0.004", stamp="FALSIFIED", tone="crimson"
    ).lower()
    assert "0.004" in html, "Metric value must be present"
    assert "falsified" in html, "FALSIFIED stamp must be present"
    for w in FORBIDDEN_WORDS:
        assert w not in html, f"Forbidden word '{w}' found in falsified tile output"


def test_falsified_tile_stamp_element_present() -> None:
    """ri-stamp element appears when stamp is provided."""
    html = proof_tile.render_tile("Rank-IC", "0.004", stamp="FALSIFIED", tone="crimson")
    assert "ri-stamp" in html, "ri-stamp class must appear when stamp is set"


def test_falsified_tile_tone_class_applied() -> None:
    """The crimson tone class is present in the rendered div."""
    html = proof_tile.render_tile("Rank-IC", "0.004", stamp="FALSIFIED", tone="crimson")
    assert "t-crimson" in html, "Crimson tone class must be applied"


# ---------------------------------------------------------------------------
# Evidence ledger — zero/honest-state
# ---------------------------------------------------------------------------


def test_evidence_ledger_renders_without_forbidden_words() -> None:
    """Both segment values appear; output is vocab-clean."""
    html = ledger.render_ledger([("UNIVERSE", "512"), ("CLEARED", "0")]).lower()
    assert "512" in html, "UNIVERSE value must be present"
    assert "cleared" in html, "CLEARED label must be present"
    for w in FORBIDDEN_WORDS:
        assert w not in html, f"Forbidden word '{w}' found in ledger zero-state output"


def test_evidence_ledger_multi_segment_vocab_clean() -> None:
    """Ledger with a tooltip-wrapped label still produces vocab-clean output."""
    tooltip_label = '<span title="Week-of-year">WEEK</span>'
    html = ledger.render_ledger(
        [(tooltip_label, "2026-W24"), ("UNIVERSE", "512"), ("CLEARED", "0")]
    ).lower()
    assert "2026-w24" in html, "Week value must be present"
    assert "512" in html, "Universe count must be present"
    for w in FORBIDDEN_WORDS:
        assert (
            w not in html
        ), f"Forbidden word '{w}' found in multi-segment ledger output"


# ---------------------------------------------------------------------------
# Proof-tile DATA_GAP state
# ---------------------------------------------------------------------------


def test_proof_tile_data_gap_state() -> None:
    """DATA_GAP: em-dash renders as the number; no stamp element present."""
    html = proof_tile.render_tile("Rank-IC", "—", tone="muted")
    assert "—" in html, "Em-dash must be present in DATA_GAP tile"
    assert (
        "ri-stamp" not in html
    ), "ri-stamp must NOT appear when stamp=None (no fabricated outcome)"


def test_proof_tile_no_stamp_when_stamp_none() -> None:
    """Explicit stamp=None produces no stamp element in rendered HTML."""
    html = proof_tile.render_tile("Rank-IC", "0.004", stamp=None, tone="muted")
    assert "ri-stamp" not in html, "ri-stamp class must be absent when stamp=None"
