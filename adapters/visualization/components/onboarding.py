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


def render_landing_door_html(local: bool) -> str:
    """Return HTML for the landing door (Home tab — no book loaded yet).

    Renders the petrol banner with heading and privacy copy only.
    The <button class="db ..."> elements have been removed — they were decorative
    HTML that could not trigger Streamlit.  The real working widgets
    (st.button / st.file_uploader) are rendered separately in _handle_onboarding().

    When ``local`` is True (is_local_runtime() returned True), the privacy promise
    and CSV upload affordance text are shown.  When False (hosted or unknown), they
    are hidden and an honest notice is shown instead.  This is the privacy gate.
    """
    if local:
        privacy = (
            '<p style="margin:0;font-size:12.5px;color:rgba(255,255,255,.82);line-height:1.5">'
            "Explore a sample book or load your own. "
            '<b style="color:#fff">Everything stays on your machine</b>'
            " — never uploaded.</p>"
        )
    else:
        privacy = (
            '<p style="margin:0;font-size:12.5px;color:rgba(255,255,255,.82);line-height:1.5">'
            "Explore the sample book. Holdings upload is disabled — "
            "this build isn't running local-only.</p>"
        )
    # Note: .door CSS has border-radius:18px 18px 0 0 (square bottom) so it connects
    # flush to the .door-actions panel / Streamlit column row that follows immediately.
    return (
        '<div class="door">'
        '<h2 style="font-family:Fraunces,serif;font-weight:700;font-size:18px;margin:0 0 6px">'
        "Load a book to begin</h2>"
        f"{privacy}"
        "</div>"
    )


def render_sample_banner_html() -> str:
    """Compact 3-column info banner for the Home tab.

    Icon | sample-book description + ticker strip | (Streamlit upload widgets follow
    in the adjacent st.column — they cannot live inside an HTML string).
    """
    return (
        '<div style="'
        "background:#FFFFFF;"
        "border:1px solid #BFDBFE;"
        "border-left:4px solid #1D4ED8;"
        "border-radius:8px;"
        "padding:12px 14px;"
        "display:flex;"
        "align-items:center;"
        'gap:14px;margin-bottom:4px;">'
        '<div style="font-size:22px;flex-shrink:0;">📋</div>'
        '<div style="flex:1;">'
        '<div style="'
        "font-family:'Fraunces',serif;"
        "font-size:14px;"
        "font-weight:700;"
        "color:#14181F;"
        'margin-bottom:2px;">Sample book — 10 popular US stocks</div>'
        '<div style="'
        "font-family:'IBM Plex Sans',sans-serif;"
        "font-size:11px;"
        'color:#717885;">'
        "Explore with real market data. Rules fire on real evidence — "
        "this is what a weekly review looks like."
        "</div>"
        '<div style="'
        "font-family:'IBM Plex Mono',monospace;"
        "font-size:10px;"
        "color:#1D4ED8;"
        'margin-top:3px;">'
        "AAPL · MSFT · NVDA · GOOGL · AMZN"
        " · TSLA · META · JPM · V · BRK-B"
        "</div>"
        "</div>"
        "</div>"
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
