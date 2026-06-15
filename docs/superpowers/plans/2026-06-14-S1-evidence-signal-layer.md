# S1 — Evidence Signal Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce, for any ticker, 5 fixed-order R/A/G evidence dimensions (Technicals, Valuation, Financials, Earnings, Analysts) plus a realized-price sparkline — honestly DATA-GAP where data is missing — as the single data source behind both the collapsed RAG squares and the expanded v9 evidence table.

**Architecture:** Pure-domain classification (`domain/evidence_rag.py`, stdlib only, threshold logic + property-tested) → a net-new earnings-history fetcher (`adapters/data/earnings_history_adapter.py`, yfinance) → an application assembler (`application/evidence_card.py`) that composes existing modules (`domain/peer_relative`, `application/analyst_panel`, `adapters/data/yfinance_adapter` field map) into one `EvidenceCard`. No framework imports in `domain/`. No look-ahead: PEG/forward_pe are display-only, never features.

**Tech Stack:** Python 3.12, dataclasses + Enum, Hypothesis (property tests), pytest, yfinance, mypy --strict.

**Spec:** `docs/superpowers/specs/2026-06-14-home-decision-card-redesign-spec.md` §3. **Visual contract:** `.superpowers/brainstorm/97077-1781379305/content/per-stock-v9.html` (the 5-row evidence table + square colors).

---

## File Structure

- Create `domain/evidence_rag.py` — `RagColor`, `RagSignal`, `DIMENSIONS`, `classify_*` (5). Pure, stdlib.
- Create `adapters/data/earnings_history_adapter.py` — `EpsQuarter`, `EarningsHistory`, `fetch_earnings_history` + `_fetch_earnings_history_impl`.
- Create `application/evidence_card.py` — `EvidenceCard`, `build_evidence_card` (composes the above + existing modules).
- Create `tests/domain/test_evidence_rag.py`, `tests/adapters/test_earnings_history_adapter.py`, `tests/application/test_evidence_card.py`.

Reuses (do NOT modify): `domain/peer_relative.sector_percentile`, `application/analyst_panel.AnalystPanel`/`build_analyst_panel`, `adapters/data/yfinance_adapter.YFinanceAdapter.get_ticker_info` field names.

---

### Task 1: RAG color + signal types

**Files:**
- Create: `domain/evidence_rag.py`
- Test: `tests/domain/test_evidence_rag.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/domain/test_evidence_rag.py
from domain.evidence_rag import RagColor, RagSignal, DIMENSIONS


def test_dimensions_fixed_order():
    assert DIMENSIONS == ("Technicals", "Valuation", "Financials", "Earnings", "Analysts")


def test_rag_signal_is_frozen():
    sig = RagSignal(dimension="Technicals", color=RagColor.RED, detail="2.3 ATR below 200-day")
    assert sig.color is RagColor.RED
    assert sig.detail == "2.3 ATR below 200-day"
    import dataclasses
    assert dataclasses.is_dataclass(sig)
    try:
        sig.detail = "x"  # type: ignore[misc]
        raised = False
    except dataclasses.FrozenInstanceError:
        raised = True
    assert raised
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/domain/test_evidence_rag.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'domain.evidence_rag'`

- [ ] **Step 3: Write minimal implementation**

```python
# domain/evidence_rag.py
"""Pure RAG evidence classification (stdlib only). No framework imports."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

DIMENSIONS: tuple[str, ...] = ("Technicals", "Valuation", "Financials", "Earnings", "Analysts")


class RagColor(Enum):
    RED = "R"
    AMBER = "A"
    GREEN = "G"
    GAP = "GAP"


@dataclass(frozen=True)
class RagSignal:
    dimension: str
    color: RagColor
    detail: str
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/domain/test_evidence_rag.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git checkout data/reports/ 2>/dev/null || true
git add domain/evidence_rag.py tests/domain/test_evidence_rag.py
git commit -m "feat(evidence): add RagColor/RagSignal types + fixed DIMENSIONS order"
```

---

### Task 2: `classify_technicals`

**Files:**
- Modify: `domain/evidence_rag.py`
- Test: `tests/domain/test_evidence_rag.py`

Rule: `atr_vs_200d` = (price − 200-day MA) in ATR units (negative = below trend). GREEN ≥ +0.5, RED ≤ −1.5, else AMBER. Missing both inputs → GAP.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/domain/test_evidence_rag.py
from domain.evidence_rag import classify_technicals


def test_technicals_below_trend_is_red():
    sig = classify_technicals(atr_vs_200d=-2.3, vs_spy_pct=-9.0)
    assert sig.color is RagColor.RED
    assert "200-day" in sig.detail and "SPY" in sig.detail


def test_technicals_above_trend_is_green():
    assert classify_technicals(atr_vs_200d=1.2, vs_spy_pct=4.0).color is RagColor.GREEN


def test_technicals_mid_is_amber():
    assert classify_technicals(atr_vs_200d=-0.4, vs_spy_pct=1.0).color is RagColor.AMBER


def test_technicals_missing_is_gap():
    sig = classify_technicals(atr_vs_200d=None, vs_spy_pct=None)
    assert sig.color is RagColor.GAP
    assert "DATA-GAP" in sig.detail
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/domain/test_evidence_rag.py -k technicals -v`
Expected: FAIL — `ImportError: cannot import name 'classify_technicals'`

- [ ] **Step 3: Implement**

```python
# append to domain/evidence_rag.py
def _fmt(v: float | None, suffix: str = "") -> str:
    return "—" if v is None else f"{v:+.1f}{suffix}"


def classify_technicals(atr_vs_200d: float | None, vs_spy_pct: float | None) -> RagSignal:
    if atr_vs_200d is None and vs_spy_pct is None:
        return RagSignal("Technicals", RagColor.GAP, "DATA-GAP: no price history")
    detail = f"{_fmt(atr_vs_200d)} ATR vs 200-day · vs SPY {_fmt(vs_spy_pct, '%')}"
    if atr_vs_200d is None:
        return RagSignal("Technicals", RagColor.AMBER, detail)
    if atr_vs_200d >= 0.5:
        return RagSignal("Technicals", RagColor.GREEN, detail)
    if atr_vs_200d <= -1.5:
        return RagSignal("Technicals", RagColor.RED, detail)
    return RagSignal("Technicals", RagColor.AMBER, detail)
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/domain/test_evidence_rag.py -k technicals -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add domain/evidence_rag.py tests/domain/test_evidence_rag.py
git commit -m "feat(evidence): classify_technicals (price vs 200-day in ATR units)"
```

---

### Task 3: `classify_valuation`

**Files:** Modify `domain/evidence_rag.py`; Test `tests/domain/test_evidence_rag.py`

Rule: GREEN if `peg ≤ 1.2` OR `sector_pctile ≥ 60` (cheaper than ≥60% of peers). RED if `peg ≥ 2.5` OR `sector_pctile ≤ 25`. else AMBER. All inputs None → GAP. (PEG is display-only attributed; never a feature.)

- [ ] **Step 1: Write failing test**

```python
from domain.evidence_rag import classify_valuation


def test_valuation_cheap_is_green():
    sig = classify_valuation(peg=0.9, pe=19.0, sector_pctile=62.0)
    assert sig.color is RagColor.GREEN
    assert "PEG 0.9" in sig.detail and "62%" in sig.detail


def test_valuation_expensive_is_red():
    assert classify_valuation(peg=3.1, pe=44.0, sector_pctile=15.0).color is RagColor.RED


def test_valuation_mid_is_amber():
    assert classify_valuation(peg=1.8, pe=22.0, sector_pctile=45.0).color is RagColor.AMBER


def test_valuation_missing_is_gap():
    assert classify_valuation(peg=None, pe=None, sector_pctile=None).color is RagColor.GAP
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/domain/test_evidence_rag.py -k valuation -v` → FAIL (ImportError)

- [ ] **Step 3: Implement**

```python
def classify_valuation(peg: float | None, pe: float | None, sector_pctile: float | None) -> RagSignal:
    if peg is None and pe is None and sector_pctile is None:
        return RagSignal("Valuation", RagColor.GAP, "DATA-GAP: no valuation data")
    parts = []
    if peg is not None:
        parts.append(f"PEG {peg:.1f}")
    if pe is not None:
        parts.append(f"P/E {pe:.0f}")
    if sector_pctile is not None:
        parts.append(f"cheaper than {sector_pctile:.0f}% of sector")
    detail = " · ".join(parts)
    cheap = (peg is not None and peg <= 1.2) or (sector_pctile is not None and sector_pctile >= 60)
    rich = (peg is not None and peg >= 2.5) or (sector_pctile is not None and sector_pctile <= 25)
    if cheap and not rich:
        return RagSignal("Valuation", RagColor.GREEN, detail)
    if rich and not cheap:
        return RagSignal("Valuation", RagColor.RED, detail)
    return RagSignal("Valuation", RagColor.AMBER, detail)
```

- [ ] **Step 4: Run to verify pass** → `pytest tests/domain/test_evidence_rag.py -k valuation -v` PASS (4)

- [ ] **Step 5: Commit**

```bash
git add domain/evidence_rag.py tests/domain/test_evidence_rag.py
git commit -m "feat(evidence): classify_valuation (PEG + sector percentile)"
```

---

### Task 4: `classify_financials`

**Files:** Modify `domain/evidence_rag.py`; Test same.

Rule: inputs `fcf_positive: bool|None`, `debt_to_equity: float|None` (yfinance scale — a percent, e.g. 45.0 = 45%), `margins_stable: bool|None`. GREEN if `fcf_positive` AND `debt_to_equity < 150`. RED if `fcf_positive is False` OR `debt_to_equity ≥ 150`. else AMBER. All None → GAP.

- [ ] **Step 1: Failing test**

```python
from domain.evidence_rag import classify_financials


def test_financials_healthy_is_green():
    sig = classify_financials(fcf_positive=True, debt_to_equity=45.0, margins_stable=True)
    assert sig.color is RagColor.GREEN
    assert "FCF positive" in sig.detail


def test_financials_levered_or_burning_is_red():
    assert classify_financials(fcf_positive=False, debt_to_equity=40.0, margins_stable=True).color is RagColor.RED
    assert classify_financials(fcf_positive=True, debt_to_equity=210.0, margins_stable=True).color is RagColor.RED


def test_financials_missing_is_gap():
    assert classify_financials(fcf_positive=None, debt_to_equity=None, margins_stable=None).color is RagColor.GAP
```

- [ ] **Step 2: Run fail** → `pytest tests/domain/test_evidence_rag.py -k financials -v` FAIL

- [ ] **Step 3: Implement**

```python
def classify_financials(
    fcf_positive: bool | None, debt_to_equity: float | None, margins_stable: bool | None
) -> RagSignal:
    if fcf_positive is None and debt_to_equity is None and margins_stable is None:
        return RagSignal("Financials", RagColor.GAP, "DATA-GAP: no financials")
    fcf_txt = "FCF positive" if fcf_positive else ("FCF negative" if fcf_positive is False else "FCF —")
    debt_txt = "debt —" if debt_to_equity is None else (
        "debt high" if debt_to_equity >= 150 else "debt moderate"
    )
    margin_txt = "margins stable" if margins_stable else ("margins —" if margins_stable is None else "margins soft")
    detail = f"{fcf_txt} · {debt_txt} · {margin_txt}"
    levered = debt_to_equity is not None and debt_to_equity >= 150
    if fcf_positive and not levered:
        return RagSignal("Financials", RagColor.GREEN, detail)
    if fcf_positive is False or levered:
        return RagSignal("Financials", RagColor.RED, detail)
    return RagSignal("Financials", RagColor.AMBER, detail)
```

- [ ] **Step 4: Run pass** → PASS (3)

- [ ] **Step 5: Commit**

```bash
git add domain/evidence_rag.py tests/domain/test_evidence_rag.py
git commit -m "feat(evidence): classify_financials (FCF + leverage + margins)"
```

---

### Task 5: `classify_earnings`

**Files:** Modify `domain/evidence_rag.py`; Test same.

Rule: `beats`/`total` over last quarters. GAP if `total is None or total == 0`. ratio = beats/total: GREEN ≥ 0.75, RED ≤ 0.25, else AMBER. Revenue surprise stays DATA-GAP (mentioned in detail, never scored).

- [ ] **Step 1: Failing test**

```python
from domain.evidence_rag import classify_earnings


def test_earnings_mostly_beats_is_green():
    sig = classify_earnings(beats=3, total=4)
    assert sig.color is RagColor.GREEN
    assert "beat 3 of 4" in sig.detail and "revenue surprise" in sig.detail.lower()


def test_earnings_mostly_miss_is_red():
    assert classify_earnings(beats=0, total=4).color is RagColor.RED


def test_earnings_no_data_is_gap():
    assert classify_earnings(beats=None, total=None).color is RagColor.GAP
    assert classify_earnings(beats=0, total=0).color is RagColor.GAP
```

- [ ] **Step 2: Run fail** → FAIL

- [ ] **Step 3: Implement**

```python
def classify_earnings(beats: int | None, total: int | None) -> RagSignal:
    if total is None or total == 0:
        return RagSignal("Earnings", RagColor.GAP, "DATA-GAP: no earnings history")
    b = beats or 0
    detail = f"EPS beat {b} of {total} · revenue surprise: needs estimates feed"
    ratio = b / total
    if ratio >= 0.75:
        return RagSignal("Earnings", RagColor.GREEN, detail)
    if ratio <= 0.25:
        return RagSignal("Earnings", RagColor.RED, detail)
    return RagSignal("Earnings", RagColor.AMBER, detail)
```

- [ ] **Step 4: Run pass** → PASS (3)

- [ ] **Step 5: Commit**

```bash
git add domain/evidence_rag.py tests/domain/test_evidence_rag.py
git commit -m "feat(evidence): classify_earnings (EPS beat ratio, revenue stays DATA-GAP)"
```

---

### Task 6: `classify_analysts`

**Files:** Modify `domain/evidence_rag.py`; Test same.

Takes `AnalystPanel` (E2) + `current_price`. GAP if `panel.data_gap`. spread = (high−low)/mean. upside = (mean−current)/current. AMBER if spread ≥ 0.30 (wide = uncertainty) — overrides. else GREEN if upside ≥ 0, RED if upside < 0.

> Note: spec §3 listed `classify_analysts(panel)`; this plan refines it to also take `current_price` (needed for upside). Keep this signature everywhere downstream.

- [ ] **Step 1: Failing test**

```python
from domain.evidence_rag import classify_analysts
from application.analyst_panel import AnalystPanel


def _panel(count=43, mean=1.9, tmean=47.8, thigh=70.0, tlow=30.0, gap=False):
    return AnalystPanel(count=count, mean_rating=mean, target_mean=tmean, target_high=thigh,
                        target_low=tlow, as_of="2026-06-14", attribution="yfinance", data_gap=gap)


def test_analysts_wide_spread_is_amber():
    sig = classify_analysts(_panel(thigh=70.0, tlow=30.0), current_price=44.63)  # spread ~0.84
    assert sig.color is RagColor.AMBER
    assert "43 cover" in sig.detail


def test_analysts_tight_upside_is_green():
    assert classify_analysts(_panel(tmean=50.0, thigh=52.0, tlow=48.0), current_price=44.63).color is RagColor.GREEN


def test_analysts_tight_downside_is_red():
    assert classify_analysts(_panel(tmean=40.0, thigh=42.0, tlow=39.0), current_price=44.63).color is RagColor.RED


def test_analysts_gap():
    assert classify_analysts(_panel(gap=True, count=0), current_price=44.63).color is RagColor.GAP
```

- [ ] **Step 2: Run fail** → FAIL

- [ ] **Step 3: Implement**

```python
from application.analyst_panel import AnalystPanel  # add to imports at top of evidence_rag.py


def classify_analysts(panel: AnalystPanel, current_price: float | None) -> RagSignal:
    if panel.data_gap or panel.target_mean is None:
        return RagSignal("Analysts", RagColor.GAP, "DATA-GAP: no analyst coverage")
    pieces = [f"{panel.count} cover"]
    upside = None
    if current_price and current_price > 0:
        upside = (panel.target_mean - current_price) / current_price
        pieces.append(f"target {upside:+.0%}")
    spread = None
    if panel.target_high is not None and panel.target_low is not None and panel.target_mean:
        spread = (panel.target_high - panel.target_low) / panel.target_mean
        pieces.append("wide spread" if spread >= 0.30 else "tight spread")
    detail = " · ".join(pieces)
    if spread is not None and spread >= 0.30:
        return RagSignal("Analysts", RagColor.AMBER, detail)
    if upside is None:
        return RagSignal("Analysts", RagColor.AMBER, detail)
    return RagSignal("Analysts", RagColor.GREEN if upside >= 0 else RagColor.RED, detail)
```

> `domain/` importing from `application/` violates inward-pointing deps. RESOLUTION: move `AnalystPanel` import to a TYPE_CHECKING-only import and accept a structural read, OR (preferred) keep `classify_analysts` taking the 5 scalars it needs instead of the dataclass. Use this signature instead to keep domain pure:
> `def classify_analysts(count: int, target_mean: float | None, target_high: float | None, target_low: float | None, data_gap: bool, current_price: float | None) -> RagSignal`
> Update the test `_panel` calls to pass scalars. The assembler (Task 9) unpacks `AnalystPanel` into these scalars. **Use the scalar signature** — it preserves hexagonal purity (no `application` import in `domain`).

- [ ] **Step 4: Re-write test + impl with the scalar signature, run pass**

```python
# replace the analyst tests' calls, e.g.:
def test_analysts_wide_spread_is_amber():
    sig = classify_analysts(count=43, target_mean=47.8, target_high=70.0, target_low=30.0,
                            data_gap=False, current_price=44.63)
    assert sig.color is RagColor.AMBER
```
```python
def classify_analysts(count: int, target_mean: float | None, target_high: float | None,
                      target_low: float | None, data_gap: bool, current_price: float | None) -> RagSignal:
    if data_gap or target_mean is None:
        return RagSignal("Analysts", RagColor.GAP, "DATA-GAP: no analyst coverage")
    pieces = [f"{count} cover"]
    upside = None
    if current_price and current_price > 0:
        upside = (target_mean - current_price) / current_price
        pieces.append(f"target {upside:+.0%}")
    spread = None
    if target_high is not None and target_low is not None and target_mean:
        spread = (target_high - target_low) / target_mean
        pieces.append("wide spread" if spread >= 0.30 else "tight spread")
    detail = " · ".join(pieces)
    if spread is not None and spread >= 0.30:
        return RagSignal("Analysts", RagColor.AMBER, detail)
    if upside is None:
        return RagSignal("Analysts", RagColor.AMBER, detail)
    return RagSignal("Analysts", RagColor.GREEN if upside >= 0 else RagColor.RED, detail)
```
Run: `pytest tests/domain/test_evidence_rag.py -k analysts -v` → PASS (4)

- [ ] **Step 5: Commit**

```bash
git add domain/evidence_rag.py tests/domain/test_evidence_rag.py
git commit -m "feat(evidence): classify_analysts (scalar args, keeps domain pure)"
```

---

### Task 7: Property tests (boundary + GAP invariants)

**Files:** Test `tests/domain/test_evidence_rag.py` (add Hypothesis block).

- [ ] **Step 1: Write property tests**

```python
from hypothesis import given, strategies as st
from domain.evidence_rag import classify_earnings, classify_technicals, RagColor


@given(beats=st.integers(min_value=0, max_value=20), total=st.integers(min_value=1, max_value=20))
def test_earnings_color_total_in_range(beats, total):
    sig = classify_earnings(min(beats, total), total)
    assert sig.color in {RagColor.RED, RagColor.AMBER, RagColor.GREEN}  # never GAP when total>0


@given(atr=st.floats(min_value=-10, max_value=10, allow_nan=False))
def test_technicals_monotone_buckets(atr):
    c = classify_technicals(atr, 0.0).color
    if atr >= 0.5:
        assert c is RagColor.GREEN
    elif atr <= -1.5:
        assert c is RagColor.RED
    else:
        assert c is RagColor.AMBER
```

- [ ] **Step 2: Run** → `pytest tests/domain/test_evidence_rag.py -k "property or buckets or in_range" -v` PASS

- [ ] **Step 3: Commit**

```bash
git add tests/domain/test_evidence_rag.py
git commit -m "test(evidence): property tests for RAG boundary + GAP invariants"
```

---

### Task 8: Earnings-history adapter (NET-NEW yfinance fetcher)

**Files:**
- Create: `adapters/data/earnings_history_adapter.py`
- Test: `tests/adapters/test_earnings_history_adapter.py`

> **Before implementing the yfinance call, verify the current API via context7** (`resolve-library-id yfinance` → `query-docs` topic "earnings_dates earnings_history Ticker"). As of writing, `yf.Ticker(t).earnings_dates` returns a DataFrame indexed by date with columns including `"EPS Estimate"`, `"Reported EPS"`, `"Surprise(%)"`. The impl parses the most recent 4 rows that have a reported EPS.

- [ ] **Step 1: Write the failing test (parser over a fake DataFrame — no network)**

```python
# tests/adapters/test_earnings_history_adapter.py
import pandas as pd
from adapters.data.earnings_history_adapter import parse_earnings_frame, EarningsHistory


def test_parse_counts_beats_last_4():
    df = pd.DataFrame(
        {
            "EPS Estimate": [0.50, 0.40, 0.30, 0.20, 0.10],
            "Reported EPS": [0.55, 0.41, 0.33, 0.18, None],  # last row not yet reported
            "Surprise(%)": [10.0, 2.5, 9.2, -10.0, None],
        },
        index=pd.to_datetime(["2026-04-01", "2026-02-01", "2025-11-01", "2025-08-01", "2026-07-01"]),
    )
    hist = parse_earnings_frame(df)
    assert isinstance(hist, EarningsHistory)
    assert hist.total == 4
    assert hist.beats == 3  # +10, +2.5, +9.2 positive; -10 miss
    assert len(hist.quarters) == 4


def test_parse_empty_returns_none():
    assert parse_earnings_frame(pd.DataFrame()) is None
    assert parse_earnings_frame(None) is None
```

- [ ] **Step 2: Run fail** → `pytest tests/adapters/test_earnings_history_adapter.py -v` FAIL (ImportError)

- [ ] **Step 3: Implement**

```python
# adapters/data/earnings_history_adapter.py
"""Net-new yfinance earnings-surprise fetcher. Revenue surprise NOT fetched (stays DATA-GAP)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class EpsQuarter:
    label: str
    eps_actual: float | None
    eps_estimate: float | None
    surprise_pct: float | None


@dataclass(frozen=True)
class EarningsHistory:
    quarters: tuple[EpsQuarter, ...]
    beats: int
    total: int


def parse_earnings_frame(df: "pd.DataFrame | None") -> EarningsHistory | None:
    if df is None or len(df) == 0 or "Reported EPS" not in df.columns:
        return None
    reported = df[df["Reported EPS"].notna()].sort_index(ascending=False).head(4)
    if len(reported) == 0:
        return None
    quarters: list[EpsQuarter] = []
    beats = 0
    for idx, row in reported.iterrows():
        surprise = row.get("Surprise(%)")
        s = float(surprise) if surprise is not None and not pd.isna(surprise) else None
        if s is not None and s > 0:
            beats += 1
        quarters.append(
            EpsQuarter(
                label=pd.Timestamp(idx).strftime("%b"),
                eps_actual=_f(row.get("Reported EPS")),
                eps_estimate=_f(row.get("EPS Estimate")),
                surprise_pct=s,
            )
        )
    return EarningsHistory(quarters=tuple(quarters), beats=beats, total=len(quarters))


def _f(v: Any) -> float | None:
    return None if v is None or pd.isna(v) else float(v)


def _fetch_earnings_history_impl(ticker: str) -> EarningsHistory | None:
    import yfinance as yf  # lazy import for CI safety

    try:
        df = yf.Ticker(ticker).earnings_dates  # verify via context7
    except Exception:  # noqa: BLE001 — network/parse failures → honest None (DATA-GAP)
        return None
    return parse_earnings_frame(df)


def fetch_earnings_history(ticker: str) -> EarningsHistory | None:
    """Streamlit-cached wrapper added in S5; for now a thin pass-through."""
    return _fetch_earnings_history_impl(ticker)
```

- [ ] **Step 4: Run pass** → `pytest tests/adapters/test_earnings_history_adapter.py -v` PASS (2)

- [ ] **Step 5: Commit**

```bash
git add adapters/data/earnings_history_adapter.py tests/adapters/test_earnings_history_adapter.py
git commit -m "feat(evidence): net-new earnings-history adapter (EPS surprise, last 4Q)"
```

---

### Task 9: `EvidenceCard` assembler

**Files:**
- Create: `application/evidence_card.py`
- Test: `tests/application/test_evidence_card.py`

Composes: yfinance `info` dict (field map), price series → technicals + sparkline, `sector_percentile`, `AnalystPanel`, `EarningsHistory` → 5 `RagSignal` in fixed order.

> **CONTRACT — `info` dict key casing (anti-drift, verified against `adapters/data/yfinance_adapter.py:100-115`):** the `info` param MUST be the output of `YFinanceAdapter.get_ticker_info()`, which maps to **snake_case** keys: `trailing_pe`, `debt_to_equity`, `peg_ratio`, `free_cashflow`, `market_cap`, etc. **Do NOT pass raw `yf.Ticker().info`** (that is camelCase `trailingPE`/`pegRatio`/… and every `info.get(...)` here would silently return None → false DATA-GAPs). `current_price` is added by the caller from the price fetch (not in `get_ticker_info`).

- [ ] **Step 1: Write the failing test (all inputs faked — no network)**

```python
# tests/application/test_evidence_card.py
from application.evidence_card import EvidenceCard, build_evidence_card
from application.analyst_panel import AnalystPanel
from adapters.data.earnings_history_adapter import EarningsHistory, EpsQuarter
from domain.evidence_rag import RagColor, DIMENSIONS


def _panel():
    return AnalystPanel(count=43, mean_rating=1.9, target_mean=47.8, target_high=52.0,
                        target_low=44.0, as_of="2026-06-14", attribution="yfinance", data_gap=False)


def _earnings():
    qs = tuple(EpsQuarter(m, a, e, s) for m, a, e, s in
               [("Aug", 0.18, 0.20, -10.0), ("Nov", 0.41, 0.40, 2.5),
                ("Feb", 0.33, 0.30, 9.2), ("Apr", 0.55, 0.50, 10.0)])
    return EarningsHistory(quarters=qs, beats=3, total=4)


def test_build_card_has_five_signals_fixed_order():
    info = {"peg_ratio": 0.9, "trailing_pe": 19.0, "free_cashflow": 1.2e9,
            "debt_to_equity": 45.0, "current_price": 44.63}
    prices = {"closes": [40.0] * 150 + [44.63], "atr": 2.0, "ma200": 50.0, "spy_1y": 0.0, "book_1y": -9.0}
    card = build_evidence_card("YUMC", info=info, prices=prices, panel=_panel(),
                               earnings=_earnings(), peers=[20.0, 25.0, 18.0, 30.0])
    assert isinstance(card, EvidenceCard)
    assert tuple(s.dimension for s in card.signals) == DIMENSIONS
    assert card.signals[3].color is RagColor.GREEN          # Earnings beat 3/4
    assert len(card.sparkline) > 0


def test_build_card_data_gap_paths():
    info = {"current_price": 10.0}  # nothing else
    prices = {"closes": [10.0], "atr": None, "ma200": None, "spy_1y": None, "book_1y": None}
    card = build_evidence_card("X", info=info, prices=prices,
                               panel=AnalystPanel(0, None, None, None, None, "2026-06-14", "yfinance", True),
                               earnings=None, peers=[])
    colors = {s.dimension: s.color for s in card.signals}
    assert colors["Earnings"] is RagColor.GAP
    assert colors["Analysts"] is RagColor.GAP
    assert colors["Technicals"] is RagColor.GAP
```

- [ ] **Step 2: Run fail** → `pytest tests/application/test_evidence_card.py -v` FAIL (ImportError)

- [ ] **Step 3: Implement**

```python
# application/evidence_card.py
"""Assemble the 5 RAG signals + sparkline for one ticker. Composes domain + adapters."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from adapters.data.earnings_history_adapter import EarningsHistory
from application.analyst_panel import AnalystPanel
from domain.evidence_rag import (
    DIMENSIONS,
    RagSignal,
    classify_analysts,
    classify_earnings,
    classify_financials,
    classify_technicals,
    classify_valuation,
)
from domain.peer_relative import sector_percentile


@dataclass(frozen=True)
class EvidenceCard:
    ticker: str
    signals: tuple[RagSignal, ...]   # length 5, DIMENSIONS order
    sparkline: tuple[float, ...]     # realized closes (~90d), no projection


def build_evidence_card(
    ticker: str, *, info: dict[str, Any], prices: dict[str, Any],
    panel: AnalystPanel, earnings: EarningsHistory | None, peers: list[float | None],
) -> EvidenceCard:
    cur = info.get("current_price")
    atr = prices.get("atr")
    ma200 = prices.get("ma200")
    atr_vs_200d = None
    if atr and ma200 and cur is not None and atr != 0:
        atr_vs_200d = (cur - ma200) / atr
    technicals = classify_technicals(atr_vs_200d, prices.get("book_1y"))

    pe = info.get("trailing_pe")
    pct = sector_percentile(pe, peers) if pe is not None and peers else None
    valuation = classify_valuation(info.get("peg_ratio"), pe, pct)

    fcf = info.get("free_cashflow")
    financials = classify_financials(
        None if fcf is None else fcf > 0, info.get("debt_to_equity"),
        None,  # margins_stable: left None until a margin-trend source exists (honest GAP contributor)
    )

    earnings_sig = classify_earnings(
        earnings.beats if earnings else None, earnings.total if earnings else None
    )

    analysts = classify_analysts(
        panel.count, panel.target_mean, panel.target_high, panel.target_low, panel.data_gap, cur
    )

    by_name = {s.dimension: s for s in (technicals, valuation, financials, earnings_sig, analysts)}
    signals = tuple(by_name[d] for d in DIMENSIONS)

    closes = prices.get("closes") or []
    sparkline = tuple(float(c) for c in closes[-90:])
    return EvidenceCard(ticker=ticker, signals=signals, sparkline=sparkline)
```

- [ ] **Step 4: Run pass** → `pytest tests/application/test_evidence_card.py -v` PASS (2)

- [ ] **Step 5: Commit**

```bash
git add application/evidence_card.py tests/application/test_evidence_card.py
git commit -m "feat(evidence): EvidenceCard assembler (5 fixed-order RAG signals + sparkline)"
```

---

### Task 10: Honesty source-scan + full S1 verify

**Files:** Test `tests/domain/test_evidence_rag.py` (add scan).

- [ ] **Step 1: Add forbidden-word source scan**

```python
import inspect
import domain.evidence_rag as _rag
import application.evidence_card as _card
from domain.fit import FORBIDDEN_WORDS


def test_no_forbidden_words_in_evidence_sources():
    for mod in (_rag, _card):
        src = inspect.getsource(mod).lower()
        for w in FORBIDDEN_WORDS:
            assert w not in src, f"forbidden word {w!r} in {mod.__name__}"
```

> If a forbidden word appears (e.g. a comment), reword it. `winner`/`buy`/`sell`/`predict`/`alpha`/`outperform`/`conviction` must not appear in source.

- [ ] **Step 2: Run the scan** → `pytest tests/domain/test_evidence_rag.py -k forbidden -v` (fix wording until PASS)

- [ ] **Step 3: Full S1 typecheck + tests**

Run:
```bash
mypy domain/evidence_rag.py application/evidence_card.py adapters/data/earnings_history_adapter.py
pytest tests/domain/test_evidence_rag.py tests/adapters/test_earnings_history_adapter.py tests/application/test_evidence_card.py -v
```
Expected: mypy `Success`; all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/domain/test_evidence_rag.py
git commit -m "test(evidence): forbidden-word source scan for S1 modules"
```

---

## Self-Review (run before handing off S1)

1. **Spec coverage (§3):** 5 dimensions ✓ (Tasks 2–6); fixed order ✓ (Task 1, asserted Task 9); earnings fetcher net-new ✓ (Task 8); DATA-GAP not fabricated ✓ (every classify_* + Task 9); reuses peer_relative/analyst_panel ✓ (Task 9); RAG-good/bad color language is in the detail strings ✓.
2. **Placeholder scan:** none — every step has complete code/commands.
3. **Type consistency:** `classify_analysts` uses the **scalar signature** everywhere (Task 6 Step 4 + Task 9). `EarningsHistory.beats/total` consistent across Tasks 8–9. `EvidenceCard.signals` length-5 fixed-order consistent.
4. **Hexagonal purity:** `domain/evidence_rag.py` imports only stdlib (no `application`/`adapters`) — enforced by the scalar `classify_analysts` signature. `application/evidence_card.py` may import domain + adapters. ✓

**Downstream contract for S3/S4/S5:** they consume `EvidenceCard` (`.signals` 5×`RagSignal{dimension,color,detail}`, `.sparkline`). S5 wraps `fetch_earnings_history` + `build_evidence_card` inputs in `@st.cache_data`.
