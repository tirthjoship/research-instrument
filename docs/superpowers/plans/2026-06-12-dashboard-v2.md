# Dashboard v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Premium-light-terminal redesign of the dashboard: 6-tab IA, verdict-first Home, upload-your-list fit scoreboard, evidence snowflake, Trust trophy wall, glossary-as-tooltips.

**Architecture:** Hexagonal unchanged — tabs render; the one new compute path is `application/batch_fit_use_case.py` reusing the ADR-054 fit machinery per ticker. New pure UI builders live in `components/` (glossary, snowflake, scorecard). Spec: `docs/superpowers/specs/2026-06-12-dashboard-v2-design.md`.

**Tech Stack:** Python 3.12, Streamlit 1.58 + Plotly, pytest (+ existing vocabulary-guard pattern from `domain/fit.py FORBIDDEN_WORDS`), pre-commit black/isort/mypy-strict/ruff — NEVER `--no-verify`; if a hook reformats, re-add and commit again.

**Branch:** `feat/dashboard-v2` (exists, spec committed). Never commit to develop/main.

---

## PRECONDITIONS

1. On `feat/dashboard-v2`, up to date with develop (yfinance fix merged).
2. Baseline `python -m pytest tests/ -q 2>&1 | tail -2` → 1593 passed. No new failures allowed.
3. Venv: `source ../../.venv/bin/activate` from repo root; `python -c "import streamlit, plotly"` ok.

## File map

| File | Role |
|---|---|
| `components/styles.py` (modify) | v2 tokens, card hover, `.section-chip`, `.tip` tooltip |
| `components/glossary.py` (create) | GLOSSARY dict (single source) + `tip()` helper |
| `components/snowflake.py` (create) | pure Plotly radar builder from axis dict |
| `components/scorecard.py` (create) | ranked batch-fit row renderer |
| `application/batch_fit_use_case.py` (create) | parse tickers/CSV, run fit per name |
| `tabs/weekly_brief.py` (rebuild render) | Home |
| `tabs/research_candidates.py` (extend) | Screener: history + upload scoreboard |
| `adapters/visualization/data_loader.py` (extend) | `load_screen_history()` |
| `tabs/stock_analysis.py` (extend) | section chips, snowflake, peer lines |
| `tabs/falsification_lab.py` → `tabs/trust.py` (rename+extend) | Trust |
| `tabs/methodology.py` (DELETE) | absorbed into Trust + glossary |
| `dashboard.py` (modify) | 6-tab router |

---

### Task 1: Theme foundation — tokens, hover, chips, tooltips, glossary module

**Files:**
- Modify: `adapters/visualization/components/styles.py`
- Create: `adapters/visualization/components/glossary.py`
- Test: `tests/test_glossary_component.py` (create)

- [ ] **Step 1: Failing test** — create `tests/test_glossary_component.py`:

```python
"""Glossary single-source + tooltip helper."""


def test_glossary_has_core_terms():
    from adapters.visualization.components.glossary import GLOSSARY

    for term in (
        "Confidence interval (CI)", "Slippage", "Tercile", "Abnormal return",
        "IC (information coefficient)", "Sharpe ratio", "Bootstrap",
        "Pre-registration", "Look-ahead bias",
    ):
        assert term in GLOSSARY
        assert len(GLOSSARY[term]) > 20  # real definition, not a stub


def test_tip_wraps_text_with_definition():
    from adapters.visualization.components.glossary import tip

    html = tip("Sharpe ratio")
    assert 'class="tip"' in html
    assert "Sharpe ratio" in html
    assert "data-tip=" in html


def test_tip_unknown_term_returns_plain_text():
    from adapters.visualization.components.glossary import tip

    assert tip("Nonsense Term") == "Nonsense Term"
```

- [ ] **Step 2: Run to verify failure** — `python -m pytest tests/test_glossary_component.py -q` → ModuleNotFoundError.

- [ ] **Step 3: Create `adapters/visualization/components/glossary.py`:**

```python
"""Single source of truth for plain-English term definitions.

Feeds (a) the .tip hover tooltips used across tabs, (b) the Trust tab's
reference table. Definitions mirror README.md's glossary — keep in sync.
"""

from __future__ import annotations

import html

GLOSSARY: dict[str, str] = {
    "Confidence interval (CI)": (
        'The range the true average plausibly sits in. "CI low > 0" = even '
        "the pessimistic read is a profit."
    ),
    "Slippage": (
        "The hidden cost of actually buying a thinly-traded stock — you move "
        "the price against yourself."
    ),
    "Tercile": (
        'Split into thirds. "Bottom liquidity tercile" = the third of stocks '
        "that are hardest to trade."
    ),
    "Abnormal return": (
        "A stock's return minus what a comparable index did over the same "
        'days — the part the stock did "on its own."'
    ),
    "IC (information coefficient)": (
        "Correlation between a signal's ranking and what actually happened "
        "next. Zero = the signal knows nothing."
    ),
    "Sharpe ratio": (
        "Return earned per unit of risk taken. Higher is better — it rewards "
        "steady gains, not lucky volatile ones."
    ),
    "Bootstrap": (
        "Re-running a test on thousands of resampled versions of the data to "
        'see how much of the result is just luck. A confidence interval that '
        '"spans zero" means the edge could easily be nothing.'
    ),
    "Pre-registration": (
        "Locking the test rules before seeing results, so you can't move the "
        "goalposts."
    ),
    "Look-ahead bias": (
        "Accidentally letting future data leak into a prediction — makes "
        "backtests look great and live trading fail."
    ),
    "Systematic share": (
        "How much of your book's movement is explained by broad market "
        "forces rather than your individual stock picks."
    ),
    "Beta": (
        "How much a stock (or your whole book) moves when the market moves. "
        "+1.00 = exactly with the market."
    ),
    "Evidence grade": (
        "Where a stock ranks on present-day facts (valuation, quality, "
        "health) versus the screened universe. A description, not a forecast."
    ),
}


def tip(term: str) -> str:
    """Wrap *term* in a hover-tooltip span if a definition exists."""
    definition = GLOSSARY.get(term)
    if definition is None:
        return term
    return (
        f'<span class="tip" data-tip="{html.escape(definition, quote=True)}">'
        f"{html.escape(term)}</span>"
    )
```

- [ ] **Step 4: styles.py token upgrade.** In `adapters/visualization/components/styles.py`:

(a) In the `:root` block, change/add (keep existing var NAMES that other CSS references — change VALUES; verify each name exists first with grep, add if missing):

```css
    --bg-page: #FAFAF8;
    --bg-primary: #FFFFFF;
    --text-primary: #1A1D27;
    --text-secondary: #5C6370;
    --accent: #1D4ED8;
    --success: #15803D;
    --warning: #B45309;
    --danger: #B91C1C;
    --radius-md: 12px;
    --shadow-sm: 0 1px 2px rgba(16,24,40,.06), 0 4px 12px rgba(16,24,40,.04);
```

(b) Page background + tabular numerals — add near the top-level styles:

```css
.stApp { background: var(--bg-page); }
[data-testid="stMetricValue"], .ws-card, .verdict-card, table {
    font-variant-numeric: tabular-nums;
}
```

(c) Upgrade `.ws-card` hover (find the existing `.ws-card` rule; ADD transition + hover):

```css
.ws-card {
    transition: box-shadow .15s ease, border-color .15s ease,
                transform .15s ease;
}
.ws-card:hover {
    box-shadow: 0 2px 4px rgba(16,24,40,.08), 0 8px 24px rgba(16,24,40,.08);
    border-color: rgba(29,78,216,.35);
    transform: translateY(-1px);
}
```

(d) New classes at the end of the CSS string:

```css
.section-chip {
    display: inline-flex; align-items: center; justify-content: center;
    width: 22px; height: 22px; border-radius: 50%;
    background: var(--accent); color: #fff;
    font-size: 12px; font-weight: 700; margin-right: 8px;
}
.tip {
    border-bottom: 1px dotted var(--text-secondary);
    cursor: help; position: relative;
}
.tip:hover::after {
    content: attr(data-tip);
    position: absolute; left: 0; bottom: 125%;
    background: #1A1D27; color: #fff; padding: 8px 12px;
    border-radius: 8px; font-size: 12px; line-height: 1.4;
    width: 260px; z-index: 99; white-space: normal;
}
.hero-gradient {
    background: linear-gradient(135deg, #FFFFFF 0%, #EEF2FF 100%);
}
```

- [ ] **Step 5: Run** — `python -m pytest tests/test_glossary_component.py tests/ -q -k "glossary or styles or phase5" 2>&1 | tail -3` green; `mypy adapters/visualization/components/glossary.py` clean.

- [ ] **Step 6: Commit**

```bash
git add adapters/visualization/components/styles.py adapters/visualization/components/glossary.py tests/test_glossary_component.py
git commit -m "feat: v2 theme tokens, card hover, section chips, tooltip CSS, glossary module"
```

---

### Task 2: Pure builders — snowflake + scorecard

**Files:**
- Create: `adapters/visualization/components/snowflake.py`
- Create: `adapters/visualization/components/scorecard.py`
- Test: `tests/test_snowflake.py`, `tests/test_scorecard.py` (create)

- [ ] **Step 1: Failing tests** — `tests/test_snowflake.py`:

```python
def test_snowflake_builds_figure_with_axes():
    from adapters.visualization.components.snowflake import build_snowflake

    fig = build_snowflake({"Valuation": 80, "Quality": 60, "Trend": 40})
    assert fig is not None
    trace = fig.data[0]
    # closed polygon: first axis repeated at the end
    assert list(trace.theta) == ["Valuation", "Quality", "Trend", "Valuation"]
    assert list(trace.r) == [80, 60, 40, 80]


def test_snowflake_needs_three_axes():
    from adapters.visualization.components.snowflake import build_snowflake

    assert build_snowflake({"Valuation": 80, "Quality": 60}) is None


def test_snowflake_clamps_to_0_100():
    from adapters.visualization.components.snowflake import build_snowflake

    fig = build_snowflake({"A": 150, "B": -10, "C": 50})
    assert list(fig.data[0].r) == [100, 0, 50, 100]
```

`tests/test_scorecard.py`:

```python
from domain.fit import FitFlag, FitVerdict


def _row(ticker, grade, flags=()):
    from application.batch_fit_use_case import BatchFitRow

    return BatchFitRow(
        ticker=ticker,
        verdict=FitVerdict(
            ticker=ticker, evidence_grade=grade, fit_flags=tuple(flags),
            summary=f"{ticker} summary.",
        ),
        fetch_ok=True,
    )


def test_scorecard_ranks_strong_first():
    from adapters.visualization.components.scorecard import rank_rows

    rows = [_row("AAA", "WEAK"), _row("BBB", "STRONG"), _row("CCC", "MODERATE")]
    ranked = rank_rows(rows)
    assert [r.ticker for r in ranked] == ["BBB", "CCC", "AAA"]


def test_scorecard_render_no_raise():
    from adapters.visualization.components.scorecard import render_scorecard

    render_scorecard([_row("NVDA", "STRONG",
                           [FitFlag("BETA_AMPLIFY", "deepens market bet", "WARNING")])])


def test_scorecard_source_has_no_forbidden_words():
    import inspect

    from adapters.visualization.components import scorecard
    from domain.fit import FORBIDDEN_WORDS

    src = inspect.getsource(scorecard).lower()
    for word in FORBIDDEN_WORDS:
        assert word not in src, f"forbidden word {word!r} in scorecard source"
```

- [ ] **Step 2: Verify failure** — both files fail on import.

- [ ] **Step 3: Create `components/snowflake.py`:**

```python
"""Evidence snowflake — descriptive Plotly radar. Factual percentiles only.

NOT the falsified conviction radar (deleted in the realignment): every axis is
a present-tense fact (factor percentile, trend state, book-fit arithmetic).
"""

from __future__ import annotations

import plotly.graph_objects as go

_MIN_AXES = 3


def build_snowflake(axes: dict[str, float]) -> "go.Figure | None":
    """Radar figure from axis-name -> 0..100 score. None if < 3 axes."""
    if len(axes) < _MIN_AXES:
        return None
    names = list(axes.keys())
    values = [max(0.0, min(100.0, float(v))) for v in axes.values()]
    fig = go.Figure(
        go.Scatterpolar(
            r=values + [values[0]],
            theta=names + [names[0]],
            fill="toself",
            fillcolor="rgba(29,78,216,0.18)",
            line={"color": "#1D4ED8", "width": 2},
        )
    )
    fig.update_layout(
        polar={
            "radialaxis": {"range": [0, 100], "showticklabels": False,
                            "gridcolor": "#E7E5E4"},
            "angularaxis": {"gridcolor": "#E7E5E4",
                             "tickfont": {"size": 12, "color": "#5C6370"}},
            "bgcolor": "rgba(0,0,0,0)",
        },
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        height=320,
        margin={"l": 60, "r": 60, "t": 30, "b": 30},
    )
    return fig
```

- [ ] **Step 4: Create `components/scorecard.py`:**

```python
"""Ranked scorecard rows for the Screener's check-your-own-list feature.

Evidence + fit language only — the vocabulary-guard test scans this module.
"""

from __future__ import annotations

import html
from typing import TYPE_CHECKING, Any, Sequence

import streamlit as st

if TYPE_CHECKING:
    from application.batch_fit_use_case import BatchFitRow

_GRADE_ORDER = {"STRONG": 0, "MODERATE": 1, "WEAK": 2, "UNKNOWN": 3}
_GRADE_COLOR = {
    "STRONG": "#15803D", "MODERATE": "#B45309",
    "WEAK": "#B91C1C", "UNKNOWN": "#5C6370",
}
_FLAG_GLYPH = {
    "BETA_AMPLIFY": "▲", "CONCENTRATION": "◔",
    "TREND_STATE": "◆", "DATA_GAP": "▢",
}


def rank_rows(rows: "Sequence[BatchFitRow]") -> "list[BatchFitRow]":
    return sorted(rows, key=lambda r: _GRADE_ORDER.get(r.verdict.evidence_grade, 9))


def _flag_icons(row: "BatchFitRow") -> str:
    parts = []
    for f in row.verdict.fit_flags:
        glyph = _FLAG_GLYPH.get(f.kind, "·")
        parts.append(
            f'<span class="tip" data-tip="{html.escape(f.message, quote=True)}"'
            f' style="margin-right:6px;">{glyph}</span>'
        )
    return "".join(parts)


def render_scorecard(rows: "Sequence[BatchFitRow]", st_module: Any = st) -> None:
    for i, row in enumerate(rank_rows(rows), start=1):
        grade = row.verdict.evidence_grade
        color = _GRADE_COLOR.get(grade, "#5C6370")
        st_module.markdown(
            f'<div class="ws-card" style="padding:10px 16px;display:flex;'
            f'align-items:center;gap:14px;">'
            f'<span style="color:#5C6370;font-weight:700;">#{i}</span>'
            f'<span style="font-weight:700;font-size:16px;">{row.ticker}</span>'
            f'<span style="background:{color};color:#fff;border-radius:999px;'
            f'padding:2px 10px;font-size:12px;font-weight:700;">{grade}</span>'
            f'<span style="font-size:14px;">{_flag_icons(row)}</span>'
            f'<span style="color:#5C6370;font-size:13px;flex:1;">'
            f"{html.escape(row.verdict.summary)}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
    st_module.caption(
        "Evidence + fit vs your book — this engine makes no trade calls "
        "(see the Trust tab)."
    )
```

- [ ] **Step 5:** Tests still fail on `BatchFitRow` import (Task 3 creates it). To keep this task self-contained, ALSO create the minimal dataclass now — `application/batch_fit_use_case.py`:

```python
"""Batch fit verdicts for a user-supplied ticker list (Screener upload)."""

from __future__ import annotations

from dataclasses import dataclass

from domain.fit import FitVerdict


@dataclass(frozen=True)
class BatchFitRow:
    ticker: str
    verdict: FitVerdict
    fetch_ok: bool
```

(Task 3 extends this module; do not duplicate the dataclass there.)

- [ ] **Step 6: Run green** — `python -m pytest tests/test_snowflake.py tests/test_scorecard.py -q` → 7 passed; mypy on the three new files clean.

- [ ] **Step 7: Commit**

```bash
git add adapters/visualization/components/snowflake.py adapters/visualization/components/scorecard.py application/batch_fit_use_case.py tests/test_snowflake.py tests/test_scorecard.py
git commit -m "feat: snowflake + scorecard builders, BatchFitRow"
```

---

### Task 3: Batch fit use case — parsing + per-ticker engine

**Files:**
- Modify: `application/batch_fit_use_case.py`
- Test: `tests/test_batch_fit_use_case.py` (create)

- [ ] **Step 1: Failing tests:**

```python
from domain.fit import FitVerdict


def _fake_fit(ticker: str) -> FitVerdict:
    return FitVerdict(ticker=ticker, evidence_grade="MODERATE", fit_flags=(),
                      summary=f"{ticker} ok.")


def test_parse_tickers_text_variants():
    from application.batch_fit_use_case import parse_tickers

    assert parse_tickers("nvda, aapl\nko msft,aapl") == ["NVDA", "AAPL", "KO", "MSFT"]


def test_parse_tickers_rejects_junk_and_caps():
    from application.batch_fit_use_case import MAX_TICKERS, parse_tickers

    out = parse_tickers(",".join(f"T{i}" for i in range(40)) + ", $$bad$$")
    assert len(out) == MAX_TICKERS
    assert all(t.isalnum() or "." in t or "-" in t for t in out)


def test_parse_csv_symbol_column():
    from application.batch_fit_use_case import parse_csv_tickers

    csv_text = "Name,Symbol,Qty\nApple,AAPL,5\nNvidia,NVDA,2\n"
    assert parse_csv_tickers(csv_text) == ["AAPL", "NVDA"]


def test_parse_csv_first_column_fallback():
    from application.batch_fit_use_case import parse_csv_tickers

    csv_text = "ko\nmsft\n"
    assert parse_csv_tickers(csv_text) == ["KO", "MSFT"]


def test_batch_fit_runs_per_ticker_and_survives_failure():
    from application.batch_fit_use_case import batch_fit

    def fit_fn(ticker):
        if ticker == "BAD":
            raise RuntimeError("boom")
        return _fake_fit(ticker)

    rows = batch_fit(["NVDA", "BAD"], fit_fn=fit_fn)
    assert len(rows) == 2
    assert rows[0].fetch_ok and rows[0].verdict.evidence_grade == "MODERATE"
    assert not rows[1].fetch_ok
    assert rows[1].verdict.evidence_grade == "UNKNOWN"
    assert rows[1].verdict.label == "RESEARCH_ONLY"
```

- [ ] **Step 2: Verify failure** — names missing.

- [ ] **Step 3: Extend `application/batch_fit_use_case.py`** (below the dataclass):

```python
import csv
import io
import re
from typing import Callable, Sequence

from loguru import logger

from domain.fit import FitFlag

MAX_TICKERS = 25

_TICKER_RE = re.compile(r"^[A-Z0-9.\-]{1,10}$")


def parse_tickers(text: str) -> list[str]:
    """Comma/whitespace/newline-separated tickers → upper, dedup, capped."""
    out: list[str] = []
    for raw in re.split(r"[,\s]+", text.strip()):
        t = raw.strip().upper()
        if t and _TICKER_RE.match(t) and t not in out:
            out.append(t)
        if len(out) >= MAX_TICKERS:
            break
    return out


def parse_csv_tickers(csv_text: str) -> list[str]:
    """Tickers from a CSV: a Symbol/Ticker column if present, else column 0."""
    reader = csv.reader(io.StringIO(csv_text))
    rows = [r for r in reader if r]
    if not rows:
        return []
    header = [c.strip().lower() for c in rows[0]]
    col = 0
    has_header = False
    for name in ("symbol", "ticker"):
        if name in header:
            col = header.index(name)
            has_header = True
            break
    body = rows[1:] if has_header else rows
    return parse_tickers("\n".join(r[col] for r in body if len(r) > col))


def batch_fit(
    tickers: Sequence[str],
    fit_fn: "Callable[[str], FitVerdict]",
    progress: "Callable[[float, str], None] | None" = None,
) -> list[BatchFitRow]:
    """Run *fit_fn* per ticker; failures become UNKNOWN/DATA_GAP rows."""
    rows: list[BatchFitRow] = []
    n = len(tickers)
    for i, t in enumerate(tickers):
        if progress is not None:
            progress((i + 1) / max(n, 1), t)
        try:
            rows.append(BatchFitRow(ticker=t, verdict=fit_fn(t), fetch_ok=True))
        except Exception as exc:
            logger.warning(f"batch fit failed for {t}: {exc}")
            rows.append(
                BatchFitRow(
                    ticker=t,
                    verdict=FitVerdict(
                        ticker=t,
                        evidence_grade="UNKNOWN",
                        fit_flags=(
                            FitFlag(
                                kind="DATA_GAP",
                                message=f"Could not assess {t} (fetch failed).",
                                severity="INFO",
                            ),
                        ),
                        summary=f"{t} could not be assessed this run.",
                    ),
                    fetch_ok=False,
                )
            )
    return rows


def default_fit_fn(ticker: str) -> "FitVerdict":
    """Production fit_fn: the ADR-054 gather path with live beta."""
    from datetime import datetime, timezone

    from application.fit_use_case import (
        default_beta_fn,
        gather_and_assess,
        market_systematic_share_threshold,
    )

    return gather_and_assess(
        ticker=ticker,
        reports_dir="data/reports",
        summary_path="data/personal/brief_summary.json",
        holdings_path="data/personal/holdings.csv",
        beta_fn=default_beta_fn,
        as_of=datetime.now(timezone.utc),
        systematic_share_threshold=market_systematic_share_threshold(),
    )
```

- [ ] **Step 4: Run green** — `python -m pytest tests/test_batch_fit_use_case.py tests/test_scorecard.py -q` → all pass; mypy clean.

- [ ] **Step 5: Commit**

```bash
git add application/batch_fit_use_case.py tests/test_batch_fit_use_case.py
git commit -m "feat: batch fit use case — ticker/CSV parsing, per-name engine, failure rows"
```

---

### Task 4: Home rebuild (`tabs/weekly_brief.py`)

**Files:**
- Modify: `adapters/visualization/tabs/weekly_brief.py`
- Test: `tests/test_weekly_brief_tab.py` (extend)

- [ ] **Step 1:** Read the current file fully. Keep: loaders, staleness error, abstention info, the grade dataframes + expanders, adherence expander, markdown-brief expander, `_GRADE_COLOR`. REPLACE the top-of-page flow (title/caption/chip strip) with:

```python
def _gauge(share: float) -> "go.Figure":
    import plotly.graph_objects as go

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=share * 100,
            number={"suffix": "%", "font": {"size": 22}},
            gauge={
                "axis": {"range": [0, 100], "visible": False},
                "bar": {"color": "#1D4ED8"},
                "threshold": {
                    "line": {"color": "#B91C1C", "width": 2},
                    "thickness": 0.9,
                    "value": 60,
                },
            },
        )
    )
    fig.update_layout(height=120, margin={"l": 8, "r": 8, "t": 8, "b": 8},
                      paper_bgcolor="rgba(0,0,0,0)")
    return fig
```

and in `render()` after loading `summary`:

```python
    holdings = summary.get("holdings", [])
    attention = [h for h in holdings if h.get("verdict") in ("REDUCE", "TRIM")]
    macro = summary.get("macro") or {}
    share = float(macro.get("systematic_share", 0.0))

    hero_cols = st.columns([3, 1])
    with hero_cols[0]:
        st.markdown(
            f'<div class="ws-card hero-gradient" style="padding:20px 24px;">'
            f'<div style="font-size:13px;color:#5C6370;">YOUR BOOK · '
            f'{summary.get("as_of", "?")} · regime {summary.get("regime", "?")}</div>'
            f'<div style="font-size:26px;font-weight:800;margin-top:4px;">'
            f"{len(attention)} things need attention this week</div>"
            f'<div style="font-size:14px;color:#5C6370;margin-top:4px;">'
            f"{len(holdings)} holdings tracked · "
            f"{share:.0%} of movement is one market-wide bet</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with hero_cols[1]:
        if macro:
            st.plotly_chart(_gauge(share), use_container_width=True)
            st.caption("Systematic share — flag at 60%")
```

Then the **attention row**: top 5 of `attention` as compact cards (reuse the severity left-border pattern: REDUCE → `verdict-negative`, TRIM → `verdict-caution`), each: ticker bold + verdict pill + unrealized % + why. Then a **week strip** of 3 small ws-cards in `st.columns(3)`: screen one-liner (from `load_latest_screen("data/reports")` already imported? — if not imported in this tab, import it; show "U screened · N passed" or "no screen yet"), adherence count (len of `load_adherence_log(...)` rows, "N resolved records"), gate line ("forward gate resolves ~mid-July 2026"). The existing full tables move BELOW these, REDUCE/TRIM dataframe retitled "All attention items"; everything else unchanged.

- [ ] **Step 2: Extend tests** — add to `tests/test_weekly_brief_tab.py`:

```python
def test_render_hero_counts_attention(tmp_path):
    import json

    p = tmp_path / "brief_summary.json"
    p.write_text(json.dumps({
        "as_of": "2026-06-12", "regime": "NEUTRAL", "abstained": True,
        "macro": {"systematic_share": 0.64},
        "holdings": [
            {"ticker": "A", "verdict": "REDUCE", "unrealized_pct": -5.0,
             "trend_state": "broken", "why": "w"},
            {"ticker": "B", "verdict": "HOLD", "unrealized_pct": 2.0,
             "trend_state": "intact", "why": "w"},
        ],
    }))
    from adapters.visualization.tabs import weekly_brief

    weekly_brief.render(path=str(p))  # must not raise
```

- [ ] **Step 3: Run** — `python -m pytest tests/test_weekly_brief_tab.py -q` green; mypy clean.

- [ ] **Step 4: Commit**

```bash
git add adapters/visualization/tabs/weekly_brief.py tests/test_weekly_brief_tab.py
git commit -m "feat: v2 Home — book-health hero, attention cards, week strip"
```

---

### Task 5: Screener — history strip + upload scoreboard

**Files:**
- Modify: `adapters/visualization/data_loader.py` (add `load_screen_history`)
- Modify: `adapters/visualization/tabs/research_candidates.py`
- Test: `tests/test_dashboard_loaders.py`, `tests/test_research_candidates_tab.py` (extend)

- [ ] **Step 1: Failing loader tests** — append to `tests/test_dashboard_loaders.py`:

```python
def test_load_screen_history_sorted_and_excludes_ic(tmp_path):
    import json

    from adapters.visualization.data_loader import load_screen_history

    (tmp_path / "screen_ic_2026-06-08.json").write_text("{}")
    (tmp_path / "screen_2026-06-01.json").write_text(json.dumps(
        {"as_of": "2026-06-01", "universe_size": 500,
         "candidates": [{"ticker": "A"}], "abstained": False}))
    (tmp_path / "screen_2026-06-08.json").write_text(json.dumps(
        {"as_of": "2026-06-08", "universe_size": 512, "candidates": [],
         "abstained": True}))
    hist = load_screen_history(str(tmp_path))
    assert [h["as_of"] for h in hist] == ["2026-06-08", "2026-06-01"]  # newest first
    assert hist[0]["n_candidates"] == 0 and hist[1]["n_candidates"] == 1


def test_load_screen_history_empty(tmp_path):
    from adapters.visualization.data_loader import load_screen_history

    assert load_screen_history(str(tmp_path)) == []
```

- [ ] **Step 2: Implement** in `data_loader.py` (same defensive style as `load_latest_screen`):

```python
def load_screen_history(reports_dir: str = "data/reports") -> list[dict[str, Any]]:
    """All weekly screens, newest first: as_of, universe_size, n_candidates,
    abstained. Excludes screen_ic_*; skips unreadable files."""
    out: list[dict[str, Any]] = []
    for f in sorted(Path(reports_dir).glob("screen_*.json"), reverse=True):
        if f.name.startswith("screen_ic_"):
            continue
        try:
            d = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        out.append(
            {
                "as_of": d.get("as_of", f.stem.replace("screen_", "")),
                "universe_size": d.get("universe_size", 0),
                "n_candidates": len(d.get("candidates", [])),
                "abstained": bool(d.get("abstained", False))
                or not d.get("candidates"),
            }
        )
    return out
```

- [ ] **Step 3: Screener tab.** In `research_candidates.py` `render()`:
(a) After the weekly-screen section (existing), add `st.divider()` then **history strip**: `hist = load_screen_history(reports_dir)`; if hist → `st.markdown("#### Screen history")` + `st.dataframe` of the list (columns: Date, Universe, Passed, Abstained), `hide_index=True`.
(b) Then the **upload section**:

```python
    st.divider()
    st.markdown("#### Check your own list")
    st.markdown(
        '<div style="color:#5C6370;font-size:14px;">Paste tickers or upload a '
        "CSV — each name gets an evidence grade and a fit check against your "
        "book. Capped at 25 names per run (live data fetch per name).</div>",
        unsafe_allow_html=True,
    )
    text = st.text_area("Tickers", placeholder="NVDA, AAPL, KO",
                        label_visibility="collapsed")
    uploaded = st.file_uploader("or upload CSV", type=["csv"])
    if st.button("Run the check", type="primary"):
        from application.batch_fit_use_case import (
            batch_fit, default_fit_fn, parse_csv_tickers, parse_tickers,
        )

        tickers = parse_tickers(text or "")
        if uploaded is not None:
            tickers = (tickers + [
                t for t in parse_csv_tickers(uploaded.getvalue().decode("utf-8",
                                                                        "replace"))
                if t not in tickers
            ])[:25]
        if not tickers:
            st.warning("No valid tickers found — paste e.g. NVDA, AAPL.")
        else:
            key = "batchfit_" + ",".join(tickers)
            if key not in st.session_state:
                bar = st.progress(0.0, text="Starting…")
                rows = batch_fit(
                    tickers, fit_fn=default_fit_fn,
                    progress=lambda frac, t: bar.progress(
                        frac, text=f"Checking {t}…"),
                )
                bar.empty()
                st.session_state[key] = rows
            from adapters.visualization.components.scorecard import (
                render_scorecard,
            )

            render_scorecard(st.session_state[key])
```

- [ ] **Step 4: Tab test** — append to `tests/test_research_candidates_tab.py`:

```python
def test_render_with_history_no_raise(tmp_path):
    import json

    (tmp_path / "screen_2026-06-08.json").write_text(json.dumps(
        {"as_of": "2026-06-08", "universe_size": 512, "candidates": [],
         "abstained": True}))
    from adapters.visualization.tabs import research_candidates

    research_candidates.render(reports_dir=str(tmp_path))
```

- [ ] **Step 5: Run** — `python -m pytest tests/test_dashboard_loaders.py tests/test_research_candidates_tab.py -q` green; mypy both files.

- [ ] **Step 6: Commit**

```bash
git add adapters/visualization/data_loader.py adapters/visualization/tabs/research_candidates.py tests/
git commit -m "feat: v2 Screener — screen history strip + check-your-own-list scoreboard"
```

---

### Task 6: Stock Analysis — chips, snowflake, peer lines

**Files:**
- Modify: `adapters/visualization/tabs/stock_analysis.py`
- Test: `tests/test_fit_card.py` (extend)

- [ ] **Step 1: Section chips.** In `render()`, right after a successful result lookup (before `_render_verdict(result)`), add a chip nav line:

```python
        _SECTIONS = ["Verdict", "Fit", "Valuation", "Growth", "Performance",
                     "Health", "Ownership", "Sentiment", "Supply chain"]
        st.markdown(
            " ".join(
                f'<span class="section-chip">{i}</span>'
                f'<span style="margin-right:14px;font-size:13px;color:#5C6370;">'
                f"{name}</span>"
                for i, name in enumerate(_SECTIONS, start=1)
            ),
            unsafe_allow_html=True,
        )
```

(Visual index, not anchors — Streamlit anchor behavior across versions is flaky; YAGNI.)

- [ ] **Step 2: Snowflake.** Add helper to the tab:

```python
def _snowflake_axes(fit: "FitVerdict | None") -> dict[str, float]:
    """Descriptive axes from the latest screen row + fit verdict. Empty dict
    when the ticker is not in the screen (snowflake hidden)."""
    axes: dict[str, float] = {}
    if fit is None:
        return axes
    screen = load_latest_screen("data/reports")
    if not screen:
        return axes
    cand = next(
        (c for c in screen.get("candidates", []) if c.get("ticker") == fit.ticker),
        None,
    )
    if cand:
        for fs in cand.get("factor_scores", []):
            name = str(fs.get("name", "")).title()
            if name in ("Value", "Quality", "Momentum", "Revision"):
                axes["Valuation" if name == "Value" else name] = (
                    float(fs.get("percentile", 0.0)) * 100
                )
        th = cand.get("trend_health")
        if isinstance(th, (int, float)):
            axes["Trend"] = max(0.0, min(100.0, 50.0 + float(th) * 50.0))
    penalty = sum(
        30.0 if f.severity == "WARNING" else 15.0 if f.severity == "CAUTION" else 0.0
        for f in fit.fit_flags
    )
    axes["Book fit"] = max(0.0, 100.0 - penalty)
    return axes
```

(`load_latest_screen` import: add to the tab's data_loader imports.) Wire inside the result-rendering block, after `_render_fit_card(fit)` — pass the SAME cached fit verdict:

```python
            axes = _snowflake_axes(fit)
            fig = build_snowflake(axes)
            if fig is not None:
                st.markdown("##### Evidence snowflake")
                st.plotly_chart(fig, use_container_width=True)
                st.caption(
                    "Factual percentiles vs the screened universe + fit "
                    "arithmetic — a description of today, not a forecast."
                )
```

(import `build_snowflake` from components.snowflake at top.) NOTE: `fit` is the variable returned by `_ensure_fit_cached` in the existing wiring — reuse it; if it is None, skip the snowflake.

- [ ] **Step 3: Peer one-liners.** Inspect `AnalysisResult` fields (`adapters/visualization/stock_analyzer.py:29-60`) for pairs like `pe_ratio` + `sector_pe` (or similar — verify exact names with grep). Where BOTH exist in the valuation section, add under the existing gauge: `st.caption(f"PE {result.pe_ratio:.0f} vs sector {result.sector_pe:.0f}")` guarded by None-checks. If no sector-comparative fields exist on AnalysisResult, SKIP this step and note it in the report — do NOT add new fetches.

- [ ] **Step 4: Test** — append to `tests/test_fit_card.py`:

```python
def test_snowflake_axes_from_fit_only(tmp_path, monkeypatch):
    from adapters.visualization.tabs import stock_analysis
    from domain.fit import FitFlag, FitVerdict

    monkeypatch.chdir(tmp_path)  # no screen file -> factor axes absent
    fit = FitVerdict(
        ticker="NVDA", evidence_grade="UNKNOWN",
        fit_flags=(FitFlag("BETA_AMPLIFY", "m", "WARNING"),),
        summary="s.",
    )
    axes = stock_analysis._snowflake_axes(fit)
    assert axes == {"Book fit": 70.0}
```

- [ ] **Step 5: Run** — `python -m pytest tests/test_fit_card.py tests/test_phase54_integration.py -q` green; mypy clean.

- [ ] **Step 6: Commit**

```bash
git add adapters/visualization/tabs/stock_analysis.py tests/test_fit_card.py
git commit -m "feat: v2 Stock Analysis — section chips, evidence snowflake, peer context"
```

---

### Task 7: Trust merge + router + methodology deletion

**Files:**
- Rename: `adapters/visualization/tabs/falsification_lab.py` → `adapters/visualization/tabs/trust.py` (`git mv`)
- Delete: `adapters/visualization/tabs/methodology.py`
- Modify: `adapters/visualization/dashboard.py`
- Tests: rename `tests/test_falsification_lab_tab.py` → `tests/test_trust_tab.py` (git mv + retarget imports); fold `tests/test_methodology_tab.py` content in (then delete it)

- [ ] **Step 1:** `git mv adapters/visualization/tabs/falsification_lab.py adapters/visualization/tabs/trust.py` and `git mv tests/test_falsification_lab_tab.py tests/test_trust_tab.py`. Update imports in the moved test (`tabs.falsification_lab` → `tabs.trust`). Grep the repo for remaining `falsification_lab` imports (`grep -rn "falsification_lab" adapters/ application/ tests/ --include="*.py"`) and update each (dashboard.py router import included).

- [ ] **Step 2: Trust page structure** in `trust.py` `render()` — reorder/extend:
1. Keep subheader (retitle "Trust") + subtitle.
2. Keep the intro ws-card.
3. **Trophy grid**: replace the current linear row loop with a 3-column grid: `rows = _SCOREBOARD + [_unit_b_row(report_path)]`, chunk into `st.columns(3)` groups; each cell = ws-card with the verdict pill (existing colors), the question (bold, 14px), the meaning line (existing `_VERDICT_MEANING`), and the per-row `st.expander("evidence trail")` beneath the card text (expander inside the column works).
4. **The four rules** section: port the 4 principle paragraphs + their italic project examples from `methodology.py`'s `_BODY` (copy the text verbatim BEFORE deleting the file) as 4 ws-cards in `st.columns(2)` × 2 rows, each titled with a `.section-chip` number.
5. Keep gate strip + exhibits expander.
6. **Glossary reference** at the bottom: render from `components/glossary.py` GLOSSARY:

```python
    with st.expander("Glossary — every term in plain English"):
        import pandas as pd

        from adapters.visualization.components.glossary import GLOSSARY

        st.dataframe(
            pd.DataFrame(
                [{"Term": k, "Meaning": v} for k, v in GLOSSARY.items()]
            ),
            hide_index=True, use_container_width=True,
        )
```

- [ ] **Step 3:** Delete `adapters/visualization/tabs/methodology.py` and `tests/test_methodology_tab.py` (its render-no-raise is superseded by the trust tests; ADD one test in `test_trust_tab.py`: `def test_render_no_raise_full(...)` calling `trust.render(report_path=..., log_path=...)` with tmp paths — likely exists already post-rename; verify it covers the new sections).

- [ ] **Step 4: Router** — `dashboard.py`: 6 labels `["Home", "Screener", "Risk", "My Portfolio", "Stock Analysis", "Trust"]`; tab0→weekly_brief.render, tab1→research_candidates.render, tab2→risk.render, tab3→positions.render, tab4→stock_analysis.render, tab5→trust.render. Remove the methodology import/withblock. Also grep tests for hardcoded tab-label lists (`grep -rn "Falsification Lab\|Methodology\|Weekly Brief" tests/ --include="*.py"`) — update `tests/test_phase5_tabs.py` (and any other) to the new 6 labels / module names.

- [ ] **Step 5: Full suite** — `python -m pytest tests/ -q 2>&1 | tail -3` — zero failures (this task touches the most test anchors; fix every import fallout, never delete unrelated tests).

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: v2 Trust tab — trophy grid + four rules + glossary; 6-tab router; methodology absorbed"
```

---

### Task 8: Verify live + ship

- [ ] **Step 1:** `python -m pytest tests/ -q 2>&1 | tail -2` green; `pre-commit run --all-files` clean on a pristine tree (`git status --porcelain` empty first — restore any test-regenerated `data/reports/*.json` newline drift with `git checkout data/reports/`).
- [ ] **Step 2:** Dashboard live check on :8501 (running instance hot-reloads; restart if import errors): all 6 tabs click through; Screener: paste "NVDA, AAPL, KO" → 3 ranked rows with pills + hover flags; Home renders hero + gauge against today's `brief_summary.json`.
- [ ] **Step 3:** Update `docs/STATUS.md` (overwrite, ~40 lines): v2 shipped, 6-tab IA, next = wrap close.
- [ ] **Step 4:** Push, PR → develop (body: feedback-driven v2, screenshots welcome), CI green, merge, develop → main release PR, merge, confirm `git rev-list --count origin/main..origin/develop` = 0.

---

## Self-review (vs spec, 2026-06-12)

- **Coverage:** §1→T1, §2→T7 (router), §3→T4, §4→T2+T3+T5, §5→T2+T6, §6→T7, §7 file map → tasks 1–7, §8→T8. Tooltips: `.tip` CSS (T1) + scorecard flag hovers (T2) + glossary feed (T1/T7); `st.metric(help=)` already present on Risk from the UX pass.
- **Placeholders:** Step T6-3 peer lines has an explicit verify-or-skip rule (AnalysisResult field names unverified) — intentional, bounded. No TBDs.
- **Type consistency:** `BatchFitRow(ticker, verdict, fetch_ok)` consistent across T2/T3/T5; `build_snowflake(dict)->Figure|None` consistent T2/T6; `parse_tickers/parse_csv_tickers/batch_fit/default_fit_fn` names match T3 def ↔ T5 import; glossary `GLOSSARY/tip` match T1 def ↔ T7 use.
- **Honesty:** vocabulary-guard tests on scorecard (T2); snowflake labeled descriptive (T2/T6); scoreboard caption + RESEARCH_ONLY framing (T2).
