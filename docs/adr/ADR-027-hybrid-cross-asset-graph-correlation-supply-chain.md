# ADR-027: Hybrid Cross-Asset Graph — Auto-Correlation + Manual Supply Chain

**Date:** 2026-06-01
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context

Markets move in clusters. Semiconductor equipment makers (AMAT, LRCX, KLAC) move together because they share the same customer (TSMC, Samsung). Pharma companies move in advance of distributors (McKesson, Cardinal Health), which move in advance of retail pharmacies. When Elon Musk announces a SpaceX contract, RKLB, ASTS, and LUNR all spike within hours.

The current feature matrix treats each ticker as independent. There is no mechanism to propagate a signal from a supply-chain leader to its downstream dependents, or to flag that a correlated cluster is breaking down.

Two approaches exist to model relationships:
- **Statistical**: rolling correlation matrix over price returns — discovers co-movement automatically
- **Domain knowledge**: hand-coded supply chain graphs — encodes relationships that may not yet appear in price data (new contracts, emerging sectors)

Neither alone is sufficient. Pure statistics finds spurious correlations without domain knowledge to filter them. Pure manual encoding misses unknown or newly forming relationships.

## Decision

Hybrid approach combining auto-discovered correlation clusters with human-reviewed manual supply chain overrides.

### Auto-discovery (statistical layer)
- Weekly: compute rolling 60-day return correlation matrix across the full ticker universe (ADR-023)
- Apply hierarchical clustering (Ward linkage) to find correlation clusters
- Filter: only pairs with |correlation| > 0.65 for at least 40/60 days enter the graph
- Compute lead-lag offsets: for each correlated pair (A, B), test whether A's return on day T predicts B's return on day T+1 through T+5 using Granger causality (simple, not deep)
- Pairs with statistically significant lead-lag (p < 0.05) get a directed edge in the graph with the lag offset stored

### Manual overrides (domain knowledge layer)
- `config/relationships/supply_chain.yaml` — structured YAML:
  ```yaml
  relationships:
    - leader: AMAT
      followers: [LRCX, KLAC, ASML]
      relationship_type: supply_chain
      sector: semiconductors
      typical_lag_days: 1-3
    - leader: TSLA
      followers: [RIVN, LCID, NIO]
      relationship_type: competitive
      sector: ev
      typical_lag_days: 0-1
  ```
- Manual relationships are always included in the graph regardless of whether correlation threshold is met
- Manual entries require human review and comment explaining the business rationale

### Graph structure
- `adapters/ml/cross_asset_graph.py` — builds and queries the graph
- NetworkX DiGraph: nodes = tickers, edges = (leader, follower) with weight = correlation, lag = days
- Query: `get_upstream_signals(ticker)` returns signals from all leaders of a given ticker
- Query: `get_contagion_risk(ticker)` returns followers at risk if this ticker breaks down

### Feature integration
- New feature group `cross_asset` added to feature matrix: `upstream_leader_signal` (mean sentiment of upstream leaders), `cluster_momentum` (mean return of cluster peers), `lead_lag_divergence` (ticker return vs expected from leaders)
- These feed directly into the existing ensemble (ADR-003)

### Human review loop
- Auto-discovered clusters are written to `reports/cluster_review_YYYYMMDD.csv` each week
- User reviews and can promote clusters to manual overrides or add exclusions to `supply_chain.yaml`

## Alternatives Considered

- **Pure manual supply chain graph** — captures known relationships well, but misses novel clusters forming around emerging themes (space tech, AI infrastructure, GLP-1 drugs). Requires constant manual updates. Rejected as sole approach.
- **Pure auto-correlation** — fast to build, no maintenance. But finds spurious correlations (two unrelated stocks that happened to both rise in 2024 bull run). Without domain filter, generates false contagion signals. Rejected as sole approach.
- **Graph Neural Network (GNN)** — most sophisticated approach. Learns relationship weights end-to-end. Too complex for current phase, requires significant training data. Deferred to Phase 6. Rejected now.
- **Sector ETF proxy** — use ETF returns as sector proxies instead of building an explicit graph. Simpler, already partially implemented via `sector_relative_strength_6m`. Does not capture intra-sector supply chain directionality. Rejected as primary graph mechanism.

## Consequences

**Positive:**
- Enables contagion sell signals for ADR-026: if AMAT breaks down, warn LRCX holders before price reaction
- Lead-lag features create a novel signal dimension not in standard financial ML feature sets
- Config-driven manual overrides let domain knowledge accumulate over time without code changes
- Human review loop prevents the model from acting on statistically spurious but economically nonsensical correlations

**Negative:**
- 60-day rolling correlation matrix for 350 tickers = 350x350 matrix computed weekly. Computationally manageable (~seconds) but adds to weekly tournament runtime
- Granger causality testing at scale (all pairs) requires multiple testing correction (Bonferroni or BH) to avoid false positives — must be implemented carefully
- `supply_chain.yaml` maintenance is a permanent ongoing responsibility — stale entries (companies that changed business models) can create wrong signals
- Lead-lag features are derived from the same price history used for technical features — correlation is not causation, and these features may reflect regime-specific patterns that don't generalize

## Superseded By
None
