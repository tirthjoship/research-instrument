# Unit B — M1/M2 Validity Fixes + Full-Window Rerun Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the two pre-registered-design validity bugs (M1 joint-filing cluster fabrication, M2 pooled/colliding tercile assignment), then rerun the full 2006–2024 insider-cluster falsification and execute the pre-committed verdict branch from the strategic wrap spec (§2 of `docs/superpowers/specs/2026-06-10-strategic-wrap-plan-design.md`).

**Architecture:** Pure-domain changes (`domain/insider_cluster.py`, `domain/insider_terciles.py`) + the application orchestrator (`application/insider_cluster_falsification_use_case.py`) + one adapter field (`adapters/data/sec_form345_dataset_adapter.py`). TDD throughout; hexagonal boundaries unchanged. The CLI is untouched (C1 echo fix already landed as 85f2eff).

**Tech Stack:** Python 3.12, pytest + Hypothesis, stdlib-only domain, click CLI, yfinance/SEC DERA adapters (already built).

**Branch:** work on existing `feat/insider-cluster-falsification`.

**Key semantic decisions (locked here):**
- **M1:** a cluster requires ≥3 greedily-matched (insider_cik, accession) pairs — each matched pair consumes its CIK *and* its accession, so one jointly-filed Form 4 (one accession, N owners) can contribute at most ONE matched insider. Greedy matching in filing-date order is deterministic and conservative (it can under-fire in rare pathological overlaps, never over-fire).
- **M2:** each event is binned against the ADV distribution of all events with `fire_date <=` its own (inclusive of itself), per EVENT not per ticker. Tie-break: first occurrence index in the sorted distribution (equal ADVs bin low — conservative toward bottom, the primary-hypothesis tercile). `MIN_TERCILE_POPULATION = 30` is disclosure-only: events binned earlier are counted and reported, never deferred or dropped.

---

### Task 1: Add `accession` to `InsiderTransaction` (domain + adapter + all fixtures)

**Files:**
- Modify: `domain/insider_cluster.py` (dataclass)
- Modify: `adapters/data/sec_form345_dataset_adapter.py` (constructor call ~line 96)
- Test: `tests/domain/test_insider_cluster.py` (helper `_txn`)
- Test: `tests/application/test_insider_cluster_falsification_use_case.py` (helper `_buy`)
- Test: `tests/adapters/test_sec_form345_dataset_adapter.py` (new assertion)

- [ ] **Step 1: Write the failing test** — in `tests/adapters/test_sec_form345_dataset_adapter.py`, extend the existing assertions inside `test_parse_join_yields_transactions` (after the `abc.aff10b51 is False` line):

```python
    assert abc.accession == "0001"
    assert other.accession == "0002"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/adapters/test_sec_form345_dataset_adapter.py::test_parse_join_yields_transactions -v`
Expected: FAIL with `AttributeError: 'InsiderTransaction' object has no attribute 'accession'`

- [ ] **Step 3: Add the field + thread it through.** In `domain/insider_cluster.py`, add `accession` to the dataclass directly under `insider_cik` (required, no default — every constructor must say where the row came from):

```python
@dataclass(frozen=True)
class InsiderTransaction:
    ticker: str
    insider_cik: str
    accession: str  # SEC accession number: one filing event (joint filings share one)
    trans_code: str
```

In `adapters/data/sec_form345_dataset_adapter.py`, in the `for cik in owner_by_acc.get(acc, []):` loop, add the field to the constructor:

```python
                out.append(
                    InsiderTransaction(
                        ticker=ticker,
                        insider_cik=cik,
                        accession=acc,
                        trans_code=(tr.get("TRANS_CODE") or "").strip(),
```

- [ ] **Step 4: Update both test helpers so existing tests keep passing.** Auto-derive a per-CIK accession when the test doesn't specify one (so the existing "3 distinct insiders fire" tests keep modeling three SEPARATE filings):

`tests/domain/test_insider_cluster.py`:

```python
def _txn(**kw):
    base = dict(
        ticker="ABC",
        insider_cik="111",
        trans_code="P",
        acquired_disp="A",
        shares=100.0,
        price_per_share=5.0,
        filing_date=date(2020, 1, 10),
        trans_date=date(2020, 1, 8),
        equity_swap=False,
        aff10b51=False,
    )
    base.update(kw)
    base.setdefault("accession", f"acc-{base['insider_cik']}")
    return InsiderTransaction(**base)
```

(Note: `setdefault` must run AFTER `base.update(kw)` so it derives from the test's cik. The property-based test needs no change — distinct ciks get distinct accessions automatically.)

`tests/application/test_insider_cluster_falsification_use_case.py`:

```python
def _buy(ticker, cik, d):
    return InsiderTransaction(
        ticker=ticker,
        insider_cik=cik,
        accession=f"acc-{ticker}-{cik}",
        trans_code="P",
        acquired_disp="A",
        shares=100.0,
        price_per_share=5.0,
        filing_date=d,
        trans_date=d,
        equity_swap=False,
        aff10b51=False,
    )
```

- [ ] **Step 5: Run the full insider suite, verify green**

Run: `python -m pytest tests/domain/ tests/application/ tests/adapters/ -q`
Expected: all pass (28 tests)

- [ ] **Step 6: Commit**

```bash
git add domain/insider_cluster.py adapters/data/sec_form345_dataset_adapter.py tests/
git commit -m "feat: thread SEC accession number through InsiderTransaction (M1 groundwork)"
```

---

### Task 2: M1 — joint-filing dedup in `detect_clusters`

**Files:**
- Modify: `domain/insider_cluster.py` (`detect_clusters` inner loop)
- Test: `tests/domain/test_insider_cluster.py`

- [ ] **Step 1: Write the failing tests** — append to `tests/domain/test_insider_cluster.py`:

```python
def test_m1_joint_filing_does_not_cluster():
    # One Form 4 (one accession) filed jointly by 3 reporting owners
    # = ONE buy decision, must NOT fire a cluster.
    txns = [
        _txn(insider_cik=c, accession="JOINT-1", filing_date=date(2020, 1, 5))
        for c in ("1", "2", "3")
    ]
    assert detect_clusters(txns) == []


def test_m1_three_ciks_two_accessions_does_not_cluster():
    txns = [
        _txn(insider_cik="1", accession="A1", filing_date=date(2020, 1, 5)),
        _txn(insider_cik="2", accession="A1", filing_date=date(2020, 1, 5)),
        _txn(insider_cik="3", accession="A2", filing_date=date(2020, 1, 8)),
    ]
    assert detect_clusters(txns) == []


def test_m1_joint_pair_plus_two_separate_filings_fires_on_completing_date():
    # ciks 1+2 file jointly (one accession); ciks 3 and 4 file separately.
    # Matched pairs: (1,J), (3,A3), (4,A4) -> fires when cik 4's filing lands.
    txns = [
        _txn(insider_cik="1", accession="J", filing_date=date(2020, 1, 5)),
        _txn(insider_cik="2", accession="J", filing_date=date(2020, 1, 5)),
        _txn(insider_cik="3", accession="A3", filing_date=date(2020, 1, 10)),
        _txn(insider_cik="4", accession="A4", filing_date=date(2020, 1, 20)),
    ]
    events = detect_clusters(txns)
    assert len(events) == 1
    assert events[0].fire_date == date(2020, 1, 20)
    assert events[0].distinct_insiders == 3
```

- [ ] **Step 2: Run tests to verify the first two fail**

Run: `python -m pytest tests/domain/test_insider_cluster.py -v -k m1`
Expected: `test_m1_joint_filing_does_not_cluster` and `test_m1_three_ciks_two_accessions_does_not_cluster` FAIL (clusters fire where they shouldn't); the third may pass by accident — fine.

- [ ] **Step 3: Implement greedy (CIK, accession) matching.** In `domain/insider_cluster.py`, replace the inner loop of `detect_clusters` (the `seen` block) with:

```python
        for i, anchor in enumerate(txns):
            # M1 (spec §3): greedy distinct-(insider, accession) matching.
            # Each matched insider consumes their accession, so one joint Form 4
            # (one accession, N reporting owners) contributes at most ONE insider.
            # Greedy in filing-date order: deterministic; can under-fire in rare
            # overlap pathologies, never over-fire (conservative).
            matched: dict[str, InsiderTransaction] = {}
            used_accessions: set[str] = set()
            for t in txns[i:]:
                if t.filing_date - anchor.filing_date > window:
                    break
                if t.insider_cik in matched or t.accession in used_accessions:
                    continue
                matched[t.insider_cik] = t
                used_accessions.add(t.accession)
                if len(matched) >= CLUSTER_MIN_INSIDERS:
                    fire_date = t.filing_date
                    # Point-in-time guard (spec sec.2 / CLAUDE.md look-ahead rule):
                    # no contributing filing may post-date the fire date. This is
                    # structurally guaranteed (txns sorted ascending; fire = the
                    # completing filing), asserted as defense-in-depth so a future
                    # refactor cannot silently leak a later filing into the signal.
                    if any(s.filing_date > fire_date for s in matched.values()):
                        raise LookAheadBiasError(
                            f"insider cluster {ticker}: a contributing Form-4 filing "
                            f"post-dates the fire date {fire_date}"
                        )
                    if fired_until is None or fire_date > fired_until:
                        events.append(
                            ClusterEvent(
                                ticker=ticker,
                                fire_date=fire_date,
                                distinct_insiders=len(matched),
                                total_buy_value=sum(
                                    s.shares * s.price_per_share
                                    for s in matched.values()
                                ),
                            )
                        )
                        fired_until = fire_date + window
                    break
```

Also update the `detect_clusters` docstring: replace the sentence "A cluster fires when >=3 DISTINCT insiders each have a qualifying buy whose FILING dates fall within a rolling 30-day window." with "A cluster fires when >=3 distinct (insider, accession) pairs are greedily matched within a rolling 30-day window — distinct insiders AND distinct filings, so a single joint Form 4 cannot fabricate a cluster (M1, spec §3 of the 2026-06-10 strategic wrap plan)."

- [ ] **Step 4: Run the domain suite, verify green**

Run: `python -m pytest tests/domain/ -q`
Expected: all pass (existing tests unaffected: distinct ciks now carry distinct auto-accessions)

- [ ] **Step 5: Commit**

```bash
git add domain/insider_cluster.py tests/domain/test_insider_cluster.py
git commit -m "fix: M1 — joint Form-4 filings can no longer fabricate insider clusters"
```

---

### Task 3: M2 — `tercile_for_event` expanding point-in-time binning (domain)

**Files:**
- Modify: `domain/insider_terciles.py` (add `tercile_for_event`, DELETE `assign_terciles`)
- Test: `tests/domain/test_insider_terciles.py` (replace `assign_terciles` tests)

- [ ] **Step 1: Write the failing tests.** Replace the whole of `tests/domain/test_insider_terciles.py` with:

```python
from domain.insider_terciles import slippage_bps_for_tercile, tercile_for_event


def test_slippage_schedule_locked():
    assert slippage_bps_for_tercile("bottom") == 150
    assert slippage_bps_for_tercile("mid") == 75
    assert slippage_bps_for_tercile("top") == 40


def test_first_event_is_bottom():
    # Singleton distribution: rank 0/1 -> bottom (conservative).
    assert tercile_for_event([], 5.0) == "bottom"


def test_expanding_distribution_bins_by_rank():
    prior = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert tercile_for_event(prior, 0.5) == "bottom"  # rank 0/6
    assert tercile_for_event(prior, 2.5) == "mid"     # rank 2/6
    assert tercile_for_event(prior, 6.0) == "top"     # rank 5/6
    assert tercile_for_event(prior, 3.5) == "mid"     # rank 3/6
    assert tercile_for_event(prior, 4.5) == "top"     # rank 4/6 = 2/3 boundary -> top


def test_ties_bin_low():
    # Equal ADVs take the first-occurrence rank -> lower bin (conservative
    # toward bottom, the primary-hypothesis tercile).
    assert tercile_for_event([2.0, 2.0], 2.0) == "bottom"  # rank 0/3


def test_same_adv_different_history_bins_differently():
    # The M2 point: the SAME adv must bin against ITS OWN point-in-time
    # distribution, not a pooled one.
    assert tercile_for_event([10.0, 20.0], 5.0) == "bottom"
    assert tercile_for_event([1.0, 2.0], 5.0) == "top"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/domain/test_insider_terciles.py -v`
Expected: FAIL with `ImportError: cannot import name 'tercile_for_event'`

- [ ] **Step 3: Implement.** In `domain/insider_terciles.py`, delete `assign_terciles` entirely and add:

```python
def tercile_for_event(prior_advs: list[float], adv: float) -> str:
    """Bin one event's ADV against its point-in-time distribution (M2, spec §3).

    Distribution = ADVs of all events with fire_date <= this event's, INCLUDING
    itself (the caller appends in fire-date order). Rank fraction = first-occurrence
    index in the sorted distribution / n, so ties bin LOW — conservative toward
    bottom, the primary-hypothesis tercile. A 2006 event is therefore never binned
    using the 2006-2024 pooled distribution.
    """
    dist = sorted(prior_advs + [adv])
    frac = dist.index(adv) / len(dist)
    if frac < 1 / 3:
        return "bottom"
    if frac < 2 / 3:
        return "mid"
    return "top"
```

Also update the module docstring's last line to mention: "Binning is per-event and point-in-time expanding (M2): see `tercile_for_event`."

- [ ] **Step 4: Run tests, verify green.** (The use-case still imports `assign_terciles` and will break — that is Task 4; only run the terciles file here.)

Run: `python -m pytest tests/domain/test_insider_terciles.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add domain/insider_terciles.py tests/domain/test_insider_terciles.py
git commit -m "feat: M2 — per-event expanding point-in-time tercile binning"
```

---

### Task 4: Use case — per-event terciles + below-min-population disclosure

**Files:**
- Modify: `application/insider_cluster_falsification_use_case.py`
- Test: `tests/application/test_insider_cluster_falsification_use_case.py`

- [ ] **Step 1: Write the failing test** — append to the use-case test file:

```python
def test_m2_same_ticker_events_binned_per_event_not_per_ticker():
    # Regression for the per-ticker ADV dict collision: one ticker, two cluster
    # events 3 months apart. Old code binned the ticker ONCE (last ADV wins,
    # tercile_counts summed to 1). Per-event binning must count BOTH events.
    txns = [_buy("ABC", c, date(2020, 1, 5)) for c in ("1", "2", "3")]
    txns += [_buy("ABC", c, date(2020, 4, 6)) for c in ("4", "5", "6")]
    uc = InsiderClusterFalsificationUseCase(
        port=_FakePort(txns),
        prices=lambda tk: [
            (date(2020, 1, 1) + timedelta(days=i), 10.0, 1000.0) for i in range(200)
        ],
        quarters=[(2020, 1)],
    )
    report = uc.run()
    assert report["n_cluster_events"] == 2
    counts = report["tercile_counts"]
    assert sum(counts.values()) == 2  # per-EVENT, not per-ticker
    assert report["n_events_binned_below_min_population"] == 2
    assert report["min_tercile_population"] == 30
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/application/test_insider_cluster_falsification_use_case.py -v`
Expected: new test FAILS (`KeyError: 'n_events_binned_below_min_population'` or `sum(counts.values()) == 1`)

- [ ] **Step 3: Rewrite the tercile section of `run()`.** In `application/insider_cluster_falsification_use_case.py`:

Replace the import line:

```python
from domain.insider_terciles import assign_terciles, slippage_bps_for_tercile
```

with:

```python
from domain.insider_terciles import slippage_bps_for_tercile, tercile_for_event
```

Add a module-level constant under `BENCHMARK_ETF`:

```python
# Disclosure-only (spec §3 stability rule): events binned while the expanding
# cross-section is below this population are COUNTED, never deferred or dropped
# (deferring would shrink the denominator — the survivorship bug C1 fixed).
MIN_TERCILE_POPULATION = 30
```

Replace this block:

```python
        adv: dict[str, float] = {
            cast(str, r["ticker"]): cast(float, r["adv"]) for r in records
        }
        terciles = assign_terciles(adv)
        bottom = [
            r for r in records if terciles.get(cast(str, r["ticker"])) == "bottom"
        ]
```

with:

```python
        # M2 (spec §3): per-EVENT point-in-time terciles. Sort by fire date
        # (ticker tie-break for determinism), bin each event against the
        # expanding ADV distribution of events up to and including itself.
        records.sort(key=lambda r: (cast(date, r["fire_date"]), cast(str, r["ticker"])))
        prior_advs: list[float] = []
        n_binned_below_min = 0
        for r in records:
            if len(prior_advs) + 1 < MIN_TERCILE_POPULATION:
                n_binned_below_min += 1
            r["tercile"] = tercile_for_event(prior_advs, cast(float, r["adv"]))
            prior_advs.append(cast(float, r["adv"]))
        bottom = [r for r in records if r["tercile"] == "bottom"]
```

Replace the gross/net loop header (records are now pre-sorted, the inner `sorted()` is redundant):

```python
        for r in sorted(bottom, key=lambda x: cast(date, x["fire_date"])):
```

with:

```python
        for r in bottom:  # already in fire-date order (sorted above)
```

Replace the `tercile_counts` entry in the returned dict:

```python
            "tercile_counts": {
                t: sum(1 for v in terciles.values() if v == t)
                for t in ("bottom", "mid", "top")
            },
```

with:

```python
            "tercile_counts": {
                t: sum(1 for r in records if r["tercile"] == t)
                for t in ("bottom", "mid", "top")
            },
            "n_events_binned_below_min_population": n_binned_below_min,
            "min_tercile_population": MIN_TERCILE_POPULATION,
```

- [ ] **Step 4: Run the full suite, verify green**

Run: `python -m pytest tests/domain/ tests/application/ tests/adapters/ -q`
Expected: all pass (~32 tests). Note for the implementer: `test_c1_no_price_event_enters_coverage_denominator` still passes — ABC is the sole record, singleton distribution → bottom; ZZZ no-price still bins to the bottom denominator.

- [ ] **Step 5: Run mypy + lint via pre-commit (catches the dict[str, object] cast issues)**

Run: `git add -A && pre-commit run --all-files` (or `make lint`)
Expected: black/isort/mypy/ruff all pass. If mypy complains about `r["tercile"]` on `dict[str, object]`, the values are already `object` — no cast needed to WRITE, only reads need `cast`.

- [ ] **Step 6: Commit**

```bash
git add application/insider_cluster_falsification_use_case.py tests/application/
git commit -m "fix: M2 — per-event expanding PIT terciles + below-min-population disclosure"
```

---

### Task 5: Document the amendment in ADR-053 (before the run)

**Files:**
- Modify: `docs/adr/053-insider-cluster-falsification-verdict.md`

- [ ] **Step 1: Add an amendment section.** Insert directly after the ADR's Context/preamble (before any results table), preserving the existing `[PENDING]` markers:

```markdown
## Amendment 2026-06-10 — validity repairs applied BEFORE the full-window run

Two detection-validity bugs found in code review were fixed after the smoke run
(2021–24) but before the full 2006–2024 verdict run. Recorded per the
pre-registration honesty rules (this is validity repair, not threshold tuning;
all gate thresholds remain locked):

- **M1 — joint-filing dedup.** One Form 4 filed jointly by N reporting owners was
  counted as N distinct insiders, so a single buy decision could fabricate a
  "cluster." Detection now requires >=3 greedily-matched distinct
  (insider, accession) pairs. Expected effect: fewer events; THIN_N risk rises.
  Accepted in advance.
- **M2 — point-in-time terciles.** Tercile assignment pooled ADV across the full
  sample and collided per ticker (one ticker's events all took the last event's
  ADV). Binning is now per-event against the expanding distribution of events up
  to each fire date (`MIN_TERCILE_POPULATION = 30`, disclosure-only).

The smoke-run numbers quoted elsewhere in this ADR predate these fixes and are
not comparable to the full-window result.
```

- [ ] **Step 2: Commit**

```bash
git add docs/adr/053-insider-cluster-falsification-verdict.md
git commit -m "docs: ADR-053 amendment — M1/M2 validity repairs recorded pre-full-run"
```

---

### Task 6: Preflight + launch the full 2006–2024 run

**Files:** none modified (operational task)

- [ ] **Step 1: Preflight imports + caches**

Run: `python -c "import yfinance, requests, click, loguru; print('imports ok')"`
Expected: `imports ok`. If `ModuleNotFoundError`, locate the interpreter the previous runs used (check `head -5 Makefile` for a venv path) and use it for every command below.

Run: `ls data/cache/sec_form345/ | wc -l && ls data/cache/yfinance/ | wc -l`
Expected: ~16+ SEC quarter zips (more will download for 2006–2020) and ~700+ cached yfinance tickers. Do NOT clear either cache — reuse is what makes the rerun cheap.

- [ ] **Step 2: Quick end-to-end sanity (already-passing regression test)**

Run: `python -m pytest tests/application/test_cli_insider.py -q`
Expected: 2 passed (guards the CLI echo/report key contract before burning hours)

- [ ] **Step 3: Launch detached (survives session end — use nohup, not a session-tied background task)**

Run:
```bash
cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender" && \
nohup python -m application.cli backtest-insider-clusters --end-year 2024 \
  > /tmp/insider_full3.log 2>&1 & echo "PID $!"
```
Expected: PID echoed. Verify liveness: `tail -3 /tmp/insider_full3.log` shows SEC DERA download / yfinance lines within ~1 min.

- [ ] **Step 4: Monitor (poll, do not block).** Check every ~15–30 min:

```bash
tail -3 /tmp/insider_full3.log; ls -la data/reports/insider_cluster_falsification_2024.json 2>/dev/null
```

Expected duration: hours (yfinance throttled). Done when the report JSON exists and the log's last lines show `VERDICT: ...`. If the log goes silent >30 min AND no process holds it (`lsof /tmp/insider_full3.log` empty), relaunch Step 3 — the caches make restarts cheap and resumable.

---

### Task 7: Execute the pre-committed verdict branch (spec §2) + finalize ADR-053

**Files:**
- Modify: `docs/adr/053-insider-cluster-falsification-verdict.md` (fill `[PENDING]`, set Status)
- Modify: `docs/STATUS.md` (overwrite, ~40 lines)
- Modify: `docs/PHASE_LOG.md` (append one entry)

- [ ] **Step 1: Read the report**

Run: `python -m json.tool data/reports/insider_cluster_falsification_2024.json`
Record: `verdict`, `n_events`, `coverage`, `gross_ci_low`, `net_ci_low`, `mean_gross_abn`, `mean_net_abn`, `n_cluster_events`, `n_bottom_population`, `n_bottom_benchmarked`, `n_events_binned_below_min_population`, `tercile_counts`.

- [ ] **Step 2: Execute EXACTLY the matching branch — no judgment calls, the tree is locked (spec §2):**

- `PASS` (net_ci_low > 0): ADR-053 verdict = PASS, next phase = 6-month forward paper validation. ADD a build item to the wrap plan: weekly live-cluster paper-trade logger (reuses `SECForm345DatasetAdapter` + `detect_clusters` on the latest quarter, appends to `data/reports/insider_paper_log.jsonl`). NO real money. Sleeve cap if paper passes: ≤5% of book, kill switch: rolling-6-month net abnormal ≤0 or sleeve drawdown >30%.
- `INCONCLUSIVE` (gross_ci_low > 0, net_ci_low ≤ 0): ADR-053 verdict = **final KILL by default** (Unit D parked, spec §6). Wording: "information real, untradeable at pre-registered costs; execution-cost measurement parked."
- `KILL` (gross_ci_low ≤ 0): ADR-053 verdict = KILL. Prediction permanently closed (ADR-052). No relitigation.
- `INCONCLUSIVE_THIN_N` / `INCONCLUSIVE_THIN_COVERAGE`: the M1/M2 amendment WAS the one allowed remediation — verdict = practical KILL ("cannot validate ⇒ cannot ever trade"). Record actual n/coverage numbers.

- [ ] **Step 3: Fill ADR-053** — replace every `[PENDING]` with the recorded numbers, set `Status: Accepted`, state the executed branch and what it forecloses.

- [ ] **Step 4: Overwrite `docs/STATUS.md`** (keep ~40 lines): current phase = "Unit B verdict in — <VERDICT>. Next: Unit C plan + hardening plan (separate plans per wrap spec §7)." Append one dated entry to `docs/PHASE_LOG.md` with verdict + headline numbers.

- [ ] **Step 5: Commit**

```bash
git add docs/adr/053-insider-cluster-falsification-verdict.md docs/STATUS.md docs/PHASE_LOG.md data/reports/insider_cluster_falsification_2024.json
git commit -m "docs: ADR-053 final — Unit B full-window verdict <VERDICT> (M1/M2-amended run)"
```

---

### Task 8: Finish the branch

- [ ] **Step 1:** Run the full insider suite + pre-commit one last time:
`python -m pytest tests/domain/ tests/application/ tests/adapters/ -q && pre-commit run --all-files`
Expected: all green.

- [ ] **Step 2:** Invoke `superpowers:finishing-a-development-branch` for `feat/insider-cluster-falsification` → PR to `develop` (never direct to main; repo convention: feature → dev → main).

---

## Out of scope for this plan (separate plans, per wrap-spec §7)

1. **Unit C** (anti-overtrade throttle + cash-buffer policy) — touches the discipline engine; plan after this branch merges.
2. **Hardening sprint** (fail-loud health checks, auto-prune delisted, retry/backoff on the weekly job).
3. **Docs refinement** (plain-language §5.5 pass, verdict-table README, write-up).
4. **Conditional paper-trade logger** — ONLY if Task 7 lands on PASS; folds into the Unit C plan.

## Self-review (done)

- Spec coverage: §2 (Task 7), §3 M1 (Tasks 1–2), §3 M2 (Tasks 3–4 incl. 30-population disclosure), amendment documentation (Task 5), rerun (Task 6). §1/§4/§5/§5.5 are later plans by design.
- No placeholders; all code complete; `tercile_for_event` signature consistent across Tasks 3–4; `accession` field consistent across Tasks 1–2.
- Type note for implementers: records are `dict[str, object]`; writing `r["tercile"]` needs no cast, reading it in comparisons doesn't either (`==` on object is fine for mypy).
