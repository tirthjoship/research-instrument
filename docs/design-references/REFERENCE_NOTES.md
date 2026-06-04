# Design Reference Notes — SimplyWallSt + Market Cap Visualizations

Extracted from 28+ screenshots provided 2026-06-04. Screenshots were temporary — these notes capture the patterns.

## Source 1: Semiconductor Market Cap Bubble Chart
- Treemap/circle-pack showing companies by market cap
- NVDA $4.4T dominant center, TSMC $1.5T, Broadcom $1.8T, Samsung $449.7B, AMD $350.1B
- Color-coded by country/region
- **Our equivalent:** Supply chain cluster visualization — bubble chart sized by market cap, colored by cluster membership

## Source 2: NVIDIA Income Statement Sankey (App Economy Insights)
- Revenue waterfall: $57.0B → segments → gross profit → operating profit → net profit
- Segment breakdown: Data Center $51.2B, Gaming $4.3B, Pro Viz $0.8B, Auto $0.6B
- Green = revenue/profit, Red = costs
- **Our equivalent:** Not feasible with yfinance data (no segment breakdown). Skip.

## Source 3: Gross Profit Margin Timeline (Motley Fool / YCharts)
- Simple line chart, 2016-2024, quarterly gross margin %
- Current value highlighted: 78.35%
- **Our equivalent:** yfinance provides `grossMargins` (current). Historical quarterly needs `yf.Ticker.quarterly_financials`. Doable.

## SimplyWallSt Pattern Analysis (Sources 4-28)

### The "Snowflake" Radar Chart
- 5-axis radar: Value, Future, Past, Health, Dividend
- Each axis scored visually (filled area = score)
- Summary sentence beneath: "Exceptional growth potential with flawless balance sheet"
- **Our equivalent:** 5-axis radar using our 5 signal layers: Technical, Sentiment, Fundamental, Cross-Asset, Event-Causal
- OR 6-axis: add Smart Money as 6th dimension (matches conviction sub-scores)

### Section Structure (EVERY section follows this)
1. **Number + Title** (e.g., "1. Valuation")
2. **Criteria checklist** — "Valuation Score 3/6" with green/red circles
3. **Plain English summary** — one paragraph explaining the finding
4. **Key Information card** — 2-column: metrics left, recent updates right
5. **Chart** — specific to the metric being discussed
6. **Verdict bullets** — green check / red X + explanation sentence

### Chart Types Used
| Chart | SWST Section | Our yfinance Data Availability |
|-------|-------------|-------------------------------|
| Price vs Fair Value bar | Valuation 1.1 | Need DCF model — SKIP for now |
| P/E vs Peers horizontal bar | Valuation 1.3 | YES — get_ticker_info() for peers in same sector |
| Historical P/E line | Valuation 1.4 | PARTIAL — need quarterly_financials history |
| P/E vs Industry histogram | Valuation 1.5 | YES — batch fetch sector peer P/E |
| P/E gauge (current vs fair) | Valuation 1.6 | PARTIAL — need fair PE estimate |
| Analyst price target with forecast cone | Valuation 1.7 | YES — get_analyst_data() has target_mean/high/low |
| Earnings + Revenue forecast line | Growth 2.1 | PARTIAL — earningsGrowth + revenueGrowth available |
| Company vs Industry vs Market bars | Growth 2.2 | YES — compare earningsGrowth across sectors |
| EPS forecast with analyst range | Growth 2.3 | PARTIAL — need analyst EPS estimates |
| ROE gauge | Past Performance 3.5 | YES — returnOnEquity available |
| Revenue + Earnings history line | Past 3.2 | YES via quarterly_financials |
| FCF vs Earnings waterfall | Past 3.3 | YES — freeCashflow + netIncome |
| ROA / ROCE gauges | Past 3.6-3.7 | PARTIAL — ROA calculable, ROCE needs extra data |
| Balance sheet treemap | Financial Health 4.3 | PARTIAL — need balance sheet items |
| Debt/Equity history line | Financial Health 4.2 | PARTIAL — debtToEquity is current only |
| Dividend yield vs market bar | Dividend 5.2 | YES — dividendYield available |
| Dividend payment history line | Dividend 5.1 | PARTIAL — need dividend history |
| CEO compensation line | Management 6.1 | NO — not in yfinance |
| Insider trading volume bars | Ownership 7.1 | PARTIAL — SEC EDGAR Form 4 data available |
| Ownership breakdown stacked bar | Ownership 7.2 | YES — heldPercentInstitutions + heldPercentInsiders |

### What We CAN Build (Available Data)
1. **5-Layer Radar** (our unique differentiator — SWST has snowflake, we have signal radar)
2. **P/E vs Sector Peers** horizontal bar (yfinance peer data)
3. **Analyst Price Target** with high/low range
4. **Company vs Industry vs Market** growth comparison bars
5. **ROE / ROA gauges** (returnOnEquity, ROA calculable)
6. **Ownership breakdown** (institutional vs insider vs public)
7. **Insider trading** (SEC EDGAR Form 4, already have adapter)
8. **Fundamental metrics table** (all 16+ yfinance fields)
9. **Price history + volume** candlestick (yfinance OHLCV)
10. **RSI + MACD overlay** (already computed in feature_engineer)
11. **Sentiment timeline** (buzz_signals over time)
12. **Supply chain bubble** (market cap sized, cluster colored)
13. **Conviction radar** (6 sub-score dimensions as radar)

### What We CANNOT Build (Missing Data)
1. DCF fair value — need financial modeling, not in scope
2. Revenue segment breakdown — yfinance doesn't provide this
3. CEO compensation history — not in yfinance
4. Quarterly financial history charts — possible but requires extra yfinance calls
5. Analyst EPS range forecasts — not in standard yfinance

### Loading State Pattern (Google-style)
Progressive messages while data loads:
- "Scanning market data..."
- "Analyzing fundamentals..."
- "Checking sentiment signals..."
- "Computing conviction score..."
- "Preparing charts..."
- "Almost ready..."

Use Streamlit progress bar + status text (already have `components/progress.py` pattern).
