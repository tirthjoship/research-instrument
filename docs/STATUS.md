# STATUS — multi-modal-stock-recommender

**As of:** 2026-06-20 (session 3)
**Branch:** `feat/corroboration-engine` (off `develop`)
**Phase:** Corroboration engine (sub-project 1 of 5) — BUILT, RESEARCH_ONLY

## NEXT ACTION (fresh session — start here)

1. PR `feat/corroboration-engine` → `develop` (gate green locally, see evidence below).
2. Then sub-projects 2–4 (consumers: surfacing / screener / portfolio-verdict) +
   SP5 (forward Hypothesis #9 gate) + SP6 (dashboard) + SP7 (weekly-job reliability).

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
| Tests | 26 passing (tier branches + Hypothesis invariant, PIT leakage guard, citation word-boundary, summarizer fallback, store round-trip, TTL cache) | ✅ |

## Verification evidence (gate)

- `mypy domain/ adapters/ application/ --strict` → **Success, 227 files** (via `.venv`).
- 26 corroboration tests pass (`PATH=.venv/bin:$PATH pytest tests/test_corroboration_* tests/test_model_registry.py tests/test_citation_verifier.py tests/test_search_harvester.py tests/test_llm_summarizer.py -q`).
- ruff clean on all new files. Two-Opus review done; both criticals fixed (mypy gate + citation word-boundary).

## Known limitations — DEFERRED (honest, not bugs)

- **Live smoke deferred**: `tavily` not installed + Tavily/Gemini keys unverified this session.
  All built + unit-tested on injected fakes; live `corroborate` run not exercised.
- **CLI `readout_fn` is an all-None stub** (`# TODO(sp2)`): the live command does NOT yet feed our
  own signals into the service, so the "stress-test against our signals" tier logic is inert
  end-to-end (the domain fully supports it; only the CLI wiring is deferred to SP2).
- **`cached_preferred` TTL cache** implemented + tested but not wired into the live CLI (re-pings
  `list_models` each run). Wire when live path is exercised.
- **Silent-empty**: live CLI prints "0 candidates" identically whether the pipeline broke or
  genuinely found nothing — add a broken-pipeline warning before the live path is trusted.

## Gotchas

- Use `.venv` (has xdist), NOT miniforge: prefix make/pytest with `PATH=.venv/bin:$PATH`.
- **Full `make check` coverage suite HANGS** (open flag, `fix/test-hang-timeout`). Smoke/visualization
  tests also fail in `.venv` because `streamlit` isn't installed there — environment, not corroboration.
  Verify corroboration via the targeted pytest set above + `--strict` mypy.
- `data/reports/*.json` + `pyproject.toml` (concurrent pytest-timeout edit from another branch)
  show dirty — never commit them with corroboration work.
