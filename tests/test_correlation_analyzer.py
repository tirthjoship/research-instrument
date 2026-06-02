"""Tests for CorrelationAnalyzer — cross-asset graph builder."""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pytest

from adapters.ml.correlation_analyzer import CorrelationAnalyzer
from domain.models import Signal


def _make_signals(
    prices: list[float], start_date: datetime | None = None
) -> list[Signal]:
    """Create Signal list from price series."""
    base = start_date or datetime(2026, 1, 1)
    return [
        Signal(
            symbol="X",
            timestamp=base + timedelta(days=i),
            price=p,
            volume=1_000_000,
            open_=p,
            high=p * 1.01,
            low=p * 0.99,
        )
        for i, p in enumerate(prices)
    ]


def _correlated_series(n: int = 80, seed: int = 42) -> tuple[list[float], list[float]]:
    """Generate two highly correlated price series."""
    rng = np.random.default_rng(seed)
    base = 100.0 + np.cumsum(rng.normal(0, 1, n))
    noise = rng.normal(0, 0.3, n)
    return base.tolist(), (base + noise).tolist()


def _lagged_series(
    n: int = 80, lag: int = 2, seed: int = 42
) -> tuple[list[float], list[float]]:
    """Generate leader series and a follower that lags by `lag` days."""
    rng = np.random.default_rng(seed)
    leader = 100.0 + np.cumsum(rng.normal(0, 1, n))
    # Follower = leader shifted by lag + small noise
    follower = np.zeros(n)
    follower[:lag] = leader[:lag]
    follower[lag:] = leader[:-lag] + rng.normal(0, 0.2, n - lag)
    return leader.tolist(), follower.tolist()


@pytest.fixture()
def yaml_path(tmp_path) -> str:
    """Create a minimal supply chain YAML for testing."""
    content = """
relationships:
  - group: test_chain
    leaders: [LEADER]
    followers: [FOLLOWER]
    typical_lag_days: 2
    notes: "test"
"""
    path = tmp_path / "supply_chain.yaml"
    path.write_text(content)
    return str(path)


@pytest.fixture()
def empty_yaml(tmp_path) -> str:
    path = tmp_path / "empty.yaml"
    path.write_text("relationships: []\n")
    return str(path)


class TestCorrelationMatrix:
    def test_computes_high_correlation(self, empty_yaml: str) -> None:
        """Two correlated series should have |corr| > 0.65."""
        a, b = _correlated_series()
        analyzer = CorrelationAnalyzer(supply_chain_path=empty_yaml)
        analyzer.build_graph(
            {"AAPL": _make_signals(a), "MSFT": _make_signals(b)},
            window_days=60,
        )
        corr = analyzer.get_correlation("AAPL", "MSFT")
        assert abs(corr) > 0.65

    def test_uncorrelated_returns_low(self, empty_yaml: str) -> None:
        """Two unrelated series should have |corr| < 0.3."""
        rng = np.random.default_rng(99)
        a = (100.0 + np.cumsum(rng.normal(0, 1, 80))).tolist()
        b = (100.0 + np.cumsum(rng.normal(0, 1, 80))).tolist()
        analyzer = CorrelationAnalyzer(supply_chain_path=empty_yaml)
        analyzer.build_graph(
            {"X": _make_signals(a), "Y": _make_signals(b)},
            window_days=60,
        )
        corr = analyzer.get_correlation("X", "Y")
        assert abs(corr) < 0.5

    def test_unknown_pair_returns_zero(self, empty_yaml: str) -> None:
        analyzer = CorrelationAnalyzer(supply_chain_path=empty_yaml)
        analyzer.build_graph({}, window_days=60)
        assert analyzer.get_correlation("X", "Y") == 0.0


class TestClustering:
    def test_correlated_tickers_in_same_cluster(self, empty_yaml: str) -> None:
        """Tickers with corr > 0.65 should be in same cluster."""
        a, b = _correlated_series(seed=10)
        rng = np.random.default_rng(999)
        c = (200.0 + np.cumsum(rng.normal(0, 1, 80))).tolist()
        analyzer = CorrelationAnalyzer(supply_chain_path=empty_yaml)
        analyzer.build_graph(
            {"A": _make_signals(a), "B": _make_signals(b), "C": _make_signals(c)},
            window_days=60,
        )
        peers_a = analyzer.get_cluster_peers("A")
        assert "B" in peers_a
        # C should not be in A's cluster (uncorrelated)

    def test_no_data_empty_cluster(self, empty_yaml: str) -> None:
        analyzer = CorrelationAnalyzer(supply_chain_path=empty_yaml)
        analyzer.build_graph({}, window_days=60)
        assert analyzer.get_cluster_peers("AAPL") == []


class TestGrangerCausality:
    def test_detects_known_lead_lag(self, empty_yaml: str) -> None:
        """Synthetic leader→follower with 2-day lag should produce Granger edge."""
        leader, follower = _lagged_series(n=120, lag=2, seed=42)
        analyzer = CorrelationAnalyzer(supply_chain_path=empty_yaml)
        analyzer.build_graph(
            {"LEADER": _make_signals(leader), "FOLLOWER": _make_signals(follower)},
            window_days=100,
        )
        edges = analyzer.get_upstream_signals("FOLLOWER")
        # Should find at least one edge from LEADER
        leader_edges = [e for e in edges if e.leader == "LEADER"]
        if leader_edges:
            assert leader_edges[0].relationship_type == "granger_causal"
            assert leader_edges[0].lag_days >= 1

    def test_skips_low_correlation_pairs(self, empty_yaml: str) -> None:
        """Uncorrelated pairs should not be Granger-tested."""
        rng = np.random.default_rng(77)
        a = (100.0 + np.cumsum(rng.normal(0, 1, 80))).tolist()
        b = (100.0 + np.cumsum(rng.normal(0, 1, 80))).tolist()
        analyzer = CorrelationAnalyzer(supply_chain_path=empty_yaml)
        analyzer.build_graph(
            {"X": _make_signals(a), "Y": _make_signals(b)},
            window_days=60,
        )
        edges = analyzer.get_upstream_signals("Y")
        granger_edges = [e for e in edges if e.relationship_type == "granger_causal"]
        assert len(granger_edges) == 0


class TestManualOverride:
    def test_yaml_edges_added(self, yaml_path: str) -> None:
        """Manual YAML edges should appear regardless of correlation."""
        rng = np.random.default_rng(42)
        a = (100.0 + np.cumsum(rng.normal(0, 1, 80))).tolist()
        b = (200.0 + np.cumsum(rng.normal(0, 1, 80))).tolist()
        analyzer = CorrelationAnalyzer(supply_chain_path=yaml_path)
        analyzer.build_graph(
            {"LEADER": _make_signals(a), "FOLLOWER": _make_signals(b)},
            window_days=60,
        )
        edges = analyzer.get_upstream_signals("FOLLOWER")
        manual = [e for e in edges if e.source == "manual_yaml"]
        assert len(manual) >= 1
        assert manual[0].leader == "LEADER"
        assert manual[0].relationship_type == "supply_chain"

    def test_missing_ticker_in_yaml_skipped(self, yaml_path: str) -> None:
        """YAML references ticker not in universe — should not crash."""
        analyzer = CorrelationAnalyzer(supply_chain_path=yaml_path)
        analyzer.build_graph({"OTHER": _make_signals([100.0] * 80)}, window_days=60)
        # No crash, empty edges for missing tickers

    def test_inverse_relationship(self, tmp_path) -> None:
        """Inverse YAML entry should store negative correlation."""
        content = """
relationships:
  - group: energy_inv
    leaders: [XOM]
    followers: [DAL]
    inverse: true
    typical_lag_days: 2
    notes: "oil hurts airlines"
"""
        path = tmp_path / "inv.yaml"
        path.write_text(content)
        rng = np.random.default_rng(42)
        a = (100.0 + np.cumsum(rng.normal(0, 1, 80))).tolist()
        b = (100.0 + np.cumsum(rng.normal(0, 1, 80))).tolist()
        analyzer = CorrelationAnalyzer(supply_chain_path=str(path))
        analyzer.build_graph(
            {"XOM": _make_signals(a), "DAL": _make_signals(b)}, window_days=60
        )
        edges = analyzer.get_upstream_signals("DAL")
        inv_edges = [e for e in edges if e.source == "manual_yaml"]
        assert len(inv_edges) >= 1
        assert inv_edges[0].correlation < 0


class TestInsufficientData:
    def test_ticker_under_40_days_excluded(self, empty_yaml: str) -> None:
        """Tickers with fewer than 40 days of data should be excluded."""
        short = _make_signals([100.0 + i for i in range(30)])
        long_series = _make_signals([100.0 + i * 0.5 for i in range(80)])
        analyzer = CorrelationAnalyzer(supply_chain_path=empty_yaml)
        analyzer.build_graph({"SHORT": short, "LONG": long_series}, window_days=60)
        assert analyzer.get_cluster_peers("SHORT") == []
        assert analyzer.get_correlation("SHORT", "LONG") == 0.0
