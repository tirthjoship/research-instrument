# Multi-Modal Stock Recommender

Production-grade ML system predicting multi-horizon stock returns using 45 technical, regime, and macro features. XGBoost + LightGBM + Ridge ensemble with walk-forward validation, permutation testing, and transaction cost modeling. Built with hexagonal architecture and strict point-in-time enforcement.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-103%20passing-success)](./tests/)
[![Coverage](https://img.shields.io/badge/coverage-91%25-brightgreen)](./tests/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![mypy: strict](https://img.shields.io/badge/mypy-strict-blue.svg)](http://mypy-lang.org/)

---

## Thesis

**Combined hypothesis:** Sentiment leads price by 1-48 hours. When that lead signal diverges from technical indicators, the divergence predicts short-term direction.

**Phase 3A tests:** Can technical + regime + macro features alone predict multi-horizon stock returns above random baseline with statistical significance?

**Phase 3B will test:** Does adding sentiment/buzz features provide measurable lift over Phase 3A's technical-only model?

---

## What It Does

1. Pulls 2-3 years of historical OHLCV, options, analyst, and macro data via yfinance
2. Computes **45 features** across 8 groups per ticker per week
3. Trains **XGBoost + LightGBM + Ridge** ensemble via walk-forward validation
4. Predicts return magnitude at **2-day, 5-day, and 10-day** horizons
5. Grades predictions using multi-horizon threshold classification (Strong Buy → Immediate Sell)
6. Evaluates with **permutation tests** (p<0.05), transaction costs, regime splits, and drawdown tracking
7. Stores results in SQLite, caches all raw data for reproducibility
8. Runs via **CLI** and GitHub Actions (Sunday cron)

---

## Architecture

**Hexagonal (Ports & Adapters) — domain layer has zero external imports.**

```
domain/                          # Pure business logic (stdlib only)
  models.py                      # Signal, Sentiment, MultiHorizonPrediction,
                                 #   StockRecommendation, RecommendationGrade,
                                 #   AccuracyRecord, EvaluationRun, WeeklyReport
  ports.py                       # MarketDataPort, TechnicalAnalysisPort,
                                 #   StockPredictorPort, FeatureEngineerPort,
                                 #   RecommendationStorePort
  services.py                    # grade_from_horizons(), validate_feature_matrix(),
                                 #   validate_data_freshness(), classify_horizon()
  exceptions.py                  # LookAheadBiasError, InsufficientDataError,
                                 #   StaleDataError

adapters/
  data/
    yfinance_adapter.py          # MarketDataPort + TechnicalAnalysisPort
    sqlite_store.py              # RecommendationStorePort (4 tables)
    cache_mixin.py               # Append-only raw data cache (ADR-017)
  ml/
    feature_engineer.py          # 45 features across 8 groups
    xgboost_predictor.py         # StockPredictorPort
    lightgbm_predictor.py        # StockPredictorPort
    ridge_predictor.py           # StockPredictorPort
    ensemble_predictor.py        # Weighted XGB + LGBM + Ridge

application/
  use_cases.py                   # PretrainingUseCase, WeeklyTournamentUseCase,
                                 #   TrackRecommendationsUseCase, EvaluationUseCase
  evaluation.py                  # WalkForwardValidator, PermutationTester,
                                 #   TransactionCostModel, RegimeSplitter,
                                 #   DrawdownTracker
  cli.py                         # Click CLI (pretrain, run-tournament, evaluate, show-report)

config/markets/us.yaml           # US market configuration
```

**Dependency rule:** All dependencies point inward. Domain imports nothing from adapters or application. Any data source or ML model can be swapped without touching business logic.

---

## Feature Groups (45 features)

| Group | Count | Examples |
|-------|-------|---------|
| Technical | 15 | RSI-14, MACD, stochastic K/D, SMA ratios, OBV trend |
| Regime | 10 | 52-week high/low ratio, 6m/12m momentum, volatility regime |
| Stronger Signals | 7 | Short interest, earnings surprise, IV skew, institutional ownership |
| Sector Context | 2 | Sector ETF return, stock vs sector |
| Options Flow | 4 | Put/call ratio, unusual volume, large block trades |
| Cross-Correlation | 2 | SPY correlation, relative strength vs peers |
| Macro Regime | 5 | VIX, 10Y yield direction, DXY, yield curve slope, SPY momentum |

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
# Expected: 103 passed
```

### CLI Usage

```bash
# Pretrain on 2-3 years of historical data
python -m application.cli pretrain --market us --start 2024-01 --end 2026-05

# Run weekly tournament
python -m application.cli run-tournament --market us --date 2026-05-25

# Evaluate last week's predictions
python -m application.cli evaluate-last-week --date 2026-05-25

# Show stored report
python -m application.cli show-report --week 2026-05-19
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

# Type checking
mypy domain/ adapters/ application/ config/ --strict

# Lint
ruff check .
```

| Test Category | Count | What's Tested |
|--------------|-------|---------------|
| Domain models | 25 | All models, exceptions, port imports |
| Domain services | 22 | Grading, leakage detection, freshness |
| Property tests | 8 | Hypothesis invariants (symmetry, bounds) |
| Feature engineer | 5 | 45 features, NaN handling, leakage check |
| ML predictors | 10 | XGB, LGBM, Ridge, Ensemble fit/predict/save/load |
| Evaluation | 12 | Walk-forward, permutation, costs, regime, drawdown |
| SQLite store | 7 | CRUD for all 4 tables |
| Use cases | 7 | Pretraining pipeline, weekly tournament |
| yfinance adapter | 7 | Caching, signals, indicators |
| **Total** | **103** | |

---

## Data Integrity

**Point-in-time enforcement is non-negotiable.**

- `LookAheadBiasError` halts the pipeline on any future-dated data
- `validate_point_in_time_access()` checks all signal/sentiment timestamps
- `validate_feature_matrix()` rejects known leakage columns: `next_day_return`, `next_week_return`, `future_earnings_surprise`, `forward_pe_ratio`
- `auto_adjust=False` on yfinance — raw prices, never retroactively adjusted
- All raw API responses cached at fetch time for reproducibility (ADR-017)

---

## Project Status

| Phase | Status | Description |
|-------|--------|-------------|
| 1 | ✅ Complete | Infrastructure, hexagonal architecture, CI/CD |
| 2 | ✅ Complete | Domain models, point-in-time validation |
| 3A | ✅ Complete | **Pretrained technical pipeline** — 45 features, ensemble, walk-forward, CLI |
| 3B | 📋 Planned | Sentiment layer — keyword + Flan-T5 NLP, divergence features, Stage 2 stacking |
| 4 | 📋 Planned | Tracking & intelligence — accuracy trends, Canadian market, LSTM-Transformer |
| 5 | 📋 Planned | Dashboard & polish — Streamlit, watchlist, Indian market |

---

## Architecture Decision Records

17 ADRs in `docs/adr/` documenting all major design choices:

| ADR | Decision |
|-----|----------|
| 001 | Combined thesis: sentiment-price lag + cross-modal divergence |
| 003 | XGBoost + LightGBM ensemble over deep learning |
| 009 | Ridge classifier in ensemble for model family diversity |
| 011 | Rigorous 5-component evaluation framework |
| 012 | Phase 3A/3B split for clean ablation |
| 014 | Two-stage stacking (pretrained technical + sentiment blending) |
| 015 | Multi-horizon magnitude targets with noise thresholds |
| 016 | Three-layer data quality gates |
| 017 | Raw data caching for reproducibility |

---

## Interview Story

> "I hypothesized that sentiment-price divergence predicts short-term stock returns. I built a rigorous quantitative system to test this: 45 features across 8 categories, pretrained on 2-3 years of historical data using walk-forward validation. The model predicts return magnitude at three horizons (2-day, 5-day, 10-day) using an XGBoost+LightGBM+Ridge ensemble, with threshold-based classification to filter noise from actionable signals. Every result is validated with permutation tests for statistical significance, transaction cost modeling, and regime-aware evaluation. I then layer sentiment analysis on top and measure the exact marginal lift — proving whether social/news divergence from technicals adds alpha beyond what price data alone provides. The system runs autonomously via GitHub Actions, caches all raw data for reproducibility, and has three-layer data quality gates for production resilience."

---

## Risk Disclaimer

This project is for educational and research purposes only. Stock recommendations generated by this system should not be construed as financial advice. Past performance does not guarantee future results. Always consult a licensed financial advisor before making investment decisions.

---

## Author

**Tirth Joshi** — UBC Master of Data Science

---

## License

MIT License. See `LICENSE` file for details.
