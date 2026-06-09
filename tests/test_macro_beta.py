from domain.models import (
    BookMacroExposure,
    HoldingMacroExposure,
    MacroBetaFlag,
    MacroFactorBeta,
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
