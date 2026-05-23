# CONTEXT.md — Domain Language & Ubiquitous Terms

This document defines the shared vocabulary for the multi-modal stock recommender. All code, documentation, and conversation should use these terms consistently.

## Core Concepts

### Thesis
**Sentiment-Price Lag:** News and social sentiment shifts precede price movement by 1-48 hours. This temporal lag is the window of opportunity.

**Cross-Modal Divergence:** When technical indicators (RSI, MACD, moving averages) and sentiment signals (news, social buzz) disagree on a stock's direction, the divergence itself predicts short-term (5-day) returns. This is the primary predictive signal.

### Stock Universe
**Dynamic Buzz-Driven Universe:** The system does not use a pre-defined stock list. Each week, it scans news, social media, and analyst coverage to discover which stocks are being discussed. The "most-discussed" stocks become that week's universe (~30-50 candidates after filtering). This avoids selection bias and surfaces high-attention stocks where sentiment matters most.

**Filtering Rules:** Penny stocks (< $5), ultra-low volume (< 100k avg daily), and stocks with fewer than 3 cross-source mentions are excluded.

### Tournament
**Weekly Tournament:** The system runs every Sunday, produces Top 15 picks, and tracks outcomes the following week. This is not a one-shot prediction — it is a continuous competition cycle.

**Recursive Feedback:** Each week's outcomes feed back into the next week's model. The system learns from its own mistakes by comparing predicted grades vs actual returns.

## Domain Models

### Signal
A market data observation at a specific point in time: price, volume, OHLC. Immutable. Must have timestamp <= prediction_time.

### Sentiment
A sentiment observation from a specific source (news, Reddit, StockTwits) at a specific time. Score in [-1.0, 1.0]. Immutable. Must have timestamp <= prediction_time.

### TechnicalIndicators
Computed from Signal data: RSI(14), MACD, SMA(20/50/200), Bollinger Bands, volume trend. Produces a composite `technical_signal` in [-1.0, 1.0] where -1.0 = fully bearish, 1.0 = fully bullish.

### DivergenceSignal
The disagreement between technical_signal and sentiment_signal for a given stock. Contains:
- `divergence_score` — magnitude of disagreement (0.0 = aligned, 2.0 = max divergence)
- `divergence_type` — "bullish_divergence" (sentiment bullish, technicals bearish), "bearish_divergence" (sentiment bearish, technicals bullish), or "aligned"

### StockRecommendation
A graded pick for a specific stock in a specific week. Contains the grade, composite score, predicted 5-day return, confidence, supporting indicators, and human-readable reasoning.

### RecommendationGrade
Five-tier grading system:
- **Strong Buy** — Top 3 picks, high confidence, strong divergence signal
- **Buy** — Rank 4-8, positive outlook
- **Hold** — Rank 9-12, mixed signals
- **May Sell** — Rank 13-15, declining signals
- **Immediate Sell** — Previously held stock with negative divergence flip

### WeeklyReport
The complete output of one tournament round: 15 recommendations + carryover updates for last week's picks + accuracy comparison vs previous week + SPY benchmark.

### AccuracyRecord
Historical record comparing what was predicted vs what actually happened. Used for rolling 90-day accuracy tracking and Sharpe ratio computation.

## Key Ports (Interfaces)

### MarketDataPort
Loads OHLCV price data with strict point-in-time filtering. Must never return data after prediction_time.

### NewsDiscoveryPort
Discovers articles mentioning stocks via RSS feeds or Google Custom Search. Returns article metadata (URL, title, snippet, source, date).

### BuzzScorerPort
Measures social buzz from Reddit and StockTwits. Returns trending tickers with mention counts and raw post text.

### SentimentScorerPort
Converts text to sentiment score [-1.0, 1.0]. Implementations: keyword baseline, Flan-T5 fine-tuned, LLM API. Swappable without changing pipeline logic.

### RecommendationStorePort
Persists and retrieves weekly reports and accuracy records. SQLite today, PostgreSQL later. The port abstraction makes the swap transparent.

### TechnicalAnalysisPort
Computes technical indicators from raw OHLCV data. Returns TechnicalIndicators with composite signal.

## Feature Groups (44 total)

| Group | Count | Source |
|-------|-------|--------|
| Technical | 15 | yfinance OHLCV data |
| Sentiment/Buzz | 11 | News + social sources |
| Divergence | 4 | Computed (technical vs sentiment) |
| Sector Context | 3 | Sector ETFs via yfinance |
| Options Flow | 4 | yfinance options chain |
| Analyst Actions | 4 | yfinance analyst recommendations |
| Cross-Correlation | 3 | Peer group comparison |

## NLP Progression Ladder

| Step | Model | Cost | When to upgrade |
|------|-------|------|----------------|
| 1 | Keyword scoring (bullish/bearish word counts) | Free | Baseline — always start here |
| 2 | Flan-T5 fine-tuned for financial sentiment | Free (local) | When keyword precision plateaus |
| 3 | Claude/Gemini API | ~$5-15/week | When Flan-T5 plateau, and only if lift > 2% |

**Upgrade rule:** Never upgrade NLP without measuring lift. If Step N+1 improves precision by < 2%, stay at Step N.

## Evaluation Framework

| Metric | What It Measures | Benchmark |
|--------|-----------------|-----------|
| Cumulative return | Business value | SPY ETF same period |
| Sharpe ratio | Risk-adjusted return | SPY Sharpe ratio |
| Directional accuracy | Prediction quality | 50% (random baseline) |
| Precision per grade | Grade reliability | Per-grade historical average |

**Never claim "beats the market" without Sharpe ratio comparison.** Raw returns without risk adjustment are misleading.

## Market Configuration

Markets are config-driven via YAML files in `config/markets/`. Each market defines:
- RSS feed URLs
- Google search targets
- Reddit subreddits
- Sector ETFs
- Trading hours and timezone
- Filtering thresholds

Adding a new market = adding a YAML file. No code changes required.

| Market | Config | Status |
|--------|--------|--------|
| US (NYSE/NASDAQ) | `us.yaml` | Phase 3 (active) |
| Canada (TSX) | `ca.yaml` | Phase 4 (planned) |
| India (NSE/BSE) | `in.yaml` | Phase 5 (planned) |

## Anti-Patterns (Never Do These)

- **Never use future-dated data** — `FUTURE_LEAKAGE_COLUMNS` lists forbidden features
- **Never evaluate with accuracy alone** — class distribution and directional accuracy require precision/recall
- **Never skip the keyword baseline** — it is the control group for all NLP experiments
- **Never hardcode stock tickers** — the universe is dynamic, discovered weekly
- **Never merge sentiment from different time zones without normalization** — US market hours differ from when news publishes
- **Never trust raw social sentiment** — normalize, aggregate, require minimum source diversity
