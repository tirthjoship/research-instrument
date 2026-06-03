"""Tests for dashboard formatters."""

from __future__ import annotations

from datetime import datetime, timedelta


class TestGradeColor:
    def test_strong_buy_green(self) -> None:
        from adapters.visualization.components.formatters import grade_color

        assert grade_color("Strong Buy") == "#00C853"

    def test_buy_light_green(self) -> None:
        from adapters.visualization.components.formatters import grade_color

        assert grade_color("Buy") == "#69F0AE"

    def test_hold_amber(self) -> None:
        from adapters.visualization.components.formatters import grade_color

        assert grade_color("Hold") == "#FFD600"

    def test_may_sell_orange(self) -> None:
        from adapters.visualization.components.formatters import grade_color

        assert grade_color("May Sell") == "#FF9100"

    def test_immediate_sell_red(self) -> None:
        from adapters.visualization.components.formatters import grade_color

        assert grade_color("Immediate Sell") == "#FF1744"

    def test_unknown_grade_gray(self) -> None:
        from adapters.visualization.components.formatters import grade_color

        assert grade_color("Unknown") == "#9E9E9E"


class TestDirectionIcon:
    def test_bullish(self) -> None:
        from adapters.visualization.components.formatters import direction_icon

        assert direction_icon("bullish") == "🟢"

    def test_bearish(self) -> None:
        from adapters.visualization.components.formatters import direction_icon

        assert direction_icon("bearish") == "🔴"

    def test_neutral(self) -> None:
        from adapters.visualization.components.formatters import direction_icon

        assert direction_icon("neutral") == "⚪"

    def test_unknown_defaults_neutral(self) -> None:
        from adapters.visualization.components.formatters import direction_icon

        assert direction_icon("anything") == "⚪"


class TestUrgencyBadge:
    def test_immediate(self) -> None:
        from adapters.visualization.components.formatters import urgency_badge

        assert urgency_badge("immediate") == "🔴 IMMEDIATE"

    def test_this_week(self) -> None:
        from adapters.visualization.components.formatters import urgency_badge

        assert urgency_badge("this_week") == "🟡 THIS WEEK"

    def test_watch(self) -> None:
        from adapters.visualization.components.formatters import urgency_badge

        assert urgency_badge("watch") == "⚪ WATCH"


class TestPct:
    def test_positive(self) -> None:
        from adapters.visualization.components.formatters import pct

        assert pct(0.032) == "+3.20%"

    def test_negative(self) -> None:
        from adapters.visualization.components.formatters import pct

        assert pct(-0.015) == "-1.50%"

    def test_zero(self) -> None:
        from adapters.visualization.components.formatters import pct

        assert pct(0.0) == "+0.00%"

    def test_none_returns_na(self) -> None:
        from adapters.visualization.components.formatters import pct

        assert pct(None) == "N/A"


class TestFreshnessStatus:
    def test_fresh(self) -> None:
        from adapters.visualization.components.formatters import freshness_status

        recent = datetime.now() - timedelta(hours=2)
        icon, label = freshness_status(recent)
        assert icon == "✅"
        assert "2h" in label or "hour" in label.lower() or "ago" in label.lower()

    def test_stale(self) -> None:
        from adapters.visualization.components.formatters import freshness_status

        old = datetime.now() - timedelta(hours=12)
        icon, _ = freshness_status(old)
        assert icon == "🟡"

    def test_warning(self) -> None:
        from adapters.visualization.components.formatters import freshness_status

        old = datetime.now() - timedelta(hours=30)
        icon, _ = freshness_status(old)
        assert icon == "⚠️"

    def test_critical(self) -> None:
        from adapters.visualization.components.formatters import freshness_status

        old = datetime.now() - timedelta(hours=80)
        icon, _ = freshness_status(old)
        assert icon == "❌"

    def test_none_returns_unknown(self) -> None:
        from adapters.visualization.components.formatters import freshness_status

        icon, label = freshness_status(None)
        assert icon == "❌"
        assert "never" in label.lower() or "unknown" in label.lower()


class TestGradeDisplayName:
    def test_strong_buy(self) -> None:
        from adapters.visualization.components.formatters import grade_display_name

        assert grade_display_name("strong_buy") == "Strong Buy"

    def test_buy(self) -> None:
        from adapters.visualization.components.formatters import grade_display_name

        assert grade_display_name("buy") == "Buy"

    def test_hold(self) -> None:
        from adapters.visualization.components.formatters import grade_display_name

        assert grade_display_name("hold") == "Hold"

    def test_may_sell(self) -> None:
        from adapters.visualization.components.formatters import grade_display_name

        assert grade_display_name("may_sell") == "May Sell"

    def test_immediate_sell(self) -> None:
        from adapters.visualization.components.formatters import grade_display_name

        assert grade_display_name("immediate_sell") == "Immediate Sell"

    def test_already_display_name(self) -> None:
        from adapters.visualization.components.formatters import grade_display_name

        assert grade_display_name("Strong Buy") == "Strong Buy"

    def test_unknown(self) -> None:
        from adapters.visualization.components.formatters import grade_display_name

        assert grade_display_name("unknown") == "Unknown"


class TestGradeBadgeHtml:
    def test_strong_buy_has_class(self) -> None:
        from adapters.visualization.components.formatters import grade_badge_html

        html = grade_badge_html("strong_buy")
        assert "grade-strong-buy" in html
        assert "Strong Buy" in html

    def test_hold_has_class(self) -> None:
        from adapters.visualization.components.formatters import grade_badge_html

        html = grade_badge_html("hold")
        assert "grade-hold" in html


class TestStatusPillHtml:
    def test_fresh(self) -> None:
        from adapters.visualization.components.formatters import status_pill_html

        html = status_pill_html("fresh", "2h ago")
        assert "pill-fresh" in html
        assert "2h ago" in html

    def test_critical(self) -> None:
        from adapters.visualization.components.formatters import status_pill_html

        html = status_pill_html("critical", "5d ago")
        assert "pill-critical" in html


class TestSignalPillHtml:
    def test_bullish(self) -> None:
        from adapters.visualization.components.formatters import signal_pill_html

        html = signal_pill_html("bullish")
        assert "signal-bullish" in html
        assert "BULLISH" in html

    def test_bearish(self) -> None:
        from adapters.visualization.components.formatters import signal_pill_html

        html = signal_pill_html("bearish")
        assert "signal-bearish" in html

    def test_neutral(self) -> None:
        from adapters.visualization.components.formatters import signal_pill_html

        html = signal_pill_html("neutral")
        assert "signal-neutral" in html


class TestConfidenceBarHtml:
    def test_high_confidence(self) -> None:
        from adapters.visualization.components.formatters import confidence_bar_html

        html = confidence_bar_html(0.85)
        assert "85%" in html

    def test_zero(self) -> None:
        from adapters.visualization.components.formatters import confidence_bar_html

        html = confidence_bar_html(0.0)
        assert "0%" in html


class TestFreshnessStatusHtml:
    def test_returns_pill_html(self) -> None:
        from adapters.visualization.components.formatters import freshness_status_html

        html = freshness_status_html(datetime.now() - timedelta(hours=2))
        assert "pill-fresh" in html
        assert "2h ago" in html

    def test_none_returns_critical(self) -> None:
        from adapters.visualization.components.formatters import freshness_status_html

        html = freshness_status_html(None)
        assert "pill-critical" in html
        assert "Never" in html
