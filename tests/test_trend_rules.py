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


def test_trend_health_positive_above_trend():
    from domain.trend_rules import trend_health

    assert trend_health(110.0, 100.0, 5.0) == 2.0


def test_trend_health_negative_below_trend():
    from domain.trend_rules import trend_health

    assert trend_health(90.0, 100.0, 5.0) == -2.0


def test_trend_health_none_when_inputs_missing():
    from domain.trend_rules import trend_health

    assert trend_health(100.0, None, 5.0) is None
    assert trend_health(100.0, 100.0, None) is None
    assert trend_health(100.0, 100.0, 0.0) is None


def test_ma_slope_rising():
    from domain.trend_rules import ma_slope

    vals = [float(i) for i in range(1, 21)]
    assert ma_slope(vals, 5) > 0


def test_ma_slope_none_when_insufficient():
    from domain.trend_rules import ma_slope

    assert ma_slope([1.0, 2.0, 3.0], 5) is None


def test_relative_strength_outperformer_positive():
    from domain.trend_rules import relative_strength

    asset = [100.0, 110.0, 120.0]
    bench = [100.0, 100.0, 110.0]
    assert abs(relative_strength(asset, bench, 2) - 0.10) < 1e-9


def test_relative_strength_none_when_insufficient():
    from domain.trend_rules import relative_strength

    assert relative_strength([1.0], [1.0], 5) is None


def test_trailing_volatility_constant_series_is_zero():
    from domain.trend_rules import trailing_volatility

    # flat prices → zero returns → zero vol
    assert trailing_volatility([100.0] * 14) == 0.0


def test_trailing_volatility_more_volatile_is_larger():
    from domain.trend_rules import trailing_volatility

    calm = [100, 101, 100, 101, 100, 101, 100, 101, 100, 101, 100, 101, 100, 101]
    wild = [100, 130, 90, 140, 80, 150, 70, 160, 60, 170, 50, 180, 40, 190]
    assert trailing_volatility(wild) > trailing_volatility(calm)


def test_trailing_volatility_insufficient_history_returns_none():
    from domain.trend_rules import trailing_volatility

    assert trailing_volatility([100.0, 101.0]) is None
