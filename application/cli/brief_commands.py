"""Weekly-brief CLI commands: weekly-brief, _build_weekly_brief, _prefetch_cited_cases."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import click
from loguru import logger

from application.holdings_risk import HoldingsRiskAssessmentUseCase
from application.price_returns import load_price_series

from ._cli_group import cli
from ._deps import (
    MACRO_HISTORY_PATH,
    _build_dependencies,
    _build_evidence_screen,
    _get_backtest_universe,
    _risk_macro_facts,
)


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

    from application.evidence_screen_use_case import label_from_verdict_file

    uc = WeeklyBriefUseCase(
        screen=screen,
        holdings_risk=holdings_risk,
        regime_reader=regime_reader,
        screen_label_fn=label_from_verdict_file,
        cluster_peers_fn=_cluster_peers,
        screen_scorecard_fn=_screen_scorecard,
        discipline_scorecard_fn=_discipline_scorecard,
        macro_fn=_macro_fn,
    )
    return uc, universe


def _prefetch_cited_cases(brief: "Any", as_of: datetime) -> None:
    """Prefetch cited-case summaries for all holding tickers; write the weekly cache.

    Strategy (minimal-from-brief):
      - We already have brief.holdings with ticker + why + verdict text.
      - Building a CaseContext from those facts avoids adding heavy per-ticker
        yfinance/news fetches to the weekly-brief run (bounded, predictable).
      - News is left empty ([]); the summarizer uses the factual why lines only.
      - This is an intentional design choice: the weekly-brief CLI should stay
        fast for most runs (default --no-cite-cases); a future enhancement could
        add per-ticker news by piping through build_news_context.

    Throttle: the summarizer returned by select_case_summarizer() is already a
    RateLimitedCaseSummarizer when GEMINI_API_KEY is set, so run_cases_with_progress
    drives the pings (one per holding) at the configured interval (default 5 s).
    GEMINI_MIN_INTERVAL_S=0 in tests collapses the wait to zero.
    """
    from application.card_loading import select_case_summarizer
    from application.case_batch import run_cases_with_progress
    from application.case_cache import CITED_CASES_PATH, write_case_cache
    from domain.case_models import CaseContext

    holding_lines = list(brief.holdings)
    if not holding_lines:
        click.echo("cite-cases: no holdings — nothing to prefetch.")
        return

    n = len(holding_lines)
    click.echo(f"\ncite-cases: prefetching {n} holding(s)…")

    # Build minimal CaseContext for each holding from the brief's why text + verdict.
    contexts: list[CaseContext] = []
    tickers: list[str] = []
    for h in holding_lines:
        fact = f"Verdict: {h.verdict.value}. {h.why}"
        trend_fact = f"Trend: {h.trend_state}"
        ctx = CaseContext(ticker=h.ticker, facts=(fact, trend_fact), news=())
        contexts.append(ctx)
        tickers.append(h.ticker)

    summarizer = select_case_summarizer()

    def _progress(fraction: float, i: int, total: int) -> None:
        click.echo(f"  Analysing {i}/{total}: {tickers[i - 1]} ({fraction:.0%})")

    results = run_cases_with_progress(contexts, summarizer, progress=_progress)  # type: ignore[arg-type]

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
def weekly_brief(
    market: str, holdings: str, out: str, report_dir: str, top_n: int, cite_cases: bool
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
    uc, universe = _build_weekly_brief(market, held, report_dir)
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
        from application.risk_second_opinion import build_risk_second_opinion

        build_risk_second_opinion(_risk_macro_facts(brief.macro), summarizer=None)

    click.echo(to_stdout_masked(brief))
    click.echo(f"\nFull brief (gitignored) written to: {out_path}")
    click.echo(f"Structured summary written to: {summary_path}")

    # Opt-in cited-case prefetch: spaced batch → cache.
    # Gated on --cite-cases flag (default off) so CI / screen-candidates never sleep.
    if cite_cases:
        _prefetch_cited_cases(brief, as_of)
