# SP6 Design Spec — Dashboard Tabs: Stock Analysis Decomposition + Corroboration Surface

**Date:** 2026-06-24
**Branch:** `feat/sp6-dashboard-tabs`
**Status:** Approved — ready for implementation plan
**Depends on:** SP1 (merged PR #73), SP2 (merged), SP5 (merged PR #79)

---

## Purpose

Surface the corroboration ecosystem in the Streamlit dashboard so the user reads, trusts, and acts on
it. North-star: **trust via legibility** — a non-expert can tell what to trust; show the evidence
chain, not a number.

---

## Scope

**In:**
- Decompose `adapters/visualization/tabs/stock_analysis.py` (1055 lines) into a `stock_analysis/`
  package following the `risk/` decomposition pattern
- Add a persistent `RESEARCH ONLY` amber banner to the entire stock analysis tab
- Add a convergence tier badge to the existing Verdict section
- Add a new `Corroboration` section (after Sentiment in the chip nav) rendering:
  - Claims grouped by tier (STRONG as cards, MODERATE as compact rows, WEAK collapsed)
  - `OurReadout` bridge (factor percentile, trend health, divergence flag, discipline flag)
  - `DirectionalView` tilt panel (LEAN_IN / HOLD / LEAN_OUT / AVOID)
  - Graceful empty state when no corroboration data exists
- Add `load_corroboration_snapshot(ticker)` to `data_loader.py` returning a `CorroborationTabView` DTO
- Add `FakeCorroborationStore` to `tests/fakes/` for test isolation
- Unit + smoke tests for corroboration sections

**Out:**
- No new prediction widgets or return projections
- No live data pings on tab load (snapshot only)
- No changes to other tabs (research_candidates, positions, trust, weekly_brief)
- No new CLI commands

---

## Architecture

### Package Structure

```
adapters/visualization/tabs/stock_analysis/   ← new package (replaces stock_analysis.py)
  __init__.py              # re-exports render() only
  compose.py               # entry: RESEARCH_ONLY banner, section router, chip nav
  verdict_section.py       # Verdict + Fit + convergence tier badge
  financials_section.py    # Valuation + Growth + Health
  market_section.py        # Performance + Ownership
  signals_section.py       # Sentiment + Supply chain
  corroboration_section.py # NEW: claim cards, OurReadout, DirectionalView, empty state
```

### Data Flow

```
CorroborationStore (SQLite)
  ↓ store.latest_run_id()
  ↓ store.load_run(run_id)        → list[HarvestedClaim]  (filter by ticker)
  ↓ store.load_candidates(run_id) → list[CandidateSnapshot] (filter by ticker)
  ↓
adapters/visualization/data_loader.py
  load_corroboration_snapshot(ticker, db_path) → CorroborationTabView | None
  ↓
corroboration_section.py
  render_corroboration(view: CorroborationTabView | None) → HTML string
```

### CorroborationTabView DTO

New dataclass in `adapters/visualization/data_loader.py` (visualization layer only — NOT domain):

```python
@dataclass(frozen=True)
class CorroborationTabView:
    ticker: str
    as_of: date
    claims: tuple[HarvestedClaim, ...]       # all claims for ticker, latest run
    snapshot: CandidateSnapshot | None        # convergence tier, verification
    our_readout: OurReadout | None            # from AnalysisResult if available
    directional_views: tuple[DirectionalView, ...]  # computed from claims by sector
```

`load_corroboration_snapshot()` builds this by:
1. `store.latest_run_id()` — if None, return None (empty state)
2. `store.load_run(run_id)` → filter `claim.ticker == ticker`
3. `store.load_candidates(run_id)` → filter by ticker → `CandidateSnapshot | None`
4. Compute `DirectionalView` list from claims grouped by sector
5. Return `CorroborationTabView`

`OurReadout` is passed in from `AnalysisResult` by the caller (compose.py already has it).

---

## Section Design

### Updated Chip Nav

```
Verdict | Fit | Valuation | Growth | Performance | Health | Ownership | Sentiment | Supply chain | Corroboration
```

`_SECTION_LABELS` gains `"Corroboration"` at index 9.

### Page-Level RESEARCH ONLY Banner (`compose.py`)

Amber `st.info()` or custom HTML banner rendered at the top of every stock analysis tab load:

> **RESEARCH ONLY — not financial advice.** Grades reflect model confidence, not return forecasts.
> Corroboration shows evidence strength, not a price prediction.

Persistent — not a modal. Does not depend on section selection.

### Verdict Section Patch (`verdict_section.py`)

Existing `_render_verdict()` (lines 204–271 in original) gains a convergence tier chip:

```
[STRONG BUY]  ↔  [STRONG convergence]
```

Chip style maps tier → colour:
- `STRONG` → green
- `MODERATE` → blue
- `WEAK` → amber
- `CONFLICTED` → red
- `NONE` → grey (hidden if no corroboration data)

Chip only renders if `CorroborationTabView` is available and `snapshot` is not None.

### Corroboration Section (`corroboration_section.py`)

**Empty state** (when `view is None` or `len(view.claims) == 0`):
```
⚠ No corroboration data for AAPL.
Run `corroborate` to surface external evidence.
```

**Claims display — grouped by convergence tier:**

| Tier | Display |
|------|---------|
| `STRONG` | Full evidence card: source, date, verified badge, full thesis, clickable URL, freshness chip |
| `MODERATE` | Compact row: source, stance icon, one-line thesis, date |
| `WEAK` | Collapsed under "Show weak signals (N)" expander |
| `CONFLICTED` | Amber warning card: shows conflicting claims side-by-side |
| `NONE` | Not rendered (no claims) |

Tier grouping computed from `claim.reliability_weight` + `snapshot.convergence`.

**OurReadout bridge** (below claim cards):

```
Our model says:
  Factor percentile: 73rd   Trend: HEALTHY   Divergence: ✗   Discipline: HOLD_OK
```

All fields are optional — if `our_readout is None`, section is hidden.

**DirectionalView tilt panel** (below OurReadout):

Table of sector/theme groups with stance and confidence:

```
Semiconductors  →  LEAN_IN   (0.82)
Energy          →  HOLD      (0.60)
Consumer        →  LEAN_OUT  (0.45)
```

Computed from `view.directional_views`. Hidden if list is empty.

---

## Testing

### Unit Tests (`tests/test_corroboration_section.py`)

Test pure-function logic without Streamlit:
- `_group_claims_by_tier(claims)` — correct bucketing for each tier
- `_empty_state_html()` — contains ticker name + instruction
- `_render_our_readout(readout)` — None fields hidden, all fields present
- `_compute_directional_views(claims)` — sector grouping and stance aggregation

### Smoke Tests (`tests/test_tab_stock_analysis.py`)

Call `render(ticker, session_state, db_path)` with `FakeCorroborationStore`:
- With data → no exception, "Corroboration" section marker in output
- Empty store → no exception, "Run `corroborate`" present in output

### FakeCorroborationStore (`tests/fakes/corroboration_store_fake.py`)

```python
class FakeCorroborationStore:
    def __init__(self, run_id=1, claims=None, candidates=None):
        self._run_id = run_id
        self._claims = claims or []
        self._candidates = candidates or []

    def latest_run_id(self): return self._run_id
    def load_run(self, run_id): return self._claims
    def load_candidates(self, run_id): return self._candidates
```

---

## Decomposition Map (stock_analysis.py → package)

| New file | Lines from original | Key functions migrated |
|----------|--------------------|-----------------------|
| `compose.py` | 71–130 | `render()`, chip nav, RESEARCH_ONLY banner |
| `verdict_section.py` | 204–393 | `_render_verdict()`, `_render_fit_card()`, `_render_analyst_panel()`, `_render_news_context()`, `_render_peer_percentiles()` |
| `financials_section.py` | 487–718 | `_render_valuation()`, `_render_growth()`, `_render_health()` |
| `market_section.py` | 614–763 | `_render_performance()`, `_render_ownership()` |
| `signals_section.py` | 765–873 | `_render_sentiment()`, `_render_supply_chain()` |
| `corroboration_section.py` | NEW | All corroboration rendering |

Note: `_render_decision_lead()` and `_ensure_fit_cached()` helpers stay in `compose.py`.

---

## Non-Functional Requirements

- Tab load: no live API calls. Corroboration reads from persisted snapshot only.
- Empty state never raises — `load_corroboration_snapshot()` returns None on any store error.
- All new functions: type-annotated, mypy strict clean.
- No direct imports of `CorroborationStore` in visualization files — goes through `data_loader.py`.
- Screenshot of live tab required before claiming done (per `verify_render_against_mockup` memory).
- Streamlit lazy-tab blank screenshot known issue — verify corroboration section via solo harness.

---

## Files Changed

| File | Change |
|------|--------|
| `adapters/visualization/tabs/stock_analysis.py` | DELETE (replaced by package) |
| `adapters/visualization/tabs/stock_analysis/` | CREATE (6 files) |
| `adapters/visualization/tabs/__init__.py` | UPDATE import path |
| `adapters/visualization/data_loader.py` | ADD `CorroborationTabView`, `load_corroboration_snapshot()` |
| `tests/fakes/corroboration_store_fake.py` | CREATE |
| `tests/test_corroboration_section.py` | CREATE |
| `tests/test_tab_stock_analysis.py` | CREATE or UPDATE |

---

## Open Questions (resolved)

| Q | Decision |
|---|----------|
| Empty state vs block on SP1 | Graceful empty state |
| Tab vs new tab vs decompose+augment | Decompose + augment (Option C) |
| Corroboration placement | Badge on Verdict + dedicated section after Sentiment |
| Claim display density | Grouped by tier (STRONG cards / MODERATE rows / WEAK collapsed) |
| DirectionalView placement | Inside Corroboration section, below OurReadout |
| RESEARCH_ONLY framing | Persistent page-level amber banner |
| Package file structure | 6-file split (compose + 4 domain sections + corroboration) |
| Data loading | `data_loader.py` extension with `CorroborationTabView` DTO |
| OurReadout placement | Below claim cards, above DirectionalView |
| Testing strategy | Unit (logic) + smoke (render path) |
