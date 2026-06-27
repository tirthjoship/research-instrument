"""Backtest-related CLI commands: backtest-trend-sleeve, backtest-insider-clusters, daily-cycle."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import click

from ._cli_group import cli
from ._deps import _cfg_cmin, _cfg_dmin, _is_backfill_due


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
    from datetime import date

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


@cli.command("lazy-prices")
@click.option("--start", default="2015-01-01", show_default=True)
@click.option("--end", default="2024-12-31", show_default=True)
@click.option("--report-dir", default="data/reports/", show_default=True)
@click.option("--cache-dir", default="data/cache/lazy_prices/", show_default=True)
@click.option(
    "--ticker-file",
    "ticker_files",
    multiple=True,
    default=("config/tickers/sp500.txt", "config/tickers/nasdaq100.txt"),
    show_default=True,
)
@click.option(
    "--limit",
    type=int,
    default=0,
    show_default=True,
    help="Cap universe size for a SMOKE test (0 = full). limit>0 is NOT a verdict run.",
)
def lazy_prices(
    start: str,
    end: str,
    report_dir: str,
    cache_dir: str,
    ticker_files: tuple[str, ...],
    limit: int,
) -> None:
    """Pre-registered Lazy Prices (ADR-057) verdict run — filing text-change vs forward excess.

    LOCKED gate (do NOT tune): primary rank-IC ci_low>0 AND mean_ic>=0.02; secondary net-of-50bps
    long-short ci_low>0; full PASS needs BOTH. 63d horizon, quarterly cohorts, static survivor
    universe (survivor-biased on purpose — see docs/runbooks/lazy-prices.md). Section text is
    cached under --cache-dir so the one-time SEC fetch survives restarts and the run is re-runnable.
    """
    import json
    from datetime import date

    from adapters.data.sec_cik_resolver import SECCikResolver
    from adapters.data.sec_filing_text_adapter import FilingRef, SECFilingTextAdapter
    from application import price_returns as pr
    from application.lazy_prices_backtest import LazyPricesBacktestUseCase
    from application.lazy_prices_runner import (
        build_forward_excess_return_fn,
        build_similarity_fn,
        build_universe_fn,
        quarterly_cohorts,
    )

    horizon_days = 63  # ADR-057 PRIMARY horizon — locked, not an option
    start_dt = datetime.fromisoformat(start)
    end_dt = datetime.fromisoformat(end)
    cohorts = quarterly_cohorts(start_dt, end_dt)

    cache_root = Path(cache_dir)
    sections_dir = cache_root / "sections"

    # --- adapters (composition root) ---
    cik = SECCikResolver(cache_path=cache_root / "company_tickers.json")
    filings = SECFilingTextAdapter()

    # Disk-cached section fetch — keyed by accession, so the long one-time fetch persists.
    def _fetch_sections_cached(ref: FilingRef) -> dict[str, str]:
        path = sections_dir / f"{ref.accession_nodash}.json"
        if path.exists():
            try:
                cached: dict[str, str] = json.loads(path.read_text())
                return cached
            except (ValueError, OSError):
                pass
        sections = filings.fetch_sections(ref)
        if sections:
            sections_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(sections))
        return sections

    # Price series cached per ticker over the full window (+ forward buffer).
    price_start = start_dt - timedelta(days=400)
    price_end = end_dt + timedelta(days=150)
    price_cache: dict[str, list[tuple[datetime, float]]] = {}

    def _series(ticker: str) -> list[tuple[datetime, float]]:
        if ticker not in price_cache:
            price_cache[ticker] = pr.load_price_series(ticker, price_start, price_end)
        return price_cache[ticker]

    # --- the three injected callables ---
    base_tickers = build_universe_fn([Path(f) for f in ticker_files])(start_dt)
    run_tickers = base_tickers[:limit] if limit > 0 else base_tickers
    if limit > 0:
        click.echo(f"[SMOKE] universe capped to {len(run_tickers)} — NOT a verdict run")

    def universe_fn(_cohort: datetime) -> list[str]:
        return run_tickers

    similarity_fn = build_similarity_fn(
        filings.list_filings, _fetch_sections_cached, cik.resolve
    )
    forward_fn = build_forward_excess_return_fn(_series, horizon_days)

    uc = LazyPricesBacktestUseCase(similarity_fn, forward_fn, universe_fn)
    click.echo(
        f"Lazy Prices run: {len(cohorts)} quarterly cohorts "
        f"({start}→{end}), universe={len(universe_fn(start_dt))}, horizon={horizon_days}d"
    )
    click.echo(
        "Fetching filings (cached) + prices — one-time fetch can take a while..."
    )
    result = uc.execute(cohorts, horizon_label=f"{horizon_days}d")

    as_of = date.today().isoformat()
    out_dir = Path(report_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"lazy_prices_ic_{horizon_days}d_{as_of}.json"
    report = {
        "as_of": as_of,
        "window": {"start": start, "end": end},
        "universe_size": len(universe_fn(start_dt)),
        "smoke_limit": limit,
        "adr": "057",
        **result,
    }
    out_file.write_text(json.dumps(report, indent=2, default=str))

    click.echo(f"\nLazy Prices ({as_of})  verdict={result['verdict']}")
    click.echo(
        f"  mean_ic={result['mean_ic']:+.4f}  n_cohorts={result['n_cohorts']}"
        f"  n_events={result['n_events']}  coverage={result['coverage']:.2%}"
    )
    boot = result.get("ic_bootstrap") or {}
    click.echo(f"  IC bootstrap CI=[{boot.get('ci_low')}, {boot.get('ci_high')}]")
    if limit > 0:
        click.echo(
            "  [SMOKE RUN — not a verdict; re-run with no --limit for the real gate]"
        )
    click.echo(f"Report -> {out_file}")


@cli.command("backtest-insider-clusters")
@click.option("--start-year", type=int, default=2006, show_default=True)
@click.option("--end-year", type=int, required=True)
@click.option(
    "--report-dir", type=click.Path(), default="data/reports", show_default=True
)
def backtest_insider_clusters(start_year: int, end_year: int, report_dir: str) -> None:
    """Pre-registered sub-$1B insider-cluster falsification (ADR-052, Unit B).

    Masked stdout: verdict + counts only. Full distribution -> tracked JSON report.
    """
    import json
    import time
    from datetime import date, timezone

    from loguru import logger

    from adapters.data.sec_form345_dataset_adapter import SECForm345DatasetAdapter
    from adapters.data.yfinance_adapter import YFinanceAdapter
    from application.insider_cluster_falsification_use_case import (
        InsiderClusterFalsificationUseCase,
    )

    quarters = [(y, q) for y in range(start_year, end_year + 1) for q in (1, 2, 3, 4)]
    port = SECForm345DatasetAdapter(cache_dir=Path("data/cache/sec_form345"))
    # use_cache=True so a re-run resumes from already-fetched tickers (resumable).
    yf = YFinanceAdapter(cache_dir=Path("data/cache/yfinance"), use_cache=True)

    # Fetch from a FIXED early date (before the 2006 data floor), NOT start_year-1.
    # The yfinance cache is keyed by symbol only and ignores the requested window
    # (review I3), so a per-run window would let an earlier short-window cache
    # entry shadow a later long-window need. A fixed full-history window makes every
    # cached series a valid superset for any run (smoke or full). prediction_time=now
    # keeps all historical bars past the point-in-time filter.
    now = datetime.now(timezone.utc)
    window_start = datetime(2005, 1, 1, tzinfo=timezone.utc)

    def prices(ticker: str) -> list[tuple[date, float, float]]:
        was_cached = yf.has_cache(ticker)
        signals = []
        delay = 2.0
        for attempt in range(5):
            try:
                signals = yf.get_signals(
                    ticker, now, start_date=window_start, end_date=now
                )
                break
            except Exception as exc:  # incl. yfinance rate-limit; degrade gracefully
                if attempt == 4:
                    logger.warning("yfinance gave up on {}: {}", ticker, exc)
                    return []
                time.sleep(delay)
                delay *= 2
        if not was_cached:
            time.sleep(0.4)  # polite throttle on fresh fetches to avoid rate limits
        return [(s.timestamp.date(), s.price, float(s.volume)) for s in signals]

    uc = InsiderClusterFalsificationUseCase(port=port, prices=prices, quarters=quarters)
    report = uc.run()

    out = Path(report_dir) / f"insider_cluster_falsification_{end_year}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str))

    click.echo(f"VERDICT: {report['verdict']}")
    click.echo(
        f"events={report['n_cluster_events']} "
        f"with_adv={report['n_records_with_adv']} "
        f"no_price={report['n_no_price']} "
        f"bottom_population={report['n_bottom_population']} "
        f"bottom_benchmarked={report['n_bottom_benchmarked']} "
        f"coverage={report['coverage']:.2%}"
    )
    click.echo(f"report -> {out}")


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
    # Import here to avoid circular at module load — these are registered by other modules
    from application.cli.data_commands import backfill_history
    from application.cli.scan_commands import resolve_calls, scan_opportunities

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
