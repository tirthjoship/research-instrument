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
