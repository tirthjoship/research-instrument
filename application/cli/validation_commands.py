"""Validation-related CLI commands: adherence-report, resolve-discipline-flags, discipline-calibration-status, audit-dimensions, validate-divergence-ic, validate-momentum-discipline, backtest-discipline-flags."""

from __future__ import annotations

from datetime import datetime, timedelta

import click

from application.discipline_backtest import backtest_discipline_calibration
from application.divergence_ic_backtest import DivergenceICBacktestUseCase
from application.momentum_exit_backtest import MomentumExitBacktestUseCase
from application.price_returns import load_price_series

from ._cli_group import cli
from ._deps import _build_dependencies, _get_backtest_universe, _get_ticker_universe


@cli.command("adherence-report")
@click.option("--log", default="data/personal/discipline_log.jsonl", show_default=True)
@click.option(
    "--cash-config",
    default="data/personal/cash.json",
    show_default=True,
    help='Gitignored JSON: {"cash_cad": 1234.56, "as_of": "YYYY-MM-DD"}. '
    "Update on material change; >28d stale flags STALE_CASH.",
)
@click.option(
    "--adherence-log",
    default="data/personal/adherence_log.jsonl",
    show_default=True,
    help="Append-only adherence records, idempotent by (ticker, flag_date).",
)
@click.option("--today", default=None, help="Override today (ISO date) for tests.")
def adherence_report(
    log: str, cash_config: str, adherence_log: str, today: str | None
) -> None:
    """Weekly Unit C report: detected trades (holdings-diff, lower bound),
    discretionary-trade throttle, CAD cash-buffer floor, and per-flag adherence
    with 21d counterfactual gap (f=0.5). Advisory only (L0). Descriptive,
    underpowered by design — no significance claims (spec Interpretation limits).
    """
    from datetime import date, timezone

    from application.adherence import run_adherence_report

    start_dt = datetime(2018, 1, 1, tzinfo=timezone.utc)
    end_dt = datetime.now(timezone.utc)

    def provider(ticker: str) -> list[tuple[datetime, float]]:
        return load_price_series(ticker, start_dt, end_dt)

    today_d = date.fromisoformat(today) if today else end_dt.date()
    s = run_adherence_report(
        log_path=log,
        adherence_log_path=adherence_log,
        cash_config_path=cash_config,
        price_provider=provider,
        today=today_d,
    )
    click.echo(f"Adherence report (today {today_d.isoformat()})  status={s['status']}")
    click.echo(
        f"  snapshots: {s['n_snapshots']}  trades detected: {len(s['trades'])}"
        "  (net weekly position changes — lower bound)"
    )
    for t in s["trades"]:
        click.echo(
            f"    {t['week_of']}  {t['ticker']:10} {t['action']:16} "
            f"{t['qty_before']:.1f} -> {t['qty_after']:.1f}"
        )
    th = s["throttle"]
    click.echo(
        f"  THROTTLE: {th['verdict']}  discretionary={th['n_discretionary']}"
        + (f"  ({th['note']})" if th.get("note") else "")
    )
    b = s["buffer"]
    pct = f"{b['cash_pct']:.1%}" if b["cash_pct"] is not None else "n/a"
    click.echo(f"  CASH BUFFER: {b['verdict']}  cash_pct={pct}")
    for r in s["adherence"]:
        click.echo(
            f"  {r['flag_date']}  {r['ticker']:10} {r['verdict']:7} "
            f"{r['label']:9} cut={r['actual_cut_fraction']:.0%} "
            f"gap={r['gap_cad']:+.0f} CAD ({r['gap_bps']:+.1f} bps)"
        )
    skipped = s["skipped_unresolved"]
    click.echo(
        f"  skipped_unresolved: {len(skipped)} {skipped} — flags excluded for "
        "missing 21d prices (incl. delistings); gap is conservative."
    )
    if "cumulative_gap_bps" in s:
        click.echo(
            f"  GAP (REDUCE-only headline): {s['cumulative_gap_bps']:+.1f} bps "
            f"over {s['days_observed']:.0f}d; annualized "
            f"{s['annualized_gap_bps']:+.1f} bps/yr "
            "(context: literature disposition effect ~848 bps/yr; point estimate "
            "only, no significance claim)"
        )
        click.echo(
            f"  TRIM gap (informational, sizing advice): {s['trim_gap_bps']:+.1f} bps"
        )


@cli.command("resolve-discipline-flags")
@click.option("--log", default="data/personal/discipline_log.jsonl", show_default=True)
@click.option("--horizon", default=21, type=int, show_default=True)
def resolve_discipline_flags(log: str, horizon: int) -> None:
    """Forward-score past REDUCE/TRIM flags: were they followed by drops? (calibration)."""
    from datetime import timezone

    from application.discipline_log import read_assessments, resolve_flags

    logged = read_assessments(log)
    if not logged:
        click.echo(f"No logged assessments at {log}.")
        return
    start_dt = datetime(2018, 1, 1, tzinfo=timezone.utc)
    end_dt = datetime.now(timezone.utc)

    def provider(ticker: str) -> list[tuple[datetime, float]]:
        return load_price_series(ticker, start_dt, end_dt)

    res = resolve_flags(logged, provider, horizon_days=horizon)
    click.echo(
        f"resolved={res['resolved']}  brier={res['brier']:.3f}  "
        f"down_rate_on_reduce={res['down_rate_on_reduce']:.0%}  "
        "(REDUCE-only — the calibration gate, ADR-048)"
    )
    click.echo(
        f"(informational) trim_resolved={res['trim_resolved']}  "
        f"down_rate_on_trim={res['down_rate_on_trim']:.0%}  "
        "— TRIM is position-sizing, excluded from the gate"
    )
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


@cli.command("discipline-calibration-status")
@click.option("--log", default="data/personal/discipline_log.jsonl", show_default=True)
@click.option("--horizon", default=21, type=int, show_default=True)
@click.option(
    "--gate-date",
    default="2026-07-15",
    show_default=True,
    help="Pre-committed gate resolution date (ADR-048 window).",
)
@click.option("--today", default=None, help="Override today (ISO date) for projection.")
def discipline_calibration_status(
    log: str, horizon: int, gate_date: str, today: str | None
) -> None:
    """Is the discipline forward-gate sample date-diverse enough to resolve honestly?

    Masked (no tickers). Reports verdict counts, REDUCE as_of diversity, resolvable
    vs pending, log freshness (dead-cron detector), and a READY/THIN readiness
    projection to the gate date. Changes no ADR-048 threshold (see ADR-051).
    """
    from datetime import date, timezone

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
    today_d = date.fromisoformat(today) if today else datetime.now(timezone.utc).date()
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
    click.echo(f"  projected n at gate {gate_d.isoformat()}: {rep.projected_n_at_gate}")
    short = ("  -- shortfalls: " + "; ".join(rep.shortfalls)) if rep.shortfalls else ""
    click.echo(f"  VERDICT: {rep.verdict}{short}")
    click.echo(
        "  (gate thresholds stay locked per ADR-048/051; log more dates if THIN)"
    )


@cli.command("audit-dimensions")
@click.option("--market", default="us")
@click.option("--date", "date_", default=None, help="scan_date (default: latest)")
def audit_dimensions(market: str, date_: str | None) -> None:
    """Per-dim variance + neutral share over logged candidates (prune evidence)."""
    from application.discrimination_audit_use_case import DiscriminationAuditUseCase

    deps = _build_dependencies(market)
    rows = deps["store"].get_scan_candidates(scan_date=date_)
    report = DiscriminationAuditUseCase().execute(rows)
    click.echo("Dimension discrimination (prune dead dims):")
    for dim, stats in sorted(report.items(), key=lambda kv: kv[1]["variance"]):
        click.echo(
            f"  {dim:16s} var={stats['variance']:.3f} "
            f"neutral_share={stats['neutral_share']:.2f} n={int(stats['n'])}"
        )


@cli.command("validate-divergence-ic")
@click.option("--market", default="us")
@click.option("--start", default="2016-01-01", show_default=True)
@click.option("--end", default="2025-12-31", show_default=True)
@click.option("--horizon-days", default=21, show_default=True, type=int)
@click.option("--min-names", default=50, show_default=True, type=int)
@click.option("--limit", default=0, type=int, help="Cap universe (0 = all ~605)")
@click.option(
    "--quick",
    is_flag=True,
    help="Monthly cadence sample (faster) instead of weekly",
)
def validate_divergence_ic(
    market: str,
    start: str,
    end: str,
    horizon_days: int,
    min_names: int,
    limit: int,
    quick: bool,
) -> None:
    """Pre-registered cross-sectional IC test of intensity-divergence (spec D §4)."""
    import json as _json
    import os

    deps = _build_dependencies(market)
    store = deps["store"]
    tickers = _get_ticker_universe(deps["config"])
    if limit:
        tickers = tickers[:limit]

    start_dt = datetime.fromisoformat(start)
    end_dt = datetime.fromisoformat(end)
    step = 28 if quick else 7
    dates: list[datetime] = []
    d = start_dt
    while d <= end_dt - timedelta(days=horizon_days):
        dates.append(d)
        d += timedelta(days=step)

    def attention_fn(ticker: str, t: datetime) -> list[tuple[datetime, float]]:
        pts = store.get_attention_series(ticker, t - timedelta(days=40), t)
        return [(p.timestamp, p.value) for p in pts]

    _price_cache: dict[str, list[tuple[datetime, float]]] = {}

    def _prices(ticker: str) -> list[tuple[datetime, float]]:
        if ticker not in _price_cache:
            _price_cache[ticker] = load_price_series(
                ticker,
                start_dt - timedelta(days=60),
                end_dt + timedelta(days=horizon_days + 5),
            )
        return _price_cache[ticker]

    def price_fn(ticker: str, t: datetime) -> list[tuple[datetime, float]]:
        return [
            (ts, px) for ts, px in _prices(ticker) if t - timedelta(days=40) <= ts <= t
        ]

    def forward_return_fn(ticker: str, t: datetime) -> float:
        from application.price_returns import compute_forward_return

        return compute_forward_return(_prices(ticker), t, horizon_days)

    uc = DivergenceICBacktestUseCase(
        attention_fn, price_fn, forward_return_fn, min_names=min_names
    )
    report = uc.execute(dates, tickers, horizon_label=f"{horizon_days}d")

    boot = report.get("bootstrap") or {}
    ci_low = boot.get("ci_low")
    mean_ic: float = report["mean_ic"]
    proceed = mean_ic >= 0.02 and ci_low is not None and ci_low > 0.0
    verdict = "PROCEED" if proceed else "KILL"
    report["verdict"] = verdict

    os.makedirs("data/reports", exist_ok=True)
    out_path = f"data/reports/divergence_ic_{horizon_days}d.json"
    with open(out_path, "w") as f:
        _json.dump(report, f, indent=2, default=str)

    click.echo(
        f"mean_ic={mean_ic:.4f} ic_ir={report['ic_ir']:.3f} "
        f"n_dates={report['n_dates']} CI=[{boot.get('ci_low')},{boot.get('ci_high')}]"
    )
    click.echo(
        f"VERDICT: {verdict}  (gate: |IC|>=0.02 & bootstrap CI excludes 0, positive)"
    )
    click.echo(f"report -> {out_path}")


@cli.command("validate-momentum-discipline")
@click.option("--market", default="us")
@click.option("--start", default="2018-01-01", show_default=True)
@click.option("--end", default="2026-06-01", show_default=True)
@click.option("--limit", default=0, type=int, help="Cap universe (0 = all)")
@click.option(
    "--quick", is_flag=True, help="Smaller universe sample for a fast dry run"
)
def validate_momentum_discipline(
    market: str, start: str, end: str, limit: int, quick: bool
) -> None:
    """Pre-registered momentum + trailing-exit backtest (spec 2026-06-07). PROCEED/KILL."""
    import json as _json
    import math
    import os
    from datetime import datetime as _dt

    from application.precision_metrics import (
        moving_block_bootstrap,
        sharpe_difference_bootstrap,
    )
    from domain.backtest_metrics import daily_returns

    start_dt = _dt.fromisoformat(start)
    end_dt = _dt.fromisoformat(end)
    universe = _get_backtest_universe(market)
    if quick:
        universe = universe[:50]
    if limit:
        universe = universe[:limit]

    _cache: dict[str, list[tuple[_dt, float]]] = {}

    def provider(ticker: str) -> list[tuple[_dt, float]]:
        if ticker not in _cache:
            _cache[ticker] = load_price_series(ticker, start_dt, end_dt)
        return _cache[ticker]

    uc = MomentumExitBacktestUseCase(provider)
    report = uc.execute(universe, start_dt, end_dt)

    s_ret = daily_returns(report["strategy"]["equity"])
    b_ret = daily_returns(report["buy_hold"]["equity"])
    n = min(len(s_ret), len(b_ret))
    diff = [s_ret[i] - b_ret[i] for i in range(n)]

    # Pre-registered gate statistic: Sharpe-difference CI (paired block bootstrap)
    sharpe_boot = sharpe_difference_bootstrap(s_ret, b_ret) if (s_ret and b_ret) else {}
    ci_low_raw = sharpe_boot.get("ci_low")
    ci_low: float = ci_low_raw if isinstance(ci_low_raw, (int, float)) else 0.0

    # Mean-excess bootstrap kept for transparency only — NOT the gate
    mean_excess_boot = moving_block_bootstrap(diff) if diff else {}

    v = uc.verdict(report, sharpe_diff_ci_low=ci_low)
    os.makedirs("data/reports", exist_ok=True)

    def _safe(x: object) -> object:
        if isinstance(x, bool):
            return x
        if isinstance(x, int):
            return x
        if isinstance(x, str):
            return x
        if isinstance(x, float):
            return x if math.isfinite(x) else 0.0
        return x

    out = {
        "report": {
            k: {m: _safe(report[k][m]) for m in report[k] if m != "equity"}
            for k in report
            if isinstance(report[k], dict)
        },
        "universe_size": len(report.get("universe", [])),
        "verdict": {kk: _safe(vv) for kk, vv in v.items()},
        "sharpe_diff_bootstrap": {
            kk: _safe(vv) for kk, vv in sharpe_boot.items() if vv is not None
        },
        "mean_excess_return_bootstrap": {
            kk: _safe(vv) for kk, vv in mean_excess_boot.items() if vv is not None
        },
    }
    with open("data/reports/momentum_discipline.json", "w") as f:
        _json.dump(out, f, indent=2, default=str)

    for name in ("strategy", "buy_hold", "spy"):
        if name in report:
            r = report[name]
            click.echo(
                f"{name:10} sharpe={r['sharpe']:.2f} cagr={r['cagr']:.2%} "
                f"maxDD={r['max_drawdown']:.2%}"
            )
    click.echo(
        f"sharpe_diff point={sharpe_boot.get('point')} "
        f"ci=[{sharpe_boot.get('ci_low')}, {sharpe_boot.get('ci_high')}]"
    )
    click.echo(
        f"VERDICT: {v['decision']}  (drawdown_reduction={v['drawdown_reduction']:.0%}, "
        f"sharpe_diff_ci_low={v['sharpe_diff_ci_low']:.4f})"
    )


@cli.command("backtest-discipline-flags")
@click.option(
    "--holdings",
    default="data/personal/holdings-report-2026-06-07.csv",
    show_default=True,
)
@click.option("--horizon", default=21, type=int, show_default=True)
@click.option("--step", default=21, type=int, show_default=True)
def backtest_discipline_flags(holdings: str, horizon: int, step: int) -> None:
    """Historical point-in-time calibration of the discipline flags across your holdings (day-1 evidence)."""
    from datetime import timezone

    from application.holdings_reader import read_holdings

    rows = read_holdings(holdings)
    if not rows:
        click.echo(f"No holdings at {holdings}.")
        return
    tickers = [h.ticker for h in rows]
    start_dt = datetime(2018, 1, 1, tzinfo=timezone.utc)
    end_dt = datetime.now(timezone.utc)
    _cache: dict[str, list[tuple[datetime, float]]] = {}

    def provider(t: str) -> list[tuple[datetime, float]]:
        if t not in _cache:
            _cache[t] = load_price_series(t, start_dt, end_dt)
        return _cache[t]

    out = backtest_discipline_calibration(
        tickers, provider, start_dt, end_dt, step_days=step, horizon_days=horizon
    )
    click.echo(
        f"Historical calibration over {len(tickers)} holdings, "
        f"{out['total_verdicts']} point-in-time verdicts:"
    )
    for v in ("REDUCE", "TRIM", "HOLD", "ADD_OK", "REVIEW"):
        b = out["by_verdict"].get(v)
        if b:
            click.echo(
                f"  {v:8} n={b['n']:4} down_rate={b['down_rate']:.0%} "
                f"mean_fwd={b['mean_fwd_return']:+.2%}"
            )
    click.echo(
        f"Brier(REDUCE asserts down)={out['brier_reduce']:.3f} "
        f"over n={out['n_reduce']}  (TRIM excluded — position-sizing, ADR-048)"
    )
    click.echo(
        "NOTE: calibrates flags vs the MARKET on history — NOT proof rules beat "
        "buy-hold (ADR-046) nor your behavior (forward-tracked)."
    )
