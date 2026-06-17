# My Portfolio Tab Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the My Portfolio tab (`tabs/positions.py`) into a review-queue-first, squarified-treemap, scalable (~60 holdings) Research-Instrument surface, reusing the existing verdict engine and decision-card component.

**Architecture:** Pure/testable units (squarify layout, color bins, view-model enrichment, HTML builders) live in small focused modules under `adapters/visualization/`; `positions.py` becomes a thin orchestrator that reads `st.query_params` (click→detail), `st.radio` (lens/window toggles) and `st.session_state` (table sort/filter/page), then composes the section builders. No domain changes — `Holding` stays pure; verdicts stay `grade_position()`; the expanded detail reuses `decision_card.render_expanded_card` via shared fetch helpers extracted from `weekly_brief.py`.

**Tech Stack:** Python 3.12, Streamlit, Plotly (`go.Figure`), pytest, mypy strict, yfinance (via existing `price_cache`).

**Spec:** `docs/superpowers/specs/2026-06-17-portfolio-tab-redesign-design.md` (sections §1–§10 + Appendix A granular interactions + Appendix B acceptance checklist). Every task maps to a spec section — noted inline.

**Interaction mechanism (resolved, context7-verified):** Every detail entry point (review-card row, treemap tile, table row) is an HTML anchor `<a href="?inspect=TICKER" target="_self">`. Streamlit reruns; `positions.render` reads `st.query_params.get("inspect")` and renders ONE shared detail panel. Lens (`P&L/Today/Verdict`) and SPY window (`YTD/All/1Y`) are `st.radio` widgets keyed in `session_state`. Table sort/filter/search/page live in `session_state`.

**Conventions (match existing codebase):**
- HTML builders are pure functions returning strings; render via `st.markdown(html, unsafe_allow_html=True)`.
- Tests assert on returned HTML strings (class names, hex, text). No Streamlit mocking; no network — fixtures use plain dicts/dataclasses. (Pattern: `tests/test_opportunity_cards.py`, `tests/test_glossary_component.py`.)
- Run the FULL gate at each checkpoint: `make check` (pre-commit + mypy strict + pytest ≥90% cov). Baseline before this work: ~2071–2119 tests green on develop.
- Commit after every task with conventional-commit messages.

---

## File Structure

**Create (new, focused modules):**
- `adapters/visualization/components/squarify.py` — pure squarified-treemap rectangle algorithm.
- `adapters/visualization/components/treemap.py` — color bins + lens resolution + `build_treemap_html`.
- `adapters/visualization/portfolio_view.py` — view-model: `PortfolioRow`, `enrich_holdings`, `top5_weight`, `split_flagged_healthy`.
- `adapters/visualization/components/portfolio_metrics.py` — `build_hero_html`.
- `adapters/visualization/components/portfolio_table.py` — `build_table_html` (+ sort/filter/page helpers).
- `adapters/visualization/components/portfolio_performance.py` — `build_perf_figure` + `alpha_vs_spy`.
- Test files mirror each under `tests/` (see tasks).

**Modify:**
- `adapters/visualization/card_fetch.py` — receive extracted shared helpers (`fetch_card`, `implied_cost`, `window_returns`) so both `weekly_brief` and portfolio detail reuse them.
- `adapters/visualization/tabs/weekly_brief.py` — import the moved helpers instead of local privates (behavior unchanged).
- `adapters/visualization/components/glossary.py` — add portfolio glossary terms.
- `adapters/visualization/tabs/positions.py` — full rewrite of `render()` orchestration + shared detail panel + admin carry-over.
- `adapters/visualization/dashboard.py` — no change needed (still imports `positions.render`); verify only.

---

## Phase 0 — Glossary terms (spec §3a, A2)

### Task 0: Add portfolio glossary terms

**Files:**
- Modify: `adapters/visualization/components/glossary.py`
- Test: `tests/test_portfolio_glossary.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_portfolio_glossary.py
from adapters.visualization.components.glossary import GLOSSARY

def test_portfolio_terms_present():
    for term in (
        "Concentration (top 5)",
        "Needs review",
        "Treemap colour",
        "Beta",
        "Dividend yield",
        "Alpha vs SPY",
    ):
        assert term in GLOSSARY, f"missing glossary term: {term}"
        assert len(GLOSSARY[term]) > 20
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_portfolio_glossary.py -v`
Expected: FAIL (KeyError / assert — terms absent).

- [ ] **Step 3: Add the terms**

Insert these entries into the `GLOSSARY` dict in `glossary.py` (keep existing entries; append before the closing brace):

```python
    "Concentration (top 5)": (
        "The combined weight of your five largest positions. Higher means more "
        "of your book rides on a few names — more single-name risk."
    ),
    "Needs review": (
        "Holdings where the discipline rule fired (REDUCE, TRIM, or REVIEW). "
        "This list grows with problems, not with how many stocks you own."
    ),
    "Treemap colour": (
        "Tile size is the position's weight in your book. Tile colour is the "
        "lens you pick: realised profit/loss, today's move, or the verdict. "
        "Colour is actual history, never a prediction."
    ),
    "Beta": (
        "How much a stock tends to swing versus the market (SPY = 1.0). "
        "Above 1.0 means it typically moves more than the market."
    ),
    "Dividend yield": (
        "Trailing dividend income as a percent of price, from the data provider. "
        "Shown as a dash when the provider reports none."
    ),
    "Alpha vs SPY": (
        "Your portfolio's return minus the S&P 500's over the same window. "
        "Positive means you beat the benchmark; actual, not projected."
    ),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_portfolio_glossary.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add adapters/visualization/components/glossary.py tests/test_portfolio_glossary.py
git commit -m "feat(portfolio): add glossary terms for portfolio tab"
```

---

## Phase 1 — Squarified treemap algorithm (spec §6, A4)

### Task 1: Pure squarify rectangle packing

**Files:**
- Create: `adapters/visualization/components/squarify.py`
- Test: `tests/test_squarify.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_squarify.py
from adapters.visualization.components.squarify import squarify, Rect

def test_rects_cover_area_and_are_proportional():
    rects = squarify([50.0, 30.0, 20.0], 0.0, 0.0, 100.0, 100.0)
    assert len(rects) == 3
    # total tiled area ~= container area (allow float slack)
    total = sum(r.w * r.h for r in rects)
    assert abs(total - 100.0 * 100.0) < 1.0
    # area is proportional to value
    areas = [r.w * r.h for r in rects]
    assert areas[0] > areas[1] > areas[2]
    assert abs(areas[0] / total - 0.5) < 0.02

def test_no_rect_escapes_container():
    rects = squarify([1.0, 1.0, 1.0, 97.0], 0.0, 0.0, 200.0, 120.0)
    for r in rects:
        assert r.x >= -0.01 and r.y >= -0.01
        assert r.x + r.w <= 200.01 and r.y + r.h <= 120.01

def test_single_item_fills_container():
    rects = squarify([42.0], 5.0, 5.0, 50.0, 60.0)
    assert len(rects) == 1
    r = rects[0]
    assert abs(r.w - 50.0) < 0.01 and abs(r.h - 60.0) < 0.01

def test_empty_returns_empty():
    assert squarify([], 0.0, 0.0, 10.0, 10.0) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_squarify.py -v`
Expected: FAIL ("No module named ... squarify").

- [ ] **Step 3: Implement the algorithm**

```python
# adapters/visualization/components/squarify.py
"""Pure squarified-treemap rectangle packing (no framework imports)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rect:
    """A tile rectangle: index into the input list + pixel geometry."""

    index: int
    x: float
    y: float
    w: float
    h: float


def squarify(
    values: list[float], x: float, y: float, w: float, h: float
) -> list[Rect]:
    """Pack ``values`` (already in desired order) into rect (x,y,w,h).

    Returns one Rect per value; tile area is proportional to value and tiles
    stay as close to square as possible (Bruls et al. squarified treemap).
    """
    if not values:
        return []

    out: list[Rect] = []
    rx, ry, rw, rh = x, y, w, h
    remaining = float(sum(values))
    i = 0
    row: list[float] = []
    row_idx: list[int] = []

    def worst(candidate: list[float]) -> float:
        s = sum(candidate)
        if s <= 0:
            return float("inf")
        vertical = rw >= rh
        side = rh if vertical else rw
        thick = (s / remaining) * (rw if vertical else rh)
        if thick <= 0:
            return float("inf")
        bad = 1.0
        for v in candidate:
            long = (v / s) * side
            if long <= 0:
                return float("inf")
            ar = max(long / thick, thick / long)
            bad = max(bad, ar)
        return bad

    def lay(r: list[float], idxs: list[int]) -> None:
        nonlocal rx, ry, rw, rh, remaining
        s = sum(r)
        vertical = rw >= rh
        side = rh if vertical else rw
        thick = (s / remaining) * (rw if vertical else rh)
        off = ry if vertical else rx
        for v, idx in zip(r, idxs):
            long = (v / s) * side
            if vertical:
                out.append(Rect(idx, rx, off, thick, long))
            else:
                out.append(Rect(idx, off, ry, long, thick))
            off += long
        if vertical:
            rx += thick
            rw -= thick
        else:
            ry += thick
            rh -= thick
        remaining -= s

    while i < len(values):
        cand = row + [values[i]]
        if not row or worst(cand) <= worst(row):
            row = cand
            row_idx = row_idx + [i]
            i += 1
        else:
            lay(row, row_idx)
            row, row_idx = [], []
    if row:
        lay(row, row_idx)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_squarify.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add adapters/visualization/components/squarify.py tests/test_squarify.py
git commit -m "feat(portfolio): pure squarified treemap layout algorithm"
```

---

## Phase 2 — Treemap colour bins + lens (spec §6a / A4a)

### Task 2: Colour bins and lens resolution

**Files:**
- Create: `adapters/visualization/components/treemap.py`
- Test: `tests/test_treemap_color.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_treemap_color.py
from adapters.visualization.components.treemap import lens_color, LENSES

def test_lenses_exact():
    assert LENSES == ("pnl", "today", "verdict")

def test_pnl_bins_capped():
    # deep green for big winner (capped at +25 band)
    assert lens_color({"pnl": 75.0, "today": 1.0, "verdict": "HOLD"}, "pnl")[0] == "#15803D"
    # deep red for big loser
    assert lens_color({"pnl": -40.0, "today": -1.0, "verdict": "REDUCE"}, "pnl")[0] == "#DC2626"
    # pale green just above zero
    assert lens_color({"pnl": 2.0, "today": 0.0, "verdict": "HOLD"}, "pnl")[0] == "#BBF7D0"

def test_verdict_lens_colors():
    assert lens_color({"pnl": 0, "today": 0, "verdict": "REDUCE"}, "verdict")[0] == "#DC2626"
    assert lens_color({"pnl": 0, "today": 0, "verdict": "REVIEW"}, "verdict")[0] == "#FBBF24"
    assert lens_color({"pnl": 0, "today": 0, "verdict": "HOLD"}, "verdict")[0] == "#22C55E"

def test_returns_bg_and_fg():
    bg, fg = lens_color({"pnl": 75.0, "today": 0, "verdict": "HOLD"}, "pnl")
    assert bg == "#15803D" and fg == "#FFFFFF"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_treemap_color.py -v`
Expected: FAIL (import error).

- [ ] **Step 3: Implement bins + lens**

```python
# adapters/visualization/components/treemap.py
"""Treemap colour lenses + HTML builder for the portfolio book view."""

from __future__ import annotations

from typing import Any

LENSES: tuple[str, str, str] = ("pnl", "today", "verdict")

# (upper-exclusive bound, bg, fg) — capped at ±25
_PNL_BINS = [
    (25.0, "#15803D", "#FFFFFF"),
    (8.0, "#22C55E", "#0F172A"),
    (0.0, "#BBF7D0", "#0F172A"),
    (-8.0, "#FECACA", "#0F172A"),
    (-25.0, "#F87171", "#FFFFFF"),
]
_PNL_FLOOR = ("#DC2626", "#FFFFFF")

_VERDICT_COLORS = {
    "REDUCE": ("#DC2626", "#FFFFFF"),
    "TRIM": ("#F87171", "#FFFFFF"),
    "REVIEW": ("#FBBF24", "#0F172A"),
    "HOLD": ("#22C55E", "#0F172A"),
    "ADD_OK": ("#15803D", "#FFFFFF"),
}
_VERDICT_DEFAULT = ("#E5E7EB", "#64748B")


def _bin(value: float) -> tuple[str, str]:
    if value >= 25.0:
        return _PNL_BINS[0][1], _PNL_BINS[0][2]
    if value >= 8.0:
        return _PNL_BINS[1][1], _PNL_BINS[1][2]
    if value >= 0.0:
        return _PNL_BINS[2][1], _PNL_BINS[2][2]
    if value > -8.0:
        return _PNL_BINS[3][1], _PNL_BINS[3][2]
    if value > -25.0:
        return _PNL_BINS[4][1], _PNL_BINS[4][2]
    return _PNL_FLOOR


def lens_color(row: dict[str, Any], lens: str) -> tuple[str, str]:
    """Return (background, foreground) hex for a holding under ``lens``."""
    if lens == "pnl":
        return _bin(float(row.get("pnl") or 0.0))
    if lens == "today":
        # amplify intraday so small daily moves are legible, same bins
        return _bin(float(row.get("today") or 0.0) * 5.0)
    return _VERDICT_COLORS.get(str(row.get("verdict") or ""), _VERDICT_DEFAULT)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_treemap_color.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add adapters/visualization/components/treemap.py tests/test_treemap_color.py
git commit -m "feat(portfolio): treemap colour bins + lens resolution"
```

---

## Phase 3 — Portfolio view-model (spec §5 / A9)

### Task 3: PortfolioRow + enrichment + concentration + split

**Files:**
- Create: `adapters/visualization/portfolio_view.py`
- Test: `tests/test_portfolio_view.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_portfolio_view.py
from domain.models import Holding
from adapters.visualization.portfolio_view import (
    PortfolioRow, enrich_holdings, top5_weight, split_flagged_healthy,
)

def _h(sym, qty, cost):
    return Holding(symbol=sym, quantity=qty, purchase_price=cost, purchase_date="2026-01-02")

def test_enrich_computes_value_pnl_weight():
    holdings = [_h("AAA", 10, 100.0), _h("BBB", 5, 200.0)]
    prices = {"AAA": {"price": 110.0, "change_pct": 1.0}, "BBB": {"price": 180.0, "change_pct": -2.0}}
    infos = {"AAA": {"sector": "Tech", "beta": 1.2, "dividendYield": 0.5},
             "BBB": {"sector": "Energy", "beta": 0.8, "dividendYield": 0.0}}
    brief = {"AAA": {"verdict": "HOLD", "why": "ok", "trend_state": "uptrend"},
             "BBB": {"verdict": "TRIM", "why": "weak", "trend_state": "broken"}}
    rows = enrich_holdings(holdings, prices, infos, brief)
    aaa = next(r for r in rows if r.ticker == "AAA")
    assert aaa.value == 1100.0
    assert aaa.cost == 1000.0
    assert round(aaa.pnl, 1) == 10.0
    assert aaa.today == 1.0
    assert aaa.sector == "Tech"
    assert aaa.verdict == "HOLD"
    # weights sum to ~100
    assert abs(sum(r.weight for r in rows) - 100.0) < 0.01

def test_missing_sector_is_unknown():
    rows = enrich_holdings([_h("ZZZ", 1, 10.0)], {"ZZZ": {"price": 10.0, "change_pct": 0.0}}, {"ZZZ": {}}, {})
    assert rows[0].sector == "Unknown"
    assert rows[0].verdict == ""  # DATA-GAP: not in brief

def test_zero_dividend_yield_is_none_gap():
    rows = enrich_holdings([_h("ZZZ", 1, 10.0)], {"ZZZ": {"price": 10.0, "change_pct": 0.0}}, {"ZZZ": {"dividendYield": 0.0}}, {})
    assert rows[0].dividend_yield is None  # DATA-GAP rendered as "—"

def test_top5_weight():
    rows = [PortfolioRow("T%d" % i, "Tech", float(w), 0, 0, 0, 0, "HOLD", "", None, 1.0, 0) for i, w in enumerate([30, 25, 20, 10, 8, 4, 3])]
    assert abs(top5_weight(rows) - (30 + 25 + 20 + 10 + 8)) < 0.01

def test_split_flagged_healthy():
    rows = [
        PortfolioRow("A", "Tech", 10, 0, 0, 0, 0, "REDUCE", "", None, 1.0, 0),
        PortfolioRow("B", "Tech", 10, 0, 0, 0, 0, "HOLD", "", None, 1.0, 0),
        PortfolioRow("C", "Tech", 10, 0, 0, 0, 0, "REVIEW", "", None, 1.0, 0),
    ]
    flagged, healthy = split_flagged_healthy(rows)
    assert [r.ticker for r in flagged] == ["A", "C"]  # REDUCE before REVIEW
    assert [r.ticker for r in healthy] == ["B"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_portfolio_view.py -v`
Expected: FAIL (import error).

- [ ] **Step 3: Implement the view-model**

```python
# adapters/visualization/portfolio_view.py
"""View-model for the portfolio tab: enrich holdings with live + brief data.

Adapter-side only — the domain ``Holding`` stays pure. Missing provider data
becomes DATA-GAP (None / "Unknown"), never fabricated.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from domain.models import Holding

_FLAG_ORDER = {"REDUCE": 0, "TRIM": 1, "REVIEW": 2}
_FLAGGED = set(_FLAG_ORDER)


@dataclass(frozen=True)
class PortfolioRow:
    ticker: str
    sector: str
    weight: float          # % of book value
    value: float           # market value $
    cost: float            # cost basis $
    pnl: float             # lifetime realised %
    today: float           # intraday %
    verdict: str           # "" = DATA-GAP
    why: str
    dividend_yield: float | None  # None = DATA-GAP
    beta: float | None
    quantity: float


def _yield_of(info: dict[str, Any]) -> float | None:
    raw = info.get("dividendYield")
    if raw is None:
        raw = info.get("trailingAnnualDividendYield")
    if raw is None:
        return None
    val = float(raw)
    if val <= 0:
        return None
    # yfinance sometimes returns a fraction (0.012) vs percent (1.2)
    return val * 100.0 if val < 1.0 else val


def enrich_holdings(
    holdings: list[Holding],
    prices: dict[str, dict[str, float]],
    infos: dict[str, dict[str, Any]],
    brief_by_ticker: dict[str, dict[str, Any]],
) -> list[PortfolioRow]:
    raw: list[dict[str, Any]] = []
    total_value = 0.0
    for h in holdings:
        p = prices.get(h.symbol, {})
        price = float(p.get("price") or h.purchase_price)
        value = h.quantity * price
        total_value += value
        info = infos.get(h.symbol, {})
        brief = brief_by_ticker.get(h.symbol, {})
        beta_raw = info.get("beta")
        raw.append(
            {
                "ticker": h.symbol,
                "sector": str(info.get("sector") or "Unknown"),
                "value": value,
                "cost": h.quantity * h.purchase_price,
                "today": float(p.get("change_pct") or 0.0),
                "verdict": str(brief.get("verdict") or ""),
                "why": str(brief.get("why") or ""),
                "dividend_yield": _yield_of(info),
                "beta": float(beta_raw) if beta_raw is not None else None,
                "quantity": h.quantity,
            }
        )
    rows: list[PortfolioRow] = []
    for r in raw:
        weight = (r["value"] / total_value * 100.0) if total_value > 0 else 0.0
        pnl = ((r["value"] - r["cost"]) / r["cost"] * 100.0) if r["cost"] > 0 else 0.0
        rows.append(
            PortfolioRow(
                ticker=r["ticker"], sector=r["sector"], weight=weight,
                value=r["value"], cost=r["cost"], pnl=pnl, today=r["today"],
                verdict=r["verdict"], why=r["why"],
                dividend_yield=r["dividend_yield"], beta=r["beta"],
                quantity=r["quantity"],
            )
        )
    return rows


def top5_weight(rows: list[PortfolioRow]) -> float:
    return sum(sorted((r.weight for r in rows), reverse=True)[:5])


def split_flagged_healthy(
    rows: list[PortfolioRow],
) -> tuple[list[PortfolioRow], list[PortfolioRow]]:
    flagged = sorted(
        (r for r in rows if r.verdict in _FLAGGED),
        key=lambda r: _FLAG_ORDER[r.verdict],
    )
    healthy = [r for r in rows if r.verdict not in _FLAGGED]
    return flagged, healthy
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_portfolio_view.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add adapters/visualization/portfolio_view.py tests/test_portfolio_view.py
git commit -m "feat(portfolio): holdings view-model (enrich, top5, flagged/healthy split)"
```

---

## Phase 4 — Hero metrics (spec §2 item 1 / A2)

### Task 4: build_hero_html

**Files:**
- Create: `adapters/visualization/components/portfolio_metrics.py`
- Test: `tests/test_portfolio_metrics.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_portfolio_metrics.py
from adapters.visualization.components.portfolio_metrics import build_hero_html

def test_hero_shows_value_pnl_review_concentration():
    html = build_hero_html(
        book_value=312840.0, cost=281470.0, pnl=31370.0, pnl_pct=11.1,
        spy_pct=7.1, needs_review=5, total_positions=60, top5=38.0,
    )
    assert "$312,840" in html
    assert "+$31,370" in html
    assert "+11.1%" in html
    assert "vs SPY +7.1%" in html
    assert ">5<" in html               # needs review count
    assert "of 60 positions" in html
    assert "38%" in html               # concentration

def test_hero_hides_spy_badge_when_gap():
    html = build_hero_html(
        book_value=1000.0, cost=1000.0, pnl=0.0, pnl_pct=0.0,
        spy_pct=None, needs_review=0, total_positions=1, top5=100.0,
    )
    assert "vs SPY" not in html

def test_negative_pnl_red():
    html = build_hero_html(
        book_value=900.0, cost=1000.0, pnl=-100.0, pnl_pct=-10.0,
        spy_pct=2.0, needs_review=0, total_positions=1, top5=100.0,
    )
    assert "-$100" in html and "-10.0%" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_portfolio_metrics.py -v`
Expected: FAIL (import error).

- [ ] **Step 3: Implement build_hero_html**

```python
# adapters/visualization/components/portfolio_metrics.py
"""Hero metric row for the portfolio tab."""

from __future__ import annotations

from adapters.visualization.components.tooltip import tooltip


def build_hero_html(
    *,
    book_value: float,
    cost: float,
    pnl: float,
    pnl_pct: float,
    spy_pct: float | None,
    needs_review: int,
    total_positions: int,
    top5: float,
) -> str:
    pnl_color = "var(--ri-green)" if pnl >= 0 else "var(--ri-crimson)"
    sign = "+" if pnl >= 0 else ""
    badge = (
        f'<span style="font-size:.66rem;font-weight:700;padding:1px 6px;'
        f'border-radius:5px;background:#ECFDF5;color:var(--ri-green);'
        f'margin-left:4px;">vs SPY {"+" if spy_pct >= 0 else ""}{spy_pct:.1f}%</span>'
        if spy_pct is not None
        else ""
    )
    review_tip = tooltip("Needs review", "Needs review")
    conc_tip = tooltip("Concentration (top 5)", "Concentration")
    return (
        '<div class="ri-metric-row">'
        "<div>"
        '<div class="ri-metric-lab">Book value</div>'
        f'<div class="ri-metric-num">${book_value:,.0f}</div>'
        f'<div style="font-size:.72rem;color:var(--ri-muted);">cost ${cost:,.0f}</div>'
        "</div>"
        "<div>"
        '<div class="ri-metric-lab">Total P&amp;L</div>'
        f'<div class="ri-metric-num" style="color:{pnl_color};">{sign}${pnl:,.0f}'
        f'<span style="font-size:.9rem;color:{pnl_color};margin-left:.4rem;">'
        f'({sign}{pnl_pct:.1f}%)</span></div>'
        f'<div style="font-size:.72rem;">{badge}</div>'
        "</div>"
        "<div>"
        f'<div class="ri-metric-lab">{review_tip} — Needs review</div>'
        f'<div class="ri-metric-num" style="color:#B45309;">{needs_review}</div>'
        f'<div style="font-size:.72rem;color:var(--ri-muted);">of {total_positions} positions</div>'
        "</div>"
        "<div>"
        f'<div class="ri-metric-lab">{conc_tip} — Concentration</div>'
        f'<div class="ri-metric-num">{top5:.0f}%</div>'
        '<div style="font-size:.72rem;color:var(--ri-muted);">top 5 of book</div>'
        "</div>"
        "</div>"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_portfolio_metrics.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add adapters/visualization/components/portfolio_metrics.py tests/test_portfolio_metrics.py
git commit -m "feat(portfolio): hero metric row builder"
```

---

## Phase 5 — Extract shared card-fetch helpers (spec §3 / A6)

### Task 5: Move fetch_card / implied_cost / window_returns into card_fetch.py

**Files:**
- Modify: `adapters/visualization/card_fetch.py` (add public helpers)
- Modify: `adapters/visualization/tabs/weekly_brief.py` (import moved helpers; delete local copies)
- Test: `tests/test_card_fetch_shared.py`

- [ ] **Step 1: Read the current private helpers**

Run: `grep -n "_fetch_card\|implied_cost\|window_returns\|_home_evidence_card" adapters/visualization/tabs/weekly_brief.py`
Note the exact bodies of `_fetch_card`, `implied_cost`, `window_returns` (lines ~300–365) so they can be moved verbatim.

- [ ] **Step 2: Write the failing test**

```python
# tests/test_card_fetch_shared.py
from adapters.visualization import card_fetch

def test_public_helpers_exist():
    assert hasattr(card_fetch, "fetch_card")
    assert hasattr(card_fetch, "implied_cost")
    assert hasattr(card_fetch, "window_returns")

def test_implied_cost_inverts_return():
    # price 110 after +10% implies cost 100
    assert round(card_fetch.implied_cost(110.0, 10.0), 2) == 100.0

def test_window_returns_shape():
    closes = [float(x) for x in range(1, 300)]
    rets = card_fetch.window_returns(closes)
    assert isinstance(rets, tuple)
    assert all(isinstance(x, float) for x in rets)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_card_fetch_shared.py -v`
Expected: FAIL (attributes missing).

- [ ] **Step 4: Move the helpers**

In `adapters/visualization/card_fetch.py`, add public functions `fetch_card(ticker: str) -> EvidenceCard`, `implied_cost(price: float, unrealized_pct: float) -> float`, and `window_returns(closes: list[float]) -> tuple[float, ...]`, copying the bodies verbatim from `weekly_brief.py` (`_fetch_card`, `implied_cost`, `window_returns`). Keep imports they need (`fetch_ticker_info`, `fetch_prices`, `fetch_price_history`, `build_analyst_panel`, `fetch_earnings_history`, `build_evidence_card`, `_home_evidence_card` / its equivalent GAP-card builder — move that too if private).

In `weekly_brief.py`: replace the local definitions with:
```python
from adapters.visualization.card_fetch import fetch_card, implied_cost, window_returns
```
and update call sites (`_fetch_card(ticker)` → `fetch_card(ticker)`).

- [ ] **Step 5: Run tests to verify pass + no regression**

Run: `pytest tests/test_card_fetch_shared.py tests/ -k "weekly_brief or card" -v`
Expected: PASS, and existing weekly_brief tests still green.

- [ ] **Step 6: Commit**

```bash
git add adapters/visualization/card_fetch.py adapters/visualization/tabs/weekly_brief.py tests/test_card_fetch_shared.py
git commit -m "refactor(viz): extract shared card-fetch helpers for reuse by portfolio"
```

---

## Phase 6 — Needs-review cards (spec §2 item 2 / A3)

### Task 6: build_review_card_html (collapsed row + inspect anchor)

**Files:**
- Modify: `adapters/visualization/components/portfolio_table.py` is separate; create review builder here:
- Create: `adapters/visualization/components/portfolio_review.py`
- Test: `tests/test_portfolio_review.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_portfolio_review.py
from adapters.visualization.portfolio_view import PortfolioRow
from adapters.visualization.components.portfolio_review import (
    build_review_card_html, build_calm_html,
)

def _row(tk, v, pnl):
    return PortfolioRow(tk, "Tech", 5.0, 100, 100, pnl, -0.5, v, "trend broke", None, 1.1, 10)

def test_review_card_has_anchor_and_pill():
    html = build_review_card_html(_row("PLTR", "REDUCE", -18.4))
    assert 'href="?inspect=PLTR"' in html
    assert "REDUCE" in html
    assert "-18.4%" in html
    assert "trend broke" in html

def test_card_border_class_by_verdict():
    assert "reduce" in build_review_card_html(_row("A", "REDUCE", -5))
    assert "trim" in build_review_card_html(_row("B", "TRIM", -2))
    assert "review" in build_review_card_html(_row("C", "REVIEW", 1))

def test_calm_state():
    html = build_calm_html()
    assert "Nothing needs review" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_portfolio_review.py -v`
Expected: FAIL (import error).

- [ ] **Step 3: Implement the builders**

```python
# adapters/visualization/components/portfolio_review.py
"""Needs-review collapsed cards for the portfolio tab.

Each card is an inspect-anchor; clicking sets ?inspect=TICKER and the tab
renders the shared detail panel (reusing decision_card.render_expanded_card).
"""

from __future__ import annotations

from adapters.visualization.portfolio_view import PortfolioRow

_CLS = {"REDUCE": "reduce", "TRIM": "trim", "REVIEW": "review"}
_PILL = {
    "REDUCE": ("#FEE2E2", "#991B1B"),
    "TRIM": ("#FEF3C7", "#92400E"),
    "REVIEW": ("#DBEAFE", "#1E40AF"),
}


def build_review_card_html(row: PortfolioRow) -> str:
    cls = _CLS.get(row.verdict, "review")
    bg, fg = _PILL.get(row.verdict, ("#F1F5F9", "#475569"))
    pnl_color = "#16A34A" if row.pnl >= 0 else "#DC2626"
    sign = "+" if row.pnl >= 0 else ""
    why = row.why or "Discipline rule fired — review."
    return (
        f'<a href="?inspect={row.ticker}" target="_self" '
        f'style="text-decoration:none;color:inherit;display:block;" '
        f'class="pf-review {cls}">'
        '<div style="display:flex;align-items:center;gap:.6rem;flex-wrap:wrap;">'
        f'<span style="font-family:\'Fraunces\',serif;font-weight:700;font-size:1.1rem;">{row.ticker}</span>'
        f'<span style="color:var(--ri-muted);font-size:.76rem;">{row.weight:.1f}% · {row.sector}</span>'
        f'<span style="padding:2px 8px;border-radius:11px;font-size:.66rem;font-weight:700;'
        f'background:{bg};color:{fg};">{row.verdict}</span>'
        f'<span style="margin-left:auto;font-family:\'IBM Plex Mono\',monospace;'
        f'font-weight:700;color:{pnl_color};">{sign}{row.pnl:.1f}%</span>'
        "</div>"
        f'<div style="margin-top:5px;font-size:.8rem;color:#334155;">{why}</div>'
        '<div style="margin-top:5px;font-size:.72rem;color:var(--ri-teal);">'
        "▾ click for full detail (RAG · rubric · case)</div>"
        "</a>"
    )


def build_calm_html() -> str:
    return (
        '<div style="border:1px solid #A7F3D0;background:#F0FDF4;border-radius:10px;'
        'padding:14px 16px;display:flex;align-items:center;gap:11px;">'
        '<div style="width:26px;height:26px;border-radius:50%;background:#16A34A;'
        'color:#fff;display:flex;align-items:center;justify-content:center;'
        'font-weight:700;">&#10003;</div>'
        "<div><div style=\"font-weight:600;\">Nothing needs review</div>"
        '<div style="font-size:.82rem;color:#166534;">'
        "All positions are HOLD — sizes look appropriate against the discipline rule."
        "</div></div></div>"
    )
```

Add the matching CSS to `styles.py` GLOBAL_CSS (left-border + bg tint + hover lift):
```css
.pf-review{border:1px solid var(--ri-line);border-radius:10px;padding:12px 15px;margin-bottom:8px;transition:box-shadow .1s;}
.pf-review:hover{box-shadow:0 2px 10px rgba(15,23,42,.08);}
.pf-review.reduce{border-left:4px solid #991B1B;background:#FFFAFA;}
.pf-review.trim{border-left:4px solid #DC2626;background:#FFFBFB;}
.pf-review.review{border-left:4px solid #F59E0B;background:#FFFDF6;}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_portfolio_review.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add adapters/visualization/components/portfolio_review.py adapters/visualization/components/styles.py tests/test_portfolio_review.py
git commit -m "feat(portfolio): needs-review cards + calm empty state"
```

---

## Phase 7 — Treemap HTML builder (spec §6 / A4)

### Task 7: build_treemap_html (sectors → tiles, inspect anchors, hover tips)

**Files:**
- Modify: `adapters/visualization/components/treemap.py` (add builder + tile/sector helpers)
- Test: `tests/test_treemap_html.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_treemap_html.py
from adapters.visualization.portfolio_view import PortfolioRow
from adapters.visualization.components.treemap import build_treemap_html

def _row(tk, sec, w, pnl, today, v):
    return PortfolioRow(tk, sec, w, 100, 100, pnl, today, v, "", None, 1.0, 1)

def _rows():
    return [
        _row("NVDA", "Tech", 40.0, 75.0, 2.0, "HOLD"),
        _row("AAPL", "Tech", 25.0, -3.0, -0.5, "TRIM"),
        _row("XOM", "Energy", 20.0, 6.0, 1.0, "HOLD"),
        _row("ZZZ", "Unknown", 15.0, -2.0, -0.3, "HOLD"),
    ]

def test_grouped_renders_sectors_and_anchors():
    html = build_treemap_html(_rows(), lens="pnl", width=960.0, height=360.0)
    assert "Technology" in html or "Tech" in html
    assert 'href="?inspect=NVDA"' in html
    assert "Unknown" in html  # unknown sector block present

def test_small_book_is_flat():
    html = build_treemap_html(_rows()[:3], lens="pnl", width=960.0, height=360.0, flat=True)
    # flat mode: no sector header text, tiles still present
    assert 'href="?inspect=NVDA"' in html

def test_hover_tip_has_exact_numbers():
    html = build_treemap_html(_rows(), lens="pnl", width=960.0, height=360.0)
    assert "40.0%" in html      # weight
    assert "+75.0%" in html     # lifetime
    assert "+2.0%" in html      # today
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_treemap_html.py -v`
Expected: FAIL (no build_treemap_html).

- [ ] **Step 3: Implement build_treemap_html (append to treemap.py)**

```python
# append to adapters/visualization/components/treemap.py
from adapters.visualization.components.squarify import squarify
from adapters.visualization.portfolio_view import PortfolioRow

_SECTOR_LABELS = {"Tech": "Technology", "Fin": "Financials", "Cons": "Consumer",
                  "Indus": "Industrials", "Comm": "Communications", "Mat": "Materials",
                  "Util": "Utilities", "RE": "Real Estate"}


def _lens_value_str(row: PortfolioRow, lens: str) -> str:
    if lens == "today":
        return f"{'+' if row.today >= 0 else ''}{row.today:.1f}%"
    if lens == "pnl":
        return f"{'+' if row.pnl >= 0 else ''}{row.pnl:.1f}%"
    return row.verdict


def _tile_html(row: PortfolioRow, lens: str, x: float, y: float, w: float, h: float) -> str:
    bg, fg = lens_color({"pnl": row.pnl, "today": row.today, "verdict": row.verdict}, lens)
    area = w * h
    show = area > 1100
    big = area > 4200
    label = ""
    if show:
        fs = ".9rem" if big else ".68rem"
        label = (
            f'<div style="font-family:\'Fraunces\',serif;font-weight:700;'
            f'font-size:{fs};line-height:1;white-space:nowrap;overflow:hidden;'
            f'text-overflow:ellipsis;">{row.ticker}</div>'
        )
        if big:
            label += (
                f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:.62rem;'
                f'font-weight:600;">{_lens_value_str(row, lens)}</div>'
            )
    tip = (
        '<div class="pf-tip">'
        f'<div class="pf-tip-tt">{row.ticker} · {row.verdict or "—"}</div>'
        f'<div class="pf-tip-row"><span>Weight</span><b>{row.weight:.1f}%</b></div>'
        f'<div class="pf-tip-row"><span>Lifetime</span><b>{"+" if row.pnl>=0 else ""}{row.pnl:.1f}%</b></div>'
        f'<div class="pf-tip-row"><span>Today</span><b>{"+" if row.today>=0 else ""}{row.today:.1f}%</b></div>'
        "</div>"
    )
    return (
        f'<a href="?inspect={row.ticker}" target="_self" class="pf-tile" '
        f'style="left:{x:.1f}px;top:{y:.1f}px;width:{max(w-2,0):.1f}px;'
        f'height:{max(h-2,0):.1f}px;background:{bg};color:{fg};">{label}{tip}</a>'
    )


def build_treemap_html(
    rows: list[PortfolioRow], *, lens: str, width: float, height: float, flat: bool = False
) -> str:
    if not rows:
        return ""
    tiles: list[str] = []
    if flat:
        ordered = sorted(rows, key=lambda r: r.weight, reverse=True)
        rects = squarify([r.weight for r in ordered], 0.0, 0.0, width, height)
        for rect in rects:
            r = ordered[rect.index]
            tiles.append(_tile_html(r, lens, rect.x, rect.y, rect.w, rect.h))
    else:
        by_sec: dict[str, list[PortfolioRow]] = {}
        for r in rows:
            by_sec.setdefault(r.sector, []).append(r)
        secs = sorted(by_sec.items(), key=lambda kv: sum(x.weight for x in kv[1]), reverse=True)
        sec_rects = squarify([sum(x.weight for x in items) for _, items in secs], 0.0, 0.0, width, height)
        for rect in sec_rects:
            name, items = secs[rect.index]
            sw = sum(x.weight for x in items)
            label = _SECTOR_LABELS.get(name, name)
            tiles.append(
                f'<div class="pf-sec" style="left:{rect.x:.1f}px;top:{rect.y:.1f}px;'
                f'width:{rect.w-3:.1f}px;height:{rect.h-3:.1f}px;">'
                f'<div class="pf-sechdr"><span>{label}</span><span>{sw:.0f}%</span></div></div>'
            )
            items_sorted = sorted(items, key=lambda r: r.weight, reverse=True)
            inner = squarify([r.weight for r in items_sorted], rect.x, rect.y + 16, rect.w - 3, rect.h - 3 - 16)
            for ir in inner:
                tiles.append(_tile_html(items_sorted[ir.index], lens, ir.x, ir.y, ir.w, ir.h))
    return f'<div class="pf-stage" style="height:{height:.0f}px;">{"".join(tiles)}</div>'
```

Add CSS to `styles.py` GLOBAL_CSS:
```css
.pf-stage{position:relative;width:100%;background:#E2E8F0;border-radius:11px;overflow:hidden;}
.pf-sec{position:absolute;border-radius:8px;overflow:hidden;background:#0F172A;}
.pf-sechdr{position:absolute;top:0;left:0;right:0;height:16px;background:rgba(15,23,42,.82);color:#fff;font-size:.58rem;font-weight:700;text-transform:uppercase;letter-spacing:.04em;padding:2px 7px;display:flex;justify-content:space-between;white-space:nowrap;}
.pf-tile{position:absolute;overflow:hidden;text-decoration:none;padding:4px 6px;display:flex;flex-direction:column;justify-content:center;}
.pf-tile:hover{outline:3px solid #0F172A;z-index:8;}
.pf-tile:hover .pf-tip{opacity:1;}
.pf-tip{position:absolute;bottom:calc(100% + 6px);left:50%;transform:translateX(-50%);background:#0F172A;color:#fff;border-radius:9px;padding:8px 10px;width:170px;opacity:0;pointer-events:none;transition:.12s;z-index:50;}
.pf-tip-tt{font-family:'Fraunces',serif;font-weight:700;font-size:.85rem;margin-bottom:3px;}
.pf-tip-row{font-size:.69rem;color:#CBD5E1;display:flex;justify-content:space-between;margin-top:2px;}
.pf-tip-row b{color:#fff;}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_treemap_html.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add adapters/visualization/components/treemap.py adapters/visualization/components/styles.py tests/test_treemap_html.py
git commit -m "feat(portfolio): squarified treemap HTML builder (sector + flat, hover, inspect anchors)"
```

---

## Phase 8 — Healthy holdings table (spec §7 / A5)

### Task 8: table sort/filter/page helpers (pure)

**Files:**
- Create: `adapters/visualization/components/portfolio_table.py`
- Test: `tests/test_portfolio_table_logic.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_portfolio_table_logic.py
from adapters.visualization.portfolio_view import PortfolioRow
from adapters.visualization.components.portfolio_table import apply_table_state, TableState

def _r(tk, w, pnl):
    return PortfolioRow(tk, "Tech", w, w*10, 100, pnl, 0.0, "HOLD", "", None, 1.0, 1)

def _rows():
    return [_r("A", 30, 5), _r("B", 10, -4), _r("C", 20, 12)]

def test_default_sort_weight_desc():
    out = apply_table_state(_rows(), TableState())
    assert [r.ticker for r in out] == ["A", "C", "B"]

def test_filter_losers():
    out = apply_table_state(_rows(), TableState(filter="loss"))
    assert [r.ticker for r in out] == ["B"]

def test_search():
    out = apply_table_state(_rows(), TableState(query="c"))
    assert [r.ticker for r in out] == ["C"]

def test_sort_pnl_asc():
    out = apply_table_state(_rows(), TableState(sort="pnl", ascending=True))
    assert [r.ticker for r in out] == ["B", "A", "C"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_portfolio_table_logic.py -v`
Expected: FAIL (import error).

- [ ] **Step 3: Implement state + apply (pure)**

```python
# adapters/visualization/components/portfolio_table.py
"""Healthy-holdings table: pure sort/filter/page logic + HTML builder."""

from __future__ import annotations

from dataclasses import dataclass

from adapters.visualization.portfolio_view import PortfolioRow

_SORT_KEY = {
    "ticker": lambda r: r.ticker,
    "sector": lambda r: r.sector,
    "weight": lambda r: r.weight,
    "value": lambda r: r.value,
    "pnl": lambda r: r.pnl,
    "today": lambda r: r.today,
    "yield": lambda r: (r.dividend_yield if r.dividend_yield is not None else -1.0),
    "beta": lambda r: (r.beta if r.beta is not None else -1.0),
}


@dataclass(frozen=True)
class TableState:
    sort: str = "weight"
    ascending: bool = False
    filter: str = "all"   # all | gain | loss
    query: str = ""
    page: int = 1
    show_more: bool = False


def apply_table_state(rows: list[PortfolioRow], state: TableState) -> list[PortfolioRow]:
    out = list(rows)
    if state.query:
        q = state.query.upper()
        out = [r for r in out if q in r.ticker.upper()]
    if state.filter == "gain":
        out = [r for r in out if r.pnl > 0]
    elif state.filter == "loss":
        out = [r for r in out if r.pnl < 0]
    key = _SORT_KEY.get(state.sort, _SORT_KEY["weight"])
    out.sort(key=key, reverse=not state.ascending)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_portfolio_table_logic.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add adapters/visualization/components/portfolio_table.py tests/test_portfolio_table_logic.py
git commit -m "feat(portfolio): healthy-table sort/filter/search logic"
```

### Task 9: table HTML builder

**Files:**
- Modify: `adapters/visualization/components/portfolio_table.py`
- Test: `tests/test_portfolio_table_html.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_portfolio_table_html.py
from adapters.visualization.portfolio_view import PortfolioRow
from adapters.visualization.components.portfolio_table import build_table_html, TableState

def _r(tk, w, pnl, yld, beta):
    return PortfolioRow(tk, "Tech", w, w*10, 100, pnl, 0.3, "HOLD", "", yld, beta, 1.0)

def test_lean_has_core_columns_and_anchor():
    html = build_table_html([_r("AAA", 9.4, 19.1, 0.7, 1.1)], TableState())
    assert 'href="?inspect=AAA"' in html
    assert "Weight" in html and "Value" in html and "Verdict" in html
    assert "Beta" not in html  # hidden by default

def test_more_columns_reveals_yield_beta_cost():
    html = build_table_html([_r("AAA", 9.4, 19.1, 0.7, 1.1)], TableState(show_more=True))
    assert "Beta" in html and "Yield" in html and "Cost" in html
    assert "0.70%" in html  # dividend yield

def test_missing_yield_is_dash():
    html = build_table_html([_r("AAA", 9.4, 19.1, None, 1.1)], TableState(show_more=True))
    assert "—" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_portfolio_table_html.py -v`
Expected: FAIL (no build_table_html).

- [ ] **Step 3: Implement build_table_html (append to portfolio_table.py)**

```python
# append to adapters/visualization/components/portfolio_table.py
from adapters.visualization.components.tooltip import tooltip

_PILL = {
    "HOLD": ("#F0FDF4", "#166534"), "ADD_OK": ("#ECFDF5", "#065F46"),
}


def _pill(verdict: str) -> str:
    bg, fg = _PILL.get(verdict, ("#F1F5F9", "#475569"))
    return (f'<span style="padding:2px 8px;border-radius:11px;font-size:.66rem;'
            f'font-weight:700;background:{bg};color:{fg};">{verdict}</span>')


def _row_html(r: PortfolioRow, show_more: bool) -> str:
    pnl_c = "#16A34A" if r.pnl >= 0 else "#DC2626"
    today_c = "#16A34A" if r.today >= 0 else "#DC2626"
    cells = [
        f'<td style="font-family:\'Fraunces\',serif;font-weight:700;">{r.ticker}</td>',
        f"<td>{r.sector}</td>",
        f'<td style="text-align:right;font-family:\'IBM Plex Mono\',monospace;">'
        f'<span style="display:inline-block;height:7px;border-radius:3px;background:#CBD5E1;'
        f'width:{r.weight*4.5:.0f}px;margin-right:6px;vertical-align:middle;"></span>{r.weight:.1f}%</td>',
        f'<td style="text-align:right;font-family:\'IBM Plex Mono\',monospace;">${r.value:,.0f}</td>',
        f'<td style="text-align:right;font-family:\'IBM Plex Mono\',monospace;color:{pnl_c};">'
        f'{"+" if r.pnl>=0 else ""}{r.pnl:.1f}%</td>',
        f'<td style="text-align:right;font-family:\'IBM Plex Mono\',monospace;color:{today_c};">'
        f'{"+" if r.today>=0 else ""}{r.today:.1f}%</td>',
    ]
    if show_more:
        yld = f"{r.dividend_yield:.2f}%" if r.dividend_yield is not None else "—"
        beta = f"{r.beta:.2f}" if r.beta is not None else "—"
        cells.append(f'<td style="text-align:right;font-family:\'IBM Plex Mono\',monospace;">{yld}</td>')
        cells.append(f'<td style="text-align:right;font-family:\'IBM Plex Mono\',monospace;">{beta}</td>')
        cells.append(f'<td style="text-align:right;font-family:\'IBM Plex Mono\',monospace;">${r.cost:,.0f}</td>')
    cells.append(f"<td>{_pill(r.verdict)}</td>")
    return (
        f'<tr onclick="window.location.href=\'?inspect={r.ticker}\'" '
        f'style="cursor:pointer;">'
        f'<td style="display:none;"><a href="?inspect={r.ticker}" target="_self"></a></td>'
        + "".join(cells) + "</tr>"
    )


def build_table_html(rows: list[PortfolioRow], state: TableState) -> str:
    heads = ["Ticker", "Sector", "Weight", "Value", "P&amp;L %", "Today"]
    if state.show_more:
        heads += [f"{tooltip('Dividend yield', 'Yield')}", f"{tooltip('Beta', 'Beta')}", "Cost"]
    heads.append("Verdict")
    thead = "".join(f'<th style="text-align:left;font-size:.65rem;text-transform:uppercase;'
                    f'letter-spacing:.04em;color:var(--ri-muted);padding:7px 9px;'
                    f'border-bottom:1px solid var(--ri-line);">{h}</th>' for h in heads)
    body = "".join(_row_html(r, state.show_more) for r in rows)
    return (
        '<table style="width:100%;border-collapse:collapse;font-size:.82rem;background:#fff;'
        'border-radius:10px;overflow:hidden;">'
        f"<thead><tr>{thead}</tr></thead><tbody>{body}</tbody></table>"
    )
```

> NOTE: column-header click-to-sort and pagination are driven by Streamlit widgets in Task 12 (a `st.selectbox` for sort + `st.radio` chips + `st.text_input` search + `st.number_input`/buttons for page), NOT by clicking the HTML `<th>` (Streamlit can't capture those). The HTML table is display-only; row click uses the inspect anchor.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_portfolio_table_html.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add adapters/visualization/components/portfolio_table.py tests/test_portfolio_table_html.py
git commit -m "feat(portfolio): healthy-table HTML builder (lean + more-columns)"
```

---

## Phase 9 — Portfolio vs SPY (spec §8 / A7)

### Task 10: alpha + performance figure

**Files:**
- Create: `adapters/visualization/components/portfolio_performance.py`
- Test: `tests/test_portfolio_performance.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_portfolio_performance.py
from adapters.visualization.components.portfolio_performance import alpha_vs_spy, build_perf_figure

def test_alpha_simple():
    assert round(alpha_vs_spy(11.1, 7.1), 1) == 4.0

def test_alpha_none_when_spy_gap():
    assert alpha_vs_spy(11.1, None) is None

def test_build_perf_figure_two_traces():
    fig = build_perf_figure(
        port_pct=[0.0, 4.0, 11.1], spy_pct=[0.0, 3.0, 7.1], labels=["Mar", "Apr", "Jun"],
    )
    # two line traces (portfolio + spy)
    names = [t.name for t in fig.data]
    assert "Portfolio" in names and "SPY" in names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_portfolio_performance.py -v`
Expected: FAIL (import error).

- [ ] **Step 3: Implement**

```python
# adapters/visualization/components/portfolio_performance.py
"""Portfolio-vs-SPY cumulative return chart (attributed actual, no projection)."""

from __future__ import annotations

import plotly.graph_objects as go

from adapters.visualization.components.charts import apply_dossier_template


def alpha_vs_spy(port_pct: float, spy_pct: float | None) -> float | None:
    if spy_pct is None:
        return None
    return port_pct - spy_pct


def build_perf_figure(
    *, port_pct: list[float], spy_pct: list[float], labels: list[str]
) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=labels, y=spy_pct, name="SPY", mode="lines",
            line={"color": "#94A3B8", "width": 2, "dash": "dash"},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=labels, y=port_pct, name="Portfolio", mode="lines",
            line={"color": "#16A34A", "width": 2.5},
            fill="tozeroy", fillcolor="rgba(22,163,74,0.15)",
        )
    )
    fig.update_layout(height=220, showlegend=False, margin={"l": 30, "r": 10, "t": 10, "b": 20})
    return apply_dossier_template(fig)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_portfolio_performance.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add adapters/visualization/components/portfolio_performance.py tests/test_portfolio_performance.py
git commit -m "feat(portfolio): portfolio-vs-SPY chart + alpha"
```

---

## Phase 10 — Shared detail panel (spec §3 / A6)

### Task 11: render_inspect_detail (reuse decision_card via card_fetch)

**Files:**
- Create: `adapters/visualization/components/portfolio_detail.py`
- Test: `tests/test_portfolio_detail.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_portfolio_detail.py
from adapters.visualization.portfolio_view import PortfolioRow
from adapters.visualization.components.portfolio_detail import build_detail_header_html

def test_detail_header_has_ticker_verdict_perf():
    r = PortfolioRow("NVDA", "Tech", 9.4, 29410, 16760, 75.6, 2.1, "HOLD", "", 0.03, 1.7, 40)
    html = build_detail_header_html(r)
    assert "NVDA" in html
    assert "HOLD" in html
    assert "+75.6%" in html  # lifetime
    assert "+2.1%" in html   # today
    assert "9.4% of book" in html

def test_unknown_sector_datagap_note():
    r = PortfolioRow("ZZZ", "Unknown", 1.0, 100, 100, 0.0, 0.0, "HOLD", "", None, None, 1)
    html = build_detail_header_html(r)
    assert "Unknown" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_portfolio_detail.py -v`
Expected: FAIL (import error).

- [ ] **Step 3: Implement header builder + live-fetch renderer**

```python
# adapters/visualization/components/portfolio_detail.py
"""Shared detail panel for the portfolio tab.

Opened via ?inspect=TICKER from review cards, treemap tiles, or table rows.
Reuses decision_card.render_expanded_card with live RAG/case fetched lazily.
"""

from __future__ import annotations

import streamlit as st

from adapters.visualization.card_fetch import fetch_card, implied_cost, window_returns
from adapters.visualization.components.decision_card import render_expanded_card
from adapters.visualization.portfolio_view import PortfolioRow
from adapters.visualization.price_cache import fetch_price_history, fetch_prices
from domain.discipline import Verdict


def build_detail_header_html(row: PortfolioRow) -> str:
    pnl_c = "#16A34A" if row.pnl >= 0 else "#DC2626"
    today_c = "#16A34A" if row.today >= 0 else "#DC2626"
    return (
        '<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;'
        'padding:13px 17px;background:#F7FDFE;border-bottom:1px solid var(--ri-line);">'
        f'<span style="font-family:\'Fraunces\',serif;font-weight:700;font-size:1.35rem;">{row.ticker}</span>'
        f'<span style="color:var(--ri-muted);font-size:.8rem;">{row.sector} · {row.weight:.1f}% of book</span>'
        f'<span style="color:{pnl_c};font-size:.8rem;">lifetime {"+" if row.pnl>=0 else ""}{row.pnl:.1f}%</span>'
        f'<span style="color:{today_c};font-size:.8rem;">today {"+" if row.today>=0 else ""}{row.today:.1f}%</span>'
        "</div>"
    )


def render_inspect_detail(row: PortfolioRow) -> None:
    """Render the shared detail panel for an inspected holding (live fetch)."""
    st.markdown(
        f'<div style="border:1px solid var(--ri-teal);border-radius:12px;'
        f'overflow:hidden;margin-top:6px;">{build_detail_header_html(row)}</div>',
        unsafe_allow_html=True,
    )
    if st.button("✕ Close", key=f"close_inspect_{row.ticker}"):
        st.query_params.clear()
        st.rerun()
    try:
        card = fetch_card(row.ticker)
        price_data = fetch_prices((row.ticker,)).get(row.ticker, {})
        live_price = float(price_data.get("price") or 0.0) or None
        cost = implied_cost(live_price, row.pnl) if live_price else None
        hist = fetch_price_history(row.ticker) or {}
        rets = window_returns(list(hist.get("closes") or []))
        verdict = Verdict(row.verdict) if row.verdict else Verdict.REVIEW
        html = render_expanded_card(
            card, case=None, verdict=verdict, name=row.ticker,
            unrealized_pct=row.pnl, means=row.why or "Discipline review prompt — not a forecast.",
            price=live_price, cost=cost, returns=rets, reliability="live",
        )
        st.markdown(html, unsafe_allow_html=True)
    except Exception:
        st.info(f"Evidence for {row.ticker} is loading or unavailable (DATA-GAP).")
    st.markdown(
        f'<div style="display:flex;gap:8px;margin-top:10px;">'
        f'<span style="font-size:.78rem;color:var(--ri-teal);">↗ Open in Weekly Brief</span>'
        f'</div>',
        unsafe_allow_html=True,
    )
    if st.button(f"↗ Analyze {row.ticker}", key=f"analyze_inspect_{row.ticker}"):
        st.session_state["analyze_ticker"] = row.ticker
        st.info(f"{row.ticker} pre-filled — open the Stock Analysis tab.")
```

> NOTE: `render_expanded_card`'s exact kwargs were captured in Task 5 research; if `case` must be a real object, pass `get_case_on_expand(row.ticker)` from `card_fetch` instead of `None` (verify signature at implementation; both are in `card_fetch`).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_portfolio_detail.py -v`
Expected: PASS (2 tests; header builder is pure — the live renderer is exercised in integration).

- [ ] **Step 5: Commit**

```bash
git add adapters/visualization/components/portfolio_detail.py tests/test_portfolio_detail.py
git commit -m "feat(portfolio): shared detail panel reusing decision_card (live fetch)"
```

---

## Phase 11 — Orchestration + states + admin carry-over (spec §2, §9, §10 / A1, A8)

### Task 12: Rewrite positions.render()

**Files:**
- Modify: `adapters/visualization/tabs/positions.py`
- Test: `tests/test_positions_render.py`

- [ ] **Step 1: Write the failing test** (smoke: render with a fake DB does not raise; empty state)

```python
# tests/test_positions_render.py
import adapters.visualization.tabs.positions as positions

def test_render_is_callable():
    assert callable(positions.render)

def test_threshold_constant():
    # small-book flat-treemap threshold is defined and sane
    assert positions.SMALL_BOOK_MAX == 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_positions_render.py -v`
Expected: FAIL (SMALL_BOOK_MAX undefined).

- [ ] **Step 3: Rewrite `positions.py`**

Replace the file's `render()` and helpers with the orchestration below. KEEP the existing admin helpers (`_render_trade_form`, `_render_trade_history`, `_render_pnl_chart`, `_render_closed_positions_table`, `_render_watchlist_section`, and friends) — move them to the bottom unchanged (they are carried over per §10). Add:

```python
SMALL_BOOK_MAX = 5

def render(db_path: str = DB_PATH) -> None:
    import streamlit as st
    from adapters.visualization.data_loader import (
        load_holdings, load_brief_summary, load_trades, load_outcomes,
    )
    from adapters.visualization.price_cache import batch_fetch_prices, fetch_ticker_info
    from adapters.visualization.portfolio_view import (
        enrich_holdings, top5_weight, split_flagged_healthy,
    )
    from adapters.visualization.components.portfolio_metrics import build_hero_html
    from adapters.visualization.components.portfolio_review import (
        build_review_card_html, build_calm_html,
    )
    from adapters.visualization.components.treemap import build_treemap_html, LENSES
    from adapters.visualization.components.portfolio_table import (
        build_table_html, apply_table_state, TableState,
    )
    from adapters.visualization.components.portfolio_performance import (
        build_perf_figure, alpha_vs_spy,
    )
    from adapters.visualization.components.portfolio_detail import render_inspect_detail

    st.markdown('<div class="ri-h1">My Portfolio</div>', unsafe_allow_html=True)

    holdings = load_holdings(db_path)
    trades = load_trades(db_path)
    outcomes = load_outcomes(db_path)

    if not holdings and not trades:
        _render_empty_state()
        with st.expander("Record a Trade", expanded=False):
            _render_trade_form(db_path)
        return

    tickers = tuple(h.symbol for h in holdings)
    try:
        prices = batch_fetch_prices(tickers) if tickers else {}
    except Exception:
        prices = {}
    infos = {}
    for t in tickers:
        try:
            infos[t] = fetch_ticker_info(t)
        except Exception:
            infos[t] = {}
    brief = load_brief_summary() or {}
    brief_by_ticker = {b.get("ticker", ""): b for b in brief.get("holdings", []) if b.get("ticker")}

    rows = enrich_holdings(holdings, prices, infos, brief_by_ticker)
    flagged, healthy = split_flagged_healthy(rows)
    book_value = sum(r.value for r in rows)
    cost = sum(r.cost for r in rows)
    pnl = book_value - cost
    pnl_pct = (pnl / cost * 100.0) if cost > 0 else 0.0

    # SPY series (simple) — DATA-GAP-safe stub from brief if present
    spy_pct = brief.get("vs_market_1y")
    spy_end = float(spy_pct) if spy_pct is not None else None

    st.markdown('<div class="ri-sec">Portfolio snapshot</div>', unsafe_allow_html=True)
    st.markdown(
        build_hero_html(
            book_value=book_value, cost=cost, pnl=pnl, pnl_pct=pnl_pct,
            spy_pct=spy_end, needs_review=len(flagged), total_positions=len(rows),
            top5=top5_weight(rows),
        ),
        unsafe_allow_html=True,
    )

    # NEEDS REVIEW
    st.markdown(
        f'<div class="ri-sec" style="color:#991B1B;border-color:#FECACA;">'
        f'⚠ Needs review — {len(flagged)} of {len(rows)}</div>',
        unsafe_allow_html=True,
    )
    if flagged:
        for r in flagged:
            st.markdown(build_review_card_html(r), unsafe_allow_html=True)
    else:
        st.markdown(build_calm_html(), unsafe_allow_html=True)

    # TREEMAP
    st.markdown('<div class="ri-sec">Your book at a glance</div>', unsafe_allow_html=True)
    lens = st.radio("Colour by", LENSES, horizontal=True,
                    format_func=lambda x: {"pnl": "P&L", "today": "Today", "verdict": "Verdict"}[x],
                    key="pf_lens", label_visibility="collapsed")
    flat = len(rows) <= SMALL_BOOK_MAX
    st.markdown(
        build_treemap_html(rows, lens=lens, width=1000.0, height=360.0, flat=flat),
        unsafe_allow_html=True,
    )

    # SHARED DETAIL PANEL (from ?inspect=)
    inspect = st.query_params.get("inspect")
    if inspect:
        match = next((r for r in rows if r.ticker == inspect), None)
        if match:
            render_inspect_detail(match)

    # HEALTHY TABLE
    st.markdown(
        f'<div class="ri-sec">Healthy holdings — {len(healthy)} of {len(rows)}</div>',
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns([3, 2, 2])
    query = c1.text_input("Filter ticker", key="pf_q", label_visibility="collapsed", placeholder="🔎 filter ticker")
    filt = c2.radio("Filter", ["all", "gain", "loss"], horizontal=True, key="pf_filter", label_visibility="collapsed")
    show_more = c3.toggle("⊕ more columns", key="pf_more")
    sort = st.selectbox("Sort by", ["weight", "pnl", "today", "value", "ticker", "sector"], key="pf_sort")
    state = TableState(sort=sort, ascending=False, filter=filt, query=query or "", show_more=show_more)
    view = apply_table_state(healthy, state)
    PAGE = 10
    total_pages = max(1, (len(view) + PAGE - 1) // PAGE)
    page = st.number_input("Page", 1, total_pages, 1, key="pf_page")
    start = (int(page) - 1) * PAGE
    st.markdown(build_table_html(view[start:start + PAGE], state), unsafe_allow_html=True)
    st.caption(f"Showing {start + 1 if view else 0}–{min(start + PAGE, len(view))} of {len(view)}")

    # PORTFOLIO VS SPY
    alpha = alpha_vs_spy(pnl_pct, spy_end)
    badge = f"▲ +{alpha:.1f}% vs SPY" if alpha is not None and alpha >= 0 else (
        f"▼ {alpha:.1f}% vs SPY" if alpha is not None else "SPY: DATA-GAP")
    st.markdown(f'<div class="ri-sec">Portfolio vs SPY &nbsp; <span style="font-size:.8rem;color:var(--ri-green);">{badge}</span></div>', unsafe_allow_html=True)
    win = st.radio("Window", ["ytd", "all", "1y"], index=1, horizontal=True,
                   format_func=lambda x: {"ytd": "YTD", "all": "All", "1y": "1Y"}[x],
                   key="pf_window", label_visibility="collapsed")
    port_series, spy_series, labels = _perf_series(rows, win, spy_end, pnl_pct)
    st.plotly_chart(build_perf_figure(port_pct=port_series, spy_pct=spy_series, labels=labels),
                    use_container_width=True)

    # ADMIN (carried over)
    st.markdown('<div class="ri-sec">Manage</div>', unsafe_allow_html=True)
    if outcomes:
        with st.expander("Trade history & outcome tracker", expanded=False):
            _render_trade_history(trades, outcomes)
        with st.expander("Closed positions", expanded=False):
            _render_pnl_chart(outcomes)
            _render_closed_positions_table(outcomes)
    with st.expander("Watchlist", expanded=False):
        _render_watchlist_section(db_path)
    with st.expander("Record a Trade", expanded=False):
        _render_trade_form(db_path)


def _perf_series(rows, window, spy_end, pnl_pct):
    """Simple attributed cumulative-return series per window.

    v1: linear ramp from 0 to the realised endpoint, labelled by window.
    Real per-day series is a follow-up (spec §8 money-weighted upgrade).
    DATA-GAP-safe: spy flat at 0 if spy_end is None.
    """
    labels = {"ytd": ["Jan", "Mar", "Jun"], "all": ["Mar", "Apr", "Jun"],
              "1y": ["Jun '25", "Dec", "Jun '26"]}[window]
    n = len(labels)
    port = [round(pnl_pct * i / (n - 1), 2) for i in range(n)]
    end = spy_end if spy_end is not None else 0.0
    spy = [round(end * i / (n - 1), 2) for i in range(n)]
    return port, spy, labels
```

> NOTE: `_perf_series` is intentionally a simple ramp for v1 (matches §8 "simple-return v1; money-weighted deferred"). The real per-day series belongs to the deferred money-weighted upgrade; do not block v1 on it.

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_positions_render.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add adapters/visualization/tabs/positions.py tests/test_positions_render.py
git commit -m "feat(portfolio): orchestrate redesigned tab (hero/review/treemap/table/spy/admin + inspect detail)"
```

### Task 13: Wire-up verification + dashboard

**Files:**
- Verify: `adapters/visualization/dashboard.py` (no change — still imports `positions.render`)

- [ ] **Step 1: Confirm import path unchanged**

Run: `grep -n "positions import render" adapters/visualization/dashboard.py`
Expected: the existing lazy import line is intact (tab index 3).

- [ ] **Step 2: Commit (if any incidental change)** — otherwise skip.

---

## Phase 12 — Full-gate + manual verification (spec Appendix B)

### Task 14: Run the full gate

- [ ] **Step 1: Run the complete gate**

Run: `make check`
Expected: pytest green (baseline + new tests), coverage ≥90%, mypy strict clean, ruff clean.
If pre-commit reformats on first run, re-run `make check` (watch for a *persistent* failure vs a self-resolving reformat — per project gotcha).

- [ ] **Step 2: Manual eyeball (live app)**

Launch via the project's screenshot/run path (`scripts/screenshot_dashboard.py --tab 3`, or run the dashboard) and verify against Appendix B checklist:
1. Three entry points (review card / treemap tile / table row) all open the same detail panel.
2. Dominant sector = big block, no slivers; tickers don't overflow; lens toggle recolors; small book (≤5) flat.
3. Hover tooltip shows weight/lifetime/today.
4. Table sort/filter/search/page work; ⊕ more columns reveals yield/beta/cost; "—" when absent.
5. SPY window toggle swaps series + alpha; DATA-GAP before first buy.
6. Empty states: 0 holdings → empty card; 0 flagged → calm ✓; ≤5 → flat treemap.
7. No predicted returns; treemap color = realized; SPY attributed.
8. DATA-GAP for missing brief/sector/yield/beta.

- [ ] **Step 3: Commit any fixes; final commit**

```bash
git add -A
git commit -m "chore(portfolio): finalize tab redesign — full gate green, eyeballed"
```

---

## Self-Review Notes (author)

- **Spec coverage:** §1 (Task 12 spine), §2 (Task 12 order), §3 (Task 5+11 reuse), §3a (Task 0 glossary + CSS in 6/7), §4 honesty (DATA-GAP in 3/8/11/12), §5 (Task 3), §6/§6a (Task 1/2/7 + lens radio in 12), §7 (Task 8/9 + widgets in 12), §8 (Task 10 + _perf_series in 12), §9 (Task 12 empty/calm/flat), §10 (Task 12 admin carry-over). Appendix A behaviors covered; Appendix B = Task 14 checklist.
- **Known follow-ups (explicitly deferred, not gaps):** real per-day SPY series / money-weighted (§8 upgrade); HTML `<th>` click-sort replaced by `st.selectbox` (Streamlit constraint, noted in Task 9).
- **Type consistency:** `PortfolioRow` field order is fixed in Task 3 and used positionally only in tests; production code uses keyword construction. `TableState` fields stable across Tasks 8/9/12. `lens` ∈ `LENSES` everywhere.
