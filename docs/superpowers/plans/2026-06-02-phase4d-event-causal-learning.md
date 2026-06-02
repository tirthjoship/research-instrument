# Phase 4D: Event-Causal Learning — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Classify news events via Gemini API, build empirical impact tables with exponential decay, and extract 8 event-causal features for the ML pipeline.

**Architecture:** EventCategory enum + EventSectorImpact domain models → EventClassifierPort protocol → GeminiEventClassifier adapter (free tier, structured output) → EventImpactAnalyzer (learns magnitude + half-life per category×sector from GDELT history) → EventCausalFeatureEngineer (8 features). All optional, backward compatible.

**Tech Stack:** Python 3.12, google-generativeai (Gemini free tier), numpy, existing GDELT adapter + yfinance adapter.

**Branch:** `feat/phase-4d-event-causal-learning`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `domain/models.py` | Add EventCategory enum, ClassifiedEvent dataclass, EventSectorImpact dataclass |
| `domain/ports.py` | Add EventClassifierPort protocol |
| `adapters/ml/gemini_event_classifier.py` | Gemini API event classification (structured output) |
| `adapters/ml/event_impact_analyzer.py` | Learn impact magnitude + half-life from historical data |
| `adapters/ml/event_causal_features.py` | Extract 8 event-causal features |
| `config/events/sector_mapping.yaml` | Event category → affected sectors mapping |
| `tests/fakes/fake_event_classifier.py` | FakeEventClassifier test double |
| `tests/test_event_models.py` | Domain model tests |
| `tests/test_event_impact_analyzer.py` | Impact analyzer unit tests |
| `tests/test_event_causal_features.py` | Feature engineer unit tests |
| `tests/test_event_integration.py` | End-to-end integration test |

---

### Task 1: Domain Models (EventCategory + ClassifiedEvent + EventSectorImpact)

**Files:**
- Modify: `domain/models.py`
- Create: `tests/test_event_models.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for event-causal domain models."""

from __future__ import annotations

import pytest

from domain.models import ClassifiedEvent, EventCategory, EventSectorImpact


class TestEventCategory:
    def test_all_categories_exist(self) -> None:
        expected = {
            "earnings_surprise", "tariff_trade", "fda_approval",
            "interest_rate", "antitrust_regulation", "geopolitical",
            "labor_layoffs", "supply_chain_disruption", "product_launch",
            "macro_data",
        }
        actual = {e.value for e in EventCategory}
        assert actual == expected

    def test_count(self) -> None:
        assert len(EventCategory) == 10


class TestClassifiedEvent:
    def test_valid_creation(self) -> None:
        e = ClassifiedEvent(
            headline="NVDA beats estimates by 20%",
            event_date="2026-05-15",
            category=EventCategory.EARNINGS_SURPRISE,
            direction=1,
            confidence=0.9,
            source="gdelt",
        )
        assert e.category == EventCategory.EARNINGS_SURPRISE
        assert e.direction == 1
        assert e.confidence == 0.9

    def test_is_frozen(self) -> None:
        e = ClassifiedEvent(
            headline="test", event_date="2026-01-01",
            category=EventCategory.MACRO_DATA,
            direction=-1, confidence=0.5, source="gdelt",
        )
        with pytest.raises(Exception):
            e.confidence = 0.1  # type: ignore[misc]

    def test_rejects_invalid_direction(self) -> None:
        with pytest.raises(ValueError, match="direction"):
            ClassifiedEvent(
                headline="test", event_date="2026-01-01",
                category=EventCategory.MACRO_DATA,
                direction=2, confidence=0.5, source="gdelt",
            )

    def test_rejects_confidence_out_of_bounds(self) -> None:
        with pytest.raises(ValueError, match="confidence"):
            ClassifiedEvent(
                headline="test", event_date="2026-01-01",
                category=EventCategory.MACRO_DATA,
                direction=1, confidence=1.5, source="gdelt",
            )

    def test_neutral_direction(self) -> None:
        e = ClassifiedEvent(
            headline="Fed holds rates steady", event_date="2026-03-01",
            category=EventCategory.INTEREST_RATE,
            direction=0, confidence=0.7, source="gdelt",
        )
        assert e.direction == 0


class TestEventSectorImpact:
    def test_valid_creation(self) -> None:
        imp = EventSectorImpact(
            category=EventCategory.TARIFF_TRADE,
            sector="Energy",
            magnitude=0.023,
            half_life_days=4.5,
            sample_count=42,
        )
        assert imp.magnitude == 0.023
        assert imp.half_life_days == 4.5
        assert imp.sample_count == 42

    def test_is_frozen(self) -> None:
        imp = EventSectorImpact(
            category=EventCategory.FDA_APPROVAL,
            sector="Healthcare",
            magnitude=0.035,
            half_life_days=2.0,
            sample_count=15,
        )
        with pytest.raises(Exception):
            imp.magnitude = 0.0  # type: ignore[misc]

    def test_rejects_negative_half_life(self) -> None:
        with pytest.raises(ValueError, match="half_life_days"):
            EventSectorImpact(
                category=EventCategory.MACRO_DATA,
                sector="Financials",
                magnitude=0.01,
                half_life_days=-1.0,
                sample_count=10,
            )

    def test_rejects_negative_sample_count(self) -> None:
        with pytest.raises(ValueError, match="sample_count"):
            EventSectorImpact(
                category=EventCategory.MACRO_DATA,
                sector="Financials",
                magnitude=0.01,
                half_life_days=3.0,
                sample_count=-1,
            )
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_event_models.py -v
```

- [ ] **Step 3: Add models to domain/models.py**

Add at end of file:

```python
class EventCategory(Enum):
    """News event categories for causal impact analysis."""

    EARNINGS_SURPRISE = "earnings_surprise"
    TARIFF_TRADE = "tariff_trade"
    FDA_APPROVAL = "fda_approval"
    INTEREST_RATE = "interest_rate"
    ANTITRUST_REGULATION = "antitrust_regulation"
    GEOPOLITICAL = "geopolitical"
    LABOR_LAYOFFS = "labor_layoffs"
    SUPPLY_CHAIN_DISRUPTION = "supply_chain_disruption"
    PRODUCT_LAUNCH = "product_launch"
    MACRO_DATA = "macro_data"


@dataclass(frozen=True)
class ClassifiedEvent:
    """A news event classified into a category with direction."""

    headline: str
    event_date: str  # YYYY-MM-DD
    category: EventCategory
    direction: int  # -1, 0, 1 (bearish, neutral, bullish)
    confidence: float  # 0-1
    source: str  # "gdelt", "rss", etc.

    def __post_init__(self) -> None:
        if self.direction not in (-1, 0, 1):
            raise ValueError("direction must be -1, 0, or 1")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")


@dataclass(frozen=True)
class EventSectorImpact:
    """Learned impact of an event category on a sector."""

    category: EventCategory
    sector: str
    magnitude: float  # avg absolute return impact
    half_life_days: float  # exponential decay half-life
    sample_count: int  # number of historical events used to learn this

    def __post_init__(self) -> None:
        if self.half_life_days <= 0:
            raise ValueError("half_life_days must be positive")
        if self.sample_count < 0:
            raise ValueError("sample_count must be non-negative")
```

- [ ] **Step 4: Add EventClassifierPort to domain/ports.py**

Add `ClassifiedEvent, EventCategory` to the existing imports from `.models`, then add at end:

```python
@runtime_checkable
class EventClassifierPort(Protocol):
    """Classifies news headlines into event categories."""

    def classify(self, headline: str, date: str) -> ClassifiedEvent | None: ...

    def classify_batch(self, headlines: list[tuple[str, str]]) -> list[ClassifiedEvent]: ...
```

- [ ] **Step 5: Run tests — expect PASS**

```bash
pytest tests/test_event_models.py -v
```

- [ ] **Step 6: Commit**

```bash
git add domain/models.py domain/ports.py tests/test_event_models.py
git commit -m "feat: EventCategory enum, ClassifiedEvent, EventSectorImpact domain models + EventClassifierPort"
```

---

### Task 2: FakeEventClassifier + Event-Sector Mapping YAML

**Files:**
- Create: `tests/fakes/fake_event_classifier.py`
- Create: `config/events/sector_mapping.yaml`

- [ ] **Step 1: Create fake**

```python
"""Fake EventClassifierPort for testing."""

from __future__ import annotations

from domain.models import ClassifiedEvent, EventCategory


class FakeEventClassifier:
    """In-memory EventClassifierPort for testing."""

    def __init__(self) -> None:
        self._responses: dict[str, ClassifiedEvent] = {}

    def add_response(self, headline: str, event: ClassifiedEvent) -> None:
        self._responses[headline] = event

    def classify(self, headline: str, date: str) -> ClassifiedEvent | None:
        return self._responses.get(headline)

    def classify_batch(
        self, headlines: list[tuple[str, str]]
    ) -> list[ClassifiedEvent]:
        results: list[ClassifiedEvent] = []
        for headline, date in headlines:
            result = self.classify(headline, date)
            if result is not None:
                results.append(result)
        return results
```

- [ ] **Step 2: Create sector mapping YAML**

```bash
mkdir -p config/events
```

```yaml
# Event category → affected sectors with expected direction.
# direction: 1 = bullish, -1 = bearish, 0 = mixed/uncertain
# Used by EventImpactAnalyzer to know which sectors to measure after an event.

mappings:
  earnings_surprise:
    - sector: Technology
      direction: 1
    - sector: Healthcare
      direction: 1
    - sector: Financials
      direction: 1
    - sector: Consumer Discretionary
      direction: 1

  tariff_trade:
    - sector: Energy
      direction: 1
    - sector: Technology
      direction: -1
    - sector: Consumer Discretionary
      direction: -1
    - sector: Industrials
      direction: -1
    - sector: Materials
      direction: -1

  fda_approval:
    - sector: Healthcare
      direction: 1

  interest_rate:
    - sector: Financials
      direction: -1
    - sector: Real Estate
      direction: -1
    - sector: Utilities
      direction: -1
    - sector: Consumer Discretionary
      direction: -1

  antitrust_regulation:
    - sector: Technology
      direction: -1
    - sector: Communication Services
      direction: -1

  geopolitical:
    - sector: Energy
      direction: 1
    - sector: Technology
      direction: -1
    - sector: Industrials
      direction: -1

  labor_layoffs:
    - sector: Technology
      direction: 0
    - sector: Industrials
      direction: -1

  supply_chain_disruption:
    - sector: Technology
      direction: -1
    - sector: Industrials
      direction: -1
    - sector: Consumer Discretionary
      direction: -1

  product_launch:
    - sector: Technology
      direction: 1
    - sector: Consumer Discretionary
      direction: 1

  macro_data:
    - sector: Financials
      direction: 0
    - sector: Technology
      direction: 0
    - sector: Consumer Discretionary
      direction: 0
    - sector: Energy
      direction: 0
```

- [ ] **Step 3: Verify YAML valid**

```bash
python -c "import yaml; data = yaml.safe_load(open('config/events/sector_mapping.yaml')); print(f'{len(data[\"mappings\"])} categories mapped')"
```

- [ ] **Step 4: Run full suite**

```bash
pytest --ignore=tests/test_rss_adapter.py --tb=short -q
```

- [ ] **Step 5: Commit**

```bash
git add tests/fakes/fake_event_classifier.py config/events/sector_mapping.yaml
git commit -m "feat: FakeEventClassifier test double + event-sector mapping YAML"
```

---

### Task 3: GeminiEventClassifier Adapter

**Files:**
- Create: `adapters/ml/gemini_event_classifier.py`
- Create: `tests/test_gemini_event_classifier.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for GeminiEventClassifier — mocked, never hits real API."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from adapters.ml.gemini_event_classifier import GeminiEventClassifier
from domain.models import ClassifiedEvent, EventCategory


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
        results = clf.classify_batch([
            ("NVDA beats estimates", "2026-05-15"),
            ("China-Taiwan tensions escalate", "2026-06-01"),
            ("Nice weather today", "2026-01-01"),
        ])
        assert len(results) == 2
        assert results[0].category == EventCategory.EARNINGS_SURPRISE
        assert results[1].category == EventCategory.GEOPOLITICAL


class TestPromptConstruction:
    def test_system_prompt_contains_categories(self) -> None:
        from adapters.ml.gemini_event_classifier import _SYSTEM_PROMPT
        for cat in EventCategory:
            assert cat.value in _SYSTEM_PROMPT
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_gemini_event_classifier.py -v
```

- [ ] **Step 3: Write implementation**

```python
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
            result = _call_gemini(self._api_key, headline)
            if result is None:
                return None
            category_str = str(result.get("category", ""))
            try:
                category = EventCategory(category_str)
            except ValueError:
                logger.debug(f"Unknown category from Gemini: {category_str}")
                return None
            direction = int(result.get("direction", 0))  # type: ignore[arg-type]
            if direction not in (-1, 0, 1):
                direction = 0
            confidence = float(result.get("confidence", 0.5))  # type: ignore[arg-type]
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

    def classify_batch(
        self, headlines: list[tuple[str, str]]
    ) -> list[ClassifiedEvent]:
        """Classify multiple headlines. Skips failures."""
        results: list[ClassifiedEvent] = []
        for headline, date in headlines:
            event = self.classify(headline, date)
            if event is not None:
                results.append(event)
        return results
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
pytest tests/test_gemini_event_classifier.py -v
```

- [ ] **Step 5: Commit**

```bash
git add adapters/ml/gemini_event_classifier.py tests/test_gemini_event_classifier.py
git commit -m "feat: GeminiEventClassifier with structured output and rate limiting"
```

---

### Task 4: EventImpactAnalyzer

**Files:**
- Create: `adapters/ml/event_impact_analyzer.py`
- Create: `tests/test_event_impact_analyzer.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for EventImpactAnalyzer — learns impact magnitude + decay from historical data."""

from __future__ import annotations

import math

import pytest

from adapters.ml.event_impact_analyzer import EventImpactAnalyzer
from domain.models import ClassifiedEvent, EventCategory, EventSectorImpact


def _make_event(category: EventCategory, date: str, direction: int = 1) -> ClassifiedEvent:
    return ClassifiedEvent(
        headline="test",
        event_date=date,
        category=category,
        direction=direction,
        confidence=0.9,
        source="test",
    )


class TestLearnImpact:
    def test_learns_magnitude_from_returns(self) -> None:
        """Given events and sector returns, learns positive magnitude."""
        analyzer = EventImpactAnalyzer()
        events = [
            _make_event(EventCategory.EARNINGS_SURPRISE, "2025-01-10"),
            _make_event(EventCategory.EARNINGS_SURPRISE, "2025-03-15"),
            _make_event(EventCategory.EARNINGS_SURPRISE, "2025-06-20"),
        ]
        # Sector returns after each event: day1, day2, ... day10
        sector_returns = {
            "2025-01-10": [0.02, 0.015, 0.01, 0.005, 0.003, 0.001, 0.0, 0.0, 0.0, 0.0],
            "2025-03-15": [0.025, 0.018, 0.012, 0.006, 0.002, 0.001, 0.0, 0.0, 0.0, 0.0],
            "2025-06-20": [0.018, 0.013, 0.008, 0.004, 0.002, 0.001, 0.0, 0.0, 0.0, 0.0],
        }
        impact = analyzer.learn_impact(
            events=events,
            sector="Technology",
            sector_returns_by_date=sector_returns,
        )
        assert impact is not None
        assert impact.magnitude > 0
        assert impact.half_life_days > 0
        assert impact.sample_count == 3

    def test_learns_half_life(self) -> None:
        """Half-life should reflect decay speed."""
        analyzer = EventImpactAnalyzer()
        # Fast decay events
        fast_events = [_make_event(EventCategory.MACRO_DATA, f"2025-0{i+1}-01") for i in range(5)]
        fast_returns = {
            f"2025-0{i+1}-01": [0.02, 0.005, 0.001, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
            for i in range(5)
        }
        fast_impact = analyzer.learn_impact(fast_events, "Financials", fast_returns)
        assert fast_impact is not None
        assert fast_impact.half_life_days < 5.0

    def test_too_few_events_returns_none(self) -> None:
        """Need at least 3 events to learn impact."""
        analyzer = EventImpactAnalyzer(min_events=3)
        events = [_make_event(EventCategory.FDA_APPROVAL, "2025-01-01")]
        returns = {"2025-01-01": [0.03] * 10}
        impact = analyzer.learn_impact(events, "Healthcare", returns)
        assert impact is None

    def test_no_returns_data_returns_none(self) -> None:
        analyzer = EventImpactAnalyzer()
        events = [_make_event(EventCategory.FDA_APPROVAL, f"2025-0{i+1}-01") for i in range(5)]
        impact = analyzer.learn_impact(events, "Healthcare", {})
        assert impact is None


class TestDecayComputation:
    def test_decay_at_zero_is_full_magnitude(self) -> None:
        analyzer = EventImpactAnalyzer()
        impact = EventSectorImpact(
            category=EventCategory.TARIFF_TRADE,
            sector="Energy",
            magnitude=0.02,
            half_life_days=3.0,
            sample_count=10,
        )
        decay = analyzer.compute_decay(impact, days_since_event=0)
        assert abs(decay - 0.02) < 1e-6

    def test_decay_at_half_life_is_half(self) -> None:
        analyzer = EventImpactAnalyzer()
        impact = EventSectorImpact(
            category=EventCategory.TARIFF_TRADE,
            sector="Energy",
            magnitude=0.02,
            half_life_days=3.0,
            sample_count=10,
        )
        decay = analyzer.compute_decay(impact, days_since_event=3)
        assert abs(decay - 0.01) < 1e-6

    def test_decay_approaches_zero(self) -> None:
        analyzer = EventImpactAnalyzer()
        impact = EventSectorImpact(
            category=EventCategory.TARIFF_TRADE,
            sector="Energy",
            magnitude=0.02,
            half_life_days=3.0,
            sample_count=10,
        )
        decay = analyzer.compute_decay(impact, days_since_event=30)
        assert decay < 0.0001


class TestLoadSectorMapping:
    def test_loads_mapping_yaml(self, tmp_path) -> None:
        content = """
mappings:
  earnings_surprise:
    - sector: Technology
      direction: 1
  tariff_trade:
    - sector: Energy
      direction: 1
    - sector: Technology
      direction: -1
"""
        path = tmp_path / "mapping.yaml"
        path.write_text(content)
        analyzer = EventImpactAnalyzer(sector_mapping_path=str(path))
        mapping = analyzer.get_affected_sectors(EventCategory.TARIFF_TRADE)
        assert len(mapping) == 2
        sectors = {m["sector"] for m in mapping}
        assert "Energy" in sectors
        assert "Technology" in sectors

    def test_unknown_category_returns_empty(self, tmp_path) -> None:
        content = "mappings:\n  earnings_surprise:\n    - sector: Technology\n      direction: 1\n"
        path = tmp_path / "mapping.yaml"
        path.write_text(content)
        analyzer = EventImpactAnalyzer(sector_mapping_path=str(path))
        mapping = analyzer.get_affected_sectors(EventCategory.FDA_APPROVAL)
        assert mapping == []
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_event_impact_analyzer.py -v
```

- [ ] **Step 3: Write implementation**

```python
"""EventImpactAnalyzer — learn event impact magnitude + decay from historical data.

For each event_category × sector pair, fits:
    impact(t) = magnitude × 0.5^(t / half_life)

Uses sector ETF daily returns after classified events to estimate parameters.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import yaml
from loguru import logger

from domain.models import ClassifiedEvent, EventCategory, EventSectorImpact


class EventImpactAnalyzer:
    """Learn and query event impact parameters."""

    def __init__(
        self,
        sector_mapping_path: str = "config/events/sector_mapping.yaml",
        min_events: int = 3,
        max_decay_days: int = 10,
    ) -> None:
        self._mapping_path = sector_mapping_path
        self._min_events = min_events
        self._max_decay_days = max_decay_days
        self._impact_table: dict[tuple[str, str], EventSectorImpact] = {}
        self._sector_mapping: dict[str, list[dict[str, Any]]] | None = None

    def get_affected_sectors(
        self, category: EventCategory
    ) -> list[dict[str, Any]]:
        """Return sectors affected by this event category."""
        if self._sector_mapping is None:
            self._load_sector_mapping()
        assert self._sector_mapping is not None
        return self._sector_mapping.get(category.value, [])

    def learn_impact(
        self,
        events: list[ClassifiedEvent],
        sector: str,
        sector_returns_by_date: dict[str, list[float]],
    ) -> EventSectorImpact | None:
        """Learn magnitude + half-life from historical event→return data.

        Args:
            events: List of classified events (same category).
            sector: Sector name (e.g., "Technology").
            sector_returns_by_date: Map of event_date → list of daily sector
                returns for days 1..max_decay_days after the event.

        Returns:
            EventSectorImpact with fitted parameters, or None if insufficient data.
        """
        if len(events) < self._min_events:
            return None

        # Collect return curves for events with data
        curves: list[list[float]] = []
        for event in events:
            returns = sector_returns_by_date.get(event.event_date)
            if returns and len(returns) >= self._max_decay_days:
                curves.append(returns[: self._max_decay_days])

        if len(curves) < self._min_events:
            return None

        # Average across events to get mean decay curve
        arr = np.array(curves)
        mean_curve = np.abs(arr).mean(axis=0)

        # Fit exponential decay: magnitude and half-life
        magnitude = float(mean_curve[0])
        if magnitude <= 0:
            magnitude = 1e-6

        # Estimate half-life: find where curve drops to ~50% of initial
        half_magnitude = magnitude * 0.5
        half_life = float(self._max_decay_days)  # default
        for day_idx in range(1, len(mean_curve)):
            if mean_curve[day_idx] <= half_magnitude:
                # Linear interpolation between day_idx-1 and day_idx
                prev = float(mean_curve[day_idx - 1])
                curr = float(mean_curve[day_idx])
                if prev > curr:
                    frac = (prev - half_magnitude) / (prev - curr)
                    half_life = float(day_idx - 1) + frac
                else:
                    half_life = float(day_idx)
                break

        # Clamp half_life to reasonable range
        half_life = max(0.5, min(half_life, float(self._max_decay_days)))

        category = events[0].category
        impact = EventSectorImpact(
            category=category,
            sector=sector,
            magnitude=round(magnitude, 6),
            half_life_days=round(half_life, 2),
            sample_count=len(curves),
        )

        self._impact_table[(category.value, sector)] = impact
        return impact

    def compute_decay(
        self, impact: EventSectorImpact, days_since_event: int
    ) -> float:
        """Compute decayed impact: magnitude × 0.5^(days / half_life)."""
        return impact.magnitude * (0.5 ** (days_since_event / impact.half_life_days))

    def get_impact(
        self, category: EventCategory, sector: str
    ) -> EventSectorImpact | None:
        """Look up learned impact from table."""
        return self._impact_table.get((category.value, sector))

    def set_impact(self, impact: EventSectorImpact) -> None:
        """Manually set an impact entry (for testing or preloading)."""
        self._impact_table[(impact.category.value, impact.sector)] = impact

    def _load_sector_mapping(self) -> None:
        path = Path(self._mapping_path)
        if not path.exists():
            logger.debug(f"Sector mapping not found: {path}")
            self._sector_mapping = {}
            return
        with open(path) as f:
            data = yaml.safe_load(f)
        self._sector_mapping = data.get("mappings", {}) if data else {}
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
pytest tests/test_event_impact_analyzer.py -v
```

- [ ] **Step 5: Run full suite**

```bash
pytest --ignore=tests/test_rss_adapter.py --tb=short -q
```

- [ ] **Step 6: Commit**

```bash
git add adapters/ml/event_impact_analyzer.py tests/test_event_impact_analyzer.py
git commit -m "feat: EventImpactAnalyzer with exponential decay learning"
```

---

### Task 5: EventCausalFeatureEngineer

**Files:**
- Create: `adapters/ml/event_causal_features.py`
- Create: `tests/test_event_causal_features.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for EventCausalFeatureEngineer — 8 event-causal features."""

from __future__ import annotations

import math

import pytest

from adapters.ml.event_causal_features import (
    EVENT_CAUSAL_FEATURE_NAMES,
    EventCausalFeatureEngineer,
)
from adapters.ml.event_impact_analyzer import EventImpactAnalyzer
from domain.models import ClassifiedEvent, EventCategory, EventSectorImpact


def _make_event(
    category: EventCategory, date: str, direction: int = 1, confidence: float = 0.9
) -> ClassifiedEvent:
    return ClassifiedEvent(
        headline="test", event_date=date, category=category,
        direction=direction, confidence=confidence, source="test",
    )


def _make_impact(
    category: EventCategory, sector: str, magnitude: float = 0.02,
    half_life: float = 3.0, samples: int = 10,
) -> EventSectorImpact:
    return EventSectorImpact(
        category=category, sector=sector, magnitude=magnitude,
        half_life_days=half_life, sample_count=samples,
    )


@pytest.fixture()
def analyzer(tmp_path) -> EventImpactAnalyzer:
    content = """
mappings:
  earnings_surprise:
    - sector: Technology
      direction: 1
  tariff_trade:
    - sector: Energy
      direction: 1
    - sector: Technology
      direction: -1
"""
    path = tmp_path / "mapping.yaml"
    path.write_text(content)
    a = EventImpactAnalyzer(sector_mapping_path=str(path))
    # Pre-load impact table
    a.set_impact(_make_impact(EventCategory.EARNINGS_SURPRISE, "Technology", 0.02, 3.0))
    a.set_impact(_make_impact(EventCategory.TARIFF_TRADE, "Energy", 0.015, 5.0))
    a.set_impact(_make_impact(EventCategory.TARIFF_TRADE, "Technology", 0.01, 4.0))
    return a


@pytest.fixture()
def eng(analyzer: EventImpactAnalyzer) -> EventCausalFeatureEngineer:
    return EventCausalFeatureEngineer(impact_analyzer=analyzer)


class TestFeatureNames:
    def test_count(self) -> None:
        assert len(EVENT_CAUSAL_FEATURE_NAMES) == 8

    def test_expected_names(self) -> None:
        expected = {
            "event_impact_score", "event_impact_max",
            "event_count_7d", "event_sentiment_direction",
            "event_half_life_avg", "event_surprise_factor",
            "event_category_dominant", "event_decay_phase",
        }
        assert set(EVENT_CAUSAL_FEATURE_NAMES) == expected


class TestImpactScore:
    def test_active_event_produces_impact(self, eng: EventCausalFeatureEngineer) -> None:
        """Recent event should produce positive impact score."""
        events = [_make_event(EventCategory.EARNINGS_SURPRISE, "2026-05-28")]
        result = eng.compute(
            sector="Technology",
            current_date="2026-06-01",
            recent_events=events,
            actual_sector_return_5d=0.01,
        )
        assert result["event_impact_score"] > 0

    def test_no_events_returns_zero(self, eng: EventCausalFeatureEngineer) -> None:
        result = eng.compute(
            sector="Technology",
            current_date="2026-06-01",
            recent_events=[],
            actual_sector_return_5d=0.0,
        )
        assert result["event_impact_score"] == 0.0


class TestImpactMax:
    def test_max_picks_strongest(self, eng: EventCausalFeatureEngineer) -> None:
        """With two events, max should be the stronger one."""
        events = [
            _make_event(EventCategory.EARNINGS_SURPRISE, "2026-05-31"),  # 1 day ago, magnitude 0.02
            _make_event(EventCategory.TARIFF_TRADE, "2026-05-25"),  # 7 days ago, decayed
        ]
        result = eng.compute(
            sector="Technology",
            current_date="2026-06-01",
            recent_events=events,
            actual_sector_return_5d=0.0,
        )
        assert result["event_impact_max"] > 0


class TestEventCount:
    def test_counts_events_in_window(self, eng: EventCausalFeatureEngineer) -> None:
        events = [
            _make_event(EventCategory.EARNINGS_SURPRISE, "2026-05-28"),
            _make_event(EventCategory.TARIFF_TRADE, "2026-05-30"),
            _make_event(EventCategory.EARNINGS_SURPRISE, "2026-05-20"),  # >7d ago
        ]
        result = eng.compute(
            sector="Technology",
            current_date="2026-06-01",
            recent_events=events,
            actual_sector_return_5d=0.0,
        )
        assert result["event_count_7d"] == 2  # only 2 within 7 days


class TestSentimentDirection:
    def test_net_bullish(self, eng: EventCausalFeatureEngineer) -> None:
        events = [
            _make_event(EventCategory.EARNINGS_SURPRISE, "2026-05-30", direction=1),
            _make_event(EventCategory.EARNINGS_SURPRISE, "2026-05-29", direction=1),
        ]
        result = eng.compute(
            sector="Technology",
            current_date="2026-06-01",
            recent_events=events,
            actual_sector_return_5d=0.0,
        )
        assert result["event_sentiment_direction"] > 0


class TestSurpriseFactor:
    def test_positive_surprise(self, eng: EventCausalFeatureEngineer) -> None:
        """Actual return exceeds expected impact → positive surprise."""
        events = [_make_event(EventCategory.EARNINGS_SURPRISE, "2026-05-30")]
        result = eng.compute(
            sector="Technology",
            current_date="2026-06-01",
            recent_events=events,
            actual_sector_return_5d=0.05,  # much bigger than expected ~0.02
        )
        assert result["event_surprise_factor"] > 0


class TestGrangerLeadSignal:
    def test_no_granger_returns_zero(self, eng: EventCausalFeatureEngineer) -> None:
        result = eng.compute(
            sector="Unknown",
            current_date="2026-06-01",
            recent_events=[],
            actual_sector_return_5d=0.0,
        )
        assert result["granger_lead_signal"] == 0.0 or result["event_impact_score"] == 0.0


class TestNoImpactData:
    def test_unknown_sector_returns_zeros(self, eng: EventCausalFeatureEngineer) -> None:
        events = [_make_event(EventCategory.FDA_APPROVAL, "2026-05-30")]
        result = eng.compute(
            sector="Unknown",
            current_date="2026-06-01",
            recent_events=events,
            actual_sector_return_5d=0.0,
        )
        # No impact data for FDA_APPROVAL in Unknown sector
        assert result["event_impact_score"] == 0.0
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_event_causal_features.py -v
```

- [ ] **Step 3: Write implementation**

```python
"""EventCausalFeatureEngineer — extract 8 event-causal features.

Features capture the decaying impact of classified news events on sectors.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

from domain.models import ClassifiedEvent, EventCategory

EVENT_CAUSAL_FEATURE_NAMES: list[str] = [
    "event_impact_score",
    "event_impact_max",
    "event_count_7d",
    "event_sentiment_direction",
    "event_half_life_avg",
    "event_surprise_factor",
    "event_category_dominant",
    "event_decay_phase",
]

# Map EventCategory to numeric for event_category_dominant feature
_CATEGORY_TO_INT: dict[EventCategory, int] = {
    cat: idx + 1 for idx, cat in enumerate(EventCategory)
}


class EventCausalFeatureEngineer:
    """Extract event-causal features from classified events + impact table."""

    def __init__(self, impact_analyzer: object) -> None:
        self._analyzer = impact_analyzer

    def compute(
        self,
        sector: str,
        current_date: str,
        recent_events: list[ClassifiedEvent],
        actual_sector_return_5d: float,
    ) -> dict[str, float]:
        """Compute all 8 event-causal features."""
        current = datetime.strptime(current_date, "%Y-%m-%d")
        features: dict[str, float] = {name: 0.0 for name in EVENT_CAUSAL_FEATURE_NAMES}

        if not recent_events:
            return features

        # Compute per-event impacts
        active_impacts: list[tuple[ClassifiedEvent, float, float]] = []  # event, impact, days
        events_in_7d: list[ClassifiedEvent] = []

        for event in recent_events:
            event_dt = datetime.strptime(event.event_date, "%Y-%m-%d")
            days_since = (current - event_dt).days
            if days_since < 0:
                continue

            if days_since <= 7:
                events_in_7d.append(event)

            # Look up impact for this event's category on this sector
            impact_entry = self._analyzer.get_impact(event.category, sector)  # type: ignore[attr-defined]
            if impact_entry is None:
                continue

            decayed = self._analyzer.compute_decay(impact_entry, days_since)  # type: ignore[attr-defined]
            active_impacts.append((event, decayed, float(days_since)))

        # 1. event_impact_score — sum of all active decaying impacts
        features["event_impact_score"] = sum(imp for _, imp, _ in active_impacts)

        # 2. event_impact_max — strongest single impact
        if active_impacts:
            features["event_impact_max"] = max(imp for _, imp, _ in active_impacts)

        # 3. event_count_7d
        features["event_count_7d"] = float(len(events_in_7d))

        # 4. event_sentiment_direction — net direction weighted by impact
        if active_impacts:
            weighted_dir = sum(
                e.direction * imp for e, imp, _ in active_impacts
            )
            total_imp = sum(imp for _, imp, _ in active_impacts)
            features["event_sentiment_direction"] = (
                weighted_dir / total_imp if total_imp > 0 else 0.0
            )

        # 5. event_half_life_avg
        half_lives: list[float] = []
        for event, _, _ in active_impacts:
            impact_entry = self._analyzer.get_impact(event.category, sector)  # type: ignore[attr-defined]
            if impact_entry is not None:
                half_lives.append(impact_entry.half_life_days)
        if half_lives:
            features["event_half_life_avg"] = sum(half_lives) / len(half_lives)

        # 6. event_surprise_factor — actual return vs expected impact
        if active_impacts:
            expected_impact = features["event_impact_score"]
            features["event_surprise_factor"] = actual_sector_return_5d - expected_impact

        # 7. event_category_dominant — numeric ID of strongest event's category
        if active_impacts:
            strongest = max(active_impacts, key=lambda x: x[1])
            features["event_category_dominant"] = float(
                _CATEGORY_TO_INT.get(strongest[0].category, 0)
            )

        # 8. event_decay_phase — where strongest event is in decay (0=peak, 1=tail)
        if active_impacts:
            strongest = max(active_impacts, key=lambda x: x[1])
            impact_entry = self._analyzer.get_impact(  # type: ignore[attr-defined]
                strongest[0].category, sector
            )
            if impact_entry is not None:
                # Normalize: 0 at event day, 1 at 3× half-life (effectively expired)
                max_days = impact_entry.half_life_days * 3
                features["event_decay_phase"] = min(
                    1.0, strongest[2] / max_days if max_days > 0 else 1.0
                )

        return features
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
pytest tests/test_event_causal_features.py -v
```

- [ ] **Step 5: Run full suite**

```bash
pytest --ignore=tests/test_rss_adapter.py --tb=short -q
```

- [ ] **Step 6: Commit**

```bash
git add adapters/ml/event_causal_features.py tests/test_event_causal_features.py
git commit -m "feat: EventCausalFeatureEngineer with 8 event-causal features"
```

---

### Task 6: Wire into Pipelines + CLI

**Files:**
- Modify: `application/use_cases.py`
- Modify: `application/cli.py`

- [ ] **Step 1: Add event_causal_engineer parameter to PretrainingUseCase**

In `application/use_cases.py`, add after `cross_asset_engineer` parameter in `__init__`:

```python
        event_causal_engineer: Any | None = None,  # Phase 4D
```

Store: `self._event_causal = event_causal_engineer`

- [ ] **Step 2: Wire event-causal features in PretrainingUseCase._compute_ticker_features**

After the cross-asset features block, add:

```python
        # Phase 4D: Add event-causal features
        if self._event_causal is not None:
            # Get ticker's sector from ticker_info
            sector = ticker_info.get("sector", "") if ticker_info else ""
            if sector:
                event_features = self._event_causal.compute(
                    sector=sector,
                    current_date=prediction_time.strftime("%Y-%m-%d"),
                    recent_events=getattr(self, "_recent_events", []),
                    actual_sector_return_5d=0.0,  # not available at prediction time
                )
                features.update(event_features)
```

- [ ] **Step 3: Add event_causal_engineer to WeeklyTournamentUseCase**

Same pattern. Add parameter, store, wire in `_score_ticker` after cross-asset features.

- [ ] **Step 4: Wire in cli.py composition root**

In `_build_dependencies()`, add after cross_asset_engineer setup:

```python
    from adapters.ml.event_impact_analyzer import EventImpactAnalyzer
    from adapters.ml.event_causal_features import EventCausalFeatureEngineer

    impact_analyzer = EventImpactAnalyzer(
        sector_mapping_path=str(Path("config/events/sector_mapping.yaml"))
    )
    event_causal_engineer = EventCausalFeatureEngineer(impact_analyzer=impact_analyzer)
```

Add to return dict: `"event_causal_engineer": event_causal_engineer,`

Update all PretrainingUseCase and WeeklyTournamentUseCase instantiation sites to pass `event_causal_engineer=deps["event_causal_engineer"]`.

- [ ] **Step 5: Run full suite**

```bash
pytest --ignore=tests/test_rss_adapter.py --tb=short -q
```

- [ ] **Step 6: Commit**

```bash
git add application/use_cases.py application/cli.py
git commit -m "feat: wire EventCausalFeatureEngineer into pretraining and tournament pipelines"
```

---

### Task 7: Integration Test + CLAUDE.md + PR

**Files:**
- Create: `tests/test_event_integration.py`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Write integration test**

```python
"""Integration test: event classification → impact learning → features."""

from __future__ import annotations

import math

from adapters.ml.event_causal_features import (
    EVENT_CAUSAL_FEATURE_NAMES,
    EventCausalFeatureEngineer,
)
from adapters.ml.event_impact_analyzer import EventImpactAnalyzer
from domain.models import ClassifiedEvent, EventCategory, EventSectorImpact


def test_end_to_end_impact_to_features(tmp_path) -> None:
    """Learn impact from events, then extract features."""
    content = """
mappings:
  earnings_surprise:
    - sector: Technology
      direction: 1
"""
    path = tmp_path / "mapping.yaml"
    path.write_text(content)

    analyzer = EventImpactAnalyzer(sector_mapping_path=str(path))

    # Learn impact from historical events
    events = [
        ClassifiedEvent("NVDA beats", f"2025-0{i+1}-15", EventCategory.EARNINGS_SURPRISE, 1, 0.9, "test")
        for i in range(5)
    ]
    returns = {
        f"2025-0{i+1}-15": [0.02, 0.015, 0.01, 0.005, 0.002, 0.001, 0.0, 0.0, 0.0, 0.0]
        for i in range(5)
    }
    impact = analyzer.learn_impact(events, "Technology", returns)
    assert impact is not None
    assert impact.magnitude > 0

    # Extract features using learned impact
    eng = EventCausalFeatureEngineer(impact_analyzer=analyzer)
    recent = [
        ClassifiedEvent("AMD beats", "2026-05-30", EventCategory.EARNINGS_SURPRISE, 1, 0.85, "test")
    ]
    features = eng.compute(
        sector="Technology",
        current_date="2026-06-01",
        recent_events=recent,
        actual_sector_return_5d=0.03,
    )
    assert set(features.keys()) == set(EVENT_CAUSAL_FEATURE_NAMES)
    assert features["event_impact_score"] > 0
    assert features["event_count_7d"] == 1
    assert features["event_surprise_factor"] != 0.0


def test_no_key_collisions_with_existing_features() -> None:
    """Event feature names don't overlap with other feature layers."""
    from adapters.ml.cross_asset_features import CROSS_ASSET_FEATURE_NAMES
    from adapters.ml.feature_engineer import FeatureEngineer
    from adapters.ml.fundamental_feature_engineer import FUNDAMENTAL_FEATURE_NAMES

    fe = FeatureEngineer()
    technical = set(fe.get_feature_names())
    fundamental = set(FUNDAMENTAL_FEATURE_NAMES)
    cross_asset = set(CROSS_ASSET_FEATURE_NAMES)
    event_causal = set(EVENT_CAUSAL_FEATURE_NAMES)

    assert technical.isdisjoint(event_causal), f"Collision: {technical & event_causal}"
    assert fundamental.isdisjoint(event_causal), f"Collision: {fundamental & event_causal}"
    assert cross_asset.isdisjoint(event_causal), f"Collision: {cross_asset & event_causal}"


def test_sector_mapping_yaml_loads() -> None:
    """Full sector mapping YAML loads without error."""
    from pathlib import Path
    import yaml

    yaml_path = Path("config/events/sector_mapping.yaml")
    if not yaml_path.exists():
        pytest.skip("sector_mapping.yaml not found")

    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    mappings = data["mappings"]
    assert len(mappings) >= 10, f"Expected >= 10 categories, got {len(mappings)}"
```

- [ ] **Step 2: Run integration tests**

```bash
pytest tests/test_event_integration.py -v --tb=short
```

- [ ] **Step 3: Update CLAUDE.md**

Add after Phase 4C "Done" section:

```
**Done (Phase 4D — Event-Causal Learning 2026-06-02):**
- EventCategory enum (10 types) + ClassifiedEvent + EventSectorImpact domain models
- EventClassifierPort protocol + GeminiEventClassifier adapter (Gemini free tier, structured output)
- EventImpactAnalyzer — learns magnitude + half-life per category×sector from historical data
- EventCausalFeatureEngineer — 8 features (impact score/max, event count, sentiment direction, half-life avg, surprise factor, dominant category, decay phase)
- Event-sector mapping YAML (10 categories × affected sectors)
- Wired into pretraining and tournament pipelines (optional, backward compatible)
- Test suite — 400+ tests passing
```

- [ ] **Step 4: Run full test suite**

```bash
pytest --ignore=tests/test_rss_adapter.py --tb=short -q
```

- [ ] **Step 5: Commit**

```bash
git add tests/test_event_integration.py CLAUDE.md
git commit -m "feat: Phase 4D integration tests + CLAUDE.md update"
```

- [ ] **Step 6: Push + PR**

```bash
git push -u origin feat/phase-4d-event-causal-learning
gh pr create --title "feat: Phase 4D — event-causal learning" --base develop --body "$(cat <<'EOF'
## Summary
- **EventCategory** enum (10 types) + **ClassifiedEvent** + **EventSectorImpact** domain models
- **GeminiEventClassifier** — Gemini free tier structured output, rate-limited, fully mocked in tests
- **EventImpactAnalyzer** — learns exponential decay parameters (magnitude + half-life) per category×sector
- **EventCausalFeatureEngineer** — 8 features (impact score/max, event count, sentiment direction, half-life avg, surprise factor, dominant category, decay phase)
- **Event-sector mapping YAML** — 10 categories with affected sectors and expected directions
- Wired into PretrainingUseCase + WeeklyTournamentUseCase (optional, backward compatible)

## Test plan
- [x] 11 domain model tests (EventCategory, ClassifiedEvent, EventSectorImpact validation)
- [x] 7 GeminiEventClassifier tests (mocked API, batch, error handling)
- [x] 9 EventImpactAnalyzer tests (learning, decay computation, YAML loading)
- [x] ~10 EventCausalFeatureEngineer tests (all 8 features, edge cases)
- [x] 3 integration tests (end-to-end, key collisions, YAML loading)
- [x] Full suite passing, all pre-commit hooks green
EOF
)"
```

---

## Dependency Graph

```
Task 1 (Domain Models) → Task 2 (Fake + YAML) → Task 3 (Gemini Classifier) → Task 4 (Impact Analyzer) → Task 5 (Features) → Task 6 (Wiring) → Task 7 (Integration + PR)
```

All sequential. Each task builds on the previous.
