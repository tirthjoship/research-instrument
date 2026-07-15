"""Batch helper that spaces Gemini pings and drives a progress callback.

The summarizer's own throttle (RateLimitedCaseSummarizer) handles spacing;
this module simply iterates, collects results, and fires progress after each
completed ping so that a loading bar advances in step with the real work.
"""

from __future__ import annotations

from typing import Callable, Protocol

from domain.case_models import CaseContext, CaseResult


class _CaseSummarizerLike(Protocol):
    def summarize_case(self, ctx: CaseContext) -> CaseResult: ...


class _BatchCaseSummarizerLike(Protocol):
    def summarize_cases(self, contexts: list[CaseContext]) -> dict[str, CaseResult]: ...


def run_cases_with_progress(
    contexts: list[CaseContext],
    summarizer: _CaseSummarizerLike,
    progress: Callable[[float, int, int], None] | None = None,
) -> list[CaseResult]:
    """Summarise a batch; the summarizer's own throttle spaces the pings.

    Calls progress(fraction_done, i, n) AFTER each ticker so a loading bar
    reflects the spaced pings — the % advances per completed ping, including
    any buffer wait built into the summarizer.

    Args:
        contexts: Ordered list of CaseContext instances to summarise.
        summarizer: Any object with a summarize_case(ctx) -> CaseResult method
                    (typically a RateLimitedCaseSummarizer).
        progress: Optional callback(fraction_done, completed_count, total_count).
                  Called after each item completes. fraction_done is in (0, 1].

    Returns:
        List of CaseResult in the same order as contexts.
    """
    n = len(contexts)
    if n == 0:
        return []

    results: list[CaseResult] = []
    for i, ctx in enumerate(contexts):
        result = summarizer.summarize_case(ctx)
        results.append(result)
        if progress is not None:
            progress((i + 1) / n, i + 1, n)
    return results


# Conservative default — no output-token cap is documented anywhere in this
# repo for the Gemini models in use, so this bounds blast radius (a malformed
# response gaps out at most chunk_size tickers, not the whole batch) rather
# than being derived from a hard external limit.
_DEFAULT_CHUNK_SIZE = 15


def run_cases_in_batches(
    contexts: list[CaseContext],
    summarizer: _BatchCaseSummarizerLike,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    progress: Callable[[float, int, int], None] | None = None,
) -> list[CaseResult]:
    """Summarise a batch via summarize_cases(), chunked — ONE call per chunk
    of up to chunk_size tickers, not one call per ticker. Cuts N tickers down
    to ceil(N / chunk_size) Gemini calls (the actual daily-quota win).

    Any ticker missing from its chunk's response degrades to
    CaseResult((), (), True) — same honesty guarantee as the unbatched path,
    never fabricated, never silently dropped.

    Args:
        contexts: Ordered list of CaseContext instances to summarise.
        summarizer: Any object with a summarize_cases(contexts) -> dict[ticker,
                    CaseResult] method (typically a RateLimitedCaseSummarizer
                    wrapping GeminiNarratorAdapter).
        chunk_size: Max tickers per summarize_cases() call.
        progress: Optional callback(fraction_done, completed_count, total_count),
                  called once per context (not once per chunk) so a loading
                  bar still advances smoothly.

    Returns:
        List of CaseResult in the same order as contexts.
    """
    n = len(contexts)
    if n == 0:
        return []

    gap = CaseResult((), (), True)
    results_by_ticker: dict[str, CaseResult] = {}
    completed = 0
    for start in range(0, n, chunk_size):
        chunk = contexts[start : start + chunk_size]
        batch_results = summarizer.summarize_cases(chunk)
        for ctx in chunk:
            results_by_ticker[ctx.ticker] = batch_results.get(ctx.ticker, gap)
            completed += 1
            if progress is not None:
                progress(completed / n, completed, n)
    return [results_by_ticker[ctx.ticker] for ctx in contexts]
