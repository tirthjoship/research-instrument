# Expanded Stock Intelligence Engine — Design Spec

**Date:** 2026-06-01
**Status:** Approved (grilling session complete)
**Scope:** Phase 3B Validation → Phase 3.5 → Phase 4A/4B/4C/4D → Phase 5

---

## Vision

An always-learning stock intelligence engine that:
1. Detects buy opportunities before momentum is fully priced in
2. Monitors holdings for sell signals (crash risk, negative sentiment avalanche)
3. Tracks cross-asset relationships (sector co-movement, supply chain propagation, thematic cascades)
4. Learns which news events move which sectors, in which direction, for how long
5. Gets sharper over time via recursive learning from outcome tracking

---

## Signal Architecture — Four Layers

The system combines four signal layers, each testable independently via ablation:

| Layer | Features | Data Source | Status |
|-------|----------|-------------|--------|
| **Technical** | 45 features (price, momentum, volatility, regime) | yfinance OHLCV | ✅ Built |
| **Fundamental** | ~15 features (PEG, P/E, P/B, FCF yield, debt, dividends, earnings) | yfinance `ticker_info` + `analyst_data` | 🆕 Phase 4A |
| **Sentiment** | 14 features (buzz volume, headline sentiment, divergence, source reliability) | RSS, StockTwits, Google Trends, news headlines | 🔨 Phase 3.5 expansion |
| **Cross-Asset** | ~10 features (lead-lag correlation, sector momentum contagion, thematic basket activation) | Price correlation matrix + supply chain graph | 🆕 Phase 4C |
| **Event-Causal** | ~8 features (event category, affected sectors, historical direction, decay duration) | News classification + historical event-sector mapping | 🆕 Phase 4D |

Total feature space: ~92 features across 5 layers. Each layer has its own feature engineer adapter implementing `FeatureEngineerPort`.

---

## Phase Roadmap

### Phase 3B Validation (Immediate — No New Code)

**Goal:** Prove existing Phase 3B code actually works end-to-end.

**What:**
1. Run full pipeline: RSS daily scan → keyword scoring → sentiment features → Stage 2 stacking → recommendation
2. Run three-way ablation on whatever sentiment data exists (even if sparse)
3. Compute permutation p-values for each horizon
4. Fix whatever breaks
5. Document results honestly — even null results

**Success criteria:**
- Pipeline runs without errors on 40-ticker universe
- Ablation produces numbers for all three configurations
- All results documented in README with p-values

**No new adapters, no new features.** Just validate what's built.

---

### Phase 3.5: Expanded Sentiment + Universe (After 3B Validates)

**Goal:** Historical sentiment data for backtesting + expand ticker universe.

#### 3.5.1 — Google Trends Adapter

**Port:** `BuzzDiscoveryPort` (existing)

**Adapter:** `adapters/data/google_trends_adapter.py`

```
GoogleTrendsAdapter implements BuzzDiscoveryPort:
  - scan_sources(scan_time) → list[BuzzSignal]
  - get_historical_interest(ticker, start_date, end_date) → list[BuzzSignal]
  - Uses pytrends library (unofficial, no API key)
  - Weekly granularity, normalized 0-100 search interest
  - Rate limit: 1 request per 2 seconds (Google throttles aggressively)
  - Maps search volume to BuzzSignal with scorer="google_trends"
```

**Historical capability:** Can fetch search interest back to 2004. This gives us years of "retail buzz" data for backtesting without waiting for live RSS accumulation.

**Features added to sentiment feature engineer:**
- `google_trends_current` — current week search volume (0-100)
- `google_trends_change_1w` — week-over-week change
- `google_trends_spike` — boolean: >2 std dev above 52-week mean

#### 3.5.2 — StockTwits Adapter

**Port:** `BuzzDiscoveryPort` (existing)

**Adapter:** `adapters/data/stocktwits_adapter.py`

```
StockTwitsAdapter implements BuzzDiscoveryPort:
  - scan_sources(scan_time) → list[BuzzSignal]
  - Free API, no approval needed
  - $CASHTAG convention makes ticker extraction trivial
  - Returns message volume + bullish/bearish ratio per ticker
  - Rate limit: 200 requests/hour
  - Maps to BuzzSignal with scorer="stocktwits"
```

**Features:**
- `stocktwits_volume_24h` — message count last 24 hours
- `stocktwits_bullish_ratio` — % of messages tagged bullish
- `stocktwits_volume_change` — vs 7-day average

#### 3.5.3 — News Headline Sentiment (GDELT or NewsAPI fallback)

**Port:** New `HistoricalSentimentPort`

```python
class HistoricalSentimentPort(Protocol):
    def get_historical_sentiment(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[Sentiment]: ...
```

**Adapter:** `adapters/data/news_sentiment_adapter.py`

**Primary: GDELT Project** (free, massive, historical)
- Global Database of Events, Language, and Tone
- Pre-scored sentiment on news articles with timestamps
- Covers major financial news sources
- Daily granularity, available back to 2015
- Complexity: BigQuery access or bulk CSV download

**Fallback: NewsAPI** ($0 for 100 req/day developer tier)
- Simpler API, limited historical (1 month on free tier)
- Good for live pipeline, weak for backtesting

**Decision:** GDELT for historical backtesting, NewsAPI for live daily scan if GDELT latency is too high.

**Features:**
- `news_sentiment_avg_7d` — average headline sentiment (last 7 days)
- `news_volume_7d` — number of articles mentioning ticker
- `news_sentiment_momentum` — sentiment change vs prior 7 days
- `news_negative_spike` — boolean: negative articles > 2 std dev (crash warning)

#### 3.5.4 — Expanded Ticker Universe

Expand from 40 hardcoded tickers to S&P 500 + NASDAQ-100 (~350 unique after overlap).

**Implementation:**
- Replace hardcoded `_get_ticker_universe()` in `cli.py` with config-driven list
- `config/markets/us.yaml` already has a `tickers` section — expand it
- Use Wikipedia S&P 500 list + NASDAQ-100 list (static snapshot, refresh quarterly)
- Store as `config/tickers/sp500.txt` and `config/tickers/nasdaq100.txt`
- ADR-017 cache mixin handles the first-run API cost — all subsequent runs use cache

**Pretraining strategy:** Pretrain all 350 upfront. First run takes hours (use `caffeinate`). Cache persists. Future: GitHub Actions `workflow_dispatch` for headless pretraining.

---

### Phase 4A: Fundamental Valuation Features

**Goal:** Add financial health and valuation signals to feature matrix.

**Adapter:** `adapters/ml/fundamental_feature_engineer.py` implementing `FeatureEngineerPort`

**Features (from yfinance `ticker_info` — already fetched, just not used):**

| Feature | Source Field | What It Measures |
|---------|-------------|-----------------|
| `peg_ratio` | `pegRatio` | Growth-adjusted P/E |
| `pe_ratio` | `trailingPE` | Price-to-earnings |
| `pe_vs_sector` | computed | P/E relative to sector median |
| `price_to_book` | `priceToBook` | Asset-based valuation |
| `debt_to_equity` | `debtToEquity` | Financial leverage / risk |
| `free_cash_flow_yield` | `freeCashflow / marketCap` | Real cash generation |
| `dividend_yield` | `dividendYield` | Income signal |
| `revenue_growth_yoy` | `revenueGrowth` | Growth trajectory |
| `earnings_surprise_last` | analyst data | Beat/miss last quarter |
| `earnings_surprise_streak` | analyst data | Consecutive beats/misses |
| `insider_net_purchases_90d` | Quiver Quant (future) | Management confidence |
| `institutional_ownership_change` | yfinance | Smart money flow |
| `current_ratio` | `currentRatio` | Short-term solvency |
| `gross_margin` | `grossMargins` | Pricing power |
| `operating_margin` | `operatingMargins` | Operational efficiency |

**Note:** Some of these (earnings_surprise, pe_vs_sector) were in the original 45-feature spec but returned NaN because the feature engineer didn't compute them from available data. Phase 4A wires them properly.

**Valuation signal (composite):**
- `valuation_z_score` — composite of PEG + P/B + FCF yield, standardized vs sector. Negative = undervalued, positive = overvalued.
- Similar to what SimplyWallSt shows as "fair value" analysis.

---

### Phase 4B: Portfolio Tracking + Sell Signals

**Goal:** Track holdings, generate sell signals, monitor risk.

#### Holdings Domain Model

```python
@dataclass(frozen=True)
class Holding:
    symbol: str
    quantity: float
    purchase_price: float
    purchase_date: str  # YYYY-MM-DD
    notes: str = ""

@dataclass(frozen=True)
class SellSignal:
    symbol: str
    signal_date: str
    signal_type: str  # "crash_risk" | "negative_sentiment" | "technical_breakdown" | "stop_loss"
    urgency: str  # "immediate" | "this_week" | "watch"
    reasoning: str
    confidence: float  # 0-1
```

#### Holdings Port

```python
class HoldingsPort(Protocol):
    def add_holding(self, holding: Holding) -> None: ...
    def remove_holding(self, symbol: str) -> None: ...
    def get_holdings(self) -> list[Holding]: ...
    def get_holding(self, symbol: str) -> Holding | None: ...
```

**Adapter:** `SQLiteStore` extended with `holdings` table.

#### Sell Signal Detection

New use case: `MonitorHoldingsUseCase`

```
For each holding:
  1. Check negative sentiment avalanche (news_negative_spike + stocktwits_bearish_surge)
  2. Check technical breakdown (price < SMA20 + MACD bearish crossover)
  3. Check fundamental deterioration (earnings miss + guidance cut)
  4. Check cross-asset contagion (sector leader crashed, holding is a follower)
  5. Compute crash probability from combined signals
  6. If crash_probability > threshold → SellSignal
```

**CLI commands:**
```bash
python -m application.cli add-holding AMD 50 --price 165.00 --date 2026-05-15
python -m application.cli list-holdings
python -m application.cli monitor-holdings  # check all holdings for sell signals
python -m application.cli remove-holding AMD
```

#### Stop-Loss Monitoring

- Configurable stop-loss per holding (default -8%)
- `current_price / purchase_price - 1 < -0.08` → immediate sell signal
- Configurable in `config/markets/us.yaml`: `risk.stop_loss_threshold: -0.08`

---

### Phase 4C: Cross-Asset Intelligence

**Goal:** Detect sector co-movement, supply chain propagation, and thematic cascades.

#### Correlation Graph

**Adapter:** `adapters/ml/correlation_analyzer.py`

```python
class CorrelationAnalyzer:
    def compute_correlation_matrix(
        self, signals_by_ticker: dict[str, list[Signal]], window_days: int = 60
    ) -> dict[tuple[str, str], float]: ...

    def detect_lead_lag(
        self, leader: list[Signal], follower: list[Signal], max_lag_days: int = 5
    ) -> tuple[int, float]:
        """Returns (lag_days, correlation_strength)."""
        ...

    def find_clusters(
        self, correlation_matrix: dict[tuple[str, str], float], threshold: float = 0.7
    ) -> list[list[str]]:
        """Group tickers by correlation clusters."""
        ...
```

#### Supply Chain Graph — Hybrid (Decision C from grilling)

**Auto-discovered:** Rolling 60-day correlation matrix clusters tickers automatically. Tickers with correlation > 0.7 are grouped.

**Manual override:** `config/supply_chains.yaml`

```yaml
semiconductors:
  leaders: [AMAT, LRCX, KLAC, ASML]
  followers: [MU, WDC, SNDK, INTC, AMD, NVDA]
  typical_lag_days: 1-3

space_defense:
  catalysts: [SpaceX_news, NASA_contract, DOD_budget]
  basket: [STM, HXL, IRDM, LUNR, ASTS, RKLB, LMT, RTX, NOC]
  typical_lag_days: 1-5

pharma_supply_chain:
  upstream: [PFE, JNJ, ABBV, MRK, LLY]
  distribution: [MCK, ABC, CAH]
  retail: [WMT, CVS, WBA]
  typical_lag_days: 2-5

big_tech_ecosystem:
  leaders: [AAPL, MSFT, GOOG, AMZN, META]
  suppliers: [TSM, AVGO, QCOM, TXN, ADI]
  typical_lag_days: 0-2

energy_chain:
  upstream: [XOM, CVX, COP, SLB]
  midstream: [WMB, KMI, ET]
  downstream: [VLO, MPC, PSX]
  consumers: [DAL, UAL, AAL]  # airlines inversely correlated
  typical_lag_days: 1-3

retail_consumer:
  leaders: [WMT, AMZN, COST]
  followers: [TGT, DG, DLTR]
  typical_lag_days: 1-3
```

**Merge strategy:** Auto-clusters are default. Manual YAML entries override auto-detected groups for those tickers. Manual entries can also specify `inverse: true` for negatively correlated pairs (airlines vs oil).

#### Cross-Asset Features

| Feature | What It Detects |
|---------|----------------|
| `sector_leader_move_1d` | Did sector leader move >2% yesterday? |
| `leader_follower_lag_signal` | Leader moved, follower hasn't yet — buy/sell signal |
| `cluster_momentum_1w` | Average return of correlated cluster last week |
| `thematic_activation` | >3 tickers in thematic basket moved same direction |
| `supply_chain_upstream_signal` | Upstream companies moved, downstream hasn't reacted |
| `correlation_regime_shift` | Correlation with cluster changing (diverging from peers) |

#### Cascade Detection Use Case

```
New use case: CascadeDetectionUseCase

Input: Today's price changes for all 350 tickers
Process:
  1. Identify any ticker with >3% move in last 24h
  2. Look up its correlation cluster + supply chain group
  3. Check which related tickers HAVEN'T moved yet
  4. Score each unmoved ticker: correlation_strength × leader_move × historical_follow_rate
  5. Output: "LRCX likely to follow AMAT (+4.2% yesterday). Historical follow rate: 73%. Expected move: +2.1-3.5% within 2 days."
```

---

### Phase 4D: Event-Causal Learning

**Goal:** Learn which news events move which sectors, in which direction, for how long.

#### Event Taxonomy

```python
class EventCategory(Enum):
    TRADE_WAR = "trade_war"
    FED_RATE_DECISION = "fed_rate_decision"
    EARNINGS_SEASON = "earnings_season"
    GEOPOLITICAL_CONFLICT = "geopolitical_conflict"
    COMMODITY_SHOCK = "commodity_shock"
    REGULATORY_ACTION = "regulatory_action"
    IPO_MAJOR = "ipo_major"
    PANDEMIC_HEALTH = "pandemic_health"
    TECH_BREAKTHROUGH = "tech_breakthrough"
    NATURAL_DISASTER = "natural_disaster"
```

#### Event-Sector Impact Model

```python
@dataclass(frozen=True)
class EventSectorImpact:
    event_category: EventCategory
    sector: str  # GICS sector
    direction: float  # -1 to +1 (mean historical impact)
    magnitude: float  # average % move
    duration_days: int  # how long the effect lasts
    confidence: float  # based on number of historical examples
    n_examples: int  # how many times this event-sector pair occurred
```

**Training:** Build from historical events:
1. Classify past news headlines into `EventCategory` (LLM scorer — Claude API or local Flan-T5)
2. For each event, measure sector ETF reactions over [1, 2, 5, 10, 20] day windows
3. Aggregate: "Trade war escalation → Energy +2.3% (5d), Defense +3.1% (5d), Tech -1.8% (5d)"
4. Store learned mappings in SQLite for lookup

**Live pipeline:**
1. Daily scan classifies new headlines into event categories
2. If event detected → look up historical sector impact
3. Cross-reference with current positions and watchlist
4. Generate alerts: "Trade war headlines detected. Historical impact: your AAPL holding -1.8% over 5 days. Defense stocks (RTX, LMT) historically +3.1%."

**Decay model:** Impact decays exponentially. Trump tariff announcement: day 1 = full impact, day 5 = 50%, day 10 = 25%. Decay half-life learned per event category from historical data.

#### Event-Causal Features

| Feature | What It Measures |
|---------|-----------------|
| `event_category_active` | Is there an active event affecting this sector? |
| `event_historical_direction` | Historical average direction for this event-sector pair |
| `event_days_since` | Days since event detected (for decay weighting) |
| `event_confidence` | How many historical examples back this prediction |
| `event_residual_impact` | Expected remaining impact (magnitude × decay) |

---

### Phase 5: Dashboard + Recursive Learning

**Goal:** Streamlit dashboard, continuous improvement, paper trading.

#### Streamlit Dashboard
- Portfolio overview (holdings, P&L, sell signals)
- Weekly tournament results (top 15 picks)
- Cross-asset correlation heatmap
- Event timeline with sector impact overlay
- Accuracy tracking over time (is model improving?)
- Ablation results visualization

#### Recursive Learning Loop
- Source reliability tracker (built) — weights sentiment by source accuracy
- Model retraining on new data (walk-forward, already built)
- Feature importance drift detection — alert if SHAP top-10 changes dramatically
- Automatic feature pruning — drop features that consistently show zero importance
- Hyperparameter re-optimization quarterly

#### Adaptive Strategy
- If model detects new correlation clusters, add to supply chain graph automatically
- If accuracy drops for a sector, increase uncertainty for that sector's predictions
- If a new event type appears (e.g., AI regulation), create new EventCategory and start learning

---

## Realistic Success Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Sentiment classification accuracy | 65-70% | With LLM scorer |
| Stock direction prediction accuracy | 52-55% | Over 50% random baseline |
| Edge over technical-only baseline | 2-5% lift | Measured via ablation |
| Cross-asset cascade detection | 60-70% follow-through rate | On high-confidence signals |
| Sell signal precision | >60% | Of sell signals issued, >60% avoided real losses |
| Model improvement over time | Measurable | Accuracy trend positive over 3+ months |

**Honest null result is still valid.** If sentiment/cross-asset/event-causal add zero lift, we document it and the project story becomes rigorous hypothesis testing with clean negative results.

---

## ADR Decisions Made During Grilling

| ADR | Decision | Rationale |
|-----|----------|-----------|
| ADR-023 | Expanded ticker universe: S&P 500 + NASDAQ-100 (~350 tickers) | 40 was Phase 3A constraint, no longer needed |
| ADR-024 | Historical sentiment via Google Trends + GDELT, not live RSS wait | Can't wait 4 weeks for data when years of history exist |
| ADR-025 | Fundamental valuation features from yfinance ticker_info | Data already fetched, just not in feature matrix |
| ADR-026 | Portfolio holdings in SQLite with sell signal detection | Option A from grilling — simplest, local, manual entry |
| ADR-027 | Hybrid cross-asset graph: auto-correlation + manual supply chain YAML | Option C from grilling — discovers unknown links, human validates |
| ADR-028 | Event-causal learning: news classification → sector impact → decay model | Historical training first, live detection second |

---

## Dependencies and Constraints

- **pytrends** — unofficial Google Trends lib, may break with Google changes
- **GDELT** — free but complex (BigQuery or bulk CSV). May need fallback to NewsAPI.
- **StockTwits API** — free tier, 200 req/hr. Sufficient for daily scan, not real-time.
- **scipy** — for binomial test in evaluation. Standard, no risk.
- **boto3** — for S3 uploads. Optional dependency.
- **LLM API (Phase 4D)** — Claude API for event classification. Cost: ~$0.01 per 1000 headlines.
- **First pretrain on 350 tickers** — multi-hour run, needs `caffeinate` or GHA workflow.

---

## Out of Scope

- Brokerage API integration (Phase 5/6)
- Real-money trading (Phase 6, requires 6 months paper trading)
- HFT / microsecond execution
- Deep learning / transformers (ensemble approach validated, no evidence DL helps)
- Crypto markets
- Options trading signals
