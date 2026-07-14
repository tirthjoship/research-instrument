# Architecture

## Pattern: Hexagonal (Ports & Adapters)

All arrows point inward. `domain/` imports nothing from `adapters/` or `application/`.
Swapping a data source, ML model, or dashboard = new adapter, never touches business rules.

```
adapters/     →     domain/     ←     application/
(external)          (pure)            (orchestration)
```

**Dependency rule enforced by `domain-check` skill and mypy strict.** Any `import` of a
non-stdlib symbol inside `domain/` is a CI failure.

---

## Module map (current)

```
domain/
  models.py              Core dataclasses (Signal, Conviction, Brief, PortfolioRisk, …)
  ports.py               All port interfaces — source of truth for adapter contracts
  services.py            Business logic (look-ahead bias enforcement lives here)
  exceptions.py          LookAheadBiasError, InsufficientDataError, SourceThrottledError
  brief.py               WeeklyBrief assembly + markdown/stdout renderers
  adherence.py           Discipline/adherence domain logic
  risk_stats.py          Risk statistics value objects
  macro_beta.py          Macro-beta domain model
  fit.py                 Portfolio-fit verdict model
  filing_textchange_service.py  Lazy Prices text-change signal (ADR-057, stdlib-only)

adapters/data/
  yfinance_*             Price, analyst estimates
  gdelt_sentiment_*      News sentiment (GDELT)
  rss_adapter.py         RSS feed ingestion
  sqlite_store.py        Persistence (1093 LOC — decomp candidate)
  fama_french_provider.py  Factor data (295 LOC)
  sector_provider.py     Sector taxonomy
  sec_filing_text_adapter.py  10-K/10-Q section text, point-in-time (Lazy Prices / ADR-057)
  …

adapters/ml/
  feature_engineer.py    101 features across 5 signal layers
  ensemble_predictor.py  XGBoost + LightGBM + Ridge stacked ensemble
  risk_stats_analyzer.py Risk statistics computation
  gemini_models.py       Gemini API adapter
  …

adapters/visualization/
  dashboard.py           Streamlit entry point (tab routing only)
  book_context.py        resolve_ui_book_context() — sample vs session-upload split (2026-07-11)
  run_gate.py            Gated Run buttons: single-flight/cooldown/freshness (2026-07-11)
  holdings_syncer.py     Personal-dogfood CSV sync + weekly-brief rebuild trigger
  tabs/
    risk/                Risk tab — DECOMPOSED 2026-06-17 (was risk.py 1710 LOC)
      compose.py         Entry point: render()
      components.py      Header, banner, vitals, dials (~390 LOC)
      evidence.py        Evidence bands, flags footer
      factor_chart.py    Fama-French factor chart (~253 LOC)
      enb_section.py     ENB drill section (~229 LOC)
      sections.py        Sector, who_owns, drift, teach
      _theme.py          Colour/style constants
    research_candidates.py  Research tab (1211 LOC — decomp candidate)
    stock_analysis.py    Stock analysis tab (1055 LOC — decomp candidate)
    weekly_brief.py      Weekly brief tab (600 LOC)
    positions.py         Positions tab
  components/
    styles.py            CSS/styling (1524 LOC — decomp candidate, T2-3 deferred)
    cards.py             Decision cards
    charts.py            Shared chart builders
    …

application/
  cli/                   CLI package — DECOMPOSED 2026-06-17 (was cli.py 3440 LOC)
    __init__.py          Re-exports cli group + shared helpers; imports all submodules
    _cli_group.py        Click group definition
    _deps.py             _build_dependencies() + shared helpers (533 LOC)
    backtest_commands.py Backtest + daily-cycle commands
    brief_commands.py    weekly-brief + cited-case prefetch
    data_commands.py     drip-backfill, backfill-history, resolve-wiki-articles
    ml_commands.py       pretrain, run-tournament, evaluate, shap-report
    portfolio_commands.py portfolio-verdict, holdings-risk
    scan_commands.py     scan-opportunities, resolve-calls, daily-scan
    screen_commands.py   screen-candidates, backtest-screen
    validation_commands.py adherence-report, divergence-IC, momentum-discipline, audit
  conviction_use_case.py Weekly tournament orchestration
  evidence_screen_use_case.py Evidence screen (RESEARCH_ONLY)
  holdings_risk.py       Holdings risk assessment
  risk_second_opinion.py Google-AI risk second-opinion (cache-first)
  divergence_ic_backtest.py  Pre-registered IC falsification (injected callables)
  lazy_prices_backtest.py    Lazy Prices IC + net-of-cost gate (ADR-057, injected callables)
  price_returns.py       Forward-return + yfinance loader (point-in-time)
  ticker_universe.py     Static S&P500 ∪ NASDAQ-100 loader
  …

config/
  markets/us.yaml        Market config + locked gate thresholds
  tickers/               Universe lists (sp500, nasdaq100)

tests/
  fakes/                 Test doubles for all domain ports — use these, never mock
  conftest.py            API-key strip autouse fixture
  domain/                Domain unit tests
  adapters/              Adapter unit tests
  application/           Use-case integration tests
  test_opportunity_cli.py  CLI smoke + integration tests
  test_cli_weekly_brief.py Weekly brief CLI tests
  …
```

---

## Key structural decisions

### Sample vs personal book split for the public UI (2026-07-11)

**Problem:** cold start on Home/Portfolio/Risk auto-loaded the operator's real
`data/personal/holdings.csv` and `data/personal/brief_summary.json` whenever those
files existed on the machine running the dashboard — a hosted public deploy would leak
real holdings to strangers.

**Fix:** `adapters/visualization/book_context.py::resolve_ui_book_context()` is the
single source of truth for which book + brief/screen artifacts the Streamlit UI shows.
Priority: a session-uploaded book (`is_sample_book=False` in `st.session_state`) — else
the bundled sample book (`application/sample_book.py` + committed `data/sample/`
artifacts). It never reads `data/personal/*`. `weekly_brief.py::_handle_onboarding`,
`positions.py::_resolve_book`, and `risk/compose.py::render` all resolve through it
instead of hardcoded personal-path defaults.

Uploads are session-only: `weekly_brief.py::_stage_csv_upload` stores the parsed book
directly in `st.session_state` and rebuilds the brief into a `tempfile.mkdtemp()`
directory — it no longer calls `holdings_syncer.save_and_sync_holdings()` (which writes
`data/personal/holdings.csv`) on the public path. That function/its CLI dogfood callers
are unchanged for local/offline use.

`adapters/visualization/run_gate.py::evaluate_run_gate()` gates the in-app "Run brief" /
"Run screener" buttons (single-flight, cooldown, disable if fresh &lt;1 day) — both
always write into a fresh session-scoped temp dir, never the committed `data/sample/`
artifacts or the operator's shared `data/reports/` output.

Personal CLI dogfood (`weekly-brief --holdings data/personal/holdings.csv`) remains
valid outside the public UI path — see
`docs/superpowers/archive/2026-07-11-public-sample-book-design.md` for the full design.

### Why hexagonal?

The core thesis (sentiment leads price) is under active test. Prediction models get
killed when they fail pre-registered gates. Hexagonal architecture means each killed
model is one adapter deletion — domain logic survives unchanged.

### Why decompose cli.py and risk.py? (2026-06-17)

**Before:** `cli.py` was 3440 LOC, `risk.py` 1710 LOC. Every targeted edit required
reading an entire file (~32k / ~19k tokens) just to change one command or one chart
section.

**After:** Largest file in `application/cli/` is `_deps.py` at 533 LOC. Largest in
`adapters/visualization/tabs/risk/` is `sections.py` at 433 LOC. A targeted edit now
costs ~4k tokens, not 32k — an 85% reduction per edit session.

**How the public interface was preserved:** `application/cli/__init__.py` re-exports
`cli` (the Click group) and all shared helpers. All existing `from application.cli import cli`
calls continue to work. Submodules register their `@cli.command` decorators on import,
triggered by the `from . import *_commands` block in `__init__.py`.

**Test monkeypatch note:** After decomposition, tests that patched `application.cli.X`
needed updating. Symbols now live in their submodule at import time; patches must target
the module where the name is looked up (e.g. `application.cli.data_commands.DripBackfillUseCase`).
Lazy imports inside function bodies (e.g. `OpportunityScanUseCase`) are patched at the
source module (`application.opportunity_scan_use_case`). Fixed 2026-06-18.

---

## Remaining decomposition candidates (not yet done)

| File | LOC | Notes |
|---|---|---|
| `adapters/visualization/components/styles.py` | 1524 | T2-3 deferred — CSS/style functions, split by component group |
| `adapters/visualization/stock_analyzer.py` | 1305 | Not yet scoped |
| `adapters/visualization/tabs/research_candidates.py` | 1211 | Not yet scoped |
| `adapters/data/sqlite_store.py` | 1093 | Not yet scoped — core persistence, higher risk |
| `adapters/visualization/tabs/stock_analysis.py` | 1055 | Not yet scoped |

Priority order: `styles.py` (lowest risk, pure CSS), then `research_candidates.py` /
`stock_analysis.py` (tab pattern, same approach as risk.py).

---

## Look-ahead bias enforcement

Point-in-time discipline is the single most critical invariant. Enforced at two layers:

1. **Runtime:** `validate_point_in_time_access()` in `domain/services.py` checks all
   signal/sentiment timestamps ≤ prediction_time. Violations raise `LookAheadBiasError`
   and halt the pipeline.

2. **Feature matrix:** `FUTURE_LEAKAGE_COLUMNS` in `adapters/ml/feature_engineer.py`
   lists columns that must never appear in training data.

---

## Port contract

`domain/ports.py` is the source of truth for every adapter contract. Adding a new
data source = implement the relevant Protocol. Adding a new model = implement
`PredictorPort`. The domain never imports the implementation.
