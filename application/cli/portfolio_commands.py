"""Portfolio-related CLI commands: portfolio-verdict, holdings-risk, add-holding, etc."""

from __future__ import annotations

from datetime import datetime

import click

from application.holdings_risk import HoldingsRiskAssessmentUseCase
from application.portfolio_verdict import PortfolioVerdictUseCase
from application.price_returns import load_price_series

from ._cli_group import cli
from ._deps import _build_dependencies


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
    from datetime import timezone

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
@click.option(
    "--prune-list",
    default="data/personal/delisted.json",
    show_default=True,
    help="Gitignored consecutive-no-data counter; >=3 weeks => skip as delisted",
)
def holdings_risk(
    holdings: str, out: str, log: str, narrate: bool, prune_list: str
) -> None:
    """Graded risk/discipline assessment of your holdings (decision-support, not prediction).
    Masked stdout (verdict distribution only); full detail to the gitignored --out file.
    """
    import os
    from datetime import timezone

    from application import price_returns as _pr
    from application.delisted import is_delisted, load_prune_list, record_fetch_outcome
    from application.discipline_log import append_assessments
    from application.fetch_health import FetchHealth
    from application.holdings_reader import read_holdings
    from application.narrator import FakeNarrator
    from domain.exceptions import PriceFetchError
    from domain.ports import NarratorPort

    rows = read_holdings(holdings)
    if not rows:
        click.echo(
            f"No holdings at {holdings} (ticker/Symbol + Quantity). It is gitignored."
        )
        return
    start_dt = datetime(2018, 1, 1, tzinfo=timezone.utc)
    end_dt = datetime.now(timezone.utc)

    health = FetchHealth()
    prune_state = load_prune_list(prune_list)
    _cache: dict[str, list[tuple[datetime, float]]] = {}

    def provider(ticker: str) -> list[tuple[datetime, float]]:
        nonlocal prune_state
        if ticker in _cache:
            return _cache[ticker]
        if is_delisted(prune_state, ticker):
            health.record_pruned(ticker)
            _cache[ticker] = []
            return []
        try:
            series = _pr.load_price_series(ticker, start_dt, end_dt, strict=True)
        except PriceFetchError:
            health.record_failed(ticker)
            _cache[ticker] = []
            return []
        if series:
            health.record_ok(ticker)
        else:
            health.record_no_data(ticker)
        prune_state = record_fetch_outcome(prune_state, ticker, had_data=bool(series))
        _cache[ticker] = series
        return series

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
                "quantity": p.quantity,
                "market_value_cad": p.market_value_cad,
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
    from application.delisted import save_prune_list as _spl

    _spl(prune_list, prune_state)
    click.echo(health.summary_line())
    if health.any_failed():
        click.echo(f"  FETCH FAILURES: {', '.join(health.failed_tickers)}")
        raise SystemExit(1)  # loud: cron under `set -euo pipefail` fails the job


@cli.command("holdings-risk-calibrate")
@click.option(
    "--ticker", required=True, help="Symbol to compute history base rates for"
)
@click.option("--horizon", default=21, type=int, show_default=True)
def holdings_risk_calibrate(ticker: str, horizon: int) -> None:
    """Warm-start base rates from price history: what followed each trend state."""
    from datetime import timezone

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
