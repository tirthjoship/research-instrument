# S4 — Home "Front Desk" Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the Home tab (`weekly_brief.py`) into the Option-A "Front Desk" layout matching `home-FINAL.html`: 4 vitals (ONE net-beta) + book-health ring + one-line honesty pointer + needs-review collapsed v9 rows + holding-steady + slim footer with brief-download. Fix the two-net-beta bug. Add a real vs-Market(1y). Remove the duplicate/relocated sections.

**Architecture:** Reuse the S3 `render_collapsed_row` for needs-review rows. Add a pure `application/vs_market.py` for the realized book-vs-SPY 1y number. Delete the evidence-ledger, validation-findings tiles (already live on Trust), verdict-distribution, and the all-attention dataframe + markdown-brief dump from Home; replace the brief dump with `st.download_button`. The landing door (S6) sits above this when no book is loaded; S4 assumes a loaded book.

**Tech Stack:** Python 3.12, Streamlit (HTML-via-markdown idiom), pytest. Depends on **S1** (`build_evidence_card`/`EvidenceCard`) and **S3** (`render_collapsed_row`). `domain/discipline.Verdict` for verdict typing.

**Spec:** §6. **Visual contract:** `home-FINAL.html`. **Existing render anchors:** component-map §3/§5 (`weekly_brief.render`, `render_tile`, `tooltip`, `render_ledger`, `_gauge`), §7 (HTML idiom). GLOSSARY already documents "Net beta", "vs Market (1y)", "Need review", "Regime", "Systematic share", "Screen"/"Cleared the bar".

---

## File Structure

- Create `application/vs_market.py` — `compute_vs_market_1y(book_closes, spy_closes) -> float | None` (pure).
- Modify `adapters/visualization/tabs/weekly_brief.py` — rewrite `render()` body; add `_render_book_strip`, `_render_book_health`, `_render_honesty_line`, `_render_needs_review`, `_home_evidence_card`; DELETE the ledger / validation-tiles / verdict-distribution / attention-dataframe / brief-dump blocks.
- Modify `tests/test_weekly_brief_tab.py` — update assertions for the new layout.
- Create `tests/application/test_vs_market.py`.

Reuses: `render_tile` (proof_tile), `tooltip` (GLOSSARY), `classify_net_beta` + `classify_systematic_share` (risk_rubric), `render_collapsed_row` (S3), `load_brief_summary`/`load_latest_screen`/`load_adherence_log` (data_loader).

---

### Task 1: `compute_vs_market_1y` (pure)

**Files:** Create `application/vs_market.py`; Test `tests/application/test_vs_market.py`.

Realized trailing-12-month book return minus SPY's, from aligned close series. Backward-looking only (no leakage). DATA-GAP (None) when either series has < 2 points.

- [ ] **Step 1: Failing test**

```python
# tests/application/test_vs_market.py
from application.vs_market import compute_vs_market_1y


def test_vs_market_outperforms():
    # book +20%, spy +10% → +10 pp
    r = compute_vs_market_1y(book_closes=[100.0, 120.0], spy_closes=[100.0, 110.0])
    assert r is not None and round(r, 1) == 10.0


def test_vs_market_underperforms():
    r = compute_vs_market_1y([100.0, 90.0], [100.0, 110.0])
    assert round(r, 1) == -20.0


def test_vs_market_insufficient_is_none():
    assert compute_vs_market_1y([100.0], [100.0, 110.0]) is None
    assert compute_vs_market_1y([], []) is None
```

- [ ] **Step 2: Run fail** → `pytest tests/application/test_vs_market.py -v` FAIL

- [ ] **Step 3: Implement**

```python
# application/vs_market.py
"""Realized book-vs-SPY trailing return. Backward-looking only — no leakage."""
from __future__ import annotations


def compute_vs_market_1y(book_closes: list[float], spy_closes: list[float]) -> float | None:
    if len(book_closes) < 2 or len(spy_closes) < 2:
        return None
    book_ret = (book_closes[-1] - book_closes[0]) / book_closes[0] * 100.0
    spy_ret = (spy_closes[-1] - spy_closes[0]) / spy_closes[0] * 100.0
    return book_ret - spy_ret
```

- [ ] **Step 4: Run pass** → PASS

- [ ] **Step 5: Commit**

```bash
git checkout data/reports/ 2>/dev/null || true
git add application/vs_market.py tests/application/test_vs_market.py
git commit -m "feat(home): compute_vs_market_1y (realized book-vs-SPY, no leakage)"
```

---

### Task 2: Book-strip helper (4 vitals, ONE net-beta — the bug fix)

**Files:** Modify `weekly_brief.py`; Test `tests/test_weekly_brief_tab.py`.

The bug: today `triage_cols[2]` shows `macro.net_beta_by_factor["SPY"]` AND the evidence ledger shows `share` (systematic %), BOTH labeled "Net beta". Fix: "Net beta" = SPY beta ONLY; systematic-share is "Book health" (Task 3). The ledger is deleted (Task 5).

- [ ] **Step 1: Failing test**

```python
# tests/test_weekly_brief_tab.py — add
def test_book_strip_single_net_beta(tmp_path):
    from adapters.visualization.tabs import weekly_brief as wb
    html = wb._render_book_strip_html(
        need_review=4, total=10, vs_market=3.2, net_beta=1.21, regime="RISK_ON",
        screen_cleared=304, screen_universe=512,
    )
    # exactly one "Net beta" label, value 1.21, and it's NOT the systematic share %
    assert html.count(">Net beta<") + html.lower().count("net beta") >= 1
    assert "1.21" in html and "ELEVATED" in html       # classify_net_beta band
    assert "+3.2%" in html and "RISK_ON" in html and "304" in html
    assert "63%" not in html  # systematic share does NOT appear in the beta tile
```

- [ ] **Step 2: Run fail** → FAIL (no `_render_book_strip_html`)

- [ ] **Step 3: Implement** — add to `weekly_brief.py`:

```python
from adapters.visualization.components.proof_tile import render_tile
from adapters.visualization.components.tooltip import tooltip
from domain.risk_rubric import classify_net_beta


def _render_book_strip_html(*, need_review: int, total: int, vs_market: float | None,
                            net_beta: float | None, regime: str,
                            screen_cleared: int, screen_universe: int) -> str:
    t_review = render_tile(label=tooltip("Need review"), number=f"{need_review} / {total}",
                           tone="crimson" if need_review else "muted", sub="holdings a rule fired on")
    vm = "—" if vs_market is None else f"{vs_market:+.1f}%"
    t_vm = render_tile(label=tooltip("vs Market (1y)"), number=vm, tone="muted", sub="realized, vs SPY")
    if net_beta is None:
        t_nb = render_tile(label=tooltip("Net beta"), number="—", tone="muted", sub="no macro data")
    else:
        band = classify_net_beta(net_beta).value
        t_nb = render_tile(label=tooltip("Net beta"), number=f"{net_beta:.2f}", stamp=band.upper(),
                           tone="muted", sub=f"moves ~{net_beta:.2f}x the market")
    t_scr = render_tile(label=tooltip("Screen"), number=str(screen_cleared), tone="green" if screen_cleared else "muted",
                        sub=f"cleared of {screen_universe}")
    return (f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px">'
            f'{t_review}{t_vm}{t_nb}{t_scr}</div>')
```

> `render_tile`'s `label` accepts trusted markup (the `tooltip()` span). "Net beta" / "vs Market (1y)" / "Need review" / "Screen" are all in GLOSSARY (component-map §3) so `tooltip()` won't KeyError.

- [ ] **Step 4: Run pass** → `pytest tests/test_weekly_brief_tab.py -k single_net_beta -v` PASS

- [ ] **Step 5: Commit**

```bash
git add adapters/visualization/tabs/weekly_brief.py tests/test_weekly_brief_tab.py
git commit -m "fix(home): one net-beta tile (SPY beta); systematic-share is book-health, not net-beta"
```

---

### Task 3: Book-health bar (ring + flag)

**Files:** Modify `weekly_brief.py`; Test same.

- [ ] **Step 1: Failing test**

```python
def test_book_health_bar_flags_above_60():
    from adapters.visualization.tabs import weekly_brief as wb
    html = wb._render_book_health_html(systematic_share=0.628)
    assert "63%" in html and "macro-leaning".lower() in html.lower()
    assert "60%" in html  # the flag reference
```

- [ ] **Step 2: Run fail** → FAIL

- [ ] **Step 3: Implement**

```python
from domain.risk_rubric import classify_systematic_share


def _render_book_health_html(systematic_share: float) -> str:
    pct = round(systematic_share * 100)
    band = classify_systematic_share(systematic_share).value  # e.g. "Macro-leaning"
    flag = '<span style="color:#C9810E">⚑ above the 60% flag</span>' if systematic_share >= 0.60 else ""
    ring = (f'<div style="width:54px;height:54px;border-radius:50%;flex-shrink:0;'
            f'background:conic-gradient(#0F6E80 {pct}%, #eef2f3 0);display:flex;align-items:center;justify-content:center">'
            f'<div style="width:40px;height:40px;border-radius:50%;background:#fff;display:flex;align-items:center;'
            f'justify-content:center;font-family:Fraunces,serif;font-weight:800;font-size:13px">{pct}%</div></div>')
    return (f'<div style="display:flex;align-items:center;gap:14px;background:#fff;border:1px solid #dde7e9;'
            f'border-radius:12px;padding:12px 15px;margin-top:12px">{ring}'
            f'<div><div style="font-family:\'IBM Plex Mono\';font-size:10px;text-transform:uppercase;color:#94a8ad">'
            f'{tooltip("Systematic share", "Book health — systematic share")}</div>'
            f'<div style="font-size:13px;margin-top:3px"><b>{pct}% {band.lower()}</b> · {flag} — '
            f'adding another same-direction name won\'t diversify.</div></div></div>')
```

> "Systematic share" is in GLOSSARY (component-map §3). `classify_systematic_share` returns `ShareBand` (component-map §6).

- [ ] **Step 4: Run pass** → PASS

- [ ] **Step 5: Commit**

```bash
git add adapters/visualization/tabs/weekly_brief.py tests/test_weekly_brief_tab.py
git commit -m "feat(home): book-health bar (systematic-share ring + 60% flag)"
```

---

### Task 4: Needs-review rows (collapsed v9 rows) + honesty line

**Files:** Modify `weekly_brief.py`; Test same.

Render one S3 `render_collapsed_row` per REDUCE/TRIM/REVIEW holding. Until S5 wires real per-holding fetch, build a minimal `EvidenceCard` with GAP squares + empty sparkline from brief data (honest — squares light up in S5). Each row wrapped in an `st.expander` for the drill-down (S5 swaps to fragment + lazy case).

- [ ] **Step 1: Failing test**

```python
def test_needs_review_rows_render_collapsed(tmp_path):
    from adapters.visualization.tabs import weekly_brief as wb
    holdings = [{"ticker": "YUMC", "verdict": "TRIM", "unrealized_pct": 22.7,
                 "trend_state": "broken", "why": "Winner pulled back below trend."}]
    html = wb._render_needs_review_html(holdings)
    assert "YUMC" in html and "TRIM" in html and "+22.7%" in html
    assert "dc-row" in html and "dc-sq" in html  # uses the S3 component


def test_home_honesty_line_points_to_trust():
    from adapters.visualization.tabs import weekly_brief as wb
    html = wb._render_honesty_line_html()
    assert "Trust" in html and ("coin flip" in html.lower() or "falsified" in html.lower())
    for w in ("buy", "sell", "predict"):
        assert w not in html.lower()
```

- [ ] **Step 2: Run fail** → FAIL

- [ ] **Step 3: Implement**

```python
from application.evidence_card import EvidenceCard
from domain.evidence_rag import RagSignal, RagColor, DIMENSIONS
from domain.discipline import Verdict
from adapters.visualization.components.decision_card import render_collapsed_row

_NEEDS_REVIEW = {"REDUCE", "TRIM", "REVIEW"}


def _home_evidence_card(ticker: str) -> EvidenceCard:
    """Minimal GAP card for S4 (squares light up once S5 wires per-holding fetch)."""
    sigs = tuple(RagSignal(d, RagColor.GAP, "DATA-GAP: loads on open") for d in DIMENSIONS)
    return EvidenceCard(ticker=ticker, signals=sigs, sparkline=())


def _render_needs_review_html(holdings: list[dict]) -> str:
    rows = []
    for h in holdings:
        if h.get("verdict") not in _NEEDS_REVIEW:
            continue
        card = _home_evidence_card(h.get("ticker", "?"))
        rows.append(render_collapsed_row(
            card, verdict=Verdict(h["verdict"]), name=h.get("ticker", "?"),
            unrealized_pct=h.get("unrealized_pct"), oneliner=h.get("why", ""),
        ))
    if not rows:
        return ('<div class="ws-card" style="padding:12px 16px;color:#1F9254">'
                'Nothing needs review this week — all positions within discipline.</div>')
    return f'<div class="ws-card" style="padding:0">{"".join(rows)}</div>'


def _render_honesty_line_html() -> str:
    return ('<div style="margin-top:12px;font-size:12px;color:#5b7178;background:#fff;'
            'border:1px dashed #dde7e9;border-radius:10px;padding:9px 13px">'
            '<b>Why doubt us:</b> our return forecasts test = a coin flip, and the ranking signal is '
            'FALSIFIED. We show evidence, never forecasts. '
            '<a href="#" style="color:#0F6E80;font-weight:600;text-decoration:none">See the proof → Trust</a></div>')
```

> Uses Verdict from `domain/discipline.py`; "FALSIFIED"/"coin flip" carry the validation finding as a one-liner (full tiles stay on Trust). No forbidden words ("forecasts" is allowed; "predict" is not).

- [ ] **Step 4: Run pass** → PASS (both)

- [ ] **Step 5: Commit**

```bash
git add adapters/visualization/tabs/weekly_brief.py tests/test_weekly_brief_tab.py
git commit -m "feat(home): needs-review collapsed rows (S3 component) + honesty line"
```

---

### Task 5: Rewrite `render()` body — assemble + delete relocated sections

**Files:** Modify `weekly_brief.py` `render()`; Test same.

Replace the body between the hero and footer with: book strip → book-health bar → honesty line → needs-review rows → holding-steady caption → footer with `st.download_button` for the brief. DELETE: `render_ledger` call, the VALIDATION FINDINGS tiles block, the BOOK HEALTH `_gauge` block, the DISCIPLINE FLAGS card loop, the RESEARCH SCREEN card, the VERDICT DISTRIBUTION chips, the all-attention `st.dataframe` + "Everything else" expander, and the full markdown-brief `st.markdown(md)` dump.

- [ ] **Step 1: Failing test (layout assertions on the real render)**

```python
def test_home_render_new_layout(tmp_path):
    import json
    from adapters.visualization.tabs import weekly_brief as wb
    p = tmp_path / "brief_summary.json"
    p.write_text(json.dumps({
        "as_of": "2026-06-14", "regime": "RISK_ON", "abstained": False,
        "holdings": [{"ticker": "YUMC", "verdict": "TRIM", "unrealized_pct": 22.7,
                      "trend_state": "broken", "why": "pulled back below trend"}],
        "macro": {"systematic_share": 0.628, "net_beta_by_factor": {"SPY": 1.42}},
    }))
    # render must not raise; capture markdown
    import streamlit as st
    from unittest.mock import patch
    captured = []
    with (patch.object(st, "markdown", side_effect=lambda c, **k: captured.append(str(c))),
          patch.object(st, "download_button"), patch.object(st, "caption"),
          patch.object(st, "expander"), patch.object(st, "divider"), patch.object(st, "columns")):
        wb.render(path=str(p), adherence_path=str(tmp_path / "a.jsonl"), reports_dir=str(tmp_path))
    html = "\n".join(captured)
    assert "Net beta" in html and html.count("1.42") >= 1
    assert "ri-ledger" not in html          # ledger DELETED
    assert "VERDICT DISTRIBUTION" not in html  # distribution DELETED
    assert "YUMC" in html                   # needs-review row present
```

- [ ] **Step 2: Run fail** → FAIL (old layout still present)

- [ ] **Step 3: Implement** — rewrite the `render()` body. Keep the hero markdown; then:

```python
    # ... after hero markdown ...
    macro = summary.get("macro", {})
    holdings = summary.get("holdings", [])
    net_beta = macro.get("net_beta_by_factor", {}).get("SPY")
    share = macro.get("systematic_share")
    screen = load_latest_screen(reports_dir) or {}
    cleared = len(screen.get("candidates", []))
    universe = screen.get("universe_size", 0)
    need = sum(1 for h in holdings if h.get("verdict") in _NEEDS_REVIEW)
    # vs-market: best-effort; DATA-GAP None if series unavailable here (S5 supplies series)
    vs_market = summary.get("vs_market_1y")  # populated by pipeline / S5; None → "—"

    st.markdown('<div class="ri-sec">YOUR BOOK — TODAY</div>', unsafe_allow_html=True)
    st.markdown(_render_book_strip_html(
        need_review=need, total=len(holdings), vs_market=vs_market, net_beta=net_beta,
        regime=str(summary.get("regime", "?")), screen_cleared=cleared, screen_universe=universe),
        unsafe_allow_html=True)
    if share is not None:
        st.markdown(_render_book_health_html(float(share)), unsafe_allow_html=True)
    st.markdown(_render_honesty_line_html(), unsafe_allow_html=True)

    st.markdown('<div class="ri-sec">NEEDS REVIEW — A RULE FIRED, YOUR CALL</div>', unsafe_allow_html=True)
    st.markdown(_render_needs_review_html(holdings), unsafe_allow_html=True)

    steady = sum(1 for h in holdings if h.get("verdict") in ("HOLD", "ADD_OK"))
    st.caption(f"Holding steady · {steady} — no rule fired, nothing to do")

    # footer: brief as a download, NOT an inline dump
    md = load_weekly_brief(path.replace("brief_summary.json", "weekly_brief.md")) or ""
    if md:
        st.download_button("⬇ Download full weekly brief (.md)", md, file_name="weekly_brief.md")
```

DELETE the old blocks listed above (ledger, validation tiles, gauge, discipline-flags loop, research-screen card, verdict-distribution, attention dataframe, "Everything else" expander, markdown dump). Keep `concentration` flags optional if present.

- [ ] **Step 4: Run pass** → `pytest tests/test_weekly_brief_tab.py -v` PASS (update/remove old assertions referencing deleted blocks).

- [ ] **Step 5: Commit**

```bash
git add adapters/visualization/tabs/weekly_brief.py tests/test_weekly_brief_tab.py
git commit -m "feat(home): Front-Desk render() — delete ledger/dist/attention/brief-dump, assemble new layout"
```

---

### Task 6: Honesty scan + full S4 verify

- [ ] **Step 1: Forbidden-word scan**

```python
def test_weekly_brief_no_forbidden_words():
    import inspect
    from adapters.visualization.tabs import weekly_brief
    from domain.fit import FORBIDDEN_WORDS
    src = inspect.getsource(weekly_brief).lower()
    for w in FORBIDDEN_WORDS:
        assert w not in src, f"forbidden word {w!r} in weekly_brief.py"
```

> If a deleted block left a forbidden word, removing the block fixes it. "forecasts" is allowed; ensure no "predict"/"buy"/"sell"/"winner".

- [ ] **Step 2: Run scan** → fix until PASS.

- [ ] **Step 3: Full S4 verify**

```bash
mypy adapters/visualization/tabs/weekly_brief.py application/vs_market.py
pytest tests/test_weekly_brief_tab.py tests/application/test_vs_market.py -v
```
Expected: mypy Success; tests PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_weekly_brief_tab.py
git commit -m "test(home): forbidden-word scan + vs-market for Front-Desk Home"
```

---

## Self-Review (S4)

1. **Spec §6 coverage:** 4 vitals + ONE net-beta (Task 2, bug fixed) ✓; book-health ring (Task 3) ✓; honesty line → Trust (Task 4) ✓; needs-review collapsed rows via S3 (Task 4) ✓; vs-Market(1y) real compute (Task 1) ✓; section dispositions — ledger/validation-tiles/gauge/discipline-loop/research-card/verdict-dist/attention-table/brief-dump all DELETED, brief → download (Task 5) ✓.
2. **Placeholders:** none. (vs_market wiring of real series is S5's job; S4 reads `summary["vs_market_1y"]` → "—" when absent — honest GAP, not a placeholder.)
3. **Type consistency:** `render_collapsed_row` signature matches S3; `Verdict` from `domain/discipline`; `classify_net_beta`/`classify_systematic_share` return `NetBetaBand`/`ShareBand` (component-map §6).
4. **Honesty:** one net-beta number; validation findings stay full on Trust (Home = 1 line); forbidden scan (Task 6); GAP squares honest until S5.

**Downstream contract:** S5 replaces `_home_evidence_card` (GAP) with `build_evidence_card` (real fetch, cached, fragment-wrapped) and supplies `vs_market_1y` + per-holding sparkline; S6 prepends the landing door above this render when no book is loaded.
