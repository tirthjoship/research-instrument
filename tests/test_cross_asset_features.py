"""Tests for CrossAssetFeatureEngineer — 8 cross-asset features."""

from __future__ import annotations

import math
from datetime import datetime, timedelta

import pytest

from adapters.ml.cross_asset_features import (
    CROSS_ASSET_FEATURE_NAMES,
    CrossAssetFeatureEngineer,
)
from domain.models import CorrelationEdge, Signal
from tests.fakes.fake_cross_asset import FakeCrossAsset


def _make_signals(
    symbol: str, prices: list[float], start: datetime | None = None
) -> list[Signal]:
    base = start or datetime(2026, 5, 1)
    return [
        Signal(
            symbol=symbol,
            timestamp=base + timedelta(days=i),
            price=p,
            volume=1_000_000,
            open_=p,
            high=p * 1.01,
            low=p * 0.99,
        )
        for i, p in enumerate(prices)
    ]


@pytest.fixture()
def fake() -> FakeCrossAsset:
    return FakeCrossAsset()


@pytest.fixture()
def eng(fake: FakeCrossAsset) -> CrossAssetFeatureEngineer:
    return CrossAssetFeatureEngineer(cross_asset=fake)


class TestFeatureNames:
    def test_count(self) -> None:
        assert len(CROSS_ASSET_FEATURE_NAMES) == 8

    def test_expected_names(self) -> None:
        expected = {
            "upstream_leader_return_1d",
            "upstream_leader_return_5d",
            "cluster_momentum_1w",
            "leader_follower_lag_signal",
            "supply_chain_divergence",
            "correlation_regime_shift",
            "thematic_activation",
            "granger_lead_signal",
        }
        assert set(CROSS_ASSET_FEATURE_NAMES) == expected


class TestUpstreamFeatures:
    def test_upstream_leader_return_1d(
        self, fake: FakeCrossAsset, eng: CrossAssetFeatureEngineer
    ) -> None:
        """Leader with +5% 1d return → positive upstream signal."""
        fake.add_edge(
            CorrelationEdge(
                leader="NVDA",
                follower="SMCI",
                correlation=0.85,
                lag_days=1,
                relationship_type="supply_chain",
                source="manual_yaml",
            )
        )
        # NVDA: last price 105, previous 100 → +5% 1d return
        nvda_prices = [100.0] * 28 + [100.0, 105.0]
        smci_prices = [50.0] * 30
        signals_by_ticker = {
            "NVDA": _make_signals("NVDA", nvda_prices),
            "SMCI": _make_signals("SMCI", smci_prices),
        }
        result = eng.compute("SMCI", signals_by_ticker["SMCI"], signals_by_ticker)
        assert result["upstream_leader_return_1d"] > 0

    def test_no_upstream_returns_nan(
        self, fake: FakeCrossAsset, eng: CrossAssetFeatureEngineer
    ) -> None:
        """Ticker with no upstream leaders → NaN."""
        signals = _make_signals("AAPL", [100.0] * 30)
        result = eng.compute("AAPL", signals, {"AAPL": signals})
        assert math.isnan(result["upstream_leader_return_1d"])
        assert math.isnan(result["upstream_leader_return_5d"])


class TestClusterMomentum:
    def test_cluster_momentum_positive(
        self, fake: FakeCrossAsset, eng: CrossAssetFeatureEngineer
    ) -> None:
        """Cluster peers all up → positive cluster momentum."""
        fake.set_cluster("AMD", ["NVDA", "INTC"])
        # All peers have positive 5d returns
        amd_signals = _make_signals("AMD", [100.0] * 30)
        nvda_signals = _make_signals("NVDA", [100.0] * 25 + [101, 102, 103, 104, 105])
        intc_signals = _make_signals("INTC", [50.0] * 25 + [51, 52, 52, 53, 53])
        signals_by_ticker = {
            "AMD": amd_signals,
            "NVDA": nvda_signals,
            "INTC": intc_signals,
        }
        result = eng.compute("AMD", amd_signals, signals_by_ticker)
        assert result["cluster_momentum_1w"] > 0

    def test_no_cluster_returns_nan(
        self, fake: FakeCrossAsset, eng: CrossAssetFeatureEngineer
    ) -> None:
        signals = _make_signals("SOLO", [100.0] * 30)
        result = eng.compute("SOLO", signals, {"SOLO": signals})
        assert math.isnan(result["cluster_momentum_1w"])


class TestLeaderFollowerLag:
    def test_leader_moved_follower_hasnt(
        self, fake: FakeCrossAsset, eng: CrossAssetFeatureEngineer
    ) -> None:
        """Leader moved >2% recently, follower flat → positive lag signal."""
        fake.add_edge(
            CorrelationEdge(
                leader="AMAT",
                follower="AMD",
                correlation=0.8,
                lag_days=2,
                relationship_type="granger_causal",
                source="computed",
            )
        )
        # AMAT moved +5% 2 days ago, AMD flat
        amat_prices = [100.0] * 27 + [100.0, 105.0, 105.0]
        amd_prices = [80.0] * 30
        signals_by_ticker = {
            "AMAT": _make_signals("AMAT", amat_prices),
            "AMD": _make_signals("AMD", amd_prices),
        }
        result = eng.compute("AMD", signals_by_ticker["AMD"], signals_by_ticker)
        assert result["leader_follower_lag_signal"] > 0


class TestThematicActivation:
    def test_activation_fires_when_3_plus_move(
        self, fake: FakeCrossAsset, eng: CrossAssetFeatureEngineer
    ) -> None:
        """More than 3 cluster peers moved same direction >1% → activation = 1.0."""
        fake.set_cluster("AMD", ["NVDA", "INTC", "MU", "AVGO"])
        base = [100.0] * 29
        signals_by_ticker = {
            "AMD": _make_signals("AMD", base + [100.0]),
            "NVDA": _make_signals("NVDA", base + [102.0]),  # +2%
            "INTC": _make_signals("INTC", base + [101.5]),  # +1.5%
            "MU": _make_signals("MU", base + [103.0]),  # +3%
            "AVGO": _make_signals("AVGO", base + [101.2]),  # +1.2%
        }
        result = eng.compute("AMD", signals_by_ticker["AMD"], signals_by_ticker)
        assert result["thematic_activation"] == 1.0

    def test_no_activation_when_few_move(
        self, fake: FakeCrossAsset, eng: CrossAssetFeatureEngineer
    ) -> None:
        """Fewer than 3 peers moved → activation = 0.0."""
        fake.set_cluster("AMD", ["NVDA", "INTC"])
        base = [100.0] * 29
        signals_by_ticker = {
            "AMD": _make_signals("AMD", base + [100.0]),
            "NVDA": _make_signals("NVDA", base + [102.0]),
            "INTC": _make_signals("INTC", base + [100.0]),  # flat
        }
        result = eng.compute("AMD", signals_by_ticker["AMD"], signals_by_ticker)
        assert result["thematic_activation"] == 0.0


class TestGrangerLeadSignal:
    def test_granger_leader_signal(
        self, fake: FakeCrossAsset, eng: CrossAssetFeatureEngineer
    ) -> None:
        """Granger-significant leader moved → positive signal."""
        fake.add_edge(
            CorrelationEdge(
                leader="NVDA",
                follower="SMCI",
                correlation=0.9,
                lag_days=1,
                relationship_type="granger_causal",
                source="computed",
            )
        )
        # NVDA moved +3% 1 day ago
        nvda_prices = [100.0] * 28 + [100.0, 103.0]
        smci_prices = [50.0] * 30
        signals_by_ticker = {
            "NVDA": _make_signals("NVDA", nvda_prices),
            "SMCI": _make_signals("SMCI", smci_prices),
        }
        result = eng.compute("SMCI", signals_by_ticker["SMCI"], signals_by_ticker)
        assert result["granger_lead_signal"] > 0

    def test_no_granger_leaders_returns_zero(
        self, fake: FakeCrossAsset, eng: CrossAssetFeatureEngineer
    ) -> None:
        """No Granger leaders → 0.0 (not NaN)."""
        signals = _make_signals("SOLO", [100.0] * 30)
        result = eng.compute("SOLO", signals, {"SOLO": signals})
        assert result["granger_lead_signal"] == 0.0


class TestTickerNotInGraph:
    def test_all_nan_for_unknown_ticker(
        self, fake: FakeCrossAsset, eng: CrossAssetFeatureEngineer
    ) -> None:
        signals = _make_signals("UNKNOWN", [100.0] * 30)
        result = eng.compute("UNKNOWN", signals, {"UNKNOWN": signals})
        for name in CROSS_ASSET_FEATURE_NAMES:
            if name == "granger_lead_signal":
                assert result[name] == 0.0
            elif name == "thematic_activation":
                assert result[name] == 0.0
            else:
                assert math.isnan(result[name]), f"{name} should be NaN"
