"""Valuation peers must be same-industry comparables, not supply-chain relations.

Regression for the live "0th percentile / n/a / amber-cheap" cascade: NVDA was
compared against its equipment suppliers (AMAT/LRCX/KLAC/ASML) because it is a
*follower* in the 'semiconductors' supply-chain group. Those are co-movement
relations, not valuation comps.
"""

from __future__ import annotations

from unittest.mock import patch

from adapters.visualization.analysis.loaders import get_sector_peers

_PC = "adapters.visualization.price_cache._fetch_ticker_info_impl"


def _stub_info(ticker: str) -> dict[str, object]:
    return {"shortName": ticker, "trailingPE": 30.0, "marketCap": 1e11}


def test_industry_comps_preferred_over_supply_chain_relations() -> None:
    sc_group = {
        "group": "semiconductors",
        "leaders": ["AMAT", "LRCX", "KLAC", "ASML"],
        "followers": ["NVDA"],
    }
    info = {"sector": "Technology", "industry": "Semiconductors"}
    with patch(_PC, side_effect=_stub_info):
        peers = get_sector_peers("NVDA", info, sc_group)
    tickers = {p["ticker"] for p in peers}
    # real semiconductor comps, not the supply-chain equipment makers
    assert "AMD" in tickers
    assert tickers.isdisjoint({"AMAT", "LRCX", "KLAC", "ASML"})
    assert "NVDA" not in tickers


def test_supply_chain_used_only_when_no_industry_or_sector_match() -> None:
    sc_group = {"group": "x", "leaders": ["AAA"], "followers": ["BBB", "TKR"]}
    info = {"sector": "", "industry": ""}
    with patch(_PC, side_effect=_stub_info):
        peers = get_sector_peers("TKR", info, sc_group)
    tickers = {p["ticker"] for p in peers}
    assert tickers == {"AAA", "BBB"}
