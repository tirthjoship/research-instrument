"""Tests for run_cases_with_progress.

Verifies:
- progress callback is called once per item with increasing fraction ending at 1.0.
- the RateLimitedCaseSummarizer's sleep is invoked between pings (spacing reflected).
- n results are returned in order.
- progress=None is safe (no error).
"""

from __future__ import annotations

import pytest

from application.case_batch import run_cases_with_progress
from application.rate_limited_summarizer import RateLimitedCaseSummarizer
from domain.case_models import CaseContext, CasePoint, CaseResult

# ---------------------------------------------------------------------------
# Fakes (re-declared here to keep tests self-contained)
# ---------------------------------------------------------------------------


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self._now = start

    def __call__(self) -> float:
        return self._now

    def advance(self, delta: float) -> None:
        self._now += delta


class FakeSleep:
    def __init__(self) -> None:
        self.calls: list[float] = []

    def __call__(self, duration: float) -> None:
        self.calls.append(duration)
        # Do NOT actually sleep.


class StubInner:
    """Returns distinct CaseResults keyed by ticker so we can verify ordering."""

    def summarize_case(self, ctx: CaseContext) -> CaseResult:
        return CaseResult(
            in_favor=(CasePoint(f"fact for {ctx.ticker}", "stub"),),
            to_watch=(),
            data_gap=False,
        )


def _ctx(ticker: str) -> CaseContext:
    return CaseContext(ticker=ticker, facts=(f"{ticker} fact",), news=())


def _make_throttle(
    min_interval: float = 5.0,
) -> tuple[RateLimitedCaseSummarizer, FakeClock, FakeSleep]:
    clock = FakeClock()
    sleep = FakeSleep()
    inner = StubInner()
    throttle = RateLimitedCaseSummarizer(
        inner=inner, min_interval_s=min_interval, clock=clock, sleep=sleep
    )
    return throttle, clock, sleep


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_progress_called_n_times_with_increasing_fraction() -> None:
    """progress(fraction, i, n) called after each item; fractions increase to 1.0."""
    tickers = ["AAPL", "MSFT", "GOOG"]
    contexts = [_ctx(t) for t in tickers]
    throttle, _, _ = _make_throttle(min_interval=0.0)

    fractions: list[float] = []
    indices: list[int] = []
    totals: list[int] = []

    def on_progress(fraction: float, i: int, n: int) -> None:
        fractions.append(fraction)
        indices.append(i)
        totals.append(n)

    run_cases_with_progress(contexts, throttle, progress=on_progress)

    assert len(fractions) == 3
    assert fractions == pytest.approx([1 / 3, 2 / 3, 1.0], abs=1e-9)
    assert indices == [1, 2, 3]
    assert totals == [3, 3, 3]


def test_sleep_called_between_pings_reflecting_spacing() -> None:
    """The throttle's sleep fires between pings; verifies spacing is reflected."""
    contexts = [_ctx("A"), _ctx("B"), _ctx("C")]
    throttle, clock, sleep = _make_throttle(min_interval=5.0)
    # clock never advances → each call after the first sleeps 5.0 s
    run_cases_with_progress(contexts, throttle, progress=None)
    # 3 items → first call no sleep, 2nd and 3rd each sleep once → 2 sleeps total
    assert len(sleep.calls) == 2
    for s in sleep.calls:
        assert s == pytest.approx(5.0, abs=1e-6)


def test_returns_n_results_in_order() -> None:
    """Returns one CaseResult per context, in input order."""
    tickers = ["TSLA", "NVDA", "AMZN", "META"]
    contexts = [_ctx(t) for t in tickers]
    throttle, _, _ = _make_throttle(min_interval=0.0)

    results = run_cases_with_progress(contexts, throttle, progress=None)

    assert len(results) == 4
    for i, ticker in enumerate(tickers):
        assert results[i].in_favor[0].text == f"fact for {ticker}"


def test_empty_batch_returns_empty_list() -> None:
    """Empty input → empty output, no progress calls, no sleep."""
    throttle, _, sleep = _make_throttle()
    called: list[bool] = []
    results = run_cases_with_progress(
        [], throttle, progress=lambda f, i, n: called.append(True)
    )
    assert results == []
    assert called == []
    assert sleep.calls == []


def test_progress_none_does_not_raise() -> None:
    """progress=None is valid; must not raise."""
    throttle, _, _ = _make_throttle(min_interval=0.0)
    results = run_cases_with_progress([_ctx("AAPL")], throttle, progress=None)
    assert len(results) == 1
