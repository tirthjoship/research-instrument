from itertools import product

import pytest
from hypothesis import given
from hypothesis import strategies as st

from domain.factor_bands import Band, band_for_percentile, band_tone_key, plain_read


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


def test_band_tone_key():
    assert band_tone_key(Band.EXCEPTIONAL) == "success"
    assert band_tone_key(Band.STRONG) == "accent"
    assert band_tone_key(Band.FLAT) == "muted"
    assert band_tone_key(Band.WEAK) == "danger"


# profile keys are the canonical factor names; values are Bands
SPG = {
    "quality": Band.EXCEPTIONAL,
    "value": Band.STRONG,
    "revision": Band.EXCEPTIONAL,
    "momentum": Band.FLAT,
    "lowvol": Band.EXCEPTIONAL,
}
KLAC = {
    "quality": Band.EXCEPTIONAL,
    "value": Band.WEAK,
    "revision": Band.FLAT,
    "momentum": Band.EXCEPTIONAL,
    "lowvol": Band.FLAT,
}


def test_plain_read_value_setup():
    txt = plain_read(SPG)
    assert "quality" in txt.lower() and "value" in txt.lower()
    assert "flat" in txt.lower()  # momentum flat surfaced
    assert txt.endswith(".")


def test_plain_read_expensive():
    txt = plain_read(KLAC)
    assert "not cheap" in txt.lower() or "expensive" in txt.lower()


def test_plain_read_no_forbidden_words():
    forbidden = (
        "buy",
        "sell",
        "winner",
        "conviction",
        "predict",
        "alpha",
        "outperform",
    )
    for profile in (SPG, KLAC):
        low = plain_read(profile).lower()
        assert not any(w in low.split() for w in forbidden)


def test_plain_read_total_over_all_profiles():
    factors = ["quality", "value", "revision", "momentum", "lowvol"]
    for combo in product(Band, repeat=len(factors)):
        profile = dict(zip(factors, combo))
        out = plain_read(profile)
        assert isinstance(out, str) and out.endswith(".")
