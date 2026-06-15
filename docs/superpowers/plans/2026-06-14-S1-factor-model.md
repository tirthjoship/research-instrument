# S1 — Factor Model (Low-vol · Revision fix · Asset-growth · IC re-run) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> **METHODOLOGY GATE:** Run `tirth-custom:ds-methodology-review` on Tasks 1–3 before locking factor math (leakage, definition validity). The IC gate (`backtest-screen`) decides "predictive" vs "descriptive"; default descriptive + disclosed.

**Goal:** Add a 5th factor (Low-Volatility), honestly resolve the mislabeled Revision factor, optionally
fold asset-growth into Quality, and re-run the IC backtest gate so the screener's Trust tile is truthful.

**Architecture:** Factor math stays pure in `domain/` (stdlib only); yfinance fetching stays in the
`adapters`/`cli` screen path. `FACTOR_KEYS` grows to 5; the composite denominator follows automatically.
The IC backtest is re-run via the existing CLI; its verdict feeds the UI (S3) Trust tile.

**Tech Stack:** Python 3.12, yfinance (via existing adapters), pytest, hypothesis, mypy strict.

**Anchors (verified):** `domain/factor_scores.py:26` FACTOR_KEYS; `:39-45` composite;
`domain/trend_rules.py:50-59` momentum; `application/evidence_screen_use_case.py:119-141` percentile,
`:251-260` winsorize/z; `application/cli.py:2487-2563` adapter wiring; `:2702` `backtest-screen`;
Revision mislabel `domain/factor_scores.py:29-36` + `cli.py:2534-2546`.

---

### Task 1: Revision data spike (decides the factor's fate) — INVESTIGATION

**Files:**
- Create: `docs/superpowers/spikes/2026-06-14-revision-source.md` (findings + decision)

This is a research task, not TDD. The current "revision" computes analyst *target spread*, not estimate
drift (yfinance serves one snapshot). Decide between (a) sourcing real point-in-time EPS-estimate
revisions, or (b) honest rename. **Fallback if (a) is infeasible = (b).**

- [ ] **Step 1:** Using context7, check the yfinance API for any time-series estimate fields:
  `Ticker.get_earnings_estimate`, `Ticker.eps_revisions`, `Ticker.get_analyst_price_targets`,
  `Ticker.recommendations_summary`. Note which (if any) expose **historical** estimate values usable
  point-in-time (timestamps ≤ as_of).
- [ ] **Step 2:** Confirm whether the project already stores any estimate history (grep
  `estimate_series`, `eps_revisions`, `recommendations` across `adapters/data/`).
- [ ] **Step 3:** Write the decision into the spike doc:
  - If a PIT estimate-revision series exists → **Decision A**: implement real revision (Task 5A).
  - Else → **Decision B**: rename factor to "Analyst dispersion" with truthful glossary def (Task 5B).
- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/spikes/2026-06-14-revision-source.md
git commit -m "docs: revision-source spike decision (S1 Task 1)"
```

---

### Task 2: Low-volatility pure factor function

**Files:**
- Modify: `domain/trend_rules.py`
- Test: `tests/domain/test_trend_rules.py`

Low-vol = inverse of trailing return volatility (lower vol → higher score). Pure; takes monthly closes
(same series momentum uses, `cli.py:2487-2497`), so no new adapter.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/domain/test_trend_rules.py
import math
from domain.trend_rules import trailing_volatility


def test_trailing_volatility_constant_series_is_zero():
    # flat prices → zero returns → zero vol
    assert trailing_volatility([100.0] * 14) == 0.0


def test_trailing_volatility_more_volatile_is_larger():
    calm = [100, 101, 100, 101, 100, 101, 100, 101, 100, 101, 100, 101, 100, 101]
    wild = [100, 130, 90, 140, 80, 150, 70, 160, 60, 170, 50, 180, 40, 190]
    assert trailing_volatility(wild) > trailing_volatility(calm)


def test_trailing_volatility_insufficient_history_returns_none():
    assert trailing_volatility([100.0, 101.0]) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/domain/test_trend_rules.py -k volatility -v`
Expected: FAIL — `ImportError: cannot import name 'trailing_volatility'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to domain/trend_rules.py
import math


def trailing_volatility(monthly_closes: list[float]) -> float | None:
    """Std-dev of trailing monthly simple returns. Needs >=13 closes (12 returns).
    Returns the raw volatility (>=0); the screen inverts + z-scores it cross-sectionally."""
    if len(monthly_closes) < 13:
        return None
    rets: list[float] = []
    for prev, cur in zip(monthly_closes[-13:-1], monthly_closes[-12:]):
        if prev <= 0:
            return None
        rets.append(cur / prev - 1.0)
    n = len(rets)
    mean = sum(rets) / n
    var = sum((r - mean) ** 2 for r in rets) / n
    return math.sqrt(var)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/domain/test_trend_rules.py -k volatility -v`
Expected: PASS (3)

- [ ] **Step 5: Commit**

```bash
git add domain/trend_rules.py tests/domain/test_trend_rules.py
git commit -m "feat: trailing_volatility pure factor (S1 Task 2)"
```

---

### Task 3: Add "lowvol" to FACTOR_KEYS (composite over 5)

**Files:**
- Modify: `domain/factor_scores.py:26`
- Test: `tests/domain/test_factor_scores.py`

The composite divides by `len(FACTOR_KEYS)` (`factor_scores.py:39-45`), so adding the key makes the
denominator 5 automatically. Low-vol is inverted to a z BEFORE composite (in the screen, Task 4); here
we only register the key and prove the composite arithmetic.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/domain/test_factor_scores.py
from domain.factor_scores import FACTOR_KEYS, composite_score


def test_factor_keys_includes_lowvol():
    assert "lowvol" in FACTOR_KEYS
    assert len(FACTOR_KEYS) == 5


def test_composite_divides_by_five():
    subs = {"momentum": 1.0, "revision": 1.0, "quality": 1.0, "value": 1.0, "lowvol": 1.0}
    assert composite_score(subs) == 1.0
    subs2 = {"momentum": 1.0, "revision": 0.0, "quality": 0.0, "value": 0.0, "lowvol": 0.0}
    assert composite_score(subs2) == 0.2          # 1.0 / 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/domain/test_factor_scores.py -k "lowvol or five" -v`
Expected: FAIL — `assert 4 == 5` / composite returns 0.25 not 0.2

- [ ] **Step 3: Write minimal implementation**

```python
# domain/factor_scores.py:26 — change
FACTOR_KEYS = ("momentum", "revision", "quality", "value", "lowvol")
```

- [ ] **Step 4: Run test + full factor_scores suite**

Run: `pytest tests/domain/test_factor_scores.py -v`
Expected: PASS. (Fix any existing test that hard-coded `/4` — update its expected value to `/5` and
note it in the commit; this is an intended contract change.)

- [ ] **Step 5: Commit**

```bash
git add domain/factor_scores.py tests/domain/test_factor_scores.py
git commit -m "feat: register lowvol factor; composite now over 5 (S1 Task 3)"
```

---

### Task 4: Wire Low-vol into the screen (adapter + z-score)

**Files:**
- Modify: `application/cli.py` (screen-candidates path, ~`2487-2563`)
- Modify: `application/evidence_screen_use_case.py` (winsorize/z loop `:251-260`, percentile `:119-141`)
- Test: `tests/application/test_evidence_screen_use_case.py`

- [ ] **Step 1: Write the failing test** (use the existing screen-use-case fixture pattern — small
  fake price/fundamental adapters, NEVER live yfinance)

```python
# append to tests/application/test_evidence_screen_use_case.py
def test_screen_emits_lowvol_factor(make_screen_uc):
    # make_screen_uc is the existing fixture building the use case with fake adapters
    uc = make_screen_uc(
        prices={"AAA": [100,101,99,102,98,103,97,104,96,105,95,106,94,107],
                "BBB": [100,140,80,150,70,160,60,170,50,180,40,190,30,200]},
    )
    result = uc.run(universe=["AAA", "BBB"], as_of="2026-06-14", top_n=2)
    aaa = next(c for c in result.candidates if c.ticker == "AAA")
    names = {f.name for f in aaa.factor_scores}
    assert "lowvol" in names
    # calmer AAA should have a higher (better) lowvol z than wilder BBB
    bbb = next(c for c in result.candidates if c.ticker == "BBB")
    aaa_lv = next(f.value for f in aaa.factor_scores if f.name == "lowvol")
    bbb_lv = next(f.value for f in bbb.factor_scores if f.name == "lowvol")
    assert aaa_lv > bbb_lv
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/application/test_evidence_screen_use_case.py -k lowvol -v`
Expected: FAIL — no `lowvol` factor emitted.

- [ ] **Step 3: Implement** — two edits:

  (3a) In `application/cli.py` screen path, alongside the momentum compute (~`cli.py:2554-2561`), call
  the new function on the same monthly-close series and pass a raw low-vol value into the sub-score map.
  **Invert** so low vol = high score before z (e.g. `lowvol_raw = -trailing_volatility(monthly)`); set
  `None`→DATA-GAP path (mirror how momentum `None` is handled).

```python
# in the per-ticker sub-score assembly (mirror existing momentum/value lines)
from domain.trend_rules import trailing_volatility
_vol = trailing_volatility(monthly_closes)
lowvol = (-_vol) if _vol is not None else None     # invert: calmer = higher
sub_scores["lowvol"] = lowvol
```

  (3b) In `application/evidence_screen_use_case.py`, ensure the winsorize/z loop (`:251-260`) and the
  percentile loop (`:119-141`) iterate `FACTOR_KEYS` (they already iterate the keys, so adding "lowvol"
  to `FACTOR_KEYS` in Task 3 auto-includes it). Verify no factor name is hard-coded; if a hard-coded
  list exists, replace with `FACTOR_KEYS`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/application/test_evidence_screen_use_case.py -k lowvol -v`
Expected: PASS

- [ ] **Step 5: Look-ahead check** — add an assertion that the low-vol series uses only closes ≤ as_of
  (the monthly-close adapter already filters to `now`; confirm in test fixture timestamps). Run the
  existing point-in-time guard test suite: `pytest tests/ -k "look_ahead or point_in_time" -v` → PASS.

- [ ] **Step 6: Commit**

```bash
git add application/cli.py application/evidence_screen_use_case.py tests/application/test_evidence_screen_use_case.py
git commit -m "feat: wire low-vol factor into screen with PIT + z-score (S1 Task 4)"
```

---

### Task 5: Resolve Revision (5A real source OR 5B honest rename) — per Task 1 decision

**Decision B (default/fallback) — honest rename:**

**Files:**
- Modify: `domain/factor_scores.py:29-36` (rename function + docstring to reflect *dispersion*)
- Modify: `application/cli.py:2534-2546` (key name if changed) — keep the FACTOR_KEYS key as
  `"revision"` for data-compat OR migrate to `"dispersion"` (if migrating, update FACTOR_KEYS + all
  consumers in S2/S3/S4 band + glossary). **Simplest honest fix: keep key, fix the label + glossary.**
- Modify: `adapters/visualization/components/glossary.py` ("Revision factor" → truthful definition)
- Test: `tests/domain/test_factor_scores.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/domain/test_factor_scores.py
from domain.factor_scores import analyst_dispersion


def test_analyst_dispersion_is_spread_over_low():
    # explicit: today's measure is (high - low)/|low|, named truthfully
    assert analyst_dispersion([10.0, 15.0, 20.0]) == (20.0 - 10.0) / abs(10.0)


def test_analyst_dispersion_none_on_empty():
    assert analyst_dispersion(None) is None
    assert analyst_dispersion([]) is None
```

- [ ] **Step 2: Run** → FAIL (`analyst_dispersion` undefined).

- [ ] **Step 3: Implement** — rename `revision_momentum` → `analyst_dispersion` (same math, honest
  name + docstring "spread of today's analyst targets; NOT temporal estimate drift"). Update the call
  site in `cli.py`. Update glossary "Revision factor" entry text to: *"Width of today's analyst price-
  target range (high vs low). A dispersion signal, not estimate-revision over time."* Keep displayed
  factor label as "Analyst spread" in the UI (S3 maps the key → this label).

- [ ] **Step 4: Run** → PASS. Also `pytest tests/ -k revision -v` (update any old test referencing the
  old name).

- [ ] **Step 5: Commit**

```bash
git add domain/factor_scores.py application/cli.py adapters/visualization/components/glossary.py tests/domain/test_factor_scores.py
git commit -m "fix: honestly rename revision→analyst_dispersion (S1 Task 5B)"
```

> **Decision A (only if Task 1 found a PIT estimate series):** instead of renaming, implement
> `estimate_revision(series_with_timestamps)` = `(latest - earliest)/|earliest|` over a PIT-filtered
> series; keep the name "Revision factor"; add a fixture-based test asserting drift sign. Same commit
> discipline. Do NOT ship Decision A without a PIT-filtered series — that would be look-ahead bias.

---

### Task 6: (Optional) Fold asset-growth into Quality — gated on data availability

**Files:**
- Modify: `application/cli.py` quality compute (~`2554-2556`)
- Test: `tests/application/test_evidence_screen_use_case.py`

- [ ] **Step 1:** Using context7, confirm yfinance `balance_sheet` exposes `Total Assets` for two
  consecutive years. If not reliably available → **skip this task**, note in spec log, leave Quality as
  ROE/margins. (YAGNI: do not block the ship on thin data.)
- [ ] **Step 2 (if available): Write the failing test** — a name with aggressive asset growth scores
  lower on quality than an identical name with flat assets.

```python
def test_quality_penalizes_aggressive_asset_growth(make_screen_uc):
    uc = make_screen_uc(
        fundamentals={"FLAT": {"roe": 0.2, "assets": [100, 101]},
                      "GROW": {"roe": 0.2, "assets": [100, 200]}})
    res = uc.run(universe=["FLAT", "GROW"], as_of="2026-06-14", top_n=2)
    qf = {c.ticker: next(f.value for f in c.factor_scores if f.name == "quality")
          for c in res.candidates}
    assert qf["FLAT"] > qf["GROW"]
```

- [ ] **Step 3:** Implement: `quality_raw = roe_component - w * asset_growth_component` (PIT-safe;
  weight `w` from `us.yaml`, default small). DATA-GAP if assets missing.
- [ ] **Step 4:** Run → PASS. Look-ahead check on balance-sheet dates.
- [ ] **Step 5: Commit**

```bash
git add application/cli.py tests/application/test_evidence_screen_use_case.py
git commit -m "feat: asset-growth discipline in quality factor (S1 Task 6)"
```

---

### Task 7: Re-run IC gate + surface verdict for the Trust tile

**Files:**
- Run: `application/cli.py:2702` `backtest-screen`
- Create: `data/reports/screen_ic_<today>.json` (output)
- Modify: `adapters/visualization/data_loader.py` (a loader for the latest IC verdict, if none exists)
- Test: `tests/adapters/test_data_loader.py`

- [ ] **Step 1:** Run the gate (still momentum-only by PIT necessity — note in output):

```bash
python -m application.cli backtest-screen --market us --start 2018-01-01 --end 2026-01-01 --horizon-days 21
```
Expected: writes `data/reports/screen_ic_<date>.json` with `decision` ∈ {PASS, INCONCLUSIVE, HALT}.

- [ ] **Step 2: Write the failing test** for a loader that reads the latest IC verdict:

```python
# tests/adapters/test_data_loader.py
def test_load_latest_ic_verdict(tmp_reports):   # tmp_reports = fixture writing a fake screen_ic JSON
    v = load_latest_ic_verdict(str(tmp_reports))
    assert v["decision"] in {"PASS", "INCONCLUSIVE", "HALT"}
    assert "mean_ic" in v
```

- [ ] **Step 3:** Run → FAIL (`load_latest_ic_verdict` undefined).
- [ ] **Step 4:** Implement `load_latest_ic_verdict` in `data_loader.py` (mirror `load_latest_screen`).
- [ ] **Step 5:** Run → PASS. This verdict feeds the S3 Trust tile (honest: "Inconclusive" unless PASS).
- [ ] **Step 6: Commit**

```bash
git checkout data/reports/    # restore tracked JSON trailing newlines before pre-commit
git add adapters/visualization/data_loader.py tests/adapters/test_data_loader.py data/reports/screen_ic_*.json
git commit -m "feat: re-run IC gate + load latest verdict for Trust tile (S1 Task 7)"
```

---

### Task 8: Methodology review + full gate

- [ ] **Step 1:** Invoke `tirth-custom:ds-methodology-review` on the factor changes (low-vol definition,
  revision resolution, asset-growth, leakage). Address findings.
- [ ] **Step 2:** `make check` (mypy strict + tests + coverage) → green.
- [ ] **Step 3: Commit** any fixes.

---

## Self-review (S1)
- Spec coverage: §5 S1 (Low-vol add ✓ Task 2-4, Revision resolve ✓ Task 1+5, asset-growth ✓ Task 6,
  IC re-run ✓ Task 7), §9 guardrails (ds-methodology ✓ Task 8, PIT ✓ Task 4/5/6, IC arbiter ✓ Task 7). ✓
- Placeholders: Task 6 is explicitly optional/gated (not a placeholder — a YAGNI branch with a test). ✓
- Type consistency: `FACTOR_KEYS` 5-tuple, `trailing_volatility`, `analyst_dispersion`,
  `load_latest_ic_verdict` stable; "lowvol" key matches S2/S4 usage. ✓
- Risk: Tasks 4/5/6 touch real adapter wiring whose exact lines the engineer must read first; anchors
  given. Revision fork resolved by Task-1 spike with a locked fallback. ✓
