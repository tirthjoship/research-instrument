# Spec — SP4: Portfolio-Verdict Corroboration Integration

**Date:** 2026-06-23
**Status:** Approved for implementation
**Depends on:** SP1 (corroboration engine), SP2 (candidate surfacing), SP3 (screener overlay), SP7 (holdings_risk crash fix) — all on develop.
**Branch:** `feat/sp4-portfolio-verdict` off `develop`

---

## Purpose

Wire corroboration evidence into the weekly verdict so the user sees "what credible sources now say about YOUR holdings" alongside the existing discipline flags — without overriding them. Attributed, RESEARCH_ONLY. No buy/sell instructions.

---

## Decisions (locked)

| # | Decision | Choice |
|---|----------|--------|
| 1 | Evidence placement | Extend `HoldingVerdictLine` with 3 optional fields |
| 2 | Conflict display | Raw `source_stance: Stance \| None` stored; conflict computed at render |
| 3 | Exposure source | Equal-weight from existing `holdings` list + `SectorProvider` |
| 4 | Snapshot injection | `CorroborationSnapshotFn = Callable[[date], list[CorroborationSnapshot]]` |
| 5 | DirectionalView storage | `directional_views: tuple[DirectionalView, ...] = ()` on `WeeklyBrief` |
| 6 | CLI holding format | Inline `│ sources: BULLISH ×3 [STRONG]` suffix; `⚠ CONFLICT` on mismatch |
| 7 | Tilt section placement | After holdings table, before scorecard |
| 8 | Missing snapshot | Footer note; uncorroborated rows render as before (no `│` segment) |
| 9 | Test scope | Unit only — fake `CorroborationSnapshotFn`, no live adapter |

---

## Domain Changes (`domain/screened_row.py`)

### `CorroborationSnapshot` — add `net_stance`

```python
from domain.corroboration_models import ConvergenceTier, Stance

@dataclass(frozen=True)
class CorroborationSnapshot:
    ticker: str
    convergence_tier: ConvergenceTier
    n_sources: int
    surfaced_at: date
    net_stance: Stance = Stance.NEUTRAL  # populated by _claims_to_snapshots()
```

`_claims_to_snapshots()` in `adapters/data/corroboration_store.py` already iterates verified claims and counts bullish/bearish — it sets `net_stance` from those counts (BULLISH if bullish > bearish, BEARISH if bearish > bullish, else NEUTRAL). This field is what the use case uses for `DirectionalView` computation — no `CorroboratedCandidate` proxy conversion needed.

---

## Domain Changes (`domain/brief.py`)

### `HoldingVerdictLine` — 3 new optional fields

```python
@dataclass(frozen=True)
class HoldingVerdictLine:
    ticker: str
    unrealized_pct: float
    trend_state: str
    verdict: Verdict
    why: str
    # SP4 — corroboration enrichment (None = no snapshot available)
    convergence_tier: ConvergenceTier | None = None
    n_sources: int | None = None
    source_stance: Stance | None = None
```

All default `None` — existing callers require no changes. Conflict is `source_stance == Stance.BULLISH and verdict == Verdict.REDUCE` (or `TRIM`), or `source_stance == Stance.BEARISH and verdict in (Verdict.ADD_OK,)` — computed at render time, never stored.

### `WeeklyBrief` — 1 new field

```python
directional_views: tuple[DirectionalView, ...] = ()
```

Empty default — brief renders correctly with zero views (e.g. no corroboration run yet).

### `assemble_brief()` — new param

```python
def assemble_brief(
    *,
    ...existing params...,
    corroboration_map: dict[str, CorroborationSnapshot] | None = None,
) -> WeeklyBrief:
```

For each holding: look up ticker in `corroboration_map`; if found, populate the three new fields; if not, leave `None`. Default `None` treated as `{}` — zero regression.

---

## Application Changes (`application/weekly_brief_use_case.py`)

### New type alias

```python
CorroborationSnapshotFn = Callable[[date], list[CorroborationSnapshot]]
```

### `WeeklyBriefUseCase.__init__()` — new optional param

```python
corroboration_fn: CorroborationSnapshotFn | None = None
```

Stored as `self._corroboration_fn`. If `None`, no enrichment — use case behaves identically to pre-SP4.

### `WeeklyBriefUseCase.run()` — enrichment steps

After existing `risk = self._holdings.execute(...)`:

1. **Snapshot fetch:** `snapshots = self._corroboration_fn(as_of) if self._corroboration_fn else []`
2. **Map by ticker:** `corr_map = {s.ticker: s for s in snapshots}`
3. **Pass to assemble_brief:** `corroboration_map=corr_map`
4. **Sector grouping:** For each held ticker, call `self._sector_provider.sector(ticker)` → build `groups: dict[str, list[CorroborationSnapshot]]` (sector → snapshots for held tickers present in corr_map).
5. **Equal-weight exposure:** `exposure_pct = {sector: count/len(holdings) for sector, count in sector_counts.items()}`
6. **DirectionalView:** Call a new pure helper `_build_directional_views(groups, exposure_pct)` (in use case module). For each sector group: compute `mean_conv = mean(_TIER_NUM[s.convergence_tier] for s in group)`, derive `net_stance` by majority of `s.net_stance`, compute tilt via same logic as `CorroborationService._tilt()`. Returns `list[DirectionalView]`. **Does NOT use `CorroborationService.roll_up()`** — that requires `CorroboratedCandidate` which is unavailable at brief time.

`SectorProvider` is already injected at the CLI composition root — pass it into `WeeklyBriefUseCase` as an optional param (`sector_provider: SectorProvider | None = None`). If `None`, skip directional views entirely.

---

## CLI Changes (`application/cli/brief_commands.py`)

### Wiring

```python
from adapters.data.corroboration_store import CorroborationStore
store = CorroborationStore(db_path)
use_case = WeeklyBriefUseCase(
    ...existing...,
    corroboration_fn=store.get_snapshots,
    sector_provider=SectorProvider(),
)
```

### Holdings table — inline evidence suffix

```
AAPL  HOLD    +12.3%  uptrend  "momentum p78 · value p45 · trend ok"  │ sources: BULLISH ×3 [STRONG]
MSFT  REDUCE   +4.1%  broken   "momentum p32 · trend weak"             │ sources: BULLISH ×2 [MOD] ⚠ CONFLICT
TSLA  HOLD     +5.2%  uptrend  "momentum p61 · trend ok"
```

Conflict condition (renderer):
```python
def _is_conflict(line: HoldingVerdictLine) -> bool:
    if line.source_stance is None:
        return False
    bullish_but_reduce = (
        line.source_stance == Stance.BULLISH
        and line.verdict in (Verdict.REDUCE, Verdict.TRIM)
    )
    bearish_but_add = (
        line.source_stance == Stance.BEARISH
        and line.verdict == Verdict.ADD_OK
    )
    return bullish_but_add or bullish_but_reduce
```

### Tilt section (after holdings, before scorecard)

```
── Directional Tilts  [RESEARCH_ONLY — attributed evidence, not a prediction] ──
Technology   LEAN_IN    evidence: BULLISH/STRONG  your book:  8%  evidence weight: 22%
Energy       LEAN_OUT   evidence: BEARISH/MOD     your book: 15%  evidence weight:  6%
Healthcare   HOLD       evidence: NEUTRAL/WEAK    your book: 12%  evidence weight:  9%
```

Only render tilts where `tilt != "HOLD"` OR `mean_convergence >= 0.4` (avoid noise from weak signals).

### Footer (conditional)

```
ⓘ  3 holding(s) have no corroboration snapshot — run `corroborate` to populate.
```

Rendered only when at least one holding has `convergence_tier is None`.

---

## Scope Boundaries

**In:**
- Enrich `HoldingVerdictLine` with corroboration fields
- `DirectionalView` tilt section in `WeeklyBrief` + CLI output
- Unit tests for domain, use case, renderer

**Out:**
- Questrade real position sizes (deferred — equal-weight is the honest substitute)
- Dashboard rendering of SP4 data (deferred to SP6)
- `GeminiNarratorAdapter` for narrative text (not needed — direct attribution is sufficient)
- Any automated trade instruction or buy/sell language
- Overriding existing discipline flags

---

## Files Touched

| File | Change |
|------|--------|
| `domain/screened_row.py` | Add `net_stance: Stance` field to `CorroborationSnapshot` (default `Stance.NEUTRAL`) |
| `adapters/data/corroboration_store.py` | `_claims_to_snapshots()` — populate `net_stance` from bullish/bearish claim counts |
| `domain/brief.py` | Extend `HoldingVerdictLine`; add `directional_views` to `WeeklyBrief`; update `assemble_brief()` |
| `application/weekly_brief_use_case.py` | Add `CorroborationSnapshotFn` type alias; inject callable + sector_provider; add `_build_directional_views()` helper; enrichment logic in `run()` |
| `application/cli/brief_commands.py` | Wire store + sector_provider; render inline evidence + tilt section + footer |
| `tests/domain/test_brief_sp4.py` | New — assemble_brief with corroboration_map, conflict detection |
| `tests/adapters/test_corroboration_store_net_stance.py` | New — `_claims_to_snapshots()` sets correct net_stance |
| `tests/test_weekly_brief_use_case_sp4.py` | New — use case with fake callable; empty fn; directional views |
| `tests/test_cli_brief_commands_sp4.py` | New — inline format, conflict marker, footer, tilt section |

---

## ADR reference

No new ADR required — SP4 is an extension within ADR-062 (corroboration engine pivot) scope. RESEARCH_ONLY label maintained per ADR-049.
