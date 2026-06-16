# S2 — Bucket Assignment Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deterministically sort screened candidates into the 6 reason buckets — top-5 per bucket,
repeats allowed (a name may appear in several), with a priority-ordered "primary" bucket per name and
honest empty buckets.

**Architecture:** New stdlib-only `domain/screen_buckets.py`. A `Bucket` enum carries label + emoji +
a pure predicate over factor percentiles. `assign_buckets` returns an ordered mapping
`Bucket → [BucketInput]` (≤5 each, ranked by composite). `primary_bucket` returns the highest-priority
bucket a name qualifies for (drives the `also …` repeat badges in S3). No randomness.

**Tech Stack:** Python 3.12, dataclasses/enum, pytest, hypothesis.

**Mockup pin:** `screener-FINAL-v2.html` — `.bkthd` headers (🌟 All-rounder, 🚀 Momentum leaders,
💎 Quality at a fair price, 📈 Value with a catalyst, ⭐ Quality compounders, 🛡️ Low-vol defensives),
the `.empty` honest-empty panel, and the `.rep` "also …" badges. Priority order = that vertical order.

---

### Task 1: BucketInput + top-quartile constant

**Files:**
- Create: `domain/screen_buckets.py`
- Test: `tests/domain/test_screen_buckets.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/domain/test_screen_buckets.py
from domain.screen_buckets import BucketInput, TOP_QUARTILE


def test_bucketinput_holds_percentiles():
    c = BucketInput(ticker="SPG", percentiles={"quality": 0.95, "value": 0.87}, composite=1.31)
    assert c.ticker == "SPG"
    assert c.percentiles["quality"] == 0.95
    assert TOP_QUARTILE == 0.75
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/domain/test_screen_buckets.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'domain.screen_buckets'`

- [ ] **Step 3: Write minimal implementation**

```python
# domain/screen_buckets.py
"""Reason-bucket assignment for the screener — pure, stdlib only."""

from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Mapping

TOP_QUARTILE = 0.75


@dataclass(frozen=True)
class BucketInput:
    ticker: str
    percentiles: Mapping[str, float]
    composite: float
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/domain/test_screen_buckets.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add domain/screen_buckets.py tests/domain/test_screen_buckets.py
git commit -m "feat: BucketInput dataclass + TOP_QUARTILE (S2)"
```

---

### Task 2: Bucket enum + per-bucket predicate

**Files:**
- Modify: `domain/screen_buckets.py`
- Test: `tests/domain/test_screen_buckets.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/domain/test_screen_buckets.py
from domain.screen_buckets import Bucket, qualifies

SPG = {"quality": 0.95, "value": 0.87, "revision": 0.92, "momentum": 0.59, "lowvol": 0.91}
KLAC = {"quality": 0.95, "value": 0.15, "revision": 0.48, "momentum": 0.95, "lowvol": 0.40}
KO = {"quality": 0.80, "value": 0.55, "revision": 0.45, "momentum": 0.40, "lowvol": 0.93}


def test_qualifies_quality_fair_price():
    assert qualifies(Bucket.QUALITY_FAIR_PRICE, SPG) is True     # quality & value both >=0.75
    assert qualifies(Bucket.QUALITY_FAIR_PRICE, KLAC) is False   # value 0.15


def test_qualifies_all_rounder():
    assert qualifies(Bucket.ALL_ROUNDER, SPG) is True            # quality,value,revision,lowvol >=0.75 (>=3)
    assert qualifies(Bucket.ALL_ROUNDER, KO) is False            # only lowvol & quality(0.80) =2


def test_qualifies_momentum_leaders_needs_both():
    assert qualifies(Bucket.MOMENTUM_LEADERS, KLAC) is False     # momentum yes, revision 0.48 no


def test_qualifies_lowvol_and_compounders():
    assert qualifies(Bucket.LOWVOL_DEFENSIVES, KO) is True       # lowvol 0.93
    assert qualifies(Bucket.QUALITY_COMPOUNDERS, KLAC) is True   # quality 0.95
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/domain/test_screen_buckets.py -k qualifies -v`
Expected: FAIL — `ImportError: cannot import name 'Bucket'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to domain/screen_buckets.py
from enum import Enum


def _top(p: Mapping[str, float], factor: str) -> bool:
    return p.get(factor, 0.0) >= TOP_QUARTILE


def _count_top(p: Mapping[str, float]) -> int:
    return sum(_top(p, f) for f in ("quality", "value", "revision", "momentum", "lowvol"))


class Bucket(Enum):
    # value = (emoji, label, predicate)
    ALL_ROUNDER = ("🌟", "All-rounder", lambda p: _count_top(p) >= 3)
    MOMENTUM_LEADERS = ("🚀", "Momentum leaders",
                        lambda p: _top(p, "momentum") and _top(p, "revision"))
    QUALITY_FAIR_PRICE = ("💎", "Quality at a fair price",
                          lambda p: _top(p, "quality") and _top(p, "value"))
    VALUE_CATALYST = ("📈", "Value with a catalyst",
                      lambda p: _top(p, "value") and _top(p, "revision"))
    QUALITY_COMPOUNDERS = ("⭐", "Quality compounders", lambda p: _top(p, "quality"))
    LOWVOL_DEFENSIVES = ("🛡️", "Low-vol defensives", lambda p: _top(p, "lowvol"))

    @property
    def emoji(self) -> str:
        return self.value[0]

    @property
    def label(self) -> str:
        return self.value[1]


def qualifies(bucket: Bucket, percentiles: Mapping[str, float]) -> bool:
    predicate = bucket.value[2]
    return bool(predicate(percentiles))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/domain/test_screen_buckets.py -k qualifies -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add domain/screen_buckets.py tests/domain/test_screen_buckets.py
git commit -m "feat: Bucket enum + qualifies predicate (S2)"
```

---

### Task 3: primary_bucket (priority order)

**Files:**
- Modify: `domain/screen_buckets.py`
- Test: `tests/domain/test_screen_buckets.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/domain/test_screen_buckets.py
from domain.screen_buckets import primary_bucket, PRIORITY


def test_priority_order_constant():
    assert PRIORITY[0] == Bucket.ALL_ROUNDER
    assert PRIORITY[-1] == Bucket.LOWVOL_DEFENSIVES


def test_primary_bucket_picks_highest_priority():
    # SPG qualifies for ALL_ROUNDER, QUALITY_FAIR_PRICE, VALUE_CATALYST, etc.
    assert primary_bucket(SPG) == Bucket.ALL_ROUNDER


def test_primary_bucket_none_when_unqualified():
    weak = {"quality": 0.1, "value": 0.1, "revision": 0.1, "momentum": 0.1, "lowvol": 0.1}
    assert primary_bucket(weak) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/domain/test_screen_buckets.py -k primary -v`
Expected: FAIL — `ImportError: cannot import name 'primary_bucket'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to domain/screen_buckets.py
PRIORITY: tuple[Bucket, ...] = (
    Bucket.ALL_ROUNDER,
    Bucket.MOMENTUM_LEADERS,
    Bucket.QUALITY_FAIR_PRICE,
    Bucket.VALUE_CATALYST,
    Bucket.QUALITY_COMPOUNDERS,
    Bucket.LOWVOL_DEFENSIVES,
)


def primary_bucket(percentiles: Mapping[str, float]) -> Bucket | None:
    for bucket in PRIORITY:
        if qualifies(bucket, percentiles):
            return bucket
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/domain/test_screen_buckets.py -k primary -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add domain/screen_buckets.py tests/domain/test_screen_buckets.py
git commit -m "feat: primary_bucket + PRIORITY order (S2)"
```

---

### Task 4: assign_buckets — top-5 per bucket, repeats allowed, ranked

**Files:**
- Modify: `domain/screen_buckets.py`
- Test: `tests/domain/test_screen_buckets.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/domain/test_screen_buckets.py
from domain.screen_buckets import assign_buckets, MAX_PER_BUCKET


def _mk(t, p, c):
    return BucketInput(ticker=t, percentiles=p, composite=c)


def test_assign_groups_and_ranks_and_allows_repeats():
    cands = [
        _mk("SPG", SPG, 1.31),
        _mk("KLAC", KLAC, 1.08),
        _mk("KO", KO, 1.05),
    ]
    out = assign_buckets(cands)
    # SPG repeats across several buckets (repeats allowed)
    fair = [c.ticker for c in out[Bucket.QUALITY_FAIR_PRICE]]
    assert "SPG" in fair
    allr = [c.ticker for c in out[Bucket.ALL_ROUNDER]]
    assert "SPG" in allr
    # KLAC (quality 0.95, value weak) is a compounder, not fair-price
    comp = [c.ticker for c in out[Bucket.QUALITY_COMPOUNDERS]]
    assert "KLAC" in comp and "KLAC" not in fair
    # KO is a low-vol defensive
    defv = [c.ticker for c in out[Bucket.LOWVOL_DEFENSIVES]]
    assert "KO" in defv


def test_assign_ranks_by_composite_desc():
    a = _mk("AAA", SPG, 0.5)
    b = _mk("BBB", SPG, 1.5)
    out = assign_buckets([a, b])
    fair = [c.ticker for c in out[Bucket.QUALITY_FAIR_PRICE]]
    assert fair == ["BBB", "AAA"]            # higher composite first


def test_assign_caps_at_five_per_bucket():
    cands = [_mk(f"T{i}", SPG, float(i)) for i in range(8)]
    out = assign_buckets(cands)
    assert len(out[Bucket.QUALITY_FAIR_PRICE]) == MAX_PER_BUCKET == 5


def test_assign_empty_bucket_present_with_empty_list():
    # no momentum-leader qualifiers in this set
    out = assign_buckets([_mk("SPG", SPG, 1.31)])
    assert Bucket.MOMENTUM_LEADERS in out
    assert out[Bucket.MOMENTUM_LEADERS] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/domain/test_screen_buckets.py -k assign -v`
Expected: FAIL — `ImportError: cannot import name 'assign_buckets'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to domain/screen_buckets.py
MAX_PER_BUCKET = 5


def assign_buckets(
    candidates: list[BucketInput],
) -> dict[Bucket, list[BucketInput]]:
    """Group candidates into every bucket they qualify for (repeats allowed),
    ranked by composite desc (ticker asc tie-break), capped at MAX_PER_BUCKET.
    Every bucket key is always present (empty list if none qualify)."""
    out: dict[Bucket, list[BucketInput]] = {b: [] for b in PRIORITY}
    for bucket in PRIORITY:
        members = [c for c in candidates if qualifies(bucket, c.percentiles)]
        members.sort(key=lambda c: (-c.composite, c.ticker))
        out[bucket] = members[:MAX_PER_BUCKET]
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/domain/test_screen_buckets.py -k assign -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add domain/screen_buckets.py tests/domain/test_screen_buckets.py
git commit -m "feat: assign_buckets top-5 per bucket with repeats (S2)"
```

---

### Task 5: Property tests — determinism + every key present

**Files:**
- Test: `tests/domain/test_screen_buckets.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/domain/test_screen_buckets.py
from hypothesis import given, strategies as st

_pct = st.floats(min_value=0.0, max_value=1.0)
_profile = st.fixed_dictionaries(
    {f: _pct for f in ("quality", "value", "revision", "momentum", "lowvol")}
)
_cand = st.builds(
    BucketInput,
    ticker=st.text(min_size=1, max_size=5, alphabet="ABCDEFGHIJ"),
    percentiles=_profile,
    composite=st.floats(min_value=-3, max_value=3, allow_nan=False),
)


@given(cands=st.lists(_cand, max_size=30))
def test_assign_deterministic_and_total(cands):
    a = assign_buckets(list(cands))
    b = assign_buckets(list(cands))
    # all 6 buckets always present
    assert set(a.keys()) == set(PRIORITY)
    # deterministic: same input → identical ticker ordering per bucket
    for bucket in PRIORITY:
        assert [c.ticker for c in a[bucket]] == [c.ticker for c in b[bucket]]
        assert len(a[bucket]) <= MAX_PER_BUCKET
```

- [ ] **Step 2: Run test to verify it fails or passes**

Run: `pytest tests/domain/test_screen_buckets.py -k deterministic -v`
Expected: PASS (implementation already deterministic). If hypothesis surfaces a non-determinism
(e.g. equal composite + equal ticker), the `(-composite, ticker)` key guarantees stability — confirm.

- [ ] **Step 3: No code change** unless a failure appears; if so, ensure the sort key is fully total.

- [ ] **Step 4: Run full module**

Run: `pytest tests/domain/test_screen_buckets.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add tests/domain/test_screen_buckets.py
git commit -m "test: property determinism for assign_buckets (S2)"
```

---

### Task 6: mypy + lint gate

- [ ] **Step 1:** `mypy --strict domain/screen_buckets.py` → Expected: `Success: no issues`
  (Note: the `Enum` value holding a lambda may need `# type: ignore[misc]` on the tuple or a
  `Callable` annotation via a helper — if mypy complains, refactor predicates into a module-level
  `_PREDICATES: dict[Bucket, Callable[[Mapping[str,float]], bool]]` instead of enum values, and have
  `qualifies` read that dict. Keep the test API identical.)
- [ ] **Step 2:** `pre-commit run --files domain/screen_buckets.py tests/domain/test_screen_buckets.py`
- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "chore: type/lint clean screen_buckets (S2)"
```

---

## Self-review (S2)
- Spec coverage: §5 S2 (6 buckets, predicates, priority primary, repeats, top-5 cap, empty states). ✓
  Mockup buckets + order + `.empty` + `.rep` all represented. ✓
- Placeholders: none. ✓
- Type consistency: `BucketInput`, `Bucket`, `qualifies`, `primary_bucket`, `assign_buckets`,
  `PRIORITY`, `MAX_PER_BUCKET`, `TOP_QUARTILE` stable across tasks. ✓
- Note: `lowvol` percentile is produced by S1 (Low-vol factor). Until S1 lands, callers pass profiles
  without `lowvol`; `_top` defaults missing factors to 0.0 → LOWVOL_DEFENSIVES stays empty (honest),
  no crash. ✓
