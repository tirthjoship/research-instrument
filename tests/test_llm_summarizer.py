from adapters.ml.llm_summarizer import LLMSummarizer
from tests.fakes.corroboration_fakes import FakeModelProvider


def test_summarizer_returns_stance_and_thesis_via_first_model() -> None:
    prov = FakeModelProvider(models=["m1"], stance="bullish", thesis="durable demand")
    s = LLMSummarizer(provider=prov, preferred=["m1"])
    stance, thesis = s.summarize("NVDA strong AI demand", "NVDA")
    assert stance == "bullish" and thesis == "durable demand"


class _FlakyProvider:
    """Raises for every model except the last one, to exercise the fallback loop."""

    def __init__(self, good_model: str) -> None:
        self._good = good_model

    def list_free_models(self) -> list[str]:
        return [self._good]

    def summarize(self, model: str, page_text: str, ticker: str) -> tuple[str, str]:
        if model != self._good:
            raise RuntimeError("model unavailable")
        return "bearish", "from fallback model"


def test_summarizer_falls_through_to_next_model_on_error() -> None:
    s = LLMSummarizer(provider=_FlakyProvider("m2"), preferred=["m1", "m2"])
    assert s.summarize("text", "NVDA") == ("bearish", "from fallback model")


def test_summarizer_returns_neutral_when_all_models_fail() -> None:
    s = LLMSummarizer(provider=_FlakyProvider("only-good"), preferred=["m1", "m2"])
    assert s.summarize("text", "NVDA") == ("neutral", "")
