import pytest

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
