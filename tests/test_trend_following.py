from domain.trend_following import (
    blend_returns,
    equity_curve,
    inverse_vol_weights,
    time_series_momentum,
    turnover,
)


def test_momentum_positive_for_uptrend() -> None:
    closes = [float(100 + 5 * i) for i in range(13)]  # 13 monthly closes, rising
    assert time_series_momentum(closes) > 0


def test_momentum_negative_for_downtrend() -> None:
    closes = [float(200 - 5 * i) for i in range(13)]
    assert time_series_momentum(closes) < 0


def test_momentum_is_12m_total_return() -> None:
    closes = [10.0] * 12 + [11.0]  # 13 values; 12 months ago = 10, now = 11
    assert abs(time_series_momentum(closes) - 0.10) < 1e-9


def test_momentum_none_when_too_short() -> None:
    assert time_series_momentum([1.0] * 12) is None  # need >= 13


def test_momentum_none_when_base_nonpositive() -> None:
    closes = [0.0] + [1.0] * 12
    assert time_series_momentum(closes) is None


def test_equity_curve_compounds() -> None:
    assert equity_curve([0.1, -0.1]) == [1.0, 1.1, 1.1 * 0.9]


def test_inverse_vol_weights_sum_to_one() -> None:
    w = inverse_vol_weights({"A": 0.1, "B": 0.2, "C": 0.4})
    assert abs(sum(w.values()) - 1.0) < 1e-9


def test_inverse_vol_down_weights_high_vol() -> None:
    w = inverse_vol_weights({"LOW": 0.1, "HIGH": 0.4})
    assert w["LOW"] > w["HIGH"]  # lower vol gets more weight


def test_inverse_vol_zero_or_missing_vol_excluded() -> None:
    w = inverse_vol_weights({"A": 0.2, "BAD": 0.0})
    assert "BAD" not in w or w["BAD"] == 0.0
    assert abs(sum(w.values()) - 1.0) < 1e-9


def test_inverse_vol_all_zero_returns_empty() -> None:
    assert inverse_vol_weights({"A": 0.0, "B": 0.0}) == {}


def test_turnover_zero_for_unchanged_book() -> None:
    w = {"A": 0.5, "B": 0.5}
    assert turnover(w, w) == 0.0


def test_turnover_one_way_half_sum_abs_delta() -> None:
    prev = {"A": 1.0}
    new = {"B": 1.0}  # fully rotate A->B: |0-1|+|1-0| = 2, one-way = 1.0
    assert turnover(prev, new) == 1.0


def test_turnover_handles_cash_shrink() -> None:
    prev = {"A": 1.0}
    new = {"A": 0.5}  # half to cash: |0.5-1.0| = 0.5, one-way = 0.25
    assert turnover(prev, new) == 0.25


def test_blend_is_convex_combination() -> None:
    core = [0.10, -0.20]
    sleeve = [0.00, 0.10]
    out = blend_returns(core, sleeve, core_weight=0.8)
    assert abs(out[0] - (0.8 * 0.10 + 0.2 * 0.00)) < 1e-12
    assert abs(out[1] - (0.8 * -0.20 + 0.2 * 0.10)) < 1e-12
