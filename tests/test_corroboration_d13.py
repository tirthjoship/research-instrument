"""Tests for D13: reliability-weighted stance distribution + convergence chip.

Stance is a real Enum (Stance.BULLISH / Stance.BEARISH / Stance.NEUTRAL).
SimpleNamespace is used so we don't need a real HarvestedClaim (which requires
published_at: date and a ticker field irrelevant to these builders).
"""

from __future__ import annotations

import inspect
from types import SimpleNamespace

from adapters.visualization.tabs.stock_analysis import corroboration_section as cs
from domain.corroboration_models import ConvergenceTier, Stance
from domain.fit import FORBIDDEN_WORDS

# ---------------------------------------------------------------------------
# Fixtures helpers
# ---------------------------------------------------------------------------


def _claim(stance: Stance, w: float, verified: bool = True) -> SimpleNamespace:
    """Minimal stand-in for HarvestedClaim with only the fields our builders touch."""
    return SimpleNamespace(
        stance=stance,
        reliability_weight=w,
        verified=verified,
        source_name="10-K",
        thesis_summary="x",
        url="",
    )


# ---------------------------------------------------------------------------
# _weighted_stance_html
# ---------------------------------------------------------------------------


def test_weighted_distribution_is_not_headcount() -> None:
    """One strong constructive claim (0.9) must outweigh two weak cautious claims (0.2 each).

    A raw headcount would show 1 vs 2 and render cautious as larger.
    Weighted: constructive 0.9 / 1.3 ≈ 69 %, cautious 0.4 / 1.3 ≈ 31 %.
    The HTML must contain a "%" (percentage) AND the word "weight".
    """
    claims = [
        _claim(Stance.BULLISH, 0.9),
        _claim(Stance.BEARISH, 0.2),
        _claim(Stance.BEARISH, 0.2),
    ]
    html = cs._weighted_stance_html(claims)
    assert "%" in html, "Expected weighted percentages in output"
    assert "weight" in html.lower(), "Expected the word 'weight' in output"


def test_weighted_distribution_empty_datagap() -> None:
    """Empty claim list must produce a data-gap message."""
    html = cs._weighted_stance_html([])
    assert (
        "gap" in html.lower() or "—" in html
    ), "Expected 'gap' or em-dash in empty-state output"


def test_weighted_distribution_single_bullish() -> None:
    """Single constructive claim should show 100% constructive, 0% everything else."""
    claims = [_claim(Stance.BULLISH, 0.8)]
    html = cs._weighted_stance_html(claims)
    assert "100" in html
    assert "weight" in html.lower()


def test_weighted_distribution_neutral_included() -> None:
    """Neutral stance should appear in output when present."""
    claims = [
        _claim(Stance.BULLISH, 0.5),
        _claim(Stance.NEUTRAL, 0.5),
    ]
    html = cs._weighted_stance_html(claims)
    assert "%" in html
    assert "50" in html  # each is 50 %


# ---------------------------------------------------------------------------
# _convergence_chip_html
# ---------------------------------------------------------------------------


def test_convergence_chip_counts_dissent() -> None:
    """2 constructive + 1 cautious → chip shows total=3 and 1 dissent."""
    claims = [
        _claim(Stance.BULLISH, 0.9),
        _claim(Stance.BULLISH, 0.5),
        _claim(Stance.BEARISH, 0.3),
    ]
    html = cs._convergence_chip_html(claims, net_stance=Stance.BULLISH)
    assert "3" in html, "Expected total claim count in chip"
    assert "dissent" in html.lower(), "Expected 'dissent' in chip"


def test_convergence_chip_empty_returns_empty() -> None:
    """No claims → empty chip (nothing to render)."""
    html = cs._convergence_chip_html([], net_stance=Stance.BULLISH)
    assert html == ""


def test_convergence_chip_zero_dissent() -> None:
    """All claims agree → 0 dissent shown."""
    claims = [
        _claim(Stance.BEARISH, 0.7),
        _claim(Stance.BEARISH, 0.4),
    ]
    html = cs._convergence_chip_html(claims, net_stance=Stance.BEARISH)
    assert "2" in html
    assert "dissent" in html.lower()
    assert "0" in html  # 0 dissenters


def test_convergence_chip_with_explicit_tier() -> None:
    """When a ConvergenceTier is passed the tier label appears in the chip."""
    claims = [
        _claim(Stance.BULLISH, 0.8),
        _claim(Stance.NEUTRAL, 0.2),
    ]
    html = cs._convergence_chip_html(
        claims, net_stance=Stance.BULLISH, convergence_tier=ConvergenceTier.MODERATE
    )
    assert "MODERATE" in html.upper()
    assert "dissent" in html.lower()


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
    from datetime import date

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
