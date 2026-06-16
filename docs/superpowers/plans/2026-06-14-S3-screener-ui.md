# S3 — Screener Tab UI Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.
> **DRIFT GUARD:** The canonical mockup `.superpowers/brainstorm/screener-FINAL-v2.html` is served live (companion URL). After EACH render task, open it beside the running tab (`make daily-scan` data + `streamlit run`) and confirm: same fonts, same tile layout, same bucket order, same collapsible behaviour. Any structural difference = drift; fix before moving on.
> **REQUIRED SUB-SKILL for build:** `frontend-design` — invoke it before writing the HTML/CSS of Tasks 3–7 to keep production quality and avoid generic styling.

**Goal:** Rewrite `adapters/visualization/tabs/research_candidates.py` to the locked design: Home design
tokens, 4 tiles, "how to read" legend, view toggle, 6 reason buckets with collapsible 5-factor cards,
honest disclosure + funnel, footer ledger. Retire all bespoke inline hex.

**Architecture:** The tab composes existing components (`proof_tile`, `tooltip`/glossary, `funnel`,
`status_pill_html`) + the new domain helpers (`factor_bands`, `screen_buckets`). Rendering helpers move
into small focused functions; the 443-line monolith is split so each piece is independently readable.

**Tech Stack:** Streamlit, the shared CSS in `styles.py`, glossary tooltips, Python 3.12.

**Mockup pin table:** see INDEX + spec §7. Each task names its anchor.

---

### Task 1: Glossary entries the new UI needs

**Files:**
- Modify: `adapters/visualization/components/glossary.py`
- Test: `tests/adapters/test_glossary.py`

The factor "i" clouds and legend rely on glossary terms. "Momentum/Revision/Quality/Value factor" exist;
add the missing ones so `tooltip()` never KeyErrors (spec caveat: `tooltip()` raises on undocumented).

- [ ] **Step 1: Write the failing test**

```python
# tests/adapters/test_glossary.py
import pytest
from adapters.visualization.components import glossary as g

@pytest.mark.parametrize("term", [
    "Evidence score", "Percentile", "Low-vol factor", "Analyst spread",
    "Trend gate", "Reason bucket",
])
def test_new_glossary_terms_present(term):
    assert term in g.GLOSSARY and len(g.GLOSSARY[term]) > 10
```

- [ ] **Step 2: Run** → FAIL (KeyErrors).
- [ ] **Step 3: Implement** — add entries (truthful, forecast-free):
```python
# add to GLOSSARY
"Evidence score": "Equal-weight average of the factor z-scores. Higher = more factors look strong now. A ranking aid, not a predicted return.",
"Percentile": "Where a name ranks among this week's trend-eligible cohort. p95 = stronger than 95% of them — not vs its sector, not vs the full universe.",
"Low-vol factor": "How little the price swings (trailing volatility). Higher score = steadier, smaller drawdowns historically. Descriptive, not a forecast.",
"Analyst spread": "Width of today's analyst price-target range (high vs low). A dispersion signal, not estimate-revision over time.",
"Trend gate": "A loose filter that keeps only names above their 200-day average. Most survivors aren't special — the ranking is the selective part.",
"Reason bucket": "A plain-English grouping (e.g. cheap & high-quality) derived from a name's strongest factors, so you see the kind of opportunity before the name.",
```
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `git commit -m "feat: glossary terms for screener redesign (S3 Task 1)"`

---

### Task 2: Factor-band UI adapter (key → label/tone/glossary term)

**Files:**
- Create: `adapters/visualization/components/factor_row.py`
- Test: `tests/adapters/test_factor_row.py`

Bridges domain `factor_bands` → HTML. Maps `band_tone_key` → the styles.py colour var; maps the factor
key → its display label + glossary term.

- [ ] **Step 1: Write the failing test**

```python
# tests/adapters/test_factor_row.py
from adapters.visualization.components.factor_row import render_factor_row

def test_render_factor_row_has_band_and_percentile_and_tooltip():
    html = render_factor_row("quality", value=2.83, percentile=0.95)
    assert "Exceptional" in html          # band label
    assert "p95" in html                  # percentile
    assert "ri-ttip" in html or "Quality factor" in html   # glossary tooltip wired
    assert "#" not in html.split("var(")[0][-2:]  # colour comes from a var(), not raw hex inline

def test_render_factor_row_data_gap():
    html = render_factor_row("lowvol", value=None, percentile=None)
    assert "DATA-GAP" in html
```

- [ ] **Step 2: Run** → FAIL (module missing).
- [ ] **Step 3: Implement** — map key→(label, glossary term); use `domain.factor_bands.band_for_percentile`
  + `band_tone_key`; colour via `var(--success|--accent|--text-muted|--danger)`; percentile `p{round*100}`;
  `None`→DATA-GAP (never fabricate). Render the diverging bar like the mockup `.frow`/`.bar`.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `git commit -m "feat: factor_row HTML adapter over factor_bands (S3 Task 2)"`

**Mockup pin:** `.frow` rows in any expanded `.row` (label · `.band` · `.bar` · `.pp`).

---

### Task 3: Header + 4 tiles + footer ledger (Home tokens)

**Files:**
- Modify: `adapters/visualization/tabs/research_candidates.py` (replace `render` header block)
- Reuse: `adapters/visualization/components/proof_tile.py`
- Test: `tests/adapters/test_research_candidates.py` (render smoke)

- [ ] **Step 1: Write the failing test**

```python
# tests/adapters/test_research_candidates.py
from adapters.visualization.tabs import research_candidates as rc

def test_header_and_tiles_render(monkeypatch, fake_screen):
    # fake_screen: fixture monkeypatching load_latest_screen to return a small screen dict
    html = rc.build_header_html(fake_screen)
    assert "research shortlist" in html.lower()
    assert "not a forecast" in html.lower()         # tile 2 sub
    assert "Showing" in html or "of 304" in html    # tile 1
    assert "UNIVERSE" in html and "CLEARED" in html # footer ledger
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** `build_header_html` — Fraunces headline "This week's research shortlist.",
  italic subhead, IBM-Plex-Mono eyebrow; 4 tiles via `render_tile` (Showing `15 of 304` / As of `Jun 14`
  "current evidence, not a forecast" / Factors `5` / Trust = latest IC verdict from `load_latest_ic_verdict`,
  honest "Inconclusive" unless PASS); mono footer ledger (`UNIVERSE · CLEARED · SHOWN · FACTORS · AS OF ·
  IC GATE · RESEARCH_ONLY`). All colours from styles.py vars; NO inline hex.
- [ ] **Step 4: Run** → PASS. **Drift check:** compare to mockup `.tiles` + `.ledger`.
- [ ] **Step 5: Commit** `git commit -m "feat: screener header + 4 tiles + ledger in Home tokens (S3 Task 3)"`

---

### Task 4: How-to-read legend + honest disclosure

**Files:**
- Modify: `research_candidates.py`
- Test: `tests/adapters/test_research_candidates.py`

- [ ] **Step 1: Write the failing test**

```python
def test_legend_and_disclosure():
    html = rc.build_legend_html()
    for token in ("Exceptional", "Strong", "Flat", "Weak", "p95", "Evidence score"):
        assert token in html
    dis = rc.build_disclosure_html()
    assert "not a forecast" in dis.lower()
    assert "momentum" in dis.lower() and "no proven edge" in dis.lower()
```

- [ ] **Step 2: Run** → FAIL. **Step 3:** implement both (mockup `#lg .legend` + `.disclose`).
- [ ] **Step 4:** Run → PASS. **Step 5:** Commit `"feat: legend + honest disclosure (S3 Task 4)"`

---

### Task 5: View toggle (Group by reason ⇄ Rank only)

**Files:**
- Modify: `research_candidates.py`
- Test: `tests/adapters/test_research_candidates.py`

- [ ] **Step 1:** Using context7, confirm the `st.session_state` + `st.radio`/`st.segmented_control`
  pattern for a persistent toggle (Streamlit version in repo).
- [ ] **Step 2: Write the failing test** for the pure view-selector helper (UI state seam):

```python
def test_view_mode_default_is_reason():
    assert rc.resolve_view_mode(session={}) == "reason"
    assert rc.resolve_view_mode(session={"screener_view": "rank"}) == "rank"
```

- [ ] **Step 3:** Run → FAIL. **Step 4:** implement `resolve_view_mode(session)` reading
  `session.get("screener_view", "reason")`; the `render()` wires `st.session_state` + a segmented control
  writing that key. **Step 5:** Run → PASS. Commit `"feat: screener view toggle state (S3 Task 5)"`.

**Mockup pin:** `.seg` control + `setView` behaviour (reason view vs flat ranked list).

---

### Task 6: Reason-bucket render + collapsible 5-factor card (REASON view)

**Files:**
- Modify: `research_candidates.py`
- Reuse: `domain.screen_buckets.assign_buckets/primary_bucket`, `factor_row`, `domain.factor_bands.plain_read`
- Test: `tests/adapters/test_research_candidates.py`

- [ ] **Step 1: Write the failing test**

```python
def test_reason_view_renders_buckets_card_and_empty(fake_candidates):
    # fake_candidates: 3 BucketInput-shaped candidates incl. one all-rounder, none momentum-leader
    html = rc.build_reason_view_html(fake_candidates)
    assert "All-rounder" in html and "🌟" in html
    assert "Momentum leaders" in html and "Empty this week" in html   # honest empty bucket
    # collapsible card body has the 5 factor rows + plain read + do-next
    for factor in ("Quality", "Value", "Momentum", "Low-vol"):
        assert factor in html
    assert "Do next" in html

def test_reason_view_repeat_badge():
    html = rc.build_reason_view_html(fake_candidates)
    assert "also" in html      # repeat badge for a name in multiple buckets
```

- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3: Implement** `build_reason_view_html`:
  - call `assign_buckets`; for each `Bucket` in `PRIORITY`, render `.bkthd` (emoji+label+signature
    subtitle + glossary "i"); members as collapsible rows; **empty bucket → `.empty` honest panel**.
  - Each row header: rank/badge + ticker (DM Sans) + one-line summary + primary `.band` + composite (mono)
    + chevron; `also …` repeat badge when `primary_bucket(c) != this bucket`.
  - Row body (collapsible): `render_factor_row` ×5, `plain_read(bands)` line, a "Do next" line, and a
    placeholder slot for the Google-AI read (filled by S6) — render an empty hook now (`<div id=gai-…>`).
  - Use `st.expander` per row OR a details/summary HTML block — pick per context7 Streamlit check; keep
    the chevron + open-first-name behaviour from the mockup.
- [ ] **Step 4:** Run → PASS. **Drift check** vs mockup buckets + `.row`/`.frow`/`.empty`/`.rep`.
- [ ] **Step 5:** Commit `"feat: reason-bucket view with collapsible 5-factor cards (S3 Task 6)"`

---

### Task 7: Rank-only view + funnel/abstention reskin + wire render()

**Files:**
- Modify: `research_candidates.py`
- Test: `tests/adapters/test_research_candidates.py`

- [ ] **Step 1: Write the failing test**

```python
def test_rank_view_is_flat_ranked(fake_candidates):
    html = rc.build_rank_view_html(fake_candidates)
    # flat list ordered by composite desc, same collapsible rows, no bucket headers
    assert "All-rounder" not in html
    assert html.index("SPG") < html.index("KLAC")     # 1.31 before 1.08

def test_abstention_path_is_honest(empty_screen):
    html = rc.build_body_html(empty_screen, view="reason")
    assert "Empty" in html or "none cleared" in html
    assert "working as designed" in html.lower() or "scanned" in html.lower()
```

- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3: Implement** `build_rank_view_html` (flat, composite-sorted, same row component) + reskin
  the existing abstention/funnel path (keep `ScreenDiagnostics`/`classify_screen` + `render_funnel`, but
  Home tokens + the honest "trend gate is wide; ranking is selective" framing). Wire `render()` to:
  load screen → header → legend → disclosure → toggle → (reason|rank) view → Zone ② hook (S5) → Zone ③
  link (S7). Remove ALL old bespoke-hex card code.
- [ ] **Step 4:** Run → PASS. **Drift check** full page vs mockup.
- [ ] **Step 5:** Commit `"feat: rank view + reskinned funnel + wired render (S3 Task 7)"`

---

### Task 8: Honesty + full gate

- [ ] **Step 1:** Test: assert rendered screener HTML contains **no FORBIDDEN_WORDS** and no
  forecast verbs:
```python
def test_screener_html_no_forbidden_words(fake_candidates):
    html = rc.build_reason_view_html(fake_candidates).lower()
    for w in ("buy","sell","winner","conviction","predict","alpha","outperform"):
        assert w not in html.split()
```
- [ ] **Step 2:** `pytest tests/ -k "research_candidates or glossary or factor_row" -v` → PASS.
- [ ] **Step 3:** `make check` → green. **Step 4:** Commit.

---

## Self-review (S3)
- Spec coverage: §5 S3 (reskin ✓ T3, tiles ✓ T3, legend ✓ T4, toggle ✓ T5, buckets+cards ✓ T6,
  rank view + funnel ✓ T7), §7 pin map (every element has a task + mockup anchor). ✓
- Placeholders: Google-AI read slot is an explicit hook filled by S6 (named, not vague). ✓
- Type consistency: consumes `factor_bands`/`screen_buckets` exactly as S4/S2 define; `build_*_html`
  helper names stable; "lowvol"/"Analyst spread" labels match S1. ✓
- Drift guard present on every render task. ✓
