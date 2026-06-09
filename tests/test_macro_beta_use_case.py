from datetime import datetime, timedelta

from adapters.ml.macro_beta_analyzer import RidgeMacroBetaEstimator
from application.macro_beta_use_case import MacroBetaUseCase


class _H:
    def __init__(self, ticker, shares):
        self.ticker = ticker
        self.shares = shares


def _trend(base, slope, n, start):
    return [(start + timedelta(days=i), base + slope * i) for i in range(n)]


def _provider_factory(series_by_ticker):
    def provider(ticker, start, end):
        return series_by_ticker.get(ticker, [])

    return provider


def _thresholds():
    return {
        "systematic_share_threshold": 0.60,
        "factor_dominance_threshold": 0.25,
        "drift_threshold": 0.50,
    }


def _make_uc(series):
    return MacroBetaUseCase(
        price_provider=_provider_factory(series),
        estimator=RidgeMacroBetaEstimator(alpha=0.2),
        factors=["SPY", "TLT", "UUP", "XLE"],
        alpha=0.2,
        headline_window=252,
        drift_window=63,
        thresholds=_thresholds(),
        history_days=400,
    )


def test_use_case_builds_book_exposure():
    start = datetime(2025, 1, 1)
    n = 320
    series = {
        "SPY": _trend(400, 0.5, n, start),
        "TLT": _trend(90, -0.05, n, start),
        "UUP": _trend(28, 0.0, n, start),
        "XLE": _trend(85, 0.1, n, start),
        "A": _trend(100, 0.4, n, start),
        "B": _trend(50, -0.02, n, start),
    }
    uc = _make_uc(series)
    book = uc.execute([_H("A", 10), _H("B", 20)], datetime(2026, 1, 1))
    assert book is not None
    assert book.total_holdings == 2
    assert book.coverage_holdings == 2
    assert set(book.net_beta_by_factor) == {"SPY", "TLT", "UUP", "XLE"}
    assert 0.0 <= book.systematic_share <= 1.0


def test_use_case_excludes_holding_without_history():
    start = datetime(2025, 1, 1)
    n = 320
    series = {
        "SPY": _trend(400, 0.5, n, start),
        "TLT": _trend(90, -0.05, n, start),
        "UUP": _trend(28, 0.0, n, start),
        "XLE": _trend(85, 0.1, n, start),
        "A": _trend(100, 0.4, n, start),
    }
    uc = _make_uc(series)
    book = uc.execute([_H("A", 10), _H("NEW", 5)], datetime(2026, 1, 1))
    assert book is not None
    assert book.total_holdings == 2
    assert book.coverage_holdings == 1


def test_use_case_all_factors_fail_returns_none():
    uc = _make_uc({})
    book = uc.execute([_H("A", 10)], datetime(2026, 1, 1))
    assert book is None
