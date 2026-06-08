"""Tests for PositionRisk and PortfolioRisk domain models."""


def test_position_risk_construction():
    from domain.discipline import Verdict
    from domain.models import PositionRisk

    pr = PositionRisk(
        ticker="MU",
        price=100.0,
        verdict=Verdict.REDUCE,
        confidence=0.8,
        trend_health=-3.0,
        vol_signal=0.5,
        relative_strength=-0.2,
        downside_to_stop=0.1,
        upside_to_recover=0.3,
        behavior_flags=("disposition_risk",),
        unrealized_pct=-0.31,
        account_type="TFSA",
        abstained=False,
        why="broke trend",
    )
    assert pr.ticker == "MU"
    assert pr.verdict == Verdict.REDUCE


def test_position_risk_rejects_bad_confidence():
    import pytest

    from domain.discipline import Verdict
    from domain.models import PositionRisk

    with pytest.raises(Exception):
        PositionRisk(
            ticker="MU",
            price=100.0,
            verdict=Verdict.HOLD,
            confidence=1.5,
            trend_health=0.0,
            vol_signal=0.0,
            relative_strength=0.0,
            downside_to_stop=0.0,
            upside_to_recover=0.0,
            behavior_flags=(),
            unrealized_pct=0.0,
            account_type="TFSA",
            abstained=False,
            why="",
        )


def test_portfolio_risk_construction():
    from domain.models import PortfolioRisk

    prisk = PortfolioRisk(
        n_positions=10,
        broken_trend_share=0.6,
        top_concentration=0.45,
        verdict_counts={"REDUCE": 3, "HOLD": 7},
    )
    assert prisk.n_positions == 10
    assert prisk.broken_trend_share == 0.6
