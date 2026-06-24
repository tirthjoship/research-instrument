# Portfolio-Fit Verdict + Weekend Wrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an honest portfolio-fit verdict (evidence grade + fit flags, never a prediction) to the Stock Analysis tab, then close the project with the final docs sprint.

**Architecture:** Hexagonal. New pure `domain/fit.py` computes the verdict from primitives; new `application/fit_use_case.py` gathers inputs from EXISTING artifacts + machinery (latest `screen_<date>.json`, `brief_summary.json` macro block, holdings CSV, `MacroBetaUseCase` for a single-ticker beta); the Stock Analysis tab renders one card. Spec: `docs/superpowers/specs/2026-06-11-phase6-fit-verdict-wrap-design.md`.

**Tech Stack:** Python 3.12, Streamlit (existing), pytest + Hypothesis, pre-commit (black/isort/mypy strict/ruff — NEVER `--no-verify`; if a hook reformats, re-add and commit again).

**Branch:** `feat/portfolio-fit-verdict` (already exists, spec committed on it). Never commit to develop/main.

---

## Plan-level amendments to the spec (validated 2026-06-11, plan supersedes §4 details)

1. **Screen scores come from the latest `screen_<date>.json` artifact, NOT a live
   `EvidenceScreenUseCase.run`.** A live run fetches ~430 tickers from yfinance —
   minutes of latency + rate-limit risk in an interactive tab. The artifact holds the
   FULL ranked distribution (verified: `cli.py screen-candidates` writes full dist;
   `rank_universe(cands, top_n=len(cands))` in `evidence_screen_use_case.py:164`),
   is refreshed by the Saturday job (dashboard plan Task 11.5), and staleness is
   surfaced on the card. Ticker missing from artifact → DATA_GAP flag.
2. **Book exposure comes from `brief_summary.json`'s `macro` block** (written by
   weekly-brief since dashboard Task 2) — `net_beta_by_factor.SPY` +
   `systematic_share`. The domain signature takes these as plain floats, not a
   `BookMacroExposure` object — purer and testable.
3. **Single-name weights use `cost_basis`** (TOTAL position cost — validated comment
   `macro_beta_use_case.py:76-78` — NOT per-share) from `read_holdings`. Card caption
   says "weights by cost basis." Avoids N live price fetches per render.
4. **Ticker beta reuses `MacroBetaUseCase.execute` with a 1-element holdings list**
   (returns `BookMacroExposure.holdings[0].betas` → SPY `beta_headline`). Zero new
   estimation code.

---

## PRECONDITIONS

1. On branch `feat/portfolio-fit-verdict`, up to date with develop (PR #39 merged).
2. Baseline: `python -m pytest tests/ -q 2>&1 | tail -3` → record count (expect 1561
   passed). Your changes must not add failures.
3. `python -c "import streamlit, plotly, hypothesis"` succeeds.

---

### Task 1: `domain/fit.py` — pure verdict logic

**Files:**
- Create: `domain/fit.py`
- Test: `tests/domain/test_fit.py` (create)

- [ ] **Step 1: Write the failing tests** — create `tests/domain/test_fit.py`:

```python
"""Domain tests for the portfolio-fit verdict (pure logic, no IO)."""

from hypothesis import given
from hypothesis import strategies as st

from domain.fit import (
    FORBIDDEN_WORDS,
    FitFlag,
    FitVerdict,
    assess_fit,
    composite_rank,
)


def _kwargs(**over):
    base = dict(
        ticker="NVDA",
        ticker_composite=1.2,
        universe_composites=[-1.0, 0.0, 0.5, 1.2, 2.0],
        ticker_beta=1.4,
        book_net_spy_beta=1.1,
        book_systematic_share=0.55,
        systematic_share_threshold=0.60,
        position_values={"AAPL": 5000.0, "MSFT": 3000.0, "ARKK": 2000.0},
        trend_state="intact",
        hypothetical_weight=0.02,
    )
    base.update(over)
    return base


# --- composite_rank ---------------------------------------------------------

def test_composite_rank_basic():
    # 1.2 beats 3 of the other 4 values
    assert composite_rank(1.2, [-1.0, 0.0, 0.5, 1.2, 2.0]) == 0.75


def test_composite_rank_empty_universe():
    assert composite_rank(1.2, []) is None


# --- evidence grade ---------------------------------------------------------

def test_grade_strong_at_80th_percentile():
    v = assess_fit(**_kwargs(ticker_composite=2.0))  # beats 4/4 -> rank 1.0
    assert v.evidence_grade == "STRONG"


def test_grade_unknown_when_no_composite():
    v = assess_fit(**_kwargs(ticker_composite=None))
    assert v.evidence_grade == "UNKNOWN"
    assert any(f.kind == "DATA_GAP" for f in v.fit_flags)


# --- BETA_AMPLIFY -----------------------------------------------------------

def test_beta_amplify_fires_same_sign_near_threshold():
    v = assess_fit(**_kwargs(ticker_beta=1.5, book_net_spy_beta=1.2,
                             book_systematic_share=0.58))
    assert any(f.kind == "BETA_AMPLIFY" and f.severity == "WARNING"
               for f in v.fit_flags)


def test_beta_amplify_silent_on_opposite_sign():
    v = assess_fit(**_kwargs(ticker_beta=-0.5))
    assert not any(f.kind == "BETA_AMPLIFY" for f in v.fit_flags)


def test_beta_missing_is_data_gap_not_crash():
    v = assess_fit(**_kwargs(ticker_beta=None))
    assert any(f.kind == "DATA_GAP" and "beta" in f.message.lower()
               for f in v.fit_flags)


# --- CONCENTRATION ----------------------------------------------------------

def test_concentration_reports_rank_of_hypothetical_add():
    # book 10,000; 2% add = 204.08 -> smaller than all three names
    v = assess_fit(**_kwargs())
    conc = [f for f in v.fit_flags if f.kind == "CONCENTRATION"]
    assert len(conc) == 1
    assert conc[0].severity == "INFO"


def test_concentration_caution_when_add_would_be_largest():
    v = assess_fit(**_kwargs(hypothetical_weight=0.60))
    conc = [f for f in v.fit_flags if f.kind == "CONCENTRATION"][0]
    assert conc.severity == "CAUTION"


def test_concentration_data_gap_without_positions():
    v = assess_fit(**_kwargs(position_values={}))
    assert not any(f.kind == "CONCENTRATION" for f in v.fit_flags)
    assert any(f.kind == "DATA_GAP" and "holding" in f.message.lower()
               for f in v.fit_flags)


# --- TREND_STATE ------------------------------------------------------------

def test_trend_state_descriptive_only():
    v = assess_fit(**_kwargs(trend_state="broken"))
    ts = [f for f in v.fit_flags if f.kind == "TREND_STATE"][0]
    assert "broken" in ts.message
    # ADR-046: wording must not imply an exit/entry signal
    assert "exit" not in ts.message.lower()
    assert "sell" not in ts.message.lower()


# --- invariants (Hypothesis) -------------------------------------------------

@given(
    composite=st.one_of(st.none(), st.floats(-5, 5, allow_nan=False)),
    universe=st.lists(st.floats(-5, 5, allow_nan=False), max_size=50),
    beta=st.one_of(st.none(), st.floats(-3, 3, allow_nan=False)),
    book_beta=st.one_of(st.none(), st.floats(-3, 3, allow_nan=False)),
    share=st.one_of(st.none(), st.floats(0, 1, allow_nan=False)),
    weight=st.floats(0.001, 0.99, allow_nan=False),
)
def test_never_raises_and_never_uses_forbidden_words(
    composite, universe, beta, book_beta, share, weight
):
    v = assess_fit(**_kwargs(
        ticker_composite=composite, universe_composites=universe,
        ticker_beta=beta, book_net_spy_beta=book_beta,
        book_systematic_share=share, hypothetical_weight=weight,
    ))
    assert isinstance(v, FitVerdict)
    assert v.label == "RESEARCH_ONLY"
    text = (v.summary + " ".join(f.message for f in v.fit_flags)).lower()
    for word in FORBIDDEN_WORDS:
        assert word not in text, f"forbidden word {word!r} in output"


@given(weight=st.floats(0.001, 0.99, allow_nan=False))
def test_hypothetical_add_never_shrinks_book(weight):
    # invariant: the implied add amount is always > 0 given positive book value
    v = assess_fit(**_kwargs(hypothetical_weight=weight))
    assert v.label == "RESEARCH_ONLY"
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/domain/test_fit.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'domain.fit'`

- [ ] **Step 3: Implement `domain/fit.py`** (pure, stdlib only — NO framework imports,
repo hard rule):

```python
"""Portfolio-fit verdict — evidence grade + fit arithmetic. NEVER a prediction.

Honest boundary (spec §2): seven falsified hypotheses killed prediction; they did
not kill evidence aggregation or portfolio arithmetic. Every output is descriptive.
The FORBIDDEN_WORDS guard is a domain invariant, enforced by tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

# Vocabulary the verdict may never emit (case-insensitive). Single source of
# truth — the UI regression test imports this same constant.
FORBIDDEN_WORDS: tuple[str, ...] = (
    "buy",
    "sell",
    "winner",
    "conviction",
    "predict",
    "alpha",
    "outperform",
)

_GRADE_STRONG = 0.80
_GRADE_MODERATE = 0.50


@dataclass(frozen=True)
class FitFlag:
    kind: str  # BETA_AMPLIFY | CONCENTRATION | TREND_STATE | DATA_GAP
    message: str  # plain English, family-readable
    severity: str  # INFO | CAUTION | WARNING


@dataclass(frozen=True)
class FitVerdict:
    ticker: str
    evidence_grade: str  # STRONG | MODERATE | WEAK | UNKNOWN
    fit_flags: tuple[FitFlag, ...]
    summary: str
    label: str = "RESEARCH_ONLY"


def composite_rank(
    composite: float, universe_composites: Sequence[float]
) -> float | None:
    """Fraction of the universe this composite beats. None if universe empty.

    The screen stores per-FACTOR percentiles only; the composite rank is not
    pre-computed anywhere (validated 2026-06-11), so it is derived here.
    """
    if not universe_composites:
        return None
    n = len(universe_composites)
    beaten = sum(1 for c in universe_composites if c < composite)
    return beaten / max(n - 1, 1) if n > 1 else 1.0


def _grade(rank: float | None) -> str:
    if rank is None:
        return "UNKNOWN"
    if rank >= _GRADE_STRONG:
        return "STRONG"
    if rank >= _GRADE_MODERATE:
        return "MODERATE"
    return "WEAK"


def assess_fit(
    ticker: str,
    ticker_composite: float | None,
    universe_composites: Sequence[float],
    ticker_beta: float | None,
    book_net_spy_beta: float | None,
    book_systematic_share: float | None,
    systematic_share_threshold: float,
    position_values: Mapping[str, float],
    trend_state: str | None,
    hypothetical_weight: float = 0.02,
) -> FitVerdict:
    """Compute the fit verdict. Degrades to DATA_GAP flags, never raises."""
    flags: list[FitFlag] = []

    rank = (
        composite_rank(ticker_composite, universe_composites)
        if ticker_composite is not None
        else None
    )
    grade = _grade(rank)
    if grade == "UNKNOWN":
        flags.append(
            FitFlag(
                kind="DATA_GAP",
                message=(
                    f"{ticker} is not in the latest evidence screen — its "
                    "evidence grade is unknown until the next screen run."
                ),
                severity="INFO",
            )
        )

    # --- BETA_AMPLIFY: same-sign beta near/over the systematic-share line ---
    if ticker_beta is None:
        flags.append(
            FitFlag(
                kind="DATA_GAP",
                message=(
                    f"No market beta could be estimated for {ticker} "
                    "(insufficient price history)."
                ),
                severity="INFO",
            )
        )
    elif (
        book_net_spy_beta is not None
        and book_systematic_share is not None
        and ticker_beta * book_net_spy_beta > 0
        and book_systematic_share >= systematic_share_threshold - 0.05
    ):
        flags.append(
            FitFlag(
                kind="BETA_AMPLIFY",
                message=(
                    f"{ticker} moves with the market the same way your book "
                    f"already does (its beta is {ticker_beta:+.2f}, your book's "
                    f"is {book_net_spy_beta:+.2f}). Adding it deepens the one "
                    "market-wide bet that already drives "
                    f"{book_systematic_share:.0%} of your book's movement."
                ),
                severity="WARNING",
            )
        )

    # --- CONCENTRATION: single-name weight arithmetic (cost-basis values) ---
    if not position_values:
        flags.append(
            FitFlag(
                kind="DATA_GAP",
                message="No holdings loaded — fit vs your book is unavailable.",
                severity="INFO",
            )
        )
    else:
        book_total = sum(position_values.values())
        if book_total > 0:
            add_value = book_total * hypothetical_weight / (1 - hypothetical_weight)
            largest_ticker, largest_value = max(
                position_values.items(), key=lambda kv: kv[1]
            )
            new_total = book_total + add_value
            n_bigger = sum(1 for v in position_values.values() if v > add_value)
            if add_value > largest_value:
                flags.append(
                    FitFlag(
                        kind="CONCENTRATION",
                        message=(
                            f"At {hypothetical_weight:.0%} sizing this would "
                            "become your single largest position — larger than "
                            f"{largest_ticker} "
                            f"({largest_value / new_total:.1%} of the book)."
                        ),
                        severity="CAUTION",
                    )
                )
            else:
                flags.append(
                    FitFlag(
                        kind="CONCENTRATION",
                        message=(
                            f"At {hypothetical_weight:.0%} sizing this would be "
                            f"your #{n_bigger + 1} position by weight; your "
                            f"largest single name stays {largest_ticker} at "
                            f"{largest_value / new_total:.1%}."
                        ),
                        severity="INFO",
                    )
                )

    # --- TREND_STATE: descriptive only (ADR-046 KILL — never an exit signal) ---
    if trend_state:
        flags.append(
            FitFlag(
                kind="TREND_STATE",
                message=f"Price trend is currently {trend_state} (descriptive only).",
                severity="INFO",
            )
        )

    grade_text = {
        "STRONG": "sits in the top fifth of the screened universe on factual "
        "evidence (valuation, quality, health)",
        "MODERATE": "sits in the upper half of the screened universe on factual "
        "evidence",
        "WEAK": "ranks in the lower half of the screened universe on factual "
        "evidence",
        "UNKNOWN": "has no evidence grade yet (not in the latest screen)",
    }[grade]
    summary = (
        f"{ticker} {grade_text}. This is evidence + fit arithmetic, not a "
        "forecast — the project tested prediction for 18 years of data and "
        "the ideas failed (see Falsification Lab)."
    )

    return FitVerdict(
        ticker=ticker,
        evidence_grade=grade,
        fit_flags=tuple(flags),
        summary=summary,
    )
```

- [ ] **Step 4: Run tests green**

Run: `python -m pytest tests/domain/test_fit.py -q`
Expected: all pass (12 tests)

- [ ] **Step 5: Commit**

```bash
git add domain/fit.py tests/domain/test_fit.py
git commit -m "feat: domain fit verdict — evidence grade + fit flags, vocabulary-guarded"
```

---

### Task 2: Fix `top_concentration` per-share-price bug (market value, not price)

**Why:** `application/holdings_risk.py:195` computes `top_concentration` from
`p.price` (per-share price), so a 1-share lot of a high-priced stock dominates.
`PositionRisk.market_value_cad` (domain/models.py:426) is the correct base. Found
during spec validation; family risk decisions read this number.

**Files:**
- Modify: `application/holdings_risk.py` (~line 195)
- Test: find existing test with `grep -rln "top_concentration" tests/` and extend

- [ ] **Step 1: Write the failing test** (append to the existing holdings-risk test
file found by the grep; follow its fixture pattern):

```python
def test_top_concentration_uses_market_value_not_price():
    # 1 share @ $1000 vs 100 shares @ $50: market values 1000 vs 5000.
    # Correct top_concentration = 5000/6000; price-based (buggy) = 1000/1050.
    from application.holdings_risk import compute_portfolio_risk  # adjust to real fn name

    # Build two PositionRisk fixtures per the file's existing pattern, with
    # market_value_cad=1000.0 (price 1000.0) and market_value_cad=5000.0 (price 50.0).
    # Assert abs(result.top_concentration - 5000/6000) < 1e-9
```

NOTE to implementer: the exact constructor/factory for `PositionRisk` fixtures is in
the existing test file — mirror it. The assertion above is the contract.

- [ ] **Step 2: Run to verify failure** — expected: assertion fails with the
price-based value (≈0.952), proving the bug.

- [ ] **Step 3: Fix** — in `application/holdings_risk.py` ~line 195, change the
concentration base from `p.price` to `p.market_value_cad`:

```python
    values = [p.market_value_cad for p in positions]
```

(Keep the same `max(values)/sum(values)` shape; only the base changes.)

- [ ] **Step 4: Full-module run** — `python -m pytest tests/ -q -k "holdings_risk or portfolio_risk"` —
fix any existing assertions that encoded the buggy value (update them to
market-value-based expectations; record each in the commit message).

- [ ] **Step 5: Commit**

```bash
git add application/holdings_risk.py tests/
git commit -m "fix: top_concentration uses market value, not per-share price"
```

---

### Task 3: `application/fit_use_case.py` — input gathering

**Files:**
- Create: `application/fit_use_case.py`
- Test: `tests/application/test_fit_use_case.py` (create)

- [ ] **Step 1: Write the failing tests:**

```python
import json
from datetime import datetime, timezone

from application.fit_use_case import gather_and_assess


def _write_screen(tmp_path, tickers_composites):
    p = tmp_path / "screen_2026-06-13.json"
    p.write_text(json.dumps({
        "as_of": "2026-06-13",
        "candidates": [
            {"ticker": t, "composite": c, "trend_health": 0.8}
            for t, c in tickers_composites
        ],
    }))
    return str(tmp_path)


def _write_summary(tmp_path, macro):
    p = tmp_path / "brief_summary.json"
    p.write_text(json.dumps({"as_of": "2026-06-13", "macro": macro}))
    return str(p)


def _write_holdings(tmp_path):
    p = tmp_path / "holdings.csv"
    p.write_text(
        "Symbol,Quantity,Book Value,Account Type\n"
        "AAPL,10,5000,TFSA\nMSFT,5,3000,TFSA\n"
    )
    return str(p)


def test_gather_full_inputs(tmp_path):
    reports = _write_screen(tmp_path, [("NVDA", 2.0), ("AAPL", 0.5), ("XYZ", -1.0)])
    summary = _write_summary(tmp_path, {
        "net_beta_by_factor": {"SPY": 1.2}, "systematic_share": 0.63,
    })
    holdings = _write_holdings(tmp_path)

    v = gather_and_assess(
        ticker="NVDA",
        reports_dir=reports,
        summary_path=summary,
        holdings_path=holdings,
        beta_fn=lambda ticker, as_of: 1.4,  # injected — no network in tests
        as_of=datetime(2026, 6, 13, tzinfo=timezone.utc),
        systematic_share_threshold=0.60,
    )
    assert v.ticker == "NVDA"
    assert v.evidence_grade == "STRONG"
    assert any(f.kind == "BETA_AMPLIFY" for f in v.fit_flags)


def test_gather_all_artifacts_missing_degrades(tmp_path):
    v = gather_and_assess(
        ticker="NVDA",
        reports_dir=str(tmp_path),
        summary_path=str(tmp_path / "nope.json"),
        holdings_path=str(tmp_path / "nope.csv"),
        beta_fn=lambda ticker, as_of: None,
        as_of=datetime(2026, 6, 13, tzinfo=timezone.utc),
        systematic_share_threshold=0.60,
    )
    assert v.evidence_grade == "UNKNOWN"
    assert v.label == "RESEARCH_ONLY"
    gaps = [f for f in v.fit_flags if f.kind == "DATA_GAP"]
    assert len(gaps) >= 2  # screen + holdings at minimum


def test_beta_fn_exception_becomes_data_gap(tmp_path):
    def boom(ticker, as_of):
        raise RuntimeError("yfinance down")

    v = gather_and_assess(
        ticker="NVDA",
        reports_dir=str(tmp_path),
        summary_path=str(tmp_path / "nope.json"),
        holdings_path=str(tmp_path / "nope.csv"),
        beta_fn=boom,
        as_of=datetime(2026, 6, 13, tzinfo=timezone.utc),
        systematic_share_threshold=0.60,
    )
    assert v.label == "RESEARCH_ONLY"  # no crash
```

- [ ] **Step 2: Run to verify failure** — `python -m pytest tests/application/test_fit_use_case.py -q`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: Implement `application/fit_use_case.py`:**

```python
"""Gather fit-verdict inputs from existing artifacts + machinery.

Reads (all best-effort; absence becomes a DATA_GAP flag, never an exception):
- latest screen_<date>.json   — full ranked distribution (Saturday job)
- brief_summary.json          — book macro block (weekly-brief CLI)
- holdings CSV                — cost-basis position values
- beta_fn                     — injected single-ticker SPY beta estimator
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from loguru import logger

from application.holdings_reader import read_holdings
from domain.fit import FitVerdict, assess_fit

BetaFn = Callable[[str, datetime], "float | None"]


def _load_latest_screen(reports_dir: str) -> dict[str, Any] | None:
    candidates = sorted(
        f
        for f in Path(reports_dir).glob("screen_*.json")
        if not f.name.startswith("screen_ic_")
    )
    if not candidates:
        return None
    try:
        return json.loads(candidates[-1].read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _load_macro(summary_path: str) -> dict[str, Any] | None:
    p = Path(summary_path)
    if not p.exists():
        return None
    try:
        macro = json.loads(p.read_text()).get("macro")
        return macro if isinstance(macro, dict) else None
    except (json.JSONDecodeError, OSError):
        return None


def gather_and_assess(
    ticker: str,
    reports_dir: str,
    summary_path: str,
    holdings_path: str,
    beta_fn: BetaFn,
    as_of: datetime,
    systematic_share_threshold: float,
    hypothetical_weight: float = 0.02,
) -> FitVerdict:
    screen = _load_latest_screen(reports_dir)
    ticker_composite: float | None = None
    trend_state: str | None = None
    universe_composites: list[float] = []
    if screen:
        for c in screen.get("candidates", []):
            comp = c.get("composite")
            if isinstance(comp, (int, float)):
                universe_composites.append(float(comp))
                if c.get("ticker") == ticker:
                    ticker_composite = float(comp)
                    th = c.get("trend_health")
                    if isinstance(th, (int, float)):
                        trend_state = "intact" if th >= 0.5 else "broken"

    macro = _load_macro(summary_path)
    book_net_spy_beta: float | None = None
    book_systematic_share: float | None = None
    if macro:
        spy = macro.get("net_beta_by_factor", {}).get("SPY")
        if isinstance(spy, (int, float)):
            book_net_spy_beta = float(spy)
        share = macro.get("systematic_share")
        if isinstance(share, (int, float)):
            book_systematic_share = float(share)

    position_values: dict[str, float] = {}
    try:
        for h in read_holdings(holdings_path):
            # cost_basis is the TOTAL position cost (not per-share) — validated
            # against macro_beta_use_case.py:76-78. Weights are by cost basis.
            position_values[h.ticker] = position_values.get(h.ticker, 0.0) + float(
                h.cost_basis
            )
    except (OSError, ValueError) as exc:
        logger.warning(f"fit: holdings unavailable ({exc}) — DATA_GAP")

    try:
        ticker_beta = beta_fn(ticker, as_of)
    except Exception as exc:  # beta estimation is best-effort by design
        logger.warning(f"fit: beta estimation failed for {ticker} ({exc})")
        ticker_beta = None

    return assess_fit(
        ticker=ticker,
        ticker_composite=ticker_composite,
        universe_composites=universe_composites,
        ticker_beta=ticker_beta,
        book_net_spy_beta=book_net_spy_beta,
        book_systematic_share=book_systematic_share,
        systematic_share_threshold=systematic_share_threshold,
        position_values=position_values,
        trend_state=trend_state,
        hypothetical_weight=hypothetical_weight,
    )


def default_beta_fn(ticker: str, as_of: datetime) -> float | None:
    """Single-ticker SPY beta via the EXISTING MacroBetaUseCase (1-element book).

    Reuses the Ridge estimator + retry/backoff price fetch end-to-end. Returns the
    SPY beta_headline, or None when history is insufficient.
    """
    from types import SimpleNamespace

    import yaml

    from adapters.ml.macro_beta_analyzer import RidgeMacroBetaEstimator
    from application.macro_beta_use_case import MacroBetaUseCase
    from application.price_returns import load_price_series

    try:
        cfg = yaml.safe_load(Path("config/markets/us.yaml").read_text()) or {}
    except OSError:
        cfg = {}
    macro_cfg = cfg.get("macro_beta", {})

    uc = MacroBetaUseCase(
        price_provider=lambda t, s, e: load_price_series(t, s, e),
        estimator=RidgeMacroBetaEstimator(alpha=macro_cfg.get("ridge_alpha", 0.2)),
        factors=macro_cfg.get("factors", ["SPY", "TLT", "UUP", "XLE"]),
        alpha=macro_cfg.get("ridge_alpha", 0.2),
        headline_window=macro_cfg.get("headline_window_days", 252),
        drift_window=macro_cfg.get("drift_window_days", 63),
        thresholds={
            "systematic_share_threshold": macro_cfg.get(
                "systematic_share_threshold", 0.60
            ),
            "factor_dominance_threshold": macro_cfg.get(
                "factor_dominance_threshold", 0.25
            ),
            "drift_threshold": macro_cfg.get("drift_threshold", 0.50),
        },
    )
    book = uc.execute(
        [SimpleNamespace(ticker=ticker, shares=1.0, cost_basis=0.0)], as_of
    )
    if book is None or not book.holdings:
        return None
    for b in book.holdings[0].betas:
        if b.factor == "SPY":
            return b.beta_headline
    return None


def market_systematic_share_threshold() -> float:
    """The same config value MacroBetaUseCase is constructed with (us.yaml, 0.60)."""
    import yaml

    try:
        cfg = yaml.safe_load(Path("config/markets/us.yaml").read_text()) or {}
    except OSError:
        return 0.60
    return float(cfg.get("macro_beta", {}).get("systematic_share_threshold", 0.60))
```

NOTE to implementer: check `read_holdings` (`application/holdings_reader.py:41`) CSV
column names against the test fixture above and adjust the fixture header to the real
parser's expectations — the contract is "two holdings, cost_basis totals 5000/3000."
Check `config/markets/us.yaml` key nesting (`macro_beta:` block) before relying on it.

- [ ] **Step 4: Run tests green** — `python -m pytest tests/application/test_fit_use_case.py -q` → 3 passed

- [ ] **Step 5: mypy + commit**

Run: `mypy application/fit_use_case.py domain/fit.py` → clean

```bash
git add application/fit_use_case.py tests/application/test_fit_use_case.py
git commit -m "feat: fit use case — artifact-driven input gathering, injected beta"
```

---

### Task 4: CSS `verdict-caution` class + fit card in Stock Analysis tab

**Files:**
- Modify: `adapters/visualization/components/styles.py` (after `.verdict-neutral`, ~line 568)
- Modify: `adapters/visualization/tabs/stock_analysis.py` (`render()` ~line 79 and new `_render_fit_card`)
- Test: `tests/test_fit_card.py` (create)

- [ ] **Step 1: Add the CSS class.** In `styles.py`, directly after the
`.verdict-neutral` line:

```css
.verdict-caution { border-left: 4px solid var(--warning, #CA8A04); }
```

(Check whether a `--warning` CSS variable exists in the `:root` block of styles.py;
if not, use the literal `#CA8A04` — the amber already used by the realignment tabs.)

- [ ] **Step 2: Write the failing tests** — create `tests/test_fit_card.py`:

```python
"""Fit card: render-no-raise + vocabulary guard on rendered output."""

import json
from datetime import datetime, timezone


def _verdict():
    from domain.fit import FitFlag, FitVerdict

    return FitVerdict(
        ticker="NVDA",
        evidence_grade="STRONG",
        fit_flags=(
            FitFlag("BETA_AMPLIFY", "deepens the market bet", "WARNING"),
            FitFlag("CONCENTRATION", "would be your #4 position", "INFO"),
        ),
        summary="NVDA sits in the top fifth of the screened universe.",
    )


def test_render_fit_card_no_raise():
    from adapters.visualization.tabs.stock_analysis import _render_fit_card

    _render_fit_card(_verdict(), screen_as_of="2026-06-13")


def test_fit_card_source_has_no_forbidden_words():
    import inspect

    from adapters.visualization.tabs import stock_analysis
    from domain.fit import FORBIDDEN_WORDS

    src = inspect.getsource(stock_analysis._render_fit_card).lower()
    for word in FORBIDDEN_WORDS:
        assert word not in src, f"forbidden word {word!r} in fit card source"


def test_severity_tone_mapping_complete():
    from adapters.visualization.tabs.stock_analysis import _SEVERITY_CLASS

    assert _SEVERITY_CLASS == {
        "INFO": "verdict-neutral",
        "CAUTION": "verdict-caution",
        "WARNING": "verdict-negative",
    }
```

- [ ] **Step 3: Run to verify failure** — ImportError on `_render_fit_card`.

- [ ] **Step 4: Implement.** In `tabs/stock_analysis.py`:

Add imports at the top:

```python
from domain.fit import FitVerdict
```

Add module-level constant and the card renderer (place after `_render_verdict`):

```python
_SEVERITY_CLASS = {
    "INFO": "verdict-neutral",
    "CAUTION": "verdict-caution",
    "WARNING": "verdict-negative",
}


def _render_fit_card(verdict: FitVerdict, screen_as_of: str | None = None) -> None:
    """Evidence grade + fit flags. Descriptive arithmetic only — never a forecast."""
    from adapters.visualization.components.formatters import grade_badge_html

    stale = f" · screen as of {screen_as_of}" if screen_as_of else ""
    st.markdown(
        f'<div class="ws-card" style="padding:12px 16px;margin-bottom:12px;">'
        f'{grade_badge_html(verdict.evidence_grade)} '
        f'<span style="font-weight:700;">Evidence + fit vs your book</span>'
        f'<span style="color:#64748B;font-size:12px;">{stale}</span>'
        f'<div style="font-size:14px;margin-top:8px;">{verdict.summary}</div>'
        "</div>",
        unsafe_allow_html=True,
    )
    for flag in verdict.fit_flags:
        css = _SEVERITY_CLASS.get(flag.severity, "verdict-neutral")
        st.markdown(
            f'<div class="verdict-card {css}">'
            f'<div style="font-size:14px;color:#111827;">{flag.message}</div>'
            "</div>",
            unsafe_allow_html=True,
        )
    st.caption(
        "Evidence + fit only — this tool does not forecast returns "
        "(see Falsification Lab). Position weights are by cost basis."
    )
```

Wire into `render()` — directly after the `_render_verdict(result)` call (~line 79):

```python
        _render_verdict(result)
        try:
            from datetime import datetime, timezone

            from application.fit_use_case import (
                default_beta_fn,
                gather_and_assess,
                market_systematic_share_threshold,
            )

            fit = gather_and_assess(
                ticker=lookup_key,
                reports_dir="data/reports",
                summary_path="data/personal/brief_summary.json",
                holdings_path="data/personal/holdings.csv",
                beta_fn=default_beta_fn,
                as_of=datetime.now(timezone.utc),
                systematic_share_threshold=market_systematic_share_threshold(),
            )
            _render_fit_card(fit)
        except Exception:
            st.caption("Fit verdict unavailable (see logs).")
```

NOTE to implementer: verify the real holdings CSV path used elsewhere
(`grep -rn "holdings" application/cli.py | grep "data/personal"` — use the same
default path the weekly-brief command uses, not a guess). The fit card computes a
live beta (a few price fetches) only when the user runs an analysis — the sanctioned
live tab.

- [ ] **Step 5: Run tests green**

Run: `python -m pytest tests/test_fit_card.py tests/test_phase54_integration.py -q`
Expected: all pass (fit card tests + the existing verdict regression stays green)

- [ ] **Step 6: Commit**

```bash
git add adapters/visualization/components/styles.py adapters/visualization/tabs/stock_analysis.py tests/test_fit_card.py
git commit -m "feat: portfolio-fit verdict card in Stock Analysis tab"
```

---

### Task 5: `docs/HYPOTHESIS_BACKLOG.md` — alpha-hunt keepalive

**Files:**
- Create: `docs/HYPOTHESIS_BACKLOG.md`

- [ ] **Step 1: Create the file** with exactly this content:

```markdown
# Hypothesis Backlog — the hunt stays disciplined, not dead

> ADR-052 closed backtest-driven alpha hunting permanently. This backlog is the ONLY
> sanctioned path for future predictive ideas: an idea may graduate to code ONLY
> after every field below is filled in and committed BEFORE any data is examined.
> Forward evidence (gate, adherence, screen IC) accrues regardless — read it before
> proposing anything here.

## Entry bar (all fields mandatory, committed before code)

| Field | Requirement |
|---|---|
| Hypothesis | One falsifiable sentence ("X predicts Y over horizon H") |
| Pre-registered thresholds | Exact pass/fail numbers, locked in an ADR |
| Kill condition | What result kills it permanently (no re-runs, no tuning) |
| Data cost | Sources, fetch budget, point-in-time feasibility |
| Conflict check | Must not violate ADR-052 scope or wrap-plan §5 (no online learning) |

## Parked ideas

### Unit D — realized-slippage measurement (parked by wrap plan §6)
- **Hypothesis:** realized execution cost on sub-$1B names is materially below the
  assumed 150 bps, enough to flip Unit B's net verdict.
- **Preconditions if ever revived:** Unit B INCONCLUSIVE with gross CI_low > 0
  (NOT met — final verdict was INCONCLUSIVE_THIN_COVERAGE → practical KILL);
  pre-registered order budget and plan; measured cost < gross edge required.
- **Status:** PARKED. Preconditions currently fail — listed for honesty, not intent.

### Correlation-vs-book fit input (deferred from fit verdict, 2026-06-11)
- **Hypothesis:** none — this is descriptive arithmetic (pairwise return correlation
  of a candidate vs current holdings), not a predictive claim.
- **Why parked:** medium build cost vs weekend wrap deadline; needs price-history
  fan-out per holding.
- **Entry path:** ordinary feature work post-wrap (no pre-registration needed —
  descriptive), budgeted under the ~1 hr/quarter maintenance allowance.
```

- [ ] **Step 2: Commit**

```bash
git add docs/HYPOTHESIS_BACKLOG.md
git commit -m "docs: hypothesis backlog — pre-registration entry bar, Unit D parked"
```

---

### Task 6: README rewrite — the family-readable front door

**Files:**
- Modify: `README.md` (full restructure per spec §6)
- Modify: `docs/SKILL_ROUTING.md` (add maintenance-mode row)

- [ ] **Step 1: Read the current README fully** (`README.md`) — preserve accurate
operational content (setup, commands, test badge), discard stale prediction-era
claims. Cross-check the test count badge against the final suite count.

- [ ] **Step 2: Restructure to exactly this section order** (spec §6):

1. **What this is** — 3 sentences, family-readable. Pattern: "A weekly research
   cockpit for one family's portfolio. It flags risk concentrations, tracks whether
   we follow our own discipline rules, and ranks stocks by factual evidence. It does
   NOT predict returns — we tested that for 18 years of data and every idea failed."
2. **The verdict table** — one row per hypothesis, phrased as plain questions:

```markdown
| Question | Answer | How we know |
|---|---|---|
| Does community conviction predict returns? | No | Pre-registered out-of-sample backtest, 2006–2024 ([ADR-039](docs/adr/039-conviction-validation-findings.md)) |
| Do conviction sub-dimensions carry signal? | No | Dimension-by-dimension IC audit ([ADR-043](docs/adr/043-conviction-dims-dead-divergence-led-surfacing.md)) |
| Does sentiment-vs-price divergence predict returns? | No | Cross-sectional IC, clean 430-ticker universe ([ADR-044](docs/adr/044-divergence-ic-verdict.md)) |
| Do momentum exits beat buy-and-hold? | No | Sharpe-difference bootstrap, CI spans zero ([ADR-046](docs/adr/046-momentum-discipline-phase1-verdict.md)) |
| Does the evidence screen's top decile outperform? | Unproven | Forward IC test, still accruing ([ADR-049](docs/adr/049-decision-support-engine-architecture.md)) |
| Does a trend-following sleeve clear its bar? | Unproven | Pre-registered backtest vs locked gate ([ADR-050](docs/adr/050-trend-following-sleeve-verdict.md)) |
| Do insider buying clusters predict returns? | Can't tell — too little clean data (treated as No) | Event study with survivorship-honest coverage guard ([ADR-053](docs/adr/053-insider-cluster-falsification-verdict.md)) |
| Does the discipline tool beat your own behavior? | Verdict ~mid-July 2026 | Live forward gate, thresholds locked in advance ([ADR-048](docs/adr/048-discipline-forward-calibration-gate.md), [ADR-051](docs/adr/051-calibration-readiness-date-diversity.md)) |
```

(ADR-048 filename verified 2026-06-11: `048-discipline-forward-calibration-gate.md`.)

3. **What the tool DOES do** — weekly brief, risk scrubber, fit verdict, discipline
   tracker, falsification lab. One sentence each, plain English.
4. **How to run it** — dashboard (`streamlit run adapters/visualization/dashboard.py`),
   Saturday job (`scripts/discipline_weekly_review.sh`), weekly-brief CLI. ≤5 lines.
5. **Glossary** — reuse the Methodology tab's table (`tabs/methodology.py` `_BODY`)
   as the source; keep the two in sync verbatim.
6. **Architecture** — hexagonal diagram (keep the existing ASCII art if present),
   link to `AGENTS.md`.
7. **The story** — 3–6 paragraphs: what was attempted, what died, why the kills are
   trustworthy (pre-registration, point-in-time, costs included), what survives.
   Family-readable.

- [ ] **Step 3: Add maintenance row to `docs/SKILL_ROUTING.md`** phase table:

```markdown
| Maintenance (post-close) | project closed | read-only; `systematic-debugging` ONLY on breakage; ~1 hr/quarter budget | Sonnet |
```

(Check the existing table — if a Maintenance row already exists, update its gate
text to "project closed" instead of adding a duplicate.)

- [ ] **Step 4: §5.5 test of done.** Re-read the README start to finish as a
non-financial reader: can they answer (a) what did this project try, (b) what did it
find, (c) why is the finding trustworthy — from the README alone? Fix any jargon
found (every finance/stats term defined on first use).

- [ ] **Step 5: Commit**

```bash
git add README.md docs/SKILL_ROUTING.md
git commit -m "docs: family-readable README — verdict table, glossary, the story"
```

---

### Task 7: Final verification + STATUS + PR

- [ ] **Step 1: Full suite** — `python -m pytest tests/ -q 2>&1 | tail -3` — no
failures; record the new count (baseline 1561 + Tasks 1–4 additions).
- [ ] **Step 2: Pre-commit** — `pre-commit run --all-files` → all pass.
- [ ] **Step 3: Smoke the tab** — `streamlit run adapters/visualization/dashboard.py`,
open Stock Analysis, run one ticker (e.g. AAPL): fit card renders below the RESEARCH
ONLY banner; with artifacts missing it shows DATA_GAP captions, not a crash.
- [ ] **Step 4: Overwrite `docs/STATUS.md`** (~40 lines max): phase = "Wrap — fit
verdict shipped, docs final"; next action = "close project: develop → main release
PR"; the two calendar dates (mid-July gate read, Dec self-experiment review); final
test count.
- [ ] **Step 5: Commit + PR**

```bash
git add docs/STATUS.md
git commit -m "docs: session-end STATUS — fit verdict + docs wrap complete"
git push -u origin feat/portfolio-fit-verdict
gh pr create --base develop --title "feat: portfolio-fit verdict + family-readable docs wrap" --body "Phase 6: honest fit verdict (evidence grade + fit arithmetic, vocabulary-guarded), top_concentration market-value fix, hypothesis backlog, family-readable README. Spec: docs/superpowers/specs/2026-06-11-phase6-fit-verdict-wrap-design.md"
```

- [ ] **Step 6:** After CI green + merge: release PR develop → main, then final
STATUS overwrite on develop marking the project CLOSED.

---

## Self-review (against spec, 2026-06-11)

- **Spec coverage:** §2 honest boundary → T1 FORBIDDEN_WORDS + card caption; §3 domain
  rules/invariants → T1 (signature simplified to primitives — plan amendment 2); §4
  orchestration → T3 (artifact-driven — plan amendment 1, rationale recorded); §5 UI +
  severity→tone map + verdict-caution CSS → T4; §6 information architecture → T6; §5
  (spec §1) HYPOTHESIS_BACKLOG → T5; top_concentration bug (spec §3 note) → T2;
  STATUS/close → T7. Correlation input explicitly parked (T5 backlog entry).
- **Placeholders:** Two intentional NOTE-to-implementer anchors (holdings CSV column
  names, ADR-048 filename) — both carry exact verification commands, not hand-waves.
- **Type consistency:** `assess_fit` signature in T1 matches the T3 call site
  keyword-for-keyword; `FitVerdict`/`FitFlag` fields consistent across T1/T3/T4 tests;
  `_SEVERITY_CLASS` keys = FitFlag severities used in T1.
```
