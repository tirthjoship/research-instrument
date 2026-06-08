import pytest

from domain.screen_models import FactorScore, ScreenCandidate, ScreenLabel, ScreenResult


def test_candidate_frozen_and_valid():
    c = ScreenCandidate(
        ticker="MU",
        composite=0.8,
        factor_scores=(FactorScore("momentum", 1.2, 0.94, 0.3),),
        trend_health=0.5,
        why="strong momentum",
        label=ScreenLabel.RESEARCH_ONLY,
    )
    with pytest.raises(Exception):
        c.composite = 0.1  # frozen


def test_result_rejects_negative_universe():
    with pytest.raises(ValueError):
        ScreenResult(
            as_of="2026-06-08",
            candidates=(),
            universe_size=-1,
            regime="NEUTRAL",
            scorecard_ref=None,
        )
