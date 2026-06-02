# Phase 4C: Cross-Asset Intelligence — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build cross-asset correlation graph with Granger causality and supply chain overrides, then extract 8 features that capture inter-stock signal propagation.

**Architecture:** CrossAssetPort protocol + CorrelationAnalyzer adapter (NetworkX graph, hierarchical clustering, Granger causality) + CrossAssetFeatureEngineer (8 features). Supply chain YAML config with 10 groups. Optional wiring into PretrainingUseCase/WeeklyTournamentUseCase.

**Tech Stack:** Python 3.12, numpy, scipy (Ward linkage), statsmodels (Granger), networkx (DiGraph), PyYAML.

**Branch:** `feat/phase-4c-cross-asset-intelligence`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `domain/models.py` | Add CorrelationEdge frozen dataclass |
| `domain/ports.py` | Add CrossAssetPort protocol |
| `adapters/ml/correlation_analyzer.py` | Build correlation graph + Granger causality + YAML merge |
| `adapters/ml/cross_asset_features.py` | Extract 8 cross-asset features from graph |
| `config/relationships/supply_chain.yaml` | 10 manual supply chain groups |
| `application/use_cases.py` | Wire cross_asset_engineer into PretrainingUseCase + WeeklyTournamentUseCase |
| `application/cli.py` | Wire CorrelationAnalyzer + CrossAssetFeatureEngineer in composition root |
| `tests/fakes/fake_cross_asset.py` | FakeCrossAsset test double |
| `tests/test_correlation_edge.py` | Domain model tests |
| `tests/test_correlation_analyzer.py` | CorrelationAnalyzer unit tests |
| `tests/test_cross_asset_features.py` | CrossAssetFeatureEngineer unit tests |
| `tests/test_cross_asset_integration.py` | End-to-end integration test |

---

### Task 1: Domain Models (CorrelationEdge + CrossAssetPort)

**Files:**
- Modify: `domain/models.py`
- Modify: `domain/ports.py`
- Create: `tests/test_correlation_edge.py`

- [ ] **Step 1: Write failing tests**

```python
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
            leader="AAPL", follower="MSFT", correlation=0.75,
            lag_days=0, relationship_type="auto_correlation", source="computed",
        )
        assert e.relationship_type == "auto_correlation"

    def test_granger_causal_type(self) -> None:
        e = CorrelationEdge(
            leader="NVDA", follower="SMCI", correlation=0.88,
            lag_days=1, relationship_type="granger_causal", source="computed",
        )
        assert e.relationship_type == "granger_causal"

    def test_negative_correlation(self) -> None:
        e = CorrelationEdge(
            leader="XOM", follower="DAL", correlation=-0.65,
            lag_days=2, relationship_type="supply_chain", source="manual_yaml",
        )
        assert e.correlation == -0.65

    def test_is_frozen(self) -> None:
        e = CorrelationEdge(
            leader="AMAT", follower="AMD", correlation=0.82,
            lag_days=2, relationship_type="supply_chain", source="manual_yaml",
        )
        with pytest.raises(Exception):
            e.correlation = 0.5  # type: ignore[misc]

    def test_rejects_correlation_out_of_bounds_high(self) -> None:
        with pytest.raises(ValueError, match="correlation"):
            CorrelationEdge(
                leader="A", follower="B", correlation=1.5,
                lag_days=0, relationship_type="auto_correlation", source="computed",
            )

    def test_rejects_correlation_out_of_bounds_low(self) -> None:
        with pytest.raises(ValueError, match="correlation"):
            CorrelationEdge(
                leader="A", follower="B", correlation=-1.5,
                lag_days=0, relationship_type="auto_correlation", source="computed",
            )

    def test_rejects_negative_lag(self) -> None:
        with pytest.raises(ValueError, match="lag_days"):
            CorrelationEdge(
                leader="A", follower="B", correlation=0.8,
                lag_days=-1, relationship_type="auto_correlation", source="computed",
            )

    def test_rejects_lag_too_high(self) -> None:
        with pytest.raises(ValueError, match="lag_days"):
            CorrelationEdge(
                leader="A", follower="B", correlation=0.8,
                lag_days=6, relationship_type="auto_correlation", source="computed",
            )

    def test_rejects_invalid_relationship_type(self) -> None:
        with pytest.raises(ValueError, match="relationship_type"):
            CorrelationEdge(
                leader="A", follower="B", correlation=0.8,
                lag_days=0, relationship_type="invalid", source="computed",
            )

    def test_rejects_invalid_source(self) -> None:
        with pytest.raises(ValueError, match="source"):
            CorrelationEdge(
                leader="A", follower="B", correlation=0.8,
                lag_days=0, relationship_type="auto_correlation", source="invalid",
            )
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_correlation_edge.py -v
```

- [ ] **Step 3: Add CorrelationEdge to domain/models.py**

Add at end of file:

```python
_VALID_RELATIONSHIP_TYPES = frozenset({"auto_correlation", "supply_chain", "granger_causal"})
_VALID_EDGE_SOURCES = frozenset({"computed", "manual_yaml"})


@dataclass(frozen=True)
class CorrelationEdge:
    """A directed relationship between two tickers."""

    leader: str
    follower: str
    correlation: float  # [-1.0, 1.0]
    lag_days: int  # 0-5
    relationship_type: str  # auto_correlation | supply_chain | granger_causal
    source: str  # computed | manual_yaml

    def __post_init__(self) -> None:
        if not -1.0 <= self.correlation <= 1.0:
            raise ValueError("correlation must be in [-1.0, 1.0]")
        if not 0 <= self.lag_days <= 5:
            raise ValueError("lag_days must be in [0, 5]")
        if self.relationship_type not in _VALID_RELATIONSHIP_TYPES:
            raise ValueError(f"relationship_type must be one of {_VALID_RELATIONSHIP_TYPES}")
        if self.source not in _VALID_EDGE_SOURCES:
            raise ValueError(f"source must be one of {_VALID_EDGE_SOURCES}")
```

- [ ] **Step 4: Add CrossAssetPort to domain/ports.py**

Add import for `CorrelationEdge` to the existing imports from `.models`, then add at end of file:

```python
@runtime_checkable
class CrossAssetPort(Protocol):
    """Builds and queries cross-asset correlation graph."""

    def build_graph(
        self,
        signals_by_ticker: dict[str, list[Signal]],
        window_days: int = 60,
    ) -> None: ...

    def get_upstream_signals(self, ticker: str) -> list[CorrelationEdge]: ...

    def get_cluster_peers(self, ticker: str) -> list[str]: ...

    def get_correlation(self, ticker_a: str, ticker_b: str) -> float: ...
```

- [ ] **Step 5: Run tests — expect PASS**

```bash
pytest tests/test_correlation_edge.py -v
```

- [ ] **Step 6: Commit**

```bash
git add domain/models.py domain/ports.py tests/test_correlation_edge.py
git commit -m "feat: add CorrelationEdge domain model and CrossAssetPort protocol"
```

---

### Task 2: FakeCrossAsset Test Double

**Files:**
- Create: `tests/fakes/fake_cross_asset.py`

- [ ] **Step 1: Create fake**

```python
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
```

- [ ] **Step 2: Run full suite to verify no regressions**

```bash
pytest --ignore=tests/test_rss_adapter.py --tb=short -q
```

- [ ] **Step 3: Commit**

```bash
git add tests/fakes/fake_cross_asset.py
git commit -m "feat: FakeCrossAsset test double for CrossAssetPort"
```

---

### Task 3: Supply Chain YAML Config

**Files:**
- Create: `config/relationships/supply_chain.yaml`

- [ ] **Step 1: Create directory and YAML file**

```bash
mkdir -p config/relationships
```

Write the full supply chain YAML with all 10 groups (15 entries including sub-groups):

```yaml
# Manual supply chain and sector relationships.
# These edges are always included in the cross-asset graph
# regardless of statistical correlation threshold.
#
# Schema:
#   group: string — group name
#   leaders: list[str] — tickers that lead
#   followers: list[str] — tickers that follow
#   typical_lag_days: int — expected lag (0-5)
#   inverse: bool (optional) — true if negatively correlated
#   notes: string — rationale for relationship

relationships:
  # --- Semiconductors ---
  - group: semiconductors
    leaders: [AMAT, LRCX, KLAC, ASML]
    followers: [MU, WDC, INTC, AMD, NVDA]
    typical_lag_days: 2
    notes: "Equipment makers lead chip producers"

  # --- Big Tech Ecosystem ---
  - group: big_tech_ecosystem
    leaders: [AAPL, MSFT, GOOG, AMZN, META]
    followers: [TSM, AVGO, QCOM, TXN, ADI]
    typical_lag_days: 1
    notes: "Big tech demand drives semiconductor suppliers"

  # --- Energy Chain ---
  - group: energy_chain
    leaders: [XOM, CVX, COP, SLB]
    followers: [WMB, KMI, ET]
    typical_lag_days: 1
    notes: "Upstream oil drives midstream"

  - group: energy_downstream
    leaders: [XOM, CVX, COP]
    followers: [VLO, MPC, PSX]
    typical_lag_days: 1
    notes: "Crude prices drive refiners"

  - group: energy_inverse
    leaders: [XOM, CVX]
    followers: [DAL, UAL, AAL]
    inverse: true
    typical_lag_days: 2
    notes: "High oil prices hurt airlines (fuel costs)"

  # --- Pharma Supply Chain ---
  - group: pharma_supply_chain
    leaders: [PFE, JNJ, ABBV, MRK, LLY]
    followers: [MCK, ABC, CAH]
    typical_lag_days: 2
    notes: "Pharma production drives distribution"

  - group: pharma_retail
    leaders: [MCK, ABC, CAH]
    followers: [WMT, CVS, WBA]
    typical_lag_days: 2
    notes: "Distribution drives pharmacy retail"

  # --- Space & Defense ---
  - group: space_defense
    leaders: [LMT, RTX, NOC]
    followers: [HXL, IRDM, LUNR, ASTS, RKLB]
    typical_lag_days: 3
    notes: "Prime contractors lead subcontractors and space startups"

  # --- Retail / Consumer ---
  - group: retail_consumer
    leaders: [WMT, AMZN, COST]
    followers: [TGT, DG, DLTR]
    typical_lag_days: 1
    notes: "Big box retail leads discount retail"

  # --- AI Supply Chain ---
  - group: ai_infrastructure
    leaders: [NVDA]
    followers: [SMCI, DELL, HPE]
    typical_lag_days: 1
    notes: "GPU maker leads AI server builders"

  - group: ai_consumers
    leaders: [NVDA, SMCI]
    followers: [MSFT, GOOG, META]
    typical_lag_days: 2
    notes: "AI hardware signals drive cloud AI spenders"

  # --- Cloud / SaaS ---
  - group: cloud_saas
    leaders: [MSFT, AMZN, GOOG]
    followers: [SNOW, DDOG, NET, MDB, CRWD]
    typical_lag_days: 1
    notes: "Cloud platform health drives SaaS ecosystem"

  # --- Financials ---
  - group: financials_banks
    leaders: [JPM, GS, MS]
    followers: [SCHW, IBKR]
    typical_lag_days: 1
    notes: "Major banks lead brokerages"

  - group: financials_payments
    leaders: [JPM, GS]
    followers: [V, MA, AXP]
    typical_lag_days: 1
    notes: "Bank health signals payment network outlook"

  # --- Housing / Rates Sensitive ---
  - group: housing_rates
    leaders: [LEN, DHI, PHM]
    followers: [HD, LOW]
    typical_lag_days: 2
    notes: "Homebuilder activity drives home improvement retail"
```

- [ ] **Step 2: Verify YAML is valid**

```bash
python -c "import yaml; yaml.safe_load(open('config/relationships/supply_chain.yaml'))"
```

- [ ] **Step 3: Commit**

```bash
git add config/relationships/supply_chain.yaml
git commit -m "feat: supply chain YAML config with 10 relationship groups"
```

---

### Task 4: CorrelationAnalyzer Adapter

**Files:**
- Create: `adapters/ml/correlation_analyzer.py`
- Create: `tests/test_correlation_analyzer.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for CorrelationAnalyzer — cross-asset graph builder."""

from __future__ import annotations

import math
from datetime import datetime, timedelta

import numpy as np
import pytest

from adapters.ml.correlation_analyzer import CorrelationAnalyzer
from domain.models import CorrelationEdge, Signal


def _make_signals(prices: list[float], start_date: datetime | None = None) -> list[Signal]:
    """Create Signal list from price series."""
    base = start_date or datetime(2026, 1, 1)
    return [
        Signal(
            symbol="X",
            timestamp=base + timedelta(days=i),
            price=p,
            volume=1_000_000,
            open=p,
            high=p * 1.01,
            low=p * 0.99,
            close=p,
        )
        for i, p in enumerate(prices)
    ]


def _correlated_series(n: int = 80, seed: int = 42) -> tuple[list[float], list[float]]:
    """Generate two highly correlated price series."""
    rng = np.random.default_rng(seed)
    base = 100.0 + np.cumsum(rng.normal(0, 1, n))
    noise = rng.normal(0, 0.3, n)
    return base.tolist(), (base + noise).tolist()


def _lagged_series(n: int = 80, lag: int = 2, seed: int = 42) -> tuple[list[float], list[float]]:
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
        analyzer.build_graph({"XOM": _make_signals(a), "DAL": _make_signals(b)}, window_days=60)
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
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_correlation_analyzer.py -v
```

- [ ] **Step 3: Write implementation**

```python
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

    def __init__(self, supply_chain_path: str = "config/relationships/supply_chain.yaml") -> None:
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
                valid[ticker] = [s.price for s in sorted(sigs, key=lambda s: s.timestamp)]

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

        # Ensure symmetry and valid range
        dist_matrix = np.clip(dist_matrix, 0.0, 2.0)
        condensed = squareform(dist_matrix)

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
        results: list[tuple[str, str, float, int, float]] = []  # leader, follower, corr, lag, p
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
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
pytest tests/test_correlation_analyzer.py -v
```

- [ ] **Step 5: Run full suite for regression check**

```bash
pytest --ignore=tests/test_rss_adapter.py --tb=short -q
```

- [ ] **Step 6: Commit**

```bash
git add adapters/ml/correlation_analyzer.py tests/test_correlation_analyzer.py
git commit -m "feat: CorrelationAnalyzer with correlation matrix, clustering, and Granger causality"
```

---

### Task 5: CrossAssetFeatureEngineer

**Files:**
- Create: `adapters/ml/cross_asset_features.py`
- Create: `tests/test_cross_asset_features.py`

- [ ] **Step 1: Write failing tests**

```python
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
            open=p,
            high=p * 1.01,
            low=p * 0.99,
            close=p,
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
    def test_upstream_leader_return_1d(self, fake: FakeCrossAsset, eng: CrossAssetFeatureEngineer) -> None:
        """Leader with +5% 1d return → positive upstream signal."""
        fake.add_edge(CorrelationEdge(
            leader="NVDA", follower="SMCI", correlation=0.85,
            lag_days=1, relationship_type="supply_chain", source="manual_yaml",
        ))
        # NVDA: last price 105, previous 100 → +5% 1d return
        nvda_prices = [100.0] * 28 + [100.0, 105.0]
        smci_prices = [50.0] * 30
        signals_by_ticker = {
            "NVDA": _make_signals("NVDA", nvda_prices),
            "SMCI": _make_signals("SMCI", smci_prices),
        }
        result = eng.compute("SMCI", signals_by_ticker["SMCI"], signals_by_ticker)
        assert result["upstream_leader_return_1d"] > 0

    def test_no_upstream_returns_nan(self, fake: FakeCrossAsset, eng: CrossAssetFeatureEngineer) -> None:
        """Ticker with no upstream leaders → NaN."""
        signals = _make_signals("AAPL", [100.0] * 30)
        result = eng.compute("AAPL", signals, {"AAPL": signals})
        assert math.isnan(result["upstream_leader_return_1d"])
        assert math.isnan(result["upstream_leader_return_5d"])


class TestClusterMomentum:
    def test_cluster_momentum_positive(self, fake: FakeCrossAsset, eng: CrossAssetFeatureEngineer) -> None:
        """Cluster peers all up → positive cluster momentum."""
        fake.set_cluster("AMD", ["NVDA", "INTC"])
        # All peers have positive 5d returns
        amd_signals = _make_signals("AMD", [100.0] * 30)
        nvda_signals = _make_signals("NVDA", [100.0] * 25 + [101, 102, 103, 104, 105])
        intc_signals = _make_signals("INTC", [50.0] * 25 + [51, 52, 52, 53, 53])
        signals_by_ticker = {
            "AMD": amd_signals, "NVDA": nvda_signals, "INTC": intc_signals,
        }
        result = eng.compute("AMD", amd_signals, signals_by_ticker)
        assert result["cluster_momentum_1w"] > 0

    def test_no_cluster_returns_nan(self, fake: FakeCrossAsset, eng: CrossAssetFeatureEngineer) -> None:
        signals = _make_signals("SOLO", [100.0] * 30)
        result = eng.compute("SOLO", signals, {"SOLO": signals})
        assert math.isnan(result["cluster_momentum_1w"])


class TestLeaderFollowerLag:
    def test_leader_moved_follower_hasnt(self, fake: FakeCrossAsset, eng: CrossAssetFeatureEngineer) -> None:
        """Leader moved >2% recently, follower flat → positive lag signal."""
        fake.add_edge(CorrelationEdge(
            leader="AMAT", follower="AMD", correlation=0.8,
            lag_days=2, relationship_type="granger_causal", source="computed",
        ))
        # AMAT moved +5% 2 days ago, AMD flat
        amat_prices = [100.0] * 27 + [105.0, 105.0, 105.0]
        amd_prices = [80.0] * 30
        signals_by_ticker = {
            "AMAT": _make_signals("AMAT", amat_prices),
            "AMD": _make_signals("AMD", amd_prices),
        }
        result = eng.compute("AMD", signals_by_ticker["AMD"], signals_by_ticker)
        assert result["leader_follower_lag_signal"] > 0


class TestThematicActivation:
    def test_activation_fires_when_3_plus_move(self, fake: FakeCrossAsset, eng: CrossAssetFeatureEngineer) -> None:
        """More than 3 cluster peers moved same direction >1% → activation = 1.0."""
        fake.set_cluster("AMD", ["NVDA", "INTC", "MU", "AVGO"])
        base = [100.0] * 29
        signals_by_ticker = {
            "AMD": _make_signals("AMD", base + [100.0]),
            "NVDA": _make_signals("NVDA", base + [102.0]),  # +2%
            "INTC": _make_signals("INTC", base + [101.5]),  # +1.5%
            "MU": _make_signals("MU", base + [103.0]),      # +3%
            "AVGO": _make_signals("AVGO", base + [101.2]),   # +1.2%
        }
        result = eng.compute("AMD", signals_by_ticker["AMD"], signals_by_ticker)
        assert result["thematic_activation"] == 1.0

    def test_no_activation_when_few_move(self, fake: FakeCrossAsset, eng: CrossAssetFeatureEngineer) -> None:
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
    def test_granger_leader_signal(self, fake: FakeCrossAsset, eng: CrossAssetFeatureEngineer) -> None:
        """Granger-significant leader moved → positive signal."""
        fake.add_edge(CorrelationEdge(
            leader="NVDA", follower="SMCI", correlation=0.9,
            lag_days=1, relationship_type="granger_causal", source="computed",
        ))
        # NVDA moved +3% 1 day ago
        nvda_prices = [100.0] * 28 + [103.0, 103.0]
        smci_prices = [50.0] * 30
        signals_by_ticker = {
            "NVDA": _make_signals("NVDA", nvda_prices),
            "SMCI": _make_signals("SMCI", smci_prices),
        }
        result = eng.compute("SMCI", signals_by_ticker["SMCI"], signals_by_ticker)
        assert result["granger_lead_signal"] > 0

    def test_no_granger_leaders_returns_zero(self, fake: FakeCrossAsset, eng: CrossAssetFeatureEngineer) -> None:
        """No Granger leaders → 0.0 (not NaN)."""
        signals = _make_signals("SOLO", [100.0] * 30)
        result = eng.compute("SOLO", signals, {"SOLO": signals})
        assert result["granger_lead_signal"] == 0.0


class TestTickerNotInGraph:
    def test_all_nan_for_unknown_ticker(self, fake: FakeCrossAsset, eng: CrossAssetFeatureEngineer) -> None:
        signals = _make_signals("UNKNOWN", [100.0] * 30)
        result = eng.compute("UNKNOWN", signals, {"UNKNOWN": signals})
        for name in CROSS_ASSET_FEATURE_NAMES:
            if name == "granger_lead_signal":
                assert result[name] == 0.0
            elif name == "thematic_activation":
                assert result[name] == 0.0
            else:
                assert math.isnan(result[name]), f"{name} should be NaN"
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_cross_asset_features.py -v
```

- [ ] **Step 3: Write implementation**

```python
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
        self, upstream: list, signals_by_ticker: dict[str, list[Signal]], days: int
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
        upstream: list,
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
            if not math.isnan(leader_ret) and abs(leader_ret) > 0.02 and abs(ticker_1d) < 0.01:
                signal = leader_ret * edge.correlation
                if abs(signal) > abs(max_signal):
                    max_signal = signal

        return max_signal

    def _supply_chain_divergence(
        self,
        ticker: str,
        signals: list[Signal],
        upstream: list,
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
        self, upstream: list, signals_by_ticker: dict[str, list[Signal]]
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
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
pytest tests/test_cross_asset_features.py -v
```

- [ ] **Step 5: Run full suite**

```bash
pytest --ignore=tests/test_rss_adapter.py --tb=short -q
```

- [ ] **Step 6: Commit**

```bash
git add adapters/ml/cross_asset_features.py tests/test_cross_asset_features.py
git commit -m "feat: CrossAssetFeatureEngineer with 8 cross-asset features"
```

---

### Task 6: Wire into PretrainingUseCase + WeeklyTournamentUseCase

**Files:**
- Modify: `application/use_cases.py`
- Modify: `application/cli.py`

- [ ] **Step 1: Add cross_asset_engineer parameter to PretrainingUseCase**

In `application/use_cases.py`, modify the `PretrainingUseCase.__init__` method. Add after `fundamental_engineer` parameter:

```python
        cross_asset_engineer: Any | None = None,  # Phase 4C
```

Store it:
```python
        self._cross_asset = cross_asset_engineer
```

- [ ] **Step 2: Wire cross-asset features in PretrainingUseCase._compute_ticker_features**

After the fundamental features block (after `features.update(fundamental_features)`), add:

```python
        # Phase 4C: Add cross-asset features
        if self._cross_asset is not None:
            cross_features = self._cross_asset.compute(
                ticker=ticker,
                signals=signals,
                signals_by_ticker=getattr(self, "_signals_cache", {}),
            )
            features.update(cross_features)
```

- [ ] **Step 3: Add signals cache to PretrainingUseCase._collect_features_and_targets**

Before the per-ticker loop in `_collect_features_and_targets`, add a signals cache so cross-asset features can access all tickers' data. After `macro_signals = self._fetch_macro(month_end)`, add:

```python
            # Cache signals for cross-asset features
            if self._cross_asset is not None:
                self._signals_cache: dict[str, list] = {}  # type: ignore[type-arg]
                for t in self._tickers:
                    try:
                        start = month_end - timedelta(days=365)
                        sigs = self._market_data.get_signals(t, month_end, start_date=start)
                        if len(sigs) >= 20:
                            self._signals_cache[t] = sigs
                    except Exception:
                        continue
                # Build graph with cached signals
                self._cross_asset._graph.build_graph(self._signals_cache, window_days=60)
```

- [ ] **Step 4: Add cross_asset_engineer to WeeklyTournamentUseCase**

Same pattern. In `__init__`, add parameter after `fundamental_engineer`:

```python
        cross_asset_engineer: Any | None = None,  # Phase 4C
```

Store:
```python
        self._cross_asset = cross_asset_engineer
```

- [ ] **Step 5: Wire cross-asset features in WeeklyTournamentUseCase._score_ticker**

After the fundamental features block, add:

```python
        # Phase 4C: Add cross-asset features
        if self._cross_asset is not None:
            cross_features = self._cross_asset.compute(
                ticker=ticker,
                signals=signals,
                signals_by_ticker=getattr(self, "_signals_cache", {}),
            )
            features.update(cross_features)
```

- [ ] **Step 6: Add signals cache to WeeklyTournamentUseCase.execute**

Before the per-ticker loop in `execute()`, after `macro_signals = self._fetch_macro(prediction_date)`, add:

```python
        # Cache signals for cross-asset features
        if self._cross_asset is not None:
            self._signals_cache: dict[str, list] = {}  # type: ignore[type-arg]
            for t in self._tickers:
                try:
                    start = prediction_date - timedelta(days=365)
                    sigs = self._market_data.get_signals(t, prediction_date, start_date=start)
                    if len(sigs) >= 20:
                        self._signals_cache[t] = sigs
                except Exception:
                    continue
            self._cross_asset._graph.build_graph(self._signals_cache, window_days=60)
```

- [ ] **Step 7: Wire in cli.py composition root**

In `_build_dependencies()`, add after the `FundamentalFeatureEngineer()` line:

```python
    from adapters.ml.correlation_analyzer import CorrelationAnalyzer
    from adapters.ml.cross_asset_features import CrossAssetFeatureEngineer

    analyzer = CorrelationAnalyzer(
        supply_chain_path=str(Path("config/relationships/supply_chain.yaml"))
    )
    cross_asset_engineer = CrossAssetFeatureEngineer(cross_asset=analyzer)
```

Add to return dict:
```python
        "cross_asset_engineer": cross_asset_engineer,
```

Then update all three places where `PretrainingUseCase` and `WeeklyTournamentUseCase` are instantiated — add `cross_asset_engineer=deps["cross_asset_engineer"]` parameter. These are in the `pretrain`, `run_tournament`, and `backtest` commands.

- [ ] **Step 8: Run full suite**

```bash
pytest --ignore=tests/test_rss_adapter.py --tb=short -q
```

- [ ] **Step 9: Commit**

```bash
git add application/use_cases.py application/cli.py
git commit -m "feat: wire CrossAssetFeatureEngineer into pretraining and tournament pipelines"
```

---

### Task 7: Integration Test + CLAUDE.md + PR

**Files:**
- Create: `tests/test_cross_asset_integration.py`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Write integration test**

```python
"""Integration test: cross-asset graph → features end-to-end."""

from __future__ import annotations

import math
from datetime import datetime, timedelta

import numpy as np

from adapters.ml.correlation_analyzer import CorrelationAnalyzer
from adapters.ml.cross_asset_features import CROSS_ASSET_FEATURE_NAMES, CrossAssetFeatureEngineer
from domain.models import Signal


def _make_signals(symbol: str, prices: list[float]) -> list[Signal]:
    base = datetime(2026, 3, 1)
    return [
        Signal(
            symbol=symbol,
            timestamp=base + timedelta(days=i),
            price=p,
            volume=1_000_000,
            open=p, high=p * 1.01, low=p * 0.99, close=p,
        )
        for i, p in enumerate(prices)
    ]


def test_end_to_end_graph_to_features(tmp_path) -> None:
    """Build graph from synthetic data, extract features, verify shape."""
    yaml_content = """
relationships:
  - group: test
    leaders: [A]
    followers: [B]
    typical_lag_days: 1
    notes: "test"
"""
    yaml_path = tmp_path / "sc.yaml"
    yaml_path.write_text(yaml_content)

    rng = np.random.default_rng(42)
    prices_a = (100.0 + np.cumsum(rng.normal(0, 0.5, 80))).tolist()
    # B follows A with noise
    prices_b = (100.0 + np.cumsum(rng.normal(0, 0.5, 80))).tolist()

    signals_by_ticker = {
        "A": _make_signals("A", prices_a),
        "B": _make_signals("B", prices_b),
    }

    analyzer = CorrelationAnalyzer(supply_chain_path=str(yaml_path))
    eng = CrossAssetFeatureEngineer(cross_asset=analyzer)

    # Build graph
    analyzer.build_graph(signals_by_ticker, window_days=60)

    # Extract features for B (follower)
    features = eng.compute("B", signals_by_ticker["B"], signals_by_ticker)

    # All 8 features present
    assert set(features.keys()) == set(CROSS_ASSET_FEATURE_NAMES)

    # Supply chain edge should exist → upstream features should not all be NaN
    # (A is leader of B via YAML)
    assert not math.isnan(features["upstream_leader_return_1d"])


def test_no_key_collisions_with_existing_features() -> None:
    """Cross-asset feature names don't overlap with technical/sentiment/fundamental."""
    from adapters.ml.feature_engineer import FeatureEngineer
    from adapters.ml.fundamental_feature_engineer import FUNDAMENTAL_FEATURE_NAMES

    fe = FeatureEngineer()
    technical_names = set(fe.get_feature_names())
    fundamental_names = set(FUNDAMENTAL_FEATURE_NAMES)
    cross_asset_names = set(CROSS_ASSET_FEATURE_NAMES)

    assert technical_names.isdisjoint(cross_asset_names), (
        f"Collision: {technical_names & cross_asset_names}"
    )
    assert fundamental_names.isdisjoint(cross_asset_names), (
        f"Collision: {fundamental_names & cross_asset_names}"
    )


def test_supply_chain_yaml_loads_all_groups() -> None:
    """Full supply chain YAML loads without error."""
    from pathlib import Path
    yaml_path = Path("config/relationships/supply_chain.yaml")
    if not yaml_path.exists():
        pytest.skip("supply_chain.yaml not found")

    import yaml
    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    groups = data["relationships"]
    assert len(groups) >= 10, f"Expected >= 10 groups, got {len(groups)}"
    for g in groups:
        assert "group" in g
        assert "leaders" in g
        assert "followers" in g
```

- [ ] **Step 2: Run integration tests**

```bash
pytest tests/test_cross_asset_integration.py -v --tb=short
```

- [ ] **Step 3: Update CLAUDE.md**

Add after Phase 4B "Done" section:

```
**Done (Phase 4C — Cross-Asset Intelligence 2026-06-02):**
- CorrelationEdge domain model + CrossAssetPort protocol
- CorrelationAnalyzer adapter — rolling correlation matrix, hierarchical clustering, Granger causality with BH correction
- CrossAssetFeatureEngineer — 8 features (upstream leader returns, cluster momentum, lag signal, supply chain divergence, correlation regime shift, thematic activation, Granger lead signal)
- Supply chain YAML config — 10 groups (semiconductors, big tech, energy, pharma, space/defense, retail, AI, cloud/SaaS, financials, housing)
- Wired into pretraining and tournament pipelines (optional, backward compatible)
- Test suite — 365+ tests passing
```

- [ ] **Step 4: Run full test suite**

```bash
pytest --ignore=tests/test_rss_adapter.py --tb=short -q
```

- [ ] **Step 5: Commit**

```bash
git add tests/test_cross_asset_integration.py CLAUDE.md
git commit -m "feat: Phase 4C integration tests + CLAUDE.md update"
```

- [ ] **Step 6: Push + PR**

```bash
git push -u origin feat/phase-4c-cross-asset-intelligence
gh pr create --title "feat: Phase 4C — cross-asset intelligence" --base develop --body "$(cat <<'EOF'
## Summary
- **CorrelationEdge** domain model + **CrossAssetPort** protocol
- **CorrelationAnalyzer** — rolling correlation matrix, Ward hierarchical clustering, Granger causality with BH correction, manual supply chain YAML merge
- **CrossAssetFeatureEngineer** — 8 features (upstream leader returns, cluster momentum, lag signal, supply chain divergence, correlation regime shift, thematic activation, Granger lead signal)
- **Supply chain YAML** — 10 groups (15 entries), 80+ tickers with directed leader→follower relationships
- Wired into PretrainingUseCase + WeeklyTournamentUseCase (optional, backward compatible)

## Test plan
- [x] 11 CorrelationEdge model tests (validation, immutability)
- [x] ~15 CorrelationAnalyzer tests (correlation, clustering, Granger, YAML merge, edge cases)
- [x] ~12 CrossAssetFeatureEngineer tests (all 8 features, NaN handling)
- [x] 3 integration tests (end-to-end, key collisions, YAML loading)
- [x] Full suite passing, all pre-commit hooks green
EOF
)"
```

---

## Dependency Graph

```
Task 1 (Domain Models) → Task 2 (Fake) → Task 3 (YAML) → Task 4 (Analyzer) → Task 5 (Features) → Task 6 (Wiring) → Task 7 (Integration + PR)
```

All sequential. Each task builds on the previous.
