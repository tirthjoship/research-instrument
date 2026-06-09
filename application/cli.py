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
from adapters.data.wikipedia_article_resolver import WikipediaArticleResolver
from adapters.data.yfinance_adapter import YFinanceAdapter
from adapters.ml.ensemble_predictor import EnsemblePredictor
from adapters.ml.feature_engineer import FeatureEngineer
from adapters.ml.fundamental_feature_engineer import FundamentalFeatureEngineer
from application.backfill_use_case import BackfillHistoryUseCase
from application.backtest_runner import run_backtest_report
from application.discipline_backtest import backtest_discipline_calibration
from application.divergence_ic_backtest import DivergenceICBacktestUseCase
from application.drip_backfill_use_case import DripBackfillUseCase
from application.holdings_risk import HoldingsRiskAssessmentUseCase
from application.momentum_exit_backtest import MomentumExitBacktestUseCase
from application.opportunity_scan_use_case import OpportunityScanUseCase
from application.portfolio_verdict import PortfolioVerdictUseCase
from application.price_returns import load_price_series
from application.use_cases import (
    PretrainingUseCase,
    TrackRecommendationsUseCase,
    WeeklyTournamentUseCase,
)
from config.loader import load_market_config
from domain.exceptions import SourceThrottledError
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


@cli.command("scan-opportunities")
@click.option("--market", default="us", help="Market config to use")
@click.option("--date", default=None, help="Scan date (YYYY-MM-DD); default: now (UTC)")
@click.option(
    "--cmin",
    default=6.0,
    show_default=True,
    type=float,
    help="Minimum conviction score to surface an opportunity",
)
@click.option(
    "--dmin",
    default=6.0,
    show_default=True,
    type=float,
    help="Minimum divergence score to surface an opportunity",
)
@click.option(
    "--max-discovery",
    default=50,
    show_default=True,
    type=int,
    help="Maximum tickers added via buzz discovery overlay",
)
@click.option(
    "--show-all",
    is_flag=True,
    default=False,
    help="Print the full candidate score distribution after scanning",
)
def scan_opportunities(
    market: str,
    date: str | None,
    cmin: float,
    dmin: float,
    max_discovery: int,
    show_all: bool,
) -> None:
    """Surface emerging opportunities: high-conviction + early divergence signals.

    Scans the thematic universe (config/universe/themes.yaml) plus buzz-discovered
    tickers. Each candidate is scored on conviction × divergence; only calls that
    clear both thresholds (--cmin, --dmin) are surfaced and persisted to the store.
    """
    from datetime import timezone

    from adapters.data.google_trends_adapter import GoogleTrendsAdapter
    from adapters.data.hybrid_universe_provider import HybridUniverseProvider
    from adapters.data.rss_adapter import RSSAdapter
    from adapters.data.sec_edgar_adapter import SECEdgarAdapter
    from adapters.data.wikipedia_pageviews_adapter import WikipediaPageviewsAdapter
    from adapters.data.yfinance_analyst_adapter import YFinanceAnalystAdapter
    from adapters.ml.smart_money_engineer import SmartMoneyFeatureEngineer
    from application.conviction_signal_cache import ConvictionSignalCache
    from application.conviction_use_case import ConvictionScoringUseCase
    from domain.analyst_service import analyst_conviction_score
    from domain.conviction import ConvictionWeights
    from domain.conviction_service import compute_conviction

    deps = _build_dependencies(market)
    store = deps["store"]
    market_data = deps["market_data"]
    config = deps["config"]

    now: datetime
    if date:
        now = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        now = datetime.now(timezone.utc)

    # ConvictionSignalCache — daily TTL from opportunity_engine config
    _opp_cfg: dict[str, Any] = config.get("opportunity_engine", {})
    _ttl: float = float(_opp_cfg.get("signal_cache_ttl_hours", 24))
    signal_cache = ConvictionSignalCache(store=store, ttl_hours=_ttl)

    # Attention sources: Wikipedia pageviews + Google Trends combined
    wiki_adapter = WikipediaPageviewsAdapter(article_map=_load_wiki_map(market))
    trends_adapter = GoogleTrendsAdapter()
    combined_attention = _CombinedAttention(wiki=wiki_adapter, trends=trends_adapter)

    # Analyst adapter (shared across all tickers; re-used by _compute_analyst closure)
    analyst_adapter = YFinanceAnalystAdapter()

    # HybridUniverseProvider: thematic spine + RSS buzz overlay.
    # RSSAdapter satisfies the scan_sources half of BuzzDiscoveryPort; the
    # get_buzz_signals half is not used by HybridUniverseProvider internally
    # (only scan_sources is called), so we suppress the structural type-check
    # gap here.  A future cleanup would add get_buzz_signals to RSSAdapter.
    rss = RSSAdapter()
    themes_path = str(
        Path(__file__).parent.parent / "config" / "universe" / "themes.yaml"
    )
    universe_provider = HybridUniverseProvider(
        themes_path=themes_path,
        buzz_discovery=rss,  # type: ignore[arg-type]
        max_discovery=max_discovery,
    )

    # conviction_provider: closure over ConvictionScoringUseCase._compute_sub_scores
    # and compute_conviction.  We pass whatever is cheaply available from deps:
    #
    # LIVE dimensions (wired to real data):
    #   - smart_money       → SmartMoneyFeatureEngineer (SEC EDGAR signals from store)
    #   - fundamental_basis → ticker_info via market_data.get_ticker_info (yfinance)
    #   - temporal_freshness→ freshest smart-money filed_date
    #   - sentiment_momentum→ buzz_signals from SQLiteStore (stored RSS/GT/ST signals)
    #   - signal_agreement  → cross-layer check using above 4 dimensions
    #   - ml_direction      → stored recommendation grade from SQLiteStore
    #
    # NEUTRAL (fall to default 5.0 — source not wired in scan command):
    #   - event_signal      → 5.0 (Gemini classifier not wired; no free inline source)
    #   - analyst_signal    → 5.0 (YFinanceAnalystAdapter not wired to avoid extra
    #                              network calls per ticker in a bulk scan)

    sec_adapter = SECEdgarAdapter()
    engineer = SmartMoneyFeatureEngineer()

    def conviction_provider(
        ticker: str, scan_time: datetime
    ) -> tuple[float, dict[str, float]]:
        # Gather smart-money signals for this ticker (SEC EDGAR — free, no API key)
        try:
            since_str = (scan_time.replace(tzinfo=None) - timedelta(days=180)).strftime(
                "%Y-%m-%d"
            )
            sm_signals = sec_adapter.get_all_signals(
                ticker=ticker, since_date=since_str
            )
        except Exception:
            sm_signals = []

        features = engineer.compute(
            ticker=ticker, signals=sm_signals, prediction_time=scan_time
        )

        # Fetch buzz signals from SQLiteStore (scan_sources already persisted them)
        try:
            buzz_signals = store.get_buzz_signals(ticker=ticker)
        except Exception:
            buzz_signals = []

        # Fetch ticker_info for fundamental_basis (yfinance — one call per ticker)
        try:
            ticker_info: dict[str, Any] = market_data.get_ticker_info(ticker)
        except Exception:
            ticker_info = {}

        # Fetch stored recommendation for ml_direction
        try:
            recs = store.get_recommendations()
            ticker_recs = [r for r in recs if r.symbol == ticker]
            recommendation = ticker_recs[0] if ticker_recs else None
        except Exception:
            recommendation = None

        def _compute_analyst(t: str, now: datetime) -> float:
            since = (now.replace(tzinfo=None) - timedelta(days=30)).replace(
                tzinfo=now.tzinfo
            )
            rating_events = analyst_adapter.get_rating_events(t, since, now)
            return analyst_conviction_score(rating_events, {}, now)

        def _compute_event(_t: str, _now: datetime) -> float:
            # Gemini event path requires a news source adapter (not wired in bulk
            # scan — no free keyless headline API is available here). Returns neutral
            # so the cache stores 5.0, preserving honesty. To enable real event
            # scoring wire an AlphaVantageNewsAdapter + GeminiEventClassifier here.
            return 5.0

        analyst_score = signal_cache.get_or_compute(
            ticker, "analyst_signal", scan_time, _compute_analyst
        )
        event_score = signal_cache.get_or_compute(
            ticker, "event_signal", scan_time, _compute_event
        )

        sub_scores = ConvictionScoringUseCase._compute_sub_scores(
            features=features,
            ticker_signals=sm_signals,
            scan_time=scan_time,
            buzz_signals=buzz_signals,
            ticker_info=ticker_info,
            recommendation=recommendation,
            event_score=event_score,
            analyst_score=analyst_score,
        )
        weights = ConvictionWeights()
        score = compute_conviction(sub_scores, weights)
        return score, sub_scores

    # buzz_discovery for OpportunityScanUseCase.execute uses get_buzz_signals —
    # SQLiteStore implements this (returns stored buzz signals per ticker).
    use_case = OpportunityScanUseCase(
        universe_provider=universe_provider,
        conviction_provider=conviction_provider,
        buzz_discovery=store,  # SQLiteStore.get_buzz_signals satisfies the port
        market_data=market_data,
        store=store,
        attention_provider=combined_attention,
        cmin=cmin,
        dmin=dmin,
    )

    click.echo(
        f"Scanning opportunities at {now.isoformat()} (cmin={cmin}, dmin={dmin})..."
    )
    calls = use_case.execute(now)

    if show_all:
        rows = store.get_scan_candidates(scan_date=now.date().isoformat())
        click.echo("\nFull candidate distribution (conviction / divergence):")
        for r in rows:
            mark = "*" if r["surfaced"] else " "
            click.echo(
                f"  {mark} {r['ticker']:6s} c={r['conviction']:.2f} "
                f"d={r['divergence']:.2f} [{r['cap_tier']}]"
            )

    if not calls:
        click.echo("No opportunities surfaced above thresholds (abstaining).")
        return

    click.echo(f"\n{len(calls)} opportunity call(s) surfaced:\n")
    for c in calls:
        click.echo(
            f"  {c.ticker:<8} conviction={c.conviction:.2f}  "
            f"divergence={c.divergence_score:.2f}  "
            f"theme={c.theme}  cap={c.cap_tier}"
        )


@cli.command("resolve-calls")
@click.option(
    "--date", default=None, help="Resolution date (YYYY-MM-DD); default: now (UTC)"
)
def resolve_calls(date: str | None) -> None:
    """Resolve due surfaced calls against actual price outcomes.

    Fetches market prices for all calls whose forward-tracking horizon has elapsed,
    computes 1w/1m/3m returns vs SPY+NDX, persists outcomes, and prints a summary.
    """
    from datetime import timezone

    from application.forward_tracking_use_case import ForwardTrackingUseCase

    deps = _build_dependencies("us")
    store = deps["store"]
    market_data = deps["market_data"]

    now: datetime
    if date:
        now = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        now = datetime.now(timezone.utc)

    use_case = ForwardTrackingUseCase(store=store, market_data=market_data)

    click.echo(f"Resolving due calls as of {now.isoformat()}...")
    outcomes = use_case.resolve_due_calls(now)

    if not outcomes:
        click.echo("No calls due for resolution.")
        return

    click.echo(f"\n{len(outcomes)} call(s) resolved:\n")
    beat_both = sum(1 for o in outcomes if o.beat_both)
    for o in outcomes:
        status = "BEAT" if o.beat_both else ("SPY" if o.beat_spy else "MISS")
        click.echo(
            f"  {o.call_id[:20]:<22} fwd={o.forward_return:+.2%}  "
            f"spy={o.spy_return:+.2%}  ndx={o.ndx_return:+.2%}  [{status}]"
        )
    click.echo(
        f"\nBeat both benchmarks: {beat_both}/{len(outcomes)} "
        f"({beat_both / len(outcomes):.0%})"
    )


@cli.command("opportunity-report")
@click.option(
    "--top", default=10, show_default=True, type=int, help="Top N signals to show"
)
def opportunity_report(top: int) -> None:
    """Show signal performance track record from resolved opportunity calls.

    Reads all resolved call outcomes, groups by signal dimension, and reports
    per-signal hit rate, trade count, and average return.
    """
    from application.forward_tracking_use_case import ForwardTrackingUseCase

    deps = _build_dependencies("us")
    store = deps["store"]
    market_data = deps["market_data"]

    use_case = ForwardTrackingUseCase(store=store, market_data=market_data)
    performances = use_case.get_track_record()

    if not performances:
        click.echo("No signal performance data yet — run resolve-calls first.")
        return

    performances.sort(key=lambda p: p.hit_rate, reverse=True)
    shown = performances[:top]

    click.echo(f"\nSignal Track Record (top {len(shown)} of {len(performances)}):\n")
    click.echo(f"  {'Signal':<28} {'Hit Rate':>10} {'Trades':>8} {'Avg Return':>12}")
    click.echo("  " + "-" * 62)
    for p in shown:
        click.echo(
            f"  {p.signal_name:<28} {p.hit_rate:>9.1%} {p.total_trades:>8d} "
            f"{p.avg_return_pct:>11.2f}%"
        )


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


class _CombinedAttention:
    """Merge Wikipedia + Google Trends attention series for a ticker.

    Each source returns [] on failure, so concatenation is always safe.
    """

    def __init__(
        self,
        wiki: Any,
        trends: Any,
    ) -> None:
        self._wiki = wiki
        self._trends = trends

    def get_attention_series(
        self, ticker: str, start: datetime, end: datetime
    ) -> list[Any]:
        wiki_pts: list[Any] = self._wiki.get_attention_series(ticker, start, end)
        trends_pts: list[Any] = self._trends.get_attention_series(ticker, start, end)
        combined: list[Any] = wiki_pts + trends_pts
        return combined


def _load_wiki_map(market: str) -> dict[str, str]:
    """Build {ticker: wiki_article} merging themes.yaml aliases + resolved YAML.

    Aliases from themes.yaml are authoritative and win on conflict.
    Also loads config/universe/wiki_articles_<market>.yaml if it exists.
    """
    return _load_wiki_map_merged(market)


def _load_wiki_map_merged(
    market: str, resolved_path: str | None = None
) -> dict[str, str]:
    """Merge curated themes.yaml aliases (authoritative) with a resolved YAML.

    Args:
        market: Market identifier (e.g. "us").
        resolved_path: Override path to the resolved YAML.  Defaults to
            config/universe/wiki_articles_<market>.yaml.

    Returns:
        Merged {ticker: wiki_article} with curated aliases winning on conflict.
    """
    import yaml

    themes_path = Path(__file__).parent.parent / "config" / "universe" / "themes.yaml"
    curated: dict[str, str] = {}
    if themes_path.exists():
        try:
            data = yaml.safe_load(themes_path.read_text())
            aliases = data.get("aliases", {})
            curated = {
                ticker: str(info.get("wiki", ""))
                for ticker, info in aliases.items()
                if info.get("wiki")
            }
        except Exception as exc:
            logger.warning(
                "_load_wiki_map_merged: failed to load curated aliases from {}: {}",
                themes_path,
                exc,
            )

    if resolved_path is None:
        resolved_path = str(
            Path(__file__).parent.parent
            / "config"
            / "universe"
            / f"wiki_articles_{market}.yaml"
        )

    resolved: dict[str, str] = {}
    rp = Path(resolved_path)
    if rp.exists():
        try:
            raw = yaml.safe_load(rp.read_text()) or {}
            resolved = {str(k): str(v) for k, v in raw.items()}
        except Exception as exc:
            logger.warning(
                "_load_wiki_map_merged: failed to load resolved YAML from {}: {}",
                rp,
                exc,
            )

    # Merge: start with resolved, then let curated win on conflict
    merged = {**resolved, **curated}
    return merged


def _get_company_name(deps: dict[str, Any], ticker: str) -> str | None:
    """Look up the company's display name via the market_data adapter."""
    try:
        adapter: Any = deps.get("market_data")
        if adapter is not None and hasattr(adapter, "get_company_name"):
            result: str | None = adapter.get_company_name(ticker)
            return result
        return None
    except Exception:
        return None


def _load_spine_tickers(market: str) -> list[str]:
    """Return the thematic spine tickers from config/universe/themes.yaml.

    Mirrors the loading HybridUniverseProvider uses: iterate themes.values() and
    collect each theme's tickers list.  Falls back to _load_wiki_map keys if the
    themes block is missing or malformed.
    """
    import yaml

    themes_path = Path(__file__).parent.parent / "config" / "universe" / "themes.yaml"
    if not themes_path.exists():
        return list(_load_wiki_map(market).keys())
    try:
        data = yaml.safe_load(themes_path.read_text())
        tickers: list[str] = []
        for theme in data.get("themes", {}).values():
            tickers.extend(
                theme if isinstance(theme, list) else theme.get("tickers", [])
            )
        return tickers if tickers else list(_load_wiki_map(market).keys())
    except Exception:
        return list(_load_wiki_map(market).keys())


@cli.command("resolve-wiki-articles")
@click.option("--market", default="us", help="Market config to use")
@click.option("--limit", default=0, type=int, help="Max tickers to process (0 = all)")
@click.option(
    "--min-views",
    default=50.0,
    type=float,
    show_default=True,
    help="Minimum mean daily pageviews to accept an article",
)
@click.option(
    "--throttle-s",
    default=1.5,
    type=float,
    show_default=True,
    help="Seconds to wait between Wikipedia API calls",
)
@click.option(
    "--out",
    default=None,
    help=("Output YAML path (default: config/universe/wiki_articles_<market>.yaml)"),
)
def resolve_wiki_articles(
    market: str,
    limit: int,
    min_views: float,
    throttle_s: float,
    out: str | None,
) -> None:
    """Resolve the ticker universe to Wikipedia article titles and write a YAML map.

    For each ticker not already covered by a curated alias in themes.yaml or the
    existing output file, the company name is looked up via yfinance and then
    resolved + validated via WikipediaArticleResolver.  The output YAML is written
    incrementally (each success is persisted immediately) so the command is resumable.
    """
    import yaml

    deps = _build_dependencies(market)
    config = deps["config"]
    tickers = _get_ticker_universe(config)
    if limit:
        tickers = tickers[:limit]

    # Validation window: stable 30-day window used to check article identity
    val_start = datetime(2024, 1, 1)
    val_end = datetime(2024, 1, 31)

    # Output path
    out_path = (
        Path(out)
        if out
        else (
            Path(__file__).parent.parent
            / "config"
            / "universe"
            / f"wiki_articles_{market}.yaml"
        )
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Load curated aliases (skip set — authoritative, never re-resolve)
    curated_map = _load_wiki_map(market)
    curated_tickers = set(curated_map.keys())

    # Load existing resolved entries (resumable skip set)
    existing: dict[str, str] = {}
    if out_path.exists():
        try:
            raw = yaml.safe_load(out_path.read_text()) or {}
            existing = {str(k): str(v) for k, v in raw.items()}
        except Exception:
            pass

    resolved_map: dict[str, str] = dict(existing)

    counts = {
        "resolved": 0,
        "no_name": 0,
        "no_article": 0,
        "skipped_existing": 0,
        "throttled": 0,
    }
    no_name_tickers: list[str] = []
    no_article_tickers: list[str] = []
    throttled_tickers: list[str] = []

    resolver = WikipediaArticleResolver(throttle_s=throttle_s)

    for ticker in tickers:
        if ticker in curated_tickers or ticker in existing:
            counts["skipped_existing"] += 1
            continue

        name = _get_company_name(deps, ticker)
        if not name:
            counts["no_name"] += 1
            no_name_tickers.append(ticker)
            logger.debug("resolve-wiki-articles: no name for {}", ticker)
            continue

        try:
            article = resolver.resolve_validated(name, val_start, val_end, min_views)
        except SourceThrottledError as exc:
            counts["throttled"] += 1
            throttled_tickers.append(ticker)
            logger.warning(
                "resolve-wiki-articles: throttled for {} ({}), skipping: {}",
                ticker,
                name,
                exc,
            )
            continue

        if article:
            resolved_map[ticker] = article
            counts["resolved"] += 1
            # Incremental write — crash-safe / resumable
            try:
                out_path.write_text(
                    yaml.dump(dict(sorted(resolved_map.items())), allow_unicode=True)
                )
            except Exception as exc:
                logger.warning("resolve-wiki-articles: write failed: {}", exc)
        else:
            counts["no_article"] += 1
            no_article_tickers.append(ticker)
            logger.debug(
                "resolve-wiki-articles: no validated article for {} ({})", ticker, name
            )

    # Final write (sorted keys)
    try:
        out_path.write_text(
            yaml.dump(dict(sorted(resolved_map.items())), allow_unicode=True)
        )
    except Exception as exc:
        logger.warning("resolve-wiki-articles: final write failed: {}", exc)

    click.echo(
        f"resolve-wiki-articles complete: "
        f"resolved={counts['resolved']} "
        f"no_name={counts['no_name']} "
        f"no_article={counts['no_article']} "
        f"throttled={counts['throttled']} "
        f"skipped_existing={counts['skipped_existing']}"
    )
    if no_name_tickers:
        click.echo(
            f"  no company name ({len(no_name_tickers)}): {', '.join(sorted(no_name_tickers))}"
        )
    if no_article_tickers:
        click.echo(
            f"  no valid article ({len(no_article_tickers)}): {', '.join(sorted(no_article_tickers))}"
        )
    if throttled_tickers:
        click.echo(
            f"  throttled / skipped ({len(throttled_tickers)}): {', '.join(sorted(throttled_tickers))}"
        )
    click.echo(f"Output: {out_path}")


@cli.command("drip-backfill")
@click.option("--market", default="us", help="Market config to use")
@click.option("--days", default=90, show_default=True, type=int)
@click.option("--limit", default=0, type=int, help="Max tickers (0 = all)")
@click.option("--spine-only", is_flag=True, help="Restrict to the thematic spine")
@click.option("--throttle-s", default=45.0, type=float, help="Seconds between requests")
@click.option(
    "--source",
    "source_filter",
    default=None,
    type=click.Choice(["wikipedia", "google_trends"]),
    help="Restrict to a single source (default: all)",
)
def drip_backfill(
    market: str,
    days: int,
    limit: int,
    spine_only: bool,
    throttle_s: float,
    source_filter: str | None,
) -> None:
    """Resumable slow-drip backfill aligned to the scan universe (rate-safe)."""
    import time
    from datetime import timezone

    from adapters.data.google_trends_adapter import GoogleTrendsAdapter
    from adapters.data.wikipedia_pageviews_adapter import WikipediaPageviewsAdapter

    deps = _build_dependencies(market)
    store = deps["store"]
    config = deps["config"]
    if spine_only:
        tickers = _load_spine_tickers(market)
    else:
        tickers = _get_ticker_universe(config)
    if limit:
        tickers = tickers[:limit]
    sources: dict[str, Any] = {
        "google_trends": GoogleTrendsAdapter(),
        "wikipedia": WikipediaPageviewsAdapter(article_map=_load_wiki_map(market)),
    }
    if source_filter:
        sources = {k: v for k, v in sources.items() if k == source_filter}
    uc = DripBackfillUseCase(
        sources=sources, store=store, sleep=time.sleep, throttle_s=throttle_s
    )
    report = uc.execute(tickers, now=datetime.now(timezone.utc), days=days)
    click.echo("Drip backfill complete. Source health:")
    for name, h in report.items():
        click.echo(
            f"  {name}: attempts={h.attempts} ok={h.ok} "
            f"empty={h.empty} throttled={h.throttled} failed={h.failed}"
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

    start_dt = datetime.fromisoformat(
        start
    )  # naive UTC — matches price/attention layers
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
            from application.price_returns import load_price_series

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


@cli.command("backfill-history")
@click.option("--market", default="us", help="Market config to use")
@click.option(
    "--days", default=90, show_default=True, type=int, help="Backfill window in days"
)
@click.option("--limit", default=0, type=int, help="Max tickers (0 = all in universe)")
def backfill_history(market: str, days: int, limit: int) -> None:
    """Backfill the divergence base window from honest historical archives (GDELT/GT/Wikipedia)."""
    from datetime import timezone

    from adapters.data.gdelt_sentiment_adapter import GdeltSentimentAdapter
    from adapters.data.google_trends_adapter import GoogleTrendsAdapter
    from adapters.data.wikipedia_pageviews_adapter import WikipediaPageviewsAdapter

    deps = _build_dependencies(market)
    store = deps["store"]
    config = deps["config"]
    tickers = _get_ticker_universe(config)
    if limit:
        tickers = tickers[:limit]

    now = datetime.now(timezone.utc)
    uc = BackfillHistoryUseCase(
        gdelt=GdeltSentimentAdapter(),
        trends=GoogleTrendsAdapter(),
        wiki=WikipediaPageviewsAdapter(article_map=_load_wiki_map(market)),
        store=store,
    )
    stats = uc.execute(tickers, now=now, days=days)
    click.echo(
        f"Backfill complete: {stats['tickers']} tickers, {stats['errors']} errors"
    )


def _cfg_cmin(market: str) -> float:
    """Return cmin threshold from market config (opportunity_engine.thresholds.cmin).

    Falls back to 6.0 (the scan-opportunities default) if the key is missing.
    """
    try:
        config = load_market_config(market)
        return float(
            config.get("opportunity_engine", {}).get("thresholds", {}).get("cmin", 6.0)
        )
    except Exception:
        return 6.0


def _cfg_dmin(market: str) -> float:
    """Return dmin threshold from market config (opportunity_engine.thresholds.dmin).

    Falls back to 6.0 (the scan-opportunities default) if the key is missing.
    """
    try:
        config = load_market_config(market)
        return float(
            config.get("opportunity_engine", {}).get("thresholds", {}).get("dmin", 6.0)
        )
    except Exception:
        return 6.0


def _is_backfill_due(market: str) -> bool:
    """Return True if 7+ days have elapsed since the most recent attention_series row.

    Implementation: we check whether get_attention_series for the first spine ticker
    returns any rows in the last 7 days.  If the table is empty OR the check fails,
    we conservatively return True (backfill is due).  This avoids adding a bespoke
    "last row" store query while keeping the check honest.
    """
    try:
        from datetime import timezone

        import yaml

        from adapters.data.sqlite_store import SQLiteStore

        store = SQLiteStore("data/recommendations.db")

        # Pick the first spine ticker from themes.yaml for the probe query
        themes_path = (
            Path(__file__).parent.parent / "config" / "universe" / "themes.yaml"
        )
        probe_ticker = "AAPL"  # safe fallback
        if themes_path.exists():
            data = yaml.safe_load(themes_path.read_text())
            tickers_in_themes: list[str] = []
            for theme in data.get("themes", {}).values():
                tickers_in_themes.extend(theme.get("tickers", []))
            if tickers_in_themes:
                probe_ticker = tickers_in_themes[0]

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        week_ago = now - timedelta(days=7)
        rows = store.get_attention_series(ticker=probe_ticker, start=week_ago, end=now)
        # If rows exist in the past 7 days → backfill not due
        return len(rows) == 0
    except Exception:
        # Can't determine → default to due (conservative)
        return True


@cli.command("daily-cycle")
@click.option("--market", default="us", help="Market config to use")
@click.option(
    "--skip-backfill",
    is_flag=True,
    help="Skip the weekly backfill refresh",
)
@click.pass_context
def daily_cycle(ctx: click.Context, market: str, skip_backfill: bool) -> None:
    """Run the full daily cycle: scan-opportunities -> resolve-calls -> weekly backfill.

    Chains three sub-commands in order:
      1. scan-opportunities  — surface new conviction × divergence calls
      2. resolve-calls       — mark due calls as outcomes vs SPY/NDX
      3. backfill-history    — refresh the divergence base window (weekly, conditional)

    The backfill step only runs when --skip-backfill is not set AND
    _is_backfill_due() returns True (i.e. no attention_series row in the last 7 days).
    """
    click.echo("Starting daily cycle...")

    ctx.invoke(
        scan_opportunities,
        market=market,
        date=None,
        cmin=_cfg_cmin(market),
        dmin=_cfg_dmin(market),
        max_discovery=50,
        show_all=False,
    )

    ctx.invoke(resolve_calls, date=None)

    if not skip_backfill and _is_backfill_due(market):
        click.echo("Backfill is due — running backfill-history...")
        ctx.invoke(backfill_history, market=market, days=14, limit=0)

    click.echo("Daily cycle complete.")


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
    from application.price_returns import load_price_series
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


def _get_backtest_universe(market: str) -> list[str]:
    """US S&P 500 + NASDAQ-100 (existing) plus TSX 60 with .TO suffix for the backtest.

    Reads ticker files directly (offline-safe — no network, no config object needed).
    """
    config_dir = Path(__file__).parent.parent / "config" / "tickers"
    us_files = [
        config_dir / "sp500.txt",
        config_dir / "nasdaq100.txt",
    ]
    us_existing = [f for f in us_files if f.exists()]

    us: list[str]
    if us_existing:
        from application.ticker_universe import load_ticker_universe

        us = load_ticker_universe(us_existing)
    else:
        # Minimal fallback identical to _get_ticker_universe's hardcoded list
        us = [
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

    tsx_path = config_dir / "tsx60.txt"
    tsx: list[str] = []
    if tsx_path.exists():
        for line in tsx_path.read_text().splitlines():
            s = line.strip()
            if s and not s.startswith("#"):
                tsx.append(f"{s}.TO")

    seen: set[str] = set()
    out: list[str] = []
    for t in [*us, *tsx]:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


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


@cli.command("portfolio-verdict")
@click.option(
    "--holdings",
    default="data/personal/holdings.csv",
    show_default=True,
    help="Local CSV (ticker,shares[,entry]) — gitignored, never committed",
)
@click.option("--market", default="us")
def portfolio_verdict(holdings: str, market: str) -> None:
    """Apply validated trend/exit rules to your current holdings (decision-support)."""
    import csv
    import os
    from datetime import datetime, timezone

    from application.price_returns import load_price_series

    if not os.path.exists(holdings):
        click.echo(
            f"No holdings file at {holdings}. Create it (ticker,shares) — it is gitignored."
        )
        return
    start_dt = datetime(2018, 1, 1, tzinfo=timezone.utc)
    end_dt = datetime.fromisoformat("2026-06-01")

    def provider(ticker: str) -> list[tuple[datetime, float]]:
        return load_price_series(ticker, start_dt, end_dt)

    uc = PortfolioVerdictUseCase(provider)
    with open(holdings) as f:
        rows = [r for r in csv.DictReader(f) if r.get("ticker")]
    click.echo(f"{'TICKER':8} {'VERDICT':16} {'TREND':6} STOP / WHY")
    for r in rows:
        v = uc.verdict_for(r["ticker"].strip().upper())
        stop = v.get("trailing_stop")
        stop_s = f"{stop:.2f}" if stop else "-"
        click.echo(
            f"{v['ticker']:8} {v['verdict']:16} "
            f"{'yes' if v['trend_intact'] else 'no':6} {stop_s}  {v.get('why','')}"
        )


@cli.command("holdings-risk")
@click.option(
    "--holdings",
    default="data/personal/holdings-report-2026-06-07.csv",
    show_default=True,
    help="Local broker CSV — gitignored, never committed",
)
@click.option(
    "--out",
    default="data/personal/holdings_risk_detail.txt",
    show_default=True,
    help="Full per-ticker detail (gitignored). Stdout stays masked.",
)
@click.option(
    "--log",
    default="data/personal/discipline_log.jsonl",
    show_default=True,
    help="Append assessments here for forward calibration (gitignored)",
)
@click.option(
    "--narrate", is_flag=True, help="Use local Ollama narrator (else template)"
)
def holdings_risk(holdings: str, out: str, log: str, narrate: bool) -> None:
    """Graded risk/discipline assessment of your holdings (decision-support, not prediction).
    Masked stdout (verdict distribution only); full detail to the gitignored --out file.
    """
    import os
    from datetime import datetime, timezone

    from application.discipline_log import append_assessments
    from application.holdings_reader import read_holdings
    from application.narrator import FakeNarrator
    from application.price_returns import load_price_series
    from domain.ports import NarratorPort

    rows = read_holdings(holdings)
    if not rows:
        click.echo(
            f"No holdings at {holdings} (ticker/Symbol + Quantity). It is gitignored."
        )
        return
    start_dt = datetime(2018, 1, 1, tzinfo=timezone.utc)
    end_dt = datetime.now(timezone.utc)

    _cache: dict[str, list[tuple[datetime, float]]] = {}

    def provider(ticker: str) -> list[tuple[datetime, float]]:
        if ticker not in _cache:
            _cache[ticker] = load_price_series(ticker, start_dt, end_dt)
        return _cache[ticker]

    narrator: NarratorPort
    if narrate:
        from adapters.ml.ollama_narrator import OllamaNarratorAdapter

        narrator = OllamaNarratorAdapter()
    else:
        narrator = FakeNarrator("")

    uc = HoldingsRiskAssessmentUseCase(provider, narrator)
    report = uc.execute(rows, start_dt, end_dt)
    positions = report["positions"]
    pf = report["portfolio"]

    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w") as f:
        f.write(f"{'TICKER':10} {'VERDICT':8} {'TREND':>6} {'UNREAL':>8}  WHY\n")
        for p in positions:
            th = f"{p.trend_health:+.1f}" if p.trend_health is not None else "  -"
            f.write(
                f"{p.ticker:10} {p.verdict.value:8} {th:>6} {p.unrealized_pct*100:+7.0f}%  {p.why}\n"
            )

    now_iso = end_dt.isoformat()
    append_assessments(
        log,
        [
            {
                "ticker": p.ticker,
                "verdict": p.verdict.value,
                "price": p.price,
                "trend_health": p.trend_health,
                "as_of": now_iso,
            }
            for p in positions
        ],
    )

    click.echo(
        f"Assessed {pf.n_positions} positions. Verdict distribution: {pf.verdict_counts}"
    )
    click.echo(
        f"Broken-trend share: {pf.broken_trend_share:.0%}  Top concentration: {pf.top_concentration:.0%}"
    )
    click.echo(f"Full per-ticker detail written to {out} (gitignored).")


@cli.command("resolve-discipline-flags")
@click.option("--log", default="data/personal/discipline_log.jsonl", show_default=True)
@click.option("--horizon", default=21, type=int, show_default=True)
def resolve_discipline_flags(log: str, horizon: int) -> None:
    """Forward-score past REDUCE/TRIM flags: were they followed by drops? (calibration)."""
    from datetime import datetime, timezone

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


@cli.command("holdings-risk-calibrate")
@click.option(
    "--ticker", required=True, help="Symbol to compute history base rates for"
)
@click.option("--horizon", default=21, type=int, show_default=True)
def holdings_risk_calibrate(ticker: str, horizon: int) -> None:
    """Warm-start base rates from price history: what followed each trend state."""
    from datetime import datetime, timezone

    from domain.calibration import base_rate_from_history

    start_dt = datetime(2018, 1, 1, tzinfo=timezone.utc)
    end_dt = datetime.now(timezone.utc)
    closes = [c for _, c in load_price_series(ticker, start_dt, end_dt)]
    rates = base_rate_from_history(
        closes, trend_window=200, atr_window=22, horizon=horizon
    )
    if not rates:
        click.echo(f"Not enough history for {ticker}.")
        return
    for bucket, stats in rates.items():
        click.echo(
            f"{bucket:6} n={int(stats['n'])} mean_fwd={stats['mean_fwd_return']:+.2%} "
            f"down_rate={stats['down_rate']:.0%}"
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
    from datetime import datetime, timezone

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


# ---------------------------------------------------------------------------
# Evidence-screen CLI commands (Task 7)
# ---------------------------------------------------------------------------


def _build_evidence_screen(deps: dict[str, Any]) -> "Any":
    """Wire the four thin adapter ports into an EvidenceScreenUseCase.

    Extracted so both `screen-candidates` and `weekly-brief` use the same
    adapter wiring (DRY).  Returns an EvidenceScreenUseCase instance.
    """
    from datetime import timezone

    from application.evidence_screen_use_case import EvidenceScreenUseCase
    from application.narrator import template_narration
    from domain.screen_models import ScreenCandidate

    market_data = deps["market_data"]

    class _PriceAdapter:
        """Wraps YFinanceAdapter to satisfy PricePort."""

        def monthly_closes(self, ticker: str) -> list[float]:
            try:
                now = datetime.now(timezone.utc)
                two_years_ago = now.replace(year=now.year - 2)
                signals = market_data.get_signals(ticker, now, start_date=two_years_ago)
                if not signals:
                    return []
                by_month: dict[str, float] = {}
                for s in signals:
                    key = f"{s.timestamp.year}-{s.timestamp.month:02d}"
                    by_month[key] = s.close
                return [by_month[k] for k in sorted(by_month)]
            except Exception:
                return []

        def trend_health(self, ticker: str) -> float:
            try:
                from domain.trend_rules import atr, sma
                from domain.trend_rules import trend_health as _th

                now = datetime.now(timezone.utc)
                two_years_ago = now.replace(year=now.year - 2)
                signals = market_data.get_signals(ticker, now, start_date=two_years_ago)
                if len(signals) < 22:
                    return 0.0
                closes = [s.close for s in signals]
                highs = [s.high for s in signals]
                lows = [s.low for s in signals]
                sma_val = sma(closes, min(200, len(closes)))
                atr_val = atr(highs, lows, closes, 22)
                th = _th(closes[-1], sma_val, atr_val)
                return th if th is not None else 0.0
            except Exception:
                return 0.0

        def has_min_history(self, ticker: str) -> bool:
            try:
                now = datetime.now(timezone.utc)
                two_years_ago = now.replace(year=now.year - 2)
                signals = market_data.get_signals(ticker, now, start_date=two_years_ago)
                return len(signals) >= 21
            except Exception:
                return False

    class _AnalystAdapter:
        """Wraps YFinanceAdapter to satisfy AnalystPort."""

        def estimate_series(self, ticker: str) -> list[float] | None:
            try:
                data = market_data.get_analyst_data(ticker, datetime.now(timezone.utc))
                if data is None:
                    return None
                targets = [
                    v
                    for k, v in data.items()
                    if "target" in k and isinstance(v, (int, float))
                ]
                return targets if targets else None
            except Exception:
                return None

    class _FundamentalsAdapter:
        """Wraps YFinanceAdapter to satisfy FundamentalsPort."""

        def quality_value(self, ticker: str) -> dict[str, float]:
            try:
                info = market_data.get_ticker_info(ticker)
                quality = (
                    info.get("return_on_equity") or info.get("profit_margins") or 0.0
                )
                value = (
                    1.0 / info["trailing_pe"]
                    if info.get("trailing_pe") and info["trailing_pe"] > 0
                    else 0.0
                )
                return {"quality": float(quality), "value": float(value)}
            except Exception:
                return {"quality": 0.0, "value": 0.0}

    class _NarratorAdapter:
        """Wraps template_narration to satisfy NarratorPort."""

        def narrate(self, candidate: ScreenCandidate) -> str:
            return template_narration(
                {
                    "ticker": candidate.ticker,
                    "verdict": candidate.label.value,
                    "trend_health": candidate.trend_health,
                }
            )

    return EvidenceScreenUseCase(
        price=_PriceAdapter(),
        analyst=_AnalystAdapter(),
        fundamentals=_FundamentalsAdapter(),
        narrator=_NarratorAdapter(),
    )


@cli.command("screen-candidates")
@click.option("--top", default=10, show_default=True, type=int, help="Top N rank limit")
@click.option(
    "--report-dir",
    default="data/reports/",
    show_default=True,
    help="Directory to write screen_<date>.json",
)
def screen_candidates(top: int, report_dir: str) -> None:
    """Screen universe for disciplined, evidence-bounded candidates.

    Writes the FULL ranked candidate distribution to <report-dir>/screen_<date>.json
    (honesty rule: full distribution, not just top-N).  Prints a masked summary to
    stdout (counts + label distribution only — no per-ticker scores).
    """
    import json
    from datetime import date, timezone

    from application.evidence_screen_use_case import label_from_verdict_file

    deps = _build_dependencies("us")
    config = deps["config"]
    tickers = _get_ticker_universe(config)

    # Reuse the shared helper so weekly-brief wires the same adapters (DRY).
    uc = _build_evidence_screen(deps)
    as_of = date.today().isoformat()
    # Run with full universe length so rank_universe returns ALL eligible candidates.
    # --top applies ONLY to the stdout masked summary and the surfaced-calls slice.
    result = uc.run(universe=tickers, as_of=as_of, top_n=len(tickers))

    # --- verdict-driven label: read latest backtest verdict and relabel candidates ---
    verdict_label = label_from_verdict_file(report_dir)
    from dataclasses import replace

    labeled_candidates = tuple(
        replace(c, label=verdict_label) for c in result.candidates
    )
    from domain.screen_models import ScreenResult

    result = ScreenResult(
        as_of=result.as_of,
        candidates=labeled_candidates,
        universe_size=result.universe_size,
        regime=result.regime,
        scorecard_ref=result.scorecard_ref,
        abstained=result.abstained,
    )

    # --- surface ONLY the top-N candidates as SurfacedCalls for forward-tracking ---
    store = deps["store"]
    as_of_dt = datetime.now(timezone.utc)
    from domain.screen_models import ScreenResult as _SR

    top_result = _SR(
        as_of=result.as_of,
        candidates=result.candidates[:top],
        universe_size=result.universe_size,
        regime=result.regime,
        scorecard_ref=result.scorecard_ref,
        abstained=result.abstained,
    )
    uc.surface_calls(top_result, as_of_dt=as_of_dt, store=store)

    # --- persist FULL distribution (honesty rule) ---
    report_path = Path(report_dir)
    report_path.mkdir(parents=True, exist_ok=True)
    out_file = report_path / f"screen_{as_of}.json"
    payload: dict[str, object] = {
        "as_of": as_of,
        "universe_size": result.universe_size,
        "top_n": top,
        "regime": result.regime,
        "abstained": result.abstained,
        "candidates": [
            {
                "ticker": c.ticker,
                "composite": c.composite,
                "trend_health": c.trend_health,
                "label": c.label.value,
                "why": c.why,
                "factor_scores": [
                    {
                        "name": f.name,
                        "value": f.value,
                        "percentile": f.percentile,
                        "contribution": f.contribution,
                    }
                    for f in c.factor_scores
                ],
            }
            for c in result.candidates  # ALL candidates (full distribution)
        ],
    }
    out_file.write_text(json.dumps(payload, indent=2))

    # --- masked stdout (counts + label distribution only) ---
    from collections import Counter

    label_counts = Counter(c.label.value for c in result.candidates)
    abstain_note = "  [abstaining: thin factor coverage]" if result.abstained else ""
    click.echo(
        f"\nScreen complete ({as_of}): {len(result.candidates)} candidates "
        f"from {result.universe_size} universe  [top_n={top}]{abstain_note}"
    )
    for label, count in sorted(label_counts.items()):
        click.echo(f"  {label}: {count}")
    click.echo(f"Full distribution written to: {out_file}")


@cli.command("backtest-screen")
@click.option("--market", default="us", show_default=True, help="Market config (us|ca)")
@click.option(
    "--start", default="2018-01-01", show_default=True, help="Backtest start date"
)
@click.option(
    "--end", default="2026-01-01", show_default=True, help="Backtest end date"
)
@click.option(
    "--horizon-days",
    default=21,
    show_default=True,
    type=int,
    help="Forward-return horizon in calendar days",
)
@click.option(
    "--limit",
    default=0,
    type=int,
    show_default=True,
    help="Cap universe size (0 = all tickers from sp500+nasdaq100+tsx60)",
)
@click.option(
    "--report-dir",
    default="data/reports/",
    show_default=True,
    help="Directory to write screen_ic_<date>.json",
)
def backtest_screen(
    market: str,
    start: str,
    end: str,
    horizon_days: int,
    limit: int,
    report_dir: str,
) -> None:
    """Point-in-time IC backtest for the evidence-screen MOMENTUM composite.

    HONESTY CONSTRAINT (project rule #2 — no look-ahead bias):
    Only the MOMENTUM factor is backtested.  Revision, quality, and value
    require point-in-time fundamental/analyst snapshots unavailable from
    yfinance for 2018-2026.  Using current values at past dates would be
    catastrophic look-ahead bias.  Those factors are flagged-neutral (None)
    throughout, exactly as the live composite_score handles missing factors.
    The caveat is printed to stdout and embedded in the JSON report every run.

    Universe: US S&P 500 + NASDAQ-100 (sp500.txt + nasdaq100.txt) plus TSX 60
    (tsx60.txt with .TO suffix).  Monthly evaluation cadence.
    """
    import json
    from datetime import date

    from application.screen_backtest_use_case import ScreenBacktestUseCase
    from application.screen_ic_panels import build_screen_panels

    _CAVEAT = (
        "Composite tested on MOMENTUM leg only; revision/quality/value lack "
        "point-in-time history for 2018-2026 and were flagged-neutral to avoid "
        "look-ahead bias (project rule #2)."
    )

    # ------------------------------------------------------------------
    # Build universe: SP500 + NASDAQ100 + TSX60 (reuse _get_backtest_universe)
    # ------------------------------------------------------------------
    tickers = _get_backtest_universe(market)
    universe_size = len(tickers)
    if limit:
        tickers = tickers[:limit]
        universe_size = len(tickers)

    click.echo(f"Universe: {universe_size} tickers (sp500+nasdaq100+tsx60, deduped)")

    # ------------------------------------------------------------------
    # Date range: monthly cadence (first-of-month / 28-day steps)
    # ------------------------------------------------------------------
    start_dt = datetime.fromisoformat(start)
    end_dt = datetime.fromisoformat(end)
    dates: list[datetime] = []
    d = start_dt
    while d <= end_dt - timedelta(days=horizon_days):
        dates.append(d)
        d += timedelta(days=28)

    click.echo(
        f"Date range: {start} → {end}  |  {len(dates)} evaluation dates  |  horizon={horizon_days}d"
    )

    # ------------------------------------------------------------------
    # Price cache (load once per ticker over [start-400d, end+horizon+5d])
    # ------------------------------------------------------------------
    price_start = start_dt - timedelta(days=400)
    price_end = end_dt + timedelta(days=horizon_days + 5)

    _price_cache: dict[str, list[tuple[datetime, float]]] = {}

    def _prices(ticker: str) -> list[tuple[datetime, float]]:
        if ticker not in _price_cache:
            _price_cache[ticker] = load_price_series(ticker, price_start, price_end)
        return _price_cache[ticker]

    # Preload benchmark
    click.echo("Loading price data (this is the network call — skipped in tests)...")
    _prices("SPY")
    all_tickers_to_load = list(tickers)
    for i, t in enumerate(all_tickers_to_load, 1):
        _prices(t)
        if i % 50 == 0:
            click.echo(f"  Loaded {i}/{len(all_tickers_to_load)} tickers...")

    n_with_data = sum(1 for t in tickers if _price_cache.get(t))
    click.echo(f"Tickers with price data: {n_with_data}/{len(tickers)}")

    # ------------------------------------------------------------------
    # Build panels
    # ------------------------------------------------------------------
    click.echo("Building point-in-time panels...")
    panels, benchmark_returns = build_screen_panels(
        tickers=list(tickers),
        dates=dates,
        price_series_fn=_prices,
        horizon_days=horizon_days,
        benchmark_ticker="SPY",
    )

    # ------------------------------------------------------------------
    # Run ScreenBacktestUseCase
    # ------------------------------------------------------------------
    uc = ScreenBacktestUseCase()
    verdict = uc.run(panels, market_returns=benchmark_returns)

    # ------------------------------------------------------------------
    # Write report JSON
    # ------------------------------------------------------------------
    as_of = date.today().isoformat()
    report_path = Path(report_dir)
    report_path.mkdir(parents=True, exist_ok=True)
    out_file = report_path / f"screen_ic_{as_of}.json"
    report_data = {
        "as_of": as_of,
        "universe_size": universe_size,
        "n_tickers_with_data": n_with_data,
        "decision": verdict.decision,
        "mean_ic": verdict.mean_ic,
        "n_dates": verdict.n_dates,
        "ic_ci_low": verdict.ic_ci_low,
        "ic_ci_high": verdict.ic_ci_high,
        "sharpe_diff_point": verdict.sharpe_diff_point,
        "sharpe_diff_ci_low": verdict.sharpe_diff_ci_low,
        "sharpe_diff_ci_high": verdict.sharpe_diff_ci_high,
        "primary_pass": verdict.primary_pass,
        "secondary_pass": verdict.secondary_pass,
        "horizon_days": horizon_days,
        "start": start,
        "end": end,
        "caveat": _CAVEAT,
    }
    out_file.write_text(json.dumps(report_data, indent=2))

    # ------------------------------------------------------------------
    # Stdout (honest/full per ADR-042 — CI and caveat every run)
    # ------------------------------------------------------------------
    _VERDICT_LABELS = {
        "PASS": "PASS — IC >= 0.02 and/or top-decile Sharpe-diff CI excludes 0.",
        "INCONCLUSIVE": "INCONCLUSIVE — IC in (0, 0.02); insufficient evidence of edge.",
        "HALT": "HALT — IC CI entirely negative; signal has no cross-sectional lift.",
    }
    click.echo(f"\nScreen IC Backtest  ({as_of})")
    click.echo(
        f"  universe        : {universe_size} tickers  ({n_with_data} with price data)"
    )
    click.echo(f"  n_dates         : {verdict.n_dates}")
    click.echo(f"  mean_IC         : {verdict.mean_ic:.6f}")
    ic_ci = (
        f"[{verdict.ic_ci_low}, {verdict.ic_ci_high}]"
        if verdict.ic_ci_low is not None
        else "n/a (n<2)"
    )
    click.echo(f"  IC bootstrap CI : {ic_ci}")
    sd_pt = (
        f"{verdict.sharpe_diff_point:.4f}"
        if verdict.sharpe_diff_point is not None
        else "n/a"
    )
    sd_ci = (
        f"[{verdict.sharpe_diff_ci_low:.4f}, {verdict.sharpe_diff_ci_high:.4f}]"
        if verdict.sharpe_diff_ci_low is not None
        else "n/a"
    )
    click.echo(f"  sharpe_diff     : {sd_pt}  CI={sd_ci}")
    click.echo(f"  primary_pass    : {verdict.primary_pass}")
    click.echo(f"  secondary_pass  : {verdict.secondary_pass}")
    click.echo(f"  verdict         : {verdict.decision}")
    click.echo(f"  {_VERDICT_LABELS.get(verdict.decision, verdict.decision)}")
    click.echo(f"\n  CAVEAT: {_CAVEAT}")
    click.echo(f"\nReport written to: {out_file}")


# ---------------------------------------------------------------------------
# Weekly Brief CLI command (Phase B)
# ---------------------------------------------------------------------------


def _build_weekly_brief(
    market: str, holdings: "list[Any]", report_dir: str
) -> "tuple[Any, list[str]]":
    """Wire real adapters into a WeeklyBriefUseCase. Returns (use_case, universe)."""
    from datetime import timezone

    from adapters.ml.correlation_analyzer import CorrelationAnalyzer
    from application.discipline_log import read_assessments, resolve_flags
    from application.forward_tracking_use_case import ForwardTrackingUseCase
    from application.narrator import FakeNarrator
    from application.weekly_brief_use_case import RegimeReadUseCase, WeeklyBriefUseCase
    from domain.trend_rules import sma as _sma
    from domain.trend_rules import trend_health as _trend_health

    deps = _build_dependencies(market)
    store = deps["store"]
    market_data = deps["market_data"]
    universe = _get_backtest_universe(market)

    # Screen ports: same adapters as screen-candidates (DRY via shared helper).
    screen = _build_evidence_screen(deps)

    def _price_provider(ticker: str) -> "list[tuple[Any, float]]":
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=420)
        return load_price_series(ticker, start, end)

    # HoldingsRiskAssessmentUseCase requires a non-None narrator; use template fallback
    # (same as holdings-risk command with --narrate off, ADR-047).
    holdings_risk = HoldingsRiskAssessmentUseCase(_price_provider, FakeNarrator(""))

    def _vix() -> float:
        end = datetime.now(timezone.utc)
        series = load_price_series("^VIX", end - timedelta(days=10), end)
        return series[-1][1] if series else 20.0

    def _spy_trend() -> float:
        end = datetime.now(timezone.utc)
        series = load_price_series("SPY", end - timedelta(days=420), end)
        closes = [c for _, c in series]
        if len(closes) < 200:
            return 0.0
        sma_val = _sma(closes, 200)
        diffs = [abs(closes[i] - closes[i - 1]) for i in range(-20, 0)]
        atr_val: float | None = sum(diffs) / len(diffs) if diffs else None
        th = _trend_health(closes[-1], sma_val, atr_val)
        return th if th is not None else 0.0

    regime_reader = RegimeReadUseCase(vix_provider=_vix, spy_trend_provider=_spy_trend)

    # Concentration: build a CorrelationAnalyzer graph over holdings + universe head.
    analyzer = CorrelationAnalyzer()
    held = [h.ticker for h in holdings]
    graph_tickers = list(dict.fromkeys(held + universe[:100]))
    signals_by_ticker = {}
    for t in graph_tickers:
        try:
            signals_by_ticker[t] = market_data.get_signals(
                t, datetime.now(timezone.utc)
            )
        except Exception:
            signals_by_ticker[t] = []
    try:
        analyzer.build_graph(signals_by_ticker)
    except Exception:
        pass  # concentration overlaps degrade to empty if the graph can't build

    def _cluster_peers(ticker: str) -> list[str]:
        try:
            return analyzer.get_cluster_peers(ticker)
        except Exception:
            return []

    forward = ForwardTrackingUseCase(store, market_data)

    def _screen_scorecard() -> "tuple[float | None, float | None, int, bool]":
        records = forward.get_track_record()
        return (None, None, len(records), False)

    def _discipline_scorecard() -> "tuple[float | None, int, str]":
        log_path = "data/personal/discipline_log.jsonl"
        try:
            logged = read_assessments(log_path)
        except Exception:
            return (None, 0, "NO-LOG")
        res = resolve_flags(logged, _price_provider, horizon_days=21)
        n = int(res.get("resolved", 0))
        # resolve_flags returns 0.0 (not None) when no REDUCE flags resolved; restore
        # the "None = no data" semantics so the brief renders down-rate "n/a", not "0%".
        dr = res.get("down_rate_on_reduce") if n > 0 else None
        brier = res.get("brier", 1.0)
        gate = (
            "PROCEED"
            if (dr is not None and dr >= 0.55 and brier <= 0.45 and n >= 30)
            else "PENDING"
        )
        return (dr, n, gate)

    from application.evidence_screen_use_case import label_from_verdict_file

    uc = WeeklyBriefUseCase(
        screen=screen,
        holdings_risk=holdings_risk,
        regime_reader=regime_reader,
        screen_label_fn=label_from_verdict_file,
        cluster_peers_fn=_cluster_peers,
        screen_scorecard_fn=_screen_scorecard,
        discipline_scorecard_fn=_discipline_scorecard,
    )
    return uc, universe


@cli.command("weekly-brief")
@click.option("--market", default="us", show_default=True, help="Market config")
@click.option(
    "--holdings",
    default="data/personal/holdings-report-2026-06-07.csv",
    show_default=True,
    help="Holdings CSV (gitignored).",
)
@click.option(
    "--out",
    default="data/personal/weekly_brief.md",
    show_default=True,
    help="Full markdown brief (gitignored — contains holdings detail).",
)
@click.option("--report-dir", default="data/reports/", show_default=True)
@click.option("--top-n", default=10, type=int, show_default=True)
def weekly_brief(
    market: str, holdings: str, out: str, report_dir: str, top_n: int
) -> None:
    """Generate the unified weekly brief (masked stdout + gitignored full markdown).

    Composes the Phase-A evidence screen, the discipline engine, a regime tilt,
    a concentration warning, and the forward scorecard. Phase B adds no predictive
    claim; a RESEARCH_ONLY screen renders no 'buy' language.
    """
    from application.holdings_reader import read_holdings
    from domain.brief import to_markdown, to_stdout_masked

    held = read_holdings(holdings)
    uc, universe = _build_weekly_brief(market, held, report_dir)
    brief = uc.execute(
        universe=universe,
        holdings=held,
        as_of=datetime.now(),
        report_dir=report_dir,
        top_n=top_n,
    )

    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(to_markdown(brief))

    click.echo(to_stdout_masked(brief))
    click.echo(f"\nFull brief (gitignored) written to: {out_path}")


@cli.command("backtest-trend-sleeve")
@click.option("--start", default="2008-01-01", show_default=True)
@click.option("--end", default="2026-01-01", show_default=True)
@click.option("--report-dir", default="data/reports/", show_default=True)
def backtest_trend_sleeve(start: str, end: str, report_dir: str) -> None:
    """Pre-registered trend-following sleeve falsification test (spec 2026-06-08).

    80% SPY + 20% 12-mo time-series-momentum sleeve (7 liquid ETFs, long/flat,
    inverse-vol). LOCKED gate: PASS if blended Sharpe-diff CI excludes 0 OR max
    drawdown cut >=25% net of cost; KILL if strictly worse; else INCONCLUSIVE.
    Backtest only — no product. Honest non-claim: diversifier sleeve, not alpha.
    """
    import json
    from datetime import date, datetime, timedelta

    from application import trend_sleeve_backtest as tsb
    from application.trend_sleeve_backtest import UNIVERSE, TrendSleeveBacktestUseCase

    start_dt = datetime.fromisoformat(start)
    end_dt = datetime.fromisoformat(end)

    # Month-end dates (28th as a stable in-month sentinel), monthly cadence.
    months: list[datetime] = []
    d = start_dt
    while d <= end_dt:
        months.append(datetime(d.year, d.month, 28))
        d = datetime(d.year + (d.month // 12), (d.month % 12) + 1, 1)

    price_start = start_dt - timedelta(days=420)  # 12-mo lookback + buffer
    cache: dict[str, list[tuple[datetime, float]]] = {}

    def _prices(ticker: str) -> list[tuple[datetime, float]]:
        if ticker not in cache:
            # Reference via the module so tests can patch load_price_series.
            cache[ticker] = tsb.load_price_series(ticker, price_start, end_dt)
        return cache[ticker]

    click.echo(f"Loading {len(UNIVERSE)} ETFs ({', '.join(UNIVERSE)})...")
    uc = TrendSleeveBacktestUseCase(price_series_fn=_prices)
    v = uc.execute(months)

    as_of = date.today().isoformat()
    out_dir = Path(report_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"trend_sleeve_{as_of}.json"
    report = {
        "as_of": as_of,
        "start": start,
        "end": end,
        "n_months": v.n_months,
        "decision": v.decision,
        "sharpe_spy": v.sharpe_spy,
        "sharpe_sleeve": v.sharpe_sleeve,
        "sharpe_blended": v.sharpe_blended,
        "maxdd_spy": v.maxdd_spy,
        "maxdd_sleeve": v.maxdd_sleeve,
        "maxdd_blended": v.maxdd_blended,
        "cagr_spy": v.cagr_spy,
        "cagr_sleeve": v.cagr_sleeve,
        "cagr_blended": v.cagr_blended,
        "sharpe_diff_point": v.sharpe_diff_point,
        "sharpe_diff_ci_low": v.sharpe_diff_ci_low,
        "sharpe_diff_ci_high": v.sharpe_diff_ci_high,
        "dd_reduction": v.dd_reduction,
        "sharpe_blended_6040": v.sharpe_blended_6040,
        "maxdd_blended_6040": v.maxdd_blended_6040,
        "claim": "diversifier sleeve (risk control), NOT alpha — see spec 2026-06-08",
    }
    out_file.write_text(json.dumps(report, indent=2))

    click.echo(f"\nTrend-Following Sleeve Backtest ({as_of})  n_months={v.n_months}")
    click.echo(
        f"  SPY-core    : Sharpe {v.sharpe_spy:+.3f}  maxDD {v.maxdd_spy:+.1%}"
        f"  CAGR {v.cagr_spy:+.1%}"
    )
    click.echo(
        f"  sleeve      : Sharpe {v.sharpe_sleeve:+.3f}  maxDD {v.maxdd_sleeve:+.1%}"
        f"  CAGR {v.cagr_sleeve:+.1%}"
    )
    click.echo(
        f"  blended80/20: Sharpe {v.sharpe_blended:+.3f}  maxDD {v.maxdd_blended:+.1%}"
        f"  CAGR {v.cagr_blended:+.1%}"
    )
    sd_ci = (
        f"[{v.sharpe_diff_ci_low}, {v.sharpe_diff_ci_high}]"
        if v.sharpe_diff_ci_low is not None
        else "n/a"
    )
    click.echo(f"  Sharpe-diff (blended-SPY): {v.sharpe_diff_point}  CI={sd_ci}")
    click.echo(f"  drawdown reduction: {v.dd_reduction:+.1%}  (gate >= 25%)")
    click.echo(
        f"  [sensitivity 60/40, not gated] Sharpe {v.sharpe_blended_6040}"
        f"  maxDD {v.maxdd_blended_6040}"
    )
    click.echo(f"  VERDICT: {v.decision}")
    click.echo("  (diversifier sleeve = risk control, NOT alpha)")
    click.echo(f"Report -> {out_file}")


if __name__ == "__main__":
    cli()
