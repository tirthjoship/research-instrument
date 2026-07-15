"""Weekly-brief CLI commands: weekly-brief, _build_weekly_brief, _prefetch_cited_cases."""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from typing import Any, Callable

import click
from loguru import logger

from application.holdings_risk import HoldingsRiskAssessmentUseCase
from application.price_returns import load_price_series
from application.snapshot_screen import SnapshotScreenReader

from ._cli_group import cli
from ._deps import (
    MACRO_HISTORY_PATH,
    _build_dependencies,
    _get_backtest_universe,
    _risk_macro_facts,
)

#: seconds between tickers when fetching correlation-graph signals below.
#: Without pacing, this loop fires up to ~100 unpaced live yfinance history
#: fetches (held_tickers + universe[:100]) — exactly the burst shape that
#: trips Cloud's shared-IP rate limit and hangs "Run brief"/CSV-upload
#: rebuilds for many minutes. Mirrors weekly_brief.py's
#: _CASE_FETCH_PACE_S for the Home tab's needs-review fetcher.
_CORR_FETCH_PACE_S = 0.6


def _fetch_correlation_signals(
    market_data: Any,
    tickers: "list[str]",
    as_of: datetime,
    sleep: Callable[[float], None] = time.sleep,
    progress_path: str | None = None,
) -> "dict[str, list[Any]]":
    """Fetch get_signals() per ticker for the concentration/correlation graph,
    paced to avoid a Cloud rate-limit burst. Any per-ticker failure degrades
    to an empty signal list — never raises, never blocks the rest of the
    brief on one bad ticker.

    ``progress_path``: when given, writes a small JSON status snapshot after
    every ticker (completed/total/succeeded/failed/failed_tickers/last_ticker).
    This CLI runs as a subprocess from the Streamlit dashboard
    (holdings_syncer.py::rebuild_weekly_brief_cached), so a file is the only
    channel back to the parent process for real per-ticker progress — lets
    the UI show "12/45 (2 failed)" instead of only elapsed wall-clock time.
    """
    signals_by_ticker: dict[str, list[Any]] = {}
    succeeded = 0
    failed_tickers: list[str] = []
    total = len(tickers)
    for i, t in enumerate(tickers):
        try:
            signals_by_ticker[t] = market_data.get_signals(t, as_of)
            succeeded += 1
        except Exception:
            signals_by_ticker[t] = []
            failed_tickers.append(t)
        if progress_path is not None:
            with open(progress_path, "w") as f:
                json.dump(
                    {
                        "completed": i + 1,
                        "total": total,
                        "succeeded": succeeded,
                        "failed": len(failed_tickers),
                        "failed_tickers": failed_tickers,
                        "last_ticker": t,
                    },
                    f,
                )
        sleep(_CORR_FETCH_PACE_S)
    return signals_by_ticker


def _build_weekly_brief(
    market: str,
    holdings: "list[Any]",
    report_dir: str,
    use_cache: bool = True,
    progress_path: str | None = None,
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

    deps = _build_dependencies(market, use_cache=use_cache)
    store = deps["store"]
    market_data = deps["market_data"]
    universe = _get_backtest_universe(market)

    # Read the published screen_<date>.json snapshot (written by the scheduled
    # GitHub Actions job) instead of running a live ~512-ticker scan inline on
    # every "Run brief" click — that inline scan was the actual source of the
    # sustained yfinance rate-limiting seen on the Cloud deploy.
    screen = SnapshotScreenReader(report_dir)

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
    signals_by_ticker = _fetch_correlation_signals(
        market_data,
        graph_tickers,
        datetime.now(timezone.utc),
        progress_path=progress_path,
    )
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

    from adapters.data.sector_provider import SectorProvider
    from adapters.ml.macro_beta_analyzer import RidgeMacroBetaEstimator
    from adapters.ml.risk_stats_analyzer import RiskStatsAnalyzer
    from application.macro_beta_use_case import MacroBetaUseCase

    macro_cfg = deps.get("config", {}).get("macro_beta", {})
    risk_stats_cfg = deps.get("config", {}).get("risk_stats", {})

    # Factor returns come from two sources: ETF tickers via yfinance, and the
    # Fama-French long-short style factors (SMB/HML/MOM/RMW/CMA) via the FF data
    # library (ADR-060). Route by factor name so both slot into one provider.
    from adapters.data.fama_french_provider import FF_FACTORS, FamaFrenchProvider

    _ff_provider = FamaFrenchProvider()

    def _macro_price_provider(
        name: str, start: datetime, end: datetime
    ) -> list[tuple[datetime, float]]:
        if name in FF_FACTORS:
            return _ff_provider.series(name, start, end)
        return load_price_series(name, start, end)

    macro_uc = MacroBetaUseCase(
        price_provider=_macro_price_provider,
        estimator=RidgeMacroBetaEstimator(alpha=macro_cfg.get("ridge_alpha", 0.2)),
        factors=macro_cfg.get("factors", ["SPY", "TLT", "UUP", "XLE"]),
        alpha=macro_cfg.get("ridge_alpha", 0.2),
        headline_window=macro_cfg.get("headline_window_days", 252),
        # FF factors lag ~6wks (publication); widen lookback so the truncated
        # FF window still clears the 252-pt headline requirement (ADR-060).
        history_days=macro_cfg.get("history_days", 500),
        drift_window=macro_cfg.get("drift_window_days", 63),
        thresholds={
            "systematic_share_threshold": macro_cfg.get(
                "systematic_share_threshold", 0.60
            ),
            "factor_dominance_threshold": macro_cfg.get(
                "factor_dominance_threshold", 0.25
            ),
            "drift_threshold": macro_cfg.get("drift_threshold", 0.50),
        },
        risk_analyzer=RiskStatsAnalyzer(
            seed=int(risk_stats_cfg.get("seed", 7)),
            bootstrap_iters=int(risk_stats_cfg.get("bootstrap_iters", 500)),
        ),
        sector_provider=SectorProvider(),
        history_path=MACRO_HISTORY_PATH,
    )

    def _macro_fn(hlds: "list[Any]", as_of: datetime) -> "Any":
        try:
            return macro_uc.execute(hlds, as_of)
        except Exception:
            logger.warning("macro-beta scrubber failed — brief renders without it")
            return None

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

    import sqlite3

    from adapters.data.corroboration_store import CorroborationStore
    from application.evidence_screen_use_case import label_from_verdict_file

    _corr_store = CorroborationStore(sqlite3.connect("data/recommendations.db"))

    uc = WeeklyBriefUseCase(
        screen=screen,
        holdings_risk=holdings_risk,
        regime_reader=regime_reader,
        screen_label_fn=label_from_verdict_file,
        cluster_peers_fn=_cluster_peers,
        screen_scorecard_fn=_screen_scorecard,
        discipline_scorecard_fn=_discipline_scorecard,
        macro_fn=_macro_fn,
        corroboration_fn=_corr_store.get_snapshots,
        sector_provider=SectorProvider(),
    )
    return uc, universe


def _prefetch_cited_cases(brief: "Any", as_of: datetime) -> None:
    """Prefetch cited-case summaries for all holding tickers; write the weekly cache.

    Facts are built identically to the live dashboard path (card.signals via
    fetch_card + verdict/why + real news + real buzz sentiment, all through
    application.personal_case_facts) so a cache hit and a live fallback never
    disagree on what a case was built from. This adds a fetch_card() call
    (yfinance price/earnings/analyst) plus news+buzz fetches per holding — real
    cost, accepted because holdings count is bounded (a personal portfolio) and
    these calls aren't rate-limited like Gemini.

    Throttle: the summarizer returned by select_case_summarizer() is already a
    RateLimitedCaseSummarizer when GEMINI_API_KEY is set. run_cases_in_batches
    chunks holdings into groups of up to 15 and makes one Gemini call per
    chunk (not one call per holding) — the throttle still spaces one call
    per chunk at the configured interval (default 5 s).
    GEMINI_MIN_INTERVAL_S=0 in tests collapses the wait to zero.
    """
    from adapters.visualization.card_fetch import fetch_card
    from application.card_loading import select_case_summarizer
    from application.case_batch import run_cases_in_batches
    from application.case_builder import build_case_context
    from application.case_cache import CITED_CASES_PATH, write_case_cache
    from application.personal_case_facts import (
        personal_case_extra_facts,
        personal_case_news,
    )
    from domain.case_models import CaseContext
    from domain.evidence_rag import RagColor

    holding_lines = list(brief.holdings)
    if not holding_lines:
        click.echo("cite-cases: no holdings — nothing to prefetch.")
        return

    n = len(holding_lines)
    click.echo(f"\ncite-cases: prefetching {n} holding(s)…")

    # Build the same fact set the live dashboard path builds: card.signals +
    # verdict/why + real news + real buzz sentiment.
    contexts: list[CaseContext] = []
    tickers: list[str] = []
    for h in holding_lines:
        card = fetch_card(h.ticker)
        sigs = tuple(s for s in card.signals if s.color is not RagColor.GAP)
        news = personal_case_news(h.ticker)
        extra_facts = personal_case_extra_facts(
            h.ticker, verdict=h.verdict.value, why=h.why
        )
        ctx = build_case_context(h.ticker, sigs, news)
        ctx = CaseContext(
            ticker=ctx.ticker, facts=ctx.facts + extra_facts, news=ctx.news
        )
        contexts.append(ctx)
        tickers.append(h.ticker)

    summarizer = select_case_summarizer()

    def _progress(fraction: float, i: int, total: int) -> None:
        click.echo(f"  Analysing {i}/{total}: {tickers[i - 1]} ({fraction:.0%})")

    results = run_cases_in_batches(contexts, summarizer, progress=_progress)  # type: ignore[arg-type]

    cases = {ticker: result for ticker, result in zip(tickers, results)}
    as_of_iso = as_of.date().isoformat()
    write_case_cache(CITED_CASES_PATH, as_of_iso, cases)
    click.echo(f"cite-cases: cache written → {CITED_CASES_PATH}")


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
@click.option(
    "--cite-cases/--no-cite-cases",
    default=False,
    show_default=True,
    help=(
        "Prefetch Gemini cited cases for all holding tickers (spaced, cached for the week). "
        "Default OFF so normal runs / CI never sleep or ping Gemini. "
        "Enable only when GEMINI_API_KEY is set and you want to refresh the weekly cache."
    ),
)
@click.option(
    "--use-cache/--no-use-cache",
    default=True,
    show_default=True,
    help="Use local cached yfinance responses",
)
@click.option(
    "--progress-path",
    default=None,
    help=(
        "Internal — write correlation-graph fetch progress (JSON) to this path. "
        "Used by the dashboard's background rebuild to show real ticker "
        "fetch progress; not needed for interactive CLI use."
    ),
)
def weekly_brief(
    market: str,
    holdings: str,
    out: str,
    report_dir: str,
    top_n: int,
    cite_cases: bool,
    use_cache: bool,
    progress_path: str | None,
) -> None:
    """Generate the unified weekly brief (masked stdout + gitignored full markdown).

    Composes the Phase-A evidence screen, the discipline engine, a regime tilt,
    a concentration warning, and the forward scorecard. Phase B adds no predictive
    claim; a RESEARCH_ONLY screen renders no 'buy' language.

    Pass --cite-cases to also prefetch Gemini cited-case summaries for each holding
    (spaced at the configured rate limit) and cache them to data/personal/cited_cases.json
    so the dashboard avoids live pings all week.  Default is --no-cite-cases so that CI
    and regular runs are instant and never touch the network.
    """
    from pathlib import Path

    from application.holdings_reader import read_holdings
    from domain.brief import to_markdown, to_stdout_masked

    held = read_holdings(holdings)
    uc, universe = _build_weekly_brief(
        market, held, report_dir, use_cache=use_cache, progress_path=progress_path
    )
    as_of = datetime.now()
    brief = uc.execute(
        universe=universe,
        holdings=held,
        as_of=as_of,
        report_dir=report_dir,
        top_n=top_n,
    )

    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(to_markdown(brief))

    import json

    from application.brief_summary import brief_to_summary_dict
    from application.macro_history_store import append_systematic_share

    summary_path = out_path.with_name("brief_summary.json")
    summary_path.write_text(json.dumps(brief_to_summary_dict(brief), indent=2))

    # Persist weekly systematic-share to drift history (gitignored data/personal/).
    if brief.macro is not None:
        append_systematic_share(
            MACRO_HISTORY_PATH, brief.macro.as_of, brief.macro.systematic_share
        )

        # Prefetch Google-AI risk second-opinion into cache (spec §9 — cache-first, no
        # live calls at render time).  Fail-safe: build_risk_second_opinion swallows all
        # errors and never raises, so weekly-brief never crashes on this.
        from application.risk_market_facts import (
            dominant_sector,
            risk_market_news,
            risk_regime_fact,
        )
        from application.risk_second_opinion import build_risk_second_opinion

        risk_facts = _risk_macro_facts(brief.macro)
        risk_facts.append(risk_regime_fact(brief.regime))
        risk_news = risk_market_news(dominant_sector(brief.macro.sector_weights))
        build_risk_second_opinion(risk_facts, summarizer=None, news=risk_news)

    click.echo(to_stdout_masked(brief))
    click.echo(f"\nFull brief (gitignored) written to: {out_path}")
    click.echo(f"Structured summary written to: {summary_path}")

    # Opt-in cited-case prefetch: spaced batch → cache.
    # Gated on --cite-cases flag (default off) so CI / screen-candidates never sleep.
    if cite_cases:
        _prefetch_cited_cases(brief, as_of)
