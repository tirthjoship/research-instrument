"""Smart money feature engineer — 8 features from SEC 13D and Form 4 filings."""

from __future__ import annotations

from datetime import datetime

from domain.conviction import SmartMoneySignal, SmartMoneyType

SMART_MONEY_FEATURE_NAMES: list[str] = [
    "sm_13d_count",
    "sm_activist_count",
    "sm_max_stake_pct",
    "sm_form4_buy_count",
    "sm_form4_sell_count",
    "sm_total_buy_value",
    "sm_total_sell_value",
    "sm_insider_cluster",
]

_BUY_TYPES = {"purchase", "buy", "acquisition"}
_SELL_TYPES = {"sale", "sell", "disposition"}


class SmartMoneyFeatureEngineer:
    """Computes 8 smart money features from SEC filing signals."""

    def get_feature_names(self) -> list[str]:
        """Return the 8 feature names produced by compute()."""
        return list(SMART_MONEY_FEATURE_NAMES)

    def compute(
        self,
        ticker: str,
        signals: list[SmartMoneySignal],
        prediction_time: datetime,
    ) -> dict[str, float]:
        """Compute smart money features for a ticker.

        Args:
            ticker: Ticker symbol to filter on.
            signals: All SmartMoneySignal objects (will be filtered by ticker).
            prediction_time: Point-in-time cutoff (unused for now; reserved for
                future look-ahead enforcement at the adapter boundary).

        Returns:
            Dict mapping each of the 8 feature names to a float.
        """
        ticker_signals = [s for s in signals if s.ticker == ticker]

        filings_13d = [
            s for s in ticker_signals if s.signal_type == SmartMoneyType.FORM_13D
        ]
        filings_form4 = [
            s for s in ticker_signals if s.signal_type == SmartMoneyType.FORM_4
        ]

        buys = [s for s in filings_form4 if s.transaction_type.lower() in _BUY_TYPES]
        sells = [s for s in filings_form4 if s.transaction_type.lower() in _SELL_TYPES]

        stake_pcts = [s.stake_pct for s in filings_13d if s.stake_pct is not None]
        max_stake = max(stake_pcts) if stake_pcts else 0.0

        num_buys = len(buys)
        cluster_score = min(num_buys / 5.0, 1.0)

        return {
            "sm_13d_count": float(len(filings_13d)),
            "sm_activist_count": float(sum(1 for s in filings_13d if s.is_activist)),
            "sm_max_stake_pct": max_stake,
            "sm_form4_buy_count": float(num_buys),
            "sm_form4_sell_count": float(len(sells)),
            "sm_total_buy_value": sum(s.transaction_value for s in buys),
            "sm_total_sell_value": sum(s.transaction_value for s in sells),
            "sm_insider_cluster": cluster_score,
        }
