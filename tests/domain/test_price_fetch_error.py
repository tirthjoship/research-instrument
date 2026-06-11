"""tests/domain/test_price_fetch_error.py"""

import pytest

from domain.exceptions import DomainError, PriceFetchError


def test_price_fetch_error_is_domain_error() -> None:
    assert issubclass(PriceFetchError, DomainError)


def test_price_fetch_error_carries_ticker_and_cause() -> None:
    cause = ValueError("network down")
    err = PriceFetchError("AC.TO", cause=cause)
    assert err.ticker == "AC.TO"
    assert err.cause is cause
    assert "AC.TO" in str(err)


def test_price_fetch_error_raisable() -> None:
    with pytest.raises(PriceFetchError):
        raise PriceFetchError("XYZ", cause=RuntimeError("boom"))
