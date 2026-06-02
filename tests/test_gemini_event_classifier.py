"""Tests for GeminiEventClassifier — mocked, never hits real API."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from adapters.ml.gemini_event_classifier import GeminiEventClassifier
from domain.models import EventCategory


class TestClassifySingle:
    @patch("adapters.ml.gemini_event_classifier._call_gemini")
    def test_classifies_earnings(self, mock_call: MagicMock) -> None:
        mock_call.return_value = {
            "category": "earnings_surprise",
            "direction": 1,
            "confidence": 0.92,
        }
        clf = GeminiEventClassifier(api_key="fake-key")
        result = clf.classify("NVDA beats estimates by 20%", "2026-05-15")
        assert result is not None
        assert result.category == EventCategory.EARNINGS_SURPRISE
        assert result.direction == 1
        assert result.confidence == 0.92

    @patch("adapters.ml.gemini_event_classifier._call_gemini")
    def test_classifies_tariff(self, mock_call: MagicMock) -> None:
        mock_call.return_value = {
            "category": "tariff_trade",
            "direction": -1,
            "confidence": 0.85,
        }
        clf = GeminiEventClassifier(api_key="fake-key")
        result = clf.classify("US imposes 25% tariff on Chinese goods", "2026-03-01")
        assert result is not None
        assert result.category == EventCategory.TARIFF_TRADE
        assert result.direction == -1

    @patch("adapters.ml.gemini_event_classifier._call_gemini")
    def test_returns_none_on_unclassifiable(self, mock_call: MagicMock) -> None:
        mock_call.return_value = None
        clf = GeminiEventClassifier(api_key="fake-key")
        result = clf.classify("The weather is nice today", "2026-01-01")
        assert result is None

    @patch("adapters.ml.gemini_event_classifier._call_gemini")
    def test_returns_none_on_api_error(self, mock_call: MagicMock) -> None:
        mock_call.side_effect = Exception("API error")
        clf = GeminiEventClassifier(api_key="fake-key")
        result = clf.classify("Some headline", "2026-01-01")
        assert result is None


class TestClassifyBatch:
    @patch("adapters.ml.gemini_event_classifier._call_gemini")
    def test_batch_classifies(self, mock_call: MagicMock) -> None:
        mock_call.side_effect = [
            {"category": "earnings_surprise", "direction": 1, "confidence": 0.9},
            {"category": "geopolitical", "direction": -1, "confidence": 0.8},
            None,  # unclassifiable
        ]
        clf = GeminiEventClassifier(api_key="fake-key")
        results = clf.classify_batch(
            [
                ("NVDA beats estimates", "2026-05-15"),
                ("China-Taiwan tensions escalate", "2026-06-01"),
                ("Nice weather today", "2026-01-01"),
            ]
        )
        assert len(results) == 2
        assert results[0].category == EventCategory.EARNINGS_SURPRISE
        assert results[1].category == EventCategory.GEOPOLITICAL


class TestPromptConstruction:
    def test_system_prompt_contains_categories(self) -> None:
        from adapters.ml.gemini_event_classifier import _SYSTEM_PROMPT

        for cat in EventCategory:
            assert cat.value in _SYSTEM_PROMPT
