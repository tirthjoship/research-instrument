"""Feature engineer: computes 45 features across 8 groups.

Groups:
  1. Technical (15) — from OHLCV
  2. Regime (10) — from historical OHLCV
  3. Stronger signals (7) — from fundamentals/options
  4. Sector context (2) — from sector ETFs
  5. Options flow (4) — from options chain
  6. Cross-correlation (2) — from SPY/peers
  7. Macro regime (5) — from macro symbols

All computations use only data available at prediction time.
"""

import math

import numpy as np

from domain.models import Signal

_NAN = float("nan")

FEATURE_NAMES: list[str] = [
    # Technical (15)
    "return_1d",
    "return_5d",
    "return_20d",
    "volatility_20d",
    "price_vs_sma20",
    "price_vs_sma50",
    "sma20_vs_sma50",
    "rsi_14",
    "macd",
    "macd_signal",
    "macd_histogram",
    "stochastic_k",
    "stochastic_d",
    "volume_ratio_20d",
    "obv_trend",
    # Regime (10)
    "price_vs_52w_high",
    "price_vs_52w_low",
    "market_cap_quintile",
    "return_6m",
    "return_12m",
    "volatility_regime",
    "drawdown_from_ath",
    "sector_relative_strength_6m",
    "revenue_growth_yoy",
    "pe_vs_sector_median",
    # Stronger signals (7)
    "short_interest_ratio",
    "short_interest_change_5d",
    "earnings_surprise_last",
    "earnings_surprise_streak",
    "iv_skew_25d",
    "iv_rank_percentile",
    "institutional_ownership_change",
    # Sector context (2)
    "sector_etf_return_5d",
    "stock_vs_sector",
    # Options flow (4)
    "unusual_options_volume",
    "put_call_ratio",
    "options_volume_vs_stock_volume",
    "large_block_trades_count",
    # Cross-correlation (2)
    "correlation_with_spy",
    "relative_strength_vs_peers",
    # Macro regime (5)
    "vix_level",
    "treasury_10y_direction",
    "dxy_strength",
    "yield_curve_slope",
    "spy_momentum_20d",
]


class FeatureEngineer:
    """Computes 45 features from raw market data."""

    def compute(
        self,
        signals: list[Signal],
        indicators: dict[str, float],
        ticker_info: dict[str, float],
        options_summary: dict[str, float] | None,
        analyst_data: dict[str, float] | None,
        macro_signals: dict[str, list[Signal]],
        sector_signals: list[Signal] | None,
    ) -> dict[str, float]:
        closes = np.array([s.price for s in signals]) if signals else np.array([])
        volumes = np.array([s.volume for s in signals]) if signals else np.array([])
        highs = np.array([s.high for s in signals]) if signals else np.array([])

        features: dict[str, float] = {}

        # --- Group 1: Technical (15) ---
        features.update(self._technical_features(closes, volumes, indicators))

        # --- Group 2: Regime (10) ---
        features.update(self._regime_features(closes, highs, ticker_info))

        # --- Group 3: Stronger signals (7) ---
        features.update(
            self._stronger_signal_features(ticker_info, analyst_data, options_summary)
        )

        # --- Group 4: Sector context (2) ---
        features.update(self._sector_features(closes, sector_signals))

        # --- Group 5: Options flow (4) ---
        features.update(self._options_features(options_summary, volumes))

        # --- Group 6: Cross-correlation (2) ---
        features.update(self._cross_correlation_features(closes, macro_signals))

        # --- Group 7: Macro regime (5) ---
        features.update(self._macro_features(macro_signals))

        return features

    def get_feature_names(self) -> list[str]:
        return list(FEATURE_NAMES)

    # --- Group implementations ---

    def _technical_features(
        self,
        closes: np.ndarray,
        volumes: np.ndarray,
        indicators: dict[str, float],
    ) -> dict[str, float]:
        n = len(closes)
        f: dict[str, float] = {}

        # Returns
        f["return_1d"] = float((closes[-1] / closes[-2]) - 1) if n >= 2 else _NAN
        f["return_5d"] = float((closes[-1] / closes[-5]) - 1) if n >= 5 else _NAN
        f["return_20d"] = float((closes[-1] / closes[-20]) - 1) if n >= 20 else _NAN

        # Volatility
        if n >= 20:
            daily_returns = np.diff(closes[-21:]) / closes[-21:-1]
            f["volatility_20d"] = float(np.std(daily_returns))
        else:
            f["volatility_20d"] = _NAN

        # Price vs SMAs
        sma20 = indicators.get("sma_20")
        sma50 = indicators.get("sma_50")
        if n > 0 and sma20 is not None and sma20 > 0:
            f["price_vs_sma20"] = float(closes[-1] / sma20 - 1)
        else:
            f["price_vs_sma20"] = _NAN

        if n > 0 and sma50 is not None and sma50 > 0:
            f["price_vs_sma50"] = float(closes[-1] / sma50 - 1)
        else:
            f["price_vs_sma50"] = _NAN

        if sma20 is not None and sma50 is not None and sma50 > 0:
            f["sma20_vs_sma50"] = float(sma20 / sma50 - 1)
        else:
            f["sma20_vs_sma50"] = _NAN

        # From indicators
        f["rsi_14"] = float(indicators.get("rsi_14", _NAN))
        f["macd"] = float(indicators.get("macd", _NAN))
        f["macd_signal"] = float(indicators.get("macd_signal", _NAN))
        f["macd_histogram"] = float(indicators.get("macd_histogram", _NAN))
        f["stochastic_k"] = float(indicators.get("stochastic_k", _NAN))
        f["stochastic_d"] = float(indicators.get("stochastic_d", _NAN))

        # Volume
        if n >= 20:
            avg_vol = float(np.mean(volumes[-20:]))
            f["volume_ratio_20d"] = (
                float(volumes[-1] / avg_vol) if avg_vol > 0 else _NAN
            )
        else:
            f["volume_ratio_20d"] = _NAN

        f["obv_trend"] = float(indicators.get("obv_trend", _NAN))

        return f

    def _regime_features(
        self,
        closes: np.ndarray,
        highs: np.ndarray,
        ticker_info: dict[str, float],
    ) -> dict[str, float]:
        n = len(closes)
        f: dict[str, float] = {}

        # 52-week high/low
        if n >= 252:
            high_52w = float(np.max(highs[-252:]))
            low_52w = float(np.min(closes[-252:]))
            f["price_vs_52w_high"] = (
                float(closes[-1] / high_52w - 1) if high_52w > 0 else _NAN
            )
            f["price_vs_52w_low"] = (
                float(closes[-1] / low_52w - 1) if low_52w > 0 else _NAN
            )
        else:
            f["price_vs_52w_high"] = _NAN
            f["price_vs_52w_low"] = _NAN

        # Market cap quintile (1-5, normalized to 0-1)
        mc = ticker_info.get("market_cap", _NAN)
        if not math.isnan(mc):
            if mc > 200e9:
                f["market_cap_quintile"] = 1.0
            elif mc > 10e9:
                f["market_cap_quintile"] = 0.75
            elif mc > 2e9:
                f["market_cap_quintile"] = 0.5
            elif mc > 300e6:
                f["market_cap_quintile"] = 0.25
            else:
                f["market_cap_quintile"] = 0.0
        else:
            f["market_cap_quintile"] = _NAN

        # 6m and 12m returns
        f["return_6m"] = float(closes[-1] / closes[-126] - 1) if n >= 126 else _NAN
        f["return_12m"] = float(closes[-1] / closes[-252] - 1) if n >= 252 else _NAN

        # Volatility regime (current 20d vol vs 1yr average vol)
        if n >= 252:
            current_vol = float(np.std(np.diff(closes[-21:]) / closes[-21:-1]))
            year_returns = np.diff(closes[-252:]) / closes[-252:-1]
            year_vol = float(np.std(year_returns))
            f["volatility_regime"] = current_vol / year_vol if year_vol > 0 else _NAN
        else:
            f["volatility_regime"] = _NAN

        # Drawdown from ATH
        if n > 0:
            ath = float(np.max(highs))
            f["drawdown_from_ath"] = float(closes[-1] / ath - 1) if ath > 0 else _NAN
        else:
            f["drawdown_from_ath"] = _NAN

        # Sector relative strength (placeholder — needs sector ETF data)
        f["sector_relative_strength_6m"] = _NAN

        # Fundamentals from ticker_info
        f["revenue_growth_yoy"] = float(ticker_info.get("revenue_growth_yoy", _NAN))
        f["pe_vs_sector_median"] = float(ticker_info.get("pe_ratio", _NAN))

        return f

    def _stronger_signal_features(
        self,
        ticker_info: dict[str, float],
        analyst_data: dict[str, float] | None,
        options_summary: dict[str, float] | None,
    ) -> dict[str, float]:
        f: dict[str, float] = {}
        ad = analyst_data or {}
        opt = options_summary or {}

        f["short_interest_ratio"] = float(
            ad.get(
                "short_interest_ratio",
                ticker_info.get("short_interest_ratio", _NAN),
            )
        )
        f["short_interest_change_5d"] = float(ad.get("short_interest_change_5d", _NAN))
        f["earnings_surprise_last"] = float(ad.get("earnings_surprise_last", _NAN))
        f["earnings_surprise_streak"] = float(ad.get("earnings_surprise_streak", _NAN))
        f["iv_skew_25d"] = float(opt.get("iv_skew_25d", _NAN))
        f["iv_rank_percentile"] = float(opt.get("iv_rank_percentile", _NAN))
        f["institutional_ownership_change"] = float(
            ticker_info.get("institutional_ownership_change", _NAN)
        )

        return f

    def _sector_features(
        self,
        closes: np.ndarray,
        sector_signals: list[Signal] | None,
    ) -> dict[str, float]:
        f: dict[str, float] = {}
        if sector_signals and len(sector_signals) >= 5 and len(closes) >= 5:
            sector_prices = np.array([s.price for s in sector_signals])
            f["sector_etf_return_5d"] = float(sector_prices[-1] / sector_prices[-5] - 1)
            stock_5d = float(closes[-1] / closes[-5] - 1)
            f["stock_vs_sector"] = stock_5d - f["sector_etf_return_5d"]
        else:
            f["sector_etf_return_5d"] = _NAN
            f["stock_vs_sector"] = _NAN
        return f

    def _options_features(
        self,
        options_summary: dict[str, float] | None,
        volumes: np.ndarray,
    ) -> dict[str, float]:
        f: dict[str, float] = {}
        opt = options_summary or {}

        f["unusual_options_volume"] = float(opt.get("unusual_options_volume", _NAN))
        f["put_call_ratio"] = float(opt.get("put_call_ratio", _NAN))

        total_opt_vol = opt.get("unusual_options_volume", _NAN)
        if len(volumes) > 0 and not math.isnan(total_opt_vol) and volumes[-1] > 0:
            f["options_volume_vs_stock_volume"] = total_opt_vol / float(volumes[-1])
        else:
            f["options_volume_vs_stock_volume"] = _NAN

        f["large_block_trades_count"] = float(opt.get("large_block_trades_count", _NAN))

        return f

    def _cross_correlation_features(
        self,
        closes: np.ndarray,
        macro_signals: dict[str, list[Signal]],
    ) -> dict[str, float]:
        f: dict[str, float] = {}

        spy_signals = macro_signals.get("SPY", [])
        if len(spy_signals) >= 20 and len(closes) >= 20:
            spy_closes = np.array([s.price for s in spy_signals[-20:]])
            stock_returns = np.diff(closes[-20:]) / closes[-20:-1]
            spy_returns = np.diff(spy_closes) / spy_closes[:-1]
            min_len = min(len(stock_returns), len(spy_returns))
            if min_len >= 2:
                corr = float(
                    np.corrcoef(stock_returns[-min_len:], spy_returns[-min_len:])[0, 1]
                )
                f["correlation_with_spy"] = corr if not math.isnan(corr) else _NAN

                # Relative strength: stock cumulative return vs SPY
                stock_cum = float(np.prod(1 + stock_returns[-min_len:]) - 1)
                spy_cum = float(np.prod(1 + spy_returns[-min_len:]) - 1)
                f["relative_strength_vs_peers"] = stock_cum - spy_cum
            else:
                f["correlation_with_spy"] = _NAN
                f["relative_strength_vs_peers"] = _NAN
        else:
            f["correlation_with_spy"] = _NAN
            f["relative_strength_vs_peers"] = _NAN

        return f

    def _macro_features(
        self, macro_signals: dict[str, list[Signal]]
    ) -> dict[str, float]:
        f: dict[str, float] = {}

        # VIX level
        vix = macro_signals.get("^VIX", [])
        f["vix_level"] = vix[-1].price if vix else _NAN

        # Treasury 10Y direction (5-day change)
        tnx = macro_signals.get("^TNX", [])
        if len(tnx) >= 5:
            f["treasury_10y_direction"] = tnx[-1].price - tnx[-5].price
        else:
            f["treasury_10y_direction"] = _NAN

        # DXY strength (20-day return)
        dxy = macro_signals.get("DX-Y.NYB", [])
        if len(dxy) >= 20:
            f["dxy_strength"] = float(dxy[-1].price / dxy[-20].price - 1)
        else:
            f["dxy_strength"] = _NAN

        # Yield curve slope (10Y - 3M)
        irx = macro_signals.get("^IRX", [])
        if tnx and irx:
            f["yield_curve_slope"] = tnx[-1].price - irx[-1].price
        else:
            f["yield_curve_slope"] = _NAN

        # SPY 20-day momentum
        spy = macro_signals.get("SPY", [])
        if len(spy) >= 20:
            f["spy_momentum_20d"] = float(spy[-1].price / spy[-20].price - 1)
        else:
            f["spy_momentum_20d"] = _NAN

        return f
