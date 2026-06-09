from datetime import datetime

from domain.macro_beta import align_returns, book_return_series, daily_returns
from domain.models import (
    BookMacroExposure,
    HoldingMacroExposure,
    MacroBetaFlag,
    MacroFactorBeta,
)


def _d(day: int) -> datetime:
    return datetime(2026, 1, day)


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
