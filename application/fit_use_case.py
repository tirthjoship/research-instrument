"""Gather fit-verdict inputs from existing artifacts + machinery.

Reads (all best-effort; absence becomes a DATA_GAP flag, never an exception):
- latest screen_<date>.json   — full ranked distribution (Saturday job)
- brief_summary.json          — book macro block (weekly-brief CLI)
- holdings CSV                — cost-basis position values
- beta_fn                     — injected single-ticker SPY beta estimator
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from loguru import logger

from application.holdings_reader import read_holdings
from domain.fit import FitVerdict, assess_fit

BetaFn = Callable[[str, datetime], "float | None"]


def _load_latest_screen(reports_dir: str) -> dict[str, Any] | None:
    candidates = sorted(
        f
        for f in Path(reports_dir).glob("screen_*.json")
        if not f.name.startswith("screen_ic_")
    )
    if not candidates:
        return None
    try:
        return json.loads(candidates[-1].read_text())  # type: ignore[no-any-return]
    except (json.JSONDecodeError, OSError):
        return None


def _load_macro(summary_path: str) -> dict[str, Any] | None:
    p = Path(summary_path)
    if not p.exists():
        return None
    try:
        macro = json.loads(p.read_text()).get("macro")
        return macro if isinstance(macro, dict) else None
    except (json.JSONDecodeError, OSError):
        return None


def gather_and_assess(
    ticker: str,
    reports_dir: str,
    summary_path: str,
    holdings_path: str,
    beta_fn: BetaFn,
    as_of: datetime,
    systematic_share_threshold: float,
    hypothetical_weight: float = 0.02,
) -> FitVerdict:
    screen = _load_latest_screen(reports_dir)
    ticker_composite: float | None = None
    trend_state: str | None = None
    universe_composites: list[float] = []
    if screen:
        for c in screen.get("candidates", []):
            comp = c.get("composite")
            if isinstance(comp, (int, float)):
                universe_composites.append(float(comp))
                if c.get("ticker") == ticker:
                    ticker_composite = float(comp)
                    th = c.get("trend_health")
                    if isinstance(th, (int, float)):
                        trend_state = "intact" if th >= 0.5 else "broken"

    macro = _load_macro(summary_path)
    book_net_spy_beta: float | None = None
    book_systematic_share: float | None = None
    if macro:
        spy = macro.get("net_beta_by_factor", {}).get("SPY")
        if isinstance(spy, (int, float)):
            book_net_spy_beta = float(spy)
        share = macro.get("systematic_share")
        if isinstance(share, (int, float)):
            book_systematic_share = float(share)

    position_values: dict[str, float] = {}
    try:
        for h in read_holdings(holdings_path):
            # cost_basis is the TOTAL position cost (not per-share) — validated
            # against macro_beta_use_case.py:76-78. Weights are by cost basis.
            position_values[h.ticker] = position_values.get(h.ticker, 0.0) + float(
                h.cost_basis
            )
    except (OSError, ValueError) as exc:
        logger.warning(f"fit: holdings unavailable ({exc}) — DATA_GAP")

    try:
        ticker_beta = beta_fn(ticker, as_of)
    except Exception as exc:  # beta estimation is best-effort by design
        logger.warning(f"fit: beta estimation failed for {ticker} ({exc})")
        ticker_beta = None

    return assess_fit(
        ticker=ticker,
        ticker_composite=ticker_composite,
        universe_composites=universe_composites,
        ticker_beta=ticker_beta,
        book_net_spy_beta=book_net_spy_beta,
        book_systematic_share=book_systematic_share,
        systematic_share_threshold=systematic_share_threshold,
        position_values=position_values,
        trend_state=trend_state,
        hypothetical_weight=hypothetical_weight,
    )


def default_beta_fn(ticker: str, as_of: datetime) -> float | None:
    """Single-ticker SPY beta via the EXISTING MacroBetaUseCase (1-element book).

    Reuses the Ridge estimator + retry/backoff price fetch end-to-end. Returns the
    SPY beta_headline, or None when history is insufficient.
    """
    from types import SimpleNamespace

    import yaml

    from adapters.ml.macro_beta_analyzer import RidgeMacroBetaEstimator
    from application.macro_beta_use_case import MacroBetaUseCase
    from application.price_returns import load_price_series

    try:
        cfg = yaml.safe_load(Path("config/markets/us.yaml").read_text()) or {}
    except OSError:
        cfg = {}
    macro_cfg = cfg.get("macro_beta", {})

    uc = MacroBetaUseCase(
        price_provider=lambda t, s, e: load_price_series(t, s, e),
        estimator=RidgeMacroBetaEstimator(alpha=macro_cfg.get("ridge_alpha", 0.2)),
        factors=macro_cfg.get("factors", ["SPY", "TLT", "UUP", "XLE"]),
        alpha=macro_cfg.get("ridge_alpha", 0.2),
        headline_window=macro_cfg.get("headline_window_days", 252),
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
    )
    book = uc.execute(
        [SimpleNamespace(ticker=ticker, shares=1.0, cost_basis=0.0)], as_of
    )
    if book is None or not book.holdings:
        return None
    for b in book.holdings[0].betas:
        if b.factor == "SPY":
            return b.beta_headline
    return None


def market_systematic_share_threshold() -> float:
    """The same config value MacroBetaUseCase is constructed with (us.yaml, 0.60)."""
    import yaml

    try:
        cfg = yaml.safe_load(Path("config/markets/us.yaml").read_text()) or {}
    except OSError:
        return 0.60
    return float(cfg.get("macro_beta", {}).get("systematic_share_threshold", 0.60))
