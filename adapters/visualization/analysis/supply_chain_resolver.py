"""Dynamic supply-chain group resolution (ADR-027 hybrid: correlation + curated YAML).

``find_supply_chain_group()`` (scoring/supply_chain.py) returns the *first* YAML
group containing a ticker — wrong for multi-group tickers (e.g. NVDA appears as a
follower in ``semiconductors`` but a leader in ``ai_infrastructure``). This module
picks the best-fit group per ticker by actually measuring co-movement across every
candidate the ticker belongs to, instead of trusting YAML ordering.

Candidate sources (merged, never LLM-invented):
  - every YAML group the ticker appears in (``config/relationships/supply_chain.yaml``)
  - the curated industry/sector peer pool already used for valuation peers
    (``loaders.INDUSTRY_PEERS`` / ``SECTOR_PEERS``)

The candidate universe is intentionally bounded (YAML groups + a ~4-6 ticker sector
pool, not the full 600-ticker S&P500+Nasdaq100 universe) — this resolver runs live,
once per dashboard page load. A full-universe correlation scan is a batch/weekly
concern (ADR-027's own cadence), not a per-request one.
"""

from __future__ import annotations

import os
from typing import Any

from loguru import logger

from adapters.visualization.analysis.scoring.supply_chain import (
    avg_pairwise_correlation,
    compute_co_movement,
)

MIN_MEMBERS = 4
MAX_MEMBERS = 10
MIN_COMOVEMENT = 0.4

_ACRONYMS = {"ai", "saas", "ev", "gpu", "it"}


def _load_yaml_relationships(
    yaml_path: str = "config/relationships/supply_chain.yaml",
) -> list[dict[str, Any]]:
    try:
        import yaml

        if not os.path.exists(yaml_path):
            return []
        with open(yaml_path) as f:
            data = yaml.safe_load(f)
        relationships = (data or {}).get("relationships", [])
        return list(relationships) if relationships else []
    except Exception as exc:
        logger.warning("Could not load supply chain config: {}", exc)
        return []


def _yaml_candidate_groups(
    ticker: str, relationships: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """All YAML groups containing ``ticker``, each enriched with ``_is_leader``."""
    out: list[dict[str, Any]] = []
    for rel in relationships:
        leaders = rel.get("leaders", []) or []
        followers = rel.get("followers", []) or []
        if ticker in leaders or ticker in followers:
            enriched = dict(rel)
            enriched["_is_leader"] = ticker in leaders
            out.append(enriched)
    return out


_NON_US_SUFFIXES = (".TO", ".NE", ".NS", ".BO")


def _industry_sector_pool(
    ticker: str, info: dict[str, Any]
) -> tuple[str, list[str]] | None:
    """Curated peer pool for the ticker's industry (preferred) or sector.

    US-only pool (loaders.INDUSTRY_PEERS/SECTOR_PEERS) — gated to US tickers.
    yfinance's generic sector/industry labels (e.g. "Consumer Cyclical") are
    shared across markets, so without this gate a non-US ticker could get
    American mega-caps as its "supply chain peers" purely because the label
    matches, with no relation to the actual company. FMP peers (this
    resolver's other live candidate source) already cover non-US markets
    correctly, so this pool simply doesn't apply outside the US.
    """
    if ticker.endswith(_NON_US_SUFFIXES):
        return None

    from adapters.visualization.analysis.loaders import INDUSTRY_PEERS, SECTOR_PEERS

    industry = info.get("industry", "") or ""
    sector = info.get("sector", "") or ""
    if industry in INDUSTRY_PEERS:
        return industry, list(INDUSTRY_PEERS[industry])
    if sector in SECTOR_PEERS:
        return sector, list(SECTOR_PEERS[sector])
    return None


def _display_name(group_id: str) -> str:
    words = group_id.replace("-", "_").split("_")
    return " ".join(
        w.upper() if w.lower() in _ACRONYMS else w.capitalize() for w in words
    )


def _determine_leader(
    ticker: str,
    present_members: list[str],
    market_caps: dict[str, float],
    cluster_closes: dict[str, list[float]],
    yaml_is_leader: bool,
) -> bool:
    """Leader if: YAML says so, else highest market cap in cluster when known,
    else most central (highest average correlation to the rest of the cluster).

    Market cap and centrality are a fallback chain, not independently-OR'd votes —
    when market caps are known they are decisive (they're the more direct proxy
    for "who's the anchor"); centrality only breaks the tie when caps are missing.
    """
    if yaml_is_leader:
        return True

    caps = {
        t: market_caps.get(t, 0.0)
        for t in present_members
        if market_caps.get(t, 0.0) > 0
    }
    if caps:
        return ticker in caps and caps[ticker] == max(caps.values())

    centrality = avg_pairwise_correlation(cluster_closes)
    if centrality:
        return max(centrality, key=lambda t: centrality[t]) == ticker

    return False


def select_best_group(
    ticker: str,
    info: dict[str, Any],
    closes_by_ticker: dict[str, list[float]],
    yaml_relationships: list[dict[str, Any]],
    fmp_peers: list[str] | None = None,
) -> dict[str, Any] | None:
    """Pure scoring core: pick the best candidate group from pre-fetched closes.

    No network I/O — market-cap-based leader detection is applied by the caller
    once the winning cluster (and therefore its member list) is known.
    """
    candidates: list[dict[str, Any]] = []

    for g in _yaml_candidate_groups(ticker, yaml_relationships):
        leaders = list(g.get("leaders", []) or [])
        followers = list(g.get("followers", []) or [])
        peers = [t for t in (leaders + followers) if t != ticker][:MAX_MEMBERS]
        candidates.append(
            {
                "source": "yaml",
                "group_id": g["group"],
                "display": _display_name(g["group"]),
                "peers": peers,
                "is_leader_hint": g["_is_leader"],
                "lag": g.get("typical_lag_days"),
                "notes": g.get("notes", ""),
                "yaml_leaders": leaders,
                "yaml_followers": followers,
            }
        )

    pool = _industry_sector_pool(ticker, info)
    if pool:
        label, members = pool
        peers = [t for t in members if t != ticker][:MAX_MEMBERS]
        candidates.append(
            {
                "source": "correlation",
                "group_id": f"{label.lower().replace(' ', '_').replace('-', '_')}_corr_cluster",
                "display": f"{label} corr-cluster",
                "peers": peers,
                "is_leader_hint": False,
                "lag": None,
                "notes": "",
                "yaml_leaders": [],
                "yaml_followers": [],
            }
        )

    if fmp_peers:
        peers = [t for t in fmp_peers if t != ticker][:MAX_MEMBERS]
        candidates.append(
            {
                "source": "fmp_peers",
                "group_id": f"{ticker.lower()}_fmp_peers",
                "display": f"{ticker} FMP Peers",
                "peers": peers,
                "is_leader_hint": False,
                "lag": None,
                "notes": "",
                "yaml_leaders": [],
                "yaml_followers": [],
            }
        )

    scored: list[tuple[float, dict[str, Any], list[str]]] = []
    for cand in candidates:
        present_members = [t for t in [ticker, *cand["peers"]] if t in closes_by_ticker]
        if len(present_members) < MIN_MEMBERS:
            continue
        cluster_closes = {t: closes_by_ticker[t] for t in present_members}
        cm = compute_co_movement(cluster_closes)
        if cm is None or cm < MIN_COMOVEMENT:
            continue
        scored.append((cm, cand, present_members))

    if not scored:
        return None

    scored.sort(key=lambda row: (row[0], row[1]["source"] == "yaml"), reverse=True)
    co_movement, cand, present_members = scored[0]
    present_peers = [t for t in present_members if t != ticker]

    return {
        "group": cand["group_id"],
        "group_display": cand["display"],
        "typical_lag_days": cand["lag"],
        "notes": cand["notes"],
        "co_movement": round(co_movement, 4),
        "resolution_score": round(co_movement, 4),
        "provenance": (
            "yaml+correlation" if cand["source"] == "yaml" else "correlation_only"
        ),
        "_yaml_leaders": cand["yaml_leaders"],
        "_yaml_followers": cand["yaml_followers"],
        "_yaml_is_leader_hint": cand["is_leader_hint"],
        "_present_peers": present_peers,
    }


def resolve_supply_chain_group(
    ticker: str,
    info: dict[str, Any],
    *,
    yaml_path: str = "config/relationships/supply_chain.yaml",
    closes_by_ticker: dict[str, list[float]] | None = None,
    market_caps: dict[str, float] | None = None,
    fmp_peers: list[str] | None = None,
) -> dict[str, Any] | None:
    """Resolve the best-fit supply-chain group for ``ticker``.

    Returns ``None`` when no candidate group clears the minimum member count
    (4) and co-movement threshold (0.4) — an honest "not enough signal" gap,
    never a guessed group.
    """
    ticker = ticker.upper().strip()
    relationships = _load_yaml_relationships(yaml_path)

    if closes_by_ticker is None:
        candidate_tickers: set[str] = {ticker}
        for g in _yaml_candidate_groups(ticker, relationships):
            candidate_tickers.update(g.get("leaders", []) or [])
            candidate_tickers.update(g.get("followers", []) or [])
        pool = _industry_sector_pool(ticker, info)
        if pool:
            candidate_tickers.update(pool[1])

        if fmp_peers is None:
            from datetime import datetime, timezone

            from adapters.data.fmp_adapter import get_cached_stock_peers
            from adapters.data.sqlite_store import SQLiteStore

            try:
                fmp_peers = get_cached_stock_peers(
                    SQLiteStore(), ticker, datetime.now(timezone.utc)
                )
            except Exception as exc:
                logger.debug("Could not fetch FMP peers for {}: {}", ticker, exc)
                fmp_peers = []
        candidate_tickers.update(fmp_peers)

        from adapters.visualization.price_cache import _batch_fetch_closes_impl

        closes_by_ticker = _batch_fetch_closes_impl(tuple(sorted(candidate_tickers)))

    picked = select_best_group(ticker, info, closes_by_ticker, relationships, fmp_peers)
    if picked is None:
        return None

    present_peers = picked.pop("_present_peers")
    yaml_leaders = picked.pop("_yaml_leaders")
    yaml_followers = picked.pop("_yaml_followers")
    yaml_is_leader_hint = picked.pop("_yaml_is_leader_hint")

    if market_caps is None:
        from adapters.visualization.price_cache import _fetch_ticker_info_impl

        market_caps = {}
        for t in [ticker, *present_peers]:
            try:
                pi = _fetch_ticker_info_impl(t)
                market_caps[t] = float(pi.get("marketCap", 0) or 0)
            except Exception as exc:
                logger.debug("Could not fetch market cap for {}: {}", t, exc)

    cluster_closes = {
        t: closes_by_ticker[t]
        for t in [ticker, *present_peers]
        if t in closes_by_ticker
    }
    is_leader = _determine_leader(
        ticker,
        [ticker, *present_peers],
        market_caps,
        cluster_closes,
        yaml_is_leader_hint,
    )

    if yaml_leaders or yaml_followers:
        leaders = list(yaml_leaders)
        followers = list(yaml_followers)
        # Relocate ticker to match its computed role even when that overrides
        # the YAML bucket it started in (e.g. a market-cap-driven promotion
        # from a stale "follower" designation to leader — this is the exact
        # NVDA bug this resolver fixes: honest role, not a fixed config label).
        if is_leader:
            if ticker in followers:
                followers.remove(ticker)
            if ticker not in leaders:
                leaders.append(ticker)
        else:
            if ticker in leaders:
                leaders.remove(ticker)
            if ticker not in followers:
                followers.append(ticker)
    else:
        leaders = [ticker] if is_leader else []
        followers = present_peers if is_leader else [ticker, *present_peers]

    picked["leaders"] = leaders
    picked["followers"] = [f for f in followers if f not in leaders]
    picked["_is_leader"] = is_leader
    picked["member_market_caps"] = market_caps
    return picked
