"""Tests for the wired select_case_summarizer() factory.

Verifies:
- With GEMINI_API_KEY set, returns a RateLimitedCaseSummarizer wrapping GeminiNarratorAdapter.
- Without the key, returns a TemplateCaseSummarizer (unthrottled).
- GEMINI_MIN_INTERVAL_S env var is respected (0.0 means no wait, still throttled wrapper).
"""

from __future__ import annotations

import importlib

import pytest

from application.case_builder import TemplateCaseSummarizer
from application.rate_limited_summarizer import RateLimitedCaseSummarizer


def _reload_card_loading() -> object:
    """Force re-import so env vars at test time are picked up."""
    import application.card_loading as mod

    importlib.reload(mod)
    return mod


def test_without_key_returns_template_summarizer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No GEMINI_API_KEY → TemplateCaseSummarizer (unthrottled)."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    mod = _reload_card_loading()
    result = mod.select_case_summarizer()  # type: ignore[union-attr]
    assert isinstance(result, TemplateCaseSummarizer)


def test_with_key_returns_rate_limited_summarizer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GEMINI_API_KEY set → RateLimitedCaseSummarizer wrapping GeminiNarratorAdapter."""
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-test")
    monkeypatch.setenv("GEMINI_MIN_INTERVAL_S", "0.0")  # no real waiting in tests
    mod = _reload_card_loading()
    result = mod.select_case_summarizer()  # type: ignore[union-attr]
    assert isinstance(result, RateLimitedCaseSummarizer)


def test_env_override_sets_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    """GEMINI_MIN_INTERVAL_S env var is wired into the RateLimitedCaseSummarizer."""
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    monkeypatch.setenv("GEMINI_MIN_INTERVAL_S", "2.5")
    mod = _reload_card_loading()
    result = mod.select_case_summarizer()  # type: ignore[union-attr]
    assert isinstance(result, RateLimitedCaseSummarizer)
    assert result._min_interval_s == pytest.approx(2.5)
