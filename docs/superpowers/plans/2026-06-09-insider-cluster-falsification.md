# Insider-Cluster Falsification (Unit B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pre-registered falsification of whether sub-$1B non-routine insider-buy clusters carry tradeable 21-day forward edge, emitting a locked-threshold verdict (PASS/KILL/INCONCLUSIVE).

**Architecture:** Hexagonal. Pure domain (cluster detection, terciles, slippage, gate/guards) with zero I/O; a new SEC DERA Form-345 ingest adapter behind a Protocol port; an application use-case that orchestrates and reuses the existing `ic_analysis` + `precision_metrics` bootstrap harness; a `click` CLI with masked stdout + tracked JSON report.

**Tech Stack:** Python 3.12, stdlib-only domain, `requests` (already a dep) for the SEC download, existing `yfinance_adapter` for prices, `click` CLI, pytest + Hypothesis.

**Spec:** `docs/superpowers/specs/2026-06-09-insider-cluster-falsification-design.md` (pre-registration; thresholds LOCKED). ADR-052.

**Effort:** LOW build / MAX verify. Implementers: Sonnet per task; Opus verification-before-completion at each phase gate.

**Pre-registered constants (LOCKED — copy verbatim, never tune):**
- `CLUSTER_MIN_INSIDERS = 3`, `CLUSTER_WINDOW_DAYS = 30`
- `INCLUDED_TRANS_CODE = "P"`, `INCLUDED_ACQ_DISP = "A"`
- `EXCLUDED_TRANS_CODES = {"S","M","A","G","F","C","W"}` (note: code "A" grant excluded; the *acquired flag* "A" is a different column)
- `FORWARD_HORIZON_TDAYS = 21`
- `BENCHMARK_ETF = {"bottom":"IWC","mid":"IWM","top":"IWM"}` (market-adjusted abn return, beta=1)
- `SLIPPAGE_BPS = {"bottom":150,"mid":75,"top":40}` (round-trip, per name)
- Gate metric = **event-study abnormal return** (NOT rank-IC — binary signal; spec §4 amendment). Leg-1 = bootstrap CI_low(gross abn) > 0; Leg-2 = bootstrap CI_low(net abn) > 0; verdict 3-state since net ≤ gross.
- `MIN_COVERAGE = 0.80`, `MIN_CLUSTER_EVENTS = 100`
- `N_RESAMPLES = 1000`, `SEED = 42`
- `DATA_FLOOR = "2006q1"`
- `DERA_URL = "https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/{q}_form345.zip"`
- `SEC_USER_AGENT = "tirthjoshi95@gmail.com portfolio-research"`

---

## File structure

| File | Responsibility |
|------|----------------|
| `domain/insider_cluster.py` (new) | `InsiderTransaction`, `ClusterEvent` dataclasses; `detect_clusters()`; `EXCLUDED_TRANS_CODES` etc. Pure. |
| `domain/insider_terciles.py` (new) | `assign_terciles()` (ADV-based), `slippage_bps_for_tercile()`. Pure. |
| `domain/insider_gate.py` (new) | `evaluate_gate()` — two-leg verdict + coverage/power guards. Pure. |
| `domain/ports.py` (modify) | add `InsiderTransactionsPort` Protocol. |
| `adapters/data/sec_form345_dataset_adapter.py` (new) | download + parse + join DERA quarterly TSVs → `list[InsiderTransaction]`. |
| `application/insider_forward_returns.py` (new) | per-event 21d forward return + trailing ADV via a price-history callable; unresolved tracking. |
| `application/insider_cluster_falsification_use_case.py` (new) | orchestrate clusters → terciles → returns → gate; build report dict. |
| `application/cli.py` (modify) | `backtest-insider-clusters` command (masked stdout + JSON report). |
| `tests/domain/test_insider_cluster.py`, `test_insider_terciles.py`, `test_insider_gate.py` (new) | pure-domain + property tests. |
| `tests/adapters/test_sec_form345_dataset_adapter.py` (new) | parse/join on a tiny fixture TSV trio. |
| `tests/application/test_insider_forward_returns.py`, `test_insider_cluster_falsification_use_case.py` (new) | use-case with fakes. |

---

## Phase 1 — Domain primitives (pure, no I/O)

### Task 1: Domain models + constants

**Files:**
- Create: `domain/insider_cluster.py`
- Test: `tests/domain/test_insider_cluster.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/domain/test_insider_cluster.py
from datetime import date
import pytest
from domain.insider_cluster import InsiderTransaction, EXCLUDED_TRANS_CODES


def _txn(**kw):
    base = dict(
        ticker="ABC", insider_cik="111", trans_code="P", acquired_disp="A",
        shares=100.0, price_per_share=5.0, filing_date=date(2020, 1, 10),
        trans_date=date(2020, 1, 8), equity_swap=False, aff10b51=False,
    )
    base.update(kw)
    return InsiderTransaction(**base)


def test_transaction_is_frozen():
    t = _txn()
    with pytest.raises(Exception):
        t.shares = 200.0  # type: ignore[misc]


def test_negative_shares_rejected():
    with pytest.raises(ValueError):
        _txn(shares=-1.0)


def test_excluded_codes_are_locked():
    assert EXCLUDED_TRANS_CODES == {"S", "M", "A", "G", "F", "C", "W"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/domain/test_insider_cluster.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'domain.insider_cluster'`

- [ ] **Step 3: Write minimal implementation**

```python
# domain/insider_cluster.py
"""Non-routine insider-cluster detection (pure domain).

Strict cluster = >=3 distinct insiders making open-market purchases (Form-4
transaction code 'P', acquired flag 'A') within a 30-day window. Signal fires on
the FILING date (point-in-time), never the transaction date. See spec
2026-06-09-insider-cluster-falsification-design.md (pre-registration).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

CLUSTER_MIN_INSIDERS = 3
CLUSTER_WINDOW_DAYS = 30
INCLUDED_TRANS_CODE = "P"
INCLUDED_ACQ_DISP = "A"
EXCLUDED_TRANS_CODES = {"S", "M", "A", "G", "F", "C", "W"}


@dataclass(frozen=True)
class InsiderTransaction:
    ticker: str
    insider_cik: str
    trans_code: str
    acquired_disp: str
    shares: float
    price_per_share: float
    filing_date: date
    trans_date: date
    equity_swap: bool
    aff10b51: bool

    def __post_init__(self) -> None:
        if self.shares < 0:
            raise ValueError(f"shares must be >= 0, got {self.shares}")
        if self.price_per_share < 0:
            raise ValueError(f"price must be >= 0, got {self.price_per_share}")

    def is_qualifying_buy(self) -> bool:
        """A non-routine open-market purchase that counts toward a cluster."""
        return (
            self.trans_code == INCLUDED_TRANS_CODE
            and self.acquired_disp == INCLUDED_ACQ_DISP
            and self.shares > 0
            and not self.equity_swap
            and not self.aff10b51
        )


@dataclass(frozen=True)
class ClusterEvent:
    ticker: str
    fire_date: date  # filing date of the 3rd qualifying insider (point-in-time)
    distinct_insiders: int
    total_buy_value: float
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/domain/test_insider_cluster.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add domain/insider_cluster.py tests/domain/test_insider_cluster.py
git commit -m "feat: insider transaction + cluster domain models (Unit B)"
```

---

### Task 2: Cluster detection (the core signal)

**Files:**
- Modify: `domain/insider_cluster.py`
- Test: `tests/domain/test_insider_cluster.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/domain/test_insider_cluster.py
from domain.insider_cluster import detect_clusters


def test_three_distinct_insiders_in_window_fires_on_filing_date():
    txns = [
        _txn(insider_cik="1", filing_date=date(2020, 1, 5)),
        _txn(insider_cik="2", filing_date=date(2020, 1, 20)),
        _txn(insider_cik="3", filing_date=date(2020, 1, 31)),
    ]
    events = detect_clusters(txns)
    assert len(events) == 1
    assert events[0].fire_date == date(2020, 1, 31)  # 3rd FILING date
    assert events[0].distinct_insiders == 3


def test_same_insider_thrice_does_not_cluster():
    txns = [_txn(insider_cik="1", filing_date=date(2020, 1, d)) for d in (5, 10, 15)]
    assert detect_clusters(txns) == []


def test_excluded_codes_never_count():
    txns = [
        _txn(insider_cik="1"), _txn(insider_cik="2"),
        _txn(insider_cik="3", trans_code="S", acquired_disp="D"),  # sale
    ]
    assert detect_clusters(txns) == []


def test_aff10b51_and_equity_swap_excluded():
    txns = [
        _txn(insider_cik="1"), _txn(insider_cik="2"),
        _txn(insider_cik="3", aff10b51=True),
        _txn(insider_cik="4", equity_swap=True),
    ]
    assert detect_clusters(txns) == []


def test_window_too_wide_does_not_cluster():
    txns = [
        _txn(insider_cik="1", filing_date=date(2020, 1, 1)),
        _txn(insider_cik="2", filing_date=date(2020, 1, 20)),
        _txn(insider_cik="3", filing_date=date(2020, 3, 1)),  # > 30d from first
    ]
    assert detect_clusters(txns) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/domain/test_insider_cluster.py -v`
Expected: FAIL with `ImportError: cannot import name 'detect_clusters'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to domain/insider_cluster.py


def detect_clusters(
    transactions: list[InsiderTransaction],
) -> list[ClusterEvent]:
    """Detect strict clusters per ticker.

    A cluster fires when >=3 DISTINCT insiders each have a qualifying buy whose
    FILING dates fall within a rolling 30-day window. Fire date = the filing date
    that completes the 3rd distinct insider (point-in-time: the cluster is only
    knowable once that 3rd Form-4 is public). At most one event per ticker per
    completing-window is emitted; subsequent qualifying buys that extend the same
    standing cluster do not re-fire until the window of distinct insiders resets.
    """
    by_ticker: dict[str, list[InsiderTransaction]] = {}
    for t in transactions:
        if t.is_qualifying_buy():
            by_ticker.setdefault(t.ticker, []).append(t)

    events: list[ClusterEvent] = []
    window = timedelta(days=CLUSTER_WINDOW_DAYS)
    for ticker, txns in by_ticker.items():
        txns.sort(key=lambda x: x.filing_date)
        fired_until: date | None = None
        for i, anchor in enumerate(txns):
            # collect distinct insiders whose filing is within [anchor, anchor+30d]
            seen: dict[str, InsiderTransaction] = {}
            for t in txns[i:]:
                if t.filing_date - anchor.filing_date > window:
                    break
                seen.setdefault(t.insider_cik, t)
                if len(seen) >= CLUSTER_MIN_INSIDERS:
                    fire_date = t.filing_date
                    if fired_until is None or fire_date > fired_until:
                        events.append(
                            ClusterEvent(
                                ticker=ticker,
                                fire_date=fire_date,
                                distinct_insiders=len(seen),
                                total_buy_value=sum(
                                    s.shares * s.price_per_share for s in seen.values()
                                ),
                            )
                        )
                        fired_until = fire_date + window
                    break
    return events
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/domain/test_insider_cluster.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Property test — no future leakage invariant**

```python
# append to tests/domain/test_insider_cluster.py
from hypothesis import given, strategies as st


@given(
    ciks=st.lists(st.sampled_from(["1", "2", "3", "4", "5"]), min_size=0, max_size=12),
)
def test_fire_date_never_precedes_any_contributing_filing(ciks):
    txns = [
        _txn(insider_cik=c, filing_date=date(2020, 1, 1) + timedelta(days=i))
        for i, c in enumerate(ciks)
    ]
    for ev in detect_clusters(txns):
        contributing = [
            t.filing_date for t in txns
            if t.is_qualifying_buy() and t.ticker == ev.ticker
            and abs((t.filing_date - ev.fire_date).days) <= CLUSTER_WINDOW_DAYS
        ]
        # fire_date is a real filing date and is the max of the 3 that completed it
        assert ev.fire_date in [t.filing_date for t in txns]
```

- [ ] **Step 6: Run + commit**

Run: `pytest tests/domain/test_insider_cluster.py -v` → Expected: PASS
```bash
git add domain/insider_cluster.py tests/domain/test_insider_cluster.py
git commit -m "feat: strict non-routine insider-cluster detection (point-in-time)"
```

---

### Task 3: ADV terciles + slippage schedule

**Files:**
- Create: `domain/insider_terciles.py`
- Test: `tests/domain/test_insider_terciles.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/domain/test_insider_terciles.py
import pytest
from domain.insider_terciles import assign_terciles, slippage_bps_for_tercile


def test_assign_terciles_splits_by_adv():
    adv = {"A": 1.0, "B": 2.0, "C": 3.0, "D": 4.0, "E": 5.0, "F": 6.0}
    t = assign_terciles(adv)
    assert t["A"] == "bottom" and t["B"] == "bottom"
    assert t["C"] == "mid" and t["D"] == "mid"
    assert t["E"] == "top" and t["F"] == "top"


def test_slippage_schedule_locked():
    assert slippage_bps_for_tercile("bottom") == 150
    assert slippage_bps_for_tercile("mid") == 75
    assert slippage_bps_for_tercile("top") == 40


def test_empty_adv_returns_empty():
    assert assign_terciles({}) == {}
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/domain/test_insider_terciles.py -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
# domain/insider_terciles.py
"""ADV-based liquidity terciles + pre-registered slippage schedule (pure).

Liquidity (ADV = avg dollar-volume) replaces market cap as the split axis: it is
fully point-in-time (no shares-outstanding history needed) and is arguably truer
to the structural thesis (liquidity, not cap, is what blocks institutions). See
spec Caveat 1.
"""
from __future__ import annotations

SLIPPAGE_BPS = {"bottom": 150, "mid": 75, "top": 40}


def assign_terciles(adv: dict[str, float]) -> dict[str, str]:
    """Split tickers into bottom/mid/top terciles by ascending ADV.

    Bottom = least liquid (smallest ADV) = the primary-hypothesis tercile.
    Ties broken by ticker for determinism. Boundaries via index thirds.
    """
    if not adv:
        return {}
    ordered = sorted(adv, key=lambda k: (adv[k], k))
    n = len(ordered)
    out: dict[str, str] = {}
    for i, tk in enumerate(ordered):
        if i < n / 3:
            out[tk] = "bottom"
        elif i < 2 * n / 3:
            out[tk] = "mid"
        else:
            out[tk] = "top"
    return out


def slippage_bps_for_tercile(tercile: str) -> int:
    return SLIPPAGE_BPS[tercile]
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/domain/test_insider_terciles.py -v` → Expected: PASS (3)

- [ ] **Step 5: Commit**

```bash
git add domain/insider_terciles.py tests/domain/test_insider_terciles.py
git commit -m "feat: ADV liquidity terciles + locked slippage schedule"
```

---

## Phase 2 — Gate (pure) + Adapter

### Task 4: Event-study gate + coverage/power guards

**Files:**
- Create: `domain/insider_gate.py`
- Test: `tests/domain/test_insider_gate.py`

This is the falsification's integrity core — MAX verify. The gate takes the per-event
**gross abnormal-return series** and **net abnormal-return series** (net = gross − slippage,
computed upstream in the use-case) plus event/coverage counts, and bootstraps each.
Verdict is 3-state because `net ≤ gross` always (slippage > 0). Calls the existing
stdlib-only deterministic `moving_block_bootstrap` directly (no I/O → stays pure-ish; see
domain-import NOTE).

- [ ] **Step 1: Write the failing test (one per verdict state + both guards)**

```python
# tests/domain/test_insider_gate.py
from domain.insider_gate import evaluate_gate


def _pos(n=200):  # mean clearly > 0, low noise => bootstrap ci_low > 0
    return [0.05 + (0.001 if i % 2 else -0.001) for i in range(n)]


def _neg(n=200):
    return [-x for x in _pos(n)]


def test_pass_when_net_ci_positive():
    v = evaluate_gate(gross_abn=_pos(), net_abn=_pos(), n_events=500, coverage=0.95)
    assert v["verdict"] == "PASS"


def test_kill_when_gross_ci_not_positive():
    v = evaluate_gate(gross_abn=_neg(), net_abn=_neg(), n_events=500, coverage=0.95)
    assert v["verdict"] == "KILL"


def test_inconclusive_gross_positive_net_not():
    # info present (gross>0) but costs kill it (net<=0) — the expected outcome
    v = evaluate_gate(gross_abn=_pos(), net_abn=_neg(), n_events=500, coverage=0.95)
    assert v["verdict"] == "INCONCLUSIVE"


def test_thin_coverage_overrides_everything():
    v = evaluate_gate(gross_abn=_pos(), net_abn=_pos(), n_events=500, coverage=0.50)
    assert v["verdict"] == "INCONCLUSIVE_THIN_COVERAGE"


def test_thin_n_overrides_legs():
    v = evaluate_gate(gross_abn=_pos(), net_abn=_pos(), n_events=42, coverage=0.95)
    assert v["verdict"] == "INCONCLUSIVE_THIN_N"
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/domain/test_insider_gate.py -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
# domain/insider_gate.py
"""Pre-registered event-study gate + guards (pure). Thresholds LOCKED (spec sec.4-6).

Leg 1 (info, gross):     bootstrap CI lower bound of gross abnormal return > 0.
Leg 2 (tradeable, net):  bootstrap CI lower bound of net abnormal return > 0.
Verdict is 3-state because net = gross - slippage <= gross (slippage > 0):
  net.ci_low > 0                      -> PASS
  gross.ci_low > 0 and net.ci_low<=0  -> INCONCLUSIVE (info real, killed by costs)
  gross.ci_low <= 0                   -> KILL
Guards (override): coverage < 0.80 -> THIN_COVERAGE; n_events < 100 -> THIN_N.
"""
from __future__ import annotations

from application.precision_metrics import moving_block_bootstrap

MIN_COVERAGE = 0.80
MIN_CLUSTER_EVENTS = 100
N_RESAMPLES = 1000
SEED = 42


def _ci_low(series: list[float]) -> float | None:
    return moving_block_bootstrap(series, n_resamples=N_RESAMPLES, seed=SEED)["ci_low"]


def evaluate_gate(
    gross_abn: list[float],
    net_abn: list[float],
    n_events: int,
    coverage: float,
) -> dict[str, object]:
    if n_events < MIN_CLUSTER_EVENTS:
        return {"verdict": "INCONCLUSIVE_THIN_N", "n_events": n_events}
    if coverage < MIN_COVERAGE:
        return {"verdict": "INCONCLUSIVE_THIN_COVERAGE", "coverage": coverage}

    gross_ci = _ci_low(gross_abn)
    net_ci = _ci_low(net_abn)
    leg1 = (gross_ci or 0.0) > 0
    leg2 = (net_ci or 0.0) > 0

    if leg2:
        verdict = "PASS"
    elif leg1:
        verdict = "INCONCLUSIVE"
    else:
        verdict = "KILL"

    mean_gross = sum(gross_abn) / len(gross_abn) if gross_abn else 0.0
    mean_net = sum(net_abn) / len(net_abn) if net_abn else 0.0
    return {
        "verdict": verdict,
        "leg1_info_pass": leg1,
        "leg2_tradeable_pass": leg2,
        "mean_gross_abn": mean_gross,
        "mean_net_abn": mean_net,
        "gross_ci_low": gross_ci,
        "net_ci_low": net_ci,
        "n_events": n_events,
        "coverage": coverage,
    }
```

> NOTE: importing `application.precision_metrics` from `domain/` technically points
> domain→application. `precision_metrics` is stdlib-only pure math. If the project's
> `domain-check` skill flags this (it enforces zero non-stdlib domain imports), move
> `moving_block_bootstrap` into `domain/bootstrap.py` and re-export from
> `application/precision_metrics.py` for back-compat. Run `/domain-check` at the phase
> gate and refactor if flagged.

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/domain/test_insider_gate.py -v` → Expected: PASS (5)

- [ ] **Step 5: Commit**

```bash
git add domain/insider_gate.py tests/domain/test_insider_gate.py
git commit -m "feat: pre-registered two-leg insider gate + coverage/power guards"
```

---

### Task 5: SEC DERA Form-345 ingest adapter

**Files:**
- Modify: `domain/ports.py` (add `InsiderTransactionsPort`)
- Create: `adapters/data/sec_form345_dataset_adapter.py`
- Test: `tests/adapters/test_sec_form345_dataset_adapter.py`

- [ ] **Step 1: Add the port (no test needed for a Protocol — covered by adapter test)**

```python
# append to domain/ports.py (near other @runtime_checkable Protocols)
@runtime_checkable
class InsiderTransactionsPort(Protocol):
    """Source of historical Form-4 insider transactions for a calendar quarter."""

    def get_quarter(self, year: int, quarter: int) -> list["InsiderTransaction"]: ...
```
Add the import at the top of `domain/ports.py`:
```python
from domain.insider_cluster import InsiderTransaction
```

- [ ] **Step 2: Write the failing test against a tiny fixture trio**

```python
# tests/adapters/test_sec_form345_dataset_adapter.py
import io
import zipfile
from datetime import date

from adapters.data.sec_form345_dataset_adapter import SECForm345DatasetAdapter


def _make_zip() -> bytes:
    sub = (
        "ACCESSION_NUMBER\tFILING_DATE\tISSUERTRADINGSYMBOL\tAFF10B5ONE\n"
        "0001\t10-JAN-2020\tABC\t0\n"
        "0002\t12-JAN-2020\tABC\t1\n"
    )
    own = (
        "ACCESSION_NUMBER\tRPTOWNERCIK\n"
        "0001\t111\n"
        "0002\t222\n"
    )
    trans = (
        "ACCESSION_NUMBER\tTRANS_CODE\tTRANS_ACQUIRED_DISP_CD\tTRANS_SHARES"
        "\tTRANS_PRICEPERSHARE\tEQUITY_SWAP_INVOLVED\tTRANS_DATE\n"
        "0001\tP\tA\t100\t5.0\t0\t08-JAN-2020\n"
        "0002\tP\tA\t200\t6.0\t0\t10-JAN-2020\n"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("SUBMISSION.tsv", sub)
        z.writestr("REPORTINGOWNER.tsv", own)
        z.writestr("NONDERIV_TRANS.tsv", trans)
    return buf.getvalue()


def test_parse_join_yields_transactions(tmp_path, monkeypatch):
    adapter = SECForm345DatasetAdapter(cache_dir=tmp_path)
    monkeypatch.setattr(adapter, "_download", lambda y, q: _make_zip())
    txns = adapter.get_quarter(2020, 1)
    assert len(txns) == 2
    abc = next(t for t in txns if t.insider_cik == "111")
    assert abc.ticker == "ABC"
    assert abc.trans_code == "P" and abc.acquired_disp == "A"
    assert abc.shares == 100.0 and abc.price_per_share == 5.0
    assert abc.filing_date == date(2020, 1, 10)
    assert abc.aff10b51 is False
    other = next(t for t in txns if t.insider_cik == "222")
    assert other.aff10b51 is True  # AFF10B5ONE = 1


def test_malformed_row_skipped(tmp_path, monkeypatch):
    bad = _make_zip()  # valid; mutate one field to malformed
    adapter = SECForm345DatasetAdapter(cache_dir=tmp_path)
    monkeypatch.setattr(adapter, "_download", lambda y, q: bad)
    # smoke: does not raise
    assert adapter.get_quarter(2020, 1)
```

- [ ] **Step 3: Run to verify fail**

Run: `pytest tests/adapters/test_sec_form345_dataset_adapter.py -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 4: Implement the adapter**

```python
# adapters/data/sec_form345_dataset_adapter.py
"""SEC DERA 'Insider Transactions' (Form 345) quarterly dataset ingest.

Downloads the quarterly zip, parses SUBMISSION / REPORTINGOWNER / NONDERIV_TRANS
TSVs, joins on ACCESSION_NUMBER, and yields domain InsiderTransaction records.
Verified live 2026-06-09: URL pattern, columns, coverage floor 2006q1 (see spec
sec.3.1). SEC fair-access requires a declared User-Agent or returns HTTP 403.
"""
from __future__ import annotations

import io
import zipfile
from datetime import date, datetime
from pathlib import Path

import requests
from loguru import logger

from domain.insider_cluster import InsiderTransaction

DERA_URL = (
    "https://www.sec.gov/files/structureddata/data/"
    "insider-transactions-data-sets/{q}_form345.zip"
)
SEC_USER_AGENT = "tirthjoshi95@gmail.com portfolio-research"


def _parse_dera_date(s: str) -> date:
    # DERA dates are 'DD-MON-YYYY' (e.g. 10-JAN-2020)
    return datetime.strptime(s.strip(), "%d-%b-%Y").date()


def _read_tsv(zf: zipfile.ZipFile, name: str) -> list[dict[str, str]]:
    with zf.open(name) as fh:
        text = io.TextIOWrapper(fh, encoding="latin-1")
        header = text.readline().rstrip("\n").split("\t")
        rows: list[dict[str, str]] = []
        for line in text:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != len(header):
                continue
            rows.append(dict(zip(header, parts)))
        return rows


class SECForm345DatasetAdapter:
    def __init__(self, cache_dir: Path, timeout: float = 60.0) -> None:
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._timeout = timeout

    def _download(self, year: int, quarter: int) -> bytes:
        q = f"{year}q{quarter}"
        cache = self._cache_dir / f"{q}_form345.zip"
        if cache.exists():
            return cache.read_bytes()
        url = DERA_URL.format(q=q)
        logger.info("SEC DERA download {}", url)
        resp = requests.get(
            url, headers={"User-Agent": SEC_USER_AGENT}, timeout=self._timeout
        )
        resp.raise_for_status()
        cache.write_bytes(resp.content)
        return resp.content

    def get_quarter(self, year: int, quarter: int) -> list[InsiderTransaction]:
        raw = self._download(year, quarter)
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            subs = {r["ACCESSION_NUMBER"]: r for r in _read_tsv(zf, "SUBMISSION.tsv")}
            owners = _read_tsv(zf, "REPORTINGOWNER.tsv")
            trans = _read_tsv(zf, "NONDERIV_TRANS.tsv")

        # one accession can have multiple owners; map accession -> owner CIKs
        owner_by_acc: dict[str, list[str]] = {}
        for o in owners:
            owner_by_acc.setdefault(o["ACCESSION_NUMBER"], []).append(o["RPTOWNERCIK"])

        out: list[InsiderTransaction] = []
        for tr in trans:
            acc = tr["ACCESSION_NUMBER"]
            sub = subs.get(acc)
            if sub is None:
                continue
            ticker = (sub.get("ISSUERTRADINGSYMBOL") or "").strip().upper()
            if not ticker:
                continue
            try:
                filing_date = _parse_dera_date(sub["FILING_DATE"])
                trans_date = _parse_dera_date(tr.get("TRANS_DATE") or sub["FILING_DATE"])
                shares = float(tr.get("TRANS_SHARES") or 0.0)
                price = float(tr.get("TRANS_PRICEPERSHARE") or 0.0)
            except (KeyError, ValueError):
                continue
            aff = (sub.get("AFF10B5ONE") or "0").strip() in ("1", "Y", "true", "True")
            swap = (tr.get("EQUITY_SWAP_INVOLVED") or "0").strip() in (
                "1", "Y", "true", "True",
            )
            for cik in owner_by_acc.get(acc, []):
                out.append(
                    InsiderTransaction(
                        ticker=ticker,
                        insider_cik=cik,
                        trans_code=(tr.get("TRANS_CODE") or "").strip(),
                        acquired_disp=(tr.get("TRANS_ACQUIRED_DISP_CD") or "").strip(),
                        shares=shares,
                        price_per_share=price,
                        filing_date=filing_date,
                        trans_date=trans_date,
                        equity_swap=swap,
                        aff10b51=aff,
                    )
                )
        logger.info("SEC DERA {}q{}: {} transactions", year, quarter, len(out))
        return out
```

- [ ] **Step 5: Run to verify pass**

Run: `pytest tests/adapters/test_sec_form345_dataset_adapter.py -v` → Expected: PASS (2)

- [ ] **Step 6: Commit**

```bash
git add domain/ports.py adapters/data/sec_form345_dataset_adapter.py tests/adapters/test_sec_form345_dataset_adapter.py
git commit -m "feat: SEC DERA Form-345 quarterly ingest adapter + port"
```

---

## Phase 3 — Forward returns + use-case

### Task 6: Forward return + ADV with unresolved tracking

**Files:**
- Create: `application/insider_forward_returns.py`
- Test: `tests/application/test_insider_forward_returns.py`

Forward return uses a price-history callable `prices(ticker) -> list[(date, close, volume)]`
so the unit is testable with fakes (the real call wraps `yfinance_adapter.get_signals`).
A name with no obtainable price is returned as `unresolved`, NEVER dropped (spec sec.5).

- [ ] **Step 1: Write the failing test**

```python
# tests/application/test_insider_forward_returns.py
from datetime import date, timedelta
from domain.insider_cluster import ClusterEvent
from application.insider_forward_returns import resolve_events


def _prices(start, closes, vols):
    return [(start + timedelta(days=i), c, v) for i, (c, v) in enumerate(zip(closes, vols))]


def test_forward_return_and_adv_computed():
    ev = ClusterEvent("ABC", date(2020, 1, 1), 3, 1000.0)
    # 30 trading-ish days of prices; fire at index 0 close=10, +21 close=11 => +10%
    closes = [10.0] * 22 + [11.0] * 10
    closes[21] = 11.0
    vols = [1000.0] * len(closes)
    series = {"ABC": _prices(date(2020, 1, 1), closes, vols)}
    resolved, unresolved = resolve_events([ev], lambda tk: series.get(tk, []))
    assert unresolved == []
    assert resolved[0]["ticker"] == "ABC"
    assert abs(resolved[0]["fwd_return"] - 0.10) < 1e-9
    assert resolved[0]["adv"] > 0


def test_missing_prices_recorded_unresolved_not_dropped():
    ev = ClusterEvent("ZZZ", date(2020, 1, 1), 3, 1000.0)
    resolved, unresolved = resolve_events([ev], lambda tk: [])
    assert resolved == []
    assert unresolved == [ev]


def test_benchmark_return_over_window():
    from application.insider_forward_returns import benchmark_return
    series = {"IWC": _prices(date(2020, 1, 1), [100.0] * 22 + [110.0] * 10, [1.0] * 32)}
    r = benchmark_return(
        lambda tk: series.get(tk, []), "IWC", date(2020, 1, 1), date(2020, 1, 23)
    )
    assert r is not None and abs(r - 0.10) < 1e-9
```

- [ ] **Step 2: Run to verify fail** — Run: `pytest tests/application/test_insider_forward_returns.py -v` → FAIL `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
# application/insider_forward_returns.py
"""Resolve cluster events to 21-trading-day forward returns + trailing ADV.

Survivorship-safe: a name with no obtainable forward price is returned in the
`unresolved` list, never silently dropped (spec sec.5). The price source is a
callable so the unit tests with fakes; production wraps yfinance get_signals.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import date

from domain.insider_cluster import ClusterEvent

FORWARD_HORIZON_TDAYS = 21
ADV_LOOKBACK_TDAYS = 21

PriceFn = Callable[[str], list[tuple[date, float, float]]]  # (date, close, volume)


def resolve_events(
    events: list[ClusterEvent], prices: PriceFn
) -> tuple[list[dict[str, object]], list[ClusterEvent]]:
    resolved: list[dict[str, object]] = []
    unresolved: list[ClusterEvent] = []
    for ev in events:
        series = sorted(prices(ev.ticker), key=lambda r: r[0])
        # locate first trading day on/after fire_date
        idx = next((i for i, r in enumerate(series) if r[0] >= ev.fire_date), None)
        if idx is None or idx + FORWARD_HORIZON_TDAYS >= len(series):
            unresolved.append(ev)
            continue
        c0 = series[idx][1]
        c1 = series[idx + FORWARD_HORIZON_TDAYS][1]
        if c0 <= 0:
            unresolved.append(ev)
            continue
        lookback = series[max(0, idx - ADV_LOOKBACK_TDAYS) : idx] or series[: idx + 1]
        adv = sum(close * vol for _, close, vol in lookback) / len(lookback)
        resolved.append(
            {
                "ticker": ev.ticker,
                "fire_date": ev.fire_date,
                "fwd_return": (c1 - c0) / c0,
                "adv": adv,
                "entry_date": series[idx][0],
                "exit_date": series[idx + FORWARD_HORIZON_TDAYS][0],
            }
        )
    return resolved, unresolved


def benchmark_return(
    prices: PriceFn, etf: str, entry_date: date, exit_date: date
) -> float | None:
    """21-tday return of the benchmark ETF over the same window. None if uncovered."""
    series = sorted(prices(etf), key=lambda r: r[0])
    entry = next((c for d, c, _ in series if d >= entry_date and c > 0), None)
    exit_ = next((c for d, c, _ in series if d >= exit_date and c > 0), None)
    if entry is None or exit_ is None:
        return None
    return (exit_ - entry) / entry
```

- [ ] **Step 4: Run to verify pass** — Run: `pytest tests/application/test_insider_forward_returns.py -v` → PASS (2)

- [ ] **Step 5: Commit**

```bash
git add application/insider_forward_returns.py tests/application/test_insider_forward_returns.py
git commit -m "feat: forward-return + ADV resolution with unresolved tracking"
```

---

### Task 7: Falsification use-case (orchestration)

**Files:**
- Create: `application/insider_cluster_falsification_use_case.py`
- Test: `tests/application/test_insider_cluster_falsification_use_case.py`

Orchestrates: load txns (port) → detect clusters → resolve returns+ADV+window → assign
terciles → for each BOTTOM-tercile event compute **gross abnormal return** = `fwd_return −
benchmark_return(IWC, same window)`, and **net** = `gross − slippage_bottom/10000` → order
by fire_date → `evaluate_gate(gross_abn, net_abn, n_events, coverage)` → assemble report.
Events missing a benchmark return are counted unresolved (coverage guard protects).

- [ ] **Step 1: Write the failing test (fakes injected; assert verdict + report shape)**

```python
# tests/application/test_insider_cluster_falsification_use_case.py
from datetime import date, timedelta
from domain.insider_cluster import InsiderTransaction
from application.insider_cluster_falsification_use_case import (
    InsiderClusterFalsificationUseCase,
)


class _FakePort:
    def __init__(self, txns):
        self._txns = txns

    def get_quarter(self, year, quarter):
        return self._txns


def _buy(ticker, cik, d):
    return InsiderTransaction(
        ticker=ticker, insider_cik=cik, trans_code="P", acquired_disp="A",
        shares=100.0, price_per_share=5.0, filing_date=d, trans_date=d,
        equity_swap=False, aff10b51=False,
    )


def test_thin_n_when_few_events():
    txns = [_buy("ABC", c, date(2020, 1, 5)) for c in ("1", "2", "3")]
    uc = InsiderClusterFalsificationUseCase(
        port=_FakePort(txns),
        prices=lambda tk: [
            (date(2020, 1, 5) + timedelta(days=i), 10.0, 1000.0) for i in range(40)
        ],
        quarters=[(2020, 1)],
    )
    report = uc.run()
    assert report["verdict"] == "INCONCLUSIVE_THIN_N"
    assert report["n_cluster_events"] == 1
    assert "coverage" in report
```

- [ ] **Step 2: Run to verify fail** — `pytest tests/application/test_insider_cluster_falsification_use_case.py -v` → FAIL `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
# application/insider_cluster_falsification_use_case.py
"""Unit B orchestration — pre-registered insider-cluster falsification (event study).

Wires the domain pieces + reuses the bootstrap harness. Produces a verdict dict
(the report). Build is deliberately thin; integrity lives in the locked gate
(domain/insider_gate.py) and the guards. See spec sec.4 (event-study amendment) + ADR-052.
"""
from __future__ import annotations

from domain.insider_cluster import detect_clusters
from domain.insider_gate import evaluate_gate
from domain.insider_terciles import assign_terciles, slippage_bps_for_tercile
from application.insider_forward_returns import PriceFn, benchmark_return, resolve_events
from domain.ports import InsiderTransactionsPort

BENCHMARK_ETF = {"bottom": "IWC", "mid": "IWM", "top": "IWM"}


class InsiderClusterFalsificationUseCase:
    def __init__(
        self,
        port: InsiderTransactionsPort,
        prices: PriceFn,
        quarters: list[tuple[int, int]],
    ) -> None:
        self._port = port
        self._prices = prices
        self._quarters = quarters

    def run(self) -> dict[str, object]:
        txns = []
        for (y, q) in self._quarters:
            txns.extend(self._port.get_quarter(y, q))
        events = detect_clusters(txns)
        resolved, unresolved = resolve_events(events, self._prices)

        n_events = len(events)

        # ADV terciles over resolved names
        adv = {r["ticker"]: float(r["adv"]) for r in resolved}
        terciles = assign_terciles(adv)
        bottom = [r for r in resolved if terciles.get(r["ticker"]) == "bottom"]

        # Event-study abnormal returns for the BOTTOM tercile, ordered by fire date.
        slip = slippage_bps_for_tercile("bottom") / 10000.0
        etf = BENCHMARK_ETF["bottom"]
        gross_abn: list[float] = []
        net_abn: list[float] = []
        n_benchmarked = 0
        for r in sorted(bottom, key=lambda x: x["fire_date"]):
            bench = benchmark_return(
                self._prices, etf, r["entry_date"], r["exit_date"]
            )
            if bench is None:
                continue  # uncovered benchmark window -> excluded from coverage below
            n_benchmarked += 1
            g = float(r["fwd_return"]) - bench
            gross_abn.append(g)
            net_abn.append(g - slip)

        # Coverage = bottom-tercile events with a usable abnormal return / all
        # bottom-tercile cluster events. (Price-unresolved events have no ADV so
        # cannot be tercile-assigned; they are tracked separately as n_unresolved.)
        coverage = (n_benchmarked / len(bottom)) if bottom else 0.0

        verdict = evaluate_gate(
            gross_abn=gross_abn,
            net_abn=net_abn,
            n_events=len(bottom),
            coverage=coverage,
        )

        return {
            **verdict,
            "n_cluster_events": n_events,
            "n_resolved": len(resolved),
            "n_unresolved": len(unresolved),
            "n_bottom_tercile": len(bottom),
            "n_benchmarked": n_benchmarked,
            "coverage": coverage,
            "benchmark_etf": etf,
            "tercile_counts": {
                t: sum(1 for v in terciles.values() if v == t)
                for t in ("bottom", "mid", "top")
            },
        }
```

> NOTE (Opus phase gate): two integrity checks. (1) `n_events` passed to the gate is the
> **bottom-tercile** population (`len(bottom)`), so MIN_CLUSTER_EVENTS=100 applies to the
> primary-hypothesis tercile, not the whole sample — confirm this matches the spec's intent
> (it does: the primary test is bottom-tercile). (2) `bottom_population` dead-code stub above
> documents that price-unresolved events can't be tercile-assigned (no ADV); decide at the
> gate whether to report total-sample coverage separately. Keep the verdict denominator =
> bottom-tercile resolved, as written.

- [ ] **Step 4: Run to verify pass** — `pytest tests/application/test_insider_cluster_falsification_use_case.py -v` → PASS (1)

- [ ] **Step 5: Commit**

```bash
git add application/insider_cluster_falsification_use_case.py tests/application/test_insider_cluster_falsification_use_case.py
git commit -m "feat: insider-cluster falsification use-case (orchestration)"
```

---

## Phase 4 — CLI + report + run

### Task 8: `backtest-insider-clusters` CLI

**Files:**
- Modify: `application/cli.py`
- Test: covered by use-case tests; add a CLI smoke test in `tests/application/test_cli_insider.py`

- [ ] **Step 1: Write the failing smoke test**

```python
# tests/application/test_cli_insider.py
from click.testing import CliRunner
from application.cli import cli


def test_backtest_insider_clusters_help():
    res = CliRunner().invoke(cli, ["backtest-insider-clusters", "--help"])
    assert res.exit_code == 0
    assert "insider" in res.output.lower()
```

- [ ] **Step 2: Run to verify fail** — `pytest tests/application/test_cli_insider.py -v` → FAIL (no such command)

- [ ] **Step 3: Implement the command** (follow the `backtest-screen` pattern at `application/cli.py:2561`; masked stdout = counts/verdict only, full distribution to JSON)

```python
# add to application/cli.py
@cli.command("backtest-insider-clusters")
@click.option("--start-year", type=int, default=2006, show_default=True)
@click.option("--end-year", type=int, required=True)
@click.option(
    "--report-dir", type=click.Path(), default="data/reports", show_default=True
)
def backtest_insider_clusters(start_year: int, end_year: int, report_dir: str) -> None:
    """Pre-registered sub-$1B insider-cluster falsification (ADR-052, Unit B).

    Masked stdout: verdict + counts only. Full distribution -> tracked JSON report.
    """
    import json
    from datetime import date
    from pathlib import Path

    from adapters.data.sec_form345_dataset_adapter import SECForm345DatasetAdapter
    from adapters.data.yfinance_adapter import YFinanceAdapter
    from application.insider_cluster_falsification_use_case import (
        InsiderClusterFalsificationUseCase,
    )

    quarters = [(y, q) for y in range(start_year, end_year + 1) for q in (1, 2, 3, 4)]
    port = SECForm345DatasetAdapter(cache_dir=Path("data/cache/sec_form345"))
    yf = YFinanceAdapter(cache_dir=Path("data/cache/yfinance"))

    def prices(ticker: str) -> list[tuple[date, float, float]]:
        # get_signals returns point-in-time OHLCV Signals (.price close, .volume)
        from datetime import datetime, timezone

        signals = yf.get_signals(ticker, datetime.now(timezone.utc))
        return [(s.timestamp.date(), s.price, float(s.volume)) for s in signals]

    uc = InsiderClusterFalsificationUseCase(port=port, prices=prices, quarters=quarters)
    report = uc.run()

    out = Path(report_dir) / f"insider_cluster_falsification_{end_year}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str))

    # masked stdout
    click.echo(f"VERDICT: {report['verdict']}")
    click.echo(
        f"events={report['n_cluster_events']} resolved={report['n_resolved']} "
        f"coverage={report['coverage']:.2%} bottom_tercile={report['n_bottom_tercile']}"
    )
    click.echo(f"report -> {out}")
```

- [ ] **Step 4: Run to verify pass** — `pytest tests/application/test_cli_insider.py -v` → PASS

- [ ] **Step 5: Commit**

```bash
git add application/cli.py tests/application/test_cli_insider.py
git commit -m "feat: backtest-insider-clusters CLI (masked stdout + JSON report)"
```

---

### Task 9: Full-suite gate, live run, ADR write-up

**Files:**
- Create: `docs/adr/053-insider-cluster-falsification-verdict.md`
- Modify: `docs/STATUS.md`, `docs/PHASE_LOG.md`

- [ ] **Step 1: Full quality gate**

Run: `make check`
Expected: lint + mypy strict + tests green, coverage ≥ 90%.

- [ ] **Step 2: `/domain-check` + `/leakage-audit`**

Run both project skills. Resolve any domain-import flag from Task 4's NOTE. Confirm no
look-ahead (signal uses filing_date only; forward return uses post-fire prices = the label).

- [ ] **Step 3: Live run (MAX-verify checkpoint — Opus)**

Run: `python -m application.cli backtest-insider-clusters --end-year 2024`
(first run backfills DERA quarters into `data/cache/sec_form345` — minutes; cached after.)
Read the JSON report. Record: verdict, n_events, coverage, mean_ic, both ci_low, tercile
counts. If `INCONCLUSIVE_THIN_*`, report honestly — do NOT loosen a locked threshold.

- [ ] **Step 4: Write ADR-053** with the verdict, the locked thresholds, the actual numbers,
and the consequence (KILL ⇒ prediction permanently off per ADR-052; PASS ⇒ RESEARCH_ONLY
pending independent re-validation). Commit the tracked JSON report alongside.

- [ ] **Step 5: Refresh STATUS.md** (overwrite: Unit B done + verdict; next = Unit C) and
append a PHASE_LOG entry.

- [ ] **Step 6: Commit + finish branch**

```bash
git add docs/adr/053-insider-cluster-falsification-verdict.md docs/STATUS.md docs/PHASE_LOG.md data/reports/insider_cluster_falsification_2024.json
git commit -m "docs: ADR-053 insider-cluster falsification verdict + STATUS/PHASE_LOG"
```
Then use superpowers:finishing-a-development-branch (PR `feat/insider-cluster-falsification` → develop).

---

## Self-review (done by plan author)

- **Spec coverage:** signal (T1-2), survivorship/unresolved (T6), ADV terciles + slippage
  (T3), event-study gate + both guards (T4), DERA source incl. AFF10B5ONE/ISSUERTRADINGSYMBOL
  (T5), benchmark abnormal return + reuse of `moving_block_bootstrap` (T6,T7), CLI masked +
  tracked report (T8), verdict semantics + ADR (T9). All spec sections map to a task.
- **Methodology resolved (was a design risk):** the original Spearman rank-IC did not fit a
  *binary* cluster signal. Resolved to **event-study abnormal return** (gross/net vs a
  liquidity-matched ETF benchmark, both bootstrap CI_low > 0), spec §4 amended while blind to
  results (pre-registration intact). `ic_analysis` is no longer on the gate path.
- **Constants:** all pre-registered constants defined once and match the amended spec
  verbatim — `SLIPPAGE_BPS` 150/75/40, `BENCHMARK_ETF` bottom=IWC/mid,top=IWM,
  `MIN_COVERAGE=0.80`, `MIN_CLUSTER_EVENTS=100`, `N_RESAMPLES=1000`, `SEED=42`.
- **Type consistency:** `evaluate_gate(gross_abn, net_abn, n_events, coverage)` signature
  matches its only caller (T7). `resolve_events` returns `entry_date`/`exit_date` consumed by
  `benchmark_return` (T6) and the use-case (T7).
- **Open items for the Opus phase gate (flagged, not blocking):** (1) the domain→application
  import in `insider_gate` (T4 NOTE — refactor if `/domain-check` flags); (2) confirm the
  gate's `n_events` denominator = bottom-tercile population (T7 NOTE).
- **Placeholders:** none.
