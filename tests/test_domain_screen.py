from domain.screen import abstain_if_thin, eligible, rank_universe
from domain.screen_models import FactorScore, ScreenCandidate, ScreenLabel


def _c(t: str, comp: float) -> ScreenCandidate:
    return ScreenCandidate(
        t,
        comp,
        (FactorScore("momentum", comp, 0.5, comp),),
        0.1,
        "",
        ScreenLabel.RESEARCH_ONLY,
    )


def test_eligible_requires_uptrend_and_history() -> None:
    assert eligible(trend_health=0.2, has_min_history=True) is True
    assert eligible(trend_health=-0.1, has_min_history=True) is False
    assert eligible(trend_health=0.2, has_min_history=False) is False


def test_rank_orders_desc_and_caps_top_n() -> None:
    out = rank_universe([_c("A", 0.1), _c("B", 0.9), _c("C", 0.5)], top_n=2)
    assert [c.ticker for c in out] == ["B", "C"]


def test_abstain_when_coverage_thin() -> None:
    assert abstain_if_thin(present_factor_fraction=0.2) is True
    assert abstain_if_thin(present_factor_fraction=0.9) is False
