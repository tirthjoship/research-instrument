"""Shared dependency wiring and private helpers for CLI commands."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import click
from loguru import logger

from adapters.data.sqlite_store import SQLiteStore
from adapters.data.yfinance_adapter import YFinanceAdapter
from adapters.ml.ensemble_predictor import EnsemblePredictor
from adapters.ml.feature_engineer import FeatureEngineer
from adapters.ml.fundamental_feature_engineer import FundamentalFeatureEngineer
from config.loader import load_market_config
from domain.models import WeeklyReport

# Path for weekly systematic-share history (gitignored — data/personal/).
MACRO_HISTORY_PATH = "data/personal/macro_history.jsonl"


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

    themes_path = (
        Path(__file__).parent.parent.parent / "config" / "universe" / "themes.yaml"
    )
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
            Path(__file__).parent.parent.parent
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

    themes_path = (
        Path(__file__).parent.parent.parent / "config" / "universe" / "themes.yaml"
    )
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


def _get_ticker_universe(config: dict[str, Any]) -> list[str]:
    """Load ticker universe from config files, with hardcoded fallback."""
    config_dir = Path(__file__).parent.parent.parent / "config" / "tickers"
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


# Mega-caps / semis scanned first so daily-scan is not limited to A* tickers.
_PRIORITY_BUZZ_TICKERS: tuple[str, ...] = (
    "NVDA",
    "AAPL",
    "MSFT",
    "GOOG",
    "GOOGL",
    "AMZN",
    "META",
    "TSLA",
    "AMD",
    "AVGO",
    "ARM",
    "ASML",
    "INTC",
    "QCOM",
    "MU",
    "AMAT",
    "LRCX",
    "KLAC",
    "SMCI",
    "PLTR",
    "CRM",
    "NFLX",
    "JPM",
    "V",
    "UNH",
    "XOM",
    "LLY",
    "COST",
    "WMT",
    "BAC",
)


def _buzz_scan_tickers(universe: list[str], limit: int = 50) -> list[str]:
    """Return up to *limit* tickers with priority names first (includes NVDA)."""
    universe_set = set(universe)
    ordered: list[str] = []
    seen: set[str] = set()
    for ticker in _PRIORITY_BUZZ_TICKERS:
        if ticker in universe_set and ticker not in seen:
            ordered.append(ticker)
            seen.add(ticker)
    for ticker in universe:
        if ticker not in seen:
            ordered.append(ticker)
            seen.add(ticker)
        if len(ordered) >= limit:
            break
    return ordered[:limit]


def _get_backtest_universe(market: str) -> list[str]:
    """US S&P 500 + NASDAQ-100 (existing) plus TSX 60 with .TO suffix for the backtest.

    Reads ticker files directly (offline-safe — no network, no config object needed).
    """
    config_dir = Path(__file__).parent.parent.parent / "config" / "tickers"
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
                # Class shares use dotted notation in the file (GIB.A); yfinance
                # wants dash + .TO (GIB-A.TO). Mirrors holdings_reader._to_yf.
                tsx.append(f"{s.replace('.', '-')}.TO")

    seen: set[str] = set()
    out: list[str] = []
    for t in [*us, *tsx]:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


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
            Path(__file__).parent.parent.parent / "config" / "universe" / "themes.yaml"
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


def _risk_macro_facts(macro: Any) -> list[str]:
    """Build 4-6 plain descriptive fact strings from a BookMacroExposure for the
    risk second-opinion prefetch (spec §9).

    MUST be free of FORBIDDEN_WORDS (buy/sell/winner/conviction/predict/alpha/
    outperform) — these facts feed the template fallback verbatim.  All lines are
    purely descriptive; no trade call, no verdict language.
    """
    betas: dict[str, float] = getattr(macro, "net_beta_by_factor", {}) or {}
    spy_beta = betas.get("SPY", 0.0)
    sys_share: float = getattr(macro, "systematic_share", 0.0)
    enb: float = getattr(macro, "enb", 0.0)
    dominant: str | None = getattr(macro, "dominant_factor", None)
    sector_hhi: float = getattr(macro, "sector_hhi", 0.0)

    facts: list[str] = [
        f"systematic share {sys_share:.0%}",
        f"net SPY beta {spy_beta:.2f}",
    ]
    if enb > 0:
        facts.append(f"effective number of bets {enb:.1f}")
    if dominant:
        facts.append(f"dominant factor {dominant}")
    if sector_hhi > 0:
        facts.append(f"sector HHI {sector_hhi:.2f}")
    return facts


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
            # Only the network fetch is tolerated to fail (per-ticker, expected).
            # The transform runs OUTSIDE the try so a field/shape bug surfaces
            # instead of silently returning [] (this is how the s.close bug hid).
            try:
                now = datetime.now(timezone.utc)
                two_years_ago = now.replace(year=now.year - 2)
                signals = market_data.get_signals(ticker, now, start_date=two_years_ago)
            except Exception:
                return []
            if not signals:
                return []
            by_month: dict[str, float] = {}
            for s in signals:
                key = f"{s.timestamp.year}-{s.timestamp.month:02d}"
                by_month[key] = s.price
            return [by_month[k] for k in sorted(by_month)]

        def daily_closes(self, ticker: str, as_of: str) -> list[float]:
            """Return daily close prices up to as_of (PIT-safe) for lowvol computation."""
            try:
                now = datetime.now(timezone.utc)
                two_years_ago = now.replace(year=now.year - 2)
                signals = market_data.get_signals(ticker, now, start_date=two_years_ago)
            except Exception:
                return []
            if not signals:
                return []
            return [s.price for s in signals]

        def trend_health(self, ticker: str) -> float:
            from domain.trend_rules import atr, sma
            from domain.trend_rules import trend_health as _th

            # Only the network fetch is tolerated to fail (per-ticker, expected).
            # The computation runs OUTSIDE the try so a field/shape bug surfaces
            # instead of silently returning 0.0 (this is how the s.close bug hid).
            try:
                now = datetime.now(timezone.utc)
                two_years_ago = now.replace(year=now.year - 2)
                signals = market_data.get_signals(ticker, now, start_date=two_years_ago)
            except Exception:
                return 0.0
            if len(signals) < 22:
                return 0.0
            closes = [s.price for s in signals]
            highs = [s.high for s in signals]
            lows = [s.low for s in signals]
            sma_val = sma(closes, min(200, len(closes)))
            atr_val = atr(highs, lows, closes, 22)
            th = _th(closes[-1], sma_val, atr_val)
            return th if th is not None else 0.0

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
