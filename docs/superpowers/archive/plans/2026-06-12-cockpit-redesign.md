# Cockpit Redesign (Project A1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the six-tab v2 dashboard with a single-scroll family cockpit (danger → your calls → week retro → look-into-next → lookup) plus a stock-detail dialog, on an untouched hexagonal core.

**Architecture:** New greenfield package `adapters/visualization/cockpit/` — one assembler + one renderer module per section. All sections READ existing artifacts (`brief_summary.json`, `screen_<date>.json`, holdings, logs) via `data_loader`/`price_cache`. Exactly ONE write: confirm-and-log to the ADR-048 discipline log (idempotent per week). One new application-level query (diversification lens). Old tab renderers are deleted at cutover; `risk.py` (drill-down) and `trust.py` (Showcase) survive.

**Tech Stack:** Python 3.12, Streamlit (`st.dialog` for the drawer), Plotly (existing components), pytest with the FakeSt headless pattern, mypy strict (NOT on adapters/visualization — but keep types anyway), pre-commit.

**Spec:** `docs/superpowers/specs/2026-06-12-cockpit-redesign-design.md` (VALIDATED 2026-06-12).

---

## Verified facts the plan relies on (do not re-derive)

- `screen_<date>.json` contains the **FULL ranked candidate distribution even when abstained** (`application/cli.py:2591` "JSON gets full dist"; `evidence_screen_use_case.py` `run()` ranks all, `abstained` is an independent thin-coverage flag). Factual top-N is always readable from the artifact.
- `FORBIDDEN_WORDS` (`domain/fit.py:13`): `("buy", "sell", "winner", "conviction", "predict", "alpha", "outperform")`. Source-scan tests use `inspect.getsource(module).lower()` **substring** matching — so cockpit copy/comments must avoid e.g. "buys", "selling", "predictive", "alpha" ANYWHERE in scanned modules. Write "research starting points only", never "not buys".
- `brief_summary.json` (loaded via `data_loader.load_brief_summary`) keys used here: `as_of`, `holdings: [{ticker, verdict, unrealized_pct, trend_state, why}]`, `scorecard: {…, discipline_window, discipline_n, discipline_gate_status}`, `macro: {factors, net_beta_by_factor, systematic_share, idiosyncratic_share, dominant_factor, flags: [kind…], coverage_holdings, total_holdings} | null`, `concentration`.
- Discipline log: `data/personal/discipline_log.jsonl`; `discipline_log.append_assessments(path, rows)` / `read_assessments(path)`. Row schema (matches `cli.py:2152`): `{ticker, verdict, price, trend_health, as_of, quantity, market_value_cad}`.
- Holdings CSV: `application/holdings_reader.read_holdings(path) -> list[Holding]` where `Holding = (ticker, shares, cost_basis, account_type)`; canonical path `data/personal/holdings.csv`.
- Prices: `adapters/visualization/price_cache.fetch_prices(tickers: tuple) -> {ticker: {"price": float, "change_pct": float}}` (TTL-cached).
- Screen JSON candidate dict shape (from `brief_summary`/`ScreenCandidate` serialization): `{ticker, composite, factor_scores: [{name, value, percentile, contribution}], trend_health, why, label}`.
- Router today: `dashboard.py` = flat `st.tabs([...])` with lazy per-tab imports; CSS injected once via `inject_global_css()`.
- Test pattern: per-file `FakeSt` class + `monkeypatch.setattr(module, "st", FakeSt())`, assertions over a `captured_md` list. No conftest.py exists. `adapters/visualization/*` is omitted from the 90% coverage gate (tests still must pass).
- `st.dialog` (Streamlit ≥1.34, current docs verified via context7): `@st.dialog("Title", width="large")` decorator; the decorated function reruns independently; dismiss = click outside / X.

## File structure (end state)

```
adapters/visualization/
  dashboard.py                  # MODIFIED — router: Cockpit (default) | Showcase
  cockpit/
    __init__.py                 # NEW
    cockpit.py                  # NEW — assembler: calls each section in priority order
    _danger.py                  # NEW — section 1: book danger strip + risk drill-down
    _calls.py                   # NEW — section 2: weekly verdict cards + confirm-and-log
    _retro.py                   # NEW — section 3: how the week went
    _discover.py                # NEW — section 4: look-into-next feed
    _lookup.py                  # NEW — section 5: ticker/list lookup
    stock_detail.py             # NEW — st.dialog drawer (fit + snowflake + facts)
  tabs/
    risk.py                     # KEPT — reused as danger drill-down
    trust.py                    # KEPT — Showcase entry
    weekly_brief.py             # DELETED at cutover (Task 8)
    research_candidates.py      # DELETED at cutover
    positions.py                # DELETED at cutover
    stock_analysis.py           # DELETED at cutover
application/
  diversification_query.py      # NEW — pure correlation-to-dominant-factor query
config/tickers/{sp500,nasdaq100}.txt   # MODIFIED — Task 0 clean
tests/cockpit/
  __init__.py, fake_st.py       # NEW — shared headless FakeSt helper
  test_cockpit_assembler.py, test_danger.py, test_calls.py, test_retro.py,
  test_discover.py, test_lookup_detail.py, test_forbidden_scan.py   # NEW
tests/application/test_diversification_query.py                    # NEW
```

Branch: work on `feat/cockpit-redesign` (already checked out). Commit per task. PR to `dev` at the end.

---

### Task 0: Clean the screen universe

**Files:**
- Modify: `config/tickers/sp500.txt`, `config/tickers/nasdaq100.txt`
- Test: `tests/test_ticker_universe.py` (append)

- [ ] **Step 1: Write the failing guard test** (append to `tests/test_ticker_universe.py`)

```python
KNOWN_DELISTED = {"SIVB", "PXD", "SPLK", "WBA"}


def test_universe_files_contain_no_known_delisted_or_foreign_suffix():
    from pathlib import Path

    from application.ticker_universe import load_ticker_universe

    config_dir = Path(__file__).parent.parent / "config" / "tickers"
    universe = load_ticker_universe(
        [config_dir / "sp500.txt", config_dir / "nasdaq100.txt"]
    )
    stale = KNOWN_DELISTED & set(universe)
    assert not stale, f"delisted tickers still in universe files: {sorted(stale)}"
    foreign = [t for t in universe if t.endswith(".TO") or t.endswith(".V")]
    assert not foreign, f"foreign-suffix artifacts in US universe: {foreign}"
```

- [ ] **Step 2: Run it — expect FAIL** (lists the stale tickers)

Run: `pytest tests/test_ticker_universe.py::test_universe_files_contain_no_known_delisted_or_foreign_suffix -v`
Expected: FAIL with `delisted tickers still in universe files: [...]` (or the foreign assert).

- [ ] **Step 3: Remove the offenders from the files**

```bash
for t in SIVB PXD SPLK WBA; do
  sed -i '' "/^${t}$/d" config/tickers/sp500.txt config/tickers/nasdaq100.txt
done
grep -nE '\.(TO|V)$' config/tickers/sp500.txt config/tickers/nasdaq100.txt
# delete any lines the grep prints, e.g.: sed -i '' '/\.TO$/d; /\.V$/d' config/tickers/*.txt
```

- [ ] **Step 4: Run test — expect PASS**

Run: `pytest tests/test_ticker_universe.py -v` — all pass.

- [ ] **Step 5: Commit**

```bash
git add config/tickers/ tests/test_ticker_universe.py
git commit -m "fix: prune delisted + foreign-suffix tickers from screen universe (cockpit Task 0)"
```

---

### Task 1: Shared FakeSt helper + cockpit skeleton + new router

**Files:**
- Create: `tests/cockpit/__init__.py`, `tests/cockpit/fake_st.py`, `tests/cockpit/test_cockpit_assembler.py`
- Create: `adapters/visualization/cockpit/__init__.py`, `adapters/visualization/cockpit/cockpit.py`
- Modify: `adapters/visualization/dashboard.py`

- [ ] **Step 1: Create the shared FakeSt helper** — `tests/cockpit/fake_st.py` (consolidates the inline pattern from `tests/test_research_candidates_tab.py:113`; new tests import it instead of redefining):

```python
"""Headless stand-in for streamlit, shared by cockpit renderer tests."""

from __future__ import annotations

from typing import Any


class FakeCol:
    def __init__(self, sink: list[str]) -> None:
        self._sink = sink

    def __enter__(self) -> "FakeCol":
        return self

    def __exit__(self, *a: object) -> None:
        pass

    def __getattr__(self, name: str) -> Any:
        return getattr(FakeSt(self._sink), name)


class FakeSt:
    """Captures markdown into `sink`; widgets return inert defaults."""

    def __init__(self, sink: list[str]) -> None:
        self.sink = sink
        self.session_state: dict[str, Any] = {}

    def markdown(self, body: object, **k: object) -> None:
        self.sink.append(str(body))

    def caption(self, body: object = "", **k: object) -> None:
        self.sink.append(str(body))

    def dataframe(self, *a: object, **k: object) -> None:
        self.sink.append("DATAFRAME")

    def plotly_chart(self, *a: object, **k: object) -> None:
        self.sink.append("PLOTLY")

    def metric(self, label: object = "", value: object = "", **k: object) -> None:
        self.sink.append(f"METRIC {label} {value}")

    def button(self, *a: object, **k: object) -> bool:
        return False

    def text_input(self, *a: object, **k: object) -> str:
        return ""

    def text_area(self, *a: object, **k: object) -> str:
        return ""

    def file_uploader(self, *a: object, **k: object) -> None:
        return None

    def columns(self, n: object, **k: object) -> list[FakeCol]:
        count = n if isinstance(n, int) else len(n)  # type: ignore[arg-type]
        return [FakeCol(self.sink) for _ in range(count)]

    def expander(self, label: object = "", **k: object) -> FakeCol:
        self.sink.append(f"EXPANDER {label}")
        return FakeCol(self.sink)

    def divider(self) -> None:
        pass

    def subheader(self, body: object = "", **k: object) -> None:
        self.sink.append(str(body))

    def info(self, body: object = "", **k: object) -> None:
        self.sink.append(str(body))

    def warning(self, body: object = "", **k: object) -> None:
        self.sink.append(str(body))

    def error(self, body: object = "", **k: object) -> None:
        self.sink.append(str(body))

    def success(self, body: object = "", **k: object) -> None:
        self.sink.append(str(body))

    def rerun(self) -> None:
        pass

    def dialog(self, title: str, **k: object):  # decorator passthrough
        def deco(fn: Any) -> Any:
            return fn

        return deco
```

Also create empty `tests/cockpit/__init__.py`.

- [ ] **Step 2: Write the failing assembler test** — `tests/cockpit/test_cockpit_assembler.py`:

```python
"""Cockpit assembler renders all five sections in priority order."""

from tests.cockpit.fake_st import FakeSt


def test_cockpit_renders_sections_in_priority_order(monkeypatch, tmp_path):
    from adapters.visualization.cockpit import cockpit

    sink: list[str] = []
    fake = FakeSt(sink)
    # each section module gets the same fake st
    for mod_name in ("_danger", "_calls", "_retro", "_discover", "_lookup"):
        mod = getattr(cockpit, mod_name)
        monkeypatch.setattr(mod, "st", fake, raising=False)
    monkeypatch.setattr(cockpit, "st", fake, raising=False)

    cockpit.render(
        summary_path=str(tmp_path / "missing.json"),
        reports_dir=str(tmp_path),
        holdings_path=str(tmp_path / "missing.csv"),
        discipline_log_path=str(tmp_path / "log.jsonl"),
        adherence_log_path=str(tmp_path / "adh.jsonl"),
        history_dir=str(tmp_path / "hist"),
    )

    joined = " ".join(sink)
    # all five anchors present even with NO data (graceful empty states)
    anchors = ["cp-danger", "cp-calls", "cp-retro", "cp-discover", "cp-lookup"]
    positions = [joined.find(a) for a in anchors]
    assert all(p >= 0 for p in positions), f"missing section anchors: {positions}"
    assert positions == sorted(positions), "sections out of priority order"
```

- [ ] **Step 3: Run — expect FAIL** (`ModuleNotFoundError: adapters.visualization.cockpit`)

Run: `pytest tests/cockpit/test_cockpit_assembler.py -v`

- [ ] **Step 4: Create the package.** `adapters/visualization/cockpit/__init__.py` (empty). `adapters/visualization/cockpit/cockpit.py`:

```python
"""Cockpit assembler — single-scroll family surface, strict priority order.

Sections render top-to-bottom: danger, your calls, week retro, look-into-next,
lookup. Each section degrades gracefully when its artifact is missing.
"""

from __future__ import annotations

import streamlit as st

from adapters.visualization.cockpit import (  # noqa: F401  (re-exported for tests)
    _calls,
    _danger,
    _discover,
    _lookup,
    _retro,
)

SUMMARY_PATH = "data/personal/brief_summary.json"
REPORTS_DIR = "data/reports"
HOLDINGS_PATH = "data/personal/holdings.csv"
DISCIPLINE_LOG_PATH = "data/personal/discipline_log.jsonl"
ADHERENCE_LOG_PATH = "data/personal/adherence_log.jsonl"
HISTORY_DIR = "data/personal/brief_history"


def render(
    summary_path: str = SUMMARY_PATH,
    reports_dir: str = REPORTS_DIR,
    holdings_path: str = HOLDINGS_PATH,
    discipline_log_path: str = DISCIPLINE_LOG_PATH,
    adherence_log_path: str = ADHERENCE_LOG_PATH,
    history_dir: str = HISTORY_DIR,
) -> None:
    st.markdown('<div id="cp-danger"></div>', unsafe_allow_html=True)
    _danger.render(summary_path=summary_path, discipline_log_path=discipline_log_path)

    st.markdown('<div id="cp-calls"></div>', unsafe_allow_html=True)
    _calls.render(
        summary_path=summary_path,
        holdings_path=holdings_path,
        discipline_log_path=discipline_log_path,
        history_dir=history_dir,
    )

    st.markdown('<div id="cp-retro"></div>', unsafe_allow_html=True)
    _retro.render(
        summary_path=summary_path,
        holdings_path=holdings_path,
        adherence_log_path=adherence_log_path,
        history_dir=history_dir,
    )

    st.markdown('<div id="cp-discover"></div>', unsafe_allow_html=True)
    _discover.render(
        summary_path=summary_path,
        reports_dir=reports_dir,
        holdings_path=holdings_path,
    )

    st.markdown('<div id="cp-lookup"></div>', unsafe_allow_html=True)
    _lookup.render(reports_dir=reports_dir, summary_path=summary_path)
```

Create the five section modules as graceful stubs that the later tasks fill in. Each starts as (example `_danger.py`; same shape for `_calls.py`, `_retro.py`, `_discover.py`, `_lookup.py` with their `render(...)` signatures from the assembler above):

```python
"""Section 1 — book danger strip."""

from __future__ import annotations

import streamlit as st


def render(*, summary_path: str, discipline_log_path: str) -> None:
    st.caption("Section pending build.")
```

- [ ] **Step 5: Run — expect PASS**

Run: `pytest tests/cockpit/test_cockpit_assembler.py -v` — PASS.

- [ ] **Step 6: Swap the router.** Replace the six-tab block in `adapters/visualization/dashboard.py` (lines 23–58) with:

```python
tab_cockpit, tab_showcase = st.tabs(["Cockpit", "Showcase"])

with tab_cockpit:
    from adapters.visualization.cockpit.cockpit import render as render_cockpit

    render_cockpit()
with tab_showcase:
    # Methodology / falsification story — intact until the A2 showcase ships.
    from adapters.visualization.tabs.trust import render as render_trust

    render_trust()
```

Keep `st.set_page_config`, `inject_global_css()`, and the footer unchanged.

- [ ] **Step 7: Smoke-run the app** (manual check, then stop it):

Run: `streamlit run adapters/visualization/dashboard.py --server.headless true` — loads with two tabs, five pending sections, no traceback. Ctrl-C.

- [ ] **Step 8: Commit**

```bash
git add adapters/visualization/cockpit tests/cockpit adapters/visualization/dashboard.py
git commit -m "feat: cockpit skeleton + two-surface router (Cockpit | Showcase)"
```

---

### Task 2: Danger strip (`_danger.py`)

**Files:**
- Modify: `adapters/visualization/cockpit/_danger.py`
- Test: `tests/cockpit/test_danger.py`

- [ ] **Step 1: Write the failing tests** — `tests/cockpit/test_danger.py`:

```python
import json

from tests.cockpit.fake_st import FakeSt

SUMMARY = {
    "as_of": "2026-06-12",
    "holdings": [],
    "concentration": [],
    "scorecard": {
        "discipline_window": "2026-04-15..2026-07-15",
        "discipline_n": 7,
        "discipline_gate_status": "ACCRUING",
    },
    "macro": {
        "factors": ["SPY", "TLT"],
        "net_beta_by_factor": {"SPY": 1.37, "TLT": -0.2},
        "systematic_share": 0.64,
        "idiosyncratic_share": 0.36,
        "dominant_factor": "SPY",
        "flags": ["FACTOR_DOMINANCE"],
        "coverage_holdings": 5,
        "total_holdings": 5,
    },
}


def _render(monkeypatch, tmp_path, summary):
    from adapters.visualization.cockpit import _danger

    sink: list[str] = []
    monkeypatch.setattr(_danger, "st", FakeSt(sink))
    p = tmp_path / "brief_summary.json"
    if summary is not None:
        p.write_text(json.dumps(summary))
    log = tmp_path / "log.jsonl"
    _danger.render(summary_path=str(p), discipline_log_path=str(log))
    return " ".join(sink)


def test_danger_shows_dominant_bet_and_gate(monkeypatch, tmp_path):
    out = _render(monkeypatch, tmp_path, SUMMARY)
    assert "64%" in out          # systematic share
    assert "SPY" in out and "1.37" in out
    assert "ACCRUING" in out     # gate status
    assert "EXPANDER" in out     # risk drill-down reachable


def test_danger_degrades_without_summary(monkeypatch, tmp_path):
    out = _render(monkeypatch, tmp_path, None)
    assert "No weekly brief yet" in out
```

- [ ] **Step 2: Run — expect FAIL** (`AssertionError` / stub caption only)

Run: `pytest tests/cockpit/test_danger.py -v`

- [ ] **Step 3: Implement** — `adapters/visualization/cockpit/_danger.py`:

```python
"""Section 1 — book danger strip. Red only when real; tap opens risk drill-down."""

from __future__ import annotations

import streamlit as st

from adapters.visualization.data_loader import load_brief_summary


def render(*, summary_path: str, discipline_log_path: str) -> None:
    summary = load_brief_summary(summary_path)
    if summary is None:
        st.info("No weekly brief yet — run the weekly brief CLI to populate the cockpit.")
        return

    macro = summary.get("macro")
    score = summary.get("scorecard", {})
    bits: list[str] = []
    danger = False
    if macro:
        share = macro.get("systematic_share")
        dom = macro.get("dominant_factor")
        beta = (macro.get("net_beta_by_factor") or {}).get(dom or "", None)
        if share is not None and dom:
            pct = f"{share:.0%}"
            beta_txt = f" · {dom} β {beta:.2f}" if beta is not None else ""
            bits.append(f"{pct} one macro bet ({dom}){beta_txt}")
            danger = danger or bool(macro.get("flags"))
    gate = score.get("discipline_gate_status")
    if gate:
        bits.append(
            f"Discipline gate {gate} · n={score.get('discipline_n', 0)}"
            f" · window {score.get('discipline_window', '—')}"
        )

    color = "var(--danger)" if danger else "var(--text-secondary)"
    st.markdown(
        '<div class="ws-card" style="padding:10px 16px;">'
        f'<span style="font-weight:700;color:{color};">Book danger</span> — '
        + " · ".join(bits)
        + "</div>",
        unsafe_allow_html=True,
    )

    with st.expander("Risk drill-down"):
        from adapters.visualization.tabs.risk import render as render_risk

        render_risk(path=summary_path)
```

- [ ] **Step 4: Run — expect PASS.** `pytest tests/cockpit/test_danger.py tests/cockpit/test_cockpit_assembler.py -v`

Note: the drill-down test only asserts the expander exists; `risk.render` runs lazily inside the real app (FakeSt's expander never executes it — the lazy import sits inside the `with`, which FakeCol enters without calling `render_risk`? It DOES call it — the import + call run inside the expander block regardless). If `risk.render` explodes under FakeSt, monkeypatch it in the test:
`monkeypatch.setattr("adapters.visualization.tabs.risk.render", lambda **k: None)`.

- [ ] **Step 5: Commit**

```bash
git add adapters/visualization/cockpit/_danger.py tests/cockpit/test_danger.py
git commit -m "feat: cockpit danger strip with risk drill-down"
```

---

### Task 3: Your calls + confirm-and-log (`_calls.py`) — the ONE write

**Files:**
- Modify: `adapters/visualization/cockpit/_calls.py`
- Test: `tests/cockpit/test_calls.py`

The write must be idempotent per `as_of`: if `read_assessments` already holds rows with this brief's `as_of`, render "logged" state instead of the button. Confirming also snapshots the brief summary into `history_dir` for Task 4's retro.

- [ ] **Step 1: Write the failing tests** — `tests/cockpit/test_calls.py`:

```python
import json

from tests.cockpit.fake_st import FakeSt

SUMMARY = {
    "as_of": "2026-06-12T00:00:00",
    "holdings": [
        {"ticker": "ARKK", "verdict": "REDUCE", "unrealized_pct": -12.0,
         "trend_state": "broken", "why": "trend broken, momentum negative"},
        {"ticker": "AAPL", "verdict": "HOLD", "unrealized_pct": 8.0,
         "trend_state": "uptrend", "why": "intact uptrend"},
    ],
}

HOLDINGS_CSV = "Symbol,Quantity,Average Cost,Account Type,Exchange\nARKK,10,50,TFSA,NYSE\nAAPL,5,150,TFSA,NASDAQ\n"


def _setup(tmp_path):
    sp = tmp_path / "brief_summary.json"
    sp.write_text(json.dumps(SUMMARY))
    hp = tmp_path / "holdings.csv"
    hp.write_text(HOLDINGS_CSV)
    return sp, hp, tmp_path / "log.jsonl", tmp_path / "hist"


def test_calls_render_verdict_cards(monkeypatch, tmp_path):
    from adapters.visualization.cockpit import _calls

    sink: list[str] = []
    monkeypatch.setattr(_calls, "st", FakeSt(sink))
    sp, hp, lp, hist = _setup(tmp_path)
    _calls.render(summary_path=str(sp), holdings_path=str(hp),
                  discipline_log_path=str(lp), history_dir=str(hist))
    out = " ".join(sink)
    assert "ARKK" in out and "REDUCE" in out and "trend broken" in out
    assert "AAPL" in out and "HOLD" in out


def test_confirm_writes_log_once_and_snapshots(monkeypatch, tmp_path):
    from adapters.visualization.cockpit import _calls
    from application.discipline_log import read_assessments

    sp, hp, lp, hist = _setup(tmp_path)
    monkeypatch.setattr(
        _calls, "fetch_prices",
        lambda tickers: {t: {"price": 100.0, "change_pct": 0.0} for t in tickers},
    )
    _calls.confirm_and_log(
        summary=json.loads(sp.read_text()), holdings_path=str(hp),
        discipline_log_path=str(lp), history_dir=str(hist),
    )
    rows = read_assessments(str(lp))
    assert {r["ticker"] for r in rows} == {"ARKK", "AAPL"}
    assert rows[0]["as_of"] == "2026-06-12T00:00:00"
    assert rows[0]["quantity"] in (10.0, 5.0)
    assert (hist / "brief_2026-06-12.json").exists()
    # idempotent: second confirm is a no-op
    _calls.confirm_and_log(
        summary=json.loads(sp.read_text()), holdings_path=str(hp),
        discipline_log_path=str(lp), history_dir=str(hist),
    )
    assert len(read_assessments(str(lp))) == 2
```

- [ ] **Step 2: Run — expect FAIL.** `pytest tests/cockpit/test_calls.py -v`

- [ ] **Step 3: Implement** — `adapters/visualization/cockpit/_calls.py`:

```python
"""Section 2 — this week's per-holding calls + the cockpit's single write action.

Replaces the old My Portfolio forms: one confirm step logs the week's verdicts
to the ADR-048 discipline forward gate (idempotent per as_of) and snapshots the
brief for next week's retro strip.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

from adapters.visualization.data_loader import load_brief_summary
from adapters.visualization.price_cache import fetch_prices
from application.discipline_log import append_assessments, read_assessments
from application.holdings_reader import read_holdings

_VERDICT_CLASS = {
    "REDUCE": "verdict-negative",
    "TRIM": "verdict-caution",
    "REVIEW": "verdict-neutral",
    "HOLD": "verdict-neutral",
    "ADD_OK": "verdict-positive",
}


def already_logged(summary: dict[str, Any], discipline_log_path: str) -> bool:
    as_of = summary.get("as_of", "")
    return any(r.get("as_of") == as_of for r in read_assessments(discipline_log_path))


def confirm_and_log(
    *,
    summary: dict[str, Any],
    holdings_path: str,
    discipline_log_path: str,
    history_dir: str,
) -> None:
    if already_logged(summary, discipline_log_path):
        return
    qty = {h.ticker: h.shares for h in _safe_holdings(holdings_path)}
    tickers = tuple(h["ticker"] for h in summary.get("holdings", []))
    prices = fetch_prices(tickers) if tickers else {}
    rows: list[dict[str, Any]] = []
    for h in summary.get("holdings", []):
        t = h["ticker"]
        price = float(prices.get(t, {}).get("price") or 0.0)
        q = float(qty.get(t, 0.0))
        rows.append(
            {
                "ticker": t,
                "verdict": h["verdict"],
                "price": price,
                "trend_health": None,
                "as_of": summary.get("as_of", ""),
                "quantity": q,
                "market_value_cad": price * q if price and q else None,
            }
        )
    append_assessments(discipline_log_path, rows)
    hist = Path(history_dir)
    hist.mkdir(parents=True, exist_ok=True)
    stamp = str(summary.get("as_of", ""))[:10]
    (hist / f"brief_{stamp}.json").write_text(json.dumps(summary))


def _safe_holdings(path: str) -> list[Any]:
    try:
        return read_holdings(path)
    except (OSError, ValueError, KeyError):
        return []


def render(
    *,
    summary_path: str,
    holdings_path: str,
    discipline_log_path: str,
    history_dir: str,
) -> None:
    summary = load_brief_summary(summary_path)
    if summary is None or not summary.get("holdings"):
        st.info("No calls this week — the weekly brief has no holdings verdicts.")
        return

    st.subheader("Your calls this week")
    for h in summary["holdings"]:
        cls = _VERDICT_CLASS.get(h["verdict"], "verdict-neutral")
        st.markdown(
            f'<div class="verdict-card {cls}">'
            f'<strong>{h["ticker"]}</strong> — {h["verdict"]} · '
            f'{h.get("unrealized_pct", 0.0):+.1f}% · {h.get("trend_state", "")}'
            f'<br><span style="color:var(--text-secondary);">{h.get("why", "")}</span>'
            "</div>",
            unsafe_allow_html=True,
        )

    if already_logged(summary, discipline_log_path):
        st.success("This week's calls are logged to the discipline gate.")
    elif st.button("Confirm all — log this week's calls", key="cp_confirm_all"):
        confirm_and_log(
            summary=summary,
            holdings_path=holdings_path,
            discipline_log_path=discipline_log_path,
            history_dir=history_dir,
        )
        st.rerun()
```

- [ ] **Step 4: Run — expect PASS.** `pytest tests/cockpit/test_calls.py -v`

- [ ] **Step 5: Commit**

```bash
git add adapters/visualization/cockpit/_calls.py tests/cockpit/test_calls.py
git commit -m "feat: cockpit your-calls section with idempotent confirm-and-log"
```

---

### Task 4: Week retrospective (`_retro.py`)

**Files:**
- Modify: `adapters/visualization/cockpit/_retro.py`
- Modify: `adapters/visualization/price_cache.py` (add `fetch_week_changes`)
- Test: `tests/cockpit/test_retro.py`

- [ ] **Step 1: Add `fetch_week_changes` to `price_cache.py`** (append; follows the module's existing `@st.cache_data` + TTL pattern — copy the decorator form used by `fetch_prices` at `price_cache.py:172`):

```python
@st.cache_data(ttl=_cache_ttl_seconds(), show_spinner=False)
def fetch_week_changes(tickers: tuple[str, ...]) -> dict[str, float]:
    """5-trading-day percent change per ticker. {} entries omitted on fetch failure."""
    out: dict[str, float] = {}
    if not tickers:
        return out
    try:
        import yfinance as yf

        data = yf.download(
            list(tickers), period="7d", interval="1d",
            progress=False, auto_adjust=True,
        )["Close"]
        for t in tickers:
            series = data[t] if len(tickers) > 1 else data
            closes = [float(v) for v in series.dropna().tolist()]
            if len(closes) >= 2:
                out[t] = (closes[-1] - closes[0]) / closes[0] * 100.0
    except Exception:  # noqa: BLE001 — network adapter edge; cockpit degrades
        return out
    return out
```

(If `_cache_ttl_seconds` is named differently in the module, reuse the exact helper `fetch_prices` uses — match the file, don't invent.)

- [ ] **Step 2: Write the failing tests** — `tests/cockpit/test_retro.py`:

```python
import json

from tests.cockpit.fake_st import FakeSt

CUR = {
    "as_of": "2026-06-12T00:00:00",
    "holdings": [
        {"ticker": "ARKK", "verdict": "TRIM", "unrealized_pct": -10.0,
         "trend_state": "broken", "why": "x"},
        {"ticker": "AAPL", "verdict": "HOLD", "unrealized_pct": 9.0,
         "trend_state": "uptrend", "why": "y"},
    ],
}
PREV = {
    "as_of": "2026-06-05T00:00:00",
    "holdings": [
        {"ticker": "ARKK", "verdict": "HOLD", "unrealized_pct": -6.0,
         "trend_state": "uptrend", "why": "x"},
        {"ticker": "AAPL", "verdict": "HOLD", "unrealized_pct": 7.0,
         "trend_state": "uptrend", "why": "y"},
    ],
}

HOLDINGS_CSV = "Symbol,Quantity,Average Cost,Account Type,Exchange\nARKK,10,50,TFSA,NYSE\nAAPL,5,150,TFSA,NASDAQ\n"


def _setup(tmp_path, with_prev):
    sp = tmp_path / "brief_summary.json"
    sp.write_text(json.dumps(CUR))
    hp = tmp_path / "holdings.csv"
    hp.write_text(HOLDINGS_CSV)
    hist = tmp_path / "hist"
    hist.mkdir()
    (hist / "brief_2026-06-12.json").write_text(json.dumps(CUR))
    if with_prev:
        (hist / "brief_2026-06-05.json").write_text(json.dumps(PREV))
    return sp, hp, tmp_path / "adh.jsonl", hist


def _render(monkeypatch, tmp_path, with_prev):
    from adapters.visualization.cockpit import _retro

    sink: list[str] = []
    monkeypatch.setattr(_retro, "st", FakeSt(sink))
    monkeypatch.setattr(
        _retro, "fetch_week_changes",
        lambda tickers: {"ARKK": -3.0, "AAPL": 2.0, "SPY": 1.0},
    )
    sp, hp, ap, hist = _setup(tmp_path, with_prev)
    _retro.render(summary_path=str(sp), holdings_path=str(hp),
                  adherence_log_path=str(ap), history_dir=str(hist))
    return " ".join(sink)


def test_retro_shows_flips_and_book_vs_spy(monkeypatch, tmp_path):
    out = _render(monkeypatch, tmp_path, with_prev=True)
    assert "ARKK" in out and "HOLD" in out and "TRIM" in out  # the flip
    assert "SPY" in out  # factual comparison present


def test_retro_first_week_degrades(monkeypatch, tmp_path):
    out = _render(monkeypatch, tmp_path, with_prev=False)
    assert "first week" in out.lower()
```

- [ ] **Step 3: Run — expect FAIL.** `pytest tests/cockpit/test_retro.py -v`

- [ ] **Step 4: Implement** — `adapters/visualization/cockpit/_retro.py`:

```python
"""Section 3 — how the week went. Descriptive only: factual moves, verdict flips,
adherence. No forecast surface."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

from adapters.visualization.data_loader import load_adherence_log, load_brief_summary
from adapters.visualization.price_cache import fetch_week_changes
from application.holdings_reader import read_holdings


def _two_latest_snapshots(history_dir: str) -> list[dict[str, Any]]:
    files = sorted(Path(history_dir).glob("brief_*.json"))
    return [json.loads(f.read_text()) for f in files[-2:]]


def _verdict_flips(prev: dict[str, Any], cur: dict[str, Any]) -> list[str]:
    prev_v = {h["ticker"]: h["verdict"] for h in prev.get("holdings", [])}
    flips: list[str] = []
    for h in cur.get("holdings", []):
        was = prev_v.get(h["ticker"])
        if was and was != h["verdict"]:
            flips.append(f"{h['ticker']}: {was} → {h['verdict']}")
    return flips


def render(
    *,
    summary_path: str,
    holdings_path: str,
    adherence_log_path: str,
    history_dir: str,
) -> None:
    summary = load_brief_summary(summary_path)
    if summary is None:
        return
    st.subheader("How the week went")

    snaps = _two_latest_snapshots(history_dir)
    if len(snaps) < 2:
        st.caption("First week — nothing to compare yet.")
        return
    prev, cur = snaps[0], snaps[1]

    try:
        holdings = read_holdings(holdings_path)
    except (OSError, ValueError, KeyError):
        holdings = []
    tickers = tuple(h.ticker for h in holdings)
    changes = fetch_week_changes(tickers + ("SPY",)) if tickers else {}
    cols = st.columns(3)
    if changes and tickers:
        weights = {h.ticker: h.shares * h.cost_basis for h in holdings}
        total = sum(weights.values()) or 1.0
        book = sum(changes.get(t, 0.0) * w for t, w in weights.items()) / total
        spy = changes.get("SPY")
        with cols[0]:
            spy_txt = f" vs SPY {spy:+.1f}%" if spy is not None else ""
            st.metric("Book this week (cost-weighted)", f"{book:+.1f}%{spy_txt}")

    flips = _verdict_flips(prev, cur)
    with cols[1]:
        st.markdown(
            "**Verdict flips:** " + ("; ".join(flips) if flips else "none"),
        )

    adherence = load_adherence_log(adherence_log_path)
    with cols[2]:
        if adherence:
            last = adherence[-1]
            st.markdown(
                f"**Last adherence:** {last.get('ticker', '')} "
                f"{last.get('label', '')}"
            )
        else:
            st.markdown("**Last adherence:** no entries yet")
```

- [ ] **Step 5: Run — expect PASS.** `pytest tests/cockpit/test_retro.py -v`

- [ ] **Step 6: Commit**

```bash
git add adapters/visualization/cockpit/_retro.py adapters/visualization/price_cache.py tests/cockpit/test_retro.py
git commit -m "feat: cockpit week retrospective strip (factual, descriptive only)"
```

---

### Task 5: Diversification query (`application/diversification_query.py`)

**Files:**
- Create: `application/diversification_query.py`
- Test: `tests/application/test_diversification_query.py`

Pure application-level composition: given close-price series for candidates and the dominant factor, return candidates ranked by LOWEST |correlation| of daily returns to that factor. No network, no streamlit — caller supplies series (cockpit fetches via yfinance/price_cache).

- [ ] **Step 1: Write the failing tests** — `tests/application/test_diversification_query.py`:

```python
import math


def _series(values):
    return [float(v) for v in values]


def test_ranks_lowest_abs_correlation_first():
    from application.diversification_query import rank_by_diversification

    factor = _series([100, 101, 99, 102, 103, 101, 104])
    mirror = _series([50, 50.5, 49.5, 51, 51.5, 50.5, 52])      # ~corr +1
    inverse = _series([50, 49.5, 50.5, 49, 48.5, 49.5, 48])     # ~corr -1
    flat = _series([50, 50.2, 49.9, 50.1, 50.0, 50.15, 49.95])  # ~corr 0

    ranked = rank_by_diversification(
        factor_series=factor,
        candidate_series={"MIRROR": mirror, "INVERSE": inverse, "FLAT": flat},
    )
    assert ranked[0][0] == "FLAT"
    assert {r[0] for r in ranked} == {"MIRROR", "INVERSE", "FLAT"}
    for _, corr in ranked:
        assert -1.0 <= corr <= 1.0 and not math.isnan(corr)


def test_skips_candidates_with_short_series():
    from application.diversification_query import rank_by_diversification

    factor = _series([100, 101, 99, 102, 103])
    ranked = rank_by_diversification(
        factor_series=factor,
        candidate_series={"SHORT": _series([1, 2]), "OK": _series([5, 6, 5, 7, 6])},
    )
    assert [r[0] for r in ranked] == ["OK"]


def test_empty_inputs_return_empty():
    from application.diversification_query import rank_by_diversification

    assert rank_by_diversification(factor_series=[], candidate_series={}) == []
```

- [ ] **Step 2: Run — expect FAIL** (module missing).

Run: `pytest tests/application/test_diversification_query.py -v`

- [ ] **Step 3: Implement** — `application/diversification_query.py`:

```python
"""Diversification lens: rank candidates by lowest |corr| of daily returns to the
book's dominant macro factor. Pure composition over caller-supplied price series —
point-in-time safety is the caller's responsibility (series end at as_of)."""

from __future__ import annotations

MIN_POINTS = 5  # need >= MIN_POINTS closes -> MIN_POINTS-1 returns


def _returns(closes: list[float]) -> list[float]:
    return [
        (b - a) / a
        for a, b in zip(closes[:-1], closes[1:], strict=False)
        if a != 0.0
    ]


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = min(len(xs), len(ys))
    if n < MIN_POINTS - 1:
        return None
    xs, ys = xs[-n:], ys[-n:]
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx == 0.0 or vy == 0.0:
        return None
    return cov / (vx**0.5 * vy**0.5)


def rank_by_diversification(
    *,
    factor_series: list[float],
    candidate_series: dict[str, list[float]],
) -> list[tuple[str, float]]:
    """Return (ticker, corr) sorted by |corr| ascending — most diversifying first."""
    fr = _returns(factor_series)
    out: list[tuple[str, float]] = []
    for ticker, closes in candidate_series.items():
        corr = _pearson(fr, _returns(closes))
        if corr is not None:
            out.append((ticker, corr))
    return sorted(out, key=lambda r: abs(r[1]))
```

- [ ] **Step 4: Run — expect PASS**, then mypy:

Run: `pytest tests/application/test_diversification_query.py -v && mypy application/diversification_query.py --strict`

- [ ] **Step 5: Commit**

```bash
git add application/diversification_query.py tests/application/test_diversification_query.py
git commit -m "feat: diversification query — rank candidates by low corr to dominant factor"
```

---

### Task 6: Look-into-next feed (`_discover.py`)

**Files:**
- Modify: `adapters/visualization/cockpit/_discover.py`
- Test: `tests/cockpit/test_discover.py`

VOCABULARY WARNING: this module is whole-module FORBIDDEN_WORDS-scanned. No "buy(s)", "sell(ing)", "predict(ive)", "alpha", "winner", "conviction", "outperform" anywhere — including comments and docstrings. The honesty banner reads: *"The screen abstains — it claims no tradeable edge. Rows below are research starting points only."*

- [ ] **Step 1: Write the failing tests** — `tests/cockpit/test_discover.py`:

```python
import inspect
import json

from tests.cockpit.fake_st import FakeSt

SCREEN = {
    "as_of": "2026-06-12",
    "abstained": True,
    "universe_size": 480,
    "candidates": [
        {"ticker": "KO", "composite": 0.8, "trend_health": 0.5,
         "why": "cheap + quality", "factor_scores": []},
        {"ticker": "NVDA", "composite": 0.7, "trend_health": 0.9,
         "why": "momentum", "factor_scores": []},
        {"ticker": "JNJ", "composite": 0.6, "trend_health": 0.4,
         "why": "quality", "factor_scores": []},
        {"ticker": "XOM", "composite": 0.5, "trend_health": 0.2,
         "why": "value", "factor_scores": []},
    ],
}
SUMMARY = {"as_of": "2026-06-12", "holdings": [],
           "macro": {"dominant_factor": "SPY", "systematic_share": 0.64,
                     "net_beta_by_factor": {"SPY": 1.3}, "factors": ["SPY"],
                     "flags": [], "coverage_holdings": 1, "total_holdings": 1,
                     "idiosyncratic_share": 0.36}}


def _render(monkeypatch, tmp_path, screen=SCREEN):
    from adapters.visualization.cockpit import _discover

    sink: list[str] = []
    monkeypatch.setattr(_discover, "st", FakeSt(sink))
    monkeypatch.setattr(
        _discover, "_diversification_ranks",
        lambda cands, dom: [("KO", 0.05), ("JNJ", 0.10), ("XOM", 0.30), ("NVDA", 0.90)],
    )
    (tmp_path / "brief_summary.json").write_text(json.dumps(SUMMARY))
    if screen is not None:
        (tmp_path / "screen_2026-06-12.json").write_text(json.dumps(screen))
    (tmp_path / "holdings.csv").write_text(
        "Symbol,Quantity,Average Cost,Account Type,Exchange\nSPY,1,400,TFSA,NYSE\n"
    )
    _discover.render(
        summary_path=str(tmp_path / "brief_summary.json"),
        reports_dir=str(tmp_path),
        holdings_path=str(tmp_path / "holdings.csv"),
    )
    return " ".join(sink)


def test_feed_shows_on_abstention_with_banner_and_capped_rows(monkeypatch, tmp_path):
    out = _render(monkeypatch, tmp_path)
    assert "research starting points only" in out.lower()
    assert "KO" in out  # most diversifying leads
    assert out.count("cp-row") <= 5  # 3-5 rows cap (validation Q3)


def test_missing_screen_falls_back_gracefully(monkeypatch, tmp_path):
    out = _render(monkeypatch, tmp_path, screen=None)
    assert "no screen artifact" in out.lower()


def test_discover_source_has_no_forbidden_words():
    from adapters.visualization.cockpit import _discover
    from domain.fit import FORBIDDEN_WORDS

    src = inspect.getsource(_discover).lower()
    for word in FORBIDDEN_WORDS:
        assert word not in src, f"forbidden word {word!r} in _discover source"
```

- [ ] **Step 2: Run — expect FAIL.** `pytest tests/cockpit/test_discover.py -v`

- [ ] **Step 3: Implement** — `adapters/visualization/cockpit/_discover.py`:

```python
"""Section 4 — look into next. Diversification-first research feed.

Factual rank (present-day percentiles, pure arithmetic) is split from the
gate verdict, which stays abstaining and is shown as such inside the feed.
"""

from __future__ import annotations

import streamlit as st

from adapters.visualization.data_loader import load_brief_summary, load_latest_screen
from adapters.visualization.price_cache import fetch_week_changes  # noqa: F401
from application.diversification_query import rank_by_diversification
from application.holdings_reader import read_holdings

MAX_ROWS = 5  # validation 2026-06-12 (Q3): research feed stays 3-5 rows
_HISTORY_DAYS = 60


def _diversification_ranks(
    candidates: list[str], dominant: str
) -> list[tuple[str, float]]:
    """Fetch ~60d closes for candidates + dominant factor, rank by low |corr|."""
    try:
        import yfinance as yf

        data = yf.download(
            [*candidates, dominant], period=f"{_HISTORY_DAYS}d", interval="1d",
            progress=False, auto_adjust=True,
        )["Close"]
        series = {
            t: [float(v) for v in data[t].dropna().tolist()] for t in candidates
        }
        factor = [float(v) for v in data[dominant].dropna().tolist()]
    except Exception:  # noqa: BLE001 — degraded state below
        return []
    return rank_by_diversification(factor_series=factor, candidate_series=series)


def render(*, summary_path: str, reports_dir: str, holdings_path: str) -> None:
    st.subheader("Look into next")
    screen = load_latest_screen(reports_dir)
    summary = load_brief_summary(summary_path)
    if screen is None:
        st.info("No screen artifact yet — run the screen CLI; the feed needs it.")
        return

    if screen.get("abstained") or not screen.get("candidates"):
        st.markdown(
            '<div class="ws-card" style="padding:8px 14px;">'
            "The screen abstains — it claims no tradeable edge. "
            "Rows below are research starting points only."
            "</div>",
            unsafe_allow_html=True,
        )
    if not screen.get("candidates"):
        st.caption("Screen artifact holds no ranked names — re-run after Task 0 clean.")
        return

    held = set()
    try:
        held = {h.ticker for h in read_holdings(holdings_path)}
    except (OSError, ValueError, KeyError):
        pass
    ranked = [c for c in screen["candidates"] if c["ticker"] not in held]
    by_ticker = {c["ticker"]: c for c in ranked}

    dominant = ((summary or {}).get("macro") or {}).get("dominant_factor")
    rows: list[tuple[str, str]] = []
    if dominant:
        share = ((summary or {}).get("macro") or {}).get("systematic_share", 0.0)
        for ticker, corr in _diversification_ranks(list(by_ticker), dominant):
            c = by_ticker[ticker]
            rows.append(
                (
                    ticker,
                    f"Low link to your {share:.0%} {dominant} bet"
                    f" (corr {corr:+.2f}) · also screens: {c.get('why', '')}",
                )
            )
            if len(rows) >= MAX_ROWS:
                break
    if not rows:  # lens unavailable -> factual composite order
        for c in ranked[:MAX_ROWS]:
            rows.append((c["ticker"], f"Screens well now: {c.get('why', '')}"))

    for ticker, why in rows:
        st.markdown(
            f'<div class="ws-card cp-row" style="padding:8px 14px;">'
            f"<strong>{ticker}</strong> — {why}</div>",
            unsafe_allow_html=True,
        )
    st.caption("Factual present-day ranks, for research. The gate verdict is above.")
```

- [ ] **Step 4: Run — expect PASS** (incl. the forbidden-words scan — if it trips, the failing word is in your copy/comments; reword).

Run: `pytest tests/cockpit/test_discover.py -v`

- [ ] **Step 5: Commit**

```bash
git add adapters/visualization/cockpit/_discover.py tests/cockpit/test_discover.py
git commit -m "feat: cockpit look-into-next feed — diversification-first, gate shown as abstention"
```

---

### Task 7: Lookup + stock-detail drawer (`_lookup.py`, `stock_detail.py`)

**Files:**
- Create: `adapters/visualization/cockpit/stock_detail.py`
- Modify: `adapters/visualization/cockpit/_lookup.py`
- Test: `tests/cockpit/test_lookup_detail.py`

`stock_detail.py` ports `_render_fit_card` (`tabs/stock_analysis.py:257`), `_ensure_fit_cached` (`:65`) and `_snowflake_axes` (`:675`) VERBATIM (copy the function bodies — they are already FORBIDDEN_WORDS-clean and tested), wrapped in `@st.dialog`. Legacy cruft (score gauges, divergence tables, default tickers) must NOT be ported — port only the three functions named.

- [ ] **Step 1: Write the failing tests** — `tests/cockpit/test_lookup_detail.py`:

```python
import inspect

from tests.cockpit.fake_st import FakeSt


def test_lookup_renders_input_and_batch_path(monkeypatch, tmp_path):
    from adapters.visualization.cockpit import _lookup

    sink: list[str] = []
    monkeypatch.setattr(_lookup, "st", FakeSt(sink))
    _lookup.render(reports_dir=str(tmp_path), summary_path=str(tmp_path / "x.json"))
    out = " ".join(sink)
    assert "Lookup" in out


def test_detail_sections_present(monkeypatch):
    from adapters.visualization.cockpit import stock_detail

    # the drawer body renders fit card + snowflake + facts for a fake verdict
    src = inspect.getsource(stock_detail)
    assert "st.dialog" in src
    assert "_render_fit_card" in src and "_snowflake_axes" in src


def test_stock_detail_source_has_no_forbidden_words():
    from adapters.visualization.cockpit import stock_detail
    from domain.fit import FORBIDDEN_WORDS

    src = inspect.getsource(stock_detail).lower()
    for word in FORBIDDEN_WORDS:
        assert word not in src, f"forbidden word {word!r} in stock_detail source"


def test_lookup_source_has_no_forbidden_words():
    from adapters.visualization.cockpit import _lookup
    from domain.fit import FORBIDDEN_WORDS

    src = inspect.getsource(_lookup).lower()
    for word in FORBIDDEN_WORDS:
        assert word not in src, f"forbidden word {word!r} in _lookup source"
```

- [ ] **Step 2: Run — expect FAIL.** `pytest tests/cockpit/test_lookup_detail.py -v`

- [ ] **Step 3: Implement `stock_detail.py`.** Structure (the three ported functions are copied verbatim from `tabs/stock_analysis.py` — open that file and copy; do not retype from memory):

```python
"""Stock-detail drawer — fit verdict + evidence grade + snowflake + present facts.

Ported intact from tabs/stock_analysis.py: _ensure_fit_cached, _render_fit_card,
_snowflake_axes. Wrapped in st.dialog; opened from any cockpit row or lookup.
"""

from __future__ import annotations

import streamlit as st

from adapters.visualization.components.snowflake import build_snowflake
from adapters.visualization.data_loader import load_latest_screen  # noqa: F401

# === BEGIN verbatim ports from tabs/stock_analysis.py (lines 65, 257, 675) ===
# _ensure_fit_cached(...)   <- copy body exactly
# _render_fit_card(...)     <- copy body exactly
# _snowflake_axes(...)      <- copy body exactly
# === END verbatim ports ===


@st.dialog("Stock detail", width="large")
def open_stock_detail(ticker: str) -> None:
    fit = _ensure_fit_cached(ticker)
    _render_fit_card(fit)
    axes = _snowflake_axes(fit)
    fig = build_snowflake(axes) if axes else None
    if fig is not None:
        st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Evidence + fit only — descriptive present-day facts; "
        "the gate verdict lives on the cockpit."
    )
```

(While porting, resolve the ported functions' imports — `gather_and_assess`, `default_beta_fn`, screen loading — exactly as `stock_analysis.py` does at its top; bring those import lines across too.)

- [ ] **Step 4: Implement `_lookup.py`:**

```python
"""Section 5 — lookup. Ticker or pasted list -> detail drawer / scorecard."""

from __future__ import annotations

import streamlit as st

from adapters.visualization.components.scorecard import render_scorecard
from application.batch_fit_use_case import batch_fit, default_fit_fn, parse_tickers


def render(*, reports_dir: str, summary_path: str) -> None:
    st.subheader("Lookup")
    single = st.text_input("Ticker", key="cp_lookup_ticker", placeholder="e.g. KO")
    if single and st.button("Open detail", key="cp_lookup_open"):
        from adapters.visualization.cockpit.stock_detail import open_stock_detail

        open_stock_detail(single.strip().upper())

    pasted = st.text_area(
        "Or paste a list (comma/newline separated, max 25)", key="cp_lookup_list"
    )
    if pasted and st.button("Check the list", key="cp_lookup_batch"):
        tickers = parse_tickers(pasted)
        if tickers:
            rows = batch_fit(tickers, default_fit_fn())
            render_scorecard(rows)
```

(Check `default_fit_fn`'s exact signature at `application/batch_fit_use_case.py:97` before calling — if it takes config args, pass the production defaults it documents; if it IS the fit function rather than a factory, drop the call parens.)

- [ ] **Step 5: Run — expect PASS.** `pytest tests/cockpit/test_lookup_detail.py -v`

- [ ] **Step 6: Wire drawer onto discovery rows.** In `_discover.py` replace the row `st.markdown` loop with button-per-row (keeps FakeSt tests valid — buttons return False there):

```python
    for ticker, why in rows:
        cols = st.columns([5, 1])
        with cols[0]:
            st.markdown(
                f'<div class="ws-card cp-row" style="padding:8px 14px;">'
                f"<strong>{ticker}</strong> — {why}</div>",
                unsafe_allow_html=True,
            )
        with cols[1]:
            if st.button("Detail", key=f"cp_detail_{ticker}"):
                from adapters.visualization.cockpit.stock_detail import (
                    open_stock_detail,
                )

                open_stock_detail(ticker)
```

- [ ] **Step 7: Run the cockpit test directory + smoke-run the app.**

Run: `pytest tests/cockpit/ -v` — all pass.
Run: `streamlit run adapters/visualization/dashboard.py --server.headless true` — open a detail drawer manually, confirm no legacy gauge/divergence/penny-stock default anywhere. Ctrl-C.

- [ ] **Step 8: Commit**

```bash
git add adapters/visualization/cockpit/ tests/cockpit/test_lookup_detail.py
git commit -m "feat: cockpit lookup + stock-detail drawer (st.dialog), legacy cruft not ported"
```

---

### Task 8: Cutover — delete retired tabs and their tests

**Files:**
- Delete: `adapters/visualization/tabs/weekly_brief.py`, `research_candidates.py`, `positions.py`, `stock_analysis.py`
- Delete/modify their tests: `tests/test_weekly_brief_tab.py`, `tests/test_research_candidates_tab.py`, `tests/test_fit_card.py`, plus any `tests/test_phase5_tabs.py` cases importing deleted tabs (keep cases covering `risk.py`/`trust.py`)
- Keep: `tabs/risk.py` (danger drill-down), `tabs/trust.py` (Showcase), `action_runner.py` (CLI-era; untouched)

- [ ] **Step 1: Verify nothing live still imports the doomed modules**

Run: `grep -rn "tabs.weekly_brief\|tabs.research_candidates\|tabs.positions\|tabs.stock_analysis" adapters/ application/ --include="*.py"`
Expected: NO hits (dashboard.py was rewired in Task 1; stock_detail ports were copies). Any hit = fix it first.

- [ ] **Step 2: Preserve guard coverage before deleting tests.** The deleted test files carry FORBIDDEN_WORDS scans for `scorecard`/`snowflake` — confirm those live in `tests/test_scorecard.py` (they do: lines 41, 71 — that file tests components, keep it). Create `tests/cockpit/test_forbidden_scan.py` to scan every cockpit module wholesale:

```python
"""FORBIDDEN_WORDS source scan across the whole cockpit package."""

import inspect

import pytest

from domain.fit import FORBIDDEN_WORDS

MODULES = [
    "adapters.visualization.cockpit.cockpit",
    "adapters.visualization.cockpit._danger",
    "adapters.visualization.cockpit._calls",
    "adapters.visualization.cockpit._retro",
    "adapters.visualization.cockpit._discover",
    "adapters.visualization.cockpit._lookup",
    "adapters.visualization.cockpit.stock_detail",
]


@pytest.mark.parametrize("mod_name", MODULES)
def test_cockpit_module_source_has_no_forbidden_words(mod_name):
    import importlib

    mod = importlib.import_module(mod_name)
    src = inspect.getsource(mod).lower()
    for word in FORBIDDEN_WORDS:
        assert word not in src, f"forbidden word {word!r} in {mod_name}"
```

NOTE: `_danger.py`/`_calls.py` may legitimately trip on domain vocabulary? They must not — REDUCE/TRIM/HOLD/ADD_OK contain none of the seven words. If a scan fails, fix the copy, never the word list.

- [ ] **Step 3: Delete the retired files and stale tests**

```bash
git rm adapters/visualization/tabs/weekly_brief.py \
       adapters/visualization/tabs/research_candidates.py \
       adapters/visualization/tabs/positions.py \
       adapters/visualization/tabs/stock_analysis.py \
       tests/test_weekly_brief_tab.py tests/test_research_candidates_tab.py \
       tests/test_fit_card.py
```

Then run `grep -rln "stock_analysis\|weekly_brief\|research_candidates\|tabs.positions" tests/` and prune the remaining references (e.g. cases inside `tests/test_phase5_tabs.py`) — delete only the cases importing deleted modules.

- [ ] **Step 4: Full suite + lint + typecheck**

Run: `make check`
Expected: all green (suite was 1628 pre-work; deletions remove some, cockpit adds ~20). Domain/application suites MUST be untouched-green. If `git checkout data/reports/` is needed before pre-commit (gitignored screen JSONs), do it.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor!: cut over to cockpit — retire v2 tab renderers (compute stays in core)"
```

---

### Task 9: Docs + wrap

**Files:**
- Modify: `docs/STATUS.md` (OVERWRITE — keep ~40 lines), `docs/PHASE_LOG.md` (append), `README.md` (dashboard section)

- [ ] **Step 1: README** — replace the 6-tab dashboard description with the two-surface model (Cockpit: danger → calls → retro → look-into-next → lookup; Showcase: methodology/falsification). Launch command unchanged: `streamlit run adapters/visualization/dashboard.py`.

- [ ] **Step 2: PHASE_LOG** — append one entry: cockpit redesign shipped, what was deleted/relocated, suite count.

- [ ] **Step 3: STATUS.md** — overwrite: phase = cockpit shipped pending PR review; next action = PR to dev; queued = A2 showcase, Project B alpha re-open (pre-registration + ds-methodology-review required).

- [ ] **Step 4: Verify + commit + PR**

Run: `make check` — green.

```bash
git add docs/ README.md
git commit -m "docs: cockpit redesign wrap — README two-surface model, STATUS, PHASE_LOG"
git push -u origin feat/cockpit-redesign
```

Open PR to `dev` (use the project `pr` skill). CI green → merge per project flow (feature → dev → main).

---

## Self-review notes (done at plan time)

- **Spec coverage:** danger→Task 2, calls+log→Task 3, retro→Task 4, discovery (factual rank + abstention banner + diversification lens + 3-5 rows)→Tasks 5-6, lookup+drawer (cruft not ported)→Task 7, universe clean→Task 0, one design system + router→Task 1 (reuses existing `ws-card` tokens — `styles.py` already single-source), retire/relocate + Trust reachable→Tasks 1/8, FORBIDDEN_WORDS on all new surfaces→per-task scans + Task 8 package-wide scan, degraded states→tested per section.
- **Resolved-question conformance:** Q1 write-in-cockpit (Task 3 idempotent), Q2 dominant-factor-only (Task 5/6), Q3 `MAX_ROWS = 5` (Task 6), Q4 Showcase entry (Task 1).
- **Known executor checkpoints (verify-at-port, not placeholders):** exact cache-TTL helper name in `price_cache.py` (Task 4 Step 1), `default_fit_fn` factory-vs-function (Task 7 Step 4), verbatim port of three `stock_analysis.py` functions (Task 7 Step 3).
- **Type consistency:** `rank_by_diversification(factor_series, candidate_series) -> list[tuple[str, float]]` used identically in Tasks 5 and 6; `render(...)` kwargs match assembler (Task 1) in every section task.
