from hypothesis import given
from hypothesis import strategies as st

from domain.screen_buckets import (
    MAX_PER_BUCKET,
    PRIORITY,
    TOP_QUARTILE,
    Bucket,
    BucketInput,
    assign_buckets,
    primary_bucket,
    qualifies,
)


def test_bucketinput_holds_percentiles():
    c = BucketInput(
        ticker="SPG", percentiles={"quality": 0.95, "value": 0.87}, composite=1.31
    )
    assert c.ticker == "SPG"
    assert c.percentiles["quality"] == 0.95
    assert TOP_QUARTILE == 0.75


SPG = {
    "quality": 0.95,
    "value": 0.87,
    "revision": 0.92,
    "momentum": 0.59,
    "lowvol": 0.91,
}
KLAC = {
    "quality": 0.95,
    "value": 0.15,
    "revision": 0.48,
    "momentum": 0.95,
    "lowvol": 0.40,
}
KO = {
    "quality": 0.80,
    "value": 0.55,
    "revision": 0.45,
    "momentum": 0.40,
    "lowvol": 0.93,
}


def test_qualifies_quality_fair_price():
    assert (
        qualifies(Bucket.QUALITY_FAIR_PRICE, SPG) is True
    )  # quality & value both >=0.75
    assert qualifies(Bucket.QUALITY_FAIR_PRICE, KLAC) is False  # value 0.15


def test_qualifies_all_rounder():
    assert (
        qualifies(Bucket.ALL_ROUNDER, SPG) is True
    )  # quality,value,revision,lowvol >=0.75 (>=3)
    assert qualifies(Bucket.ALL_ROUNDER, KO) is False  # only lowvol & quality(0.80) =2


def test_qualifies_momentum_leaders_needs_both():
    assert (
        qualifies(Bucket.MOMENTUM_LEADERS, KLAC) is False
    )  # momentum yes, revision 0.48 no


def test_qualifies_lowvol_and_compounders():
    assert qualifies(Bucket.LOWVOL_DEFENSIVES, KO) is True  # lowvol 0.93
    assert qualifies(Bucket.QUALITY_COMPOUNDERS, KLAC) is True  # quality 0.95


def test_priority_order_constant():
    assert PRIORITY[0] == Bucket.ALL_ROUNDER
    assert PRIORITY[-1] == Bucket.LOWVOL_DEFENSIVES


def test_primary_bucket_picks_highest_priority():
    # SPG qualifies for ALL_ROUNDER, QUALITY_FAIR_PRICE, VALUE_CATALYST, etc.
    assert primary_bucket(SPG) == Bucket.ALL_ROUNDER


def test_primary_bucket_none_when_unqualified():
    weak = {
        "quality": 0.1,
        "value": 0.1,
        "revision": 0.1,
        "momentum": 0.1,
        "lowvol": 0.1,
    }
    assert primary_bucket(weak) is None


def _mk(t, p, c):
    return BucketInput(ticker=t, percentiles=p, composite=c)


def test_assign_groups_and_ranks_and_allows_repeats():
    cands = [
        _mk("SPG", SPG, 1.31),
        _mk("KLAC", KLAC, 1.08),
        _mk("KO", KO, 1.05),
    ]
    out = assign_buckets(cands)
    # SPG repeats across several buckets (repeats allowed)
    fair = [c.ticker for c in out[Bucket.QUALITY_FAIR_PRICE]]
    assert "SPG" in fair
    allr = [c.ticker for c in out[Bucket.ALL_ROUNDER]]
    assert "SPG" in allr
    # KLAC (quality 0.95, value weak) is a compounder, not fair-price
    comp = [c.ticker for c in out[Bucket.QUALITY_COMPOUNDERS]]
    assert "KLAC" in comp and "KLAC" not in fair
    # KO is a low-vol defensive
    defv = [c.ticker for c in out[Bucket.LOWVOL_DEFENSIVES]]
    assert "KO" in defv


def test_assign_ranks_by_composite_desc():
    a = _mk("AAA", SPG, 0.5)
    b = _mk("BBB", SPG, 1.5)
    out = assign_buckets([a, b])
    fair = [c.ticker for c in out[Bucket.QUALITY_FAIR_PRICE]]
    assert fair == ["BBB", "AAA"]  # higher composite first


def test_assign_caps_at_five_per_bucket():
    cands = [_mk(f"T{i}", SPG, float(i)) for i in range(8)]
    out = assign_buckets(cands)
    assert len(out[Bucket.QUALITY_FAIR_PRICE]) == MAX_PER_BUCKET == 5


def test_assign_empty_bucket_present_with_empty_list():
    # no momentum-leader qualifiers in this set
    out = assign_buckets([_mk("SPG", SPG, 1.31)])
    assert Bucket.MOMENTUM_LEADERS in out
    assert out[Bucket.MOMENTUM_LEADERS] == []


_pct = st.floats(min_value=0.0, max_value=1.0)
_profile = st.fixed_dictionaries(
    {f: _pct for f in ("quality", "value", "revision", "momentum", "lowvol")}
)
_cand = st.builds(
    BucketInput,
    ticker=st.text(min_size=1, max_size=5, alphabet="ABCDEFGHIJ"),
    percentiles=_profile,
    composite=st.floats(min_value=-3, max_value=3, allow_nan=False),
)


@given(cands=st.lists(_cand, max_size=30))
def test_assign_deterministic_and_total(cands):
    a = assign_buckets(list(cands))
    b = assign_buckets(list(cands))
    # all 6 buckets always present
    assert set(a.keys()) == set(PRIORITY)
    # deterministic: same input → identical ticker ordering per bucket
    for bucket in PRIORITY:
        assert [c.ticker for c in a[bucket]] == [c.ticker for c in b[bucket]]
        assert len(a[bucket]) <= MAX_PER_BUCKET
