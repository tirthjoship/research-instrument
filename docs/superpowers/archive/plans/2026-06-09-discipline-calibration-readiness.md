# Discipline Calibration-Readiness Harness — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (or subagent-driven-development) to implement task-by-task, TDD, committing each. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Make the ADR-048 discipline forward-gate resolve on *date-diverse* data and make its readiness *visible* — via daily logging, a readiness-status CLI, and a symmetric pre-resolution date-diversity guard — without changing any locked ADR-048 threshold.

**Architecture:** One pure stdlib module `application/calibration_readiness.py` (all date-diversity / readiness / guard math, unit-tested on synthetic logged-row dicts, no network) + two CLI surfaces (`discipline-calibration-status`; a guard label wrapped around `resolve-discipline-flags`) + a corrected daily launchd cron + ADR-051. No `domain/` change.

**Tech Stack:** Python 3.12 stdlib, click CLI, pytest, mypy strict, black/isort/ruff. Spec: `docs/superpowers/specs/2026-06-09-discipline-calibration-readiness-design.md`.

**Logged-row schema (verbatim, from `holdings-risk`):** keys `ticker`, `verdict` (REDUCE/TRIM/ADD_OK/HOLD/REVIEW), `price`, `trend_health`, `as_of` (full ISO timestamp string, e.g. `"2026-06-08T09:09:17.844714+00:00"`). Date-diversity dedupes on the **date** part. REDUCE is the only directional down-call (ADR-048).

**Locked constants (do NOT retune):** horizon 21 calendar days; gate thresholds `down_rate ≥ 0.55` AND `brier ≤ 0.45` AND `n ≥ 30`; diversity precondition `k_dates = 3` distinct as_of dates, `d_days = 10` calendar-day span.

---

## File Structure

- **Create** `application/calibration_readiness.py` — pure: `spread_of_as_ofs`, `as_of_spread`, `resolvable_split`, `freshness`, `ReadinessReport`, `readiness`, `diversity_label`.
- **Create** `tests/test_calibration_readiness.py`.
- **Modify** `application/discipline_log.py` — `resolve_flags` also returns `reduce_resolved_as_ofs`.
- **Modify** `application/cli.py` — add `discipline-calibration-status`; wrap `resolve-discipline-flags` label with `diversity_label`.
- **Create** `tests/test_cli_calibration_readiness.py`.
- **Create** `scripts/discipline_daily.sh`.
- **Modify** `docs/scheduling.md` — corrected daily `holdings-risk` plist section.
- **Create** `docs/adr/051-calibration-readiness-date-diversity.md`.

---

## Task 1: `as_of` spread (`application/calibration_readiness.py`)

**Files:** Create `application/calibration_readiness.py`; Test `tests/test_calibration_readiness.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_calibration_readiness.py
from application.calibration_readiness import as_of_spread, spread_of_as_ofs


def _row(verdict: str, as_of: str) -> dict[str, object]:
    return {"ticker": "X", "verdict": verdict, "price": 1.0, "as_of": as_of}


def test_spread_empty() -> None:
    s = spread_of_as_ofs([])
    assert s == {"distinct_dates": 0, "span_days": 0, "min_date": None, "max_date": None}


def test_spread_single_date_dedupes_timestamps() -> None:
    s = spread_of_as_ofs(
        ["2026-06-08T09:00:00+00:00", "2026-06-08T17:30:00+00:00"]
    )
    assert s["distinct_dates"] == 1
    assert s["span_days"] == 0
    assert s["min_date"] == "2026-06-08"


def test_spread_multi_date_span() -> None:
    s = spread_of_as_ofs(
        ["2026-06-08T09:00:00+00:00", "2026-06-18T09:00:00+00:00"]
    )
    assert s["distinct_dates"] == 2
    assert s["span_days"] == 10
    assert s["max_date"] == "2026-06-18"


def test_as_of_spread_reads_rows() -> None:
    rows = [_row("REDUCE", "2026-06-08T09:00:00+00:00"),
            _row("REDUCE", "2026-06-13T09:00:00+00:00")]
    s = as_of_spread(rows)
    assert s["distinct_dates"] == 2 and s["span_days"] == 5
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_calibration_readiness.py -v`
Expected: FAIL `ModuleNotFoundError: No module named 'application.calibration_readiness'`.

- [ ] **Step 3: Implement**

```python
# application/calibration_readiness.py
"""Pure date-diversity / readiness math for the discipline forward-calibration gate.

Strengthens the ADR-048 experimental design (pre-outcome) by measuring the as_of
diversity of the REDUCE forward-log sample. Changes NO locked threshold. Stdlib
only; unit-testable on synthetic logged-row dicts (no network). See ADR-051.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

__all__ = [
    "spread_of_as_ofs",
    "as_of_spread",
    "resolvable_split",
    "freshness",
    "ReadinessReport",
    "readiness",
    "diversity_label",
]

REDUCE = "REDUCE"


def _date_of(as_of: str) -> date:
    return datetime.fromisoformat(as_of).date()


def spread_of_as_ofs(as_ofs: list[str]) -> dict[str, Any]:
    """Distinct as_of DATES + calendar span across a list of ISO timestamp strings."""
    dates = sorted({_date_of(s) for s in as_ofs})
    if not dates:
        return {"distinct_dates": 0, "span_days": 0, "min_date": None, "max_date": None}
    return {
        "distinct_dates": len(dates),
        "span_days": (dates[-1] - dates[0]).days,
        "min_date": dates[0].isoformat(),
        "max_date": dates[-1].isoformat(),
    }


def as_of_spread(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """spread_of_as_ofs over the as_of field of every row that has one."""
    return spread_of_as_ofs([str(r["as_of"]) for r in rows if "as_of" in r])
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_calibration_readiness.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add application/calibration_readiness.py tests/test_calibration_readiness.py
git commit -m "feat(calib): as_of date-diversity spread (pure)"
```

---

## Task 2: resolvable split + freshness (`application/calibration_readiness.py`)

**Files:** Modify `application/calibration_readiness.py`; Test `tests/test_calibration_readiness.py`

- [ ] **Step 1: Write the failing tests (append)**

```python
# tests/test_calibration_readiness.py  (append)
from datetime import date

from application.calibration_readiness import freshness, resolvable_split


def test_resolvable_split_counts_reduce_only_past_horizon() -> None:
    rows = [
        _row("REDUCE", "2026-05-01T09:00:00+00:00"),  # old -> resolvable
        _row("REDUCE", "2026-06-08T09:00:00+00:00"),  # recent -> pending
        _row("TRIM", "2026-05-01T09:00:00+00:00"),    # not REDUCE -> ignored
    ]
    out = resolvable_split(rows, today=date(2026, 6, 9), horizon_days=21)
    assert out == {"resolvable": 1, "pending": 1}


def test_resolvable_split_boundary_exactly_horizon_is_resolvable() -> None:
    rows = [_row("REDUCE", "2026-05-19T00:00:00+00:00")]  # +21d = 2026-06-09
    out = resolvable_split(rows, today=date(2026, 6, 9), horizon_days=21)
    assert out == {"resolvable": 1, "pending": 0}


def test_freshness_days_since_last() -> None:
    rows = [_row("HOLD", "2026-06-04T09:00:00+00:00"),
            _row("REDUCE", "2026-06-08T09:00:00+00:00")]
    assert freshness(rows, today=date(2026, 6, 9)) == 1


def test_freshness_none_when_empty() -> None:
    assert freshness([], today=date(2026, 6, 9)) is None
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_calibration_readiness.py -k "resolvable or freshness" -v`
Expected: FAIL `ImportError: cannot import name 'resolvable_split'`.

- [ ] **Step 3: Implement (append)**

```python
# application/calibration_readiness.py  (append)
def resolvable_split(
    rows: list[dict[str, Any]], today: date, horizon_days: int
) -> dict[str, int]:
    """REDUCE flags whose horizon has elapsed by `today` (resolvable) vs not (pending)."""
    resolvable = pending = 0
    for r in rows:
        if r.get("verdict") != REDUCE:
            continue
        if _date_of(str(r["as_of"])) + timedelta(days=horizon_days) <= today:
            resolvable += 1
        else:
            pending += 1
    return {"resolvable": resolvable, "pending": pending}


def freshness(rows: list[dict[str, Any]], today: date) -> int | None:
    """Calendar days since the most recent as_of date. None if no rows."""
    dates = [_date_of(str(r["as_of"])) for r in rows if "as_of" in r]
    if not dates:
        return None
    return (today - max(dates)).days
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_calibration_readiness.py -k "resolvable or freshness" -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add application/calibration_readiness.py tests/test_calibration_readiness.py
git commit -m "feat(calib): resolvable/pending split + log freshness (pure)"
```

---

## Task 3: readiness report (`application/calibration_readiness.py`)

**Files:** Modify `application/calibration_readiness.py`; Test `tests/test_calibration_readiness.py`

- [ ] **Step 1: Write the failing tests (append)**

```python
# tests/test_calibration_readiness.py  (append)
from application.calibration_readiness import readiness


def _reduce_on(dates: list[str]) -> list[dict[str, object]]:
    return [_row("REDUCE", f"{d}T09:00:00+00:00") for d in dates]


def test_readiness_single_date_is_thin_even_with_many_flags() -> None:
    rows = _reduce_on(["2026-06-08"] * 40)  # n big, but one date
    rep = readiness(rows, today=date(2026, 6, 9), horizon_days=21,
                    gate_date=date(2026, 7, 15))
    assert rep.verdict == "THIN"
    assert any("distinct_dates" in s for s in rep.shortfalls)


def test_readiness_diverse_and_enough_is_ready() -> None:
    # 30 flags across 3 dates spanning 14 days, all resolvable by the gate.
    dates = ["2026-06-09"] * 10 + ["2026-06-16"] * 10 + ["2026-06-23"] * 10
    rows = _reduce_on(dates)
    rep = readiness(rows, today=date(2026, 7, 14), horizon_days=21,
                    gate_date=date(2026, 7, 15))
    assert rep.verdict == "READY"
    assert rep.shortfalls == ()
    assert rep.projected_n_at_gate == 30
    assert rep.distinct_reduce_dates == 3


def test_readiness_projection_excludes_flags_resolving_after_gate() -> None:
    # logged too late to resolve by the gate (as_of + 21d > gate_date)
    rows = _reduce_on(["2026-07-10"] * 30)
    rep = readiness(rows, today=date(2026, 7, 11), horizon_days=21,
                    gate_date=date(2026, 7, 15))
    assert rep.projected_n_at_gate == 0
    assert rep.verdict == "THIN"
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_calibration_readiness.py -k readiness -v`
Expected: FAIL `ImportError: cannot import name 'readiness'`.

- [ ] **Step 3: Implement (append)**

```python
# application/calibration_readiness.py  (append)
@dataclass(frozen=True)
class ReadinessReport:
    verdict: str  # READY | THIN
    distinct_reduce_dates: int
    reduce_span_days: int
    resolvable_now: int
    projected_n_at_gate: int
    shortfalls: tuple[str, ...]


def readiness(
    rows: list[dict[str, Any]],
    today: date,
    horizon_days: int,
    gate_date: date,
    *,
    k_dates: int = 3,
    d_days: int = 10,
    n_min: int = 30,
) -> ReadinessReport:
    """Project whether the REDUCE sample will be diverse + large enough by gate_date.

    THIN unless: projected_n_at_gate >= n_min AND distinct dates >= k_dates AND
    span >= d_days. Pre-registered design check — changes no locked threshold.
    """
    reduce_rows = [r for r in rows if r.get("verdict") == REDUCE]
    sp = as_of_spread(reduce_rows)
    projected = sum(
        1
        for r in reduce_rows
        if _date_of(str(r["as_of"])) + timedelta(days=horizon_days) <= gate_date
    )
    resolvable_now = resolvable_split(rows, today, horizon_days)["resolvable"]
    shortfalls: list[str] = []
    if projected < n_min:
        shortfalls.append(f"projected_n {projected} < {n_min}")
    if sp["distinct_dates"] < k_dates:
        shortfalls.append(f"distinct_dates {sp['distinct_dates']} < {k_dates}")
    if sp["span_days"] < d_days:
        shortfalls.append(f"span_days {sp['span_days']} < {d_days}")
    return ReadinessReport(
        verdict="READY" if not shortfalls else "THIN",
        distinct_reduce_dates=int(sp["distinct_dates"]),
        reduce_span_days=int(sp["span_days"]),
        resolvable_now=resolvable_now,
        projected_n_at_gate=projected,
        shortfalls=tuple(shortfalls),
    )
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_calibration_readiness.py -k readiness -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add application/calibration_readiness.py tests/test_calibration_readiness.py
git commit -m "feat(calib): readiness projection (READY/THIN + shortfalls)"
```

---

## Task 4: symmetric diversity guard (`application/calibration_readiness.py`)

**Files:** Modify `application/calibration_readiness.py`; Test `tests/test_calibration_readiness.py`

- [ ] **Step 1: Write the failing tests (append)**

```python
# tests/test_calibration_readiness.py  (append)
from application.calibration_readiness import diversity_label


def _as_ofs(dates: list[str]) -> list[str]:
    return [f"{d}T09:00:00+00:00" for d in dates]


def test_guard_confounded_high_downrate_is_thin_not_proceed() -> None:
    # one date, n>=30, down_rate passes, brier passes -> STILL thin (symmetric)
    as_ofs = _as_ofs(["2026-06-08"] * 40)
    assert diversity_label(as_ofs, down_rate=0.70, brier=0.30) == "INCONCLUSIVE_THIN_DATES"


def test_guard_confounded_low_downrate_is_thin_not_kill() -> None:
    as_ofs = _as_ofs(["2026-06-08"] * 40)
    assert diversity_label(as_ofs, down_rate=0.20, brier=0.60) == "INCONCLUSIVE_THIN_DATES"


def test_guard_diverse_passing_thresholds_is_proceed() -> None:
    as_ofs = _as_ofs(["2026-06-09"] * 14 + ["2026-06-16"] * 14 + ["2026-06-23"] * 14)
    assert diversity_label(as_ofs, down_rate=0.60, brier=0.40) == "PROCEED"


def test_guard_diverse_failing_thresholds_is_kill() -> None:
    as_ofs = _as_ofs(["2026-06-09"] * 14 + ["2026-06-16"] * 14 + ["2026-06-23"] * 14)
    assert diversity_label(as_ofs, down_rate=0.40, brier=0.60) == "KILL"


def test_guard_thin_n_is_thin() -> None:
    as_ofs = _as_ofs(["2026-06-09", "2026-06-16", "2026-06-23"])  # diverse but n=3
    assert diversity_label(as_ofs, down_rate=0.99, brier=0.01) == "INCONCLUSIVE_THIN_DATES"
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_calibration_readiness.py -k guard -v`
Expected: FAIL `ImportError: cannot import name 'diversity_label'`.

- [ ] **Step 3: Implement (append)**

```python
# application/calibration_readiness.py  (append)
def diversity_label(
    resolved_reduce_as_ofs: list[str],
    down_rate: float,
    brier: float,
    *,
    k_dates: int = 3,
    d_days: int = 10,
    n_min: int = 30,
    down_rate_min: float = 0.55,
    brier_max: float = 0.45,
) -> str:
    """Pre-resolution validity guard THEN the LOCKED ADR-048 thresholds.

    Returns INCONCLUSIVE_THIN_DATES when the resolved REDUCE sample is too small or
    not date-diverse — SYMMETRICALLY, regardless of down_rate (blocks a confounded
    PROCEED and a confounded KILL alike). Only on a diverse sample are the locked
    thresholds (down_rate >= 0.55 AND brier <= 0.45) evaluated. Changes no threshold.
    """
    n = len(resolved_reduce_as_ofs)
    sp = spread_of_as_ofs(resolved_reduce_as_ofs)
    if n < n_min or sp["distinct_dates"] < k_dates or sp["span_days"] < d_days:
        return "INCONCLUSIVE_THIN_DATES"
    if down_rate >= down_rate_min and brier <= brier_max:
        return "PROCEED"
    return "KILL"
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_calibration_readiness.py -v`
Expected: PASS (all calibration_readiness tests).

- [ ] **Step 5: Commit**

```bash
git add application/calibration_readiness.py tests/test_calibration_readiness.py
git commit -m "feat(calib): symmetric date-diversity guard (locked ADR-048 thresholds)"
```

---

## Task 5: resolved-as_of plumbing + wire guard into `resolve-discipline-flags`

**Files:** Modify `application/discipline_log.py` (`resolve_flags` return), `application/cli.py` (`resolve-discipline-flags`); Test `tests/test_discipline_log.py`, `tests/test_cli_calibration_readiness.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_discipline_log.py  (append)
def test_resolve_flags_returns_resolved_reduce_as_ofs():
    from datetime import datetime, timezone

    from application.discipline_log import resolve_flags

    logged = [
        {"ticker": "AAA", "verdict": "REDUCE", "price": 100.0,
         "as_of": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat()},
    ]
    series = {"AAA": [
        (datetime(2026, 1, 1, tzinfo=timezone.utc), 100.0),
        (datetime(2026, 2, 5, tzinfo=timezone.utc), 90.0),
    ]}
    out = resolve_flags(logged, lambda t: series.get(t, []), horizon_days=21)
    assert out["reduce_resolved_as_ofs"] == [
        datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat()
    ]
```

```python
# tests/test_cli_calibration_readiness.py
import json
from datetime import datetime, timedelta, timezone

from click.testing import CliRunner

from application import cli as cli_mod


def _log(tmp_path, dates):  # type: ignore[no-untyped-def]
    p = tmp_path / "disc.jsonl"
    with open(p, "w") as fh:
        for d in dates:
            fh.write(json.dumps(
                {"ticker": "AAA", "verdict": "REDUCE", "price": 100.0,
                 "as_of": d}
            ) + "\n")
    return str(p)


def test_resolve_flags_cli_thin_dates_label(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    # one as_of date, the name drops -> would naively PROCEED, but guard says THIN
    log = _log(tmp_path, [datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat()] * 40)

    def fake_prices(ticker, start, end):  # type: ignore[no-untyped-def]
        return [
            (datetime(2026, 1, 1, tzinfo=timezone.utc), 100.0),
            (datetime(2026, 3, 1, tzinfo=timezone.utc), 80.0),
        ]

    monkeypatch.setattr("application.cli.load_price_series", fake_prices, raising=False)
    result = CliRunner().invoke(
        cli_mod.cli, ["resolve-discipline-flags", "--log", log]
    )
    assert result.exit_code == 0, result.output
    assert "INCONCLUSIVE_THIN_DATES" in result.output
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_discipline_log.py::test_resolve_flags_returns_resolved_reduce_as_ofs tests/test_cli_calibration_readiness.py -v`
Expected: FAIL — `KeyError: 'reduce_resolved_as_ofs'` / label not in output.

- [ ] **Step 3a: Add `reduce_resolved_as_ofs` to `resolve_flags`**

In `application/discipline_log.py`, inside `resolve_flags`, add a collector. After `reduce_outcomes: list[int] = []` add:

```python
    reduce_resolved_as_ofs: list[str] = []
```

In the REDUCE branch, where `reduce_outcomes.append(went_down)` runs, also record the as_of:

```python
        if verdict == "REDUCE":
            reduce_probs.append(1.0)
            reduce_outcomes.append(went_down)
            down_on_reduce += went_down
            reduce_resolved_as_ofs.append(str(row["as_of"]))
```

In the returned dict, add the key:

```python
        "reduce_resolved_as_ofs": reduce_resolved_as_ofs,
```

- [ ] **Step 3b: Wire the guard into the CLI**

In `application/cli.py`, in `resolve_discipline_flags`, after the existing `res = resolve_flags(...)` and the two `click.echo` lines, append:

```python
    from application.calibration_readiness import diversity_label

    label = diversity_label(
        res["reduce_resolved_as_ofs"],
        down_rate=res["down_rate_on_reduce"],
        brier=res["brier"],
    )
    click.echo(
        f"GATE LABEL: {label}  "
        "(INCONCLUSIVE_THIN_DATES = sample not date-diverse yet; "
        "thresholds locked per ADR-048/051)"
    )
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_discipline_log.py tests/test_cli_calibration_readiness.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add application/discipline_log.py application/cli.py tests/test_discipline_log.py tests/test_cli_calibration_readiness.py
git commit -m "feat(calib): resolved-as_of plumbing + date-diversity gate label in resolve-discipline-flags"
```

---

## Task 6: `discipline-calibration-status` CLI

**Files:** Modify `application/cli.py`; Test `tests/test_cli_calibration_readiness.py`

- [ ] **Step 1: Write the failing test (append)**

```python
# tests/test_cli_calibration_readiness.py  (append)
def test_calibration_status_reports_thin_single_date(tmp_path):  # type: ignore[no-untyped-def]
    log = _log(tmp_path, [datetime(2026, 6, 8, tzinfo=timezone.utc).isoformat()] * 46)
    result = CliRunner().invoke(
        cli_mod.cli,
        ["discipline-calibration-status", "--log", log,
         "--today", "2026-06-09", "--gate-date", "2026-07-15"],
    )
    assert result.exit_code == 0, result.output
    assert "VERDICT: THIN" in result.output
    assert "distinct" in result.output.lower()
    assert "AAA" not in result.output  # masked: no tickers on stdout
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_cli_calibration_readiness.py::test_calibration_status_reports_thin_single_date -v`
Expected: FAIL (no such command).

- [ ] **Step 3: Implement the command in `application/cli.py`**

Add near the other discipline commands:

```python
@cli.command("discipline-calibration-status")
@click.option("--log", default="data/personal/discipline_log.jsonl", show_default=True)
@click.option("--horizon", default=21, type=int, show_default=True)
@click.option("--gate-date", default="2026-07-15", show_default=True,
              help="Pre-committed gate resolution date (ADR-048 window).")
@click.option("--today", default=None, help="Override today (ISO date) for projection.")
def discipline_calibration_status(
    log: str, horizon: int, gate_date: str, today: str | None
) -> None:
    """Is the discipline forward-gate sample date-diverse enough to resolve honestly?

    Masked (no tickers). Reports verdict counts, REDUCE as_of diversity, resolvable
    vs pending, log freshness (dead-cron detector), and a READY/THIN readiness
    projection to the gate date. Changes no ADR-048 threshold (see ADR-051).
    """
    from datetime import date, datetime, timezone

    from application.calibration_readiness import (
        as_of_spread,
        freshness,
        readiness,
        resolvable_split,
    )
    from application.discipline_log import read_assessments

    rows = read_assessments(log)
    if not rows:
        click.echo(f"No logged assessments at {log}.")
        return
    today_d = (
        date.fromisoformat(today)
        if today
        else datetime.now(timezone.utc).date()
    )
    gate_d = date.fromisoformat(gate_date)

    counts: dict[str, int] = {}
    for r in rows:
        v = str(r.get("verdict", "?"))
        counts[v] = counts.get(v, 0) + 1
    reduce_rows = [r for r in rows if r.get("verdict") == "REDUCE"]
    sp = as_of_spread(reduce_rows)
    split = resolvable_split(rows, today_d, horizon)
    fresh = freshness(rows, today_d)
    rep = readiness(rows, today_d, horizon, gate_d)

    click.echo(f"Discipline Calibration Readiness (today {today_d.isoformat()})")
    click.echo(
        f"  logged: {len(rows)}  ("
        + " / ".join(f"{k} {counts[k]}" for k in sorted(counts))
        + ")"
    )
    click.echo(
        f"  REDUCE as_of dates: {sp['distinct_dates']} distinct, "
        f"span {sp['span_days']}d ({sp['min_date']} -> {sp['max_date']})"
    )
    click.echo(
        f"  REDUCE resolvable now: {split['resolvable']}  "
        f"pending: {split['pending']}  (horizon {horizon}d)"
    )
    click.echo(
        f"  last logged: {sp['max_date'] or 'n/a'}  "
        f"({fresh if fresh is not None else 'n/a'} days ago)"
    )
    click.echo(
        f"  projected n at gate {gate_d.isoformat()}: {rep.projected_n_at_gate}"
    )
    short = ("  -- shortfalls: " + "; ".join(rep.shortfalls)) if rep.shortfalls else ""
    click.echo(f"  VERDICT: {rep.verdict}{short}")
    click.echo("  (gate thresholds stay locked per ADR-048/051; log more dates if THIN)")
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_cli_calibration_readiness.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add application/cli.py tests/test_cli_calibration_readiness.py
git commit -m "feat(calib): discipline-calibration-status CLI (masked readiness view)"
```

---

## Task 7: daily cron + corrected plist + ADR-051 + full gate

**Files:** Create `scripts/discipline_daily.sh`; Modify `docs/scheduling.md`; Create `docs/adr/051-calibration-readiness-date-diversity.md`

- [ ] **Step 1: Create the wrapper script**

```bash
# scripts/discipline_daily.sh
#!/usr/bin/env bash
# Daily discipline-risk logging for the ADR-048/051 forward-calibration gate.
# Appends one as_of snapshot per run to data/personal/discipline_log.jsonl.
# Requires a real holdings CSV at data/personal/holdings.csv (gitignored).
set -euo pipefail
REPO="/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender"
cd "$REPO"
# Adjust the python path to your venv if not on PATH.
PYTHON="${DISCIPLINE_PYTHON:-python}"
"$PYTHON" -m application.cli holdings-risk \
  --holdings data/personal/holdings.csv \
  >> data/reports/discipline_daily.log 2>&1
```

Then: `chmod +x scripts/discipline_daily.sh`.

> Note: confirm the `holdings-risk` flag name for the CSV (`--holdings` vs `--file`) by running `python -m application.cli holdings-risk --help`; correct the script to match before committing.

- [ ] **Step 2: Add the corrected plist section to `docs/scheduling.md`**

Append a new section:

````markdown
## Discipline forward-calibration daily logging (ADR-048/051)

The opportunity `daily-cycle` plist above does NOT log discipline verdicts. For the
ADR-048 REDUCE-flag forward gate you must run `holdings-risk` itself daily so the
forward log accrues date-diverse `as_of` snapshots. Save as
`~/Library/LaunchAgents/com.tirthjoshi.stockrec.discipline-daily.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.tirthjoshi.stockrec.discipline-daily</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender/scripts/discipline_daily.sh</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>DISCIPLINE_PYTHON</key>
    <string>/PATH/TO/venv/bin/python</string>
  </dict>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>18</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardOutPath</key>
  <string>/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender/data/reports/discipline_daily.log</string>
  <key>StandardErrorPath</key>
  <string>/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender/data/reports/discipline_daily.log</string>
</dict>
</plist>
```

Load: `launchctl load -w ~/Library/LaunchAgents/com.tirthjoshi.stockrec.discipline-daily.plist`

**Laptop sleep:** launchd will not fire while asleep. Keep the machine awake at the
scheduled time (`caffeinate -i` during a known-awake window) or run `pmset schedule
wake` before 18:00. Verify the cron is alive with
`python -m application.cli discipline-calibration-status` — the "last logged … days
ago" line is your dead-cron detector.
````

- [ ] **Step 3: Write ADR-051**

```markdown
# ADR-051: Calibration-Readiness — Date-Diversity Precondition for the ADR-048 Gate

**Date:** 2026-06-09
**Status:** Accepted
**Amends (design only, thresholds unchanged):** ADR-048
**Builds on:** ADR-047, ADR-050 (discipline is the terminal bet)

## Context

The ADR-048 discipline REDUCE-flag forward gate is the project's terminal bet. On
2026-06-09 its forward log held 132 rows ALL dated 2026-06-08 (46 REDUCE). Two flaws
threatened it: (1) no automated logging — the documented launchd plist runs
`daily-cycle` (opportunity loop), which never appends discipline verdicts; (2) a
single-`as_of` confound — all REDUCE flags would resolve over one identical market
window, so the pooled down-rate would ride on that one month's direction, not on
whether the flags discriminate. A confounded PROCEED and a confounded KILL are
equally worthless.

## Decision

Strengthen the EXPERIMENTAL DESIGN before any outcome is observable (earliest flag
resolves ~2026-06-30; this is decided 2026-06-09). The ADR-048 thresholds are
UNCHANGED: down_rate >= 0.55 AND brier <= 0.45 AND n >= 30, 21-day horizon.

Add a pre-resolution **date-diversity precondition**, pre-committed here:
- The resolved REDUCE sample must span **>= 3 distinct as_of dates over >= 10
  calendar days** before the locked thresholds are evaluated.
- Below that → **INCONCLUSIVE_THIN_DATES** (an honest design failure: we did not
  collect a clean sample), never PROCEED and never KILL.

Implemented as: daily `holdings-risk` logging (cron), a `discipline-calibration-status`
readiness view, and a symmetric `diversity_label` guard wired into
`resolve-discipline-flags`.

### Anti-p-hacking protections (pre-committed)

1. **Symmetric:** the guard blocks a confounded PROCEED and a confounded KILL alike.
2. **Fixed thresholds:** k=3 dates, d=10 days set now, not tuned to observed down-rates.
3. **Fixed resolution date:** the gate resolves in the ADR-048 mid-late-July window;
   we do NOT extend collection to chase a result. Whatever diverse sample exists then
   is the sample. INCONCLUSIVE_THIN_DATES at that date is a permitted terminal outcome.

## Consequences

- The gate can only return PROCEED/KILL on a non-confounded sample — the result, either
  way, becomes trustworthy.
- If diversity is still insufficient at the resolution date, the honest outcome is
  INCONCLUSIVE_THIN_DATES, and the discipline tool ships as decision-support without a
  validated forward edge (consistent with the ADR-050 terminal-state framing).
- No domain change; no scorer change; no threshold change.
```

- [ ] **Step 4: Full gate**

Run: `make check`
Expected: green — mypy strict, ≥90% coverage, all tests pass. (`calibration_readiness.py` is pure → fully covered by Tasks 1–4.)

- [ ] **Step 5: Commit**

```bash
chmod +x scripts/discipline_daily.sh
git add scripts/discipline_daily.sh docs/scheduling.md docs/adr/051-calibration-readiness-date-diversity.md
git commit -m "docs(calib): daily holdings-risk cron + corrected plist + ADR-051"
```

---

## Self-Review (completed by planner)

**Spec coverage:**
- §2 frame (thresholds locked; pre-outcome amendment) → ADR-051 (Task 7) + locked defaults in `diversity_label` (Task 4).
- §3.A daily cron → Task 7 (script + plist + caffeinate).
- §3.B status CLI → Task 6 (`discipline-calibration-status`, masked, freshness, READY/THIN).
- §3.C resolve guard → Task 5 (`diversity_label` wired into `resolve-discipline-flags`).
- §4 architecture (pure module, no domain change, masked) → Tasks 1–4 (pure) + Tasks 5–6 (CLI masked).
- §5 testing (spread, resolvable, freshness, readiness, guard SYMMETRY, status smoke) → Tasks 1–6 tests.
- §6 ADR-051 → Task 7.
- §7 YAGNI (no dashboard, no scorer change, no backfill) → respected; no such tasks.

**Placeholder scan:** none. One explicit verify-the-flag note in Task 7 Step 1 (the `holdings-risk` CSV flag name) — resolved by `--help` before commit, not a code placeholder.

**Type consistency:** `spread_of_as_ofs`/`as_of_spread` return the same dict shape used by `readiness` and `diversity_label`. `resolve_flags` gains `reduce_resolved_as_ofs: list[str]`, consumed by `diversity_label(resolved_reduce_as_ofs: list[str], ...)` in Task 5 — names/types match. `ReadinessReport` fields used in the Task 6 printout match the Task 3 dataclass. `readiness(... gate_date, *, k_dates, d_days, n_min)` keyword-only params match the Task 3 signature.

**One known subtlety:** `discipline-calibration-status --today` is overridable so tests are deterministic; production omits it and uses UTC today. The gate date defaults to 2026-07-15 (ADR-048 window) and is overridable but pre-committed in ADR-051.
