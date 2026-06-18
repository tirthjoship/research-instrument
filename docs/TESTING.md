# Testing

## Make targets (use the narrowest one that covers your change)

| Target | When to use | Typical time |
|---|---|---|
| `make test-tab tab=<name>` | Editing any dashboard tab | <15s |
| `pytest tests/test_<file>.py -q` | Editing one CLI command or adapter | <5s |
| `make test-domain` | Editing `domain/` | <10s |
| `make test-adapters` | Editing `adapters/` | <20s |
| `make test-smoke` | Before every commit (cross-cutting sanity) | ~14s |
| `make test-fast` | Cross-cutting change, unsure of scope | ~35s |
| `make check` | Before PR only — full gate (lint + mypy + test-cov) | ~22 min |

**Never run `make check` during iterative edits.** It runs coverage which serialises
output and dominates wall-clock. Reserve it for PR checkpoints.

Tab names for `make test-tab`: `risk`, `weekly_brief`, `research`, `screener`, `positions`, `trust`

---

## Pytest markers

Defined in `pyproject.toml` under `[tool.pytest.ini_options].markers`:

| Marker | What it covers |
|---|---|
| `smoke` | Critical regression guard — ~264 tests, ~14s. Runs in CI on every push. |
| `tab_risk` | Risk tab tests |
| `tab_weekly_brief` | Weekly brief tab tests |
| `tab_research` | Research candidates tab tests |
| `tab_screener` | Screener tab tests |
| `tab_positions` | Positions tab tests |
| `tab_trust` | Trust tab tests |

Add `@pytest.mark.smoke` to: Hypothesis property tests, port contract tests, critical
use-case integration paths. Never add it to Streamlit rendering tests (too slow).

---

## Test structure

```
tests/
  fakes/                 Test doubles for ALL domain ports — always use these, never mock
  conftest.py            Single autouse fixture: strips live API keys from env
  domain/                Unit tests for domain/ models and services
  adapters/              Unit tests for adapter implementations
  application/           Integration tests for use cases
  test_opportunity_cli.py  CLI smoke tests (Click CliRunner)
  test_cli_weekly_brief.py Weekly brief CLI integration
  test_risk_tab.py       Risk tab render tests
  test_research_candidates*.py  Research tab tests
  …
```

---

## Rules

**Use fakes, not mocks.** `tests/fakes/` has a fake for every domain port. Mocks
break when interfaces change; fakes fail loudly and stay in sync with the Protocol.

**Small fixtures.** Never use real yfinance/Reddit/GDELT calls in tests. Fixtures are
hand-crafted minimal datasets (3–10 rows). Hypothesis handles edge-case enumeration.

**Property tests for invariants.** Any domain invariant that holds for all inputs
(e.g. signal grades are monotone, look-ahead bias is always raised) gets a Hypothesis
`@given` test, not a table of examples.

**`conftest.py` is minimal.** One autouse fixture that strips `GEMINI_API_KEY` and
`YFINANCE_*` from `os.environ`. No session-scoped fixtures that write to disk.

---

## Monkeypatch targets after cli.py decomposition (2026-06-18)

After `cli.py` was split into `application/cli/` subpackage, tests that patched
`application.cli.X` needed updating. The rule:

- **Eager top-level import** (`from application.foo import Bar` at module top) →
  patch in the submodule that owns it, e.g. `application.cli.data_commands.DripBackfillUseCase`
- **Lazy import inside function body** (`from application.foo import Bar` inside the function) →
  patch at the source module, e.g. `application.opportunity_scan_use_case.OpportunityScanUseCase`
- **Shared helpers re-exported from `__init__.py`** (`_build_dependencies`, `_get_ticker_universe`, etc.) →
  patch in the submodule where the command function actually uses it

Quick reference:

| Symbol | Correct patch target |
|---|---|
| `OpportunityScanUseCase` | `application.opportunity_scan_use_case` (lazy) |
| `DripBackfillUseCase` | `application.cli.data_commands` |
| `DivergenceICBacktestUseCase` | `application.cli.validation_commands` |
| `WikipediaArticleResolver` | `application.cli.data_commands` |
| `PortfolioVerdictUseCase` | `application.cli.portfolio_commands` |
| `HoldingsRiskAssessmentUseCase` | `application.cli.portfolio_commands` |
| `_build_dependencies` | `application.cli.validation_commands` (or whichever submodule's command uses it) |
| `load_price_series` (adherence) | `application.cli.validation_commands` |
| `build_risk_second_opinion` | `application.risk_second_opinion` (lazy import in brief_commands) |

---

## Coverage gate

`make check` enforces `--cov-fail-under=90`. Current: **93%**.

Coverage is measured over `domain/`, `adapters/`, `application/`. Test files and
`scripts/` are excluded. Do not add tests purely to hit the number — meaningful
coverage comes from testing real behaviour paths, not line-touching.

---

## Why the smoke suite exists (2026-06-17, ADR-061)

Before the efficiency overhaul, the only gate was `make check` at 484s (serial +
verbose). Developers were either skipping it (CI surprise) or running it after every
edit (slow + token-heavy).

The smoke suite gives a 14s sanity check that covers: all Hypothesis property tests,
all port contract tests, and the critical weekly-brief / evidence-screen / discipline
pipelines. It is not a substitute for `make check` at PR time — it is the between-edit
checkpoint.
