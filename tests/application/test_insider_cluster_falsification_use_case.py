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
