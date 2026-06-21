# SP7 Codebase Grounding

## Summary

The SP7 spec is grounded in live code and current planning docs. ADR-062 records `run-tournament` as the superseded dead prediction path and states weekly-job reliability is fixed first. `weekly-brief` currently wires real holdings through `HoldingsRiskAssessmentUseCase`, whose volatility path uses `statistics.pstdev`. The same volatility pattern exists in `application/discipline_backtest.py`, so the SP7 spec's class-level volatility fix maps to more than one live call site. The corroboration CLI exists today, depends on `ddgs`/`duckduckgo_search` at import time inside the search function, and persists to `data/recommendations.db` through `CorroborationStore`.

## SP7 Order In Current Docs

- `docs/STATUS.md:3-15` records `feat/corroboration-engine`, marks the next phase as SP7 spec review, and documents the order SP7 -> SP2 -> SP3 -> SP4 -> SP5 -> SP6.
- `docs/adr/ADR-062-corroboration-engine-pivot.md:42-50` says SP7 weekly-job reliability is fixed first, while SP2-SP6 consume the corroboration core.
- `docs/superpowers/specs/2026-06-20-sp4-portfolio-verdict-brief.md:22-36` says SP4 extends `weekly_brief_use_case` after the SP7 `holdings_risk._vol` crash is fixed.
- `docs/superpowers/specs/2026-06-20-sp5-hypothesis9-forward-gate-brief.md:12-18` defines `resolve-corroboration` and `corroboration-calibration-status` as SP5 scope.
- `docs/superpowers/specs/2026-06-20-sp6-stock-analysis-tabs-brief.md:24-28` says SP6 renders from persisted `CorroborationStore` snapshots and depends ideally on SP2-SP4 consumers.

## Weekly Brief Path

- `application/cli/brief_commands.py:24-53` builds the weekly brief use case and instantiates `HoldingsRiskAssessmentUseCase`.
- `application/cli/brief_commands.py:155-189` wires screen scorecard, discipline scorecard, macro function, and holdings risk into `WeeklyBriefUseCase`.
- `application/holdings_risk.py:52-61` normalizes dates and computes volatility with `statistics.pstdev(tail)`.
- `application/holdings_risk.py:93-96` feeds recent and base volatility into `conditional_vol_signal`.
- `tests/test_holdings_risk.py:36-62` already has a regression around live-provider datetime normalization, but no numpy-scalar volatility regression in the current file.

## Discipline Backtest Volatility Path

- `application/discipline_backtest.py:40-42` defines a second `_vol()` helper using `statistics.pstdev(tail)`.
- `application/discipline_backtest.py:93-96` feeds that helper into `conditional_vol_signal` for historical calibration.
- `tests/` contains `test_discipline_backtest.py`, so the existing test layout already has a natural place for discipline-backtest coverage.

## Run-Tournament Path

- `docs/adr/ADR-062-corroboration-engine-pivot.md:18-21` documents the live `run-tournament` ML path as structurally dead: training never persists, serving never loads, and it produces 0 picks silently.
- `application/cli/ml_commands.py:63-89` exposes `run-tournament`, builds `WeeklyTournamentUseCase`, calls `execute()`, and prints the resulting report.
- `application/use_cases.py:341-395` scores tickers, catches per-ticker exceptions, sorts remaining candidates, saves recommendations, saves a weekly report, and logs the count.
- `application/use_cases.py:550-559` calls predictor methods directly for each horizon.

## Corroboration Weekly Cadence Pieces

- `application/cli/corroboration_commands.py:18-26` exposes the `corroborate` command and labels it `RESEARCH_ONLY`.
- `application/cli/corroboration_commands.py:61-83` performs the free search through `ddgs` with fallback to `duckduckgo_search`, returning an empty list if search fails.
- `application/cli/corroboration_commands.py:98-101` opens `data/recommendations.db` and initializes `CorroborationStore`.
- `application/cli/corroboration_commands.py:117-170` runs the use case and prints the `RESEARCH_ONLY` banner before and after output.
- `pyproject.toml:11-29` lists runtime dependencies and does not include `ddgs` or `duckduckgo_search`.
- `pyproject.toml:90-114` and `pyproject.toml:175-181` contain mypy configuration for `ddgs` / `duckduckgo_search`, which means type config already knows about the module names even though runtime dependencies do not list them.

## Existing Scheduling Evidence

- No Python, YAML, TOML, or Markdown file in the current branch defines an implemented `resolve-corroboration` command.
- Existing docs discuss launchd/cron patterns in older plans, but the SP5 brief is where `resolve-corroboration` is introduced as future scope.
