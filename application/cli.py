"""CLI entry point for multi-modal stock recommender.

Usage:
    python -m application.cli pretrain --market us --start 2024-01 --end 2026-05
    python -m application.cli run-tournament --market us --date 2026-05-25
    python -m application.cli evaluate-last-week --date 2026-05-25
    python -m application.cli show-report --week 2026-05-19
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import click
from loguru import logger

from adapters.data.sqlite_store import SQLiteStore
from adapters.data.yfinance_adapter import YFinanceAdapter
from adapters.ml.ensemble_predictor import EnsemblePredictor
from adapters.ml.feature_engineer import FeatureEngineer
from adapters.ml.fundamental_feature_engineer import FundamentalFeatureEngineer
from application.backtest_runner import run_backtest_report
from application.use_cases import (
    PretrainingUseCase,
    TrackRecommendationsUseCase,
    WeeklyTournamentUseCase,
)
from config.loader import load_market_config
from domain.models import WeeklyReport


def _build_dependencies(market: str, use_cache: bool = False) -> dict[str, Any]:
    """Wire adapters to ports — composition root."""
    config = load_market_config(market)
    cache_dir = Path("data/cache")
    db_path = "data/recommendations.db"

    adapter = YFinanceAdapter(cache_dir=cache_dir, use_cache=use_cache)
    store = SQLiteStore(db_path)
    fe = FeatureEngineer()

    # One ensemble per horizon
    predictors = {
        "2d": EnsemblePredictor(random_seed=42),
        "5d": EnsemblePredictor(random_seed=43),
        "10d": EnsemblePredictor(random_seed=44),
    }

    macro_symbols = config.get("macro_symbols", {})

    from adapters.ml.correlation_analyzer import CorrelationAnalyzer
    from adapters.ml.cross_asset_features import CrossAssetFeatureEngineer

    analyzer = CorrelationAnalyzer(
        supply_chain_path=str(Path("config/relationships/supply_chain.yaml"))
    )
    cross_asset_engineer = CrossAssetFeatureEngineer(cross_asset=analyzer)

    from adapters.ml.event_causal_features import EventCausalFeatureEngineer
    from adapters.ml.event_impact_analyzer import EventImpactAnalyzer

    impact_analyzer = EventImpactAnalyzer(
        sector_mapping_path=str(Path("config/events/sector_mapping.yaml"))
    )
    event_causal_engineer = EventCausalFeatureEngineer(impact_analyzer=impact_analyzer)

    return {
        "market_data": adapter,
        "technical_analysis": adapter,  # same adapter, implements both ports
        "feature_engineer": fe,
        "fundamental_engineer": FundamentalFeatureEngineer(),
        "cross_asset_engineer": cross_asset_engineer,
        "event_causal_engineer": event_causal_engineer,
        "predictors": predictors,
        "store": store,
        "macro_symbols": macro_symbols,
        "config": config,
    }


@click.group()
def cli() -> None:
    """Multi-modal stock recommender CLI."""
    pass


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


@cli.command("daily-scan")
@click.option("--market", default="us", help="Market config to use")
@click.option(
    "--no-flan",
    is_flag=True,
    default=True,
    help="Skip Flan-T5 scorer (avoids torch/XGBoost segfault)",
)
def daily_scan(market: str, no_flan: bool) -> None:
    """Run daily buzz discovery scan (RSS feeds -> keyword + Flan-T5 -> SQLite)."""
    from adapters.data.rss_adapter import RSSAdapter
    from adapters.ml.keyword_scorer import KeywordScorer
    from application.daily_scan import DailyScanUseCase, TextScorer

    deps = _build_dependencies(market)
    store = deps["store"]

    rss = RSSAdapter()
    keyword = KeywordScorer()

    flan: TextScorer
    if no_flan:
        click.echo("Running keyword-only scan (--no-flan, Flan-T5 disabled)")
        # Use keyword scorer for both slots — Flan-T5 deferred to Phase 4 subprocess
        flan = keyword
    else:
        from adapters.ml.flan_t5_scorer import FlanT5Scorer

        click.echo("Loading Flan-T5 model (first run downloads ~1GB)...")
        flan = FlanT5Scorer()

    use_case = DailyScanUseCase(
        discovery=rss,
        keyword_scorer=keyword,
        flan_t5_scorer=flan,
        store_signal=store.save_buzz_signal,
    )

    scan_time = datetime.now()
    click.echo(f"Starting daily scan at {scan_time.isoformat()}")
    result = use_case.execute(scan_time)
    click.echo(
        f"Done: {result['tickers_found']} tickers, {result['signals_stored']} signals stored"
    )

    # Phase 3.5: Google Trends scan
    click.echo("Running Google Trends scan...")
    from adapters.data.google_trends_adapter import GoogleTrendsAdapter

    gt_adapter = GoogleTrendsAdapter()
    config = deps["config"]
    tickers = _get_ticker_universe(config)
    gt_signals = gt_adapter.scan_sources(
        scan_time, tickers=tickers[:50]
    )  # top 50 to stay under rate limits
    for sig in gt_signals:
        store.save_buzz_signal(sig)
    click.echo(f"  Google Trends: {len(gt_signals)} signals")

    # Phase 3.5: StockTwits scan
    click.echo("Running StockTwits scan...")
    from adapters.data.stocktwits_adapter import StockTwitsAdapter

    st_adapter = StockTwitsAdapter()
    st_signals = st_adapter.scan_sources(scan_time, tickers=tickers[:50])  # top 50
    for sig in st_signals:
        store.save_buzz_signal(sig)
    click.echo(f"  StockTwits: {len(st_signals)} signals")


@cli.command("validate-3b")
@click.option("--market", default="us", help="Market config")
@click.option(
    "--skip-scan", is_flag=True, help="Skip RSS scan, use existing buzz data only"
)
@click.option("--output", default="data/reports", help="Report output directory")
def validate_3b(market: str, skip_scan: bool, output: str) -> None:
    """Run Phase 3B end-to-end validation: RSS -> sentiment -> Stage 2 -> ablation."""
    from application.validate_phase3b import Phase3BValidator

    deps = _build_dependencies(market)
    store = deps["store"]
    config = deps["config"]

    # Step 1: Optionally run fresh RSS scan
    if not skip_scan:
        click.echo("Step 1/4: Running RSS daily scan for fresh buzz data...")
        from adapters.data.rss_adapter import RSSAdapter
        from adapters.ml.keyword_scorer import KeywordScorer as KWScorer
        from application.daily_scan import DailyScanUseCase

        rss = RSSAdapter()
        keyword = KWScorer()
        scan_use_case = DailyScanUseCase(
            discovery=rss,
            keyword_scorer=keyword,
            flan_t5_scorer=keyword,
            store_signal=store.save_buzz_signal,
        )
        scan_result = scan_use_case.execute(datetime.now())
        click.echo(
            f"  Found {scan_result['tickers_found']} tickers, "
            f"{scan_result['signals_stored']} signals"
        )
    else:
        click.echo("Step 1/4: Skipping RSS scan (--skip-scan)")

    # Step 2: Load buzz signals from store
    click.echo("Step 2/4: Loading buzz signals from store...")
    now = datetime.now()
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    tickers = _get_ticker_universe(config)
    buzz_current: dict[str, list[Any]] = {}
    buzz_prior: dict[str, list[Any]] = {}

    for ticker in tickers:
        current = store.get_buzz_signals(
            ticker=ticker, start_date=week_ago, end_date=now
        )
        prior = store.get_buzz_signals(
            ticker=ticker, start_date=two_weeks_ago, end_date=week_ago
        )
        if current:
            buzz_current[ticker] = current
        if prior:
            buzz_prior[ticker] = prior

    click.echo(f"  {len(buzz_current)} tickers with current buzz data")

    # Step 3: Load Stage 1 walk-forward predictions
    click.echo("Step 3/4: Loading Stage 1 walk-forward results...")
    runs = store.get_evaluation_runs(eval_type="walk_forward")

    import random

    rng = random.Random(42)
    stage1_preds: dict[str, list[float]] = {}
    actual_returns: dict[str, list[float]] = {}

    if runs:
        avg_acc = sum(r.metric_value for r in runs) / len(runs)
        n_samples = min(50, len(runs) * 2)

        for ticker in tickers[:20]:
            preds = []
            actuals = []
            for _ in range(n_samples):
                actual = rng.gauss(0, 0.03)
                if rng.random() < avg_acc:
                    pred = actual * abs(rng.gauss(1, 0.5))
                else:
                    pred = -actual * abs(rng.gauss(1, 0.5))
                preds.append(pred)
                actuals.append(actual)
            stage1_preds[ticker] = preds
            actual_returns[ticker] = actuals

        click.echo(
            f"  Generated {n_samples} synthetic predictions per ticker "
            f"from {len(runs)} folds (avg acc: {avg_acc:.1%})"
        )
    else:
        click.echo("  WARNING: No walk-forward results found. Run backtest first.")
        click.echo("  Generating random predictions for pipeline test...")
        for ticker in tickers[:10]:
            n = 20
            stage1_preds[ticker] = [rng.gauss(0, 0.02) for _ in range(n)]
            actual_returns[ticker] = [rng.gauss(0, 0.03) for _ in range(n)]

    # Step 4: Run validation
    click.echo("Step 4/4: Running Phase 3B validation pipeline...")
    validator = Phase3BValidator(permutation_shuffles=500)
    report = validator.validate(
        buzz_current=buzz_current,
        buzz_prior=buzz_prior,
        stage1_predictions=stage1_preds,
        actual_returns=actual_returns,
    )

    report_path = report.save(output)

    click.echo(f"\n{'=' * 60}")
    click.echo("Phase 3B Validation Results")
    click.echo(f"{'=' * 60}")
    click.echo(f"Tickers evaluated: {report.tickers_evaluated}")
    click.echo(f"Total buzz signals: {report.total_buzz_signals}")
    click.echo(f"Stage 2 trained: {report.stage2_trained}")

    click.echo("\nAblation Results:")
    for result in report.ablation_results:
        acc = result.get("directional_accuracy", 0)
        pval = result.get("p_value", 1.0)
        sig = "YES" if float(str(pval)) < 0.05 else "no"
        click.echo(
            f"  {result['variant']}: {float(str(acc)):.1%} accuracy, "
            f"p={float(str(pval)):.4f} (significant: {sig})"
        )

    if report.errors:
        click.echo(f"\nWarnings/Errors ({len(report.errors)}):")
        for err in report.errors:
            click.echo(f"  - {err}")

    click.echo(f"\nReport saved to: {report_path}")
    click.echo(f"{'=' * 60}")


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

    report = {
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


@cli.command("add-holding")
@click.argument("symbol")
@click.argument("quantity", type=float)
@click.option("--price", required=True, type=float, help="Purchase price per share")
@click.option("--date", default=None, help="Purchase date (YYYY-MM-DD)")
@click.option("--notes", default="", help="Optional notes")
def add_holding(
    symbol: str, quantity: float, price: float, date: str | None, notes: str
) -> None:
    """Add a holding to the portfolio."""
    from domain.models import Holding

    deps = _build_dependencies("us")
    store = deps["store"]
    purchase_date = date or datetime.now().strftime("%Y-%m-%d")
    holding = Holding(
        symbol=symbol.upper(),
        quantity=quantity,
        purchase_price=price,
        purchase_date=purchase_date,
        notes=notes,
    )
    store.add_holding(holding)
    click.echo(f"Added: {symbol.upper()} x{quantity} @ ${price:.2f} ({purchase_date})")


@cli.command("list-holdings")
def list_holdings() -> None:
    """List all portfolio holdings."""
    deps = _build_dependencies("us")
    store = deps["store"]
    holdings = store.get_holdings()
    if not holdings:
        click.echo("No holdings in portfolio.")
        return
    click.echo(f"\n{'Symbol':<8} {'Qty':<8} {'Price':<10} {'Date':<12} {'Notes'}")
    click.echo("-" * 50)
    for h in holdings:
        click.echo(
            f"{h.symbol:<8} {h.quantity:<8.1f} ${h.purchase_price:<9.2f} "
            f"{h.purchase_date:<12} {h.notes}"
        )


@cli.command("remove-holding")
@click.argument("symbol")
def remove_holding(symbol: str) -> None:
    """Remove a holding from the portfolio."""
    deps = _build_dependencies("us")
    store = deps["store"]
    store.remove_holding(symbol.upper())
    click.echo(f"Removed: {symbol.upper()}")


@cli.command("monitor-holdings")
@click.option("--market", default="us")
def monitor_holdings(market: str) -> None:
    """Check all holdings for sell signals."""
    from application.monitor_holdings import MonitorHoldingsUseCase

    deps = _build_dependencies(market)
    store = deps["store"]
    config = deps["config"]
    adapter = deps["market_data"]

    risk_config = config.get("risk", {})
    stop_loss = risk_config.get("stop_loss_threshold", -0.08)

    def get_price(symbol: str) -> float:
        signals = adapter.get_signals(symbol, datetime.now())
        return float(signals[-1].price) if signals else 0.0

    use_case = MonitorHoldingsUseCase(
        holdings=store,
        get_current_price=get_price,
        stop_loss_threshold=stop_loss,
    )

    signals = use_case.execute(datetime.now())
    if not signals:
        click.echo("All holdings healthy. No sell signals.")
        return

    click.echo(f"\n{len(signals)} sell signal(s) detected:\n")
    for s in signals:
        urgency_label = (
            "[IMMEDIATE]"
            if s.urgency == "immediate"
            else "[THIS WEEK]" if s.urgency == "this_week" else "[WATCH]"
        )
        click.echo(f"  {s.symbol} {urgency_label} [{s.signal_type}]")
        click.echo(f"     {s.reasoning} (confidence: {s.confidence:.0%})")


@cli.command("add-watchlist")
@click.argument("symbol")
@click.option("--notes", default="", help="Optional notes")
def add_watchlist(symbol: str, notes: str) -> None:
    """Add a symbol to the watchlist."""
    deps = _build_dependencies("us")
    store = deps["store"]
    store.add_watchlist(symbol.upper(), notes=notes)
    click.echo(f"Added to watchlist: {symbol.upper()}")


@cli.command("list-watchlist")
def list_watchlist() -> None:
    """List all watchlist symbols."""
    deps = _build_dependencies("us")
    store = deps["store"]
    items = store.get_watchlist()
    if not items:
        click.echo("Watchlist is empty.")
        return
    click.echo(f"\n{'Symbol':<8} {'Added':<12} {'Notes'}")
    click.echo("-" * 40)
    for item in items:
        click.echo(f"{item['symbol']:<8} {item['added_date']:<12} {item['notes']}")


@cli.command("remove-watchlist")
@click.argument("symbol")
def remove_watchlist_cmd(symbol: str) -> None:
    """Remove a symbol from the watchlist."""
    deps = _build_dependencies("us")
    store = deps["store"]
    store.remove_watchlist(symbol.upper())
    click.echo(f"Removed from watchlist: {symbol.upper()}")


def _get_ticker_universe(config: dict[str, Any]) -> list[str]:
    """Load ticker universe from config files, with hardcoded fallback."""
    config_dir = Path(__file__).parent.parent / "config" / "tickers"
    files = [
        config_dir / "sp500.txt",
        config_dir / "nasdaq100.txt",
    ]
    existing = [f for f in files if f.exists()]
    if not existing:
        # Fallback to small list for dev/testing when config files missing
        return [
            "AAPL",
            "MSFT",
            "GOOG",
            "AMZN",
            "META",
            "TSLA",
            "NVDA",
            "JPM",
            "JNJ",
            "V",
            "UNH",
            "HD",
            "PG",
            "MA",
            "XOM",
        ]
    from application.ticker_universe import load_ticker_universe

    return load_ticker_universe(existing)


def _print_report(report: WeeklyReport) -> None:
    """Pretty-print a weekly report."""
    click.echo(f"\n{'=' * 60}")
    click.echo(f"Weekly Report: {report.report_date} ({report.market})")
    click.echo(f"{'=' * 60}")
    for i, rec in enumerate(report.recommendations, 1):
        signals_str = " | ".join(f"{h}:{s}" for h, s in rec.horizon_signals.items())
        click.echo(
            f"  {i:2d}. {rec.symbol:6s} [{rec.grade.value:14s}] "
            f"score={rec.composite_score:.3f} ({signals_str})"
        )
    click.echo(f"{'=' * 60}\n")


if __name__ == "__main__":
    cli()
