from application.brief_summary import brief_to_summary_dict
from domain.brief import (
    BuyCandidateLine,
    ConcentrationFlag,
    HoldingVerdictLine,
    ScorecardSnapshot,
    WeeklyBrief,
)
from domain.discipline import Verdict  # validated: domain/discipline.py:38
from domain.regime import Regime  # validated: domain/regime.py:21, UPPERCASE members
from domain.screen_models import ScreenLabel


def _brief(macro=None):
    return WeeklyBrief(
        as_of="2026-06-13",
        regime=Regime.NEUTRAL,
        tilt={"equity": 1.0},
        candidates=(
            BuyCandidateLine(
                ticker="ABC",
                composite=0.71,
                factor_summary="value strong",
                why="cheap vs sector",
                already_held=False,
                label=ScreenLabel.RESEARCH_ONLY,
            ),
        ),
        holdings=(
            HoldingVerdictLine(
                ticker="ARKK",
                unrealized_pct=-12.0,
                trend_state="broken",
                verdict=Verdict.REDUCE,
                why="trend broken, momentum negative",
            ),
        ),
        research_links=(),
        concentration=(ConcentrationFlag(descriptor="Tech 40%", soft_warning=True),),
        scorecard=ScorecardSnapshot(
            screen_window="4w",
            screen_top_ret=None,
            screen_spy_ret=None,
            screen_n=0,
            screen_significant=False,
            discipline_window="8w",
            discipline_reduce_down_rate=None,
            discipline_n=42,
            discipline_gate_status="ACCRUING",
        ),
        screen_label=ScreenLabel.RESEARCH_ONLY,
        macro=macro,
    )


def test_summary_dict_has_flags_grouped_and_dates():
    d = brief_to_summary_dict(_brief())
    assert d["as_of"] == "2026-06-13"
    assert d["screen_label"] == "RESEARCH_ONLY"
    assert d["holdings"][0] == {
        "ticker": "ARKK",
        "verdict": "REDUCE",
        "unrealized_pct": -12.0,
        "trend_state": "broken",
        "why": "trend broken, momentum negative",
    }
    assert d["candidates"][0]["ticker"] == "ABC"
    assert d["macro"] is None
    assert d["scorecard"]["discipline_gate_status"] == "ACCRUING"
    assert d["abstained"] is False  # 1 candidate present


def test_summary_dict_abstention_flag():
    # abstained must come from the WeeklyBrief.abstained flag (sourced from
    # ScreenResult.abstained), NOT recomputed from len(candidates).
    b = _brief()
    # Explicitly set abstained=True; candidates being empty is orthogonal.
    b = WeeklyBrief(**{**b.__dict__, "candidates": (), "abstained": True})
    d = brief_to_summary_dict(b)
    assert d["abstained"] is True


def test_summary_dict_abstained_false_when_empty_candidates_but_not_abstained():
    """Regression: zero candidates with abstained=False must return False.
    The old len(candidates)==0 logic would return True here — that was the bug."""
    b = _brief()
    b = WeeklyBrief(**{**b.__dict__, "candidates": (), "abstained": False})
    d = brief_to_summary_dict(b)
    assert d["abstained"] is False
