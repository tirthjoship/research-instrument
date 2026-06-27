# Spec — SP5: Hypothesis #9 Pre-registered Forward Validation Gate

**Date:** 2026-06-23
**Status:** Approved for implementation
**Depends on:** SP1 (CorroborationStore weekly snapshots), SP2 (candidate surfacing), SP3 (screener overlay)
**Branch:** `feat/sp5-forward-gate` off `develop`

---

## Purpose

Answer honestly: **does STRONG-tier corroboration forward-beat SPY?** Hypothesis #9 — 8 prior hypotheses ALL failed. Must be pre-registered and forward-only (harvested recs cannot be backtested — no historical snapshot exists). Mirrors ADR-048 discipline forward-gate pattern. ADR-064 locks all gate parameters before any resolution data accrues.

Corroboration stays **RESEARCH_ONLY** until gate passes. Permanent KILL if gate fails at n≥30.

---

## Locked Decisions

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| 1 | Unit of observation | per-ticker-snapshot `(ticker, snapshot_date)` pair | Reaches n=30 in ~3-5 weeks vs 7.5 months for per-run batch |
| 2 | Gate statistic | Mean 21d excess vs SPY; block-bootstrap 95% CI lower bound > 0 | Matches discipline gate pattern; interpretable |
| 3 | Economic bar | 50 bps (0.005) mean 21d excess | Meaningful alpha (~12% annualised); not trivially achievable by noise |
| 4 | Tier scope | STRONG only | MODERATE dilutes the test; fail means the top tier has no edge |
| 5 | Secondary metric | Hit rate (% STRONG beats SPY at 21d) — displayed, not gated | Legibility without muddying the pre-registered criterion |
| 6 | Secondary horizon | 63d excess — displayed, not gated | Informational long-term framing at near-zero resolver cost |
| 7 | KILL clause | Permanent on first evaluation where n≥30 and gate fails | Pre-registration is meaningless if revival is allowed |
| 8 | Source learning | Deferred — `reliability_weight` stays static in SP5 | Kill clause makes SP5 the proof-of-concept; learning loop adds risk before signal is validated |
| 9 | Gate state storage | `data/corroboration_gate_log.jsonl` + `data/corroboration_samples.jsonl` | Mirrors `discipline_log.jsonl` pattern; audit trail; no DB overhead |
| 10 | Scheduling | Included — shell script + launchd plist | Feature is dead without automation; copy of discipline pattern |
| 11 | ADR | ADR-064 as Task 1 (committed before any resolver code runs) | Pre-registration requires the lock to precede data |
| 12 | New port | `ResolverPricePort.price_at(ticker: str, on: date) -> float` | Existing `PricePort` is wrong shape; minimal new protocol keeps ports clean |
| 13 | Deduplication | By `(ticker, snapshot_date)` on load | Resolver is idempotent — safe to re-run weekly |

---

## Architecture

### New files

```
docs/adr/ADR-063-sp3-screener-blend-formula.md     (retroactive, Task 0)
docs/adr/ADR-064-corroboration-forward-gate.md      (pre-registration, Task 1)
domain/corroboration_gate.py                        (pure stdlib, gate logic)
application/corroboration_resolver_use_case.py      (orchestration)
adapters/data/corroboration_gate_log.py             (JSONL adapter)
scripts/corroboration_weekly_resolve.sh             (shell script)
tests/domain/test_corroboration_gate.py
tests/application/test_corroboration_resolver.py
tests/adapters/test_corroboration_gate_log.py
tests/test_cli_corroboration_resolve.py
```

### Modified files

```
domain/ports.py                                     (add ResolverPricePort)
application/cli/corroboration_commands.py           (add 2 commands)
docs/scheduling.md                                  (add plist)
```

### Data flow

```
corroborate (weekly) → CorroborationStore (harvested_recs, candidates_snapshot)
                              ↓ (21+ days later)
           resolve-corroboration
             → load STRONG snapshots ≥21d old
             → fetch ticker + SPY prices via ResolverPricePort
             → build GateSamples
             → append to corroboration_samples.jsonl (dedup by ticker+snapshot_date)
             → evaluate_gate() if n_resolved ≥ 30
             → append GateResult to corroboration_gate_log.jsonl
                              ↓
    corroboration-calibration-status
             → load samples + latest GateResult
             → display: n, mean_excess_21d, CI, hit_rate, mean_excess_63d, verdict
```

---

## Domain Types (`domain/corroboration_gate.py`)

Pure stdlib. Zero external imports.

```python
@dataclass(frozen=True)
class GateSample:
    ticker: str
    snapshot_date: date
    resolved_at: date
    excess_21d: float        # ticker 21d return − SPY 21d return
    excess_63d: float | None # None if <63d elapsed at resolution time
    beat_spy_21d: bool

@dataclass(frozen=True)
class GateResult:
    n_resolved: int
    mean_excess_21d: float
    ci_lower: float          # block-bootstrap 95% CI lower bound on mean excess
    ci_upper: float
    hit_rate_21d: float      # fraction of samples where beat_spy_21d is True
    mean_excess_63d: float | None
    verdict: Literal["PENDING", "PASS", "FAIL"]
    evaluated_at: date

def evaluate_gate(
    samples: list[GateSample],
    min_n: int = 30,
    economic_bar: float = 0.005,
) -> GateResult:
    """PENDING if n < min_n. PASS if ci_lower > 0 AND mean_excess ≥ economic_bar. FAIL otherwise."""
```

**Verdict logic:**
- `n < 30` → `PENDING` (no evaluation written to log)
- `n ≥ 30` AND `ci_lower > 0` AND `mean_excess_21d ≥ 0.005` → `PASS`
- `n ≥ 30` AND either condition fails → `FAIL` (permanent)

Bootstrap: `moving_block_bootstrap` from `domain/bootstrap.py` (already exists, stdlib-only).

---

## New Port (`domain/ports.py`)

```python
class ResolverPricePort(Protocol):
    def price_at(self, ticker: str, on: date) -> float:
        """Closing price for ticker on the given date. Raises if unavailable."""
        ...
```

Resolver computes cumulative return as `(price_at(ticker, end) - price_at(ticker, start)) / price_at(ticker, start)` inline.

---

## Resolver Use Case (`application/corroboration_resolver_use_case.py`)

```python
class CorroborationResolverUseCase:
    def __init__(self, store: CorroborationStore, price: ResolverPricePort) -> None: ...

    def resolve(self, as_of: date) -> list[GateSample]:
        """Load STRONG snapshots ≥21d old, compute excess returns, return GateSamples.
        Idempotent — caller deduplicates by (ticker, snapshot_date)."""
        snapshots = self._store.get_snapshots(as_of, window_days=90)
        strong = [s for s in snapshots if s.convergence_tier == ConvergenceTier.STRONG]
        cutoff = as_of - timedelta(days=21)
        resolvable = [s for s in strong if s.surfaced_at <= cutoff]
        samples = []
        for snap in resolvable:
            t0, t21 = snap.surfaced_at, snap.surfaced_at + timedelta(days=21)
            t63 = snap.surfaced_at + timedelta(days=63)
            ticker_21 = _ret(self._price, snap.ticker, t0, t21)
            spy_21    = _ret(self._price, "SPY", t0, t21)
            excess_63 = None
            if as_of >= t63:
                excess_63 = (_ret(self._price, snap.ticker, t0, t63)
                             - _ret(self._price, "SPY", t0, t63))
            samples.append(GateSample(
                ticker=snap.ticker,
                snapshot_date=t0,
                resolved_at=as_of,
                excess_21d=ticker_21 - spy_21,
                excess_63d=excess_63,
                beat_spy_21d=ticker_21 > spy_21,
            ))
        return samples

def _ret(price: ResolverPricePort, ticker: str, start: date, end: date) -> float:
    p0, p1 = price.price_at(ticker, start), price.price_at(ticker, end)
    return (p1 - p0) / p0
```

Price fetch failures are logged and skip that sample (don't crash the job).

---

## Gate Log Adapter (`adapters/data/corroboration_gate_log.py`)

```python
SAMPLES_PATH = Path("data/corroboration_samples.jsonl")
RESULTS_PATH = Path("data/corroboration_gate_log.jsonl")

def append_samples(samples: list[GateSample], path: Path = SAMPLES_PATH) -> None:
    """Deduplicate by (ticker, snapshot_date) before appending new samples."""

def load_samples(path: Path = SAMPLES_PATH) -> list[GateSample]:
    """Read all samples. Returns [] if file missing."""

def append_result(result: GateResult, path: Path = RESULTS_PATH) -> None:
    """Append a GateResult. Only called when verdict != PENDING."""

def load_latest_result(path: Path = RESULTS_PATH) -> GateResult | None:
    """Most recent GateResult. None if never evaluated (still PENDING)."""
```

Both files gitignored (local data). Dedup key: `f"{s.ticker}:{s.snapshot_date.isoformat()}"`.

---

## CLI Commands (add to `corroboration_commands.py`)

### `resolve-corroboration`

```
Usage: stockrec resolve-corroboration [--as-of DATE]
```

1. Build `CorroborationResolverUseCase` with yfinance `ResolverPricePort`
2. Call `resolve(as_of)` → new samples
3. Load existing samples, dedup, append new ones
4. If n_resolved ≥ 30: `evaluate_gate()` → append `GateResult`
5. Print: `resolved N new samples (total: M). Gate: PENDING | PASS | FAIL`

Gate FAIL prints a prominent warning: `HYPOTHESIS #9 FAILED — corroboration stays RESEARCH_ONLY (permanent).`

### `corroboration-calibration-status`

```
Usage: stockrec corroboration-calibration-status
```

Mirrors `discipline-calibration-status` output format:

```
Corroboration Forward Gate (Hypothesis #9)
  verdict:          PENDING
  n resolved:       12 / 30 required
  mean excess 21d:  +0.31%
  95% CI:           [−0.12%, +0.74%]
  hit rate 21d:     58%
  mean excess 63d:  n/a (insufficient data)
  gate locked:      2026-06-23 (ADR-064)
  RESEARCH_ONLY until gate passes.
```

---

## Scheduling

**`scripts/corroboration_weekly_resolve.sh`:**

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
uv run python -m application.cli resolve-corroboration
uv run python -m application.cli corroboration-calibration-status
```

**Plist:** `com.tirthjoshi.stockrec.corroboration-weekly` — runs Sunday 18:00 local time (after market close + corroborate job). Added to `docs/scheduling.md`.

---

## Testing Strategy

| File | What | Pattern |
|---|---|---|
| `tests/domain/test_corroboration_gate.py` | `evaluate_gate()` — PENDING/PASS/FAIL, CI, economic bar, n boundary | Hypothesis property-based + unit |
| `tests/domain/test_corroboration_gate.py` | n=29 → PENDING; n=30 + ci<0 → FAIL; n=30 + excess<50bps → FAIL | unit |
| `tests/application/test_corroboration_resolver.py` | price fetching, excess calc, idempotency, price failure skip | fake `ResolverPricePort` |
| `tests/adapters/test_corroboration_gate_log.py` | append/load/dedup, missing file returns `[]` | `tmp_path` |
| `tests/test_cli_corroboration_resolve.py` | `resolve-corroboration` + `calibration-status` output | `CliRunner` + fakes |

No live yfinance calls in any test.

---

## Out of Scope

- Source reliability update / learning loop → deferred (see future-enhancements note in STATUS.md)
- Historical backtest of LLM-harvested recs (impossible — no historical snapshot)
- Dashboard badge (SP6)
- Live trading off badge
