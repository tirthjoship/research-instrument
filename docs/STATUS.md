# STATUS — multi-modal-stock-recommender

**As of:** 2026-06-14 (late)
**Branch:** `feat/dashboard-legibility-redesign` — **all 6 redesign subsystems BUILT + verified, committed.**
**Phase:** Home + Decision-Card redesign — **IMPLEMENTED. Full suite 1799 passing, mypy --strict clean (16 modules).**

## Current State

The full Home + decision-card redesign (designed → spec'd → planned this session) is **implemented and
verified** via subagent-driven-development (Sonnet implementers) with an **Opus verification-before-completion
pass after every subsystem**. All committed on the branch.

**Subsystems shipped (each Opus-verified PASS):**
- **S1** evidence signal layer — `domain/evidence_rag.py` (5 RAG classifiers, fixed order, DATA-GAP honest),
  `adapters/data/earnings_history_adapter.py` (net-new EPS-surprise fetcher), `application/evidence_card.py`.
- **S3** v9 decision card — `adapters/visualization/components/decision_card.py` (collapsed row + expanded v9:
  5/5 cited case, 5-row RAG table, "not a trade signal" footer). Redesigned **Stock Analysis tab** (lead card
  above the existing deep-dive, which is untouched/green).
- **S4** Home "Front Desk" — rewrote `weekly_brief.py`: 4 vitals (net-beta **bug fixed** — one number),
  book-health ring, honesty line → Trust, needs-review collapsed rows, brief→download. Deleted ledger /
  validation-tiles / verdict-dist / attention-table / brief-dump (relocated, not lost). `application/vs_market.py`.
- **S2** Gemini cited case — `adapters/ml/gemini_narrator.py` (`CaseSummarizerPort`, cited-only, fail-safe
  `data_gap=True`, no trade verbs) + `application/case_builder.py` (`TemplateCaseSummarizer` CI fallback).
- **S5** loading infra — `application/card_loading.py` (RowState PENDING≠GAP), `adapters/visualization/card_fetch.py`
  (airtight lazy-case-on-expand gate), progressive rows + progress bar + **live `st.fragment` per-row** (1.58),
  cached price-history fetch (Technicals + sparkline + Analysts now light up — mock-vs-reality delta closed).
- **S6** onboarding — `application/runtime_guard.py` (`is_local_runtime()` **fail-safe** + CI tripwire — a hosted
  deploy can NEVER show the "stays on your machine" promise), sample book, privacy-gated landing door.

**Honesty held throughout:** FORBIDDEN_WORDS source-scans on every new module; DATA-GAP never fabricated;
attributed-not-adopted; the cited case "informs you, not the verdict"; privacy promise babyproofed.

## Next Action

1. **Visual proof:** run the app (`STOCKREC_LOCAL_ONLY=1 streamlit run adapters/visualization/dashboard.py`)
   and eyeball Home (Front-Desk triage + collapsed→expand cards) + Stock Analysis (v9 lead) against
   `home-FINAL.html` / `per-stock-v9.html`. Note: Home rows fetch live per holding (cached) — first load is slow.
2. **Finish the branch:** decide merge / PR. **PR ordering (unchanged):** PR #58 (diagnostics + s.close→s.price)
   → develop first; this branch stacks. BLOCK-before-main: confirm no surface presents 512→0 as EMH/discipline.
3. Optional polish (non-blocking, flagged in reviews): GEMINI_API_KEY enables the real cited case (else
   TemplateCaseSummarizer); per-holding news feed for Home cards (currently `news=[]` → template case).

## Caveats

- **All redesign work committed on `feat/dashboard-legibility-redesign`** (S1-S6 + diagnostics fix + spec/plans).
  Nothing merged. `git checkout data/reports/` before any verify (2 tracked JSONs strip trailing newlines).
- **Verify-via-context7 confirmed during build:** `st.fragment` exists (Streamlit 1.58); yfinance earnings/history
  APIs wired; Streamlit server-address/client-host read defensively (fail-safe to remote) for the privacy guard.
- **Plans + spec** in `docs/superpowers/`; canonical mockups in `.superpowers/brainstorm/97077-1781379305/content/`
  (`home-FINAL.html`, `per-stock-v9.html` are the acceptance references). Review hub: `index.html` there.
- Standing watch (unchanged): ADR-048/051 discipline forward gate ~mid-July 2026; ~Dec 2026 behavior-gap review.
