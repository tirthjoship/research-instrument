"""Data loaders for stock analysis — DB and config sources."""

from __future__ import annotations

import os
from typing import Any

from loguru import logger

from adapters.visualization.analysis.scoring.supply_chain import find_supply_chain_group

__all__ = [
    "load_buzz_signals",
    "load_recommendation",
    "find_supply_chain_group",
    "get_sector_peers",
]


def load_buzz_signals(ticker: str, db_path: str) -> list[Any]:
    """Load buzz signals from SQLite. Returns [] on any error."""
    try:
        if not os.path.exists(db_path):
            return []
        from adapters.data.sqlite_store import SQLiteStore

        store = SQLiteStore(db_path)
        return store.get_buzz_signals(ticker=ticker)
    except Exception as exc:
        logger.warning("Could not load buzz signals for {}: {}", ticker, exc)
        return []


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
    # Determine peer tickers
    peer_tickers: list[str] = []

    if sc_group:
        leaders = sc_group.get("leaders", [])
        followers = sc_group.get("followers", [])
        candidates = leaders + followers
        peer_tickers = [t for t in candidates if t != ticker][:4]
    else:
        # Sector-based hardcoded fallback
        sector = info.get("sector", "")
        _SECTOR_PEERS: dict[str, list[str]] = {
            "Technology": ["MSFT", "AAPL", "GOOGL", "META"],
            "Healthcare": ["JNJ", "PFE", "ABBV", "MRK"],
            "Financial Services": ["JPM", "BAC", "GS", "MS"],
            "Consumer Cyclical": ["AMZN", "TSLA", "HD", "NKE"],
            "Energy": ["XOM", "CVX", "COP", "SLB"],
            "Industrials": ["CAT", "DE", "HON", "GE"],
        }
        peer_tickers = [
            t for t in _SECTOR_PEERS.get(sector, ["SPY", "QQQ"]) if t != ticker
        ][:4]

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
