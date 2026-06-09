"""Pure screen ranking + eligibility (stdlib only)."""

from domain.screen_models import ScreenCandidate


def eligible(trend_health: float, has_min_history: bool) -> bool:
    """Screen + ride: only confirmed-uptrend names with enough history."""
    return has_min_history and trend_health > 0.0


def rank_universe(
    candidates: list[ScreenCandidate], top_n: int = 10
) -> list[ScreenCandidate]:
    ranked = sorted(candidates, key=lambda c: c.composite, reverse=True)
    return ranked[:top_n]


def abstain_if_thin(present_factor_fraction: float, threshold: float = 0.5) -> bool:
    """Flag the whole result research-only when factor coverage is poor."""
    return present_factor_fraction < threshold
