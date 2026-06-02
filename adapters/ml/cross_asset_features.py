"""CrossAssetFeatureEngineer — extract 8 cross-asset features from correlation graph.

Features capture inter-stock signal propagation: upstream leader returns,
cluster momentum, lead-lag signals, supply chain divergence, and more.
"""

from __future__ import annotations

import math
from typing import Any

from domain.models import Signal

CROSS_ASSET_FEATURE_NAMES: list[str] = [
    "upstream_leader_return_1d",
    "upstream_leader_return_5d",
    "cluster_momentum_1w",
    "leader_follower_lag_signal",
    "supply_chain_divergence",
    "correlation_regime_shift",
    "thematic_activation",
    "granger_lead_signal",
]


class CrossAssetFeatureEngineer:
    """Extract cross-asset features from a CrossAssetPort graph."""

    def __init__(self, cross_asset: Any) -> None:
        self._graph = cross_asset

    def compute(
        self,
        ticker: str,
        signals: list[Signal],
        signals_by_ticker: dict[str, list[Signal]],
    ) -> dict[str, float]:
        """Compute all 8 cross-asset features for a ticker."""
        features: dict[str, float] = {}

        upstream = self._graph.get_upstream_signals(ticker)
        peers = self._graph.get_cluster_peers(ticker)

        # 1-2. Upstream leader returns (1d and 5d)
        features["upstream_leader_return_1d"] = self._upstream_return(
            upstream, signals_by_ticker, days=1
        )
        features["upstream_leader_return_5d"] = self._upstream_return(
            upstream, signals_by_ticker, days=5
        )

        # 3. Cluster momentum (mean 5d return of peers)
        features["cluster_momentum_1w"] = self._cluster_momentum(
            peers, signals_by_ticker
        )

        # 4. Leader-follower lag signal
        features["leader_follower_lag_signal"] = self._lag_signal(
            upstream, signals, signals_by_ticker
        )

        # 5. Supply chain divergence
        features["supply_chain_divergence"] = self._supply_chain_divergence(
            ticker, signals, upstream, signals_by_ticker
        )

        # 6. Correlation regime shift
        features["correlation_regime_shift"] = self._regime_shift(
            ticker, peers, signals_by_ticker
        )

        # 7. Thematic activation
        features["thematic_activation"] = self._thematic_activation(
            peers, signals_by_ticker
        )

        # 8. Granger lead signal
        features["granger_lead_signal"] = self._granger_signal(
            upstream, signals_by_ticker
        )

        return features

    def _get_return(self, sigs: list[Signal], days: int) -> float:
        """Compute return over last `days` trading days."""
        if len(sigs) < days + 1:
            return float("nan")
        return (sigs[-1].price / sigs[-(days + 1)].price) - 1.0

    def _upstream_return(
        self, upstream: list[Any], signals_by_ticker: dict[str, list[Signal]], days: int
    ) -> float:
        """Weighted avg return of upstream leaders."""
        if not upstream:
            return float("nan")

        total_weight = 0.0
        weighted_return = 0.0
        for edge in upstream:
            leader_sigs = signals_by_ticker.get(edge.leader, [])
            ret = self._get_return(leader_sigs, days)
            if not math.isnan(ret):
                w = abs(edge.correlation)
                weighted_return += ret * w
                total_weight += w

        if total_weight == 0:
            return float("nan")
        return weighted_return / total_weight

    def _cluster_momentum(
        self, peers: list[str], signals_by_ticker: dict[str, list[Signal]]
    ) -> float:
        """Mean 5d return of cluster peers."""
        if not peers:
            return float("nan")

        returns: list[float] = []
        for peer in peers:
            sigs = signals_by_ticker.get(peer, [])
            ret = self._get_return(sigs, 5)
            if not math.isnan(ret):
                returns.append(ret)

        if not returns:
            return float("nan")
        return sum(returns) / len(returns)

    def _lag_signal(
        self,
        upstream: list[Any],
        ticker_signals: list[Signal],
        signals_by_ticker: dict[str, list[Signal]],
    ) -> float:
        """Leader moved >2% in past lag_days, follower hasn't moved >1%."""
        if not upstream:
            return float("nan")

        ticker_1d = self._get_return(ticker_signals, 1)
        if math.isnan(ticker_1d):
            return float("nan")

        max_signal = 0.0
        for edge in upstream:
            leader_sigs = signals_by_ticker.get(edge.leader, [])
            lag = max(edge.lag_days, 1)
            leader_ret = self._get_return(leader_sigs, lag)
            if (
                not math.isnan(leader_ret)
                and abs(leader_ret) > 0.02
                and abs(ticker_1d) < 0.01
            ):
                signal = leader_ret * edge.correlation
                if abs(signal) > abs(max_signal):
                    max_signal = signal

        return max_signal

    def _supply_chain_divergence(
        self,
        ticker: str,
        signals: list[Signal],
        upstream: list[Any],
        signals_by_ticker: dict[str, list[Signal]],
    ) -> float:
        """Ticker's 5d return minus weighted avg of upstream group's 5d return."""
        ticker_ret = self._get_return(signals, 5)
        upstream_ret = self._upstream_return(upstream, signals_by_ticker, days=5)

        if math.isnan(ticker_ret) or math.isnan(upstream_ret):
            return float("nan")
        return ticker_ret - upstream_ret

    def _regime_shift(
        self,
        ticker: str,
        peers: list[str],
        signals_by_ticker: dict[str, list[Signal]],
    ) -> float:
        """Current 20d avg pairwise corr with peers minus 60d baseline."""
        if not peers:
            return float("nan")

        ticker_sigs = signals_by_ticker.get(ticker, [])
        if len(ticker_sigs) < 60:
            return float("nan")

        ticker_prices = [s.price for s in ticker_sigs]

        corrs_20d: list[float] = []
        corrs_60d: list[float] = []

        for peer in peers:
            peer_sigs = signals_by_ticker.get(peer, [])
            if len(peer_sigs) < 60:
                continue
            peer_prices = [s.price for s in peer_sigs]

            # Align lengths
            min_len = min(len(ticker_prices), len(peer_prices))
            tp = ticker_prices[-min_len:]
            pp = peer_prices[-min_len:]

            if min_len >= 60:
                # 60d correlation (baseline)
                import numpy as np

                t_ret_60 = np.diff(tp[-60:]) / np.array(tp[-60:])[:-1]
                p_ret_60 = np.diff(pp[-60:]) / np.array(pp[-60:])[:-1]
                t_ret_60 = np.nan_to_num(t_ret_60)
                p_ret_60 = np.nan_to_num(p_ret_60)
                if np.std(t_ret_60) > 0 and np.std(p_ret_60) > 0:
                    corr_60 = float(np.corrcoef(t_ret_60, p_ret_60)[0, 1])
                    corrs_60d.append(corr_60)

            if min_len >= 20:
                import numpy as np

                t_ret_20 = np.diff(tp[-20:]) / np.array(tp[-20:])[:-1]
                p_ret_20 = np.diff(pp[-20:]) / np.array(pp[-20:])[:-1]
                t_ret_20 = np.nan_to_num(t_ret_20)
                p_ret_20 = np.nan_to_num(p_ret_20)
                if np.std(t_ret_20) > 0 and np.std(p_ret_20) > 0:
                    corr_20 = float(np.corrcoef(t_ret_20, p_ret_20)[0, 1])
                    corrs_20d.append(corr_20)

        if not corrs_20d or not corrs_60d:
            return float("nan")

        avg_20 = sum(corrs_20d) / len(corrs_20d)
        avg_60 = sum(corrs_60d) / len(corrs_60d)
        return avg_20 - avg_60

    def _thematic_activation(
        self, peers: list[str], signals_by_ticker: dict[str, list[Signal]]
    ) -> float:
        """1.0 if >3 peers moved same direction >1% today, else 0.0."""
        if not peers:
            return 0.0

        up_count = 0
        down_count = 0
        for peer in peers:
            sigs = signals_by_ticker.get(peer, [])
            ret = self._get_return(sigs, 1)
            if not math.isnan(ret):
                if ret > 0.01:
                    up_count += 1
                elif ret < -0.01:
                    down_count += 1

        if up_count > 3 or down_count > 3:
            return 1.0
        return 0.0

    def _granger_signal(
        self, upstream: list[Any], signals_by_ticker: dict[str, list[Signal]]
    ) -> float:
        """For Granger-significant leaders: leader's return(lag ago) × correlation."""
        granger_edges = [e for e in upstream if e.relationship_type == "granger_causal"]
        if not granger_edges:
            return 0.0

        max_signal = 0.0
        for edge in granger_edges:
            leader_sigs = signals_by_ticker.get(edge.leader, [])
            lag = max(edge.lag_days, 1)
            ret = self._get_return(leader_sigs, lag)
            if not math.isnan(ret):
                signal = ret * edge.correlation
                if abs(signal) > abs(max_signal):
                    max_signal = signal

        return max_signal
