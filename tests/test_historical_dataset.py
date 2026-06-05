"""Tests for the leakage-safe historical dataset generator.

The leak-guard test is the most critical — it verifies that signals dated
AFTER the scan date are invisible to the sub-score function.
"""

from __future__ import annotations

from datetime import datetime

from application.historical_dataset import (
    BacktestSample,
    build_historical_dataset,
    make_historical_sub_score_fn,
    metrics_from_samples,
)
from domain.analyst import AnalystAction, AnalystRating
from domain.conviction import SmartMoneySignal, SmartMoneyType


def _sm(ticker: str, filed: str) -> SmartMoneySignal:
    """Build a minimal valid SmartMoneySignal (Form 4 insider BUY)."""
    return SmartMoneySignal(
        ticker=ticker,
        signal_type=SmartMoneyType.FORM_4,
        filer_name="TestInsider",
        stake_pct=None,
        transaction_value=50_000.0,
        filed_date=filed,
        is_activist=False,
        insider_role="CFO",
        transaction_type="Purchase",
    )


def _ar(
    ticker: str, when: datetime, action: AnalystAction = AnalystAction.UPGRADE
) -> AnalystRating:
    return AnalystRating(
        ticker=ticker,
        firm="GoodFirm",
        rating="Buy",
        prior_rating="Hold",
        action=action,
        price_target=None,
        published_at=when,
        source="yf",
    )


# ---------------------------------------------------------------------------
# LEAK GUARD — the most important test in this file
# ---------------------------------------------------------------------------


def test_leak_guard_future_signals_do_not_affect_score() -> None:
    """A signal dated AFTER the scan date must NOT change the sub-scores."""
    date = datetime(2026, 6, 1)
    future_sm = _sm("NVDA", "2026-09-01")  # filed AFTER date
    future_ar = _ar("NVDA", datetime(2026, 9, 1))  # published AFTER date

    fn_with_future = make_historical_sub_score_fn([future_sm], [future_ar])
    fn_empty = make_historical_sub_score_fn([], [])

    # Future signals must be invisible at `date` — identical to having no signals
    assert fn_with_future("NVDA", date) == fn_empty("NVDA", date)


# ---------------------------------------------------------------------------
# Past signal contribution
# ---------------------------------------------------------------------------


def test_past_signal_does_affect_score() -> None:
    """A past analyst upgrade within the lookback window lifts analyst sub-score."""
    date = datetime(2026, 6, 1)
    past_ar = _ar("NVDA", datetime(2026, 5, 25))  # within lookback, before date
    fn = make_historical_sub_score_fn([], [past_ar])
    scores = fn("NVDA", date)
    assert scores["analyst_signal"] > 5.0  # fresh upgrade → score above neutral


# ---------------------------------------------------------------------------
# build_historical_dataset
# ---------------------------------------------------------------------------


def test_build_dataset_shapes_and_win_flag() -> None:
    """build_historical_dataset returns one sample per (date, ticker)."""
    dates = [datetime(2026, 6, 1)]
    sub_fn = make_historical_sub_score_fn([], [])

    def conv_fn(sub: dict[str, float]) -> float:
        return 5.0

    def fwd_fn(t: str, d: datetime) -> float:
        return 0.08 if t == "AAA" else -0.02

    def bench_fn(d: datetime) -> float:
        return 0.01

    samples = build_historical_dataset(
        dates, ["AAA", "BBB"], sub_fn, conv_fn, fwd_fn, bench_fn
    )
    assert len(samples) == 2

    aaa = next(s for s in samples if s.ticker == "AAA")
    assert aaa.win == 1
    assert aaa.forward_return == 0.08
    assert aaa.benchmark_return == 0.01

    bbb = next(s for s in samples if s.ticker == "BBB")
    assert bbb.win == 0


# ---------------------------------------------------------------------------
# metrics_from_samples
# ---------------------------------------------------------------------------


def test_metrics_from_samples_perfect_ranking() -> None:
    """High conviction == winners → top-decile hit rate 1.0."""
    samples = [
        BacktestSample("A", "2026-06-01", {}, 9.0, 0.10, 0.0, 1),
        BacktestSample("B", "2026-06-01", {}, 8.0, 0.09, 0.0, 1),
        BacktestSample("C", "2026-06-01", {}, 1.0, -0.05, 0.0, 0),
        BacktestSample("D", "2026-06-01", {}, 0.5, -0.06, 0.0, 0),
    ]
    r = metrics_from_samples(samples, decile=0.25)
    assert r["top_decile_hit_rate"] == 1.0
