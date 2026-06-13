# External-AI Feedback Prompt — multi-modal-stock-recommender

**Purpose:** Paste the block below into **both** Gemini and ChatGPT, attach the 6 dashboard
screenshots (Home, Screener, Risk, My Portfolio, Stock Analysis, Trust), and compare answers.
Built 2026-06-12. Strict honesty-guardrail variant. Screenshots = your 22:34–22:38 set from
the live `127.0.0.1:8531` v2 build.

---

## PASTE EVERYTHING BELOW THIS LINE

You are a senior product designer **and** a quant-savvy ML engineer reviewing a data-science
portfolio project. I want sharp, specific, non-generic feedback. I have attached **6 screenshots**
— the six tabs of the project's dashboard (Home, Screener, Risk, My Portfolio, Stock Analysis,
Trust). Study them carefully; reference specific tabs in your critique.

### What the project is

A **multi-modal stock research engine** (Python 3.12, hexagonal / ports-&-adapters architecture,
Streamlit + Plotly front end, XGBoost/LightGBM/Ridge ensemble, SQLite, yfinance + GDELT +
Google Trends + Wikipedia attention data, Flan-T5 / Gemini for NLP). ~1,600 passing tests,
mypy-strict, 55+ architecture decision records. It is a learning/portfolio project for a data
scientist, **not** a trading product.

### The intellectual spine (this is the whole point — read carefully)

This project's defining feature is **intellectual honesty about what does and doesn't work.**
It has a *graveyard of falsified hypotheses*, documented openly:

- The original thesis — "sentiment–price divergence predicts 5-day returns" — was **pre-registered,
  tested on a clean 2006–2024 universe, and FALSIFIED** (cross-sectional rank-IC ≈ 0.004, CI spans
  zero = noise). The signal was **killed**, not buried.
- Directional accuracy on mega-caps sits at **~50%**, exactly as the Efficient Market Hypothesis
  predicts. The project says this out loud.
- It then **pivoted from prediction to process** (the "Process > Prediction" principle): the honest,
  achievable edge for a retail investor is *better process* — risk management, closing the
  behavior gap (selling winners early / holding losers), trend-following exits, factor premia —
  **not** better forecasting.
- The engine **abstains** when nothing clears a pre-registered evidence bar. The Screener literally
  says "512 names — none cleared the bar this week. That is the discipline working, not failing."

The **Trust tab** showcases all of this: "We tried seven ways to predict the market. None survived
testing," plus ablation and SHAP exhibits labeled FALSIFIED. This honesty is the project's rarest,
most valuable competency.

### The problem I want help with

The project is **substance-rich but presentation-flat.** The dashboard looks like a generic
Streamlit app: off-white background, default Plotly charts, walls of small gray text, low contrast,
no visual hierarchy or brand. Worse, its greatest strength (honesty → abstention → ~50% accuracy →
empty screens) makes the UI *feel empty and anticlimactic*, even though that emptiness is the rigor.

I want feedback on **four axes**:
1. **Visual / design polish** — make it look like a distinctive, production-grade product, not a
   default Streamlit demo.
2. **New features** — concrete capabilities worth adding.
3. **New technologies** — modern tools/libraries/techniques worth onboarding.
4. **Legibility of depth + employer impact** — make the existing rigor (falsification, abstention,
   process-over-prediction) *immediately legible and impressive* to a data-science hiring manager,
   without faking anything.

### HARD CONSTRAINTS — these are non-negotiable filters

Any suggestion that violates these is **wrong** for this project and must be discarded:

- **RESEARCH_ONLY.** No buy/sell/trade recommendations. No "signals" presented as actionable calls.
  The UI must never imply "the system says buy X."
- **No manufactured confidence or prediction.** Do not suggest re-adding return forecasts, price
  targets, "AI confidence scores," win-probability dials, or a stock-picking chatbot. Those were
  *already tried and falsified*; re-adding them would re-break the project's hardest-won lesson.
- **Abstention is a feature, not a bug.** Do not suggest hiding empty states or always showing picks
  to "look fuller." Suggest making honest abstention *legible and compelling* instead.
- **Show before ship; consolidation ≠ redesign.** A prior redesign attempt deleted/merged working
  components, called it "progress," and shipped zero visible change — it was rolled back. Prefer
  **additive** changes or genuine visual transformation. If you propose removing something, say
  exactly what replaces it and why the result is visibly better.
- **No fabricated data or results.** Every number on screen must trace to a real computation.

### Required output format

First, **silently discard** any idea that fails the HARD CONSTRAINTS — do not list rejected ideas.
Then organize what survives into these sections:

1. **Art direction (1 cohesive visual direction, not piecemeal tweaks).** Describe a specific look:
   palette, typography, spacing, chart restyling, light/dark, the *one* signature visual element.
   Reference the attached tabs.
2. **Legibility wins** — how to make the falsification/abstention/process-over-prediction depth
   *pop* for a first-time viewer in the first 10 seconds.
3. **Feature additions (honesty-safe).**
4. **Technology / technique upgrades** (libraries, viz, infra, ML — honesty-safe).
5. **Employer-impact framing** — what would make a hiring manager think "this person is rigorous."
6. **Top 5 do-first**, ranked.

For **every** recommendation, tag it inline:
- **Axis:** Visual / Feature / Tech / Legibility / Employer
- **Replaces or Adds:** (if replaces, name what — and why the result is *visibly* better, not just
  "cleaner")
- **Honesty check:** PASS + one line confirming it manufactures no signal/confidence/prediction
- **Effort:** S / M / L
- **Why it's not generic:** one line distinguishing it from default "add a chatbot / add predictions"
  advice
- **Portfolio signal:** what competency it demonstrates to a data-science interviewer

Be concrete and specific to *this* project. Generic dashboard advice ("use cards," "add filters")
is not useful. Critique the actual screenshots. If you think the honesty constraints are
*themselves* the thing limiting visual impact, say so directly and propose how to resolve the
tension without abandoning honesty.

## PASTE EVERYTHING ABOVE THIS LINE
