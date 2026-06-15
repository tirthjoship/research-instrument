from domain.screen_buckets import TOP_QUARTILE, BucketInput


def test_bucketinput_holds_percentiles():
    c = BucketInput(
        ticker="SPG", percentiles={"quality": 0.95, "value": 0.87}, composite=1.31
    )
    assert c.ticker == "SPG"
    assert c.percentiles["quality"] == 0.95
    assert TOP_QUARTILE == 0.75
