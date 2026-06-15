from domain.screen_buckets import (
    PRIORITY,
    TOP_QUARTILE,
    Bucket,
    BucketInput,
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
