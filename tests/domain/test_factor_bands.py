import pytest
from hypothesis import given
from hypothesis import strategies as st

from domain.factor_bands import Band, band_for_percentile


@pytest.mark.parametrize(
    "pct,expected",
    [
        (0.95, Band.EXCEPTIONAL),
        (0.90, Band.EXCEPTIONAL),  # inclusive lower edge
        (0.89, Band.STRONG),
        (0.75, Band.STRONG),  # inclusive lower edge
        (0.74, Band.FLAT),
        (0.40, Band.FLAT),  # inclusive lower edge
        (0.39, Band.WEAK),
        (0.00, Band.WEAK),
    ],
)
def test_band_for_percentile_boundaries(pct, expected):
    assert band_for_percentile(pct) == expected


_ORDER = {Band.WEAK: 0, Band.FLAT: 1, Band.STRONG: 2, Band.EXCEPTIONAL: 3}


@given(
    a=st.floats(min_value=0.0, max_value=1.0),
    b=st.floats(min_value=0.0, max_value=1.0),
)
def test_band_monotonic(a, b):
    if a <= b:
        assert _ORDER[band_for_percentile(a)] <= _ORDER[band_for_percentile(b)]


@given(p=st.floats(allow_nan=False, allow_infinity=False))
def test_band_clamps_out_of_range(p):
    # values <0 or >1 (e.g. float noise) must still return a valid Band, never raise
    assert band_for_percentile(p) in Band
