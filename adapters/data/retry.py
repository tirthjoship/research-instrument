"""Stdlib retry-with-exponential-backoff. Injectable sleep so tests run with a
fake clock (no real waiting). No external dependency (project ethos: no tenacity)."""

from __future__ import annotations

import time
from typing import Callable, TypeVar

T = TypeVar("T")


def retry_with_backoff(
    fn: Callable[[], T],
    *,
    attempts: int = 3,
    base_delay: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
    retryable: tuple[type[BaseException], ...] = (Exception,),
) -> T:
    """Call fn(); on a retryable exception, wait base_delay * 2**i and retry.
    Re-raises the last exception after `attempts` tries. Sleeps BETWEEN tries
    only (never after the final failure). A non-retryable exception propagates
    immediately."""
    last_exc: BaseException | None = None
    for i in range(attempts):
        try:
            return fn()
        except retryable as exc:
            last_exc = exc
            if i < attempts - 1:
                sleep(base_delay * 2**i)
    assert last_exc is not None  # unreachable: attempts >= 1 and we caught
    raise last_exc
