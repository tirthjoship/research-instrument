# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository. Read `AGENTS.md` for all coding standards, architecture rules, and testing requirements before touching any code.

## Project Context

Multi-modal stock recommendation engine combining structured market data (yfinance) with unstructured sentiment signals (news, Reddit, StockTwits) to generate weekly Top 15 stock picks. Core hypothesis: **sentiment leads price by 1-48 hours**, and when technical indicators diverge from sentiment signals, the divergence predicts 5-day directional returns.

The project uses hexagonal architecture (ports & adapters) so the domain logic stays pure and any data source, ML model, or UI can be swapped without touching business rules.

## Commands

```bash
# Full quality check (lint + typecheck + test with coverage)
make check

# Individual targets
make test          # pytest -v --tb=short
make test-cov      # pytest with --cov-fail-under=90
make lint          # pre-commit run --all-files
make typecheck     # mypy strict on domain/ adapters/ application/
make setup         # pip install + pre-commit install
make daily-scan    # run daily sentiment scan and update recommendations

# Single test
pytest tests/test_domain_models.py::test_signal_valid_creation -v
```

## Architecture

**Hexagonal (Ports & Adapters) with inward-pointing dependencies.**

```
adapters/     →  domain/  ←  application/
(external)       (pure)      (orchestration)
```

- `domain/` — Business rules, models, port interfaces, exceptions. ZERO external framework imports.
- `adapters/data/` — yfinance, RSS feeds, Google Trends, StockTwits, GDELT sentiment, SQLite store.
- `adapters/ml/` — Keyword scorer, Flan-T5 sentiment, XGBoost predictor, LightGBM predictor, ensemble.
- `adapters/visualization/` — Streamlit dashboard (Phase 5).
- `application/` — Use case orchestration (WeeklyTournament, TrackRecommendations, Backtest).
- `config/markets/` — Market-specific configuration (us.yaml, future: ca.yaml, in.yaml).

Port interfaces in `domain/ports.py` define contracts. Adapters implement them. New tool = new adapter, never new domain code.

## Critical Domain Knowledge

**Look-ahead bias — the biggest risk in this project.**

Point-in-time enforcement is non-negotiable. All data accessed during prediction must have timestamps <= prediction_time. Violations are catastrophic — they make backtests look profitable while the live system fails.

Enforced via:
- `LookAheadBiasError` in `domain/exceptions.py` — halts pipeline on violation
- `validate_point_in_time_access()` in `domain/services.py` — checks all signal/sentiment timestamps
- Every adapter must filter data to prediction_time before returning

**FUTURE_LEAKAGE_COLUMNS** (must never appear in feature matrices):
- `next_day_return` — future price data
- `next_week_return` — future price data
- `future_earnings_surprise` — post-event data
- `forward_pe_ratio` — uses future earnings estimates

**Sentiment-price dynamics (from thesis):**
- Sentiment leads price by 1-48 hours (hypothesis under test)
- Cross-modal divergence (technicals disagree with sentiment) is the primary predictive signal
- Buzz alone does not equal returns — the model must learn which buzz patterns precede moves

**5-tier grading system:**
- Strong Buy (top 3, high confidence)
- Buy (rank 4-8)
- Hold (rank 9-12)
- May Sell (rank 13-15, declining signals)
- Immediate Sell (held stock with negative divergence flip)

**Evaluation — always compare against SPY benchmark:**
- Never claim "model beats the market" without risk-adjusted comparison
- Sharpe ratio, not raw returns
- Precision/recall on directional predictions, not accuracy alone

## Non-Negotiable Rules

Five hard stops — see `AGENTS.md` for full details:

1. **No framework imports in domain/** — domain/ imports only typing, dataclasses, datetime, enum
2. **No look-ahead bias** — all data timestamps must be <= prediction_time. LookAheadBiasError enforced.
3. **Evaluate with Sharpe ratio + precision/recall** — never raw returns or accuracy alone
4. **No direct commits to main or dev** — feature branches only, PR to dev
5. **Tests use small fixtures** — never hit real APIs (yfinance, Reddit) in CI tests. Use fakes.

## Phase Status

**Done:**
- Domain layer (models, ports, services, exceptions) — Signal, Sentiment, BacktestResult, RecommendationGrade, MultiHorizonPrediction, StockRecommendation, AccuracyRecord, EvaluationRun, WeeklyReport
- Domain ports — MarketDataPort, SentimentPort, TechnicalAnalysisPort, StockPredictorPort, FeatureEngineerPort, RecommendationStorePort, BacktestResultPort, BuzzDiscoveryPort, SourceReliabilityPort, HistoricalSentimentPort
- Domain services — validate_point_in_time_access(), grade_from_horizons(), validate_feature_matrix(), validate_data_freshness()
- Feature engineering — 45 features across 7 groups (technical, regime, stronger signals, sector, options, cross-correlation, macro)
- ML models — XGBoost + LightGBM + Ridge ensemble, one per horizon (2d/5d/10d)
- YFinance adapter — MarketDataPort + TechnicalAnalysisPort with caching mixin (ADR-017)
- SQLite store — RecommendationStorePort with recommendations, accuracy, evaluations, reports
- Application use cases — PretrainingUseCase, WeeklyTournamentUseCase, TrackRecommendationsUseCase
- Evaluation components — WalkForwardValidator, PermutationTester, TransactionCostModel, RegimeSplitter, DrawdownTracker
- CLI — pretrain, run-tournament, evaluate-last-week, show-report commands
- Config — us.yaml market config with macro symbols, sector ETFs, quality gates
- Test suite — 300 tests passing, Hypothesis property tests, full fake suite
- CI workflows (test + lint + security) — 3 GitHub Actions
- Pre-commit hooks — black, isort, mypy strict, ruff, gitleaks
- Makefile — test, lint, typecheck, setup, check targets
- Design spec + 17 Architecture Decision Records (docs/adr/)
- CLAUDE.md + AGENTS.md + CONTEXT.md — project orientation and standards

**Done (Phase 3A Completion — methodology gaps closed 2026-05-29):**
- Real-data backtest — 40 tickers, 2024-01 to 2026-05, 19 walk-forward folds. Result: ~50% accuracy (random baseline).
- SHAP feature importance — 32/45 features near-zero, only 3 stable+important (correlation_with_spy, macd, macd_histogram)
- Wire evaluation pipeline — FullEvaluationSuite connecting all 5 ADR-011 components
- Fix imputation — native NaN for XGBoost/LightGBM, stored medians for Ridge (ADR-018)
- Fix composite score — signed values for long-only ranking
- Naive baselines — momentum, low-vol, random, equal-weight (ADR-020)
- Ensemble disagreement confidence (ADR-019)
- Wire sector_relative_strength_6m
- Bug fixes: cache staleness, 2d weekend target bug, rate limit crash retry

**Done (Phase 3B — Code Complete 2026-05-30):**
- Keyword + Flan-T5 zero-shot parallel scorers (ADR-008)
- RSS, Google CSE, Reddit, StockTwits adapters
- 16 additional features (sentiment/buzz 11 + divergence 4 + sector_buzz_ratio 1)
- Ablation: technical-only vs sentiment-only vs combined
- Recursive learning with decay weighting

**Done (Phase 3.5 — Expanded Sentiment Sources 2026-06-01):**
- Google Trends adapter — historical interest back to 2004, weekly granularity, rate-limited (pytrends)
- StockTwits adapter — free API, message volume + bullish/bearish ratio
- GDELT historical sentiment adapter — DOC API, V2Tone normalization, 2015-present
- HistoricalSentimentPort added to domain/ports.py
- Ticker universe expanded to ~350 (S&P 500 + NASDAQ-100) via config/tickers/ files
- 10 new sentiment features (24 total): google_trends_current/change/spike, stocktwits_volume/bullish/change, news_avg/volume/momentum/negative_spike
- Daily scan pipeline wires all three new adapters
- Test suite — 262 tests passing

**Done (Phase 4A — Fundamental Valuation Features 2026-06-01):**
- FundamentalFeatureEngineer — 16 features (PEG, P/E, P/B, FCF yield, margins, debt, earnings, valuation_z_score)
- YFinance field_map expanded with pegRatio, freeCashflow, grossMargins, operatingMargins
- Sector-relative metrics (pe_vs_sector, valuation_z_score) — sector context wired with empty list (sector batching in future phase)
- Wired into pretraining and tournament pipelines (optional, backward compatible)
- Test suite — 300 tests passing

**Done (Phase 4B — Portfolio Tracking + Sell Signals 2026-06-01):**
- Holding + SellSignal domain models — frozen dataclasses with validation
- HoldingsPort protocol + SQLite CRUD (add/remove/get/list holdings)
- MonitorHoldingsUseCase — stop-loss (-8%), negative sentiment, technical breakdown detection
- 4 CLI commands: add-holding, list-holdings, remove-holding, monitor-holdings
- Risk config in us.yaml (stop_loss_threshold, sentiment_sell_threshold)
- Test suite — 334+ tests passing

**Done (Phase 4C — Cross-Asset Intelligence 2026-06-02):**
- CorrelationEdge domain model + CrossAssetPort protocol
- CorrelationAnalyzer adapter — rolling correlation matrix, hierarchical clustering, Granger causality with BH correction
- CrossAssetFeatureEngineer — 8 features (upstream leader returns, cluster momentum, lag signal, supply chain divergence, correlation regime shift, thematic activation, Granger lead signal)
- Supply chain YAML config — 10 groups (semiconductors, big tech, energy, pharma, space/defense, retail, AI, cloud/SaaS, financials, housing)
- Wired into pretraining and tournament pipelines (optional, backward compatible)
- Test suite — 370+ tests passing

**Done (Phase 4D — Event-Causal Learning 2026-06-02):**
- EventCategory enum (10 types) + ClassifiedEvent + EventSectorImpact domain models
- EventClassifierPort protocol + GeminiEventClassifier adapter (Gemini free tier, structured output)
- EventImpactAnalyzer — learns magnitude + half-life per category×sector from historical data
- EventCausalFeatureEngineer — 8 features (impact score/max, event count, sentiment direction, half-life avg, surprise factor, dominant category, decay phase)
- Event-sector mapping YAML (10 categories × affected sectors)
- Wired into pretraining and tournament pipelines (optional, backward compatible)
- Test suite — 410+ tests passing

**Done (Phase 5 — Decision Dashboard 2026-06-02):**
- 6-tab Streamlit dashboard (Command Center, Model Confidence, Signal Breakdown, Positions, Opportunities, Market Pulse)
- Shared Plotly chart builders (accuracy line, grade donut, sector heatmap, decay curve, SHAP bar, ablation bar)
- Dashboard formatters (grade colors, direction icons, urgency badges, percentages, freshness)
- Data loader with graceful degradation (empty states, missing DB/files)
- Watchlist SQLite table + 3 CLI commands (add-watchlist, list-watchlist, remove-watchlist)
- Metric card and action card Streamlit components
- Smoke + integration tests, all pre-commit hooks pass
- Test suite — 470+ tests passing

**Done (Phase 5.1 — Dashboard UI Overhaul 2026-06-02):**
- Renamed `pages/` → `tabs/` to fix Streamlit sidebar auto-discovery bug
- Global CSS module (`styles.py`) — Modern SaaS styling with cards, pills, badges, layer colors
- 6 HTML formatters: grade badges, status pills, signal pills, confidence bars, freshness pills, grade display names
- Fixed grade donut colors (enum → display name), human-readable ablation labels, SHAP layer-colored bars
- Styled metric cards with HTML containers, signal layer cards with colored borders, info sections with tooltips
- Action runner with progress-tracked `run_monitor_holdings`, `run_add_holding`, `run_add_watchlist`
- All 6 tabs rewritten: styled cards, convergence bars, inline forms, expanders
- Test suite — 496 tests passing

**Done (Phase 5.2 — Dashboard UX Overhaul 2026-06-03):**
- CSS overhaul: Inter font (Google Fonts CDN), `#2563EB` accent blue, hover lift effects, styled buttons/inputs
- Footer watermark: "Multi-Modal Stock Recommender · Hexagonal Architecture · Built by Tirth Joshi"
- Verdict-first pattern: every section answers a question in plain English before showing numbers
- 5 verdict generators: command center, model confidence, signal layer, pick, ablation
- Hero banner + verdict card + inline context components (replaces all `st.expander("Learn more")`)
- One-click actions: Run Full Cycle (chains scan→tournament→track), Run Tournament, Run Backtest
- Emoji-free content: urgency pills + freshness dots use CSS classes, no emoji in content areas
- Top 5 pick cards on Opportunities tab (no expanders for important data)
- Data pipeline status panel on Market Pulse (shows all 7 connected data sources)
- Supply chain groups expanded by default (no click to reveal)
- Test suite — 518 tests passing

**Done (Phase 7 — Opportunity Intelligence Foundation 2026-06-03):**
- ConvictionScore, ConvictionWeights, OpportunityCard, SmartMoneySignal domain models
- SmartMoneyPort protocol + validate_smart_money_signals temporal guard
- Conviction scoring service — weighted multi-signal aggregation, freshness decay, ranking
- SEC EDGAR adapter — 13D activist filings + Form 4 insider trades (free, no API key)
- Smart money feature engineer — 8 features (13D count, insider cluster, stake %, buy/sell counts)
- ConvictionScoringUseCase — orchestrates signal gathering → scoring → card generation
- Opportunity card HTML components — conviction badges, action badges, evidence/risk rendering
- Dashboard freshness header — last scan timestamp, market status, S&P 500 sparkline
- Command Center → Opportunity Feed tab with conviction-ranked cards
- Conviction weights + SEC EDGAR config in us.yaml
- ADR-032 documenting the reframe from direction prediction to opportunity surfacing
- Test suite — 660+ tests passing

**Done (Phase 8 — Outcome Tracking & Memory 2026-06-03):**
- TrackedTrade, TradeOutcome, SignalPerformance domain models
- Outcome tracking service — compute_outcome, compute_signal_performance, generate_report_card
- SQLite persistence — tracked_trades + trade_outcomes tables with CRUD
- OutcomeTrackingUseCase — record_buy, record_sell, get_signal_report, get_outcomes_summary
- Dashboard data loaders — load_trades, load_outcomes with graceful defaults
- Outcome Tracker tab (was Positions) — trade recording form, P&L display, outcomes table
- System Intelligence tab (was Model Confidence) — signal report card + learning progress
- Historical bootstrap engine — simulates past outcomes for cold-start learning
- ADR-033 documenting outcome tracking and signal learning
- Test suite — 735+ tests passing

**Planned (Phase 4):** Tracking & Intelligence — accuracy trends, long-short ranking, conformal prediction, Canadian market, LLM analyst layer, risk management, position sizing
