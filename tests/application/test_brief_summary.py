import json

from application.brief_summary import brief_to_summary_dict
from domain.brief import (
    BuyCandidateLine,
    ConcentrationFlag,
    HoldingVerdictLine,
    ScorecardSnapshot,
    WeeklyBrief,
)
from domain.discipline import Verdict  # validated: domain/discipline.py:38
from domain.models import (
    BookMacroExposure,
    HoldingMacroExposure,
    MacroBetaFlag,
    MacroFactorBeta,
)
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


# ---------------------------------------------------------------------------
# Task 9 — v8 macro-stats serialization
# ---------------------------------------------------------------------------


def _v8_macro() -> BookMacroExposure:
    """Minimal BookMacroExposure with all v8 fields populated for serialization tests."""
    hme = HoldingMacroExposure(
        ticker="NVDA",
        weight=0.15,
        betas=(MacroFactorBeta("SPY", 1.18, 1.21, 0.03),),
        r_squared=0.62,
    )
    flag = MacroBetaFlag(
        kind="SYSTEMATIC_DOMINANT",
        factor=None,
        message="systematic share above threshold",
        value=0.71,
        threshold=0.6,
    )
    return BookMacroExposure(
        as_of="2026-06-15",
        factors=("SPY", "TLT"),
        net_beta_by_factor={"SPY": 1.18, "TLT": -0.10},
        systematic_share=0.71,
        idiosyncratic_share=0.29,
        dominant_factor="SPY",
        flags=(flag,),
        holdings=(hme,),
        coverage_holdings=1,
        total_holdings=2,
        coverage_value_frac=0.75,
        # v8 fields
        enb=3.2,
        pc_variance=(0.55, 0.22, 0.12),
        pc_labels=("market", "rates", "momentum"),
        pc_labels_data_gap=False,
        systematic_share_adj=0.69,
        systematic_share_ci=(0.66, 0.76),
        beta_ci_by_factor={"SPY": (1.09, 1.27)},
        suppressed_factors=("XLE",),
        downside_beta=1.35,
        risk_contribution={"NVDA": 0.60, "AAPL": 0.40},
        holdings_meta=({"ticker": "NVDA", "sector": "Technology", "weight": 0.15},),
        sector_weights={"Technology": 0.55, "Healthcare": 0.20},
        sector_hhi=0.34,
        sector_gaps=("Energy", "Utilities"),
        vif_by_factor={"SPY": 2.1, "TLT": float("inf")},
        diversification_ratio=1.42,
        sys_share_history=(("2026-06-01", 0.68), ("2026-06-08", 0.71)),
    )


def test_macro_block_serializes_new_fields():
    """All v8 keys must be present in the serialized macro dict."""
    macro = _v8_macro()
    brief = _brief(macro=macro)
    d = brief_to_summary_dict(brief)["macro"]
    assert d is not None

    # Key presence
    for key in (
        "enb",
        "pc_variance",
        "pc_labels",
        "pc_labels_data_gap",
        "systematic_share_adj",
        "systematic_share_ci",
        "beta_ci_by_factor",
        "suppressed_factors",
        "downside_beta",
        "risk_contribution",
        "holdings_meta",
        "sector_weights",
        "sector_hhi",
        "sector_gaps",
        "vif_by_factor",
        "diversification_ratio",
        "sys_share_history",
    ):
        assert key in d, f"missing key: {key}"

    # Value fidelity — tuple→list conversions
    assert d["systematic_share_ci"] == [0.66, 0.76]
    assert d["beta_ci_by_factor"]["SPY"] == [1.09, 1.27]
    assert d["enb"] == 3.2
    assert d["pc_variance"] == [0.55, 0.22, 0.12]
    assert d["pc_labels"] == ["market", "rates", "momentum"]
    assert d["pc_labels_data_gap"] is False
    assert d["suppressed_factors"] == ["XLE"]
    assert d["sector_gaps"] == ["Energy", "Utilities"]
    assert d["downside_beta"] == 1.35
    assert d["sector_hhi"] == 0.34
    assert d["diversification_ratio"] == 1.42
    assert d["systematic_share_adj"] == 0.69
    assert d["risk_contribution"] == {"NVDA": 0.60, "AAPL": 0.40}
    assert d["sector_weights"] == {"Technology": 0.55, "Healthcare": 0.20}
    # holdings_meta: tuple of dicts → list of dicts
    assert d["holdings_meta"] == [
        {"ticker": "NVDA", "sector": "Technology", "weight": 0.15}
    ]
    # sys_share_history: tuple of (date, value) → list of [date, value]
    assert d["sys_share_history"] == [["2026-06-01", 0.68], ["2026-06-08", 0.71]]


def test_macro_block_inf_vif_serializes_as_none():
    """float('inf') in vif_by_factor must serialize to None (JSON-safe sentinel)."""
    macro = _v8_macro()
    brief = _brief(macro=macro)
    d = brief_to_summary_dict(brief)["macro"]
    # TLT VIF was set to float('inf') — must come out as None
    assert d["vif_by_factor"]["TLT"] is None
    # SPY VIF was a finite float — must pass through as-is
    assert d["vif_by_factor"]["SPY"] == 2.1


def test_macro_block_full_dict_is_json_serializable():
    """json.dumps of brief_to_summary_dict must not raise (esp. with inf VIF)."""
    macro = _v8_macro()
    brief = _brief(macro=macro)
    d = brief_to_summary_dict(brief)
    # This must not raise — float('inf') must already be converted to None
    serialized = json.dumps(d)
    parsed = json.loads(serialized)
    assert parsed["macro"]["vif_by_factor"]["TLT"] is None
