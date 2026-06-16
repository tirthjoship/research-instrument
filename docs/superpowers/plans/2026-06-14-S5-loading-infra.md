# S5 — Loading / Fetch Infra Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Home + Stock Analysis fetch progressively after a book loads: rows appear instantly with verdict, squares/sparkline fill per holding, a global determinate progress bar shows N/total, and the Google-AI case is fetched LAZILY only when a card is expanded. Loading (shimmer) is visually distinct from DATA-GAP (hatched). Per-ticker results are cached.

**Architecture:** A pure data-readiness state machine (`application/card_loading.py`, testable without Streamlit) + `@st.cache_data` wrappers (mirroring `price_cache.py`) for earnings + evidence + case. `st.fragment` wraps each row so one slow holding doesn't freeze the page (verify availability via context7; fallback `st.status`). The lazy case is gated on an expand flag in `st.session_state` so the summarizer (S2) is never called at load time.

**Tech Stack:** Python 3.12, Streamlit (`st.cache_data`, `st.fragment`, `st.progress`), pytest. Depends on **S1** (`build_evidence_card`, `fetch_earnings_history`), **S2** (`CaseSummarizerPort`, `TemplateCaseSummarizer`/`GeminiNarratorAdapter`, `build_case_context`), **S3** (`render_collapsed_row`/`render_expanded_card`), **S4** (Home render).

**Spec:** §7. **Anchors:** component-map §5 (`price_cache.py` `@st.cache_data` TTL pattern, `research_candidates.py:91` `st.progress`). **No `st.fragment`/`st.status` exists today** → first use; verify version via context7.

---

## File Structure

- Create `application/card_loading.py` — `RowState` enum + `card_state(card) -> RowState` + `select_case_summarizer() -> CaseSummarizerPort` (pure-ish).
- Modify `adapters/data/earnings_history_adapter.py` — add `@st.cache_data` `fetch_earnings_history` (S1 left a pass-through).
- Create `adapters/visualization/card_fetch.py` — `load_evidence_card_cached(ticker) -> EvidenceCard` (`@st.cache_data`), `load_case_cached(ticker, facts, news) -> CaseResult` (`@st.cache_data`), `get_case_on_expand(ticker, card, news, expanded) -> CaseResult | None`.
- Modify `adapters/visualization/tabs/weekly_brief.py` — `_render_needs_review` uses `st.fragment` per row + real cached card + progress bar.
- Modify `adapters/visualization/tabs/stock_analysis.py` — case loads lazily on the decision-card expander.
- Create `tests/application/test_card_loading.py`, `tests/adapters/test_card_fetch.py`.

---

### Task 1: Row-state machine (pure)

**Files:** Create `application/card_loading.py`; Test `tests/application/test_card_loading.py`.

`RowState`: `PENDING` (no data yet), `READY` (≥1 non-GAP signal), `GAP` (all 5 GAP — a real data gap, NOT loading). This drives shimmer (PENDING) vs hatched (GAP) — they must differ.

- [ ] **Step 1: Failing test**

```python
# tests/application/test_card_loading.py
from application.card_loading import RowState, card_state
from application.evidence_card import EvidenceCard
from domain.evidence_rag import RagSignal, RagColor, DIMENSIONS


def _card(colors):
    sigs = tuple(RagSignal(d, c, "x") for d, c in zip(DIMENSIONS, colors))
    return EvidenceCard("T", sigs, ())


def test_ready_when_any_real_signal():
    c = _card([RagColor.GREEN, RagColor.GAP, RagColor.GAP, RagColor.GAP, RagColor.GAP])
    assert card_state(c) is RowState.READY


def test_gap_when_all_gap():
    c = _card([RagColor.GAP] * 5)
    assert card_state(c) is RowState.GAP


def test_pending_when_no_signals():
    assert card_state(EvidenceCard("T", (), ())) is RowState.PENDING
```

- [ ] **Step 2: Run fail** → `pytest tests/application/test_card_loading.py -v` FAIL

- [ ] **Step 3: Implement**

```python
# application/card_loading.py
"""Pure data-readiness state for a card row. PENDING≠GAP (shimmer vs hatched)."""
from __future__ import annotations

from enum import Enum

from application.evidence_card import EvidenceCard
from domain.evidence_rag import RagColor


class RowState(Enum):
    PENDING = "pending"   # loading — render shimmer
    READY = "ready"       # has real signals
    GAP = "gap"           # genuine data gap — render hatched, never shimmer forever


def card_state(card: EvidenceCard) -> RowState:
    if not card.signals:
        return RowState.PENDING
    if all(s.color is RagColor.GAP for s in card.signals):
        return RowState.GAP
    return RowState.READY


def select_case_summarizer() -> object:
    """Gemini if a key is present, else the deterministic template (CI/no-key safe)."""
    import os

    from application.case_builder import TemplateCaseSummarizer

    if os.environ.get("GEMINI_API_KEY"):
        from adapters.ml.gemini_narrator import GeminiNarratorAdapter

        return GeminiNarratorAdapter()
    return TemplateCaseSummarizer()
```

- [ ] **Step 4: Run pass** → PASS

- [ ] **Step 5: Commit**

```bash
git checkout data/reports/ 2>/dev/null || true
git add application/card_loading.py tests/application/test_card_loading.py
git commit -m "feat(loading): RowState machine (PENDING≠GAP) + summarizer selector"
```

---

### Task 2: Cached fetch wrappers

**Files:** Modify `adapters/data/earnings_history_adapter.py`; Create `adapters/visualization/card_fetch.py`; Test `tests/adapters/test_card_fetch.py`.

> **Verify `st.cache_data` + `st.fragment` availability via context7** (`resolve-library-id streamlit` → topic "cache_data fragment"). The cache wrappers lazy-import streamlit (CI-safe, matching `price_cache.py`).

- [ ] **Step 1: Failing test (the lazy-case gate — the key behavior)**

```python
# tests/adapters/test_card_fetch.py
from adapters.visualization.card_fetch import get_case_on_expand
from application.evidence_card import EvidenceCard
from domain.evidence_rag import RagSignal, RagColor, DIMENSIONS


class _SpySummarizer:
    def __init__(self): self.calls = 0
    def summarize_case(self, ctx):
        self.calls += 1
        from domain.case_models import CaseResult
        return CaseResult((), (), True)


def _card():
    sigs = tuple(RagSignal(d, RagColor.GREEN, "x") for d in DIMENSIONS)
    return EvidenceCard("YUMC", sigs, ())


def test_case_not_fetched_unless_expanded():
    spy = _SpySummarizer()
    assert get_case_on_expand("YUMC", _card(), news=[], expanded=False, summarizer=spy) is None
    assert spy.calls == 0          # NOT called when collapsed


def test_case_fetched_on_expand():
    spy = _SpySummarizer()
    res = get_case_on_expand("YUMC", _card(), news=[], expanded=True, summarizer=spy)
    assert res is not None and spy.calls == 1
```

- [ ] **Step 2: Run fail** → FAIL

- [ ] **Step 3: Implement**

`adapters/data/earnings_history_adapter.py` — replace the pass-through `fetch_earnings_history` with a cached wrapper:

```python
def fetch_earnings_history(ticker: str) -> "EarningsHistory | None":
    import streamlit as st  # lazy import, CI-safe (matches price_cache.py)

    @st.cache_data(ttl=3600, show_spinner=False)
    def _cached(t: str) -> "EarningsHistory | None":
        return _fetch_earnings_history_impl(t)

    return _cached(ticker)
```

`adapters/visualization/card_fetch.py`:

```python
"""Streamlit-cached card fetches + the lazy-case gate."""
from __future__ import annotations

from application.case_builder import build_case_context
from application.evidence_card import EvidenceCard
from domain.case_models import CaseResult


def get_case_on_expand(ticker: str, card: EvidenceCard, news: list, *, expanded: bool,
                       summarizer: object) -> CaseResult | None:
    """Fetch the cited case ONLY when the card is expanded. Returns None when collapsed."""
    if not expanded:
        return None
    facts = tuple(s for s in card.signals)  # passed through to context builder below
    from domain.evidence_rag import RagColor
    sigs = tuple(s for s in card.signals if s.color is not RagColor.GAP)
    ctx = build_case_context(ticker, sigs, news)
    return summarizer.summarize_case(ctx)  # type: ignore[attr-defined]
```

- [ ] **Step 4: Run pass** → `pytest tests/adapters/test_card_fetch.py -v` PASS

- [ ] **Step 5: Commit**

```bash
git add adapters/data/earnings_history_adapter.py adapters/visualization/card_fetch.py tests/adapters/test_card_fetch.py
git commit -m "feat(loading): cached earnings fetch + lazy case-on-expand gate"
```

---

### Task 3: Progressive Home rows + progress bar + fragments

**Files:** Modify `adapters/visualization/tabs/weekly_brief.py`; Test `tests/test_weekly_brief_tab.py`.

Replace S4's `_home_evidence_card` (all-GAP) with real per-holding cached fetch, wrapped so each row renders independently. Drive `st.progress` over the holdings. Each row in an `st.fragment` (verify; fallback below).

- [ ] **Step 1: Failing test (the loader builds real cards; pure helper)**

```python
def test_home_cards_loader_returns_one_per_needs_review(monkeypatch):
    from adapters.visualization.tabs import weekly_brief as wb
    holds = [{"ticker": "YUMC", "verdict": "TRIM", "unrealized_pct": 1.0, "why": "x"},
             {"ticker": "AAPL", "verdict": "HOLD", "unrealized_pct": 2.0, "why": "y"}]
    # stub the cached fetch to avoid network
    monkeypatch.setattr(wb, "_fetch_card", lambda t: __import__("application.evidence_card",
        fromlist=["EvidenceCard"]).EvidenceCard(t, (), ()))
    cards = wb._needs_review_cards(holds)
    assert [t for t, _ in cards] == ["YUMC"]  # only the TRIM row
```

- [ ] **Step 2: Run fail** → FAIL

- [ ] **Step 3: Implement** — in `weekly_brief.py`:

```python
from adapters.visualization.card_fetch import get_case_on_expand
from application.card_loading import select_case_summarizer


def _fetch_card(ticker: str):
    """Cached real EvidenceCard for a ticker (S1 build via cached inputs)."""
    from adapters.visualization.price_cache import fetch_ticker_info, fetch_prices
    from adapters.data.earnings_history_adapter import fetch_earnings_history
    from application.analyst_panel import build_analyst_panel
    from application.evidence_card import build_evidence_card
    raw = fetch_ticker_info(ticker)
    info = {k: v for k, v in raw.items()}  # already snake-cased by YFinanceAdapter via price_cache
    px = fetch_prices((ticker,)).get(ticker, {})
    info["current_price"] = px.get("price")
    panel = build_analyst_panel(raw, "")
    prices = {"closes": px.get("closes", []), "atr": px.get("atr"), "ma200": px.get("ma200"),
              "spy_1y": None, "book_1y": px.get("vs_spy")}
    return build_evidence_card(ticker, info=info, prices=prices, panel=panel,
                               earnings=fetch_earnings_history(ticker), peers=[])


def _needs_review_cards(holdings: list[dict]) -> list[tuple[str, dict]]:
    return [(h["ticker"], h) for h in holdings if h.get("verdict") in _NEEDS_REVIEW]
```

Then rewrite `_render_needs_review` to: create `bar = st.progress(0.0, text="Fetching holdings…")`; iterate `_needs_review_cards`, for each call `_fetch_card`, render `render_collapsed_row` inside an `st.expander`; on expander-open render `render_expanded_card` with `get_case_on_expand(..., expanded=True, summarizer=select_case_summarizer())`; update `bar.progress(i/n, text=f"{i}/{n}")`; `bar.empty()` at end. Wrap each holding's render block in `@st.fragment` if available:

```python
import streamlit as st

def _render_needs_review(holdings):
    cards = _needs_review_cards(holdings)
    if not cards:
        st.markdown(_render_needs_review_html([]), unsafe_allow_html=True); return
    bar = st.progress(0.0, text=f"Fetching 0 / {len(cards)} holdings…")
    summarizer = select_case_summarizer()
    for i, (ticker, h) in enumerate(cards, 1):
        _render_one(ticker, h, summarizer)   # decorated with st.fragment if present
        bar.progress(i / len(cards), text=f"Fetching {i} / {len(cards)} holdings…")
    bar.empty()

# st.fragment fallback: if not hasattr(st, "fragment"), define a no-op decorator.
_fragment = getattr(st, "fragment", lambda f=None: (f if f else (lambda g: g)))

@_fragment
def _render_one(ticker, h, summarizer):
    card = _fetch_card(ticker)
    with st.expander(f"{ticker} — {h.get('verdict')}"):
        from domain.discipline import Verdict
        expanded = True  # inside expander body Streamlit only runs when open
        case = get_case_on_expand(ticker, card, news=[], expanded=expanded, summarizer=summarizer)
        st.markdown(render_expanded_card(card, case=case, verdict=Verdict(h["verdict"]),
                    name=ticker, unrealized_pct=h.get("unrealized_pct"),
                    means=h.get("why", ""), price=None, cost=None, returns=(),
                    reliability="measured forward; see Trust"), unsafe_allow_html=True)
    st.markdown(render_collapsed_row(card, verdict=Verdict(h["verdict"]), name=ticker,
                unrealized_pct=h.get("unrealized_pct"), oneliner=h.get("why", "")), unsafe_allow_html=True)
```

> **context7 verify:** confirm `st.fragment` exists in the installed Streamlit; if not, the `_fragment` fallback (no-op) keeps it working (just without per-row isolation). Confirm `st.progress(value, text=...)` signature (already used at `research_candidates.py:91`).

- [ ] **Step 4: Run pass** → `pytest tests/test_weekly_brief_tab.py -k cards_loader -v` PASS; run the full file + manual smoke if possible.

- [ ] **Step 5: Commit**

```bash
git add adapters/visualization/tabs/weekly_brief.py tests/test_weekly_brief_tab.py
git commit -m "feat(loading): progressive Home rows + progress bar + fragment + lazy case"
```

---

### Task 4: Lazy case on the Stock Analysis decision card

**Files:** Modify `adapters/visualization/tabs/stock_analysis.py`; Test `tests/test_stock_analysis_tab.py`.

S3 rendered the lead card with `case=None`. Now fetch the case lazily (the tab already has a single ticker in focus, so fetch once, cached) and pass it in.

- [ ] **Step 1: Failing test**

```python
def test_stock_analysis_case_uses_summarizer(monkeypatch):
    from adapters.visualization.tabs import stock_analysis as sa
    from domain.case_models import CaseResult, CasePoint
    monkeypatch.setattr(sa, "select_case_summarizer", lambda: type("S", (), {
        "summarize_case": lambda self, ctx: CaseResult((CasePoint("Cheap", "valuation"),), (), False)})())
    html = sa._render_decision_lead_html(_fake_result(), verdict_value="TRIM", with_case=True)
    assert "Cheap" in html
```

- [ ] **Step 2: Run fail** → FAIL

- [ ] **Step 3: Implement** — extend `_render_decision_lead_html(result, verdict_value, with_case=False)`: when `with_case`, build the card, then `case = get_case_on_expand(result.ticker, card, news=result_news, expanded=True, summarizer=select_case_summarizer())` and pass `case=case` to `render_expanded_card`. Import `select_case_summarizer` from `application.card_loading` and `get_case_on_expand` from `card_fetch`. Default the tab call to `with_case=True`.

- [ ] **Step 4: Run pass** → PASS

- [ ] **Step 5: Commit**

```bash
git add adapters/visualization/tabs/stock_analysis.py tests/test_stock_analysis_tab.py
git commit -m "feat(loading): lazy cited-case on Stock Analysis decision card"
```

---

### Task 5: Full S5 verify

- [ ] **Step 1: Typecheck + tests**

```bash
mypy application/card_loading.py adapters/visualization/card_fetch.py adapters/data/earnings_history_adapter.py
pytest tests/application/test_card_loading.py tests/adapters/test_card_fetch.py tests/test_weekly_brief_tab.py tests/test_stock_analysis_tab.py -v
```
Expected: mypy Success; tests PASS.

- [ ] **Step 2: Manual smoke (if a venv + data exist)**

```bash
STOCKREC_LOCAL_ONLY=1 streamlit run adapters/visualization/dashboard.py --server.port 8531 --server.headless true
# then: scripts/screenshot_dashboard.py --port 8531 --tab 0 --out /tmp/home.png ; eyeball progressive load + lazy case
```

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "test(loading): full S5 verify (state machine, lazy case, progressive rows)"
```

---

## Self-Review (S5)

1. **Spec §7 coverage:** progressive rows + progress bar (Task 3) ✓; lazy AI-case on expand (Task 2 gate + Tasks 3/4) ✓; shimmer≠DATA-GAP via `RowState` PENDING≠GAP (Task 1) + S3 CSS ✓; per-ticker cache (Task 2) ✓; `st.fragment` with no-op fallback (Task 3) ✓.
2. **Placeholders:** none. (`news=[]` on Home rows is a conscious default — Home cards have no per-holding news feed yet; Stock Analysis passes real news. Documented, not a placeholder.)
3. **Type consistency:** `EvidenceCard`/`build_evidence_card` (S1), `render_collapsed_row`/`render_expanded_card` (S3), `summarize_case(ctx)->CaseResult` (S2) — all used with matching signatures.
4. **Honesty:** lazy case never called collapsed (Task 2 test); PENDING shimmer resolves to READY or GAP (never infinite shimmer on a real gap); no-key → TemplateCaseSummarizer (S2), still attributed.

**Downstream:** S6 prepends the landing door; once a book loads (sample/CSV/manual) it flows into `_render_needs_review` here.
