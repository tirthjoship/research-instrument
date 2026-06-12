# CONTEXT — multi-modal-stock-recommender

Navigational + domain-language anchor. Stable facts about *what this project is*. For
*current state / next action* read `STATUS.md`; for *decisions* read `adr/`; for *history*
read `PHASE_LOG.md`.

## What it is

A personal, **research-only** stock decision-support tool for a family book. It does
**not** predict returns and must never imply it does — every predictive hypothesis tested
(2006–2024) was falsified (ADR-039/043/044/046/049/050/053; alpha hunt closed in ADR-052).
What survived is **descriptive**: factual screening, portfolio-fit verdicts, risk/macro
exposure, and discipline tracking.

## The honesty invariants (non-negotiable)

- **RESEARCH_ONLY** — no buy/sell call anywhere in the product.
- **FORBIDDEN_WORDS** = `buy, sell, winner, conviction, predict, alpha, outperform`
  (`domain/fit.py`). Enforced by source-scan + property tests, not convention — drift fails
  CI. New user-facing surfaces get a scoped scan.
- **No look-ahead bias** — all data timestamps ≤ prediction_time; `LookAheadBiasError`
  halts the pipeline. `FUTURE_LEAKAGE_COLUMNS` never enter feature matrices.
- **Evaluate with Sharpe + precision/recall vs SPY**, never raw returns / accuracy.

## Architecture (hexagonal, dependencies point inward)

```
adapters/  →  domain/  ←  application/
(external)    (pure)      (orchestration)
```

- `domain/` — pure business rules/models/ports/exceptions. **stdlib only** (typing,
  dataclasses, datetime, enum). Key: `fit.py` (verdict + FORBIDDEN_WORDS), `screen_models.py`,
  `brief.py`, `discipline.py`, `models.py` (incl. `BookMacroExposure`).
- `application/` — use-case orchestration over ports. Notable: `evidence_screen_use_case`
  (factual rank), `weekly_brief_use_case` + `brief_summary` (per-holding verdicts),
  `macro_beta_use_case` (book factor exposure), `fit_use_case` / `batch_fit_use_case`,
  `discipline_log` (the forward-gate log), `adherence`, `diversification_query` (pure corr
  ranking). **A new tool = a new adapter, never new domain code.**
- `adapters/` — `data/` (yfinance, RSS, Google Trends, StockTwits, GDELT, SQLite),
  `ml/` (scorers, predictors, ensemble, `correlation_analyzer`), `visualization/`
  (Streamlit; see below).

## The dashboard — two surfaces (ADR-055)

`adapters/visualization/dashboard.py` routes **Cockpit | Showcase**.

- **Cockpit** (`adapters/visualization/cockpit/`) — single-scroll family triage, strict
  priority order via the assembler `cockpit.py`: `_danger` → `_calls` → `_retro` →
  `_discover` → `_lookup`, with `stock_detail.py` as an `st.dialog` drawer. One design
  system (`components/styles.py` ws-card tokens). The **only write** is `_calls`
  confirm-and-log to the discipline gate (idempotent per `as_of`). Discovery (`_discover`)
  splits factual rank (always shown) from the abstaining edge verdict (shown as abstention),
  diversification-first vs the dominant macro factor.
- **Showcase** — `tabs/trust.py`: the falsification / methodology credibility wall.
- Surviving tab: `tabs/risk.py` (danger drill-down). Other v2 tab renderers were deleted;
  their compute stays in the core.

Launch: `streamlit run adapters/visualization/dashboard.py`. `adapters/visualization/*` is
excluded from the coverage gate but still unit-tested via a headless `FakeSt` stub
(`tests/cockpit/fake_st.py`).

## Domain language (quick glossary)

- **Screen / evidence rank** — cross-sectional z-score composite over momentum, revision,
  quality, value; percentile per factor. Can **abstain** (thin coverage) yet still persist
  the full ranked distribution (`data/reports/screen_<date>.json`).
- **Verdict** — per-holding REDUCE / TRIM / REVIEW / HOLD / ADD_OK (`domain/discipline.py`).
- **Fit verdict** — evidence grade (STRONG/MODERATE/WEAK/UNKNOWN) + fit flags
  (BETA_AMPLIFY/CONCENTRATION/TREND_STATE/DATA_GAP). Descriptive, never a call.
- **Discipline forward gate** (ADR-048) — logs the week's calls; resolves down-rate on
  REDUCE over a horizon. Calibration window resolves ~mid-July 2026 (ADR-051).
- **Macro/book exposure** — dollar-weighted net beta per factor (SPY/TLT/UUP/USO/XLE),
  systematic vs idiosyncratic share, dominant factor (`BookMacroExposure`).

## Conventions

- Python 3.12+, mypy strict on domain/application/non-viz adapters, black, pre-commit
  enforced (never `--no-verify`). `data/reports/screen_20*.json` gitignored — `git checkout
  data/reports/` before pre-commit if they appear dirty.
- Branches: feature → `develop` → `main` (PRs, never direct to develop/main). Conventional
  commits. Tests use small fixtures, never live APIs.
