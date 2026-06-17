# STATUS — multi-modal-stock-recommender

**As of:** 2026-06-17
**Branch:** `feat/risk-tab-fixes` (off `develop`) — **24 commits ahead, NOT yet PR'd**. `develop` is ahead of `main` (whole redesign + Risk v8 release still pending user go).
**Phase:** Risk-tab fix sprint + Cursor follow-ups + 9-factor FF expansion + project-wide Gemini fallback — **ALL DONE, gate-green (2145 tests, 92.8%, mypy strict).** Ready to PR.

## NEXT ACTION (fresh session — start here)
1. **PR `feat/risk-tab-fixes` → `develop`** (24 commits), CI confirm, merge. Then cut the long-pending `develop`→`main` release (needs explicit user go).
2. **THEN: the efficiency / token-bottleneck pass (ADR-061)** — its own dedicated session. Suite is ~2145 tests + climbing, run serial+verbose+coverage every time; oversized modules (`cli.py` 3440 LOC, `risk.py` 1710, `styles.py` 1505) make edits token-heavy. Plan in ADR-061: pytest-xdist + `make test-fast`, run-discipline (targeted tests while iterating, full gate only at checkpoints), module decomposition, cheaper verification, test-value review. **Baseline timings/token cost FIRST, then fix highest-leverage.**

## What shipped this session (all on feat/risk-tab-fixes)
- **R01–R09** Risk-tab redesign fixes (header/banner copy + tooltips, lens-nav, factor chart, ENB drill, who-owns, Google-AI placement, teach donut, refresh-button removal).
- **Cursor follow-up gap-fixes:** R02 scroll shim (CDP-verified 0→4358px), who-owns top-5 cap, R08 Q3 human labels, R07 re-run→info line, CSS cleanup, NET BETA (SPY) tooltip, factor source-bracket dedupe.
- **R03 9-factor FF expansion (ADR-060):** authentic Fama-French long-short factors via new `FamaFrenchProvider` (NOT collinear ETF proxies). `[SPY,SMB,HML,MOM,RMW,CMA,TLT,UUP,XLE]`, sorted by impact, tilts-vs-market line, per-factor tooltips. `history_days=500`.
- **R07 honesty + Gemini:** template output never shown as Google AI (data-gap stub when no key); fixed CLI not loading `.env` (shared `dotenv_loader`); **project-wide Gemini multi-model fallback chain (ADR-061-adjacent — see commit f0e6f15)** — exhausted model falls through to the next free model (verified live: 3.5-flash→2.5-flash, real insights). `tests/conftest.py` strips live API keys so tests never hit real APIs.
- **ADR-059** verdict-logic deferral, **ADR-060** factor expansion, **ADR-061** efficiency initiative.

## Verification
- Full `make check` green at each checkpoint: **2145 passed, 92.8%**, mypy strict + ruff clean.
- Live eyeball (server bound `--server.address localhost`): 9 factors render with badges/tooltips; R07 real Gemini panel renders; who-owns capped to 5.

## Open items
- **PR feat/risk-tab-fixes → develop**, then **develop→main release** (user go).
- **Efficiency pass (ADR-061)** — next dedicated session.
- **#57** fix/adherence-tz-naive-aware — unrelated, still open.
- Risk readout is **~6wks stale** (FF publication lag bounds the regression window) — documented tradeoff (ADR-060). Could add a fresh-4-vs-full-9 toggle if wanted.

## Gotchas (carry forward)
- **Gemini panel needs `--server.address localhost`** (privacy guard requires loopback server) AND a live `GEMINI_API_KEY` (now in `.env`, CLI loads it). Plain `streamlit run` binds 0.0.0.0 → panel hidden by design.
- **Disk-full** fills mid-`weekly-brief` and silently writes stale output — `df -h`, clear `.mypy_cache`/`__pycache__`/pip cache + kill stray streamlit/chrome, re-run clean.
- **mypy env disagreement** on `google.generativeai` (191 vs 196 file views) — handled by `disable_error_code=["attr-defined"]` override in pyproject for the 3 gemini modules; don't use `# type: ignore` (flagged unused in one view).
- **pre-commit auto-fixes** (black/whitespace) → first `make check` "fails", passes on re-run; watch for a *persistent* failure vs self-resolving reformat.
- `data/reports/*.json` + `data/cache/`, `data/personal/cited_cases.json` regenerate / are gitignored — leave unstaged.
- FF cache: `data/cache/fama_french_daily.json` (refresh via weekly-brief).
