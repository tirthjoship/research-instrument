"""Leakage-safe historical dataset generation for the conviction backtest.

The point-in-time guarantee lives in `make_historical_sub_score_fn`: EVERY signal
is filtered to filed/published <= date BEFORE scoring. Do not weaken this.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from adapters.ml.smart_money_engineer import SmartMoneyFeatureEngineer
from application.conviction_backtest import run_conviction_backtest
from domain.analyst import AnalystRating
from domain.analyst_service import analyst_conviction_score
from domain.conviction import SmartMoneySignal

_NEUTRAL = 5.0


def is_signal_bearing(sub_scores: dict[str, float]) -> bool:
    """True if the name has any active smart-money or analyst signal (not pure-neutral).

    Isolates the real hypothesis (does insider/analyst activity predict outperformance?)
    from the neutral mass that only differs by tie-breaking.
    """
    return (
        sub_scores.get("smart_money", 0.0) > 0.0
        or sub_scores.get("analyst_signal", 5.0) != 5.0
    )


@dataclass(frozen=True)
class BacktestSample:
    """One (ticker, date) observation from the historical conviction backtest."""

    ticker: str
    date: str  # "YYYY-MM-DD"
    sub_scores: dict[str, float]
    conviction: float
    forward_return: float
    benchmark_return: float
    win: int


def make_historical_sub_score_fn(
    smart_money_signals: list[SmartMoneySignal],
    analyst_events: list[AnalystRating],
) -> Callable[[str, datetime], dict[str, float]]:
    """Return a point-in-time sub-score function.

    Signals are filtered to <= date before scoring (the leakage guard).
    Non-reconstructable dimensions (fundamentals, sentiment, ml, event) are
    held NEUTRAL (5.0) to avoid leakage from data that is not stored
    historically.

    Feature keys from SmartMoneyFeatureEngineer.compute():
        sm_13d_count, sm_activist_count, sm_max_stake_pct,
        sm_form4_buy_count, sm_form4_sell_count,
        sm_total_buy_value, sm_total_sell_value, sm_insider_cluster
    """
    engineer = SmartMoneyFeatureEngineer()

    def sub_score_fn(ticker: str, date: datetime) -> dict[str, float]:
        # POINT-IN-TIME: only signals filed on or before `date`
        sm_filtered = [
            s
            for s in smart_money_signals
            if s.ticker == ticker
            and datetime.strptime(s.filed_date, "%Y-%m-%d") <= date
        ]
        feats = engineer.compute(
            ticker=ticker, signals=sm_filtered, prediction_time=date
        )
        # Combine smart-money features into a single 0-10 sub-score.
        # Weights: insider cluster (7) dominates; 13D presence (3) and
        # activist count (2) supplement.
        sm_raw = (
            feats.get("sm_13d_count", 0.0) * 3.0
            + feats.get("sm_insider_cluster", 0.0) * 7.0
            + feats.get("sm_activist_count", 0.0) * 2.0
        )
        sm_score = min(sm_raw, 10.0)

        # POINT-IN-TIME: only ratings published on or before `date`
        analysts_filtered = [
            a for a in analyst_events if a.ticker == ticker and a.published_at <= date
        ]
        analyst_score = analyst_conviction_score(analysts_filtered, {}, date)

        return {
            "smart_money": sm_score,
            "analyst_signal": analyst_score,
            # Held neutral — not reconstructable from stored history without
            # additional point-in-time data stores.
            "signal_agreement": _NEUTRAL,
            "temporal_freshness": _NEUTRAL,
            "sentiment_momentum": _NEUTRAL,
            "fundamental_basis": _NEUTRAL,
            "ml_direction": _NEUTRAL,
            "event_signal": _NEUTRAL,
        }

    return sub_score_fn


def build_historical_dataset(
    scan_dates: list[datetime],
    tickers: list[str],
    sub_score_fn: Callable[[str, datetime], dict[str, float]],
    conviction_fn: Callable[[dict[str, float]], float],
    forward_return_fn: Callable[[str, datetime], float],
    benchmark_return_fn: Callable[[datetime], float],
) -> list[BacktestSample]:
    """Generate one BacktestSample per (date, ticker) combination.

    Args:
        scan_dates: Ordered list of historical scan dates (point-in-time anchors).
        tickers: Universe of tickers to score on each date.
        sub_score_fn: Point-in-time sub-score function (use
            ``make_historical_sub_score_fn`` to build one).
        conviction_fn: Maps sub_scores dict → single conviction float.
        forward_return_fn: Returns observed forward return for (ticker, date).
        benchmark_return_fn: Returns benchmark return for date.

    Returns:
        List of BacktestSample, one per (date, ticker), in date-ticker order.
    """
    out: list[BacktestSample] = []
    for date in scan_dates:
        bench = benchmark_return_fn(date)
        for ticker in tickers:
            sub = sub_score_fn(ticker, date)
            conv = conviction_fn(sub)
            fwd = forward_return_fn(ticker, date)
            out.append(
                BacktestSample(
                    ticker=ticker,
                    date=date.strftime("%Y-%m-%d"),
                    sub_scores=sub,
                    conviction=conv,
                    forward_return=fwd,
                    benchmark_return=bench,
                    win=1 if fwd > bench else 0,
                )
            )
    return out


def metrics_from_samples(
    samples: list[BacktestSample],
    decile: float = 0.1,
) -> dict[str, object]:
    """Compute precision-first backtest metrics from pre-built samples.

    Reuses the tested ``run_conviction_backtest`` under the hood, converting
    the flat sample list into the lookup structures it expects.

    Args:
        samples: Output of ``build_historical_dataset``.
        decile: Fraction of tickers to treat as the "top decile" selection.

    Returns:
        Metrics dict from ``run_conviction_backtest`` (top_decile_hit_rate,
        f_beta_0_5, model_sharpe, p_value, …).
    """
    dates = sorted({s.date for s in samples})
    tickers = sorted({s.ticker for s in samples})
    conv_lookup = {(s.date, s.ticker): s.conviction for s in samples}
    fwd_lookup = {(s.date, s.ticker): s.forward_return for s in samples}
    bench_lookup = {s.date: s.benchmark_return for s in samples}

    def score_fn(d: str) -> dict[str, float]:
        return {t: conv_lookup[(d, t)] for t in tickers if (d, t) in conv_lookup}

    def forward_return_fn(t: str, d: str) -> float:
        return fwd_lookup[(d, t)]

    def benchmark_return_fn(d: str) -> float:
        return bench_lookup[d]

    return run_conviction_backtest(
        dates,
        tickers,
        score_fn,
        forward_return_fn,
        benchmark_return_fn,
        decile=decile,
    )
