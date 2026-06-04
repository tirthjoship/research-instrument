"""Tests for domain/conviction_service.py — TDD, written before implementation."""

from __future__ import annotations

from datetime import datetime, timedelta

from domain.conviction import ActionType, ConvictionScore, ConvictionWeights
from domain.conviction_service import (
    compute_conviction,
    compute_freshness_score,
    determine_action,
    rank_opportunities,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW = datetime(2026, 6, 3, 12, 0, 0)


def _make_score(ticker: str, score: float) -> ConvictionScore:
    return ConvictionScore(
        ticker=ticker,
        score=score,
        sub_scores={},
        signals_firing=1,
        freshest_signal=NOW,
        explanation="test",
    )


# ---------------------------------------------------------------------------
# TestFreshnessScore — 5 time buckets
# ---------------------------------------------------------------------------


class TestFreshnessScore:
    def test_under_4_hours(self) -> None:
        signal_time = NOW - timedelta(hours=2)
        assert compute_freshness_score(signal_time, NOW) == 10.0

    def test_exactly_4_hours_is_recent(self) -> None:
        signal_time = NOW - timedelta(hours=4)
        assert compute_freshness_score(signal_time, NOW) == 8.0

    def test_between_4_and_24_hours(self) -> None:
        signal_time = NOW - timedelta(hours=12)
        assert compute_freshness_score(signal_time, NOW) == 8.0

    def test_between_1_and_3_days(self) -> None:
        signal_time = NOW - timedelta(hours=36)
        assert compute_freshness_score(signal_time, NOW) == 6.0

    def test_between_3_and_7_days(self) -> None:
        signal_time = NOW - timedelta(days=5)
        assert compute_freshness_score(signal_time, NOW) == 4.0

    def test_over_7_days(self) -> None:
        signal_time = NOW - timedelta(days=10)
        assert compute_freshness_score(signal_time, NOW) == 2.0

    def test_exactly_24_hours_is_1_to_3_days(self) -> None:
        signal_time = NOW - timedelta(hours=24)
        assert compute_freshness_score(signal_time, NOW) == 6.0

    def test_exactly_7_days_is_over_7(self) -> None:
        signal_time = NOW - timedelta(days=7)
        assert compute_freshness_score(signal_time, NOW) == 2.0


# ---------------------------------------------------------------------------
# TestDetermineAction
# ---------------------------------------------------------------------------


class TestDetermineAction:
    def test_high_score_bullish_is_buy(self) -> None:
        assert determine_action(9.0, is_bullish=True) == ActionType.BUY

    def test_high_score_bearish_is_sell(self) -> None:
        assert determine_action(8.5, is_bullish=False) == ActionType.SELL

    def test_exactly_7_bullish_is_buy(self) -> None:
        assert determine_action(7.0, is_bullish=True) == ActionType.BUY

    def test_exactly_7_bearish_is_sell(self) -> None:
        assert determine_action(7.0, is_bullish=False) == ActionType.SELL

    def test_medium_score_bullish_is_watch(self) -> None:
        assert determine_action(5.0, is_bullish=True) == ActionType.WATCH

    def test_medium_score_bearish_is_watch(self) -> None:
        assert determine_action(5.0, is_bullish=False) == ActionType.WATCH

    def test_low_score_bullish_is_watch(self) -> None:
        assert determine_action(2.0, is_bullish=True) == ActionType.WATCH

    def test_low_score_bearish_is_watch(self) -> None:
        assert determine_action(1.0, is_bullish=False) == ActionType.WATCH

    def test_just_below_threshold_is_watch(self) -> None:
        assert determine_action(6.9, is_bullish=True) == ActionType.WATCH


# ---------------------------------------------------------------------------
# TestComputeConviction
# ---------------------------------------------------------------------------


class TestComputeConviction:
    def test_all_aligned_high(self) -> None:
        sub_scores = {
            "signal_agreement": 9.0,
            "smart_money": 9.0,
            "sentiment_momentum": 9.0,
            "fundamental_basis": 9.0,
            "temporal_freshness": 9.0,
            "ml_direction": 9.0,
        }
        weights = ConvictionWeights()
        result = compute_conviction(sub_scores, weights)
        assert result > 6.0
        assert 1.0 <= result <= 10.0

    def test_technical_only_low(self) -> None:
        sub_scores = {
            "signal_agreement": 2.0,
            "smart_money": 2.0,
            "sentiment_momentum": 2.0,
            "fundamental_basis": 2.0,
            "temporal_freshness": 2.0,
            "ml_direction": 2.0,
        }
        weights = ConvictionWeights()
        result = compute_conviction(sub_scores, weights)
        assert result < 4.0

    def test_custom_weights_differ(self) -> None:
        sub_scores = {
            "signal_agreement": 8.0,
            "smart_money": 2.0,
        }
        weights_heavy_signal = ConvictionWeights(signal_agreement=5.0, smart_money=1.0)
        weights_heavy_smart = ConvictionWeights(signal_agreement=1.0, smart_money=5.0)
        r1 = compute_conviction(sub_scores, weights_heavy_signal)
        r2 = compute_conviction(sub_scores, weights_heavy_smart)
        assert r1 > r2

    def test_empty_sub_scores_returns_1(self) -> None:
        result = compute_conviction({}, ConvictionWeights())
        assert result == 1.0

    def test_zero_weight_keys_ignored(self) -> None:
        sub_scores = {"signal_agreement": 8.0, "unknown_key": 9.0}
        weights = ConvictionWeights(signal_agreement=1.0)
        result = compute_conviction(sub_scores, weights)
        # Only signal_agreement contributes
        assert abs(result - 8.0) < 0.01

    def test_result_clamped_at_10(self) -> None:
        sub_scores = {"signal_agreement": 10.0}
        weights = ConvictionWeights(signal_agreement=1.0)
        assert compute_conviction(sub_scores, weights) == 10.0

    def test_result_clamped_at_1(self) -> None:
        sub_scores = {"signal_agreement": 0.0}
        weights = ConvictionWeights(signal_agreement=1.0)
        assert compute_conviction(sub_scores, weights) == 1.0


# ---------------------------------------------------------------------------
# TestRankOpportunities
# ---------------------------------------------------------------------------


class TestRankOpportunities:
    def _scores(self) -> list[ConvictionScore]:
        return [
            _make_score("AAPL", 8.0),
            _make_score("MSFT", 6.5),
            _make_score("GOOG", 5.0),
            _make_score("AMZN", 2.5),  # below min_score
            _make_score("TSLA", 9.0),
        ]

    def test_descending_order(self) -> None:
        results = rank_opportunities(self._scores())
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_min_score_filters_low(self) -> None:
        results = rank_opportunities(self._scores(), min_score=3.0)
        tickers = [r.ticker for r in results]
        assert "AMZN" not in tickers

    def test_top_n_respected(self) -> None:
        scores = [_make_score(f"T{i}", 5.0) for i in range(20)]
        results = rank_opportunities(scores, top_n=5)
        assert len(results) <= 5

    def test_pinned_always_included(self) -> None:
        results = rank_opportunities(
            self._scores(), top_n=2, pinned={"AMZN"}, min_score=3.0
        )
        tickers = [r.ticker for r in results]
        assert "AMZN" in tickers

    def test_pinned_not_duplicated(self) -> None:
        # TSLA (score=9.0) would make top_n naturally; pin it too
        results = rank_opportunities(
            self._scores(), top_n=5, pinned={"TSLA"}, min_score=3.0
        )
        assert sum(1 for r in results if r.ticker == "TSLA") == 1

    def test_empty_input(self) -> None:
        assert rank_opportunities([]) == []

    def test_all_below_min_score_empty_without_pinned(self) -> None:
        scores = [_make_score("X", 1.5)]
        assert rank_opportunities(scores, min_score=3.0) == []

    def test_pinned_appended_after_top_n(self) -> None:
        """Pinned tickers that missed cut appear at the end, not mixed in."""
        results = rank_opportunities(
            self._scores(), top_n=2, pinned={"AMZN"}, min_score=3.0
        )
        # First 2 are top scorers (TSLA=9, AAPL=8), AMZN appended last
        assert results[-1].ticker == "AMZN"


def test_rank_opportunities_returns_top_n_when_all_below_min_score():
    from datetime import datetime

    from domain.conviction import ConvictionScore
    from domain.conviction_service import rank_opportunities

    scores = [
        ConvictionScore(
            ticker=f"T{i}",
            score=2.0 + i * 0.1,
            sub_scores={},
            signals_firing=1,
            freshest_signal=datetime(2026, 6, 4),
            explanation="",
        )
        for i in range(20)
    ]
    result = rank_opportunities(scores, top_n=5, min_score=3.0)
    assert len(result) >= 5
