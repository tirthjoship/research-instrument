"""tests/application/test_price_returns_strict.py"""

from datetime import datetime

import pytest

import application.price_returns as pr
from domain.exceptions import PriceFetchError


def test_empty_df_returns_empty_both_modes(monkeypatch) -> None:
    # A fetch that yields no rows is NO-DATA, never an error.
    monkeypatch.setattr(pr, "_fetch_history", lambda t, s, e: [])
    start, end = datetime(2024, 1, 1), datetime(2024, 2, 1)
    assert pr.load_price_series("NEW.TO", start, end) == []
    assert pr.load_price_series("NEW.TO", start, end, strict=True) == []


def test_error_non_strict_returns_empty(monkeypatch) -> None:
    def boom(t, s, e):
        raise ConnectionError("network")

    monkeypatch.setattr(pr, "_fetch_history", boom)
    monkeypatch.setattr(pr, "_SLEEP", lambda d: None)  # no real backoff wait
    start, end = datetime(2024, 1, 1), datetime(2024, 2, 1)
    assert pr.load_price_series("AC.TO", start, end) == []  # legacy contract


def test_error_strict_raises_price_fetch_error(monkeypatch) -> None:
    def boom(t, s, e):
        raise ConnectionError("network")

    monkeypatch.setattr(pr, "_fetch_history", boom)
    monkeypatch.setattr(pr, "_SLEEP", lambda d: None)
    start, end = datetime(2024, 1, 1), datetime(2024, 2, 1)
    with pytest.raises(PriceFetchError) as ei:
        pr.load_price_series("AC.TO", start, end, strict=True)
    assert ei.value.ticker == "AC.TO"


def test_transient_then_success_retries(monkeypatch) -> None:
    calls = {"n": 0}

    def flaky(t, s, e):
        calls["n"] += 1
        if calls["n"] < 2:
            raise ConnectionError("transient")
        return [(datetime(2024, 1, 2), 10.0)]

    monkeypatch.setattr(pr, "_fetch_history", flaky)
    monkeypatch.setattr(pr, "_SLEEP", lambda d: None)
    start, end = datetime(2024, 1, 1), datetime(2024, 2, 1)
    out = pr.load_price_series("AC.TO", start, end, strict=True)
    assert out == [(datetime(2024, 1, 2), 10.0)]
    assert calls["n"] == 2  # retried once
