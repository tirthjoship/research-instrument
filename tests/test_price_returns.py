from datetime import datetime

from application.price_returns import compute_forward_return


def test_forward_return_basic():
    series = [
        (datetime(2026, 1, 1), 100.0),
        (datetime(2026, 1, 15), 110.0),
        (datetime(2026, 2, 1), 120.0),
    ]
    # entry = last close <= 2026-01-01 -> 100; exit = first close >= entry+21d (2026-01-22) -> 2026-02-01 = 120
    assert compute_forward_return(series, datetime(2026, 1, 1), 21) == 0.2


def test_forward_return_entry_uses_last_close_on_or_before():
    series = [
        (datetime(2026, 1, 1), 100.0),
        (datetime(2026, 1, 10), 105.0),
        (datetime(2026, 2, 10), 130.0),
    ]
    # entry_date 2026-01-12 -> entry = last close <= that = 105 (Jan 10); exit >= Feb 2 -> 130
    r = compute_forward_return(series, datetime(2026, 1, 12), 21)
    assert abs(r - (130.0 - 105.0) / 105.0) < 1e-9


def test_forward_return_insufficient_data_returns_zero():
    series = [(datetime(2026, 1, 1), 100.0)]
    assert compute_forward_return(series, datetime(2026, 1, 1), 21) == 0.0


def test_forward_return_no_entry_before_date_returns_zero():
    series = [(datetime(2026, 5, 1), 100.0)]
    assert compute_forward_return(series, datetime(2026, 1, 1), 21) == 0.0
