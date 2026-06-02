# ADR-030: Event-Causal Learning Architecture — Gemini Classification + Empirical Impact + Exponential Decay

**Status:** Accepted (2026-06-02)

**Context:** Phase 4D implements the event-causal learning layer from ADR-028. This ADR records the architectural and algorithmic decisions made during the Phase 4D brainstorming session.

## Decisions

### 1. LLM Classification: Gemini Free Tier (Option B)

Use Google Gemini API free tier (15 RPM, 1.5M tokens/day, zero cost) for structured event classification of news headlines. Temperature=0 for determinism. `google-generativeai` package.

**Rejected alternatives:**
- Local LLM (Ollama) — heavy dependency, mediocre quality at 7-8B, not reproducible for recruiters
- Claude API — costs money, no free tier at sufficient volume
- Google AI Mode (search bar) — consumer feature, not an API, can't call programmatically
- Rule-based only — less impressive for portfolio, misses ambiguous events

### 2. Event Categories: 10 Types (Option A)

| Category | Example |
|----------|---------|
| `earnings_surprise` | "NVDA beats estimates by 20%" |
| `tariff_trade` | "US imposes 25% tariff on Chinese goods" |
| `fda_approval` | "FDA approves Lilly's weight loss drug" |
| `interest_rate` | "Fed holds rates steady" |
| `antitrust_regulation` | "DOJ sues Google over ad monopoly" |
| `geopolitical` | "China-Taiwan tensions escalate" |
| `labor_layoffs` | "Intel announces 15,000 layoffs" |
| `supply_chain_disruption` | "TSMC fab hit by earthquake" |
| `product_launch` | "Apple announces AR glasses" |
| `macro_data` | "CPI comes in hot at 4.2%" |

10 covers most market-moving events without sparse data problems.

### 3. Historical Impact Data: Bootstrap from GDELT + Gemini (Option A)

Classify stored GDELT historical news headlines (2015-present) using Gemini, then correlate event dates with actual sector ETF returns in following days. Build impact table empirically.

Portfolio story: "I classified 3 years of GDELT news into 10 categories, then measured actual sector impact with decay curves."

**Rejected:** Hardcoded impact table (not "learning"), pure manual (not data-driven).

### 4. Decay Model: Exponential with Learned Half-Life (Option A)

`impact(t) = magnitude × 0.5^(t/half_life)`

Two parameters per event_category × sector pair: `magnitude` and `half_life`. Fit from historical data. Standard in event studies, interpretable.

**Rejected:** Fixed windows (less elegant), regime-conditioned decay (overfits with sparse data).

### 5. Features: 8 Event-Causal Features

| Feature | Description |
|---------|-------------|
| `event_impact_score` | Sum of all active decaying impacts for ticker's sector |
| `event_impact_max` | Strongest single active event impact |
| `event_count_7d` | Classified events affecting sector in past 7 days |
| `event_sentiment_direction` | Net direction of active events (+1/-1) |
| `event_half_life_avg` | Avg half-life of active events |
| `event_surprise_factor` | Actual sector return vs expected from impact table |
| `event_category_dominant` | Numeric encoding of dominant active event type |
| `event_decay_phase` | Position in decay curve (0=peak, 1=tail) |

## Consequences

**Positive:**
- Novel feature layer — event-causal impact with learned decay is not standard in financial ML
- Free (Gemini free tier)
- Empirically grounded — impact table built from real data
- Interpretable — "tariffs have 8-day half-life on energy"

**Negative:**
- Gemini API dependency (external service)
- Classification quality depends on model (may need prompt tuning)
- Sparse events per category — some categories may have <50 historical examples
- Decay fit may be noisy with few data points

**Risks:**
- Gemini free tier rate limits may slow historical classification
- Event categories may overlap (macro_data vs interest_rate)
- Features may have near-zero SHAP importance
- Overfitting 2 parameters on <50 events per category×sector

**Mitigation:** Build, measure with SHAP, prune if useless. Same philosophy as all previous phases.
