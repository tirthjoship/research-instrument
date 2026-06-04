# Opportunity Intelligence Engine — Design Spec

> **Date:** 2026-06-03
> **Scope:** Phases 7–9 of multi-modal-stock-recommender
> **Purpose:** Transform the system from a direction predictor into an adaptive opportunity surfacing engine for personal investment use + portfolio showcase.

---

## 1. Vision

The current system predicts stock direction (up/down) with 46–49% accuracy — no edge. But the infrastructure (5 data adapters, 350+ tickers, 6-tab dashboard, 518 tests) is solid.

The reframe: **stop predicting direction, start surfacing opportunities early with conviction scoring.** Not "AAPL will go up" but "unusual hedge fund accumulation + positive tone shift + strong fundamentals on AAPL — investigate now, conviction 8/10."

The system learns from tracked outcomes and evolves its strategy over time, becoming genuinely intelligent after enough feedback.

### Design Principles

- **Speed of information** — catch trends before mainstream/influencers
- **Multi-signal convergence** — one signal is noise, 4+ aligned signals is conviction
- **Beginner-friendly** — no jargon, plain English, simple actions (Buy/Hold/Watch/Sell)
- **Honest** — shows confidence level, explains what could go wrong, admits uncertainty
- **Adaptive** — learns from mistakes, adjusts weights, remembers patterns
- **Portfolio-grade polish** — WealthSimple / Simply Wall St level UI (via `/frontend-design`)

---

## 2. Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                        DATA LAYER                                │
│  Existing: yfinance, RSS, StockTwits, GDELT, Google Trends       │
│  New: SEC EDGAR (13D filings, Form 4 insider trades)             │
└──────────────┬───────────────────────────────────────────────────┘
               ▼
┌──────────────────────────────────────────────────────────────────┐
│                     SIGNAL LAYER                                 │
│  Technical features ──┐                                          │
│  Fundamental features ┤                                          │
│  Cross-asset features ┤──▶ Per-ticker signal vector              │
│  Event-causal features┤                                          │
│  Sentiment features ──┤                                          │
│  Smart money signals ─┘  (NEW: 13D, Form 4)                     │
│  ML direction prediction ── low-weight input from existing model │
└──────────────┬───────────────────────────────────────────────────┘
               ▼
┌──────────────────────────────────────────────────────────────────┐
│                  CONVICTION ENGINE (NEW)                          │
│  Multi-signal scoring: agreement × quality × freshness           │
│  Output: conviction score 1–10 per ticker                        │
│  Ranks 350+ tickers → surfaces top 15                            │
│  Pinned watchlist always included                                │
└──────────────┬───────────────────────────────────────────────────┘
               ▼
┌──────────────────────────────────────────────────────────────────┐
│               RECOMMENDATION ENGINE (NEW)                        │
│  Generates 4-part opportunity cards:                              │
│    Alert → Evidence → Suggestion → Risk                          │
│  Plain English, beginner-friendly                                │
│  Actions: Buy / Hold / Watch / Sell                              │
└──────────────┬───────────────────────────────────────────────────┘
               ▼
┌──────────────────────────────────────────────────────────────────┐
│                OUTCOME TRACKER (NEW)                              │
│  Manual tracking: user marks buy/sell in dashboard                │
│  Correlates outcomes to signals that fired                       │
│  Signal report card: which signals work, which don't             │
│  Historical bootstrap: simulate 6mo of past recommendations     │
└──────────────┬───────────────────────────────────────────────────┘
               ▼
┌──────────────────────────────────────────────────────────────────┐
│               PATTERN MEMORY + LEARNING (NEW)                    │
│  Stores: signal combination → outcome, N occurrences             │
│  Strategy evolution: weight adjustment from outcome data         │
│  New rules emerge: "never recommend pure-technical mega-caps"    │
│  Learns from YOUR investment style over time                     │
└──────────────────────────────────────────────────────────────────┘
```

---

## 3. New Data Sources

### SEC EDGAR — 13D Filings (Activist Investors)

- **What:** When an investor acquires 5%+ of a company, they must file a 13D within 10 days.
- **Why:** Activist stakes often precede major price moves — the "hedge fund making a move" signal.
- **API:** SEC EDGAR XBRL/RSS feeds — free, no API key required.
- **Adapter:** `SECEdgar13DAdapter` implementing existing `SignalSourcePort`.
- **Features extracted:** filer name, stake size (%), date filed, passive vs activist intent, ticker.

### SEC EDGAR — Form 4 (Insider Trading)

- **What:** Company insiders (CEO, CFO, directors, 10%+ holders) must report trades within 2 business days.
- **Why:** Insider buying clusters = strong bullish signal. One insider sells = nothing. Five insiders buy in a week = meaningful.
- **API:** SEC EDGAR XBRL/RSS feeds — free, no API key required.
- **Adapter:** `SECEdgarForm4Adapter` implementing existing `SignalSourcePort`.
- **Features extracted:** insider role, transaction type (buy/sell), shares, dollar value, date, cluster detection (multiple insiders within N days).

### Hexagonal Integration

Both adapters implement new port protocols following the existing pattern (like `MarketDataPort`, `SentimentPort`, `BuzzDiscoveryPort`). No changes to existing domain layer. New features flow through existing `validate_point_in_time_access()` guard in `domain/services.py`.

---

## 4. Conviction Scoring Engine

### Domain Model

```python
@dataclass(frozen=True)
class ConvictionScore:
    ticker: str
    score: float          # 1.0 – 10.0
    sub_scores: dict      # per-dimension breakdown
    signals_firing: int   # count of active signals
    freshest_signal: datetime
    explanation: str      # plain English summary

@dataclass(frozen=True)
class ConvictionWeights:
    signal_agreement: float   # default 1.0
    smart_money: float        # default 1.5
    sentiment_momentum: float # default 1.0
    fundamental_basis: float  # default 1.0
    temporal_freshness: float # default 1.2
    ml_direction: float       # default 0.3 (low — unproven)
```

### Scoring Dimensions

| Dimension | Inputs | Score Range | Weight |
|-----------|--------|-------------|--------|
| Signal agreement | Count of layers with aligned signals | 0–10 | 1.0 |
| Smart money | 13D filings, Form 4 insider clusters | 0–10 | 1.5 |
| Sentiment momentum | RSS trend, StockTwits, GDELT tone shift direction + magnitude | 0–10 | 1.0 |
| Fundamental basis | P/E, revenue growth, sector-relative valuation | 0–10 | 1.0 |
| Temporal freshness | Age of newest signal (fresher = higher) | 0–10 | 1.2 |
| ML direction | Existing model's directional probability | 0–10 | 0.3 |

**Total conviction** = weighted average of sub-scores, normalized to 1–10.

### Freshness Decay

| Signal Age | Freshness Score |
|------------|----------------|
| < 4 hours | 10 |
| 4–24 hours | 8 |
| 1–3 days | 6 |
| 3–7 days | 4 |
| > 7 days | 2 |

### Universe + Ranking

- Scan full 350+ ticker universe
- Score every ticker with available signals
- Rank by conviction score descending
- Surface top 15 + any pinned watchlist tickers regardless of rank
- Minimum conviction threshold: 3/10 to appear (filter noise)

---

## 5. Recommendation Engine

### Opportunity Card (4-part output)

Each surfaced opportunity produces a card:

**Part 1 — Alert:**
```
NVDA  ·  Conviction 8/10  ·  ▲ BUY signal
Signals: 4 of 6 layers aligned  ·  Freshest: 2 hours ago
```

**Part 2 — Evidence (plain English):**
```
• Smart Money: An activist investor (ValueAct Capital) just filed a 13D —
  they bought 5.2% of the company. This often precedes big changes.
• Sentiment: Social media chatter turned sharply positive over the last
  3 days (+0.4 tone shift on GDELT). This started BEFORE mainstream
  news picked it up.
• Fundamentals: P/E ratio is 18.3, below the sector average of 24.1.
  Revenue grew 12% last quarter.
• Insider Activity: CFO bought $2.3M in shares yesterday (Form 4 filed).
```

**Part 3 — Suggestion:**
```
Suggestion: BUY — multiple independent signals converging.
Only invest money you're comfortable losing.
```

**Part 4 — Risk:**
```
What could go wrong:
• The 13D filing could be passive (no activist intent)
• Broad market downturn could drag this stock down regardless
• Sentiment spikes sometimes reverse quickly
```

### Action Types

| Action | When | Plain English |
|--------|------|---------------|
| **BUY** | Conviction ≥ 7, signals aligned bullish | "Multiple signals say this looks good" |
| **WATCH** | Conviction 5–7, or mixed signals | "Something interesting brewing, keep an eye on it" |
| **HOLD** | Already own + no strong sell signals | "No reason to sell yet, stay the course" |
| **SELL** | Conviction ≥ 7 bearish, or thesis invalidated | "The reasons you bought may no longer apply" |

---

## 6. Outcome Tracking + Learning

### Manual Tracking

User records in dashboard:
- "Bought NVDA at $142 on 2026-06-05" (links to opportunity card that surfaced it)
- "Sold NVDA at $158 on 2026-07-10"
- System calculates: +11.3% return, 35-day hold

### Signal Report Card (monthly)

```
Your Signal Performance — June 2026
────────────────────────────────────
Best signal:    Insider buying clusters (72% hit rate, 8 trades)
Worst signal:   Technical indicators alone (44% hit rate, 12 trades)
Most profitable: GDELT tone + insider combo (avg +8.2% return)
Least useful:   ML direction prediction (49% accuracy — still noise)

Recommendation: Increase smart money weight. Consider ignoring
pure-technical opportunities until ML model improves.
```

### Historical Bootstrap (Cold-Start Solution)

Use 6 months of historical data (2025-12 to 2026-05) to simulate:
1. For each date, compute what signals were available
2. Generate simulated conviction scores
3. Record what actually happened 7/30/90 days later
4. Pre-populate pattern memory with 100+ simulated outcomes

This gives the system semi-intelligent weights on day one — not perfect, but better than uniform defaults.

### Pattern Memory (Phase 9)

Stores tuples: `(signal_combination, sector, market_condition) → outcome_distribution`

Examples:
- `(insider_cluster + GDELT_spike, tech, bull_market) → +8.2% avg, 72% positive, N=14`
- `(technical_only, mega_cap, any) → +0.3% avg, 48% positive, N=31` → system learns to weight this near zero
- `(13D_activist + sentiment_shift, any, any) → +12.1% avg, 78% positive, N=6` → high confidence despite small N due to magnitude

### Strategy Evolution

- Weights adjust quarterly based on outcome data
- New rules can emerge: "never recommend pure-technical plays on mega-caps" (learned, not hardcoded)
- System shows its learning: "Conviction weights changed this month: smart_money 1.5→1.8, ml_direction 0.3→0.15"
- User can override: "I trust fundamentals more" → manual weight adjustment

---

## 7. Temporal Context + Freshness

### Cross-Cutting: Every View Shows Time

| Element | Display |
|---------|---------|
| **Dashboard header** | "Last scan: Jun 3, 2026 at 2:15 PM PDT · Market: OPEN" |
| **S&P 500 sparkline** | Intraday chart in header or Market Pulse — today's market context |
| **Opportunity cards** | Per-signal timestamps: "13D filed: 6hrs ago", "Sentiment shift: 2 days ago" |
| **Market data** | "Prices as of: 2:15 PM (market open)" or "4:00 PM (market closed)" |

### Freshness Color Coding

| Age | Color | Meaning |
|-----|-------|---------|
| < 4 hours | Green | Fresh — act on this |
| 4–24 hours | Yellow | Recent — still relevant |
| > 24 hours | Red | Stale — verify before acting |

### S&P 500 Context Widget

- Small intraday sparkline from yfinance (free, no new adapter)
- Shows: current value, daily change %, intraday high/low
- Purpose: "Am I looking at a conviction-8 BUY during a crash or a rally?"
- Location: dashboard header bar (persistent across all tabs)

---

## 8. Dashboard Tab Evolution

| Tab | Current | Evolves To | Key Changes |
|-----|---------|-----------|-------------|
| **Command Center** | Manual run buttons | **Opportunity Feed** | Top 15 cards ranked by conviction, run button triggers full scan |
| **Market Pulse** | Macro overview | **Market Pulse + Context** | Add S&P sparkline, sector heatmap, "market mood" indicator |
| **Model Confidence** | ML accuracy stats | **System Intelligence** | Signal report card, weight history, learning progress, pattern memory stats |
| **Signal Breakdown** | Per-ticker signal table | **Signal Deep Dive** | Feeds evidence cards, shows all signals per ticker with timestamps |
| **Positions** | Current holdings display | **Outcome Tracker** | Manual buy/sell logging, P&L, outcome correlation to signals |
| **Opportunities** | Watchlist + scan | **Watchlist + History** | Pinned favorites, historical recommendations, "what happened to past alerts" |

### Design Direction

- `/frontend-design` skill for WealthSimple / Simply Wall St level polish
- Clean, confident, minimal — not a data science notebook
- Mobile-friendly card layouts
- Conviction score as the hero number on each card
- Green/yellow/red freshness indicators throughout

---

## 9. Operating Modes

### Daily Scan (Primary)

- Triggered manually or via scheduled job
- Runs all adapters, computes conviction scores, generates opportunity cards
- Updates dashboard with fresh results
- Target runtime: < 5 minutes for full 350+ ticker scan

### Periodic Filing Check (2–3x daily)

- Lightweight: only checks SEC EDGAR for new 13D/Form 4 filings since last check
- If new filing found for any tracked ticker → recompute conviction for that ticker
- Dashboard shows "New filing detected" badge

### Scan Cadence

```
6:00 AM  — Pre-market: full daily scan (all adapters)
12:00 PM — Midday: filing check only (SEC EDGAR)
6:00 PM  — Post-market: filing check + end-of-day price update
```

User can trigger manual full scan anytime from dashboard.

---

## 10. Phasing

### Phase 7: Foundation

**Delivers:** "Surface opportunities I'd miss"

| Task | Component | Depends On |
|------|-----------|------------|
| 7.1 | SEC EDGAR 13D adapter | — |
| 7.2 | SEC EDGAR Form 4 adapter | — |
| 7.3 | Smart money feature extraction (cluster detection, stake %) | 7.1, 7.2 |
| 7.4 | ConvictionScore domain model + scoring engine | — |
| 7.5 | ConvictionWeights with configurable weights | 7.4 |
| 7.6 | Opportunity card generation (4-part: alert/evidence/suggestion/risk) | 7.4 |
| 7.7 | Dashboard: Command Center → Opportunity Feed | 7.6 |
| 7.8 | Dashboard: header freshness bar + S&P sparkline | — |
| 7.9 | Dashboard: freshness color coding across all tabs | — |
| 7.10 | Dashboard: `/frontend-design` polish pass | 7.7, 7.8, 7.9 |

### Phase 8: Memory

**Delivers:** "Track what works"

| Task | Component | Depends On |
|------|-----------|------------|
| 8.1 | Outcome tracking domain model (Trade, Outcome) | — |
| 8.2 | Manual buy/sell entry in Positions → Outcome Tracker tab | 8.1 |
| 8.3 | Outcome correlation engine (link outcomes to signals that fired) | 8.1 |
| 8.4 | Signal report card generation | 8.3 |
| 8.5 | Model Confidence → System Intelligence tab | 8.4 |
| 8.6 | Historical bootstrap: simulate 6mo of past recommendations | 7.4, 8.3 |
| 8.7 | Pre-populate pattern data from bootstrap | 8.6 |

### Phase 9: Intelligence

**Delivers:** "System gets smarter"

| Task | Component | Depends On |
|------|-----------|------------|
| 9.1 | Pattern memory store (signal combo → outcome distribution) | 8.3 |
| 9.2 | Strategy evolution: weight adjustment from outcomes | 9.1 |
| 9.3 | Emergent rules: auto-detect "never do X" patterns | 9.1 |
| 9.4 | Adaptive recommendation: adjust suggestions based on pattern memory | 9.2, 9.3 |
| 9.5 | System Intelligence tab: show learning progress, weight changes, new rules | 9.2, 9.3 |
| 9.6 | Watchlist + History tab: "what happened to past alerts" retrospective | 8.3 |

### Phase Combination Opportunities

- 7.1 + 7.2 are independent → parallel
- 7.7 + 7.8 + 7.9 can merge into one dashboard sprint
- 8.6 + 8.7 (bootstrap) could pull into Phase 7 if we want day-one intelligence
- 7.10 (design polish) can run as a continuous thread across all phases

---

## 11. Hexagonal Compliance

All new components follow existing architecture:

| Component | Layer | Location |
|-----------|-------|----------|
| ConvictionScore, ConvictionWeights, Trade, Outcome | Domain | `domain/models.py` |
| ConvictionScoringService, OutcomeTracker, PatternMemory | Domain | `domain/services.py` |
| SmartMoneyPort, OutcomePort, PatternMemoryPort | Domain | `domain/ports.py` |
| SECEdgar13DAdapter, SECEdgarForm4Adapter | Adapter | `adapters/data/` |
| ConvictionScoringUseCase, OutcomeTrackingUseCase | Application | `application/use_cases.py` |
| Dashboard tabs | Adapter | `adapters/visualization/tabs/` |

**Guard:** `validate_point_in_time_access()` in `domain/services.py` applies to all SEC EDGAR signals — no future data leaks.

---

## 12. What This Is NOT

- **Not a trading bot** — never auto-executes trades
- **Not financial advice** — personal research tool with clear disclaimers
- **Not real-time** — daily scan + periodic checks, not HFT
- **Not guaranteed** — system admits uncertainty, shows confidence levels, explains risks
- **Not a black box** — every recommendation has full evidence trail

---

## 13. Success Criteria

| Metric | Phase 7 | Phase 8 | Phase 9 |
|--------|---------|---------|---------|
| Opportunities surfaced | Top 15 with conviction scores | Same + tracked outcomes | Same + adaptive |
| Signal sources | 7 (existing 5 + 13D + Form 4) | Same | Same |
| Dashboard polish | WealthSimple-level UI | + outcome tracker | + learning dashboard |
| Learning | Static weights | Signal report card | Auto-adjusting weights |
| Tests | Existing 518 + new adapter/engine tests | + outcome tracking tests | + pattern memory tests |
| Bootstrap | — | 100+ simulated historical outcomes | Pattern memory seeded |
