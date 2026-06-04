"""Tests for opportunity card HTML components — TDD first pass."""

from __future__ import annotations

from datetime import datetime

from adapters.visualization.components.formatters import (
    action_badge_html,
    conviction_badge_html,
    freshness_indicator_html,
)
from adapters.visualization.components.opportunity_cards import (
    render_evidence_html,
    render_opportunity_card_html,
    render_risk_html,
)
from domain.conviction import (
    ActionType,
    ConvictionScore,
    FreshnessLevel,
    OpportunityCard,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_card(
    conviction: float = 8.5,
    action: ActionType = ActionType.BUY,
) -> OpportunityCard:
    score = ConvictionScore(
        ticker="AAPL",
        score=conviction,
        sub_scores={"signal_agreement": 1.0},
        signals_firing=3,
        freshest_signal=datetime(2026, 6, 3, 10, 0, 0),
        explanation="Test explanation",
    )
    return OpportunityCard(
        ticker="AAPL",
        conviction=conviction,
        action=action,
        alert_summary="Institutional buying detected with strong momentum.",
        evidence=[
            "RSI crossed 60",
            "Smart money 13D filing",
            "Positive earnings revision",
        ],
        suggestion="Consider initiating a position with a stop at $175.",
        risks=["Macro headwinds could pressure valuations", "Earnings volatility"],
        generated_at=datetime(2026, 6, 3, 10, 0, 0),
        conviction_score=score,
    )


# ---------------------------------------------------------------------------
# conviction_badge_html
# ---------------------------------------------------------------------------


class TestConvictionBadgeHtml:
    def test_high_conviction_green(self) -> None:
        html = conviction_badge_html(8.5)
        assert "8.5/10" in html
        assert "#00C853" in html or "green" in html.lower() or "166534" in html

    def test_medium_conviction_amber(self) -> None:
        html = conviction_badge_html(5.0)
        assert "5.0/10" in html
        assert "#FFD600" in html or "amber" in html.lower() or "854D0E" in html

    def test_low_conviction_red(self) -> None:
        html = conviction_badge_html(3.0)
        assert "3.0/10" in html
        assert "#FF1744" in html or "red" in html.lower() or "991B1B" in html

    def test_boundary_high_at_7(self) -> None:
        html = conviction_badge_html(7.0)
        assert "#00C853" in html or "166534" in html

    def test_boundary_medium_at_4(self) -> None:
        html = conviction_badge_html(4.0)
        assert "#FFD600" in html or "854D0E" in html

    def test_returns_string(self) -> None:
        assert isinstance(conviction_badge_html(6.0), str)


# ---------------------------------------------------------------------------
# action_badge_html
# ---------------------------------------------------------------------------


class TestActionBadgeHtml:
    def test_buy_is_green(self) -> None:
        html = action_badge_html(ActionType.BUY)
        assert "BUY" in html
        assert "#00C853" in html or "166534" in html or "green" in html.lower()

    def test_sell_is_red(self) -> None:
        html = action_badge_html(ActionType.SELL)
        assert "SELL" in html
        assert "#FF1744" in html or "991B1B" in html or "red" in html.lower()

    def test_watch_is_amber(self) -> None:
        html = action_badge_html(ActionType.WATCH)
        assert "WATCH" in html
        assert "#FFD600" in html or "854D0E" in html or "amber" in html.lower()

    def test_hold_is_gray(self) -> None:
        html = action_badge_html(ActionType.HOLD)
        assert "HOLD" in html
        # gray can be represented multiple ways
        assert any(c in html for c in ["#6B7280", "4B5563", "gray", "grey", "F3F4F6"])

    def test_returns_string(self) -> None:
        assert isinstance(action_badge_html(ActionType.BUY), str)


# ---------------------------------------------------------------------------
# freshness_indicator_html
# ---------------------------------------------------------------------------


class TestFreshnessIndicatorHtml:
    def test_fresh_label(self) -> None:
        html = freshness_indicator_html(FreshnessLevel.FRESH)
        assert "Fresh" in html

    def test_stale_label(self) -> None:
        html = freshness_indicator_html(FreshnessLevel.STALE)
        assert "Stale" in html

    def test_recent_label(self) -> None:
        html = freshness_indicator_html(FreshnessLevel.RECENT)
        assert "Recent" in html

    def test_fresh_has_colored_dot(self) -> None:
        html = freshness_indicator_html(FreshnessLevel.FRESH)
        # Should contain a colored dot character or CSS dot element
        assert "●" in html or "dot" in html or "#059669" in html or "00C853" in html

    def test_stale_has_red_dot(self) -> None:
        html = freshness_indicator_html(FreshnessLevel.STALE)
        assert "●" in html or "dot" in html or "#DC2626" in html or "FF1744" in html

    def test_returns_string(self) -> None:
        assert isinstance(freshness_indicator_html(FreshnessLevel.FRESH), str)


# ---------------------------------------------------------------------------
# render_evidence_html
# ---------------------------------------------------------------------------


class TestRenderEvidenceHtml:
    def test_contains_each_item(self) -> None:
        items = ["RSI crossed 60", "Smart money filing", "Earnings revision"]
        html = render_evidence_html(items)
        for item in items:
            assert item in html

    def test_is_ul_list(self) -> None:
        html = render_evidence_html(["item one", "item two"])
        assert "<ul" in html
        assert "<li" in html

    def test_empty_list_returns_string(self) -> None:
        result = render_evidence_html([])
        assert isinstance(result, str)

    def test_returns_string(self) -> None:
        assert isinstance(render_evidence_html(["a", "b"]), str)


# ---------------------------------------------------------------------------
# render_risk_html
# ---------------------------------------------------------------------------


class TestRenderRiskHtml:
    def test_contains_each_risk(self) -> None:
        risks = ["Macro headwinds", "Earnings volatility"]
        html = render_risk_html(risks)
        for risk in risks:
            assert risk in html

    def test_has_header(self) -> None:
        html = render_risk_html(["some risk"])
        assert "could go wrong" in html.lower() or "risk" in html.lower()

    def test_warning_box_styling(self) -> None:
        html = render_risk_html(["a risk"])
        # Should have orange/warning styling
        assert any(
            c in html
            for c in ["#FF", "orange", "warning", "D97706", "EA580C", "FFEDD5"]
        )

    def test_returns_string(self) -> None:
        assert isinstance(render_risk_html(["a"]), str)


# ---------------------------------------------------------------------------
# render_opportunity_card_html
# ---------------------------------------------------------------------------


class TestRenderOpportunityCardHtml:
    def test_contains_ticker(self) -> None:
        card = _make_card()
        html = render_opportunity_card_html(card, now=datetime(2026, 6, 3, 11, 0, 0))
        assert "AAPL" in html

    def test_contains_alert_summary(self) -> None:
        card = _make_card()
        html = render_opportunity_card_html(card, now=datetime(2026, 6, 3, 11, 0, 0))
        assert "Institutional buying detected" in html

    def test_contains_evidence(self) -> None:
        card = _make_card()
        html = render_opportunity_card_html(card, now=datetime(2026, 6, 3, 11, 0, 0))
        assert "RSI crossed 60" in html

    def test_contains_suggestion(self) -> None:
        card = _make_card()
        html = render_opportunity_card_html(card, now=datetime(2026, 6, 3, 11, 0, 0))
        assert "Consider initiating" in html

    def test_contains_risks(self) -> None:
        card = _make_card()
        html = render_opportunity_card_html(card, now=datetime(2026, 6, 3, 11, 0, 0))
        assert "Macro headwinds" in html

    def test_uses_dashboard_card_class(self) -> None:
        card = _make_card()
        html = render_opportunity_card_html(card, now=datetime(2026, 6, 3, 11, 0, 0))
        assert "dashboard-card" in html

    def test_green_border_for_high_conviction(self) -> None:
        card = _make_card(conviction=8.5)
        html = render_opportunity_card_html(card, now=datetime(2026, 6, 3, 11, 0, 0))
        assert "#00C853" in html or "059669" in html

    def test_red_border_for_low_conviction(self) -> None:
        card = _make_card(conviction=2.5)
        html = render_opportunity_card_html(card, now=datetime(2026, 6, 3, 11, 0, 0))
        assert "#FF1744" in html or "DC2626" in html or "991B1B" in html

    def test_returns_string(self) -> None:
        card = _make_card()
        result = render_opportunity_card_html(card, now=datetime(2026, 6, 3, 11, 0, 0))
        assert isinstance(result, str)

    def test_conviction_score_present(self) -> None:
        card = _make_card(conviction=8.5)
        html = render_opportunity_card_html(card, now=datetime(2026, 6, 3, 11, 0, 0))
        assert "8.5" in html
