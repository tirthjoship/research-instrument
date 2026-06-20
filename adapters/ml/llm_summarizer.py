"""Summarize fetched page text into (stance, attributed thesis). Model order from
ModelRegistry; falls through providers on error. Never sources a URL (spec §4)."""

from __future__ import annotations

from domain.ports import ModelProviderPort


class LLMSummarizer:
    def __init__(self, provider: ModelProviderPort, preferred: list[str]):
        self._provider = provider
        self._preferred = preferred

    def summarize(self, page_text: str, ticker: str) -> tuple[str, str]:
        for model in self._preferred:
            try:
                return self._provider.summarize(model, page_text, ticker)
            except Exception:
                continue
        return "neutral", ""
