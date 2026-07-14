"""Tests for D13: reliability-weighted stance distribution + convergence chip.

D13's original vertical per-stance bars / single combined chip were superseded
by the mockup-aligned horizontal stance bar + two-chip (align/dissent) design
in ``corroboration_view.py`` (see tests/test_corroboration_view.py for
``_stance_segments`` / ``_chips_html`` coverage). This file now covers what
still lives in ``corroboration_section.py``: the sa-* claim-card migration and
the module-wide FORBIDDEN_WORDS scan.
"""

from __future__ import annotations

import inspect
from datetime import date
from types import SimpleNamespace

from adapters.visualization.tabs.stock_analysis import corroboration_section as cs
from domain.corroboration_models import Stance
from domain.fit import FORBIDDEN_WORDS

# ---------------------------------------------------------------------------
# FORBIDDEN_WORDS — scan the whole module source
# ---------------------------------------------------------------------------


def test_clean_of_slop() -> None:
    """The corroboration section module must not contain any FORBIDDEN_WORDS."""
    src = inspect.getsource(cs).lower()
    violations = [w for w in FORBIDDEN_WORDS if w in src]
    assert not violations, f"FORBIDDEN_WORDS found in module: {violations}"


# ---------------------------------------------------------------------------
# Task 4: sa-* design system migration
# ---------------------------------------------------------------------------


def _minimal_claim() -> SimpleNamespace:
    """Minimal HarvestedClaim stand-in for sa-* migration tests."""
    return SimpleNamespace(
        stance=Stance.BULLISH,
        reliability_weight=0.9,
        verified=True,
        source_name="10-K",
        thesis_summary="Strong fundamentals.",
        url="https://example.com",
        published_at=date(2026, 6, 27),
    )


def test_claim_card_uses_sa_claim_not_ws_card() -> None:
    """_claim_card_html must use .sa-claim, not the old ws-card container."""
    html = cs._claim_card_html(_minimal_claim())  # type: ignore[attr-defined]
    assert "sa-claim" in html, "Expected 'sa-claim' class in claim card HTML"
    assert (
        "ws-card" not in html
    ), "Old 'ws-card' class must not appear in claim card HTML"


def test_claim_card_content_intact_after_migration() -> None:
    """All data (source, thesis, verified badge, url) must survive the sa-* migration."""
    claim = _minimal_claim()
    html = cs._claim_card_html(claim)  # type: ignore[attr-defined]
    assert "10-K" in html, "source_name must be present"
    assert "Strong fundamentals." in html, "thesis_summary must be present"
    assert "VERIFIED" in html, "verified badge must be present for verified claim"
    assert "https://example.com" in html, "url must be present"
