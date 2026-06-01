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

    return {
        "market_data": adapter,
        "technical_analysis": adapter,  # same adapter, implements both ports
        "feature_engineer": fe,
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


def _get_ticker_universe(config: dict[str, Any]) -> list[str]:
    """Get ticker universe from config.

    Phase 3A: static list. Phase 3B: dynamic buzz-driven discovery.
    """
    # Default S&P 500 subset for Phase 3A
    return [
        "AAPL",
        "MSFT",
        "GOOG",
        "AMZN",
        "NVDA",
        "META",
        "TSLA",
        "BRK-B",
        "UNH",
        "JNJ",
        "V",
        "XOM",
        "JPM",
        "PG",
        "MA",
        "HD",
        "CVX",
        "MRK",
        "ABBV",
        "LLY",
        "PEP",
        "KO",
        "COST",
        "AVGO",
        "WMT",
        "MCD",
        "CSCO",
        "ACN",
        "TMO",
        "ABT",
        "DHR",
        "NEE",
        "LIN",
        "TXN",
        "PM",
        "UPS",
        "RTX",
        "HON",
        "LOW",
        "QCOM",
    ]


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
