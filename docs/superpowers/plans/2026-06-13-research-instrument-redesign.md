# Research Instrument Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the 6-tab Streamlit dashboard into a distinctive, intuitive, SimplyWall.st-grade "Research Instrument" — purely by presenting already-computed honest evidence better, with zero return predictions.

**Architecture:** All work in `adapters/visualization/` (UI adapter; `domain/` stays framework-free). Extend the existing component library + `styles.py` with a white/petrol design system, a reusable hover-tooltip glossary, and signature components (Evidence Ledger, anti-KPI tile, verdict card, abstention funnel). Stock Analysis is enriched into an *attributed* multi-source dossier (E1–E3, E5) using data already ingested. Hexagonal boundaries preserved: pure math in `domain/`, fetch in existing adapters.

**Tech Stack:** Python 3.12, Streamlit 1.58, Plotly, pytest + Hypothesis, mypy strict. Fonts via Google Fonts @import (Fraunces, IBM Plex Sans, IBM Plex Mono).

**Source of truth for the look:** ADR-055/056 + `docs/superpowers/specs/2026-06-12-research-instrument-redesign-design.md`. The approved visual reference is preserved at `docs/design-references/research-instrument-home-spike.md` (a throwaway prototype, code embedded — salvage its CSS/components, do not ship the monolith as-is).

**Hard rules (every task):**
- FORBIDDEN_WORDS (`domain/fit.py`: buy, sell, winner, conviction, predict, alpha, outperform) must never appear in new component **source** or **rendered output**. Third-party data is **attributed**, never adopted.
- Show-before-ship: each Stage ends by launching the app, screenshotting the tab, and getting Tirth's approval **before** merge.
- `make check` (lint + mypy strict + pytest ≥90% cov) green at every commit. Run `git checkout data/reports/` before any pre-commit/CI verify (tests strip trailing newlines from 2 tracked JSONs).
- Conventional commits (`feat:`/`test:`/`docs:`/`chore:`). Branch only; never commit to develop/main directly.

**Visual verification note:** CSS/layout is not classically unit-testable. "Looks-right" tasks are verified by a full-page screenshot (via the CDP method below) + Tirth's sign-off. LOGIC tasks (helpers, math, guards) are verified by TDD. Both gates are mandatory.

**Screenshot method (reuse each Stage):** launch `streamlit run adapters/visualization/dashboard.py --server.port 8531 --server.headless true`, then drive headless Chrome via CDP (`websocket-client` + `requests`, both installed): navigate, click `button[role="tab"]`, force-expand the `[data-testid="stMain"]` scroll container, set device height to `stMainBlockContainer.scrollHeight`, `Page.captureScreenshot` with `captureBeyondViewport`. A working driver was used during design; re-create it as `scripts/screenshot_dashboard.py` in Task 0.2 so it's durable.

---

## File Structure

**Create:**
- `scripts/screenshot_dashboard.py` — durable CDP full-page tab screenshotter (Task 0.2)
- `adapters/visualization/components/tooltip.py` — `tooltip(term)` helper + dotted-underline wrapper
- `adapters/visualization/components/ledger.py` — Evidence Ledger strip
- `adapters/visualization/components/proof_tile.py` — anti-KPI tile w/ rubber-stamp badge
- `adapters/visualization/components/funnel.py` — Screener abstention funnel
- `domain/peer_relative.py` — pure sector-percentile math (E1)
- `application/analyst_panel.py` — attributed analyst-estimate aggregation (E2)
- `application/news_context.py` — attributed news/event theme aggregation (E3)
- `tests/test_tooltip.py`, `tests/test_glossary_complete.py`, `tests/domain/test_peer_relative.py`, `tests/test_analyst_panel.py`, `tests/test_news_context.py`, `tests/test_ledger.py`, `tests/test_proof_tile.py`, `tests/test_funnel.py`, `tests/test_honest_state_snapshots.py`

**Modify (EXTEND — these already exist, do NOT duplicate):**
- `adapters/visualization/components/styles.py` — add Research Instrument tokens + font @import + tooltip CSS
- `adapters/visualization/components/charts.py` — add shared Plotly template `apply_dossier_template(fig)`
- `adapters/visualization/components/glossary.py` — expand GLOSSARY 12 → ~40 terms
- `adapters/visualization/components/{hero,cards,metrics,verdicts,scorecard,snowflake}.py` — restyle to tokens
- `adapters/visualization/tabs/{weekly_brief,research_candidates,risk,positions,stock_analysis,trust}.py` — apply system + new components
- `adapters/visualization/stock_analyzer.py` — wire E1/E2/E3 reads into the analysis payload
- `README.md` glossary table — keep in sync with expanded `glossary.py`

---

## Stage P0 — Branch & baseline

### Task 0.1: Create branch and confirm green baseline

- [ ] **Step 1:** Create the feature branch.

Run:
```bash
cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender"
git checkout develop && git pull
git checkout -b feat/research-instrument-redesign
```

- [ ] **Step 2:** Confirm baseline green before any change.

Run: `git checkout data/reports/ 2>/dev/null; make check`
Expected: lint + mypy + pytest all PASS, **1628 tests passing**.

- [ ] **Step 3:** Commit nothing yet (baseline only). Proceed.

### Task 0.2: Durable screenshot driver

**Files:** Create `scripts/screenshot_dashboard.py`

- [ ] **Step 1:** Create the CDP screenshotter. It must: launch Chrome headless with `--remote-allow-origins=*`, navigate to a port arg, click the Nth `button[role="tab"]`, force `[data-testid="stMain"]`/`stApp` ancestors to `overflow:visible;height:auto`, measure `[data-testid="stMainBlockContainer"].scrollHeight`, set device metrics to that height, and `Page.captureScreenshot({captureBeyondViewport:true})`. CLI: `python scripts/screenshot_dashboard.py --port 8531 --tab <0-5> --out /tmp/<name>.png`. (A reference implementation exists from the design session; reproduce it here.)

- [ ] **Step 2:** Smoke-test against the CURRENT app.

Run:
```bash
.venv/bin/streamlit run adapters/visualization/dashboard.py --server.port 8531 --server.headless true &
python scripts/screenshot_dashboard.py --port 8531 --tab 0 --out /tmp/baseline_home.png
```
Expected: a non-blank PNG with height > 1200px is written; height varies by tab.

- [ ] **Step 3:** Commit.
```bash
git add scripts/screenshot_dashboard.py
git commit -m "chore: durable CDP full-page dashboard screenshotter"
```

---

## Stage 0 — Design system foundation + Home

### Task 1: Research Instrument design tokens + fonts

**Files:** Modify `adapters/visualization/components/styles.py`

- [ ] **Step 1:** Add the token + font + base CSS into `inject_global_css()`’s style string (append; keep existing v2 tokens working until tabs migrate). Insert this block:

```css
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap');
:root{
  --ri-app:#F4F6F8; --ri-card:#FFFFFF; --ri-ink:#14181F; --ri-ink2:#3A4250; --ri-muted:#717885;
  --ri-line:#E3E7EC; --ri-hair:#EDF0F3; --ri-teal:#0F6E80;
  --ri-crimson:#CE2F26; --ri-amber:#C9810E; --ri-green:#1F9254;
}
#MainMenu,header[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stDecoration"]{display:none!important;}
html,body,[data-testid="stApp"],.stApp{background:radial-gradient(1100px 520px at 12% -8%,#FFF 0%,rgba(255,255,255,0) 55%),var(--ri-app)!important;}
[data-testid="stMainBlockContainer"],.block-container{max-width:1180px!important;padding:2.2rem 2.4rem 3rem!important;font-family:'IBM Plex Sans',sans-serif;color:var(--ri-ink);}
.ri-h1{font-family:'Fraunces',serif;font-weight:600;font-size:2.6rem;line-height:1.03;letter-spacing:-.015em;color:var(--ri-ink);}
.ri-sub{font-family:'Fraunces',serif;font-style:italic;font-size:1.12rem;color:var(--ri-ink2);}
.ri-sec{font-family:'IBM Plex Mono',monospace;font-size:.72rem;letter-spacing:.2em;text-transform:uppercase;color:var(--ri-muted);display:flex;align-items:center;gap:.8rem;margin:.4rem 0 1rem;}
.ri-sec::after{content:"";flex:1;height:1px;background:var(--ri-hair);}
```

- [ ] **Step 2:** Launch + screenshot Home to confirm CSS loads without breaking the existing layout.

Run: `python scripts/screenshot_dashboard.py --port 8531 --tab 0 --out /tmp/s0_tokens.png` (restart streamlit first).
Expected: app still renders; bg is cool-white; Streamlit header hidden. (Tabs not yet restyled — that's fine.)

- [ ] **Step 3:** Commit.
```bash
git add adapters/visualization/components/styles.py
git commit -m "feat: add Research Instrument design tokens, fonts, base CSS"
```

### Task 2: Tooltip helper + glossary expansion (TDD)

**Files:** Create `adapters/visualization/components/tooltip.py`, `tests/test_tooltip.py`, `tests/test_glossary_complete.py`; Modify `components/glossary.py`, `styles.py`

- [ ] **Step 1: Write the failing test** — `tests/test_tooltip.py`:

```python
from adapters.visualization.components.tooltip import tooltip
from adapters.visualization.components import glossary as g

def test_tooltip_wraps_known_term_with_definition():
    html = tooltip("Beta")
    assert "Beta" in html
    assert g.GLOSSARY["Beta"] in html
    assert "ri-tip" in html  # the cloud span class

def test_tooltip_unknown_term_raises():
    import pytest
    with pytest.raises(KeyError):
        tooltip("NotARealTerm")

def test_tooltip_label_override_keeps_definition():
    html = tooltip("Beta", label="Net β")
    assert "Net β" in html
    assert g.GLOSSARY["Beta"] in html
```

- [ ] **Step 2: Run to verify fail.** Run: `pytest tests/test_tooltip.py -v` — Expected: FAIL (module not found).

- [ ] **Step 3: Implement** `components/tooltip.py`:

```python
"""Reusable hover-tooltip ('cloud') sourced from the single glossary."""
from __future__ import annotations
from html import escape
from adapters.visualization.components import glossary as _g

def tooltip(term: str, label: str | None = None) -> str:
    definition = _g.GLOSSARY[term]  # KeyError if undocumented — by design
    shown = escape(label if label is not None else term)
    return (
        f'<span class="ri-ttip">{shown}'
        f'<span class="ri-tip">{escape(definition)}</span></span>'
    )
```

- [ ] **Step 4: Run to verify pass.** Run: `pytest tests/test_tooltip.py -v` — Expected: PASS.

- [ ] **Step 5: Add tooltip CSS** to `styles.py` (append to the style string):

```css
.ri-ttip{position:relative;cursor:help;border-bottom:1px dotted var(--ri-muted);}
.ri-tip{position:absolute;bottom:142%;left:50%;transform:translateX(-50%) translateY(5px);background:#1b2733;color:#eef3f6;font-family:'IBM Plex Sans';font-size:.76rem;line-height:1.45;padding:.65rem .8rem;border-radius:10px;width:240px;box-shadow:0 10px 30px rgba(15,30,45,.22);opacity:0;visibility:hidden;transition:.15s;z-index:60;text-align:left;}
.ri-tip::after{content:"";position:absolute;top:100%;left:50%;transform:translateX(-50%);border:6px solid transparent;border-top-color:#1b2733;}
.ri-ttip:hover .ri-tip{opacity:1;visibility:visible;transform:translateX(-50%) translateY(0);}
```

- [ ] **Step 6: Expand the glossary.** In `components/glossary.py`, add entries (plain-English, meaning + implication, NO FORBIDDEN_WORDS) for at least: `Net beta`, `Universe`, `Cleared the bar`, `Abstention`, `Directional accuracy`, `Rank-IC`, `Evidence screen`, `Trend filter`, `Concentrated risk`, `Reduce flag`, `Trim flag`, `Hold flag`, `Add-on flag`, `Book health`, `Momentum factor`, `Revision factor`, `Quality factor`, `Value factor`, `Industry percentile`, `Analyst consensus`, `Dispersion`, `Snowflake`, `Portfolio fit`, `EMH`, `SMA-200`, `Falsified`. (Bring total to ~38.)

- [ ] **Step 7: Write the completeness test** — `tests/test_glossary_complete.py`:

```python
from adapters.visualization.components import glossary as g
from domain.fit import FORBIDDEN_WORDS

REQUIRED = {  # every term the UI hovers must be documented
    "Net beta","Universe","Cleared the bar","Abstention","Directional accuracy","Rank-IC",
    "Evidence screen","Trend filter","Concentrated risk","Reduce flag","Trim flag","Hold flag",
    "Add-on flag","Book health","Momentum factor","Revision factor","Quality factor","Value factor",
    "Industry percentile","Analyst consensus","Dispersion","Portfolio fit",
}

def test_required_terms_present():
    missing = REQUIRED - set(g.GLOSSARY)
    assert not missing, f"glossary missing: {missing}"

def test_glossary_definitions_have_no_forbidden_words():
    for term, definition in g.GLOSSARY.items():
        low = definition.lower()
        for w in FORBIDDEN_WORDS:
            assert w not in low, f"'{w}' in glossary[{term}]"
```

- [ ] **Step 8: Run to verify pass.** Run: `pytest tests/test_tooltip.py tests/test_glossary_complete.py -v` — Expected: PASS. Fix any definition that trips a forbidden word (rephrase as evidence, e.g. avoid the word "predict").

- [ ] **Step 9: Sync README glossary table** with the new terms.

- [ ] **Step 10: Commit.**
```bash
git add adapters/visualization/components/tooltip.py adapters/visualization/components/glossary.py adapters/visualization/components/styles.py tests/test_tooltip.py tests/test_glossary_complete.py README.md
git commit -m "feat: hover-tooltip glossary system (12->38 terms, vocab-guarded)"
```

### Task 3: Shared Plotly template

**Files:** Modify `components/charts.py`; Create `tests/test_charts_template.py`

- [ ] **Step 1: Write the failing test:**

```python
import plotly.graph_objects as go
from adapters.visualization.components.charts import apply_dossier_template

def test_template_sets_transparent_bg_and_font():
    fig = apply_dossier_template(go.Figure())
    assert fig.layout.paper_bgcolor in ("rgba(0,0,0,0)", "rgba(0, 0, 0, 0)")
    assert fig.layout.plot_bgcolor in ("rgba(0,0,0,0)", "rgba(0, 0, 0, 0)")
    assert "Plex" in (fig.layout.font.family or "")
```

- [ ] **Step 2: Run to verify fail.** Run: `pytest tests/test_charts_template.py -v` — Expected: FAIL.

- [ ] **Step 3: Implement** `apply_dossier_template(fig)` in `charts.py`:

```python
def apply_dossier_template(fig):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="IBM Plex Sans, sans-serif", color="#3A4250", size=13),
        margin=dict(l=8, r=8, t=28, b=8),
        colorway=["#0F6E80", "#1F9254", "#C9810E", "#CE2F26", "#717885"],
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor="#E3E7EC")
    fig.update_yaxes(showgrid=True, gridcolor="#EDF0F3", zeroline=False)
    return fig
```

- [ ] **Step 4: Run to verify pass.** Run: `pytest tests/test_charts_template.py -v` — Expected: PASS.

- [ ] **Step 5: Commit.**
```bash
git add adapters/visualization/components/charts.py tests/test_charts_template.py
git commit -m "feat: shared dossier Plotly template"
```

### Task 4: Evidence Ledger + anti-KPI tile components (TDD on vocab + structure)

**Files:** Create `components/ledger.py`, `components/proof_tile.py`, `tests/test_ledger.py`, `tests/test_proof_tile.py`

- [ ] **Step 1: Write failing tests** — `tests/test_ledger.py` and `tests/test_proof_tile.py`:

```python
# tests/test_ledger.py
import inspect
from adapters.visualization.components import ledger
from domain.fit import FORBIDDEN_WORDS

def test_ledger_renders_segments():
    html = ledger.render_ledger([("UNIVERSE", "512"), ("CLEARED", "0"), ("NET β", "+1.37")])
    assert "512" in html and "CLEARED" in html and "ri-ledger" in html

def test_ledger_source_has_no_forbidden_words():
    src = inspect.getsource(ledger).lower()
    for w in FORBIDDEN_WORDS:
        assert w not in src
```

```python
# tests/test_proof_tile.py
import inspect
from adapters.visualization.components import proof_tile
from domain.fit import FORBIDDEN_WORDS

def test_tile_renders_number_and_stamp():
    html = proof_tile.render_tile("Rank-IC", "0.004", stamp="FALSIFIED", tone="crimson")
    assert "0.004" in html and "FALSIFIED" in html and "ri-stamp" in html

def test_proof_tile_source_clean():
    src = inspect.getsource(proof_tile).lower()
    for w in FORBIDDEN_WORDS:
        assert w not in src
```

- [ ] **Step 2: Run to verify fail.** Run: `pytest tests/test_ledger.py tests/test_proof_tile.py -v` — Expected: FAIL.

- [ ] **Step 3: Implement** `ledger.py` and `proof_tile.py` (HTML returning functions; escape inputs; tones map to `--ri-crimson|amber|green|muted`). Add matching `.ri-ledger`, `.ri-tile`, `.ri-stamp` CSS to `styles.py` (salvage from the spike: monospace ledger strip with `border-top:1.5px solid`; tile = white card, colored left rule, rotated rubber-stamp badge). Each tile param: `label, number, stamp, tone, sub`.

- [ ] **Step 4: Run to verify pass.** Run: `pytest tests/test_ledger.py tests/test_proof_tile.py -v` — Expected: PASS.

- [ ] **Step 5: Commit.**
```bash
git add adapters/visualization/components/ledger.py adapters/visualization/components/proof_tile.py adapters/visualization/components/styles.py tests/test_ledger.py tests/test_proof_tile.py
git commit -m "feat: Evidence Ledger + anti-KPI proof-tile components (vocab-guarded)"
```

### Task 5: Rebuild the Home tab on the system

**Files:** Modify `adapters/visualization/tabs/weekly_brief.py` (+ `components/hero.py`, `verdicts.py` as needed)

- [ ] **Step 1:** Restyle Home to use: `<div class="ri-h1">` hero ("A stock engine that learned when not to predict"), `render_ledger(...)` with real values from the brief payload, three `render_tile(...)` anti-KPIs (Rank-IC `0.004` FALSIFIED / `49.8%` = EMH / `512 → 0` ABSTAINED — pull from the screen/brief artifacts; if a value is unavailable, render a DATA_GAP dash, never a fabricated number), the book-health ring, and honest verdict cards (relabel the trend chip "Trend filter"). Wrap every metric label in `tooltip("<term>")`.

- [ ] **Step 2:** Keep the existing weekly-brief vocab guard test green; if Home copy changes, update `tests/test_weekly_brief_tab.py::test_weekly_brief_hero_copy_has_no_forbidden_words` scoped strings accordingly (it is a SCOPED test by design).

- [ ] **Step 3:** Run: `pytest tests/test_weekly_brief_tab.py -v` — Expected: PASS.

- [ ] **Step 4: Screenshot gate.** Restart streamlit; `python scripts/screenshot_dashboard.py --port 8531 --tab 0 --out /tmp/s0_home.png`. Verify against criteria: white/petrol look, ledger present, 3 anti-KPI tiles with stamps, verdict cards color-coded, tooltips show on hover (force one open to confirm), no Streamlit chrome.

- [ ] **Step 5: SHOW-BEFORE-SHIP — STOP.** Present `/tmp/s0_home.png` to Tirth. Do not proceed to Stage 1 until he approves the Home look running.

- [ ] **Step 6: Commit.**
```bash
git checkout data/reports/ 2>/dev/null
git add adapters/visualization/tabs/weekly_brief.py adapters/visualization/components/*.py tests/
git commit -m "feat: rebuild Home tab on Research Instrument system"
```

- [ ] **Step 7:** Run `make check` — Expected: all green (≥1628+ tests).

---

## Stage 1 — Screener (abstention funnel) + Risk

### Task 6: Abstention funnel component + data (TDD)

**Files:** Create `components/funnel.py`, `tests/test_funnel.py`; Modify `tabs/research_candidates.py`

- [ ] **Step 1: Write failing test** — `tests/test_funnel.py`:

```python
import inspect
from adapters.visualization.components import funnel
from domain.fit import FORBIDDEN_WORDS

def test_funnel_stages_render_counts():
    html = funnel.render_funnel([("Universe",512),("Liquidity",480),("Evidence bar",0)])
    assert "512" in html and "0" in html and "ri-funnel" in html

def test_funnel_source_clean():
    src = inspect.getsource(funnel).lower()
    for w in FORBIDDEN_WORDS:
        assert w not in src
```

- [ ] **Step 2: Run to verify fail.** Run: `pytest tests/test_funnel.py -v` — Expected: FAIL.

- [ ] **Step 3: Implement** `render_funnel(stages: list[tuple[str,int]])` — a horizontal/stepped exhibit (`Universe N → … → 0`) styled with tokens; final stage tone amber when count is 0 (abstention). Add `.ri-funnel` CSS.

- [ ] **Step 4: Run to verify pass.** Run: `pytest tests/test_funnel.py -v` — Expected: PASS.

- [ ] **Step 5:** In `research_candidates.py`, replace the gray "512 → none cleared" text block with `render_funnel(...)`, sourcing stage counts from the existing candidate-distribution / screen-history data (Universe → liquidity filter → evidence bar → cleared). Must render on abstention weeks (count 0). Keep check-your-own-list + history; restyle. Tooltip every term.

- [ ] **Step 6: Screenshot gate.** `--tab 1 --out /tmp/s1_screener.png`. Verify funnel renders the 512→0 story as a designed exhibit.

- [ ] **Step 7:** Run existing scoped guard: `pytest tests/test_research_candidates_tab.py -v` — Expected: PASS.

- [ ] **Step 8: Commit.**
```bash
git checkout data/reports/ 2>/dev/null
git add adapters/visualization/components/funnel.py adapters/visualization/tabs/research_candidates.py adapters/visualization/components/styles.py tests/test_funnel.py
git commit -m "feat: Screener abstention funnel exhibit"
```

### Task 7: Restyle Risk tab + conclusion band

**Files:** Modify `tabs/risk.py`

- [ ] **Step 1:** Apply `apply_dossier_template(fig)` to the factor + risk-source charts; wrap them in token cards; add a plain-English **conclusion band** sourced from the existing macro-beta result (e.g. "64% of swings come from one market-wide bet — another single name will not diversify this"). Tooltip `Net beta`, `Systematic share`, `Concentrated risk`, dominant factor.

- [ ] **Step 2: Screenshot gate.** `--tab 2 --out /tmp/s1_risk.png`. Verify restyle + conclusion band + tooltips.

- [ ] **Step 3:** Run `make check` — Expected: green.

- [ ] **Step 4: SHOW-BEFORE-SHIP — STOP.** Present `/tmp/s1_screener.png` + `/tmp/s1_risk.png`; get approval.

- [ ] **Step 5: Commit.**
```bash
git checkout data/reports/ 2>/dev/null
git add adapters/visualization/tabs/risk.py
git commit -m "feat: restyle Risk tab + plain-English conclusion band"
```

---

## Stage 2 — My Portfolio + Trust

### Task 8: De-densify My Portfolio

**Files:** Modify `tabs/positions.py`

- [ ] **Step 1:** Apply progressive disclosure: a positions hero (book value, P&L, count) + restyled positions table; move closed positions, all-attention, and watchlist into `st.expander`s. Add drill-down: each ticker is `tooltip`-wrapped and links to Stock Analysis (set `st.session_state["analyze_ticker"]` + nav) plus a small `↗` Yahoo link (`finance.yahoo.com/quote/<T>`). Apply tokens. No logic change to holdings math.

- [ ] **Step 2: Screenshot gate.** `--tab 3 --out /tmp/s2_portfolio.png`. Verify hierarchy (no single endless scroll), expanders collapsed by default.

- [ ] **Step 3:** Run `pytest tests/ -k positions -v` (existing tests) — Expected: PASS.

- [ ] **Step 4: Commit.**
```bash
git checkout data/reports/ 2>/dev/null
git add adapters/visualization/tabs/positions.py
git commit -m "feat: de-densify My Portfolio (progressive disclosure + drill-down)"
```

### Task 9: Trust tab — anti-KPI hero + experiment cards

**Files:** Modify `tabs/trust.py`

- [ ] **Step 1:** Add a top row of `render_tile(...)` anti-KPIs (Rank-IC `0.004` FALSIFIED, Directional `~50%` = EMH, hypotheses-killed count). Convert the falsified-hypothesis text walls into **experiment cards** (Claim → Test → Result → Decision: Retired), one per killed hypothesis (ADR-039/043/044/046/049/050/053). Apply `apply_dossier_template` to the ablation/SHAP exhibits. Trust legitimately uses falsification vocabulary — keep it SCOPED (not whole-module guarded), per existing pattern.

- [ ] **Step 2: Screenshot gate.** `--tab 5 --out /tmp/s2_trust.png`. Verify anti-KPI hero + scannable experiment cards.

- [ ] **Step 3:** Run `pytest tests/ -k trust -v` — Expected: PASS.

- [ ] **Step 4: SHOW-BEFORE-SHIP — STOP.** Present `/tmp/s2_portfolio.png` + `/tmp/s2_trust.png`; get approval.

- [ ] **Step 5: Commit.**
```bash
git checkout data/reports/ 2>/dev/null
git add adapters/visualization/tabs/trust.py
git commit -m "feat: Trust tab anti-KPI hero + experiment cards"
```

---

## Stage 3 — Stock Analysis: attributed evidence dossier

### Task 10: Industry-relative percentile math — E1 (TDD)

**Files:** Create `domain/peer_relative.py`, `tests/domain/test_peer_relative.py`

- [ ] **Step 1: Write failing test:**

```python
from domain.peer_relative import sector_percentile

def test_percentile_basic():
    peers = [10.0, 20.0, 30.0, 40.0]
    assert sector_percentile(25.0, peers) == 50.0   # beats 2 of 4
    assert sector_percentile(45.0, peers) == 100.0
    assert sector_percentile(5.0, peers) == 0.0

def test_percentile_ignores_none_and_empty():
    assert sector_percentile(10.0, []) is None
    assert sector_percentile(10.0, [None, None]) is None
```

- [ ] **Step 2: Run to verify fail.** Run: `pytest tests/domain/test_peer_relative.py -v` — Expected: FAIL.

- [ ] **Step 3: Implement** `domain/peer_relative.py` (stdlib only — domain purity):

```python
"""Pure sector-relative percentile math (E1). No external imports."""
from __future__ import annotations

def sector_percentile(value: float | None, peers: list[float | None]) -> float | None:
    clean = [p for p in peers if p is not None]
    if value is None or not clean:
        return None
    beaten = sum(1 for p in clean if value > p)
    return round(100.0 * beaten / len(clean), 1)
```

- [ ] **Step 4: Run to verify pass.** Run: `pytest tests/domain/test_peer_relative.py -v` — Expected: PASS.

- [ ] **Step 5: Commit.**
```bash
git add domain/peer_relative.py tests/domain/test_peer_relative.py
git commit -m "feat: sector-relative percentile math (E1, pure domain)"
```

### Task 11: Attributed analyst panel — E2 (TDD)

**Files:** Create `application/analyst_panel.py`, `tests/test_analyst_panel.py`

- [ ] **Step 1: Write failing test:**

```python
from application.analyst_panel import build_analyst_panel

def test_panel_attributes_and_shows_dispersion():
    raw = {"analyst_recommendation_mean": 2.1, "analyst_count": 28,
           "targetMeanPrice": 480.0, "targetHighPrice": 600.0, "targetLowPrice": 350.0}
    p = build_analyst_panel(raw, as_of="2026-06-12")
    assert p.count == 28 and p.target_high == 600.0 and p.target_low == 350.0
    assert p.as_of == "2026-06-12"
    assert p.attribution.lower().startswith("the street")  # attributed, not adopted

def test_panel_handles_missing_data_gap():
    p = build_analyst_panel({}, as_of="2026-06-12")
    assert p.count == 0 and p.data_gap is True
```

- [ ] **Step 2: Run to verify fail.** Run: `pytest tests/test_analyst_panel.py -v` — Expected: FAIL.

- [ ] **Step 3: Implement** `application/analyst_panel.py` — a dataclass `AnalystPanel(count, mean_rating, target_mean, target_high, target_low, as_of, attribution, data_gap)`; `build_analyst_panel(info: dict, as_of: str)` maps the existing yfinance `info` fields, sets `attribution = "The Street (per yfinance) currently reads…"`, and `data_gap=True` when count is 0/missing. NO FORBIDDEN_WORDS; never frame as the engine's claim.

- [ ] **Step 4: Run to verify pass.** Run: `pytest tests/test_analyst_panel.py -v` — Expected: PASS.

- [ ] **Step 5: Commit.**
```bash
git add application/analyst_panel.py tests/test_analyst_panel.py
git commit -m "feat: attributed analyst-estimate panel (E2)"
```

### Task 12: Attributed news-context aggregation — E3 (TDD)

**Files:** Create `application/news_context.py`, `tests/test_news_context.py`

- [ ] **Step 1: Write failing test:**

```python
from application.news_context import build_news_context

def test_news_context_groups_and_labels():
    signals = [{"source":"GDELT","title":"X expands datacenter","date":"2026-06-10"},
               {"source":"Google News","title":"X earnings beat","date":"2026-06-11"}]
    ctx = build_news_context(signals, limit=10)
    assert ctx.label == "context, not signal"
    assert len(ctx.items) == 2
    assert ctx.items[0].source in {"GDELT", "Google News"}

def test_news_context_empty_is_data_gap():
    ctx = build_news_context([], limit=10)
    assert ctx.data_gap is True
```

- [ ] **Step 2: Run to verify fail.** Run: `pytest tests/test_news_context.py -v` — Expected: FAIL.

- [ ] **Step 3: Implement** `application/news_context.py` — dataclasses `NewsItem(source,title,date)` + `NewsContext(items,label,data_gap)`; `build_news_context(signals, limit)` sorts by date desc, caps at `limit`, sets `label="context, not signal"`, `data_gap=True` when empty. Attribution by source. NO FORBIDDEN_WORDS.

- [ ] **Step 4: Run to verify pass.** Run: `pytest tests/test_news_context.py -v` — Expected: PASS.

- [ ] **Step 5: Commit.**
```bash
git add application/news_context.py tests/test_news_context.py
git commit -m "feat: attributed news/event context aggregation (E3)"
```

### Task 13: Wire E1/E2/E3 + E5 into Stock Analysis and restyle

**Files:** Modify `adapters/visualization/stock_analyzer.py`, `tabs/stock_analysis.py`, `components/snowflake.py`

- [ ] **Step 1:** In `stock_analyzer.py`, extend the per-ticker payload with: sector-peer percentiles per axis (E1, via `sector_percentile` over peers fetched from existing fundamentals by GICS sector), `build_analyst_panel(info, as_of)` (E2), `build_news_context(buzz_signals, 10)` (E3). Reuse existing fetch paths; every missing input → DATA_GAP, never fabricated.

- [ ] **Step 2:** In `stock_analysis.py`: add an "Evidence Status: not a forecast" framing header; render the E2 analyst panel (attributed, with high/low/count/as-of), the E3 news-context panel (labeled), industry-relative percentiles on each axis (E1), and surface E5 differentiators (portfolio-fit verdict card already exists + a falsification badge linking to Trust). Relabel the trend axis "Trend filter (one signal)". Apply tokens + `apply_dossier_template`. Tooltip every term. Keep the snowflake caption "a description of today, not a forecast."

- [ ] **Step 3:** Confirm the FORBIDDEN_WORDS guards still pass on snowflake/scorecard source and rendered fit output.

Run: `pytest tests/test_scorecard.py tests/test_fit.py tests/test_fit_card.py -v` — Expected: PASS.

- [ ] **Step 4: Screenshot gate (two states).** Restart streamlit; screenshot Stock Analysis empty + with a ticker typed (`--tab 4`). Verify: dossier sections, attributed analyst panel with dispersion, news-context labeled, industry percentiles, evidence-status header, tooltips.

- [ ] **Step 5: SHOW-BEFORE-SHIP — STOP.** Present the Stock Analysis screenshots; get approval. Confirm with Tirth: zero forecast framing, all third-party data attributed.

- [ ] **Step 6: Commit.**
```bash
git checkout data/reports/ 2>/dev/null
git add adapters/visualization/stock_analyzer.py adapters/visualization/tabs/stock_analysis.py adapters/visualization/components/snowflake.py
git commit -m "feat: Stock Analysis attributed evidence dossier (E1/E2/E3/E5)"
```

---

## Stage 4 — Hardening

### Task 14: Honest-state snapshot/structure tests

**Files:** Create `tests/test_honest_state_snapshots.py`

- [ ] **Step 1: Write tests** that render each tab's key honest state with a fake/fixture payload and assert structural invariants + vocabulary cleanliness (the regression guard that would have caught the cockpit). Example:

```python
from domain.fit import FORBIDDEN_WORDS
from adapters.visualization.components import funnel, proof_tile

def test_abstention_funnel_renders_zero_state_without_forbidden_words():
    html = funnel.render_funnel([("Universe",512),("Evidence bar",0)]).lower()
    assert "512" in html and "0" in html
    for w in FORBIDDEN_WORDS:
        assert w not in html

def test_falsified_tile_renders_without_forbidden_words():
    html = proof_tile.render_tile("Rank-IC","0.004",stamp="FALSIFIED",tone="crimson").lower()
    assert "0.004" in html and "falsified" in html
    for w in FORBIDDEN_WORDS:
        assert w not in html
```

- [ ] **Step 2: Run to verify pass.** Run: `pytest tests/test_honest_state_snapshots.py -v` — Expected: PASS.

- [ ] **Step 3: Commit.**
```bash
git add tests/test_honest_state_snapshots.py
git commit -m "test: snapshot guards for honest UI states (abstention/falsified)"
```

### Task 15: Full verification + docs

- [ ] **Step 1:** Run the full suite + types + lint.

Run: `git checkout data/reports/ 2>/dev/null && make check`
Expected: lint PASS, mypy strict PASS, pytest PASS (≥ baseline 1628 + new tests), coverage ≥90%.

- [ ] **Step 2:** Update `docs/STATUS.md` (redesign shipped → maintenance), `docs/PHASE_LOG.md` (append the redesign phase with the honesty reasoning), and confirm `CONTEXT.md` terms match what shipped. Confirm ADR-055/056 are accurate to the built result; amend if any decision changed during build.

- [ ] **Step 3: Final full-dashboard screenshot set** (all 6 tabs) for the PR description + Tirth's final before/after sign-off.

- [ ] **Step 4: Commit + open PR.**
```bash
git checkout data/reports/ 2>/dev/null
git add docs/
git commit -m "docs: wrap Research Instrument redesign (STATUS/PHASE_LOG/ADR)"
git push -u origin feat/research-instrument-redesign
gh pr create --base develop --title "feat: Research Instrument dashboard redesign" --body "<screenshots + ADR-055/056 + spec link>"
```

- [ ] **Step 5:** After CI green + Tirth approves the running app, merge to develop, then release PR develop → main keeping them in sync (`git rev-list --count origin/main..origin/develop` = 0).

---

## Self-Review

**Spec coverage:** D1 stay-Streamlit (no migration task — correct, it's the absence of one) · D2 no predictions (guarded every task) · D3 art direction (Task 1) · D4 three strands (visual=1,3,4,5,7,9; IA=2 tooltips,8 drill-down,6 funnel; honest-confidence=4,9,13) · D5 tooltips (Task 2) · D6 click=both (Task 8, 13) · D7 dossier E1–E3/E5 (Tasks 10–13) · D8 staged show-before-ship (gates in 5,7,9,13). Per-tab §7 all covered (Home 5, Screener 6, Risk 7, Portfolio 8, Stock Analysis 13, Trust 9). Honesty §9 = vocab-guard tests in 2,4,6,10–14. Testing §11 = snapshot tests Task 14, make check Task 15. E4/DCF correctly ABSENT (deferred).

**Placeholder scan:** logic tasks carry full code; visual tasks carry token CSS + screenshot-verify gates (visual quality is verified by render + sign-off, not fake asserts — stated explicitly up top). No TBD/TODO.

**Type consistency:** `tooltip(term,label=None)`, `render_ledger(list[tuple])`, `render_tile(label,number,stamp,tone,sub)`, `render_funnel(list[tuple[str,int]])`, `sector_percentile(value,peers)->float|None`, `build_analyst_panel(info,as_of)->AnalystPanel`, `build_news_context(signals,limit)->NewsContext` — names used consistently across tasks.

**Known gap to verify during build:** the exact GICS sector/peer source for E1 (Task 13 Step 1) depends on what `FundamentalsPort`/yfinance `info["sector"]` exposes; confirm the peer-fetch path before implementing E1 wiring — if peers aren't cheaply available, scope E1 to the sectors already covered by the existing sector-ETF/supply-chain groups and log the limitation (no silent partial coverage).
