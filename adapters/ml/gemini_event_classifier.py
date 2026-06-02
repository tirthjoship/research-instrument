"""GeminiEventClassifier — classify news headlines into event categories.

Uses Google Gemini free tier (15 RPM, 1.5M tokens/day) with structured output.
All API calls go through _call_gemini() which is easily mockable for testing.
"""

from __future__ import annotations

import json
import os
import time

from loguru import logger

from domain.models import ClassifiedEvent, EventCategory

_CATEGORIES_LIST = ", ".join(sorted(e.value for e in EventCategory))

_SYSTEM_PROMPT = f"""You are a financial news event classifier. Given a news headline, classify it into one of these categories:

{_CATEGORIES_LIST}

Respond with a JSON object:
{{"category": "<category>", "direction": <-1|0|1>, "confidence": <0.0-1.0>}}

- direction: 1 = bullish for affected sectors, -1 = bearish, 0 = neutral/mixed
- confidence: how certain you are about the classification
- If the headline is not a market-moving financial event, respond with null

Only respond with the JSON object or null. No explanation."""


def _call_gemini(api_key: str, headline: str) -> dict[str, object] | None:
    """Call Gemini API. Separated for easy mocking."""
    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(
            f"{_SYSTEM_PROMPT}\n\nHeadline: {headline}",
            generation_config=genai.GenerationConfig(temperature=0),
        )
        text = response.text.strip()
        if text.lower() == "null" or not text:
            return None
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            text = text.rsplit("```", 1)[0].strip()
        return json.loads(text)  # type: ignore[no-any-return]
    except Exception as exc:
        logger.debug(f"Gemini API error: {exc}")
        raise


class GeminiEventClassifier:
    """EventClassifierPort implementation using Gemini free tier."""

    def __init__(
        self,
        api_key: str | None = None,
        rate_limit_rpm: int = 14,
    ) -> None:
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self._min_interval = 60.0 / max(rate_limit_rpm, 1)
        self._last_call_time = 0.0

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_call_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call_time = time.time()

    def classify(self, headline: str, date: str) -> ClassifiedEvent | None:
        """Classify a single headline. Returns None if unclassifiable or error."""
        try:
            self._throttle()
            result = _call_gemini(self._api_key or "", headline)
            if result is None:
                return None
            category_str = str(result.get("category", ""))
            try:
                category = EventCategory(category_str)
            except ValueError:
                logger.debug(f"Unknown category from Gemini: {category_str}")
                return None
            raw_direction = result.get("direction", 0)
            direction = (
                int(raw_direction) if isinstance(raw_direction, (int, float)) else 0
            )
            if direction not in (-1, 0, 1):
                direction = 0
            raw_confidence = result.get("confidence", 0.5)
            confidence = (
                float(raw_confidence)
                if isinstance(raw_confidence, (int, float))
                else 0.5
            )
            confidence = max(0.0, min(1.0, confidence))
            return ClassifiedEvent(
                headline=headline,
                event_date=date,
                category=category,
                direction=direction,
                confidence=confidence,
                source="gemini",
            )
        except Exception as exc:
            logger.debug(f"Classification failed for '{headline[:50]}': {exc}")
            return None

    def classify_batch(self, headlines: list[tuple[str, str]]) -> list[ClassifiedEvent]:
        """Classify multiple headlines. Skips failures."""
        results: list[ClassifiedEvent] = []
        for headline, date in headlines:
            event = self.classify(headline, date)
            if event is not None:
                results.append(event)
        return results
