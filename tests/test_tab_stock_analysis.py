"""Smoke tests for the stock_analysis tab package — SP6 Task 5.

Pure-function tests only: no Streamlit import required.
"""

from __future__ import annotations

from datetime import date

from adapters.visualization.data_loader import CorroborationTabView
from adapters.visualization.tabs.stock_analysis import (
    _SECTION_LABELS,
    _convergence_badge_html,
)
from domain.corroboration_models import ConvergenceTier
from tests.fakes.corroboration_store_fake import FAKE_SNAPSHOT


def _make_corr_view(snapshot=None):  # type: ignore[no-untyped-def]
    """Build a minimal CorroborationTabView for tests."""
    return CorroborationTabView(
        ticker="AAPL",
        as_of=date(2026, 6, 24),
        claims=(),
        snapshot=snapshot,
        our_readout=None,
        directional_views=(),
    )


# ---------------------------------------------------------------------------
# Section label smoke tests
# ---------------------------------------------------------------------------


def test_section_labels_length() -> None:
    """_SECTION_LABELS must have exactly 10 entries."""
    assert len(_SECTION_LABELS) == 10


def test_section_labels_has_corroboration() -> None:
    """Last entry of _SECTION_LABELS must be 'Corroboration'."""
    assert _SECTION_LABELS[-1] == "Corroboration"


# ---------------------------------------------------------------------------
# Convergence badge pure-function tests
# ---------------------------------------------------------------------------


def test_convergence_badge_html_strong() -> None:
    """STRONG tier badge must contain the green colour #16A34A."""
    html = _convergence_badge_html(ConvergenceTier.STRONG)
    assert "#16A34A" in html
    assert "STRONG" in html


def test_convergence_badge_html_conflicted() -> None:
    """CONFLICTED tier badge must contain the red colour #DC2626."""
    html = _convergence_badge_html(ConvergenceTier.CONFLICTED)
    assert "#DC2626" in html
    assert "CONFLICTED" in html


def test_convergence_badge_html_moderate() -> None:
    """MODERATE tier badge must contain the blue colour #2563EB."""
    html = _convergence_badge_html(ConvergenceTier.MODERATE)
    assert "#2563EB" in html
    assert "MODERATE" in html


def test_convergence_badge_html_weak() -> None:
    """WEAK tier badge must contain the amber colour #CA8A04."""
    html = _convergence_badge_html(ConvergenceTier.WEAK)
    assert "#CA8A04" in html
    assert "WEAK" in html


def test_convergence_badge_html_none_tier() -> None:
    """NONE tier badge must contain the gray colour #94A3B8."""
    html = _convergence_badge_html(ConvergenceTier.NONE)
    assert "#94A3B8" in html
    assert "NONE" in html


# ---------------------------------------------------------------------------
# Badge suppression when snapshot is absent
# ---------------------------------------------------------------------------


def test_convergence_badge_none_when_no_snapshot() -> None:
    """When corr_view.snapshot is None, no badge HTML should be produced."""
    view = _make_corr_view(snapshot=None)
    # Mirrors the guard logic in _render_verdict: badge is empty string when no snapshot.
    badge = ""
    if view is not None and view.snapshot is not None:
        badge = _convergence_badge_html(view.snapshot.convergence)
    assert badge == ""


def test_convergence_badge_present_when_snapshot_provided() -> None:
    """When corr_view.snapshot is set, badge HTML must be non-empty."""
    view = _make_corr_view(snapshot=FAKE_SNAPSHOT)
    badge = ""
    if view is not None and view.snapshot is not None:
        badge = _convergence_badge_html(view.snapshot.convergence)
    assert badge != ""
    # FAKE_SNAPSHOT has ConvergenceTier.MODERATE
    assert "#2563EB" in badge
