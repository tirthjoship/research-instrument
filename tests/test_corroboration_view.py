"""Tests for corroboration_view.build_corroboration_view — pure, no Streamlit."""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from datetime import date

from adapters.visualization.tabs.stock_analysis import corroboration_view as cv
from domain.corroboration_models import (
    CandidateSnapshot,
    ConvergenceTier,
    DirectionalView,
    HarvestedClaim,
    OurReadout,
    Stance,
    TrendHealth,
)
from domain.fit import FORBIDDEN_WORDS


def _claim(
    stance: Stance,
    weight: float,
    source: str = "Source",
    verified: bool = True,
    thesis: str = "x",
) -> HarvestedClaim:
    return HarvestedClaim(
        source_name=source,
        ticker="NVDA",
        stance=stance,
        thesis_summary=thesis,
        url="https://example.com",
        published_at=date(2026, 7, 1),
        verified=verified,
        reliability_weight=weight,
    )


@dataclass(frozen=True)
class _FakeCorrView:
    """Minimal stand-in for CorroborationTabView (avoids the data_loader import)."""

    ticker: str
    claims: tuple[HarvestedClaim, ...]
    snapshot: CandidateSnapshot | None = None
    directional_views: tuple[DirectionalView, ...] = field(default_factory=tuple)
    our_readout: OurReadout | None = None
    as_of: date = date(2026, 7, 8)


def _mockup_claims() -> tuple[HarvestedClaim, ...]:
    """6 claims matching the mockup shape: 4 bullish, 1 neutral, 1 bearish dissent."""
    return (
        _claim(
            Stance.BULLISH, 0.85, "Reuters", thesis="Backlog extends into next year."
        ),
        _claim(Stance.BULLISH, 0.65, "Analyst note", thesis="Margin expansion likely."),
        _claim(
            Stance.BULLISH,
            0.55,
            "Trade press",
            verified=False,
            thesis="Supplier ramping.",
        ),
        _claim(
            Stance.BULLISH, 0.30, "Blog", verified=False, thesis="Bullish momentum."
        ),
        _claim(
            Stance.NEUTRAL,
            0.90,
            "Company 10-K",
            thesis="Customer concentration disclosed.",
        ),
        _claim(Stance.BEARISH, 0.60, "Analyst B", thesis="Valuation is stretched."),
    )


def _view_with_snapshot(tier: ConvergenceTier) -> _FakeCorrView:
    claims = _mockup_claims()
    return _FakeCorrView(
        ticker="NVDA",
        claims=claims,
        snapshot=CandidateSnapshot(
            ticker="NVDA",
            convergence=tier,
            verification="PARTIAL",
            mean_convergence=0.6,
        ),
        directional_views=(
            DirectionalView(
                group_kind="sector",
                group_name="Evidence consensus",
                net_stance=Stance.BULLISH,
                mean_convergence=0.65,
                your_exposure_pct=0.0,
                evidence_weight_pct=0.65,
                tilt="HOLD",
            ),
        ),
    )


# ---------------------------------------------------------------------------
# Headline / reline
# ---------------------------------------------------------------------------


def test_moderate_with_dissent_headline_and_dissent_callout() -> None:
    view = cv.build_corroboration_view(_view_with_snapshot(ConvergenceTier.MODERATE))
    assert view["empty"] is False
    assert "honest dissent" in view["headline"]
    assert view["n_align"] == 4
    assert view["n_neutral"] == 1
    assert view["n_dissent"] == 1
    assert view["show_dissent_callout"] is True
    assert view["dissent_claim"] is not None
    assert view["dissent_claim"].source_name == "Analyst B"


def test_strong_tier_headline() -> None:
    claims = (
        _claim(Stance.BULLISH, 0.9, "A"),
        _claim(Stance.BULLISH, 0.8, "B"),
        _claim(Stance.BULLISH, 0.7, "C"),
    )
    v = _FakeCorrView(
        ticker="AAPL",
        claims=claims,
        snapshot=CandidateSnapshot(
            ticker="AAPL",
            convergence=ConvergenceTier.STRONG,
            verification="ALL_VERIFIED",
            mean_convergence=1.0,
        ),
        directional_views=(
            DirectionalView(
                group_kind="sector",
                group_name="x",
                net_stance=Stance.BULLISH,
                mean_convergence=1.0,
                your_exposure_pct=0.0,
                evidence_weight_pct=1.0,
                tilt="LEAN_IN",
            ),
        ),
    )
    view = cv.build_corroboration_view(v)
    assert view["headline"] == "Outside evidence aligns"
    assert view["n_dissent"] == 0
    assert view["show_dissent_callout"] is False


def test_conflicted_tier_flags_conflicted() -> None:
    claims = (_claim(Stance.BULLISH, 0.5, "A"), _claim(Stance.BEARISH, 0.5, "B"))
    v = _FakeCorrView(
        ticker="F",
        claims=claims,
        snapshot=CandidateSnapshot(
            ticker="F",
            convergence=ConvergenceTier.CONFLICTED,
            verification="PARTIAL",
            mean_convergence=0.1,
        ),
        directional_views=(
            DirectionalView(
                group_kind="sector",
                group_name="x",
                net_stance=Stance.NEUTRAL,
                mean_convergence=0.1,
                your_exposure_pct=0.0,
                evidence_weight_pct=0.1,
                tilt="HOLD",
            ),
        ),
    )
    view = cv.build_corroboration_view(v)
    assert view["conflicted"] is True
    assert "disagree" in view["headline"].lower()


def test_empty_claims_returns_educational_view() -> None:
    view = cv.build_corroboration_view(_FakeCorrView(ticker="NVDA", claims=()))
    assert view["empty"] is True
    assert view["ticker"] == "NVDA"
    assert "DATA GAP" in view["chips_html"]
    assert "cross-checks our panels" in view["headline"]
    assert "ADR-062" in view["reline"]
    assert view["claims_strong"] == []
    assert view["show_dissent_callout"] is False


def test_empty_corroboration_html_shows_readout_and_education() -> None:
    from adapters.visualization.tabs.stock_analysis.corroboration_section import (
        build_corroboration_html,
    )
    from adapters.visualization.tabs.stock_analysis.corroboration_view import (
        build_corroboration_view,
    )
    from domain.corroboration_models import OurReadout, TrendHealth

    view = build_corroboration_view(
        None,
        our_readout=OurReadout(
            factor_percentile=82.0,
            trend_health=TrendHealth.HEALTHY,
            divergence_flag=False,
            discipline_flag="clear",
        ),
    )
    html = build_corroboration_html(view)
    assert "Corroboration" in html
    assert "DATA GAP" in html
    assert "Our readout" in html
    assert "82" in html
    assert "corroborate" in html
    assert "Why this section exists" in html


def test_none_input_returns_empty_view_with_blank_ticker() -> None:
    view = cv.build_corroboration_view(None)
    assert view["empty"] is True
    assert view["ticker"] == ""
    assert "cross-checks our panels" in view["headline"]


# ---------------------------------------------------------------------------
# Chips
# ---------------------------------------------------------------------------


def test_chips_html_shows_tier_align_and_dissent() -> None:
    view = cv.build_corroboration_view(_view_with_snapshot(ConvergenceTier.MODERATE))
    html = view["chips_html"]
    assert "MODERATE" in html
    assert "4 of 6 align" in html
    assert "dissent" in html.lower()
    assert "1" in html


def test_chips_html_hides_dissent_chip_when_zero() -> None:
    claims = (_claim(Stance.BULLISH, 0.9, "A"), _claim(Stance.BULLISH, 0.8, "B"))
    v = _FakeCorrView(
        ticker="X",
        claims=claims,
        snapshot=CandidateSnapshot(
            ticker="X",
            convergence=ConvergenceTier.STRONG,
            verification="ALL_VERIFIED",
            mean_convergence=1.0,
        ),
        directional_views=(
            DirectionalView(
                group_kind="sector",
                group_name="x",
                net_stance=Stance.BULLISH,
                mean_convergence=1.0,
                your_exposure_pct=0.0,
                evidence_weight_pct=1.0,
                tilt="LEAN_IN",
            ),
        ),
    )
    view = cv.build_corroboration_view(v)
    assert "dissent" not in view["chips_html"].lower()


# ---------------------------------------------------------------------------
# Stance bar (weighted, headcount labels)
# ---------------------------------------------------------------------------


def test_stance_segments_weighted_not_headcount() -> None:
    view = cv.build_corroboration_view(_view_with_snapshot(ConvergenceTier.MODERATE))
    segments = {s["stance"]: s for s in view["stance_segments"]}
    assert segments["bullish"]["count"] == 4
    assert segments["neutral"]["count"] == 1
    assert segments["bearish"]["count"] == 1
    total_pct = sum(s["pct"] for s in view["stance_segments"])
    assert abs(total_pct - 100.0) < 1e-6


def test_stance_segments_empty_claims_all_zero() -> None:
    view = cv.build_corroboration_view(_FakeCorrView(ticker="X", claims=()))
    assert view["stance_segments"] == []


# ---------------------------------------------------------------------------
# Readout rows
# ---------------------------------------------------------------------------


def test_readout_rows_populated() -> None:
    readout = OurReadout(
        factor_percentile=82.0,
        trend_health=TrendHealth.HEALTHY,
        divergence_flag=False,
        discipline_flag="clear",
    )
    view = cv.build_corroboration_view(
        _view_with_snapshot(ConvergenceTier.MODERATE), our_readout=readout
    )
    rows = dict(view["readout_rows"])
    assert rows["Factor percentile"] == "82th"
    assert rows["Trend health"] == "healthy"
    assert rows["Divergence flag"] == "none"
    assert rows["Discipline flag"] == "clear"


def test_readout_rows_none_readout_is_data_gap() -> None:
    view = cv.build_corroboration_view(_view_with_snapshot(ConvergenceTier.MODERATE))
    rows = dict(view["readout_rows"])
    assert all(v == "—" for v in rows.values())


# ---------------------------------------------------------------------------
# Claim grouping reuse
# ---------------------------------------------------------------------------


def test_claims_grouped_into_strong_moderate_weak() -> None:
    view = cv.build_corroboration_view(_view_with_snapshot(ConvergenceTier.MODERATE))
    assert len(view["claims_strong"]) == 2  # Reuters .85, 10-K .90 (verified & >=0.70)
    # Analyst note .65 (verified), Trade press .55 (unverified but weight>=0.45), Analyst B .60 (verified)
    assert len(view["claims_moderate"]) == 3
    assert len(view["claims_weak"]) == 1  # Blog .30 unverified, weight<0.45


# ---------------------------------------------------------------------------
# FORBIDDEN_WORDS
# ---------------------------------------------------------------------------


def test_clean_of_slop() -> None:
    src = inspect.getsource(cv).lower()
    violations = [w for w in FORBIDDEN_WORDS if w in src]
    assert not violations, f"FORBIDDEN_WORDS found in module: {violations}"
