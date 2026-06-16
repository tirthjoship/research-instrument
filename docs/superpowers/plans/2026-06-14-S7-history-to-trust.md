# S7 — Move Screen History to Trust Tab Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or executing-plans. Checkbox steps.
> **DRIFT GUARD:** mockup Zone ③ — screener shows only a one-line link; the table lives on Trust.

**Goal:** Relocate the screen-history table from the screener to the Trust tab; leave a one-line link on
the screener. No data change.

**Anchors:** history render currently in `research_candidates.py:32-51` (`_render_history_and_upload`);
loader `load_screen_history`; Trust tab `adapters/visualization/tabs/trust.py`.

---

### Task 1: Render history on Trust tab

**Files:**
- Modify: `adapters/visualization/tabs/trust.py`
- Test: `tests/adapters/test_trust.py`

- [ ] **Step 1: Write the failing test**

```python
from adapters.visualization.tabs import trust
def test_trust_renders_screen_history(fake_history):
    html = trust.build_screen_history_html(fake_history)
    assert "Past screens" in html or "Screen history" in html
    assert "Universe" in html and "Passed" in html
```

- [ ] **Step 2:** Run → FAIL. **Step 3:** add `build_screen_history_html(history)` to `trust.py`
  (reuse `load_screen_history` shape: Date/Universe/Passed/Abstained) in Home tokens; wire into
  `trust.render()`. **Step 4:** Run → PASS. **Step 5:** Commit `"feat: screen history on Trust tab (S7 T1)"`.

---

### Task 2: Replace screener history block with a link

**Files:**
- Modify: `adapters/visualization/tabs/research_candidates.py` (remove history table from
  `_render_history_and_upload`; keep the upload/Zone ② part)
- Test: `tests/adapters/test_research_candidates.py`

- [ ] **Step 1: Write the failing test**

```python
def test_screener_zone3_is_link_not_table(fake_screen):
    html = rc.build_zone3_html()
    assert "Trust tab" in html and "See past screens" in html
    assert "Universe" not in html        # table no longer here
```

- [ ] **Step 2:** Run → FAIL. **Step 3:** implement `build_zone3_html()` = the one-line link; delete the
  history-table code path from the screener (keep Zone ② upload intact, owned by S5). **Step 4:** Run →
  PASS. **Step 5:** Commit `"refactor: screener history → Trust link (S7 T2)"`.

---

### Task 3: Gate

- [ ] `pytest tests/ -k "trust or research_candidates" -v` → PASS. `make check` green. Commit.

## Self-review (S7)
- Spec coverage §5 S7: history on Trust ✓T1, screener link only ✓T2, loader reused (no data change). ✓
- Placeholders: none. Type consistency: `load_screen_history` shape unchanged. ✓
