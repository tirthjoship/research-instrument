def test_sma_basic():
    from domain.trend_rules import sma

    assert sma([1.0, 2.0, 3.0, 4.0], 2) == 3.5


def test_sma_insufficient_returns_none():
    from domain.trend_rules import sma

    assert sma([1.0, 2.0], 5) is None


def test_above_trend_true_when_price_over_sma():
    from domain.trend_rules import above_trend

    assert above_trend(105.0, 100.0) is True


def test_above_trend_false_when_sma_none():
    from domain.trend_rules import above_trend

    assert above_trend(105.0, None) is False
