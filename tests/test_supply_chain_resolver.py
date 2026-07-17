"""Tests for dynamic supply-chain group resolution (replaces first-match YAML lookup).

All tests inject ``closes_by_ticker`` / ``market_caps`` directly — no network calls,
except the two ``test_live_fetch_*`` tests below, which patch the live-fetch seam
itself (``get_cached_stock_peers`` and ``_batch_fetch_closes_impl``) to exercise the
``if closes_by_ticker is None: ... if fmp_peers is None:`` branch that every other
test bypasses by injecting ``closes_by_ticker`` directly.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from adapters.visualization.analysis.supply_chain_resolver import (
    resolve_supply_chain_group,
)

_RETURNS = [0.02, -0.0098039, 0.0297030, -0.0096154, 0.0291262]


def _compound(start: float, returns: list[float] = _RETURNS) -> list[float]:
    closes = [start]
    for r in returns:
        closes.append(closes[-1] * (1 + r))
    return closes


def test_nvda_resolves_to_leader_not_follower_in_semiconductors_first() -> None:
    """NVDA is a follower in the first YAML match (semiconductors) but a leader in
    ai_infrastructure — only the ai_infrastructure peers have price data, so that's
    the only candidate with enough members to be scored, and it wins on co-movement."""
    closes = {
        "NVDA": _compound(400.0),
        "SMCI": _compound(30.0),
        "DELL": _compound(90.0),
        "HPE": _compound(18.0),
    }
    info = {"sector": "Technology", "industry": "Semiconductors"}
    result = resolve_supply_chain_group(
        "NVDA", info, closes_by_ticker=closes, market_caps={"NVDA": 4.2e12}
    )
    assert result is not None
    assert result["group"] == "ai_infrastructure"
    assert result["_is_leader"] is True
    assert result["co_movement"] == pytest.approx(1.0)
    assert result["provenance"] == "yaml+correlation"


def test_unknown_ticker_returns_none() -> None:
    result = resolve_supply_chain_group(
        "ZZZZ", {}, closes_by_ticker={"ZZZZ": _compound(10.0)}, market_caps={}
    )
    assert result is None


def test_mocked_closes_yield_stable_co_movement() -> None:
    closes = {
        "NVDA": _compound(400.0),
        "SMCI": _compound(30.0),
        "DELL": _compound(90.0),
        "HPE": _compound(18.0),
    }
    info = {"sector": "Technology"}
    r1 = resolve_supply_chain_group(
        "NVDA", info, closes_by_ticker=closes, market_caps={}
    )
    r2 = resolve_supply_chain_group(
        "NVDA", info, closes_by_ticker=closes, market_caps={}
    )
    assert r1 is not None and r2 is not None
    assert r1["co_movement"] == r2["co_movement"] == pytest.approx(1.0)


def test_insufficient_members_with_data_returns_none() -> None:
    """AMAT is a YAML leader in 'semiconductors', but only one peer has price data —
    below the 4-member minimum — and there's no sector/industry pool match either."""
    closes = {"AMAT": _compound(200.0), "LRCX": _compound(700.0)}
    result = resolve_supply_chain_group(
        "AMAT", {}, closes_by_ticker=closes, market_caps={}
    )
    assert result is None


def test_low_comovement_below_threshold_returns_none() -> None:
    closes = {
        "AMAT": _compound(200.0, [0.02, -0.03, 0.01, -0.02, 0.015]),
        "LRCX": _compound(700.0, [-0.01, 0.02, -0.015, 0.03, -0.005]),
        "KLAC": _compound(500.0, [0.015, -0.01, 0.02, -0.03, 0.01]),
        "ASML": _compound(900.0, [-0.02, 0.01, -0.03, 0.02, -0.015]),
    }
    result = resolve_supply_chain_group(
        "AMAT", {}, closes_by_ticker=closes, market_caps={}
    )
    assert result is None


def test_correlation_only_provenance_and_market_cap_leader() -> None:
    """CRM is not in supply_chain.yaml at all — a pure sector/industry correlation
    cluster (from the existing Software - Application peer pool) is the only
    candidate. Highest market cap in the cluster determines leader role."""
    closes = {
        "CRM": _compound(250.0),
        "NOW": _compound(900.0),
        "INTU": _compound(600.0),
        "ADBE": _compound(400.0),
    }
    info = {"industry": "Software - Application"}
    market_caps = {"CRM": 3.0e11, "NOW": 1.8e11, "INTU": 1.7e11, "ADBE": 1.6e11}
    result = resolve_supply_chain_group(
        "CRM", info, closes_by_ticker=closes, market_caps=market_caps
    )
    assert result is not None
    assert result["provenance"] == "correlation_only"
    assert result["_is_leader"] is True


def test_correlation_only_follower_when_not_highest_market_cap() -> None:
    closes = {
        "CRM": _compound(250.0),
        "NOW": _compound(900.0),
        "INTU": _compound(600.0),
        "ADBE": _compound(400.0),
    }
    info = {"industry": "Software - Application"}
    market_caps = {"CRM": 1.0e11, "NOW": 1.8e11, "INTU": 1.7e11, "ADBE": 1.6e11}
    result = resolve_supply_chain_group(
        "CRM", info, closes_by_ticker=closes, market_caps=market_caps
    )
    assert result is not None
    assert result["_is_leader"] is False
    assert "CRM" in result["followers"]


def test_yaml_follower_promoted_to_leader_relocates_out_of_followers() -> None:
    """NVDA is a YAML follower in 'semiconductors', but if it has by far the
    highest market cap in the actual cluster, it should be promoted to leader
    AND moved out of the followers list — not double-counted."""
    closes = {
        "NVDA": _compound(900.0),
        "AMAT": _compound(200.0),
        "LRCX": _compound(700.0),
        "KLAC": _compound(500.0),
    }
    market_caps = {"NVDA": 4.7e12, "AMAT": 4.4e11, "LRCX": 4.1e11, "KLAC": 2.8e11}
    result = resolve_supply_chain_group(
        "NVDA", {}, closes_by_ticker=closes, market_caps=market_caps
    )
    assert result is not None
    assert result["group"] == "semiconductors"
    assert result["_is_leader"] is True
    assert "NVDA" in result["leaders"]
    assert "NVDA" not in result["followers"]


def test_result_has_group_display_and_resolution_score() -> None:
    closes = {
        "NVDA": _compound(400.0),
        "SMCI": _compound(30.0),
        "DELL": _compound(90.0),
        "HPE": _compound(18.0),
    }
    result = resolve_supply_chain_group(
        "NVDA", {}, closes_by_ticker=closes, market_caps={}
    )
    assert result is not None
    assert result["group_display"]
    assert result["resolution_score"] == pytest.approx(result["co_movement"])


def test_fmp_peers_used_as_candidate_when_yaml_and_sector_absent() -> None:
    """FORCEMOT.NS has no YAML entry and no industry/sector pool match (both
    are US-only) — FMP peers are the only candidate source available."""
    closes = {
        "FORCEMOT.NS": _compound(2500.0),
        "ASAHIINDIA.NS": _compound(880.0),
        "EIHOTEL.NS": _compound(340.0),
        "MOTHERSON.NS": _compound(120.0),
    }
    result = resolve_supply_chain_group(
        "FORCEMOT.NS",
        {},
        closes_by_ticker=closes,
        market_caps={},
        fmp_peers=["ASAHIINDIA.NS", "EIHOTEL.NS", "MOTHERSON.NS"],
    )
    assert result is not None
    assert result["group"] == "forcemot.ns_fmp_peers"
    assert result["provenance"] == "correlation_only"


def test_fmp_peers_absent_falls_back_to_none_when_no_other_candidates() -> None:
    result = resolve_supply_chain_group(
        "FORCEMOT.NS",
        {},
        closes_by_ticker={"FORCEMOT.NS": _compound(2500.0)},
        market_caps={},
        fmp_peers=[],
    )
    assert result is None


def test_fmp_peers_below_comovement_threshold_returns_none() -> None:
    closes = {
        "FORCEMOT.NS": _compound(2500.0, [0.02, -0.03, 0.01, -0.02, 0.015]),
        "ASAHIINDIA.NS": _compound(880.0, [-0.01, 0.02, -0.015, 0.03, -0.005]),
        "EIHOTEL.NS": _compound(340.0, [0.015, -0.01, 0.02, -0.03, 0.01]),
        "MOTHERSON.NS": _compound(120.0, [-0.02, 0.01, -0.03, 0.02, -0.015]),
    }
    result = resolve_supply_chain_group(
        "FORCEMOT.NS",
        {},
        closes_by_ticker=closes,
        market_caps={},
        fmp_peers=["ASAHIINDIA.NS", "EIHOTEL.NS", "MOTHERSON.NS"],
    )
    assert result is None


def test_fmp_peers_truncated_to_max_members() -> None:
    from adapters.visualization.analysis.supply_chain_resolver import MAX_MEMBERS

    many_peers = [f"PEER{i}.NS" for i in range(MAX_MEMBERS + 5)]
    closes = {"FORCEMOT.NS": _compound(2500.0)}
    for i, p in enumerate(many_peers):
        closes[p] = _compound(100.0 + i)
    result = resolve_supply_chain_group(
        "FORCEMOT.NS", {}, closes_by_ticker=closes, market_caps={}, fmp_peers=many_peers
    )
    assert result is not None
    assert len(result["followers"]) + len(result["leaders"]) - 1 <= MAX_MEMBERS


def test_live_fetch_forwards_fmp_peers_into_candidate_pool() -> None:
    """When closes_by_ticker is None (the real dashboard code path) and
    fmp_peers isn't explicitly passed, resolve_supply_chain_group must fetch
    it live via get_cached_stock_peers and use it as a candidate — this is
    the seam every other test in this file bypasses by injecting
    closes_by_ticker directly."""
    closes = {
        "FORCEMOT.NS": _compound(2500.0),
        "ASAHIINDIA.NS": _compound(880.0),
        "EIHOTEL.NS": _compound(340.0),
        "MOTHERSON.NS": _compound(120.0),
    }
    with (
        patch(
            "adapters.data.fmp_adapter.get_cached_stock_peers",
            return_value=["ASAHIINDIA.NS", "EIHOTEL.NS", "MOTHERSON.NS"],
        ) as mock_get_peers,
        patch("adapters.data.sqlite_store.SQLiteStore"),
        patch(
            "adapters.visualization.price_cache._batch_fetch_closes_impl",
            return_value=closes,
        ),
    ):
        result = resolve_supply_chain_group("FORCEMOT.NS", {})

    assert result is not None
    assert result["group"] == "forcemot.ns_fmp_peers"
    mock_get_peers.assert_called_once()


def test_live_fetch_degrades_to_empty_peers_on_exception() -> None:
    """A live FMP fetch failure (network error, DB error, anything) must
    degrade to an empty peers list — never propagate and crash the resolver."""
    closes = {"FORCEMOT.NS": _compound(2500.0)}
    with (
        patch(
            "adapters.data.fmp_adapter.get_cached_stock_peers",
            side_effect=RuntimeError("boom"),
        ),
        patch("adapters.data.sqlite_store.SQLiteStore"),
        patch(
            "adapters.visualization.price_cache._batch_fetch_closes_impl",
            return_value=closes,
        ),
    ):
        result = resolve_supply_chain_group("FORCEMOT.NS", {})

    assert result is None  # no candidates clear the bar — an honest gap, not a crash
