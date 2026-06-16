"""Build CaseContext from evidence + news; deterministic template summarizer (no network)."""

from __future__ import annotations

from application.news_context import NewsItem
from domain.case_models import CaseContext, CasePoint, CaseResult
from domain.evidence_rag import RagColor, RagSignal


def build_case_context(
    ticker: str,
    signals: tuple[RagSignal, ...] | list[RagSignal],
    news: list[NewsItem],
) -> CaseContext:
    facts = tuple(
        f"{s.dimension}: {s.detail}" for s in signals if s.color is not RagColor.GAP
    )
    news_pairs = tuple((n.source, n.title) for n in news)
    return CaseContext(ticker=ticker, facts=facts, news=news_pairs)


class TemplateCaseSummarizer:
    """Pure CaseSummarizerPort fallback — deterministic, no network, honesty-safe."""

    def summarize_case(self, ctx: CaseContext) -> CaseResult:
        favor: list[CasePoint] = []
        watch: list[CasePoint] = []
        for fact in ctx.facts:
            dim, _, detail = fact.partition(": ")
            point = CasePoint(text=f"{dim}: {detail}", source_tag=dim.lower())
            # GREEN-ish details already read positive; route by keyword heuristic is avoided —
            # the assembler that feeds us only positive/negative is the LLM; template keeps it neutral:
            (favor if _reads_favorable(detail) else watch).append(point)
        for source, title in ctx.news:
            favor.append(CasePoint(text=title, source_tag=source))
        if not favor and not watch:
            return CaseResult((), (), True)
        return CaseResult(
            in_favor=tuple(favor[:5]), to_watch=tuple(watch[:5]), data_gap=False
        )


def _reads_favorable(detail: str) -> bool:
    d = detail.lower()
    neg = ("below", "broke", "negative", "weak", "wide spread", "high", "miss", "soft")
    return not any(n in d for n in neg)
