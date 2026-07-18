"""Attributed analyst-estimate panel.

All data in this module is ATTRIBUTED, not adopted. Figures come from
third-party analyst consensus (via yfinance) and must be displayed as
such — the engine makes no claim of its own about price targets or
analyst ratings. See ADR-055/056 for the attributed-not-adopted rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

# Canada is the only market with a confirmed-live Finnhub recommendation-trend
# fallback as of 2026-07-18 (India 403s premium-gated — see docs/STATUS.md).
_FINNHUB_FALLBACK_SUFFIXES = (".TO", ".V", ".NE")


@dataclass(frozen=True)
class AnalystPanel:
    """Third-party analyst consensus snapshot — attributed source, not engine output."""

    count: int
    mean_rating: float | None
    target_mean: float | None
    target_high: float | None
    target_low: float | None
    as_of: str
    attribution: str
    data_gap: bool


def build_analyst_panel(info: dict[str, object], as_of: str) -> AnalystPanel:
    """Build an attributed AnalystPanel from a yfinance-style info dict.

    Data is presented as third-party analyst consensus sourced from
    yfinance (The Street aggregates). It is never framed as a
    recommendation or forecast by this engine.

    Args:
        info: yfinance-style ticker.info dict (may be empty).
        as_of: ISO date string for the snapshot date.

    Returns:
        AnalystPanel with fields populated from available data.
        Sets data_gap=True when no analyst coverage is present.
    """

    def _to_int(val: object) -> int:
        if isinstance(val, (int, float)):
            return int(val)
        if isinstance(val, str):
            return int(val)
        return 0

    def _to_float(val: object) -> float | None:
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            return float(val)
        return None

    count: int = _to_int(info.get("analyst_count"))
    mean_rating: float | None = _to_float(info.get("analyst_recommendation_mean"))
    target_mean: float | None = _to_float(info.get("targetMeanPrice"))
    target_high: float | None = _to_float(info.get("targetHighPrice"))
    target_low: float | None = _to_float(info.get("targetLowPrice"))

    attribution = (
        "The Street (per yfinance) currently reads the following analyst consensus — "
        "these are third-party estimates, not this engine's views."
    )

    data_gap: bool = count == 0

    return AnalystPanel(
        count=count,
        mean_rating=mean_rating,
        target_mean=target_mean,
        target_high=target_high,
        target_low=target_low,
        as_of=as_of,
        attribution=attribution,
        data_gap=data_gap,
    )


def build_finnhub_consensus_panel(
    trend: dict[str, int] | None, as_of: str
) -> AnalystPanel:
    """Build an attributed AnalystPanel from a Finnhub recommendation-trend dict.

    Finnhub's endpoint gives rating-bucket counts (strongBuy/buy/hold/sell/
    strongSell), not target prices — target_mean/high/low stay None rather
    than fabricating a series that isn't there.

    Args:
        trend: Dict of counts from
            ``FinnhubRecommendationAdapter.get_recommendation_trend()``, or
            None if unavailable.
        as_of: ISO date string for the snapshot date.

    Returns:
        AnalystPanel with count/mean_rating populated from Finnhub, target
        fields always None. data_gap=True when trend is None or empty.
    """
    count = sum(trend.values()) if trend else 0

    mean_rating: float | None = None
    if trend and count > 0:
        # yfinance's 1 (Strong Buy) .. 5 (Strong Sell) scale, for display parity.
        weighted = (
            1 * trend.get("strongBuy", 0)
            + 2 * trend.get("buy", 0)
            + 3 * trend.get("hold", 0)
            + 4 * trend.get("sell", 0)
            + 5 * trend.get("strongSell", 0)
        )
        mean_rating = weighted / count

    attribution = (
        "Finnhub currently reads the following analyst recommendation trend — "
        "these are third-party estimates, not this engine's views. "
        "Target prices are unavailable from this source."
    )

    return AnalystPanel(
        count=count,
        mean_rating=mean_rating,
        target_mean=None,
        target_high=None,
        target_low=None,
        as_of=as_of,
        attribution=attribution,
        data_gap=count == 0,
    )


class _RecommendationTrendSource(Protocol):
    def get_recommendation_trend(self, ticker: str) -> dict[str, int] | None: ...


def get_analyst_panel_with_fallback(
    ticker: str,
    info: dict[str, object],
    as_of: str,
    finnhub_adapter: _RecommendationTrendSource | None = None,
) -> AnalystPanel:
    """Build an AnalystPanel from yfinance, falling back to Finnhub's
    recommendation-trend endpoint for markets yfinance leaves empty.

    Only Canadian tickers (.TO/.V/.NE suffix) trigger the fallback — Finnhub's
    recommendation endpoint 403s for India as of 2026-07-18 (see
    docs/STATUS.md), so there's nothing to gain by calling it there.

    Args:
        ticker: Stock ticker symbol, yfinance-suffixed (e.g. ``"RY.TO"``).
        info: yfinance-style ticker.info dict (may be empty).
        as_of: ISO date string for the snapshot date.
        finnhub_adapter: Optional injected adapter (constructed fresh if
            omitted and the fallback path is taken).

    Returns:
        AnalystPanel — from yfinance if it has coverage, else from Finnhub
        for Canadian tickers, else the yfinance data-gap panel unchanged.
    """
    panel = build_analyst_panel(info, as_of)
    if not panel.data_gap or not ticker.endswith(_FINNHUB_FALLBACK_SUFFIXES):
        return panel

    adapter = finnhub_adapter
    if adapter is None:
        from adapters.data.finnhub_recommendation_adapter import (
            FinnhubRecommendationAdapter,
        )

        adapter = FinnhubRecommendationAdapter()

    trend = adapter.get_recommendation_trend(ticker)
    return build_finnhub_consensus_panel(trend, as_of)
