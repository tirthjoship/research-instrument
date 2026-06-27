"""Tests for application.corroboration_readout — all pure, no network."""

from __future__ import annotations

from application.corroboration_readout import (
    assemble_readout,
    factor_percentile_from_screen,
    trend_health_band,
)
from domain.corroboration_models import OurReadout, TrendHealth

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_screen(*tickers_and_percentiles: tuple[str, list[float]]) -> dict:  # type: ignore[type-arg]
    """Build a minimal screen dict mirroring the real screen_<date>.json shape.

    Each entry is (ticker, [percentile_per_factor]) where each percentile is a
    0-1 fraction (matching the serialisation in screen_commands.py).
    """
    factor_names = ["momentum", "revision", "quality", "value", "lowvol"]
    candidates = []
    for ticker, percs in tickers_and_percentiles:
        factor_scores = [
            {
                "name": factor_names[i],
                "value": 0.5,
                "percentile": p,
                "contribution": 0.1,
            }
            for i, p in enumerate(percs)
        ]
        candidates.append({"ticker": ticker, "factor_scores": factor_scores})
    return {
        "as_of": "2026-06-20",
        "universe_size": len(tickers_and_percentiles),
        "top_n": 10,
        "regime": "NEUTRAL",
        "abstained": False,
        "diagnostics": None,
        "candidates": candidates,
    }


# ---------------------------------------------------------------------------
# trend_health_band
# ---------------------------------------------------------------------------


class TestTrendHealthBand:
    def test_none_returns_none(self) -> None:
        assert trend_health_band(None) is None

    def test_zero_is_healthy(self) -> None:
        assert trend_health_band(0.0) == TrendHealth.HEALTHY

    def test_positive_is_healthy(self) -> None:
        assert trend_health_band(1.5) == TrendHealth.HEALTHY

    def test_large_positive_is_healthy(self) -> None:
        assert trend_health_band(10.0) == TrendHealth.HEALTHY

    def test_small_negative_is_caution(self) -> None:
        assert trend_health_band(-0.5) == TrendHealth.CAUTION

    def test_minus_two_boundary_is_caution(self) -> None:
        # th == -2.0 is exactly on the CAUTION side (BROKEN requires th < -2.0)
        assert trend_health_band(-2.0) == TrendHealth.CAUTION

    def test_below_minus_two_is_broken(self) -> None:
        assert trend_health_band(-2.5) == TrendHealth.BROKEN

    def test_very_negative_is_broken(self) -> None:
        assert trend_health_band(-10.0) == TrendHealth.BROKEN


# ---------------------------------------------------------------------------
# factor_percentile_from_screen
# ---------------------------------------------------------------------------


class TestFactorPercentileFromScreen:
    def test_screen_none_returns_none(self) -> None:
        assert factor_percentile_from_screen("AAPL", None) is None

    def test_ticker_absent_returns_none(self) -> None:
        screen = _make_screen(("MSFT", [0.6, 0.7, 0.8, 0.5, 0.4]))
        assert factor_percentile_from_screen("AAPL", screen) is None

    def test_ticker_present_returns_mean_times_100(self) -> None:
        # 5 factors at 0.6, 0.7, 0.8, 0.5, 0.4 → mean = 0.6 → 60.0
        screen = _make_screen(("AAPL", [0.6, 0.7, 0.8, 0.5, 0.4]))
        result = factor_percentile_from_screen("AAPL", screen)
        assert result is not None
        assert abs(result - 60.0) < 1e-9

    def test_returns_correct_ticker_when_multiple(self) -> None:
        # AAPL at mean=0.5 (50), MSFT at mean=1.0 (100)
        screen = _make_screen(
            ("AAPL", [0.5, 0.5, 0.5, 0.5, 0.5]),
            ("MSFT", [1.0, 1.0, 1.0, 1.0, 1.0]),
        )
        assert abs(factor_percentile_from_screen("AAPL", screen) - 50.0) < 1e-9  # type: ignore[operator]
        assert abs(factor_percentile_from_screen("MSFT", screen) - 100.0) < 1e-9  # type: ignore[operator]

    def test_malformed_screen_returns_none(self) -> None:
        # candidates not a list
        assert factor_percentile_from_screen("AAPL", {"candidates": "bad"}) is None

    def test_malformed_candidate_dict_returns_none(self) -> None:
        # candidate is a string, not a dict
        screen: dict = {"candidates": ["not-a-dict"]}  # type: ignore[type-arg]
        assert factor_percentile_from_screen("AAPL", screen) is None

    def test_missing_factor_scores_returns_none(self) -> None:
        screen: dict = {"candidates": [{"ticker": "AAPL"}]}  # type: ignore[type-arg]
        assert factor_percentile_from_screen("AAPL", screen) is None

    def test_empty_factor_scores_returns_none(self) -> None:
        screen: dict = {"candidates": [{"ticker": "AAPL", "factor_scores": []}]}  # type: ignore[type-arg]
        assert factor_percentile_from_screen("AAPL", screen) is None

    def test_non_numeric_percentile_skipped(self) -> None:
        # One valid entry, one with a string percentile → uses only numeric ones
        screen: dict = {  # type: ignore[type-arg]
            "candidates": [
                {
                    "ticker": "AAPL",
                    "factor_scores": [
                        {"name": "momentum", "percentile": 0.8},
                        {"name": "revision", "percentile": "bad"},
                    ],
                }
            ]
        }
        result = factor_percentile_from_screen("AAPL", screen)
        # Only 0.8 is numeric → 0.8 * 100 = 80.0
        assert result is not None
        assert abs(result - 80.0) < 1e-9

    def test_single_factor_score(self) -> None:
        screen: dict = {  # type: ignore[type-arg]
            "candidates": [
                {
                    "ticker": "NVDA",
                    "factor_scores": [{"name": "momentum", "percentile": 0.95}],
                }
            ]
        }
        result = factor_percentile_from_screen("NVDA", screen)
        assert result is not None
        assert abs(result - 95.0) < 1e-9


# ---------------------------------------------------------------------------
# assemble_readout
# ---------------------------------------------------------------------------


class TestAssembleReadout:
    def test_all_nones_passes_through(self) -> None:
        result = assemble_readout(
            "AAPL",
            trend_health_float=None,
            screen=None,
            divergence_flag=False,
            discipline_flag=None,
        )
        assert result == OurReadout(
            factor_percentile=None,
            trend_health=None,
            divergence_flag=False,
            discipline_flag=None,
        )

    def test_wires_trend_health(self) -> None:
        result = assemble_readout(
            "AAPL",
            trend_health_float=1.0,
            screen=None,
            divergence_flag=False,
            discipline_flag=None,
        )
        assert result.trend_health == TrendHealth.HEALTHY

    def test_wires_factor_percentile(self) -> None:
        screen = _make_screen(("AAPL", [0.8, 0.8, 0.8, 0.8, 0.8]))
        result = assemble_readout(
            "AAPL",
            trend_health_float=None,
            screen=screen,
            divergence_flag=False,
            discipline_flag=None,
        )
        assert result.factor_percentile is not None
        assert abs(result.factor_percentile - 80.0) < 1e-9

    def test_wires_divergence_flag(self) -> None:
        result = assemble_readout(
            "TSLA",
            trend_health_float=0.0,
            screen=None,
            divergence_flag=True,
            discipline_flag=None,
        )
        assert result.divergence_flag is True

    def test_wires_discipline_flag(self) -> None:
        result = assemble_readout(
            "MSFT",
            trend_health_float=-0.5,
            screen=None,
            divergence_flag=False,
            discipline_flag="REDUCE",
        )
        assert result.discipline_flag == "REDUCE"
        assert result.trend_health == TrendHealth.CAUTION

    def test_full_wiring(self) -> None:
        screen = _make_screen(("GOOG", [0.5, 0.6, 0.7, 0.4, 0.3]))
        result = assemble_readout(
            "GOOG",
            trend_health_float=-2.5,
            screen=screen,
            divergence_flag=True,
            discipline_flag="HOLD",
        )
        expected_pct = (0.5 + 0.6 + 0.7 + 0.4 + 0.3) / 5.0 * 100.0
        assert result.trend_health == TrendHealth.BROKEN
        assert result.factor_percentile is not None
        assert abs(result.factor_percentile - expected_pct) < 1e-9
        assert result.divergence_flag is True
        assert result.discipline_flag == "HOLD"
