"""Throttle + retry/backoff for YFinanceAdapter network calls.

A ~500-ticker universe sweep must not fire all yfinance calls at once
(Yahoo 429s the whole run). The adapter centralises a min-interval throttle
plus exponential-backoff retry on YFRateLimitError so every caller inherits it.

Tests inject fake sleep/monotonic — CI never sleeps and never hits the network.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from yfinance.exceptions import YFRateLimitError

from adapters.data.yfinance_adapter import YFinanceAdapter


def _adapter(tmp: str, **kwargs: object) -> YFinanceAdapter:
    defaults: dict[str, object] = {
        "min_interval_s": 0.0,
        "backoff_base_s": 0.0,
        "jitter_s": 0.0,
        "sleep": lambda _s: None,
    }
    defaults.update(kwargs)
    return YFinanceAdapter(cache_dir=Path(tmp), **defaults)  # type: ignore[arg-type]


def test_call_with_retry_retries_on_rate_limit_then_succeeds() -> None:
    """A transient 429 is retried and the eventual success is returned."""
    calls = {"n": 0}

    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise YFRateLimitError()
        return "ok"

    with TemporaryDirectory() as tmp:
        adapter = _adapter(tmp, max_retries=3)
        result = adapter._call_with_retry("AAPL", flaky)

    assert result == "ok"
    assert calls["n"] == 3


def test_call_with_retry_reraises_after_exhausting() -> None:
    """Persistent rate-limit re-raises (never a silent empty result)."""

    def always_fail() -> str:
        raise YFRateLimitError()

    with TemporaryDirectory() as tmp:
        adapter = _adapter(tmp, max_retries=2)
        with pytest.raises(YFRateLimitError):
            adapter._call_with_retry("AAPL", always_fail)


def test_call_with_retry_throttles_min_interval() -> None:
    """Back-to-back calls sleep to honour the min interval between network hits."""
    clock = {"t": 100.0}
    sleeps: list[float] = []

    def fake_sleep(s: float) -> None:
        sleeps.append(s)
        clock["t"] += s

    def monotonic() -> float:
        return clock["t"]

    with TemporaryDirectory() as tmp:
        adapter = _adapter(
            tmp, min_interval_s=0.5, sleep=fake_sleep, monotonic=monotonic
        )
        adapter._call_with_retry("A", lambda: "x")  # first call: no prior, no wait
        adapter._call_with_retry("B", lambda: "y")  # immediate: must throttle

    assert any(abs(s - 0.5) < 1e-9 for s in sleeps), sleeps


def test_first_call_does_not_throttle() -> None:
    """The very first network call has no predecessor, so it does not sleep."""
    sleeps: list[float] = []

    with TemporaryDirectory() as tmp:
        adapter = _adapter(tmp, min_interval_s=0.5, sleep=sleeps.append)
        adapter._call_with_retry("A", lambda: "x")

    assert sleeps == []
