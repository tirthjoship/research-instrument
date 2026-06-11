"""tests/adapters/data/test_retry.py"""

import pytest

from adapters.data.retry import retry_with_backoff


def test_returns_immediately_on_success() -> None:
    calls = []
    delays: list[float] = []
    result = retry_with_backoff(lambda: calls.append(1) or "ok", sleep=delays.append)
    assert result == "ok"
    assert len(calls) == 1
    assert delays == []  # no retry, no sleep


def test_retries_then_succeeds() -> None:
    attempts = {"n": 0}
    delays: list[float] = []

    def flaky() -> str:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise ValueError("transient")
        return "ok"

    result = retry_with_backoff(flaky, attempts=3, base_delay=1.0, sleep=delays.append)
    assert result == "ok"
    assert attempts["n"] == 3
    assert delays == [1.0, 2.0]  # exponential backoff between the 3 tries


def test_raises_last_exception_after_attempts_exhausted() -> None:
    delays: list[float] = []

    def always_fail() -> str:
        raise RuntimeError("down")

    with pytest.raises(RuntimeError, match="down"):
        retry_with_backoff(always_fail, attempts=3, base_delay=1.0, sleep=delays.append)
    assert delays == [1.0, 2.0]  # slept between tries, not after the last


def test_only_retries_listed_exceptions() -> None:
    def raises_key_error() -> str:
        raise KeyError("not retryable here")

    with pytest.raises(KeyError):
        retry_with_backoff(
            raises_key_error, attempts=3, retryable=(ValueError,), sleep=lambda d: None
        )
