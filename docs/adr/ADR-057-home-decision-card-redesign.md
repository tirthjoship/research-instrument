# ADR-057 — Home + Decision-Card Redesign (Research Instrument, v9 card)

**Status:** Accepted · Implemented (branch `feat/dashboard-legibility-redesign`, 2026-06-14) · not yet merged
**Supersedes/extends:** ADR-035 (dashboard redesign), ADR-055/056 (Research Instrument). Pairs with the
spec `docs/superpowers/specs/2026-06-14-home-decision-card-redesign-spec.md` and plans
`docs/superpowers/plans/2026-06-14-S1..S6`.

## Context

North-star: the non-expert user who did not trade (0 trades) because he could not tell **what to trust**.
The flat dashboard surfaced numbers without a legible decision path, and the Home tab had grown to ~9 stacked
sections (much duplicated across other tabs) plus a raw weekly-brief markdown dump. We needed a triage-first
Home and a per-stock **decision card** that presents **attributed evidence, never a prediction**.

The decision-card design was recovered from prior brainstorm mockups (`per-stock-v9.html`, `home-FINAL.html`)
and locked via a grill + brainstorm + frontend-design pass. Canonical mockups live in
`.superpowers/brainstorm/97077-1781379305/content/`.

## Decision

**Six independently-shippable subsystems** (built S1→S3→S4→S2→S5→S6 via subagent-driven development with an
Opus verification-before-completion pass per phase):

1. **S1 — Evidence layer** (`domain/evidence_rag.py`, `adapters/data/earnings_history_adapter.py`,
   `application/evidence_card.py`). Five **fundamental** RAG dimensions in fixed order — Technicals · Valuation ·
   Financials · Earnings · Analysts — each classified R/A/G by pure-domain threshold logic, **DATA-GAP when data
   is absent (never fabricated)**. Net-new yfinance EPS-surprise fetcher. (RAG=good/bad is correct HERE, unlike
   the Risk tab's distance-ramp "character not quality" for beta.)
2. **S3 — v9 decision card** (`adapters/visualization/components/decision_card.py`) = collapsed triage row
   (verdict + 5 RAG squares + realized sparkline + unrealized%) ↔ expanded card (5/5 cited "Google-AI" case +
   5-row RAG evidence table + verdict rubric + research-only footer). One component, two zoom levels. It is the
   redesigned **Stock Analysis tab** (the tab pre-existed; the v9 card leads, the deep-dive remains below).
3. **S4 — Home "Front Desk"** (rewrote `weekly_brief.py`): landing door → 4 vitals (**net-beta two-number bug
   fixed** — one SPY-beta number; systematic-share is "Book health") → book-health ring → one-line "why doubt us
   → Trust" honesty pointer → needs-review collapsed rows → holding-steady → footer with brief **download**.
   Deleted the evidence-ledger / validation tiles / verdict-distribution / attention-table / brief-dump
   (relocated to Trust/Portfolio/Screener, not lost). `application/vs_market.py` for realized book-vs-SPY 1y.
4. **S2 — Cited case** (`adapters/ml/gemini_narrator.py`, `application/case_builder.py`): a `CaseSummarizerPort`
   that summarizes **only fetched cited articles**, both sides forced, **fail-safe `data_gap=True`** on any
   error/no-key, **no trade verbs** ("informs you, not the verdict"). Local `TemplateCaseSummarizer` fallback.
5. **S5 — Loading infra** (`application/card_loading.py`, `adapters/visualization/card_fetch.py`): progressive
   row fill + global progress bar + live `st.fragment` per-row isolation; **lazy cited-case on card-expand only**
   (airtight gate — no ping for a collapsed card); shimmer (loading) ≠ hatched (DATA-GAP); per-ticker caches +
   a cached price-history fetch that lights Technicals + sparkline.
6. **S6 — Onboarding** (`application/runtime_guard.py`, `application/sample_book.py`, landing door): sample book /
   CSV upload / add-manually. **Privacy babyproofing:** `is_local_runtime()` is fail-safe (default False; requires
   `STOCKREC_LOCAL_ONLY=1` + loopback server + loopback client) with a CI tripwire — a hosted deploy can **never**
   show the "stays on your machine" promise or the upload control.

**Round-2 follow-ups (same session):** Gemini ping **rate-limit** (`RateLimitedCaseSummarizer`, 5s default buffer,
`GEMINI_MIN_INTERVAL_S` / `us.yaml gemini.min_interval_seconds`) on all paths; **weekly cited-case cache**
(`application/case_cache.py` + `--cite-cases` CLI prefetch with spaced pings; dashboard reads cache first, lazy
live ping only on miss); money to 2dp; **1-year return window** added (7/30/90/180d · 1y); the **multi-factor
verdict rubric** surfaced in the card (REVIEW/TRIM/REDUCE/ADD_OK/HOLD with their real `grade_position` triggers);
title → Fraunces; onboarding widgets restyled + functional.

## Honesty invariants (held throughout, source-scan enforced)

`FORBIDDEN_WORDS` (`domain/fit.py`: buy/sell/winner/conviction/predict/alpha/outperform) scanned on every new
module; the v9 footer reads "not a **trade** signal"; third-party data attributed, never adopted; DATA-GAP never
fabricated; the cited case never issues a recommendation; the privacy promise is babyproofed.

## Consequences

- Full suite **~1858 passing**, mypy --strict clean on all new/changed modules. Live Home/Stock-Analysis match
  the canonical mockups (verified by screenshot).
- The verdict displayed by the card is the deterministic **trend-break rule v1** (`domain/discipline.grade_position`)
  — already multi-factor (trend + ATR + disposition + volatility + relative strength + trailing-stop + market
  context) and now surfaced as a rubric.
- **Open methodology question (deferred — needs its own ADR/grill):** whether to **extend the verdict logic** to
  fold earnings/valuation *into* the REDUCE/TRIM/BUY decision rather than presenting them only as evidence. This
  changes what the instrument *claims*, so it was intentionally NOT done silently.
- **Loose ends (honest GAPs, non-blocking):** vs-Market(1y) tile shows "—" until the weekly-brief CLI populates
  `summary["vs_market_1y"]` (compute fn exists); Home cards use `news=[]` → TemplateCaseSummarizer unless
  `GEMINI_API_KEY` set; the lazy on-expand cited case has no per-holding news on Home yet.
- **Merge ordering (unchanged):** PR #58 (s.close→s.price + diagnostics fix) lands on develop first; this branch
  stacks. BLOCK-before-main: confirm no surface presents 512→0 as EMH/discipline.
