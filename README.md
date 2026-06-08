# Multi-Modal Stock Recommender

Production-grade, hexagonal ML research system for equities, built around **rigorous, pre-registered falsification** and **honest reporting of negative results**. A 5-layer feature architecture (45 technical + 24 sentiment/buzz/divergence + 16 fundamental + 8 cross-asset + 8 event-causal), XGBoost/LightGBM/Ridge ensembles, walk-forward validation, permutation testing, transaction-cost modeling, cross-asset Granger causality, and an adaptive-intelligence dashboard — all with strict point-in-time enforcement.

> **⚠️ Honest status (2026-06-07, ADR-045).** The original thesis — predicting returns from public sentiment/attention/conviction — was **falsified** by three independent pre-registered tests (ADR-039 no OOS conviction edge; ADR-043 conviction dimensions dead; ADR-044 intensity-divergence has no cross-sectional IC on a clean 430-ticker universe). This is a convergent negative result, not a bug: retail-accessible public attention contains no detectable tradeable alpha (semi-strong efficiency). The project's real value is the **falsification harness** (pre-registration, cross-sectional IC, bootstrap significance, OOS validation, abstention) and the **honest negative finding** itself. It is now **pivoting** (ADR-045) from *return prediction* to an **exit-discipline + risk-management engine** (trend filter + ATR trailing exit + relative momentum), grounded in the principle that a retail edge is **better process, not better prediction**. Ambition is bounded by an explicit evidence hierarchy; nothing ships without passing a pre-registered backtest gate. See `docs/adr/` (039, 043, 044, 045).

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-1052%20passing-success)](./tests/)
[![Coverage](https://img.shields.io/badge/coverage-90%25+-brightgreen)](./tests/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![mypy: strict](https://img.shields.io/badge/mypy-strict-blue.svg)](http://mypy-lang.org/)

---

## Thesis

**Combined hypothesis:** Sentiment leads price by 1-48 hours. When that lead signal diverges from technical indicators, the divergence predicts short-term direction.

**Phase 3A tests:** Can technical + regime + macro features alone predict multi-horizon stock returns above random baseline with statistical significance?

**Phase 3B tests:** Does adding sentiment/buzz features (from RSS news + social media) provide measurable lift (>2%) over Phase 3A's ~50% technical-only baseline?

**Phases 7-9 reframe:** Direction prediction alone shows no edge (~49% accuracy on mega-caps). The system now surfaces opportunities via multi-signal conviction scoring with adaptive learning — catching trends before mainstream awareness through SEC filing analysis, sentiment convergence, and pattern memory.

**Current engine status (2026-06-05):** A discrimination audit over 63 warmed thematic mid-cap candidates found that 6 of 8 conviction dimensions are completely non-discriminating on this universe (smart-money, signal-agreement, sentiment-momentum, ml-direction, event-signal, analyst-signal all returned var=0.000). Only `temporal_freshness` and `fundamental_basis` vary, meaning conviction currently ranks by data recency, not opportunity quality. The engine honestly abstains on the spine. Sub-project C will pivot to **divergence-led surfacing** — attention-acceleration vs price as the primary trigger, with conviction demoted to a light tiebreaker — so the daily forward-tracking loop can finally accumulate resolved out-of-sample outcomes. See [ADR-043](docs/adr/043-conviction-dims-dead-divergence-led-surfacing.md).

---

## What It Does

1. **Multi-source buzz scan** — scans 6 RSS feeds, Google Trends (historical back to 2004), StockTwits (bullish/bearish ratio), and GDELT news sentiment (2015-present)
2. Pulls 2-3 years of historical OHLCV, options, analyst, and macro data via yfinance
3. Computes **101 features**: 45 technical (Stage 1) + 24 sentiment/buzz/divergence (Stage 2) + 16 fundamental valuation + 8 cross-asset intelligence + 8 event-causal
4. Trains **two-stage stacking**: Stage 1 (XGBoost + LightGBM + Ridge ensemble, frozen) → Stage 2 (XGBoost blending technicals + sentiment + fundamentals)
5. Predicts return magnitude at **2-day, 5-day, and 10-day** horizons
6. **Dynamic ticker discovery** via buzz acceleration — finds stocks where mentions are spiking, not just high
7. **Cross-asset intelligence** — correlation graph with Granger causality, supply chain propagation (10 groups, 80+ tickers), lead-lag signal detection
8. Covers **~350 tickers** (S&P 500 + NASDAQ-100) via config-driven universe
8. Grades predictions using multi-horizon threshold classification (Strong Buy → Immediate Sell)
9. Evaluates with **permutation tests** (p<0.05), transaction costs, regime splits, drawdown tracking, and **three-way ablation** (tech-only vs +sentiment vs +sentiment+source-weights)
10. **Source reliability tracking** — learns which news sources are directionally accurate over time
11. Stores results in SQLite, caches all raw data for reproducibility
12. **Portfolio tracking** — add/remove holdings, automated sell signal detection (stop-loss, negative sentiment, technical breakdown)
13. **Decision dashboard** — 6-tab Streamlit app (Command Center, Model Confidence, Signal Breakdown, Positions, Opportunities, Market Pulse) with interactive Plotly charts
14. Runs via **CLI** (daily-scan + weekly tournament + portfolio management + dashboard)
15. **Conviction scoring** — 6-dimension weighted scoring (signal agreement, smart money, sentiment, fundamentals, freshness, ML direction) surfaces top 15 opportunities from 350+ tickers
16. **SEC EDGAR integration** — 13D activist filings and Form 4 insider trades as "smart money" signals (free, no API key)
17. **Opportunity cards** — 4-part output: Alert (headline), Evidence (plain English), Suggestion (Buy/Watch/Hold/Sell), Risk (what could go wrong)
18. **Outcome tracking** — manual buy/sell logging with P&L computation, signal correlation, and signal report card showing which signals actually work
19. **Adaptive intelligence** — pattern memory learns from tracked outcomes, auto-adjusts conviction weights (boost >65% hit rate, reduce <50%), discovers rules ("avoid X in sector Y")

---

## Architecture

**Hexagonal (Ports & Adapters) — domain layer has zero external imports.**

```
domain/                          # Pure business logic (stdlib only)
  models.py                      # Signal, Sentiment, BuzzSignal, SourceReliability,
                                 #   MultiHorizonPrediction, StockRecommendation,
                                 #   RecommendationGrade, AccuracyRecord,
                                 #   EvaluationRun, WeeklyReport, Holding,
                                 #   SellSignal, CorrelationEdge
  ports.py                       # MarketDataPort, SentimentPort, BuzzDiscoveryPort,
                                 #   SourceReliabilityPort, HistoricalSentimentPort,
                                 #   HoldingsPort, CrossAssetPort,
                                 #   TechnicalAnalysisPort, StockPredictorPort,
                                 #   FeatureEngineerPort, RecommendationStorePort
  services.py                    # grade_from_horizons(), validate_feature_matrix(),
                                 #   validate_data_freshness(), classify_horizon()
  exceptions.py                  # LookAheadBiasError, InsufficientDataError,
                                 #   StaleDataError
  conviction.py                  # ConvictionScore, ConvictionWeights, OpportunityCard,
                                 #   SmartMoneySignal, ActionType, FreshnessLevel
  conviction_service.py          # compute_conviction(), compute_freshness_score(),
                                 #   determine_action(), rank_opportunities()
  outcome.py                     # TrackedTrade, TradeOutcome, SignalPerformance
  outcome_service.py             # compute_outcome(), compute_signal_performance(),
                                 #   generate_report_card()
  pattern_memory.py              # PatternEntry, WeightAdjustment, LearnedRule
  pattern_service.py             # build_patterns_from_outcomes(),
                                 #   compute_weight_adjustments(), discover_rules()
  ports.py                       # (add) SmartMoneyPort
  services.py                    # (add) validate_smart_money_signals()

adapters/
  data/
    yfinance_adapter.py          # MarketDataPort + TechnicalAnalysisPort
    rss_adapter.py               # BuzzDiscoveryPort (6 RSS publishers)
    google_trends_adapter.py     # BuzzDiscoveryPort (pytrends, historical)
    stocktwits_adapter.py        # BuzzDiscoveryPort (free API, bull/bear)
    gdelt_sentiment_adapter.py   # HistoricalSentimentPort (GDELT DOC API)
    sqlite_store.py              # RecommendationStorePort + HoldingsPort (8 tables)
    cache_mixin.py               # Append-only raw data cache (ADR-017)
    sec_edgar_adapter.py         # SmartMoneyPort (SEC EDGAR EFTS API, 13D + Form 4)
    sqlite_store.py              # (add) 4 new tables: tracked_trades, trade_outcomes,
                                 #   weight_history, learned_rules
  ml/
    feature_engineer.py          # 45 technical features
    sentiment_feature_engineer.py # 24 sentiment/buzz/divergence features
    fundamental_feature_engineer.py # 16 valuation/financial health features
    correlation_analyzer.py        # CrossAssetPort (NetworkX graph, Granger)
    cross_asset_features.py        # 8 cross-asset intelligence features
    gemini_event_classifier.py     # EventClassifierPort (Gemini free tier)
    event_impact_analyzer.py       # Exponential decay impact learning
    event_causal_features.py       # 8 event-causal features
    smart_money_engineer.py      # 8 smart money features (13D count, insider cluster, etc.)
    keyword_scorer.py            # SentimentPort (rule-based, instant)
    flan_t5_scorer.py            # SentimentPort (zero-shot NLP, MPS)
    xgboost_predictor.py         # StockPredictorPort (Stage 1)
    lightgbm_predictor.py        # StockPredictorPort (Stage 1)
    ridge_predictor.py           # StockPredictorPort (Stage 1)
    ensemble_predictor.py        # Weighted XGB + LGBM + Ridge (Stage 1)
    stage2_predictor.py          # Stage 2 stacking (technicals + sentiment)
  visualization/
    dashboard.py                 # Streamlit entry point (6-tab router)
    data_loader.py               # SQLite + JSON loading with graceful defaults
    components/
      charts.py                  # 7 Plotly builders (accuracy, donut, heatmap, decay, SHAP, ablation)
      formatters.py              # Grade colors, icons, urgency badges, freshness
      metrics.py                 # Metric card + action card components
    components/
      styles.py                  # Global CSS (Inter font, #2563EB accent, hover effects)
      formatters.py              # Grade badges, status pills, freshness dots (CSS, no emoji)
      metrics.py                 # Hero banner, verdict card, inline context, pick card
      verdicts.py                # Plain-English verdict generators (5 functions)
      charts.py                  # 7 Plotly builders (accuracy, donut, heatmap, decay, SHAP, ablation)
    tabs/
      command_center.py          # Tab 1: Opportunity Feed — conviction-ranked cards
      model_confidence.py        # Tab 2: System Intelligence — signal report + weight history + rules
      signal_breakdown.py        # Tab 3: Per-ticker 5-layer signal view with verdicts
      positions.py               # Tab 4: Outcome Tracker — trade recording + P&L
      opportunities.py           # Tab 5: Top 5 pick cards, Run Tournament, watchlist
      market_pulse.py            # Tab 6: Data pipeline status, supply chains, event decay
      opportunity_cards.py       # Conviction badges, evidence/risk card rendering
    action_runner.py             # (add) run_conviction_scan, run_record_buy, run_record_sell

application/
  use_cases.py                   # PretrainingUseCase, WeeklyTournamentUseCase,
                                 #   TrackRecommendationsUseCase, EvaluationUseCase
  conviction_use_case.py         # ConvictionScoringUseCase (signal → score → cards)
  outcome_use_case.py            # OutcomeTrackingUseCase (record_buy, record_sell, report)
  bootstrap_use_case.py          # HistoricalBootstrapUseCase (cold-start simulation)
  learning_use_case.py           # LearningUseCase (pattern analysis → weight adjustment → rules)
  monitor_holdings.py            # MonitorHoldingsUseCase (sell signal detection)
  daily_scan.py                  # DailyScanUseCase (RSS → scorers → SQLite)
  ablation.py                    # Three-way ablation runner
  evaluation.py                  # WalkForwardValidator, PermutationTester,
                                 #   TransactionCostModel, RegimeSplitter,
                                 #   DrawdownTracker, FullEvaluationSuite,
                                 #   BaselineRanker
  backtest_runner.py             # End-to-end backtest report generation
  shap_analysis.py               # Per-fold SHAP feature importance
  cli.py                         # Click CLI (daily-scan, pretrain, run-tournament,
                                 #   evaluate, show-report, backtest, shap-report,
                                 #   add-holding, list-holdings, remove-holding,
                                 #   monitor-holdings, add-watchlist, list-watchlist,
                                 #   remove-watchlist)

  ticker_universe.py               # Config-driven ticker loader (S&P 500 + NASDAQ-100)

config/
  markets/us.yaml                  # US market + sentiment configuration + conviction weights + SEC EDGAR config
  relationships/supply_chain.yaml  # 10 supply chain groups (80+ tickers)
  events/sector_mapping.yaml       # 10 event categories → affected sectors
  tickers/sp500.txt                # ~503 S&P 500 constituents
  tickers/nasdaq100.txt            # ~101 NASDAQ-100 constituents
```

**Dependency rule:** All dependencies point inward. Domain imports nothing from adapters or application. Any data source or ML model can be swapped without touching business logic.

---

## Feature Groups (101 features)

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

### Layer 4 — Cross-Asset Intelligence (8 features)

| Group | Count | Features |
|-------|-------|----------|
| Upstream Signal | 2 | upstream_leader_return_1d, upstream_leader_return_5d |
| Cluster | 1 | cluster_momentum_1w (mean 5d return of correlation cluster peers) |
| Lead-Lag | 2 | leader_follower_lag_signal, granger_lead_signal |
| Divergence | 1 | supply_chain_divergence (ticker vs supply chain group) |
| Regime | 1 | correlation_regime_shift (20d vs 60d avg pairwise correlation) |
| Activation | 1 | thematic_activation (>3 peers moved same direction >1%) |

Supply chain relationships (10 groups): semiconductors, big tech, energy (upstream/downstream/inverse), pharma, space/defense, retail, AI infrastructure/consumers, cloud/SaaS, financials, housing. Auto-discovered via hierarchical clustering + Granger causality, with manual YAML overrides.

### Layer 5 — Event-Causal (8 features)

| Group | Count | Features |
|-------|-------|----------|
| Impact | 2 | event_impact_score (sum of decaying impacts), event_impact_max |
| Activity | 2 | event_count_7d, event_sentiment_direction |
| Decay | 2 | event_half_life_avg, event_decay_phase (0=peak, 1=tail) |
| Surprise | 1 | event_surprise_factor (actual vs expected sector return) |
| Category | 1 | event_category_dominant (numeric ID of strongest event) |

10 event categories classified via Gemini free tier: earnings surprise, tariff/trade, FDA approval, interest rate, antitrust, geopolitical, labor/layoffs, supply chain disruption, product launch, macro data. Impact learned empirically with exponential decay: `impact(t) = magnitude × 0.5^(t/half_life)`.

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

pip install -e ".[dev,dashboard]"
pre-commit install
```

### Verify

```bash
pytest tests/ -v
# Expected: ~1052 passed
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

# Portfolio management
python -m application.cli add-holding NVDA 10 --price=950.00 --date=2026-04-01 --notes="AI play"
python -m application.cli list-holdings
python -m application.cli remove-holding NVDA

# Monitor holdings for sell signals (stop-loss, sentiment, technical breakdown)
python -m application.cli monitor-holdings --market us

# Watchlist management
python -m application.cli add-watchlist TSLA --notes="earnings play"
python -m application.cli list-watchlist
python -m application.cli remove-watchlist TSLA

# Launch decision dashboard (requires dashboard extras)
streamlit run adapters/visualization/dashboard.py
```

---

## Scheduling

The daily opportunity cycle (`scan-opportunities → resolve-calls → weekly backfill`) runs via
macOS **launchd** pre-market at 08:00 local time. See [docs/scheduling.md](docs/scheduling.md)
for the ready-to-edit plist, load/unload instructions, Reddit credential setup, and the ADR-007
deviation note explaining why local scheduling follows from the local SQLite decision.

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
| Holdings models | 14 | Holding/SellSignal validation, immutability |
| Holdings store | 7 | SQLite CRUD: add/get/list/remove/duplicate/notes |
| Monitor holdings | 12 | Stop-loss, sentiment, technical, multi-signal, empty |
| Correlation edge | 11 | CorrelationEdge validation, bounds, immutability |
| Correlation analyzer | 11 | Correlation matrix, clustering, Granger, YAML merge |
| Cross-asset features | 12 | 8 features, NaN handling, thematic activation |
| Event models | 11 | EventCategory, ClassifiedEvent, EventSectorImpact validation |
| Gemini classifier | 6 | Mocked API, batch, error handling, prompt content |
| Event impact analyzer | 9 | Learning, decay computation, YAML loading |
| Event-causal features | 10 | 8 features, edge cases |
| Integration | 16 | Multi-source, fundamental, Phase 3B, holdings, cross-asset, event, dashboard E2E |
| yfinance adapter | 12 | Caching, signals, indicators, expanded field_map |
| Dashboard formatters | 22 | Grade colors, icons, urgency badges, percentages, freshness |
| Dashboard charts | 14 | Plotly builders: accuracy, donut, heatmap, decay, SHAP, ablation |
| Dashboard data loader | 15 | SQLite + JSON loading, graceful defaults, missing DB handling |
| Dashboard smoke | 4 | Import verification for all visualization modules |
| Watchlist | 6 | SQLite CRUD: add, upsert dedup, remove, empty, dict structure |
| Conviction models | 27 | ConvictionScore, OpportunityCard, SmartMoneySignal |
| Conviction service | 32 | Freshness, action mapping, weighted scoring, ranking |
| SEC EDGAR adapter | 10 | 13D/Form 4 parsing, error handling, rate limiting |
| Smart money features | 9 | 8 feature extraction, cluster detection |
| Conviction use case | 7 | Signal gathering → scoring → card generation |
| Opportunity cards | 35 | HTML rendering, badges, evidence, risk sections |
| Outcome models | 8 | TrackedTrade, TradeOutcome, SignalPerformance |
| Outcome service | 32 | Trade outcomes, signal performance, report cards |
| Outcome use case | 23 | Buy/sell recording, outcome computation |
| Bootstrap | 5 | Historical simulation for cold-start |
| Pattern memory | 16 | PatternEntry, WeightAdjustment, LearnedRule |
| Pattern service | 19 | Pattern building, weight adjustment, rules |
| Learning use case | 11 | Pattern analysis → weight adjustment → rules |
| **Total** | **~1052** | |

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

### Full Universe Backtest (2026-06-03)

Walk-forward on S&P 500 + NASDAQ-100 (~350 tickers), all 5 feature layers active:

| Horizon | Accuracy | p-value | Folds | Predictions | Verdict |
|---------|----------|---------|-------|-------------|---------|
| 2d | 46.7% | 0.9945 | 38 | 1,520 | Worse than random |
| 5d | 49.4% | 0.7282 | 57 | 2,280 | Indistinguishable from random |
| 10d | 48.2% | 0.9281 | 38 | 1,520 | Worse than random |

**Interpretation:** Confirms Phase 3A finding at full scale. Technical + fundamental + cross-asset + event-causal features together do not predict direction on mega-caps. Sentiment features (which require live data, not historical backtest) are the potential differentiator — Phase 3B in-sample showed 69.7% with sentiment, but that result is not yet out-of-sample validated.

### Naive Baselines (implemented, not yet compared)

Four stock-selection baselines are ready for comparison against the ML model:
- **Momentum** — top 15 by 6-month return
- **Low-volatility** — top 15 by lowest 20-day vol
- **Random** — random 15, averaged over 100 trials
- **Equal-weight** — hold entire universe

---

## Financial Intelligence Engine v1 (ADR-038, ADR-039)

### Approach

Phases 5.0–5.5 were six consecutive dashboard redesigns applied to an unvalidated conviction score. The fabricated backtest reported `accuracy - 0.5` relabeled as "excess returns" — directional accuracy is not a return metric. ADR-038 documents the pivot.

The Financial Intelligence Engine v1 replaces that with a **validation-first, precision-first system**:

1. **Conviction backtest harness** — a leakage-safe stratified walk-forward backtest (monthly steps, 21-day forward horizon). Headline metric: **Top-Decile Hit Rate** (did picks in the top conviction decile beat a coin flip?). Full suite: precision@top-decile, monotonic precision–conviction curve, F₀.₅, expected-profit-per-signal, real Sharpe vs SPY. Accuracy banned as a standalone claim.
2. **Event intelligence revived** — Phase 4D event engine (previously dormant) now feeds live news into the Gemini classifier. A `government_investment` event category was added; the resulting `event_conviction_score` is wired into conviction, point-in-time safe.
3. **Analyst signal** — Finnhub (live) + yfinance (multi-year history) upgrade/downgrade adapters, track-record-weighted. `analyst_conviction_score` wired into conviction, point-in-time safe.
4. **New free data adapters** — `NewsHeadlinePort` (Alpha Vantage news), `AnalystRatingsPort` (Finnhub + yfinance). CI uses fakes; no network calls in tests.
5. **Honest abstention** — the system abstains when no signal clears the conviction bar, rather than generating low-confidence picks.

### Validation Findings (First Powered, Leakage-Safe Backtest)

Stratified walk-forward, 76 tickers, 2023-06 → 2026-05, monthly steps, 21-day horizon, top-decile signals only, signal-bearing tickers only. Two tickers (CIVI, GMS) dropped as delisted/unavailable.

| Cohort | Top-Decile Hit Rate | Excess Sharpe vs SPY | n (top-decile picks) | p-value |
|--------|--------------------|--------------------|---------------------|---------|
| Large-cap | 57.4% | +0.52 | 61 | 0.15 |
| Small/mid-cap | 48.6% | −0.52 | 35 | 0.63 |
| Overall | 56.1% | +0.39 | 98 | 0.13 |

**Honest interpretation:**

- **No statistically significant edge** in any cohort (all p > 0.13). Not tradeable as-is.
- A **faint, non-significant positive lean** overall (56.1%, p=0.13): "something, maybe" — not nothing, not a proven edge.
- The small/mid-cap hypothesis was **not supported** — it underperformed SPY (−0.52 excess Sharpe) despite survivorship bias in the small-cap list that should have flatered it. Any faint hint lives in large-caps.
- Top-decile sample sizes remain modest (61 / 35 / 98).
- **Caveats:** only 2 of 8 conviction dimensions are historically reconstructable (smart-money + analyst); events, sentiment, and fundamentals were held at neutral to avoid look-ahead bias. Small-cap list has survivorship bias.

### Product Framing (ADR-039)

Given the "credible-null-with-a-whisper" result, the product is an **honest evidence-aggregator + calibrated-abstention tool**: surface organized, point-in-time evidence per name; abstain when nothing clears the conviction bar. It is not a "beat-the-market predictor."

Next directions (to be decided): densify signal and add statistical power; forward-track the event + sentiment-spike layer using existing outcome-tracking infrastructure (these signals cannot be cleanly backtested historically); do not chase small-caps.

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
| 4B | ✅ Complete | **Portfolio tracking + sell signals** — Holding/SellSignal models, HoldingsPort, MonitorHoldingsUseCase (stop-loss/sentiment/technical), 4 CLI commands, risk config |
| 4C | ✅ Complete | **Cross-asset intelligence** — CorrelationAnalyzer (correlation matrix, Ward clustering, Granger causality w/ BH correction), 8 features, 10 supply chain groups, CrossAssetPort |
| 4D | ✅ Complete | **Event-causal learning** — Gemini event classification (10 categories), exponential decay impact learning, 8 features, event-sector mapping |
| 5 | ✅ Complete | **Decision dashboard** — 6-tab Streamlit (Command Center, Model Confidence, Signal Breakdown, Positions, Opportunities, Market Pulse), Plotly charts, watchlist, graceful empty states |
| 5.1 | ✅ Complete | **Dashboard UI polish** — CSS cards/pills/badges, pages→tabs rename, grade donut fix, SHAP layer colors |
| 5.2 | ✅ Complete | **Dashboard UX overhaul** — Inter font, verdict-first layout, Run Full Cycle/Tournament/Backtest buttons, emoji-free content, pick cards, data pipeline panel |
| 7 | ✅ Complete | **Opportunity Intelligence Foundation** — conviction scoring engine (6 dimensions), SEC EDGAR adapter (13D + Form 4), smart money features, opportunity cards, Opportunity Feed dashboard tab, freshness header with S&P 500 sparkline |
| 8 | ✅ Complete | **Outcome Tracking & Memory** — trade logging, outcome tracking with P&L, signal report card, historical bootstrap, Outcome Tracker tab, System Intelligence tab |
| 9 | ✅ Complete | **Adaptive Intelligence** — pattern memory, weight adjustment with guardrails, learned rule discovery, Run Learning Cycle, weight history display |
| 5.3 | ✅ Complete | **Dashboard redesign** — WealthSimple 5-tab layout, auto-scan, compact conviction cards, learning progress bar, onboarding flow, market context grid |
| 5.4 | ✅ Complete | **SimplyWallSt-Grade Redesign** — SWST design language, signal radar, Stock Analysis tab (7 sections), live prices, conviction engine fix (3 placeholder sub-scores wired), 15+ new chart builders, criteria cards + verdict bullets on all tabs, CSS tooltips with hover explainers |
| FIE v1 | ✅ Complete | **Financial Intelligence Engine v1** — leakage-safe conviction backtest harness (precision-first metrics), event intelligence revived (`government_investment` category), analyst signal (Finnhub + yfinance), new free data adapters, fabricated returns metric removed. First powered validation: 56.1% top-decile hit rate overall (p=0.13, not significant). ~1052 tests. |

---

## Architecture Decision Records

39 ADRs in `docs/adr/` documenting all major design choices:

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
| 029 | Cross-asset feature architecture: dual adapter + Granger pre-filter |
| 030 | Event-causal learning: Gemini free tier + empirical impact + exponential decay |
| 031 | Decision dashboard: 6-tab Streamlit + Plotly, command center first |
| 032 | Opportunity intelligence: reframe from direction prediction to conviction-scored opportunity surfacing |
| 033 | Outcome tracking: trade logging, signal report card, historical bootstrap |
| 034 | Adaptive intelligence: pattern memory, weight evolution with guardrails, rule discovery |
| 035 | Dashboard redesign: WealthSimple 5-tab layout, auto-scan, compact conviction cards |
| 036 | Phase 5.4 SimplyWallSt-grade redesign: signal radar, Stock Analysis tab, SWST design language |
| 037 | Phase 5.5 UX overhaul: action-oriented redesign, action queue, portfolio health, Gemini AI |
| 038 | Financial Intelligence Engine v1: validation-first pivot, precision metrics, fabricated returns removed |
| 039 | Conviction validation findings: first powered backtest results, product framing as honest evidence-aggregator |

---

## Orchestration

Three GitHub Actions workflows automate quality gates:

| Workflow | Trigger | What it does |
|----------|---------|-------------|
| `test.yml` | Push/PR to develop | Runs ~1052 tests, enforces 90% coverage |
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
> **Layer 4 (Cross-Asset)** adds 8 features from a correlation graph built with Granger causality. The system auto-discovers which stocks move together using hierarchical clustering, then tests for lead-lag relationships. Manual supply chain overrides (10 groups, 80+ tickers) capture domain knowledge like 'semiconductor equipment makers lead chip producers by 1-2 days.'
>
> **Layer 5 (Event-Causal)** adds 8 features from a news event classification pipeline. Gemini classifies headlines into 10 event categories (earnings, tariffs, FDA, interest rates, etc.), then an impact analyzer learns exponential decay parameters per category×sector pair. The system discovers that 'tariff announcements impact energy stocks with a 5-day half-life' from historical data.
>
> **Portfolio Management** layer adds holdings tracking with automated sell signal detection — stop-loss triggers, negative sentiment spikes, and technical breakdowns. The system doesn't just predict what to buy; it monitors what you hold and tells you when to sell.
>
> **Decision Dashboard** ties it all together — a 6-tab Streamlit app designed like Wealthsimple/SimplyWallSt. Every section explains itself in plain English first ('The model doesn't have a proven edge yet'), then shows the evidence. One-click 'Run Full Cycle' button chains scan→tournament→accuracy tracking — no terminal needed. The Command Center shows prioritized actions (urgent/this week/watch). Model Confidence is brutally honest about what works and what doesn't. Opportunities tab shows top 5 picks as full detail cards with layer convergence and source attribution.
>
> **Opportunity Intelligence** (Phases 7-9) is the real breakthrough. After proving that direction prediction has no edge on mega-caps, I reframed the entire system around opportunity surfacing. A conviction engine scores every ticker across 6 dimensions — smart money activity (SEC EDGAR 13D activist filings, Form 4 insider trades), sentiment momentum, fundamentals, and signal freshness. It surfaces the top 15 opportunities as plain-English cards: 'ValueAct Capital just filed a 13D on NVDA — conviction 8/10, here's the evidence, here's what could go wrong.'
>
> The system learns from outcomes. When I buy based on a recommendation, I log it. When I sell, it computes the return and correlates back to which signals fired. A monthly report card shows 'insider buying clusters had 72% hit rate, ML direction prediction was 48% — stop weighting it.' Weights adjust automatically: boost signals that work (>65% hit rate), reduce signals that don't (<50%), with guardrails to prevent wild swings. The system discovers rules from data: 'never recommend pure-technical plays on mega-caps' — learned, not hardcoded.
>
> **Full-universe backtest** (350+ tickers, 29 months, 2024-2026) confirms: technical + fundamental + cross-asset + event-causal features alone achieve ~49% accuracy — indistinguishable from random on mega-caps. This honest null result is the foundation. The thesis posits that live sentiment divergence is the edge — Phase 3B in-sample showed 69.7% with sentiment, but out-of-sample validation is pending.
>
> The system uses three-way ablation to isolate what drives any observed lift. Every result is validated with permutation tests (p<0.05), transaction costs, and regime-aware evaluation. Built with hexagonal architecture — any data source, ML model, or NLP scorer can be swapped without touching business logic. ~1052 tests, mypy strict, full CI/CD.
>
> **Financial Intelligence Engine v1** (2026-06-04) closes the validation gap. I discovered the backtest had been fabricating a return metric — literally `accuracy - 0.5` relabeled as 'excess returns.' That's gone. A leakage-safe conviction backtest (stratified walk-forward, 76 tickers, 2023-06 to 2026-05, top-decile precision) replaced it. First honest result: 56.1% top-decile hit rate overall (p=0.13) — a faint positive lean, not statistically significant. Large-caps show 57.4% (p=0.15); small/mid-caps underperformed SPY (48.6%, −0.52 excess Sharpe). The product is now framed honestly: an evidence-aggregator that surfaces organized, point-in-time information per name and abstains when nothing clears the conviction bar. Not a market-beating predictor — not yet. The next step is densifying signal and forward-tracking the event+sentiment-spike layer that can't be cleanly backtested."

---

## Risk Disclaimer

This project is for educational and research purposes only. Stock recommendations generated by this system should not be construed as financial advice. Past performance does not guarantee future results. Always consult a licensed financial advisor before making investment decisions.

---

## Author

**Tirth Joshi** — UBC Master of Data Science

---

## License

MIT License. See `LICENSE` file for details.
