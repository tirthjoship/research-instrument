from datetime import date

import pytest

from domain.insider_cluster import EXCLUDED_TRANS_CODES, InsiderTransaction


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
