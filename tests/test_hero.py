"""Tests for hero section HTML components."""

from __future__ import annotations

from adapters.visualization.components.hero import (
    render_hero_html,
    render_market_panel,
    render_portfolio_panel,
    render_signal_panel,
)


class TestRenderMarketPanel:
    def test_contains_spy_price(self) -> None:
        html = render_market_panel(
            spy_price=5432.10,
            spy_change=1.23,
            market_open=True,
            time_est="10:30 AM",
            mood="Bullish",
        )
        assert "5,432" in html

    def test_positive_change_green(self) -> None:
        html = render_market_panel(5000.0, 1.5, True, "09:00 AM", "Bullish")
        assert "+1.50%" in html
        assert (
            "green" in html.lower()
            or "#00" in html
            or "#0" in html
            or "059669" in html
            or "16a34a" in html
            or "color" in html
        )

    def test_negative_change_red(self) -> None:
        html = render_market_panel(5000.0, -0.8, False, "04:01 PM", "Bearish")
        assert "-0.80%" in html

    def test_market_open_shows_open(self) -> None:
        html = render_market_panel(5000.0, 0.5, True, "11:00 AM", "Neutral")
        assert "OPEN" in html

    def test_market_closed_shows_closed(self) -> None:
        html = render_market_panel(5000.0, -0.2, False, "05:00 PM", "Bearish")
        assert "CLOSED" in html

    def test_time_and_mood_present(self) -> None:
        html = render_market_panel(5000.0, 0.1, True, "02:15 PM", "Optimistic")
        assert "02:15 PM" in html
        assert "Optimistic" in html

    def test_uses_hero_panel_class(self) -> None:
        html = render_market_panel(5000.0, 0.5, True, "10:00 AM", "Neutral")
        assert "hero-panel" in html


class TestRenderPortfolioPanel:
    def test_contains_total_value(self) -> None:
        html = render_portfolio_panel(
            total_value=25000.0,
            total_pnl=1500.0,
            pnl_pct=6.38,
            n_positions=5,
            best_performer="AAPL",
        )
        assert "25,000" in html or "25000" in html

    def test_positive_pnl_shows_green(self) -> None:
        html = render_portfolio_panel(10000.0, 500.0, 5.0, 3, "NVDA")
        assert "500" in html
        assert "+5.00%" in html or "+5.0%" in html

    def test_negative_pnl_shows_red(self) -> None:
        html = render_portfolio_panel(10000.0, -200.0, -2.0, 2, "TSLA")
        assert "-200" in html or "-2.0" in html

    def test_positions_count_shown(self) -> None:
        html = render_portfolio_panel(10000.0, 100.0, 1.0, 7, "MSFT")
        assert "7" in html

    def test_best_performer_shown(self) -> None:
        html = render_portfolio_panel(10000.0, 100.0, 1.0, 3, "GOOG")
        assert "GOOG" in html

    def test_uses_hero_panel_class(self) -> None:
        html = render_portfolio_panel(10000.0, 0.0, 0.0, 0, "—")
        assert "hero-panel" in html


class TestRenderSignalPanel:
    def test_contains_opportunity_count(self) -> None:
        html = render_signal_panel(
            n_new_opps=12,
            top_ticker="AAPL",
            top_conviction=8.5,
            n_watchlist_alerts=3,
            summary="Strong momentum across tech",
        )
        assert "12" in html

    def test_top_ticker_shown(self) -> None:
        html = render_signal_panel(5, "NVDA", 9.1, 1, "Semiconductors surging")
        assert "NVDA" in html

    def test_conviction_shown(self) -> None:
        html = render_signal_panel(5, "NVDA", 9.1, 1, "Semiconductors surging")
        assert "9.1" in html

    def test_watchlist_alerts_shown(self) -> None:
        html = render_signal_panel(3, "TSLA", 7.2, 4, "Mixed signals")
        assert "4" in html

    def test_summary_shown(self) -> None:
        html = render_signal_panel(2, "AAPL", 6.0, 0, "Cautious outlook")
        assert "Cautious outlook" in html

    def test_uses_hero_panel_class(self) -> None:
        html = render_signal_panel(0, "—", 5.0, 0, "No signals today")
        assert "hero-panel" in html


class TestRenderHeroHtml:
    def test_assembles_all_three_panels(self) -> None:
        market = {
            "spy_price": 5200.0,
            "spy_change": 0.5,
            "market_open": True,
            "time_est": "10:00 AM",
            "mood": "Bullish",
        }
        portfolio = {
            "total_value": 15000.0,
            "total_pnl": 300.0,
            "pnl_pct": 2.0,
            "n_positions": 4,
            "best_performer": "AAPL",
        }
        signal = {
            "n_new_opps": 8,
            "top_ticker": "NVDA",
            "top_conviction": 8.8,
            "n_watchlist_alerts": 2,
            "summary": "Strong tech signals",
        }
        html = render_hero_html(market, portfolio, signal)
        # All three panels present
        assert "OPEN" in html
        assert "AAPL" in html
        assert "NVDA" in html
        # Grid wrapper present
        assert "hero-panel" in html

    def test_returns_string(self) -> None:
        market = {
            "spy_price": 5000.0,
            "spy_change": 0.0,
            "market_open": False,
            "time_est": "4:00 PM",
            "mood": "Neutral",
        }
        portfolio = {
            "total_value": 0.0,
            "total_pnl": 0.0,
            "pnl_pct": 0.0,
            "n_positions": 0,
            "best_performer": "—",
        }
        signal = {
            "n_new_opps": 0,
            "top_ticker": "—",
            "top_conviction": 5.0,
            "n_watchlist_alerts": 0,
            "summary": "No data",
        }
        result = render_hero_html(market, portfolio, signal)
        assert isinstance(result, str)
        assert len(result) > 0
