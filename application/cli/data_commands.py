"""Data-related CLI commands: resolve-wiki-articles, drip-backfill, backfill-history, add-watchlist, list-watchlist, remove-watchlist."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import click

from adapters.data.wikipedia_article_resolver import WikipediaArticleResolver
from application.backfill_use_case import BackfillHistoryUseCase
from application.drip_backfill_use_case import DripBackfillUseCase
from domain.exceptions import SourceThrottledError

from ._cli_group import cli
from ._deps import (
    _build_dependencies,
    _get_company_name,
    _get_ticker_universe,
    _load_spine_tickers,
    _load_wiki_map,
)


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
    from loguru import logger

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
            Path(__file__).parent.parent.parent
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
        from loguru import logger as _log

        _log.warning("resolve-wiki-articles: final write failed: {}", exc)

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
