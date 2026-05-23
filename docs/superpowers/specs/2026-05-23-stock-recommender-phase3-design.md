# Design Spec: Multi-Modal Stock Recommender — Phase 3 Core Engine

**Date:** 2026-05-23
**Status:** Approved
**Author:** Tirth Joshi + Claude Code
**Branch:** dev/structural-updates
**Scope:** Phase 3 — Vertical Slice (working weekly predictions)

---

## 1. Thesis

**Combined hypothesis:** Sentiment leads price by X hours. When that lead signal diverges from technical indicators, the divergence predicts short-term direction with Y accuracy.

Two testable claims:
1. **Sentiment-price lag** — news/social sentiment moves before price adjusts (1-48hr window)
2. **Cross-modal divergence** — when technicals and sentiment disagree, the divergence itself is predictive of 5-day direction/volatility

## 2. System Overview

A live weekly stock recommendation system that:
- Scans financial news, social media, and analyst coverage to discover buzzing stocks
- Computes technical indicators and sentiment scores per ticker
- Detects divergence between technical and sentiment signals
- Predicts 5-day returns using XGBoost + LightGBM ensemble
- Grades top 15 picks on a 5-tier scale (Strong Buy to Immediate Sell)
- Tracks past predictions vs actual outcomes with rolling accuracy
- Runs autonomously via GitHub Actions every Sunday

## 3. Architecture

Hexagonal (Ports and Adapters) with inward-pointing dependencies. Domain layer has zero external imports.

```
domain/                          # Pure business logic
  models.py                      # Extended: TechnicalIndicators, DivergenceSignal,
                                 #   StockRecommendation, RecommendationGrade,
                                 #   WeeklyReport, AccuracyRecord
  ports.py                       # Extended: NewsDiscoveryPort, BuzzScorerPort,
                                 #   SentimentScorerPort, RecommendationStorePort,
                                 #   TechnicalAnalysisPort
  services.py                    # Extended: compute_divergence_score(),
                                 #   grade_recommendation()
  exceptions.py                  # Extended: InsufficientDataError, StaleDataError

adapters/
  data/
    yfinance_adapter.py          # MarketDataPort + TechnicalAnalysisPort
    reddit_adapter.py            # BuzzScorerPort (PRAW)
    stocktwits_adapter.py        # BuzzScorerPort
    rss_adapter.py               # NewsDiscoveryPort (6 RSS feeds)
    google_search_adapter.py     # NewsDiscoveryPort (Custom Search API)
    sqlite_store.py              # RecommendationStorePort
  ml/
    keyword_scorer.py            # SentimentScorerPort (baseline)
    flan_t5_scorer.py            # SentimentScorerPort (step 2)
    xgboost_predictor.py         # StockPredictorPort
    lightgbm_predictor.py        # StockPredictorPort
    ensemble_predictor.py        # StockPredictorPort (combines XGB + LGBM)
  visualization/                 # Phase 5 — untouched

application/
  use_cases.py                   # WeeklyTournamentUseCase,
                                 #   TrackRecommendationsUseCase,
                                 #   BacktestUseCase
  cli.py                         # CLI entry point

config/
  markets/
    us.yaml                      # US market: tickers, sources, trading hours

.github/workflows/
  weekly_picks.yml               # Sunday cron job
```

### Key Architectural Principles
- Domain stays pure — no yfinance, no PRAW, no pandas imports in domain/
- Each data source = one adapter implementing one port
- Adapters swappable — add Canada/India later by adding config yaml
- SQLite behind port — upgrade to PostgreSQL without touching domain
- All use cases receive ports via constructor injection — testable with fakes

## 4. Data Sources

### Tier 1 — RSS Feeds (auto-discovery)
| Source | URL | Signal |
|--------|-----|--------|
| Motley Fool | fool.com/feeds/ | Editorial stock picks |
| Seeking Alpha | seekingalpha.com/feed | Analyst articles |
| Yahoo Finance | finance.yahoo.com/news/rss | Broad financial news |
| MarketWatch | feeds.marketwatch.com | Market commentary |
| Benzinga | benzinga.com/feed | Breaking financial news |
| Robinhood Snacks | snacks.robinhood.com/feed/ | Retail-focused picks |

### Tier 2 — Google Custom Search API (targeted discovery)
Queries:
- `"stocks to buy this week" site:morningstar.com`
- `"top stock picks" site:barrons.com`
- `"best stocks" site:investorsbusinessdaily.com`
- `"stocks to buy" site:zacks.com`
- `"stock recommendations" site:kiplinger.com`

100 free queries/day. Configurable in us.yaml.

### Tier 3 — Social Buzz
| Source | Method | Signal |
|--------|--------|--------|
| Reddit | PRAW API | r/wallstreetbets, r/stocks, r/investing |
| StockTwits | Public API | Trending tickers, message sentiment |
| Quiver Quantitative | Free API | Robinhood retail popularity data |

### Tier 4 — Market Data
| Source | Method | Signal |
|--------|--------|--------|
| yfinance | Python library | OHLCV, technicals, options chain, analyst recommendations |

## 5. Domain Models (Extensions)

Existing models (Signal, Sentiment, BacktestResult) remain untouched. New additions:

### RecommendationGrade (Enum)
```
STRONG_BUY      — Top 3, high confidence
BUY             — Rank 4-8
HOLD            — Rank 9-12
MAY_SELL        — Rank 13-15, declining signals
IMMEDIATE_SELL  — Held stock with negative divergence flip
```

### TechnicalIndicators (frozen dataclass)
Fields: symbol, timestamp, rsi_14 (0-100), macd, macd_signal, sma_20, sma_50, sma_200, bollinger_upper, bollinger_lower, volume_trend, technical_signal (-1.0 to 1.0)

Validation: rsi_14 in 0-100, technical_signal in -1.0 to 1.0

### DivergenceSignal (frozen dataclass)
Fields: symbol, timestamp, technical_signal (-1.0 to 1.0), sentiment_signal (-1.0 to 1.0), divergence_score, divergence_type (bullish_divergence | bearish_divergence | aligned)

### StockRecommendation (frozen dataclass)
Fields: symbol, week_start, grade (RecommendationGrade), composite_score, predicted_5d_return, confidence (0.0 to 1.0), technical_summary (TechnicalIndicators), sentiment_score, divergence (DivergenceSignal), reasoning (str), sources (list[str])

### WeeklyReport (frozen dataclass)
Fields: report_date, market (us|ca|in), recommendations (list[StockRecommendation] — must be exactly 15), carryover_updates (list[StockRecommendation]), accuracy_vs_last_week (float|None), spy_return_same_period (float|None)

Validation: recommendations must have between 1 and 15 items (fewer than 15 if insufficient qualified tickers — log warning but do not fail), week_start must be a Monday

### AccuracyRecord (frozen dataclass)
Fields: symbol, week_start, predicted_grade, predicted_return, actual_return, grade_correct (bool), held_weeks (int)

## 6. Ports (New Interfaces)

### NewsDiscoveryPort (Protocol)
- `discover_articles(query, max_results) -> list[dict[str, str]]` — returns url, title, snippet, source, published_date
- `extract_tickers(text) -> list[str]` — pull ticker symbols from article text

Implemented by: google_search_adapter.py, rss_adapter.py

### BuzzScorerPort (Protocol)
- `get_trending_tickers(lookback_hours=168) -> list[dict[str, int]]` — returns ticker, mention_count, unique_authors
- `get_raw_posts(ticker, limit=50) -> list[dict[str, str]]` — returns text, author, timestamp, score

Implemented by: reddit_adapter.py, stocktwits_adapter.py

### SentimentScorerPort (Protocol)
- `score(text) -> float` — sentiment score -1.0 to 1.0
- `score_batch(texts) -> list[float]` — batch scoring

Implemented by: keyword_scorer.py, flan_t5_scorer.py

### RecommendationStorePort (Protocol)
- `save_weekly_report(report) -> None`
- `get_report(week_start) -> WeeklyReport | None`
- `get_reports_range(start, end) -> list[WeeklyReport]`
- `save_accuracy_record(record) -> None`
- `get_accuracy_history(days=90) -> list[AccuracyRecord]`
- `get_rolling_accuracy(days=90) -> float`

Implemented by: sqlite_store.py

### TechnicalAnalysisPort (Protocol)
- `compute_indicators(symbol, lookback_days=90) -> TechnicalIndicators`
- `compute_technical_signal(indicators) -> float` — composite -1.0 to 1.0

Implemented by: yfinance_adapter.py

## 7. Application Layer — Use Cases

### WeeklyTournamentUseCase
Constructor receives lists of ports (multiple news sources, multiple buzz sources). Orchestrates full Sunday pipeline:

1. `discover_tickers()` — aggregate from all news + buzz sources -> ~50-100 raw tickers
2. `filter_universe()` — deduplicate, remove penny stocks (price < $5), remove ultra-low volume (< 100k avg daily), require minimum 3 mentions -> ~30-50 qualified
3. `enrich_technicals()` — yfinance 90-day OHLCV + compute TechnicalIndicators per ticker
4. `score_sentiment()` — keyword/Flan-T5 scoring on all mentions -> sentiment per ticker
5. `detect_divergence()` — compare technical vs sentiment signal -> DivergenceSignal per ticker
6. `predict_and_grade()` — XGBoost + LightGBM ensemble -> predicted 5-day return -> top 15 -> assign RecommendationGrade
7. `handle_carryover()` — re-grade last week's picks not in this week's top 15
8. `store_and_publish()` — save WeeklyReport to SQLite + generate CLI markdown report

Point-in-time enforcement: steps 3-4 validate all data timestamps < prediction_time. LookAheadBiasError kills pipeline if violated.

### TrackRecommendationsUseCase
- `evaluate_last_week(current_date)` — compare predicted vs actual 5-day returns -> list[AccuracyRecord]
- `rolling_accuracy(days=90)` — overall accuracy, accuracy by grade, vs SPY, Sharpe ratio, best/worst pick

### BacktestUseCase
- `run(start_date, end_date)` — simulate weekly tournaments over historical window with strict point-in-time enforcement -> list[WeeklyReport]

## 8. Feature Engineering

44 features per ticker across 7 groups:

### Technical Features (15) — from yfinance
- Price action: return_1d, return_5d, return_20d, volatility_20d, price_vs_sma20, price_vs_sma50, sma20_vs_sma50
- Momentum: rsi_14, macd, macd_signal, macd_histogram, stochastic_k, stochastic_d
- Volume: volume_ratio_20d, obv_trend
- Volatility: bollinger_position, atr_14

### Sentiment/Buzz Features (11) — from news + social
- Buzz: mention_count_total, mention_count_reddit, mention_count_news, unique_sources, buzz_acceleration
- Sentiment: sentiment_mean, sentiment_std, sentiment_max, sentiment_min, sentiment_news_vs_social
- Temporal: sentiment_trend_3d, days_since_first_mention

### Divergence Features (4) — computed
- divergence_score, divergence_direction, divergence_persistence, historical_divergence_accuracy

### Sector Context (3) — from sector ETFs via yfinance
- sector_etf_return_5d, stock_vs_sector, sector_buzz_ratio

### Options Flow (4) — from yfinance options chain
- unusual_options_volume, put_call_ratio, options_volume_vs_stock_volume, large_block_trades_count

### Analyst Actions (4) — from yfinance recommendations
- recent_upgrades_count, recent_downgrades_count, consensus_change, analyst_sentiment_vs_social

### Cross-Correlation (3) — computed from yfinance
- peer_group_momentum, correlation_with_spy, relative_strength_vs_peers

### Target Variable
- `actual_5d_return` — binary classification (up/down) for grading, regression for return magnitude

## 9. NLP Sentiment Ladder

Progressive sophistication with measured lift at each step:

| Step | Model | Cost | When |
|------|-------|------|------|
| 1 (Baseline) | Keyword scoring (bullish/bearish word counts) | Free | Phase 3 start |
| 2 (Upgrade) | Flan-T5 fine-tuned for financial sentiment | Free (local) | Phase 3, after baseline measured |
| 3 (Escalation) | Claude/Gemini API | ~$5-15/week | Phase 4, if Flan-T5 plateau |

Each step measures precision/recall lift over previous. If lift < 2%, previous step is sufficient.

## 10. ML Models

### Phase 3 Models
- **XGBoost** — gradient boosting on 44 tabular features. SHAP for explainability.
- **LightGBM** — second gradient boosting model. Handles categoricals natively (sector, source type).
- **Simple Ensemble** — average predicted probabilities from XGBoost + LightGBM. Weighted by recent accuracy.

### Training Strategy
- Initial training: backtest on historical data (minimum 6 months)
- Weekly retraining: incremental update with last week's outcomes
- Feature importance: SHAP values computed weekly, logged for drift detection
- Seeds pinned for reproducibility

### Evaluation Framework
| Metric | What It Measures | Benchmark |
|--------|-----------------|-----------|
| Cumulative return vs SPY | Business value | SPY ETF return same period |
| Sharpe ratio | Risk-adjusted return | SPY Sharpe ratio |
| Directional accuracy | Prediction quality | 50% (random) |
| Precision per grade | Grade reliability | Per-grade baseline |
| SHAP feature importance | Feature contribution | Track drift over time |

## 11. Data Pipeline — Weekly Flow

```
Sunday 5:00 UTC (Saturday 9 PM PST), GitHub Actions triggers:

Step 1: DISCOVER
  Google Custom Search + RSS feeds + Reddit + StockTwits + Quiver
  -> ~50-100 unique tickers + raw text per mention

Step 2: FILTER
  Deduplicate, remove penny stocks (< $5), remove low volume (< 100k),
  require minimum 3 mentions across sources
  -> ~30-50 qualified tickers

Step 3: ENRICH
  yfinance -> 90 days OHLCV + options chain + analyst recommendations
  Compute: 15 technical + 4 options flow + 4 analyst + 3 cross-correlation features
  -> technical feature matrix per ticker

Step 4: SCORE SENTIMENT
  Keyword baseline (or Flan-T5) on all raw text per ticker
  Aggregate across sources -> 11 sentiment/buzz features per ticker
  -> sentiment feature vector per ticker

Step 5: DETECT DIVERGENCE
  Compare technical_signal vs sentiment_signal
  Compute divergence_score, direction, persistence
  -> 4 divergence features per ticker

Step 6: PREDICT + GRADE
  XGBoost + LightGBM ensemble -> predicted 5-day return
  Rank by composite score (predicted return x confidence)
  Top 15 -> assign grade (Strong Buy through Immediate Sell)
  -> WeeklyReport with 15 graded picks + reasoning

Step 7: STORE + COMPARE
  Save to SQLite (recommendations + accuracy tables)
  Pull last week's picks -> compare predicted vs actual
  Update rolling 90-day accuracy metrics
  -> accuracy_report + updated history

Step 8: PUBLISH
  Generate CLI markdown report
  Commit to repo: reports/YYYY-MM-DD-weekly-picks.md
```

Point-in-time enforcement: Steps 3-4 validate all data timestamps < prediction_time. LookAheadBiasError kills pipeline if violated.

Carryover logic: Last week's picks not in this week's top 15 get re-evaluated and graded as Hold or May Sell based on current signals. Never silently dropped.

## 12. Storage Schema (SQLite)

```sql
CREATE TABLE recommendations (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    week_start DATE NOT NULL,
    grade TEXT NOT NULL,
    composite_score REAL,
    predicted_5d_return REAL,
    confidence REAL,
    sentiment_score REAL,
    divergence_score REAL,
    divergence_type TEXT,
    reasoning TEXT,
    sources TEXT,  -- JSON array
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, week_start)
);

CREATE TABLE accuracy_records (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    week_start DATE NOT NULL,
    predicted_grade TEXT,
    predicted_return REAL,
    actual_return REAL,
    grade_correct BOOLEAN,
    held_weeks INTEGER DEFAULT 1,
    evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, week_start)
);

CREATE TABLE watchlist (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL UNIQUE,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

CREATE INDEX idx_rec_week ON recommendations(week_start);
CREATE INDEX idx_rec_symbol ON recommendations(symbol);
CREATE INDEX idx_acc_week ON accuracy_records(week_start);
```

## 13. GitHub Actions Configuration

```yaml
name: Weekly Stock Tournament
on:
  schedule:
    - cron: '0 5 * * 0'     # Sunday 5:00 UTC (Sat 9 PM PST)
  workflow_dispatch:          # manual trigger for testing

env:
  GOOGLE_CSE_API_KEY: ${{ secrets.GOOGLE_CSE_API_KEY }}
  GOOGLE_CSE_ID: ${{ secrets.GOOGLE_CSE_ID }}
  REDDIT_CLIENT_ID: ${{ secrets.REDDIT_CLIENT_ID }}
  REDDIT_CLIENT_SECRET: ${{ secrets.REDDIT_CLIENT_SECRET }}

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
          git commit -m "feat: weekly picks $(date +%Y-%m-%d)"
          git push
```

CLI interface:
- `python -m application.cli run-tournament` — full pipeline
- `python -m application.cli evaluate-last-week` — accuracy check
- `python -m application.cli backtest --start 2025-01 --end 2026-05` — historical simulation
- `python -m application.cli show-report --week 2026-05-19` — view past report

## 14. Testing Strategy

### Layer 1: Domain Tests (Pure, Fast)
- test_domain_models.py — TechnicalIndicators bounds, divergence computation, grade ordering, WeeklyReport must have 15 picks, week_start must be Monday
- test_domain_services.py — divergence aligned/bullish/bearish, grade thresholds
- test_properties.py (Hypothesis) — sentiment always bounded, divergence symmetric, grading monotonic, point-in-time never leaks

### Layer 2: Adapter Tests
- test_yfinance_adapter.py — integration (marked @pytest.mark.slow)
- test_reddit_adapter.py — integration (marked @pytest.mark.slow)
- test_sqlite_store.py — in-memory SQLite, fast
- test_keyword_scorer.py — pure, no external deps
- test_rss_adapter.py — mock HTTP responses
- test_google_search_adapter.py — mock HTTP responses

### Layer 3: Use Case Tests (End-to-End with Fakes)
- test_weekly_tournament.py — full pipeline with fake adapters, lookahead bias failure, carryover logic, fewer than 15 tickers handled
- test_track_recommendations.py — accuracy computation, rolling 90-day window, SPY benchmark
- test_backtest.py — point-in-time enforcement, produces weekly reports

### Fake Adapters
```
tests/fakes/
  fake_market_data.py         # Canned OHLCV data
  fake_news_discovery.py      # Canned articles
  fake_buzz_scorer.py         # Canned ticker mentions
  fake_sentiment_scorer.py    # Deterministic scores
  fake_store.py               # In-memory dict store
```

### Testing Principles
- No real API calls in CI — fakes for all ports
- Integration tests marked @pytest.mark.slow — run manually
- Leakage prevention — property test: no feature timestamp > prediction_time
- Grading consistency — property test: monotonic (higher score never gets lower grade)
- Reproducibility — all random seeds pinned
- Coverage — 90% gate, domain must be 100%

## 15. Market Configuration

```yaml
# config/markets/us.yaml
market:
  name: "US"
  currency: "USD"
  trading_hours:
    open: "09:30"
    close: "16:00"
    timezone: "America/New_York"

filters:
  min_price: 5.0
  min_avg_volume: 100000
  min_mentions: 3

news_discovery:
  rss_feeds:
    - name: motley_fool
      url: "https://fool.com/feeds/index.aspx"
    - name: seeking_alpha
      url: "https://seekingalpha.com/feed"
    - name: yahoo_finance
      url: "https://finance.yahoo.com/news/rss"
    - name: marketwatch
      url: "https://feeds.marketwatch.com/..."
    - name: benzinga
      url: "https://benzinga.com/feed"
    - name: robinhood_snacks
      url: "https://snacks.robinhood.com/feed/"

  google_search_targets:
    - "stocks to buy this week site:morningstar.com"
    - "top stock picks site:barrons.com"
    - "best stocks site:investorsbusinessdaily.com"
    - "stocks to buy site:zacks.com"
    - "stock recommendations site:kiplinger.com"

buzz_sources:
  reddit:
    subreddits:
      - wallstreetbets
      - stocks
      - investing
  stocktwits:
    enabled: true
  quiver_quantitative:
    enabled: true

sector_etfs:
  - XLK   # Technology
  - XLF   # Financials
  - XLE   # Energy
  - XLV   # Healthcare
  - XLI   # Industrials
  - XLC   # Communication
  - XLY   # Consumer Discretionary
  - XLP   # Consumer Staples
  - XLU   # Utilities
  - XLRE  # Real Estate
  - XLB   # Materials
```

## 16. Project Phasing Roadmap

### Phase 3: Core Engine (This Spec) — BUILD NOW
Working weekly predictions with CLI output. Vertical slice: yfinance technicals first, then layer sentiment sources one by one. Each addition measured for lift.

### Phase 4: Tracking and Intelligence
- Week-over-week accuracy tracking with visual trends
- 90-day rolling performance window
- SPY benchmark + Sharpe ratio comparison
- Canadian market config (ca.yaml)
- LSTM-Transformer hybrid ensemble
- LLM-generated formulaic alphas
- Macro calendar features (FOMC, CPI, earnings season)
- Market regime detection (VIX, yield curve)
- Pipeline-first data quality validation pass

### Phase 5: Dashboard and Polish
- Streamlit app (Recommendations, Tracking, Watchlist tabs)
- Personal watchlist input
- Short-term vs long-term return probability display
- Historical performance charts
- EDA notebooks for hypothesis validation
- Indian market config (in.yaml)

### Future Extensions (Unbounded)
- Daily frequency upgrade
- Sector rotation signals thesis
- Earnings surprise prediction thesis
- Claude/Gemini sentiment escalation (LLM tier)
- Morningstar direct scraping (if ToS resolved)
- SerpAPI upgrade (from free Google Custom Search)
- Shareable stock picks
- Danelfin AI scoring integration
- StockGeist real-time social sentiment
- LunarCrush social intelligence
- FinLlama as advanced NLP tier
- Unusual Whales options flow (paid tier)
- Dark pool activity data
- Reinforcement learning for dynamic position sizing
- 270+ auto-generated feature approach
- PostgreSQL/DuckDB migration
- Transformer-based model exploration
- Google AI Mode integration (if API becomes available)

## 17. Decisions Log

| Decision | Choice | Why |
|----------|--------|-----|
| Thesis | Sentiment-price lag + cross-modal divergence | Coherent story, testable, contrarian signals |
| Stock universe | Dynamic buzz-driven | Avoids human bias, surfaces attention stocks |
| Market | US first, config-driven multi-market | Best data coverage, hardest market proves rigor |
| Data sources | yfinance + Google CSE + RSS + Reddit + StockTwits + Quiver | Free/cheap, diverse signal types |
| NLP | Keyword -> Flan-T5 -> LLM ladder | Measure lift at each step, cheapest first |
| Model | XGBoost + LightGBM ensemble | King for tabular, SHAP explainability, fast |
| Output | Top 15, 5-tier grading | Actionable, nuanced, trackable |
| Evaluation | SPY + Sharpe + precision/recall | Business + risk + DS angles |
| Storage | SQLite | Zero setup, years of data, port-swappable |
| Deployment | GitHub Actions Sunday cron | Free, reliable, visible in repo |
| Approach | Vertical slice | Working predictions fastest, each source = A/B test |
| FinBERT replacement | Flan-T5 fine-tuned | Outperforms FinBERT, smaller than FinGPT, free |

## 18. Interview Story

"I hypothesized that when social sentiment and technical indicators disagree on a stock's direction, the divergence itself predicts short-term returns. I built a live weekly system that scans news, Reddit, and analyst coverage, computes 44 features across 7 categories, and uses an XGBoost+LightGBM ensemble to pick the top 15 stocks each week with a 5-tier grading system. I measured progressive NLP sophistication — keyword baseline vs Flan-T5 — and tracked each step's marginal lift. The system runs autonomously via GitHub Actions, commits its picks to the repo for full audit trail, and evaluates itself against SPY using risk-adjusted returns."

---

*This spec covers Phase 3 only. Phases 4, 5, and Future Extensions are documented in Section 16 as roadmap.*
