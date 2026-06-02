# Phase 4C: Cross-Asset Intelligence — Design Spec

**Date:** 2026-06-02
**ADRs:** 027 (hybrid graph concept), 029 (architecture decisions)
**Branch:** `feat/phase-4c-cross-asset-intelligence`
**Depends on:** Phase 4A (fundamental features wired), Phase 4B (portfolio tracking)

---

## Goal

Detect sector co-movement, supply chain propagation, and lead-lag relationships across ~350 tickers. Produce ~8 cross-asset features that capture inter-stock signal propagation — a signal layer absent from standard financial ML feature sets.

## Non-Goals

- Cascade detection use case (deferred to Phase 5 dashboard)
- GNN-based graph learning (deferred to future research)
- Real-time alerting on cross-asset moves
- Brokerage API integration

---

## Architecture

```
domain/
  ports.py                          → CrossAssetPort protocol (new)
  models.py                         → CorrelationEdge dataclass (new)

adapters/ml/
  correlation_analyzer.py           → Builds NetworkX graph, Granger causality
  cross_asset_features.py           → Extracts 8 features from graph per ticker

config/relationships/
  supply_chain.yaml                 → 10 manual supply chain groups

tests/
  fakes/fake_cross_asset.py         → FakeCrossAsset test double
  test_correlation_analyzer.py      → Unit tests for graph builder
  test_cross_asset_features.py      → Unit tests for feature extraction
  test_cross_asset_integration.py   → End-to-end integration test
```

---

## Domain Layer

### CorrelationEdge (new dataclass in models.py)

```python
@dataclass(frozen=True)
class CorrelationEdge:
    """A directed relationship between two tickers."""
    leader: str
    follower: str
    correlation: float          # [-1.0, 1.0]
    lag_days: int               # 0-5, how many days leader leads
    relationship_type: str      # "auto_correlation" | "supply_chain" | "granger_causal"
    source: str                 # "computed" | "manual_yaml"
```

Validation:
- correlation in [-1.0, 1.0]
- lag_days in [0, 5]
- relationship_type in {"auto_correlation", "supply_chain", "granger_causal"}
- source in {"computed", "manual_yaml"}

### CrossAssetPort (new protocol in ports.py)

```python
@runtime_checkable
class CrossAssetPort(Protocol):
    """Builds and queries cross-asset correlation graph."""

    def build_graph(
        self,
        signals_by_ticker: dict[str, list["Signal"]],
        window_days: int = 60,
    ) -> None: ...

    def get_upstream_signals(self, ticker: str) -> list["CorrelationEdge"]: ...

    def get_cluster_peers(self, ticker: str) -> list[str]: ...

    def get_correlation(self, ticker_a: str, ticker_b: str) -> float: ...
```

---

## CorrelationAnalyzer Adapter

**File:** `adapters/ml/correlation_analyzer.py`
**Implements:** `CrossAssetPort`
**Dependencies:** numpy, scipy (hierarchical clustering, Granger), networkx

### Algorithm

1. **Extract close prices** — from `signals_by_ticker`, build a DataFrame of daily close prices (tickers × dates). Require minimum 40 days of data per ticker.

2. **Rolling correlation matrix** — compute pairwise Pearson correlation over `window_days` (default 60). Result: N×N matrix.

3. **Hierarchical clustering** — Ward linkage on `1 - |correlation|` distance matrix. Cut dendrogram at threshold where |correlation| > 0.65 to form clusters. Store cluster assignments per ticker.

4. **Granger causality pre-filter** — for pairs with |correlation| > 0.65:
   - Run Granger causality test (statsmodels `grangercausalitytests`) with max_lag=5
   - Collect minimum p-value across lags
   - Apply Benjamini-Hochberg correction across all tested pairs
   - Pairs with adjusted p < 0.05 get directed edges with the lag that produced minimum p-value

5. **Manual override merge** — load `config/relationships/supply_chain.yaml`:
   - Add edges for all leader→follower pairs regardless of correlation threshold
   - Manual edges get `source="manual_yaml"`, `relationship_type="supply_chain"`
   - If a manual edge conflicts with auto-discovered direction, manual wins

6. **Build NetworkX DiGraph** — nodes = tickers, edges = CorrelationEdge attributes

### Query Methods

- `get_upstream_signals(ticker)` — return all incoming edges (predecessors in DiGraph)
- `get_cluster_peers(ticker)` — return tickers in same hierarchical cluster
- `get_correlation(a, b)` — return pairwise correlation from matrix (0.0 if insufficient data)

### Edge Cases

- Ticker with <40 days data → excluded from graph, returns empty for all queries
- No correlated pairs found → empty graph, features all NaN (handled gracefully downstream)
- Supply chain ticker not in universe → skip that edge, log warning

---

## Supply Chain YAML

**File:** `config/relationships/supply_chain.yaml`

```yaml
# Manual supply chain and sector relationships
# These edges are always included in the cross-asset graph
# regardless of statistical correlation threshold.

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

### YAML Loading

- CorrelationAnalyzer loads YAML at `build_graph()` time
- Path configurable (default: `config/relationships/supply_chain.yaml`)
- `inverse: true` flag → correlation stored as negative, lag signal inverted
- Tickers not in current universe → silently skipped (log at DEBUG level)

---

## CrossAssetFeatureEngineer

**File:** `adapters/ml/cross_asset_features.py`

### Interface

```python
class CrossAssetFeatureEngineer:
    def __init__(self, cross_asset: CrossAssetPort) -> None: ...

    def compute(
        self,
        ticker: str,
        signals: list[Signal],
        signals_by_ticker: dict[str, list[Signal]],
    ) -> dict[str, float]: ...
```

### Features (8 total)

| # | Feature | Computation | Type |
|---|---------|-------------|------|
| 1 | `upstream_leader_return_1d` | Weighted avg 1d return of upstream leaders (weighted by correlation strength) | float |
| 2 | `upstream_leader_return_5d` | Weighted avg 5d return of upstream leaders | float |
| 3 | `cluster_momentum_1w` | Mean 5d return of all tickers in same correlation cluster | float |
| 4 | `leader_follower_lag_signal` | Max(leader_return × correlation) for leaders that moved >2% in past lag_days but ticker hasn't moved >1% yet | float |
| 5 | `supply_chain_divergence` | Ticker's 5d return minus weighted avg of supply chain group's 5d return | float |
| 6 | `correlation_regime_shift` | Current 20d avg pairwise correlation with cluster peers minus 60d baseline avg pairwise correlation | float |
| 7 | `thematic_activation` | 1.0 if >3 tickers in any of ticker's groups moved same direction >1% today, else 0.0 | float |
| 8 | `granger_lead_signal` | For Granger-significant leaders: leader's return(lag_days ago) × correlation. Max across leaders. 0.0 if no Granger leaders | float |

### NaN Handling

- No upstream leaders → all upstream features = NaN
- No cluster peers → cluster features = NaN
- No Granger-significant leaders → `granger_lead_signal` = 0.0 (absence of signal, not missing data)
- Ticker not in graph → all 8 features = NaN

---

## Pipeline Wiring

### PretrainingUseCase + WeeklyTournamentUseCase

- CrossAssetFeatureEngineer wired as **optional** parameter (like FundamentalFeatureEngineer)
- Graph built **once** per run with all tickers' signals, then queried per ticker
- Feature dict merged into existing feature matrix

### Composition Root (cli.py / _build_dependencies)

```python
# Build cross-asset graph
from adapters.ml.correlation_analyzer import CorrelationAnalyzer
from adapters.ml.cross_asset_features import CrossAssetFeatureEngineer

analyzer = CorrelationAnalyzer(supply_chain_path="config/relationships/supply_chain.yaml")
cross_asset_engineer = CrossAssetFeatureEngineer(cross_asset=analyzer)

# Pass to use cases
PretrainingUseCase(..., cross_asset_engineer=cross_asset_engineer)
```

### Graph Lifecycle

- **Pretraining:** Graph rebuilt per walk-forward fold (using only data available at fold's prediction time)
- **Tournament:** Graph built once at start with latest 60 days of data
- **Backtest:** Graph rebuilt per evaluation window

---

## Testing Strategy

### FakeCrossAsset (test double)

```python
class FakeCrossAsset:
    """In-memory CrossAssetPort for testing."""

    def __init__(self) -> None:
        self._edges: dict[str, list[CorrelationEdge]] = {}
        self._clusters: dict[str, list[str]] = {}
        self._correlations: dict[tuple[str, str], float] = {}

    def build_graph(self, signals_by_ticker, window_days=60) -> None:
        pass  # pre-populated in tests

    def add_edge(self, edge: CorrelationEdge) -> None: ...
    def set_cluster(self, ticker: str, peers: list[str]) -> None: ...
    def set_correlation(self, a: str, b: str, corr: float) -> None: ...
```

### Test Files

**test_correlation_analyzer.py** (~15 tests):
- Correlation matrix computation with known synthetic data
- Hierarchical clustering forms expected groups
- Granger causality detects known lead-lag (synthetic: A = B shifted by 2 days)
- Granger pre-filter respects 0.65 threshold
- BH correction reduces false positives
- Manual YAML override merges correctly
- Manual edges override auto-discovered direction
- Inverse relationships handled (energy→airlines)
- Tickers with insufficient data excluded
- Empty universe → empty graph
- get_upstream_signals returns correct edges
- get_cluster_peers returns correct members
- get_correlation returns 0.0 for unknown pairs

**test_cross_asset_features.py** (~12 tests):
- Each of 8 features computed correctly with known graph
- NaN handling for missing upstream/cluster/Granger
- Thematic activation threshold (>3 tickers)
- Leader-follower lag signal only fires when leader moved but follower hasn't
- Supply chain divergence sign correct
- Correlation regime shift detects changing correlation

**test_cross_asset_integration.py** (~3 tests):
- End-to-end: synthetic price series → build graph → extract features → verify shapes
- Supply chain YAML loaded and merged
- Features integrate with existing feature matrix (no key collisions)

### Domain Model Tests

- CorrelationEdge validation (correlation bounds, lag bounds, valid types)
- Frozen/immutable

---

## Dependencies

### New Python Packages

- `networkx` — graph data structure (already common in DS stacks, lightweight)
- `statsmodels` — Granger causality tests (`grangercausalitytests`). Already available if scipy is installed.
- `pyyaml` — YAML loading (already a dependency)

### Verify Before Implementation

```bash
pip list | grep -i -E "networkx|statsmodels"
```

If missing, add to `pyproject.toml` `[project.dependencies]`.

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Granger finds nothing significant | Expected outcome is valid. Features default to NaN/0.0. SHAP will confirm. |
| Spurious correlations | 0.65 threshold + BH correction + manual override review |
| Regime-specific lead-lag | Correlation regime shift feature explicitly captures this |
| Performance (350×350 matrix) | NumPy vectorized. Sub-second for 350 tickers. |
| Supply chain YAML maintenance | Config-driven, no code changes. Add/remove groups freely. |

---

## Success Criteria

1. All new tests pass (target: ~30 new tests, total ~365)
2. 8 cross-asset features computed for tickers with graph data
3. Features wired into pretraining/tournament pipelines (optional, backward compatible)
4. Supply chain YAML with 10 groups loaded and merged
5. Granger causality produces at least some significant edges (or documents honest null)
6. All pre-commit hooks pass (mypy strict, black, ruff)
7. No regressions in existing 334 tests
