"""Unit C weekly adherence report: holdings-diff trades, discretionary
throttle, CAD cash buffer, obligation matching + 21d counterfactual gap.
Appends idempotently to a gitignored adherence_log.jsonl. PRIVACY: all inputs
and outputs live under data/personal/. Spec:
docs/superpowers/specs/2026-06-10-unit-c-adherence-design.md (v4)."""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from application.discipline_log import _price_on_or_after, read_assessments
from domain.adherence import (
    CANONICAL_CUT_FRACTION,
    HORIZON_DAYS,
    DetectedTrade,
    TradeAction,
    actual_cut_fraction,
    adherence_label,
    annualize_bps,
    build_obligations,
    cash_buffer_check,
    diff_holdings,
    gap_bps,
    gap_cad,
    throttle_check,
)

PriceProvider = Callable[[str], list[tuple[datetime, float]]]


def _date_of(as_of: str) -> date:
    return datetime.fromisoformat(as_of).date()


def _snapshots(
    rows: list[dict[str, Any]],
) -> dict[date, list[dict[str, Any]]]:
    """Group rows by as_of DATE (calibration_readiness convention). Same-day
    re-runs: keep only rows from the max as_of timestamp on that date."""
    # Key the same-day run dict by the PARSED datetime, not the raw string, so
    # max() compares chronologically even if formats/offsets ever differ
    # (Z vs +00:00, variable microsecond width). Date-only as_of values
    # ("2026-06-11") parse as tz-naive; normalise them to UTC so max() never
    # compares naive against aware (which raises TypeError).
    by_date: dict[date, dict[datetime, list[dict[str, Any]]]] = {}
    for r in rows:
        if r.get("quantity") is None:  # legacy rows: pre-Unit-C, no baseline
            continue
        ts = datetime.fromisoformat(str(r["as_of"]))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        d = ts.date()
        by_date.setdefault(d, {}).setdefault(ts, []).append(r)
    return {d: runs[max(runs)] for d, runs in by_date.items()}


def _read_cash(path: str) -> tuple[float, date] | None:
    if not os.path.exists(path):
        return None
    with open(path) as fh:
        cfg = json.load(fh)
    return float(cfg["cash_cad"]), date.fromisoformat(str(cfg["as_of"]))


def _existing_keys(adherence_log_path: str) -> set[tuple[str, str]]:
    if not os.path.exists(adherence_log_path):
        return set()
    keys: set[tuple[str, str]] = set()
    with open(adherence_log_path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                rec = json.loads(line)
                keys.add((str(rec["ticker"]), str(rec["flag_date"])))
    return keys


def run_adherence_report(
    log_path: str,
    adherence_log_path: str,
    cash_config_path: str,
    price_provider: PriceProvider,
    today: date,
    horizon_days: int = HORIZON_DAYS,
) -> dict[str, Any]:
    rows = read_assessments(log_path)
    snaps = _snapshots(rows)
    dates = sorted(snaps)

    summary: dict[str, Any] = {
        "status": "OK",
        "n_snapshots": len(dates),
        "trades": [],
        "adherence": [],
        "skipped_unresolved": [],
    }

    # --- cash buffer (always computed; loud when inputs missing) ---
    latest_qty: dict[str, float] = {}
    latest_pv: float | None = None
    if dates:
        latest_rows = snaps[dates[-1]]
        latest_qty = {str(r["ticker"]): float(r["quantity"]) for r in latest_rows}
        mvs = [r.get("market_value_cad") for r in latest_rows]
        latest_pv = (
            sum(float(v) for v in mvs if v is not None)
            if any(v is not None for v in mvs)
            else None
        )
    summary["latest_snapshot"] = latest_qty
    cash = _read_cash(cash_config_path)
    if cash is None:
        buffer = cash_buffer_check(0.0, None, today, today)
    else:
        buffer = cash_buffer_check(cash[0], latest_pv, cash[1], today)
    summary["buffer"] = {
        "verdict": buffer.verdict.value,
        "cash_pct": buffer.cash_pct,
    }

    if len(dates) < 2:
        summary["status"] = "NO_BASELINE"
        summary["throttle"] = {"verdict": "OK", "n_discretionary": 0}
        return summary

    # --- trades from consecutive snapshot diffs ---
    trades: list[DetectedTrade] = []
    for prev_d, curr_d in zip(dates, dates[1:]):
        prev_q = {str(r["ticker"]): float(r["quantity"]) for r in snaps[prev_d]}
        curr_q = {str(r["ticker"]): float(r["quantity"]) for r in snaps[curr_d]}
        trades.extend(diff_holdings(prev_q, curr_q, curr_d))
    summary["trades"] = [
        {
            "ticker": t.ticker,
            "action": t.action.value,
            "qty_before": t.qty_before,
            "qty_after": t.qty_after,
            "week_of": t.week_of.isoformat(),
        }
        for t in trades
    ]

    # --- obligations (one per ticker+verdict per horizon) ---
    flag_rows = [
        {
            "ticker": r["ticker"],
            "verdict": r["verdict"],
            "as_of_date": _date_of(str(r["as_of"])),
            "quantity": r["quantity"],
            "market_value_cad": r["market_value_cad"],
        }
        for d in dates
        for r in snaps[d]
        if r.get("verdict") in ("REDUCE", "TRIM")
        and r.get("market_value_cad") is not None
    ]
    obligations = build_obligations(flag_rows, horizon_days)

    # --- throttle on DISCRETIONARY trades of the latest diff window ---
    open_tickers = {
        o.ticker for o in obligations if (dates[-1] - o.flag_date).days <= horizon_days
    }
    latest_trades = [t for t in trades if t.week_of == dates[-1]]
    discretionary = [
        t
        for t in latest_trades
        if not (
            t.action in (TradeAction.SELL, TradeAction.EXIT)
            and t.ticker in open_tickers
        )
        and t.action is not TradeAction.SUSPECTED_SPLIT
    ]
    weeks = max(1.0, (dates[-1] - dates[-2]).days / 7.0)
    throttle = throttle_check(len(discretionary), weeks)
    summary["throttle"] = {
        "verdict": throttle.verdict.value,
        "trades_per_week": throttle.trades_per_week,
        "n_discretionary": len(discretionary),
        "note": "net weekly position changes; intra-week round trips invisible "
        "(lower bound)",
    }

    # --- adherence + gap for obligations whose horizon elapsed ---
    pv_by_date: dict[date, float] = {}
    for d in dates:
        mvs2 = [r.get("market_value_cad") for r in snaps[d]]
        vals = [float(v) for v in mvs2 if v is not None]
        if vals:
            pv_by_date[d] = sum(vals)

    existing = _existing_keys(adherence_log_path)
    new_records: list[dict[str, Any]] = []
    cumulative_reduce_bps = 0.0
    cumulative_trim_bps = 0.0
    for ob in obligations:
        if (today - ob.flag_date).days < horizon_days:
            continue  # still open, resolve later
        window_end = ob.flag_date + timedelta(days=horizon_days)
        # Absence from a later snapshot is modeled as a FULL exit (qty 0 = full
        # cut): snapshots are full-portfolio exports, so "not present" means
        # "not held". This is the most load-bearing silent assumption in the
        # gap math — if snapshots ever become per-ticker, revisit this default.
        later_qs = [
            float(
                next(
                    (r["quantity"] for r in snaps[d] if str(r["ticker"]) == ob.ticker),
                    0.0,
                )
            )
            for d in dates
            if ob.flag_date < d <= window_end
        ]
        cut = actual_cut_fraction(ob.quantity, later_qs)
        label = adherence_label(cut)
        series = [(dt.replace(tzinfo=None), c) for dt, c in price_provider(ob.ticker)]
        flag_dt = datetime(ob.flag_date.year, ob.flag_date.month, ob.flag_date.day)
        entry = _price_on_or_after(series, flag_dt)
        later = _price_on_or_after(series, flag_dt + timedelta(days=horizon_days))
        if entry is None or later is None or entry <= 0:
            summary["skipped_unresolved"].append(ob.ticker)
            continue
        r_21d = later / entry - 1.0
        g = gap_cad(ob.market_value_cad, cut, r_21d)
        pv = pv_by_date.get(ob.flag_date, 0.0)
        g_bps = gap_bps(g, pv)
        if ob.verdict == "REDUCE":
            cumulative_reduce_bps += g_bps
        else:
            cumulative_trim_bps += g_bps
        record = {
            "ticker": ob.ticker,
            "verdict": ob.verdict,
            "flag_date": ob.flag_date.isoformat(),
            "actual_cut_fraction": cut,
            "label": label.value,
            "r_21d": r_21d,
            "gap_cad": g,
            "gap_bps": g_bps,
            "f": CANONICAL_CUT_FRACTION,
        }
        summary["adherence"].append(record)
        if (ob.ticker, ob.flag_date.isoformat()) not in existing:
            new_records.append(record)

    if new_records:
        os.makedirs(os.path.dirname(adherence_log_path) or ".", exist_ok=True)
        with open(adherence_log_path, "a") as fh:
            for rec in new_records:
                fh.write(json.dumps(rec) + "\n")

    days_observed = max(1.0, float((dates[-1] - dates[0]).days))
    summary["cumulative_gap_bps"] = cumulative_reduce_bps  # REDUCE-only headline
    summary["trim_gap_bps"] = cumulative_trim_bps  # informational (sizing advice)
    summary["annualized_gap_bps"] = annualize_bps(cumulative_reduce_bps, days_observed)
    summary["days_observed"] = days_observed
    return summary
