# S5 — Zone ② "Check Your Own List" Full-Matrix Parity Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or executing-plans. Checkbox steps.
> **DRIFT GUARD:** mockup `screener-FINAL-v2.html` Zone ② (NVDA expanded). The pasted-name card must match the shortlist card.

**Goal:** Make "Run the check" render the **same expandable 5-factor card** as the shortlist (bands,
percentile vs cohort, fit verdict, Google-AI hook) — in-screen names reuse stored scores, off-universe
names are live-computed, DATA-GAP where data is thin.

**Architecture:** `FitVerdict`/`BatchFitRow` currently carry only the grade (`domain/fit.py:38-44`).
Add the 5 factor scores. A new use-case computes/looks-up factors + percentile-vs-cohort. The render
reuses S3's `factor_row` + `factor_bands`.

**Anchors:** `application/batch_fit_use_case.py:16-20,61-107`; `application/fit_use_case.py:50-73`
(`gather_and_assess`, reads `universe_composites`); `evidence_screen_use_case.py:119-141` percentile.

---

### Task 1: Extend BatchFitRow with factor scores

**Files:**
- Modify: `application/batch_fit_use_case.py:16-20`
- Test: `tests/application/test_batch_fit.py`

- [ ] **Step 1: Write the failing test**

```python
from application.batch_fit_use_case import BatchFitRow
def test_batchfitrow_carries_factor_scores():
    row = BatchFitRow(ticker="KO", verdict=_fake_verdict(), fetch_ok=True,
                      factor_scores=[{"name":"quality","value":0.5,"percentile":0.80}])
    assert row.factor_scores[0]["name"] == "quality"
```

- [ ] **Step 2:** Run → FAIL (`factor_scores` arg unknown).
- [ ] **Step 3:** Add `factor_scores: list[dict] = field(default_factory=list)` to `BatchFitRow`
  (`@dataclass(frozen=True)` → use `tuple` + `field(default=())` for hashability; store dicts as a tuple).
- [ ] **Step 4:** Run → PASS. **Step 5:** Commit `"feat: BatchFitRow carries factor_scores (S5 T1)"`.

---

### Task 2: Factor lookup/compute for an arbitrary ticker

**Files:**
- Create: `application/ticker_factors_use_case.py`
- Test: `tests/application/test_ticker_factors.py`

- [ ] **Step 1: Write the failing test**

```python
def test_in_screen_ticker_reuses_stored_scores(fake_screen_with_factors):
    fs = ticker_factor_scores("SPG", screen=fake_screen_with_factors, fetch_fn=_no_fetch)
    assert {f["name"] for f in fs} >= {"momentum","value","quality","lowvol"}
    assert fs[0]["percentile"] is not None

def test_off_universe_ticker_live_computes_and_ranks(fake_screen_with_factors, fake_fetch):
    fs = ticker_factor_scores("ZZZZ", screen=fake_screen_with_factors, fetch_fn=fake_fetch)
    # percentile derived by ranking the live z against the cohort distribution
    assert all(0.0 <= f["percentile"] <= 1.0 for f in fs if f["percentile"] is not None)

def test_missing_data_is_data_gap(fake_screen_with_factors):
    fs = ticker_factor_scores("NODATA", screen=fake_screen_with_factors, fetch_fn=_fetch_raises)
    assert any(f["percentile"] is None for f in fs)   # DATA-GAP, never fabricated
```

- [ ] **Step 2:** Run → FAIL (module missing).
- [ ] **Step 3:** Implement `ticker_factor_scores(ticker, screen, fetch_fn)`:
  - if `ticker` in `screen["candidates"]` → return its stored `factor_scores` (reuse, free).
  - else → `fetch_fn` returns raw sub-scores; **reuse** the screen's cohort z-distribution (persisted)
    to compute each factor's percentile by ranking the live z among cohort z's (mirror
    `evidence_screen_use_case.py:119-141`). No NEW scoring logic.
  - any factor whose raw input is missing → `{"name":f, "value":None, "percentile":None}` (DATA-GAP).
- [ ] **Step 4:** Run → PASS. Look-ahead: live fetch uses `as_of`/now only. **Step 5:** Commit.

---

### Task 3: Wire batch_fit to populate factor_scores

**Files:**
- Modify: `application/batch_fit_use_case.py:61-107` (`batch_fit`, `default_fit_fn`)
- Test: `tests/application/test_batch_fit.py`

- [ ] **Step 1: Write the failing test** — `batch_fit(["KO"], …)` returns a row whose `factor_scores`
  is non-empty.
- [ ] **Step 2:** Run → FAIL. **Step 3:** in `batch_fit`, after building the `FitVerdict`, call
  `ticker_factor_scores` and attach to the row. **Step 4:** Run → PASS. **Step 5:** Commit.

---

### Task 4: Render Zone ② cards with the shortlist component

**Files:**
- Modify: `adapters/visualization/tabs/research_candidates.py` (Zone ② block)
- Reuse: `factor_row`, `factor_bands.plain_read`, S3 row component
- Test: `tests/adapters/test_research_candidates.py`

- [ ] **Step 1: Write the failing test**

```python
def test_zone2_card_matches_shortlist(fake_batch_rows):
    html = rc.build_check_your_own_html(fake_batch_rows)
    for token in ("Quality","Value","Low-vol","STRONG","fit"):
        assert token in html
    assert "p" in html  # percentile shown
```

- [ ] **Step 2:** Run → FAIL. **Step 3:** implement `build_check_your_own_html(rows)` reusing the same
  collapsible row + `render_factor_row` ×5 + grade badge (STRONG/MODERATE/WEAK with glossary "i") +
  fit-vs-book line from the verdict flags + Google-AI hook (S6). Note off-universe vs in-screen in the
  row subtitle ("your list · live-computed" / "in this week's screen"). **Step 4:** Run → PASS. Drift
  check vs mockup Zone ②. **Step 5:** Commit.

---

### Task 5: Honesty + gate

- [ ] Test: Zone ② HTML has no FORBIDDEN_WORDS; DATA-GAP rows show "DATA-GAP" not a number.
- [ ] `make check` green. Commit.

## Self-review (S5)
- Spec coverage §5 S5: extend verdict ✓T1, lookup/compute+percentile+DATA-GAP ✓T2, wire ✓T3,
  full-card render ✓T4, cap 25 unchanged (batch_fit MAX_TICKERS untouched). ✓
- Placeholders: none. Type consistency: `factor_scores` dict shape matches S3 `render_factor_row`
  args (`name/value/percentile`). ✓
