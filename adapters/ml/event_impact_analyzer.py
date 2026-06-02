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

    def get_affected_sectors(self, category: EventCategory) -> list[dict[str, Any]]:
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

    def compute_decay(self, impact: EventSectorImpact, days_since_event: int) -> float:
        """Compute decayed impact: magnitude × 0.5^(days / half_life)."""
        return float(
            impact.magnitude * (0.5 ** (days_since_event / impact.half_life_days))
        )

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
