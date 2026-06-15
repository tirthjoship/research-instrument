from application.case_builder import TemplateCaseSummarizer, build_case_context
from application.news_context import NewsItem
from domain.evidence_rag import RagColor, RagSignal


def _signals():
    return (
        RagSignal("Technicals", RagColor.RED, "2.3 ATR below 200-day"),
        RagSignal("Valuation", RagColor.GREEN, "PEG 0.9 cheap"),
        RagSignal("Earnings", RagColor.GREEN, "EPS beat 3 of 4"),
    )


def test_build_context_carries_facts_and_news():
    ctx = build_case_context(
        "YUMC", _signals(), [NewsItem("Reuters", "Same-store sales up", "2026-06-01")]
    )
    assert ctx.ticker == "YUMC"
    assert any("PEG 0.9" in f for f in ctx.facts)
    assert ctx.news == (("Reuters", "Same-store sales up"),)


def test_template_summarizer_splits_favor_and_watch():
    ctx = build_case_context(
        "YUMC", _signals(), [NewsItem("Reuters", "Same-store sales up", "2026-06-01")]
    )
    res = TemplateCaseSummarizer().summarize_case(ctx)
    assert res.data_gap is False
    favor_text = " ".join(p.text for p in res.in_favor).lower()
    watch_text = " ".join(p.text for p in res.to_watch).lower()
    assert "valuation" in favor_text or "earnings" in favor_text
    assert "technicals" in watch_text
