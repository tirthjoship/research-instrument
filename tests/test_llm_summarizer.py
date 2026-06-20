from adapters.ml.llm_summarizer import LLMSummarizer
from tests.fakes.corroboration_fakes import FakeModelProvider


def test_summarizer_returns_stance_and_thesis_via_first_model() -> None:
    prov = FakeModelProvider(models=["m1"], stance="bullish", thesis="durable demand")
    s = LLMSummarizer(provider=prov, preferred=["m1"])
    stance, thesis = s.summarize("NVDA strong AI demand", "NVDA")
    assert stance == "bullish" and thesis == "durable demand"
