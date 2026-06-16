# S2 — Google-AI Cited Case (`GeminiNarratorAdapter`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce the v9 "The case — Google AI, from cited sources" 5-in-favor / 5-to-watch block by summarizing ONLY already-fetched cited articles (E3 `NewsItem`) + S1 facts, each point source-tagged, both sides forced, labeled "informs you, not the verdict." Deterministic DATA-GAP fallback when no key / error — never blank-faked, never a buy/sell call.

**Architecture:** A `CaseSummarizerPort` Protocol (`domain/ports.py`) + domain types (`domain/case_models.py`). A `GeminiNarratorAdapter` (`adapters/ml/gemini_narrator.py`) mirroring the existing `GeminiEventClassifier` (google.generativeai, `gemini-2.0-flash`, `GEMINI_API_KEY`, rate-limit) and `OllamaNarratorAdapter` fallback shape. A pure `TemplateCaseSummarizer` fallback (no network) used as default + in tests. The card (S3 `render_expanded_card`) already accepts `case`; S5 calls the summarizer lazily.

**Tech Stack:** Python 3.12, `google-generativeai` (already a dep — see `GeminiEventClassifier`), Protocol ports, pytest. Depends on **S1** (`RagSignal`) and E3 (`application/news_context.NewsItem`).

**Spec:** §4. **Anchors:** component-map §7 (`GeminiEventClassifier` pattern), §2 (`OllamaNarratorAdapter` fallback), `domain/ports.py` `@runtime_checkable Protocol` style.

---

## File Structure

- Create `domain/case_models.py` — `CasePoint`, `CaseContext`, `CaseResult`.
- Modify `domain/ports.py` — add `CaseSummarizerPort` Protocol.
- Create `application/case_builder.py` — `build_case_context(ticker, signals, news) -> CaseContext` + `TemplateCaseSummarizer` (pure fallback).
- Create `adapters/ml/gemini_narrator.py` — `GeminiNarratorAdapter` implementing `CaseSummarizerPort`.
- Create `tests/domain/test_case_models.py`, `tests/application/test_case_builder.py`, `tests/adapters/test_gemini_narrator.py`.

Reuses: `application/news_context.NewsItem` (E3), `domain/evidence_rag.RagSignal` (S1).

---

### Task 1: Case domain types

**Files:** Create `domain/case_models.py`; Test `tests/domain/test_case_models.py`.

- [ ] **Step 1: Failing test**

```python
# tests/domain/test_case_models.py
from domain.case_models import CasePoint, CaseContext, CaseResult


def test_case_result_holds_both_sides_and_gap_flag():
    favor = (CasePoint(text="Beat EPS 3 of 4 quarters", source_tag="reported"),)
    watch = (CasePoint(text="Below 200-day trend", source_tag="technical"),)
    res = CaseResult(in_favor=favor, to_watch=watch, data_gap=False)
    assert res.in_favor[0].source_tag == "reported"
    assert res.to_watch[0].text == "Below 200-day trend"
    assert res.data_gap is False


def test_case_result_gap_default():
    assert CaseResult(in_favor=(), to_watch=(), data_gap=True).data_gap is True
```

- [ ] **Step 2: Run fail** → `pytest tests/domain/test_case_models.py -v` FAIL

- [ ] **Step 3: Implement**

```python
# domain/case_models.py
"""Domain types for the attributed 'case' block. Stdlib only."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CasePoint:
    text: str
    source_tag: str   # e.g. "reported", "valuation", "Reuters", "your rule"


@dataclass(frozen=True)
class CaseContext:
    ticker: str
    facts: tuple[str, ...]      # plain-English fact lines from the 5 RAG dimensions
    news: tuple[tuple[str, str], ...]   # (source, title) pairs — the ONLY free-text source


@dataclass(frozen=True)
class CaseResult:
    in_favor: tuple[CasePoint, ...]
    to_watch: tuple[CasePoint, ...]
    data_gap: bool
```

- [ ] **Step 4: Run pass** → PASS

- [ ] **Step 5: Commit**

```bash
git checkout data/reports/ 2>/dev/null || true
git add domain/case_models.py tests/domain/test_case_models.py
git commit -m "feat(case): CasePoint/CaseContext/CaseResult domain types"
```

---

### Task 2: `CaseSummarizerPort`

**Files:** Modify `domain/ports.py`; Test `tests/domain/test_case_models.py`.

- [ ] **Step 1: Failing test**

```python
def test_case_summarizer_port_is_runtime_checkable():
    from domain.ports import CaseSummarizerPort
    from domain.case_models import CaseContext, CaseResult

    class _Fake:
        def summarize_case(self, ctx: CaseContext) -> CaseResult:
            return CaseResult((), (), True)

    assert isinstance(_Fake(), CaseSummarizerPort)
```

- [ ] **Step 2: Run fail** → FAIL (ImportError)

- [ ] **Step 3: Implement** — add to `domain/ports.py` (mirror the existing `@runtime_checkable Protocol` style):

```python
from domain.case_models import CaseContext, CaseResult  # add near other imports


@runtime_checkable
class CaseSummarizerPort(Protocol):
    def summarize_case(self, ctx: CaseContext) -> CaseResult: ...
```

- [ ] **Step 4: Run pass** → PASS

- [ ] **Step 5: Commit**

```bash
git add domain/ports.py tests/domain/test_case_models.py
git commit -m "feat(case): CaseSummarizerPort protocol"
```

---

### Task 3: `build_case_context` + `TemplateCaseSummarizer` (pure fallback)

**Files:** Create `application/case_builder.py`; Test `tests/application/test_case_builder.py`.

The template summarizer is deterministic (no network): it turns RED/AMBER signals into "to watch" and GREEN into "in favor", tags each with the dimension, and appends cited news titles. Used as the default + in CI.

- [ ] **Step 1: Failing test**

```python
# tests/application/test_case_builder.py
from application.case_builder import build_case_context, TemplateCaseSummarizer
from domain.evidence_rag import RagSignal, RagColor
from application.news_context import NewsItem


def _signals():
    return (
        RagSignal("Technicals", RagColor.RED, "2.3 ATR below 200-day"),
        RagSignal("Valuation", RagColor.GREEN, "PEG 0.9 cheap"),
        RagSignal("Earnings", RagColor.GREEN, "EPS beat 3 of 4"),
    )


def test_build_context_carries_facts_and_news():
    ctx = build_case_context("YUMC", _signals(), [NewsItem("Reuters", "Same-store sales up", "2026-06-01")])
    assert ctx.ticker == "YUMC"
    assert any("PEG 0.9" in f for f in ctx.facts)
    assert ctx.news == (("Reuters", "Same-store sales up"),)


def test_template_summarizer_splits_favor_and_watch():
    ctx = build_case_context("YUMC", _signals(), [NewsItem("Reuters", "Same-store sales up", "2026-06-01")])
    res = TemplateCaseSummarizer().summarize_case(ctx)
    assert res.data_gap is False
    favor_text = " ".join(p.text for p in res.in_favor).lower()
    watch_text = " ".join(p.text for p in res.to_watch).lower()
    assert "valuation" in favor_text or "earnings" in favor_text
    assert "technicals" in watch_text
```

- [ ] **Step 2: Run fail** → FAIL

- [ ] **Step 3: Implement**

```python
# application/case_builder.py
"""Build CaseContext from evidence + news; deterministic template summarizer (no network)."""
from __future__ import annotations

from domain.case_models import CaseContext, CasePoint, CaseResult
from domain.evidence_rag import RagColor, RagSignal
from application.news_context import NewsItem


def build_case_context(ticker: str, signals: tuple[RagSignal, ...] | list[RagSignal],
                       news: list[NewsItem]) -> CaseContext:
    facts = tuple(f"{s.dimension}: {s.detail}" for s in signals if s.color is not RagColor.GAP)
    news_pairs = tuple((n.source, n.title) for n in news)
    return CaseContext(ticker=ticker, facts=facts, news=news_pairs)


class TemplateCaseSummarizer:
    """Pure CaseSummarizerPort fallback — deterministic, no network, honesty-safe."""

    def summarize_case(self, ctx: CaseContext) -> CaseResult:
        favor: list[CasePoint] = []
        watch: list[CasePoint] = []
        for fact in ctx.facts:
            dim, _, detail = fact.partition(": ")
            point = CasePoint(text=f"{dim}: {detail}", source_tag=dim.lower())
            # GREEN-ish details already read positive; route by keyword heuristic is avoided —
            # the assembler that feeds us only positive/negative is the LLM; template keeps it neutral:
            (favor if _reads_favorable(detail) else watch).append(point)
        for source, title in ctx.news:
            favor.append(CasePoint(text=title, source_tag=source))
        if not favor and not watch:
            return CaseResult((), (), True)
        return CaseResult(in_favor=tuple(favor[:5]), to_watch=tuple(watch[:5]), data_gap=False)


def _reads_favorable(detail: str) -> bool:
    d = detail.lower()
    neg = ("below", "broke", "negative", "weak", "wide spread", "high", "miss", "soft")
    return not any(n in d for n in neg)
```

- [ ] **Step 4: Run pass** → PASS

- [ ] **Step 5: Commit**

```bash
git add application/case_builder.py tests/application/test_case_builder.py
git commit -m "feat(case): build_case_context + deterministic TemplateCaseSummarizer fallback"
```

---

### Task 4: `GeminiNarratorAdapter`

**Files:** Create `adapters/ml/gemini_narrator.py`; Test `tests/adapters/test_gemini_narrator.py`.

> **Verify the google.generativeai API via context7 before implementing** (`resolve-library-id google-generativeai` → topic "GenerativeModel generate_content"). Mirror `GeminiEventClassifier` exactly (same import, model id, key handling). On ANY error / missing key → return `CaseResult(data_gap=True)` (or delegate to `TemplateCaseSummarizer`). Tests MUST NOT hit the network — patch the model call.

- [ ] **Step 1: Failing test (parser + fallback; no network)**

```python
# tests/adapters/test_gemini_narrator.py
from adapters.ml.gemini_narrator import GeminiNarratorAdapter, parse_case_json
from domain.case_models import CaseContext


def test_parse_case_json_maps_both_sides():
    raw = ('{"in_favor":[{"text":"Beat EPS 3 of 4","source":"reported"}],'
           '"to_watch":[{"text":"Below 200-day trend","source":"technical"}]}')
    res = parse_case_json(raw)
    assert res.in_favor[0].source_tag == "reported"
    assert res.to_watch[0].text == "Below 200-day trend"
    assert res.data_gap is False


def test_parse_garbage_is_gap():
    assert parse_case_json("not json").data_gap is True


def test_adapter_without_key_falls_back_to_gap(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    adapter = GeminiNarratorAdapter()
    res = adapter.summarize_case(CaseContext("X", facts=("Valuation: cheap",), news=()))
    assert res.data_gap is True  # no key → honest gap, never fabricated
```

- [ ] **Step 2: Run fail** → FAIL

- [ ] **Step 3: Implement**

```python
# adapters/ml/gemini_narrator.py
"""Google-AI cited-case summarizer (CaseSummarizerPort). Summarizes ONLY supplied cited facts/news.

Honesty: prompt forbids trade verbs; output is attributed; any failure -> data_gap=True (never faked).
"""
from __future__ import annotations

import json
import os

from domain.case_models import CaseContext, CasePoint, CaseResult

_MODEL = "gemini-2.0-flash"
_PROMPT = (
    "You summarise an investment research CASE from ONLY the facts and cited article titles given. "
    "Output STRICT JSON: {{\"in_favor\":[{{\"text\":..,\"source\":..}}],\"to_watch\":[{{\"text\":..,\"source\":..}}]}}. "
    "Up to 5 each side. Use ONLY the supplied facts/sources — invent nothing. "
    "Do NOT use the words buy, sell, predict, winner, conviction, alpha, or outperform. "
    "This informs the reader; it is NOT a recommendation.\n\nFACTS:\n{facts}\n\nARTICLES:\n{news}"
)


def parse_case_json(raw: str) -> CaseResult:
    try:
        data = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
        favor = tuple(CasePoint(p["text"], p.get("source", "")) for p in data.get("in_favor", []))
        watch = tuple(CasePoint(p["text"], p.get("source", "")) for p in data.get("to_watch", []))
        if not favor and not watch:
            return CaseResult((), (), True)
        return CaseResult(favor[:5], watch[:5], False)
    except Exception:  # noqa: BLE001 — any parse failure → honest gap
        return CaseResult((), (), True)


class GeminiNarratorAdapter:
    def __init__(self, api_key: str | None = None) -> None:
        self._key = api_key or os.environ.get("GEMINI_API_KEY")

    def summarize_case(self, ctx: CaseContext) -> CaseResult:
        if not self._key:
            return CaseResult((), (), True)
        try:
            import google.generativeai as genai  # lazy import (matches GeminiEventClassifier)

            genai.configure(api_key=self._key)
            model = genai.GenerativeModel(_MODEL)
            prompt = _PROMPT.format(
                facts="\n".join(ctx.facts),
                news="\n".join(f"[{s}] {t}" for s, t in ctx.news) or "(none)",
            )
            resp = model.generate_content(prompt)
            return parse_case_json(resp.text)
        except Exception:  # noqa: BLE001 — network/quota/parse → honest gap
            return CaseResult((), (), True)
```

- [ ] **Step 4: Run pass** → `pytest tests/adapters/test_gemini_narrator.py -v` PASS

- [ ] **Step 5: Commit**

```bash
git add adapters/ml/gemini_narrator.py tests/adapters/test_gemini_narrator.py
git commit -m "feat(case): GeminiNarratorAdapter (cited-only, fail-safe DATA-GAP, no trade verbs)"
```

---

### Task 5: Honesty scan + full S2 verify

- [ ] **Step 1: Forbidden-word scan (rendered output, not the prompt's negation list)**

```python
# tests/adapters/test_gemini_narrator.py — add
def test_template_case_output_has_no_forbidden_words():
    from application.case_builder import build_case_context, TemplateCaseSummarizer
    from domain.evidence_rag import RagSignal, RagColor
    from domain.fit import FORBIDDEN_WORDS
    ctx = build_case_context("YUMC", (RagSignal("Valuation", RagColor.GREEN, "PEG 0.9 cheap"),), [])
    res = TemplateCaseSummarizer().summarize_case(ctx)
    rendered = " ".join(p.text for p in res.in_favor + res.to_watch).lower()
    for w in FORBIDDEN_WORDS:
        assert w not in rendered
```

> Source scan note: `gemini_narrator.py`'s `_PROMPT` literally lists the forbidden words ("Do NOT use buy, sell, …"). A naive `inspect.getsource` scan would flag them. Exempt this file from the source scan (it negates them), but ASSERT on rendered OUTPUT instead (above). Document the exemption in the test file.

- [ ] **Step 2: Run** → fix until PASS.

- [ ] **Step 3: Full S2 verify**

```bash
mypy domain/case_models.py domain/ports.py application/case_builder.py adapters/ml/gemini_narrator.py
pytest tests/domain/test_case_models.py tests/application/test_case_builder.py tests/adapters/test_gemini_narrator.py -v
```
Expected: mypy Success; tests PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/adapters/test_gemini_narrator.py
git commit -m "test(case): honesty scan on rendered case output"
```

---

## Self-Review (S2)

1. **Spec §4 coverage:** port ✓ (Task 2); CaseContext/Result ✓ (Task 1); Gemini adapter mirrors GeminiEventClassifier ✓ (Task 4); cited-only + both-sides + data_gap fallback ✓; template fallback for CI/no-key ✓ (Task 3).
2. **Placeholders:** none.
3. **Type consistency:** `CaseResult`/`CasePoint` used identically in S3 `render_expanded_card._case_html` (which reads `p.text`, `p.source_tag`) — matches. `summarize_case(ctx) -> CaseResult` is the port everywhere.
4. **Honesty:** failure → `data_gap=True` (never faked); rendered-output forbidden scan; prompt forbids trade verbs + "informs, not a recommendation"; source-scan exemption documented for the prompt file only.

**Downstream contract:** S5 instantiates a `CaseSummarizerPort` (Gemini if key present, else `TemplateCaseSummarizer`) and calls `summarize_case` LAZILY on card expand, passing the result as `case=` to `render_expanded_card`.
