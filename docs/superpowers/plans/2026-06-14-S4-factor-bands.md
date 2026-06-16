# S4 — Factor Bands & Plain-Read Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn a factor percentile into a plain-language band (Exceptional/Strong/Flat/Weak) and turn a name's band profile into a deterministic one-sentence "plain read" — no LLM, pure domain.

**Architecture:** New stdlib-only module `domain/factor_bands.py`. A `Band` enum, a pure
`band_for_percentile`, label/colour-key helpers, and a deterministic `plain_read` template keyed off
the band profile. Consumed by the screener UI (S3) and Zone-② cards (S5). Property-tested.

**Tech Stack:** Python 3.12, dataclasses/enum, pytest, hypothesis.

**Mockup pin:** `screener-FINAL-v2.html` — `.band` classes (`t-grn` Exceptional, `t-blu` Strong,
`t-gry` Flat, `t-red` Weak) and the row-body "plain read" line. Band thresholds below are the contract.

---

### Task 1: Band enum + percentile→band

**Files:**
- Create: `domain/factor_bands.py`
- Test: `tests/domain/test_factor_bands.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/domain/test_factor_bands.py
import pytest
from domain.factor_bands import Band, band_for_percentile


@pytest.mark.parametrize(
    "pct,expected",
    [
        (0.95, Band.EXCEPTIONAL),
        (0.90, Band.EXCEPTIONAL),   # inclusive lower edge
        (0.89, Band.STRONG),
        (0.75, Band.STRONG),        # inclusive lower edge
        (0.74, Band.FLAT),
        (0.40, Band.FLAT),          # inclusive lower edge
        (0.39, Band.WEAK),
        (0.00, Band.WEAK),
    ],
)
def test_band_for_percentile_boundaries(pct, expected):
    assert band_for_percentile(pct) == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/domain/test_factor_bands.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'domain.factor_bands'`

- [ ] **Step 3: Write minimal implementation**

```python
# domain/factor_bands.py
"""Plain-language bands for factor percentiles — pure, stdlib only."""

from __future__ import annotations

from enum import Enum


class Band(Enum):
    EXCEPTIONAL = "Exceptional"
    STRONG = "Strong"
    FLAT = "Flat"
    WEAK = "Weak"


def band_for_percentile(percentile: float) -> Band:
    """Map a 0–1 percentile to a plain-language band. Cutoffs are inclusive lower edges."""
    if percentile >= 0.90:
        return Band.EXCEPTIONAL
    if percentile >= 0.75:
        return Band.STRONG
    if percentile >= 0.40:
        return Band.FLAT
    return Band.WEAK
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/domain/test_factor_bands.py -v`
Expected: PASS (8 cases)

- [ ] **Step 5: Commit**

```bash
git add domain/factor_bands.py tests/domain/test_factor_bands.py
git commit -m "feat: add Band enum and band_for_percentile (S4)"
```

---

### Task 2: Property test — monotonic in percentile + clamping

**Files:**
- Modify: `domain/factor_bands.py`
- Test: `tests/domain/test_factor_bands.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/domain/test_factor_bands.py
from hypothesis import given, strategies as st

_ORDER = {Band.WEAK: 0, Band.FLAT: 1, Band.STRONG: 2, Band.EXCEPTIONAL: 3}


@given(
    a=st.floats(min_value=0.0, max_value=1.0),
    b=st.floats(min_value=0.0, max_value=1.0),
)
def test_band_monotonic(a, b):
    if a <= b:
        assert _ORDER[band_for_percentile(a)] <= _ORDER[band_for_percentile(b)]


@given(p=st.floats(allow_nan=False, allow_infinity=False))
def test_band_clamps_out_of_range(p):
    # values <0 or >1 (e.g. float noise) must still return a valid Band, never raise
    assert band_for_percentile(p) in Band
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/domain/test_factor_bands.py::test_band_clamps_out_of_range -v`
Expected: PASS already for in-range; confirm no exception on extreme floats (it won't raise — both
guards are `>=`). If hypothesis finds nothing, the property holds. (Monotonic test should also pass.)

- [ ] **Step 3: No code change needed** — current implementation already total over all floats. If a
  reviewer wants explicit intent, add a clarifying comment:

```python
    # No clamping needed: the >= ladder is total — any float resolves to exactly one band.
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/domain/test_factor_bands.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add domain/factor_bands.py tests/domain/test_factor_bands.py
git commit -m "test: property tests for band monotonicity (S4)"
```

---

### Task 3: Colour-key helper (maps Band → CSS token name, not hex)

**Files:**
- Modify: `domain/factor_bands.py`
- Test: `tests/domain/test_factor_bands.py`

Rationale: domain must not hold hex. It returns a *semantic key*; the UI (S3) maps key → the styles.py
colour var. This keeps the honesty/legibility colour mapping in one place and testable.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/domain/test_factor_bands.py
from domain.factor_bands import band_tone_key


def test_band_tone_key():
    assert band_tone_key(Band.EXCEPTIONAL) == "success"
    assert band_tone_key(Band.STRONG) == "accent"
    assert band_tone_key(Band.FLAT) == "muted"
    assert band_tone_key(Band.WEAK) == "danger"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/domain/test_factor_bands.py::test_band_tone_key -v`
Expected: FAIL — `ImportError: cannot import name 'band_tone_key'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to domain/factor_bands.py
_TONE = {
    Band.EXCEPTIONAL: "success",
    Band.STRONG: "accent",
    Band.FLAT: "muted",
    Band.WEAK: "danger",
}


def band_tone_key(band: Band) -> str:
    """Semantic colour key (UI maps to a styles.py var; domain holds no hex)."""
    return _TONE[band]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/domain/test_factor_bands.py::test_band_tone_key -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add domain/factor_bands.py tests/domain/test_factor_bands.py
git commit -m "feat: band_tone_key semantic colour mapping (S4)"
```

---

### Task 4: Deterministic plain-read from a band profile

**Files:**
- Modify: `domain/factor_bands.py`
- Test: `tests/domain/test_factor_bands.py`

The plain read is the row's one-sentence summary (mockup: SPG "a value setup", KLAC "not cheap").
It is keyed strictly off bands — never an LLM, never a forecast verb (FORBIDDEN_WORDS).

- [ ] **Step 1: Write the failing test**

```python
# append to tests/domain/test_factor_bands.py
from domain.factor_bands import plain_read

# profile keys are the canonical factor names; values are Bands
SPG = {"quality": Band.EXCEPTIONAL, "value": Band.STRONG,
       "revision": Band.EXCEPTIONAL, "momentum": Band.FLAT, "lowvol": Band.EXCEPTIONAL}
KLAC = {"quality": Band.EXCEPTIONAL, "value": Band.WEAK,
        "revision": Band.FLAT, "momentum": Band.EXCEPTIONAL, "lowvol": Band.FLAT}


def test_plain_read_value_setup():
    txt = plain_read(SPG)
    assert "quality" in txt.lower() and "value" in txt.lower()
    assert "flat" in txt.lower()           # momentum flat surfaced
    assert txt.endswith(".")


def test_plain_read_expensive():
    txt = plain_read(KLAC)
    assert "not cheap" in txt.lower() or "expensive" in txt.lower()


def test_plain_read_no_forbidden_words():
    forbidden = ("buy", "sell", "winner", "conviction", "predict", "alpha", "outperform")
    for profile in (SPG, KLAC):
        low = plain_read(profile).lower()
        assert not any(w in low.split() for w in forbidden)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/domain/test_factor_bands.py -k plain_read -v`
Expected: FAIL — `ImportError: cannot import name 'plain_read'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to domain/factor_bands.py
_STRONG = {Band.EXCEPTIONAL, Band.STRONG}


def plain_read(bands: dict[str, "Band"]) -> str:
    """One-sentence, forecast-free read of a name's band profile. Deterministic."""
    q = bands.get("quality", Band.FLAT)
    v = bands.get("value", Band.FLAT)
    m = bands.get("momentum", Band.FLAT)
    r = bands.get("revision", Band.FLAT)

    strengths = [name for name, b in
                 (("quality", q), ("value", v), ("revision", r)) if b in _STRONG]
    head = (
        "Strong on " + " and ".join(strengths)
        if strengths else "No standout factor"
    )

    # momentum caveat
    mom = "momentum flat" if m == Band.FLAT else (
        "momentum weak" if m == Band.WEAK else "momentum strong")

    # value framing
    if v == Band.WEAK:
        tail = "but not cheap — decide if the premium is justified"
    elif v in _STRONG and q in _STRONG:
        tail = "a value setup worth a look, not urgent"
    else:
        tail = "a reason to investigate, not a return forecast"

    return f"{head}; {mom} — {tail}."
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/domain/test_factor_bands.py -k plain_read -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Property test — never raises across any profile**

```python
# append to tests/domain/test_factor_bands.py
from itertools import product

def test_plain_read_total_over_all_profiles():
    factors = ["quality", "value", "revision", "momentum", "lowvol"]
    for combo in product(Band, repeat=len(factors)):
        profile = dict(zip(factors, combo))
        out = plain_read(profile)
        assert isinstance(out, str) and out.endswith(".")
```

Run: `pytest tests/domain/test_factor_bands.py -v`
Expected: PASS (all)

- [ ] **Step 6: Commit**

```bash
git add domain/factor_bands.py tests/domain/test_factor_bands.py
git commit -m "feat: deterministic plain_read from band profile (S4)"
```

---

### Task 5: mypy + lint gate

- [ ] **Step 1:** Run `mypy --strict domain/factor_bands.py` → Expected: `Success: no issues`
- [ ] **Step 2:** Run `pre-commit run --files domain/factor_bands.py tests/domain/test_factor_bands.py` → Expected: all hooks pass
- [ ] **Step 3: Commit** (if hooks reformatted)

```bash
git add -A && git commit -m "chore: lint/type clean factor_bands (S4)"
```

---

## Self-review (S4)
- Spec coverage: §5 S4 (band mapping, plain read, glossary entries — glossary additions handled in S3
  where `tooltip()` is wired). ✓
- Placeholders: none. ✓
- Type consistency: `Band` enum used identically across tasks; `band_for_percentile`/`band_tone_key`/
  `plain_read` signatures stable. ✓
