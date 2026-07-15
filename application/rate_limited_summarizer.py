"""Rate-limited wrapper for CaseSummarizerPort.

Enforces a minimum buffer between summarize_case calls to avoid hitting
Gemini free-tier rate limits (~14 rpm = ~4.3 s minimum between calls;
default configured to 5.0 s for safety margin).

Clock and sleep are injectable for testability — no real sleeping in tests.
"""

from __future__ import annotations

import time
from typing import Callable, Protocol, runtime_checkable

from domain.case_models import CaseContext, CaseResult


@runtime_checkable
class _CaseSummarizerLike(Protocol):
    def summarize_case(self, ctx: CaseContext) -> CaseResult: ...
    def summarize_cases(self, contexts: list[CaseContext]) -> dict[str, CaseResult]: ...


class RateLimitedCaseSummarizer:
    """Wraps a CaseSummarizerPort; enforces a minimum buffer between summarize_case calls.

    Injectable clock+sleep for testability. First call never sleeps.
    """

    def __init__(
        self,
        inner: _CaseSummarizerLike,
        min_interval_s: float,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._inner = inner
        self._min_interval_s = min_interval_s
        self._clock = clock
        self._sleep = sleep
        self._last_call_time: float | None = None

    def summarize_case(self, ctx: CaseContext) -> CaseResult:
        now = self._clock()
        if self._last_call_time is not None:
            elapsed = now - self._last_call_time
            remainder = self._min_interval_s - elapsed
            if remainder > 0:
                self._sleep(remainder)
        self._last_call_time = self._clock()
        return self._inner.summarize_case(ctx)

    def summarize_cases(self, contexts: list[CaseContext]) -> dict[str, CaseResult]:
        """Batched variant — throttles once for the whole call, not once per
        ticker (per-ticker throttling would defeat batching's purpose)."""
        now = self._clock()
        if self._last_call_time is not None:
            elapsed = now - self._last_call_time
            remainder = self._min_interval_s - elapsed
            if remainder > 0:
                self._sleep(remainder)
        self._last_call_time = self._clock()
        return self._inner.summarize_cases(contexts)
