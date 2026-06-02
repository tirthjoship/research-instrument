"""Fundamental feature engineer — 16 valuation/financial health features.

Computes features from yfinance ticker_info dict. No external imports
beyond stdlib math + statistics. Sector-aware where applicable.
"""

from __future__ import annotations

import math
import statistics

_NAN = float("nan")

FUNDAMENTAL_FEATURE_NAMES: list[str] = [
    "peg_ratio",
    "pe_ratio",
    "pe_vs_sector",
    "price_to_book",
    "debt_to_equity",
    "free_cash_flow_yield",
    "dividend_yield",
    "revenue_growth_yoy",
    "earnings_surprise_last",
    "earnings_surprise_streak",
    "institutional_ownership_change",
    "current_ratio",
    "gross_margin",
    "operating_margin",
    "valuation_z_score",
    "insider_net_purchases_90d",
]


class FundamentalFeatureEngineer:
    """Computes 16 fundamental/valuation features from ticker_info."""

    def compute(
        self,
        ticker_info: dict[str, float],
        sector_ticker_infos: list[dict[str, float]],
        analyst_data: dict[str, float] | None = None,
        prior_institutional_ownership: float | None = None,
    ) -> dict[str, float]:
        """Compute fundamental features.

        Args:
            ticker_info: Dict from YFinanceAdapter.get_ticker_info().
            sector_ticker_infos: List of ticker_info dicts for sector peers (for relative metrics).
            analyst_data: Optional dict with earnings_surprise_pct and earnings_surprise_streak.
            prior_institutional_ownership: Prior period institutional ownership for change calc.
        """
        f: dict[str, float] = {}

        # Direct pass-throughs
        f["peg_ratio"] = _get(ticker_info, "peg_ratio")
        f["pe_ratio"] = _get(ticker_info, "trailing_pe")
        f["price_to_book"] = _get(ticker_info, "price_to_book")
        f["debt_to_equity"] = _get(ticker_info, "debt_to_equity")
        f["dividend_yield"] = _get(ticker_info, "dividend_yield")
        f["revenue_growth_yoy"] = _get(ticker_info, "revenue_growth")
        f["current_ratio"] = _get(ticker_info, "current_ratio")
        f["gross_margin"] = _get(ticker_info, "gross_margins")
        f["operating_margin"] = _get(ticker_info, "operating_margins")

        # Computed: FCF yield = free_cashflow / market_cap
        fcf = ticker_info.get("free_cashflow")
        mcap = ticker_info.get("market_cap")
        if fcf is not None and mcap is not None and mcap > 0:
            f["free_cash_flow_yield"] = fcf / mcap
        else:
            f["free_cash_flow_yield"] = _NAN

        # Computed: P/E vs sector median = (ticker_pe - sector_median) / sector_median
        pe = ticker_info.get("trailing_pe")
        sector_pes = [
            s.get("trailing_pe", _NAN)
            for s in sector_ticker_infos
            if "trailing_pe" in s and not math.isnan(s.get("trailing_pe", _NAN))
        ]
        if pe is not None and sector_pes:
            sector_median_pe = statistics.median(sector_pes)
            if sector_median_pe > 0:
                f["pe_vs_sector"] = (pe - sector_median_pe) / sector_median_pe
            else:
                f["pe_vs_sector"] = _NAN
        else:
            f["pe_vs_sector"] = _NAN

        # Earnings features from analyst data
        ad = analyst_data or {}
        f["earnings_surprise_last"] = _get(ad, "earnings_surprise_pct")
        f["earnings_surprise_streak"] = _get(ad, "earnings_surprise_streak")

        # Institutional ownership change = current - prior
        current_inst = ticker_info.get("institutional_ownership")
        if current_inst is not None and prior_institutional_ownership is not None:
            f["institutional_ownership_change"] = (
                current_inst - prior_institutional_ownership
            )
        else:
            f["institutional_ownership_change"] = _NAN

        # Insider purchases (future: Quiver Quant adapter — NaN for now)
        f["insider_net_purchases_90d"] = _NAN

        # Composite: valuation_z_score
        f["valuation_z_score"] = self._compute_valuation_z_score(
            ticker_info, sector_ticker_infos
        )

        return f

    def _compute_valuation_z_score(
        self,
        ticker_info: dict[str, float],
        sector_ticker_infos: list[dict[str, float]],
    ) -> float:
        """Composite valuation: PEG + P/B + FCF yield vs sector.

        Negative = undervalued relative to sector. Positive = overvalued.
        """
        peg = ticker_info.get("peg_ratio")
        pb = ticker_info.get("price_to_book")
        fcf = ticker_info.get("free_cashflow")
        mcap = ticker_info.get("market_cap")

        if peg is None or pb is None or fcf is None or mcap is None or mcap <= 0:
            return _NAN

        fcf_yield = fcf / mcap

        # Sector medians
        sector_pegs = [s["peg_ratio"] for s in sector_ticker_infos if "peg_ratio" in s]
        sector_pbs = [
            s["price_to_book"] for s in sector_ticker_infos if "price_to_book" in s
        ]

        if not sector_pegs or not sector_pbs:
            return _NAN

        median_peg = statistics.median(sector_pegs)
        median_pb = statistics.median(sector_pbs)

        # Z-components: positive = more expensive
        z_peg = (peg - median_peg) / max(median_peg, 0.01)
        z_pb = (pb - median_pb) / max(median_pb, 0.01)
        # FCF yield: higher = cheaper, so negate
        z_fcf = -fcf_yield * 100  # scale to similar magnitude

        return (z_peg + z_pb + z_fcf) / 3.0

    def get_feature_names(self) -> list[str]:
        return list(FUNDAMENTAL_FEATURE_NAMES)


def _get(d: dict[str, float], key: str) -> float:
    """Get value from dict, return NaN if missing."""
    val = d.get(key)
    if val is None:
        return _NAN
    return float(val)
