# Corroboration Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a free-tier, RESEARCH_ONLY corroboration engine that harvests credible stock recommendations (real citations from a search API), verifies them, stress-tests each name against existing project signals, and emits per-ticker `CorroboratedCandidate` + theme/sector `DirectionalView`.

**Architecture:** Hexagonal. Pure domain `CorroborationService` computes a transparent convergence tier from verified attributed claims + existing signals. Adapters handle harvest (decoupled Search→LLM), citation verification, model discovery, and SQLite persistence. No prediction claim; predictive validity is deferred to forward-only Hypothesis #9 (separate sub-project).

**Tech Stack:** Python 3.12, dataclasses (stdlib-only domain), pytest + Hypothesis, SQLite, free search APIs (Tavily/Brave/DDG), free LLMs (Gemini/Groq via a self-updating registry). Spec: `docs/superpowers/specs/2026-06-20-corroboration-engine-design.md`.

---

## File structure

| File | Responsibility |
|------|----------------|
| `domain/corroboration_models.py` | `Stance`, `ConvergenceTier`, `TrendHealth` enums; `HarvestedClaim`, `OurReadout`, `Agreement`, `Uncertainty`, `CorroboratedCandidate`, `DirectionalView` dataclasses |
| `domain/corroboration_service.py` | Pure tier math (§6 spec): claims + readout → `CorroboratedCandidate`; rollup → `DirectionalView` |
| `domain/ports.py` (modify) | Add `RecommendationHarvestPort`, `CitationVerifierPort`, `ModelProviderPort` protocols |
| `adapters/data/citation_verifier.py` | Fetch URL, confirm 200 + names ticker → verified bool |
| `adapters/ml/model_registry.py` | Discover free models per wired provider; cached preferred order |
| `adapters/data/search_harvester.py` | Free search API → real result URLs (Tavily→Brave→DDG) |
| `adapters/ml/llm_summarizer.py` | Fetched page text → stance + attributed thesis (registry-driven) |
| `adapters/data/corroboration_store.py` | SQLite `harvested_recs` + `corroboration_runs` |
| `application/corroboration_use_case.py` | Orchestrate harvest→verify→corroborate→persist |
| `application/cli/corroboration_commands.py` | `corroborate` CLI command |
| `tests/fakes/corroboration_fakes.py` | Fake harvester, verifier, model provider |
| `tests/test_corroboration_*.py` | Tests per component |

---

## Task 1: Domain enums + dataclasses

**Files:**
- Create: `domain/corroboration_models.py`
- Test: `tests/test_corroboration_models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_corroboration_models.py
from datetime import date
from domain.corroboration_models import (
    Stance, ConvergenceTier, TrendHealth, HarvestedClaim,
)

def test_harvested_claim_is_frozen_and_carries_attribution():
    claim = HarvestedClaim(
        source_name="Morningstar", ticker="NVDA", stance=Stance.BULLISH,
        thesis_summary="5-star, AI demand durable", url="https://x/y",
        published_at=date(2026, 6, 18), verified=True, reliability_weight=0.7,
    )
    assert claim.stance is Stance.BULLISH
    assert claim.verified is True
    assert 0.0 <= claim.reliability_weight <= 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_corroboration_models.py -q`
Expected: FAIL — `ModuleNotFoundError: domain.corroboration_models`

- [ ] **Step 3: Write minimal implementation**

```python
# domain/corroboration_models.py
"""Domain types for the corroboration engine. Stdlib-only (hexagonal rule)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum


class Stance(Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class ConvergenceTier(Enum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    CONFLICTED = "conflicted"
    NONE = "none"


class TrendHealth(Enum):
    HEALTHY = "healthy"
    CAUTION = "caution"
    BROKEN = "broken"


@dataclass(frozen=True)
class HarvestedClaim:
    source_name: str
    ticker: str
    stance: Stance
    thesis_summary: str
    url: str
    published_at: date
    verified: bool
    reliability_weight: float
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_corroboration_models.py -q`
Expected: PASS

- [ ] **Step 5: Add the remaining dataclasses**

Append to `domain/corroboration_models.py`:

```python
@dataclass(frozen=True)
class OurReadout:
    factor_percentile: float | None          # 0-100, our EvidenceScreen rank
    trend_health: TrendHealth | None
    divergence_flag: bool
    discipline_flag: str | None              # "REDUCE"/"HOLD"/"ADD_OK" if held


@dataclass(frozen=True)
class Agreement:
    n_bullish: int
    n_bearish: int
    weighted_score: float                    # [-1, 1]
    our_alignment: str                       # "AGREES"/"DIVERGES"/"NEUTRAL"


@dataclass(frozen=True)
class Uncertainty:
    coverage_n: int
    conflict: bool
    freshness_days: int                      # age of newest source vs as_of


@dataclass(frozen=True)
class CorroboratedCandidate:
    ticker: str
    as_of: date
    sources: tuple[HarvestedClaim, ...]
    our_readout: OurReadout
    convergence: ConvergenceTier
    agreement: Agreement
    uncertainty: Uncertainty
    held: bool
    verification: str                        # "ALL_VERIFIED"/"PARTIAL"/"NONE_DROPPED"


@dataclass(frozen=True)
class DirectionalView:
    group_kind: str                          # "theme" or "sector"
    group_name: str
    net_stance: Stance
    mean_convergence: float                   # 0-1 numeric tier mean
    your_exposure_pct: float
    evidence_weight_pct: float
    tilt: str                                # "LEAN_IN"/"HOLD"/"LEAN_OUT"/"AVOID"
```

- [ ] **Step 6: Run + commit**

Run: `pytest tests/test_corroboration_models.py -q` → PASS
```bash
git add domain/corroboration_models.py tests/test_corroboration_models.py
git commit -m "feat(corroboration): domain enums + dataclasses"
```

---

## Task 2: CorroborationService — convergence tier math (§6, pure)

**Files:**
- Create: `domain/corroboration_service.py`
- Test: `tests/test_corroboration_service.py`

This is the honesty core. Implement the §6 tier table exactly. TDD each branch.

- [ ] **Step 1: Write failing tests for weighted_score + the STRONG branch**

```python
# tests/test_corroboration_service.py
from datetime import date
from domain.corroboration_models import (
    Stance, ConvergenceTier, TrendHealth, HarvestedClaim, OurReadout,
)
from domain.corroboration_service import CorroborationService

def _claim(src, stance, w, ticker="NVDA"):
    return HarvestedClaim(src, ticker, stance, "why", "https://u",
                          date(2026, 6, 18), True, w)

def _readout(pct=5.0, trend=TrendHealth.HEALTHY, div=False, disc=None):
    return OurReadout(pct, trend, div, disc)

def test_three_bull_sources_plus_our_agreement_is_strong():
    svc = CorroborationService()
    claims = [_claim("A", Stance.BULLISH, 0.8),
              _claim("B", Stance.BULLISH, 0.7),
              _claim("C", Stance.BULLISH, 0.6)]
    cand = svc.corroborate("NVDA", date(2026, 6, 20), claims,
                           _readout(pct=5.0), held=True)
    assert cand.agreement.weighted_score > 0.9
    assert cand.agreement.our_alignment == "AGREES"
    assert cand.convergence is ConvergenceTier.STRONG
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_corroboration_service.py -q`
Expected: FAIL — `ModuleNotFoundError: domain.corroboration_service`

- [ ] **Step 3: Implement the service**

```python
# domain/corroboration_service.py
"""Pure corroboration tier math. Stdlib-only. See spec §6/§7."""
from __future__ import annotations

from datetime import date

from domain.corroboration_models import (
    Agreement, ConvergenceTier, CorroboratedCandidate, HarvestedClaim,
    OurReadout, Stance, TrendHealth, Uncertainty,
)

_SIGN = {Stance.BULLISH: 1, Stance.BEARISH: -1, Stance.NEUTRAL: 0}


class CorroborationService:
    """Combine verified attributed claims + our own signals into a tier."""

    def corroborate(
        self,
        ticker: str,
        as_of: date,
        claims: list[HarvestedClaim],
        readout: OurReadout,
        held: bool,
    ) -> CorroboratedCandidate:
        verified = [c for c in claims if c.verified]
        agreement = self._agreement(verified, readout)
        uncertainty = self._uncertainty(verified, as_of)
        tier = self._tier(agreement, uncertainty)
        verification = (
            "NONE_DROPPED" if not verified
            else "ALL_VERIFIED" if len(verified) == len(claims)
            else "PARTIAL"
        )
        return CorroboratedCandidate(
            ticker=ticker, as_of=as_of, sources=tuple(verified),
            our_readout=readout, convergence=tier, agreement=agreement,
            uncertainty=uncertainty, held=held, verification=verification,
        )

    def _agreement(self, verified: list[HarvestedClaim], r: OurReadout) -> Agreement:
        wsum = sum(c.reliability_weight for c in verified)
        score = (
            sum(_SIGN[c.stance] * c.reliability_weight for c in verified) / wsum
            if wsum > 0 else 0.0
        )
        n_bull = sum(1 for c in verified if c.stance is Stance.BULLISH)
        n_bear = sum(1 for c in verified if c.stance is Stance.BEARISH)
        align = self._alignment(score, r)
        return Agreement(n_bull, n_bear, score, align)

    def _alignment(self, score: float, r: OurReadout) -> str:
        # Our directional read: healthy+top-decile = bullish lean; broken = bearish.
        our_sign = 0
        if r.trend_health is TrendHealth.HEALTHY and (r.factor_percentile or 100) <= 25:
            our_sign = 1
        elif r.trend_health is TrendHealth.BROKEN:
            our_sign = -1
        if our_sign == 0:
            return "NEUTRAL"
        if (score > 0 and our_sign > 0) or (score < 0 and our_sign < 0):
            return "AGREES"
        return "DIVERGES"

    def _uncertainty(self, verified: list[HarvestedClaim], as_of: date) -> Uncertainty:
        n = len(verified)
        has_bull = any(c.stance is Stance.BULLISH for c in verified)
        has_bear = any(c.stance is Stance.BEARISH for c in verified)
        freshness = (
            min((as_of - c.published_at).days for c in verified) if verified else 9999
        )
        return Uncertainty(coverage_n=n, conflict=(has_bull and has_bear),
                           freshness_days=freshness)

    def _tier(self, a: Agreement, u: Uncertainty) -> ConvergenceTier:
        s = a.weighted_score
        if u.coverage_n == 0:
            return ConvergenceTier.NONE
        if u.conflict and abs(s) < 0.2:
            return ConvergenceTier.CONFLICTED
        if abs(s) >= 0.5 and u.coverage_n >= 3:
            if a.our_alignment == "DIVERGES":
                return ConvergenceTier.CONFLICTED
            if a.our_alignment == "AGREES":
                return ConvergenceTier.STRONG
            return ConvergenceTier.MODERATE
        if 0.2 <= abs(s) < 0.5 and u.coverage_n >= 2 and a.our_alignment != "DIVERGES":
            return ConvergenceTier.MODERATE
        return ConvergenceTier.WEAK
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_corroboration_service.py -q`
Expected: PASS

- [ ] **Step 5: Add a test per remaining tier branch + Hypothesis invariants**

```python
from hypothesis import given, strategies as st

def test_diverges_yields_conflicted_even_when_sources_strong():
    svc = CorroborationService()
    claims = [_claim("A", Stance.BULLISH, 0.9), _claim("B", Stance.BULLISH, 0.9),
              _claim("C", Stance.BULLISH, 0.9)]
    cand = svc.corroborate("NVDA", date(2026, 6, 20), claims,
                           _readout(trend=TrendHealth.BROKEN), held=False)
    assert cand.convergence is ConvergenceTier.CONFLICTED

def test_no_verified_sources_is_none():
    svc = CorroborationService()
    unverified = HarvestedClaim("A", "NVDA", Stance.BULLISH, "w", "https://u",
                                date(2026, 6, 18), False, 0.5)
    cand = svc.corroborate("NVDA", date(2026, 6, 20), [unverified],
                           _readout(), held=False)
    assert cand.convergence is ConvergenceTier.NONE
    assert cand.verification == "NONE_DROPPED"

def test_conflicting_sources_near_zero_is_conflicted():
    svc = CorroborationService()
    claims = [_claim("A", Stance.BULLISH, 0.5), _claim("B", Stance.BEARISH, 0.5)]
    cand = svc.corroborate("NVDA", date(2026, 6, 20), claims, _readout(), held=False)
    assert cand.convergence is ConvergenceTier.CONFLICTED

@given(w=st.floats(min_value=0.01, max_value=1.0))
def test_all_bearish_never_strong_bull(w):
    svc = CorroborationService()
    claims = [_claim("A", Stance.BEARISH, w), _claim("B", Stance.BEARISH, w),
              _claim("C", Stance.BEARISH, w)]
    cand = svc.corroborate("NVDA", date(2026, 6, 20), claims,
                           _readout(trend=TrendHealth.HEALTHY), held=False)
    assert cand.agreement.weighted_score < 0
```

- [ ] **Step 6: Run + commit**

Run: `pytest tests/test_corroboration_service.py -q` → PASS
```bash
git add domain/corroboration_service.py tests/test_corroboration_service.py
git commit -m "feat(corroboration): pure convergence-tier service + invariant tests"
```

---

## Task 3: DirectionalView rollup

**Files:**
- Modify: `domain/corroboration_service.py` (add `roll_up`)
- Test: `tests/test_corroboration_directional.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_corroboration_directional.py
from datetime import date
from domain.corroboration_models import (
    Stance, ConvergenceTier, TrendHealth, HarvestedClaim, OurReadout,
)
from domain.corroboration_service import CorroborationService

def _cand(svc, ticker, stance):
    c = HarvestedClaim("A", ticker, stance, "w", "https://u", date(2026, 6, 18), True, 0.8)
    return svc.corroborate(ticker, date(2026, 6, 20), [c, c, c],
                           OurReadout(5.0, TrendHealth.HEALTHY, False, None), held=False)

def test_rollup_groups_by_theme_and_flags_underexposed_lean_in():
    svc = CorroborationService()
    cands = [_cand(svc, "NVDA", Stance.BULLISH), _cand(svc, "AMD", Stance.BULLISH)]
    themes = {"ai_infra": ["NVDA", "AMD"]}
    exposure = {"ai_infra": 2.0}     # only 2% of book in a strongly-corroborated theme
    views = svc.roll_up(cands, themes, exposure)
    ai = next(v for v in views if v.group_name == "ai_infra")
    assert ai.net_stance is Stance.BULLISH
    assert ai.tilt == "LEAN_IN"
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_corroboration_directional.py -q`
Expected: FAIL — `AttributeError: 'CorroborationService' object has no attribute 'roll_up'`

- [ ] **Step 3: Implement `roll_up`**

Append to `domain/corroboration_service.py`:

```python
from domain.corroboration_models import DirectionalView

_TIER_NUM = {
    ConvergenceTier.STRONG: 1.0, ConvergenceTier.MODERATE: 0.6,
    ConvergenceTier.WEAK: 0.3, ConvergenceTier.CONFLICTED: 0.1,
    ConvergenceTier.NONE: 0.0,
}

    # (method on CorroborationService — keep indentation)
    def roll_up(self, candidates, groups, exposure_pct, group_kind="theme"):
        views = []
        by_ticker = {c.ticker: c for c in candidates}
        for name, tickers in groups.items():
            members = [by_ticker[t] for t in tickers if t in by_ticker]
            if not members:
                continue
            mean_conv = sum(_TIER_NUM[m.convergence] for m in members) / len(members)
            net = sum(m.agreement.weighted_score for m in members) / len(members)
            net_stance = (Stance.BULLISH if net > 0.1 else
                          Stance.BEARISH if net < -0.1 else Stance.NEUTRAL)
            yours = exposure_pct.get(name, 0.0)
            ev_weight = mean_conv * 100.0
            tilt = self._tilt(net_stance, mean_conv, yours, ev_weight)
            views.append(DirectionalView(
                group_kind=group_kind, group_name=name, net_stance=net_stance,
                mean_convergence=mean_conv, your_exposure_pct=yours,
                evidence_weight_pct=ev_weight, tilt=tilt))
        return views

    def _tilt(self, net_stance, mean_conv, yours, ev_weight):
        if net_stance is Stance.BEARISH and mean_conv >= 0.6:
            return "LEAN_OUT" if yours > 0 else "AVOID"
        if net_stance is Stance.BULLISH and mean_conv >= 0.6 and yours < ev_weight * 0.5:
            return "LEAN_IN"
        return "HOLD"
```

Note: move the `_TIER_NUM` dict to module top with the other module-level constants; the `roll_up`
and `_tilt` defs are methods — paste them inside the `CorroborationService` class body.

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_corroboration_directional.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add domain/corroboration_service.py tests/test_corroboration_directional.py
git commit -m "feat(corroboration): theme/sector DirectionalView rollup"
```

---

## Task 4: Ports + fakes

**Files:**
- Modify: `domain/ports.py`
- Create: `tests/fakes/corroboration_fakes.py`
- Test: `tests/test_corroboration_fakes.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_corroboration_fakes.py
from datetime import date
from tests.fakes.corroboration_fakes import FakeHarvester, FakeVerifier

def test_fake_harvester_returns_seeded_claims():
    h = FakeHarvester(seed_tickers=["NVDA"])
    claims = h.harvest(date(2026, 6, 20))
    assert claims and claims[0].ticker == "NVDA"

def test_fake_verifier_marks_known_url_verified():
    v = FakeVerifier(good_urls={"https://good"})
    assert v.verify("https://good", "NVDA") is True
    assert v.verify("https://bad", "NVDA") is False
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_corroboration_fakes.py -q`
Expected: FAIL — `ModuleNotFoundError: tests.fakes.corroboration_fakes`

- [ ] **Step 3: Add protocols + fakes**

Append to `domain/ports.py`:

```python
from datetime import date as _date
from typing import Protocol
from domain.corroboration_models import HarvestedClaim


class RecommendationHarvestPort(Protocol):
    def harvest(self, as_of: _date) -> list[HarvestedClaim]: ...


class CitationVerifierPort(Protocol):
    def verify(self, url: str, ticker: str) -> bool: ...


class ModelProviderPort(Protocol):
    def list_free_models(self) -> list[str]: ...
    def summarize(self, model: str, page_text: str, ticker: str) -> tuple[str, str]:
        """Return (stance_str, thesis_summary)."""
        ...
```

Create `tests/fakes/corroboration_fakes.py`:

```python
from __future__ import annotations
from datetime import date
from domain.corroboration_models import HarvestedClaim, Stance


class FakeHarvester:
    def __init__(self, seed_tickers):
        self._tickers = seed_tickers

    def harvest(self, as_of: date) -> list[HarvestedClaim]:
        return [HarvestedClaim(f"src-{t}", t, Stance.BULLISH, "seeded why",
                               f"https://good/{t}", as_of, True, 0.6)
                for t in self._tickers]


class FakeVerifier:
    def __init__(self, good_urls):
        self._good = set(good_urls)

    def verify(self, url: str, ticker: str) -> bool:
        return url in self._good


class FakeModelProvider:
    def __init__(self, models, stance="bullish", thesis="fake thesis"):
        self._models = models
        self._stance = stance
        self._thesis = thesis

    def list_free_models(self):
        return list(self._models)

    def summarize(self, model, page_text, ticker):
        return self._stance, self._thesis
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_corroboration_fakes.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add domain/ports.py tests/fakes/corroboration_fakes.py tests/test_corroboration_fakes.py
git commit -m "feat(corroboration): ports + test fakes"
```

---

## Task 5: ModelRegistry (self-updating free-model discovery)

**Files:**
- Create: `adapters/ml/model_registry.py`
- Test: `tests/test_model_registry.py`

**Build-time probe (do first, record result in commit body):** run
`python -c "import google.generativeai as g; g.configure(api_key=__import__('os').environ['GEMINI_API_KEY']); print([m.name for m in g.list_models()][:10])"`
to confirm the `list_models()` shape. If it differs, adjust `_gemini_free` parsing.

- [ ] **Step 1: Write the failing test (registry ranks + drops deprecated, no network)**

```python
# tests/test_model_registry.py
from adapters.ml.model_registry import ModelRegistry

def test_registry_prefers_newer_and_drops_unavailable():
    # injected lister simulates a provider's list-models endpoint
    available = ["gemini-2.5-flash", "gemini-3.0-flash", "gemini-2.0-flash"]
    reg = ModelRegistry(listers={"gemini": lambda: available},
                        deprecated={"gemini-2.0-flash"})
    order = reg.preferred("gemini")
    assert order[0] == "gemini-3.0-flash"          # newest ranked first
    assert "gemini-2.0-flash" not in order          # deprecated dropped
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_model_registry.py -q`
Expected: FAIL — `ModuleNotFoundError: adapters.ml.model_registry`

- [ ] **Step 3: Implement (dependency-injected listers → testable, no live calls in test)**

```python
# adapters/ml/model_registry.py
"""Self-updating free-model discovery. Polls wired providers' list endpoints,
ranks by version recency, drops deprecated. Availability not quality (spec §7b)."""
from __future__ import annotations

import re
from typing import Callable


def _version_key(name: str) -> tuple:
    nums = [int(n) for n in re.findall(r"\d+", name)]
    return tuple(nums) or (0,)


class ModelRegistry:
    def __init__(self, listers: dict[str, Callable[[], list[str]]],
                 deprecated: set[str] | None = None):
        self._listers = listers
        self._deprecated = deprecated or set()

    def preferred(self, provider: str) -> list[str]:
        try:
            models = self._listers[provider]()
        except Exception:
            return []
        live = [m for m in models if m not in self._deprecated]
        return sorted(live, key=_version_key, reverse=True)
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_model_registry.py -q`
Expected: PASS

- [ ] **Step 5: Add the live Gemini lister + cache (covered by a guarded test)**

Append a `gemini_lister()` module function that lazily imports `google.generativeai`, calls
`list_models()`, keeps names containing `flash` (free family), and a `cached_preferred()` that reads/writes
`data/cache/model_registry.json` with a 7-day TTL using an injected `now` + `read_text`/`write_text` so the
TTL logic is unit-tested without real time or disk. Test the TTL branch with a fake clock (mirror the
yfinance throttle test pattern on `fix/yfinance-throttle`).

- [ ] **Step 6: Commit**

```bash
git add adapters/ml/model_registry.py tests/test_model_registry.py
git commit -m "feat(corroboration): self-updating ModelRegistry (availability-ranked)"
```

---

## Task 6: CitationVerifier

**Files:**
- Create: `adapters/data/citation_verifier.py`
- Test: `tests/test_citation_verifier.py`

- [ ] **Step 1: Write the failing test (injected fetcher → no network)**

```python
# tests/test_citation_verifier.py
from adapters.data.citation_verifier import CitationVerifier

def test_verified_when_page_resolves_and_names_ticker():
    fetch = lambda url: (200, "NVIDIA (NVDA) raised to 5 stars")
    v = CitationVerifier(fetcher=fetch, name_map={"NVDA": ["NVIDIA"]})
    assert v.verify("https://x", "NVDA") is True

def test_dropped_on_404():
    v = CitationVerifier(fetcher=lambda u: (404, ""), name_map={})
    assert v.verify("https://x", "NVDA") is False

def test_dropped_when_ticker_not_mentioned():
    fetch = lambda url: (200, "unrelated content")
    v = CitationVerifier(fetcher=fetch, name_map={"NVDA": ["NVIDIA"]})
    assert v.verify("https://x", "NVDA") is False
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_citation_verifier.py -q`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
# adapters/data/citation_verifier.py
"""Verify a citation resolves (HTTP 200) and names the ticker/company.
Unverified claims are dropped (spec §4). Default fetcher is throttled requests."""
from __future__ import annotations

from typing import Callable


class CitationVerifier:
    def __init__(self, fetcher: Callable[[str], tuple[int, str]],
                 name_map: dict[str, list[str]]):
        self._fetch = fetcher
        self._names = name_map

    def verify(self, url: str, ticker: str) -> bool:
        try:
            status, text = self._fetch(url)
        except Exception:
            return False
        if status != 200 or not text:
            return False
        needles = [ticker] + self._names.get(ticker, [])
        low = text.lower()
        return any(n.lower() in low for n in needles)
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_citation_verifier.py -q` → PASS

- [ ] **Step 5: Add default throttled `requests` fetcher**

Add a module function `requests_fetcher(url, timeout=10)` returning `(status_code, text)`, reusing the
min-interval throttle pattern from `adapters/data/yfinance_adapter.py` (`fix/yfinance-throttle`). Not unit-
tested against network; the injected fetcher covers logic.

- [ ] **Step 6: Commit**

```bash
git add adapters/data/citation_verifier.py tests/test_citation_verifier.py
git commit -m "feat(corroboration): citation verifier (resolve + names-ticker gate)"
```

---

## Task 7: SearchHarvester + LLMSummarizer

**Files:**
- Create: `adapters/data/search_harvester.py`, `adapters/ml/llm_summarizer.py`
- Test: `tests/test_search_harvester.py`, `tests/test_llm_summarizer.py`

**Build-time probe:** confirm a free Tavily key returns `results[].url`. If unavailable, wire Brave/DDG
first. Record which provider was used in the commit body.

- [ ] **Step 1: Failing test — harvester maps search results to candidate URLs (injected client)**

```python
# tests/test_search_harvester.py
from datetime import date
from adapters.data.search_harvester import SearchHarvester

def test_harvester_extracts_tickers_and_urls_from_results():
    client = lambda q: [{"url": "https://a/nvda", "title": "Why NVDA is a top buy",
                         "content": "NVDA strong"}]
    h = SearchHarvester(search=client, known_tickers={"NVDA"}, cap=25)
    raw = h.search_candidates(date(2026, 6, 20))
    assert any(r["ticker"] == "NVDA" and r["url"] == "https://a/nvda" for r in raw)
```

- [ ] **Step 2: Run → FAIL.** `pytest tests/test_search_harvester.py -q`

- [ ] **Step 3: Implement `SearchHarvester`**

```python
# adapters/data/search_harvester.py
"""Free search API → real, citable candidate URLs (spec §4). Search is a fact
source; the LLM never invents URLs. Provider fallback handled by the injected client."""
from __future__ import annotations

import re
from datetime import date
from typing import Callable

_QUERIES = ["stocks to buy now analyst", "best stocks to invest in this week",
            "top stock picks"]


class SearchHarvester:
    def __init__(self, search: Callable[[str], list[dict]],
                 known_tickers: set[str], cap: int = 25):
        self._search = search
        self._known = known_tickers
        self._cap = cap

    def search_candidates(self, as_of: date) -> list[dict]:
        out: list[dict] = []
        seen = set()
        for q in _QUERIES:
            try:
                results = self._search(q)
            except Exception:
                continue
            for r in results:
                text = f"{r.get('title','')} {r.get('content','')}"
                for tk in self._tickers_in(text):
                    key = (tk, r["url"])
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append({"ticker": tk, "url": r["url"], "snippet": text[:400]})
                    if len(out) >= self._cap:
                        return out
        return out

    def _tickers_in(self, text: str) -> list[str]:
        toks = set(re.findall(r"\b[A-Z]{1,5}\b", text))
        return [t for t in toks if t in self._known]
```

- [ ] **Step 4: Run → PASS.**

- [ ] **Step 5: LLMSummarizer test + impl (registry-driven, injected provider)**

```python
# tests/test_llm_summarizer.py
from adapters.ml.llm_summarizer import LLMSummarizer
from tests.fakes.corroboration_fakes import FakeModelProvider

def test_summarizer_returns_stance_and_thesis_via_first_model():
    prov = FakeModelProvider(models=["m1"], stance="bullish", thesis="durable demand")
    s = LLMSummarizer(provider=prov, preferred=["m1"])
    stance, thesis = s.summarize("NVDA strong AI demand", "NVDA")
    assert stance == "bullish" and thesis == "durable demand"
```

```python
# adapters/ml/llm_summarizer.py
"""Summarize fetched page text into (stance, attributed thesis). Model order from
ModelRegistry; falls through providers on error. Never sources a URL (spec §4)."""
from __future__ import annotations


class LLMSummarizer:
    def __init__(self, provider, preferred: list[str]):
        self._provider = provider
        self._preferred = preferred

    def summarize(self, page_text: str, ticker: str) -> tuple[str, str]:
        for model in self._preferred:
            try:
                return self._provider.summarize(model, page_text, ticker)
            except Exception:
                continue
        return "neutral", ""
```

- [ ] **Step 6: Run both → PASS, then commit**

```bash
git add adapters/data/search_harvester.py adapters/ml/llm_summarizer.py \
        tests/test_search_harvester.py tests/test_llm_summarizer.py
git commit -m "feat(corroboration): decoupled SearchHarvester + LLMSummarizer"
```

---

## Task 8: CorroborationSnapshotStore (SQLite)

**Files:**
- Create: `adapters/data/corroboration_store.py`
- Test: `tests/test_corroboration_store.py`

- [ ] **Step 1: Failing test — round-trip a run + claims via in-memory SQLite**

```python
# tests/test_corroboration_store.py
import sqlite3
from datetime import date
from domain.corroboration_models import Stance, HarvestedClaim
from adapters.data.corroboration_store import CorroborationStore

def test_save_and_load_run_roundtrips():
    conn = sqlite3.connect(":memory:")
    store = CorroborationStore(conn)
    store.init_schema()
    claim = HarvestedClaim("A", "NVDA", Stance.BULLISH, "why", "https://u",
                           date(2026, 6, 18), True, 0.7)
    run_id = store.save_run(date(2026, 6, 20), [claim])
    loaded = store.load_run(run_id)
    assert loaded[0].ticker == "NVDA" and loaded[0].verified is True
```

- [ ] **Step 2: Run → FAIL.** `pytest tests/test_corroboration_store.py -q`

- [ ] **Step 3: Implement (mirror `adapters/data/sqlite_store.py` conventions)**

```python
# adapters/data/corroboration_store.py
"""Weekly corroboration snapshots — mandatory for forward Hypothesis #9 (spec §8)."""
from __future__ import annotations

import sqlite3
from datetime import date
from domain.corroboration_models import HarvestedClaim, Stance


class CorroborationStore:
    def __init__(self, conn: sqlite3.Connection):
        self._c = conn

    def init_schema(self) -> None:
        self._c.executescript(
            """
            CREATE TABLE IF NOT EXISTS corroboration_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, as_of TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS harvested_recs (
                run_id INTEGER, source_name TEXT, ticker TEXT, stance TEXT,
                thesis TEXT, url TEXT, published_at TEXT, verified INTEGER,
                reliability_weight REAL);
            """
        )
        self._c.commit()

    def save_run(self, as_of: date, claims: list[HarvestedClaim]) -> int:
        cur = self._c.execute(
            "INSERT INTO corroboration_runs (as_of) VALUES (?)", (as_of.isoformat(),))
        run_id = int(cur.lastrowid)
        self._c.executemany(
            "INSERT INTO harvested_recs VALUES (?,?,?,?,?,?,?,?,?)",
            [(run_id, c.source_name, c.ticker, c.stance.value, c.thesis_summary,
              c.url, c.published_at.isoformat(), int(c.verified), c.reliability_weight)
             for c in claims])
        self._c.commit()
        return run_id

    def load_run(self, run_id: int) -> list[HarvestedClaim]:
        rows = self._c.execute(
            "SELECT source_name,ticker,stance,thesis,url,published_at,verified,"
            "reliability_weight FROM harvested_recs WHERE run_id=?", (run_id,)).fetchall()
        return [HarvestedClaim(r[0], r[1], Stance(r[2]), r[3], r[4],
                               date.fromisoformat(r[5]), bool(r[6]), r[7]) for r in rows]
```

- [ ] **Step 4: Run → PASS. Commit**

```bash
git add adapters/data/corroboration_store.py tests/test_corroboration_store.py
git commit -m "feat(corroboration): SQLite snapshot store (runs + harvested_recs)"
```

---

## Task 9: Use case + `corroborate` CLI command

**Files:**
- Create: `application/corroboration_use_case.py`, `application/cli/corroboration_commands.py`
- Modify: `application/cli/_cli_group.py` (register command)
- Test: `tests/test_corroboration_use_case.py`

- [ ] **Step 1: Failing test — orchestration with all fakes produces candidates + persists**

```python
# tests/test_corroboration_use_case.py
import sqlite3
from datetime import date
from application.corroboration_use_case import CorroborationUseCase
from adapters.data.corroboration_store import CorroborationStore
from tests.fakes.corroboration_fakes import FakeHarvester, FakeVerifier

def test_use_case_emits_candidates_and_persists():
    conn = sqlite3.connect(":memory:")
    store = CorroborationStore(conn); store.init_schema()
    uc = CorroborationUseCase(
        harvester=FakeHarvester(["NVDA"]),
        verifier=FakeVerifier(good_urls={"https://good/NVDA"}),
        readout_fn=lambda t, d: __import__("domain.corroboration_models",
            fromlist=["OurReadout", "TrendHealth"]).OurReadout(
            5.0, __import__("domain.corroboration_models",
            fromlist=["TrendHealth"]).TrendHealth.HEALTHY, False, None),
        held_tickers=set(), store=store)
    result = uc.execute(date(2026, 6, 20))
    assert result.candidates and result.candidates[0].ticker == "NVDA"
    assert result.run_id is not None
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement use case**

```python
# application/corroboration_use_case.py
"""Orchestrate harvest → verify → corroborate → persist (spec §4). RESEARCH_ONLY."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

from domain.corroboration_models import CorroboratedCandidate, OurReadout
from domain.corroboration_service import CorroborationService


@dataclass(frozen=True)
class CorroborationResult:
    run_id: int
    candidates: list[CorroboratedCandidate]


class CorroborationUseCase:
    def __init__(self, harvester, verifier, readout_fn: Callable[[str, date], OurReadout],
                 held_tickers: set[str], store, service: CorroborationService | None = None):
        self._harvester = harvester
        self._verifier = verifier
        self._readout_fn = readout_fn
        self._held = held_tickers
        self._store = store
        self._svc = service or CorroborationService()

    def execute(self, as_of: date) -> CorroborationResult:
        # Point-in-time guard (spec §9): drop any claim published after as_of.
        claims = [c for c in self._harvester.harvest(as_of) if c.published_at <= as_of]
        verified = [
            __import__("dataclasses").replace(
                c, verified=self._verifier.verify(c.url, c.ticker))
            for c in claims
        ]
        run_id = self._store.save_run(as_of, verified)
        by_ticker: dict[str, list] = {}
        for c in verified:
            by_ticker.setdefault(c.ticker, []).append(c)
        cands = [
            self._svc.corroborate(t, as_of, cs, self._readout_fn(t, as_of),
                                  held=(t in self._held))
            for t, cs in by_ticker.items()
        ]
        return CorroborationResult(run_id=run_id, candidates=cands)
```

- [ ] **Step 4: Run → PASS.**

- [ ] **Step 5: Add the CLI command** (mirror `application/cli/*_commands.py`)

Create `application/cli/corroboration_commands.py` with a `@cli.command("corroborate")` that builds real
adapters (SearchHarvester+LLMSummarizer via ModelRegistry, CitationVerifier with `requests_fetcher`,
`readout_fn` calling the existing `EvidenceScreenUseCase`/trend signals), runs the use case, and prints each
`CorroboratedCandidate` (ticker, tier, sources w/ URLs, our_readout) + `DirectionalView` under a bold
`RESEARCH_ONLY — attributed evidence, not a forecast` banner. Register it in `_cli_group.py` import list.

Manual smoke (real, gated by keys): `python -m application.cli corroborate --date 2026-06-20`.

- [ ] **Step 6: Commit**

```bash
git add application/corroboration_use_case.py application/cli/corroboration_commands.py \
        application/cli/_cli_group.py tests/test_corroboration_use_case.py
git commit -m "feat(corroboration): use case + corroborate CLI (RESEARCH_ONLY)"
```

---

## Task 10: Dated-source historical sanity check (labelled)

**Files:**
- Create: `application/corroboration_sanity.py`
- Test: `tests/test_corroboration_sanity.py`

Per spec §8: a 3–6 month retrospective on the **dated-source slice only** (yfinance analyst rating
events + dated news), labelled SANITY-NOT-VERDICT. Excludes LLM-harvested recs (look-ahead).

- [ ] **Step 1: Failing test — sanity computes forward hit-rate on dated analyst events from a fixture**

```python
# tests/test_corroboration_sanity.py
from datetime import date
from application.corroboration_sanity import dated_source_hit_rate

def test_hit_rate_on_dated_events_fixture():
    # event: (ticker, date, stance, forward_21d_return)
    events = [("AAA", date(2026, 3, 1), "bullish", 0.04),
              ("BBB", date(2026, 3, 1), "bullish", -0.02)]
    res = dated_source_hit_rate(events)
    assert res["n"] == 2
    assert res["hit_rate"] == 0.5
    assert res["label"] == "SANITY-NOT-VERDICT"
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement**

```python
# application/corroboration_sanity.py
"""3-6mo retrospective on DATED sources only. Sanity signal, never a verdict (spec §8)."""
from __future__ import annotations


def dated_source_hit_rate(events: list[tuple]) -> dict:
    n = len(events)
    hits = sum(1 for _, _, stance, ret in events
               if (stance == "bullish" and ret > 0) or (stance == "bearish" and ret < 0))
    return {"n": n, "hit_rate": (hits / n if n else 0.0),
            "label": "SANITY-NOT-VERDICT"}
```

- [ ] **Step 4: Run → PASS. Commit**

```bash
git add application/corroboration_sanity.py tests/test_corroboration_sanity.py
git commit -m "feat(corroboration): dated-source historical sanity check (labelled)"
```

---

## Task 11: Gate + docs

- [ ] **Step 1: Full gate**

Run: `PATH=.venv/bin:$PATH make check`
Expected: lint + mypy strict + coverage ≥90% all green.

- [ ] **Step 2: Update STATUS.md** — set phase to "Corroboration engine (sub-project 1) built,
RESEARCH_ONLY", branch `feat/corroboration-engine`, next action = "wire consumers (sub-projects 2-4) +
register Hypothesis #9 (sub-project 5)".

- [ ] **Step 3: Add ADR** `docs/adr/0XX-corroboration-engine.md` recording: attributed-not-predicted
stance, decoupled Search+LLM rationale, forward-only validation, ModelRegistry honest-limits.

- [ ] **Step 4: Commit**

```bash
git add docs/STATUS.md docs/adr/0XX-corroboration-engine.md
git commit -m "docs: STATUS + ADR for corroboration engine sub-project 1"
```

---

## Notes / known follow-ups (out of scope for this plan)

- `weekly-brief` crashes in `holdings_risk._vol` (numpy float → `statistics.pstdev`, Py3.12). Separate fix.
- `fix/yfinance-throttle` (throttle+backoff) and `feat/questrade-holdings` are open un-PR'd branches.
- Consumers (surfacing/screener/portfolio-verdict) = sub-projects 2-4, each its own spec+plan.
- Hypothesis #9 pre-registered forward gate = sub-project 5 (consumes these weekly snapshots).
