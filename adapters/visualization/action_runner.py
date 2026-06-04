"""Progress-tracked wrappers for running use cases from the dashboard.

Each function wraps a use case with stage-based progress reporting.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable

from domain.conviction import OpportunityCard
from domain.models import SellSignal


def run_monitor_holdings(
    db_path: str = "data/recommendations.db",
    market: str = "us",
    progress_callback: Callable[[float, str], None] | None = None,
) -> list[SellSignal]:
    """Check all holdings for sell signals with progress tracking.

    Stages: Load holdings (30%) → Check prices (60%) → Analyze (100%).
    """
    _update = progress_callback or (lambda p, m: None)

    from adapters.data.sqlite_store import SQLiteStore

    _update(0.1, "Loading holdings...")
    store = SQLiteStore(db_path)
    holdings = store.get_holdings()

    if not holdings:
        _update(1.0, "No holdings to check.")
        return []

    _update(0.3, f"Checking {len(holdings)} holdings...")

    from application.monitor_holdings import MonitorHoldingsUseCase

    def get_price_stub(symbol: str) -> float:
        """Stub price getter — returns purchase price (no live API in dashboard)."""
        for h in holdings:
            if h.symbol == symbol:
                return h.purchase_price
        return 0.0

    from config.loader import load_market_config

    config = load_market_config(market)
    risk_config = config.get("risk", {})
    stop_loss = risk_config.get("stop_loss_threshold", -0.08)

    _update(0.6, "Analyzing sell signals...")
    use_case = MonitorHoldingsUseCase(
        holdings=store,
        get_current_price=get_price_stub,
        stop_loss_threshold=stop_loss,
    )

    signals = use_case.execute(datetime.now())
    _update(1.0, f"Done — {len(signals)} signal(s) found.")
    return signals


def run_add_holding(
    symbol: str,
    quantity: float,
    price: float,
    notes: str = "",
    db_path: str = "data/recommendations.db",
) -> None:
    """Add a holding to the portfolio via SQLite."""
    from adapters.data.sqlite_store import SQLiteStore
    from domain.models import Holding

    store = SQLiteStore(db_path)
    holding = Holding(
        symbol=symbol.upper(),
        quantity=quantity,
        purchase_price=price,
        purchase_date=datetime.now().strftime("%Y-%m-%d"),
        notes=notes,
    )
    store.add_holding(holding)


def run_add_watchlist(
    symbol: str,
    notes: str = "",
    db_path: str = "data/recommendations.db",
) -> None:
    """Add a symbol to the watchlist."""
    from adapters.data.sqlite_store import SQLiteStore

    store = SQLiteStore(db_path)
    store.add_watchlist(symbol.upper(), notes=notes)


def run_full_cycle(
    db_path: str = "data/recommendations.db",
    market: str = "us",
    progress_callback: Callable[[float, str], None] | None = None,
) -> dict[str, str]:
    """Run the complete daily cycle: scan -> tournament -> track accuracy.

    Stages: Scan (0-40%) -> Tournament (40-80%) -> Track (80-100%).
    """
    _update = progress_callback or (lambda p, m: None)
    results: dict[str, str] = {}

    # Stage 1: Daily Scan
    _update(0.05, "Stage 1/3: Initializing daily scan...")

    from adapters.data.rss_adapter import RSSAdapter
    from adapters.data.sqlite_store import SQLiteStore
    from adapters.ml.keyword_scorer import KeywordScorer
    from application.daily_scan import DailyScanUseCase

    store = SQLiteStore(db_path)
    rss = RSSAdapter()
    keyword = KeywordScorer()

    scan_uc = DailyScanUseCase(
        discovery=rss,
        keyword_scorer=keyword,
        flan_t5_scorer=keyword,  # keyword-only (avoid torch segfault)
        store_signal=store.save_buzz_signal,
    )

    _update(0.10, "Stage 1/3: Scanning RSS feeds...")
    scan_result = scan_uc.execute(datetime.now())
    results["scan"] = (
        f"{scan_result['tickers_found']} tickers, "
        f"{scan_result['signals_stored']} signals"
    )

    # Google Trends
    _update(0.20, "Stage 1/3: Scanning Google Trends...")
    tickers: list[str] = []
    try:
        from adapters.data.google_trends_adapter import GoogleTrendsAdapter
        from config.loader import load_market_config

        config = load_market_config(market)
        tickers = config.get("tickers", [])
        if not tickers:
            ticker_path = Path("config/tickers")
            if ticker_path.exists():
                for f in ticker_path.glob("*.txt"):
                    tickers.extend(f.read_text().strip().split("\n"))
        gt = GoogleTrendsAdapter()
        gt_signals = gt.scan_sources(datetime.now(), tickers=tickers[:10])
        for sig in gt_signals:
            store.save_buzz_signal(sig)
        results["google_trends"] = f"{len(gt_signals)} signals"
    except Exception as e:
        results["google_trends"] = f"skipped ({e})"

    # StockTwits
    _update(0.30, "Stage 1/3: Scanning StockTwits...")
    try:
        from adapters.data.stocktwits_adapter import StockTwitsAdapter

        st_adapter = StockTwitsAdapter()
        st_signals = st_adapter.scan_sources(datetime.now(), tickers=tickers[:10])
        for sig in st_signals:
            store.save_buzz_signal(sig)
        results["stocktwits"] = f"{len(st_signals)} signals"
    except Exception as e:
        results["stocktwits"] = f"skipped ({e})"

    _update(0.40, "Stage 1/3: Scan complete.")

    # Stage 2: Tournament
    _update(0.45, "Stage 2/3: Running tournament...")
    try:
        run_tournament(db_path=db_path, market=market)
        results["tournament"] = "complete"
    except Exception as e:
        results["tournament"] = f"failed ({e})"

    _update(0.80, "Stage 2/3: Tournament complete.")

    # Stage 3: Track accuracy
    _update(0.85, "Stage 3/3: Tracking prediction accuracy...")
    try:
        from adapters.data.yfinance_adapter import YFinanceAdapter
        from application.use_cases import TrackRecommendationsUseCase

        adapter = YFinanceAdapter(cache_dir=Path("data/cache"))
        track_uc = TrackRecommendationsUseCase(
            market_data=adapter,
            store=store,
        )
        records = track_uc.execute(evaluation_date=datetime.now())
        results["tracking"] = f"{len(records)} records evaluated"
    except Exception as e:
        results["tracking"] = f"skipped ({e})"

    _update(1.0, "Full cycle complete.")
    return results


def run_tournament(
    db_path: str = "data/recommendations.db",
    market: str = "us",
    progress_callback: Callable[[float, str], None] | None = None,
) -> None:
    """Run weekly tournament to rank tickers and produce Top 15."""
    _update = progress_callback or (lambda p, m: None)

    _update(0.1, "Loading dependencies...")

    from application.cli import _build_dependencies, _get_ticker_universe

    deps = _build_dependencies(market)
    config = deps["config"]
    tickers = _get_ticker_universe(config)

    _update(0.3, f"Scoring {len(tickers)} tickers...")

    from application.use_cases import WeeklyTournamentUseCase

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

    _update(0.5, "Running tournament...")
    use_case.execute(prediction_date=datetime.now())
    _update(1.0, "Tournament complete.")


def run_conviction_scan(
    db_path: str = "data/recommendations.db",
    market: str = "us",
    progress_callback: Callable[[float, str], None] | None = None,
) -> list[OpportunityCard]:
    """Scan for conviction-ranked opportunities using smart money signals.

    Stages: Config (20%) → Tickers (40%) → Signals (60%) → Watchlist (70%) → Score (80-100%).
    Returns list[OpportunityCard].
    """
    _update = progress_callback or (lambda p, m: None)

    # 1. Load market config
    _update(0.20, "Loading market config...")
    from config.loader import load_market_config

    config = load_market_config(market)

    # 2. Load tickers from config files
    _update(0.40, "Loading ticker universe...")
    tickers: list[str] = config.get("tickers", [])
    if not tickers:
        from pathlib import Path

        ticker_path = Path("config/tickers")
        if ticker_path.exists():
            for f in ticker_path.glob("*.txt"):
                tickers.extend(
                    [t.strip() for t in f.read_text().strip().split("\n") if t.strip()]
                )

    # Limit for performance
    tickers = tickers[:50]

    # 3. Create SECEdgarAdapter and fetch signals
    _update(0.60, f"Fetching smart money signals for {len(tickers)} tickers...")
    from adapters.data.sec_edgar_adapter import SECEdgarAdapter

    edgar = SECEdgarAdapter()

    # 4. Load watchlist for pinned tickers
    _update(0.70, "Loading watchlist...")
    pinned: set[str] = set()
    try:
        from adapters.data.sqlite_store import SQLiteStore

        store = SQLiteStore(db_path)
        watchlist = store.get_watchlist()
        pinned = {w["symbol"] for w in watchlist}
    except Exception:
        pass

    # 5. Run conviction scoring
    _update(0.80, "Scoring conviction...")
    from application.conviction_use_case import ConvictionScoringUseCase
    from domain.conviction import ConvictionWeights

    weights = ConvictionWeights()
    use_case = ConvictionScoringUseCase(
        smart_money=edgar,
        tickers=tickers,
        weights=weights,
        pinned=pinned,
        top_n=15,
    )

    def _inner_progress(idx: int, total_: int) -> None:
        frac = 0.80 + 0.20 * (idx / max(total_, 1))
        _update(frac, f"Scoring {idx}/{total_} tickers...")

    cards = use_case.run(
        scan_time=datetime.now(),
        progress_callback=_inner_progress,
    )
    _update(1.0, f"Scan complete — {len(cards)} opportunities found.")
    return cards


def run_record_buy(
    ticker: str,
    price: float,
    quantity: int,
    trade_date: str,
    conviction: float = 0.0,
    signals: list[str] | None = None,
    db_path: str = "data/recommendations.db",
) -> None:
    """Record a BUY trade via OutcomeTrackingUseCase."""
    from adapters.data.sqlite_store import SQLiteStore
    from application.outcome_use_case import OutcomeTrackingUseCase

    store = SQLiteStore(db_path)
    uc = OutcomeTrackingUseCase(store=store)
    uc.record_buy(
        ticker=ticker,
        price=price,
        quantity=quantity,
        trade_date=trade_date,
        conviction=conviction,
        signals=signals or [],
    )


def run_record_sell(
    ticker: str,
    price: float,
    quantity: int,
    trade_date: str,
    db_path: str = "data/recommendations.db",
) -> None:
    """Record a SELL trade via OutcomeTrackingUseCase."""
    from adapters.data.sqlite_store import SQLiteStore
    from application.outcome_use_case import OutcomeTrackingUseCase

    store = SQLiteStore(db_path)
    uc = OutcomeTrackingUseCase(store=store)
    uc.record_sell(
        ticker=ticker,
        price=price,
        quantity=quantity,
        trade_date=trade_date,
    )


def run_backtest(
    market: str = "us",
    start: str = "2024-01",
    end: str = "2026-05",
    progress_callback: Callable[[float, str], None] | None = None,
) -> None:
    """Run full backtest with progress tracking."""
    _update = progress_callback or (lambda p, m: None)

    _update(0.1, "Loading dependencies...")
    from application.cli import _build_dependencies, _get_ticker_universe

    deps = _build_dependencies(market, use_cache=False)
    config = deps["config"]
    tickers = _get_ticker_universe(config)

    _update(0.2, f"Pretraining on {len(tickers)} tickers ({start} to {end})...")

    from application.use_cases import PretrainingUseCase

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

    _update(0.8, "Generating evaluation report...")
    from application.backtest_runner import run_backtest_report

    run_backtest_report()
    _update(1.0, "Backtest complete.")
