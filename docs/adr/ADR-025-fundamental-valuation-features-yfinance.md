# ADR-025: Fundamental Valuation Features from yfinance

**Date:** 2026-06-01
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context

The current 45-feature matrix (built in Phase 3A) is entirely price- and volume-derived: technical indicators, regime features, correlation features, macro proxies. This is intentional for the initial hypothesis test, but it leaves a major signal dimension untested.

Valuation context matters. A stock with MACD bullish and sentiment positive but trading at 80x P/E with negative FCF is very different from the same technical + sentiment setup at 15x P/E with strong FCF growth. The model currently cannot distinguish these cases.

yfinance already provides fundamental data via `ticker.info` (a dict with 100+ fields). The data is available in the existing `YFinanceAdapter` — it just hasn't been extracted into the feature matrix. No new API dependency is needed.

Key available fields: `trailingPE`, `priceToBook`, `pegRatio`, `freeCashflow`, `dividendYield`, `returnOnEquity`, `debtToEquity`, `revenueGrowth`, `earningsGrowth`, `enterpriseToEbitda`.

## Decision

Add ~15 fundamental features as a new named feature group (`fundamental`) in the feature matrix. Implement a dedicated `FundamentalFeatureEngineer` adapter that implements the `FeatureEngineerPort` protocol.

Feature list:
- `pe_ratio` — trailing P/E (NaN for unprofitable companies)
- `peg_ratio` — P/E to growth ratio
- `price_to_book` — P/B ratio
- `ev_to_ebitda` — enterprise value / EBITDA
- `free_cashflow_yield` — FCF / market cap (normalized)
- `dividend_yield` — annual dividend / price
- `return_on_equity` — ROE
- `debt_to_equity` — leverage ratio
- `revenue_growth_yoy` — year-over-year revenue growth rate
- `earnings_growth_yoy` — year-over-year earnings growth rate
- `gross_margin` — gross profit / revenue
- `operating_margin` — operating income / revenue
- `current_ratio` — current assets / current liabilities
- `valuation_z_score` — composite: z-score of (pe_ratio + peg_ratio + price_to_book + ev_to_ebitda). Lower = cheaper. Inspired by SimplyWallSt fair value methodology.
- `quality_score` — composite: z-score of (roe + fcf_yield + gross_margin - debt_to_equity). Higher = better quality business.

Missing fundamentals (e.g., non-US companies, unprofitable tech) are imputed with sector median, consistent with ADR-018 imputation strategy.

`FundamentalFeatureEngineer` fetches from the already-cached `ticker.info` dict, so no additional yfinance calls are needed when ADR-017 cache is warm.

## Alternatives Considered

- **External fundamental data API (Simplywall.st, Quiver Quant, Intrinio)** — adds cost and dependency. yfinance already has it. Rejected.
- **Skip fundamentals entirely** — leaves a known signal dimension unexplored. The SHAP analysis from Phase 3A showed 32/45 features near-zero; adding a new dimension with stronger prior signal probability is justified. Rejected.
- **FactSet / Bloomberg data** — institutional quality but requires expensive subscriptions. Out of scope for a portfolio project. Rejected.
- **Compute valuation scores manually from financial statements** — quarterly filing scraping, complex normalization. Far more work than using the already-available `ticker.info`. Rejected.

## Consequences

**Positive:**
- Adds a qualitatively different signal dimension with strong financial theory backing
- Zero new API dependencies — all data from existing `ticker.info` cache
- `valuation_z_score` and `quality_score` composites give the model a direct "cheap quality" signal, which maps directly to known factor investing returns (value + quality premium)
- SHAP analysis in Phase 4 backtest will show whether fundamentals dominate over technical features or complement them

**Negative:**
- `ticker.info` is not point-in-time — it returns current fundamentals. For historical backtests, fundamental data at past dates is unavailable via yfinance. This introduces a mild look-ahead bias in historical backtests (using today's P/E to predict 2024 prices). Mitigated by noting it in evaluation reports and scoping backtests as "directionally indicative, not precise."
- Sector median imputation for missing fundamentals requires sector assignment — adds a dependency on `config/markets/us.yaml` sector map
- Feature matrix grows from 45 to ~60 features. XGBoost handles this well; ridge regularization may need retuning

## Superseded By
None
