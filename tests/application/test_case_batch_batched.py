"""Tests for run_cases_in_batches — chunks N contexts into groups of
chunk_size and makes ONE summarize_cases() call per chunk instead of one
summarize_case() call per ticker. This is the actual quota win: 60 tickers
at chunk_size=15 costs 4 API calls, not 60."""

from __future__ import annotations

import pytest

from application.case_batch import run_cases_in_batches
from domain.case_models import CaseContext, CasePoint, CaseResult


def _ctx(ticker: str) -> CaseContext:
    return CaseContext(ticker=ticker, facts=(f"{ticker} fact",), news=())


def _result(ticker: str) -> CaseResult:
    return CaseResult(
        in_favor=(CasePoint(f"fact for {ticker}", "stub"),), to_watch=(), data_gap=False
    )


class StubBatchSummarizer:
    """Returns a fixed CaseResult per ticker; records each summarize_cases call."""

    def __init__(self) -> None:
        self.batch_calls: list[list[str]] = []

    def summarize_cases(self, contexts: list[CaseContext]) -> dict[str, CaseResult]:
        self.batch_calls.append([c.ticker for c in contexts])
        return {c.ticker: _result(c.ticker) for c in contexts}


def test_chunks_into_groups_of_chunk_size() -> None:
    """22 tickers at chunk_size=15 → exactly 2 batch calls (15 + 7), not 22."""
    tickers = [f"T{i}" for i in range(22)]
    contexts = [_ctx(t) for t in tickers]
    summarizer = StubBatchSummarizer()

    run_cases_in_batches(contexts, summarizer, chunk_size=15)

    assert len(summarizer.batch_calls) == 2
    assert len(summarizer.batch_calls[0]) == 15
    assert len(summarizer.batch_calls[1]) == 7


def test_returns_n_results_in_original_order() -> None:
    tickers = ["TSLA", "NVDA", "AMZN", "META"]
    contexts = [_ctx(t) for t in tickers]
    summarizer = StubBatchSummarizer()

    results = run_cases_in_batches(contexts, summarizer, chunk_size=2)

    assert len(results) == 4
    for i, ticker in enumerate(tickers):
        assert results[i].in_favor[0].text == f"fact for {ticker}"


def test_missing_ticker_in_chunk_response_is_honest_gap() -> None:
    """If a chunk's response omits a ticker, that ticker degrades to
    data_gap=True — never silently dropped, never fabricated."""

    class _PartialSummarizer:
        def summarize_cases(self, contexts: list[CaseContext]) -> dict[str, CaseResult]:
            return {contexts[0].ticker: _result(contexts[0].ticker)}  # drops the rest

    contexts = [_ctx("AAPL"), _ctx("MSFT")]
    results = run_cases_in_batches(contexts, _PartialSummarizer(), chunk_size=15)

    assert results[0].in_favor[0].text == "fact for AAPL"
    assert results[1].data_gap is True


def test_progress_fires_once_per_context_not_once_per_chunk() -> None:
    tickers = [f"T{i}" for i in range(5)]
    contexts = [_ctx(t) for t in tickers]
    summarizer = StubBatchSummarizer()

    fractions: list[float] = []
    run_cases_in_batches(
        contexts,
        summarizer,
        chunk_size=2,
        progress=lambda f, i, n: fractions.append(f),
    )

    assert len(fractions) == 5
    assert fractions[-1] == pytest.approx(1.0)


def test_empty_batch_returns_empty_list_no_calls() -> None:
    summarizer = StubBatchSummarizer()
    assert run_cases_in_batches([], summarizer, chunk_size=15) == []
    assert summarizer.batch_calls == []


def test_default_chunk_size_is_fifteen() -> None:
    """No documented Gemini output-token cap exists in this repo — 15 is a
    conservative default chosen to bound blast radius on a malformed
    response, not derived from a hard external limit."""
    tickers = [f"T{i}" for i in range(16)]
    contexts = [_ctx(t) for t in tickers]
    summarizer = StubBatchSummarizer()

    run_cases_in_batches(contexts, summarizer)

    assert len(summarizer.batch_calls) == 2
    assert len(summarizer.batch_calls[0]) == 15
    assert len(summarizer.batch_calls[1]) == 1
