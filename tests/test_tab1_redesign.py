"""Tests for Tab 1 Phase 5.4 redesign — Tasks 13-20."""

from __future__ import annotations

from datetime import datetime

from adapters.visualization.components.compact_card import (
    _hold_duration_text,
    _sub_score_bars_html,
    render_compact_card_html,
)
from domain.conviction import ActionType, ConvictionScore, OpportunityCard

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_card(
    ticker: str,
    conviction: float,
    action: ActionType = ActionType.BUY,
    sub_scores: dict[str, float] | None = None,
) -> OpportunityCard:
    now = datetime(2026, 6, 4, 10, 0, 0)
    # sub_scores are on a 0-10 scale (matching ConvictionScore domain model)
    score = ConvictionScore(
        ticker=ticker,
        score=conviction,
        sub_scores=sub_scores or {"sentiment": 8.0, "technical": 6.0},
        signals_firing=3,
        freshest_signal=now,
        explanation="Test explanation",
    )
    return OpportunityCard(
        ticker=ticker,
        conviction=conviction,
        action=action,
        alert_summary=f"{ticker} is showing strong signals",
        evidence=["RSI oversold", "Positive sentiment surge"],
        suggestion="Consider entering at market open",
        risks=["Earnings risk", "Sector rotation"],
        generated_at=now,
        conviction_score=score,
    )


# ---------------------------------------------------------------------------
# Task 17: compact_card enhancements
# ---------------------------------------------------------------------------


class TestHoldDurationText:
    # sub_scores are on 0-10 scale (domain model ConvictionScore)
    def test_high_scores_returns_hold_until_flip(self) -> None:
        result = _hold_duration_text({"sentiment": 9.0, "technical": 8.5})
        assert result == "Hold until flip"

    def test_medium_scores_position_hold(self) -> None:
        result = _hold_duration_text({"sentiment": 6.0, "technical": 5.0})
        assert result == "Position hold (5-10d)"

    def test_low_scores_monitor_daily(self) -> None:
        result = _hold_duration_text({"sentiment": 1.0, "technical": 2.0})
        assert result == "Monitor daily"

    def test_empty_sub_scores_returns_monitor_daily(self) -> None:
        result = _hold_duration_text({})
        assert result == "Monitor daily"


class TestSubScoreBarsHtml:
    # sub_scores are on 0-10 scale (domain model ConvictionScore)
    def test_returns_string(self) -> None:
        html = _sub_score_bars_html({"sentiment": 8.0, "technical": 6.0})
        assert isinstance(html, str)
        assert len(html) > 0

    def test_contains_score_labels(self) -> None:
        html = _sub_score_bars_html({"sentiment": 8.0})
        assert "Sentiment" in html

    def test_empty_returns_empty_string(self) -> None:
        html = _sub_score_bars_html({})
        assert html == ""

    def test_clamps_pct_to_100(self) -> None:
        # Value > 10 should clamp bar to 100%
        html = _sub_score_bars_html({"sentiment": 15.0})
        assert "100.0%" in html


class TestEnhancedCompactCard:
    def test_hold_duration_in_html(self) -> None:
        # sub_scores on 0-10 scale
        card = _make_card("AAPL", 8.5, sub_scores={"sentiment": 9.0, "technical": 8.5})
        html = render_compact_card_html(card, datetime(2026, 6, 4, 10, 30, 0))
        assert (
            "Hold until flip" in html
            or "Position hold" in html
            or "Short hold" in html
            or "Monitor" in html
        )

    def test_sub_score_bars_rendered(self) -> None:
        # sub_scores on 0-10 scale
        card = _make_card("NVDA", 7.5, sub_scores={"sentiment": 8.0, "technical": 7.0})
        html = render_compact_card_html(card, datetime(2026, 6, 4, 10, 30, 0))
        assert "Sentiment" in html

    def test_analyze_link_present(self) -> None:
        card = _make_card("TSLA", 7.0)
        html = render_compact_card_html(card, datetime(2026, 6, 4, 10, 30, 0))
        assert "Analyze TSLA" in html

    def test_ticker_still_present(self) -> None:
        card = _make_card("MSFT", 6.0)
        html = render_compact_card_html(card, datetime(2026, 6, 4, 10, 30, 0))
        assert "MSFT" in html

    def test_conviction_bar_still_present(self) -> None:
        card = _make_card("GOOG", 5.5)
        html = render_compact_card_html(card, datetime(2026, 6, 4, 10, 30, 0))
        assert "conviction-fill" in html

    def test_action_badge_still_present(self) -> None:
        card = _make_card("AMZN", 8.0, ActionType.BUY)
        html = render_compact_card_html(card, datetime(2026, 6, 4, 10, 30, 0))
        assert "BUY" in html

    def test_risks_still_present(self) -> None:
        card = _make_card("META", 7.2)
        html = render_compact_card_html(card, datetime(2026, 6, 4, 10, 30, 0))
        assert "Earnings risk" in html


# ---------------------------------------------------------------------------
# Task 20: Importability + data loader checks
# ---------------------------------------------------------------------------


def test_command_center_importable() -> None:
    from adapters.visualization.tabs.command_center import render

    assert callable(render)


def test_compact_card_importable() -> None:
    from adapters.visualization.components.compact_card import render_compact_card_html

    assert callable(render_compact_card_html)


def test_load_recommendations_latest_returns_sorted_list() -> None:
    """load_recommendations_latest returns recs sorted by composite_score desc."""
    from adapters.visualization.data_loader import load_recommendations_latest

    recs = load_recommendations_latest("data/recommendations.db")
    if len(recs) > 1:
        scores = [r.composite_score for r in recs]
        assert scores == sorted(scores, reverse=True)


def test_load_recommendations_latest_missing_db_returns_empty() -> None:
    from adapters.visualization.data_loader import load_recommendations_latest

    recs = load_recommendations_latest("data/nonexistent_db_phase54.db")
    assert recs == []


def test_batch_fetch_prices_importable() -> None:
    from adapters.visualization.price_cache import batch_fetch_prices

    assert callable(batch_fetch_prices)


def test_fetch_index_prices_importable() -> None:
    from adapters.visualization.price_cache import fetch_index_prices

    assert callable(fetch_index_prices)


def test_rec_card_html_renders_symbol() -> None:
    """_rec_card_html renders the symbol in HTML output."""
    from adapters.visualization.tabs.command_center import _rec_card_html

    class FakeRec:
        symbol = "AAPL"
        composite_score = 0.75
        predicted_return_5d = 0.05
        confidence_5d = 0.72
        sentiment_score = 0.65
        reasoning = "Strong momentum."
        horizon_signals: dict[str, str] = {
            "2d": "bullish",
            "5d": "bullish",
            "10d": "bearish",
        }

        class grade:
            value = "buy"

    html = _rec_card_html(FakeRec())
    assert "AAPL" in html
    assert "buy" in html.lower() or "Buy" in html
