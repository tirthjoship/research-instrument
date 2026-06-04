# Phase 5.3: Dashboard Redesign — Design Spec

> **Date:** 2026-06-03
> **Scope:** Complete dashboard UX overhaul — WealthSimple-inspired, friendly, informative
> **Purpose:** Transform prototype dashboard into a personal investment tool that's intuitive, self-explanatory, and feels like a website not a data dump.

---

## 1. Design Principles

- **Light theme, friendly voice** — WealthSimple tone, not Bloomberg density
- **Progressive disclosure** — summary first, details on demand
- **Conversational verdicts** — every section opens with a sentence telling you what to think
- **Compact, scannable** — above the fold = what matters. Everything else expandable.
- **Self-explanatory** — new user understands without a tutorial
- **EST timestamps** — all times displayed in Eastern Standard Time
- **No emoji in UI** — clean text, CSS-styled indicators only

---

## 2. Tab Structure (5 tabs, 3 modes)

| # | Tab | Mode | Purpose |
|---|-----|------|---------|
| 1 | **Today's Opportunities** | Act | Top 15 conviction cards, 3-panel hero, auto-scan |
| 2 | **Watchlist** | Act | Pinned tickers, historical recommendations |
| 3 | **My Portfolio** | Track | Trade recording (add/remove), P&L, outcomes, signal report |
| 4 | **How It Works** | Understand | Collapsible: signal performance, system learning, backtest |
| 5 | **Market Context** | Understand | Data pipeline, supply chains, event decay |

**Killed:** Old "Opportunities" tournament tab. Signal Breakdown merged into opportunity card expand.

---

## 3. Global Header

Replaces current plain text header. Part of every tab.

```
Multi-Modal Stock Recommender
─────────────────────────────────────────
```

No market info in header — that moves to the hero section on Tab 1. Header is just the app title, clean and minimal.

---

## 4. Tab 1: Today's Opportunities

### 4.1 Auto-Scan with Smart Cache

- On first load: auto-run conviction scan. Show loading skeleton.
- Cache results in st.session_state with timestamp.
- Cache duration: 15 min during market hours (9:30-16:00 ET), 60 min after hours.
- "Scan Now" button for manual refresh. Shows "Last scanned: X min ago" next to it.
- "Run Full Cycle" button (secondary) runs scan + tournament + track.

### 4.2 Onboarding (first-run only)

If no scan results AND no trades AND no watchlist:

```
Welcome to your Investment Intelligence System

Get started in 3 steps:

1. [Scan for Opportunities]  — finds what's moving
   System scans 350+ tickers for smart money activity

2. [Add to Watchlist]  — track what interests you
   Pin tickers you want to monitor daily

3. [Record a Trade]  — start the learning loop
   Log your first buy so the system can learn
   which signals work for YOUR investment style

The system gets smarter with every trade you track.
```

Disappears once data exists.

### 4.3 Three-Panel Hero

Three cards in a row, always visible (after onboarding):

**Panel 1 — Market Status:**
- S&P 500 price + daily change (green/red)
- "Market: OPEN" / "Market: CLOSED"
- Current time in EST
- One-line mood: "Bull day — most sectors green" or "Mixed signals today"

**Panel 2 — Your Portfolio:**
- Total invested value
- Total P&L (dollar + percent, green/red)
- Number of positions
- Best/worst performer today
- [Add Position] [Remove Position] inline buttons

**Panel 3 — Today's Signal:**
- Count of new opportunities since last scan
- Highest conviction ticker + score
- Watchlist alerts (any pinned ticker with new signals)
- One-line summary: "Smart money moving on AMD — conviction 7.2"

### 4.4 Opportunity Cards (compact)

Below hero. Ranked by conviction descending.

**Compact card (default):**
```
NVDA  NVIDIA Corporation         ████████░░ 8.2/10  ▲ BUY  ● Fresh
Why: Activist 13D filed + 3 insider buys + GDELT tone shift
⚠ 13D could be passive · Market risk
                        [See Signals ▾]  [Track Trade →]
```

**Expanded card (on click "See Signals"):**
Shows 5-layer mini-cards inline (Technical, Sentiment, Fundamental, Cross-Asset, Event-Causal) — same content as old Signal Breakdown tab but embedded per-ticker.

**Card styling:**
- Left border: green (conviction 7+), amber (4-6), red (<4)
- Subtle background tint matching border color at 5% opacity
- Conviction shown as both number AND fill bar
- "Track Trade" button links to My Portfolio tab with ticker pre-filled
- Freshness dot: green (<4hr), amber (4-24hr), red (>24hr)

### 4.5 Bottom Section

- "Scan Now" button + "Last scanned 12 min ago (EST)"
- "Showing top 15 of 350+ tickers scanned"

---

## 5. Tab 2: Watchlist

### 5.1 Purpose
Tickers you're monitoring but haven't acted on. Historical view of what the system recommended.

### 5.2 Layout

**Add to Watchlist form** — ticker input + notes + [Add] button. Inline, compact.

**Watchlist table** — ticker, date added, notes, current conviction score (live from last scan), action column with [Remove] button.

**Historical Recommendations** — "What did the system say last week?"
- List of past opportunity cards grouped by scan date
- Shows: ticker, conviction at time, action suggested, what actually happened (price change since)
- Helps user see "should I have listened?"

### 5.3 Empty State
"Your watchlist is empty. Pin tickers from Today's Opportunities to track them here."

---

## 6. Tab 3: My Portfolio

### 6.1 Purpose
Record trades, see P&L, understand which signals led to good outcomes.

### 6.2 Layout

**Portfolio Summary (hero row):**
- Total positions | Total invested | Total P&L | Win Rate
- Only shows metrics that have data (no "—" dashes)

**Trade Recording Form:**
- Action: Buy / Sell toggle
- Ticker: text input (with autocomplete from watchlist/known tickers)
- Price: number input
- Quantity: number input
- Date: date picker (YYYY-MM-DD format)
- [Record Trade] button
- On sell: shows computed outcome inline ("NVDA: +11.3% return, 35 days held")

**Closed Positions Table** (if outcomes exist):
- Ticker, buy price, sell price, return %, return $, holding days, signals at entry
- Rows colored: green for profitable, red for loss
- Sortable by return %

**Open Positions** (buys without matching sell):
- Ticker, buy price, quantity, date, conviction at entry
- [Record Sell] button per row

**Signal Report Card** (if 5+ outcomes):
- "Your best signal: insider_buying (72% hit rate)"
- "Your worst signal: ml_direction (48%)"
- "Recommendation: increase smart_money weight, reduce ml_direction"

### 6.3 Empty State
"No trades recorded yet. When you spot an opportunity, click 'Track Trade' on the card to log it here. The system learns from every trade you make."

---

## 7. Tab 4: How It Works

### 7.1 Purpose
Transparency — show the user HOW the system makes decisions and how it's learning.

### 7.2 Layout

**Learning Progress Bar (always visible):**
```
Your system is learning from N completed trades.
████████░░░░░░░░░░░░ N/50 trades toward reliable intelligence
```

Milestones: 10 (first insights), 50 (reliable patterns), 200 (mature intelligence).

**3 collapsible sections (all collapsed by default):**

**▸ Signal Performance**
- Per-signal hit rate table (when data exists)
- "Which signals make you money?"
- Recommendation text from generate_report_card()

**▸ System Learning**
- Weight history table (dimension, old → new, reason, date)
- Learned rules list with confidence badges
- "Run Learning Cycle" button
- "Weights adjust automatically as you track more trades"

**▸ Model Baseline**
- Walk-forward accuracy chart
- Ablation study chart
- SHAP feature importance
- p-value pills
- Known limitations
- "This is the honest baseline — the system uses conviction scoring (not this model) for recommendations"

### 7.3 Empty State
"Track 10 trades to unlock your first signal performance insights. The more you trade, the smarter the system gets."

---

## 8. Tab 5: Market Context

### 8.1 Purpose
Background intelligence — macro context, data sources, supply chain relationships.

### 8.2 Layout (mostly keep current, polish)

**Data Pipeline Status Grid** (replace bullet list):
- 2x4 grid of cards, each showing: source name, status (green/amber/red dot), description, last updated
- Sources: RSS, Google Trends, StockTwits, GDELT, Fundamental, Cross-Asset, Event-Causal, SEC EDGAR (new)

**Supply Chain Cascades** (keep current, polish cards):
- Consistent card borders
- Leader/Follower pill styling matches opportunity card pills

**Event Impact Decay** (keep current):
- Interactive sliders
- Decay chart

### 8.3 Empty State
"Data sources are configured and ready. Run a scan to see live status."

---

## 9. CSS Theme — WealthSimple-Inspired Light

### Color Palette
```css
--bg-primary: #FFFFFF;
--bg-secondary: #F8FAFC;
--bg-card: #FFFFFF;
--border: #E2E8F0;
--text-primary: #1A202C;
--text-secondary: #64748B;
--text-muted: #94A3B8;
--accent: #2563EB;
--success: #16A34A;
--warning: #D97706;
--danger: #DC2626;
--conviction-high: #16A34A;
--conviction-mid: #D97706;
--conviction-low: #DC2626;
```

### Typography
```css
--font-display: 'DM Sans', sans-serif;  /* headings — distinctive, not Inter */
--font-body: 'Inter', sans-serif;       /* body — already loaded */
--font-mono: 'JetBrains Mono', monospace; /* numbers, code */
```

### Card Styling
```css
.card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 16px;           /* rounder than current 12px */
    padding: 1.25rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    transition: all 0.2s ease;
}
.card:hover {
    box-shadow: 0 4px 16px rgba(0,0,0,0.08);
    transform: translateY(-1px);
}
```

### Conviction Bar
```css
.conviction-bar {
    height: 8px;
    border-radius: 4px;
    background: var(--border);
}
.conviction-bar-fill {
    height: 100%;
    border-radius: 4px;
    transition: width 0.5s ease;
}
```

---

## 10. Streamlit-Specific Implementation Notes

- Use `st.html()` for custom components (cards, hero panels)
- Use `st.columns()` for grid layouts (3-panel hero = 3 equal columns)
- Use `st.expander()` for collapsible sections in How It Works
- Cache scan results in `st.session_state["scan_cache"]` with timestamp
- Check cache age: `datetime.now(ET) - cache_timestamp > timedelta(minutes=15)`
- EST conversion: `from zoneinfo import ZoneInfo; ET = ZoneInfo("America/New_York")`
- Auto-scan: check cache on render, if stale → scan automatically
- Loading skeleton: `st.markdown('<div class="skeleton">...</div>')` with CSS animation
- Tab labels: plain text, no emoji — `st.tabs(["Today's Opportunities", "Watchlist", ...])`

---

## 11. Success Criteria

| Metric | Target |
|--------|--------|
| Tabs | 5 (down from 6) |
| First-load experience | Onboarding card OR auto-scan with skeleton |
| Time to first insight | < 30 seconds (auto-scan) |
| Opportunity cards | Compact by default, expandable for signal detail |
| Empty states | Every section has helpful guidance, not "no data" |
| Signal Breakdown | Merged into opportunity card expand, not separate tab |
| Tournament display | Removed entirely |
| All timestamps | EST |
| Portfolio CRUD | Add/remove inline on hero + My Portfolio tab |
| Visual identity | Consistent light theme, DM Sans headings, rounded cards |
