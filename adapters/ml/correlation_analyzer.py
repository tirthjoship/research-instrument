"""CorrelationAnalyzer — builds cross-asset correlation graph.

Implements CrossAssetPort. Combines auto-discovered correlations
(Pearson + hierarchical clustering + Granger causality) with
manual supply chain overrides from YAML config.
"""

from __future__ import annotations

from pathlib import Path

import networkx as nx
import numpy as np
import yaml
from loguru import logger
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

from domain.models import CorrelationEdge, Signal


class CorrelationAnalyzer:
    """Build and query cross-asset correlation graph."""

    def __init__(
        self, supply_chain_path: str = "config/relationships/supply_chain.yaml"
    ) -> None:
        self._yaml_path = supply_chain_path
        self._graph: nx.DiGraph = nx.DiGraph()
        self._corr_matrix: dict[tuple[str, str], float] = {}
        self._clusters: dict[str, list[str]] = {}
        self._tickers: list[str] = []

    def build_graph(
        self,
        signals_by_ticker: dict[str, list[Signal]],
        window_days: int = 60,
    ) -> None:
        """Build correlation graph from price signals."""
        self._graph = nx.DiGraph()
        self._corr_matrix = {}
        self._clusters = {}

        # 1. Extract close prices, filter tickers with insufficient data
        prices, tickers = self._extract_prices(signals_by_ticker, min_days=40)
        self._tickers = tickers

        if len(tickers) < 2:
            self._merge_manual_overrides(set(signals_by_ticker.keys()))
            return

        # 2. Compute correlation matrix
        corr_matrix = np.corrcoef(prices)
        for i, t1 in enumerate(tickers):
            for j, t2 in enumerate(tickers):
                if i != j:
                    self._corr_matrix[(t1, t2)] = float(corr_matrix[i, j])

        # 3. Hierarchical clustering
        self._compute_clusters(corr_matrix, tickers)

        # 4. Granger causality on high-correlation pairs
        self._run_granger(prices, tickers, corr_matrix, window_days)

        # 5. Add auto-correlation edges for high-corr pairs
        for i in range(len(tickers)):
            for j in range(i + 1, len(tickers)):
                corr = float(corr_matrix[i, j])
                if abs(corr) > 0.65:
                    edge = CorrelationEdge(
                        leader=tickers[i],
                        follower=tickers[j],
                        correlation=corr,
                        lag_days=0,
                        relationship_type="auto_correlation",
                        source="computed",
                    )
                    self._graph.add_edge(tickers[i], tickers[j], edge=edge)

        # 6. Merge manual overrides
        self._merge_manual_overrides(set(signals_by_ticker.keys()))

    def get_upstream_signals(self, ticker: str) -> list[CorrelationEdge]:
        """Return all incoming edges (predecessors → ticker)."""
        edges: list[CorrelationEdge] = []
        if ticker not in self._graph:
            return edges
        for pred in self._graph.predecessors(ticker):
            data = self._graph.edges[pred, ticker]
            if "edge" in data:
                edges.append(data["edge"])
        return edges

    def get_cluster_peers(self, ticker: str) -> list[str]:
        """Return tickers in the same hierarchical cluster."""
        return self._clusters.get(ticker, [])

    def get_correlation(self, ticker_a: str, ticker_b: str) -> float:
        """Return pairwise correlation (0.0 if unknown)."""
        return self._corr_matrix.get((ticker_a, ticker_b), 0.0)

    # --- Private methods ---

    def _extract_prices(
        self, signals_by_ticker: dict[str, list[Signal]], min_days: int
    ) -> tuple[np.ndarray, list[str]]:
        """Extract aligned close price matrix. Returns (prices_array, ticker_list)."""
        valid: dict[str, list[float]] = {}
        for ticker, sigs in signals_by_ticker.items():
            if len(sigs) >= min_days:
                valid[ticker] = [
                    s.price for s in sorted(sigs, key=lambda s: s.timestamp)
                ]

        if not valid:
            return np.array([]), []

        # Align to shortest length
        min_len = min(len(v) for v in valid.values())
        tickers = sorted(valid.keys())
        prices = np.array([valid[t][-min_len:] for t in tickers])

        # Use returns instead of raw prices for correlation
        returns = np.diff(prices, axis=1) / prices[:, :-1]
        # Replace any inf/nan with 0
        returns = np.nan_to_num(returns, nan=0.0, posinf=0.0, neginf=0.0)

        return returns, tickers

    def _compute_clusters(self, corr_matrix: np.ndarray, tickers: list[str]) -> None:
        """Hierarchical clustering using Ward linkage."""
        n = len(tickers)
        if n < 2:
            return

        # Distance = 1 - |correlation|
        dist_matrix = 1.0 - np.abs(corr_matrix)
        np.fill_diagonal(dist_matrix, 0.0)

        # Ensure symmetry and valid range (floating-point can break symmetry)
        dist_matrix = (dist_matrix + dist_matrix.T) / 2.0
        dist_matrix = np.clip(dist_matrix, 0.0, 1.0)
        np.fill_diagonal(dist_matrix, 0.0)
        condensed = squareform(dist_matrix, checks=False)

        try:
            Z = linkage(condensed, method="ward")
            # Cut at threshold: distance < 0.35 means |corr| > 0.65
            labels = fcluster(Z, t=0.35, criterion="distance")
        except Exception:
            logger.debug("Clustering failed, skipping")
            return

        # Group tickers by cluster label
        cluster_groups: dict[int, list[str]] = {}
        for ticker, label in zip(tickers, labels):
            cluster_groups.setdefault(int(label), []).append(ticker)

        # Store: each ticker maps to its peers (excluding itself)
        for members in cluster_groups.values():
            if len(members) > 1:
                for ticker in members:
                    self._clusters[ticker] = [t for t in members if t != ticker]

    def _run_granger(
        self,
        returns: np.ndarray,
        tickers: list[str],
        corr_matrix: np.ndarray,
        window_days: int,
    ) -> None:
        """Run Granger causality on pairs with |corr| > 0.65."""
        try:
            from statsmodels.tsa.stattools import grangercausalitytests
        except ImportError:
            logger.warning("statsmodels not installed, skipping Granger causality")
            return

        n = len(tickers)
        candidates: list[tuple[int, int, float]] = []
        for i in range(n):
            for j in range(n):
                if i != j and abs(float(corr_matrix[i, j])) > 0.65:
                    candidates.append((i, j, float(corr_matrix[i, j])))

        if not candidates:
            return

        # Run Granger tests
        results: list[tuple[str, str, float, int, float]] = (
            []
        )  # leader, follower, corr, lag, p
        for i, j, corr in candidates:
            try:
                # Test if ticker i Granger-causes ticker j
                data = np.column_stack([returns[j], returns[i]])
                if len(data) < 15:
                    continue
                gc = grangercausalitytests(data, maxlag=5, verbose=False)
                # Find minimum p-value across lags
                min_p = 1.0
                best_lag = 1
                for lag in range(1, 6):
                    if lag in gc:
                        p_val = gc[lag][0]["ssr_ftest"][1]
                        if p_val < min_p:
                            min_p = p_val
                            best_lag = lag
                results.append((tickers[i], tickers[j], corr, best_lag, min_p))
            except Exception:
                continue

        if not results:
            return

        # Benjamini-Hochberg correction
        p_values = [r[4] for r in results]
        adjusted = self._bh_correction(p_values)

        for (leader, follower, corr, lag, _), adj_p in zip(results, adjusted):
            if adj_p < 0.05:
                edge = CorrelationEdge(
                    leader=leader,
                    follower=follower,
                    correlation=corr,
                    lag_days=lag,
                    relationship_type="granger_causal",
                    source="computed",
                )
                self._graph.add_edge(leader, follower, edge=edge)

    @staticmethod
    def _bh_correction(p_values: list[float]) -> list[float]:
        """Benjamini-Hochberg FDR correction."""
        n = len(p_values)
        if n == 0:
            return []
        indexed = sorted(enumerate(p_values), key=lambda x: x[1])
        adjusted = [0.0] * n
        prev = 1.0
        for rank_idx in range(n - 1, -1, -1):
            orig_idx, p = indexed[rank_idx]
            rank = rank_idx + 1
            adj = min(prev, p * n / rank)
            adjusted[orig_idx] = adj
            prev = adj
        return adjusted

    def _merge_manual_overrides(self, universe: set[str]) -> None:
        """Load supply chain YAML and add manual edges."""
        path = Path(self._yaml_path)
        if not path.exists():
            logger.debug(f"Supply chain YAML not found: {path}")
            return

        with open(path) as f:
            data = yaml.safe_load(f)

        if not data or "relationships" not in data:
            return

        for group in data["relationships"]:
            leaders = group.get("leaders", [])
            followers = group.get("followers", [])
            lag = group.get("typical_lag_days", 1)
            inverse = group.get("inverse", False)

            for leader in leaders:
                if leader not in universe:
                    continue
                for follower in followers:
                    if follower not in universe:
                        continue
                    # Compute actual correlation if available, else use default
                    corr = self._corr_matrix.get((leader, follower), 0.5)
                    if inverse:
                        corr = -abs(corr) if corr > 0 else corr

                    edge = CorrelationEdge(
                        leader=leader,
                        follower=follower,
                        correlation=round(corr, 4),
                        lag_days=min(lag, 5),
                        relationship_type="supply_chain",
                        source="manual_yaml",
                    )
                    # Manual overrides auto-discovered edges
                    self._graph.add_edge(leader, follower, edge=edge)
