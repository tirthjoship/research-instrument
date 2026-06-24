# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository. Read `AGENTS.md` for all coding standards, architecture rules, and testing requirements before touching any code.

## Project Context

Multi-modal stock recommendation engine combining structured market data (yfinance) with unstructured sentiment signals (news, Reddit, StockTwits) to generate weekly Top 15 stock picks. Core hypothesis: **sentiment leads price by 1-48 hours**, and when technical indicators diverge from sentiment signals, the divergence predicts 5-day directional returns.

The project uses hexagonal architecture (ports & adapters) so the domain logic stays pure and any data source, ML model, or UI can be swapped without touching business rules.

## Commands

```bash
# Full quality gate (lint + typecheck + test with coverage) — CI and pre-PR only
make check

# Fast iteration targets
make test-fast        # full suite, parallel, no coverage (~35s)
make test-tab tab=risk  # single tab tests, <15s — replace 'risk' with tab name
make test-domain      # domain/ tests only
make test-adapters    # adapters/ tests only

# Coverage gate (when you need to confirm coverage)
make test-cov

# Other targets
make lint             # pre-commit run --all-files
make typecheck        # mypy strict on domain/ adapters/ application/
make setup            # uv sync + pre-commit install

# Single test
pytest tests/test_domain_models.py::test_signal_valid_creation -q
```

## Model Routing (this project)

Use the right model for each task — never burn Opus on work Sonnet handles.

| Task | Model |
|------|-------|
| Tab/adapter edits, CLI commands, tests | Sonnet |
| Domain model changes | Sonnet |
| Architecture decisions, ADRs | Fable (main loop) |
| Debugging test failures, root cause analysis | Opus |
| File lookup, grep, targeted search | Haiku |
| Full codebase exploration (Explore agent) | Sonnet |
| Code review pre-PR | Opus |

## Testing Discipline (mandatory — not advisory)

Run the narrowest target that covers your change. `make check` is for checkpoints and PR only — not after every edit.

| Change type | Run immediately | Before commit | Before PR |
|-------------|-----------------|---------------|-----------|
| Any dashboard tab | `make test-tab tab=<name>` | `make test-smoke` | `make check` |
| CLI command | `pytest tests/test_<name>.py -q` | `make test-smoke` | `make check` |
| Domain model | `make test-domain` | `make test-smoke` | `make check` |
| Adapter change | `make test-adapters` | `make test-smoke` | `make check` |
| Cross-cutting | `make test-fast` | `make test-smoke` | `make check` |

Tab names for `make test-tab`: `risk`, `weekly_brief`, `research`, `screener`, `positions`, `trust`

**Never run `make check` during iterative edits in a session — only at checkpoints and pre-PR.**

## Architecture

**Hexagonal (Ports & Adapters) with inward-pointing dependencies.**

```
adapters/     →  domain/  ←  application/
(external)       (pure)      (orchestration)
```

- `domain/` — Business rules, models, port interfaces, exceptions. ZERO external framework imports.
- `adapters/data/` — yfinance, RSS feeds, Google Trends, StockTwits, GDELT sentiment, SQLite store.
- `adapters/ml/` — Keyword scorer, Flan-T5 sentiment, XGBoost predictor, LightGBM predictor, ensemble.
- `adapters/visualization/` — Streamlit dashboard (Phase 5).
- `application/` — Use case orchestration (WeeklyTournament, TrackRecommendations, Backtest).
- `config/markets/` — Market-specific configuration (us.yaml, future: ca.yaml, in.yaml).

Port interfaces in `domain/ports.py` define contracts. Adapters implement them. New tool = new adapter, never new domain code.

## Critical Domain Knowledge

**Look-ahead bias — the biggest risk in this project.**

Point-in-time enforcement is non-negotiable. All data accessed during prediction must have timestamps <= prediction_time. Violations are catastrophic — they make backtests look profitable while the live system fails.

Enforced via:
- `LookAheadBiasError` in `domain/exceptions.py` — halts pipeline on violation
- `validate_point_in_time_access()` in `domain/services.py` — checks all signal/sentiment timestamps
- Every adapter must filter data to prediction_time before returning

**FUTURE_LEAKAGE_COLUMNS** (must never appear in feature matrices):
- `next_day_return` — future price data
- `next_week_return` — future price data
- `future_earnings_surprise` — post-event data
- `forward_pe_ratio` — uses future earnings estimates

**Sentiment-price dynamics (from thesis):**
- Sentiment leads price by 1-48 hours (hypothesis under test)
- Cross-modal divergence (technicals disagree with sentiment) is the primary predictive signal
- Buzz alone does not equal returns — the model must learn which buzz patterns precede moves

**5-tier grading system:**
- Strong Buy (top 3, high confidence)
- Buy (rank 4-8)
- Hold (rank 9-12)
- May Sell (rank 13-15, declining signals)
- Immediate Sell (held stock with negative divergence flip)

**Evaluation — always compare against SPY benchmark:**
- Never claim "model beats the market" without risk-adjusted comparison
- Sharpe ratio, not raw returns
- Precision/recall on directional predictions, not accuracy alone

## Non-Negotiable Rules

Five hard stops — see `AGENTS.md` for full details:

1. **No framework imports in domain/** — domain/ imports only typing, dataclasses, datetime, enum
2. **No look-ahead bias** — all data timestamps must be <= prediction_time. LookAheadBiasError enforced.
3. **Evaluate with Sharpe ratio + precision/recall** — never raw returns or accuracy alone
4. **No direct commits to main or dev** — feature branches only, PR to dev
5. **Tests use small fixtures** — never hit real APIs (yfinance, Reddit) in CI tests. Use fakes.

## External Documentation — context7

This repo leans on fast-moving libraries: **yfinance, streamlit, plotly, click, xgboost,
lightgbm, scikit-learn, pandas, pytest, hypothesis**. Their APIs drift between versions.

Invoke the `context7` MCP server (`resolve-library-id` → `query-docs`) **before** writing or
debugging code against any of these — do not answer from memory. Typical triggers here:
adding/altering a Streamlit tab or Plotly chart (dashboard realignment), a yfinance fetch
signature, a click command option, or an xgboost/lightgbm training call. Skip it for pure
domain logic (`domain/` is stdlib-only) and refactors with no third-party API involved.

Full per-phase routing incl. context7: `docs/SKILL_ROUTING.md` (when it lands, dashboard plan Task 1).

## Key Files — Where to Look

```
domain/models.py                   Core dataclasses (Signal, Conviction, Brief, etc.)
domain/ports.py                    All port interfaces — source of truth for contracts
domain/services.py                 Business logic (LookAheadBias enforcement here)
application/cli/                   CLI package (decomposed from 3440-LOC monolith)
  _cli_group.py                    Click group definition
  _deps.py                         _build_dependencies() + shared helpers
  *_commands.py                    One file per command domain (~300-500 LOC each)
adapters/visualization/tabs/risk/   Risk tab package (decomposed from 1710-LOC monolith)
  compose.py                        _compose() + render() entry point
  components.py                     Header, banner, nav, vitals, dials (~400 LOC)
  evidence.py                       Evidence bands, grill drill, flags footer
  factor_chart.py                   Fama-French factor chart (~240 LOC isolated)
  enb_section.py                    ENB drill section (~220 LOC isolated)
  sections.py                       Sector, who_owns, drift, teach sections
adapters/visualization/tabs/stock_analysis/  SP6 package (decomposed from 1055-LOC monolith — in progress)
  compose.py                        render() entry, RESEARCH_ONLY banner, chip nav
  verdict_section.py                Verdict, Fit, Analyst, News, Peer percentiles
  financials_section.py             Valuation, Growth, Health
  market_section.py                 Performance, Ownership
  signals_section.py                Sentiment, Supply chain
  corroboration_section.py          NEW: claim cards, OurReadout bridge, DirectionalView
adapters/visualization/components/ Shared UI components (styles.py, charts.py, cards.py)
adapters/visualization/data_loader.py  Dashboard data boundary — all store reads go here
  CorroborationTabView              DTO for corroboration tab data (SP6)
  load_corroboration_snapshot()     Reads CorroborationStore snapshot by ticker
domain/corroboration_models.py     Corroboration domain types (HarvestedClaim, CorroboratedCandidate, etc.)
adapters/data/corroboration_store.py  SQLite persistence for corroboration runs + snapshots
adapters/data/sqlite_store.py      Main persistence layer (recommendations, holdings, etc.)
tests/fakes/                       Test doubles for all ports — use these, never mock
  corroboration_store_fake.py       FakeCorroborationStore + FAKE_CLAIM_* fixtures (SP6)
tests/conftest.py                  Strips live API keys — one autouse fixture only
```

## Files — Do NOT auto-read

| File / Directory | Why |
|---|---|
| `CONTEXT.md` | Historical session timeline (~17,800 tokens). Open only if user asks about project history. |
| `docs/superpowers/plans/*.md` | Implementation plans (600-1500 LOC each). SDD `task-brief` script extracts the relevant task — never read the full plan inline in the controller. Archive after SP merges. |
| `docs/superpowers/specs/*.md` | Design specs. Read on demand only (when the named task references one). Archive after SP merges. |
| `docs/superpowers/archive/` | Completed plans/specs — never read. |
| `docs/PHASE_LOG.md` | History doc — open only for past detail requests. |
| `research/` | Investigation snapshots — open only if explicitly referenced. |

**Archive discipline (mandatory):** When an SP merges to develop, move its plan + spec to `docs/superpowers/archive/` in the same session. Unarchived completed plans auto-load into every SDD subagent context (~9k tokens per session per forgotten plan).

Current state: `docs/STATUS.md` — read this first. It is short and authoritative.

## Phase Status

**Current state + next action: `docs/STATUS.md`** (read this first — it is the
single source of truth, kept short and current).
Skill/agent routing per phase: `docs/SKILL_ROUTING.md` (which skill to invoke, which gate must pass).

Full phase-by-phase history: `docs/PHASE_LOG.md` (read on demand only).
Architecture decisions: `docs/adr/` (read the specific ADR a task references).
