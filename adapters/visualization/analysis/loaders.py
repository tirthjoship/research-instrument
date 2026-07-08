"""Data loaders for stock analysis — DB and config sources."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from loguru import logger

from adapters.visualization.analysis.scoring.supply_chain import find_supply_chain_group

BUZZ_MENTION_WINDOW_DAYS = 30
BUZZ_FALLBACK_WINDOW_DAYS = 90


def _distinct_harvest_days(rows: list[Any]) -> int:
    dates = {str(getattr(r, "fetched_at", "") or "")[:10] for r in rows}
    dates.discard("")
    return len(dates)


def _prefer_scored_buzz_rows(rows: list[Any]) -> list[Any]:
    """Prefer keyword-scored rows; fall back to rss_raw placeholders.

    Avoids triple-counting rss_raw + keyword + flan_t5 duplicates in panels.
    Old rows used timestamp-based kw_* hashes; keep those when no article_text era.
    """
    keyword = [
        r for r in rows if getattr(r, "scorer", None) in ("keyword", "keyword_live")
    ]
    if keyword:
        return keyword
    raw = [r for r in rows if getattr(r, "scorer", None) == "rss_raw"]
    if raw:
        return raw
    return rows


def _query_buzz_window(
    store: Any,
    ticker: str,
    anchor: datetime,
    window_days: int,
) -> list[Any]:
    start = anchor - timedelta(days=window_days)
    return list(
        store.get_buzz_signals(
            ticker=ticker,
            start_date=start,
            end_date=anchor,
        )
    )


def load_buzz_signals(
    ticker: str,
    db_path: str,
    *,
    window_days: int = BUZZ_MENTION_WINDOW_DAYS,
    ref: datetime | None = None,
) -> tuple[list[Any], bool]:
    """Load buzz signals from SQLite within a rolling window.

      Returns ``(signals, stale)``. *stale* is True when the primary window had
    no rows but an older harvest within ``BUZZ_FALLBACK_WINDOW_DAYS`` exists.
    """
    try:
        if not os.path.exists(db_path):
            return [], False
        from adapters.data.sqlite_store import SQLiteStore

        anchor = ref or datetime.now(timezone.utc)
        if anchor.tzinfo is None:
            anchor = anchor.replace(tzinfo=timezone.utc)
        store = SQLiteStore(db_path)
        rows = _query_buzz_window(store, ticker, anchor, window_days)
        if rows:
            return _prefer_scored_buzz_rows(rows), False
        fallback = _query_buzz_window(store, ticker, anchor, BUZZ_FALLBACK_WINDOW_DAYS)
        if fallback:
            return _prefer_scored_buzz_rows(fallback), True
        return [], False
    except Exception as exc:
        logger.warning("Could not load buzz signals for {}: {}", ticker, exc)
        return [], False


def load_buzz_volume_signals(
    ticker: str,
    db_path: str,
    *,
    window_days: int = BUZZ_MENTION_WINDOW_DAYS,
    ref: datetime | None = None,
) -> tuple[list[Any], bool]:
    """Load buzz rows for the volume chart — extends to 90d when 30d is one-day sparse."""
    primary, stale = load_buzz_signals(
        ticker, db_path, window_days=window_days, ref=ref
    )
    if _distinct_harvest_days(primary) >= 2:
        return primary, False
    extended, ext_stale = load_buzz_signals(
        ticker,
        db_path,
        window_days=BUZZ_FALLBACK_WINDOW_DAYS,
        ref=ref,
    )
    if _distinct_harvest_days(extended) >= 2:
        return extended, True
    return primary, stale


__all__ = [
    "BUZZ_FALLBACK_WINDOW_DAYS",
    "BUZZ_MENTION_WINDOW_DAYS",
    "_distinct_harvest_days",
    "load_buzz_signals",
    "load_buzz_volume_signals",
    "load_recommendation",
    "find_supply_chain_group",
    "get_sector_peers",
]


def load_recommendation(ticker: str, db_path: str) -> Any:
    """Load the most recent recommendation for ticker. Returns None on error."""
    try:
        if not os.path.exists(db_path):
            return None
        from adapters.data.sqlite_store import SQLiteStore

        store = SQLiteStore(db_path)
        recs = store.get_recommendations(symbol=ticker)
        if recs:
            return recs[0]  # Most recent
        return None
    except Exception as exc:
        logger.warning("Could not load recommendation for {}: {}", ticker, exc)
        return None


def get_sector_peers(
    ticker: str, info: dict[str, Any], sc_group: dict[str, Any] | None
) -> list[dict[str, Any]]:
    """Return 4-5 peer dicts {ticker, name, pe, market_cap, change_pct, role}."""
    # Determine peer tickers. Valuation peers must be same-industry/sector
    # comparables — NOT supply-chain leaders/followers, which are co-movement
    # relations (a follower's "leaders" are its suppliers, with very different
    # valuation profiles). Supply-chain co-members are only a last resort.
    peer_tickers: list[str] = []
    sector = info.get("sector", "")
    industry = info.get("industry", "")
    _INDUSTRY_PEERS: dict[str, list[str]] = {
        "Semiconductors": ["AMD", "AVGO", "QCOM", "TXN", "INTC", "MU"],
        "Semiconductor Equipment & Materials": ["AMAT", "LRCX", "KLAC", "ASML"],
        "Software - Infrastructure": ["MSFT", "ORCL", "ADBE", "CRM"],
        "Software - Application": ["CRM", "NOW", "INTU", "ADBE"],
        "Consumer Electronics": ["AAPL", "SONY", "DELL", "HPQ"],
    }
    _SECTOR_PEERS: dict[str, list[str]] = {
        "Technology": ["MSFT", "AAPL", "GOOGL", "META"],
        "Healthcare": ["JNJ", "PFE", "ABBV", "MRK"],
        "Financial Services": ["JPM", "BAC", "GS", "MS"],
        "Consumer Cyclical": ["AMZN", "TSLA", "HD", "NKE"],
        "Energy": ["XOM", "CVX", "COP", "SLB"],
        "Industrials": ["CAT", "DE", "HON", "GE"],
    }
    pool = _INDUSTRY_PEERS.get(industry) or _SECTOR_PEERS.get(sector)
    if pool:
        peer_tickers = [t for t in pool if t != ticker][:4]
    elif sc_group:
        candidates = sc_group.get("leaders", []) + sc_group.get("followers", [])
        peer_tickers = [t for t in candidates if t != ticker][:4]
    else:
        peer_tickers = [t for t in ["SPY", "QQQ"] if t != ticker][:4]

    # Fetch info for peers
    from adapters.visualization.price_cache import _fetch_ticker_info_impl

    peers: list[dict[str, Any]] = []
    for pt in peer_tickers:
        try:
            pi = _fetch_ticker_info_impl(pt)
            peers.append(
                {
                    "ticker": pt,
                    "name": pi.get("shortName", pt),
                    "pe": pi.get("trailingPE"),
                    "market_cap": float(pi.get("marketCap", 0) or 0),
                    "revenue_growth": pi.get("revenueGrowth"),
                    "gross_margins": pi.get("grossMargins"),
                    "change_pct": 0.0,  # Would need separate price fetch
                    "role": (
                        "leader"
                        if pt in (sc_group or {}).get("leaders", [])
                        else "peer"
                    ),
                }
            )
        except Exception as exc:
            logger.warning("Could not fetch peer data for {}: {}", pt, exc)

    return peers
