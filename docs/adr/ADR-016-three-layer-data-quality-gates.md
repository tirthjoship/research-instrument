# ADR-016: Three-layer data quality gates with graduated failure modes

**Date:** 2026-05-25
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context
Pipeline has zero data validation between adapter output and model training. Real financial data has: missing values (halted stocks, API failures), outliers (40% gap-ups, 50x volume spikes, extreme sentiment), stale data (weekend caching, API rate limits). Unhandled, these corrupt model training and produce unreliable predictions.

## Decision
Three validation layers with different failure modes:

### Layer 1: Adapter-Level Validation
Each adapter validates its own output before returning. Failure = skip source for that ticker, not kill pipeline. Other sources still contribute.

- yfinance: min 20 trading days, no >50% NaN, price > 0
- RSS: valid XML parse, has title + link fields
- Reddit/StockTwits: API 200 response, non-empty
- Google CSE: valid JSON, within daily quota

### Layer 2: Feature-Level Validation
After adapters return, before feature engineering:

| Problem | Action |
|---------|--------|
| Missing OHLCV (gap ≤3 days) | Forward-fill |
| Missing OHLCV (gap >3 days) | Skip ticker |
| Price outlier (single day ±30%) | Cap at ±30%, log |
| Volume outlier (>20x avg) | Keep (meme activity is signal) |
| Sentiment outlier (±1.0 extreme) | Winsorize at 5th/95th percentile |
| Missing options chain | NaN features (tree models handle natively) |
| Zero sentiment texts | Neutral (0.0), flag low_sentiment_coverage |
| Stale data (>3 days old) | StaleDataError, skip ticker |

### Layer 3: Pipeline-Level Validation
After filtering and feature engineering, before prediction:

| Check | Threshold | Action |
|-------|-----------|--------|
| Qualified tickers | ≥15 | Normal run |
| Qualified tickers | 5-14 | Degraded run, fewer picks, log warning |
| Qualified tickers | <5 | Abort: InsufficientDataError |
| Feature NaN rate | <5% | Impute silently (column median) |
| Feature NaN rate | 5-30% | Impute, log which features |
| Feature NaN rate | >30% | Abort: data quality too low |
| Data freshness | All data >5 days old | Abort: stale predictions dangerous |

### Architecture placement
- `domain/services.py`: validate_feature_matrix(), validate_data_freshness() — pure validation rules
- `adapters/*`: each adapter validates its own output — data-specific checks
- `application/use_cases.py`: pipeline-level gates — orchestration decisions
- Domain stays pure: validation functions take dicts/lists, know nothing about adapters

### Key principles
- **Impute** when missing data is one dimension of many
- **Skip ticker** when core data is unreliable
- **Abort pipeline** only when overall data quality is below minimum viable threshold
- **Never hallucinate** data — imputation uses column median or neutral defaults, never synthetic values
- **Always log** what was imputed, skipped, or flagged — audit trail for debugging

## Alternatives Considered
- **No validation (status quo)** — corrupt data reaches model. Rejected.
- **Strict validation (fail on any issue)** — too many aborted runs from minor data gaps. Rejected.
- **Single validation layer** — can't distinguish adapter failures from pipeline failures. Rejected.

## Consequences
**Positive:**
- Pipeline is resilient to partial data failures.
- Graduated failure modes: degrade gracefully, don't crash on minor issues.
- Audit trail: every imputation and skip is logged.
- Domain purity preserved: validation rules in services, not adapters.

**Negative:**
- More code to maintain (validation at three layers).
- Accepted: data quality is the foundation — worth the investment.
- Imputation introduces small biases (median fill).
- Accepted: better than NaN propagation or crashes.

## Superseded By
None
