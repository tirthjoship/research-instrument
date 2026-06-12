"""Section 4 — look into next. Diversification-first research feed.

Factual rank (present-day percentiles, pure arithmetic) is split from the
gate verdict, which stays abstaining and is shown as such inside the feed.
"""

from __future__ import annotations

import streamlit as st

from adapters.visualization.data_loader import load_brief_summary, load_latest_screen
from adapters.visualization.price_cache import fetch_week_changes  # noqa: F401
from application.diversification_query import rank_by_diversification
from application.holdings_reader import read_holdings

MAX_ROWS = 5  # validation 2026-06-12 (Q3): research feed stays 3-5 rows
_HISTORY_DAYS = 60


def _diversification_ranks(
    candidates: list[str], dominant: str
) -> list[tuple[str, float]]:
    """Fetch ~60d closes for candidates + dominant factor, rank by low |corr|."""
    try:
        import yfinance as yf

        data = yf.download(
            [*candidates, dominant],
            period=f"{_HISTORY_DAYS}d",
            interval="1d",
            progress=False,
            auto_adjust=True,
        )["Close"]
        series = {t: [float(v) for v in data[t].dropna().tolist()] for t in candidates}
        factor = [float(v) for v in data[dominant].dropna().tolist()]
    except Exception:  # noqa: BLE001 — degraded state below
        return []
    return rank_by_diversification(factor_series=factor, candidate_series=series)


def render(*, summary_path: str, reports_dir: str, holdings_path: str) -> None:
    st.subheader("Look into next")
    screen = load_latest_screen(reports_dir)
    summary = load_brief_summary(summary_path)
    if screen is None:
        st.info("No screen artifact yet — run the screen CLI; the feed needs it.")
        return

    if screen.get("abstained") or not screen.get("candidates"):
        st.markdown(
            '<div class="ws-card" style="padding:8px 14px;">'
            "The screen abstains — it claims no tradeable edge. "
            "Rows below are research starting points only."
            "</div>",
            unsafe_allow_html=True,
        )
    if not screen.get("candidates"):
        st.caption("Screen artifact holds no ranked names — re-run after Task 0 clean.")
        return

    held = set()
    try:
        held = {h.ticker for h in read_holdings(holdings_path)}
    except (OSError, ValueError, KeyError):
        pass
    ranked = [c for c in screen["candidates"] if c["ticker"] not in held]
    by_ticker = {c["ticker"]: c for c in ranked}

    dominant = ((summary or {}).get("macro") or {}).get("dominant_factor")
    rows: list[tuple[str, str]] = []
    if dominant:
        share = ((summary or {}).get("macro") or {}).get("systematic_share", 0.0)
        for ticker, corr in _diversification_ranks(list(by_ticker), dominant):
            c = by_ticker[ticker]
            rows.append(
                (
                    ticker,
                    f"Low link to your {share:.0%} {dominant} bet"
                    f" (corr {corr:+.2f}) · also screens: {c.get('why', '')}",
                )
            )
            if len(rows) >= MAX_ROWS:
                break
    if not rows:  # lens unavailable -> factual composite order
        for c in ranked[:MAX_ROWS]:
            rows.append((c["ticker"], f"Screens well now: {c.get('why', '')}"))

    for ticker, why in rows:
        cols = st.columns([5, 1])
        with cols[0]:
            st.markdown(
                f'<div class="ws-card cp-row" style="padding:8px 14px;">'
                f"<strong>{ticker}</strong> — {why}</div>",
                unsafe_allow_html=True,
            )
        with cols[1]:
            if st.button("Detail", key=f"cp_detail_{ticker}"):
                from adapters.visualization.cockpit.stock_detail import (
                    open_stock_detail,
                )

                open_stock_detail(ticker)
    st.caption("Factual present-day ranks, for research. The gate verdict is above.")
