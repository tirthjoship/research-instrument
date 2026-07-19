from datetime import datetime

from hypothesis import given
from hypothesis import strategies as st

from domain.macro_beta import (
    aggregate_macro_exposure,
    align_returns,
    book_return_series,
    build_flags,
    daily_returns,
    net_beta,
)
from domain.models import (
    BookMacroExposure,
    HoldingMacroExposure,
    MacroBetaFlag,
    MacroFactorBeta,
)


def _d(day: int) -> datetime:
    return datetime(2026, 1, day)


def _hme(
    ticker: str,
    weight: float,
    betas: list[tuple[str, float, float]],
    r2: float,
) -> HoldingMacroExposure:
    return HoldingMacroExposure(
        ticker=ticker,
        weight=weight,
        betas=tuple(MacroFactorBeta(f, bh, br, br - bh) for f, bh, br in betas),
        r_squared=r2,
    )


def test_macro_factor_beta_drift_field():
    b = MacroFactorBeta(factor="TLT", beta_headline=0.4, beta_recent=0.7, drift=0.3)
    assert b.factor == "TLT"
    assert b.drift == 0.3


def test_book_macro_exposure_holds_pieces():
    hb = HoldingMacroExposure(
        ticker="NVDA",
        weight=0.1,
        betas=(MacroFactorBeta("SPY", 1.2, 1.3, 0.1),),
        r_squared=0.55,
    )
    flag = MacroBetaFlag(
        kind="SYSTEMATIC_DOMINANT",
        factor=None,
        message="x",
        value=0.7,
        threshold=0.6,
    )
    book = BookMacroExposure(
        as_of="2026-06-09",
        factors=("SPY", "TLT", "UUP", "XLE"),
        net_beta_by_factor={"SPY": 0.9, "TLT": -0.2, "UUP": 0.1, "XLE": 0.3},
        systematic_share=0.7,
        idiosyncratic_share=0.3,
        dominant_factor="SPY",
        flags=(flag,),
        holdings=(hb,),
        coverage_holdings=1,
        total_holdings=1,
        coverage_value_frac=1.0,
    )
    assert book.dominant_factor == "SPY"
    assert book.holdings[0].ticker == "NVDA"
    assert book.flags[0].kind == "SYSTEMATIC_DOMINANT"


def test_daily_returns_simple():
    series = [(_d(1), 100.0), (_d(2), 110.0), (_d(3), 99.0)]
    out = daily_returns(series)
    assert out[0][0] == _d(2)
    assert abs(out[0][1] - 0.10) < 1e-9
    assert abs(out[1][1] - (-0.10)) < 1e-9


def test_daily_returns_skips_zero_prev():
    series = [(_d(1), 0.0), (_d(2), 100.0), (_d(3), 110.0)]
    out = daily_returns(series)
    assert len(out) == 1
    assert abs(out[0][1] - 0.10) < 1e-9


def test_align_returns_inner_join():
    y = [(_d(2), 0.01), (_d(3), 0.02), (_d(4), 0.03)]
    factors = {
        "SPY": [(_d(2), 0.005), (_d(3), 0.006)],
        "TLT": [(_d(3), -0.01), (_d(4), -0.02)],
    }
    y_out, f_out = align_returns(y, factors)
    assert y_out == [0.02]
    assert f_out["SPY"] == [0.006]
    assert f_out["TLT"] == [-0.01]


def test_book_return_series_renormalizes_per_date():
    holding_returns = {
        "A": [(_d(2), 0.10), (_d(3), 0.20)],
        "B": [(_d(2), 0.30)],
    }
    weights = {"A": 0.5, "B": 0.5}
    out = book_return_series(holding_returns, weights, [_d(2), _d(3)])
    assert abs(out[0][1] - 0.20) < 1e-9
    assert abs(out[1][1] - 0.20) < 1e-9


def test_net_beta_dollar_weighted():
    holdings = [
        _hme("A", 0.5, [("SPY", 1.0, 1.0), ("TLT", -0.4, -0.4)], 0.6),
        _hme("B", 0.5, [("SPY", 0.6, 0.6), ("TLT", 0.2, 0.2)], 0.4),
    ]
    nb = net_beta(holdings, ("SPY", "TLT"))
    assert abs(nb["SPY"] - 0.8) < 1e-9
    assert abs(nb["TLT"] - (-0.1)) < 1e-9


def test_build_flags_systematic_dominant():
    flags = build_flags(
        net_beta_by_factor={"SPY": 0.2, "TLT": 0.0},
        systematic_share=0.72,
        factor_move_std={"SPY": 0.01, "TLT": 0.01},
        book_drift_by_factor={"SPY": 0.0, "TLT": 0.0},
        beta_headline_by_factor={"SPY": 0.2, "TLT": 0.0},
        systematic_share_threshold=0.60,
        factor_dominance_threshold=0.25,
        drift_threshold=0.50,
    )
    kinds = {f.kind for f in flags}
    assert "SYSTEMATIC_DOMINANT" in kinds


def test_build_flags_factor_dominance_and_drift():
    flags = build_flags(
        net_beta_by_factor={"TLT": 2.0},
        systematic_share=0.30,
        factor_move_std={"TLT": 0.20},
        book_drift_by_factor={"TLT": 0.6},
        beta_headline_by_factor={"TLT": 1.0},
        systematic_share_threshold=0.60,
        factor_dominance_threshold=0.25,
        drift_threshold=0.50,
    )
    kinds = {f.kind for f in flags}
    assert "FACTOR_DOMINANCE" in kinds
    assert "DRIFT" in kinds


def test_aggregate_empty_abstains():
    book = aggregate_macro_exposure(
        as_of="2026-06-09",
        factors=("SPY", "TLT", "UUP", "XLE"),
        per_holding=[],
        systematic_share=0.0,
        factor_move_std={},
        book_drift_by_factor={},
        beta_headline_by_factor={},
        total_holdings=5,
        coverage_value_frac=0.0,
        thresholds={
            "systematic_share_threshold": 0.60,
            "factor_dominance_threshold": 0.25,
            "drift_threshold": 0.50,
        },
    )
    assert book.coverage_holdings == 0
    assert book.flags == ()
    assert book.dominant_factor is None


@given(
    w=st.floats(min_value=0.01, max_value=0.99),
    b1=st.floats(min_value=-3, max_value=3),
    b2=st.floats(min_value=-3, max_value=3),
)
def test_net_beta_equals_weighted_sum_property(w: float, b1: float, b2: float) -> None:
    holdings = [
        _hme("A", w, [("SPY", b1, b1)], 0.5),
        _hme("B", 1 - w, [("SPY", b2, b2)], 0.5),
    ]
    nb = net_beta(holdings, ("SPY",))
    assert abs(nb["SPY"] - (w * b1 + (1 - w) * b2)) < 1e-6


@given(s=st.floats(min_value=0.0, max_value=1.0))
def test_systematic_idiosyncratic_sum_to_one(s: float) -> None:
    book = aggregate_macro_exposure(
        as_of="2026-06-09",
        factors=("SPY",),
        per_holding=[_hme("A", 1.0, [("SPY", 1.0, 1.0)], s)],
        systematic_share=s,
        factor_move_std={"SPY": 0.01},
        book_drift_by_factor={"SPY": 0.0},
        beta_headline_by_factor={"SPY": 1.0},
        total_holdings=1,
        coverage_value_frac=1.0,
        thresholds={
            "systematic_share_threshold": 0.60,
            "factor_dominance_threshold": 0.25,
            "drift_threshold": 0.50,
        },
    )
    assert abs(book.systematic_share + book.idiosyncratic_share - 1.0) < 1e-9
    assert 0.0 <= book.systematic_share <= 1.0


def test_estimator_port_is_protocol():
    from domain.ports import MacroBetaEstimatorPort

    class _Fake:
        def estimate(self, y_returns, factor_returns, alpha):
            return ({k: 0.0 for k in factor_returns}, 0.0)

    f: MacroBetaEstimatorPort = _Fake()
    betas, r2 = f.estimate([0.1], {"SPY": [0.1]}, 0.2)
    assert r2 == 0.0
    assert betas == {"SPY": 0.0}


def test_brief_renders_macro_section():
    from domain.brief import (
        ScorecardSnapshot,
        WeeklyBrief,
        to_markdown,
        to_stdout_masked,
    )
    from domain.models import (
        BookMacroExposure,
        HoldingMacroExposure,
        MacroBetaFlag,
        MacroFactorBeta,
    )
    from domain.regime import Regime
    from domain.screen_models import ScreenLabel

    macro = BookMacroExposure(
        as_of="2026-06-09",
        factors=("SPY", "TLT", "UUP", "XLE"),
        net_beta_by_factor={"SPY": 0.9, "TLT": -0.6, "UUP": 0.1, "XLE": 0.2},
        systematic_share=0.72,
        idiosyncratic_share=0.28,
        dominant_factor="SPY",
        flags=(MacroBetaFlag("SYSTEMATIC_DOMINANT", None, "72% macro", 0.72, 0.60),),
        holdings=(
            HoldingMacroExposure(
                "NVDA", 0.2, (MacroFactorBeta("SPY", 1.4, 1.5, 0.1),), 0.6
            ),
        ),
        coverage_holdings=1,
        total_holdings=1,
        coverage_value_frac=0.95,
    )
    brief = WeeklyBrief(
        as_of="2026-06-09",
        regime=Regime.RISK_ON,
        tilt={"momentum": 0.25, "revision": 0.25, "quality": 0.25, "value": 0.25},
        candidates=(),
        holdings=(),
        research_links=(),
        concentration=(),
        scorecard=ScorecardSnapshot(
            "forward since 2026-06-09", None, None, 0, False, "21d", None, 0, "PENDING"
        ),
        screen_label=ScreenLabel.RESEARCH_ONLY,
        macro=macro,
    )
    md = to_markdown(brief)
    assert "## Macro Exposure" in md
    assert "72%" in md
    assert "NVDA" in md

    masked = to_stdout_masked(brief)
    assert "MACRO" in masked
    assert "NVDA" not in masked


def test_drift_suppressed_for_negligible_beta():
    # Huge drift RATIO but tiny absolute exposure (headline 0.03, recent ~0.20 drift):
    # must NOT fire DRIFT — that's the UUP-562% alarm-fatigue case.
    flags = build_flags(
        net_beta_by_factor={"UUP": 0.03},
        systematic_share=0.30,
        factor_move_std={"UUP": 0.01},
        book_drift_by_factor={"UUP": 0.17},  # recent = 0.03 + 0.17 = 0.20
        beta_headline_by_factor={"UUP": 0.03},
        systematic_share_threshold=0.60,
        factor_dominance_threshold=0.25,
        drift_threshold=0.50,
    )
    assert all(f.kind != "DRIFT" for f in flags)


def test_drift_fires_for_material_beta():
    # Material exposure (headline 1.0) with >50% drift: DRIFT SHOULD fire.
    flags = build_flags(
        net_beta_by_factor={"TLT": 1.0},
        systematic_share=0.30,
        factor_move_std={"TLT": 0.01},
        book_drift_by_factor={"TLT": 0.6},  # recent = 1.6, ratio 0.6 > 0.5
        beta_headline_by_factor={"TLT": 1.0},
        systematic_share_threshold=0.60,
        factor_dominance_threshold=0.25,
        drift_threshold=0.50,
    )
    assert any(f.kind == "DRIFT" and f.factor == "TLT" for f in flags)


def test_brief_macro_none_renders_safely():
    from domain.brief import ScorecardSnapshot, WeeklyBrief, to_markdown
    from domain.regime import Regime
    from domain.screen_models import ScreenLabel

    brief = WeeklyBrief(
        as_of="2026-06-09",
        regime=Regime.RISK_ON,
        tilt={"momentum": 0.25, "revision": 0.25, "quality": 0.25, "value": 0.25},
        candidates=(),
        holdings=(),
        research_links=(),
        concentration=(),
        scorecard=ScorecardSnapshot(
            "forward since 2026-06-09", None, None, 0, False, "21d", None, 0, "PENDING"
        ),
        screen_label=ScreenLabel.RESEARCH_ONLY,
    )
    md = to_markdown(brief)
    assert "## Macro Exposure" in md
    assert "not computed" in md


def test_aligned_return_matrix_common_dates_only():
    from datetime import datetime

    from domain.macro_beta import aligned_return_matrix

    d1, d2, d3 = datetime(2026, 1, 2), datetime(2026, 1, 3), datetime(2026, 1, 4)
    hr = {
        "AAA": [(d1, 0.01), (d2, 0.02), (d3, 0.03)],
        "BBB": [(d2, -0.01), (d3, 0.04)],  # missing d1
    }
    tickers, rows = aligned_return_matrix(hr)
    assert tickers == ["AAA", "BBB"]
    assert rows == [[0.02, -0.01], [0.03, 0.04]]  # only d2, d3 common


def test_aligned_return_matrix_empty():
    from domain.macro_beta import aligned_return_matrix

    assert aligned_return_matrix({}) == ([], [])


def test_book_macro_exposure_carries_new_fields():
    from domain.models import BookMacroExposure

    b = BookMacroExposure(
        as_of="2026-06-15",
        factors=("SPY",),
        net_beta_by_factor={"SPY": 1.18},
        systematic_share=0.71,
        idiosyncratic_share=0.29,
        dominant_factor="SPY",
        flags=(),
        holdings=(),
        coverage_holdings=58,
        total_holdings=66,
        coverage_value_frac=0.9,
        enb=3.2,
        pc_variance=(0.64, 0.14, 0.09),
        pc_labels=("PC1", "PC2", "PC3"),
        systematic_share_adj=0.66,
        systematic_share_ci=(0.66, 0.76),
        beta_ci_by_factor={"SPY": (1.09, 1.27)},
        suppressed_factors=(),
        downside_beta=1.31,
        risk_contribution={"NVDA": 0.14},
        holdings_meta=(
            {
                "ticker": "NVDA",
                "name": "Nvidia",
                "sector": "Information Technology",
                "weight": 0.09,
            },
        ),
        sector_weights={"Information Technology": 0.52},
        sector_hhi=0.34,
        sector_gaps=("Health Care",),
        vif_by_factor={"SPY": 1.0},
        diversification_ratio=1.4,
        sys_share_history=(("2026-06-08", 0.64), ("2026-06-15", 0.71)),
    )
    assert b.enb == 3.2 and b.downside_beta == 1.31
