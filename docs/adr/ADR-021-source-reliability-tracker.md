# ADR-021: Source Reliability Tracker

**Date:** 2026-05-30
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context

Phase 3B adds sentiment from multiple sources (RSS publishers, Reddit). Not all sources are equally reliable — a Reuters article and a Reddit shitpost carry different signal quality. Without tracking which sources are directionally accurate, the model treats all sentiment equally, diluting signal from reliable sources with noise from unreliable ones.

The BUZZ ETF failure (VanEck, see ADR-011 context) showed that raw buzz aggregation doesn't work. Source quality differentiation is a potential edge.

## Decision

Add a `SourceReliabilityPort` to the domain layer with a `SourceReliability` model. Track per-source, per-ticker directional accuracy over rolling windows. Store in SQLite `source_reliability` table. Use reliability scores to weight sentiment features.

### Domain Model

```python
@dataclass(frozen=True)
class SourceReliability:
    source: str          # e.g., "reuters_rss", "reddit_wsb"
    ticker: str | None   # None = aggregate across all tickers
    correct_calls: int
    total_calls: int

    @property
    def accuracy(self) -> float:
        if self.total_calls < 10:
            return 0.5  # uninformative prior
        return self.correct_calls / self.total_calls
```

### Port Protocol

```python
class SourceReliabilityPort(Protocol):
    def record_outcome(self, source, ticker, predicted_direction, actual_direction) -> None
    def get_reliability(self, source, ticker=None) -> SourceReliability
    def get_all_reliabilities(self) -> list[SourceReliability]
```

### SQLite Schema

```sql
source_reliability (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    ticker TEXT,
    correct_calls INTEGER DEFAULT 0,
    total_calls INTEGER DEFAULT 0,
    last_updated TIMESTAMP,
    UNIQUE(source, ticker)
)
```

### How It Integrates

1. Daily scan stores buzz signals with `source` tag
2. Weekly tournament runs predictions
3. After outcomes known (next week), `record_outcome()` updates source accuracy
4. `source_weighted_sentiment` feature = `avg_sentiment × source_accuracy`
5. `top_source_reliability` feature = best source's accuracy for that ticker
6. Stage 2 XGBoost learns optimal weighting via these features

### Key Design Choices

- **Uninformative prior (0.5)** until 10+ calls recorded — prevents cold-start bias
- **Per-ticker tracking** — Reuters may be reliable for tech but not energy
- **Passive tracker** — records and reports, doesn't filter. ML model decides how much to weight.
- **Rolling window** — 90 days (configurable). Old outcomes expire to adapt to source quality changes.

## Alternatives Considered

- **No source tracking** — treat all sources equally. Rejected: dilutes signal from reliable sources.
- **Hard source filtering** — drop sources below accuracy threshold. Rejected: too aggressive, loses data. Let ML decide.
- **Bayesian reliability** — Beta distribution per source. Deferred: simpler frequency counting sufficient for Phase 3B.

## Consequences

**Positive:**
- Every sentiment signal has provenance — can explain "why this recommendation"
- Source quality improves over time as tracker accumulates data
- Differentiator from naive buzz ETFs that treat all mentions equally
- Interview story: "Our system learns which sources to trust"

**Negative:**
- Needs 10+ outcomes per source before accuracy is meaningful (~2-3 months)
- Initial period uses uninformative prior (0.5) — no benefit until data accumulates
- Accepted: tracker is baked in from day one specifically to accumulate data early

## Superseded By
None
