"""Hero section HTML components — 3-panel market status dashboard header.

Pure functions returning HTML strings for use with st.markdown(..., unsafe_allow_html=True).
"""

from __future__ import annotations

from typing import Any


def render_market_panel(
    spy_price: float,
    spy_change: float,
    market_open: bool,
    time_est: str,
    mood: str,
) -> str:
    """Return HTML for the market status panel.

    Shows S&P 500 price, change% (green/red), OPEN/CLOSED status, EST time, mood text.
    """
    sign = "+" if spy_change >= 0 else ""
    change_color = "#059669" if spy_change >= 0 else "#DC2626"
    status_label = "OPEN" if market_open else "CLOSED"
    status_color = "#059669" if market_open else "#DC2626"

    return (
        f'<div class="hero-panel">'
        f'<div class="hero-label">S&amp;P 500 / MARKET</div>'
        f'<div class="hero-value">${spy_price:,.2f}</div>'
        f'<div class="hero-sub" style="color:{change_color};">{sign}{spy_change:.2f}%</div>'
        f'<div class="hero-sub">'
        f'<span style="color:{status_color}; font-weight:600;">{status_label}</span>'
        f" &nbsp;·&nbsp; {time_est} EST"
        f"</div>"
        f'<div class="hero-sub">{mood}</div>'
        f"</div>"
    )


def render_portfolio_panel(
    total_value: float,
    total_pnl: float,
    pnl_pct: float,
    n_positions: int,
    best_performer: str,
) -> str:
    """Return HTML for the portfolio summary panel.

    Shows total value, P&L (green/red), positions count, best performer.
    """
    pnl_sign = "+" if total_pnl >= 0 else ""
    pct_sign = "+" if pnl_pct >= 0 else ""
    pnl_color = "#059669" if total_pnl >= 0 else "#DC2626"

    return (
        f'<div class="hero-panel">'
        f'<div class="hero-label">PORTFOLIO</div>'
        f'<div class="hero-value">${total_value:,.0f}</div>'
        f'<div class="hero-sub" style="color:{pnl_color};">'
        f"{pnl_sign}${total_pnl:,.0f} &nbsp;({pct_sign}{pnl_pct:.2f}%)"
        f"</div>"
        f'<div class="hero-sub">{n_positions} positions</div>'
        f'<div class="hero-sub">Best: <strong>{best_performer}</strong></div>'
        f"</div>"
    )


def render_signal_panel(
    n_new_opps: int,
    top_ticker: str,
    top_conviction: float,
    n_watchlist_alerts: int,
    summary: str,
) -> str:
    """Return HTML for the signal intelligence panel.

    Shows opportunity count, top ticker + conviction, watchlist alerts, summary quote.
    """
    return (
        f'<div class="hero-panel">'
        f'<div class="hero-label">SIGNALS</div>'
        f'<div class="hero-value">{n_new_opps} opportunities</div>'
        f'<div class="hero-sub">'
        f"Top: <strong>{top_ticker}</strong> &nbsp;{top_conviction:.1f}/10"
        f"</div>"
        f'<div class="hero-sub">{n_watchlist_alerts} watchlist alerts</div>'
        f'<div class="hero-sub" style="font-style:italic;">&ldquo;{summary}&rdquo;</div>'
        f"</div>"
    )


def render_hero_html(
    market: dict[str, Any], portfolio: dict[str, Any], signal: dict[str, Any]
) -> str:
    """Assemble 3 hero panels in a CSS grid row.

    Args:
        market: Keys: spy_price, spy_change, market_open, time_est, mood.
        portfolio: Keys: total_value, total_pnl, pnl_pct, n_positions, best_performer.
        signal: Keys: n_new_opps, top_ticker, top_conviction, n_watchlist_alerts, summary.

    Returns:
        Full hero section HTML string.
    """
    market_html = render_market_panel(
        spy_price=market["spy_price"],
        spy_change=market["spy_change"],
        market_open=market["market_open"],
        time_est=market["time_est"],
        mood=market["mood"],
    )
    portfolio_html = render_portfolio_panel(
        total_value=portfolio["total_value"],
        total_pnl=portfolio["total_pnl"],
        pnl_pct=portfolio["pnl_pct"],
        n_positions=portfolio["n_positions"],
        best_performer=portfolio["best_performer"],
    )
    signal_html = render_signal_panel(
        n_new_opps=signal["n_new_opps"],
        top_ticker=signal["top_ticker"],
        top_conviction=signal["top_conviction"],
        n_watchlist_alerts=signal["n_watchlist_alerts"],
        summary=signal["summary"],
    )

    return (
        f'<div style="display:grid; grid-template-columns:repeat(3,1fr); gap:1rem;">'
        f"{market_html}{portfolio_html}{signal_html}"
        f"</div>"
    )
