from domain.factor_scores import winsorize, zscore


def test_zscore_centers_and_scales():
    out = zscore([1.0, 2.0, 3.0, 4.0, 5.0])
    assert abs(sum(out)) < 1e-9
    assert abs(out[0] + out[4]) < 1e-9 and out[0] < 0 < out[4]


def test_zscore_degenerate_returns_zeros():
    assert zscore([2.0, 2.0, 2.0]) == [0.0, 0.0, 0.0]


def test_winsorize_clamps_tails():
    out = winsorize([0.0, 1, 2, 3, 100.0], p=0.2)
    assert max(out) < 100.0 and min(out) >= 0.0
