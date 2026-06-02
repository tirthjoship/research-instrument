"""Fake CrossAssetPort for testing."""

from __future__ import annotations

from domain.models import CorrelationEdge, Signal


class FakeCrossAsset:
    """In-memory CrossAssetPort for testing."""

    def __init__(self) -> None:
        self._edges: dict[str, list[CorrelationEdge]] = {}
        self._clusters: dict[str, list[str]] = {}
        self._correlations: dict[tuple[str, str], float] = {}

    def build_graph(
        self,
        signals_by_ticker: dict[str, list[Signal]],
        window_days: int = 60,
    ) -> None:
        pass  # pre-populated in tests

    def add_edge(self, edge: CorrelationEdge) -> None:
        self._edges.setdefault(edge.follower, []).append(edge)

    def set_cluster(self, ticker: str, peers: list[str]) -> None:
        self._clusters[ticker] = peers

    def set_correlation(self, a: str, b: str, corr: float) -> None:
        self._correlations[(a, b)] = corr
        self._correlations[(b, a)] = corr

    def get_upstream_signals(self, ticker: str) -> list[CorrelationEdge]:
        return self._edges.get(ticker, [])

    def get_cluster_peers(self, ticker: str) -> list[str]:
        return self._clusters.get(ticker, [])

    def get_correlation(self, ticker_a: str, ticker_b: str) -> float:
        return self._correlations.get((ticker_a, ticker_b), 0.0)
