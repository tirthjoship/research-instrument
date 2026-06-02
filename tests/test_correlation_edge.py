"""Tests for CorrelationEdge domain model."""

from __future__ import annotations

import pytest

from domain.models import CorrelationEdge


class TestCorrelationEdge:
    def test_valid_creation(self) -> None:
        e = CorrelationEdge(
            leader="AMAT",
            follower="AMD",
            correlation=0.82,
            lag_days=2,
            relationship_type="supply_chain",
            source="manual_yaml",
        )
        assert e.leader == "AMAT"
        assert e.follower == "AMD"
        assert e.correlation == 0.82
        assert e.lag_days == 2

    def test_auto_correlation_type(self) -> None:
        e = CorrelationEdge(
            leader="AAPL",
            follower="MSFT",
            correlation=0.75,
            lag_days=0,
            relationship_type="auto_correlation",
            source="computed",
        )
        assert e.relationship_type == "auto_correlation"

    def test_granger_causal_type(self) -> None:
        e = CorrelationEdge(
            leader="NVDA",
            follower="SMCI",
            correlation=0.88,
            lag_days=1,
            relationship_type="granger_causal",
            source="computed",
        )
        assert e.relationship_type == "granger_causal"

    def test_negative_correlation(self) -> None:
        e = CorrelationEdge(
            leader="XOM",
            follower="DAL",
            correlation=-0.65,
            lag_days=2,
            relationship_type="supply_chain",
            source="manual_yaml",
        )
        assert e.correlation == -0.65

    def test_is_frozen(self) -> None:
        e = CorrelationEdge(
            leader="AMAT",
            follower="AMD",
            correlation=0.82,
            lag_days=2,
            relationship_type="supply_chain",
            source="manual_yaml",
        )
        with pytest.raises(Exception):
            e.correlation = 0.5  # type: ignore[misc]

    def test_rejects_correlation_out_of_bounds_high(self) -> None:
        with pytest.raises(ValueError, match="correlation"):
            CorrelationEdge(
                leader="A",
                follower="B",
                correlation=1.5,
                lag_days=0,
                relationship_type="auto_correlation",
                source="computed",
            )

    def test_rejects_correlation_out_of_bounds_low(self) -> None:
        with pytest.raises(ValueError, match="correlation"):
            CorrelationEdge(
                leader="A",
                follower="B",
                correlation=-1.5,
                lag_days=0,
                relationship_type="auto_correlation",
                source="computed",
            )

    def test_rejects_negative_lag(self) -> None:
        with pytest.raises(ValueError, match="lag_days"):
            CorrelationEdge(
                leader="A",
                follower="B",
                correlation=0.8,
                lag_days=-1,
                relationship_type="auto_correlation",
                source="computed",
            )

    def test_rejects_lag_too_high(self) -> None:
        with pytest.raises(ValueError, match="lag_days"):
            CorrelationEdge(
                leader="A",
                follower="B",
                correlation=0.8,
                lag_days=6,
                relationship_type="auto_correlation",
                source="computed",
            )

    def test_rejects_invalid_relationship_type(self) -> None:
        with pytest.raises(ValueError, match="relationship_type"):
            CorrelationEdge(
                leader="A",
                follower="B",
                correlation=0.8,
                lag_days=0,
                relationship_type="invalid",
                source="computed",
            )

    def test_rejects_invalid_source(self) -> None:
        with pytest.raises(ValueError, match="source"):
            CorrelationEdge(
                leader="A",
                follower="B",
                correlation=0.8,
                lag_days=0,
                relationship_type="auto_correlation",
                source="invalid",
            )
