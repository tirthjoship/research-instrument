"""Screen-related CLI commands: screen-candidates, backtest-screen."""

from __future__ import annotations

import os
import sqlite3
from datetime import date as _date
from datetime import datetime, timedelta
from pathlib import Path

import click

from adapters.data.corroboration_store import CorroborationStore
from adapters.visualization.price_cache import _fetch_recent_news_impl
from application.card_loading import select_case_summarizer
from application.screener_case_facts import candidate_bands, facts_from_bands
from application.screener_sentiment_facts import buzz_sentiment_fact
from domain.corroboration_models import ConvergenceTier as _CT
from domain.screened_row import CorroborationSnapshot, ScreenedRow
from domain.screener_composite_service import ScreenerCompositeService

from ._cli_group import cli
from ._deps import (
    _build_dependencies,
    _build_evidence_screen,
    _get_backtest_universe,
    _get_ticker_universe,
)


def _prefetch_screener_cited_cases(
    screened_rows: "tuple[ScreenedRow, ...]",
    top: int,
    report_dir: str,
    as_of: str,
    db_path: str,
) -> str:
    """Prefetch Gemini green/red-flag reads for the top-N shown candidates.

    Mirrors weekly-brief's `_prefetch_cited_cases` (batched via
    run_cases_in_batches — one Gemini call per chunk of up to 15 tickers,
    not one per ticker; progress still echoed per ticker) but feeds real
    per-ticker news + market-sentiment facts, not just factor-band facts.
    Writes <report_dir>/screen_cited_cases.json. Returns the cache file path.
    """
    from application.case_batch import run_cases_in_batches
    from application.case_cache import write_case_cache
    from domain.case_models import CaseContext

    shown = list(screened_rows[:top])
    contexts: list[CaseContext] = []
    tickers: list[str] = []
    for row in shown:
        cand = row.candidate
        cand_dict = {
            "ticker": cand.ticker,
            "factor_scores": [
                {"name": fs.name, "value": fs.value, "percentile": fs.percentile}
                for fs in cand.factor_scores
            ],
        }
        factor_by_name = {
            fs.name: {"percentile": fs.percentile} for fs in cand.factor_scores
        }
        bands = candidate_bands(cand_dict)
        facts = facts_from_bands(bands, factor_by_name)
        buzz_fact = buzz_sentiment_fact(cand.ticker, db_path)
        if buzz_fact:
            facts = {**facts, "Market sentiment": buzz_fact}
        news_items = _fetch_recent_news_impl(cand.ticker, limit=5)
        news_pairs = tuple(
            (n.get("source", "news"), n["title"]) for n in news_items if n.get("title")
        )
        facts_tuple = tuple(f"{k}: {v}" for k, v in facts.items() if v)
        contexts.append(
            CaseContext(ticker=cand.ticker, facts=facts_tuple, news=news_pairs)
        )
        tickers.append(cand.ticker)

    if not contexts:
        return ""

    click.echo(f"\ncite-cases: prefetching {len(contexts)} candidate(s)…")
    summarizer = select_case_summarizer()

    def _progress(fraction: float, i: int, total: int) -> None:
        click.echo(f"  Analysing {i}/{total}: {tickers[i - 1]} ({fraction:.0%})")

    results = run_cases_in_batches(contexts, summarizer, progress=_progress)  # type: ignore[arg-type]
    cases = dict(zip(tickers, results))
    cache_path = os.path.join(report_dir, "screen_cited_cases.json")
    write_case_cache(cache_path, as_of, cases)
    click.echo(f"cite-cases: cache written → {cache_path}")
    return cache_path


@cli.command("screen-candidates")
@click.option(
    "--market", default="us", show_default=True, help="Market config (us|ca|in)"
)
@click.option("--top", default=10, show_default=True, type=int, help="Top N rank limit")
@click.option(
    "--report-dir",
    default="data/reports/",
    show_default=True,
    help="Directory to write screen_<date>.json",
)
@click.option(
    "--cite-cases/--no-cite-cases",
    default=False,
    show_default=True,
    help="Also prefetch Gemini green/red-flag reads for the top-N shown candidates.",
)
def screen_candidates(market: str, top: int, report_dir: str, cite_cases: bool) -> None:
    """Screen universe for disciplined, evidence-bounded candidates.

    Writes the FULL ranked candidate distribution to <report-dir>/screen_<date>.json
    (honesty rule: full distribution, not just top-N).  Prints a masked summary to
    stdout (counts + label distribution only — no per-ticker scores).
    """
    import json
    from datetime import date, timezone

    from application.evidence_screen_use_case import label_from_verdict_file

    deps = _build_dependencies(market)
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
    # Use replace() so ALL fields (incl. diagnostics) carry through — a full
    # reconstruction silently dropped `diagnostics`, writing `diagnostics: null`
    # and starving the Screener funnel / Home tile of their rich states.
    result = replace(result, candidates=labeled_candidates)

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
    # Serialize diagnostics if available (4 raw ints — no fabrication).
    diagnostics_payload: dict[str, int] | None = None
    if result.diagnostics is not None:
        d = result.diagnostics
        diagnostics_payload = {
            "scanned": d.scanned,
            "had_history": d.had_history,
            "above_trend": d.above_trend,
            "cleared": d.cleared,
        }

    payload: dict[str, object] = {
        "as_of": as_of,
        "market": market,
        "universe_size": result.universe_size,
        "top_n": top,
        "regime": result.regime,
        "abstained": result.abstained,
        "diagnostics": diagnostics_payload,
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

    # --- SP3: blend with corroboration snapshots ---
    db_path = os.path.join(report_dir, "..", "recommendations.db")
    corroboration_run_date: _date | None = None
    snapshots: list[CorroborationSnapshot] = []
    try:
        conn = sqlite3.connect(db_path)
        corr_store = CorroborationStore(conn)
        corr_store.init_schema()
        as_of_date = _date.fromisoformat(as_of)
        snapshots = corr_store.get_snapshots(as_of_date, window_days=7)
        if snapshots:
            corroboration_run_date = snapshots[0].surfaced_at
        conn.close()
    except Exception as e:
        click.echo(f"  WARNING: corroboration unavailable — {e}", err=True)

    svc = ScreenerCompositeService()
    screened_rows = svc.compose(result, snapshots, _date.fromisoformat(as_of))
    screened_path = _write_screened_json(
        screened_rows, as_of, corroboration_run_date, report_dir
    )

    n_corroborated = sum(1 for r in screened_rows if not r.factor_only)
    if n_corroborated > 0:
        strong = sum(
            1
            for r in screened_rows
            if r.corroboration and r.corroboration.convergence_tier == _CT.STRONG
        )
        moderate = sum(
            1
            for r in screened_rows
            if r.corroboration and r.corroboration.convergence_tier == _CT.MODERATE
        )
        weak = sum(
            1
            for r in screened_rows
            if r.corroboration and r.corroboration.convergence_tier == _CT.WEAK
        )
        click.echo(
            f"  corroboration: {n_corroborated}/{len(screened_rows)} tickers "
            f"· {strong} STRONG  {moderate} MODERATE  {weak} WEAK"
        )
    else:
        click.echo("  corroboration: no data this week — showing factor signals only")

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
    click.echo(f"Blended screened rows written to: {screened_path}")

    # --- optional: prefetch Gemini green/red-flag reads (off the live UI path) ---
    if cite_cases:
        _prefetch_screener_cited_cases(screened_rows, top, report_dir, as_of, db_path)


def _write_screened_json(
    rows: tuple[ScreenedRow, ...],
    as_of: str,
    corroboration_run_date: _date | None,
    report_dir: str,
) -> str:
    """Persist screened_<date>.json sidecar with blended rows. Returns file path."""
    import json

    # Factor percentiles from original composite scores — independent of blended rerank
    _sorted_by_factor = sorted(rows, key=lambda r: r.candidate.composite)
    _n = len(_sorted_by_factor)
    _factor_pct: dict[str, float] = {
        r.candidate.ticker: i / max(_n - 1, 1) for i, r in enumerate(_sorted_by_factor)
    }

    def _row_to_dict(r: ScreenedRow) -> dict[str, object]:
        corr = r.corroboration
        return {
            "ticker": r.candidate.ticker,
            "composite": r.candidate.composite,
            "factor_percentile": round(_factor_pct[r.candidate.ticker], 4),
            "blended_percentile": round(r.blended_percentile, 4),
            "factor_only": r.factor_only,
            "convergence_tier": corr.convergence_tier.value if corr else None,
            "n_sources": corr.n_sources if corr else 0,
            "corroboration_date": corr.surfaced_at.isoformat() if corr else None,
            "why": r.candidate.why,
            "label": r.candidate.label.value,
            "factor_scores": [
                {
                    "name": fs.name,
                    "value": round(fs.value, 4),
                    "percentile": round(fs.percentile, 4),
                }
                for fs in r.candidate.factor_scores
            ],
        }

    payload: dict[str, object] = {
        "as_of": as_of,
        "corroboration_run_date": (
            corroboration_run_date.isoformat() if corroboration_run_date else None
        ),
        "rows": [_row_to_dict(r) for r in rows],
    }
    os.makedirs(report_dir, exist_ok=True)
    path = os.path.join(report_dir, f"screened_{as_of}.json")
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    return path


@cli.command("backtest-screen")
@click.option(
    "--market", default="us", show_default=True, help="Market config (us|ca|in)"
)
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
    # Build universe for the selected market only (us|ca|in) — markets are
    # no longer combined; each `market` selects its own single-country
    # ticker list via _get_backtest_universe.
    # ------------------------------------------------------------------
    tickers = _get_backtest_universe(market)
    universe_size = len(tickers)
    if limit:
        tickers = tickers[:limit]
        universe_size = len(tickers)

    _UNIVERSE_LABELS = {"us": "sp500+nasdaq100", "ca": "tsx60", "in": "nifty50"}
    universe_label = _UNIVERSE_LABELS.get(market, market)
    click.echo(f"Universe: {universe_size} tickers ({universe_label}, deduped)")

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
            from application.price_returns import load_price_series

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
