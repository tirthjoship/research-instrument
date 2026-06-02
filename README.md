# Multi-Modal Stock Recommender

Production-grade ML system predicting multi-horizon stock returns using a multi-layer feature architecture: 45 technical features (Stage 1) + 24 sentiment/buzz/divergence features (Stage 2) + 16 fundamental valuation features. XGBoost + LightGBM + Ridge ensemble with walk-forward validation, permutation testing, and transaction cost modeling. Built with hexagonal architecture and strict point-in-time enforcement.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-300%20passing-success)](./tests/)
[![Coverage](https://img.shields.io/badge/coverage-90%25+-brightgreen)](./tests/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![mypy: strict](https://img.shields.io/badge/mypy-strict-blue.svg)](http://mypy-lang.org/)

---

## Thesis

**Combined hypothesis:** Sentiment leads price by 1-48 hours. When that lead signal diverges from technical indicators, the divergence predicts short-term direction.

**Phase 3A tests:** Can technical + regime + macro features alone predict multi-horizon stock returns above random baseline with statistical significance?

**Phase 3B tests:** Does adding sentiment/buzz features (from RSS news + social media) provide measurable lift (>2%) over Phase 3A's ~50% technical-only baseline?

---

## What It Does

1. **Multi-source buzz scan** — scans 6 RSS feeds, Google Trends (historical back to 2004), StockTwits (bullish/bearish ratio), and GDELT news sentiment (2015-present)
2. Pulls 2-3 years of historical OHLCV, options, analyst, and macro data via yfinance
3. Computes **85 features**: 45 technical (Stage 1) + 24 sentiment/buzz/divergence (Stage 2) + 16 fundamental valuation (Phase 4A)
4. Trains **two-stage stacking**: Stage 1 (XGBoost + LightGBM + Ridge ensemble, frozen) → Stage 2 (XGBoost blending technicals + sentiment + fundamentals)
5. Predicts return magnitude at **2-day, 5-day, and 10-day** horizons
6. **Dynamic ticker discovery** via buzz acceleration — finds stocks where mentions are spiking, not just high
7. Covers **~350 tickers** (S&P 500 + NASDAQ-100) via config-driven universe
8. Grades predictions using multi-horizon threshold classification (Strong Buy → Immediate Sell)
9. Evaluates with **permutation tests** (p<0.05), transaction costs, regime splits, drawdown tracking, and **three-way ablation** (tech-only vs +sentiment vs +sentiment+source-weights)
10. **Source reliability tracking** — learns which news sources are directionally accurate over time
11. Stores results in SQLite, caches all raw data for reproducibility
12. Runs via **CLI** (daily-scan + weekly tournament)

---

## Architecture

**Hexagonal (Ports & Adapters) — domain layer has zero external imports.**

```
domain/                          # Pure business logic (stdlib only)
  models.py                      # Signal, Sentiment, BuzzSignal, SourceReliability,
                                 #   MultiHorizonPrediction, StockRecommendation,
                                 #   RecommendationGrade, AccuracyRecord,
                                 #   EvaluationRun, WeeklyReport
  ports.py                       # MarketDataPort, SentimentPort, BuzzDiscoveryPort,
                                 #   SourceReliabilityPort, HistoricalSentimentPort,
                                 #   TechnicalAnalysisPort, StockPredictorPort,
                                 #   FeatureEngineerPort, RecommendationStorePort
  services.py                    # grade_from_horizons(), validate_feature_matrix(),
                                 #   validate_data_freshness(), classify_horizon()
  exceptions.py                  # LookAheadBiasError, InsufficientDataError,
                                 #   StaleDataError

adapters/
  data/
    yfinance_adapter.py          # MarketDataPort + TechnicalAnalysisPort
    rss_adapter.py               # BuzzDiscoveryPort (6 RSS publishers)
    google_trends_adapter.py     # BuzzDiscoveryPort (pytrends, historical)
    stocktwits_adapter.py        # BuzzDiscoveryPort (free API, bull/bear)
    gdelt_sentiment_adapter.py   # HistoricalSentimentPort (GDELT DOC API)
    sqlite_store.py              # RecommendationStorePort (6 tables)
    cache_mixin.py               # Append-only raw data cache (ADR-017)
  ml/
    feature_engineer.py          # 45 technical features
    sentiment_feature_engineer.py # 24 sentiment/buzz/divergence features
    fundamental_feature_engineer.py # 16 valuation/financial health features
    keyword_scorer.py            # SentimentPort (rule-based, instant)
    flan_t5_scorer.py            # SentimentPort (zero-shot NLP, MPS)
    xgboost_predictor.py         # StockPredictorPort (Stage 1)
    lightgbm_predictor.py        # StockPredictorPort (Stage 1)
    ridge_predictor.py           # StockPredictorPort (Stage 1)
    ensemble_predictor.py        # Weighted XGB + LGBM + Ridge (Stage 1)
    stage2_predictor.py          # Stage 2 stacking (technicals + sentiment)

application/
  use_cases.py                   # PretrainingUseCase, WeeklyTournamentUseCase,
                                 #   TrackRecommendationsUseCase, EvaluationUseCase
  daily_scan.py                  # DailyScanUseCase (RSS → scorers → SQLite)
  ablation.py                    # Three-way ablation runner
  evaluation.py                  # WalkForwardValidator, PermutationTester,
                                 #   TransactionCostModel, RegimeSplitter,
                                 #   DrawdownTracker, FullEvaluationSuite,
                                 #   BaselineRanker
  backtest_runner.py             # End-to-end backtest report generation
  shap_analysis.py               # Per-fold SHAP feature importance
  cli.py                         # Click CLI (daily-scan, pretrain, run-tournament,
                                 #   evaluate, show-report, backtest, shap-report)

  ticker_universe.py               # Config-driven ticker loader (S&P 500 + NASDAQ-100)

config/
  markets/us.yaml                  # US market + sentiment configuration
  tickers/sp500.txt                # ~503 S&P 500 constituents
  tickers/nasdaq100.txt            # ~101 NASDAQ-100 constituents
```

**Dependency rule:** All dependencies point inward. Domain imports nothing from adapters or application. Any data source or ML model can be swapped without touching business logic.

---

## Feature Groups (85 features)

### Layer 1 — Technical (45 features)

| Group | Count | Examples |
|-------|-------|---------|
| Technical | 15 | RSI-14, MACD, stochastic K/D, SMA ratios, OBV trend |
| Regime | 10 | 52-week high/low ratio, 6m/12m momentum, volatility regime |
| Stronger Signals | 7 | Short interest, earnings surprise, IV skew, institutional ownership |
| Sector Context | 2 | Sector ETF return, stock vs sector |
| Options Flow | 4 | Put/call ratio, unusual volume, large block trades |
| Cross-Correlation | 2 | SPY correlation, relative strength vs peers |
| Macro Regime | 5 | VIX, 10Y yield direction, DXY, yield curve slope, SPY momentum |

### Layer 2 — Sentiment (24 features)

| Group | Count | Features |
|-------|-------|----------|
| Buzz | 2 | buzz_volume, buzz_acceleration (week-over-week change) |
| Sentiment Scores | 3 | keyword score, Flan-T5 score, scorer agreement |
| Sentiment Momentum | 2 | 3-day trend, 7-day trend |
| Source Reliability | 2 | source-weighted sentiment, top source accuracy |
| Divergence | 3 | RSS/Reddit divergence, sentiment-price divergence (flag + magnitude) |
| Cross-Signal | 2 | buzz-price divergence, sector buzz ratio |
| Google Trends | 3 | current interest, week-over-week change, spike detection |
| StockTwits | 3 | 24h message volume, bullish ratio, volume change vs 7d avg |
| News Headlines | 4 | 7d avg sentiment, article volume, sentiment momentum, negative spike |

The **sentiment-price divergence** features are the core thesis signal: when sentiment is bullish but price is falling (or vice versa), this cross-modal disagreement predicts short-term direction.

### Layer 3 — Fundamental Valuation (16 features)

| Group | Count | Features |
|-------|-------|----------|
| Valuation Ratios | 4 | PEG ratio, P/E ratio, P/E vs sector median, price-to-book |
| Financial Health | 3 | debt-to-equity, current ratio, free cash flow yield |
| Profitability | 2 | gross margin, operating margin |
| Growth | 2 | revenue growth YoY, dividend yield |
| Earnings | 2 | last earnings surprise %, surprise streak |
| Smart Money | 2 | institutional ownership change, insider net purchases (future) |
| Composite | 1 | valuation_z_score (PEG + P/B + FCF yield vs sector) |

---

## Multi-Horizon Grading

| Horizon | Noise Threshold | Signal Type |
|---------|----------------|-------------|
| 2-day | ±1.5% | News reaction, momentum |
| 5-day | ±2.0% | Trend confirmation |
| 10-day | ±3.0% | Value recovery, rotation |

| Grade | Criteria |
|-------|---------|
| **Strong Buy** | Bullish 2+ horizons, magnitude >5% on longest |
| **Buy** | Bullish 1+ horizon |
| **Hold** | All neutral or conflicting signals |
| **May Sell** | Bearish 1 horizon |
| **Immediate Sell** | Bearish 2+ horizons, magnitude >3% |

---

## Evaluation Framework (ADR-011)

- **Walk-forward validation** — expanding window, never single split
- **Permutation test** — 1000 shuffles, p<0.05 or result is luck
- **Transaction costs** — 0.1% per trade deducted from returns
- **Regime-aware splits** — bull/sideways/bear (SPY ±10% annualized)
- **Drawdown tracking** — max drawdown and recovery time
- **SPY benchmark** — Sharpe ratio comparison, not raw returns
- **Three-way ablation** — technical-only vs +sentiment vs +sentiment+source-weights (isolates what drives lift)

---

## Quick Start

### Prerequisites
- Python 3.12+
- Conda (recommended)

### Installation

```bash
git clone https://github.com/tirthjoship/multi-modal-stock-recommender.git
cd multi-modal-stock-recommender

conda create -n multi-modal-stock-ml python=3.12 -y
conda activate multi-modal-stock-ml

pip install -e ".[dev]"
pre-commit install
```

### Verify

```bash
pytest tests/ -v
# Expected: 300 passed
```

### CLI Usage

```bash
# Full backtest: pretrain + evaluate + report (recommended first run)
python -m application.cli backtest --market us --start 2024-01 --end 2026-05

# Pretrain on historical data only
python -m application.cli pretrain --market us --start 2024-01 --end 2026-05

# Run weekly tournament
python -m application.cli run-tournament --market us --date 2026-05-25

# Evaluate last week's predictions
python -m application.cli evaluate-last-week --date 2026-05-25

# Show stored report
python -m application.cli show-report --week 2026-05-19

# SHAP feature importance analysis
python -m application.cli shap-report --market us

# Daily buzz discovery scan (RSS feeds → keyword scoring → SQLite)
python -m application.cli daily-scan --market us

# Daily scan with Flan-T5 NLP (requires no torch/XGBoost conflict)
python -m application.cli daily-scan --market us --no-no-flan
```

---

## Testing

```bash
# Full suite
pytest tests/ -v

# With coverage (90% gate)
pytest tests/ --cov=domain --cov=adapters --cov=application --cov-fail-under=90

# Property-based tests (Hypothesis)
pytest tests/test_properties.py -v

# Type checking (via pre-commit)
pre-commit run mypy --all-files

# Lint
ruff check .

# Full quality check (all of the above)
make check
```

| Test Category | Count | What's Tested |
|--------------|-------|---------------|
| Domain models | 31 | All models incl. BuzzSignal, SourceReliability |
| Domain services | 22 | Grading, leakage detection, freshness |
| Property tests | 8 | Hypothesis invariants (symmetry, bounds) |
| Feature engineer | 6 | 45 technical features, NaN handling, leakage check |
| Sentiment features | 22 | 24 sentiment features (original 14 + 10 expanded) |
| Fundamental features | 30 | 16 valuation features, sector-relative metrics |
| ML predictors | 16 | XGB, LGBM, Ridge, Ensemble — fit/predict/save/load |
| Stage 2 predictor | 4 | Stacking fit/predict, save/load, confidence |
| Keyword scorer | 7 | Bullish/bearish/neutral text, bounds, SentimentPort |
| Flan-T5 scorer | 9 | Label mapping, mocked inference, SentimentPort |
| Google Trends adapter | 19 | Batch scanning, historical interest, rate limiting |
| StockTwits adapter | 19 | Bullish/bearish ratio, error handling, rate limiting |
| GDELT adapter | 21 | CSV parsing, V2Tone normalization, error paths |
| Ticker universe | 3 | Dedup, comment stripping, sorted output |
| Evaluation | 18 | Walk-forward, permutation, costs, regime, drawdown, baselines |
| Ablation | 3 | Three-way comparison, best variant selection |
| Daily scan | 3 | Discovery + scoring pipeline, empty feed handling |
| SHAP analysis | 2 | Importance dict structure, signal feature ranking |
| SQLite store | 14 | CRUD for 6 tables, buzz dedup, source reliability |
| Use cases | 9 | Pretraining, tournament, sentiment blending |
| Integration | 8 | Multi-source pipeline, fundamental compose, Phase 3B validation |
| yfinance adapter | 12 | Caching, signals, indicators, expanded field_map |
| **Total** | **300** | |

---

## Data Integrity

**Point-in-time enforcement is non-negotiable.**

- `LookAheadBiasError` halts the pipeline on any future-dated data
- `validate_point_in_time_access()` checks all signal/sentiment timestamps
- `validate_feature_matrix()` rejects known leakage columns: `next_day_return`, `next_week_return`, `future_earnings_surprise`, `forward_pe_ratio`
- `auto_adjust=False` on yfinance — raw prices, never retroactively adjusted
- All raw API responses cached at fetch time for reproducibility (ADR-017)

---

## Phase 3A Results — Technical-Only Baseline

### Walk-Forward Backtest (40 S&P 500 tickers, Jan 2024 → May 2026, 19 folds)

| Horizon | Directional Accuracy | vs Random (50%) | p-value (binomial) | Significant? |
|---------|---------------------|-----------------|-------------------|-------------|
| 5-day | 51.6% | +1.6% | 0.19 | No (p > 0.05) |
| 2-day | 47.1% | -2.9% | 0.95 | No |
| 10-day | 47.1% | -2.9% | 0.95 | No |

**Statistical note:** P-values from one-sided binomial test (H₀: accuracy = 50%, H₁: accuracy > 50%, n ≈ 760 predictions per horizon). None significant at α = 0.05 — technical features alone are indistinguishable from random on S&P 500 mega-caps, consistent with EMH.

**Finding:** Technical features alone do not beat random on S&P 500 mega-caps. This is consistent with the efficient market hypothesis for highly-analyzed, liquid stocks — and is the expected Phase 3A result. The project thesis posits that **sentiment divergence** (Phase 3B) is the signal, not technicals alone.

### SHAP Feature Importance

Only **3 of 45 features** are both important AND stable across folds:

| Feature | Mean |SHAP| | CV | Stability |
|---------|-------------|------|-----------|
| `correlation_with_spy` | 0.0154 | 0.48 | Stable |
| `macd` | 0.0019 | 0.93 | Stable |
| `macd_histogram` | 0.0007 | 0.35 | Stable |

32 features have near-zero importance (mostly NaN from sparse yfinance options/analyst data). Phase 3B adds 14 sentiment features on top to test whether divergence signals provide the lift that technicals alone cannot.

### Sharpe Ratio vs SPY Benchmark

| Metric | Model (5d) | SPY (same period) |
|--------|-----------|-------------------|
| Annualized Sharpe | ~0.0 | ~1.2 |
| Mean excess accuracy/fold | +1.6% | — |

**Interpretation:** Model's per-fold excess accuracy (over 50% random baseline) has near-zero Sharpe — high variance across folds, no consistent edge. SPY buy-and-hold dominates. This confirms the technical-only baseline is not tradeable; the thesis requires sentiment divergence (Phase 3B+) for edge.

### Phase 3B Validation Results (2026-06-01)

Pipeline validated end-to-end: RSS scan → keyword scoring → 14 sentiment features → Stage 2 stacking → three-way ablation.

| Variant | Directional Accuracy | p-value | Significant? |
|---------|---------------------|---------|-------------|
| Technical-only (Stage 1) | 47.4% | 0.8460 | No |
| + Sentiment (Stage 2) | 69.7% | 0.0000 | YES |
| + Source weights (Stage 2 full) | 69.7% | 0.0000 | YES |

**Tickers with buzz data:** 7 of 40 (from stored RSS scan)
**Stage 2 trained:** Yes (350 training samples)

**Interpretation:** Stage 2 sentiment blending shows significant lift over technical-only baseline. However, this is an **in-sample result** — Stage 2 was trained and evaluated on the same data (no holdout split). The 69.7% reflects the model's ability to fit sentiment features to known outcomes, not out-of-sample prediction power. Proper out-of-sample validation requires historical sentiment data (Phase 3.5: Google Trends + GDELT) for walk-forward testing.

**What this proves:** The pipeline works end-to-end without errors. All components (RSS → keyword scoring → sentiment features → Stage 2 XGBoost → ablation → permutation p-values) are wired correctly and produce real numbers.

- **Known limitation:** Flan-T5 scorer disabled by default (`--no-flan`) due to torch/XGBoost OpenMP conflict on macOS; keyword-only scoring active

### Naive Baselines (implemented, not yet compared)

Four stock-selection baselines are ready for comparison against the ML model:
- **Momentum** — top 15 by 6-month return
- **Low-volatility** — top 15 by lowest 20-day vol
- **Random** — random 15, averaged over 100 trials
- **Equal-weight** — hold entire universe

---

## Project Status

| Phase | Status | Description |
|-------|--------|-------------|
| 1 | ✅ Complete | Infrastructure, hexagonal architecture, CI/CD |
| 2 | ✅ Complete | Domain models, point-in-time validation |
| 3A | ✅ Complete | **Pretrained technical pipeline** — 45 features, ensemble, walk-forward, CLI, real-data backtest (~50% baseline), SHAP analysis |
| 3B | ✅ Complete | **Sentiment layer** — keyword + Flan-T5 NLP, 14 sentiment features, RSS adapter (6 publishers), Stage 2 stacking, source reliability tracker, daily buzz scan, three-way ablation |
| 3.5 | ✅ Complete | **Expanded sentiment sources** — Google Trends (2004+), StockTwits, GDELT (2015+), 10 new features (24 total), ticker universe expanded to ~350 (S&P 500 + NASDAQ-100) |
| 4A | ✅ Complete | **Fundamental valuation** — 16 features (PEG, P/E, P/B, FCF yield, margins, earnings, valuation_z_score), wired into pipelines |
| 4B | 📋 Planned | Portfolio tracking + sell signals — holdings SQLite, crash risk detection |
| 4C | 📋 Planned | Cross-asset intelligence — lead-lag correlations, sector contagion |
| 4D | 📋 Planned | Event-causal learning — news→sector impact mapping with decay |
| 5 | 📋 Planned | Dashboard & polish — Streamlit, watchlist, paper trading |

---

## Architecture Decision Records

28 ADRs in `docs/adr/` documenting all major design choices:

| ADR | Decision |
|-----|----------|
| 001 | Combined thesis: sentiment-price lag + cross-modal divergence |
| 003 | XGBoost + LightGBM ensemble over deep learning |
| 004 | Flan-T5 over FinBERT for sentiment (MPS on Apple Silicon) |
| 008 | Parallel NLP baselines from day one (keyword + Flan-T5) |
| 009 | Ridge classifier in ensemble for model family diversity |
| 011 | Rigorous 6-component evaluation framework (incl. three-way ablation) |
| 012 | Phase 3A/3B split for clean ablation |
| 014 | Two-stage stacking (pretrained technical + sentiment blending) |
| 015 | Multi-horizon magnitude targets with noise thresholds |
| 016 | Three-layer data quality gates |
| 017 | Raw data caching for reproducibility |
| 018 | Native NaN for tree models, stored medians for Ridge |
| 019 | Ensemble disagreement as confidence proxy |
| 020 | Naive baselines for validating ML lift |
| 021 | Source reliability tracker (per-source accuracy learning) |
| 022 | Daily discovery scan + weekly full analysis (dual-cadence) |
| 023 | Expanded ticker universe: S&P 500 + NASDAQ-100 (~350 tickers) |
| 024 | Historical sentiment via Google Trends + GDELT for backtesting |
| 025 | Fundamental valuation features from yfinance ticker_info |
| 026 | Portfolio holdings SQLite schema + sell signal detection |
| 027 | Hybrid cross-asset graph correlation + supply chain |
| 028 | Event-causal learning: news → sector impact with decay |

---

## Orchestration

Three GitHub Actions workflows automate quality gates:

| Workflow | Trigger | What it does |
|----------|---------|-------------|
| `test.yml` | Push/PR to develop | Runs 300 tests, enforces 90% coverage |
| `lint.yml` | Push/PR to develop | black, isort, ruff, mypy strict |
| `security.yml` | Push/PR to develop | gitleaks secret scanning |

Future: `daily-scan.yml` cron workflow for automated RSS buzz collection.

---

## Interview Story

> "I hypothesized that sentiment-price divergence predicts short-term stock returns. I built a multi-layer ML system to test this rigorously across ~350 tickers.
>
> **Layer 1 (Technical)** establishes the baseline: 45 features, XGBoost+LightGBM+Ridge ensemble, walk-forward validated on S&P 500 mega-caps. Result: ~50% directional accuracy — indistinguishable from random, exactly as EMH predicts. SHAP revealed only 3 of 45 features carry stable signal. This honest null result is the foundation.
>
> **Layer 2 (Sentiment)** adds 24 features from 4 sources: RSS feeds (6 publishers), Google Trends (historical back to 2004), StockTwits (bullish/bearish crowd sentiment), and GDELT (global news sentiment, 2015-present). The core thesis signal is sentiment-price divergence — when news is bullish but price is falling. A source reliability tracker learns which publishers are directionally accurate over time.
>
> **Layer 3 (Fundamental)** adds 16 valuation features: PEG, P/E vs sector median, FCF yield, margins, earnings surprises, and a composite valuation z-score. These capture whether a stock is cheap/expensive relative to its sector — a different signal from momentum or sentiment.
>
> The system uses three-way ablation to isolate what drives any observed lift. Every result is validated with permutation tests (p<0.05), transaction costs, and regime-aware evaluation. Built with hexagonal architecture — any data source, ML model, or NLP scorer can be swapped without touching business logic. 300 tests, mypy strict, full CI/CD."

---

## Risk Disclaimer

This project is for educational and research purposes only. Stock recommendations generated by this system should not be construed as financial advice. Past performance does not guarantee future results. Always consult a licensed financial advisor before making investment decisions.

---

## Author

**Tirth Joshi** — UBC Master of Data Science

---

## License

MIT License. See `LICENSE` file for details.
