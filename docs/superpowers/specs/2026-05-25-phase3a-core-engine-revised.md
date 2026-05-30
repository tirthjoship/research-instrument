# Design Spec: Multi-Modal Stock Recommender — Phase 3A Core Engine (Revised)

**Date:** 2026-05-25
**Status:** Approved
**Author:** Tirth Joshi + Claude Code
**Branch:** dev/structural-updates
**Scope:** Phase 3A — Pretrained Technical Pipeline (working predictions from historical data)
**Supersedes:** 2026-05-23-stock-recommender-phase3-design.md (Phase 3A portion only)

---

## 1. Thesis (unchanged)

**Combined hypothesis:** Sentiment leads price by X hours. When that lead signal diverges from technical indicators, the divergence predicts short-term direction with Y accuracy.

Phase 3A tests the first half: **Can technical + regime + macro features alone predict multi-horizon stock returns above random baseline with statistical significance?**

Phase 3B tests the second half: **Does adding sentiment/buzz features provide measurable lift over Phase 3A's technical-only model?**

## 2. What Changed Since Original Spec

Grilling session (2026-05-25) produced 10 architectural improvements captured in ADR-008 through ADR-017:

| Change | ADR | Impact |
|--------|-----|--------|
| Parallel NLP baselines (keyword + Flan-T5) | 008 | Phase 3B — eliminates scorer ambiguity |
| Ridge classifier in ensemble | 009 | Model family diversity |
| 2-3 year historical pretraining | 010 | Solves features-vs-data ratio |
| Rigorous evaluation (significance, walk-forward, costs) | 011 | Statistical rigor |
| Phase 3A/3B split | 012 | Clean separation |
| Macro regime features | 013 | Market environment awareness |
| Two-stage stacking model | 014 | Preserves pretrained knowledge |
| Multi-horizon threshold targets | 015 | Actionable predictions, hold duration |
| Three-layer data quality gates | 016 | Pipeline resilience |
| Raw data caching | 017 | Reproducibility |

## 3. System Overview — Phase 3A

A pretrained stock prediction pipeline that:
- Pulls 2-3 years of historical OHLCV, options, analyst, and macro data via yfinance
- Computes 45 features across 8 groups per ticker per week
- Trains XGBoost + LightGBM + Ridge ensemble via walk-forward validation
- Predicts return magnitude at 2-day, 5-day, and 10-day horizons
- Grades predictions using multi-horizon threshold classification
- Evaluates with permutation tests, transaction costs, regime splits, and drawdown tracking
- Stores results in SQLite
- Caches all raw data for reproducibility
- Runs via CLI and GitHub Actions

## 4. Architecture

Hexagonal (Ports and Adapters). Domain layer has zero external imports.

```
domain/                          # Pure business logic
  models.py                      # Signal, Sentiment, BacktestResult,
                                 #   TechnicalIndicators, DivergenceSignal,
                                 #   StockRecommendation, RecommendationGrade,
                                 #   WeeklyReport, AccuracyRecord,
                                 #   MultiHorizonPrediction
  ports.py                       # MarketDataPort, TechnicalAnalysisPort,
                                 #   RecommendationStorePort,
                                 #   (Phase 3B: NewsDiscoveryPort, BuzzScorerPort,
                                 #    SentimentScorerPort)
  services.py                    # validate_point_in_time_access(),
                                 #   compute_divergence_score(),
                                 #   grade_from_horizons(),
                                 #   validate_feature_matrix(),
                                 #   validate_data_freshness()
  exceptions.py                  # DomainError, InvalidMarketDataError,
                                 #   InvalidPredictionError, LookAheadBiasError,
                                 #   InsufficientDataError, StaleDataError

adapters/
  data/
    yfinance_adapter.py          # MarketDataPort + TechnicalAnalysisPort
    sqlite_store.py              # RecommendationStorePort
    cache_mixin.py               # CachingMixin base class
  ml/
    xgboost_predictor.py         # StockPredictorPort
    lightgbm_predictor.py        # StockPredictorPort
    ridge_predictor.py           # StockPredictorPort
    ensemble_predictor.py        # StockPredictorPort (XGB + LGBM + Ridge)
    feature_engineer.py          # Computes 45 features from raw data

application/
  use_cases.py                   # PretrainingUseCase,
                                 #   WeeklyTournamentUseCase,
                                 #   TrackRecommendationsUseCase,
                                 #   EvaluationUseCase
  cli.py                         # CLI entry point
  evaluation.py                  # WalkForwardValidator, PermutationTester,
                                 #   TransactionCostModel, RegimeSplitter,
                                 #   DrawdownTracker

config/
  markets/
    us.yaml                      # US market configuration

data/
  cache/                         # Raw API response cache (gitignored)
  recommendations.db             # SQLite store
```

## 5. Feature Groups (45 features — Phase 3A)

### Technical Features (15) — from yfinance OHLCV
- Price action: return_1d, return_5d, return_20d, volatility_20d, price_vs_sma20, price_vs_sma50, sma20_vs_sma50
- Momentum: rsi_14, macd, macd_signal, macd_histogram, stochastic_k, stochastic_d
- Volume: volume_ratio_20d, obv_trend

### Regime Features (10) — from yfinance 2-3yr history
- price_vs_52w_high, price_vs_52w_low
- market_cap_quintile
- return_6m, return_12m (strongest documented momentum factor)
- volatility_regime (current vs 1yr history)
- drawdown_from_ath
- sector_relative_strength_6m
- revenue_growth_yoy
- pe_vs_sector_median

### Stronger Signal Features (7) — from yfinance
- short_interest_ratio, short_interest_change_5d
- earnings_surprise_last, earnings_surprise_streak
- iv_skew_25d, iv_rank_percentile
- institutional_ownership_change

### Sector Context (2) — from sector ETFs via yfinance
- sector_etf_return_5d, stock_vs_sector
- (sector_buzz_ratio deferred to Phase 3B — requires buzz data)

### Options Flow (4) — from yfinance options chain
- unusual_options_volume, put_call_ratio, options_volume_vs_stock_volume, large_block_trades_count

### Cross-Correlation (2) — computed from yfinance
- correlation_with_spy, relative_strength_vs_peers

**Phase 3A total: 15 + 10 + 7 + 2 + 4 + 2 + 5 = 45 features**

### Macro Regime (5) — global features, same for all tickers per week
- vix_level (^VIX)
- treasury_10y_direction (^TNX)
- dxy_strength (DX-Y.NYB)
- yield_curve_slope (^TNX - ^IRX)
- spy_momentum_20d (SPY)

### Phase 3B additions (not in 3A)
- 11 sentiment/buzz features
- 4 divergence features
- 1 sector_buzz_ratio (deferred from sector context)
- Total with 3B: 61 features

## 6. Target Variables — Multi-Horizon Magnitude (ADR-015)

| Horizon | Target | Noise threshold | Signal type |
|---------|--------|-----------------|-------------|
| 2-day | predicted_return_2d | ±1.5% | News reaction, momentum |
| 5-day | predicted_return_5d | ±2.0% | Trend confirmation |
| 10-day | predicted_return_10d | ±3.0% | Value recovery, rotation |

Classification from magnitude:
- **Bullish:** predicted return > positive threshold
- **Neutral:** within ±threshold (noise — no action)
- **Bearish:** predicted return < negative threshold

## 7. Grading Logic — Multi-Horizon (ADR-015)

| Grade | Criteria |
|-------|----------|
| Strong Buy | Bullish on 2+ horizons AND magnitude > 5% on longest bullish horizon |
| Buy | Bullish on 1+ horizon AND magnitude > threshold |
| Hold | Neutral on all horizons OR conflicting signals |
| May Sell | Bearish on 1+ horizon |
| Immediate Sell | Bearish on 2+ horizons AND magnitude > -3% |

Hold duration emerges from horizon disagreement:
- Bullish 2d, neutral 5d → short hold (2-3 days)
- Neutral 2d, bullish 10d → longer hold (5-10 days)
- Bullish all horizons → strong conviction

## 8. Model Architecture — Two-Stage Stacking (ADR-014)

### Phase 3A: Stage 1 Only

```
Stage 1: Pretrained Technical Model
  ├── Input:  45 features (all Phase 3A features)
  ├── Training: 2-3 years historical data, walk-forward
  ├── Models: XGBoost + LightGBM + Ridge (per horizon)
  ├── Output: predicted_return_{2d,5d,10d}, confidence
  └── Retrain: Monthly full retrain
```

Three separate ensemble instances — one per horizon. Each ensemble = XGBoost + LightGBM + Ridge averaged (weighted by recent accuracy).

### Phase 3B: Adds Stage 2

```
Stage 2: Sentiment Blending Model
  ├── Input:  Stage 1 outputs (6: 3 returns + 3 confidences) + 15 sentiment features = 21 features
  ├── Training: 90-day backfill + weekly accumulation
  ├── Models: Shallow XGBoost (max_depth=3) or Ridge per horizon
  ├── Output: final_predicted_return_{2d,5d,10d}, final_confidence
  ├── Retrain: Weekly warm-start, monthly full retrain
  └── Decay: 8-week half-life on sample weights
```

## 9. Pretraining Pipeline

### Data Collection
- yfinance: 2-3 years OHLCV, options chain, analyst recommendations for all stocks that appeared in S&P 500 + popular ETF holdings during the period
- Macro: VIX, TNX, DXY, IRX, SPY for same period
- Known universe snapshots: list of valid tickers per month (partial survivorship bias mitigation)

### Walk-Forward Training
```
For each month M in [2024-01 ... 2026-04]:
  Train on all data before M
  Predict all tickers in month M
  Record predictions vs actuals for all three horizons
  Slide forward
```

### Evaluation on Pretrained Model
- Directional accuracy per horizon
- Permutation test (1000 shuffles) per horizon
- Transaction cost-adjusted returns (0.1% per trade)
- Regime-split performance (bull/sideways/bear based on SPY)
- Maximum drawdown and recovery time
- Sharpe ratio vs SPY benchmark

## 10. Data Quality Gates (ADR-016)

### Layer 1: Adapter-Level
| Adapter | Validation | On failure |
|---------|-----------|------------|
| yfinance | Min 20 trading days, <50% NaN, price > 0 | Skip ticker |
| Options chain | Non-empty | NaN features (trees handle) |

### Layer 2: Feature-Level
| Problem | Action |
|---------|--------|
| Missing OHLCV ≤3 days | Forward-fill |
| Missing OHLCV >3 days | Skip ticker |
| Price outlier ±30% single day | Cap at ±30%, log |
| Volume outlier >20x avg | Keep (signal) |
| Missing options/analyst data | NaN features |
| Stale data >3 days | StaleDataError, skip |

### Layer 3: Pipeline-Level
| Check | Threshold | Action |
|-------|-----------|--------|
| Qualified tickers ≥15 | Normal | Full run |
| Qualified tickers 5-14 | Degraded | Fewer picks, log warning |
| Qualified tickers <5 | Abort | InsufficientDataError |
| Feature NaN <5% | Normal | Impute silently (column median) |
| Feature NaN 5-30% | Warning | Impute, log which features |
| Feature NaN >30% | Abort | Data quality too low |

## 11. Raw Data Caching (ADR-017)

Every adapter caches raw API response before processing.

```
data/cache/
  yfinance/{symbol}/{YYYY-MM-DDTHH:MM:SS}.parquet
```

- Live mode (`use_cache=False`): fetch API, save to cache
- Replay mode (`use_cache=True`): load from cache, deterministic results
- Append-only: never overwrite past fetches
- ~50MB/week, gitignored

## 12. Point-in-Time Enforcement

- `validate_point_in_time_access()`: all timestamps ≤ prediction_time
- `LookAheadBiasError`: halts pipeline on violation
- `auto_adjust=False` on yfinance: raw prices, not retroactively adjusted
- Known universe snapshots: list of valid tickers per backtest date
- Documented limitations: survivorship bias partially mitigated, not eliminated

### FUTURE_LEAKAGE_COLUMNS (must never appear in features)
- next_day_return, next_week_return, future_earnings_surprise, forward_pe_ratio

## 13. Evaluation Framework (ADR-011)

### Per-Horizon Metrics
| Metric | Benchmark |
|--------|-----------|
| Directional accuracy | 50% (random) |
| Magnitude MAE | Naive baseline (predict 0%) |
| Precision per threshold class (bullish/neutral/bearish) | Per-class baseline |

### Portfolio-Level Metrics
| Metric | Benchmark |
|--------|-----------|
| Cumulative return (cost-adjusted, 0.1%/trade) | SPY same period |
| Sharpe ratio | SPY Sharpe |
| Maximum drawdown | SPY max drawdown |
| Recovery time (days) | SPY recovery |

### Statistical Rigor
| Component | Threshold |
|-----------|-----------|
| Permutation test (1000 shuffles) | p < 0.05 or result is luck |
| Walk-forward validation | All metrics from walk-forward, never single split |
| Regime-aware splits | Bull/sideways/bear (SPY ±10% annualized) |

### Ablation (Phase 3A baseline for 3B comparison)
| Variant | Features | Purpose |
|---------|----------|---------|
| Technical-only (Phase 3A) | 45 features | Baseline — does price predict? |
| Technical + sentiment (Phase 3B) | 57 features (45 + 11 sentiment/buzz + 1 sector_buzz_ratio) | Does sentiment add lift? |
| Technical + sentiment + divergence (Phase 3B) | 61 features (57 + 4 divergence) | Does divergence add lift over raw sentiment? |

## 14. Storage Schema (SQLite)

```sql
CREATE TABLE recommendations (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    week_start TEXT NOT NULL,
    grade TEXT NOT NULL,
    composite_score REAL,
    predicted_return_2d REAL,
    predicted_return_5d REAL,
    predicted_return_10d REAL,
    confidence REAL,
    horizon_signals TEXT,          -- JSON: {"2d":"bullish","5d":"neutral","10d":"bullish"}
    sentiment_score REAL,
    divergence_score REAL,
    divergence_type TEXT,
    technical_signal REAL,
    rsi_14 REAL,
    macd REAL,
    reasoning TEXT,
    sources TEXT,                   -- JSON array
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(symbol, week_start)
);

CREATE TABLE accuracy_records (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    week_start TEXT NOT NULL,
    predicted_grade TEXT,
    predicted_return_2d REAL,
    predicted_return_5d REAL,
    predicted_return_10d REAL,
    actual_return_2d REAL,
    actual_return_5d REAL,
    actual_return_10d REAL,
    grade_correct INTEGER,
    direction_correct_2d INTEGER,
    direction_correct_5d INTEGER,
    direction_correct_10d INTEGER,
    held_weeks INTEGER DEFAULT 1,
    evaluated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(symbol, week_start)
);

CREATE TABLE evaluation_runs (
    id INTEGER PRIMARY KEY,
    run_date TEXT NOT NULL,
    eval_type TEXT NOT NULL,        -- 'walk_forward', 'permutation', 'regime'
    horizon TEXT NOT NULL,          -- '2d', '5d', '10d'
    metric_name TEXT NOT NULL,
    metric_value REAL,
    p_value REAL,
    regime TEXT,                    -- 'bull', 'sideways', 'bear', NULL
    details TEXT,                   -- JSON
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE weekly_reports (
    id INTEGER PRIMARY KEY,
    report_date TEXT NOT NULL UNIQUE,
    market TEXT NOT NULL,
    accuracy_vs_last_week REAL,
    spy_return_same_period REAL,
    max_drawdown REAL,
    sharpe_ratio REAL,
    transaction_costs REAL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_rec_week ON recommendations(week_start);
CREATE INDEX idx_rec_symbol ON recommendations(symbol);
CREATE INDEX idx_acc_week ON accuracy_records(week_start);
CREATE INDEX idx_eval_date ON evaluation_runs(run_date);
```

## 15. Testing Strategy

### Layer 1: Domain Tests (Pure, Fast)
- test_domain_models.py — all model validation, grade ordering, multi-horizon classification
- test_domain_services.py — divergence computation, grade_from_horizons, feature matrix validation, data freshness validation
- test_properties.py (Hypothesis) — sentiment bounded, divergence symmetric, grading monotonic, point-in-time never leaks, multi-horizon consistency

### Layer 2: Adapter Tests
- test_yfinance_adapter.py — mocked yfinance, point-in-time filtering, caching
- test_sqlite_store.py — in-memory SQLite, multi-horizon storage/retrieval
- test_feature_engineer.py — feature computation, NaN handling, outlier capping
- test_ml_predictors.py — XGBoost, LightGBM, Ridge, ensemble training and prediction

### Layer 3: Use Case Tests (End-to-End with Fakes)
- test_weekly_tournament.py — full pipeline with fakes, multi-horizon grading, data quality gate failures
- test_pretraining.py — walk-forward training, model persistence
- test_evaluation.py — permutation test, transaction costs, regime splits, drawdown

### Fake Adapters
```
tests/fakes/
  fake_market_data.py
  fake_technical_analysis.py
  fake_store.py
```

### Testing Principles
- No real API calls in CI — fakes for all ports
- Integration tests marked @pytest.mark.slow
- Leakage prevention: property test verifies no feature timestamp > prediction_time
- Grading consistency: property test verifies monotonic multi-horizon grading
- Reproducibility: all random seeds pinned
- Coverage: 90% gate, domain must be 100%

## 16. CLI Interface

```bash
# Pretraining
python -m application.cli pretrain --market us --start 2024-01 --end 2026-05

# Live tournament
python -m application.cli run-tournament --market us --date 2026-05-25

# Evaluate last week
python -m application.cli evaluate-last-week --date 2026-05-25

# Full evaluation report
python -m application.cli evaluate --type walk-forward --start 2024-01 --end 2026-05
python -m application.cli evaluate --type permutation --n-shuffles 1000

# Show past report
python -m application.cli show-report --week 2026-05-19
```

## 17. GitHub Actions

```yaml
name: Weekly Stock Tournament
on:
  schedule:
    - cron: '0 5 * * 0'     # Sunday 5:00 UTC
  workflow_dispatch:

jobs:
  weekly-tournament:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -e ".[dev]"
      - run: python -m application.cli run-tournament
      - run: python -m application.cli evaluate-last-week
      - run: |
          git config user.name "Stock Tournament Bot"
          git config user.email "bot@tournament"
          git add reports/ data/recommendations.db
          git diff --cached --quiet || git commit -m "feat: weekly picks $(date +%Y-%m-%d)"
          git push
```

## 18. Phase 3A Scope Summary

| Component | Count/Detail |
|-----------|-------------|
| Features | 45 (15 technical + 10 regime + 7 stronger + 2 sector + 4 options + 2 cross-corr + 5 macro) |
| Target variables | 3 horizons × magnitude regression |
| Model ensemble | XGBoost + LightGBM + Ridge per horizon (9 models total) |
| Pretraining | 2-3 years walk-forward |
| Evaluation | Permutation + walk-forward + cost-adjusted + regime + drawdown |
| Data quality | 3-layer gates (adapter → feature → pipeline) |
| Caching | All raw data cached at fetch time |
| Point-in-time | Timestamp checks + auto_adjust=False + known universe |
| Storage | SQLite with multi-horizon schema |
| New tests | ~60-70 |

## 19. What Phase 3B Adds (separate spec)

- Keyword + Flan-T5 zero-shot parallel NLP scorers
- RSS, Google CSE, Reddit, StockTwits adapters
- 15-20 additional sentiment/buzz/divergence features
- Stage 2 stacking model (blends sentiment with Stage 1 outputs)
- 90-day sentiment backfill
- Ablation: technical-only vs sentiment-only vs combined
- Recursive learning with 8-week decay half-life
- Marginal lift measurement

## 20. Decisions Log (updated)

| # | Decision | Choice | Why | ADR |
|---|----------|--------|-----|-----|
| 1 | Thesis | Sentiment-price lag + cross-modal divergence | Testable, contrarian, academically grounded | 001 |
| 2 | Stock universe | Dynamic buzz-driven | Avoids human bias | 002 |
| 3 | Model ensemble | XGBoost + LightGBM + Ridge | Tree + linear diversity | 003, 009 |
| 4 | NLP strategy | Keyword + Flan-T5 parallel | Eliminates scorer ambiguity | 005, 008 |
| 5 | Storage | SQLite | Zero setup, port-swappable | 006 |
| 6 | Deployment | GitHub Actions Sunday cron | Free, reliable | 007 |
| 7 | Pretraining | 2-3yr historical on technical features | Solves features-vs-data ratio | 010 |
| 8 | Evaluation | 5-component rigorous framework | Statistical significance required | 011 |
| 9 | Phasing | 3A (technical) + 3B (sentiment) | Clean ablation, manageable scope | 012 |
| 10 | Macro features | VIX, 10Y, DXY, yield curve, SPY momentum | Market environment awareness | 013 |
| 11 | Model architecture | Two-stage stacking | Preserves pretrained knowledge | 014 |
| 12 | Target variable | Multi-horizon magnitude + threshold | Actionable predictions, hold duration | 015 |
| 13 | Data quality | Three-layer validation gates | Pipeline resilience | 016 |
| 14 | Reproducibility | Raw data caching at fetch time | Deterministic replay | 017 |

## 21. Interview Story (updated)

"I hypothesized that sentiment-price divergence predicts short-term stock returns. I built a rigorous quantitative system to test this: 45 features across 8 categories, pretrained on 2-3 years of historical data using walk-forward validation. The model predicts return magnitude at three horizons (2-day, 5-day, 10-day) using an XGBoost+LightGBM+Ridge ensemble, with threshold-based classification to filter noise from actionable signals. Every result is validated with permutation tests for statistical significance, transaction cost modeling, and regime-aware evaluation. I then layered sentiment analysis on top and measured the exact marginal lift — proving whether social/news divergence from technicals adds alpha beyond what price data alone provides. The system runs autonomously via GitHub Actions, caches all raw data for reproducibility, and has three-layer data quality gates for production resilience."

---

*This spec covers Phase 3A only. Phase 3B (sentiment layer) will be a separate spec building on this foundation.*
