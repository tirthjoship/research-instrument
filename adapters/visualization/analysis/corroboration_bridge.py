"""Bridge: build a live OurReadout from an already-computed AnalysisResult.

Deliberately reuses data already fetched onto ``AnalysisResult`` (price_history,
peer_percentiles) plus on-disk screen/holdings files — no new network calls in
the dashboard's hot path. Mirrors the CLI's ``_build_readout_fn``
(application/cli/corroboration_commands.py) but without the live yfinance
re-fetch, since compose.py already has the price series on ``result``.

Every field is honestly None/False/"clear" unless it can be derived — no
fabrication (ADR-062).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from application.corroboration_readout import (
    factor_percentile_from_screen,
    trend_health_band,
)
from domain.corroboration_models import OurReadout
from domain.trend_rules import trend_health as _trend_health_from_series

logger = logging.getLogger(__name__)


def _latest_screen(reports_dir: str) -> dict[str, Any] | None:
    """Most recent screen_<date>.json in reports_dir, or None."""
    try:
        report_dir = Path(reports_dir)
        if not report_dir.exists():
            return None
        candidates = sorted(
            p
            for p in report_dir.glob("screen_*.json")
            if not p.name.startswith("screen_ic_")
        )
        if not candidates:
            return None
        return json.loads(candidates[-1].read_text())  # type: ignore[no-any-return]
    except Exception as exc:
        logger.warning("corroboration bridge: failed to load latest screen: %s", exc)
        return None


def _factor_percentile(ticker: str, result: Any, reports_dir: str) -> float | None:
    """(1) latest screen JSON, (2) mean of result.peer_percentiles, (3) None."""
    screen = _latest_screen(reports_dir)
    pct = factor_percentile_from_screen(ticker, screen)
    if pct is not None:
        return pct
    percentiles: list[float] = [
        float(v)
        for v in (getattr(result, "peer_percentiles", None) or {}).values()
        if v is not None
    ]
    if percentiles:
        return sum(percentiles) / len(percentiles)
    return None


def _trend_health_float(result: Any) -> float | None:
    """Signed ATR-distance from result.price_history — already fetched, no new call."""
    price_history = getattr(result, "price_history", None)
    if not price_history:
        return None
    closes = price_history.get("closes")
    if not closes:
        return None
    ma200 = price_history.get("ma200")
    atr = price_history.get("atr")
    return _trend_health_from_series(closes[-1], ma200, atr)


def _is_held(ticker: str, holdings_path: str) -> bool:
    try:
        from application.holdings_reader import read_holdings

        holdings = read_holdings(holdings_path)
        return any(h.ticker.upper() == ticker.upper() for h in holdings)
    except Exception as exc:
        logger.warning("corroboration bridge: failed to read holdings: %s", exc)
        return False


def build_readout_from_analysis(
    result: Any,
    *,
    holdings_path: str = "data/personal/holdings.csv",
    reports_dir: str = "data/reports",
) -> OurReadout:
    """Assemble an OurReadout from an already-computed AnalysisResult.

    - factor_percentile: latest screen_*.json (factor_percentile_from_screen),
      else the mean of result.peer_percentiles' non-None values, else None.
    - trend_health: domain.trend_rules.trend_health() applied to
      result.price_history's closes/ma200/atr — the same series already
      fetched for the Performance panel, not a new fetch.
    - divergence_flag: always False here. Real cross-modal divergence needs a
      point-in-time buzz-vs-price series this bridge doesn't have; deferred
      rather than shipped as a buzz-only proxy (buzz alone is not divergence —
      same deferral and rationale as corroboration_commands.py's
      _build_readout_fn).
    - discipline_flag: "clear" when the ticker isn't held (nothing to flag).
      When it IS held, a real REDUCE/HOLD/ADD_OK verdict needs trailing-stop /
      market-trend / volatility inputs this bridge does not have, so it is
      left as None (displays as a data gap) rather than guessed.
    """
    ticker = str(getattr(result, "ticker", ""))
    held = _is_held(ticker, holdings_path)
    return OurReadout(
        factor_percentile=_factor_percentile(ticker, result, reports_dir),
        trend_health=trend_health_band(_trend_health_float(result)),
        divergence_flag=False,
        discipline_flag=None if held else "clear",
    )
