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
