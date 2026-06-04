"""Onboarding card HTML component — shown on first run when no data exists.

Pure functions returning HTML strings for use with st.markdown(..., unsafe_allow_html=True).
"""

from __future__ import annotations


def render_onboarding_html() -> str:
    """Return HTML for the 3-step onboarding card.

    Steps: Scan → Watchlist → Trade.
    Shown when the user has no scan results, trades, or watchlist entries.
    """
    steps = [
        ("1", "Scan the Market", "Run Full Cycle to scan 350+ tickers for signals."),
        ("2", "Build Your Watchlist", "Pin tickers you want to track daily."),
        ("3", "Record Your Trades", "Log entries and exits to build learning memory."),
    ]

    steps_html = "".join(
        f'<div class="onboarding-step">'
        f'<div class="onboarding-num">{num}</div>'
        f"<div>"
        f'<div style="font-weight:600; font-size:14px; color:#111827;">{title}</div>'
        f'<div style="font-size:13px; color:#6B7280; margin-top:2px;">{desc}</div>'
        f"</div>"
        f"</div>"
        for num, title, desc in steps
    )

    return (
        f'<div class="onboarding-card">'
        f'<div style="font-size:16px; font-weight:700; color:#111827; margin-bottom:1rem;">'
        f"Get started in 3 steps"
        f"</div>"
        f"{steps_html}"
        f"</div>"
    )


def should_show_onboarding(
    has_scan_results: bool,
    has_trades: bool,
    has_watchlist: bool,
) -> bool:
    """Return True if all inputs are False (nothing has been done yet).

    Args:
        has_scan_results: True if at least one scan has been run.
        has_trades: True if at least one trade has been recorded.
        has_watchlist: True if at least one ticker is on the watchlist.

    Returns:
        True only when the user has not yet done anything.
    """
    return not has_scan_results and not has_trades and not has_watchlist
