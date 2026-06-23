# tests/domain/test_screened_row.py
from __future__ import annotations

from datetime import date

import pytest

from domain.corroboration_models import ConvergenceTier
from domain.screen_models import FactorScore, ScreenCandidate, ScreenLabel
from domain.screened_row import TIER_RANK, CorroborationSnapshot, ScreenedRow, blend


def _make_candidate(composite: float = 1.0) -> ScreenCandidate:
    fs = FactorScore(name="momentum", value=composite, percentile=0.9, contribution=0.2)
    return ScreenCandidate(
        ticker="AAPL",
        composite=composite,
        factor_scores=(fs,),
        trend_health=0.8,
        why="strong momentum",
        label=ScreenLabel.RESEARCH_ONLY,
    )


def _make_snap(tier: ConvergenceTier, n: int = 3) -> CorroborationSnapshot:
    return CorroborationSnapshot(
        ticker="AAPL",
        convergence_tier=tier,
        n_sources=n,
        surfaced_at=date(2026, 6, 21),
    )


def test_tier_rank_values() -> None:
    assert TIER_RANK[ConvergenceTier.STRONG] == 1.0
    assert TIER_RANK[ConvergenceTier.MODERATE] == pytest.approx(0.67)
    assert TIER_RANK[ConvergenceTier.WEAK] == pytest.approx(0.33)
    assert TIER_RANK[ConvergenceTier.CONFLICTED] == 0.0


def test_blend_strong_corroboration() -> None:
    result = blend(factor_pct=0.8, snap=_make_snap(ConvergenceTier.STRONG))
    assert result == pytest.approx(0.5 * 0.8 + 0.5 * 1.0)


def test_blend_no_corroboration_returns_factor_pct() -> None:
    assert blend(factor_pct=0.75, snap=None) == pytest.approx(0.75)


def test_blend_none_tier_returns_factor_pct() -> None:
    assert blend(
        factor_pct=0.6, snap=_make_snap(ConvergenceTier.NONE)
    ) == pytest.approx(0.6)


def test_screened_row_factor_only_flag() -> None:
    row = ScreenedRow(
        candidate=_make_candidate(),
        corroboration=None,
        blended_percentile=0.75,
        factor_only=True,
    )
    assert row.factor_only is True
    assert row.corroboration is None
