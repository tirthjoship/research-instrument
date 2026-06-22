"""Scan-related CLI commands: daily-scan, validate-3b, scan-opportunities, resolve-calls, opportunity-report."""

from __future__ import annotations

from datetime import date as _date
from datetime import datetime, timedelta
from typing import Any

import click

from ._cli_group import cli
from ._deps import (
    _build_dependencies,
    _CombinedAttention,
    _get_ticker_universe,
    _load_wiki_map,
)


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
    from pathlib import Path

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
        Path(__file__).parent.parent.parent / "config" / "universe" / "themes.yaml"
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
    from application.opportunity_scan_use_case import OpportunityScanUseCase

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


@cli.command("surface-candidates")
@click.option(
    "--run-id",
    default=None,
    type=int,
    help="Corroboration run ID to read (default: latest)",
)
@click.option(
    "--date",
    "as_of_str",
    default=None,
    help="As-of date YYYY-MM-DD for TTL (default: today UTC)",
)
@click.option(
    "--max",
    "max_admissions",
    default=10,
    show_default=True,
    type=int,
    help="Max tickers to admit this run",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Print admissions without writing to store",
)
def surface_candidates(
    run_id: int | None,
    as_of_str: str | None,
    max_admissions: int,
    dry_run: bool,
) -> None:
    """Surface corroborated tickers into the discovered-universe overlay. RESEARCH_ONLY."""
    import sqlite3
    from pathlib import Path

    import yaml

    from adapters.data.corroboration_store import CorroborationStore
    from adapters.data.yfinance_resolver import YFinanceResolver
    from application.surfacing_use_case import SurfacingUseCase

    as_of = _date.fromisoformat(as_of_str) if as_of_str else datetime.utcnow().date()

    conn = sqlite3.connect("data/recommendations.db")
    store = CorroborationStore(conn)
    store.init_schema()

    # Resolve run_id
    resolved_run_id = run_id if run_id is not None else store.latest_run_id()
    if resolved_run_id is None:
        click.echo(
            click.style(
                "No corroboration runs found. Run `corroborate` first.", fg="yellow"
            )
        )
        return

    candidates = store.load_candidates(resolved_run_id)
    if not candidates:
        click.echo(
            click.style(
                f"No candidate snapshots for run #{resolved_run_id}. Re-run `corroborate`.",
                fg="yellow",
            )
        )
        return

    # Load spine tickers (themes.yaml + sp500.txt + nasdaq100.txt)
    spine: set[str] = set()
    themes_path = Path("config/universe/themes.yaml")
    if themes_path.exists():
        data = yaml.safe_load(themes_path.read_text())
        for tickers in data.get("themes", {}).values():
            spine.update(tickers)
    config_dir = Path("config/tickers")
    for fname in ("sp500.txt", "nasdaq100.txt"):
        fpath = config_dir / fname
        if fpath.exists():
            for line in fpath.read_text().splitlines():
                s = line.strip()
                if s and not s.startswith("#"):
                    spine.add(s)

    click.echo(click.style("\n  RESEARCH ONLY -- no buy/sell signals\n", bold=True))
    click.echo(
        f"Surfacing from run #{resolved_run_id} ({as_of.isoformat()}) -- {len(candidates)} candidate(s)"
    )

    if dry_run:
        # Print what would be admitted without writing
        from domain.corroboration_models import ConvergenceTier

        _ADMIT_TIERS = {ConvergenceTier.STRONG, ConvergenceTier.MODERATE}
        eligible = sorted(
            (
                c
                for c in candidates
                if c.convergence in _ADMIT_TIERS and c.verification == "ALL_VERIFIED"
            ),
            key=lambda c: c.mean_convergence,
            reverse=True,
        )[:max_admissions]
        for c in eligible:
            if c.ticker in spine:
                click.echo(f"  ~ {c.ticker:<6} already in spine -- would skip")
            else:
                click.echo(f"  + {c.ticker:<6} convergence={c.convergence.value}")
        click.echo("\n[dry-run] no changes written.")
        return

    uc = SurfacingUseCase(
        store=store,
        spine_tickers=frozenset(spine),
        resolver=YFinanceResolver(),
        max_admissions=max_admissions,
    )
    active = uc.run(candidates=candidates, run_id=resolved_run_id, as_of=as_of)

    click.echo(f"\nActive discovered universe: {len(active)} ticker(s)")
    for entry in sorted(active, key=lambda e: e.ticker):
        click.echo(
            f"  {entry.ticker:<6} {entry.company_name:<30} ({entry.sector})  convergence={entry.convergence.value}"
        )

    click.echo(click.style("\n  RESEARCH ONLY -- no buy/sell signals\n", bold=True))
