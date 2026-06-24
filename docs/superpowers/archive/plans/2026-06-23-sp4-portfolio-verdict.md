# SP4: Portfolio-Verdict Corroboration Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire corroboration evidence (sources, stance, directional sector tilts) into the weekly brief so the user sees attributed third-party views on their holdings alongside discipline flags — RESEARCH_ONLY, no buy/sell instructions.

**Architecture:** Add `net_stance: Stance` to `CorroborationSnapshot`; extend `HoldingVerdictLine` with 3 optional corroboration fields and `WeeklyBrief` with `directional_views`; inject a `CorroborationSnapshotFn` callable into `WeeklyBriefUseCase`; render inline evidence suffix per holding in `to_markdown()` and a tilt section in both renderers.

**Tech Stack:** Python 3.12, dataclasses (frozen), pytest, click, sqlite3 (via `CorroborationStore`).

## Global Constraints

- All domain types (`domain/`) must have zero external imports — stdlib only.
- `HoldingVerdictLine` and `WeeklyBrief` are frozen dataclasses — add new fields with defaults so all existing callers compile without changes.
- RESEARCH_ONLY label maintained per ADR-049: no buy/sell language anywhere in new output.
- Tests use fakes only — no live yfinance/Gemini/SQLite calls.
- Run `make test-fast` (not `make check`) after each task during iteration.
- All new test files go under `tests/` matching existing naming patterns.
- Commit after each task using conventional commit format (`feat:` / `fix:` / `test:`).
- Branch: `feat/sp4-portfolio-verdict` off `develop`.

---

### Task 1: Add `net_stance` to `CorroborationSnapshot` + populate in store

**Files:**
- Modify: `domain/screened_row.py`
- Modify: `adapters/data/corroboration_store.py` (function `_claims_to_snapshots`)
- Create: `tests/adapters/test_corroboration_store_net_stance.py`

**Interfaces:**
- Produces: `CorroborationSnapshot.net_stance: Stance` — consumed by Tasks 2, 3, 4.
- `_claims_to_snapshots(claims, run_date)` returns `list[CorroborationSnapshot]` with `net_stance` set.

- [ ] **Step 1: Create the test file with a failing test**

```python
# tests/adapters/test_corroboration_store_net_stance.py
from datetime import date

import pytest

from adapters.data.corroboration_store import _claims_to_snapshots
from domain.corroboration_models import HarvestedClaim, Stance, ConvergenceTier
from domain.screened_row import CorroborationSnapshot


def _claim(ticker: str, stance: Stance, verified: bool = True) -> HarvestedClaim:
    return HarvestedClaim(
        source_name="Example",
        ticker=ticker,
        stance=stance,
        thesis_summary="thesis",
        url="https://example.com",
        published_at=date(2026, 6, 23),
        verified=verified,
        reliability_weight=1.0,
    )


def test_net_stance_bullish_majority() -> None:
    claims = [
        _claim("AAPL", Stance.BULLISH),
        _claim("AAPL", Stance.BULLISH),
        _claim("AAPL", Stance.BEARISH),
    ]
    snaps = _claims_to_snapshots(claims, date(2026, 6, 23))
    assert len(snaps) == 1
    assert snaps[0].net_stance == Stance.BULLISH


def test_net_stance_bearish_majority() -> None:
    claims = [
        _claim("MSFT", Stance.BEARISH),
        _claim("MSFT", Stance.BEARISH),
        _claim("MSFT", Stance.BULLISH),
    ]
    snaps = _claims_to_snapshots(claims, date(2026, 6, 23))
    assert snaps[0].net_stance == Stance.BEARISH


def test_net_stance_neutral_on_tie() -> None:
    claims = [
        _claim("TSLA", Stance.BULLISH),
        _claim("TSLA", Stance.BEARISH),
    ]
    snaps = _claims_to_snapshots(claims, date(2026, 6, 23))
    assert snaps[0].net_stance == Stance.NEUTRAL


def test_unverified_claims_excluded_from_net_stance() -> None:
    claims = [
        _claim("NVDA", Stance.BULLISH, verified=True),
        _claim("NVDA", Stance.BEARISH, verified=False),  # excluded
    ]
    snaps = _claims_to_snapshots(claims, date(2026, 6, 23))
    assert snaps[0].net_stance == Stance.BULLISH
```

- [ ] **Step 2: Run to verify it fails**

```bash
pytest tests/adapters/test_corroboration_store_net_stance.py -v
```

Expected: `ImportError` or `AttributeError` — `CorroborationSnapshot` has no `net_stance`.

- [ ] **Step 3: Add `net_stance` field to `CorroborationSnapshot` in `domain/screened_row.py`**

Current file starts with:
```python
from domain.corroboration_models import ConvergenceTier
```

Change to:
```python
from domain.corroboration_models import ConvergenceTier, Stance
```

Change the dataclass from:
```python
@dataclass(frozen=True)
class CorroborationSnapshot:
    ticker: str
    convergence_tier: ConvergenceTier
    n_sources: int
    surfaced_at: date
```

To:
```python
@dataclass(frozen=True)
class CorroborationSnapshot:
    ticker: str
    convergence_tier: ConvergenceTier
    n_sources: int
    surfaced_at: date
    net_stance: Stance = Stance.NEUTRAL
```

- [ ] **Step 4: Populate `net_stance` in `_claims_to_snapshots()` in `adapters/data/corroboration_store.py`**

Find `_claims_to_snapshots` at the bottom of the file. Current body builds `CorroborationSnapshot(ticker=ticker, convergence_tier=tier, n_sources=len(verified_claims), surfaced_at=run_date)`.

Replace the snapshots.append call with:

```python
        bullish_n = sum(1 for c in verified_claims if c.stance == Stance.BULLISH)
        bearish_n = sum(1 for c in verified_claims if c.stance == Stance.BEARISH)
        if bullish_n > bearish_n:
            net_stance = Stance.BULLISH
        elif bearish_n > bullish_n:
            net_stance = Stance.BEARISH
        else:
            net_stance = Stance.NEUTRAL
        snapshots.append(
            CorroborationSnapshot(
                ticker=ticker,
                convergence_tier=tier,
                n_sources=len(verified_claims),
                surfaced_at=run_date,
                net_stance=net_stance,
            )
        )
```

Note: `bullish` and `bearish` counts are already computed above in the existing loop (for tier derivation) — reuse them, don't recompute. Check the existing variable names in the function body first and reuse if already there.

- [ ] **Step 5: Run tests**

```bash
pytest tests/adapters/test_corroboration_store_net_stance.py -v
```

Expected: 4 PASSED.

Also run existing snapshot tests to check no regression:
```bash
pytest tests/adapters/test_corroboration_store_snapshots.py -v
```

Expected: all PASSED.

- [ ] **Step 6: Typecheck**

```bash
make typecheck
```

Expected: `Success: no issues found in N source files`.

- [ ] **Step 7: Commit**

```bash
git add domain/screened_row.py adapters/data/corroboration_store.py tests/adapters/test_corroboration_store_net_stance.py
git commit -m "feat(domain): add net_stance to CorroborationSnapshot, populate in _claims_to_snapshots"
```

---

### Task 2: Extend `HoldingVerdictLine`, `WeeklyBrief`, and `assemble_brief()`

**Files:**
- Modify: `domain/brief.py`
- Create: `tests/domain/test_brief_sp4.py`

**Interfaces:**
- Consumes: `CorroborationSnapshot.net_stance` (Task 1), `ConvergenceTier`, `Stance` from `domain.corroboration_models`, `DirectionalView` from `domain.corroboration_models`.
- Produces:
  - `HoldingVerdictLine` with optional fields `convergence_tier: ConvergenceTier | None`, `n_sources: int | None`, `source_stance: Stance | None`
  - `WeeklyBrief.directional_views: tuple[DirectionalView, ...]`
  - `assemble_brief(..., corroboration_map: dict[str, CorroborationSnapshot] | None = None, directional_views: list[DirectionalView] | None = None) -> WeeklyBrief`

- [ ] **Step 1: Write failing tests**

```python
# tests/domain/test_brief_sp4.py
from datetime import date

import pytest

from domain.brief import HoldingVerdictLine, WeeklyBrief, assemble_brief
from domain.corroboration_models import ConvergenceTier, DirectionalView, Stance
from domain.discipline import Verdict
from domain.screened_row import CorroborationSnapshot


def _make_snapshot(
    ticker: str,
    tier: ConvergenceTier = ConvergenceTier.STRONG,
    n: int = 3,
    stance: Stance = Stance.BULLISH,
) -> CorroborationSnapshot:
    return CorroborationSnapshot(
        ticker=ticker,
        convergence_tier=tier,
        n_sources=n,
        surfaced_at=date(2026, 6, 23),
        net_stance=stance,
    )


def test_holding_verdict_line_corroboration_fields_default_none() -> None:
    line = HoldingVerdictLine(
        ticker="AAPL",
        unrealized_pct=0.12,
        trend_state="uptrend",
        verdict=Verdict.HOLD,
        why="momentum ok",
    )
    assert line.convergence_tier is None
    assert line.n_sources is None
    assert line.source_stance is None


def test_assemble_brief_enriches_holdings_from_corroboration_map(
    minimal_brief_kwargs: dict,
) -> None:
    snap = _make_snapshot("AAPL", ConvergenceTier.STRONG, 3, Stance.BULLISH)
    brief = assemble_brief(**minimal_brief_kwargs, corroboration_map={"AAPL": snap})
    aapl_line = next(h for h in brief.holdings if h.ticker == "AAPL")
    assert aapl_line.convergence_tier == ConvergenceTier.STRONG
    assert aapl_line.n_sources == 3
    assert aapl_line.source_stance == Stance.BULLISH


def test_assemble_brief_leaves_missing_tickers_as_none(
    minimal_brief_kwargs: dict,
) -> None:
    # AAPL in holdings but no snapshot — fields remain None
    brief = assemble_brief(**minimal_brief_kwargs, corroboration_map={})
    aapl_line = next(h for h in brief.holdings if h.ticker == "AAPL")
    assert aapl_line.convergence_tier is None


def test_assemble_brief_no_corroboration_map_is_safe(
    minimal_brief_kwargs: dict,
) -> None:
    brief = assemble_brief(**minimal_brief_kwargs)
    assert all(h.convergence_tier is None for h in brief.holdings)


def test_weekly_brief_directional_views_default_empty(
    minimal_brief_kwargs: dict,
) -> None:
    brief = assemble_brief(**minimal_brief_kwargs)
    assert brief.directional_views == ()


def test_weekly_brief_stores_directional_views(minimal_brief_kwargs: dict) -> None:
    view = DirectionalView(
        group_kind="sector",
        group_name="Technology",
        net_stance=Stance.BULLISH,
        mean_convergence=0.8,
        your_exposure_pct=0.15,
        evidence_weight_pct=0.25,
        tilt="LEAN_IN",
    )
    brief = assemble_brief(**minimal_brief_kwargs, directional_views=[view])
    assert len(brief.directional_views) == 1
    assert brief.directional_views[0].tilt == "LEAN_IN"
```

Add a `minimal_brief_kwargs` fixture to `tests/conftest.py` (or inline in the test file as a function). Check `tests/conftest.py` first — if a similar fixture exists, extend it. Otherwise define it locally:

```python
# At top of tests/domain/test_brief_sp4.py (if no shared fixture available)
import pytest
from domain.brief import assemble_brief
from domain.regime import Regime
from domain.screen_models import ScreenLabel, ScreenResult
from domain.models import PositionRisk, PortfolioRisk
from domain.brief import ScorecardSnapshot

@pytest.fixture
def minimal_brief_kwargs() -> dict:
    return dict(
        as_of="2026-06-23",
        regime=Regime.BULL,
        tilt={"momentum": 0.5, "revision": 0.3, "quality": 0.1, "value": 0.1},
        screen_result=ScreenResult(candidates=[], abstained=False),
        screen_label=ScreenLabel.RESEARCH_ONLY,
        top_n=5,
        positions=[
            PositionRisk(
                ticker="AAPL",
                unrealized_pct=0.12,
                trend_health=0.5,
                verdict=Verdict.HOLD,
                why="ok",
            )
        ],
        portfolio=PortfolioRisk(top_concentration=0.10),
        held_tickers={"AAPL"},
        cluster_overlaps={},
        scorecard=ScorecardSnapshot(
            screen_window="2026-06-23",
            screen_top_ret=None,
            screen_spy_ret=None,
            screen_n=0,
            screen_significant=False,
            discipline_window="21d",
            discipline_reduce_down_rate=None,
            discipline_n=0,
            discipline_gate_status="OPEN",
        ),
    )
```

**Important:** Check the actual signatures of `PositionRisk`, `PortfolioRisk`, `ScreenResult`, `ScorecardSnapshot` in the codebase before writing the fixture — field names may differ. Run `grep -n "class PositionRisk\|class PortfolioRisk\|class ScreenResult\|class ScorecardSnapshot" domain/models.py domain/brief.py domain/screen_models.py` first and adjust.

- [ ] **Step 2: Run to verify tests fail**

```bash
pytest tests/domain/test_brief_sp4.py -v
```

Expected: `AttributeError` or `TypeError` — `HoldingVerdictLine` has no `convergence_tier`.

- [ ] **Step 3: Extend `HoldingVerdictLine` in `domain/brief.py`**

Add imports at top of `domain/brief.py` (after existing imports):
```python
from domain.corroboration_models import ConvergenceTier, DirectionalView, Stance
from domain.screened_row import CorroborationSnapshot
```

Extend `HoldingVerdictLine`:
```python
@dataclass(frozen=True)
class HoldingVerdictLine:
    ticker: str
    unrealized_pct: float
    trend_state: str
    verdict: Verdict
    why: str
    convergence_tier: ConvergenceTier | None = None
    n_sources: int | None = None
    source_stance: Stance | None = None
```

- [ ] **Step 4: Add `directional_views` to `WeeklyBrief`**

In the `WeeklyBrief` dataclass, after the `abstained` field:
```python
    directional_views: tuple[DirectionalView, ...] = ()
```

- [ ] **Step 5: Update `assemble_brief()` signature and body**

Add two new keyword-only params with defaults (existing callers unaffected):
```python
def assemble_brief(
    *,
    as_of: str,
    regime: Regime,
    tilt: dict[str, float],
    screen_result: ScreenResult,
    screen_label: ScreenLabel,
    top_n: int,
    positions: list[PositionRisk],
    portfolio: PortfolioRisk,
    held_tickers: set[str],
    cluster_overlaps: dict[str, list[str]],
    scorecard: ScorecardSnapshot,
    concentration_threshold: float = 0.20,
    macro: BookMacroExposure | None = None,
    corroboration_map: dict[str, CorroborationSnapshot] | None = None,
    directional_views: list[DirectionalView] | None = None,
) -> WeeklyBrief:
```

In the holdings construction block (where `HoldingVerdictLine` objects are built), enrich from the map:
```python
    _corr = corroboration_map or {}
    holdings = tuple(
        sorted(
            [
                HoldingVerdictLine(
                    ticker=p.ticker,
                    unrealized_pct=p.unrealized_pct,
                    trend_state=_trend_state(p.trend_health),
                    verdict=p.verdict,
                    why=p.why,
                    convergence_tier=_corr[p.ticker].convergence_tier if p.ticker in _corr else None,
                    n_sources=_corr[p.ticker].n_sources if p.ticker in _corr else None,
                    source_stance=_corr[p.ticker].net_stance if p.ticker in _corr else None,
                )
                for p in positions
            ],
            key=lambda h: _VERDICT_ORDER.get(h.verdict, 99),
        )
    )
```

In the `WeeklyBrief(...)` constructor call at the end of `assemble_brief`, add:
```python
        directional_views=tuple(directional_views) if directional_views else (),
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/domain/test_brief_sp4.py -v
```

Expected: all PASSED.

Run regression check:
```bash
pytest tests/domain/ -q
```

Expected: no new failures.

- [ ] **Step 7: Typecheck**

```bash
make typecheck
```

Expected: `Success`.

- [ ] **Step 8: Commit**

```bash
git add domain/brief.py domain/screened_row.py tests/domain/test_brief_sp4.py
git commit -m "feat(domain): extend HoldingVerdictLine + WeeklyBrief with corroboration fields"
```

---

### Task 3: `CorroborationSnapshotFn` + `_build_directional_views()` in `WeeklyBriefUseCase`

**Files:**
- Modify: `application/weekly_brief_use_case.py`
- Create: `tests/test_weekly_brief_use_case_sp4.py`

**Interfaces:**
- Consumes: `CorroborationSnapshot` (Task 1), `assemble_brief(corroboration_map=..., directional_views=...)` (Task 2), `SectorProvider.sector(ticker) -> str` (already in adapters).
- Produces:
  - `CorroborationSnapshotFn = Callable[[date], list[CorroborationSnapshot]]`
  - `WeeklyBriefUseCase.__init__(..., corroboration_fn: CorroborationSnapshotFn | None = None, sector_provider: Any | None = None)`
  - `_build_directional_views(groups: dict[str, list[CorroborationSnapshot]], exposure_pct: dict[str, float]) -> list[DirectionalView]` (module-level pure function)

- [ ] **Step 1: Write failing tests**

```python
# tests/test_weekly_brief_use_case_sp4.py
from datetime import date, datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest

from application.weekly_brief_use_case import (
    WeeklyBriefUseCase,
    _build_directional_views,
)
from domain.corroboration_models import ConvergenceTier, Stance
from domain.screened_row import CorroborationSnapshot


def _snap(ticker: str, tier: ConvergenceTier, stance: Stance) -> CorroborationSnapshot:
    return CorroborationSnapshot(
        ticker=ticker,
        convergence_tier=tier,
        n_sources=2,
        surfaced_at=date(2026, 6, 23),
        net_stance=stance,
    )


class FakeSectorProvider:
    def __init__(self, mapping: dict[str, str]) -> None:
        self._m = mapping

    def sector(self, ticker: str) -> str:
        return self._m.get(ticker, "Unknown")


def test_build_directional_views_lean_in() -> None:
    groups = {
        "Technology": [
            _snap("AAPL", ConvergenceTier.STRONG, Stance.BULLISH),
            _snap("MSFT", ConvergenceTier.STRONG, Stance.BULLISH),
        ]
    }
    exposure = {"Technology": 0.08}  # 8% — below evidence weight
    views = _build_directional_views(groups, exposure)
    assert len(views) == 1
    assert views[0].tilt == "LEAN_IN"
    assert views[0].group_name == "Technology"
    assert views[0].net_stance == Stance.BULLISH


def test_build_directional_views_lean_out() -> None:
    groups = {
        "Energy": [
            _snap("XOM", ConvergenceTier.MODERATE, Stance.BEARISH),
            _snap("CVX", ConvergenceTier.MODERATE, Stance.BEARISH),
        ]
    }
    exposure = {"Energy": 0.30}
    views = _build_directional_views(groups, exposure)
    assert views[0].tilt == "LEAN_OUT"


def test_build_directional_views_hold() -> None:
    groups = {
        "Healthcare": [_snap("JNJ", ConvergenceTier.WEAK, Stance.NEUTRAL)]
    }
    exposure = {"Healthcare": 0.10}
    views = _build_directional_views(groups, exposure)
    assert views[0].tilt == "HOLD"


def test_build_directional_views_empty_groups() -> None:
    assert _build_directional_views({}, {}) == []


def test_use_case_enriches_holdings_via_corroboration_fn(
    minimal_uc_kwargs: dict,
) -> None:
    snap = _snap("AAPL", ConvergenceTier.STRONG, Stance.BULLISH)
    uc = WeeklyBriefUseCase(
        **minimal_uc_kwargs,
        corroboration_fn=lambda _: [snap],
        sector_provider=FakeSectorProvider({"AAPL": "Technology"}),
    )
    brief = uc.execute(**minimal_execute_kwargs())
    aapl = next(h for h in brief.holdings if h.ticker == "AAPL")
    assert aapl.convergence_tier == ConvergenceTier.STRONG
    assert aapl.source_stance == Stance.BULLISH


def test_use_case_no_corroboration_fn_safe(minimal_uc_kwargs: dict) -> None:
    uc = WeeklyBriefUseCase(**minimal_uc_kwargs)
    brief = uc.execute(**minimal_execute_kwargs())
    assert all(h.convergence_tier is None for h in brief.holdings)
    assert brief.directional_views == ()


def test_use_case_empty_corroboration_fn_safe(minimal_uc_kwargs: dict) -> None:
    uc = WeeklyBriefUseCase(
        **minimal_uc_kwargs,
        corroboration_fn=lambda _: [],
    )
    brief = uc.execute(**minimal_execute_kwargs())
    assert all(h.convergence_tier is None for h in brief.holdings)
```

Add fixtures for `minimal_uc_kwargs` and `minimal_execute_kwargs()` — look at the existing `tests/test_weekly_brief_use_case.py` (if it exists) for the pattern; copy and adapt. The use case requires: `screen`, `holdings_risk`, `regime_reader`, `screen_label_fn`, `cluster_peers_fn`, `screen_scorecard_fn`, `discipline_scorecard_fn`. Use `MagicMock` for each, configured to return appropriate minimal values.

- [ ] **Step 2: Run to verify tests fail**

```bash
pytest tests/test_weekly_brief_use_case_sp4.py -v
```

Expected: `ImportError` — `_build_directional_views` not yet defined.

- [ ] **Step 3: Add type alias and `_build_directional_views()` to `application/weekly_brief_use_case.py`**

Add imports at the top:
```python
from datetime import date as _date
from domain.corroboration_models import (
    ConvergenceTier,
    DirectionalView,
    Stance,
)
from domain.screened_row import CorroborationSnapshot
```

Add type alias after existing type aliases (near top of file, after `MacroFn`):
```python
CorroborationSnapshotFn = Callable[[_date], list[CorroborationSnapshot]]
```

Add module-level pure helper function (before `WeeklyBriefUseCase` class):
```python
_TIER_NUM: dict[ConvergenceTier, float] = {
    ConvergenceTier.STRONG: 1.0,
    ConvergenceTier.MODERATE: 0.6,
    ConvergenceTier.WEAK: 0.3,
    ConvergenceTier.CONFLICTED: 0.1,
    ConvergenceTier.NONE: 0.0,
}


def _build_directional_views(
    groups: dict[str, list[CorroborationSnapshot]],
    exposure_pct: dict[str, float],
) -> list[DirectionalView]:
    """Compute DirectionalView per sector from snapshot groups. Pure — no IO."""
    views: list[DirectionalView] = []
    for sector, snaps in groups.items():
        if not snaps:
            continue
        mean_conv = sum(_TIER_NUM[s.convergence_tier] for s in snaps) / len(snaps)
        bullish_n = sum(1 for s in snaps if s.net_stance == Stance.BULLISH)
        bearish_n = sum(1 for s in snaps if s.net_stance == Stance.BEARISH)
        if bullish_n > bearish_n:
            net_stance = Stance.BULLISH
        elif bearish_n > bullish_n:
            net_stance = Stance.BEARISH
        else:
            net_stance = Stance.NEUTRAL
        yours = exposure_pct.get(sector, 0.0)
        ev_weight = mean_conv * 100.0
        # Tilt logic mirrors CorroborationService._tilt()
        if net_stance is Stance.BEARISH and mean_conv >= 0.6:
            tilt = "LEAN_OUT" if yours > 0 else "AVOID"
        elif net_stance is Stance.BULLISH and mean_conv >= 0.6 and yours * 100 < ev_weight * 0.5:
            tilt = "LEAN_IN"
        else:
            tilt = "HOLD"
        views.append(
            DirectionalView(
                group_kind="sector",
                group_name=sector,
                net_stance=net_stance,
                mean_convergence=mean_conv,
                your_exposure_pct=yours,
                evidence_weight_pct=ev_weight,
                tilt=tilt,
            )
        )
    return views
```

- [ ] **Step 4: Extend `WeeklyBriefUseCase.__init__()` with new optional params**

Add to `__init__` signature:
```python
    corroboration_fn: "CorroborationSnapshotFn | None" = None,
    sector_provider: "Any | None" = None,
```

Store:
```python
        self._corroboration_fn = corroboration_fn
        self._sector_provider = sector_provider
```

- [ ] **Step 5: Wire enrichment in `execute()` (the method is named `execute`, not `run`)**

After `risk = self._holdings.execute(holdings, start, as_of)` and before `assemble_brief(...)`:

```python
        # SP4: corroboration enrichment
        as_of_date = as_of.date()
        corr_map: dict[str, CorroborationSnapshot] = {}
        directional_views: list[DirectionalView] = []
        if self._corroboration_fn is not None:
            snapshots = self._corroboration_fn(as_of_date)
            corr_map = {s.ticker: s for s in snapshots}
            if self._sector_provider is not None and corr_map:
                # Group held tickers that have corroboration by sector
                sector_groups: dict[str, list[CorroborationSnapshot]] = {}
                for h in holdings:
                    if h.ticker in corr_map:
                        sector = self._sector_provider.sector(h.ticker)
                        sector_groups.setdefault(sector, []).append(corr_map[h.ticker])
                # Equal-weight exposure per sector
                total = len(holdings) or 1
                sector_counts = {
                    self._sector_provider.sector(h.ticker): 0 for h in holdings
                }
                for h in holdings:
                    sector_counts[self._sector_provider.sector(h.ticker)] += 1
                exposure_pct = {s: c / total for s, c in sector_counts.items()}
                directional_views = _build_directional_views(sector_groups, exposure_pct)
```

In the `assemble_brief(...)` call, add:
```python
            corroboration_map=corr_map,
            directional_views=directional_views,
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_weekly_brief_use_case_sp4.py -v
```

Expected: all PASSED.

Regression check:
```bash
make test-fast
```

Expected: no new failures.

- [ ] **Step 7: Typecheck**

```bash
make typecheck
```

Expected: `Success`.

- [ ] **Step 8: Commit**

```bash
git add application/weekly_brief_use_case.py tests/test_weekly_brief_use_case_sp4.py
git commit -m "feat(application): add CorroborationSnapshotFn + _build_directional_views to WeeklyBriefUseCase"
```

---

### Task 4: Wire CLI + render inline evidence + tilt section + footer

**Files:**
- Modify: `application/cli/brief_commands.py`
- Modify: `domain/brief.py` (renderers `to_markdown`, `to_stdout_masked`)
- Create: `tests/test_cli_brief_commands_sp4.py`

**Interfaces:**
- Consumes: `HoldingVerdictLine.convergence_tier`, `.n_sources`, `.source_stance` (Task 2); `WeeklyBrief.directional_views` (Task 2); `WeeklyBriefUseCase(corroboration_fn=..., sector_provider=...)` (Task 3).
- Produces: CLI output with inline `│ sources:` per holding (in `to_markdown`); tilt section after holdings (in both renderers); footer in `to_markdown`.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_cli_brief_commands_sp4.py
import pytest
from domain.brief import HoldingVerdictLine, WeeklyBrief, to_markdown, to_stdout_masked
from domain.corroboration_models import ConvergenceTier, DirectionalView, Stance
from domain.discipline import Verdict


def _holding(
    ticker: str = "AAPL",
    verdict: Verdict = Verdict.HOLD,
    tier: ConvergenceTier | None = None,
    n: int | None = None,
    stance: Stance | None = None,
) -> HoldingVerdictLine:
    return HoldingVerdictLine(
        ticker=ticker,
        unrealized_pct=0.12,
        trend_state="uptrend",
        verdict=verdict,
        why="momentum ok",
        convergence_tier=tier,
        n_sources=n,
        source_stance=stance,
    )


def _view(
    name: str = "Technology",
    tilt: str = "LEAN_IN",
    stance: Stance = Stance.BULLISH,
    tier: ConvergenceTier = ConvergenceTier.STRONG,
    yours: float = 0.08,
) -> DirectionalView:
    return DirectionalView(
        group_kind="sector",
        group_name=name,
        net_stance=stance,
        mean_convergence=1.0,
        your_exposure_pct=yours,
        evidence_weight_pct=100.0,
        tilt=tilt,
    )


def _minimal_brief(
    holdings: list[HoldingVerdictLine],
    views: list[DirectionalView] | None = None,
) -> WeeklyBrief:
    # Build a minimal WeeklyBrief for renderer tests.
    # Import and construct directly — do NOT call assemble_brief (adds complexity).
    from domain.brief import ScorecardSnapshot, WeeklyBrief
    from domain.regime import Regime
    from domain.screen_models import ScreenLabel

    return WeeklyBrief(
        as_of="2026-06-23",
        regime=Regime.BULL,
        tilt={"momentum": 0.5, "revision": 0.3, "quality": 0.1, "value": 0.1},
        candidates=(),
        holdings=tuple(holdings),
        research_links=(),
        concentration=(),
        scorecard=ScorecardSnapshot(
            screen_window="2026-06-23",
            screen_top_ret=None,
            screen_spy_ret=None,
            screen_n=0,
            screen_significant=False,
            discipline_window="21d",
            discipline_reduce_down_rate=None,
            discipline_n=0,
            discipline_gate_status="OPEN",
        ),
        screen_label=ScreenLabel.RESEARCH_ONLY,
        directional_views=tuple(views or []),
    )


def test_to_markdown_shows_inline_sources_for_corroborated_holding() -> None:
    h = _holding(tier=ConvergenceTier.STRONG, n=3, stance=Stance.BULLISH)
    brief = _minimal_brief([h])
    md = to_markdown(brief)
    assert "│ sources: BULLISH ×3 [STRONG]" in md


def test_to_markdown_no_sources_segment_when_no_snapshot() -> None:
    h = _holding()  # no corroboration
    brief = _minimal_brief([h])
    md = to_markdown(brief)
    assert "│ sources:" not in md


def test_to_markdown_shows_conflict_marker() -> None:
    h = _holding(verdict=Verdict.REDUCE, tier=ConvergenceTier.MODERATE, n=2, stance=Stance.BULLISH)
    brief = _minimal_brief([h])
    md = to_markdown(brief)
    assert "⚠ CONFLICT" in md


def test_to_markdown_no_conflict_when_aligned() -> None:
    h = _holding(verdict=Verdict.HOLD, tier=ConvergenceTier.STRONG, n=3, stance=Stance.BULLISH)
    brief = _minimal_brief([h])
    md = to_markdown(brief)
    assert "⚠ CONFLICT" not in md


def test_to_markdown_shows_tilt_section() -> None:
    view = _view("Technology", "LEAN_IN", Stance.BULLISH)
    brief = _minimal_brief([_holding()], views=[view])
    md = to_markdown(brief)
    assert "Directional Tilts" in md
    assert "LEAN_IN" in md
    assert "Technology" in md
    assert "RESEARCH_ONLY" in md


def test_to_markdown_no_tilt_section_when_no_views() -> None:
    brief = _minimal_brief([_holding()])
    md = to_markdown(brief)
    assert "Directional Tilts" not in md


def test_to_markdown_footer_when_missing_snapshots() -> None:
    h1 = _holding("AAPL", tier=ConvergenceTier.STRONG, n=3, stance=Stance.BULLISH)
    h2 = _holding("MSFT")  # no snapshot
    brief = _minimal_brief([h1, h2])
    md = to_markdown(brief)
    assert "1 holding(s) have no corroboration snapshot" in md


def test_to_markdown_no_footer_when_all_corroborated() -> None:
    h = _holding(tier=ConvergenceTier.STRONG, n=3, stance=Stance.BULLISH)
    brief = _minimal_brief([h])
    md = to_markdown(brief)
    assert "no corroboration snapshot" not in md


def test_to_stdout_masked_shows_tilt_section() -> None:
    view = _view("Energy", "LEAN_OUT", Stance.BEARISH)
    brief = _minimal_brief([_holding()], views=[view])
    out = to_stdout_masked(brief)
    assert "Directional Tilts" in out
    assert "LEAN_OUT" in out
    assert "Energy" in out


def test_to_stdout_masked_no_per_holding_sources() -> None:
    # Masked output must never reveal per-holding detail
    h = _holding(tier=ConvergenceTier.STRONG, n=3, stance=Stance.BULLISH)
    brief = _minimal_brief([h])
    out = to_stdout_masked(brief)
    assert "│ sources:" not in out
    assert "AAPL" not in out  # ticker masked
```

- [ ] **Step 2: Run to verify tests fail**

```bash
pytest tests/test_cli_brief_commands_sp4.py -v
```

Expected: multiple failures — `to_markdown` / `to_stdout_masked` don't render corroboration yet.

- [ ] **Step 3: Update `to_markdown()` in `domain/brief.py`**

In the holdings section of `to_markdown()`, find the line that appends holding lines and replace with:

```python
    lines.append("## HOLDINGS")
    for h in brief.holdings:
        base = (
            f"- **{h.ticker}** {h.verdict.value} "
            f"{h.unrealized_pct:+.1%} {h.trend_state} — {h.why}"
        )
        if h.convergence_tier is not None and h.n_sources is not None and h.source_stance is not None:
            tier_label = h.convergence_tier.value  # e.g. "STRONG"
            src_line = f"│ sources: {h.source_stance.value} ×{h.n_sources} [{tier_label}]"
            conflict = _is_corroboration_conflict(h)
            if conflict:
                src_line += " ⚠ CONFLICT"
            base = base + "  " + src_line
        lines.append(base)
```

Add `_is_corroboration_conflict()` as a module-level helper in `domain/brief.py`:

```python
def _is_corroboration_conflict(h: HoldingVerdictLine) -> bool:
    if h.source_stance is None:
        return False
    bullish_but_reduce = h.source_stance == Stance.BULLISH and h.verdict in (
        Verdict.REDUCE,
        Verdict.TRIM,
    )
    bearish_but_add = h.source_stance == Stance.BEARISH and h.verdict == Verdict.ADD_OK
    return bullish_but_reduce or bearish_but_add
```

Add tilt section after holdings, before scorecard in `to_markdown()`:

```python
    if brief.directional_views:
        lines.append("")
        lines.append(
            "## Directional Tilts  [RESEARCH_ONLY — attributed evidence, not a prediction]"
        )
        for v in brief.directional_views:
            lines.append(
                f"- **{v.group_name}** {v.tilt}  "
                f"evidence: {v.net_stance.value}/{v.convergence_tier_label}  "
                f"your book: {v.your_exposure_pct:.0%}  "
                f"evidence weight: {v.evidence_weight_pct:.0f}%"
            )
```

**Note:** `DirectionalView` has no `convergence_tier_label` — use `mean_convergence` directly instead:
```python
                f"evidence: {v.net_stance.value} mean_conv={v.mean_convergence:.2f}  "
```

Add footer after tilt section, before scorecard:

```python
    missing_n = sum(1 for h in brief.holdings if h.convergence_tier is None)
    if missing_n > 0:
        lines.append("")
        lines.append(
            f"ⓘ {missing_n} holding(s) have no corroboration snapshot — "
            "run `corroborate` to populate."
        )
```

- [ ] **Step 4: Update `to_stdout_masked()` in `domain/brief.py`**

Add tilt section after the HOLDINGS masked line, before scorecard (masked output shows sector tilts — these are not per-ticker so not masked):

```python
    if brief.directional_views:
        lines.append("DIRECTIONAL TILTS (RESEARCH_ONLY):")
        for v in brief.directional_views:
            lines.append(
                f"  {v.group_name}: {v.tilt}  "
                f"({v.net_stance.value}, your book {v.your_exposure_pct:.0%})"
            )
```

Place this block after the existing `counts`/`HOLDINGS (masked)` line.

- [ ] **Step 5: Wire `CorroborationStore` + `SectorProvider` in `_build_weekly_brief()` in `application/cli/brief_commands.py`**

In `_build_weekly_brief()`, after `deps = _build_dependencies(market)`:

```python
    import sqlite3

    from adapters.data.corroboration_store import CorroborationStore
    from adapters.data.sector_provider import SectorProvider

    _conn = sqlite3.connect("data/recommendations.db")
    _corr_store = CorroborationStore(_conn)
    _sector_provider = SectorProvider()
```

In the `WeeklyBriefUseCase(...)` constructor call, add:
```python
        corroboration_fn=_corr_store.get_snapshots,
        sector_provider=_sector_provider,
```

**Note:** `CorroborationStore` takes a `sqlite3.Connection`, not a path string. The standard DB path used across all CLI commands is `"data/recommendations.db"` — confirmed by `corroboration_commands.py:99`.

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_cli_brief_commands_sp4.py -v
```

Expected: all PASSED.

Full regression:
```bash
make test-fast
```

Expected: no new failures (the pre-existing `test_cli_calibration_readiness.py` live-API timeout is a known flake — exclude if needed: `pytest --ignore=tests/test_cli_calibration_readiness.py -q`).

- [ ] **Step 7: Typecheck + lint**

```bash
make typecheck && make lint
```

Expected: both pass.

- [ ] **Step 8: Commit**

```bash
git add domain/brief.py application/cli/brief_commands.py tests/test_cli_brief_commands_sp4.py
git commit -m "feat(cli): render corroboration evidence inline + directional tilt section in weekly-brief"
```

---

## Self-Review Against Spec

| Spec requirement | Task |
|-----------------|------|
| `CorroborationSnapshot.net_stance` added | Task 1 |
| `_claims_to_snapshots()` populates net_stance | Task 1 |
| `HoldingVerdictLine` +3 optional fields, defaults None | Task 2 |
| `WeeklyBrief.directional_views` with empty default | Task 2 |
| `assemble_brief(corroboration_map=..., directional_views=...)` | Task 2 |
| `CorroborationSnapshotFn` type alias | Task 3 |
| `WeeklyBriefUseCase` injects callable + sector_provider | Task 3 |
| `_build_directional_views()` pure helper | Task 3 |
| Equal-weight exposure from holdings list | Task 3 |
| CLI: `│ sources: BULLISH ×3 [STRONG]` inline | Task 4 |
| CLI: `⚠ CONFLICT` when stance vs verdict mismatch | Task 4 |
| CLI: tilt section after holdings, before scorecard | Task 4 |
| CLI: footer when N holdings missing snapshots | Task 4 |
| `to_stdout_masked` tilt section (no per-ticker leak) | Task 4 |
| Unit tests only — no live adapters | All tasks |
| Existing callers unaffected (all new fields have defaults) | Tasks 2, 3 |
| RESEARCH_ONLY label on tilt section | Task 4 |
| `CorroborationStore` wired in `_build_weekly_brief()` | Task 4 |
| Dashboard rendering deferred to SP6 | ✓ (out of scope) |
