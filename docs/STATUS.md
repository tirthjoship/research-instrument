# STATUS — multi-modal-stock-recommender

**As of:** 2026-06-15 (evening)
**Branch:** `feat/dashboard-legibility-redesign` (many commits, UNCOMMITTED prior-session work also present; NOT merged).
**Phase:** **Screener (Research Candidates) tab redesign — UI shipped & iterated against the mockup; Gemini live; a few polish items + decisions open.**

## How to run / verify
- App: `streamlit run adapters/visualization/dashboard.py --server.port 8560 --server.headless true` → http://localhost:8560 → **Screener** tab (2nd tab; renders lazily — blank for a beat then fills).
- Tests: `python -m pytest tests/ -q` → **2006 passing**. mypy strict clean (pre-commit gate). `git checkout data/reports/` before any verify (tests strip trailing newlines from 2 tracked JSONs — currently dirty, ignore).
- Canonical mockup (drift reference): `.superpowers/brainstorm/screener-FINAL-v2.html` (serve via `python3 -m http.server 8570 --directory .superpowers/brainstorm` → open `/screener-FINAL-v2.html`).
- **Non-default Streamlit tabs screenshot BLANK** via `scripts/screenshot_dashboard.py` (lazy tabs + JS click) — NOT a bug; verify a tab by rendering it solo (see memory `reference-streamlit-screenshot-lazy-tabs`).

## ALSO on this branch — Home + Decision-Card redesign (parallel session, COMPLETE, see ADR-057)
The branch carries a SECOND redesign built in a parallel session: the **Home "Front Desk" + v9 decision card**
(Stock Analysis tab). Complete + Opus-verified per phase. See `docs/adr/ADR-057-home-decision-card-redesign.md`
+ spec/plans `docs/superpowers/{specs,plans}/2026-06-14-home-decision-card-redesign*` / `...-S1..S6`.
Highlights: 5 fundamental RAG dims (`domain/evidence_rag.py`), v9 card (`components/decision_card.py`,
collapsed↔expanded, 5/5 cited Google-AI case), Front-Desk Home (net-beta bug fixed, vs-Market 1y, book-health),
Gemini cited-case + `RateLimitedCaseSummarizer` (5s buffer) + weekly cache, fail-safe `is_local_runtime()`
privacy guard, money 2dp, 1y return window, multi-factor verdict rubric surfaced. **Open (Home):** verdict-logic
extension decision (evidence-only vs fold-in fundamentals — memory `project-verdict-logic-extension-question`);
wire `compute_vs_market_1y` into the brief; per-holding news for Home cited cases.

## DONE this session (Screener — other parallel session, all committed on the branch)
- **Spec + 7 plans:** `docs/superpowers/{specs,plans}/2026-06-14-screener-*`.
- **Domain:** `factor_bands.py` (band/percentile→band/plain_read), `screen_buckets.py` (6 buckets, top-5, repeats), `trend_rules.trailing_volatility` (daily/log/annualized).
- **S1 scoring landed:** `FACTOR_KEYS`→5 (added **lowvol**, inverted daily-vol, z-scored); composite denom = present-factor count; `revision_momentum` honestly = analyst-target dispersion (docstring + glossary; key still "revision", UI label "Analyst spread"); lowvol added to IC panel (code). **Live 5-factor screen regenerated:** `data/reports/screen_2026-06-15.json` (304 cands, all 5 factors 100% coverage). IC backtest NOT re-run (Trust tile still honest INCONCLUSIVE).
- **UI (`adapters/visualization/tabs/research_candidates.py`):** 4 tiles + mono ledger (dynamic factor count=5) · how-to-read legend (Grade line, ~top5%, 304 cohort) · honest disclosure · **view toggle in header top-right** (`st.segmented_control`) · 6 reason buckets + honest-empty + hero #1 open/elevated · collapsible 5-factor cards (Quality·Value·Analyst spread·Low-vol·Momentum, momentum last) · filled STRONG/MOD/WEAK grade pills · plain row summary ("Quality, value & analyst signal strong; momentum flat") · company name + "also in 💎📈 · repeat = strength" · momentum **sparkline** · **grey-circle ⓘ** tooltips (factor_row + tiles + bucket headers) · `content-visibility:auto` for faster paint.
- **Zone ② "check your own list":** full 5-factor card parity; in-universe names reuse the screen, **off-universe live-computed** (`application/ticker_factors_use_case.py`, `batch_fit(live_fetch=True)`); wrapped in **`st.fragment`** (Run-the-check reruns ONLY that section + progress bar); CSV uploader cleaned up.
- **Gemini WORKS:** added `.env` loader (`dashboard.py`), installed `google-generativeai` (in pyproject `dashboard` extra), model `gemini-flash-latest` (2.0-flash was 429 quota-exhausted). Verified live: returns attributed ▲/▼ cited points. Currently surfaces on the **Stock Analysis tab (v9 card)**; the screener cards show a **pointer** to it (not inline).

## Next Action (open items + decisions for the fresh session)
1. **Inline Gemini on the screener hero card** — wire `maybe_render_gemini(ticker, facts, news)` into the hero's `gai` slot (real ▲green/▼red read), hero-only + cached per ticker (minimal quota). Needs a per-ticker news fetch (find the news adapter; facts can come from the bands). User wants this.
2. **Gemini quota resilience** — model-fallback chain (flash-latest → alt model on 429) + optional 2nd key (`GEMINI_API_KEY_2`) the adapter rotates to. User asked.
3. **Loading on tab-switch** — render() is 5ms; blank = Streamlit atomic tab-frame latency + 187KB paint (mitigated by content-visibility). A true in-page skeleton needs a session-state deferred-render (flashes once/first entry) — offered, user to decide. Streamlit's top-right "running" indicator is the native signal.
4. **IC gate re-run** (`backtest-screen`) incl. lowvol → updates Trust tile honestly. Needs the methodology gate (ds-methodology-review already done the design pass).

## Caveats
- **Honesty invariants hold:** no FORBIDDEN_WORDS (note "predictive" contains "predict" — avoid), DATA-GAP never faked, "not a forecast" present, Gemini never feeds the score (attributed companion only).
- `screen_2026-06-15.json` is **gitignored** (generated) — lives on disk; the app reads it. Regenerate via `python -m application.cli screen-candidates --top 15` (live yfinance, a few min).
- `st.fragment` decorator needs `# type: ignore[misc]` for the pre-commit mypy gate (standalone `mypy --strict` flag flip-flops — keep the ignore).
