# STATUS — multi-modal-stock-recommender

**As of:** 2026-06-20 (session 4 — wrap/handoff)
**Branch:** `feat/corroboration-engine` (off `develop`) — SP1 done, PR #73 open (deferred)
**Phase:** Corroboration engine SP1 BUILT + LIVE-VALIDATED, RESEARCH_ONLY → next = SP2–7 specs

## NEXT ACTION (fresh session — start here)

**Spec the next sub-project (SP2–7).** PR #73 is OPEN but deferred by user — do NOT merge/PR this session.
Briefs already committed: `docs/superpowers/specs/2026-06-20-sp{2..7}-*.md`. Pick one with the user, then
brainstorming → writing-plans → subagent-driven-development.

Sub-project sequence (ADR-062): SP2 candidate-surfacing → SP3 screener-revamp → SP4 portfolio-verdict →
SP5 Hypothesis #9 forward gate → SP6 stock-analysis tabs → SP7 weekly-job reliability. ADR-062 notes SP7
reliability is "fixed first" — confirm with user which to spec first.

**CAVEAT — shared working tree:** the main repo tree may be on another branch (a concurrent session ran
`fix/test-hang-timeout`). Check `git branch --show-current` first; do SP2+ work in an isolated `git worktree`
off `feat/corroboration-engine` (or off `develop` once #73 merges). `.venv` is uv-managed (no pip → use
`uv pip install`); symlink it into the worktree.

Plan: `docs/superpowers/plans/2026-06-20-corroboration-engine.md`
Spec: `docs/superpowers/specs/2026-06-20-corroboration-engine-design.md`
ADR:  `docs/adr/ADR-062-corroboration-engine-pivot.md` (the corroboration-engine ADR — no
separate ADR added; 062 already records attributed-not-predicted, decoupled search+LLM,
forward-only validation, ModelRegistry honest-limits).

## What landed (11 TDD tasks, ~12 commits)

| Layer | Files | Status |
|-------|-------|--------|
| Domain (stdlib-only) | `corroboration_models.py`, `corroboration_service.py` (§6 tier math + rollup), `ports.py` (+3 protocols) | ✅ |
| Adapters | `model_registry.py`, `citation_verifier.py`, `search_harvester.py`, `llm_summarizer.py`, `corroboration_store.py` | ✅ |
| Application | `corroboration_use_case.py`, `corroboration_sanity.py`, `cli/corroboration_commands.py` (`corroborate` cmd) | ✅ |
| Tests | 50 passing (tier branches + Hypothesis invariant, PIT leakage guard, citation word-boundary, summarizer fallback, store round-trip, TTL cache, readout band/percentile/assembly) | ✅ |

## Verification evidence (gate)

- `mypy domain/ adapters/ application/ --strict` → **Success, 228 files** (via `.venv`).
- 50 corroboration tests pass. ruff clean. Two-Opus review done; both criticals fixed.
- **LIVE smoke PASSED** (`python -m application.cli corroborate`, Run ID 2, 4 candidates):
  real ddgs search → real verified citations (kiplinger URLs resolve + name ticker) → real Gemini
  stances → real per-ticker trend_health (NVDA=healthy, MSFT=broken, AMZN=healthy, IBM=caution);
  IBM dropped (NONE_DROPPED) by the verifier. Double RESEARCH_ONLY banner, no prediction language.

## Post-review live-path fixes (all DONE on this branch)

- **readout_fn now real** (`application/corroboration_readout.py`, pure+tested): live trend_health
  (yfinance) → TrendHealth band; factor_percentile from `screen_<date>.json` when present (else None);
  divergence/discipline honestly deferred (no buzz-only proxy — buzz ≠ returns per thesis).
- **Gemini auth fixed**: `gemini_lister`/`_GeminiProvider` now `genai.configure(GEMINI_API_KEY)` —
  the live LLM was previously silently dead (never authenticated).
- **Search**: switched to maintained `ddgs` package (duckduckgo_search deprecated/renamed).
- **`cached_preferred` wired** into the CLI (7-day TTL; no more re-pinging list_models).
- **Broken-vs-empty warning**: CLI distinguishes "search returned nothing" from "all dropped".

## Still deferred (honest, not bugs)

- **factor_percentile** is None unless a `screen_<date>.json` exists (run `screen-candidates` first).
- **divergence_flag / discipline_flag**: deferred to SP2 (need price+buzz series; holdings input).
- `ddgs` is a runtime dep for the live path (installed in `.venv`; add to pyproject extras in SP2/SP7).

## Gotchas

- Use `.venv` (uv-managed, no pip — use `uv pip install`), NOT miniforge: prefix with `PATH=.venv/bin:$PATH`.
- **Full `make check` coverage suite HANGS** (open flag, `fix/test-hang-timeout`). streamlit not in `.venv`
  so viz/smoke tests fail there — environment, not corroboration. Verify via the targeted pytest set + `--strict` mypy.
- google.generativeai prints a deprecation FutureWarning (project-wide; migrate to google.genai later).
