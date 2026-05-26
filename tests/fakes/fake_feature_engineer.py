"""Fake FeatureEngineerPort implementation for testing."""
from domain.models import Signal

FAKE_FEATURE_NAMES: list[str] = [
    "return_1d", "return_5d", "return_20d", "volatility_20d",
    "price_vs_sma20", "price_vs_sma50", "sma20_vs_sma50",
    "rsi_14", "macd", "macd_signal", "macd_histogram",
    "stochastic_k", "stochastic_d", "volume_ratio_20d", "obv_trend",
    "price_vs_52w_high", "price_vs_52w_low", "market_cap_quintile",
    "return_6m", "return_12m", "volatility_regime",
    "drawdown_from_ath", "sector_relative_strength_6m",
    "revenue_growth_yoy", "pe_vs_sector_median",
    "short_interest_ratio", "short_interest_change_5d",
    "earnings_surprise_last", "earnings_surprise_streak",
    "iv_skew_25d", "iv_rank_percentile", "institutional_ownership_change",
    "sector_etf_return_5d", "stock_vs_sector",
    "unusual_options_volume", "put_call_ratio",
    "options_volume_vs_stock_volume", "large_block_trades_count",
    "correlation_with_spy", "relative_strength_vs_peers",
    "vix_level", "treasury_10y_direction", "dxy_strength",
    "yield_curve_slope", "spy_momentum_20d",
]


class FakeFeatureEngineer:
    def __init__(self, override: dict[str, float] | None = None) -> None:
        self._override = override or {}

    def compute(self, signals: list[Signal], indicators: dict[str, float],
                ticker_info: dict[str, float], options_summary: dict[str, float] | None,
                analyst_data: dict[str, float] | None,
                macro_signals: dict[str, list[Signal]],
                sector_signals: list[Signal] | None) -> dict[str, float]:
        base = signals[-1].price if signals else 100.0
        features: dict[str, float] = {}
        for i, name in enumerate(FAKE_FEATURE_NAMES):
            if name in self._override:
                features[name] = self._override[name]
            else:
                features[name] = (base + i) * 0.01
        return features

    def get_feature_names(self) -> list[str]:
        return list(FAKE_FEATURE_NAMES)
