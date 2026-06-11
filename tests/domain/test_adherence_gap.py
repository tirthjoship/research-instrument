"""tests/domain/test_adherence_gap.py"""

from datetime import date

from hypothesis import given
from hypothesis import strategies as st

from domain.adherence import (
    CANONICAL_CUT_FRACTION,
    AdherenceLabel,
    Obligation,
    actual_cut_fraction,
    adherence_label,
    annualize_bps,
    build_obligations,
    gap_cad,
)


def _flag(ticker: str, d: date, verdict: str = "REDUCE") -> dict[str, object]:
    return {
        "ticker": ticker,
        "verdict": verdict,
        "as_of_date": d,
        "quantity": 100.0,
        "market_value_cad": 5000.0,
    }


def test_single_flag_one_obligation() -> None:
    obs = build_obligations([_flag("AC.TO", date(2026, 6, 13))])
    assert len(obs) == 1
    assert obs[0] == Obligation("AC.TO", "REDUCE", date(2026, 6, 13), 100.0, 5000.0)


def test_consecutive_weekly_reflag_suppressed() -> None:
    flags = [
        _flag("AC.TO", date(2026, 6, 13)),
        _flag("AC.TO", date(2026, 6, 20)),
        _flag("AC.TO", date(2026, 6, 27)),
    ]
    assert len(build_obligations(flags)) == 1  # property: N identical flags -> 1


def test_reflag_exactly_at_horizon_opens_new_obligation() -> None:
    # Boundary: obligation resolves AT 21d, so a flag exactly 21d later is a
    # NEW obligation, not a suppressed re-flag. Pins `< horizon` (not `<=`) —
    # the seam that decides whether the headline gap double-counts.
    flags = [
        _flag("AC.TO", date(2026, 6, 13)),
        _flag("AC.TO", date(2026, 7, 4)),  # exactly 21d later
    ]
    assert len(build_obligations(flags)) == 2


def test_reflag_after_horizon_opens_new_obligation() -> None:
    flags = [
        _flag("AC.TO", date(2026, 6, 13)),
        _flag("AC.TO", date(2026, 7, 11)),  # 28d later > 21d horizon
    ]
    assert len(build_obligations(flags)) == 2


def test_reduce_and_trim_are_separate_tracks() -> None:
    flags = [
        _flag("AC.TO", date(2026, 6, 13), "REDUCE"),
        _flag("AC.TO", date(2026, 6, 13), "TRIM"),
    ]
    assert len(build_obligations(flags)) == 2


@given(st.integers(min_value=1, max_value=10))
def test_property_n_identical_flags_one_obligation(n: int) -> None:
    flags = [_flag("AC.TO", date(2026, 6, 13)) for _ in range(n)]
    assert len(build_obligations(flags)) == 1


def test_cut_fraction_cumulative_min_over_window() -> None:
    # qty 100 at flag; later weekly snapshots 80 then 40 inside window
    cut = actual_cut_fraction(100.0, [80.0, 40.0])
    assert cut == 0.6


def test_cut_fraction_rebuy_does_not_uncut() -> None:
    # sold to 40 then re-bought to 90: max cut reached is what counts
    assert actual_cut_fraction(100.0, [40.0, 90.0]) == 0.6


def test_labels_derive_from_canonical_fraction() -> None:
    assert adherence_label(0.5) is AdherenceLabel.FOLLOWED
    assert adherence_label(0.6) is AdherenceLabel.FOLLOWED
    assert adherence_label(0.2) is AdherenceLabel.PARTIAL
    assert adherence_label(0.0) is AdherenceLabel.IGNORED


def test_gap_ignored_full_shortfall() -> None:
    # ignored REDUCE, price fell 10%: gap = 5000 * 0.5 * 0.10 = +250 CAD
    assert gap_cad(5000.0, 0.0, -0.10) == 250.0


def test_gap_followed_is_zero() -> None:
    assert gap_cad(5000.0, 0.5, -0.10) == 0.0


def test_gap_partial_scales_with_shortfall() -> None:
    # cut 0.25 of position, shortfall 0.25: gap = 5000 * 0.25 * 0.10 = +125
    assert gap_cad(5000.0, 0.25, -0.10) == 125.0


def test_gap_negative_when_price_rises() -> None:
    # ignored flag but price rose: following would have COST money
    assert gap_cad(5000.0, 0.0, 0.10) == -250.0


def test_annualize() -> None:
    assert annualize_bps(100.0, days_observed=182.5) == 200.0


def test_canonical_fraction_is_single_source() -> None:
    assert CANONICAL_CUT_FRACTION == 0.5
