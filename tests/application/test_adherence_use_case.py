"""tests/application/test_adherence_use_case.py

Fixture story: AC.TO flagged REDUCE on Jun 13 with qty 100 @ 5000 CAD.
Week 2 (Jun 20): user sold to 40 (cut 0.6 >= f -> FOLLOWED).
XYZ flagged REDUCE Jun 13, never sold -> IGNORED; price falls 10% over 21d.
Discretionary trade: NEW position NEW1 on Jun 20 (no flag) -> throttle input.
"""

import json
from datetime import date, datetime, timedelta

from application.adherence import run_adherence_report


def _row(
    ticker: str, verdict: str, as_of: str, qty: float, mv: float
) -> dict[str, object]:
    return {
        "ticker": ticker,
        "verdict": verdict,
        "price": 50.0,
        "trend_health": -2.5,
        "as_of": as_of,
        "quantity": qty,
        "market_value_cad": mv,
    }


W1 = "2026-06-13T09:00:00+00:00"
W2 = "2026-06-20T09:00:00+00:00"


def _log_rows() -> list[dict[str, object]]:
    return [
        _row("AC.TO", "REDUCE", W1, 100.0, 5000.0),
        _row("XYZ.TO", "REDUCE", W1, 50.0, 5000.0),
        _row("AC.TO", "HOLD", W2, 40.0, 2000.0),
        _row("XYZ.TO", "REDUCE", W2, 50.0, 4500.0),  # re-flag: suppressed
        _row("NEW1.TO", "HOLD", W2, 10.0, 1000.0),  # discretionary NEW
    ]


def _falling_provider(ticker: str) -> list[tuple[datetime, float]]:
    # 100 -> 90 linearly over 30 days from Jun 13 (r_21d = -0.07 for XYZ check
    # is fine; exactness asserted via gap sign, not magnitude)
    start = datetime(2026, 6, 13)
    return [(start + timedelta(days=i), 100.0 - i * (10.0 / 30.0)) for i in range(40)]


def _write_log(path, rows) -> None:
    with open(path, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


def test_report_end_to_end(tmp_path) -> None:
    log = tmp_path / "discipline_log.jsonl"
    adh = tmp_path / "adherence_log.jsonl"
    cash = tmp_path / "cash.json"
    _write_log(log, _log_rows())
    cash.write_text(json.dumps({"cash_cad": 500.0, "as_of": "2026-06-18"}))

    summary = run_adherence_report(
        log_path=str(log),
        adherence_log_path=str(adh),
        cash_config_path=str(cash),
        price_provider=_falling_provider,
        today=date(2026, 7, 10),  # 27d after W1 -> obligations resolvable
    )

    # snapshots: 2 dates
    assert summary["n_snapshots"] == 2
    # trades: AC.TO SELL (tool-matched), NEW1.TO NEW (discretionary)
    actions = {(t["ticker"], t["action"]) for t in summary["trades"]}
    assert ("AC.TO", "SELL") in actions
    assert ("NEW1.TO", "NEW") in actions
    # throttle counts ONLY discretionary
    assert summary["throttle"]["n_discretionary"] == 1
    assert summary["throttle"]["verdict"] == "OK"
    # buffer: 500 / (500 + 7500 latest pv) ~ 6.25% >= 5%
    assert summary["buffer"]["verdict"] == "OK"
    # adherence: AC.TO FOLLOWED (cut 0.6), XYZ.TO IGNORED with positive gap
    by_ticker = {r["ticker"]: r for r in summary["adherence"]}
    assert by_ticker["AC.TO"]["label"] == "FOLLOWED"
    assert by_ticker["AC.TO"]["gap_cad"] == 0.0
    assert by_ticker["XYZ.TO"]["label"] == "IGNORED"
    assert by_ticker["XYZ.TO"]["gap_cad"] > 0.0
    # one obligation per ticker despite XYZ re-flag
    assert len(summary["adherence"]) == 2
    # disclosure fields exist
    assert "skipped_unresolved" in summary
    assert "cumulative_gap_bps" in summary and "annualized_gap_bps" in summary


def test_rerun_is_idempotent(tmp_path) -> None:
    log = tmp_path / "discipline_log.jsonl"
    adh = tmp_path / "adherence_log.jsonl"
    cash = tmp_path / "cash.json"
    _write_log(log, _log_rows())
    cash.write_text(json.dumps({"cash_cad": 500.0, "as_of": "2026-06-18"}))

    for _ in range(3):
        run_adherence_report(
            log_path=str(log),
            adherence_log_path=str(adh),
            cash_config_path=str(cash),
            price_provider=_falling_provider,
            today=date(2026, 7, 10),
        )
    lines = adh.read_text().splitlines()
    keys = [(json.loads(ln)["ticker"], json.loads(ln)["flag_date"]) for ln in lines]
    assert len(keys) == len(set(keys))  # no duplicate (ticker, flag_date)


def test_legacy_rows_without_quantity_no_baseline(tmp_path) -> None:
    log = tmp_path / "discipline_log.jsonl"
    legacy = [
        {
            "ticker": "AC.TO",
            "verdict": "REDUCE",
            "price": 20.0,
            "trend_health": -2.0,
            "as_of": W1,
        }
    ]
    _write_log(log, legacy)
    summary = run_adherence_report(
        log_path=str(log),
        adherence_log_path=str(tmp_path / "adh.jsonl"),
        cash_config_path=str(tmp_path / "nope.json"),
        price_provider=_falling_provider,
        today=date(2026, 7, 10),
    )
    assert summary["status"] == "NO_BASELINE"
    assert summary["buffer"]["verdict"] == "STALE_CASH"  # missing cash.json -> loud


def test_missing_cash_config_is_stale_not_ok(tmp_path) -> None:
    log = tmp_path / "discipline_log.jsonl"
    _write_log(log, _log_rows())
    summary = run_adherence_report(
        log_path=str(log),
        adherence_log_path=str(tmp_path / "adh.jsonl"),
        cash_config_path=str(tmp_path / "missing.json"),
        price_provider=_falling_provider,
        today=date(2026, 7, 10),
    )
    assert summary["buffer"]["verdict"] == "STALE_CASH"


def test_same_day_rerun_keeps_latest(tmp_path) -> None:
    log = tmp_path / "discipline_log.jsonl"
    rows = _log_rows() + [
        _row("AC.TO", "HOLD", "2026-06-20T15:00:00+00:00", 41.0, 2050.0)
    ]  # second run same day, later timestamp -> wins
    _write_log(log, rows)
    summary = run_adherence_report(
        log_path=str(log),
        adherence_log_path=str(tmp_path / "adh.jsonl"),
        cash_config_path=str(tmp_path / "missing.json"),
        price_provider=_falling_provider,
        today=date(2026, 7, 10),
    )
    # AC.TO June-20 qty must come from the 15:00 run (41), not 09:00 (40)
    snap = summary["latest_snapshot"]
    assert snap["AC.TO"] == 41.0
