import pytest

from domain.risk_stats import adjusted_r2


def test_adjusted_r2_penalizes_parameters():
    adj = adjusted_r2(0.71, n=252, p=9)
    assert adj < 0.71
    assert adj == pytest.approx(1 - (1 - 0.71) * (252 - 1) / (252 - 9 - 1), rel=1e-9)


def test_adjusted_r2_degenerate_guards():
    assert adjusted_r2(0.5, n=5, p=9) == 0.5
    assert adjusted_r2(0.0, n=100, p=3) == 0.0
