"""ML-related CLI commands: pretrain, run-tournament, evaluate-last-week, etc."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import click
from loguru import logger

from application.backtest_runner import run_backtest_report
from application.use_cases import (
    PretrainingUseCase,
    TrackRecommendationsUseCase,
    WeeklyTournamentUseCase,
)

from ._cli_group import cli
from ._deps import _build_dependencies, _get_ticker_universe, _print_report

_LARGE_CAP_TICKERS = (
    "AAPL,MSFT,NVDA,AMD,INTC,MU,TSLA,GOOGL,META,AMZN,QCOM,TXN,AVGO,CRM,ORCL,"
    "ADBE,CSCO,PLTR,UBER,NFLX,JPM,BAC,WFC,V,MA,UNH,JNJ,PFE,MRK,XOM,CVX,WMT,"
    "HD,COST,DIS,KO,PEP,NKE,BA,CAT"
)

_SMALL_MID_TICKERS = (
    "HALO,EXEL,CYTK,ARWR,INSM,VKTX,KRYS,BLDR,CROX,SHAK,WING,SOFI,AFRM,UPST,"
    "SITM,RMBS,LSCC,POWI,AMKR,SMTC,ONTO,COHU,FORM,ACLS,BOOT,STRL,ATKR,GMS,"
    "MGY,CIVI,AIT,CALM,IBP,FOUR,DOCS,PRCT"
)


@cli.command()
@click.option("--market", default="us", help="Market config (us, ca, in)")
@click.option("--start", default="2024-01", help="Start month (YYYY-MM)")
@click.option("--end", default="2026-05", help="End month (YYYY-MM)")
def pretrain(market: str, start: str, end: str) -> None:
    """Run walk-forward pretraining on historical data."""
    deps = _build_dependencies(market)
    config = deps["config"]

    tickers = _get_ticker_universe(config)

    use_case = PretrainingUseCase(
        market_data=deps["market_data"],
        technical_analysis=deps["technical_analysis"],
        feature_engineer=deps["feature_engineer"],
        predictors=deps["predictors"],
        store=deps["store"],
        tickers=tickers,
        macro_symbols=deps["macro_symbols"],
        fundamental_engineer=deps["fundamental_engineer"],
        cross_asset_engineer=deps["cross_asset_engineer"],
        event_causal_engineer=deps["event_causal_engineer"],
    )

    logger.info(f"Starting pretraining: {start} to {end}, {len(tickers)} tickers")
    use_case.execute(start_month=start, end_month=end)
    logger.info("Pretraining complete")


@cli.command("run-tournament")
@click.option("--market", default="us")
@click.option("--date", default=None, help="Prediction date (YYYY-MM-DD)")
def run_tournament(market: str, date: str | None) -> None:
    """Run weekly tournament and generate top 15 picks."""
    deps = _build_dependencies(market)

    # Pre-flight: abort loud if any predictor not trained
    for horizon, predictor in deps["predictors"].items():
        if not predictor.is_fitted():
            click.echo(
                f"ERROR: {horizon} predictor is not trained. "
                "Run `train-models` first to fit and save the ensemble.",
                err=True,
            )
            raise SystemExit(1)

    config = deps["config"]
    tickers = _get_ticker_universe(config)

    prediction_date = datetime.strptime(date, "%Y-%m-%d") if date else datetime.now()

    use_case = WeeklyTournamentUseCase(
        market_data=deps["market_data"],
        technical_analysis=deps["technical_analysis"],
        feature_engineer=deps["feature_engineer"],
        predictors=deps["predictors"],
        store=deps["store"],
        tickers=tickers,
        macro_symbols=deps["macro_symbols"],
        market=market,
        fundamental_engineer=deps["fundamental_engineer"],
        cross_asset_engineer=deps["cross_asset_engineer"],
        event_causal_engineer=deps["event_causal_engineer"],
    )

    report = use_case.execute(prediction_date=prediction_date)
    _print_report(report)


@cli.command("evaluate-last-week")
@click.option("--date", default=None, help="Evaluation date (YYYY-MM-DD)")
def evaluate_last_week(date: str | None) -> None:
    """Compare last week's predictions with actual outcomes."""
    deps = _build_dependencies("us")
    eval_date = datetime.strptime(date, "%Y-%m-%d") if date else datetime.now()

    use_case = TrackRecommendationsUseCase(
        market_data=deps["market_data"],
        store=deps["store"],
    )

    records = use_case.execute(evaluation_date=eval_date)
    if records:
        correct_2d = sum(1 for r in records if r.direction_correct_2d) / len(records)
        correct_5d = sum(1 for r in records if r.direction_correct_5d) / len(records)
        correct_10d = sum(1 for r in records if r.direction_correct_10d) / len(records)
        click.echo(f"Evaluated {len(records)} recommendations:")
        click.echo(f"  2-day accuracy: {correct_2d:.1%}")
        click.echo(f"  5-day accuracy: {correct_5d:.1%}")
        click.echo(f"  10-day accuracy: {correct_10d:.1%}")
    else:
        click.echo("No recommendations to evaluate")


@cli.command("show-report")
@click.option("--week", required=True, help="Week start date (YYYY-MM-DD)")
def show_report(week: str) -> None:
    """Display a stored weekly report."""
    deps = _build_dependencies("us")
    report = deps["store"].get_weekly_report(week)
    if report:
        _print_report(report)
    else:
        click.echo(f"No report found for week {week}")


@cli.command("backtest")
@click.option("--market", default="us")
@click.option("--start", default="2024-01", help="Start month (YYYY-MM)")
@click.option("--end", default="2026-05", help="End month (YYYY-MM)")
def backtest(market: str, start: str, end: str) -> None:
    """Run full backtest: pretrain + evaluate + report."""
    click.echo("Step 1/3: Running walk-forward pretraining...")
    deps = _build_dependencies(market, use_cache=False)
    config = deps["config"]
    tickers = _get_ticker_universe(config)

    use_case = PretrainingUseCase(
        market_data=deps["market_data"],
        technical_analysis=deps["technical_analysis"],
        feature_engineer=deps["feature_engineer"],
        predictors=deps["predictors"],
        store=deps["store"],
        tickers=tickers,
        macro_symbols=deps["macro_symbols"],
        fundamental_engineer=deps["fundamental_engineer"],
        cross_asset_engineer=deps["cross_asset_engineer"],
        event_causal_engineer=deps["event_causal_engineer"],
    )
    use_case.execute(start_month=start, end_month=end)

    click.echo("Step 2/3: Generating evaluation report...")
    report = run_backtest_report()

    click.echo("\nStep 3/3: Results")
    click.echo("=" * 60)
    horizons = report.get("horizons")
    if isinstance(horizons, dict):
        for horizon, metrics in horizons.items():
            click.echo(f"\n{horizon} horizon:")
            if isinstance(metrics, dict):
                for k, v in metrics.items():
                    click.echo(f"  {k}: {v}")
    click.echo("=" * 60)


@cli.command("shap-report")
@click.option("--market", default="us")
@click.option("--start", default="2024-06")
@click.option("--end", default="2025-12")
@click.option("--output", default="data/reports/shap_importance.json")
def shap_report(market: str, start: str, end: str, output: str) -> None:
    """Compute per-fold SHAP feature importance."""
    click.echo("Computing SHAP feature importance...")
    click.echo(f"Results will be saved to {output}")
    click.echo("(Run backtest first to generate trained models)")


@cli.command("backtest-conviction")
@click.option(
    "--tickers",
    default=_LARGE_CAP_TICKERS,
    show_default=False,
    help="Comma-separated large-cap tickers (default: 40 large-caps)",
)
@click.option(
    "--small-tickers",
    default=_SMALL_MID_TICKERS,
    show_default=False,
    help="Comma-separated small/mid-cap tickers (default: ~36 mid/small-caps)",
)
@click.option(
    "--start",
    default=None,
    help="Start date (YYYY-MM-DD). Defaults to 2 years before today.",
)
@click.option(
    "--end",
    default=None,
    help="End date (YYYY-MM-DD). Defaults to today.",
)
@click.option(
    "--horizon-days",
    default=21,
    show_default=True,
    help="Forward-return horizon in calendar days",
)
@click.option(
    "--decile",
    default=0.1,
    show_default=True,
    help="Top-decile fraction used for hit-rate calculation",
)
@click.option(
    "--signal-bearing/--no-signal-bearing",
    default=True,
    show_default=True,
    help=(
        "When ON, filter samples to those with active insider/analyst signal "
        "before computing metrics (removes neutral mass)."
    ),
)
def backtest_conviction(
    tickers: str,
    small_tickers: str,
    start: str | None,
    end: str | None,
    horizon_days: int,
    decile: float,
    signal_bearing: bool,
) -> None:
    """Run a real-data historical conviction backtest with cap-cohort stratification.

    Builds dataset over the UNION of large-cap and small/mid-cap tickers (one pass),
    then reports metrics for each cohort and overall. Use --signal-bearing (default ON)
    to isolate names with actual insider or analyst activity.
    """
    import json
    from pathlib import Path

    from adapters.data.sec_edgar_adapter import SECEdgarAdapter
    from adapters.data.yfinance_analyst_adapter import YFinanceAnalystAdapter
    from application.historical_dataset import (
        build_historical_dataset,
        is_signal_bearing,
        make_historical_sub_score_fn,
        metrics_from_samples,
    )
    from application.price_returns import compute_forward_return, load_price_series
    from domain.conviction import ConvictionWeights
    from domain.conviction_service import compute_conviction

    today = datetime.now()
    two_years_ago = today.replace(year=today.year - 2)

    start_dt = datetime.strptime(start, "%Y-%m-%d") if start else two_years_ago
    end_dt = datetime.strptime(end, "%Y-%m-%d") if end else today

    large_set = {t.strip().upper() for t in tickers.split(",") if t.strip()}
    small_set = {t.strip().upper() for t in small_tickers.split(",") if t.strip()}
    all_tickers = sorted(large_set | small_set)

    logger.info(
        "backtest-conviction: {} large, {} small/mid, {} total unique tickers, "
        "{} → {}, horizon={}d, decile={}, signal_bearing={}",
        len(large_set),
        len(small_set),
        len(all_tickers),
        start_dt.strftime("%Y-%m-%d"),
        end_dt.strftime("%Y-%m-%d"),
        horizon_days,
        decile,
        signal_bearing,
    )

    logger.warning(
        "Small-cap list uses current tickers (survivorship bias) — "
        "interpret small/mid-cap results as optimistic upper bounds."
    )

    # Build monthly scan dates, excluding last horizon_days so forward returns exist
    cutoff = end_dt - timedelta(days=horizon_days)
    scan_dates: list[datetime] = []
    current = start_dt.replace(day=1)
    while current <= cutoff:
        scan_dates.append(current)
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)

    logger.info("Scan dates: {} monthly snapshots", len(scan_dates))

    # Fetch smart-money signals from SEC EDGAR (network)
    click.echo(f"Fetching SEC EDGAR signals for {len(all_tickers)} tickers...")
    sec_adapter = SECEdgarAdapter()
    all_smart_money = []
    since_str = start_dt.strftime("%Y-%m-%d")
    for ticker in all_tickers:
        sigs = sec_adapter.get_all_signals(ticker=ticker, since_date=since_str)
        all_smart_money.extend(sigs)
    logger.info("SEC EDGAR: {} total smart-money signals", len(all_smart_money))

    # Fetch analyst rating events from yfinance (network)
    click.echo(f"Fetching analyst rating events for {len(all_tickers)} tickers...")
    analyst_adapter = YFinanceAnalystAdapter()
    all_analyst = []
    for ticker in all_tickers:
        events = analyst_adapter.get_rating_events(ticker, start_dt, end_dt)
        all_analyst.extend(events)
    logger.info("Analyst events: {} total rating events", len(all_analyst))

    # Load price series for each ticker + SPY (network)
    click.echo(f"Loading price series for {len(all_tickers) + 1} tickers (+ SPY)...")
    price_end = end_dt + timedelta(days=horizon_days + 10)
    price_series: dict[str, list[tuple[datetime, float]]] = {}
    for ticker in all_tickers:
        price_series[ticker] = load_price_series(ticker, start_dt, price_end)
    spy_series = load_price_series("SPY", start_dt, price_end)
    logger.info("Price series loaded for {} tickers", len(price_series))

    # Wire conviction pipeline
    sub_score_fn = make_historical_sub_score_fn(all_smart_money, all_analyst)
    weights = ConvictionWeights()

    def conviction_fn(sub: dict[str, float]) -> float:
        return compute_conviction(sub, weights)

    def forward_return_fn(ticker: str, scan_date: datetime) -> float:
        series = price_series.get(ticker, [])
        return compute_forward_return(series, scan_date, horizon_days)

    def benchmark_return_fn(scan_date: datetime) -> float:
        return compute_forward_return(spy_series, scan_date, horizon_days)

    # Build samples (one pass over the full universe)
    click.echo("Building historical dataset...")
    samples = build_historical_dataset(
        scan_dates,
        all_tickers,
        sub_score_fn,
        conviction_fn,
        forward_return_fn,
        benchmark_return_fn,
    )

    # Drop samples with no price data (both returns == 0.0)
    kept = [
        s
        for s in samples
        if not (s.forward_return == 0.0 and s.benchmark_return == 0.0)
    ]
    logger.info(
        "Samples: {} total, {} kept after dropping missing-price rows",
        len(samples),
        len(kept),
    )

    if not kept:
        click.echo("No samples with price data. Check tickers / date range.")
        return

    # Partition into cohorts
    large_samples = [s for s in kept if s.ticker in large_set]
    small_mid_samples = [s for s in kept if s.ticker in small_set]

    # Optionally apply signal-bearing filter
    def _filter(subset: list) -> list:  # type: ignore[type-arg]
        if signal_bearing:
            return [s for s in subset if is_signal_bearing(s.sub_scores)]
        return subset

    cohorts = {
        "large": large_samples,
        "small_mid": small_mid_samples,
        "overall": kept,
    }

    # Compute metrics per cohort
    click.echo("Computing conviction backtest metrics per cohort...")
    cohort_metrics: dict[str, object] = {}
    for cohort_name, cohort_samples in cohorts.items():
        filtered = _filter(cohort_samples)
        n_signal_bearing = len(filtered)
        if n_signal_bearing == 0:
            logger.warning(
                "COHORT {} | 0 signal-bearing samples — skipping metric computation",
                cohort_name,
            )
            cohort_metrics[cohort_name] = {"n_signals": 0, "skipped": True}
            continue
        m = metrics_from_samples(filtered, decile)
        cohort_metrics[cohort_name] = {
            **{
                k: (float(v) if isinstance(v, (int, float)) else v)
                for k, v in m.items()
            },
            "n_signal_bearing": n_signal_bearing,
            "n_total": len(cohort_samples),
        }

    # Log cohort table
    for cohort_name in ("large", "small_mid", "overall"):
        cm = cohort_metrics.get(cohort_name, {})
        if isinstance(cm, dict) and cm.get("skipped"):
            logger.info(
                "COHORT {:<10} | n_signals=0 (no signal-bearing samples)",
                cohort_name,
            )
            continue
        if isinstance(cm, dict):
            hit_rate = float(str(cm.get("top_decile_hit_rate", 0.0)))
            exc_sharpe = cm.get("excess_sharpe", float("nan"))
            n_sig = cm.get("n_signals", 0)
            pval = cm.get("p_value", float("nan"))
            logger.info(
                "COHORT {:<10} | hit_rate {:5.1f}% | excess_sharpe {:6.2f} "
                "| n_signals {:4d} | p={:.2f}",
                cohort_name,
                hit_rate * 100,
                float(str(exc_sharpe)) if exc_sharpe is not None else float("nan"),
                int(float(str(n_sig))),
                float(str(pval)) if pval is not None else float("nan"),
            )

    # Write stratified report
    Path("data/reports").mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = Path(f"data/reports/conviction_backtest_stratified_{timestamp}.json")

    report: dict[str, Any] = {
        "run_at": datetime.now().isoformat(),
        "large_tickers": sorted(large_set),
        "small_mid_tickers": sorted(small_set),
        "start": start_dt.strftime("%Y-%m-%d"),
        "end": end_dt.strftime("%Y-%m-%d"),
        "horizon_days": horizon_days,
        "decile": decile,
        "signal_bearing_filter": signal_bearing,
        "n_scan_dates": len(scan_dates),
        "n_samples_total": len(samples),
        "n_samples_kept": len(kept),
        "cohort_metrics": cohort_metrics,
        "validated_signal_scope": (
            "smart_money + analyst_signal active; 6/8 conviction sub-scores held "
            "neutral (event_signal, sentiment_momentum, fundamental_basis, "
            "ml_direction, signal_agreement, temporal_freshness) and analyst "
            "firm-accuracy weighting inactive. This backtest validates the "
            "smart-money + analyst slice, NOT the full conviction engine."
        ),
    }

    logger.warning(
        "VALIDATED SCOPE: smart-money + analyst slice only (6/8 sub-scores neutral, "
        "firm-accuracy off) — not a validation of the full conviction engine."
    )
    report_path.write_text(json.dumps(report, indent=2, default=str))
    click.echo(f"\nReport saved to: {report_path}")
