"""Tests for compact opportunity card HTML component."""

from __future__ import annotations

from datetime import datetime

from adapters.visualization.components.compact_card import render_compact_card_html
from domain.conviction import ActionType, ConvictionScore, OpportunityCard


def _make_card(
    ticker: str, conviction: float, action: ActionType = ActionType.BUY
) -> OpportunityCard:
    now = datetime(2026, 6, 3, 10, 0, 0)
    score = ConvictionScore(
        ticker=ticker,
        score=conviction,
        sub_scores={"sentiment": 0.8},
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


class TestRenderCompactCardHtml:
    def test_renders_ticker(self) -> None:
        card = _make_card("AAPL", 8.0)
        html = render_compact_card_html(card, datetime(2026, 6, 3, 10, 30, 0))
        assert "AAPL" in html

    def test_renders_conviction_score(self) -> None:
        card = _make_card("NVDA", 7.5)
        html = render_compact_card_html(card, datetime(2026, 6, 3, 10, 30, 0))
        assert "7.5" in html

    def test_high_conviction_uses_high_class(self) -> None:
        card = _make_card("TSLA", 7.5)
        html = render_compact_card_html(card, datetime(2026, 6, 3, 10, 30, 0))
        assert "opp-card-high" in html

    def test_mid_conviction_uses_mid_class(self) -> None:
        card = _make_card("MSFT", 5.0)
        html = render_compact_card_html(card, datetime(2026, 6, 3, 10, 30, 0))
        assert "opp-card-mid" in html

    def test_low_conviction_uses_low_class(self) -> None:
        card = _make_card("GME", 2.5)
        html = render_compact_card_html(card, datetime(2026, 6, 3, 10, 30, 0))
        assert "opp-card-low" in html

    def test_base_opp_card_class_present(self) -> None:
        card = _make_card("AAPL", 8.0)
        html = render_compact_card_html(card, datetime(2026, 6, 3, 10, 30, 0))
        assert "opp-card" in html

    def test_action_badge_present(self) -> None:
        card = _make_card("AAPL", 8.0, ActionType.BUY)
        html = render_compact_card_html(card, datetime(2026, 6, 3, 10, 30, 0))
        assert "badge" in html
        assert "BUY" in html

    def test_sell_action_badge(self) -> None:
        card = _make_card("AAPL", 3.0, ActionType.SELL)
        html = render_compact_card_html(card, datetime(2026, 6, 3, 10, 30, 0))
        assert "SELL" in html

    def test_alert_summary_shown(self) -> None:
        card = _make_card("AAPL", 8.0)
        html = render_compact_card_html(card, datetime(2026, 6, 3, 10, 30, 0))
        assert "AAPL is showing strong signals" in html

    def test_first_two_risks_shown(self) -> None:
        card = _make_card("AAPL", 8.0)
        html = render_compact_card_html(card, datetime(2026, 6, 3, 10, 30, 0))
        assert "Earnings risk" in html
        assert "Sector rotation" in html

    def test_risks_joined_by_dot(self) -> None:
        card = _make_card("AAPL", 8.0)
        html = render_compact_card_html(card, datetime(2026, 6, 3, 10, 30, 0))
        assert " · " in html

    def test_freshness_dot_present(self) -> None:
        card = _make_card("AAPL", 8.0)
        html = render_compact_card_html(card, datetime(2026, 6, 3, 10, 30, 0))
        # Fresh signal (same time), should show fresh or recent status dot
        assert (
            "status-dot" in html
            or "badge-fresh" in html
            or "badge-recent" in html
            or "badge-stale" in html
        )

    def test_conviction_bar_present(self) -> None:
        card = _make_card("AAPL", 8.0)
        html = render_compact_card_html(card, datetime(2026, 6, 3, 10, 30, 0))
        # Conviction fill bar should be present
        assert "conviction" in html.lower() or "fill" in html.lower() or "%" in html

    def test_returns_string(self) -> None:
        card = _make_card("AAPL", 6.0)
        result = render_compact_card_html(card, datetime(2026, 6, 3, 10, 0, 0))
        assert isinstance(result, str)
        assert len(result) > 0
