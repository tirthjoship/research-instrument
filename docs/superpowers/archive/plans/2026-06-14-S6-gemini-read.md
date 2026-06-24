# S6 — Attributed Google-AI Read on the Screener Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or executing-plans. Checkbox steps.
> **HONESTY HARD STOP:** The Gemini read is a companion BESIDE the score. It is **never** passed to, or derived into, any factor or composite. No exception.
> **DRIFT GUARD:** mockup `.gai` block ("Google-AI read · ▲ in favor · ▼ to watch · cited case →").

**Goal:** On a row expand, render an attributed "Google-AI read" (≤5 in-favor / ≤5 to-watch) summarizing
already-fetched public facts+news, reusing the shipped `GeminiNarratorAdapter`. Lazy, fail-safe, local-only.

**Architecture:** `adapters/ml/gemini_narrator.py` already exists (`:14-58`): `summarize_case(ctx)` →
`CaseResult(in_favor, to_watch, data_gap)`, no score access, forbidden-words negated, fails safe. S6
only builds the `CaseContext` from already-fetched data, calls it lazily on expand, and renders the
attributed block into the S3/S5 `<div id=gai-…>` hook.

**Anchors:** `adapters/ml/gemini_narrator.py:14-19,44-58`; v9 card privacy pattern (`is_local_runtime`).

---

### Task 1: CaseContext builder from already-fetched data

**Files:**
- Create: `adapters/visualization/components/gemini_read.py`
- Test: `tests/adapters/test_gemini_read.py`

- [ ] **Step 1: Write the failing test**

```python
from adapters.visualization.components.gemini_read import build_case_context
def test_build_context_uses_only_supplied_facts_and_news():
    ctx = build_case_context(ticker="SPG", facts={"occupancy":"recovering"},
                             news=[{"title":"REIT rates ease"}])
    assert ctx.ticker == "SPG"
    # context carries NO score/composite/grade field
    assert not hasattr(ctx, "composite") and not hasattr(ctx, "evidence_grade")
```

- [ ] **Step 2:** Run → FAIL. **Step 3:** implement `build_case_context` returning the adapter's
  `CaseContext` from supplied facts+news only (no scores). **Step 4:** Run → PASS. **Step 5:** Commit.

---

### Task 2: Render attributed block, fail-safe

**Files:**
- Modify: `adapters/visualization/components/gemini_read.py`
- Test: `tests/adapters/test_gemini_read.py`

- [ ] **Step 1: Write the failing test**

```python
def test_render_gemini_read_attributed_and_safe():
    res = _CaseResult(in_favor=("occupancy recovering",), to_watch=("refi wall",), data_gap=False)
    html = render_gemini_read(res)
    assert "Google-AI read" in html
    assert "never an input" in html.lower()      # attribution disclaimer
    assert "occupancy recovering" in html and "refi wall" in html

def test_render_gemini_read_data_gap_hides_or_notes():
    res = _CaseResult((), (), True)
    html = render_gemini_read(res)
    assert "unavailable" in html.lower() or html == ""

def test_gemini_read_no_forbidden_words():
    res = _CaseResult(in_favor=("strong demand",), to_watch=("valuation",), data_gap=False)
    low = render_gemini_read(res).lower()
    for w in ("buy","sell","winner","conviction","predict","alpha","outperform"):
        assert w not in low.split()
```

- [ ] **Step 2:** Run → FAIL. **Step 3:** implement `render_gemini_read(result)` → the `.gai` block
  (▲ in-favor / ▼ to-watch + "summary beside the score — never an input" + "cited case →" link);
  `data_gap` → "Google-AI read unavailable" or empty. **Step 4:** Run → PASS. **Step 5:** Commit.

---

### Task 3: Lazy call on expand + privacy guard

**Files:**
- Modify: `adapters/visualization/tabs/research_candidates.py` (fill the `gai-…` hook on expand)
- Test: `tests/adapters/test_research_candidates.py`

- [ ] **Step 1:** Using context7, confirm `st.fragment`/expander lazy pattern (only call Gemini when a
  row is open, not on every render — cost + latency).
- [ ] **Step 2: Write the failing test** — when `is_local_runtime()` is False, the read is NOT called
  (privacy fail-safe), block shows nothing/"local only".

```python
def test_gemini_skipped_when_not_local(monkeypatch):
    monkeypatch.setattr(rc, "is_local_runtime", lambda: False)
    html = rc.maybe_render_gemini("SPG", facts={}, news=[])
    assert html == "" or "local" in html.lower()
```

- [ ] **Step 3:** Run → FAIL. **Step 4:** implement `maybe_render_gemini(ticker, facts, news)`:
  guard on `is_local_runtime()`; build context; call adapter; render; cache per ticker in
  `st.session_state` to avoid re-calling. **Step 5:** Run → PASS. **Step 6:** Commit.

---

### Task 4: Honesty + gate

- [ ] Test: a static check that `gemini_read` / `research_candidates` never import or reference the
  composite/factor values when building the context (grep test or AST assertion).
- [ ] `make check` green. Commit.

## Self-review (S6)
- Spec coverage §5 S6 + §2 invariant: attributed-only ✓ (Task 1/4 prove no score access), lazy ✓ T3,
  fail-safe ✓ T2, forbidden-words ✓ T2, privacy ✓ T3. ✓
- Placeholders: none. Type consistency: reuses adapter `CaseContext`/`CaseResult` as shipped. ✓
