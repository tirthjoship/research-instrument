# SP3 Screener Revamp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Augment the screener with a corroboration overlay — each `ScreenCandidate` is optionally joined with SP2 analyst-corroboration data to produce a blended `ScreenedRow` rank; existing UI cards gain a corroboration badge + drill-down, zero breaking changes.

**Architecture:** Pure additive. New domain types (`CorroborationSnapshot`, `ScreenedRow`) and a pure domain service (`ScreenerCompositeService`) do the join and blending. `CorroborationStore` gains one read-only query method. CLI writes a new `screened_<date>.json` sidecar; dashboard tries it first, falls back to `screen_<date>.json`. All existing `ScreenCandidate` paths remain unchanged. RESEARCH_ONLY label and ADR-049 IC gate unchanged.

**Tech Stack:** Python 3.12, sqlite3 stdlib, mypy strict, pytest, Streamlit (dashboard only).

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `domain/screened_row.py` | **Create** | `CorroborationSnapshot`, `ScreenedRow`, blend formula constants |
| `domain/screener_composite_service.py` | **Create** | `ScreenerCompositeService.compose()` — pure, no IO |
| `adapters/data/corroboration_store.py` | **Modify** | Add `get_snapshots(as_of, window_days)` read method |
| `application/cli/screen_commands.py` | **Modify** | Wire composite service, write `screened_<date>.json`, print summary |
| `adapters/visualization/data_loader.py` | **Modify** | Add `load_latest_screened()` with fallback |
| `adapters/visualization/tabs/research_candidates.py` | **Modify** | Render corroboration badge + drill-down on each card |
| `tests/domain/test_screened_row.py` | **Create** | Unit tests for blend formula + `ScreenedRow` construction |
| `tests/domain/test_screener_composite_service.py` | **Create** | Unit tests for compose(), graceful degrade, ±7-day window |
| `tests/adapters/test_corroboration_store_snapshots.py` | **Create** | Unit tests for `get_snapshots()` |

---

## Task 1: Domain types — `CorroborationSnapshot` and `ScreenedRow`

**Files:**
- Create: `domain/screened_row.py`
- Create: `tests/domain/test_screened_row.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/domain/test_screened_row.py
from __future__ import annotations

from datetime import date

import pytest

from domain.corroboration_models import ConvergenceTier
from domain.screened_row import (
    CorroborationSnapshot,
    ScreenedRow,
    TIER_RANK,
    blend,
)
from domain.screen_models import ScreenCandidate, FactorScore


def _make_candidate(composite: float = 1.0) -> ScreenCandidate:
    fs = FactorScore(name="momentum", value=composite, percentile=0.9, contribution=0.2)
    return ScreenCandidate(
        ticker="AAPL",
        composite=composite,
        factor_scores=(fs,),
        trend_health=0.8,
        why="strong momentum",
        label="RESEARCH_ONLY",
    )


def _make_snap(tier: ConvergenceTier, n: int = 3) -> CorroborationSnapshot:
    return CorroborationSnapshot(
        ticker="AAPL",
        convergence_tier=tier,
        n_sources=n,
        surfaced_at=date(2026, 6, 21),
    )


def test_tier_rank_values() -> None:
    assert TIER_RANK[ConvergenceTier.STRONG] == 1.0
    assert TIER_RANK[ConvergenceTier.MODERATE] == pytest.approx(0.67)
    assert TIER_RANK[ConvergenceTier.WEAK] == pytest.approx(0.33)
    assert TIER_RANK[ConvergenceTier.CONFLICTED] == 0.0


def test_blend_strong_corroboration() -> None:
    result = blend(factor_pct=0.8, snap=_make_snap(ConvergenceTier.STRONG))
    assert result == pytest.approx(0.5 * 0.8 + 0.5 * 1.0)


def test_blend_no_corroboration_returns_factor_pct() -> None:
    assert blend(factor_pct=0.75, snap=None) == pytest.approx(0.75)


def test_blend_none_tier_returns_factor_pct() -> None:
    assert blend(factor_pct=0.6, snap=_make_snap(ConvergenceTier.NONE)) == pytest.approx(0.6)


def test_screened_row_factor_only_flag() -> None:
    row = ScreenedRow(
        candidate=_make_candidate(),
        corroboration=None,
        blended_percentile=0.75,
        factor_only=True,
    )
    assert row.factor_only is True
    assert row.corroboration is None
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender"
pytest tests/domain/test_screened_row.py -q
```

Expected: `ImportError` — `domain.screened_row` not found.

- [ ] **Step 3: Create `domain/screened_row.py`**

```python
"""SP3 composite screener types — ScreenedRow wraps ScreenCandidate + optional corroboration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from domain.corroboration_models import ConvergenceTier
from domain.screen_models import ScreenCandidate

TIER_RANK: dict[ConvergenceTier, float | None] = {
    ConvergenceTier.STRONG: 1.0,
    ConvergenceTier.MODERATE: 0.67,
    ConvergenceTier.WEAK: 0.33,
    ConvergenceTier.CONFLICTED: 0.0,
    ConvergenceTier.NONE: None,
}


@dataclass(frozen=True)
class CorroborationSnapshot:
    ticker: str
    convergence_tier: ConvergenceTier
    n_sources: int
    surfaced_at: date


@dataclass(frozen=True)
class ScreenedRow:
    candidate: ScreenCandidate
    corroboration: CorroborationSnapshot | None
    blended_percentile: float
    factor_only: bool


def blend(factor_pct: float, snap: CorroborationSnapshot | None) -> float:
    """Equal-weight rank-average of factor percentile and convergence tier rank.

    Returns factor_pct unchanged when no corroboration or tier is NONE.
    """
    if snap is None:
        return factor_pct
    tier_pct = TIER_RANK.get(snap.convergence_tier)
    if tier_pct is None:
        return factor_pct
    return 0.5 * factor_pct + 0.5 * tier_pct
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/domain/test_screened_row.py -q
```

Expected: `5 passed`.

- [ ] **Step 5: Typecheck**

```bash
uv run mypy domain/screened_row.py --strict
```

Expected: `Success: no issues found in 1 source file`.

- [ ] **Step 6: Commit**

```bash
git add domain/screened_row.py tests/domain/test_screened_row.py
git commit -m "feat(sp3): add CorroborationSnapshot + ScreenedRow domain types with blend formula"
```

---

## Task 2: Pure domain service — `ScreenerCompositeService`

**Files:**
- Create: `domain/screener_composite_service.py`
- Create: `tests/domain/test_screener_composite_service.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/domain/test_screener_composite_service.py
from __future__ import annotations

from datetime import date

import pytest

from domain.corroboration_models import ConvergenceTier
from domain.screen_models import ScreenCandidate, ScreenResult, FactorScore
from domain.screened_row import CorroborationSnapshot
from domain.screener_composite_service import ScreenerCompositeService


def _cand(ticker: str, composite: float) -> ScreenCandidate:
    fs = FactorScore(name="momentum", value=composite, percentile=0.5, contribution=0.2)
    return ScreenCandidate(
        ticker=ticker,
        composite=composite,
        factor_scores=(fs,),
        trend_health=0.5,
        why="",
        label="RESEARCH_ONLY",
    )


def _result(*composites: tuple[str, float]) -> ScreenResult:
    cands = tuple(_cand(t, c) for t, c in composites)
    return ScreenResult(
        as_of="2026-06-22",
        candidates=cands,
        universe_size=100,
        regime="NEUTRAL",
        scorecard_ref=None,
        abstained=False,
        diagnostics=None,
    )


def _snap(ticker: str, tier: ConvergenceTier) -> CorroborationSnapshot:
    return CorroborationSnapshot(
        ticker=ticker,
        convergence_tier=tier,
        n_sources=3,
        surfaced_at=date(2026, 6, 21),
    )


AS_OF = date(2026, 6, 22)


def test_compose_no_corroboration_preserves_factor_order() -> None:
    result = _result(("AAPL", 1.8), ("MSFT", 1.2), ("GOOG", 0.6))
    svc = ScreenerCompositeService()
    rows = svc.compose(result, [], AS_OF)
    assert [r.candidate.ticker for r in rows] == ["AAPL", "MSFT", "GOOG"]
    assert all(r.factor_only for r in rows)


def test_compose_strong_corroboration_boosts_rank() -> None:
    # GOOG has lowest factor score but STRONG corroboration
    result = _result(("AAPL", 1.8), ("MSFT", 1.2), ("GOOG", 0.6))
    snaps = [_snap("GOOG", ConvergenceTier.STRONG)]
    svc = ScreenerCompositeService()
    rows = svc.compose(result, snaps, AS_OF)
    # GOOG has factor_pct=0.0, blend=0.5*0.0+0.5*1.0=0.5
    # MSFT has factor_pct=0.5, blend=0.5 (factor only)
    # GOOG blended_percentile == 0.5, MSFT == 0.5 — tie broken by factor
    # AAPL has factor_pct=1.0 → stays #1
    assert rows[0].candidate.ticker == "AAPL"
    goog_row = next(r for r in rows if r.candidate.ticker == "GOOG")
    assert not goog_row.factor_only
    assert goog_row.corroboration is not None


def test_compose_stale_corroboration_outside_window_ignored() -> None:
    result = _result(("AAPL", 1.8))
    stale_snap = CorroborationSnapshot(
        ticker="AAPL",
        convergence_tier=ConvergenceTier.STRONG,
        n_sources=3,
        surfaced_at=date(2026, 6, 10),  # 12 days before as_of
    )
    svc = ScreenerCompositeService()
    rows = svc.compose(result, [stale_snap], AS_OF, window_days=7)
    assert rows[0].factor_only is True


def test_compose_within_window_accepted() -> None:
    result = _result(("AAPL", 1.8))
    fresh_snap = CorroborationSnapshot(
        ticker="AAPL",
        convergence_tier=ConvergenceTier.STRONG,
        n_sources=3,
        surfaced_at=date(2026, 6, 17),  # 5 days before as_of
    )
    svc = ScreenerCompositeService()
    rows = svc.compose(result, [fresh_snap], AS_OF, window_days=7)
    assert rows[0].factor_only is False


def test_compose_empty_candidates_returns_empty() -> None:
    result = _result()
    svc = ScreenerCompositeService()
    rows = svc.compose(result, [], AS_OF)
    assert rows == ()
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/domain/test_screener_composite_service.py -q
```

Expected: `ImportError` — `domain.screener_composite_service` not found.

- [ ] **Step 3: Create `domain/screener_composite_service.py`**

```python
"""SP3 pure domain service — joins ScreenResult with corroboration snapshots."""

from __future__ import annotations

from datetime import date

from domain.screen_models import ScreenCandidate, ScreenResult
from domain.screened_row import CorroborationSnapshot, ScreenedRow, blend


class ScreenerCompositeService:
    def compose(
        self,
        result: ScreenResult,
        snapshots: list[CorroborationSnapshot],
        as_of: date,
        window_days: int = 7,
    ) -> tuple[ScreenedRow, ...]:
        """Join ScreenResult candidates with corroboration snapshots and re-rank.

        Candidates with no matching snapshot within window_days are marked
        factor_only=True and ranked by factor percentile alone.
        """
        if not result.candidates:
            return ()

        in_window = {
            s.ticker: s
            for s in snapshots
            if abs((as_of - s.surfaced_at).days) <= window_days
        }

        factor_pcts = _rank_percentiles(result.candidates)

        rows = []
        for cand in result.candidates:
            snap = in_window.get(cand.ticker)
            fp = factor_pcts[cand.ticker]
            rows.append(
                ScreenedRow(
                    candidate=cand,
                    corroboration=snap,
                    blended_percentile=blend(fp, snap),
                    factor_only=snap is None,
                )
            )

        rows.sort(key=lambda r: r.blended_percentile, reverse=True)
        return tuple(rows)


def _rank_percentiles(candidates: tuple[ScreenCandidate, ...]) -> dict[str, float]:
    """Convert composite z-scores to [0, 1] rank percentiles (0=worst, 1=best)."""
    n = len(candidates)
    if n == 1:
        return {candidates[0].ticker: 1.0}
    sorted_tickers = sorted(candidates, key=lambda c: c.composite)
    return {c.ticker: i / (n - 1) for i, c in enumerate(sorted_tickers)}
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/domain/test_screener_composite_service.py -q
```

Expected: `5 passed`.

- [ ] **Step 5: Typecheck**

```bash
uv run mypy domain/screener_composite_service.py domain/screened_row.py --strict
```

Expected: `Success: no issues found in 2 source files`.

- [ ] **Step 6: Commit**

```bash
git add domain/screener_composite_service.py tests/domain/test_screener_composite_service.py
git commit -m "feat(sp3): add ScreenerCompositeService — pure domain blend + re-rank"
```

---

## Task 3: Add `get_snapshots()` to `CorroborationStore`

**Files:**
- Modify: `adapters/data/corroboration_store.py`
- Create: `tests/adapters/test_corroboration_store_snapshots.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/adapters/test_corroboration_store_snapshots.py
from __future__ import annotations

import sqlite3
from datetime import date

from domain.corroboration_models import ConvergenceTier, HarvestedClaim, Stance
from adapters.data.corroboration_store import CorroborationStore


def _make_store() -> CorroborationStore:
    conn = sqlite3.connect(":memory:")
    store = CorroborationStore(conn)
    store.init_schema()
    return store


def _bullish(ticker: str) -> HarvestedClaim:
    return HarvestedClaim(
        source_name="Kiplinger",
        ticker=ticker,
        stance=Stance.BULLISH,
        thesis_summary="Buy signal",
        url="https://example.com",
        published_at=date(2026, 6, 20),
        verified=True,
        reliability_weight=1.0,
    )


def _bearish(ticker: str) -> HarvestedClaim:
    return HarvestedClaim(
        source_name="Barrons",
        ticker=ticker,
        stance=Stance.BEARISH,
        thesis_summary="Sell signal",
        url="https://example.com",
        published_at=date(2026, 6, 20),
        verified=True,
        reliability_weight=1.0,
    )


def test_get_snapshots_returns_correct_tiers() -> None:
    store = _make_store()
    as_of = date(2026, 6, 21)
    claims = [
        _bullish("NVDA"), _bullish("NVDA"), _bullish("NVDA"),  # 3 → STRONG
        _bullish("MSFT"), _bullish("MSFT"),                    # 2 → MODERATE
        _bullish("AAPL"),                                      # 1 → WEAK
        _bullish("IBM"), _bearish("IBM"),                      # conflict → CONFLICTED
    ]
    store.save_run(as_of, claims)
    snaps = store.get_snapshots(date(2026, 6, 22), window_days=7)
    by_ticker = {s.ticker: s for s in snaps}
    assert by_ticker["NVDA"].convergence_tier == ConvergenceTier.STRONG
    assert by_ticker["NVDA"].n_sources == 3
    assert by_ticker["MSFT"].convergence_tier == ConvergenceTier.MODERATE
    assert by_ticker["AAPL"].convergence_tier == ConvergenceTier.WEAK
    assert by_ticker["IBM"].convergence_tier == ConvergenceTier.CONFLICTED


def test_get_snapshots_outside_window_excluded() -> None:
    store = _make_store()
    store.save_run(date(2026, 6, 1), [_bullish("NVDA")])  # 21 days before
    snaps = store.get_snapshots(date(2026, 6, 22), window_days=7)
    assert snaps == []


def test_get_snapshots_no_runs_returns_empty() -> None:
    store = _make_store()
    snaps = store.get_snapshots(date(2026, 6, 22), window_days=7)
    assert snaps == []


def test_get_snapshots_uses_most_recent_run_in_window() -> None:
    store = _make_store()
    # Two runs in window — use most recent
    store.save_run(date(2026, 6, 18), [_bullish("NVDA")])          # WEAK (1 claim)
    store.save_run(date(2026, 6, 21), [_bullish("NVDA"), _bullish("NVDA"), _bullish("NVDA")])  # STRONG
    snaps = store.get_snapshots(date(2026, 6, 22), window_days=7)
    by_ticker = {s.ticker: s for s in snaps}
    assert by_ticker["NVDA"].convergence_tier == ConvergenceTier.STRONG
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/adapters/test_corroboration_store_snapshots.py -q
```

Expected: `AttributeError: 'CorroborationStore' object has no attribute 'get_snapshots'`.

- [ ] **Step 3: Add `get_snapshots()` to `adapters/data/corroboration_store.py`**

Add these imports at the top (after existing imports):

```python
from datetime import date  # already present
from domain.corroboration_models import HarvestedClaim, Stance, ConvergenceTier  # add ConvergenceTier
from domain.screened_row import CorroborationSnapshot  # new import
```

Add this method to `CorroborationStore` after `load_run`:

```python
def get_snapshots(self, as_of: date, window_days: int = 7) -> list[CorroborationSnapshot]:
    """Return CorroborationSnapshot per ticker from most recent run within window_days of as_of."""
    rows = self._c.execute(
        "SELECT id, as_of FROM corroboration_runs ORDER BY as_of DESC"
    ).fetchall()

    run_id: int | None = None
    run_date: date | None = None
    for row in rows:
        candidate_date = date.fromisoformat(row[1])
        if abs((as_of - candidate_date).days) <= window_days:
            run_id = int(row[0])
            run_date = candidate_date
            break

    if run_id is None or run_date is None:
        return []

    claims = self.load_run(run_id)
    return _claims_to_snapshots(claims, run_date)


def _claims_to_snapshots(
    claims: list[HarvestedClaim], run_date: date
) -> list[CorroborationSnapshot]:
    from collections import defaultdict

    by_ticker: dict[str, list[HarvestedClaim]] = defaultdict(list)
    for c in claims:
        if c.verified:
            by_ticker[c.ticker].append(c)

    snapshots = []
    for ticker, verified_claims in by_ticker.items():
        bullish = sum(1 for c in verified_claims if c.stance == Stance.BULLISH)
        bearish = sum(1 for c in verified_claims if c.stance == Stance.BEARISH)
        if bullish > 0 and bearish > 0:
            tier = ConvergenceTier.CONFLICTED
        elif bullish >= 3:
            tier = ConvergenceTier.STRONG
        elif bullish == 2:
            tier = ConvergenceTier.MODERATE
        elif bullish == 1:
            tier = ConvergenceTier.WEAK
        else:
            tier = ConvergenceTier.NONE
        snapshots.append(
            CorroborationSnapshot(
                ticker=ticker,
                convergence_tier=tier,
                n_sources=len(verified_claims),
                surfaced_at=run_date,
            )
        )
    return snapshots
```

Note: `_claims_to_snapshots` is a module-level function (not a method) — place it after the class definition.

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/adapters/test_corroboration_store_snapshots.py -q
```

Expected: `4 passed`.

- [ ] **Step 5: Typecheck**

```bash
uv run mypy adapters/data/corroboration_store.py --strict
```

Expected: `Success`.

- [ ] **Step 6: Commit**

```bash
git add adapters/data/corroboration_store.py tests/adapters/test_corroboration_store_snapshots.py
git commit -m "feat(sp3): add CorroborationStore.get_snapshots() — derive convergence tier from raw claims"
```

---

## Task 4: Wire CLI — compose, persist `screened_<date>.json`, print summary

**Files:**
- Modify: `application/cli/screen_commands.py`

- [ ] **Step 1: Read the current `screen_candidates` function**

```bash
sed -n '19,133p' application/cli/screen_commands.py
```

Understand: where `uc.run()` is called, where the JSON is written, where stdout summary is printed.

- [ ] **Step 2: Add imports at top of `screen_commands.py`**

After existing imports, add:

```python
import sqlite3
from datetime import date as _date

from adapters.data.corroboration_store import CorroborationStore
from domain.screened_row import CorroborationSnapshot, ScreenedRow
from domain.screener_composite_service import ScreenerCompositeService
```

- [ ] **Step 3: Add `_write_screened_json()` helper after `screen_candidates` function**

```python
def _write_screened_json(
    rows: tuple[ScreenedRow, ...],
    as_of: str,
    corroboration_run_date: _date | None,
    report_dir: str,
) -> str:
    """Persist screened_<date>.json sidecar with blended rows. Returns file path."""
    import json, os

    def _row_to_dict(r: ScreenedRow) -> dict[str, object]:
        corr = r.corroboration
        return {
            "ticker": r.candidate.ticker,
            "composite": r.candidate.composite,
            "factor_percentile": round(
                1.0 - (
                    [rr.candidate.ticker for rr in rows].index(r.candidate.ticker)
                    / max(len(rows) - 1, 1)
                ),
                4,
            ),
            "blended_percentile": round(r.blended_percentile, 4),
            "factor_only": r.factor_only,
            "convergence_tier": corr.convergence_tier.value if corr else None,
            "n_sources": corr.n_sources if corr else 0,
            "corroboration_date": corr.surfaced_at.isoformat() if corr else None,
            "why": r.candidate.why,
            "label": r.candidate.label,
            "factor_scores": [
                {
                    "name": fs.name,
                    "value": round(fs.value, 4),
                    "percentile": round(fs.percentile, 4),
                }
                for fs in r.candidate.factor_scores
            ],
        }

    payload: dict[str, object] = {
        "as_of": as_of,
        "corroboration_run_date": corroboration_run_date.isoformat() if corroboration_run_date else None,
        "rows": [_row_to_dict(r) for r in rows],
    }
    os.makedirs(report_dir, exist_ok=True)
    path = os.path.join(report_dir, f"screened_{as_of}.json")
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    return path
```

- [ ] **Step 4: Modify `screen_candidates()` to call composite service after `uc.run()`**

Find the block after `uc.surface_calls(...)` that prints the masked summary. Add the composite service wiring BEFORE the print block:

```python
    # --- SP3: blend with corroboration snapshots ---
    db_path = os.path.join(report_dir, "..", "recommendations.db")
    corroboration_run_date: _date | None = None
    snapshots = []
    try:
        conn = sqlite3.connect(db_path)
        corr_store = CorroborationStore(conn)
        corr_store.init_schema()
        as_of_date = _date.fromisoformat(as_of)
        snapshots = corr_store.get_snapshots(as_of_date, window_days=7)
        if snapshots:
            corroboration_run_date = snapshots[0].surfaced_at
        conn.close()
    except Exception:
        pass  # corroboration unavailable — graceful degrade

    svc = ScreenerCompositeService()
    screened_rows = svc.compose(full_result, snapshots, _date.fromisoformat(as_of))
    _write_screened_json(screened_rows, as_of, corroboration_run_date, report_dir)

    # --- corroboration summary line ---
    n_corroborated = sum(1 for r in screened_rows if not r.factor_only)
    if n_corroborated > 0:
        from domain.corroboration_models import ConvergenceTier as _CT
        strong = sum(1 for r in screened_rows if r.corroboration and r.corroboration.convergence_tier == _CT.STRONG)
        moderate = sum(1 for r in screened_rows if r.corroboration and r.corroboration.convergence_tier == _CT.MODERATE)
        weak = sum(1 for r in screened_rows if r.corroboration and r.corroboration.convergence_tier == _CT.WEAK)
        click.echo(
            f"  corroboration: {n_corroborated}/{len(screened_rows)} tickers "
            f"· {strong} STRONG  {moderate} MODERATE  {weak} WEAK"
        )
    else:
        click.echo("  corroboration: no data this week — showing factor signals only")
```

- [ ] **Step 5: Run the screener tab tests**

```bash
make test-tab tab=screener
```

Expected: all existing screener tests still pass (no CLI tests reference the new JSON output yet).

- [ ] **Step 6: Typecheck**

```bash
uv run mypy application/cli/screen_commands.py --strict
```

Fix any type errors. Common fix: annotate `snapshots` as `list[CorroborationSnapshot]`.

- [ ] **Step 7: Commit**

```bash
git add application/cli/screen_commands.py
git commit -m "feat(sp3): wire ScreenerCompositeService in CLI — write screened_<date>.json + summary line"
```

---

## Task 5: Data loader — `load_latest_screened()` with fallback

**Files:**
- Modify: `adapters/visualization/data_loader.py`

- [ ] **Step 1: Find `load_latest_screen()` in data_loader.py**

```bash
grep -n "load_latest_screen\|def load_" adapters/visualization/data_loader.py
```

Note the line numbers and the function signature.

- [ ] **Step 2: Add `load_latest_screened()` after `load_latest_screen()`**

```python
def load_latest_screened(reports_dir: str = "data/reports") -> dict[str, Any] | None:
    """Load newest screened_<date>.json (SP3 blended). Falls back to screen_<date>.json.

    Returns dict with key 'rows' (list of ScreenedRow dicts) if screened file found,
    or standard screen dict with key 'candidates' if falling back.
    The caller checks for 'rows' key to distinguish.
    """
    import glob, os

    screened = sorted(
        [
            p
            for p in glob.glob(os.path.join(reports_dir, "screened_*.json"))
            if "screened_" in os.path.basename(p)
        ]
    )
    if screened:
        import json
        with open(screened[-1]) as f:
            data = json.load(f)
        data["_source"] = "screened"
        return data

    # Fallback: return standard screen JSON
    screen = load_latest_screen(reports_dir)
    if screen:
        screen["_source"] = "screen"
    return screen
```

- [ ] **Step 3: Typecheck**

```bash
uv run mypy adapters/visualization/data_loader.py --strict
```

Expected: `Success`.

- [ ] **Step 4: Commit**

```bash
git add adapters/visualization/data_loader.py
git commit -m "feat(sp3): add load_latest_screened() with fallback to screen JSON"
```

---

## Task 6: Dashboard — corroboration badge + drill-down

**Files:**
- Modify: `adapters/visualization/tabs/research_candidates.py`

- [ ] **Step 1: Read the card rendering section**

```bash
sed -n '550,760p' adapters/visualization/tabs/research_candidates.py
```

Identify: where each card is rendered in `build_reason_view_html()`. Look for the ticker + company name row that starts each card.

- [ ] **Step 2: Add `_corroboration_badge_html()` helper near the top of the file (after constants)**

Find where other helper functions are defined (around line 100-200). Add:

```python
def _corroboration_badge_html(row_dict: dict[str, object]) -> str:
    """Return HTML pill showing corroboration tier, or empty string if factor-only."""
    if row_dict.get("factor_only", True):
        return '<span style="color:#888;font-size:0.78rem;margin-left:8px">(factor only)</span>'
    tier = str(row_dict.get("convergence_tier", "")).upper()
    n = int(row_dict.get("n_sources", 0))
    corr_date = str(row_dict.get("corroboration_date", ""))
    colours = {
        "STRONG": ("#22c55e", "#052e16"),
        "MODERATE": ("#f59e0b", "#1c1100"),
        "WEAK": ("#94a3b8", "#0f172a"),
        "CONFLICTED": ("#f87171", "#1c0505"),
    }
    bg, fg = colours.get(tier, ("#94a3b8", "#0f172a"))
    label = f"✓ {tier.capitalize()} · {n} source{'s' if n != 1 else ''}"
    date_note = f'<span style="color:#888;font-size:0.72rem;margin-left:6px">corroborated {corr_date}</span>'
    return (
        f'<span style="background:{bg};color:{fg};padding:2px 8px;'
        f'border-radius:4px;font-size:0.78rem;font-weight:600;margin-left:8px">'
        f"{label}</span>{date_note}"
    )
```

- [ ] **Step 3: Modify `render()` to use `load_latest_screened()` instead of `load_latest_screen()`**

Find the `render()` function (around line 1117). Change:

```python
# BEFORE
screen = load_latest_screen(reports_dir)
candidates = screen.get("candidates", [])[:_TOP_N]
```

To:

```python
# AFTER
screen = load_latest_screened(reports_dir)
# screened_*.json has 'rows'; screen_*.json has 'candidates'
if screen and screen.get("_source") == "screened":
    candidates = screen.get("rows", [])[:_TOP_N]
    _using_screened = True
else:
    candidates = (screen or {}).get("candidates", [])[:_TOP_N]
    _using_screened = False
```

Also add the import at the top of the file:
```python
from adapters.visualization.data_loader import load_latest_screen, load_latest_screened
```

- [ ] **Step 4: Add no-corroboration note to header when falling back**

In `build_header_html()` or just before the view renders in `render()`, add after the `_using_screened` check:

```python
if not _using_screened:
    st.caption("ℹ No corroboration data this week — run `corroborate` to blend analyst signals.")
```

- [ ] **Step 5: Add badge to each card in `build_reason_view_html()`**

Find where ticker + company name is rendered per card. The function signature currently takes `candidates: list[dict]`. Each dict has a `ticker` key. Add the badge inline after the ticker heading.

Target line ~664 in `build_reason_view_html()` (reason view) and ~726 (rank view):

```python
# line ~664 — reason view card header (BEFORE)
f"<b style=\"font-family:'DM Sans',sans-serif;\">{safe_ticker}</b>"

# AFTER — append badge after ticker bold tag
f"<b style=\"font-family:'DM Sans',sans-serif;\">{safe_ticker}</b>"
+ _corroboration_badge_html(cand)
```

Also line ~985 in the detail/drill-down card:
```python
# BEFORE
f"<b style=\"font-family:'DM Sans',sans-serif;\">{ticker}</b>"

# AFTER (unchanged — drill-down shows factor detail, badge only on top-level card)
f"<b style=\"font-family:'DM Sans',sans-serif;\">{ticker}</b>"
```

The `cand` dict is already in scope in both loops (`for cand in bucket_candidates` and `for cand in candidates`).

- [ ] **Step 6: Run the screener tab tests**

```bash
make test-tab tab=screener
```

Expected: all pass. If `load_latest_screened` is not imported in the tab test fixtures, add it.

- [ ] **Step 7: Typecheck**

```bash
uv run mypy adapters/visualization/tabs/research_candidates.py --strict
```

Fix any type errors (common: `Any` on dict values, mark with `# type: ignore` only as last resort).

- [ ] **Step 8: Run full suite**

```bash
make test-fast
```

Expected: ≥2239 passed (same count or higher).

- [ ] **Step 9: Commit**

```bash
git add adapters/visualization/tabs/research_candidates.py
git commit -m "feat(sp3): add corroboration badge + drill-down to screener cards"
```

---

## Task 7: Final gate

- [ ] **Step 1: Run full quality gate**

```bash
make check
```

Expected: lint passes, all tests pass, coverage gate holds.

- [ ] **Step 2: Verify import shim still works**

```bash
uv run python -c "
from domain.screened_row import CorroborationSnapshot, ScreenedRow, blend, TIER_RANK
from domain.screener_composite_service import ScreenerCompositeService
from adapters.data.corroboration_store import CorroborationStore
print('SP3 imports OK')
"
```

Expected: `SP3 imports OK`.

- [ ] **Step 3: Commit (if any lint auto-fixes landed)**

```bash
git status
# If any files changed:
git add -u
git commit -m "chore(sp3): lint auto-fixes from make check"
```
