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


def test_true_range_uses_max_of_three():
    from domain.trend_rules import true_range

    assert true_range(105.0, 100.0, 101.0) == 5.0


def test_atr_averages_true_ranges():
    from domain.trend_rules import atr

    highs = [10.0, 11.0, 12.0]
    lows = [9.0, 10.0, 11.0]
    closes = [9.5, 10.5, 11.5]
    assert atr(highs, lows, closes, 3) == (1.0 + 1.5 + 1.5) / 3


def test_atr_insufficient_returns_none():
    from domain.trend_rules import atr

    assert atr([1.0], [1.0], [1.0], 5) is None


def test_chandelier_stop_below_high():
    from domain.trend_rules import chandelier_stop

    assert chandelier_stop(120.0, 4.0, 3.0) == 108.0


def test_momentum_12_1_skips_recent_month():
    from domain.trend_rules import momentum_12_1

    closes = [100.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 150.0, 999.0]
    assert abs(momentum_12_1(closes) - 0.5) < 1e-9


def test_momentum_12_1_insufficient_returns_none():
    from domain.trend_rules import momentum_12_1

    assert momentum_12_1([1.0] * 5) is None


def test_top_fraction_threshold_tercile():
    from domain.trend_rules import top_fraction_threshold

    vals = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
    assert top_fraction_threshold(vals, 1 / 3) == 0.5
