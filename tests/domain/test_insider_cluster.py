from datetime import date, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from domain.insider_cluster import (
    EXCLUDED_TRANS_CODES,
    InsiderTransaction,
    detect_clusters,
)


def _txn(**kw):
    base = dict(
        ticker="ABC",
        insider_cik="111",
        trans_code="P",
        acquired_disp="A",
        shares=100.0,
        price_per_share=5.0,
        filing_date=date(2020, 1, 10),
        trans_date=date(2020, 1, 8),
        equity_swap=False,
        aff10b51=False,
    )
    base.update(kw)
    base.setdefault("accession", f"acc-{base['insider_cik']}")
    return InsiderTransaction(**base)


def test_transaction_is_frozen():
    t = _txn()
    with pytest.raises(Exception):
        t.shares = 200.0  # type: ignore[misc]


def test_negative_shares_rejected():
    with pytest.raises(ValueError):
        _txn(shares=-1.0)


def test_excluded_codes_are_locked():
    assert EXCLUDED_TRANS_CODES == {"S", "M", "A", "G", "F", "C", "W"}


def test_three_distinct_insiders_in_window_fires_on_filing_date():
    txns = [
        _txn(insider_cik="1", filing_date=date(2020, 1, 5)),
        _txn(insider_cik="2", filing_date=date(2020, 1, 20)),
        _txn(insider_cik="3", filing_date=date(2020, 1, 31)),
    ]
    events = detect_clusters(txns)
    assert len(events) == 1
    assert events[0].fire_date == date(2020, 1, 31)
    assert events[0].distinct_insiders == 3


def test_same_insider_thrice_does_not_cluster():
    txns = [_txn(insider_cik="1", filing_date=date(2020, 1, d)) for d in (5, 10, 15)]
    assert detect_clusters(txns) == []


def test_excluded_codes_never_count():
    txns = [
        _txn(insider_cik="1"),
        _txn(insider_cik="2"),
        _txn(insider_cik="3", trans_code="S", acquired_disp="D"),
    ]
    assert detect_clusters(txns) == []


def test_aff10b51_and_equity_swap_excluded():
    txns = [
        _txn(insider_cik="1"),
        _txn(insider_cik="2"),
        _txn(insider_cik="3", aff10b51=True),
        _txn(insider_cik="4", equity_swap=True),
    ]
    assert detect_clusters(txns) == []


def test_window_too_wide_does_not_cluster():
    txns = [
        _txn(insider_cik="1", filing_date=date(2020, 1, 1)),
        _txn(insider_cik="2", filing_date=date(2020, 1, 20)),
        _txn(insider_cik="3", filing_date=date(2020, 3, 1)),
    ]
    assert detect_clusters(txns) == []


@given(
    ciks=st.lists(st.sampled_from(["1", "2", "3", "4", "5"]), min_size=0, max_size=12),
)
def test_fire_date_is_always_a_real_filing_date(ciks):
    txns = [
        _txn(insider_cik=c, filing_date=date(2020, 1, 1) + timedelta(days=i))
        for i, c in enumerate(ciks)
    ]
    filing_dates = [t.filing_date for t in txns]
    for ev in detect_clusters(txns):
        assert ev.fire_date in filing_dates
