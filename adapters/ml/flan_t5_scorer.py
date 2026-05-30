"""Flan-T5 zero-shot sentiment scorer with MPS/CUDA/CPU auto-detection.

Uses google/flan-t5-base (250M params) locally for financial news sentiment
classification. Runs in parallel with the keyword scorer (ADR-008).

Device priority: MPS (Apple Silicon) > CUDA > CPU.
"""

from __future__ import annotations

from datetime import datetime

from domain.models import Sentiment

_MODEL_ID = "google/flan-t5-base"

_LABEL_SCORES: dict[str, float] = {
    "positive": 0.8,
    "negative": -0.8,
    "neutral": 0.0,
}

_PROMPT_TEMPLATE = (
    "Classify the sentiment of this financial news about {ticker} as positive, "
    "negative, or neutral: {text}"
)


class FlanT5Scorer:
    """Zero-shot sentiment scorer backed by Flan-T5.

    Attributes:
        _model: Seq2Seq model (loaded on __init__).
        _tokenizer: Matching tokenizer.
        _device: Resolved torch device string.
    """

    def __init__(self) -> None:  # pragma: no cover
        import torch  # lazy import — keep torch out of module-level for test isolation
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        if torch.backends.mps.is_available():
            self._device = "mps"
        elif torch.cuda.is_available():
            self._device = "cuda"
        else:
            self._device = "cpu"

        self._tokenizer = AutoTokenizer.from_pretrained(_MODEL_ID)
        self._model = AutoModelForSeq2SeqLM.from_pretrained(_MODEL_ID).to(self._device)
        self._model.eval()

    @staticmethod
    def _label_to_score(label: str) -> float:
        """Map a decoded label string to a sentiment score.

        Checks whether any known key is *contained in* the label string so that
        verbose outputs like "the sentiment is positive" still match.

        Args:
            label: Raw decoded string from model output.

        Returns:
            Score in [-1, 1]. Defaults to 0.0 for unknown labels.
        """
        label_lower = label.lower()
        for key, score in _LABEL_SCORES.items():
            if key in label_lower:
                return score
        return 0.0

    def score_text(
        self,
        ticker: str,
        text: str,
        timestamp: datetime,
        source: str,
    ) -> list[Sentiment]:
        """Run zero-shot classification on a single text snippet.

        Args:
            ticker: Stock ticker symbol (e.g. "AAPL").
            text: Raw news or social post text.
            timestamp: Publication time (must be <= prediction_time at call site).
            source: Source identifier (e.g. "reuters").

        Returns:
            A single-element list containing the resulting Sentiment object.
        """
        prompt = _PROMPT_TEMPLATE.format(ticker=ticker, text=text)
        inputs = self._tokenizer(
            prompt, return_tensors="pt", truncation=True, max_length=512
        )
        input_ids = inputs["input_ids"].to(self._device)
        attention_mask = inputs["attention_mask"].to(self._device)

        output_ids = self._model.generate(
            input_ids=input_ids, attention_mask=attention_mask, max_new_tokens=8
        )
        label: str = str(
            self._tokenizer.decode(output_ids[0], skip_special_tokens=True)
        )
        score = self._label_to_score(label)

        sentiment = Sentiment(
            source=source,
            timestamp=timestamp,
            sentiment_score=score,
            confidence=0.7,
            text_snippet=text,
        )
        return [sentiment]

    def get_sentiment(
        self,
        symbol: str,
        prediction_time: datetime,
        **kwargs: object,
    ) -> list[Sentiment]:
        """SentimentPort stub — not yet wired to a live data source.

        Returns an empty list until an RSS/news adapter is connected.

        Args:
            symbol: Stock ticker.
            prediction_time: Point-in-time cutoff.
            **kwargs: Ignored extra arguments.

        Returns:
            Empty list.
        """
        return []
