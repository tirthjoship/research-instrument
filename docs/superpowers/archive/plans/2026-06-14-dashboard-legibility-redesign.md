# Dashboard Legibility Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the shipped "Research Instrument" dashboard legible + honest by adding two pure-domain modules (screen diagnostics, risk rubric) and wiring them + decided A/B layouts into 5 tabs (Screener, Risk, Home, My Portfolio, Trust). Stock Analysis is explicitly deferred to a later plan.

**Architecture:** Hexagonal. New pure-`domain/` modules (stdlib-only) hold all classification/verdict logic with unit tests. Streamlit tab adapters in `adapters/visualization/tabs/` consume them and render; no business logic in adapters. Honesty rails are non-negotiable (see each task).

**Tech Stack:** Python 3.12, pytest + Hypothesis, Streamlit, Plotly. Design system: `adapters/visualization/components/styles.py` (Fraunces + IBM Plex; tokens `--accent #1D4ED8`, `--purple #7C3AED`, `--ok #15803D`, `--warn #B45309`, `--danger #B91C1C`).

**Branch:** `feat/dashboard-legibility-redesign` (stacked on the `s.close→s.price` fix).

**Approved mockup (visual source of truth):** `.superpowers/brainstorm/whole-site/content/site-proposal-v1.html`. Per-tab specs: `docs/superpowers/specs/2026-06-13-*.md`. A/B decisions: memory `project-whole-site-redesign-decisions`.

**Honesty rails (ALL tasks):** no buy/sell verdict or return forecast; verdict = discipline rule ("review prompt, not forecast"); confidence = "calibrating…" until the gate; risk = character not quality; third-party (analyst/Google-AI) = attributed; RESEARCH_ONLY on every screen surface; no fabricated data (missing = explicit DATA-GAP); never present a degraded-to-neutral value as a finding.

---

## Phase 0 — Pure-domain foundation (TDD)

### Task 1: Screen diagnostics + verdict (pure domain)

**Files:**
- Create: `domain/screen_diagnostics.py`
- Test: `tests/domain/test_screen_diagnostics.py`

- [ ] **Step 1: Write the failing test**

```python
from domain.screen_diagnostics import ScreenDiagnostics, ScreenVerdict, classify_screen

def test_under_powered_when_history_coverage_low():
    d = ScreenDiagnostics(scanned=512, had_history=20, above_trend=0, cleared=0)
    assert classify_screen(d, coverage_floor=0.5) is ScreenVerdict.UNDER_POWERED

def test_earned_abstention_when_coverage_healthy_but_zero_cleared():
    d = ScreenDiagnostics(scanned=512, had_history=490, above_trend=0, cleared=0)
    assert classify_screen(d, coverage_floor=0.5) is ScreenVerdict.EARNED_ABSTENTION

def test_has_candidates_when_cleared_positive():
    d = ScreenDiagnostics(scanned=512, had_history=490, above_trend=300, cleared=70)
    assert classify_screen(d, coverage_floor=0.5) is ScreenVerdict.HAS_CANDIDATES

def test_coverage_floor_boundary_is_inclusive_healthy():
    # exactly at floor counts as healthy (not under-powered)
    d = ScreenDiagnostics(scanned=100, had_history=50, above_trend=0, cleared=0)
    assert classify_screen(d, coverage_floor=0.5) is ScreenVerdict.EARNED_ABSTENTION

def test_diagnostics_rejects_impossible_counts():
    import pytest
    with pytest.raises(ValueError):
        ScreenDiagnostics(scanned=10, had_history=20, above_trend=0, cleared=0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/domain/test_screen_diagnostics.py -v`
Expected: FAIL with "No module named 'domain.screen_diagnostics'"

- [ ] **Step 3: Write minimal implementation**

```python
"""Pure screen diagnostics + honesty verdict (stdlib only)."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


class ScreenVerdict(Enum):
    UNDER_POWERED = "UNDER_POWERED"        # thin feed: can't claim discipline
    EARNED_ABSTENTION = "EARNED_ABSTENTION"  # coverage healthy, none cleared
    HAS_CANDIDATES = "HAS_CANDIDATES"


@dataclass(frozen=True)
class ScreenDiagnostics:
    scanned: int
    had_history: int
    above_trend: int
    cleared: int

    def __post_init__(self) -> None:
        seq = [self.scanned, self.had_history, self.above_trend, self.cleared]
        if any(v < 0 for v in seq):
            raise ValueError("counts must be >= 0")
        if not (self.scanned >= self.had_history >= self.above_trend >= self.cleared):
            raise ValueError("counts must be monotonically non-increasing through the funnel")

    @property
    def history_coverage(self) -> float:
        return self.had_history / self.scanned if self.scanned else 0.0


def classify_screen(d: ScreenDiagnostics, coverage_floor: float) -> ScreenVerdict:
    if d.cleared > 0:
        return ScreenVerdict.HAS_CANDIDATES
    if d.history_coverage < coverage_floor:
        return ScreenVerdict.UNDER_POWERED
    return ScreenVerdict.EARNED_ABSTENTION
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/domain/test_screen_diagnostics.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git checkout data/reports/
git add domain/screen_diagnostics.py tests/domain/test_screen_diagnostics.py
git commit -m "feat: pure-domain screen diagnostics + honesty verdict"
```

---

### Task 2: Populate ScreenDiagnostics in the screen use case

**Files:**
- Modify: `application/evidence_screen_use_case.py` (the `run()` eligibility loop, ~lines 75–94, 169–176)
- Modify: `domain/screen_models.py` (add `diagnostics: ScreenDiagnostics | None = None` field to `ScreenResult`, default None for back-compat)
- Test: `tests/test_evidence_screen_use_case.py` (add a diagnostics case using the existing fakes)

- [ ] **Step 1: Write the failing test** — add to the existing file, reuse its fake ports:

```python
def test_run_populates_diagnostics_counts(make_uc):  # use existing fixture/builder
    uc = make_uc(history={"A": True, "B": True, "C": False},
                 trend={"A": 2.0, "B": -1.0, "C": 0.0})
    res = uc.run(universe=["A", "B", "C"], as_of="2026-06-14", top_n=10)
    assert res.diagnostics is not None
    assert res.diagnostics.scanned == 3
    assert res.diagnostics.had_history == 2     # A, B
    assert res.diagnostics.above_trend == 1     # A only (trend>0)
    assert res.diagnostics.cleared == len(res.candidates)
```

If the test file lacks a `make_uc` builder, write one mirroring the fakes already in that file (do not invent new port shapes — copy the existing fakes).

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_evidence_screen_use_case.py -k diagnostics -v`
Expected: FAIL (`diagnostics` is None / attribute missing)

- [ ] **Step 3: Implement** — in `run()`, count gates while iterating the universe:

```python
from domain.screen_diagnostics import ScreenDiagnostics
# inside run(), before the eligibility loop:
_scanned = len(universe)
_had_history = 0
_above_trend = 0
for t in universe:
    th = self._price.trend_health(t)
    hist_ok = self._price.has_min_history(t)
    if hist_ok:
        _had_history += 1
    if hist_ok and th > 0.0:
        _above_trend += 1
    if not eligible(th, hist_ok):
        continue
    ...
# when building BOTH ScreenResult returns (empty + populated), pass:
diagnostics=ScreenDiagnostics(scanned=_scanned, had_history=_had_history,
                              above_trend=_above_trend, cleared=len(<candidates>))
```

Add the `diagnostics` field to `ScreenResult` (frozen dataclass, default `None`).

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_evidence_screen_use_case.py tests/test_domain_screen_models.py -v`
Expected: PASS (all, including existing)

- [ ] **Step 5: Commit**

```bash
git checkout data/reports/
git add application/evidence_screen_use_case.py domain/screen_models.py tests/test_evidence_screen_use_case.py
git commit -m "feat: populate ScreenDiagnostics gate counts in screen use case"
```

---

### Task 3: Single source of truth for `abstained`

**Files:**
- Modify: `application/brief_summary.py:21` (stop redefining `abstained = len(candidates)==0`)
- Test: `tests/test_brief.py` (add)

- [ ] **Step 1: Write the failing test**

```python
def test_brief_summary_does_not_redefine_abstained(sample_brief_with_candidates):
    # brief has candidates AND its source abstained flag is False
    out = build_brief_summary(sample_brief_with_candidates)
    assert out["abstained"] is False  # must mirror source, not len(candidates)==0
```

Build `sample_brief_with_candidates` from the existing brief fixtures in that test module (reuse, don't invent).

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_brief.py -k abstained -v`
Expected: FAIL (current code returns `len(candidates)==0`)

- [ ] **Step 3: Implement** — carry the real flag through:

```python
"abstained": bool(getattr(brief, "abstained", False)),
```

(Confirm the brief object exposes `abstained`; if it derives from `ScreenResult`, thread it through `WeeklyBrief`.)

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_brief.py tests/test_cli_weekly_brief.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git checkout data/reports/
git add application/brief_summary.py tests/test_brief.py
git commit -m "fix: single source of truth for screen 'abstained' flag"
```

---

### Task 4: Risk rubric classification (pure domain)

**Files:**
- Create: `domain/risk_rubric.py`
- Test: `tests/domain/test_risk_rubric.py`

- [ ] **Step 1: Write the failing test**

```python
from domain.risk_rubric import (
    classify_net_beta, classify_systematic_share, net_beta_position, NetBetaBand, ShareBand,
)

def test_net_beta_bands():
    assert classify_net_beta(-0.3) is NetBetaBand.HEDGED
    assert classify_net_beta(0.5) is NetBetaBand.DEFENSIVE
    assert classify_net_beta(1.0) is NetBetaBand.MARKET_LIKE
    assert classify_net_beta(1.42) is NetBetaBand.ELEVATED
    assert classify_net_beta(1.8) is NetBetaBand.AGGRESSIVE

def test_net_beta_boundaries_lower_inclusive_upper_exclusive():
    assert classify_net_beta(0.8) is NetBetaBand.MARKET_LIKE
    assert classify_net_beta(1.2) is NetBetaBand.ELEVATED
    assert classify_net_beta(1.6) is NetBetaBand.AGGRESSIVE
    assert classify_net_beta(0.0) is NetBetaBand.DEFENSIVE

def test_systematic_share_bands_and_flag_boundary():
    assert classify_systematic_share(0.30, flag=0.60) is ShareBand.STOCK_SPECIFIC
    assert classify_systematic_share(0.50, flag=0.60) is ShareBand.BALANCED
    assert classify_systematic_share(0.60, flag=0.60) is ShareBand.MACRO_LEANING  # flag edge
    assert classify_systematic_share(0.80, flag=0.60) is ShareBand.MACRO_DOMINATED

def test_net_beta_position_maps_domain_minus_half_to_two():
    assert net_beta_position(0.0) == 20.0
    assert net_beta_position(1.0) == 60.0
    assert abs(net_beta_position(1.6) - 84.0) < 1e-9
    assert net_beta_position(-1.0) == 0.0   # clamps to domain min
    assert net_beta_position(3.0) == 100.0  # clamps to domain max
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/domain/test_risk_rubric.py -v`
Expected: FAIL (module missing)

- [ ] **Step 3: Implement**

```python
"""Pure risk rubric: character-not-quality bands + scale positions (stdlib only)."""
from __future__ import annotations
from enum import Enum


class NetBetaBand(Enum):
    HEDGED = "Hedged"; DEFENSIVE = "Defensive"; MARKET_LIKE = "Market-like"
    ELEVATED = "Elevated"; AGGRESSIVE = "Aggressive"


class ShareBand(Enum):
    STOCK_SPECIFIC = "Stock-specific"; BALANCED = "Balanced"
    MACRO_LEANING = "Macro-leaning"; MACRO_DOMINATED = "Macro-dominated"


def classify_net_beta(v: float) -> NetBetaBand:
    if v < 0.0: return NetBetaBand.HEDGED
    if v < 0.8: return NetBetaBand.DEFENSIVE
    if v < 1.2: return NetBetaBand.MARKET_LIKE
    if v < 1.6: return NetBetaBand.ELEVATED
    return NetBetaBand.AGGRESSIVE


def classify_systematic_share(v: float, flag: float = 0.60) -> ShareBand:
    if v < 0.40: return ShareBand.STOCK_SPECIFIC
    if v < flag: return ShareBand.BALANCED
    if v < 0.75: return ShareBand.MACRO_LEANING
    return ShareBand.MACRO_DOMINATED


_DOMAIN_LO, _DOMAIN_HI = -0.5, 2.0  # net beta rendered domain


def net_beta_position(v: float) -> float:
    """Linear position 0..100 for the needle; clamps outside the rendered domain."""
    pct = (v - _DOMAIN_LO) / (_DOMAIN_HI - _DOMAIN_LO) * 100.0
    return max(0.0, min(100.0, pct))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/domain/test_risk_rubric.py -v`
Expected: PASS

- [ ] **Step 5: Add a Hypothesis monotonicity property test, then commit**

```python
from hypothesis import given, strategies as st

@given(st.floats(min_value=-1, max_value=3, allow_nan=False))
def test_net_beta_position_monotonic_nondecreasing(v):
    assert net_beta_position(v - 0.01) <= net_beta_position(v) + 1e-9
```

```bash
git checkout data/reports/
git add domain/risk_rubric.py tests/domain/test_risk_rubric.py
git commit -m "feat: pure-domain risk rubric bands + scale positions"
```

---

## Phase 1 — Screener tab (supersede)

### Task 5: Screener diagnostic funnel + verdict line

**Files:**
- Modify: `adapters/visualization/tabs/research_candidates.py`
- Reference: `adapters/visualization/components/funnel.py` (existing), the approved mockup §Screener
- Test: extend `tests/test_honest_state_snapshots.py` OR new `tests/test_research_candidates_tab.py`

Render rules (consume `ScreenResult.diagnostics` + `classify_screen`, coverage floor from `config/markets/us.yaml`; default 0.5):
- Funnel row: `scanned → had_history → above_trend → cleared`.
- Verdict-driven headline (NEVER hardcode "discipline working"):
  - `UNDER_POWERED` → ⚠ "Screen under-powered — only X of N had usable price history" (danger color).
  - `EARNED_ABSTENTION` → ✓ "Working as designed — scanned & scored, none cleared the bar" (success).
  - `HAS_CANDIDATES` → "N cleared, of 512 scanned" + candidate list (Task 6).
- RESEARCH_ONLY pill always visible.

- [ ] **Step 1:** Write a render-contract test: feed a fake result with `diagnostics=ScreenDiagnostics(512,490,300,70)`; assert the rendered markdown (capture via the same harness `test_honest_state_snapshots.py` uses) contains "70" and NOT the string "discipline working". Add an `UNDER_POWERED` case asserting "under-powered".
- [ ] **Step 2:** Run it; expect FAIL (current tab hardcodes the discipline copy).
- [ ] **Step 3:** Implement the verdict switch in `render()`, reading `result.diagnostics`. Use existing `funnel.py` for the bars; map verdict→headline+color via a small local helper.
- [ ] **Step 4:** Run `python -m pytest tests/test_research_candidates_tab.py tests/test_honest_state_snapshots.py -v`; expect PASS.
- [ ] **Step 5:** Commit (`feat: screener verdict-driven funnel (no false 'discipline working')`).

### Task 6: Screener candidate cards — 4 real factors

**Files:** Modify `adapters/visualization/tabs/research_candidates.py`; reference `components/cards.py`, mockup §Screener.

Render rules (per the live-run correction — ALL 4 factors populate; revision may be per-ticker gap):
- Top ~10 candidates: rich card — ticker · composite (labelled "research-priority score, not a forecast") · 4 factor rows (momentum/revision/quality/value), each z-bar centered at 0 (green right / red left) + percentile; a per-ticker `None` factor renders DATA-GAP (hatched), never a number.
- Remaining candidates: compact table (ticker · composite · top factor).
- "What this tells you" line (research read) + "Do next" (research step) — investigation language only, never buy/sell.

- [ ] **Step 1:** Render-contract test: a fake candidate with all 4 factor scores → assert all four factor names appear and composite label includes "not a forecast"; a candidate with `revision=None` → assert "gap"/DATA-GAP rendered, no fabricated number.
- [ ] **Step 2:** Run; expect FAIL.
- [ ] **Step 3:** Implement cards (top-N rich) + tail table. Reuse `cards.py`/`formatters.py` patterns + design tokens.
- [ ] **Step 4:** Run the tab tests; PASS.
- [ ] **Step 5:** Commit (`feat: screener 4-factor candidate cards + research read`).

---

## Phase 2 — Risk tab (additive)

### Task 7: Risk rubric band strips (prepend, keep charts)

**Files:** Modify `adapters/visualization/tabs/risk.py`; test `tests/test_risk_tab.py`.

Render rules (Option A — additive): ABOVE the existing factor-bar/donut/conclusion, render two band strips using `domain/risk_rubric.py`:
- Net beta strip (Hedged/Defensive/Market-like/Elevated/Aggressive) with needle at `net_beta_position(net_beta)`, anchors 0 and 1.0; band label pill from `classify_net_beta`.
- Systematic-share strip (4 bands) with needle at `share*100`, flag tick at 60; pill from `classify_systematic_share` (flag from config).
- Character-not-quality coloring (mono distance ramp, NOT RAG). Keep all existing charts below, unchanged.

- [ ] **Step 1:** Extend `test_risk_tab.py`: feed net_beta=1.42, share=0.628 → assert rendered output contains "Elevated" and "Macro-leaning" and the existing chart elements still present.
- [ ] **Step 2:** Run; expect FAIL (bands not rendered).
- [ ] **Step 3:** Implement the two strips at top of `render()`; reuse `classify_*`/`net_beta_position`. Do not remove existing chart calls.
- [ ] **Step 4:** Run `python -m pytest tests/test_risk_tab.py -v`; PASS.
- [ ] **Step 5:** Commit (`feat: risk tab distance-ramp band strips (additive)`).

---

## Phase 3 — Home tab (hybrid + fix anti-KPI)

### Task 8: Home triage strip (lead) + fix 512→0 ledger tile

**Files:** Modify `adapters/visualization/tabs/weekly_brief.py`; reference `components/metrics.py`, `ledger.py`; test `tests/test_weekly_brief_tab.py`.

Render rules (Option: hybrid):
- NEW triage strip ABOVE the evidence ledger: tiles `Need review (N/total)` · `vs Market (1y)` · `Net beta + band pill` (reuse `classify_net_beta`) · `Regime`. "Need review" leads (dominant). Plain-language line under it.
- FIX the ledger "screen" anti-KPI tile: derive from `ScreenResult.diagnostics`/verdict. If `HAS_CANDIDATES` → "N cleared / 512" (NOT "512→0 ABSTAINED =EMH"). The EMH/falsification framing only applies to the return-prediction tiles (47.4%, 0.004), which stay.
- Evidence ledger stays below the triage strip.

- [ ] **Step 1:** Test: with a diagnostics showing cleared=70 → assert rendered Home does NOT contain "512→0 ABSTAINED" and DOES contain "70"; assert "Need review" present.
- [ ] **Step 2:** Run; expect FAIL.
- [ ] **Step 3:** Implement triage strip + verdict-driven screen tile. Keep the two return-prediction anti-KPIs intact.
- [ ] **Step 4:** Run `python -m pytest tests/test_weekly_brief_tab.py -v`; PASS.
- [ ] **Step 5:** Commit (`feat: home hybrid triage strip + honest screen tile`).

---

## Phase 4 — My Portfolio tab (decision-card rows)

### Task 9: Holding decision-card rows

**Files:** Modify `adapters/visualization/tabs/positions.py`; reference `components/compact_card.py`, `verdicts.py`; test new `tests/test_positions_tab.py` (or extend existing positions tests if present).

Render rules: each holding row = ticker · verdict pill (discipline rule; "review prompt, not forecast") · 5 RAG signal dots · one-line meaning · unrealized % · expander → existing evidence. Reuse `verdicts.py` for the pill, `compact_card.py` patterns.

- [ ] **Step 1:** Test: a holding with verdict TRIM + 5 signals → assert pill text "TRIM", 5 dots rendered, "%" present, and verdict copy contains "review" not "buy"/"sell".
- [ ] **Step 2:** Run; expect FAIL.
- [ ] **Step 3:** Implement decision-card rows; keep expander evidence.
- [ ] **Step 4:** Run the positions tab tests; PASS.
- [ ] **Step 5:** Commit (`feat: my-portfolio decision-card rows`).

---

## Phase 5 — Trust tab (audit only)

### Task 10: Re-source any 512→0 citation

**Files:** Modify `adapters/visualization/tabs/trust.py`; test `tests/test_trust_tab.py`.

Render rules: KEEP the 7 experiment cards + the return-prediction falsification tiles (0.004 / 47.4% — these are real, untouched). ONLY audit any card/sentence that cites the screener "512→0 abstention" as evidence; re-source it to the verdict (post-fix the screener clears candidates). If no such citation exists, this task is a no-op verified by a test asserting Trust contains no "512 → 0" abstention-as-evidence string.

- [ ] **Step 1:** Test: assert `trust.py` rendered output contains no "512" tied to "abstain"/"ABSTAINED" as evidence (grep-style assertion); the falsification tiles (47.4%, 0.004) remain.
- [ ] **Step 2:** Run; expect FAIL only if a citation exists.
- [ ] **Step 3:** If failing, correct the copy; else confirm no-op.
- [ ] **Step 4:** Run `python -m pytest tests/test_trust_tab.py -v`; PASS.
- [ ] **Step 5:** Commit (`chore: trust tab — re-source 512→0 citation, keep falsification record`).

---

## Final — Verification

- [ ] `git checkout data/reports/` then `python -m pytest -q` → all pass.
- [ ] `python -m mypy domain/ adapters/ application/` → clean.
- [ ] `pre-commit run --files <all changed>` → green.
- [ ] Launch dashboard + screenshot the 5 changed tabs (`scripts/screenshot_dashboard.py --debug-port 9223`); confirm against the approved mockup. Hand screenshots to the user for next-session review.
- [ ] REQUIRED: run superpowers:verification-before-completion before claiming done.

## Self-review notes
- Stock Analysis (tab 4) intentionally NOT in this plan (deferred).
- Domain logic (Tasks 1,4) is fully TDD'd; UI tasks (5–10) verify via render-contract tests + screenshots (Streamlit layout isn't unit-test-friendly — snapshot/contract is the project's existing pattern, see `test_honest_state_snapshots.py`).
- Honesty rails restated per task; no buy/sell anywhere; DATA-GAP for missing values.
