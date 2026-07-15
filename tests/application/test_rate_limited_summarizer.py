"""Tests for RateLimitedCaseSummarizer — no real sleeping, all clock/sleep injected."""

from __future__ import annotations

import pytest

from application.rate_limited_summarizer import RateLimitedCaseSummarizer
from domain.case_models import CaseContext, CasePoint, CaseResult
from domain.ports import CaseSummarizerPort

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeClock:
    """Controllable monotonic clock — advances only when told to."""

    def __init__(self, start: float = 0.0) -> None:
        self._now = start

    def __call__(self) -> float:
        return self._now

    def advance(self, delta: float) -> None:
        self._now += delta


class FakeSleep:
    """Records every sleep duration; never actually sleeps."""

    def __init__(self) -> None:
        self.calls: list[float] = []

    def __call__(self, duration: float) -> None:
        self.calls.append(duration)


class StubSummarizer:
    """Returns a fixed CaseResult for any ctx."""

    RESULT = CaseResult(
        in_favor=(CasePoint("good news", "stub"),),
        to_watch=(),
        data_gap=False,
    )

    def summarize_case(self, ctx: CaseContext) -> CaseResult:
        return self.RESULT

    def summarize_cases(self, contexts: list[CaseContext]) -> dict[str, CaseResult]:
        self.batch_calls = getattr(self, "batch_calls", 0) + 1
        return {ctx.ticker: self.RESULT for ctx in contexts}


def _ctx(ticker: str = "AAPL") -> CaseContext:
    return CaseContext(ticker=ticker, facts=("Revenue up 10%",), news=())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_throttle(
    min_interval: float = 5.0,
    clock: FakeClock | None = None,
    sleep: FakeSleep | None = None,
) -> tuple[RateLimitedCaseSummarizer, FakeClock, FakeSleep, StubSummarizer]:
    clock = clock or FakeClock()
    sleep = sleep or FakeSleep()
    inner = StubSummarizer()
    throttle = RateLimitedCaseSummarizer(
        inner=inner, min_interval_s=min_interval, clock=clock, sleep=sleep
    )
    return throttle, clock, sleep, inner


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_first_call_does_not_sleep() -> None:
    """First call must never sleep regardless of min_interval."""
    throttle, _, sleep, _ = _make_throttle(min_interval=10.0)
    throttle.summarize_case(_ctx())
    assert sleep.calls == []


def test_second_call_immediately_sleeps_full_interval() -> None:
    """If clock has not advanced since first call, second call sleeps ~min_interval."""
    throttle, clock, sleep, _ = _make_throttle(min_interval=5.0)
    throttle.summarize_case(_ctx())  # first — records timestamp at t=0
    # clock stays at 0 → elapsed = 0 → must sleep 5.0
    throttle.summarize_case(_ctx())
    assert len(sleep.calls) == 1
    assert sleep.calls[0] == pytest.approx(5.0, abs=1e-6)


def test_second_call_after_interval_elapsed_does_not_sleep() -> None:
    """If clock advanced more than min_interval, no sleep needed."""
    throttle, clock, sleep, _ = _make_throttle(min_interval=5.0)
    throttle.summarize_case(_ctx())  # first call at t=0
    clock.advance(6.0)  # > 5.0 → no sleep needed
    throttle.summarize_case(_ctx())
    assert sleep.calls == []


def test_second_call_partial_elapsed_sleeps_remainder() -> None:
    """If 2 s of 5 s has elapsed, sleep the remaining 3 s."""
    throttle, clock, sleep, _ = _make_throttle(min_interval=5.0)
    throttle.summarize_case(_ctx())  # t=0
    clock.advance(2.0)
    throttle.summarize_case(_ctx())
    assert len(sleep.calls) == 1
    assert sleep.calls[0] == pytest.approx(3.0, abs=1e-6)


def test_returns_inner_result() -> None:
    """Result must be exactly what inner.summarize_case returned."""
    throttle, _, _, inner = _make_throttle()
    result = throttle.summarize_case(_ctx())
    assert result == StubSummarizer.RESULT


def test_satisfies_case_summarizer_port() -> None:
    """isinstance check against CaseSummarizerPort must pass (runtime_checkable)."""
    throttle, _, _, _ = _make_throttle()
    assert isinstance(throttle, CaseSummarizerPort)


def test_summarize_cases_delegates_to_inner_batch_method() -> None:
    """The throttle wraps summarize_cases too — one throttled call for the
    whole batch, not one per ticker (that would defeat batching's purpose)."""
    throttle, _, sleep, inner = _make_throttle(min_interval=10.0)
    contexts = [_ctx("AAPL"), _ctx("MSFT")]

    results = throttle.summarize_cases(contexts)

    assert inner.batch_calls == 1
    assert results["AAPL"] == StubSummarizer.RESULT
    assert results["MSFT"] == StubSummarizer.RESULT
    assert sleep.calls == []  # first call never sleeps


def test_summarize_cases_and_summarize_case_share_one_throttle_clock() -> None:
    """A batch call counts as ONE throttled event — a following single-ticker
    call must still wait the full interval, proving they share timing state."""
    throttle, clock, sleep, _ = _make_throttle(min_interval=5.0)
    throttle.summarize_cases([_ctx("AAPL"), _ctx("MSFT")])  # t=0, no sleep
    throttle.summarize_case(_ctx("GOOGL"))  # clock unchanged → must sleep 5.0
    assert len(sleep.calls) == 1
    assert sleep.calls[0] == pytest.approx(5.0, abs=1e-6)
