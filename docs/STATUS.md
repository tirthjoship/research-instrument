# STATUS — multi-modal-stock-recommender

**As of:** 2026-06-14 (evening)
**Branch:** `feat/dashboard-legibility-redesign` (16 prior commits + this session's work, **UNCOMMITTED**).
**Phase:** **Home + Decision-Card redesign — DESIGN LOCKED, SPEC written, plans S1/S3 of 6 written.** Next: write S4/S2/S5/S6, then execute.

## Current State

This session pivoted from visual review into a full **grill + brainstorm + frontend-design** pass that
**locked the Home + decision-card redesign** and produced a spec + the first 2 of 6 implementation plans.

**Shipped this session (UNCOMMITTED on branch):**
- 🔴 **Diagnostics bug fixed** — `screen-candidates` rebuilt `ScreenResult` and dropped `diagnostics`
  (always wrote `diagnostics: null`). Fix = `replace(result, candidates=…)` (`application/cli.py` ~2621)
  + regression test `test_screen_candidates_json_preserves_diagnostics`. Live run now: 512→304 candidates,
  funnel **512 scanned→494 had_history→304 above_trend→304 cleared**. 42 screener tests pass, mypy clean.
- 📐 **Design LOCKED** (mockups in `.superpowers/brainstorm/97077-1781379305/content/`):
  `home-FINAL.html` (canonical Home flow), `per-stock-v9.html` (canonical decision card),
  `collapsed-expanded.html`, `loading-states-AB.html`, `home-redesign-AB.html`, `compare-v8-v9.html`.
- 📄 **SPEC** `docs/superpowers/specs/2026-06-14-home-decision-card-redesign-spec.md` (6 subsystems S1–S6,
  every UI claim pinned to a mockup, every data claim to a real file; R1 privacy + R4 holding-model resolved).
- 📋 **Plans written:** `docs/superpowers/plans/2026-06-14-S1-evidence-signal-layer.md`,
  `…-S3-decision-card-stock-analysis.md` (TDD, no placeholders, validated against 2 codebase maps).

**Key locked decisions** (also in memory `project-decision-card-v9-spec`):
- Home = **Option A "Front Desk"**: landing door (sample/CSV/manual) → 4 vitals (ONE net-beta) + book-health
  ring → "why doubt us → Trust" line → needs-review collapsed v9 rows → holding-steady → footer (brief download).
- Decision card = **v9** (full 5/5 cited Google-AI case + 5-row RAG evidence table). Card = the redesigned
  **Stock Analysis tab** (tab already EXISTS — it's a redesign, not new). Home/Portfolio rows = collapsed form.
- RAG squares = 5 FUNDAMENTAL dims (Technicals/Valuation/Financials/Earnings/Analysts), fixed order, hover,
  **DATA-GAP = hatched** (≠ loading shimmer). NOT the screen factors.
- Loading = progressive fill + global progress bar + **lazy AI-case on expand**; shimmer≠hatched.
- Verdict source = `domain/discipline.grade_position` (the trend-break rule v1). Google-AI case = NEW
  `GeminiNarratorAdapter`. Privacy = local-only + `is_local_runtime()` fail-safe guard + CI tripwire.

## Next Action

1. **Write remaining plans** (same TDD/no-placeholder rigor, build order): **S4** (Home rewrite + net-beta
   bug fix + vs-Market + section moves) → **S2** (`GeminiNarratorAdapter` cited case) → **S5** (loading infra:
   st.fragment + progress + lazy-case + cache) → **S6** (CSV upload + add-manually + sample book + privacy guard).
2. **Then execute** via subagent-driven-development (Sonnet implementers, Opus review per task).
3. **Two codebase maps already done** this session (backend modules + viz component layer) — anchors are in
   the S1/S3 plans; reuse for S4–S6. Verdict=`grade_position`; CSS injector=`inject_global_css()`; validation
   tiles ALREADY on Trust; `tooltip()` KeyErrors on undocumented terms (squares use bespoke hover, not tooltip).
4. **PR ordering:** PR #58 (diagnostics + s.close→s.price) → develop first; this branch stacks. BLOCK-before-main:
   confirm no surface presents 512→0 as EMH/discipline.

## Caveats

- **Nothing committed this session** — diagnostics fix + spec + 2 plans all sit uncommitted on the branch.
- **Honesty invariant holds:** FORBIDDEN_WORDS (`domain/fit.py`, 7 words) source-scanned per new module; v9
  footer reworded "not a trade signal" to pass; third-party data attributed, never adopted; DATA-GAP never faked.
- `git checkout data/reports/` before any pre-commit/CI verify (tests strip trailing newlines from 2 tracked JSONs).
- **Verify-via-context7 flags in the plans:** yfinance `earnings_dates` API (S1), `st.fragment`/`st.status`
  availability (S5), Streamlit server-address/client-host API for the privacy guard (S6).
- Standing watch: ADR-048/051 discipline forward gate resolves ~mid-July 2026 (weekly Saturday job); ~Dec 2026
  behavior-gap review.
