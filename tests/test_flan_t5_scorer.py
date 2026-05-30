"""Tests for Flan-T5 zero-shot sentiment scorer.

CRITICAL: These tests NEVER load real model weights.
All model/tokenizer interactions are mocked.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

from adapters.ml.flan_t5_scorer import FlanT5Scorer
from domain.models import Sentiment


class TestFlanT5Scorer:
    def test_label_to_score_positive(self) -> None:
        scorer = FlanT5Scorer.__new__(FlanT5Scorer)
        assert scorer._label_to_score("positive") > 0

    def test_label_to_score_negative(self) -> None:
        scorer = FlanT5Scorer.__new__(FlanT5Scorer)
        assert scorer._label_to_score("negative") < 0

    def test_label_to_score_neutral(self) -> None:
        scorer = FlanT5Scorer.__new__(FlanT5Scorer)
        assert scorer._label_to_score("neutral") == 0.0

    def test_label_to_score_unknown(self) -> None:
        scorer = FlanT5Scorer.__new__(FlanT5Scorer)
        assert scorer._label_to_score("gibberish") == 0.0

    def test_label_to_score_label_with_extra_text(self) -> None:
        """Label string containing the keyword should still match."""
        scorer = FlanT5Scorer.__new__(FlanT5Scorer)
        assert scorer._label_to_score("the sentiment is positive") > 0
        assert scorer._label_to_score("very negative outlook") < 0

    def test_score_text_returns_sentiment(self) -> None:
        scorer = FlanT5Scorer.__new__(FlanT5Scorer)
        scorer._model = MagicMock()
        scorer._tokenizer = MagicMock()
        scorer._device = "cpu"

        mock_inputs: dict[str, MagicMock] = {
            "input_ids": MagicMock(),
            "attention_mask": MagicMock(),
        }
        mock_inputs["input_ids"].to = MagicMock(return_value=mock_inputs["input_ids"])
        mock_inputs["attention_mask"].to = MagicMock(
            return_value=mock_inputs["attention_mask"]
        )
        scorer._tokenizer.return_value = mock_inputs
        scorer._tokenizer.decode.return_value = "positive"
        scorer._model.generate.return_value = MagicMock()

        results = scorer.score_text(
            "AAPL", "Apple record revenue", datetime(2026, 5, 30), "reuters"
        )
        assert len(results) == 1
        assert isinstance(results[0], Sentiment)
        assert results[0].sentiment_score > 0
        assert results[0].source == "reuters"

    def test_score_text_negative_label(self) -> None:
        scorer = FlanT5Scorer.__new__(FlanT5Scorer)
        scorer._model = MagicMock()
        scorer._tokenizer = MagicMock()
        scorer._device = "cpu"

        mock_inputs: dict[str, MagicMock] = {
            "input_ids": MagicMock(),
            "attention_mask": MagicMock(),
        }
        mock_inputs["input_ids"].to = MagicMock(return_value=mock_inputs["input_ids"])
        mock_inputs["attention_mask"].to = MagicMock(
            return_value=mock_inputs["attention_mask"]
        )
        scorer._tokenizer.return_value = mock_inputs
        scorer._tokenizer.decode.return_value = "negative"
        scorer._model.generate.return_value = MagicMock()

        results = scorer.score_text(
            "TSLA", "Tesla misses earnings", datetime(2026, 5, 30), "bloomberg"
        )
        assert len(results) == 1
        assert results[0].sentiment_score < 0
        assert results[0].source == "bloomberg"

    def test_score_text_sets_text_snippet(self) -> None:
        scorer = FlanT5Scorer.__new__(FlanT5Scorer)
        scorer._model = MagicMock()
        scorer._tokenizer = MagicMock()
        scorer._device = "cpu"

        mock_inputs: dict[str, MagicMock] = {
            "input_ids": MagicMock(),
            "attention_mask": MagicMock(),
        }
        mock_inputs["input_ids"].to = MagicMock(return_value=mock_inputs["input_ids"])
        mock_inputs["attention_mask"].to = MagicMock(
            return_value=mock_inputs["attention_mask"]
        )
        scorer._tokenizer.return_value = mock_inputs
        scorer._tokenizer.decode.return_value = "neutral"
        scorer._model.generate.return_value = MagicMock()

        text = "Market holds steady amid mixed signals"
        results = scorer.score_text("SPY", text, datetime(2026, 5, 30), "reuters")
        assert results[0].text_snippet == text

    def test_get_sentiment_returns_empty(self) -> None:
        scorer = FlanT5Scorer.__new__(FlanT5Scorer)
        assert scorer.get_sentiment("AAPL", datetime(2026, 5, 30)) == []
