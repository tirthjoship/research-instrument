"""Unit tests for corroboration_section.py pure HTML-builder functions.

Pure functions only — no Streamlit import needed.
"""

from __future__ import annotations

from adapters.visualization.tabs.stock_analysis.corroboration_section import (
    _claim_card_html,
    _claim_row_html,
    _directional_views_html,
    _empty_state_html,
    _group_claims_by_weight,
    _our_readout_html,
)
from domain.corroboration_models import DirectionalView, OurReadout, Stance, TrendHealth
from tests.fakes.corroboration_store_fake import (
    FAKE_CLAIM_BEARISH,
    FAKE_CLAIM_BULLISH,
    FAKE_CLAIM_WEAK,
)


def test_empty_state_html_contains_ticker() -> None:
    html = _empty_state_html("AAPL")
    assert "AAPL" in html
    assert "corroborate" in html


def test_empty_state_html_no_ticker() -> None:
    html = _empty_state_html("")
    assert "corroborate" in html


def test_group_claims_bullish_high_weight_goes_to_strong() -> None:
    strong, moderate, weak = _group_claims_by_weight((FAKE_CLAIM_BULLISH,))
    assert FAKE_CLAIM_BULLISH in strong
    assert not moderate
    assert not weak


def test_group_claims_unverified_low_weight_goes_to_weak() -> None:
    strong, moderate, weak = _group_claims_by_weight((FAKE_CLAIM_WEAK,))
    assert not strong
    assert not moderate
    assert FAKE_CLAIM_WEAK in weak


def test_group_claims_verified_mid_weight_goes_to_moderate() -> None:
    strong, moderate, weak = _group_claims_by_weight((FAKE_CLAIM_BEARISH,))
    # FAKE_CLAIM_BEARISH: verified=True, weight=0.65 → moderate bucket
    assert not strong
    assert FAKE_CLAIM_BEARISH in moderate
    assert not weak


def test_group_claims_mixed() -> None:
    strong, moderate, weak = _group_claims_by_weight(
        (FAKE_CLAIM_BULLISH, FAKE_CLAIM_BEARISH, FAKE_CLAIM_WEAK)
    )
    assert len(strong) == 1
    assert len(moderate) == 1
    assert len(weak) == 1


def test_claim_card_html_contains_source_and_thesis() -> None:
    html = _claim_card_html(FAKE_CLAIM_BULLISH)
    assert "Goldman Sachs" in html
    assert "Strong iPhone cycle" in html
    assert "VERIFIED" in html
    assert "https://example.com/gs-aapl-2026" in html


def test_claim_card_html_unverified_has_no_verified_badge() -> None:
    html = _claim_card_html(FAKE_CLAIM_WEAK)
    assert "VERIFIED" not in html


def test_claim_row_html_contains_source() -> None:
    html = _claim_row_html(FAKE_CLAIM_BEARISH)
    assert "Barclays" in html
    assert "China headwinds" in html


def test_our_readout_html_all_fields() -> None:
    readout = OurReadout(
        factor_percentile=73.0,
        trend_health=TrendHealth.HEALTHY,
        divergence_flag=False,
        discipline_flag="HOLD",
    )
    html = _our_readout_html(readout)
    assert "73" in html
    assert "HEALTHY" in html
    assert "HOLD" in html


def test_our_readout_html_none_fields() -> None:
    readout = OurReadout(
        factor_percentile=None,
        trend_health=None,
        divergence_flag=False,
        discipline_flag=None,
    )
    html = _our_readout_html(readout)
    assert "N/A" in html


def test_directional_views_html_lean_in() -> None:
    view = DirectionalView(
        group_kind="sources",
        group_name="Evidence consensus",
        net_stance=Stance.BULLISH,
        mean_convergence=0.80,
        your_exposure_pct=0.0,
        evidence_weight_pct=0.80,
        tilt="LEAN_IN",
    )
    html = _directional_views_html([view])
    assert "LEAN_IN" in html
    assert "Evidence consensus" in html
    assert "#16A34A" in html  # green for LEAN_IN


def test_directional_views_html_empty_returns_empty_string() -> None:
    assert _directional_views_html([]) == ""
