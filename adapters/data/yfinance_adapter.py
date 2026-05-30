"""yfinance adapter implementing MarketDataPort + TechnicalAnalysisPort.

Fetches OHLCV data via yfinance with point-in-time filtering,
caches raw API responses for reproducibility (ADR-017).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import yfinance as yf

from domain.exceptions import LookAheadBiasError
from domain.models import Signal

from .cache_mixin import CachingMixin

logger = logging.getLogger(__name__)


class YFinanceAdapter(CachingMixin):
    """Adapter for yfinance market data.

    Implements MarketDataPort and TechnicalAnalysisPort protocols.
    Uses auto_adjust=False for point-in-time correctness.
    """

    def __init__(
        self,
        cache_dir: Path,
        use_cache: bool = False,
    ) -> None:
        super().__init__(cache_dir)
        self._use_cache = use_cache

    # ── MarketDataPort ──────────────────────────────────────────────

    def get_signals(
        self,
        symbol: str,
        prediction_time: datetime,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[Signal]:
        """Fetch OHLCV data and convert to list[Signal] with point-in-time filtering."""
        self.validate_point_in_time(prediction_time)

        if self._use_cache and self.has_cache(symbol):
            cached = self.load_from_cache(symbol)
            if cached and "history" in cached:
                return self._dict_to_signals(symbol, cached["history"], prediction_time)

        ticker = yf.Ticker(symbol)

        effective_start = start_date or datetime(
            prediction_time.year - 1, prediction_time.month, prediction_time.day
        )
        effective_end = end_date or prediction_time

        df = ticker.history(
            start=effective_start.strftime("%Y-%m-%d"),
            end=effective_end.strftime("%Y-%m-%d"),
            auto_adjust=False,
        )

        if df.empty:
            logger.warning("No data returned for %s", symbol)
            return []

        # Cache raw response
        history_dict: dict[str, Any] = {
            col: {str(idx): val for idx, val in df[col].items()} for col in df.columns
        }
        self.save_to_cache(symbol, {"history": history_dict, "symbol": symbol})

        signals = self._df_to_signals(symbol, df, prediction_time)
        return signals

    def get_ticker_info(self, symbol: str) -> dict[str, float]:
        """Map yfinance info fields to standardised feature names."""
        ticker = yf.Ticker(symbol)
        info = ticker.info

        field_map: dict[str, str] = {
            "marketCap": "market_cap",
            "trailingPE": "trailing_pe",
            "forwardPE": "forward_pe",
            "priceToBook": "price_to_book",
            "revenueGrowth": "revenue_growth",
            "earningsGrowth": "earnings_growth",
            "profitMargins": "profit_margins",
            "returnOnEquity": "return_on_equity",
            "debtToEquity": "debt_to_equity",
            "currentRatio": "current_ratio",
            "heldPercentInstitutions": "institutional_ownership",
            "heldPercentInsiders": "insider_ownership",
            "beta": "beta",
            "dividendYield": "dividend_yield",
            "trailingAnnualDividendYield": "trailing_dividend_yield",
        }

        result: dict[str, float] = {}
        for yf_key, feat_name in field_map.items():
            val = info.get(yf_key)
            if val is not None:
                result[feat_name] = float(val)

        return result

    def get_options_summary(
        self, symbol: str, prediction_time: datetime
    ) -> dict[str, float] | None:
        """Compute put/call ratio and IV skew from options chain."""
        self.validate_point_in_time(prediction_time)

        try:
            ticker = yf.Ticker(symbol)
            expirations = ticker.options
            if not expirations:
                return None

            # Use nearest expiration
            chain = ticker.option_chain(expirations[0])
            calls = chain.calls
            puts = chain.puts

            total_call_oi = (
                float(calls["openInterest"].sum())
                if "openInterest" in calls.columns
                else 0.0
            )
            total_put_oi = (
                float(puts["openInterest"].sum())
                if "openInterest" in puts.columns
                else 0.0
            )

            put_call_ratio = total_put_oi / total_call_oi if total_call_oi > 0 else 0.0

            call_iv = (
                float(calls["impliedVolatility"].mean())
                if "impliedVolatility" in calls.columns
                else 0.0
            )
            put_iv = (
                float(puts["impliedVolatility"].mean())
                if "impliedVolatility" in puts.columns
                else 0.0
            )
            iv_skew = put_iv - call_iv

            return {
                "put_call_ratio": put_call_ratio,
                "iv_skew": iv_skew,
                "call_iv_mean": call_iv,
                "put_iv_mean": put_iv,
                "total_call_oi": total_call_oi,
                "total_put_oi": total_put_oi,
            }
        except Exception:
            logger.warning("Failed to fetch options for %s", symbol, exc_info=True)
            return None

    def get_analyst_data(
        self, symbol: str, prediction_time: datetime
    ) -> dict[str, float] | None:
        """Extract short interest and earnings surprise data."""
        self.validate_point_in_time(prediction_time)

        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            result: dict[str, float] = {}

            short_fields: dict[str, str] = {
                "shortRatio": "short_ratio",
                "shortPercentOfFloat": "short_percent_of_float",
            }
            for yf_key, feat_name in short_fields.items():
                val = info.get(yf_key)
                if val is not None:
                    result[feat_name] = float(val)

            analyst_fields: dict[str, str] = {
                "recommendationMean": "analyst_recommendation_mean",
                "numberOfAnalystOpinions": "analyst_count",
                "targetMeanPrice": "target_mean_price",
                "targetHighPrice": "target_high_price",
                "targetLowPrice": "target_low_price",
            }
            for yf_key, feat_name in analyst_fields.items():
                val = info.get(yf_key)
                if val is not None:
                    result[feat_name] = float(val)

            return result if result else None
        except Exception:
            logger.warning("Failed to fetch analyst data for %s", symbol, exc_info=True)
            return None

    def validate_point_in_time(self, prediction_time: datetime) -> None:
        """Ensure prediction_time is not in the future."""
        now = datetime.now(timezone.utc)
        # Allow naive datetimes by comparing without timezone
        pt = (
            prediction_time.replace(tzinfo=None)
            if prediction_time.tzinfo
            else prediction_time
        )
        now_naive = now.replace(tzinfo=None)
        if pt > now_naive:
            raise LookAheadBiasError(
                f"prediction_time {prediction_time} is in the future (now={now})"
            )

    # ── TechnicalAnalysisPort ───────────────────────────────────────

    def compute_indicators(self, signals: list[Signal]) -> dict[str, float]:
        """Compute RSI-14, MACD(12,26,9), Stochastic K/D, SMA 20/50, OBV trend."""
        if len(signals) < 2:
            return {}

        closes = np.array([s.price for s in signals], dtype=np.float64)
        highs = np.array([s.high for s in signals], dtype=np.float64)
        lows = np.array([s.low for s in signals], dtype=np.float64)
        volumes = np.array([s.volume for s in signals], dtype=np.float64)

        result: dict[str, float] = {}

        # RSI-14
        if len(closes) >= 15:
            deltas = np.diff(closes)
            gains = np.where(deltas > 0, deltas, 0.0)
            losses = np.where(deltas < 0, -deltas, 0.0)
            avg_gain = float(np.mean(gains[-14:]))
            avg_loss = float(np.mean(losses[-14:]))
            if avg_loss == 0:
                result["rsi_14"] = 100.0
            else:
                rs = avg_gain / avg_loss
                result["rsi_14"] = 100.0 - (100.0 / (1.0 + rs))

        # MACD (12, 26, 9)
        if len(closes) >= 26:
            ema12 = self._ema(closes, 12)
            ema26 = self._ema(closes, 26)
            macd_line = ema12 - ema26
            if len(macd_line) >= 9:
                signal_line = self._ema(macd_line, 9)
                result["macd"] = float(macd_line[-1])
                result["macd_signal"] = float(signal_line[-1])
                result["macd_histogram"] = float(macd_line[-1] - signal_line[-1])

        # Stochastic K/D (14-period)
        if len(closes) >= 14:
            low_14 = float(np.min(lows[-14:]))
            high_14 = float(np.max(highs[-14:]))
            if high_14 != low_14:
                stoch_k = ((closes[-1] - low_14) / (high_14 - low_14)) * 100.0
            else:
                stoch_k = 50.0
            result["stochastic_k"] = float(stoch_k)
            # D is 3-period SMA of K; approximate with current K
            result["stochastic_d"] = float(stoch_k)

        # SMA 20 / 50
        if len(closes) >= 20:
            result["sma_20"] = float(np.mean(closes[-20:]))
        if len(closes) >= 50:
            result["sma_50"] = float(np.mean(closes[-50:]))

        # OBV trend (sign of OBV slope over last 14 days)
        if len(closes) >= 14:
            obv = np.zeros(len(closes))
            for i in range(1, len(closes)):
                if closes[i] > closes[i - 1]:
                    obv[i] = obv[i - 1] + volumes[i]
                elif closes[i] < closes[i - 1]:
                    obv[i] = obv[i - 1] - volumes[i]
                else:
                    obv[i] = obv[i - 1]
            obv_recent = obv[-14:]
            x = np.arange(len(obv_recent), dtype=np.float64)
            slope = float(np.polyfit(x, obv_recent, 1)[0])
            result["obv_trend"] = 1.0 if slope > 0 else (-1.0 if slope < 0 else 0.0)

        return result

    # ── Private helpers ─────────────────────────────────────────────

    @staticmethod
    def _ema(data: np.ndarray, period: int) -> np.ndarray:
        """Compute exponential moving average."""
        alpha = 2.0 / (period + 1)
        ema = np.empty_like(data)
        ema[0] = data[0]
        for i in range(1, len(data)):
            ema[i] = alpha * data[i] + (1 - alpha) * ema[i - 1]
        return ema

    def _df_to_signals(
        self, symbol: str, df: Any, prediction_time: datetime
    ) -> list[Signal]:
        """Convert a pandas DataFrame to list[Signal] with point-in-time filter."""
        signals: list[Signal] = []
        for idx, row in df.iterrows():
            ts = idx.to_pydatetime() if hasattr(idx, "to_pydatetime") else idx
            # Strip timezone for comparison
            ts_naive = (
                ts.replace(tzinfo=None) if hasattr(ts, "replace") and ts.tzinfo else ts
            )
            pt_naive = (
                prediction_time.replace(tzinfo=None)
                if prediction_time.tzinfo
                else prediction_time
            )
            if ts_naive > pt_naive:
                continue

            close_col = "Close"
            open_col = "Open"
            high_col = "High"
            low_col = "Low"
            vol_col = "Volume"

            signals.append(
                Signal(
                    symbol=symbol,
                    timestamp=ts_naive,
                    price=float(row[close_col]),
                    volume=float(row[vol_col]),
                    open_=float(row[open_col]),
                    high=float(row[high_col]),
                    low=float(row[low_col]),
                )
            )
        return signals

    def _dict_to_signals(
        self,
        symbol: str,
        history: dict[str, Any],
        prediction_time: datetime,
    ) -> list[Signal]:
        """Convert cached dict back to list[Signal]."""
        from datetime import datetime as dt

        close_data = history.get("Close", {})
        open_data = history.get("Open", {})
        high_data = history.get("High", {})
        low_data = history.get("Low", {})
        volume_data = history.get("Volume", {})

        pt_naive = (
            prediction_time.replace(tzinfo=None)
            if prediction_time.tzinfo
            else prediction_time
        )

        signals: list[Signal] = []
        for ts_str in sorted(close_data.keys()):
            try:
                ts = dt.fromisoformat(ts_str.split(" ")[0])
            except (ValueError, AttributeError):
                continue
            if ts > pt_naive:
                continue
            signals.append(
                Signal(
                    symbol=symbol,
                    timestamp=ts,
                    price=float(close_data[ts_str]),
                    volume=float(volume_data.get(ts_str, 0)),
                    open_=float(open_data.get(ts_str, 0)),
                    high=float(high_data.get(ts_str, 0)),
                    low=float(low_data.get(ts_str, 0)),
                )
            )
        return signals
