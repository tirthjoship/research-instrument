from datetime import date, timedelta

from application.insider_cluster_falsification_use_case import (
    InsiderClusterFalsificationUseCase,
)
from domain.insider_cluster import InsiderTransaction


class _FakePort:
    def __init__(self, txns):
        self._txns = txns

    def get_quarter(self, year, quarter):
        return self._txns


def _buy(ticker, cik, d):
    return InsiderTransaction(
        ticker=ticker,
        insider_cik=cik,
        accession=f"acc-{ticker}-{cik}",
        trans_code="P",
        acquired_disp="A",
        shares=100.0,
        price_per_share=5.0,
        filing_date=d,
        trans_date=d,
        equity_swap=False,
        aff10b51=False,
    )


def test_thin_n_when_few_events():
    txns = [_buy("ABC", c, date(2020, 1, 5)) for c in ("1", "2", "3")]
    uc = InsiderClusterFalsificationUseCase(
        port=_FakePort(txns),
        prices=lambda tk: [
            (date(2020, 1, 5) + timedelta(days=i), 10.0, 1000.0) for i in range(40)
        ],
        quarters=[(2020, 1)],
    )
    report = uc.run()
    assert report["verdict"] == "INCONCLUSIVE_THIN_N"
    assert report["n_cluster_events"] == 1
    assert "coverage" in report


def test_c1_no_price_event_enters_coverage_denominator():
    # Two clusters: ABC has prices (resolved), ZZZ has none (delisted/unmapped).
    # C1 fix: the ZZZ no-price event MUST count in the bottom-tercile denominator,
    # so coverage = 1 resolved / 2 total = 0.5 — not a spurious 1.0.
    txns = [_buy("ABC", c, date(2020, 1, 5)) for c in ("1", "2", "3")]
    txns += [_buy("ZZZ", c, date(2020, 1, 6)) for c in ("4", "5", "6")]
    abc = [(date(2020, 1, 5) + timedelta(days=i), 10.0, 1000.0) for i in range(40)]
    iwc = [(date(2020, 1, 5) + timedelta(days=i), 50.0, 1.0) for i in range(40)]

    def prices(tk):
        if tk == "ABC":
            return abc
        if tk == "IWC":
            return iwc
        return []  # ZZZ has no price data at all -> no_price

    uc = InsiderClusterFalsificationUseCase(
        port=_FakePort(txns), prices=prices, quarters=[(2020, 1)]
    )
    report = uc.run()
    assert report["n_cluster_events"] == 2
    assert report["n_no_price"] == 1
    assert report["n_bottom_population"] == 2  # ABC record + ZZZ no-price
    assert report["n_bottom_benchmarked"] == 1  # only ABC
    assert abs(report["coverage"] - 0.5) < 1e-9  # NOT a spurious 1.0


def test_m2_same_ticker_events_binned_per_event_not_per_ticker():
    # Regression for the per-ticker ADV dict collision: one ticker, two cluster
    # events 3 months apart. Old code binned the ticker ONCE (last ADV wins,
    # tercile_counts summed to 1). Per-event binning must count BOTH events.
    txns = [_buy("ABC", c, date(2020, 1, 5)) for c in ("1", "2", "3")]
    txns += [_buy("ABC", c, date(2020, 4, 6)) for c in ("4", "5", "6")]
    uc = InsiderClusterFalsificationUseCase(
        port=_FakePort(txns),
        prices=lambda tk: [
            (date(2020, 1, 1) + timedelta(days=i), 10.0, 1000.0) for i in range(200)
        ],
        quarters=[(2020, 1)],
    )
    report = uc.run()
    assert report["n_cluster_events"] == 2
    counts = report["tercile_counts"]
    assert sum(counts.values()) == 2  # per-EVENT, not per-ticker
    assert report["n_events_binned_below_min_population"] == 2
    assert report["min_tercile_population"] == 30
