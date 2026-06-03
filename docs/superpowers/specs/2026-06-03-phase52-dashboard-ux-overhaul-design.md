# Phase 5.2: Dashboard UX Overhaul — Design Spec

> **Goal:** Transform the Streamlit dashboard from a functional but generic data viewer into a polished, self-explanatory decision tool inspired by Wealthsimple and SimplyWallSt. Every section answers a question in plain English first, then shows evidence. One-click actions make it a real tool, not a static report.

## Audience

**Dual audience (decided in brainstorming):**
1. **Hiring managers** — 2-3 minute walkthrough. Must instantly communicate "this person built something real and thoughtful."
2. **Retail investors** — daily use. Must understand every metric, run scans, act on signals without reading documentation.

The dashboard explains itself as if a real investor would use it. That self-explanation IS the interview signal.

## Design Principles

1. **Verdict first, evidence below** — every section answers a question in English, then shows numbers
2. **Explain through the visual** — color, shape, and layout carry meaning (not tooltips or text blocks)
3. **Color = meaning** — green/red immediately tells good/bad, no legend needed
4. **Progressive disclosure** — headline verdict → supporting visual → raw numbers only if you dig
5. **No hidden content for important data** — top picks are cards, not expanders
6. **One-click actionability** — Run Full Cycle button chains the entire pipeline

## Visual Identity

**Tone:** Light clean SaaS (Wealthsimple/Linear inspired)

**Font:** Inter (Google Fonts CDN import)
- h1: 28px, weight 600, color `#111827`
- h2: 20px, weight 600, color `#111827`
- h3: 16px, weight 600, color `#374151`
- Body: 15px, color `#374151`
- Muted: 13px, color `#6B7280`
- Hero metrics: 32px, weight 700
- Card metrics: 24px, weight 700

**Primary accent:** `#2563EB` (blue-600, Linear/Stripe family)

**Spacing:**
- Card padding: `1.5rem`
- Section gaps: `margin-bottom: 2rem`
- Tab content area: `padding: 0 1rem`
- Card border-radius: `12px`
- Button border-radius: `8px`

**Hover effects:**
- Cards: `transform: translateY(-2px)` + shadow deepen (`0 4px 12px rgba(0,0,0,0.12)`)
- Table rows: background `#F8FAFC` on hover
- Buttons: darken 10% on hover, slight scale `1.02`

**Buttons:**
- Primary: `#2563EB` bg, white text, `padding: 12px 24px`
- Secondary: white bg, `#2563EB` border, blue text
- Danger: `#DC2626` bg, white text (sell signals)

**Brand:**
- Footer: "Multi-Modal Stock Recommender · Hexagonal Architecture · Built by Tirth Joshi" in `#D1D5DB` at 12px
- Tab underline active color: `#2563EB` (replaces Streamlit default red)
- Emoji stays on tab labels (visual anchors) — removed from ALL content (urgency, freshness, SHAP legend, badges)

**Things we will NOT do:**
- Dark mode toggle (complexity, no interview value)
- SVG/icon fonts (marginal gain in Streamlit)
- Sidebar navigation (tabs work fine)

## Explanation Pattern

Replaces the current `st.expander("Learn more")` pattern everywhere.

**Section-level:** 1-line plain English sentence always visible under each section header in muted text. No click needed. Answers "what am I looking at?"

**Term-level:** Individual metric labels get HTML `title` attribute hover tooltips. Answers "what does RSI mean?" on demand without cluttering the page.

**Verdict cards:** Key findings stated as plain English sentences with supporting evidence below. Example: "The model doesn't have a proven edge yet" with p-value and accuracy below.

All `st.expander("Learn more")` instances are removed and replaced with inline context sentences.

## Tab 1: Command Center

### Layout

```
┌─────────────────────────────────────────────────────────┐
│  HERO BANNER                                             │
│  Verdict: "3 actions need attention today"               │
│  Portfolio: $20,650 across 4 positions                   │
│  Data: "Signals are fresh — last scan 2h ago"            │
│                                                           │
│  [Run Full Cycle]  (primary button, prominent)           │
│  Progress bar + stage label when running                  │
└─────────────────────────────────────────────────────────┘

┌── URGENT ────────┐  ┌── THIS WEEK ──────┐  ┌── WATCH ─────────┐
│  Colored red      │  │  Colored amber     │  │  Colored gray     │
│  border-left      │  │  border-left       │  │  border-left      │
│  Sell signals or  │  │  Buy opportunities │  │  Emerging signals │
│  stop-loss alerts │  │  with high         │  │  worth monitoring │
│                   │  │  conviction        │  │                   │
└───────────────────┘  └────────────────────┘  └───────────────────┘

Signal Freshness (single row of colored dots)
"All signals current — last scan covered RSS, sentiment, and technical indicators."
Backtest ● fresh   Tournament ● fresh   SHAP ● stale   Holdings ● 4 tracked
```

### Hero Banner

- White card with subtle blue-left border
- Verdict sentence generated from: count of sell signals + buy opportunities + watchlist alerts
- Portfolio total computed from holdings
- Freshness verdict: single sentence summarizing data state
- "Run Full Cycle" button: `#2563EB`, large, right-aligned in banner

### Run Full Cycle Button

**What it chains (3 stages):**
1. **Daily Scan** — RSS + Google Trends + StockTwits + sentiment scoring
2. **Tournament** — Score all tickers, produce Top 15 ranked picks
3. **Track Accuracy** — Compare last week's predictions vs actual prices (learn from mistakes)

**Progress UI:**
```
[████████████░░░░░░░░░░░░░] 45%
Stage 2/3: Running tournament — scoring 350 tickers...
```

Progress bar + stage label. Auto-refreshes tab data on completion via `st.rerun()`.

**Implementation:** New function `run_full_cycle()` in `action_runner.py` that chains:
- `DailyScanUseCase.execute()`
- `WeeklyTournamentUseCase.execute()`
- `TrackRecommendationsUseCase.execute()`

Each stage reports progress via callback.

### Action Cards

Three priority buckets displayed as columns:
- **URGENT** (red border-left): Sell signals, stop-loss breaches
- **THIS WEEK** (amber border-left): High-conviction buy opportunities
- **WATCH** (gray border-left): Emerging signals, lower conviction

Each card contains:
- Ticker + grade badge (CSS-colored, no emoji)
- Plain English verdict: "Semiconductor momentum + supply chain signal"
- Confidence bar (CSS)

Urgency badges use CSS pills: red pill "URGENT", amber pill "THIS WEEK", gray pill "WATCH" — no emoji.

### Signal Freshness

Single row, not 4 separate cards. Format:
- One summary sentence in muted text
- Colored CSS dots (green/amber/red) inline with labels
- Compact, scannable

### Removed from Command Center
- Portfolio table (lives in Positions tab — was duplicated)
- "Active Events" placeholder section

## Tab 2: Model Confidence

### Layout

```
Verdict Card (full width):
┌─────────────────────────────────────────────────────────┐
│  "The model doesn't have a proven edge yet."             │
│   52% accuracy across 19 folds · p=0.15                 │
│   Technical features alone perform at random on          │
│   mega-caps. Adding sentiment lifted accuracy to         │
│   69.7% in-sample — promising but unproven.              │
│                                                [Run Backtest] │
└─────────────────────────────────────────────────────────┘

Horizon selector (radio, styled)

┌─ Metrics row ───────────────────────────────────────────┐
│  Avg Accuracy: 52.0%   Folds: 19   Predictions: 760    │
└─────────────────────────────────────────────────────────┘

Walk-Forward Accuracy chart (keep current)

───────────────────────────────────────────────────────────

Ablation Study
"Does sentiment actually help? Yes — 47.4% → 69.7%"
  Ablation bar chart (keep current, colors good)
  P-value pills below (keep current)

───────────────────────────────────────────────────────────

SHAP Feature Importance
"Which features drive predictions? Colored by signal layer."
  Legend: ● Technical  ● Sentiment  ● Fundamental
         ● Cross-Asset  ● Event-Causal
  (CSS colored dots, NOT emoji circles)
  SHAP bar chart (keep current, layer colors)

───────────────────────────────────────────────────────────

Known Limitations (keep current card style)
```

### Changes from current

- **Verdict card replaces "BEATS RANDOM?" card** — plain English story, not shouting red text
- Verdict is contextual: explains WHY (technical alone = random, sentiment helps)
- **"Run Backtest" button** inside verdict card
- **SHAP legend uses CSS dots** not emoji circles (🔵🟣🟢🟠🔴 → colored `<span>` dots)
- **Ablation gets a verdict sentence**: "Does sentiment actually help? Yes — 47.4% → 69.7%"
- Remove all `st.expander("Learn more")` — replaced with inline context sentences

## Tab 3: Signal Breakdown

### Layout

```
Select Ticker: [AAPL ▾]

┌─────────────────────────────────────────────────────────┐
│  AAPL  HOLD                                              │
│  "Signals are mixed — 1 of 3 layers bullish"            │
│                                                           │
│  Composite: 0.450   5d: +0.50%   Confidence: 55%       │
│                                                           │
│  Convergence: ████░░░░░░ 1/3 bullish (amber bar)       │
└─────────────────────────────────────────────────────────┘

┌─ Technical ─────┐  ┌─ Sentiment ─────┐  ┌─ Fundamental ──┐
│  ● NEUTRAL       │  │  ● NEUTRAL       │  │  ● NOT YET RUN │
│  "No strong      │  │  "Slight         │  │  "Run a         │
│   directional    │  │   positive buzz  │  │   tournament    │
│   pressure"      │  │   but weak"      │  │   with --fund   │
│                  │  │                  │  │   flag to see"  │
│  RSI: 50.0       │  │  Score: 0.20     │  │                 │
│  MACD: 0.05      │  │  Divergence: 0.05│  │                 │
│  Signal: 0.10    │  │  Type: aligned   │  │                 │
└──────────────────┘  └──────────────────┘  └─────────────────┘

┌─ Cross-Asset ──────────────┐  ┌─ Event-Causal ────────────┐
│  ● NOT YET RUN              │  │  ● NOT YET RUN             │
│  "Run a tournament with     │  │  "Run event classification │
│   cross-asset features"     │  │   pipeline to populate"    │
└─────────────────────────────┘  └────────────────────────────┘
```

### Changes from current

- **Verdict sentence per layer card** — "No strong directional pressure" instead of just numbers
- **"NOT YET RUN"** with actionable instruction instead of just "No data"
- **Convergence bar** is visual (colored fill bar) not just text
- Layer cards keep colored top borders (blue/purple/green/orange/red)
- **Signal direction uses CSS pills** not plain text: green "BULLISH", red "BEARISH", gray "NEUTRAL"
- Each metric label gets `title` attribute tooltip (hover for "RSI measures overbought/oversold momentum on a 0-100 scale")

## Tab 4: My Positions

### Layout (mostly unchanged — cleanest tab)

```
┌─ Summary metrics ─────────────────────────────────────┐
│  4 Positions   $20,650 Invested   $5,162 Avg Position │
└───────────────────────────────────────────────────────┘

Holdings table (keep current dataframe)

Sell Signals
"Checks three conditions: stop-loss breach (-8%),
 negative sentiment spike, and technical breakdown"
  [Check Holdings]  (keep current button + progress)
  Result: "All Clear — No sell signals detected" (green card)

Add Holding form (keep current)
```

### Changes from current
- Inline context sentence replaces expander
- Term tooltips on "stop-loss", "sentiment spike", "technical breakdown"
- Otherwise this tab is good — minimal changes

## Tab 5: Opportunities

### Layout

```
[Run Tournament]  button at top right

┌─ Top 5 as full cards ──────────────────────────────────┐

┌─ #1 ──────────────────────────────────────────────────┐
│  NVDA                                      STRONG BUY  │
│  "Highest conviction — 3/3 layers bullish"             │
│                                                         │
│  5d: +3.20%   Confidence ████████████░░ 85%           │
│  Earnings catalyst + upstream leader signal             │
│  + AI demand surge                                      │
│                                                         │
│  Technical ● bullish  Sentiment ● bullish              │
│  Cross-Asset ● bullish                                  │
│  Sources: yfinance, rss, stocktwits, google trends     │
└────────────────────────────────────────────────────────┘

┌─ #2 ──────────────────────────────────────────────────┐
│  AMD                                              BUY  │
│  "Strong momentum — semiconductor supply chain"        │
│  5d: +2.80%   Confidence ██████████░░░░ 72%          │
│  ...                                                    │
└────────────────────────────────────────────────────────┘

(#3, #4, #5 as cards)

└────────────────────────────────────────────────────────┘

┌─ Picks #6-15 compact table ──────┐  ┌─ Grade Donut ──┐
│  Rank | Symbol | Grade | Score   │  │  (keep current) │
│  ...colored grade badges...      │  │                  │
└──────────────────────────────────┘  └──────────────────┘

Watchlist section (keep current table + add form)
```

### Changes from current

- **Top 5 are full cards** with verdict sentence, confidence bar, layer dots, sources — no expanders
- **Picks #6-15** stay as compact table with colored grade badges in Grade column
- **"Run Tournament" button** at top to refresh picks
- **Sources line** on each card shows which data sources backed the recommendation
- **Verdict sentence** per card: generated from grade + layer agreement + reasoning
- Grade donut stays on right side (working correctly now)
- Watchlist section unchanged

## Tab 6: Market Pulse

### Layout

```
┌─ MARKET CONTEXT ────────────────────────────────────────┐
│  "Market conditions as of your last scan"                │
│                                                           │
│  Data Sources Active:                                    │
│  RSS ● connected (15 feeds)                              │
│  Google Trends ● connected (350 tickers)                 │
│  StockTwits ● connected                                  │
│  GDELT ● not configured                                  │
│  Fundamental ● via yfinance (real-time)                  │
│  Cross-Asset ● correlation matrix (daily)                │
│  Event-Causal ● Gemini classifier (10 categories)       │
└─────────────────────────────────────────────────────────┘

SUPPLY CHAIN CASCADES
"When leaders move >3%, followers often follow within 1-3 days"

┌─ Semiconductors ────────────────────────────────────────┐
│  Leaders: AMAT  LRCX  KLAC  ASML                       │
│  →  Followers: MU  WDC  INTC  AMD  NVDA                │
│  Typical lag: 2 days                                     │
│  "Equipment makers lead chip producers"                  │
└─────────────────────────────────────────────────────────┘

┌─ Big Tech Ecosystem ────────────────────────────────────┐
│  Leaders: AAPL  MSFT  GOOG  AMZN  META                 │
│  →  Followers: TSM  AVGO  QCOM  TXN  ADI               │
│  Typical lag: 1 day                                      │
│  "Big tech demand drives semiconductor suppliers"        │
└─────────────────────────────────────────────────────────┘

(all groups expanded by default — no expanders)

EVENT IMPACT MODEL
"How quickly news events lose market impact"
  Plain English: "A 5% earnings surprise loses half
  its effect in 5 days"
  Interactive sliders (keep current) + decay curve

DATA PIPELINE STATUS
"What your system knows and when it last checked"
  Table: Source | Status | Last Run | Items Processed
```

### Changes from current

- **Data sources panel** at top — transparency about what's plugged in
- **All supply chain groups expanded by default** — no expander clicks
- **Pipeline status table** at bottom — shows what system knows
- **Event decay keeps sliders** but adds plain English interpretation sentence
- Remove `st.expander("Learn more")` everywhere

## CSS Changes Summary

### New in `styles.py`

```
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
```

- Inter font applied to all elements
- Tab underline active: `#2563EB`
- Card hover: `translateY(-2px)` + shadow deepen
- Table row hover: `#F8FAFC` background
- Button primary: `#2563EB` bg, `border-radius: 8px`, hover darken
- Button secondary: white bg, blue border
- Card padding: `1.5rem`
- Section margin: `2rem`
- Hero card: larger padding `2rem`, subtle blue-left border
- Footer watermark: fixed bottom, `#D1D5DB`, 12px
- Urgency pills: CSS only (red/amber/gray backgrounds), no emoji
- Freshness dots: CSS `::before` colored circles, no emoji
- SHAP legend: CSS colored spans, no emoji
- Form inputs: `border-radius: 8px`, focus ring `#2563EB`
- Colored grade badges in dataframe via `st.dataframe` column config or HTML table

### Emoji Policy

- **Keep:** Tab labels only (🎯📊🔍💼🚀🌍)
- **Remove:** ALL content emoji — urgency badges, freshness indicators, SHAP legend, direction icons
- **Replace with:** CSS-colored pills, dots, and badges

## New Files

| File | Purpose |
|------|---------|
| `adapters/visualization/action_runner.py` | Add `run_full_cycle()`, `run_tournament()`, `run_backtest()` |
| `adapters/visualization/components/styles.py` | Major rewrite — Inter font, hover effects, new CSS classes |
| `adapters/visualization/components/verdicts.py` (new) | Plain English verdict generators per tab |

## Modified Files

| File | Changes |
|------|---------|
| `adapters/visualization/tabs/command_center.py` | Hero banner, priority-bucketed actions, Run Full Cycle button, freshness row |
| `adapters/visualization/tabs/model_confidence.py` | Verdict card, Run Backtest button, CSS SHAP legend, inline context |
| `adapters/visualization/tabs/signal_breakdown.py` | Layer verdict sentences, NOT YET RUN states, convergence bar |
| `adapters/visualization/tabs/positions.py` | Inline context sentences, term tooltips (minimal changes) |
| `adapters/visualization/tabs/opportunities.py` | Top 5 cards, Run Tournament button, sources line, compact table #6-15 |
| `adapters/visualization/tabs/market_pulse.py` | Data sources panel, expanded groups, pipeline status |
| `adapters/visualization/components/formatters.py` | Remove emoji from urgency/freshness/direction, add verdict helpers |
| `adapters/visualization/components/metrics.py` | Hero banner component, verdict card component |
| `adapters/visualization/dashboard.py` | Footer watermark |
| `tests/test_formatters.py` | Update for emoji removal, new verdict functions |
| `tests/test_action_runner.py` | Tests for run_full_cycle, run_tournament, run_backtest |
| `tests/test_verdicts.py` (new) | Tests for verdict generators |
| `tests/test_dashboard_smoke.py` | Update for new imports |

## What This Does NOT Include

- Dark mode
- Sidebar navigation
- Real-time websocket price updates
- GDELT adapter (not wired — separate phase)
- Model retraining from dashboard (pretrain stays CLI-only — too long-running)
- Mobile responsive layout

## Success Criteria

1. An investor with no ML background can open the dashboard, read the verdicts, and understand what the system recommends and why
2. One click ("Run Full Cycle") refreshes all data — no terminal needed for daily use
3. Zero emoji in content areas — professional, designed feel
4. Every section has an inline explanation — no hidden "Learn more" expanders
5. Hover effects, Inter font, consistent spacing — feels like a designed product, not a Streamlit prototype
6. Top 5 picks are full visual cards with verdicts — no clicking to reveal content
7. Sources (RSS, Google Trends, StockTwits) visible on each recommendation card
