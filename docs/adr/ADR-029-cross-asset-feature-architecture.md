# ADR-029: Cross-Asset Feature Architecture — Port + Dual Adapter + Granger Pre-Filter

**Status:** Accepted (2026-06-02)

**Context:** Phase 4C implements the cross-asset intelligence layer from ADR-027. This ADR records the architectural and algorithmic decisions made during the Phase 4C brainstorming session.

## Decisions

### 1. Scope: Pragmatic + Granger (Option B+)

Include rolling correlation matrix, hierarchical clustering, Granger causality, manual supply chain YAML, and ~8 cross-asset features. Skip cascade detection use case (deferred to Phase 5 dashboard). Rationale: Granger causality is cheap to compute; we won't know if lead-lag signals are real without testing. Same lesson as Phase 3A — build, measure, prune.

### 2. Granger Pre-Filter: Correlation Threshold (Option A)

Only run Granger causality on pairs with |correlation| > 0.65 (ADR-027 threshold). At 350 tickers, the full 122,500-pair matrix is too expensive. Pre-filtering by correlation reduces to ~200-500 candidate pairs. Benjamini-Hochberg correction for multiple testing on survivors.

**Rejected alternatives:**
- Sector-constrained only — misses cross-sector relationships (energy→airlines)
- Both correlation + sector — too conservative, supply chain YAML already covers known cross-sector
- Run all + correct — computationally heavy for marginal discovery benefit

### 3. Supply Chain YAML: 10 Groups (Option A+)

Ship all 6 groups from ADR-027 grilling session plus 4 additional:
- AI Supply Chain (NVDA → SMCI/DELL/HPE → MSFT/GOOG/META)
- Cloud/SaaS (MSFT/AMZN/GOOG → SNOW/DDOG/NET/MDB/CRWD)
- Financials Chain (JPM/GS/MS → SCHW/IBKR → V/MA/AXP)
- Housing/Rates (LEN/DHI/PHM → HD/LOW)

All relationships are well-documented and defensible. YAML config only — no code difference for more groups.

### 4. Feature Architecture: Separate Analyzer + Feature Engineer (Option C)

Two files with clear responsibilities:
- `adapters/ml/correlation_analyzer.py` — builds NetworkX graph, computes correlations, runs Granger, merges manual overrides. Implements `CrossAssetPort`.
- `adapters/ml/cross_asset_features.py` — extracts ~8 features from the graph for a given ticker. Implements `FeatureEngineerPort` pattern.

Rationale: matches hexagonal pattern. Same separation as yfinance_adapter (data) + feature_engineer (features).

### 5. New Port: CrossAssetPort (Option A)

Add `CrossAssetPort` protocol to `domain/ports.py` with:
- `build_graph()` — construct correlation graph from signals
- `get_upstream_signals()` — leaders for a ticker
- `get_cluster_peers()` — correlation cluster members
- `get_correlation()` — pairwise correlation lookup

Even though it's internal computation, the graph could come from different sources (pre-computed, cached, external API). Port keeps it swappable.

## Consequences

**Positive:**
- 8 novel features not in standard financial ML (interview differentiator)
- Granger causality may reveal real lead-lag structure (testable hypothesis)
- 10 supply chain groups show domain knowledge
- Clean hexagonal architecture (port + adapter separation)

**Negative:**
- NetworkX dependency added
- Weekly graph rebuild adds ~seconds of compute
- Granger on 200-500 pairs with BH correction may yield few significant results
- Supply chain YAML is permanent maintenance

**Risks:**
- Lead-lag features may be regime-specific (correlation clusters shift in bear markets)
- Granger significance doesn't imply economic significance
- Features may have near-zero SHAP importance (like 32/45 in Phase 3A)

**Mitigation:** Build, measure with SHAP, prune if useless. Data-driven, not intuition-driven.
