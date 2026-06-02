"""EventCausalFeatureEngineer — extract 8 event-causal features.

Features capture the decaying impact of classified news events on sectors.
"""

from __future__ import annotations

from datetime import datetime

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
        active_impacts: list[tuple[ClassifiedEvent, float, float]] = (
            []
        )  # event, impact, days
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
            weighted_dir = sum(e.direction * imp for e, imp, _ in active_impacts)
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
            features["event_surprise_factor"] = (
                actual_sector_return_5d - expected_impact
            )

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
