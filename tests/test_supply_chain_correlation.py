import pytest

from adapters.visualization.analysis.scoring.supply_chain import compute_co_movement


def _compound(start: float, returns: list[float]) -> list[float]:
    closes = [start]
    for r in returns:
        closes.append(closes[-1] * (1 + r))
    return closes


_RETURNS = [0.02, -0.0098039, 0.0297030, -0.0096154, 0.0291262]


def test_perfectly_correlated_series_returns_one() -> None:
    closes = {
        "NVDA": _compound(100.0, _RETURNS),
        "AMD": _compound(50.0, _RETURNS),
    }
    result = compute_co_movement(closes)
    assert result == pytest.approx(1.0)


def test_perfectly_anticorrelated_series_returns_negative_one() -> None:
    closes = {
        "NVDA": _compound(100.0, _RETURNS),
        "OIL": _compound(50.0, [-r for r in _RETURNS]),
    }
    result = compute_co_movement(closes)
    assert result == pytest.approx(-1.0)


def test_single_ticker_returns_none() -> None:
    closes = {"NVDA": [100.0, 102.0, 101.0]}
    assert compute_co_movement(closes) is None


def test_empty_dict_returns_none() -> None:
    assert compute_co_movement({}) is None


def test_insufficient_history_returns_none() -> None:
    closes = {"NVDA": [100.0], "AMD": [50.0]}
    assert compute_co_movement(closes) is None


def test_flat_series_excluded_no_variance() -> None:
    closes = {
        "NVDA": [100.0, 100.0, 100.0, 100.0],
        "AMD": [50.0, 51.0, 50.5, 52.0],
    }
    assert compute_co_movement(closes) is None


def test_averages_across_three_tickers() -> None:
    closes = {
        "NVDA": _compound(100.0, _RETURNS),
        "AMD": _compound(50.0, _RETURNS),
        "OIL": _compound(50.0, [-r for r in _RETURNS]),
    }
    result = compute_co_movement(closes)
    # NVDA/AMD = +1.0, NVDA/OIL = -1.0, AMD/OIL = -1.0 -> mean = -1/3
    assert result == pytest.approx(-1 / 3)
